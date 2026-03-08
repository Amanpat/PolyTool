"""Integration tests for wallet.py, real_client wiring in LiveExecutor,
and RiskManager inventory_skew_limit.

All tests are fully offline: no network calls, secrets, or real CLOB clients.
"""

from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch
from packages.polymarket.simtrader.execution.live_executor import (
    LiveExecutor,
    OrderRequest,
)
from packages.polymarket.simtrader.execution.rate_limiter import TokenBucketRateLimiter
from packages.polymarket.simtrader.execution.risk_manager import RiskConfig, RiskManager
from tools.cli import simtrader


# ===========================================================================
# Helpers
# ===========================================================================


def _make_limiter():
    t = [0.0]

    def clock():
        return t[0]

    def sleep(s):
        t[0] += s

    return TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)


def _make_ks(tripped: bool = False):
    ks = MagicMock()
    ks.is_tripped.return_value = tripped
    if tripped:
        ks.check_or_raise.side_effect = RuntimeError("Kill switch is active")
    else:
        ks.check_or_raise.return_value = None
    return ks


def _make_request() -> OrderRequest:
    return OrderRequest(
        asset_id="tok1",
        side="BUY",
        price=Decimal("0.50"),
        size=Decimal("10"),
    )


# ===========================================================================
# wallet.build_client — ImportError when py_clob_client not installed
# ===========================================================================


class TestBuildClientImportError:
    def test_raises_import_error_when_package_missing(self) -> None:
        """build_client() must raise ImportError with pip install hint."""
        # Temporarily hide py_clob_client from sys.modules
        original = sys.modules.get("py_clob_client")
        sys.modules["py_clob_client"] = None  # type: ignore[assignment]
        # Also hide sub-module used inside wallet._require_clob_client
        original_client = sys.modules.get("py_clob_client.client")
        sys.modules["py_clob_client.client"] = None  # type: ignore[assignment]
        try:
            # Re-import so the guard re-runs
            import importlib

            import packages.polymarket.simtrader.execution.wallet as wallet_mod

            importlib.reload(wallet_mod)

            with pytest.raises(ImportError, match="pip install py-clob-client"):
                wallet_mod.build_client()
        finally:
            # Restore original state
            if original is None:
                sys.modules.pop("py_clob_client", None)
            else:
                sys.modules["py_clob_client"] = original
            if original_client is None:
                sys.modules.pop("py_clob_client.client", None)
            else:
                sys.modules["py_clob_client.client"] = original_client

    def test_raises_import_error_message_contains_hint(self) -> None:
        """ImportError message must mention py-clob-client."""
        with patch.dict(sys.modules, {"py_clob_client": None, "py_clob_client.client": None}):
            import importlib

            import packages.polymarket.simtrader.execution.wallet as wallet_mod

            importlib.reload(wallet_mod)

            with pytest.raises(ImportError) as exc_info:
                wallet_mod.build_client()

            assert "py-clob-client" in str(exc_info.value) or "py_clob_client" in str(
                exc_info.value
            )


# ===========================================================================
# LiveExecutor with real_client — create_order called exactly once
# ===========================================================================


class TestLiveExecutorRealClient:
    def test_real_client_create_order_called_once(self) -> None:
        """With real_client set and dry_run=False, create_order fires exactly once."""
        real_client = MagicMock()
        real_client.create_order.return_value = {"status": "ok", "order_id": "x1"}

        dummy_client = MagicMock()  # should NOT be called

        executor = LiveExecutor(
            clob_client=dummy_client,
            rate_limiter=_make_limiter(),
            kill_switch=_make_ks(),
            dry_run=False,
            real_client=real_client,
        )

        result = executor.place_order(_make_request())

        real_client.create_order.assert_called_once()
        dummy_client.place_order.assert_not_called()
        assert result.submitted is True
        assert result.dry_run is False
        assert result.raw_response == {"status": "ok", "order_id": "x1"}

    def test_real_client_cancel_called(self) -> None:
        """With real_client set, cancel_order uses real_client.cancel."""
        real_client = MagicMock()
        real_client.cancel.return_value = {"status": "ok"}

        dummy_client = MagicMock()

        executor = LiveExecutor(
            clob_client=dummy_client,
            rate_limiter=_make_limiter(),
            kill_switch=_make_ks(),
            dry_run=False,
            real_client=real_client,
        )

        result = executor.cancel_order("order-abc")

        real_client.cancel.assert_called_once_with("order-abc")
        dummy_client.cancel_order.assert_not_called()
        assert result.submitted is True

    def test_real_client_ignored_in_dry_run(self) -> None:
        """Even if real_client is provided, dry_run=True must skip all clients."""
        real_client = MagicMock()
        dummy_client = MagicMock()

        executor = LiveExecutor(
            clob_client=dummy_client,
            rate_limiter=_make_limiter(),
            kill_switch=_make_ks(),
            dry_run=True,
            real_client=real_client,
        )

        result = executor.place_order(_make_request())

        real_client.create_order.assert_not_called()
        dummy_client.place_order.assert_not_called()
        assert result.dry_run is True
        assert result.submitted is False

    def test_no_real_client_falls_back_to_duck_typed_client(self) -> None:
        """Without real_client, the original duck-typed place_order is used."""
        dummy_client = MagicMock()
        dummy_client.place_order.return_value = {"status": "ok"}

        executor = LiveExecutor(
            clob_client=dummy_client,
            rate_limiter=_make_limiter(),
            kill_switch=_make_ks(),
            dry_run=False,
            real_client=None,
        )

        result = executor.place_order(_make_request())

        dummy_client.place_order.assert_called_once()
        assert result.submitted is True


# ===========================================================================
# RiskManager — inventory_skew_limit
# ===========================================================================


class TestRiskManagerInventorySkew:
    def _skew_config(self, skew_limit: str = "100") -> RiskConfig:
        return RiskConfig(
            max_order_notional_usd=Decimal("50"),
            max_position_notional_usd=Decimal("500"),
            daily_loss_cap_usd=Decimal("50"),
            max_inventory_units=Decimal("10000"),
            inventory_skew_limit_usd=Decimal(skew_limit),
        )

    def test_rejects_when_skew_exceeds_limit(self) -> None:
        """After fills that push net notional over skew limit, new orders are rejected."""
        rm = RiskManager(self._skew_config("100"))

        # Fill 200 units at 1.0 on a single asset -> net notional = 200 > 100
        rm.on_fill("tok1", "BUY", Decimal("1.0"), Decimal("200"))

        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("10"))
        assert allowed is False
        assert "inventory_skew_limit" in reason

    def test_allows_when_skew_within_limit(self) -> None:
        """Orders are allowed when net inventory notional is within the skew limit."""
        rm = RiskManager(self._skew_config("500"))

        # Fill 100 units at 1.0 -> net notional = 100 < 500
        rm.on_fill("tok1", "BUY", Decimal("1.0"), Decimal("100"))

        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("10"))
        assert allowed is True
        assert reason == ""

    def test_skew_uses_last_fill_price(self) -> None:
        """net_inventory_notional reflects the most recent fill price per asset."""
        rm = RiskManager(self._skew_config("500"))

        rm.on_fill("tok1", "BUY", Decimal("0.20"), Decimal("200"))  # notional = 40
        assert abs(rm.net_inventory_notional - Decimal("40")) < Decimal("0.01")

        # Price update: same asset fills at higher price
        rm.on_fill("tok1", "BUY", Decimal("0.80"), Decimal("10"))
        # units = 210, last price = 0.80 -> notional = 168
        assert abs(rm.net_inventory_notional - Decimal("168")) < Decimal("0.01")

    def test_net_inventory_notional_zero_initially(self) -> None:
        rm = RiskManager(self._skew_config("100"))
        assert rm.net_inventory_notional == Decimal("0")

    def test_default_skew_limit_is_400(self) -> None:
        config = RiskConfig()
        assert config.inventory_skew_limit_usd == Decimal("400")

    def test_sell_fills_reduce_net_notional(self) -> None:
        """SELL fills reduce position units, lowering net notional."""
        rm = RiskManager(self._skew_config("500"))
        rm.on_fill("tok1", "BUY", Decimal("1.0"), Decimal("300"))  # units=300, notional=300
        rm.on_fill("tok1", "SELL", Decimal("1.0"), Decimal("250"))  # units=50, notional=50
        assert abs(rm.net_inventory_notional - Decimal("50")) < Decimal("0.01")


# ===========================================================================
# simtrader live CLI - Stage 1 live safety flow
# ===========================================================================


class TestSimtraderLiveCliStage1:
    def _gate_registry(self, tmp_path: Path) -> tuple[tuple[str, Path], ...]:
        gate_names = ("replay_gate", "sweep_gate", "shadow_gate", "dry_run_gate")
        return tuple(
            (gate_name, tmp_path / "gates" / gate_name / "gate_passed.json")
            for gate_name in gate_names
        )

    def _close_all_gates(self, gate_registry: tuple[tuple[str, Path], ...]) -> None:
        for _, gate_path in gate_registry:
            gate_path.parent.mkdir(parents=True, exist_ok=True)
            gate_path.write_text("{}", encoding="utf-8")

    def test_live_requires_all_gate_artifacts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gate_registry = self._gate_registry(tmp_path)
        build_client = MagicMock()

        monkeypatch.setattr(simtrader, "_LIVE_GATE_REGISTRY", gate_registry)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.wallet.build_client",
            build_client,
        )

        exit_code = simtrader.main(
            ["live", "--live", "--kill-switch", str(tmp_path / "kill_switch.txt")]
        )
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "GATE NOT CLOSED: replay_gate" in captured.err
        build_client.assert_not_called()

    def test_live_reports_missing_pk_after_gates_close(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gate_registry = self._gate_registry(tmp_path)
        self._close_all_gates(gate_registry)

        monkeypatch.setattr(simtrader, "_LIVE_GATE_REGISTRY", gate_registry)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.wallet.build_client",
            MagicMock(side_effect=KeyError("PK")),
        )

        exit_code = simtrader.main(
            ["live", "--live", "--kill-switch", str(tmp_path / "kill_switch.txt")]
        )
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "PK is not set" in captured.err

    def test_live_requires_explicit_confirm(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gate_registry = self._gate_registry(tmp_path)
        self._close_all_gates(gate_registry)
        build_client = MagicMock(return_value=MagicMock())

        monkeypatch.setattr(simtrader, "_LIVE_GATE_REGISTRY", gate_registry)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.wallet.build_client",
            build_client,
        )
        monkeypatch.setattr("builtins.input", lambda _prompt: "no")

        exit_code = simtrader.main(
            ["live", "--live", "--kill-switch", str(tmp_path / "kill_switch.txt")]
        )
        captured = capsys.readouterr()

        assert exit_code == 1
        assert simtrader._LIVE_WARNING_BANNER in captured.err
        assert "Live mode aborted." in captured.err
        build_client.assert_called_once()

    def test_live_with_confirm_runs_noop_in_live_mode(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        gate_registry = self._gate_registry(tmp_path)
        self._close_all_gates(gate_registry)
        real_client = MagicMock()
        build_client = MagicMock(return_value=real_client)

        monkeypatch.setattr(simtrader, "_LIVE_GATE_REGISTRY", gate_registry)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.wallet.build_client",
            build_client,
        )
        monkeypatch.setattr("builtins.input", lambda _prompt: "CONFIRM")

        exit_code = simtrader.main(
            ["live", "--live", "--kill-switch", str(tmp_path / "kill_switch.txt")]
        )
        captured = capsys.readouterr()

        assert exit_code == 0
        assert '"dry_run": false' in captured.out
        assert simtrader._LIVE_WARNING_BANNER in captured.err
        build_client.assert_called_once()
        real_client.create_order.assert_not_called()

    def test_kill_subcommand_arms_kill_switch(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        kill_switch_path = tmp_path / "artifacts" / "kill_switch.txt"

        exit_code = simtrader.main(
            ["kill", "--kill-switch", str(kill_switch_path)]
        )
        captured = capsys.readouterr()

        assert exit_code == 0
        assert kill_switch_path.read_text(encoding="utf-8") == "1"
        assert "Kill switch armed. All new orders will be blocked." in captured.out
