"""Offline unit tests for the live execution layer primitives.

All tests are fully offline: no network calls, no real sleeps (clocks are
injected or monkeypatched), no real file I/O beyond tmp_path.
"""

from __future__ import annotations

import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch
from packages.polymarket.simtrader.execution.live_executor import (
    LiveExecutor,
    OrderRequest,
    OrderResult,
)
from packages.polymarket.simtrader.execution.live_runner import LiveRunConfig, LiveRunner
from packages.polymarket.simtrader.execution.rate_limiter import TokenBucketRateLimiter
from packages.polymarket.simtrader.execution.risk_manager import RiskConfig, RiskManager


# ===========================================================================
# KillSwitch
# ===========================================================================


class TestFileBasedKillSwitch:
    def test_not_tripped_when_file_absent(self, tmp_path: Path) -> None:
        ks = FileBasedKillSwitch(tmp_path / "ks.txt")
        assert ks.is_tripped() is False

    def test_not_tripped_when_file_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "ks.txt"
        p.write_text("", encoding="utf-8")
        ks = FileBasedKillSwitch(p)
        assert ks.is_tripped() is False

    @pytest.mark.parametrize("content", ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON"])
    def test_tripped_on_truthy_values(self, tmp_path: Path, content: str) -> None:
        p = tmp_path / "ks.txt"
        p.write_text(content, encoding="utf-8")
        ks = FileBasedKillSwitch(p)
        assert ks.is_tripped() is True

    @pytest.mark.parametrize("content", ["0", "false", "no", "off", "nope"])
    def test_not_tripped_on_falsy_values(self, tmp_path: Path, content: str) -> None:
        p = tmp_path / "ks.txt"
        p.write_text(content, encoding="utf-8")
        ks = FileBasedKillSwitch(p)
        assert ks.is_tripped() is False

    def test_check_or_raise_does_not_raise_when_clear(self, tmp_path: Path) -> None:
        ks = FileBasedKillSwitch(tmp_path / "ks.txt")
        ks.check_or_raise()  # should not raise

    def test_check_or_raise_raises_when_tripped(self, tmp_path: Path) -> None:
        p = tmp_path / "ks.txt"
        p.write_text("1", encoding="utf-8")
        ks = FileBasedKillSwitch(p)
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            ks.check_or_raise()

    def test_error_message_contains_path(self, tmp_path: Path) -> None:
        p = tmp_path / "my_switch.txt"
        p.write_text("true", encoding="utf-8")
        ks = FileBasedKillSwitch(p)
        with pytest.raises(RuntimeError, match="my_switch.txt"):
            ks.check_or_raise()

    def test_trip_then_clear(self, tmp_path: Path) -> None:
        p = tmp_path / "ks.txt"
        p.write_text("1", encoding="utf-8")
        ks = FileBasedKillSwitch(p)
        assert ks.is_tripped() is True
        p.unlink()
        assert ks.is_tripped() is False


# ===========================================================================
# RateLimiter
# ===========================================================================


class TestTokenBucketRateLimiter:
    def _make_fake_clock(self, start: float = 0.0):
        """Returns a mutable fake clock and a no-op sleep."""
        t = [start]

        def clock():
            return t[0]

        def advance(secs: float):
            t[0] += secs

        sleeps: list[float] = []

        def sleep(secs: float):
            t[0] += secs  # advance clock when sleep is called
            sleeps.append(secs)

        return clock, advance, sleep, sleeps

    def test_invalid_max_per_minute(self) -> None:
        with pytest.raises(ValueError):
            TokenBucketRateLimiter(0)

    def test_try_acquire_succeeds_when_tokens_available(self) -> None:
        clock, _, sleep, _ = self._make_fake_clock()
        rl = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        assert rl.try_acquire(1) is True

    def test_try_acquire_fails_when_bucket_empty(self) -> None:
        clock, advance, sleep, _ = self._make_fake_clock()
        rl = TokenBucketRateLimiter(2, _clock=clock, _sleep=sleep)
        # Drain the bucket (starts full at 2 tokens)
        assert rl.try_acquire(2) is True
        assert rl.try_acquire(1) is False

    def test_try_acquire_refills_over_time(self) -> None:
        clock, advance, sleep, _ = self._make_fake_clock()
        rl = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        # Drain fully
        assert rl.try_acquire(60) is True
        assert rl.try_acquire(1) is False
        # Advance 2 seconds (= 2 tokens at 1/s)
        advance(2.0)
        assert rl.try_acquire(2) is True

    def test_acquire_does_not_call_sleep_when_tokens_available(self) -> None:
        clock, _, sleep, sleeps = self._make_fake_clock()
        rl = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        rl.acquire(1)
        assert sleeps == []

    def test_acquire_sleeps_minimum_when_tokens_insufficient(self) -> None:
        clock, advance, sleep, sleeps = self._make_fake_clock()
        rl = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        # Drain all tokens
        rl.try_acquire(60)
        # acquire(1) should sleep briefly then succeed
        rl.acquire(1)
        assert len(sleeps) >= 1
        assert sleeps[0] > 0

    def test_invalid_n_raises(self) -> None:
        clock, _, sleep, _ = self._make_fake_clock()
        rl = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        with pytest.raises(ValueError):
            rl.try_acquire(0)
        with pytest.raises(ValueError):
            rl.acquire(0)

    def test_bucket_does_not_overflow_max(self) -> None:
        clock, advance, sleep, _ = self._make_fake_clock()
        rl = TokenBucketRateLimiter(10, _clock=clock, _sleep=sleep)
        advance(10000.0)  # huge time advance
        rl._refill()
        assert rl._tokens <= 10.0


# ===========================================================================
# RiskManager
# ===========================================================================


class TestRiskManager:
    def _small_config(self) -> RiskConfig:
        return RiskConfig(
            max_order_notional_usd=Decimal("10"),
            max_position_notional_usd=Decimal("20"),
            daily_loss_cap_usd=Decimal("5"),
            max_inventory_units=Decimal("100"),
        )

    def test_allows_valid_order(self) -> None:
        rm = RiskManager(self._small_config())
        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("10"))
        assert allowed is True
        assert reason == ""

    def test_rejects_when_order_notional_too_large(self) -> None:
        rm = RiskManager(self._small_config())
        # 0.50 * 25 = 12.50 > 10
        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("25"))
        assert allowed is False
        assert "max_order_notional_usd" in reason

    def test_rejects_when_position_notional_exceeded(self) -> None:
        rm = RiskManager(self._small_config())
        # First buy: 0.50 * 10 = 5 (ok)
        rm.on_fill("tok1", "BUY", Decimal("0.50"), Decimal("10"))
        # Second buy: 0.50 * 10 = 5, total = 10 (ok)
        rm.on_fill("tok1", "BUY", Decimal("0.50"), Decimal("10"))
        # Third buy would bring projected notional to 15 -> 15 (ok) but 20 is cap
        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("25"))
        # 25 * 0.50 = 12.5 > 10, rejected by order notional first
        assert allowed is False

    def test_rejects_when_projected_position_exceeds_cap(self) -> None:
        rm = RiskManager(self._small_config())
        # Fill 15 units at 1.0 notional = 15 (under 20 cap)
        rm.on_fill("tok1", "BUY", Decimal("1.0"), Decimal("15"))
        # Now try to buy 10 more at 1.0: projected = 25 > 20
        allowed, reason = rm.check_order("tok1", "BUY", Decimal("1.0"), Decimal("10"))
        assert allowed is False
        assert "max_position_notional_usd" in reason

    def test_rejects_when_inventory_cap_exceeded(self) -> None:
        rm = RiskManager(self._small_config())
        # First fill takes us to 99 units
        rm.on_fill("tok1", "BUY", Decimal("0.05"), Decimal("99"))
        # Now try to buy 10 more: 99 + 10 = 109 > 100
        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.05"), Decimal("10"))
        assert allowed is False
        assert "max_inventory_units" in reason

    def test_rejects_non_positive_price(self) -> None:
        rm = RiskManager(self._small_config())
        allowed, _ = rm.check_order("tok1", "BUY", Decimal("0"), Decimal("5"))
        assert allowed is False

    def test_rejects_non_positive_size(self) -> None:
        rm = RiskManager(self._small_config())
        allowed, _ = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("0"))
        assert allowed is False

    def test_should_halt_returns_false_initially(self) -> None:
        rm = RiskManager(self._small_config())
        halted, _ = rm.should_halt()
        assert halted is False

    def test_daily_loss_cap_triggers_halt(self) -> None:
        rm = RiskManager(self._small_config())
        # Pay fees of 6 > daily_loss_cap_usd=5
        rm.on_fill("tok1", "BUY", Decimal("0.50"), Decimal("2"), fee=Decimal("6"))
        halted, reason = rm.should_halt()
        assert halted is True
        assert "daily_loss_cap_usd" in reason

    def test_halted_state_blocks_new_orders(self) -> None:
        rm = RiskManager(self._small_config())
        rm.on_fill("tok1", "BUY", Decimal("0.50"), Decimal("2"), fee=Decimal("6"))
        allowed, reason = rm.check_order("tok1", "BUY", Decimal("0.50"), Decimal("1"))
        assert allowed is False
        assert "daily_loss_cap_usd" in reason

    def test_halt_is_sticky(self) -> None:
        rm = RiskManager(self._small_config())
        rm.on_fill("tok1", "BUY", Decimal("0.50"), Decimal("2"), fee=Decimal("6"))
        # Even if we query twice, still halted
        rm.should_halt()
        halted, _ = rm.should_halt()
        assert halted is True

    def test_default_config_is_conservative(self) -> None:
        config = RiskConfig()
        assert config.max_order_notional_usd == Decimal("25")
        assert config.max_position_notional_usd == Decimal("100")
        assert config.daily_loss_cap_usd == Decimal("15")
        assert config.max_inventory_units == Decimal("1000")


# ===========================================================================
# LiveExecutor
# ===========================================================================


class TestLiveExecutor:
    def _make_executor(self, dry_run: bool = True, ks_tripped: bool = False):
        ks = MagicMock()
        ks.is_tripped.return_value = ks_tripped
        if ks_tripped:
            ks.check_or_raise.side_effect = RuntimeError("Kill switch is active: some/path")
        else:
            ks.check_or_raise.return_value = None

        clock_t = [0.0]

        def clock():
            return clock_t[0]

        def sleep(s):
            clock_t[0] += s

        limiter = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        client = MagicMock()
        client.place_order.return_value = {"status": "ok"}
        client.cancel_order.return_value = {"status": "ok"}

        executor = LiveExecutor(
            clob_client=client,
            rate_limiter=limiter,
            kill_switch=ks,
            dry_run=dry_run,
        )
        return executor, ks, limiter, client

    def _make_request(self) -> OrderRequest:
        return OrderRequest(
            asset_id="abc123",
            side="BUY",
            price=Decimal("0.50"),
            size=Decimal("10"),
        )

    def test_dry_run_does_not_call_client(self) -> None:
        executor, _, _, client = self._make_executor(dry_run=True)
        result = executor.place_order(self._make_request())
        assert result.submitted is False
        assert result.dry_run is True
        assert result.reason == "dry_run"
        client.place_order.assert_not_called()

    def test_kill_switch_blocks_dry_run(self) -> None:
        executor, ks, _, client = self._make_executor(dry_run=True, ks_tripped=True)
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            executor.place_order(self._make_request())
        client.place_order.assert_not_called()

    def test_kill_switch_blocks_live_run(self) -> None:
        executor, ks, _, client = self._make_executor(dry_run=False, ks_tripped=True)
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            executor.place_order(self._make_request())
        client.place_order.assert_not_called()

    def test_live_run_calls_client_exactly_once(self) -> None:
        executor, _, _, client = self._make_executor(dry_run=False)
        result = executor.place_order(self._make_request())
        assert result.submitted is True
        assert result.dry_run is False
        client.place_order.assert_called_once()

    def test_live_run_passes_correct_args_to_client(self) -> None:
        executor, _, _, client = self._make_executor(dry_run=False)
        req = self._make_request()
        executor.place_order(req)
        client.place_order.assert_called_once_with(
            req.asset_id, req.side, req.price, req.size, req.post_only
        )

    def test_rate_limiter_acquire_called_in_live_mode(self) -> None:
        executor, _, limiter, client = self._make_executor(dry_run=False)
        with patch.object(limiter, "acquire", wraps=limiter.acquire) as mock_acquire:
            executor.place_order(self._make_request())
        mock_acquire.assert_called_once_with(1)

    def test_rate_limiter_not_called_in_dry_run(self) -> None:
        executor, _, limiter, client = self._make_executor(dry_run=True)
        with patch.object(limiter, "acquire", wraps=limiter.acquire) as mock_acquire:
            executor.place_order(self._make_request())
        mock_acquire.assert_not_called()

    def test_cancel_order_dry_run(self) -> None:
        executor, _, _, client = self._make_executor(dry_run=True)
        result = executor.cancel_order("order-123")
        assert result.submitted is False
        assert result.dry_run is True
        client.cancel_order.assert_not_called()

    def test_cancel_order_live(self) -> None:
        executor, _, _, client = self._make_executor(dry_run=False)
        result = executor.cancel_order("order-123")
        assert result.submitted is True
        client.cancel_order.assert_called_once_with("order-123")

    def test_kill_switch_checked_before_cancel(self) -> None:
        executor, ks, _, client = self._make_executor(dry_run=False, ks_tripped=True)
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            executor.cancel_order("order-123")


# ===========================================================================
# LiveRunner
# ===========================================================================


class TestLiveRunner:
    def _make_executor(self, dry_run: bool = True, ks_tripped: bool = False):
        ks = MagicMock()
        if ks_tripped:
            ks.check_or_raise.side_effect = RuntimeError("Kill switch is active: path")
        else:
            ks.check_or_raise.return_value = None
        ks.is_tripped.return_value = ks_tripped

        clock_t = [0.0]

        def clock():
            return clock_t[0]

        def sleep(s):
            clock_t[0] += s

        limiter = TokenBucketRateLimiter(60, _clock=clock, _sleep=sleep)
        client = MagicMock()
        client.place_order.return_value = {"status": "ok"}

        executor = LiveExecutor(
            clob_client=client,
            rate_limiter=limiter,
            kill_switch=ks,
            dry_run=dry_run,
        )
        return executor, ks, client

    def _make_request(self, price="0.50", size="10") -> OrderRequest:
        return OrderRequest(
            asset_id="tok1",
            side="BUY",
            price=Decimal(price),
            size=Decimal(size),
        )

    def test_dry_run_produces_submitted_zero(self) -> None:
        executor, _, _ = self._make_executor(dry_run=True)
        rm = RiskManager(RiskConfig())
        runner = LiveRunner(LiveRunConfig(dry_run=True), executor=executor, risk_manager=rm)
        summary = runner.run_once(lambda: [self._make_request()])
        assert summary["submitted"] == 0
        assert summary["dry_run"] is True
        assert summary["attempted"] == 1

    def test_risk_rejection_prevents_executor_call(self) -> None:
        executor, _, client = self._make_executor(dry_run=False)
        config = RiskConfig(max_order_notional_usd=Decimal("1"))  # very small cap
        rm = RiskManager(config)
        runner = LiveRunner(LiveRunConfig(dry_run=False), executor=executor, risk_manager=rm)
        # price=0.50 * size=10 = 5.0 > 1.0 -> rejected
        summary = runner.run_once(lambda: [self._make_request()])
        assert summary["rejected"] == 1
        assert summary["submitted"] == 0
        client.place_order.assert_not_called()

    def test_kill_switch_raises_before_strategy(self) -> None:
        executor, _, _ = self._make_executor(dry_run=True, ks_tripped=True)
        rm = RiskManager(RiskConfig())
        runner = LiveRunner(LiveRunConfig(dry_run=True), executor=executor, risk_manager=rm)
        with pytest.raises(RuntimeError, match="Kill switch is active"):
            runner.run_once(lambda: [self._make_request()])

    def test_empty_strategy_returns_zero_counts(self) -> None:
        executor, _, _ = self._make_executor(dry_run=True)
        rm = RiskManager(RiskConfig())
        runner = LiveRunner(LiveRunConfig(dry_run=True), executor=executor, risk_manager=rm)
        summary = runner.run_once(lambda: [])
        assert summary["attempted"] == 0
        assert summary["submitted"] == 0
        assert summary["rejected"] == 0

    def test_multiple_orders_risk_partial_rejection(self) -> None:
        executor, _, client = self._make_executor(dry_run=True)
        config = RiskConfig(max_order_notional_usd=Decimal("10"))
        rm = RiskManager(config)
        runner = LiveRunner(LiveRunConfig(dry_run=True), executor=executor, risk_manager=rm)
        # Order 1: 0.50 * 10 = 5.0 -> ok
        # Order 2: 0.50 * 25 = 12.5 -> rejected
        requests = [
            self._make_request(price="0.50", size="10"),
            self._make_request(price="0.50", size="25"),
        ]
        summary = runner.run_once(lambda: requests)
        assert summary["attempted"] == 2
        assert summary["rejected"] == 1
        assert len(summary["reasons"]) == 1

    def test_summary_contains_reasons_list(self) -> None:
        executor, _, _ = self._make_executor(dry_run=True)
        config = RiskConfig(max_order_notional_usd=Decimal("1"))
        rm = RiskManager(config)
        runner = LiveRunner(LiveRunConfig(dry_run=True), executor=executor, risk_manager=rm)
        summary = runner.run_once(lambda: [self._make_request()])
        assert isinstance(summary["reasons"], list)
        assert len(summary["reasons"]) == 1
        assert "max_order_notional_usd" in summary["reasons"][0]

    def test_live_run_config_defaults(self) -> None:
        config = LiveRunConfig()
        assert config.dry_run is True
        assert config.rate_limit_per_min == 30
        assert "kill_switch" in str(config.kill_switch_path)
        assert config.clob_client is None

    def test_live_runner_uses_config_clob_client_when_live(self, tmp_path: Path) -> None:
        real_client = MagicMock()
        real_client.create_order.return_value = {"status": "ok", "order_id": "live-1"}

        config = LiveRunConfig(
            dry_run=False,
            kill_switch_path=tmp_path / "kill_switch.txt",
            clob_client=real_client,
        )
        runner = LiveRunner(config)

        summary = runner.run_once(lambda: [self._make_request()])

        real_client.create_order.assert_called_once()
        assert summary["submitted"] == 1
        assert summary["dry_run"] is False
