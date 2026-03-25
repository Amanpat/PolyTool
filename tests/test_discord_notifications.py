"""Offline unit tests for packages.polymarket.notifications.discord.

All tests are fully offline: no real HTTP calls.  requests.post is patched
at the module level so nothing can reach Discord even if DISCORD_WEBHOOK_URL
is accidentally set in the test environment.

Also covers the LiveRunner notifier integration points.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.polymarket.notifications.discord import (
    notify_gate_result,
    notify_kill_switch,
    notify_risk_halt,
    notify_session_error,
    notify_session_start,
    notify_session_stop,
    post_message,
)
from packages.polymarket.simtrader.execution.live_runner import LiveRunConfig, LiveRunner
from packages.polymarket.simtrader.execution.risk_manager import RiskConfig, RiskManager
from tools.cli import simtrader as simtrader_cli

import packages.polymarket.notifications.discord as discord_module


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FAKE_URL = "https://discord.example.com/api/webhooks/123/token"


def _mock_post(ok: bool = True):
    """Return a mock for requests.post that simulates a 200 or non-200 response."""
    mock_resp = MagicMock()
    mock_resp.ok = ok
    return patch(
        "packages.polymarket.notifications.discord.requests.post",
        return_value=mock_resp,
    )


# ===========================================================================
# post_message — core transport
# ===========================================================================


class TestPostMessage:
    def test_returns_false_when_no_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        assert post_message("hello") is False

    def test_returns_false_when_url_empty_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
        assert post_message("hello") is False

    def test_returns_true_on_http_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", _FAKE_URL)
        with _mock_post(ok=True) as mock_post:
            result = post_message("hello")
        assert result is True
        mock_post.assert_called_once()

    def test_posts_correct_json_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", _FAKE_URL)
        with _mock_post(ok=True) as mock_post:
            post_message("test content")
        _, kwargs = mock_post.call_args
        assert kwargs["json"] == {"content": "test content"}

    def test_returns_false_on_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", _FAKE_URL)
        with _mock_post(ok=False):
            result = post_message("hello")
        assert result is False

    def test_returns_false_on_network_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", _FAKE_URL)
        with patch(
            "packages.polymarket.notifications.discord.requests.post",
            side_effect=ConnectionError("no route"),
        ):
            result = post_message("hello")
        assert result is False

    def test_webhook_url_kwarg_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        override = "https://override.example.com/webhook"
        with _mock_post(ok=True) as mock_post:
            result = post_message("hi", webhook_url=override)
        assert result is True
        mock_post.assert_called_once_with(
            override,
            json={"content": "hi"},
            timeout=5,
        )


# ===========================================================================
# notify_gate_result
# ===========================================================================


class TestNotifyGateResult:
    def test_pass_message_contains_pass_label(self) -> None:
        with _mock_post(ok=True) as mock_post:
            result = notify_gate_result("replay", True, commit="abc123", webhook_url=_FAKE_URL)
        assert result is True
        body = mock_post.call_args[1]["json"]["content"]
        assert "PASSED" in body
        assert "abc123" in body
        assert "Replay" in body

    def test_fail_message_contains_fail_label(self) -> None:
        with _mock_post(ok=True) as mock_post:
            result = notify_gate_result(
                "sweep",
                False,
                commit="def456",
                detail="profitable_fraction: 0.0",
                webhook_url=_FAKE_URL,
            )
        assert result is True
        body = mock_post.call_args[1]["json"]["content"]
        assert "FAILED" in body
        assert "def456" in body
        assert "profitable_fraction" in body

    def test_no_url_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
        assert notify_gate_result("dry_run", True) is False

    def test_gate_name_underscores_converted(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_gate_result("dry_run", True, webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "Dry Run" in body

    def test_detail_omitted_when_none(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_gate_result("replay", True, webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "None" not in body


# ===========================================================================
# notify_session_start
# ===========================================================================


class TestNotifySessionStart:
    def test_dry_run_label(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_session_start("live", "market_maker_v0", "tok1", dry_run=True, webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "DRY-RUN" in body
        assert "market_maker_v0" in body
        assert "tok1" in body

    def test_live_label_when_not_dry_run(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_session_start("live", "market_maker_v0", "tok1", dry_run=False, webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "LIVE" in body


# ===========================================================================
# notify_session_stop
# ===========================================================================


class TestNotifySessionStop:
    def test_basic_fields_present(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_session_stop("live", "market_maker_v0", "tok1", webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "Session Stop" in body
        assert "market_maker_v0" in body

    def test_summary_stats_included_when_provided(self) -> None:
        summary = {"attempted": 10, "submitted": 8, "rejected": 2}
        with _mock_post(ok=True) as mock_post:
            notify_session_stop("live", "market_maker_v0", "tok1", summary=summary, webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "attempted: 10" in body
        assert "submitted: 8" in body
        assert "rejected: 2" in body


# ===========================================================================
# notify_session_error
# ===========================================================================


class TestNotifySessionError:
    def test_message_contains_context_and_exception(self) -> None:
        exc = ValueError("something went wrong")
        with _mock_post(ok=True) as mock_post:
            notify_session_error("WS reconnect", exc, webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "Runtime Error" in body
        assert "WS reconnect" in body
        assert "something went wrong" in body


# ===========================================================================
# notify_kill_switch
# ===========================================================================


class TestNotifyKillSwitch:
    def test_message_contains_path(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_kill_switch("artifacts/kill_switch.txt", webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "Kill Switch Tripped" in body
        assert "artifacts/kill_switch.txt" in body

    def test_context_included_when_provided(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_kill_switch(
                "artifacts/kill_switch.txt",
                context="run_once pre-tick check",
                webhook_url=_FAKE_URL,
            )
        body = mock_post.call_args[1]["json"]["content"]
        assert "run_once pre-tick check" in body


# ===========================================================================
# notify_risk_halt
# ===========================================================================


class TestNotifyRiskHalt:
    def test_message_contains_reason(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_risk_halt(
                "risk: daily net loss 16.50 exceeds daily_loss_cap_usd 15",
                webhook_url=_FAKE_URL,
            )
        body = mock_post.call_args[1]["json"]["content"]
        assert "Risk Manager Halt" in body
        assert "daily net loss" in body

    def test_context_included_when_provided(self) -> None:
        with _mock_post(ok=True) as mock_post:
            notify_risk_halt("risk: halt reason", context="asset_id=abc", webhook_url=_FAKE_URL)
        body = mock_post.call_args[1]["json"]["content"]
        assert "asset_id=abc" in body


# ===========================================================================
# LiveRunner notifier integration
# ===========================================================================


class TestLiveRunnerNotifier:
    """Tests for notifier hooks in LiveRunner.run_once()."""

    def _make_runner(self, ks_path: Path, notifier: object) -> LiveRunner:
        config = LiveRunConfig(
            kill_switch_path=ks_path,
            notifier=notifier,
        )
        return LiveRunner(config)

    def test_kill_switch_notified_on_trip(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        ks_path.write_text("1")  # arm immediately
        notifier = MagicMock()
        runner = self._make_runner(ks_path, notifier)

        with pytest.raises(RuntimeError):
            runner.run_once(lambda: [])

        notifier.notify_kill_switch.assert_called_once()
        call_args = notifier.notify_kill_switch.call_args
        assert str(ks_path) in call_args[0][0]

    def test_kill_switch_notified_only_once(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        ks_path.write_text("1")
        notifier = MagicMock()
        runner = self._make_runner(ks_path, notifier)

        for _ in range(3):
            with pytest.raises(RuntimeError):
                runner.run_once(lambda: [])

        assert notifier.notify_kill_switch.call_count == 1

    def test_no_kill_switch_notification_when_clear(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        notifier = MagicMock()
        runner = self._make_runner(ks_path, notifier)

        runner.run_once(lambda: [])

        notifier.notify_kill_switch.assert_not_called()

    def test_risk_halt_notified_when_daily_loss_exceeded(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        notifier = MagicMock()
        config = LiveRunConfig(
            kill_switch_path=ks_path,
            notifier=notifier,
            risk_config=RiskConfig(daily_loss_cap_usd=Decimal("1")),
        )
        runner = LiveRunner(config)

        # Force the risk manager into a halt state by simulating a big fee
        runner._risk._total_fees_paid = Decimal("2")
        runner._risk._daily_realized_pnl = Decimal("0")

        runner.run_once(lambda: [])

        notifier.notify_risk_halt.assert_called_once()
        call_args = notifier.notify_risk_halt.call_args
        assert "daily" in call_args[0][0].lower() or "risk" in call_args[0][0].lower()

    def test_risk_halt_notified_only_once(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        notifier = MagicMock()
        config = LiveRunConfig(
            kill_switch_path=ks_path,
            notifier=notifier,
            risk_config=RiskConfig(daily_loss_cap_usd=Decimal("1")),
        )
        runner = LiveRunner(config)
        runner._risk._total_fees_paid = Decimal("2")

        for _ in range(3):
            runner.run_once(lambda: [])

        assert notifier.notify_risk_halt.call_count == 1

    def test_no_risk_halt_notification_when_healthy(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        notifier = MagicMock()
        runner = self._make_runner(ks_path, notifier)

        runner.run_once(lambda: [])

        notifier.notify_risk_halt.assert_not_called()

    def test_notifier_exception_does_not_crash_runner(self, tmp_path: Path) -> None:
        ks_path = tmp_path / "ks.txt"
        ks_path.write_text("1")
        notifier = MagicMock()
        notifier.notify_kill_switch.side_effect = RuntimeError("discord down")
        runner = self._make_runner(ks_path, notifier)

        # Should re-raise the kill-switch RuntimeError, NOT the notifier error
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            runner.run_once(lambda: [])

    def test_no_notifier_does_not_crash(self, tmp_path: Path) -> None:
        """LiveRunner with notifier=None should never call notification methods."""
        ks_path = tmp_path / "ks.txt"
        config = LiveRunConfig(kill_switch_path=ks_path, notifier=None)
        runner = LiveRunner(config)
        runner.run_once(lambda: [])  # should not raise


class _FakeCliLiveRunnerSuccess:
    last_config = None

    def __init__(self, config, *, executor=None, risk_manager=None) -> None:
        self.config = config
        type(self).last_config = config

    def run_once(self, strategy_fn):
        strategy_fn()
        return {
            "attempted": 0,
            "submitted": 0,
            "rejected": 0,
            "dry_run": self.config.dry_run,
            "reasons": [],
        }


class _FakeCliLiveRunnerError:
    def __init__(self, config, *, executor=None, risk_manager=None) -> None:
        self.config = config

    def run_once(self, strategy_fn):
        strategy_fn()
        raise RuntimeError("tick failed")


class TestSimTraderCliDiscordLifecycle:
    def test_live_cli_notifies_session_start_and_stop(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        start = MagicMock(return_value=True)
        stop = MagicMock(return_value=True)
        error = MagicMock(return_value=True)

        monkeypatch.setattr(discord_module, "notify_session_start", start)
        monkeypatch.setattr(discord_module, "notify_session_stop", stop)
        monkeypatch.setattr(discord_module, "notify_session_error", error)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.live_runner.LiveRunner",
            _FakeCliLiveRunnerSuccess,
        )

        exit_code = simtrader_cli.main(["live", "--kill-switch", str(tmp_path / "kill_switch.txt")])

        assert exit_code == 0
        assert _FakeCliLiveRunnerSuccess.last_config.notifier is discord_module
        start.assert_called_once_with("live", "noop", "unknown", dry_run=True)
        stop.assert_called_once()
        stop_args = stop.call_args
        assert stop_args.args == ("live", "noop", "unknown")
        assert stop_args.kwargs["summary"] == {
            "attempted": 0,
            "submitted": 0,
            "rejected": 0,
            "dry_run": True,
            "reasons": [],
        }
        error.assert_not_called()

    def test_live_cli_notifies_session_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        start = MagicMock(return_value=True)
        stop = MagicMock(return_value=True)
        error = MagicMock(return_value=True)

        monkeypatch.setattr(discord_module, "notify_session_start", start)
        monkeypatch.setattr(discord_module, "notify_session_stop", stop)
        monkeypatch.setattr(discord_module, "notify_session_error", error)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.live_runner.LiveRunner",
            _FakeCliLiveRunnerError,
        )

        exit_code = simtrader_cli.main(["live", "--kill-switch", str(tmp_path / "kill_switch.txt")])

        assert exit_code == 1
        start.assert_called_once_with("live", "noop", "unknown", dry_run=True)
        stop.assert_not_called()
        error.assert_called_once()
        error_args = error.call_args
        assert "simtrader live run_once" in error_args.args[0]
        assert "strategy=noop" in error_args.args[0]
        assert "asset_id=unknown" in error_args.args[0]
        assert isinstance(error_args.args[1], RuntimeError)
        assert str(error_args.args[1]) == "tick failed"

    def test_live_cli_start_stop_notification_failures_are_non_fatal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            discord_module,
            "notify_session_start",
            MagicMock(side_effect=RuntimeError("discord down")),
        )
        monkeypatch.setattr(
            discord_module,
            "notify_session_stop",
            MagicMock(side_effect=RuntimeError("discord down")),
        )
        error = MagicMock(return_value=True)

        monkeypatch.setattr(discord_module, "notify_session_error", error)
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.live_runner.LiveRunner",
            _FakeCliLiveRunnerSuccess,
        )

        exit_code = simtrader_cli.main(["live", "--kill-switch", str(tmp_path / "kill_switch.txt")])

        assert exit_code == 0
        error.assert_not_called()

    def test_live_cli_error_notification_failure_is_non_fatal(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        start = MagicMock(return_value=True)
        stop = MagicMock(return_value=True)

        monkeypatch.setattr(discord_module, "notify_session_start", start)
        monkeypatch.setattr(discord_module, "notify_session_stop", stop)
        monkeypatch.setattr(
            discord_module,
            "notify_session_error",
            MagicMock(side_effect=RuntimeError("discord down")),
        )
        monkeypatch.setattr(
            "packages.polymarket.simtrader.execution.live_runner.LiveRunner",
            _FakeCliLiveRunnerError,
        )

        exit_code = simtrader_cli.main(["live", "--kill-switch", str(tmp_path / "kill_switch.txt")])

        assert exit_code == 1
        start.assert_called_once()
        stop.assert_not_called()
