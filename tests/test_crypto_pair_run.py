from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

import packages.polymarket.crypto_pairs.paper_runner as paper_runner_module
from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.paper_runner import (
    CryptoPairPaperRunner,
    _dashboard_header,
    _dashboard_market_line,
    _dashboard_stats_line,
    build_runner_settings,
)
from packages.polymarket.crypto_pairs.opportunity_scan import PairOpportunity
from packages.polymarket.crypto_pairs.position_store import CryptoPairPositionStore
from packages.polymarket.crypto_pairs.reference_feed import (
    FeedConnectionState,
    ReferencePriceSnapshot,
)
from tools.cli.crypto_pair_run import build_parser, run_crypto_pair_runner


def _make_mock_market(
    slug: str = "btc-5m-up",
    question: str = "Will BTC be higher in 5 minutes?",
    symbol: str = "BTC",
) -> MagicMock:
    market = MagicMock()
    market.market_slug = slug
    market.question = question
    market.clob_token_ids = [f"{slug}-yes", f"{slug}-no"]
    market.outcomes = ["Yes", "No"]
    market.active = True
    market.accepting_orders = True
    market.condition_id = f"cond-{slug}"
    market.end_date_iso = None
    return market


def _make_gamma_client(markets: list[MagicMock]) -> MagicMock:
    result = MagicMock()
    result.markets = markets
    client = MagicMock()
    client.fetch_all_markets.return_value = result
    return client


def _make_clob_client(
    prices: dict[str, tuple[Optional[float], Optional[float]]],
) -> MagicMock:
    def _side_effect(token_id: str):
        if token_id not in prices:
            return None
        best_bid, best_ask = prices[token_id]
        return OrderBookTop(
            token_id=token_id,
            best_bid=best_bid,
            best_ask=best_ask,
            raw_json={},
        )

    client = MagicMock()
    client.get_best_bid_ask.side_effect = _side_effect
    return client


def _fresh_snapshot(
    symbol: str = "BTC",
    *,
    feed_source: str = "binance",
) -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=1000.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=False,
        stale_threshold_s=15.0,
        feed_source=feed_source,
    )


def _stale_snapshot(
    symbol: str = "BTC",
    *,
    feed_source: str = "binance",
) -> ReferencePriceSnapshot:
    return ReferencePriceSnapshot(
        symbol=symbol,
        price=60_000.0,
        observed_at_s=980.0,
        connection_state=FeedConnectionState.CONNECTED,
        is_stale=True,
        stale_threshold_s=15.0,
        feed_source=feed_source,
    )


class StaticFeed:
    def __init__(self, snapshot: ReferencePriceSnapshot) -> None:
        self.snapshot = snapshot

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        return self.snapshot


class MomentumFeed:
    """Feed that simulates a rising price to trigger an UP momentum signal.

    Returns the base snapshot price for the first ``history_depth`` calls,
    then returns a price that is ``rise_pct`` above the base. After
    ``history_depth + 1`` calls the runner's internal price history deque
    contains a move larger than the default 0.3% threshold.
    """

    def __init__(
        self,
        base_snapshot: ReferencePriceSnapshot,
        *,
        rise_pct: float = 0.01,
        history_depth: int = 2,
    ) -> None:
        self._base = base_snapshot
        self._rise_pct = rise_pct
        self._history_depth = history_depth
        self._call_count: int = 0

    def connect(self) -> None:
        return None

    def disconnect(self) -> None:
        return None

    def get_snapshot(self, symbol: str) -> ReferencePriceSnapshot:
        import dataclasses

        self._call_count += 1
        if self._call_count <= self._history_depth:
            price = self._base.price
        else:
            price = self._base.price * (1.0 + self._rise_pct)
        return dataclasses.replace(self._base, price=price)


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_paper_default_path_creates_jsonl_bundle(tmp_path: Path) -> None:
    # Uses 3 cycles + MomentumFeed so the directional entry fires on cycle 3:
    # Cycles 1-2 seed the price history at the base price; cycle 3 returns +1%
    # which clears the 0.3% momentum threshold.
    # yes_ask=0.72 < max_favorite_entry=0.75 -> favorite=YES fills.
    # no_ask=0.18 < max_hedge_price=0.20 -> hedge=NO fills (paired).
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=3,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        config_payload={"paper_config": {"momentum": {"momentum_threshold": 0.003}}},
    )

    run_dir = Path(manifest["artifact_dir"])
    assert manifest["mode"] == "paper"
    assert manifest["stopped_reason"] == "completed"
    assert run_dir.exists()
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "config_snapshot.json").exists()
    assert (run_dir / "runtime_events.jsonl").exists()
    assert (run_dir / "observations.jsonl").exists()
    assert (run_dir / "order_intents.jsonl").exists()
    assert (run_dir / "fills.jsonl").exists()
    assert (run_dir / "exposures.jsonl").exists()
    assert (run_dir / "market_rollups.jsonl").exists()
    assert (run_dir / "run_summary.json").exists()

    intents = _read_jsonl(run_dir / "order_intents.jsonl")
    fills = _read_jsonl(run_dir / "fills.jsonl")
    exposures = _read_jsonl(run_dir / "exposures.jsonl")
    assert len(intents) == 1
    assert len(fills) == 2
    assert len(exposures) == 1
    assert exposures[0]["exposure_status"] == "paired"


def test_paper_disconnect_freezes_new_intents_and_logs_transition(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_stale_snapshot()),
    )

    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")
    intents_path = run_dir / "order_intents.jsonl"

    assert not intents_path.exists()
    assert any(
        event["event_type"] == "feed_state_changed"
        and event["payload"]["to_state"] == "stale"
        for event in runtime_events
    )
    assert any(
        event["event_type"] == "paper_new_intents_frozen"
        for event in runtime_events
    )


def test_duration_window_stops_after_expected_cycles(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    sleep_calls: list[int] = []

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 5},
        artifact_base_dir=tmp_path,
        duration_seconds=11,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
    )

    manifest = runner.run()

    assert manifest["stopped_reason"] == "completed"
    assert manifest["runner_result"]["cycles_completed"] == 3
    assert sleep_calls == [5, 5]


def test_runner_emits_heartbeat_event_and_callback(tmp_path: Path) -> None:
    # Uses 3 cycles + MomentumFeed so the directional entry fires on cycle 3
    # (cycles 1-2 seed the baseline price history, cycle 3 is +1% = UP signal).
    # yes_ask=0.72, no_ask=0.18 ensures both legs fill (hedge ask <= max_hedge_price).
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.72),
            "btc-5m-up-no": (None, 0.18),
        }
    )
    started_at = datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc)
    current_time = started_at + timedelta(minutes=2)
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
        started_at=started_at,
    )
    heartbeat_payloads: list[dict] = []

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 5},
        artifact_base_dir=tmp_path,
        duration_seconds=0,
        cycle_limit=3,
        heartbeat_interval_seconds=60,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=MomentumFeed(_fresh_snapshot(), rise_pct=0.01, history_depth=2),
        store=store,
        heartbeat_callback=heartbeat_payloads.append,
        now_fn=lambda: current_time,
        sleep_fn=lambda _: None,
    )

    manifest = runner.run()

    runtime_events = _read_jsonl(Path(manifest["artifact_dir"]) / "runtime_events.jsonl")
    heartbeats = [
        event for event in runtime_events if event["event_type"] == "runner_heartbeat"
    ]

    # Heartbeat fires after cycle 1 (elapsed=120s >= interval=60s, frozen clock).
    # Cycle 1 records 1 observation but the momentum signal doesn't fire until cycle 3,
    # so intents_generated and completed_pairs are 0 at heartbeat time.
    assert len(heartbeats) == 1
    assert heartbeat_payloads[0]["elapsed_runtime"] == "00:02:00"
    assert heartbeats[0]["payload"]["opportunities_observed"] == 1
    assert heartbeats[0]["payload"]["intents_generated"] == 0
    assert heartbeats[0]["payload"]["completed_pairs"] == 0
    assert heartbeats[0]["payload"]["partial_exposure_count"] == 0
    assert heartbeats[0]["payload"]["latest_feed_states"] == {"BTC": "connected_fresh"}
    assert heartbeats[0]["payload"]["stale_symbols"] == []


def test_operator_interrupt_finalizes_artifacts_cleanly(tmp_path: Path) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 5},
        artifact_base_dir=tmp_path,
        duration_seconds=10,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        sleep_fn=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
    )

    manifest = runner.run()
    run_dir = Path(manifest["artifact_dir"])
    runtime_events = _read_jsonl(run_dir / "runtime_events.jsonl")

    assert manifest["stopped_reason"] == "operator_interrupt"
    assert (run_dir / "run_manifest.json").exists()
    assert (run_dir / "run_summary.json").exists()
    assert any(
        event["event_type"] == "operator_interrupt"
        for event in runtime_events
    )


def test_cli_help_includes_reference_feed_provider_flag() -> None:
    help_text = build_parser().format_help()

    assert "--reference-feed-provider" in help_text
    assert "binance" in help_text
    assert "coinbase" in help_text
    assert "auto" in help_text


def test_run_defaults_to_binance_reference_feed_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    selected: dict[str, str] = {}

    def _fake_build_reference_feed(provider: str):
        selected["provider"] = provider
        return StaticFeed(_fresh_snapshot(feed_source="binance"))

    monkeypatch.setattr(paper_runner_module, "build_reference_feed", _fake_build_reference_feed)

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=gamma,
        clob_client=clob,
    )

    config_snapshot = json.loads(
        (Path(manifest["artifact_dir"]) / "config_snapshot.json").read_text(
            encoding="utf-8"
        )
    )

    assert selected["provider"] == "binance"
    assert config_snapshot["runner"]["reference_feed_provider"] == "binance"


def test_run_allows_coinbase_reference_feed_provider_from_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    selected: dict[str, str] = {}

    def _fake_build_reference_feed(provider: str):
        selected["provider"] = provider
        return StaticFeed(_fresh_snapshot(feed_source="coinbase"))

    monkeypatch.setattr(paper_runner_module, "build_reference_feed", _fake_build_reference_feed)

    manifest = run_crypto_pair_runner(
        output_base=tmp_path,
        duration_seconds=0,
        cycle_limit=1,
        gamma_client=gamma,
        clob_client=clob,
        config_payload={"reference_feed_provider": "coinbase"},
    )

    config_snapshot = json.loads(
        (Path(manifest["artifact_dir"]) / "config_snapshot.json").read_text(
            encoding="utf-8"
        )
    )

    assert selected["provider"] == "coinbase"
    assert config_snapshot["runner"]["reference_feed_provider"] == "coinbase"


def test_run_rejects_unsupported_reference_feed_provider(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported reference_feed_provider"):
        run_crypto_pair_runner(
            output_base=tmp_path,
            duration_seconds=0,
            cycle_limit=1,
            reference_feed_provider="kraken",
        )


# ---------------------------------------------------------------------------
# Task 1 TDD tests — duration bug fix + dashboard module
# ---------------------------------------------------------------------------


class _AdvancingClock:
    """Each call to __call__() advances the clock by ``step_seconds``."""

    def __init__(self, start: datetime, step_seconds: float) -> None:
        self._current = start
        self._step = timedelta(seconds=step_seconds)

    def __call__(self) -> datetime:
        t = self._current
        self._current += self._step
        return t


def test_duration_stops_on_elapsed_time(tmp_path: Path) -> None:
    """Runner stops when wall-clock elapsed >= duration_seconds, even when cycle_limit > remaining."""
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    start = datetime(2026, 3, 29, 20, 0, 0, tzinfo=timezone.utc)
    # Each now_fn() call advances 2 seconds; duration_seconds=3 → stops after 2 cycles
    # (elapsed reaches 4s after cycle 2 sleep check)
    advancing_clock = _AdvancingClock(start, step_seconds=2.0)

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 0.5},
        artifact_base_dir=tmp_path,
        duration_seconds=3,
        cycle_limit=20,
    )
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
        started_at=start,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        store=store,
        now_fn=advancing_clock,
        sleep_fn=lambda _: None,
    )

    manifest = runner.run()
    assert manifest["runner_result"]["cycles_completed"] < 20


def test_duration_runs_all_cycles_when_fast(tmp_path: Path) -> None:
    """Runner runs all 5 cycles when each cycle is 1s and duration is 30s."""
    market = _make_mock_market()
    gamma = _make_gamma_client([market])
    clob = _make_clob_client(
        {
            "btc-5m-up-yes": (None, 0.47),
            "btc-5m-up-no": (None, 0.48),
        }
    )
    start = datetime(2026, 3, 29, 20, 0, 0, tzinfo=timezone.utc)
    advancing_clock = _AdvancingClock(start, step_seconds=1.0)

    settings = build_runner_settings(
        config_payload={"cycle_interval_seconds": 0.5},
        artifact_base_dir=tmp_path,
        duration_seconds=30,
        cycle_limit=5,
    )
    store = CryptoPairPositionStore(
        mode="paper",
        artifact_base_dir=tmp_path,
        started_at=start,
    )
    runner = CryptoPairPaperRunner(
        settings,
        gamma_client=gamma,
        clob_client=clob,
        reference_feed=StaticFeed(_fresh_snapshot()),
        store=store,
        now_fn=advancing_clock,
        sleep_fn=lambda _: None,
    )

    manifest = runner.run()
    assert manifest["runner_result"]["cycles_completed"] == 5


def _make_opportunity(
    slug: str = "btc-5m-1234",
    symbol: str = "BTC",
    yes_ask: Optional[float] = 0.55,
    no_ask: Optional[float] = 0.42,
) -> PairOpportunity:
    return PairOpportunity(
        slug=slug,
        symbol=symbol,
        duration_min=5,
        question=f"Will {symbol} be higher in 5 minutes?",
        condition_id=f"cond-{slug}",
        yes_token_id=f"{slug}-yes",
        no_token_id=f"{slug}-no",
        yes_ask=yes_ask,
        no_ask=no_ask,
        book_status="ok",
        assumptions=[],
    )


def test_dashboard_header_format() -> None:
    settings = build_runner_settings(
        config_payload={},
        duration_seconds=30,
    )
    header = _dashboard_header(settings, market_count=12, started_at_str="2026-03-29 20:29:33")
    assert "=== Crypto Pair Bot" in header
    assert "Markets found: 12" in header
    assert "Started: 2026-03-29 20:29:33" in header
    assert "\u2500" * 10 in header  # separator line present


def test_dashboard_market_line_no_signal() -> None:
    opp = _make_opportunity()
    line = _dashboard_market_line(
        ts="20:30:05",
        opportunity=opp,
        ref_price=66641.0,
        price_change_pct=-0.0005,
        signal_direction="NONE",
        action="no_action",
    )
    assert "Signal: NONE" in line
    assert ">>>" not in line


def test_dashboard_market_line_signal() -> None:
    opp = _make_opportunity()
    line = _dashboard_market_line(
        ts="20:30:05",
        opportunity=opp,
        ref_price=66641.0,
        price_change_pct=0.005,
        signal_direction="UP",
        action="accumulate",
    )
    assert ">>> SIGNAL: UP" in line
    assert "BUY YES" in line


def test_dashboard_stats_line() -> None:
    line = _dashboard_stats_line(
        cycle=120,
        observations=2848,
        signals=0,
        intents=0,
        elapsed_seconds=150,
        duration_seconds=900,
    )
    assert "Cycles: 120" in line
    assert "Observations: 2848" in line
    assert "Remaining: 12m 30s" in line


def test_verbose_flag_parsed() -> None:
    parser = build_parser()
    args = parser.parse_args(["--verbose"])
    assert args.verbose is True


def test_verbose_flag_default_false() -> None:
    parser = build_parser()
    args = parser.parse_args([])
    assert args.verbose is False
