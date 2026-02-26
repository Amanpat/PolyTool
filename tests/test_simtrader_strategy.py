"""Tests for SimTrader strategy interface, StrategyRunner, and CopyWalletReplay.

Test categories
---------------
1. Runner determinism — same tape + config => identical summary
2. CopyWalletReplay delay — signal_delay_ticks shifts submit seq as expected
3. End-to-end — tiny fixture tape + trade list => known ledger result
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

ASSET_ID = "test-asset-001"
BINARY_YES_ID = "yes-auto-001"
BINARY_NO_ID = "no-auto-001"

# A minimal tape: book snapshot + 5 price_change events
# Book at seq 0: bid=0.40 (500), ask=0.45 (300)
# seq 1: ask 0.45 reduced to 200
# seq 2: bid 0.41 added (100)
# seq 3: ask 0.45 reduced to 100
# seq 4: bid 0.42 added (50)
# seq 5: ask 0.46 added (150)
TAPE_EVENTS = [
    {
        "parser_version": 1,
        "seq": 0,
        "ts_recv": 0.0,
        "event_type": "book",
        "asset_id": ASSET_ID,
        "bids": [{"price": "0.40", "size": "500"}],
        "asks": [{"price": "0.45", "size": "300"}],
    },
    {
        "parser_version": 1,
        "seq": 1,
        "ts_recv": 1.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "SELL", "price": "0.45", "size": "200"}],
    },
    {
        "parser_version": 1,
        "seq": 2,
        "ts_recv": 2.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "BUY", "price": "0.41", "size": "100"}],
    },
    {
        "parser_version": 1,
        "seq": 3,
        "ts_recv": 3.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "SELL", "price": "0.45", "size": "100"}],
    },
    {
        "parser_version": 1,
        "seq": 4,
        "ts_recv": 4.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "BUY", "price": "0.42", "size": "50"}],
    },
    {
        "parser_version": 1,
        "seq": 5,
        "ts_recv": 5.0,
        "event_type": "price_change",
        "asset_id": ASSET_ID,
        "changes": [{"side": "SELL", "price": "0.46", "size": "150"}],
    },
]


def _write_tape(path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for event in TAPE_EVENTS:
            fh.write(json.dumps(event) + "\n")


def _write_binary_tape(path: Path) -> None:
    events = [
        {
            "parser_version": 1,
            "seq": 0,
            "ts_recv": 0.0,
            "event_type": "book",
            "asset_id": BINARY_YES_ID,
            "bids": [{"price": "0.40", "size": "200"}],
            "asks": [{"price": "0.44", "size": "200"}],
        },
        {
            "parser_version": 1,
            "seq": 1,
            "ts_recv": 1.0,
            "event_type": "book",
            "asset_id": BINARY_NO_ID,
            "bids": [{"price": "0.52", "size": "200"}],
            "asks": [{"price": "0.56", "size": "200"}],
        },
    ]
    with open(path, "w", encoding="utf-8") as fh:
        for event in events:
            fh.write(json.dumps(event) + "\n")


def _write_trades(path: Path, trades: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for t in trades:
            fh.write(json.dumps(t) + "\n")


def _read_decisions(run_dir: Path) -> list[dict]:
    path = run_dir / "decisions.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _read_summary(run_dir: Path) -> dict:
    return json.loads((run_dir / "summary.json").read_text())


def _read_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "run_manifest.json").read_text())


# ---------------------------------------------------------------------------
# Test 1: Runner determinism
# ---------------------------------------------------------------------------


def test_runner_determinism(tmp_path: Path) -> None:
    """Two StrategyRunner calls with identical inputs produce identical summaries."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(
        trades_path,
        [{"seq": 2, "side": "BUY", "limit_price": "0.50", "size": "100", "trade_id": "t1"}],
    )

    def _do_run(run_id: str) -> dict:
        run_dir = tmp_path / run_id
        strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
        runner = StrategyRunner(
            events_path=tape_path,
            run_dir=run_dir,
            strategy=strategy,
            starting_cash=Decimal("1000"),
        )
        return runner.run()

    summary_a = _do_run("run_a")
    summary_b = _do_run("run_b")

    # All numeric fields must match exactly (both runs are deterministic)
    for key in ("starting_cash", "net_profit", "realized_pnl", "total_fees",
                "final_cash", "final_equity"):
        assert summary_a[key] == summary_b[key], f"Mismatch in summary field {key!r}"

    # decisions.jsonl should also have the same structure
    decisions_a = _read_decisions(tmp_path / "run_a")
    decisions_b = _read_decisions(tmp_path / "run_b")
    assert len(decisions_a) == len(decisions_b)
    for da, db in zip(decisions_a, decisions_b):
        for k in ("action", "side", "limit_price", "size"):
            assert da[k] == db[k], f"Decision field {k!r} differs"


# ---------------------------------------------------------------------------
# Test 2: CopyWalletReplay delay behavior
# ---------------------------------------------------------------------------


def test_copy_wallet_delay_zero(tmp_path: Path) -> None:
    """With signal_delay_ticks=0, order is submitted at trade.seq (seq=2)."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(
        trades_path,
        [{"seq": 2, "side": "BUY", "limit_price": "0.50", "size": "100", "trade_id": "t1"}],
    )

    run_dir = tmp_path / "run_delay0"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    )
    runner.run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 1, "Expected exactly one decision"
    assert decisions[0]["action"] == "submit"
    assert decisions[0]["seq"] == 2, f"Expected seq=2 but got seq={decisions[0]['seq']}"
    assert decisions[0]["side"] == "BUY"


def test_copy_wallet_delay_two_ticks(tmp_path: Path) -> None:
    """With signal_delay_ticks=2, order for seq=2 is submitted at seq=4."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(
        trades_path,
        [{"seq": 2, "side": "BUY", "limit_price": "0.50", "size": "100", "trade_id": "t1"}],
    )

    run_dir = tmp_path / "run_delay2"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=2)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    )
    runner.run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 1, "Expected exactly one decision"
    assert decisions[0]["action"] == "submit"
    assert decisions[0]["seq"] == 4, f"Expected seq=4 but got seq={decisions[0]['seq']}"


def test_delay_shifts_submit_seq_relative_to_zero(tmp_path: Path) -> None:
    """Delay shifts the submit seq by exactly signal_delay_ticks events."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    # Trade at seq=1; with delay=3 → triggers at first seq >= 4
    _write_trades(
        trades_path,
        [{"seq": 1, "side": "BUY", "limit_price": "0.50", "size": "10"}],
    )

    def _submit_seq(delay: int) -> int:
        run_dir = tmp_path / f"run_d{delay}"
        strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=delay)
        runner = StrategyRunner(
            events_path=tape_path,
            run_dir=run_dir,
            strategy=strategy,
            starting_cash=Decimal("1000"),
        )
        runner.run()
        decisions = _read_decisions(run_dir)
        assert decisions, "Expected at least one decision"
        return decisions[0]["seq"]

    seq_d0 = _submit_seq(0)
    seq_d2 = _submit_seq(2)

    assert seq_d0 == 1, f"delay=0: expected seq=1, got {seq_d0}"
    assert seq_d2 == 3, f"delay=2: expected seq=3, got {seq_d2}"
    assert seq_d2 > seq_d0, "Delayed submit must happen later"


def test_delay_beyond_tape_end_produces_no_decision(tmp_path: Path) -> None:
    """A trade whose trigger_seq exceeds the last tape seq is never submitted."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)  # highest seq = 5
    _write_trades(
        trades_path,
        [{"seq": 3, "side": "BUY", "limit_price": "0.50", "size": "50"}],
    )

    run_dir = tmp_path / "run_too_late"
    # delay=10 → trigger_seq = 3 + 10 = 13, beyond seq=5
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=10)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    )
    runner.run()

    decisions = _read_decisions(run_dir)
    assert decisions == [], "No decisions expected when trigger_seq exceeds tape"


# ---------------------------------------------------------------------------
# Test 3: End-to-end known ledger result
# ---------------------------------------------------------------------------


def test_end_to_end_buy_fills_at_ask(tmp_path: Path) -> None:
    """BUY 100 shares at limit 0.50 against ask=0.45 → fills fully at 0.45."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(
        trades_path,
        [{"seq": 2, "side": "BUY", "limit_price": "0.50", "size": "100", "trade_id": "t1"}],
    )

    run_dir = tmp_path / "run_e2e"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
        fee_rate_bps=Decimal("200"),
        mark_method="bid",
    )
    pnl_summary = runner.run()

    # --- artifact files exist ---
    for fname in (
        "best_bid_ask.jsonl",
        "orders.jsonl",
        "fills.jsonl",
        "ledger.jsonl",
        "equity_curve.jsonl",
        "summary.json",
        "decisions.jsonl",
        "run_manifest.json",
        "meta.json",
    ):
        assert (run_dir / fname).exists(), f"Missing artifact: {fname}"

    # --- exactly one decision (the submit) ---
    decisions = _read_decisions(run_dir)
    assert len(decisions) == 1
    assert decisions[0]["action"] == "submit"
    assert decisions[0]["side"] == "BUY"
    assert decisions[0]["limit_price"] == "0.50"
    assert decisions[0]["size"] == "100"

    # --- order filled: manifest reports 1 fill ---
    manifest = _read_manifest(run_dir)
    assert manifest["fills_count"] == 1
    assert manifest["decisions_count"] == 1

    # --- fills.jsonl shows full fill ---
    fills = [
        json.loads(line)
        for line in (run_dir / "fills.jsonl").read_text().splitlines()
        if line.strip()
    ]
    assert len(fills) == 1
    assert fills[0]["fill_status"] == "full"
    assert Decimal(fills[0]["fill_price"]) == Decimal("0.45"), (
        f"Expected fill at ask 0.45, got {fills[0]['fill_price']}"
    )
    assert Decimal(fills[0]["fill_size"]) == Decimal("100")

    # --- summary has required fields ---
    for field_name in (
        "starting_cash", "final_cash", "final_equity",
        "realized_pnl", "unrealized_pnl", "total_fees", "net_profit",
    ):
        assert field_name in pnl_summary, f"summary missing field: {field_name}"

    # Cash spent: 100 shares at 0.45 + fee
    # Fees > 0 because fee_rate_bps=200
    assert Decimal(pnl_summary["total_fees"]) > 0
    assert Decimal(pnl_summary["starting_cash"]) == Decimal("1000")

    # Position held → final_cash < starting_cash (cash was used to buy)
    assert Decimal(pnl_summary["final_cash"]) < Decimal("1000")


def test_end_to_end_multiple_trades(tmp_path: Path) -> None:
    """Two trades in the fixture both fill; decisions.jsonl has two entries."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    # Two BUY trades both at limit > best_ask (0.45) → both fill
    _write_trades(
        trades_path,
        [
            {"seq": 1, "side": "BUY", "limit_price": "0.50", "size": "50", "trade_id": "t1"},
            {"seq": 3, "side": "BUY", "limit_price": "0.50", "size": "50", "trade_id": "t2"},
        ],
    )

    run_dir = tmp_path / "run_multi"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("2000"),
        fee_rate_bps=Decimal("0"),  # zero fees for cleaner assertions
        mark_method="bid",
    )
    runner.run()

    decisions = _read_decisions(run_dir)
    assert len(decisions) == 2, f"Expected 2 decisions, got {len(decisions)}"
    assert decisions[0]["seq"] == 1
    assert decisions[1]["seq"] == 3

    manifest = _read_manifest(run_dir)
    assert manifest["fills_count"] == 2
    assert manifest["decisions_count"] == 2


def test_end_to_end_no_fill_when_limit_too_low(tmp_path: Path) -> None:
    """A BUY with limit below best_ask never fills; position stays zero."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    # limit 0.30 < best_ask 0.45 → no fill
    _write_trades(
        trades_path,
        [{"seq": 0, "side": "BUY", "limit_price": "0.30", "size": "100"}],
    )

    run_dir = tmp_path / "run_nofill"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
        fee_rate_bps=Decimal("0"),
    )
    pnl_summary = runner.run()

    manifest = _read_manifest(run_dir)
    assert manifest["fills_count"] == 0

    # Cash should equal starting_cash minus reservation (order still open at end)
    # Actually - order is open (never cancelled) so cash is reserved but not spent.
    # Net profit should be 0 (no fills, no fees on unfilled orders)
    assert Decimal(pnl_summary["total_fees"]) == Decimal("0")


# ---------------------------------------------------------------------------
# Test 4: Strategy base class defaults
# ---------------------------------------------------------------------------


def test_strategy_base_defaults() -> None:
    """The base Strategy class provides safe no-op defaults."""
    from packages.polymarket.simtrader.strategy.base import Strategy

    s = Strategy()
    # on_start is a no-op
    s.on_start("tok", Decimal("1000"))

    # on_event returns empty list
    result = s.on_event({}, 0, 0.0, None, None, {})
    assert result == []

    # on_finish is a no-op
    s.on_finish()


def test_order_intent_defaults() -> None:
    """OrderIntent requires only action; all other fields default to None/{}."""
    from packages.polymarket.simtrader.strategy.base import OrderIntent

    intent = OrderIntent(action="submit")
    assert intent.action == "submit"
    assert intent.asset_id is None
    assert intent.side is None
    assert intent.limit_price is None
    assert intent.size is None
    assert intent.order_id is None
    assert intent.reason is None
    assert intent.meta == {}


# ---------------------------------------------------------------------------
# Test 5: No-trade run — ledger always has initial + final snapshots
# ---------------------------------------------------------------------------


def test_no_trade_ledger_has_initial_final_snapshots(tmp_path: Path) -> None:
    """A run with zero orders must still write >= 2 ledger rows: initial + final."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(trades_path, [])  # empty trade list → no orders submitted

    run_dir = tmp_path / "no_trade_run"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("500"),
    )
    runner.run()

    ledger_path = run_dir / "ledger.jsonl"
    assert ledger_path.exists(), "ledger.jsonl must always be written"

    lines = [ln for ln in ledger_path.read_text().splitlines() if ln.strip()]
    assert len(lines) >= 2, f"Expected >= 2 ledger lines for no-trade run, got {len(lines)}"

    first = json.loads(lines[0])
    last = json.loads(lines[-1])

    # First row is "initial" snapshot — cash equals starting_cash, no positions
    assert first["event"] == "initial", f"First ledger event should be 'initial', got {first['event']!r}"
    assert first["cash_usdc"] == "500", f"Expected cash_usdc='500', got {first['cash_usdc']!r}"
    assert first["positions"] == {}, "Initial snapshot must have empty positions"
    assert first["reserved_shares"] == {}, "Initial snapshot must have no reserved shares"
    assert first["realized_pnl"] == "0"
    assert first["total_fees"] == "0"

    # Last row is "final" snapshot — same state for no-trade run
    assert last["event"] == "final", f"Last ledger event should be 'final', got {last['event']!r}"
    assert last["cash_usdc"] == "500"
    assert last["positions"] == {}


def test_no_trade_ledger_seq_matches_tape_bounds(tmp_path: Path) -> None:
    """Initial snapshot seq matches first tape event; final matches last."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)   # seqs: 0, 1, 2, 3, 4, 5
    _write_trades(trades_path, [])

    run_dir = tmp_path / "no_trade_seqs"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    )
    runner.run()

    lines = [ln for ln in (run_dir / "ledger.jsonl").read_text().splitlines() if ln.strip()]
    first = json.loads(lines[0])
    last = json.loads(lines[-1])

    # TAPE_EVENTS seqs run 0..5; initial should be at seq=0, final at seq=5
    assert first["seq"] == 0
    assert last["seq"] == 5


def test_trade_run_ledger_unchanged_by_no_trade_fix(tmp_path: Path) -> None:
    """A run with orders must still have order-event snapshots (existing behavior)."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    # BUY at limit 0.50 >= ask 0.45 → will fill at seq 2
    _write_trades(
        trades_path,
        [{"seq": 2, "side": "BUY", "limit_price": "0.50", "size": "100", "trade_id": "t1"}],
    )

    run_dir = tmp_path / "trade_run_compat"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
        fee_rate_bps=Decimal("0"),
    )
    runner.run()

    lines = [ln for ln in (run_dir / "ledger.jsonl").read_text().splitlines() if ln.strip()]
    # Must have at least 2 rows (order_submitted + fill events)
    assert len(lines) >= 2

    # None of them should be the synthetic "initial"/"final" labels
    events = [json.loads(ln)["event"] for ln in lines]
    assert "initial" not in events, "Trade run must not have synthetic 'initial' snapshot"
    assert "final" not in events, "Trade run must not have synthetic 'final' snapshot"


# ---------------------------------------------------------------------------
# Test 5: CopyWalletReplay fixture loading
# ---------------------------------------------------------------------------


def test_copy_wallet_loads_fixture(tmp_path: Path) -> None:
    """CopyWalletReplay loads trades correctly from a JSONL fixture."""
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    trades_path = tmp_path / "trades.jsonl"
    _write_trades(
        trades_path,
        [
            {"seq": 5, "side": "buy", "limit_price": "0.45", "size": "100", "trade_id": "x1"},
            {"seq": 10, "side": "SELL", "limit_price": "0.60", "size": "50"},
        ],
    )

    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    strategy.on_start("tok", Decimal("500"))

    assert len(strategy._trades) == 2
    assert strategy._trades[0].side == "BUY"  # normalised to upper
    assert strategy._trades[0].seq == 5
    assert strategy._trades[1].side == "SELL"
    assert strategy._trades[1].trade_id == ""  # optional field absent


def test_copy_wallet_skips_malformed_lines(tmp_path: Path) -> None:
    """Malformed JSONL lines are skipped with a warning, valid lines loaded."""
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    trades_path = tmp_path / "trades.jsonl"
    trades_path.write_text(
        '{"seq": 1, "side": "BUY", "limit_price": "0.40", "size": "10"}\n'
        "this is not json\n"
        '{"seq": 2, "side": "SELL", "limit_price": "0.60", "size": "5"}\n',
        encoding="utf-8",
    )

    strategy = CopyWalletReplay(trades_path=trades_path)
    strategy.on_start("tok", Decimal("1000"))

    assert len(strategy._trades) == 2


# ---------------------------------------------------------------------------
# Test 6: CLI run subcommand
# ---------------------------------------------------------------------------


def test_cli_run_subcommand(tmp_path: Path) -> None:
    """``simtrader run`` CLI produces summary.json and decisions.jsonl."""
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    trades_path = tmp_path / "trades.jsonl"
    _write_tape(tape_path)
    _write_trades(
        trades_path,
        [{"seq": 2, "side": "BUY", "limit_price": "0.50", "size": "100"}],
    )

    run_id = "cli-test-run"
    strategy_cfg = json.dumps(
        {"trades_path": str(trades_path), "signal_delay_ticks": 0}
    )

    rc = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "copy_wallet_replay",
            "--strategy-config", strategy_cfg,
            "--run-id", run_id,
            "--starting-cash", "500",
            "--fee-rate-bps", "0",
        ]
    )
    assert rc == 0, f"CLI returned non-zero exit code: {rc}"

    run_dir = Path("artifacts/simtrader/runs") / run_id
    assert (run_dir / "summary.json").exists(), "summary.json not written"
    assert (run_dir / "decisions.jsonl").exists(), "decisions.jsonl not written"


def test_cli_run_strategy_config_json_string_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--strategy-config` JSON string is parsed once and passed through as dict."""
    import packages.polymarket.simtrader.strategy.facade as facade
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)

    expected = {
        "trades_path": "trades.jsonl",
        "signal_delay_ticks": 2,
    }
    captured: list[dict] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)

    rc = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "copy_wallet_replay",
            "--strategy-config", json.dumps(expected),
        ]
    )
    assert rc == 0
    assert captured == [expected]


def test_cli_run_strategy_config_path_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--strategy-config-path` JSON file is parsed and passed through as dict."""
    import packages.polymarket.simtrader.strategy.facade as facade
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)

    expected = {
        "trades_path": "trades.jsonl",
        "signal_delay_ticks": 2,
    }
    cfg_path = tmp_path / "strategy_config.json"
    cfg_path.write_text(json.dumps(expected), encoding="utf-8")

    captured: list[dict] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)

    rc = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "copy_wallet_replay",
            "--strategy-config-path", str(cfg_path),
        ]
    )
    assert rc == 0
    assert captured == [expected]


def test_cli_run_strategy_config_string_and_path_parse_identically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """String and file config paths produce identical parsed dicts."""
    import packages.polymarket.simtrader.strategy.facade as facade
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)

    expected = {
        "trades_path": "trades.jsonl",
        "signal_delay_ticks": 2,
    }
    cfg_path = tmp_path / "strategy_config.json"
    cfg_path.write_text(json.dumps(expected), encoding="utf-8")

    captured: list[dict] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)

    rc_str = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "copy_wallet_replay",
            "--strategy-config", json.dumps(expected),
        ]
    )
    rc_path = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "copy_wallet_replay",
            "--strategy-config-path", str(cfg_path),
        ]
    )

    assert rc_str == 0
    assert rc_path == 0
    assert captured == [expected, expected]


def test_cli_run_strategy_config_and_path_are_mutually_exclusive(tmp_path: Path) -> None:
    """Providing both strategy-config flags returns error."""
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)
    cfg_path = tmp_path / "strategy_config.json"
    cfg_path.write_text('{"signal_delay_ticks": 1}', encoding="utf-8")

    rc = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "copy_wallet_replay",
            "--strategy-config", '{"signal_delay_ticks": 0}',
            "--strategy-config-path", str(cfg_path),
        ]
    )
    assert rc == 1


def test_cli_run_unknown_strategy(tmp_path: Path) -> None:
    """``simtrader run`` with an unknown strategy name returns exit code 1."""
    from tools.cli.simtrader import main as simtrader_main

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)

    rc = simtrader_main(
        [
            "run",
            "--tape", str(tape_path),
            "--strategy", "nonexistent_strategy_xyz",
            "--strategy-config", "{}",
        ]
    )
    assert rc == 1


def test_cli_run_binary_arb_manual_yes_no_without_asset_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_manual_only"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)

    captured_configs: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured_configs.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", tmp_path / "artifacts" / "simtrader")

    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--yes-asset-id",
            "yes-manual",
            "--no-asset-id",
            "no-manual",
            "--run-id",
            "manual-no-asset-id",
        ]
    )
    assert rc == 0
    assert len(captured_configs) == 1
    assert captured_configs[0]["yes_asset_id"] == "yes-manual"
    assert captured_configs[0]["no_asset_id"] == "no-manual"
    assert captured_asset_ids == ["yes-manual"]


def test_cli_run_binary_arb_strategy_config_json_merges_with_inferred_ids(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_cfg_json_merge"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "quickrun_context": {
                    "yes_token_id": BINARY_YES_ID,
                    "no_token_id": BINARY_NO_ID,
                }
            }
        ),
        encoding="utf-8",
    )

    captured_configs: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured_configs.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        params.run_dir.mkdir(parents=True, exist_ok=True)
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": params.run_dir.name}) + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--strategy-config-json",
            '{"buffer": 0.02, "max_size": 7}',
            "--run-id",
            "cfg-json-merge",
        ]
    )
    assert rc == 0
    assert len(captured_configs) == 1
    cfg = captured_configs[0]
    assert cfg["yes_asset_id"] == BINARY_YES_ID
    assert cfg["no_asset_id"] == BINARY_NO_ID
    assert cfg["buffer"] == 0.02
    assert cfg["max_size"] == 7
    assert captured_asset_ids == [BINARY_YES_ID]


def test_cli_run_binary_arb_strategy_preset_loose_expands_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_preset_loose"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)

    captured_configs: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured_configs.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", tmp_path / "artifacts" / "simtrader")

    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--yes-asset-id",
            "yes-loose",
            "--no-asset-id",
            "no-loose",
            "--strategy-preset",
            "loose",
        ]
    )
    assert rc == 0
    assert len(captured_configs) == 1
    cfg = captured_configs[0]
    assert cfg["yes_asset_id"] == "yes-loose"
    assert cfg["no_asset_id"] == "no-loose"
    assert cfg["max_size"] == 1
    assert abs(float(cfg["buffer"]) - 0.0005) < 1e-12
    assert cfg["max_notional_usdc"] == 25
    assert captured_asset_ids == ["yes-loose"]


def test_cli_run_reproduce_includes_non_default_flags(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_path = tmp_path / "events.jsonl"
    _write_tape(tape_path)

    def _fake_run_strategy(_params):
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", tmp_path / "artifacts" / "simtrader")

    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "copy_wallet_replay",
            "--strategy-config-json",
            '{"trades_path":"trades.jsonl"}',
            "--run-id",
            "repro-non-defaults",
            "--starting-cash",
            "500",
            "--fee-rate-bps",
            "10",
            "--mark-method",
            "midpoint",
            "--latency-ticks",
            "2",
            "--cancel-latency-ticks",
            "3",
            "--strict",
            "--allow-degraded",
        ]
    )
    assert rc == 0

    out = capsys.readouterr().out
    assert "Reproduce" in out
    assert "--strategy-config-json" in out
    assert "--run-id repro-non-defaults" in out
    assert "--starting-cash 500.0" in out
    assert "--fee-rate-bps 10.0" in out
    assert "--mark-method midpoint" in out
    assert "--latency-ticks 2" in out
    assert "--cancel-latency-ticks 3" in out
    assert "--strict" in out
    assert "--allow-degraded" in out


def test_cli_run_binary_arb_infers_ids_from_quickrun_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_quickrun"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "quickrun_context": {
                    "yes_token_id": BINARY_YES_ID,
                    "no_token_id": BINARY_NO_ID,
                }
            }
        ),
        encoding="utf-8",
    )

    captured: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        params.run_dir.mkdir(parents=True, exist_ok=True)
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": params.run_dir.name}) + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_id = "infer-quickrun-meta"
    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--run-id",
            run_id,
        ]
    )
    assert rc == 0
    assert len(captured) == 1
    cfg = captured[0]
    assert cfg["yes_asset_id"] == BINARY_YES_ID
    assert cfg["no_asset_id"] == BINARY_NO_ID
    assert cfg["buffer"] == 0.01
    assert cfg["max_size"] == 50
    assert captured_asset_ids == [BINARY_YES_ID]

    manifest = json.loads(
        (artifacts_root / "runs" / run_id / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.get("inferred_ids_from_tape_meta") is True


def test_cli_run_binary_arb_infers_ids_from_shadow_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_shadow"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "shadow_context": {
                    "yes_token_id": BINARY_YES_ID,
                    "no_token_id": BINARY_NO_ID,
                }
            }
        ),
        encoding="utf-8",
    )

    captured: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        params.run_dir.mkdir(parents=True, exist_ok=True)
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": params.run_dir.name}) + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_id = "infer-shadow-meta"
    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--run-id",
            run_id,
        ]
    )
    assert rc == 0
    assert len(captured) == 1
    cfg = captured[0]
    assert cfg["yes_asset_id"] == BINARY_YES_ID
    assert cfg["no_asset_id"] == BINARY_NO_ID
    assert cfg["buffer"] == 0.01
    assert cfg["max_size"] == 50
    assert captured_asset_ids == [BINARY_YES_ID]

    manifest = json.loads(
        (artifacts_root / "runs" / run_id / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.get("inferred_ids_from_tape_meta") is True


def test_cli_run_writes_market_context_manifest_when_ids_inferred(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_id = "20260225T234032Z_shadow_97449340"
    tape_dir = tmp_path / "legacy_tapes" / tape_id
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "shadow_context": {
                    "selected_slug": "inferred-shadow-market",
                    "yes_token_id": BINARY_YES_ID,
                    "no_token_id": BINARY_NO_ID,
                }
            }
        ),
        encoding="utf-8",
    )

    def _fake_run_strategy(params):
        params.run_dir.mkdir(parents=True, exist_ok=True)
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": params.run_dir.name}) + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_id = "manifest-market-context-inferred"
    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--run-id",
            run_id,
        ]
    )
    assert rc == 0

    manifest = json.loads(
        (artifacts_root / "runs" / run_id / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.get("market_slug") == "inferred-shadow-market"
    assert manifest.get("inferred_ids_from_tape_meta") is True

    market_context = manifest.get("market_context")
    assert isinstance(market_context, dict)
    assert market_context.get("market_slug") == "inferred-shadow-market"
    assert market_context.get("yes_token_id") == BINARY_YES_ID
    assert market_context.get("no_token_id") == BINARY_NO_ID
    assert market_context.get("tape_id") == tape_id
    assert market_context.get("tape_path") == str(tape_path)


def test_run_infers_from_shadow_run_manifest_when_tape_meta_missing_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_id = "20260225T234032Z_shadow_97449340"
    tape_dir = tmp_path / "legacy_tapes" / tape_id
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "source": "websocket",
                "event_count": 2,
            }
        ),
        encoding="utf-8",
    )

    artifacts_root = tmp_path / "artifacts" / "simtrader"
    shadow_manifest_dir = artifacts_root / "shadow_runs" / tape_id
    shadow_manifest_dir.mkdir(parents=True, exist_ok=True)
    (shadow_manifest_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": tape_id,
                "shadow_context": {
                    "selected_slug": "fallback-shadow-market",
                    "yes_token_id": BINARY_YES_ID,
                    "no_token_id": BINARY_NO_ID,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    captured: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        params.run_dir.mkdir(parents=True, exist_ok=True)
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": params.run_dir.name}) + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_id = "infer-from-shadow-run-manifest"
    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--run-id",
            run_id,
        ]
    )
    assert rc == 0
    assert len(captured) == 1
    cfg = captured[0]
    assert cfg["yes_asset_id"] == BINARY_YES_ID
    assert cfg["no_asset_id"] == BINARY_NO_ID
    assert captured_asset_ids == [BINARY_YES_ID]

    manifest = json.loads(
        (artifacts_root / "runs" / run_id / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest.get("inferred_ids_from_tape_meta") is True


def test_cli_run_binary_arb_meta_missing_contexts_has_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_bad_meta"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "quickrun_context": {"yes_token_id": BINARY_YES_ID},
                "shadow_context": {},
            }
        ),
        encoding="utf-8",
    )

    def _should_not_run(_params):
        raise AssertionError("run_strategy should not be called when ID inference fails")

    monkeypatch.setattr(facade, "run_strategy", _should_not_run)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--run-id",
            "infer-missing-meta",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "requires yes/no asset IDs" in err
    assert "--strategy-config" in err
    assert "--strategy-config-path" in err
    assert "--yes-asset-id" in err
    assert "--no-asset-id" in err


def test_cli_run_binary_arb_missing_meta_file_has_clear_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_no_meta"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)

    def _should_not_run(_params):
        raise AssertionError("run_strategy should not be called when meta.json is missing")

    monkeypatch.setattr(facade, "run_strategy", _should_not_run)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--run-id",
            "infer-no-meta",
        ]
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "requires yes/no asset IDs" in err
    assert "meta.json is missing" in err
    assert "--strategy-config" in err
    assert "--strategy-config-path" in err


def test_cli_run_binary_arb_manual_yes_no_flags_override_meta(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import packages.polymarket.simtrader.strategy.facade as facade
    import tools.cli.simtrader as simtrader_cli

    tape_dir = tmp_path / "tape_manual_override"
    tape_dir.mkdir(parents=True, exist_ok=True)
    tape_path = tape_dir / "events.jsonl"
    _write_binary_tape(tape_path)
    (tape_dir / "meta.json").write_text(
        json.dumps(
            {
                "quickrun_context": {
                    "yes_token_id": BINARY_YES_ID,
                    "no_token_id": BINARY_NO_ID,
                }
            }
        ),
        encoding="utf-8",
    )

    captured: list[dict] = []
    captured_asset_ids: list[str | None] = []

    def _fake_run_strategy(params):
        captured.append(params.strategy_config)
        captured_asset_ids.append(params.asset_id)
        params.run_dir.mkdir(parents=True, exist_ok=True)
        (params.run_dir / "run_manifest.json").write_text(
            json.dumps({"run_id": params.run_dir.name}) + "\n",
            encoding="utf-8",
        )
        return SimpleNamespace(metrics={"net_profit": "0"})

    monkeypatch.setattr(facade, "run_strategy", _fake_run_strategy)
    artifacts_root = tmp_path / "artifacts" / "simtrader"
    monkeypatch.setattr(simtrader_cli, "DEFAULT_ARTIFACTS_DIR", artifacts_root)

    run_id = "manual-override-meta"
    rc = simtrader_cli.main(
        [
            "run",
            "--tape",
            str(tape_path),
            "--strategy",
            "binary_complement_arb",
            "--yes-asset-id",
            "yes-manual",
            "--no-asset-id",
            "no-manual",
            "--run-id",
            run_id,
        ]
    )
    assert rc == 0
    assert len(captured) == 1
    cfg = captured[0]
    assert cfg["yes_asset_id"] == "yes-manual"
    assert cfg["no_asset_id"] == "no-manual"
    assert captured_asset_ids == ["yes-manual"]

    manifest = json.loads(
        (artifacts_root / "runs" / run_id / "run_manifest.json").read_text(encoding="utf-8")
    )
    assert "inferred_ids_from_tape_meta" not in manifest


# ---------------------------------------------------------------------------
# Batched price_changes[] format support in StrategyRunner
# ---------------------------------------------------------------------------


_YES_ID = "yes-tok-batch"
_NO_ID  = "no-tok-batch"


def _batched_tape_events() -> list[dict]:
    """Minimal tape with book snapshots + one modern batched price_change event."""
    return [
        # seq 0: YES snapshot
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": _YES_ID,
            "bids": [{"price": "0.44", "size": "300"}],
            "asks": [{"price": "0.46", "size": "200"}],
        },
        # seq 1: NO snapshot
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "book", "asset_id": _NO_ID,
            "bids": [{"price": "0.52", "size": "100"}],
            "asks": [{"price": "0.54", "size": "150"}],
        },
        # seq 2: batched price_change — updates YES bid + NO ask in one message.
        {
            "parser_version": 1, "seq": 2, "ts_recv": 2.0,
            "event_type": "price_change",
            # No top-level asset_id — modern format.
            "price_changes": [
                {"asset_id": _YES_ID, "side": "BUY",  "price": "0.45", "size": "80"},
                {"asset_id": _NO_ID,  "side": "SELL", "price": "0.53", "size": "90"},
            ],
        },
    ]


def _write_batched_tape(path: Path) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for evt in _batched_tape_events():
            fh.write(json.dumps(evt) + "\n")


def test_batched_price_change_updates_both_books(tmp_path: Path) -> None:
    """A modern batched price_changes[] event updates both YES and NO books."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    _write_batched_tape(tape_path)

    trades_path = tmp_path / "trades.jsonl"
    trades_path.write_text("")  # no trades — passive observer

    run_dir = tmp_path / "run_batched"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=_YES_ID,
        extra_book_asset_ids=[_NO_ID],
        starting_cash=Decimal("1000"),
    )
    runner.run()

    # best_bid_ask.jsonl is the primary-asset timeline.
    rows = [
        json.loads(l)
        for l in (run_dir / "best_bid_ask.jsonl").read_text().splitlines()
        if l.strip()
    ]
    # Expect: YES book snapshot (seq=0) + YES update from batch (seq=2).
    # NO snapshot (seq=1) does NOT emit a row because NO is not the primary asset.
    assert len(rows) == 2, f"Expected 2 timeline rows, got {len(rows)}: {rows}"

    # After the batched event, YES best_bid should be 0.45 (updated by batch).
    batch_row = rows[-1]
    assert batch_row["seq"] == 2
    assert batch_row["best_bid"] == pytest.approx(0.45)


def test_batched_price_change_timeline_rows_gt_one(tmp_path: Path) -> None:
    """timeline_rows > 1 confirms batched events are being processed."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    tape_path = tmp_path / "events.jsonl"
    _write_batched_tape(tape_path)

    trades_path = tmp_path / "trades.jsonl"
    trades_path.write_text("")

    run_dir = tmp_path / "run_batched2"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=_YES_ID,
        extra_book_asset_ids=[_NO_ID],
        starting_cash=Decimal("1000"),
    )
    runner.run()

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["timeline_rows"] > 1, (
        "timeline_rows should be > 1 after batched price_changes[] update"
    )


def test_batched_price_change_resolve_asset_id(tmp_path: Path) -> None:
    """_resolve_asset_id works for tapes where price_changes[] carry the asset_id."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    # Single-asset tape: one book snapshot + one batched price_change (no top-level id).
    SOLO_ID = "solo-tok"
    events = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": SOLO_ID,
            "bids": [{"price": "0.40", "size": "100"}],
            "asks": [{"price": "0.42", "size": "100"}],
        },
        {
            "parser_version": 1, "seq": 1, "ts_recv": 1.0,
            "event_type": "price_change",
            "price_changes": [
                {"asset_id": SOLO_ID, "side": "BUY", "price": "0.41", "size": "50"},
            ],
        },
    ]
    tape_path = tmp_path / "events.jsonl"
    with open(tape_path, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")

    trades_path = tmp_path / "trades.jsonl"
    trades_path.write_text("")

    run_dir = tmp_path / "run_solo"
    # asset_id NOT passed — must be auto-detected from the tape.
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        starting_cash=Decimal("1000"),
    )
    runner.run()

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["asset_id"] == SOLO_ID
    assert manifest["timeline_rows"] == 2  # snapshot + batch update


def test_blank_run_warning_in_manifest(tmp_path: Path) -> None:
    """When timeline_rows stays at 1 despite large total_events, manifest warns."""
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.strategies.copy_wallet_replay import CopyWalletReplay

    # Tape has one book snapshot and many events for a DIFFERENT (untracked) asset.
    OTHER_ID = "other-tok"
    events = [
        {
            "parser_version": 1, "seq": 0, "ts_recv": 0.0,
            "event_type": "book", "asset_id": ASSET_ID,
            "bids": [{"price": "0.40", "size": "100"}],
            "asks": [{"price": "0.42", "size": "100"}],
        },
    ]
    # Add 10 price_change events for a different asset (untracked).
    for i in range(1, 11):
        events.append({
            "parser_version": 1, "seq": i, "ts_recv": float(i),
            "event_type": "price_change", "asset_id": OTHER_ID,
            "changes": [{"side": "BUY", "price": "0.30", "size": str(i * 10)}],
        })

    tape_path = tmp_path / "events.jsonl"
    with open(tape_path, "w") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")

    trades_path = tmp_path / "trades.jsonl"
    trades_path.write_text("")

    run_dir = tmp_path / "run_blank"
    strategy = CopyWalletReplay(trades_path=trades_path, signal_delay_ticks=0)
    runner = StrategyRunner(
        events_path=tape_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=ASSET_ID,
        starting_cash=Decimal("1000"),
    )
    runner.run()

    manifest = json.loads((run_dir / "run_manifest.json").read_text())
    assert manifest["timeline_rows"] == 1
    # The blank-run warning should be present.
    assert any("timeline_rows" in w for w in manifest.get("warnings", [])), (
        f"Expected blank-run warning in manifest, got: {manifest.get('warnings')}"
    )
