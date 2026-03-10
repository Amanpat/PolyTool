"""Tests for adverse-selection signals and the RiskManager integration."""

from __future__ import annotations

import pytest
from decimal import Decimal
from unittest.mock import MagicMock

from packages.polymarket.simtrader.execution.adverse_selection import (
    AdverseSelectionGuard,
    GuardResult,
    MMWithdrawalSignal,
    OFISignal,
    SignalResult,
)
from packages.polymarket.simtrader.execution.risk_manager import RiskConfig, RiskManager


# ===========================================================================
# Helpers
# ===========================================================================


def _make_book(best_bid=None, best_ask=None, bids=None, asks=None):
    """Build a mock book with L2Book-compatible interface."""
    book = MagicMock()
    book.best_bid = best_bid
    book.best_ask = best_ask
    book.top_bids.return_value = bids or []
    book.top_asks.return_value = asks or []
    return book


def _push_ofi_ticks(signal: OFISignal, directions: list[str]) -> None:
    """Push mid-price moves: 'up', 'down', or 'flat'."""
    mid = 0.50
    signal.on_book_update(mid)  # seed _last_mid
    for d in directions:
        if d == "up":
            mid += 0.01
        elif d == "down":
            mid -= 0.01
        # 'flat' → same mid
        signal.on_book_update(mid)


# ===========================================================================
# OFISignal — construction guards
# ===========================================================================


def test_ofi_invalid_window():
    with pytest.raises(ValueError, match="window_ticks"):
        OFISignal(window_ticks=1)


def test_ofi_invalid_threshold():
    with pytest.raises(ValueError, match="threshold"):
        OFISignal(threshold=0.0)


def test_ofi_invalid_min_samples():
    with pytest.raises(ValueError, match="min_samples"):
        OFISignal(min_samples=0)


# ===========================================================================
# OFISignal — cold start and warming-up
# ===========================================================================


def test_ofi_cold_start():
    sig = OFISignal()
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "cold_start"


def test_ofi_warming_up():
    sig = OFISignal(min_samples=5)
    # Push 3 up ticks (less than min_samples=5)
    _push_ofi_ticks(sig, ["up", "up", "up"])
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "warming_up"
    assert result.metadata["classified_ticks"] == 3


def test_ofi_none_mid_skipped():
    """None mid values are skipped; _last_mid is preserved across gaps."""
    sig = OFISignal(min_samples=1)
    sig.on_book_update(0.50)   # seeds _last_mid
    sig.on_book_update(None)   # should skip — no tick, no _last_mid update
    sig.on_book_update(0.51)   # should compare to 0.50 → up tick
    result = sig.check()
    assert result.metadata.get("buy_ticks", 0) == 1


# ===========================================================================
# OFISignal — trigger and no-trigger
# ===========================================================================


def test_ofi_triggers_on_heavy_buy_imbalance():
    """All-up moves → imbalance = 1.0 > threshold → trigger."""
    sig = OFISignal(window_ticks=30, threshold=0.70, min_samples=10)
    _push_ofi_ticks(sig, ["up"] * 15)
    result = sig.check()
    assert result.triggered
    assert "ofi" in result.reason
    assert result.metadata["buy_ticks"] > 0
    assert result.metadata["sell_ticks"] == 0


def test_ofi_triggers_on_heavy_sell_imbalance():
    """All-down moves → imbalance = 1.0 > threshold → trigger."""
    sig = OFISignal(window_ticks=30, threshold=0.70, min_samples=10)
    _push_ofi_ticks(sig, ["down"] * 15)
    result = sig.check()
    assert result.triggered
    assert result.metadata["sell_ticks"] > 0


def test_ofi_no_trigger_when_balanced():
    """Alternating up/down → imbalance ≈ 0 < threshold → no trigger."""
    sig = OFISignal(window_ticks=30, threshold=0.70, min_samples=10)
    _push_ofi_ticks(sig, ["up", "down"] * 10)
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "active"


def test_ofi_neutral_all_flat():
    """All-flat moves → no classified ticks → neutral status."""
    sig = OFISignal(min_samples=3)
    sig.on_book_update(0.50)
    for _ in range(10):
        sig.on_book_update(0.50)
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "neutral"


# ===========================================================================
# MMWithdrawalSignal — construction guards
# ===========================================================================


def test_mmws_invalid_window():
    with pytest.raises(ValueError, match="window_ticks"):
        MMWithdrawalSignal(window_ticks=1)


def test_mmws_invalid_depth_levels():
    with pytest.raises(ValueError, match="depth_levels"):
        MMWithdrawalSignal(depth_levels=0)


def test_mmws_invalid_threshold():
    with pytest.raises(ValueError, match="depth_drop_threshold"):
        MMWithdrawalSignal(depth_drop_threshold=0.0)


def test_mmws_invalid_threshold_high():
    with pytest.raises(ValueError, match="depth_drop_threshold"):
        MMWithdrawalSignal(depth_drop_threshold=1.0)


# ===========================================================================
# MMWithdrawalSignal — cold start and warming-up
# ===========================================================================


def test_mmws_cold_start():
    sig = MMWithdrawalSignal()
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "cold_start"


def test_mmws_warming_up():
    sig = MMWithdrawalSignal(min_samples=5)
    bids = [{"price": 0.49, "size": 100.0}]
    asks = [{"price": 0.51, "size": 100.0}]
    for _ in range(3):
        sig.on_book_update(bids, asks)
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "warming_up"
    assert result.metadata["samples"] == 3


def test_mmws_zero_baseline():
    """Empty book (all-zero depth) → zero_baseline → no trigger."""
    sig = MMWithdrawalSignal(min_samples=3)
    for _ in range(5):
        sig.on_book_update([], [])
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "zero_baseline"


# ===========================================================================
# MMWithdrawalSignal — trigger and no-trigger
# ===========================================================================


def test_mmws_triggers_on_depth_collapse():
    """Stable depth followed by a sharp drop triggers the signal."""
    sig = MMWithdrawalSignal(min_samples=5, depth_drop_threshold=0.50)
    normal_bids = [{"price": 0.49, "size": 100.0}]
    normal_asks = [{"price": 0.51, "size": 100.0}]
    thin_bids = [{"price": 0.49, "size": 5.0}]
    thin_asks = [{"price": 0.51, "size": 5.0}]

    for _ in range(10):
        sig.on_book_update(normal_bids, normal_asks)
    sig.on_book_update(thin_bids, thin_asks)

    result = sig.check()
    assert result.triggered
    assert "mm_withdrawal" in result.reason
    assert result.metadata["ratio"] < 0.50


def test_mmws_no_trigger_stable_depth():
    """Stable depth → no trigger."""
    sig = MMWithdrawalSignal(min_samples=5, depth_drop_threshold=0.50)
    bids = [{"price": 0.49, "size": 100.0}]
    asks = [{"price": 0.51, "size": 100.0}]
    for _ in range(15):
        sig.on_book_update(bids, asks)
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "active"


def test_mmws_empty_book_not_trigger_when_warming():
    """Empty book levels (missing data) during warm-up → warming_up, no trigger."""
    sig = MMWithdrawalSignal(min_samples=10)
    for _ in range(3):
        sig.on_book_update([], [])
    result = sig.check()
    assert not result.triggered
    assert result.metadata["status"] == "warming_up"


# ===========================================================================
# AdverseSelectionGuard
# ===========================================================================


def test_guard_cold_start_no_trigger():
    """Fresh guard with no book updates → not blocked."""
    guard = AdverseSelectionGuard()
    result = guard.check()
    assert not result.blocked
    assert result.reason == ""
    assert "ofi" in result.signals
    assert "mm_withdrawal" in result.signals


def test_guard_none_book_safe():
    """on_book_update(None) must not raise and must not trigger."""
    guard = AdverseSelectionGuard()
    guard.on_book_update(None)
    result = guard.check()
    assert not result.blocked


def test_guard_book_without_expected_attrs():
    """Object with no relevant attributes → safe no-trigger."""
    guard = AdverseSelectionGuard()
    guard.on_book_update(object())
    result = guard.check()
    assert not result.blocked


def test_guard_blocks_when_ofi_triggers():
    """Guard blocks when OFI triggers; mm_withdrawal may be warming up."""
    ofi = OFISignal(window_ticks=30, threshold=0.70, min_samples=10)
    guard = AdverseSelectionGuard(ofi=ofi)

    # Force OFI to trigger via direct signal manipulation
    book_up = _make_book(best_bid=0.40, best_ask=0.42)
    book_up2 = _make_book(best_bid=0.41, best_ask=0.43)
    # Alternate to push many up ticks
    mid = 0.50
    ofi.on_book_update(mid)
    for _ in range(15):
        mid += 0.01
        ofi.on_book_update(mid)

    result = guard.check()
    assert result.blocked
    assert "ofi" in result.reason


def test_guard_blocks_when_mm_withdrawal_triggers():
    """Guard blocks when MM withdrawal triggers; OFI warming up."""
    mm = MMWithdrawalSignal(min_samples=5, depth_drop_threshold=0.50)
    guard = AdverseSelectionGuard(mm_withdrawal=mm)

    normal_bids = [{"price": 0.49, "size": 100.0}]
    normal_asks = [{"price": 0.51, "size": 100.0}]
    thin_bids = [{"price": 0.49, "size": 5.0}]
    thin_asks = [{"price": 0.51, "size": 5.0}]

    for _ in range(10):
        mm.on_book_update(normal_bids, normal_asks)
    mm.on_book_update(thin_bids, thin_asks)

    result = guard.check()
    assert result.blocked
    assert "mm_withdrawal" in result.reason


def test_guard_with_valid_book_mock():
    """Guard.on_book_update wires correctly to both signals via mock book."""
    guard = AdverseSelectionGuard(
        ofi=OFISignal(min_samples=1),
        mm_withdrawal=MMWithdrawalSignal(min_samples=1),
    )
    book = _make_book(
        best_bid=0.49,
        best_ask=0.51,
        bids=[{"price": 0.49, "size": 100.0}],
        asks=[{"price": 0.51, "size": 100.0}],
    )
    guard.on_book_update(book)
    result = guard.check()
    # After a single update with min_samples=1, mm_withdrawal needs at least
    # 1 sample but check uses prior samples for baseline; result is warming_up.
    assert not result.blocked  # not enough samples yet for either signal to trigger


# ===========================================================================
# RiskManager integration
# ===========================================================================


def test_risk_manager_no_guard_passes_through():
    """RiskManager without adverse_selection guard passes valid orders."""
    rm = RiskManager(RiskConfig())
    allowed, reason = rm.check_order(
        asset_id="tok1", side="BUY", price=Decimal("0.50"), size=Decimal("10")
    )
    assert allowed
    assert reason == ""


def test_risk_manager_on_book_update_no_guard_noop():
    """on_book_update with no guard configured is a safe no-op."""
    rm = RiskManager()
    rm.on_book_update(None)  # must not raise
    rm.on_book_update(_make_book(best_bid=0.49, best_ask=0.51))


def test_risk_manager_with_guard_blocks_when_triggered():
    """RiskManager blocks orders when guard is triggered."""
    ofi = OFISignal(window_ticks=30, threshold=0.70, min_samples=10)
    guard = AdverseSelectionGuard(ofi=ofi)

    # Trigger OFI: 15 consecutive up ticks
    mid = 0.50
    ofi.on_book_update(mid)
    for _ in range(15):
        mid += 0.01
        ofi.on_book_update(mid)

    rm = RiskManager(RiskConfig(), adverse_selection=guard)
    allowed, reason = rm.check_order(
        asset_id="tok1", side="BUY", price=Decimal("0.50"), size=Decimal("10")
    )
    assert not allowed
    assert "adverse_selection" in reason


def test_risk_manager_with_guard_allows_when_warming_up():
    """RiskManager allows orders while guard signals are still warming up."""
    guard = AdverseSelectionGuard()  # fresh — cold start on both signals
    rm = RiskManager(RiskConfig(), adverse_selection=guard)
    allowed, reason = rm.check_order(
        asset_id="tok1", side="BUY", price=Decimal("0.50"), size=Decimal("10")
    )
    assert allowed


def test_risk_manager_on_book_update_feeds_guard():
    """on_book_update routes to guard.on_book_update."""
    guard = MagicMock()
    rm = RiskManager(adverse_selection=guard)
    book = _make_book(best_bid=0.49, best_ask=0.51)
    rm.on_book_update(book)
    guard.on_book_update.assert_called_once_with(book)


def test_risk_manager_guard_check_called_in_check_order():
    """check_order calls guard.check() before other risk checks."""
    guard = MagicMock()
    guard.check.return_value = GuardResult(
        blocked=True, reason="test block", signals={}
    )
    rm = RiskManager(adverse_selection=guard)
    allowed, reason = rm.check_order(
        asset_id="tok1", side="BUY", price=Decimal("0.50"), size=Decimal("10")
    )
    assert not allowed
    assert "adverse_selection" in reason
    guard.check.assert_called_once()


# ===========================================================================
# LiveRunner integration (smoke test — book kwarg forwarded to risk)
# ===========================================================================


def test_live_runner_book_kwarg_feeds_risk_manager():
    """run_once(strategy_fn, book=book) calls risk.on_book_update(book)."""
    from packages.polymarket.simtrader.execution.live_runner import LiveRunConfig, LiveRunner

    guard = MagicMock()
    guard.check.return_value = GuardResult(blocked=False, reason="", signals={})
    rm = RiskManager(adverse_selection=guard)

    runner = LiveRunner(LiveRunConfig(dry_run=True), risk_manager=rm)
    book = _make_book(best_bid=0.49, best_ask=0.51)
    runner.run_once(lambda: [], book=book)

    guard.on_book_update.assert_called_once_with(book)


def test_live_runner_no_book_kwarg_no_error():
    """run_once without book= kwarg does not crash (backward compat)."""
    from packages.polymarket.simtrader.execution.live_runner import LiveRunConfig, LiveRunner

    runner = LiveRunner(LiveRunConfig(dry_run=True))
    result = runner.run_once(lambda: [])
    assert result["attempted"] == 0
