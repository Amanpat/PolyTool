"""Tests for PMXT Deliverable B: sports_momentum, sports_favorite, sports_vwap."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

ASSET_ID = "sports-test-001"


# ---------------------------------------------------------------------------
# Tape helpers
# ---------------------------------------------------------------------------

def _book_event(seq: int, ts: float, bid: float, ask: float) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": ts,
        "event_type": "book",
        "asset_id": ASSET_ID,
        "bids": [{"price": str(bid), "size": "500"}],
        "asks": [{"price": str(ask), "size": "500"}],
    }


def _trade_event(seq: int, ts: float, price: float, size: float = 1.0) -> dict:
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": ts,
        "event_type": "last_trade_price",
        "asset_id": ASSET_ID,
        "price": str(price),
        "size": str(size),
    }


def _write_tape(path: Path, events: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def _read_decisions(run_dir: Path) -> list[dict]:
    path = run_dir / "decisions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# SportsMomentum tests
# ---------------------------------------------------------------------------


def test_sports_momentum_entry_and_take_profit(tmp_path: Path) -> None:
    """Price crosses entry_price inside the window, then hits take_profit → exactly 2 decisions."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum

    # market_close_time=100; window=[40,100]
    # seq 0 ts=0: bid=0.75, ask=0.78 → midpoint=0.765 (below entry 0.80; outside window)
    # seq 1 ts=41: bid=0.79, ask=0.82 → midpoint=0.805 (above entry; prev<entry → BUY)
    # seq 2 ts=42: bid=0.91, ask=0.93 → midpoint=0.92 (>= take_profit 0.92 → SELL)
    events = [
        _book_event(0, 0.0, 0.75, 0.78),
        _book_event(1, 41.0, 0.79, 0.82),
        _book_event(2, 42.0, 0.91, 0.93),
    ]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsMomentum(
        market_close_time=100.0,
        final_period_minutes=1.0,   # window = [40, 100]
        entry_price=0.80,
        take_profit_price=0.92,
        stop_loss_price=0.50,
        trade_size=100,
    )
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 2
    assert decisions[0]["side"] == "BUY"
    assert decisions[1]["side"] == "SELL"


def test_sports_momentum_no_entry_outside_window(tmp_path: Path) -> None:
    """Price crosses entry threshold but ts_recv is outside the window → 0 decisions."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum

    # window = [40, 100]; all events at ts=0,1 → outside window
    events = [
        _book_event(0, 0.0, 0.75, 0.78),
        _book_event(1, 1.0, 0.79, 0.82),
        _book_event(2, 2.0, 0.91, 0.93),
    ]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsMomentum(
        market_close_time=100.0,
        final_period_minutes=1.0,
        entry_price=0.80,
        take_profit_price=0.92,
        stop_loss_price=0.50,
    )
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    assert _read_decisions(run_dir) == []


def test_sports_momentum_stop_loss_exit(tmp_path: Path) -> None:
    """Price hits stop_loss after entry → exactly 2 decisions (BUY then SELL)."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum

    events = [
        _book_event(0, 0.0, 0.75, 0.78),
        _book_event(1, 41.0, 0.79, 0.82),   # triggers BUY (entry cross)
        _book_event(2, 42.0, 0.48, 0.52),   # midpoint=0.50 <= stop_loss=0.50 → SELL
    ]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsMomentum(
        market_close_time=100.0,
        final_period_minutes=1.0,
        entry_price=0.80,
        take_profit_price=0.92,
        stop_loss_price=0.50,
    )
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 2
    assert decisions[0]["side"] == "BUY"
    assert decisions[1]["side"] == "SELL"


def test_sports_momentum_already_above_threshold_no_entry(tmp_path: Path) -> None:
    """M2: first observation inside the window is already above entry_price → no BUY.

    Only after the price dips below and then crosses back up should a BUY fire.
    """
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum

    # market_close_time_ns = 120e9 → 120s; window = [60, 120]
    strategy = SportsMomentum(
        market_close_time_ns=120_000_000_000.0,
        final_period_minutes=1.0,
        entry_price=0.80,
        take_profit_price=0.92,
        stop_loss_price=0.50,
    )

    # ts=60: first tick, midpoint=0.81 — already above entry; _prev_price is None → no BUY
    result = strategy.on_event({}, seq=0, ts_recv=60.0, best_bid=0.80, best_ask=0.82, open_orders={})
    assert result == [], "first tick above threshold must not trigger entry"

    # ts=61: midpoint=0.79 — below entry
    result = strategy.on_event({}, seq=1, ts_recv=61.0, best_bid=0.78, best_ask=0.80, open_orders={})
    assert result == []

    # ts=62: midpoint=0.81 — prev=0.79 < 0.80 <= 0.81 → crossing → BUY
    result = strategy.on_event({}, seq=2, ts_recv=62.0, best_bid=0.80, best_ask=0.82, open_orders={})
    assert len(result) == 1
    assert result[0].side == "BUY"


def test_sports_momentum_close_time_exit(tmp_path: Path) -> None:
    """M3: strategy emits SELL when ts_recv reaches market_close_time after a fill."""
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum

    strategy = SportsMomentum(
        market_close_time_ns=120_000_000_000.0,
        final_period_minutes=1.0,
        entry_price=0.80,
        take_profit_price=0.95,
        stop_loss_price=0.40,
    )

    # Trigger entry at ts=62
    strategy.on_event({}, seq=0, ts_recv=60.0, best_bid=0.78, best_ask=0.82, open_orders={})
    strategy.on_event({}, seq=1, ts_recv=61.0, best_bid=0.78, best_ask=0.80, open_orders={})
    entry_intents = strategy.on_event({}, seq=2, ts_recv=62.0, best_bid=0.80, best_ask=0.82, open_orders={})
    assert len(entry_intents) == 1 and entry_intents[0].side == "BUY"

    # Simulate fill
    strategy.on_fill("ord-1", ASSET_ID, "BUY", Decimal("0.82"), Decimal("100"), "filled", 2, 62.0)

    # ts=70: in position, price mid 0.85 — above entry, but below TP 0.95 → no exit
    mid_intents = strategy.on_event({}, seq=3, ts_recv=70.0, best_bid=0.84, best_ask=0.86, open_orders={})
    assert mid_intents == []

    # ts=120: at close → SELL
    close_intents = strategy.on_event({}, seq=4, ts_recv=120.0, best_bid=0.84, best_ask=0.86, open_orders={})
    assert len(close_intents) == 1
    assert close_intents[0].side == "SELL"
    assert close_intents[0].reason == "momentum_exit"


def test_sports_momentum_disabled_when_close_time_zero() -> None:
    """M4: market_close_time_ns=0 (and market_close_time=0) → strategy never activates."""
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum

    strategy = SportsMomentum(
        market_close_time_ns=0.0,
        market_close_time=0.0,
        final_period_minutes=1.0,
        entry_price=0.80,
    )

    # Even a clear below-to-above cross should not fire
    strategy.on_event({}, seq=0, ts_recv=60.0, best_bid=0.78, best_ask=0.80, open_orders={})
    result = strategy.on_event({}, seq=1, ts_recv=61.0, best_bid=0.80, best_ask=0.82, open_orders={})
    assert result == [], "market_close_time=0 must disable strategy entirely"


# ---------------------------------------------------------------------------
# SportsFavorite tests
# ---------------------------------------------------------------------------


def test_sports_favorite_entry_on_signal(tmp_path: Path) -> None:
    """Midpoint at or above entry_price → exactly one BUY decision."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite

    # bid=0.84, ask=0.86 → midpoint=0.85 >= entry_price=0.85 → BUY
    events = [
        _book_event(0, 0.0, 0.84, 0.86),
        _book_event(1, 1.0, 0.84, 0.86),
    ]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsFavorite(entry_price=0.85, trade_size=25)
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 1
    assert decisions[0]["side"] == "BUY"


def test_sports_favorite_no_entry_before_activation(tmp_path: Path) -> None:
    """All events occur before activation_start_time → 0 decisions."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite

    events = [
        _book_event(0, 0.0, 0.90, 0.92),
        _book_event(1, 1.0, 0.90, 0.92),
    ]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsFavorite(
        entry_price=0.85,
        activation_start_time=200.0,  # activation far in the future
    )
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    assert _read_decisions(run_dir) == []


def test_sports_favorite_one_entry_only(tmp_path: Path) -> None:
    """Signal fires on every tick but strategy only enters once."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite

    events = [_book_event(i, float(i), 0.90, 0.92) for i in range(5)]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsFavorite(entry_price=0.85)
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    decisions = _read_decisions(run_dir)
    buy_decisions = [d for d in decisions if d.get("side") == "BUY"]
    assert len(buy_decisions) == 1


def test_sports_favorite_before_activation_then_entry() -> None:
    """F2: signal before activation_start_time_ns is ignored; first eligible tick fires BUY."""
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite

    # activation_start_time_ns=60e9 → 60s; market_close_time_ns=120e9 → 120s
    strategy = SportsFavorite(
        entry_price=0.85,
        activation_start_time_ns=60_000_000_000.0,
        market_close_time_ns=120_000_000_000.0,
    )

    # ts=59: above threshold but before activation → ignored
    result = strategy.on_event({}, seq=0, ts_recv=59.0, best_bid=0.86, best_ask=0.88, open_orders={})
    assert result == [], "signal before activation_start_time must be ignored"

    # ts=60: at activation boundary → BUY
    result = strategy.on_event({}, seq=1, ts_recv=60.0, best_bid=0.86, best_ask=0.88, open_orders={})
    assert len(result) == 1
    assert result[0].side == "BUY"


def test_sports_favorite_post_close_ignored() -> None:
    """F3: signal after market_close_time_ns is ignored → 0 intents."""
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite

    strategy = SportsFavorite(
        entry_price=0.85,
        activation_start_time_ns=60_000_000_000.0,
        market_close_time_ns=120_000_000_000.0,
    )

    # ts=121: past close → ignored
    result = strategy.on_event({}, seq=0, ts_recv=121.0, best_bid=0.88, best_ask=0.90, open_orders={})
    assert result == [], "signal after market_close_time must be ignored"


def test_sports_favorite_no_exit_after_fill() -> None:
    """F4: no SELL or exit intent emitted after a fill — position held until tape end."""
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite

    strategy = SportsFavorite(
        entry_price=0.85,
        activation_start_time_ns=60_000_000_000.0,
        market_close_time_ns=120_000_000_000.0,
    )

    # ts=60: above threshold → BUY
    entry = strategy.on_event({}, seq=0, ts_recv=60.0, best_bid=0.86, best_ask=0.88, open_orders={})
    assert len(entry) == 1 and entry[0].side == "BUY"

    # Simulate fill
    strategy.on_fill("ord-1", ASSET_ID, "BUY", Decimal("0.88"), Decimal("25"), "filled", 0, 60.0)

    # Subsequent ticks at various prices — no exit should be emitted
    for ts in [70.0, 80.0, 90.0, 110.0, 119.0]:
        result = strategy.on_event({}, seq=int(ts), ts_recv=ts, best_bid=0.50, best_ask=0.55, open_orders={})
        assert result == [], f"no exit expected at ts={ts} after fill"


# ---------------------------------------------------------------------------
# SportsVWAP tests
# ---------------------------------------------------------------------------


def test_sports_vwap_entry_and_reversion_exit(tmp_path: Path) -> None:
    """5 trades at 0.75 establish VWAP; price 0.738 triggers entry; 0.748 triggers reversion exit."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

    events = []
    for i in range(5):
        events.append(_trade_event(i, float(i), 0.75))
        events.append(_book_event(i * 10 + 100, float(i), 0.73, 0.74))

    # Entry tick: trade below VWAP - entry_threshold
    events.append(_trade_event(50, 5.0, 0.738))
    events.append(_book_event(51, 5.0, 0.735, 0.739))

    # Exit tick: price recovers to vwap - exit_threshold
    events.append(_trade_event(60, 6.0, 0.748))
    events.append(_book_event(61, 6.0, 0.745, 0.750))

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsVWAP(
        trade_size=1,
        vwap_window=5,
        entry_threshold=0.008,
        exit_threshold=0.002,
        take_profit=0.10,
        stop_loss=0.10,
    )
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 2
    assert decisions[0]["side"] == "BUY"
    assert decisions[1]["side"] == "SELL"


def test_sports_vwap_no_entry_insufficient_window(tmp_path: Path) -> None:
    """Fewer than vwap_window trades → strategy never activates → 0 decisions."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

    # Only 3 trade events; vwap_window=5 → not enough
    events = [
        _trade_event(0, 0.0, 0.75),
        _trade_event(1, 1.0, 0.74),
        _trade_event(2, 2.0, 0.73),
        _book_event(10, 3.0, 0.72, 0.74),
    ]
    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path, events)
    run_dir = tmp_path / "run"

    strategy = SportsVWAP(vwap_window=5, entry_threshold=0.008)
    StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    ).run()

    assert _read_decisions(run_dir) == []


def test_sports_vwap_min_tick_size_filters_small_trades() -> None:
    """V1: ticks with size < min_tick_size are excluded from VWAP accumulation.

    With min_tick_size=50, sizes 10 and 20 are filtered; size 100 is accepted.
    The window must fill with accepted ticks only.
    """
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

    strategy = SportsVWAP(
        vwap_window=3,
        min_tick_size=50.0,
        entry_threshold=0.05,
        exit_threshold=0.01,
        take_profit=0.10,
        stop_loss=0.10,
    )

    def _trade(price: float, size: float) -> dict:
        return {
            "event_type": "last_trade_price",
            "price": str(price),
            "size": str(size),
        }

    # Rejected ticks (size < 50) — window must remain empty
    strategy.on_event(_trade(0.60, 10.0), seq=0, ts_recv=0.0, best_bid=None, best_ask=None, open_orders={})
    strategy.on_event(_trade(0.61, 20.0), seq=1, ts_recv=1.0, best_bid=None, best_ask=None, open_orders={})
    assert len(strategy._window) == 0, "small-size ticks must not enter the window"

    # Three accepted ticks (size=100) — window fills
    strategy.on_event(_trade(0.60, 100.0), seq=2, ts_recv=2.0, best_bid=None, best_ask=None, open_orders={})
    strategy.on_event(_trade(0.61, 100.0), seq=3, ts_recv=3.0, best_bid=None, best_ask=None, open_orders={})
    strategy.on_event(_trade(0.60, 100.0), seq=4, ts_recv=4.0, best_bid=None, best_ask=None, open_orders={})
    assert len(strategy._window) == 3, "three accepted ticks must fill the window"

    # Now window is full; a tick well below VWAP with a valid ask should trigger BUY
    # VWAP ≈ 0.6033; entry_threshold=0.05 → entry when price < 0.5533
    result = strategy.on_event(
        _trade(0.50, 100.0),
        seq=5, ts_recv=5.0, best_bid=0.49, best_ask=0.51, open_orders={}
    )
    assert len(result) == 1
    assert result[0].side == "BUY"


def test_sports_vwap_take_profit_exit() -> None:
    """V3: exit reason is 'vwap_take_profit' when fill_price + take_profit is reached."""
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

    strategy = SportsVWAP(
        vwap_window=3,
        entry_threshold=0.05,
        exit_threshold=0.01,
        take_profit=0.05,
        stop_loss=0.10,
    )

    def _trade(price: float) -> dict:
        return {"event_type": "last_trade_price", "price": str(price), "size": "1.0"}

    # Fill window: 3 trades at ~0.60
    for i, p in enumerate([0.60, 0.61, 0.60]):
        strategy.on_event(_trade(p), seq=i, ts_recv=float(i), best_bid=None, best_ask=None, open_orders={})

    # VWAP ≈ 0.6033; entry when price < 0.5533 — send a low trade + valid ask
    strategy.on_event(
        _trade(0.50),
        seq=3, ts_recv=3.0, best_bid=0.49, best_ask=0.51, open_orders={}
    )

    # Simulate fill at 0.51
    strategy.on_fill("ord-1", ASSET_ID, "BUY", Decimal("0.51"), Decimal("1"), "filled", 3, 3.0)

    # Price reaches fill + take_profit = 0.51 + 0.05 = 0.56
    exit_intents = strategy.on_event(
        _trade(0.56),
        seq=4, ts_recv=4.0, best_bid=0.55, best_ask=0.57, open_orders={}
    )
    assert len(exit_intents) == 1
    assert exit_intents[0].side == "SELL"
    assert exit_intents[0].reason == "vwap_take_profit"


def test_sports_vwap_stop_loss_exit() -> None:
    """V4: exit reason is 'vwap_stop_loss' when price falls to fill_price - stop_loss."""
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

    strategy = SportsVWAP(
        vwap_window=3,
        entry_threshold=0.05,
        exit_threshold=0.01,
        take_profit=0.15,
        stop_loss=0.05,
    )

    def _trade(price: float) -> dict:
        return {"event_type": "last_trade_price", "price": str(price), "size": "1.0"}

    # Fill window
    for i, p in enumerate([0.60, 0.61, 0.60]):
        strategy.on_event(_trade(p), seq=i, ts_recv=float(i), best_bid=None, best_ask=None, open_orders={})

    # Trigger entry
    strategy.on_event(
        _trade(0.50),
        seq=3, ts_recv=3.0, best_bid=0.49, best_ask=0.51, open_orders={}
    )

    # Simulate fill at 0.51
    strategy.on_fill("ord-1", ASSET_ID, "BUY", Decimal("0.51"), Decimal("1"), "filled", 3, 3.0)

    # Price falls to fill - stop_loss = 0.51 - 0.05 = 0.46
    exit_intents = strategy.on_event(
        _trade(0.46),
        seq=4, ts_recv=4.0, best_bid=0.45, best_ask=0.47, open_orders={}
    )
    assert len(exit_intents) == 1
    assert exit_intents[0].side == "SELL"
    assert exit_intents[0].reason == "vwap_stop_loss"


def test_sports_vwap_size_weighted_vwap() -> None:
    """Size-weighted VWAP differs from equal-weight; entry fires only with correct weighting.

    Trades: (0.90, 1000), (0.90, 1000), (0.82, 1).
    Weighted VWAP = (0.90*1000 + 0.90*1000 + 0.82*1) / 2001 approx 0.9004.
    entry_threshold=0.05, so weighted trigger when price < 0.8504.
    Equal-weight VWAP = (0.90+0.90+0.82)/3 = 0.8733, trigger when price < 0.8233.
    last_price=0.82 satisfies weighted trigger (0.82 < 0.8504) but NOT equal-weight (0.82 >= 0.8233).
    The BUY on the 3rd trade proves size-weighted VWAP is used.
    """
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP

    strategy = SportsVWAP(
        vwap_window=3,
        entry_threshold=0.05,
        exit_threshold=0.01,
        take_profit=0.15,
        stop_loss=0.10,
    )

    def _trade(price: float, size: float) -> dict:
        return {"event_type": "last_trade_price", "price": str(price), "size": str(size)}

    # Two large high-price trades fill 2/3 of window; no best_ask so entry cannot fire
    strategy.on_event(_trade(0.90, 1000.0), seq=0, ts_recv=0.0, best_bid=None, best_ask=None, open_orders={})
    strategy.on_event(_trade(0.90, 1000.0), seq=1, ts_recv=1.0, best_bid=None, best_ask=None, open_orders={})

    # Third trade fills window; entry check fires in the same call.
    # Weighted VWAP approx 0.9004; last_price=0.82; 0.82 < 0.8504 => BUY
    # Equal-weight VWAP = 0.8733; 0.82 >= 0.8233 => would NOT trigger under equal-weight
    result = strategy.on_event(
        _trade(0.82, 1.0),
        seq=2, ts_recv=2.0, best_bid=0.81, best_ask=0.83, open_orders={}
    )
    assert len(result) == 1
    assert result[0].side == "BUY", "size-weighted VWAP must trigger entry at price=0.82"


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------


def test_strategy_registry_contains_all_three() -> None:
    """All three sports strategies are registered and can be instantiated via the registry."""
    from packages.polymarket.simtrader.strategy.facade import STRATEGY_REGISTRY, _build_strategy

    assert "sports_momentum" in STRATEGY_REGISTRY
    assert "sports_favorite" in STRATEGY_REGISTRY
    assert "sports_vwap" in STRATEGY_REGISTRY

    # Instantiate each via _build_strategy (same path used by CLI)
    sm = _build_strategy("sports_momentum", {})
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum
    assert isinstance(sm, SportsMomentum)

    sf = _build_strategy("sports_favorite", {})
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite
    assert isinstance(sf, SportsFavorite)

    sv = _build_strategy("sports_vwap", {})
    from packages.polymarket.simtrader.strategies.sports_vwap import SportsVWAP
    assert isinstance(sv, SportsVWAP)


def test_ns_config_keys_accepted() -> None:
    """_build_strategy must accept the documented *_ns config keys without raising."""
    from packages.polymarket.simtrader.strategy.facade import _build_strategy

    # These keys are what the validation pack and --strategy-config-json use
    sm = _build_strategy("sports_momentum", {
        "market_close_time_ns": 120_000_000_000.0,
        "final_period_minutes": 1.0,
    })
    from packages.polymarket.simtrader.strategies.sports_momentum import SportsMomentum
    assert isinstance(sm, SportsMomentum)
    # Verify the ns value was converted: 120e9 ns → 120s
    assert sm._cfg.market_close_time == pytest.approx(120.0)

    sf = _build_strategy("sports_favorite", {
        "activation_start_time_ns": 60_000_000_000.0,
        "market_close_time_ns": 120_000_000_000.0,
    })
    from packages.polymarket.simtrader.strategies.sports_favorite import SportsFavorite
    assert isinstance(sf, SportsFavorite)
    assert sf._cfg.activation_start_time == pytest.approx(60.0)
    assert sf._cfg.market_close_time == pytest.approx(120.0)
