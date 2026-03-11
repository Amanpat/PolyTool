"""Tests for BinaryComplementArb strategy.

Test categories
---------------
1. Detection correctness on synthetic book
   - Arb detected when sum_ask < 1 - buffer
   - No arb when sum_ask >= 1 - buffer
   - No arb before both books are initialized

2. Legging policy behavior on synthetic tape
   - wait_N_then_unwind: both legs fill → merge recorded
   - wait_N_then_unwind: timeout, neither fills → cancelled
   - wait_N_then_unwind: YES fills, NO doesn't → legged_out + unwind
   - immediate_unwind: counts from first leg fill, not entry

3. Determinism: same tape + config → identical opportunities.jsonl

4. Runner integration: multi-asset books, fill_asset_id filter
   - YES orders fill against YES book (not NO book)
   - NO orders fill against NO book (not YES book)

5. merge_full_set assumption labeling
   - ASSUMPTION key present in merge records
   - modeled_arb_summary has ASSUMPTION field
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

YES_ID = "yes-001"
NO_ID = "no-001"

# YES book: bid=0.40, ask=0.44 (300 shares)
# NO  book: bid=0.48, ask=0.52 (200 shares)
# sum_ask = 0.96 < 0.98 (1 - buffer=0.02) → ARB
# Both books have enough depth to fill max_size=100 per leg.
BASE_TAPE = [
    # seq 0: YES snapshot
    {
        "parser_version": 1, "seq": 0, "ts_recv": 0.0,
        "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.40", "size": "500"}],
        "asks": [{"price": "0.44", "size": "300"}],
    },
    # seq 1: NO snapshot
    {
        "parser_version": 1, "seq": 1, "ts_recv": 1.0,
        "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.48", "size": "400"}],
        "asks": [{"price": "0.52", "size": "200"}],
    },
    # seq 2: YES price change (bid side only, arb condition unchanged)
    {
        "parser_version": 1, "seq": 2, "ts_recv": 2.0,
        "event_type": "price_change", "asset_id": YES_ID,
        "changes": [{"side": "BUY", "price": "0.41", "size": "100"}],
    },
    # seq 3: NO price change (bid side only)
    {
        "parser_version": 1, "seq": 3, "ts_recv": 3.0,
        "event_type": "price_change", "asset_id": NO_ID,
        "changes": [{"side": "BUY", "price": "0.49", "size": "50"}],
    },
    # seq 4–7: interleaved YES/NO events (book unchanged: arb still present)
    {
        "parser_version": 1, "seq": 4, "ts_recv": 4.0,
        "event_type": "price_change", "asset_id": YES_ID,
        "changes": [{"side": "BUY", "price": "0.42", "size": "50"}],
    },
    {
        "parser_version": 1, "seq": 5, "ts_recv": 5.0,
        "event_type": "price_change", "asset_id": NO_ID,
        "changes": [{"side": "BUY", "price": "0.50", "size": "30"}],
    },
    {
        "parser_version": 1, "seq": 6, "ts_recv": 6.0,
        "event_type": "price_change", "asset_id": YES_ID,
        "changes": [{"side": "BUY", "price": "0.43", "size": "20"}],
    },
    {
        "parser_version": 1, "seq": 7, "ts_recv": 7.0,
        "event_type": "price_change", "asset_id": NO_ID,
        "changes": [{"side": "BUY", "price": "0.51", "size": "10"}],
    },
]

# A "no arb" tape: sum_ask = 0.50 + 0.55 = 1.05 > 1.00 − 0.02 = 0.98
NO_ARB_TAPE = [
    {
        "parser_version": 1, "seq": 0, "ts_recv": 0.0,
        "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.45", "size": "500"}],
        "asks": [{"price": "0.50", "size": "300"}],
    },
    {
        "parser_version": 1, "seq": 1, "ts_recv": 1.0,
        "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.40", "size": "400"}],
        "asks": [{"price": "0.55", "size": "200"}],
    },
    {
        "parser_version": 1, "seq": 2, "ts_recv": 2.0,
        "event_type": "price_change", "asset_id": YES_ID,
        "changes": [{"side": "BUY", "price": "0.46", "size": "10"}],
    },
]


def _write_tape(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")


def _run(
    tmp_path: Path,
    tape: list[dict],
    run_id: str = "test",
    buffer: float = 0.02,
    max_size: float = 100.0,
    legging_policy: str = "wait_N_then_unwind",
    unwind_wait_ticks: int = 5,
    enable_merge: bool = True,
    starting_cash: float = 5000.0,
    fee_rate_bps: float = 0.0,  # zero for clean arithmetic
    allow_degraded: bool = True,
) -> tuple[dict, list[dict]]:
    """Helper: run arb strategy and return (pnl_summary, opportunities)."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    tape_path = tmp_path / f"{run_id}_events.jsonl"
    _write_tape(tape_path, tape)

    run_dir = tmp_path / run_id
    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=buffer,
        max_size=max_size,
        legging_policy=legging_policy,
        unwind_wait_ticks=unwind_wait_ticks,
        enable_merge_full_set=enable_merge,
    )
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal(str(starting_cash)),
        fee_rate_bps=Decimal(str(fee_rate_bps)),
        allow_degraded=allow_degraded,
    )
    summary = runner.run()
    opps = list(strategy.opportunities)
    return summary, opps


def _opps_of_type(opps: list[dict], type_: str) -> list[dict]:
    return [o for o in opps if o["type"] == type_]


# ---------------------------------------------------------------------------
# 1. Detection correctness
# ---------------------------------------------------------------------------


def test_arb_detected_when_sum_ask_below_threshold(tmp_path: Path) -> None:
    """Arb detected at first event where both books are initialized and sum_ask < threshold."""
    _, opps = _run(tmp_path, BASE_TAPE, run_id="detect")
    detected = _opps_of_type(opps, "detected")
    assert len(detected) >= 1, "Expected at least one detection"
    d = detected[0]
    assert Decimal(d["yes_ask"]) == Decimal("0.44")
    assert Decimal(d["no_ask"]) == Decimal("0.52")
    assert Decimal(d["sum_ask"]) == Decimal("0.96")
    assert Decimal(d["expected_profit_per_share"]) == Decimal("0.04")
    assert d["yes_asset_id"] == YES_ID
    assert d["no_asset_id"] == NO_ID


def test_no_arb_when_sum_ask_above_threshold(tmp_path: Path) -> None:
    """No arb detected when sum_ask ≥ 1 - buffer."""
    _, opps = _run(tmp_path, NO_ARB_TAPE, run_id="noarb")
    detected = _opps_of_type(opps, "detected")
    assert detected == [], "Should not detect arb when sum_ask = 1.05 > 0.98"


def test_no_arb_before_both_books_initialized(tmp_path: Path) -> None:
    """Strategy should not fire before it has seen both YES and NO snapshots."""
    # Tape: only YES snapshot, no NO events
    yes_only_tape = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "300"}],
        },
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": "0.41", "size": "10"}],
        },
    ]
    _, opps = _run(tmp_path, yes_only_tape, run_id="yes_only")
    assert _opps_of_type(opps, "detected") == []


def test_detection_threshold_exact_boundary(tmp_path: Path) -> None:
    """sum_ask = exactly 1 - buffer → no arb (strict less-than required)."""
    # buffer=0.02 → threshold=0.98; sum_ask=0.50+0.48=0.98 → NOT detected
    boundary_tape = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.50", "size": "100"}],
        },
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.43", "size": "100"}],
            "asks": [{"price": "0.48", "size": "100"}],
        },
        {
            "parser_version": 1, "seq": 2, "ts_recv": 2.0,
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": "0.46", "size": "5"}],
        },
    ]
    _, opps = _run(tmp_path, boundary_tape, run_id="boundary", buffer=0.02)
    assert _opps_of_type(opps, "detected") == []


# ---------------------------------------------------------------------------
# 2. Legging policy behavior
# ---------------------------------------------------------------------------


def test_both_legs_fill_merge_recorded(tmp_path: Path) -> None:
    """Both legs fill on arb tape → both_filled + merge_full_set logged."""
    _, opps = _run(tmp_path, BASE_TAPE, run_id="both_fill", unwind_wait_ticks=10)
    both = _opps_of_type(opps, "both_filled")
    merge = _opps_of_type(opps, "merge_full_set")
    assert len(both) >= 1, "Expected both_filled event"
    assert len(merge) >= 1, "Expected merge_full_set event"

    m = merge[0]
    assert "ASSUMPTION" in m, "merge_full_set must carry ASSUMPTION key"
    assert "MODELED ONLY" in m["ASSUMPTION"], "ASSUMPTION must contain disclaimer"
    assert Decimal(m["modeled_proceeds"]) == Decimal("100"), "100 pairs × $1 = $100"
    assert Decimal(m["modeled_cost"]) == Decimal("96"), "100 × (0.44+0.52) = $96"
    assert Decimal(m["modeled_profit"]) == Decimal("4"), "$100 - $96 = $4"


def test_merge_disabled_no_merge_event(tmp_path: Path) -> None:
    """With enable_merge_full_set=False, no merge_full_set event logged."""
    _, opps = _run(
        tmp_path, BASE_TAPE, run_id="no_merge",
        enable_merge=False, unwind_wait_ticks=10,
    )
    assert _opps_of_type(opps, "merge_full_set") == []
    # but both_filled should still be logged
    assert len(_opps_of_type(opps, "both_filled")) >= 1


def test_wait_N_timeout_neither_fills(tmp_path: Path) -> None:
    """Wait-N policy: if neither leg fills in unwind_wait_ticks, mark cancelled."""
    # Use a tape where the ask prices are too high for any buy to fill
    no_fill_tape = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "300"}],
        },
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.48", "size": "400"}],
            "asks": [{"price": "0.52", "size": "200"}],
        },
        # After detection at seq 2, the ask prices jump up so orders can't fill.
        # We simulate this by removing the ask level (size=0) before any YES/NO
        # book events that would trigger fills.  But since fill requires the
        # right limit price, we just submit with a very low limit: use max_size
        # but the strategy limit = ask at detection.  To prevent fills, we
        # completely wipe the ask side via price_change size=0 BEFORE broker.step
        # processes the YES order.
        #
        # Actually: the strategy submits at limit=ask (0.44 for YES, 0.52 for NO).
        # broker.step for YES fills at seq 2 since YES ask=0.44 ≤ limit=0.44.
        # So there WILL be fills on this tape.
        #
        # To get NO fills: use a tape where NO ask is ABOVE limit at fill time.
        # The strategy submits NO at limit=0.52.  If NO ask is 0.60 at fill time
        # → no fill.  We can do this by:
        #   1. NO book snapshot with ask=0.52 at seq 1
        #   2. Before seq 3 (first NO book event): change NO ask to 0.60
        #      (but the order is submitted at limit=0.52, so 0.60 > 0.52 → no fill)
        #
        # Wait — on the detection tape above the strategy submits NO at 0.52.
        # The broker only tries to fill the NO order when it processes NO events.
        # Let's just not include any NO events after seq 1 for several ticks.
        # The YES order fills at seq 2.  The NO order stays pending.
        # After unwind_wait_ticks=3 events, the attempt times out.
    ] + [
        {
            "parser_version": 1, "seq": i, "ts_recv": float(i),
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": f"0.3{i}", "size": "5"}],
        }
        for i in range(2, 8)
    ]
    # With unwind_wait_ticks=3, the YES order fills at seq 2 (YES event).
    # NO order never gets a NO event → never fills.
    # At tick 3 since entry, strategy should detect legged_out (or if YES filled, unwind).
    # Actually: yes fills at seq 2, then after 3 more ticks (seqs 3,4,5 are YES events)
    # → legged_out, not cancelled.
    # For "cancelled" (neither fills), we need to also prevent YES fills.
    # Make limit price below the YES ask:
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    # Custom tape: YES ask=0.60, NO ask=0.35; sum=0.95 < 0.98 → detect.
    # Strategy submits YES at limit=0.60, NO at limit=0.35.
    # YES ask=0.60 ≤ limit=0.60 → fills.  That's legged out again.
    # To get NEITHER fills: make limit < ask.
    # Strategy submits at BEST_ASK.  To prevent fills, change ask UPWARD before
    # broker.step processes the fill.  Since book.apply and broker.step happen
    # in the same tick, if we raise the ask in the same event... tricky.
    #
    # Simplest: make YES ask=0.40 and NO ask=0.53, sum=0.93 → detect.
    # Broker.step tries to fill YES at limit=0.40 against YES book ask=0.40 → fills!
    # Still fills.
    #
    # The fill happens at the SAME tick as detection because limit = ask exactly.
    # To prevent fills: submit order with effective_seq offset.
    # Use latency_ticks > 0 so order activates AFTER the current tick.
    # Then change the ask price before the order activates.

    no_fill_tape2 = [
        # YES book: bid=0.40, ask=0.44 (sum_ask=0.96 with NO, arb detected)
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "300"}],
        },
        # NO book: ask=0.52 (sum=0.96)
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.48", "size": "400"}],
            "asks": [{"price": "0.52", "size": "200"}],
        },
        # seq 2: YES event → detection fires, orders submitted at limit=0.44 (YES) and 0.52 (NO)
        # YES order activates at seq=2+latency_ticks.  If latency=2: activates at seq 4.
        {
            "parser_version": 1, "seq": 2, "ts_recv": 2.0,
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": "0.41", "size": "10"}],
        },
        # seq 3: YES ask jumps to 0.70 → order at limit=0.44 CAN'T fill
        {
            "parser_version": 1, "seq": 3, "ts_recv": 3.0,
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "SELL", "price": "0.44", "size": "0"},  # remove 0.44 ask
                        {"side": "SELL", "price": "0.70", "size": "500"}],  # add high ask
        },
        # seq 4: NO ask jumps too
        {
            "parser_version": 1, "seq": 4, "ts_recv": 4.0,
            "event_type": "price_change", "asset_id": NO_ID,
            "changes": [{"side": "SELL", "price": "0.52", "size": "0"},
                        {"side": "SELL", "price": "0.75", "size": "300"}],
        },
        # seq 5-8: more YES/NO events with wide spreads (no fill possible)
        {"parser_version": 1, "seq": 5, "ts_recv": 5.0, "event_type": "price_change",
         "asset_id": YES_ID, "changes": [{"side": "BUY", "price": "0.41", "size": "5"}]},
        {"parser_version": 1, "seq": 6, "ts_recv": 6.0, "event_type": "price_change",
         "asset_id": NO_ID, "changes": [{"side": "BUY", "price": "0.48", "size": "5"}]},
        {"parser_version": 1, "seq": 7, "ts_recv": 7.0, "event_type": "price_change",
         "asset_id": YES_ID, "changes": [{"side": "BUY", "price": "0.42", "size": "3"}]},
        {"parser_version": 1, "seq": 8, "ts_recv": 8.0, "event_type": "price_change",
         "asset_id": NO_ID, "changes": [{"side": "BUY", "price": "0.49", "size": "2"}]},
    ]
    tape_path = tmp_path / "no_fill_events.jsonl"
    _write_tape(tape_path, no_fill_tape2)
    run_dir = tmp_path / "no_fill_run"

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=100,
        legging_policy="wait_N_then_unwind",
        unwind_wait_ticks=3,
        enable_merge_full_set=True,
    )
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal("5000"),
        fee_rate_bps=Decimal("0"),
        # latency_ticks=2 so orders activate AFTER the ask has moved
        latency=__import__(
            "packages.polymarket.simtrader.broker.latency", fromlist=["LatencyConfig"]
        ).LatencyConfig(submit_ticks=2),
    )
    runner.run()

    opps = strategy.opportunities
    cancelled = _opps_of_type(opps, "cancelled")
    assert len(cancelled) >= 1, f"Expected cancelled; got types: {[o['type'] for o in opps]}"
    assert cancelled[0]["reason"] == "timeout_no_fills"


def test_wait_N_timeout_one_leg_filled_legged_out(tmp_path: Path) -> None:
    """Wait-N: YES fills immediately, NO never gets events → legged_out + unwind sell."""
    # Tape: YES fills at seq 2, then only YES events for 10+ ticks (NO never steps)
    yes_fills_no_doesnt = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "300"}],
        },
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.48", "size": "400"}],
            "asks": [{"price": "0.52", "size": "200"}],
        },
    ] + [
        {
            "parser_version": 1, "seq": i, "ts_recv": float(i),
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": f"0.3{i % 9}", "size": "1"}],
        }
        for i in range(2, 15)
    ]
    _, opps = _run(
        tmp_path, yes_fills_no_doesnt,
        run_id="legged_out",
        unwind_wait_ticks=3,
    )
    leg_filled = _opps_of_type(opps, "leg_filled")
    legged_out = _opps_of_type(opps, "legged_out")
    assert any(lf.get("leg") == "yes" for lf in leg_filled), "YES leg should have filled"
    assert len(legged_out) >= 1, "Expected legged_out event"
    lo = legged_out[0]
    assert lo["filled_leg"] == "yes"
    assert lo["cancelled_leg"] == "no"


def test_immediate_unwind_counts_from_first_fill(tmp_path: Path) -> None:
    """immediate_unwind: deadline is first_fill_tick + N, not entry_tick + N."""
    # YES fills at seq 2 (tick 1 after entry at seq 1).
    # With immediate_unwind + unwind_wait_ticks=2: deadline = tick 1 + 2 = tick 3
    # So no unwind at ticks 1 or 2, but unwind at tick 3.
    # With wait_N_then_unwind + same N=2: deadline = entry_tick + 2 = tick 2
    # → unwind happens EARLIER.
    yes_fills_only = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "300"}],
        },
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.48", "size": "400"}],
            "asks": [{"price": "0.52", "size": "200"}],
        },
    ] + [
        {
            "parser_version": 1, "seq": i, "ts_recv": float(i),
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": f"0.3{i % 9}", "size": "1"}],
        }
        for i in range(2, 15)
    ]
    # immediate_unwind, wait=2: legged_out happens at tick ≥ first_fill_tick + 2
    _, opps_immediate = _run(
        tmp_path, yes_fills_only,
        run_id="imm_unwind",
        legging_policy="immediate_unwind",
        unwind_wait_ticks=2,
    )
    # wait_N_then_unwind, wait=2: legged_out happens at tick ≥ entry_tick + 2
    _, opps_wait = _run(
        tmp_path, yes_fills_only,
        run_id="wait_n_unwind",
        legging_policy="wait_N_then_unwind",
        unwind_wait_ticks=2,
    )

    lo_imm = _opps_of_type(opps_immediate, "legged_out")
    lo_wait = _opps_of_type(opps_wait, "legged_out")
    assert lo_imm, "immediate_unwind should produce legged_out"
    assert lo_wait, "wait_N_then_unwind should produce legged_out"
    # immediate_unwind waits longer (starts timer at fill, not entry)
    assert lo_imm[0]["ticks_waited"] >= lo_wait[0]["ticks_waited"]


# ---------------------------------------------------------------------------
# 3. Determinism
# ---------------------------------------------------------------------------


def test_runner_determinism(tmp_path: Path) -> None:
    """Same tape + config → identical opportunity log across two runs."""
    _, opps_a = _run(tmp_path, BASE_TAPE, run_id="det_a", unwind_wait_ticks=10)
    _, opps_b = _run(tmp_path, BASE_TAPE, run_id="det_b", unwind_wait_ticks=10)

    assert len(opps_a) == len(opps_b), "Opportunity log lengths differ"
    for i, (a, b) in enumerate(zip(opps_a, opps_b)):
        for k in ("type", "attempt_id", "seq"):
            assert a.get(k) == b.get(k), f"Record {i} field {k!r} differs: {a.get(k)} vs {b.get(k)}"


def test_opportunities_jsonl_written(tmp_path: Path) -> None:
    """Runner writes opportunities.jsonl to run_dir."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, BASE_TAPE)
    run_dir = tmp_path / "opp_test"

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID, no_asset_id=NO_ID,
        buffer=0.02, max_size=50, unwind_wait_ticks=10,
    )
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal("5000"),
        fee_rate_bps=Decimal("0"),
    )
    runner.run()

    opp_path = run_dir / "opportunities.jsonl"
    assert opp_path.exists(), "opportunities.jsonl not written"
    rows = [json.loads(ln) for ln in opp_path.read_text().splitlines() if ln.strip()]
    assert len(rows) >= 1


# ---------------------------------------------------------------------------
# 4. Multi-asset fill isolation
# ---------------------------------------------------------------------------


def test_yes_order_fills_at_yes_ask_not_no_ask(tmp_path: Path) -> None:
    """YES orders must fill at YES ask prices, not NO ask prices."""
    _, opps = _run(tmp_path, BASE_TAPE, run_id="iso_yes", unwind_wait_ticks=20)
    leg_fills = _opps_of_type(opps, "leg_filled")
    yes_fills = [lf for lf in leg_fills if lf.get("leg") == "yes"]
    assert yes_fills, "YES leg should have filled"
    for yf in yes_fills:
        assert Decimal(yf["fill_price"]) == Decimal("0.44"), (
            f"YES fill at wrong price: {yf['fill_price']} (expected 0.44)"
        )


def test_no_order_fills_at_no_ask_not_yes_ask(tmp_path: Path) -> None:
    """NO orders must fill at NO ask prices, not YES ask prices."""
    _, opps = _run(tmp_path, BASE_TAPE, run_id="iso_no", unwind_wait_ticks=20)
    leg_fills = _opps_of_type(opps, "leg_filled")
    no_fills = [lf for lf in leg_fills if lf.get("leg") == "no"]
    assert no_fills, "NO leg should have filled"
    for nf in no_fills:
        assert Decimal(nf["fill_price"]) == Decimal("0.52"), (
            f"NO fill at wrong price: {nf['fill_price']} (expected 0.52)"
        )


def test_no_fill_without_complement_book_events(tmp_path: Path) -> None:
    """NO order must NOT fill if no NO book events arrive after detection.

    Detection fires on a YES event (seq 2); subsequent events are YES-only.
    The NO order is submitted but broker.step is never called with fill_asset_id=NO_ID
    after seq 2, so the NO order cannot fill.
    """
    # NO snapshot at seq 1 has ask=0.55 → sum_ask=0.44+0.55=0.99 ≥ 0.98, no arb yet.
    # YES ask drops to 0.40 at seq 2 → sum_ask=0.40+0.55=0.95 < 0.98, arb detected.
    # After seq 2: only YES events → NO order is never fill-stepped.
    yes_only_after_setup = [
        {   # seq 0: YES snapshot, ask=0.44
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "300"}],
        },
        {   # seq 1: NO snapshot, ask=0.55 → sum=0.99, no arb
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.48", "size": "400"}],
            "asks": [{"price": "0.55", "size": "200"}],
        },
        {   # seq 2: YES ask drops to 0.40 → sum=0.40+0.55=0.95 < 0.98, arb!
            "parser_version": 1, "seq": 2, "ts_recv": 2.0,
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [
                {"side": "SELL", "price": "0.44", "size": "0"},   # remove old ask
                {"side": "SELL", "price": "0.40", "size": "300"},  # add lower ask
            ],
        },
    ] + [
        {
            "parser_version": 1, "seq": i, "ts_recv": float(i),
            "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": f"0.3{i % 9}", "size": "1"}],
        }
        for i in range(3, 20)
    ]
    _, opps = _run(
        tmp_path, yes_only_after_setup,
        run_id="no_only",
        unwind_wait_ticks=5,
    )
    no_fills = [lf for lf in _opps_of_type(opps, "leg_filled") if lf.get("leg") == "no"]
    assert no_fills == [], f"NO leg should NOT fill without NO events; got: {no_fills}"


# ---------------------------------------------------------------------------
# 5. Assumption labeling
# ---------------------------------------------------------------------------


def test_assumption_key_in_merge(tmp_path: Path) -> None:
    """merge_full_set records must carry the ASSUMPTION key."""
    _, opps = _run(tmp_path, BASE_TAPE, run_id="assume", unwind_wait_ticks=20)
    for m in _opps_of_type(opps, "merge_full_set"):
        assert "ASSUMPTION" in m, "ASSUMPTION key missing from merge_full_set record"
        assert m["ASSUMPTION"] != "", "ASSUMPTION value must not be empty"


def test_modeled_arb_summary_has_assumption_when_merged(tmp_path: Path) -> None:
    """modeled_arb_summary must include ASSUMPTION field when merges occurred."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, BASE_TAPE)
    run_dir = tmp_path / "sum_assume"

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID, no_asset_id=NO_ID,
        buffer=0.02, max_size=100, unwind_wait_ticks=20,
    )
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal("5000"),
        fee_rate_bps=Decimal("0"),
    )
    runner.run()

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert "modeled_arb_summary" in manifest
    summary = manifest["modeled_arb_summary"]
    if summary.get("merged_modeled", 0) > 0:
        assert summary.get("ASSUMPTION") is not None, (
            "modeled_arb_summary must carry ASSUMPTION when merges occurred"
        )


def test_no_assumption_field_when_no_merges(tmp_path: Path) -> None:
    """modeled_arb_summary.ASSUMPTION is None when no merges occurred."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, BASE_TAPE)
    run_dir = tmp_path / "no_merge_sum"

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID, no_asset_id=NO_ID,
        buffer=0.02, max_size=100, unwind_wait_ticks=20,
        enable_merge_full_set=False,
    )
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal("5000"),
        fee_rate_bps=Decimal("0"),
    )
    runner.run()

    summary = strategy.modeled_arb_summary
    assert summary.get("ASSUMPTION") is None, "No ASSUMPTION when merge disabled"


# ---------------------------------------------------------------------------
# 6. Rejection counters
# ---------------------------------------------------------------------------


def test_rejection_counter_no_bbo_when_no_book_yet() -> None:
    """Ticks before the NO book is initialized increment no_bbo counter."""
    from decimal import Decimal

    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=10,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    # Tick: YES book has BBO but NO book is still empty → no_bbo
    event = {
        "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.50", "size": "100"}],
    }
    intents = strategy.on_event(event, 1, 1.0, best_bid=0.45, best_ask=0.50, open_orders={})

    assert intents == [], "No intents expected when NO BBO is absent"
    strategy.on_finish()

    counts = strategy.modeled_arb_summary["rejection_counts"]
    assert counts["no_bbo"] >= 1, f"Expected no_bbo >= 1, got {counts}"
    assert counts["edge_below_threshold"] == 0
    assert counts["waiting_on_attempt"] == 0


def test_rejection_counter_edge_below_threshold() -> None:
    """Ticks where sum_ask >= 1-buffer increment edge_below_threshold counter."""
    from decimal import Decimal

    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,  # threshold = 0.98; sum_ask=1.05 → no arb
        max_size=10,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    # First set up NO book via an event
    no_book_event = {
        "seq": 0, "ts_recv": 0.0, "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.40", "size": "100"}],
        "asks": [{"price": "0.55", "size": "100"}],
    }
    strategy.on_event(no_book_event, 0, 0.0, best_bid=None, best_ask=None, open_orders={})

    # YES ask=0.50, NO ask=0.55 → sum=1.05 > 0.98 → edge_below_threshold
    yes_event = {
        "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.45", "size": "100"}],
        "asks": [{"price": "0.50", "size": "100"}],
    }
    intents = strategy.on_event(yes_event, 1, 1.0, best_bid=0.45, best_ask=0.50, open_orders={})
    assert intents == [], "No intents when edge is insufficient"

    strategy.on_finish()
    counts = strategy.modeled_arb_summary["rejection_counts"]
    assert counts["edge_below_threshold"] >= 1, f"Expected edge_below_threshold >= 1, got {counts}"
    # seq 0 fires with best_ask=None so no_bbo may be 1; that's acceptable
    assert counts["waiting_on_attempt"] == 0


def test_rejection_counter_waiting_on_attempt(tmp_path: Path) -> None:
    """Ticks while an attempt is active increment waiting_on_attempt counter."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    tape_path = tmp_path / "events.jsonl"
    # BASE_TAPE: arb detected at seq 2, attempt active for several ticks
    _write_tape(tape_path, BASE_TAPE)

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=100,
        unwind_wait_ticks=20,  # long wait → many ticks with active attempt
    )
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=tmp_path / "wait_run",
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal("5000"),
        fee_rate_bps=Decimal("0"),
    )
    runner.run()

    counts = strategy.rejection_counts
    assert counts["waiting_on_attempt"] >= 1, (
        f"Expected waiting_on_attempt >= 1 after attempt entry; got {counts}"
    )


def test_rejection_counter_insufficient_depth_yes() -> None:
    """A thin YES best-ask level increments insufficient_depth_yes deterministically."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=50,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    # Seed NO snapshot (setup phase may increment unrelated counters).
    no_event = {
        "seq": 0, "ts_recv": 0.0, "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.48", "size": "100"}],
        "asks": [{"price": "0.52", "size": "100"}],
    }
    strategy.on_event(no_event, 0, 0.0, best_bid=None, best_ask=None, open_orders={})

    before = dict(strategy.rejection_counts)
    yes_event = {
        "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.39", "size": "100"}],
        "asks": [{"price": "0.40", "size": "10"}],  # thinner than max_size=50
    }
    intents = strategy.on_event(yes_event, 1, 1.0, best_bid=0.39, best_ask=0.40, open_orders={})

    assert intents == []
    assert (
        strategy.rejection_counts["insufficient_depth_yes"]
        == before["insufficient_depth_yes"] + 1
    )


def test_rejection_counter_insufficient_depth_no() -> None:
    """A thin NO best-ask level increments insufficient_depth_no deterministically."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=50,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    no_event = {
        "seq": 0, "ts_recv": 0.0, "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.48", "size": "100"}],
        "asks": [{"price": "0.52", "size": "10"}],  # thinner than max_size=50
    }
    strategy.on_event(no_event, 0, 0.0, best_bid=None, best_ask=None, open_orders={})

    before = dict(strategy.rejection_counts)
    yes_event = {
        "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.39", "size": "100"}],
        "asks": [{"price": "0.40", "size": "100"}],
    }
    intents = strategy.on_event(yes_event, 1, 1.0, best_bid=0.39, best_ask=0.40, open_orders={})

    assert intents == []
    assert (
        strategy.rejection_counts["insufficient_depth_no"]
        == before["insufficient_depth_no"] + 1
    )


def test_rejection_counter_fee_kills_edge() -> None:
    """sum_ask below $1 but above threshold increments fee_kills_edge."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,  # threshold=0.98
        max_size=10,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    no_event = {
        "seq": 0, "ts_recv": 0.0, "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.48", "size": "100"}],
        "asks": [{"price": "0.50", "size": "100"}],
    }
    strategy.on_event(no_event, 0, 0.0, best_bid=None, best_ask=None, open_orders={})

    before = dict(strategy.rejection_counts)
    # sum_ask=0.49+0.50=0.99 (positive gross edge, below-fees/buffer edge fails)
    yes_event = {
        "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.48", "size": "100"}],
        "asks": [{"price": "0.49", "size": "100"}],
    }
    intents = strategy.on_event(yes_event, 1, 1.0, best_bid=0.48, best_ask=0.49, open_orders={})

    assert intents == []
    assert strategy.rejection_counts["fee_kills_edge"] == before["fee_kills_edge"] + 1


def test_rejection_counter_min_notional_or_max_notional_gate() -> None:
    """Notional gate increments min_notional_or_max_notional_gate deterministically."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=100,
        max_notional_usdc=20,  # force gating (expected notional around 95-100)
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    no_event = {
        "seq": 0, "ts_recv": 0.0, "event_type": "book", "asset_id": NO_ID,
        "bids": [{"price": "0.48", "size": "200"}],
        "asks": [{"price": "0.52", "size": "200"}],
    }
    strategy.on_event(no_event, 0, 0.0, best_bid=None, best_ask=None, open_orders={})

    before = dict(strategy.rejection_counts)
    yes_event = {
        "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.40", "size": "200"}],
        "asks": [{"price": "0.43", "size": "200"}],  # sum_ask=0.95, entry otherwise valid
    }
    intents = strategy.on_event(yes_event, 1, 1.0, best_bid=0.40, best_ask=0.43, open_orders={})

    assert intents == []
    assert (
        strategy.rejection_counts["min_notional_or_max_notional_gate"]
        == before["min_notional_or_max_notional_gate"] + 1
    )


def test_rejection_counters_legging_blocked_and_unwind_in_progress() -> None:
    """Active-attempt ticks split between legging_blocked and unwind_in_progress."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=10,
        unwind_wait_ticks=10,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    # Seed both books and create an active attempt.
    strategy.on_event(
        {
            "seq": 0, "ts_recv": 0.0, "event_type": "book", "asset_id": NO_ID,
            "bids": [{"price": "0.48", "size": "100"}],
            "asks": [{"price": "0.52", "size": "100"}],
        },
        0,
        0.0,
        best_bid=None,
        best_ask=None,
        open_orders={},
    )
    entry_intents = strategy.on_event(
        {
            "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.40", "size": "100"}],
            "asks": [{"price": "0.44", "size": "100"}],
        },
        1,
        1.0,
        best_bid=0.40,
        best_ask=0.44,
        open_orders={},
    )
    assert len(entry_intents) == 2, "Expected entry intents to open an attempt"

    before = dict(strategy.rejection_counts)

    # Tick with active attempt and no fills yet -> legging_blocked.
    strategy.on_event(
        {
            "seq": 2, "ts_recv": 2.0, "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": "0.41", "size": "10"}],
        },
        2,
        2.0,
        best_bid=0.41,
        best_ask=0.44,
        open_orders={},
    )
    assert strategy.rejection_counts["legging_blocked"] == before["legging_blocked"] + 1

    # Mark YES leg as filled, then next tick should be counted as unwind_in_progress.
    strategy.on_fill(
        order_id="yes-fill-1",
        asset_id=YES_ID,
        side="BUY",
        fill_price=Decimal("0.44"),
        fill_size=Decimal("10"),
        fill_status="full",
        seq=2,
        ts_recv=2.0,
    )
    strategy.on_event(
        {
            "seq": 3, "ts_recv": 3.0, "event_type": "price_change", "asset_id": YES_ID,
            "changes": [{"side": "BUY", "price": "0.42", "size": "10"}],
        },
        3,
        3.0,
        best_bid=0.42,
        best_ask=0.44,
        open_orders={},
    )
    assert strategy.rejection_counts["unwind_in_progress"] == before["unwind_in_progress"] + 1
    assert strategy.rejection_counts["waiting_on_attempt"] == before["waiting_on_attempt"] + 2


def test_rejection_counter_stale_or_missing_snapshot() -> None:
    """Missing NO snapshot increments stale_or_missing_snapshot deterministically."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=10,
    )
    strategy.on_start(YES_ID, Decimal("1000"))

    before = dict(strategy.rejection_counts)
    strategy.on_event(
        {
            "seq": 1, "ts_recv": 1.0, "event_type": "book", "asset_id": YES_ID,
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.50", "size": "100"}],
        },
        1,
        1.0,
        best_bid=0.45,
        best_ask=0.50,
        open_orders={},
    )
    assert (
        strategy.rejection_counts["stale_or_missing_snapshot"]
        == before["stale_or_missing_snapshot"] + 1
    )


def test_rejection_counts_in_manifest_and_summary(tmp_path: Path) -> None:
    """rejection_counts appear in run_manifest.json strategy_debug and summary.json."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, NO_ARB_TAPE)  # no arb → only edge_below_threshold ticks

    strategy = BinaryComplementArb(
        yes_asset_id=YES_ID,
        no_asset_id=NO_ID,
        buffer=0.02,
        max_size=100,
    )
    run_dir = tmp_path / "counts_artifacts"
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=YES_ID,
        extra_book_asset_ids=[NO_ID],
        starting_cash=Decimal("1000"),
        fee_rate_bps=Decimal("0"),
    )
    runner.run()

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert "strategy_debug" in manifest, "run_manifest must have strategy_debug"
    assert "rejection_counts" in manifest["strategy_debug"]
    counts_m = manifest["strategy_debug"]["rejection_counts"]
    assert "no_bbo" in counts_m
    assert "edge_below_threshold" in counts_m
    assert "waiting_on_attempt" in counts_m
    assert "insufficient_depth_yes" in counts_m
    assert "insufficient_depth_no" in counts_m
    assert "fee_kills_edge" in counts_m
    assert "min_notional_or_max_notional_gate" in counts_m
    assert "unwind_in_progress" in counts_m
    assert "legging_blocked" in counts_m
    assert "stale_or_missing_snapshot" in counts_m

    summary = json.loads((run_dir / "summary.json").read_text())
    assert "strategy_debug" in summary, "summary.json must have strategy_debug"
    assert "rejection_counts" in summary["strategy_debug"]

    # NO_ARB_TAPE has no arb → edge_below_threshold should be > 0 after both books are set
    counts_s = summary["strategy_debug"]["rejection_counts"]
    assert counts_s["edge_below_threshold"] >= 1, (
        f"NO_ARB_TAPE should produce edge_below_threshold ticks; got {counts_s}"
    )
# ---------------------------------------------------------------------------
# 6. Strategy base on_fill default
# ---------------------------------------------------------------------------


def test_base_strategy_on_fill_is_noop() -> None:
    """Strategy base class on_fill is a safe no-op."""
    from packages.polymarket.simtrader.strategy.base import Strategy
    s = Strategy()
    s.on_fill("oid", "asset", "BUY", Decimal("0.5"), Decimal("100"), "full", 1, 1.0)


# ---------------------------------------------------------------------------
# 7. SimBroker fill_asset_id filter
# ---------------------------------------------------------------------------


def test_broker_fill_asset_id_filters_fills() -> None:
    """broker.step with fill_asset_id only fills orders for that asset."""
    from packages.polymarket.simtrader.broker.sim_broker import SimBroker
    from packages.polymarket.simtrader.orderbook.l2book import L2Book

    # YES book: ask=0.44
    yes_book = L2Book(YES_ID, strict=False)
    yes_book_event = {
        "seq": 0, "ts_recv": 0.0,
        "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.40", "size": "500"}],
        "asks": [{"price": "0.44", "size": "300"}],
    }
    yes_step_event = {
        "seq": 1, "ts_recv": 1.0,
        "event_type": "price_change", "asset_id": YES_ID,
        "changes": [{"side": "BUY", "price": "0.41", "size": "10"}],
    }
    yes_book.apply(yes_book_event)

    broker = SimBroker()
    # Submit a YES BUY order
    yes_oid = broker.submit_order(
        asset_id=YES_ID, side="BUY",
        limit_price=Decimal("0.50"), size=Decimal("100"),
        submit_seq=1, submit_ts=1.0,
    )
    # Submit a NO BUY order
    no_oid = broker.submit_order(
        asset_id=NO_ID, side="BUY",
        limit_price=Decimal("0.55"), size=Decimal("50"),
        submit_seq=1, submit_ts=1.0,
    )

    yes_book.apply(yes_step_event)
    # Step with fill_asset_id=YES_ID: only YES order should fill
    fills = broker.step(yes_step_event, yes_book, fill_asset_id=YES_ID)

    fill_order_ids = {f.order_id for f in fills}
    assert yes_oid in fill_order_ids, "YES order should fill against YES book"
    assert no_oid not in fill_order_ids, "NO order should NOT fill against YES book"


def test_broker_no_fill_asset_id_fills_all() -> None:
    """broker.step with fill_asset_id=None fills orders of any asset (original behavior)."""
    from packages.polymarket.simtrader.broker.sim_broker import SimBroker
    from packages.polymarket.simtrader.orderbook.l2book import L2Book

    book = L2Book(YES_ID, strict=False)
    book_event = {
        "seq": 0, "ts_recv": 0.0,
        "event_type": "book", "asset_id": YES_ID,
        "bids": [{"price": "0.40", "size": "500"}],
        "asks": [{"price": "0.44", "size": "500"}],
    }
    step_event = {
        "seq": 1, "ts_recv": 1.0,
        "event_type": "price_change", "asset_id": YES_ID,
        "changes": [{"side": "BUY", "price": "0.41", "size": "1"}],
    }
    book.apply(book_event)

    broker = SimBroker()
    oid_a = broker.submit_order(
        asset_id=YES_ID, side="BUY",
        limit_price=Decimal("0.50"), size=Decimal("10"),
        submit_seq=1, submit_ts=1.0,
    )
    oid_b = broker.submit_order(
        asset_id="other-asset", side="BUY",
        limit_price=Decimal("0.50"), size=Decimal("10"),
        submit_seq=1, submit_ts=1.0,
    )
    book.apply(step_event)
    # No filter: both orders attempt fill
    fills = broker.step(step_event, book, fill_asset_id=None)
    fill_ids = {f.order_id for f in fills if f.fill_size > Decimal("0")}
    assert oid_a in fill_ids, "Order A should fill with no filter"
    assert oid_b in fill_ids, "Order B should also fill with no filter (original behavior)"


# ---------------------------------------------------------------------------
# 8. Invalid legging policy
# ---------------------------------------------------------------------------


def test_invalid_legging_policy_raises() -> None:
    """BinaryComplementArb raises ValueError for unknown legging policy."""
    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    with pytest.raises(ValueError, match="legging_policy"):
        BinaryComplementArb(
            yes_asset_id=YES_ID,
            no_asset_id=NO_ID,
            legging_policy="magic_unwind",
        )


# ---------------------------------------------------------------------------
# 9. CLI integration
# ---------------------------------------------------------------------------


def test_cli_run_binary_arb(tmp_path: Path) -> None:
    """``simtrader run --strategy binary_complement_arb`` exits 0 and writes artifacts."""
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, BASE_TAPE)

    strategy_cfg = json.dumps({
        "yes_asset_id": YES_ID,
        "no_asset_id": NO_ID,
        "buffer": 0.02,
        "max_size": 50.0,
        "unwind_wait_ticks": 10,
    })

    rc = simtrader_main([
        "run",
        "--tape", str(tape_path),
        "--strategy", "binary_complement_arb",
        "--strategy-config", strategy_cfg,
        "--asset-id", YES_ID,
        "--run-id", "cli-arb-test",
        "--starting-cash", "2000",
        "--fee-rate-bps", "0",
    ])
    assert rc == 0, f"CLI returned non-zero: {rc}"

    run_dir = Path("artifacts/simtrader/runs/cli-arb-test")
    assert (run_dir / "summary.json").exists()
    assert (run_dir / "decisions.jsonl").exists()
