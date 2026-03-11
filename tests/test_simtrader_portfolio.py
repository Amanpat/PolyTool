"""Tests for SimTrader-2 Portfolio + PnL.

Three invariant families
------------------------
1. **Ledger invariants** — cash, reserved funds, positions, and realized PnL
   remain internally consistent on synthetic broker event sequences.
2. **Reconciliation** — ledger totals reconcile to raw fill data within
   Decimal tolerance (no floating-point drift).
3. **Determinism** — same order events + same timeline + same starting cash
   → byte-identical ledger.jsonl, equity_curve.jsonl, and summary.json.

Additional coverage
-------------------
- Partial fills across multiple price levels update average cost correctly.
- Cancel latency: reservation is released only when ``cancelled`` event fires,
  not when ``cancel_submitted`` fires.
- FIFO cost basis: sells consume oldest lots first.
- Conservative mark price (bid-side): unrealized PnL never overstated.
- Midpoint mark price mode.
- Fee computation (Decimal, curve formula).
- CLI end-to-end: ``simtrader trade --starting-cash N`` produces all artifacts.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pytest

from packages.polymarket.simtrader.portfolio.fees import (
    DEFAULT_FEE_RATE_BPS,
    compute_fill_fee,
    worst_case_fee,
)
from packages.polymarket.simtrader.portfolio.ledger import PortfolioLedger
from packages.polymarket.simtrader.portfolio.mark import MARK_BID, MARK_MID, mark_price
from packages.polymarket.simtrader.tape.schema import PARSER_VERSION

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_D = Decimal  # shorthand


def _order_event(event: str, order_id: str, seq: int, ts: float = 1000.0, **extra) -> dict:
    return {"event": event, "order_id": order_id, "seq": seq, "ts_recv": ts, **extra}


def _submitted(
    order_id: str,
    seq: int,
    side: str = "BUY",
    asset_id: str = "tok1",
    limit_price: str = "0.42",
    size: str = "100",
    ts: float = 1000.0,
) -> dict:
    return _order_event(
        "submitted", order_id, seq, ts,
        side=side, asset_id=asset_id,
        limit_price=limit_price, size=size,
        effective_seq=seq,
    )


def _activated(order_id: str, seq: int, ts: float = 1000.5) -> dict:
    return _order_event("activated", order_id, seq, ts)


def _fill(
    order_id: str,
    seq: int,
    fill_price: str,
    fill_size: str,
    remaining: str,
    fill_status: str = "full",
    ts: float = 1001.0,
) -> dict:
    return _order_event(
        "fill", order_id, seq, ts,
        fill_price=fill_price,
        fill_size=fill_size,
        remaining=remaining,
        fill_status=fill_status,
        because={},
    )


def _cancel_submitted(order_id: str, seq: int, cancel_eff: int, ts: float = 1001.5) -> dict:
    return _order_event("cancel_submitted", order_id, seq, ts, cancel_effective_seq=cancel_eff)


def _cancelled(order_id: str, seq: int, remaining: str, ts: float = 1002.0) -> dict:
    return _order_event("cancelled", order_id, seq, ts, remaining=remaining)


def _tl_row(seq: int, ts: float = 1000.0, best_bid: Optional[float] = 0.40,
             best_ask: Optional[float] = 0.43) -> dict:
    return {"seq": seq, "ts_recv": ts, "best_bid": best_bid, "best_ask": best_ask}


def _book_event(seq: int = 0, ts: float = 1000.0, asset_id: str = "tok1",
                bids=None, asks=None) -> dict:
    return {
        "parser_version": PARSER_VERSION,
        "seq": seq, "ts_recv": ts, "event_type": "book", "asset_id": asset_id,
        "market": "0xabc",
        "bids": bids if bids is not None else [],
        "asks": asks if asks is not None else [],
    }


def _price_change(seq: int, ts: float = 1001.0, asset_id: str = "tok1", changes=None) -> dict:
    return {
        "parser_version": PARSER_VERSION,
        "seq": seq, "ts_recv": ts, "event_type": "price_change", "asset_id": asset_id,
        "changes": changes if changes is not None else [],
    }


def _write_events(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")


# ===========================================================================
# Fees module
# ===========================================================================


class TestComputeFillFee:
    def test_zero_size_returns_zero(self):
        assert compute_fill_fee(_D("0"), _D("0.50"), _D("200")) == _D("0")

    def test_zero_price_returns_zero(self):
        assert compute_fill_fee(_D("100"), _D("0"), _D("200")) == _D("0")

    def test_price_at_one_returns_zero(self):
        assert compute_fill_fee(_D("100"), _D("1"), _D("200")) == _D("0")

    def test_default_fee_rate_applied_when_none(self):
        fee_with_default = compute_fill_fee(_D("100"), _D("0.50"), None)
        fee_explicit = compute_fill_fee(_D("100"), _D("0.50"), DEFAULT_FEE_RATE_BPS)
        assert fee_with_default == fee_explicit

    def test_fee_is_decimal(self):
        fee = compute_fill_fee(_D("100"), _D("0.42"), _D("200"))
        assert isinstance(fee, Decimal)

    def test_fee_increases_with_size(self):
        fee_small = compute_fill_fee(_D("50"), _D("0.50"), _D("200"))
        fee_large = compute_fill_fee(_D("100"), _D("0.50"), _D("200"))
        assert fee_large == 2 * fee_small

    def test_fee_increases_with_rate(self):
        fee_low = compute_fill_fee(_D("100"), _D("0.50"), _D("100"))
        fee_high = compute_fill_fee(_D("100"), _D("0.50"), _D("200"))
        assert fee_high == 2 * fee_low

    def test_curve_factor_symmetric_around_half(self):
        """The curve *factor* (price*(1-price))^2 is symmetric at 0.3 and 0.7,
        but because the formula also multiplies by ``price`` linearly, the total
        fee at 0.3 and 0.7 are NOT equal.  This test verifies the ratio is
        correct: fee(0.7) / fee(0.3) == 0.7 / 0.3 (same curve factor, different
        linear price term)."""
        fee_low = compute_fill_fee(_D("100"), _D("0.30"), _D("200"))
        fee_high = compute_fill_fee(_D("100"), _D("0.70"), _D("200"))
        # Curve factor: (0.3*0.7)^2 == (0.7*0.3)^2 → identical
        # Linear price term: 0.70 / 0.30 = 7/3
        expected_ratio = _D("0.70") / _D("0.30")
        actual_ratio = fee_high / fee_low
        assert abs(actual_ratio - expected_ratio) < _D("1e-10")

    def test_zero_fee_rate_returns_zero(self):
        assert compute_fill_fee(_D("100"), _D("0.50"), _D("0")) == _D("0")

    def test_worst_case_fee_geq_actual(self):
        """worst_case_fee must always be >= actual fee at any price."""
        for price_str in ("0.1", "0.3", "0.5", "0.7", "0.9"):
            price = _D(price_str)
            actual = compute_fill_fee(_D("100"), price, _D("200"))
            worst = worst_case_fee(_D("100"), price, _D("200"))
            assert worst >= actual, f"worst_case_fee < actual fee at price={price}"


# ===========================================================================
# Mark price module
# ===========================================================================


class TestMarkPrice:
    def test_bid_method_long_uses_best_bid(self):
        mp = mark_price("BUY", best_bid=0.58, best_ask=0.60, method=MARK_BID)
        assert mp == _D("0.58")

    def test_bid_method_short_uses_best_ask(self):
        mp = mark_price("SELL", best_bid=0.58, best_ask=0.60, method=MARK_BID)
        assert mp == _D("0.60")

    def test_midpoint_uses_average(self):
        mp = mark_price("BUY", best_bid=0.58, best_ask=0.60, method=MARK_MID)
        assert mp == _D("0.59")

    def test_bid_method_none_bid_returns_none(self):
        assert mark_price("BUY", best_bid=None, best_ask=0.60) is None

    def test_midpoint_requires_both_sides(self):
        assert mark_price("BUY", best_bid=0.58, best_ask=None, method=MARK_MID) is None
        assert mark_price("BUY", best_bid=None, best_ask=0.60, method=MARK_MID) is None

    def test_unknown_method_raises(self):
        with pytest.raises(ValueError, match="Unknown mark method"):
            mark_price("BUY", 0.5, 0.6, method="bad_method")

    def test_result_is_decimal(self):
        mp = mark_price("BUY", 0.42, 0.44)
        assert isinstance(mp, Decimal)


# ===========================================================================
# PortfolioLedger — invariant: cash conservation
# ===========================================================================


class TestLedgerCashConservation:
    """Cash conservation: starting_cash = cash + reserved + spent − received − fees."""

    def _total_cash(self, ledger: PortfolioLedger) -> Decimal:
        reserved = sum(ledger._reserved_cash.values())
        return ledger._cash + reserved

    def test_no_trades_cash_unchanged(self):
        ledger = PortfolioLedger(_D("1000"))
        ledger.process([], [])
        assert ledger._cash == _D("1000")

    def test_buy_submission_reserves_cash(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [_submitted("o1", 0, limit_price="0.42", size="100")]
        ledger.process(events, [])
        # 0.42 * 100 = 42 reserved
        assert ledger._reserved_cash["o1"] == _D("42")
        assert ledger._cash == _D("958")
        assert self._total_cash(ledger) == _D("1000")

    def test_full_buy_fill_cash_decreases_by_cost_plus_fee(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _fill("o1", 1, fill_price="0.40", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        # spent 40 USDC + 0 fee; excess from reservation = 42 - 40 = 2 returned
        assert ledger._cash == _D("960")  # 1000 - 42 (reserve) + 2 (excess) = 960
        assert not ledger._reserved_cash  # fully filled → reservation cleared

    def test_partial_fill_reservation_correct(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _fill("o1", 1, fill_price="0.40", fill_size="50", remaining="50",
                  fill_status="partial"),
        ]
        ledger.process(events, [])
        # Reserved 42 total; filled 50 shares:
        #   Released for fill: 0.42 * 50 = 21 from reservation
        #   Spent: 0.40 * 50 = 20; excess 1 returned to cash
        #   Remaining reservation: 42 - 21 = 21
        assert ledger._reserved_cash["o1"] == _D("21")
        assert ledger._cash == _D("958") + _D("1")  # 958 + excess 1 = 959
        assert self._total_cash(ledger) == _D("1000") - _D("20")  # spent on 50 shares

    def test_cancel_releases_full_reservation(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _cancel_submitted("o1", 1, cancel_eff=2),
            _cancelled("o1", 2, remaining="100"),
        ]
        ledger.process(events, [])
        assert ledger._cash == _D("1000")  # all cash returned
        assert not ledger._reserved_cash

    def test_partial_fill_then_cancel_releases_remaining(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _fill("o1", 1, fill_price="0.40", fill_size="50", remaining="50",
                  fill_status="partial"),
            _cancel_submitted("o1", 2, cancel_eff=3),
            _cancelled("o1", 3, remaining="50"),
        ]
        ledger.process(events, [])
        # Spent 20 on 50 shares; 21 released at cancel; cash = 958 + 1 (excess) + 21 = 980
        assert ledger._cash == _D("980")
        assert not ledger._reserved_cash


# ===========================================================================
# PortfolioLedger — invariant: positions (FIFO cost basis)
# ===========================================================================


class TestLedgerPositions:
    def test_buy_fill_creates_lot(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _fill("o1", 1, fill_price="0.40", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        lots = ledger._lots["tok1"]
        assert len(lots) == 1
        assert lots[0] == (_D("100"), _D("0.40"))

    def test_multiple_partial_fills_accumulate_lots(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="200"),
            _fill("o1", 1, fill_price="0.40", fill_size="80", remaining="120",
                  fill_status="partial"),
            _fill("o1", 2, fill_price="0.41", fill_size="120", remaining="0"),
        ]
        ledger.process(events, [])
        lots = ledger._lots["tok1"]
        assert len(lots) == 2
        assert lots[0] == (_D("80"), _D("0.40"))
        assert lots[1] == (_D("120"), _D("0.41"))

    def test_sell_consumes_lots_fifo(self):
        """FIFO: sell 80 shares should consume the first lot (80@0.40) entirely."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            # Buy two lots
            _submitted("o1", 0, limit_price="0.50", size="200"),
            _fill("o1", 1, fill_price="0.40", fill_size="80", remaining="120",
                  fill_status="partial"),
            _fill("o1", 2, fill_price="0.41", fill_size="120", remaining="0"),
            # Sell 80 (should consume first lot exactly)
            _submitted("o2", 3, side="SELL", limit_price="0.45", size="80"),
            _fill("o2", 4, fill_price="0.45", fill_size="80", remaining="0"),
        ]
        ledger.process(events, [])
        lots = ledger._lots["tok1"]
        assert len(lots) == 1
        # Only the second lot remains
        assert lots[0] == (_D("120"), _D("0.41"))

    def test_sell_partial_lot_fifo(self):
        """Selling 50 of a 100-share lot leaves 50 in the lot."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.45", size="50"),
            _fill("o2", 3, fill_price="0.45", fill_size="50", remaining="0"),
        ]
        ledger.process(events, [])
        lots = ledger._lots["tok1"]
        assert len(lots) == 1
        assert lots[0][0] == _D("50")   # 50 remaining
        assert lots[0][1] == _D("0.42")  # cost unchanged


# ===========================================================================
# PortfolioLedger — invariant: realized PnL
# ===========================================================================


class TestLedgerRealizedPnL:
    def test_simple_round_trip_realized_pnl(self):
        """Buy 100 @ 0.42, sell 100 @ 0.45 → gross PnL = 3.00."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.40", size="100"),
            _fill("o2", 3, fill_price="0.45", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        assert ledger._realized_pnl == _D("3.00")

    def test_realized_pnl_negative_when_loss(self):
        """Buy @ 0.50, sell @ 0.40 → realized PnL = -10."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.55", size="100"),
            _fill("o1", 1, fill_price="0.50", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.35", size="100"),
            _fill("o2", 3, fill_price="0.40", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        assert ledger._realized_pnl == _D("-10")

    def test_fifo_pnl_uses_oldest_cost_basis(self):
        """
        Two lots: 80@0.40, 120@0.41.  Sell 80 shares @ 0.45.
        Should use 80@0.40 lot → PnL = 80*(0.45-0.40) = 4.00.
        """
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="200"),
            _fill("o1", 1, fill_price="0.40", fill_size="80", remaining="120",
                  fill_status="partial"),
            _fill("o1", 2, fill_price="0.41", fill_size="120", remaining="0"),
            _submitted("o2", 3, side="SELL", limit_price="0.44", size="80"),
            _fill("o2", 4, fill_price="0.45", fill_size="80", remaining="0"),
        ]
        ledger.process(events, [])
        assert ledger._realized_pnl == _D("80") * (_D("0.45") - _D("0.40"))

    def test_fees_tracked_separately_from_realized_pnl(self):
        """realized_pnl is gross; total_fees is separate."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("200"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.40", size="100"),
            _fill("o2", 3, fill_price="0.45", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        assert ledger._realized_pnl == _D("3.00")  # gross, no fees
        assert ledger._total_fees > _D("0")

    def test_net_profit_in_summary_deducts_fees(self):
        """summary net_profit = realized_pnl - total_fees (no open positions)."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("200"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.40", size="100"),
            _fill("o2", 3, fill_price="0.45", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        s = ledger.summary("r1", None, None)
        net = _D(s["net_profit"])
        assert net == ledger._realized_pnl - ledger._total_fees


# ===========================================================================
# PortfolioLedger — reconciliation
# ===========================================================================


class TestLedgerReconciliation:
    """Ledger totals must reconcile to raw fill arithmetic within Decimal tolerance."""

    def test_cash_reconciles_to_fills(self):
        """
        After all fills with zero fees:
          final_cash = starting_cash
                       - sum(buy fill_price * fill_size)
                       + sum(sell fill_price * fill_size)
        """
        starting = _D("1000")
        ledger = PortfolioLedger(starting, fee_rate_bps=_D("0"))

        buy_fills = [("0.40", "80"), ("0.41", "120")]
        sell_fills = [("0.45", "80")]

        events = [_submitted("o1", 0, limit_price="0.50", size="200")]
        seq = 1
        remaining = _D("200")
        for price, size in buy_fills:
            remaining -= _D(size)
            events.append(_fill("o1", seq, price, size,
                                str(remaining), "partial" if remaining > 0 else "full"))
            seq += 1

        events.append(_submitted("o2", seq, side="SELL", limit_price="0.44", size="80"))
        seq += 1
        for price, size in sell_fills:
            events.append(_fill("o2", seq, price, size, "0"))
            seq += 1

        ledger.process(events, [])

        expected_cash = (
            starting
            - sum(_D(p) * _D(s) for p, s in buy_fills)
            + sum(_D(p) * _D(s) for p, s in sell_fills)
        )
        assert ledger._cash == expected_cash

    def test_total_fees_reconciles_to_sum_of_fill_fees(self):
        """total_fees must equal the sum of compute_fill_fee for each fill."""
        rate = _D("200")
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=rate)

        fills_data = [
            ("0.40", "80"),
            ("0.41", "120"),
        ]
        events = [_submitted("o1", 0, limit_price="0.50", size="200")]
        remaining = _D("200")
        for seq, (price, size) in enumerate(fills_data, start=1):
            remaining -= _D(size)
            events.append(_fill("o1", seq, price, size, str(remaining),
                                "partial" if remaining > 0 else "full"))

        ledger.process(events, [])
        expected_fees = sum(
            compute_fill_fee(_D(s), _D(p), rate) for p, s in fills_data
        )
        assert ledger._total_fees == expected_fees


# ===========================================================================
# PortfolioLedger — equity curve
# ===========================================================================


class TestEquityCurve:
    def _make_ledger_with_position(self) -> PortfolioLedger:
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
        ]
        timeline = [
            _tl_row(0, best_bid=0.38, best_ask=0.43),
            _tl_row(1, best_bid=0.40, best_ask=0.43),
        ]
        ledger.process(events, timeline)
        return ledger

    def test_equity_curve_row_count_matches_timeline(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
        ]
        timeline = [_tl_row(0), _tl_row(1), _tl_row(2)]
        _, equity_curve = ledger.process(events, timeline)
        assert len(equity_curve) == 3

    def test_equity_after_buy_uses_bid_mark(self):
        """After buying 100 @ 0.42, equity at bid=0.40 = cash + 100*0.40."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
        ]
        timeline = [_tl_row(1, best_bid=0.40, best_ask=0.44)]
        _, equity_curve = ledger.process(events, timeline)
        row = equity_curve[0]
        # cash = 1000 - 42 (reserved) + 8 (excess since fill @0.42 = limit) = 1000 - 42 = 958 + 0 = 958
        # Actually: reserve = 0.50*100 = 50; fill @0.42; excess = 50 - 42 = 8; cash = 1000-50+8 = 958
        assert _D(row["cash_usdc"]) == _D("958")
        # position mark = 100 * 0.40 = 40
        assert _D(row["position_mark_value"]) == _D("40")
        # equity = 958 + 40 = 998
        assert _D(row["equity"]) == _D("998")
        # unrealized_pnl = 100 * (0.40 - 0.42) = -2
        assert _D(row["unrealized_pnl"]) == _D("-2")

    def test_midpoint_mark_gives_higher_equity_than_bid(self):
        """Midpoint mark > bid mark for longs → higher unrealized PnL."""
        def _run(mark_method: str) -> Decimal:
            ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"),
                                     mark_method=mark_method)
            events = [
                _submitted("o1", 0, limit_price="0.50", size="100"),
                _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
            ]
            timeline = [_tl_row(1, best_bid=0.40, best_ask=0.44)]
            _, equity_curve = ledger.process(events, timeline)
            return _D(equity_curve[0]["equity"])

        equity_bid = _run(MARK_BID)
        equity_mid = _run(MARK_MID)
        assert equity_mid > equity_bid

    def test_equity_is_starting_cash_with_no_trades(self):
        ledger = PortfolioLedger(_D("500"), fee_rate_bps=_D("0"))
        timeline = [_tl_row(0, best_bid=0.40, best_ask=0.43)]
        _, equity_curve = ledger.process([], timeline)
        assert _D(equity_curve[0]["equity"]) == _D("500")

    def test_equity_curve_row_has_required_fields(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        timeline = [_tl_row(0)]
        _, equity_curve = ledger.process([], timeline)
        row = equity_curve[0]
        required = {
            "seq", "ts_recv", "cash_usdc", "reserved_cash_usdc",
            "position_mark_value", "unrealized_pnl", "realized_pnl",
            "total_fees", "equity", "mark_method", "best_bid", "best_ask",
        }
        assert required.issubset(row.keys())


# ===========================================================================
# PortfolioLedger — ledger snapshots
# ===========================================================================


class TestLedgerSnapshots:
    def test_snapshot_emitted_on_submission(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [_submitted("o1", 0)]
        snapshots, _ = ledger.process(events, [])
        assert len(snapshots) == 1
        assert snapshots[0]["event"] == "order_submitted"
        assert snapshots[0]["order_id"] == "o1"

    def test_snapshot_emitted_on_fill(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _fill("o1", 1, "0.42", "100", "0"),
        ]
        snapshots, _ = ledger.process(events, [])
        assert len(snapshots) == 2
        assert snapshots[1]["event"] == "fill"

    def test_snapshot_emitted_on_cancel(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.42", size="100"),
            _cancelled("o1", 1, remaining="100"),
        ]
        snapshots, _ = ledger.process(events, [])
        assert len(snapshots) == 2
        assert snapshots[-1]["event"] == "cancelled"

    def test_activated_event_does_not_produce_snapshot(self):
        """'activated' events are no-ops for the ledger; they suppress the snapshot."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0),
            _activated("o1", 1),
        ]
        snapshots, _ = ledger.process(events, [])
        assert len(snapshots) == 1  # only submission
        assert snapshots[0]["event"] == "order_submitted"

    def test_snapshot_has_required_fields(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        snapshots, _ = ledger.process([_submitted("o1", 0)], [])
        snap = snapshots[0]
        required = {
            "seq", "ts_recv", "event", "order_id",
            "cash_usdc", "reserved_cash_usdc", "reserved_shares",
            "positions", "realized_pnl", "total_fees",
        }
        assert required.issubset(snap.keys())


# ===========================================================================
# PortfolioLedger — summary
# ===========================================================================


class TestSummary:
    def test_summary_has_required_fields(self):
        ledger = PortfolioLedger(_D("1000"))
        s = ledger.summary("run1", None, None)
        required = {
            "run_id", "starting_cash", "final_cash", "reserved_cash",
            "position_mark_value", "final_equity", "realized_pnl",
            "unrealized_pnl", "total_fees", "net_profit",
            "mark_method", "fee_rate_bps",
        }
        assert required.issubset(s.keys())

    def test_summary_net_profit_zero_with_no_trades(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        s = ledger.summary("r1", None, None)
        assert _D(s["net_profit"]) == _D("0")

    def test_summary_records_run_id(self):
        ledger = PortfolioLedger(_D("1000"))
        s = ledger.summary("my-run-123", None, None)
        assert s["run_id"] == "my-run-123"

    def test_summary_net_profit_buy_hold_resolution(self):
        """
        Buy 100 @ 0.57 (zero fees), mark at bid=1.0 (resolution).
        net_profit ≈ 43.00.
        """
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.60", size="100"),
            _fill("o1", 1, fill_price="0.57", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        s = ledger.summary("r1", final_best_bid=1.0, final_best_ask=1.0)
        # unrealized: 100 * (1.0 - 0.57) = 43.00
        assert _D(s["unrealized_pnl"]) == _D("43.00")
        assert _D(s["net_profit"]) == _D("43.00")

    def test_summary_net_profit_buy_sell_round_trip(self):
        """Buy 100 @ 0.57, sell 100 @ 0.60 (no fees) → net_profit = 3.00."""
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.60", size="100"),
            _fill("o1", 1, fill_price="0.57", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.58", size="100"),
            _fill("o2", 3, fill_price="0.60", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        s = ledger.summary("r1", None, None)
        assert _D(s["net_profit"]) == _D("3.00")
        assert _D(s["unrealized_pnl"]) == _D("0")  # position closed

    def test_summary_final_equity_matches_cash_when_no_positions(self):
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("0"))
        events = [
            _submitted("o1", 0, limit_price="0.50", size="100"),
            _fill("o1", 1, fill_price="0.42", fill_size="100", remaining="0"),
            _submitted("o2", 2, side="SELL", limit_price="0.40", size="100"),
            _fill("o2", 3, fill_price="0.45", fill_size="100", remaining="0"),
        ]
        ledger.process(events, [])
        s = ledger.summary("r1", None, None)
        assert _D(s["final_equity"]) == _D(s["final_cash"])


# ===========================================================================
# PortfolioLedger — determinism
# ===========================================================================


class TestLedgerDeterminism:
    """Invariant: same inputs → identical outputs."""

    def _make_events(self) -> list[dict]:
        return [
            _submitted("o1", 0, limit_price="0.50", size="200"),
            _fill("o1", 1, fill_price="0.40", fill_size="80", remaining="120",
                  fill_status="partial"),
            _fill("o1", 2, fill_price="0.41", fill_size="120", remaining="0"),
            _submitted("o2", 3, side="SELL", limit_price="0.44", size="80"),
            _fill("o2", 4, fill_price="0.45", fill_size="80", remaining="0"),
        ]

    def _make_timeline(self) -> list[dict]:
        return [
            _tl_row(0, best_bid=0.38, best_ask=0.43),
            _tl_row(1, best_bid=0.39, best_ask=0.43),
            _tl_row(2, best_bid=0.40, best_ask=0.44),
            _tl_row(3, best_bid=0.42, best_ask=0.44),
            _tl_row(4, best_bid=0.43, best_ask=0.45),
        ]

    def _run(self) -> tuple[list[dict], list[dict], dict]:
        ledger = PortfolioLedger(_D("1000"), fee_rate_bps=_D("200"), mark_method=MARK_BID)
        snapshots, equity_curve = ledger.process(self._make_events(), self._make_timeline())
        summary = ledger.summary("r1", final_best_bid=0.43, final_best_ask=0.45)
        return snapshots, equity_curve, summary

    def test_two_runs_produce_identical_snapshots(self):
        s1, _, _ = self._run()
        s2, _, _ = self._run()
        assert s1 == s2

    def test_two_runs_produce_identical_equity_curve(self):
        _, e1, _ = self._run()
        _, e2, _ = self._run()
        assert e1 == e2

    def test_two_runs_produce_identical_summary(self):
        _, _, sum1 = self._run()
        _, _, sum2 = self._run()
        assert sum1 == sum2

    def test_json_serialised_equity_curve_byte_identical(self):
        """Byte-level determinism: json.dumps output is identical."""
        _, e1, _ = self._run()
        _, e2, _ = self._run()
        s1 = "\n".join(json.dumps(r) for r in e1)
        s2 = "\n".join(json.dumps(r) for r in e2)
        assert s1 == s2


# ===========================================================================
# CLI — end-to-end portfolio artifacts
# ===========================================================================


class TestPortfolioCLI:
    """End-to-end tests for the extended `simtrader trade` CLI."""

    _TAPE_EVENTS = [
        {
            "parser_version": PARSER_VERSION,
            "seq": 0, "ts_recv": 1000.0,
            "event_type": "book", "asset_id": "tok1", "market": "0xabc",
            "bids": [{"price": "0.38", "size": "500"}],
            "asks": [{"price": "0.42", "size": "200"}],
        },
        {
            "parser_version": PARSER_VERSION,
            "seq": 1, "ts_recv": 1001.0,
            "event_type": "price_change", "asset_id": "tok1",
            "changes": [{"side": "SELL", "price": "0.42", "size": "50"}],
        },
    ]

    def _run_trade_cli(
        self,
        tmp_path: Path,
        extra_args: list[str] | None = None,
        run_id: str = "pf-test-run",
    ) -> int:
        from tools.cli.simtrader import main as simtrader_main

        tape = tmp_path / "events.jsonl"
        _write_events(tape, self._TAPE_EVENTS)

        argv = [
            "trade",
            "--tape", str(tape),
            "--buy",
            "--limit", "0.42",
            "--size", "100",
            "--at-seq", "0",
            "--run-id", run_id,
            "--starting-cash", "500",
        ] + (extra_args or [])
        return simtrader_main(argv)

    def test_trade_exits_zero(self, tmp_path):
        rc = self._run_trade_cli(tmp_path)
        assert rc == 0

    def test_trade_produces_portfolio_artifacts(self, tmp_path):
        self._run_trade_cli(tmp_path)
        run_dir = Path("artifacts/simtrader/runs/pf-test-run")
        assert (run_dir / "ledger.jsonl").exists()
        assert (run_dir / "equity_curve.jsonl").exists()
        assert (run_dir / "summary.json").exists()

    def test_summary_has_net_profit_field(self, tmp_path):
        self._run_trade_cli(tmp_path)
        s = json.loads(
            Path("artifacts/simtrader/runs/pf-test-run/summary.json").read_text()
        )
        assert "net_profit" in s
        # Numeric and parseable
        _D(s["net_profit"])

    def test_summary_starting_cash_matches_arg(self, tmp_path):
        self._run_trade_cli(tmp_path)
        s = json.loads(
            Path("artifacts/simtrader/runs/pf-test-run/summary.json").read_text()
        )
        assert _D(s["starting_cash"]) == _D("500")

    def test_ledger_jsonl_is_valid(self, tmp_path):
        self._run_trade_cli(tmp_path)
        path = Path("artifacts/simtrader/runs/pf-test-run/ledger.jsonl")
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        assert len(rows) >= 1
        for row in rows:
            assert "event" in row
            assert "cash_usdc" in row
            assert "realized_pnl" in row

    def test_equity_curve_jsonl_is_valid(self, tmp_path):
        self._run_trade_cli(tmp_path)
        path = Path("artifacts/simtrader/runs/pf-test-run/equity_curve.jsonl")
        rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        assert len(rows) >= 1
        for row in rows:
            assert "equity" in row
            assert "mark_method" in row

    def test_manifest_contains_portfolio_config(self, tmp_path):
        self._run_trade_cli(tmp_path)
        m = json.loads(
            Path("artifacts/simtrader/runs/pf-test-run/run_manifest.json").read_text()
        )
        assert "portfolio_config" in m
        pc = m["portfolio_config"]
        assert _D(pc["starting_cash"]) == _D("500")
        assert pc["mark_method"] == "bid"

    def test_midpoint_mark_method_recorded(self, tmp_path):
        self._run_trade_cli(tmp_path, extra_args=["--mark-method", "midpoint"],
                            run_id="pf-mid-run")
        s = json.loads(
            Path("artifacts/simtrader/runs/pf-mid-run/summary.json").read_text()
        )
        assert s["mark_method"] == "midpoint"

    def test_custom_fee_rate_recorded(self, tmp_path):
        self._run_trade_cli(tmp_path, extra_args=["--fee-rate-bps", "100"],
                            run_id="pf-fee-run")
        s = json.loads(
            Path("artifacts/simtrader/runs/pf-fee-run/summary.json").read_text()
        )
        assert _D(s["fee_rate_bps"]) == _D("100")

    def test_determinism_same_starting_cash_same_summary(self, tmp_path):
        """Running twice produces identical summary net_profit."""
        tape = tmp_path / "events.jsonl"
        _write_events(tape, self._TAPE_EVENTS)

        from tools.cli.simtrader import main as simtrader_main

        def run_once(rid: str) -> str:
            simtrader_main([
                "trade", "--tape", str(tape),
                "--buy", "--limit", "0.42", "--size", "100",
                "--at-seq", "0",
                "--run-id", rid,
                "--starting-cash", "1000",
                "--fee-rate-bps", "200",
                "--mark-method", "bid",
            ])
            s = json.loads(
                Path(f"artifacts/simtrader/runs/{rid}/summary.json").read_text()
            )
            return s["net_profit"]

        np1 = run_once("det-run-1")
        np2 = run_once("det-run-2")
        assert np1 == np2, f"net_profit differs: {np1!r} vs {np2!r}"

    @classmethod
    def teardown_class(cls):
        import shutil
        for run_id in (
            "pf-test-run", "pf-mid-run", "pf-fee-run",
            "det-run-1", "det-run-2",
        ):
            p = Path("artifacts/simtrader/runs") / run_id
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
