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
