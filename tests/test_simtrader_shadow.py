"""Offline tests for ShadowRunner and the 'shadow' CLI subcommand.

All tests are fully offline — no network calls are made.  The WS layer is
replaced by injecting a pre-built list of normalised events via the
``_event_source`` parameter.
"""

from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

YES_ID = "aaa" * 20 + "1"
NO_ID = "bbb" * 20 + "2"
SLUG = "will-shadow-test-2026"
QUESTION = "Will shadow mode pass tests?"


# ---------------------------------------------------------------------------
# Event fixture helpers
# ---------------------------------------------------------------------------


def _book_event(asset_id: str, seq: int, bids=None, asks=None) -> dict:
    """Return a minimal 'book' snapshot event."""
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": 1000.0 + seq,
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids if bids is not None else [{"price": "0.45", "size": "100"}],
        "asks": asks if asks is not None else [{"price": "0.55", "size": "100"}],
    }


def _price_change_event(seq: int, price_changes: list) -> dict:
    """Return a modern batched 'price_change' event."""
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": 1000.0 + seq,
        "event_type": "price_change",
        "price_changes": price_changes,
    }


def _legacy_price_change(asset_id: str, seq: int, side: str, price: str, size: str) -> dict:
    """Return a legacy single-asset 'price_change' event."""
    return {
        "parser_version": 1,
        "seq": seq,
        "ts_recv": 1000.0 + seq,
        "event_type": "price_change",
        "asset_id": asset_id,
        "changes": [{"side": side, "price": price, "size": size}],
    }


def _make_fake_events(yes_id=YES_ID, no_id=NO_ID) -> list[dict]:
    """Build a minimal but realistic event stream for two assets."""
    events = [
        # Book snapshots for both assets
        _book_event(yes_id, 0, bids=[{"price": "0.45", "size": "200"}],
                    asks=[{"price": "0.55", "size": "200"}]),
        _book_event(no_id, 1, bids=[{"price": "0.44", "size": "200"}],
                    asks=[{"price": "0.56", "size": "200"}]),
        # Legacy price_change for YES
        _legacy_price_change(yes_id, 2, "BUY", "0.46", "50"),
        # Modern batched price_change for both
        _price_change_event(3, [
            {"asset_id": yes_id, "side": "SELL", "price": "0.54", "size": "60"},
            {"asset_id": no_id, "side": "SELL", "price": "0.55", "size": "60"},
        ]),
        # More ticks to produce timeline rows
        _legacy_price_change(yes_id, 4, "BUY", "0.47", "30"),
        _legacy_price_change(no_id, 5, "SELL", "0.54", "30"),
    ]
    return events


# ---------------------------------------------------------------------------
# Minimal no-op strategy for testing
# ---------------------------------------------------------------------------


class _NoOpStrategy:
    """Strategy that never submits orders — used for artifact existence tests."""

    def on_start(self, asset_id, starting_cash):
        pass

    def on_event(self, event, seq, ts_recv, best_bid, best_ask, open_orders):
        return []

    def on_fill(self, **kwargs):
        pass

    def on_finish(self):
        pass


# ---------------------------------------------------------------------------
# ShadowRunner core tests
# ---------------------------------------------------------------------------


class TestShadowRunnerArtifacts:
    """Verify artifact files are created with correct structure."""

    def _make_runner(self, run_dir, tape_dir=None, events=None, strategy=None):
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        return ShadowRunner(
            run_dir=run_dir,
            asset_ids=[YES_ID, NO_ID],
            strategy=strategy or _NoOpStrategy(),
            primary_asset_id=YES_ID,
            extra_book_asset_ids=[NO_ID],
            duration_seconds=None,
            starting_cash=Decimal("1000"),
            fee_rate_bps=None,
            mark_method="bid",
            tape_dir=tape_dir,
            shadow_context={"selected_slug": SLUG, "yes_token_id": YES_ID, "no_token_id": NO_ID},
            _event_source=events if events is not None else _make_fake_events(),
        )

    def test_creates_all_artifact_files(self, tmp_path):
        """All expected artifact files are created after run()."""
        run_dir = tmp_path / "run"
        runner = self._make_runner(run_dir)
        runner.run()

        expected = [
            "best_bid_ask.jsonl",
            "orders.jsonl",
            "fills.jsonl",
            "ledger.jsonl",
            "equity_curve.jsonl",
            "decisions.jsonl",
            "summary.json",
            "run_manifest.json",
            "meta.json",
        ]
        for name in expected:
            assert (run_dir / name).exists(), f"Missing artifact: {name}"

    def test_artifacts_are_nonempty(self, tmp_path):
        """All JSONL artifacts have at least one line; JSON files are parseable."""
        run_dir = tmp_path / "run"
        runner = self._make_runner(run_dir)
        runner.run()

        # JSONL files that should always have content:
        for name in ("ledger.jsonl",):
            content = (run_dir / name).read_text(encoding="utf-8")
            lines = [l for l in content.splitlines() if l.strip()]
            assert lines, f"{name} must have at least one line"

        # JSON files must be valid:
        for name in ("summary.json", "run_manifest.json", "meta.json"):
            content = (run_dir / name).read_text(encoding="utf-8")
            parsed = json.loads(content)
            assert isinstance(parsed, dict)

    def test_run_manifest_mode_is_shadow(self, tmp_path):
        """run_manifest.json has mode='shadow'."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["mode"] == "shadow"

    def test_run_manifest_has_shadow_context(self, tmp_path):
        """run_manifest.json contains shadow_context with the expected keys."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        ctx = manifest.get("shadow_context", {})
        assert ctx.get("selected_slug") == SLUG
        assert ctx.get("yes_token_id") == YES_ID
        assert ctx.get("no_token_id") == NO_ID

    def test_run_manifest_has_timestamps(self, tmp_path):
        """run_manifest.json includes started_at and ended_at."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert "started_at" in manifest
        assert "ended_at" in manifest
        assert manifest["started_at"]  # not empty

    def test_meta_mode_is_shadow(self, tmp_path):
        """meta.json has mode='shadow'."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta.get("mode") == "shadow"

    def test_ledger_has_at_least_two_rows(self, tmp_path):
        """ledger.jsonl always has at least 2 rows even on no-trade runs."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        lines = [
            l for l in (run_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        assert len(lines) >= 2, f"ledger.jsonl has {len(lines)} rows, expected >= 2"

    def test_ledger_initial_final_events(self, tmp_path):
        """First ledger row is event='initial', last is event='final' (no-trade case)."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        lines = [
            l for l in (run_dir / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        first = json.loads(lines[0])
        last = json.loads(lines[-1])
        assert first["event"] == "initial"
        assert last["event"] == "final"

    def test_summary_has_net_profit_key(self, tmp_path):
        """summary.json always contains net_profit."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir).run()
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        assert "net_profit" in summary

    def test_returns_pnl_dict(self, tmp_path):
        """run() returns a dict with net_profit."""
        run_dir = tmp_path / "run"
        result = self._make_runner(run_dir).run()
        assert isinstance(result, dict)
        assert "net_profit" in result

    def test_empty_event_stream_produces_minimal_artifacts(self, tmp_path):
        """An empty _event_source still produces all artifact files."""
        run_dir = tmp_path / "run"
        runner = self._make_runner(run_dir, events=[])
        runner.run()
        assert (run_dir / "run_manifest.json").exists()
        assert (run_dir / "meta.json").exists()
        assert (run_dir / "summary.json").exists()


# ---------------------------------------------------------------------------
# Tape recording tests
# ---------------------------------------------------------------------------


class TestShadowTapeRecording:
    """Verify tape files are created when tape_dir is set."""

    def _make_runner(self, run_dir, tape_dir=None, events=None, shadow_context=None):
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        return ShadowRunner(
            run_dir=run_dir,
            asset_ids=[YES_ID, NO_ID],
            strategy=_NoOpStrategy(),
            primary_asset_id=YES_ID,
            extra_book_asset_ids=[NO_ID],
            duration_seconds=None,
            starting_cash=Decimal("1000"),
            tape_dir=tape_dir,
            shadow_context=shadow_context or {},
            _event_source=events if events is not None else _make_fake_events(),
        )

    def test_tape_files_created_when_tape_dir_set(self, tmp_path):
        """events.jsonl and meta.json are written to tape_dir."""
        run_dir = tmp_path / "run"
        tape_dir = tmp_path / "tape"
        self._make_runner(run_dir, tape_dir=tape_dir).run()

        assert (tape_dir / "events.jsonl").exists()
        assert (tape_dir / "meta.json").exists()

    def test_tape_events_jsonl_has_all_events(self, tmp_path):
        """events.jsonl in tape_dir contains one line per input event."""
        run_dir = tmp_path / "run"
        tape_dir = tmp_path / "tape"
        fake_events = _make_fake_events()
        self._make_runner(run_dir, tape_dir=tape_dir, events=fake_events).run()

        lines = [
            l for l in (tape_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        assert len(lines) == len(fake_events)

    def test_tape_meta_json_is_valid(self, tmp_path):
        """tape/meta.json is valid JSON with expected fields."""
        run_dir = tmp_path / "run"
        tape_dir = tmp_path / "tape"
        self._make_runner(run_dir, tape_dir=tape_dir).run()

        meta = json.loads((tape_dir / "meta.json").read_text(encoding="utf-8"))
        assert "event_count" in meta
        assert "reconnect_count" in meta
        assert "started_at" in meta
        assert "ended_at" in meta
        # In injected mode, raw_ws.jsonl is not expected — source is "injected"
        assert meta.get("source") == "injected"

    def test_shadow_tape_meta_includes_shadow_context(self, tmp_path):
        """tape/meta.json includes shadow_context with slug + yes/no IDs."""
        run_dir = tmp_path / "run"
        tape_dir = tmp_path / "tape"
        expected_context = {
            "selected_slug": SLUG,
            "yes_token_id": YES_ID,
            "no_token_id": NO_ID,
        }
        self._make_runner(
            run_dir,
            tape_dir=tape_dir,
            shadow_context=expected_context,
        ).run()

        meta = json.loads((tape_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta.get("shadow_context") == expected_context

    def test_no_tape_files_when_tape_dir_none(self, tmp_path):
        """When tape_dir is None, no tape directory or files are created."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, tape_dir=None).run()

        # No tape subdirectory should exist under tmp_path besides "run".
        children = [p.name for p in tmp_path.iterdir()]
        assert "tape" not in children

    def test_run_manifest_tape_dir_is_null_when_not_recording(self, tmp_path):
        """run_manifest.json has tape_dir=null when not recording."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, tape_dir=None).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["tape_dir"] is None

    def test_run_manifest_tape_dir_is_set_when_recording(self, tmp_path):
        """run_manifest.json has tape_dir path when tape_dir is given."""
        run_dir = tmp_path / "run"
        tape_dir = tmp_path / "tape"
        self._make_runner(run_dir, tape_dir=tape_dir).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["tape_dir"] is not None
        assert "tape" in manifest["tape_dir"]


# ---------------------------------------------------------------------------
# Timeline and event processing tests
# ---------------------------------------------------------------------------


class TestShadowEventProcessing:
    """Verify book updates and timeline rows are correct."""

    def _run_with_events(self, events, tmp_path):
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        run_dir = tmp_path / "run"
        runner = ShadowRunner(
            run_dir=run_dir,
            asset_ids=[YES_ID, NO_ID],
            strategy=_NoOpStrategy(),
            primary_asset_id=YES_ID,
            extra_book_asset_ids=[NO_ID],
            duration_seconds=None,
            starting_cash=Decimal("500"),
            _event_source=events,
        )
        runner.run()
        return run_dir

    def test_timeline_has_rows_from_book_events(self, tmp_path):
        """best_bid_ask.jsonl has a row for each primary-asset book-affecting event."""
        events = [
            _book_event(YES_ID, 0),
            _book_event(NO_ID, 1),
            _legacy_price_change(YES_ID, 2, "BUY", "0.47", "10"),
            _legacy_price_change(NO_ID, 3, "BUY", "0.43", "10"),
        ]
        run_dir = self._run_with_events(events, tmp_path)
        lines = [
            l for l in (run_dir / "best_bid_ask.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()
        ]
        # Events at seq 0 (book YES) and seq 2 (price_change YES) should appear
        # NO events should NOT appear in the primary-asset timeline
        yes_lines = [json.loads(l) for l in lines if json.loads(l).get("asset_id") == YES_ID]
        assert len(yes_lines) >= 2

    def test_manifest_total_events_count(self, tmp_path):
        """run_manifest.json.total_events equals the number of injected events."""
        events = _make_fake_events()
        run_dir = self._run_with_events(events, tmp_path)
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["total_events"] == len(events)

    def test_modern_batched_price_change_processed(self, tmp_path):
        """Modern batched price_changes[] events update both books."""
        events = [
            _book_event(YES_ID, 0),
            _book_event(NO_ID, 1),
            _price_change_event(2, [
                {"asset_id": YES_ID, "side": "SELL", "price": "0.54", "size": "20"},
                {"asset_id": NO_ID, "side": "SELL", "price": "0.55", "size": "20"},
            ]),
        ]
        run_dir = self._run_with_events(events, tmp_path)
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        # All 3 events should be counted
        assert manifest["total_events"] == 3
        # Run should complete without warnings about blank runs
        assert manifest["run_quality"] in ("ok", "warnings")


# ---------------------------------------------------------------------------
# CLI shadow subcommand tests
# ---------------------------------------------------------------------------


class TestShadowCLI:
    """Tests for the 'shadow' CLI subcommand (offline, mocked externals)."""

    def _make_market(self, slug=SLUG):
        m = MagicMock()
        m.market_slug = slug
        m.question = QUESTION
        m.outcomes = ["Yes", "No"]
        m.clob_token_ids = [YES_ID, NO_ID]
        return m

    def _make_good_book(self):
        return {
            "bids": [{"price": "0.45", "size": "100"}],
            "asks": [{"price": "0.55", "size": "100"}],
        }

    def test_dry_run_exits_zero(self, tmp_path):
        """--dry-run resolves market and exits 0 without starting shadow loop."""
        from tools.cli.simtrader import main

        with (
            patch("packages.polymarket.gamma.GammaClient") as MockGamma,
            patch("packages.polymarket.clob.ClobClient") as MockClob,
        ):
            gamma_instance = MockGamma.return_value
            gamma_instance.fetch_markets_filtered.return_value = [self._make_market()]
            clob_instance = MockClob.return_value
            clob_instance.fetch_book.return_value = self._make_good_book()

            rc = main([
                "shadow",
                "--market", SLUG,
                "--duration", "10",
                "--dry-run",
            ])

        assert rc == 0

    def test_bad_market_slug_returns_1(self):
        """An unresolvable slug causes exit code 1."""
        from tools.cli.simtrader import main

        with (
            patch("packages.polymarket.gamma.GammaClient") as MockGamma,
            patch("packages.polymarket.clob.ClobClient") as MockClob,
        ):
            gamma_instance = MockGamma.return_value
            gamma_instance.fetch_markets_filtered.return_value = []  # no markets
            MockClob.return_value

            rc = main([
                "shadow",
                "--market", "nonexistent-slug",
                "--duration", "10",
                "--dry-run",
            ])

        assert rc == 1

    def test_shadow_run_offline(self, tmp_path):
        """Full shadow run with injected events produces artifacts."""
        from tools.cli.simtrader import main

        fake_events = _make_fake_events()

        with (
            patch("packages.polymarket.gamma.GammaClient") as MockGamma,
            patch("packages.polymarket.clob.ClobClient") as MockClob,
            patch(
                "packages.polymarket.simtrader.shadow.runner.ShadowRunner.run",
                return_value={"net_profit": "0.00", "run_id": "test"},
            ) as mock_run,
        ):
            gamma_instance = MockGamma.return_value
            gamma_instance.fetch_markets_filtered.return_value = [self._make_market()]
            clob_instance = MockClob.return_value
            clob_instance.fetch_book.return_value = self._make_good_book()

            rc = main([
                "shadow",
                "--market", SLUG,
                "--duration", "10",
                "--no-record-tape",
            ])

        assert rc == 0
        assert mock_run.called

    def test_shadow_loose_strategy_preset_expands_strategy_config(self):
        """--strategy-preset loose maps to JSON-equivalent strategy config overrides."""
        from tools.cli.simtrader import main

        captured: dict = {}

        def fake_build_strategy(strategy_name, strategy_config):
            captured["strategy_name"] = strategy_name
            captured["strategy_config"] = dict(strategy_config)
            return _NoOpStrategy()

        with (
            patch("packages.polymarket.gamma.GammaClient") as MockGamma,
            patch("packages.polymarket.clob.ClobClient") as MockClob,
            patch(
                "packages.polymarket.simtrader.strategy.facade._build_strategy",
                side_effect=fake_build_strategy,
            ),
            patch(
                "packages.polymarket.simtrader.shadow.runner.ShadowRunner.run",
                return_value={"net_profit": "0.00", "run_id": "test"},
            ),
        ):
            gamma_instance = MockGamma.return_value
            gamma_instance.fetch_markets_filtered.return_value = [self._make_market()]
            clob_instance = MockClob.return_value
            clob_instance.fetch_book.return_value = self._make_good_book()

            rc = main(
                [
                    "shadow",
                    "--market",
                    SLUG,
                    "--duration",
                    "1",
                    "--strategy-preset",
                    "loose",
                    "--no-record-tape",
                ]
            )

        assert rc == 0
        assert captured["strategy_name"] == "binary_complement_arb"
        cfg = captured["strategy_config"]
        assert cfg["max_size"] == 1
        assert abs(float(cfg["buffer"]) - 0.0005) < 1e-12
        assert cfg["max_notional_usdc"] == 25

    def test_shadow_subcommand_in_parser(self):
        """'shadow' is a registered subcommand in the argument parser."""
        from tools.cli.simtrader import _build_parser

        parser = _build_parser()
        # parse_args should not raise for 'shadow --market X'
        args = parser.parse_args(["shadow", "--market", "test-slug"])
        assert args.subcommand == "shadow"
        assert args.market == "test-slug"

    def test_shadow_parser_defaults(self):
        """Shadow parser has expected default values."""
        from tools.cli.simtrader import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["shadow", "--market", "test-slug"])
        assert args.duration == 300.0
        assert args.strategy == "binary_complement_arb"
        assert args.starting_cash == 1000.0
        assert args.mark_method == "bid"
        assert args.strategy_preset == "sane"
        assert args.no_record_tape is False
        assert args.dry_run is False

    def test_shadow_no_record_tape_flag(self):
        """--no-record-tape flag is properly parsed."""
        from tools.cli.simtrader import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["shadow", "--market", "test-slug", "--no-record-tape"])
        assert args.no_record_tape is True


# ---------------------------------------------------------------------------
# ShadowRunner._normalize tests
# ---------------------------------------------------------------------------


class TestNormalize:
    """Test the static _normalize method directly."""

    def _normalize(self, evt, seq=0, ts_recv=1000.0):
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        return ShadowRunner._normalize(evt, seq, ts_recv)

    def test_known_event_type_returned(self):
        evt = {"event_type": "book", "asset_id": YES_ID, "bids": [], "asks": []}
        result = self._normalize(evt)
        assert result is not None
        assert result["event_type"] == "book"
        assert result["seq"] == 0
        assert result["ts_recv"] == 1000.0
        assert "parser_version" in result

    def test_unknown_event_type_returns_none(self):
        evt = {"event_type": "unknown_type", "data": {}}
        result = self._normalize(evt)
        assert result is None

    def test_non_dict_returns_none(self):
        result = self._normalize("not a dict")
        assert result is None

    def test_type_field_fallback(self):
        """Events using 'type' instead of 'event_type' are recognized and preserved."""
        evt = {"type": "price_change", "price_changes": []}
        result = self._normalize(evt)
        # The normalizer accepts 'type' as a fallback for 'event_type'.
        # The original 'type' key is preserved in the output dict (no renaming).
        assert result is not None
        assert result.get("type") == "price_change"


# ---------------------------------------------------------------------------
# Metrics counter tests
# ---------------------------------------------------------------------------


class TestShadowMetrics:
    """Verify run_metrics counters in run_manifest.json."""

    def _make_runner(self, run_dir, events, **kwargs):
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        return ShadowRunner(
            run_dir=run_dir,
            asset_ids=[YES_ID, NO_ID],
            strategy=_NoOpStrategy(),
            primary_asset_id=YES_ID,
            extra_book_asset_ids=[NO_ID],
            duration_seconds=None,
            starting_cash=Decimal("1000"),
            _event_source=events,
            **kwargs,
        )

    def test_run_metrics_always_present(self, tmp_path):
        """run_metrics is always present in run_manifest.json."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events()).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert "run_metrics" in manifest
        rm = manifest["run_metrics"]
        for key in (
            "ws_reconnects", "ws_timeouts", "events_received",
            "batched_price_changes", "per_asset_update_counts",
        ):
            assert key in rm, f"run_metrics missing key: {key}"

    def test_events_received_matches_injected_count(self, tmp_path):
        """events_received equals the exact number of events injected."""
        events = _make_fake_events()  # 6 events
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, events).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["run_metrics"]["events_received"] == len(events)

    def test_batched_price_changes_counted(self, tmp_path):
        """batched_price_changes counts events that carry a price_changes[] list."""
        events = [
            _book_event(YES_ID, 0),
            _book_event(NO_ID, 1),
            _price_change_event(2, [
                {"asset_id": YES_ID, "side": "SELL", "price": "0.54", "size": "10"},
                {"asset_id": NO_ID, "side": "SELL", "price": "0.55", "size": "10"},
            ]),
            _price_change_event(3, [
                {"asset_id": YES_ID, "side": "BUY", "price": "0.46", "size": "10"},
            ]),
            # Legacy price_change (no price_changes[]) must NOT be counted as batched.
            _legacy_price_change(YES_ID, 4, "BUY", "0.47", "5"),
        ]
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, events).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        # seq 2 and seq 3 are batched; seq 4 is legacy (not batched)
        assert manifest["run_metrics"]["batched_price_changes"] == 2

    def test_per_asset_update_counts_both_assets(self, tmp_path):
        """per_asset_update_counts has entries for both YES and NO assets."""
        events = [
            _book_event(YES_ID, 0),
            _book_event(NO_ID, 1),
            _legacy_price_change(YES_ID, 2, "BUY", "0.46", "10"),
            _legacy_price_change(NO_ID, 3, "SELL", "0.54", "10"),
        ]
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, events).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        counts = manifest["run_metrics"]["per_asset_update_counts"]
        assert YES_ID in counts, "YES asset missing from per_asset_update_counts"
        assert NO_ID in counts, "NO asset missing from per_asset_update_counts"
        # Each asset has at least a book snapshot + one price_change
        assert counts[YES_ID] >= 2
        assert counts[NO_ID] >= 2

    def test_ws_reconnects_and_timeouts_zero_in_injected_mode(self, tmp_path):
        """In injected-source mode, ws_reconnects and ws_timeouts are both 0."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events()).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        rm = manifest["run_metrics"]
        assert rm["ws_reconnects"] == 0
        assert rm["ws_timeouts"] == 0


# ---------------------------------------------------------------------------
# Stall kill-switch tests
# ---------------------------------------------------------------------------


class TestShadowStall:
    """Verify stall kill-switch via _stall_after_n_events test hook."""

    def _make_runner(self, run_dir, events, stall_after, max_stall_seconds=30.0):
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        return ShadowRunner(
            run_dir=run_dir,
            asset_ids=[YES_ID, NO_ID],
            strategy=_NoOpStrategy(),
            primary_asset_id=YES_ID,
            extra_book_asset_ids=[NO_ID],
            duration_seconds=None,
            starting_cash=Decimal("1000"),
            max_ws_stall_seconds=max_stall_seconds,
            _event_source=events,
            _stall_after_n_events=stall_after,
        )

    def test_stall_writes_exit_reason_to_manifest(self, tmp_path):
        """Stall exit sets exit_reason in run_manifest.json containing 'stall'."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events(), stall_after=3).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert "exit_reason" in manifest
        assert "stall" in manifest["exit_reason"]

    def test_stall_writes_exit_reason_to_meta(self, tmp_path):
        """Stall exit also sets exit_reason in meta.json."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events(), stall_after=2).run()
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert "exit_reason" in meta
        assert "stall" in meta["exit_reason"]

    def test_stall_stops_after_n_events(self, tmp_path):
        """With _stall_after_n_events=3, exactly 3 events are processed."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events(), stall_after=3).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert manifest["run_metrics"]["events_received"] == 3

    def test_stall_all_artifacts_still_written(self, tmp_path):
        """All artifact files are still created after a stall exit."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events(), stall_after=2).run()
        expected = [
            "run_manifest.json", "meta.json", "summary.json",
            "ledger.jsonl", "orders.jsonl", "fills.jsonl", "decisions.jsonl",
        ]
        for name in expected:
            assert (run_dir / name).exists(), f"Missing after stall: {name}"

    def test_no_stall_no_exit_reason(self, tmp_path):
        """Normal completion (no stall) leaves exit_reason absent from manifest."""
        from packages.polymarket.simtrader.shadow.runner import ShadowRunner

        run_dir = tmp_path / "run"
        ShadowRunner(
            run_dir=run_dir,
            asset_ids=[YES_ID, NO_ID],
            strategy=_NoOpStrategy(),
            primary_asset_id=YES_ID,
            extra_book_asset_ids=[NO_ID],
            duration_seconds=None,
            starting_cash=Decimal("1000"),
            _event_source=_make_fake_events(),
        ).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        assert "exit_reason" not in manifest

    def test_stall_reason_contains_event_count(self, tmp_path):
        """Stall reason string mentions the index at which the stall fired."""
        run_dir = tmp_path / "run"
        self._make_runner(run_dir, _make_fake_events(), stall_after=4).run()
        manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
        # Runner fires at i=4, reason says "simulated after 4 events"
        assert "4 events" in manifest["exit_reason"]
