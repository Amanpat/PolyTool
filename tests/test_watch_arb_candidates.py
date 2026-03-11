"""Tests for tools.cli.watch_arb_candidates.

Covers:
  - evaluate_trigger: fires on near-edge + sufficient depth
  - evaluate_trigger: does NOT fire on deep but clearly non-edge markets
  - evaluate_trigger: does NOT fire on near-edge but insufficient-depth markets
  - evaluate_trigger: does NOT fire when BBO is missing
  - ArbWatcher: recorder invocation uses correct market resolution (slug, token IDs)
  - ArbWatcher: recorder is NOT invoked in dry-run mode
  - ArbWatcher: recorder is NOT invoked when max_concurrent already reached
  - ArbWatcher: already-recording market skips poll
  - main(): accepts --markets and --dry-run
  - watchlist-file ingest: validates rows, skips expired entries, dedupes slugs
  - main(): --markets and --watchlist-file coexist cleanly
  - main(): rejects invalid --near-edge
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.cli.watch_arb_candidates import (
    ArbWatcher,
    ResolvedWatch,
    _collect_watch_targets,
    _load_watchlist_file,
    evaluate_trigger,
    main,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NEAR_EDGE = 1.00      # default trigger threshold
_STRATEGY_ENTRY = 0.99  # the actual strategy threshold (DO NOT change)
_MIN_DEPTH = 50.0


def _asks(price: float, size: float) -> list:
    """Build a minimal ask-levels list with a single level."""
    return [{"price": str(price), "size": str(size)}]


def _resolved(slug: str = "test-market") -> ResolvedWatch:
    return ResolvedWatch(
        slug=slug,
        yes_token_id="yes-token-" + slug,
        no_token_id="no-token-" + slug,
    )


def _write_watchlist(tmp_path: Path, entries: list[dict]) -> Path:
    path = tmp_path / "watchlist.json"
    payload = {
        "schema_version": "report_to_watchlist_v1",
        "watchlist": entries,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# evaluate_trigger: correct firing behaviour
# ---------------------------------------------------------------------------


class TestEvaluateTrigger:
    """Pure trigger evaluation — no network, no threads."""

    def test_fires_on_near_edge_and_sufficient_depth(self):
        """Trigger fires when sum_ask < near_edge_threshold AND both sizes >= min_depth."""
        snap = evaluate_trigger(
            _asks(0.49, 100),  # YES ask
            _asks(0.50, 100),  # NO ask  → sum = 0.99 < 1.00
            "market-a",
            near_edge_threshold=_NEAR_EDGE,
            min_depth=_MIN_DEPTH,
        )
        assert snap.trigger is True
        assert snap.near_edge is True
        assert snap.depth_ok is True
        assert snap.sum_ask == pytest.approx(0.99)

    def test_fires_at_sum_just_below_threshold(self):
        """sum_ask = 0.999 fires at near_edge=1.00 but would not reach strategy entry."""
        snap = evaluate_trigger(
            _asks(0.499, 60),
            _asks(0.500, 60),  # sum = 0.999
            "market-b",
            near_edge_threshold=1.00,
            min_depth=50.0,
        )
        assert snap.trigger is True
        assert snap.sum_ask == pytest.approx(0.999)

    def test_does_not_fire_on_non_edge_market(self):
        """Trigger does NOT fire when sum_ask is clearly above threshold (typical market)."""
        snap = evaluate_trigger(
            _asks(0.50, 1000),  # deep
            _asks(0.51, 1000),  # deep, but sum = 1.01 > 1.00
            "market-no-edge",
            near_edge_threshold=_NEAR_EDGE,
            min_depth=_MIN_DEPTH,
        )
        assert snap.trigger is False
        assert snap.near_edge is False
        assert snap.depth_ok is True     # depth is fine
        assert snap.sum_ask == pytest.approx(1.01)

    def test_does_not_fire_on_near_edge_but_insufficient_depth(self):
        """Trigger does NOT fire when near-edge but ask size is below min_depth."""
        snap = evaluate_trigger(
            _asks(0.49, 10),   # near-edge price but only 10 shares (< 50)
            _asks(0.50, 100),  # good depth on NO side
            "market-low-depth",
            near_edge_threshold=_NEAR_EDGE,
            min_depth=_MIN_DEPTH,
        )
        assert snap.trigger is False
        assert snap.near_edge is True    # sum = 0.99 < 1.00
        assert snap.depth_ok is False    # YES side: 10 < 50

    def test_does_not_fire_when_no_bbo(self):
        """Trigger does NOT fire when orderbook is empty."""
        snap = evaluate_trigger(
            [],   # empty YES book
            _asks(0.50, 100),
            "market-empty",
            near_edge_threshold=_NEAR_EDGE,
            min_depth=_MIN_DEPTH,
        )
        assert snap.trigger is False
        assert snap.sum_ask is None

    def test_does_not_fire_when_both_books_empty(self):
        snap = evaluate_trigger([], [], "market-both-empty")
        assert snap.trigger is False
        assert snap.sum_ask is None

    def test_at_exact_threshold_does_not_fire(self):
        """sum_ask == near_edge_threshold is NOT near-edge (strict less-than)."""
        snap = evaluate_trigger(
            _asks(0.50, 100),
            _asks(0.50, 100),  # sum = 1.00 exactly
            "market-at-threshold",
            near_edge_threshold=1.00,
            min_depth=50.0,
        )
        assert snap.trigger is False
        assert snap.near_edge is False   # 1.00 < 1.00 is False
        assert snap.sum_ask == pytest.approx(1.00)

    def test_strategy_threshold_is_not_changed(self):
        """The strategy entry threshold (0.99) is independent of the watch trigger.

        A market with sum_ask=0.995 should trigger watching (near_edge=1.00)
        but would NOT satisfy the strategy entry at threshold=0.99.
        This ensures we never accidentally change strategy logic.
        """
        snap = evaluate_trigger(
            _asks(0.497, 60),
            _asks(0.498, 60),  # sum = 0.995
            "market-in-watch-zone",
            near_edge_threshold=1.00,   # watch trigger
            min_depth=50.0,
        )
        assert snap.trigger is True     # yes: 0.995 < 1.00
        # Verify the snapshot preserves the raw values for operator inspection
        assert snap.sum_ask is not None
        # 0.995 is ABOVE the strategy entry threshold (0.99) — the strategy would NOT enter,
        # but the watch trigger fires anyway. This is the intended near-miss capture behaviour.
        assert snap.sum_ask > _STRATEGY_ENTRY  # 0.995 > 0.99 → near-miss zone
        assert snap.sum_ask < 1.00             # 0.995 < 1.00 → watch trigger fires

    def test_near_edge_threshold_configurable(self):
        """A tighter trigger (0.995) does not fire at sum=0.999."""
        snap = evaluate_trigger(
            _asks(0.499, 60),
            _asks(0.500, 60),  # sum = 0.999
            "market-tight",
            near_edge_threshold=0.995,  # tighter than default 1.00
            min_depth=50.0,
        )
        assert snap.trigger is False   # 0.999 >= 0.995 → no trigger
        assert snap.near_edge is False


# ---------------------------------------------------------------------------
# ArbWatcher: trigger → recording wiring
# ---------------------------------------------------------------------------


def _make_watcher(
    resolved_markets: list[ResolvedWatch],
    *,
    near_edge_threshold: float = _NEAR_EDGE,
    min_depth: float = _MIN_DEPTH,
    fetch_fn=None,
    record_fn=None,
    max_concurrent: int = 2,
    dry_run: bool = False,
) -> ArbWatcher:
    return ArbWatcher(
        resolved_markets=resolved_markets,
        near_edge_threshold=near_edge_threshold,
        min_depth=min_depth,
        poll_interval=0.0,
        duration_seconds=1.0,
        tapes_base_dir=Path("artifacts/simtrader/tapes"),
        ws_url="wss://test",
        max_concurrent=max_concurrent,
        dry_run=dry_run,
        _fetch_fn=fetch_fn,
        _record_fn=record_fn,
    )


class TestArbWatcherTrigger:
    """Watcher integration tests — no real network or disk writes."""

    def test_recorder_called_with_correct_resolved_market(self):
        """Recorder invocation uses the correct slug and token IDs from resolution."""
        resolved = _resolved("market-x")
        recorded_calls: list = []

        def fake_fetch(r: ResolvedWatch):
            # Return near-edge snapshot with sufficient depth
            return _asks(0.49, 100), _asks(0.50, 100)

        def fake_record(r: ResolvedWatch, tape_dir: Path, *, duration_seconds, ws_url,
                        near_edge_threshold=None, threshold_source=None, regime=None):
            recorded_calls.append({
                "slug": r.slug,
                "yes_token_id": r.yes_token_id,
                "no_token_id": r.no_token_id,
                "tape_dir": tape_dir,
                "duration_seconds": duration_seconds,
            })

        watcher = _make_watcher(
            [resolved],
            fetch_fn=fake_fetch,
            record_fn=fake_record,
        )
        watcher._poll_round()

        # Allow background recording thread to run
        time.sleep(0.1)

        assert len(recorded_calls) == 1
        assert recorded_calls[0]["slug"] == "market-x"
        assert recorded_calls[0]["yes_token_id"] == resolved.yes_token_id
        assert recorded_calls[0]["no_token_id"] == resolved.no_token_id
        assert recorded_calls[0]["duration_seconds"] == pytest.approx(1.0)

    def test_recorder_not_called_when_no_trigger(self):
        """Recorder is NOT invoked when sum_ask is above near_edge_threshold."""
        resolved = _resolved("market-no-trigger")
        recorded_calls: list = []

        def fake_fetch(r):
            return _asks(0.50, 1000), _asks(0.52, 1000)  # sum = 1.02

        def fake_record(r, tape_dir, **kw):
            recorded_calls.append(r.slug)

        watcher = _make_watcher([resolved], fetch_fn=fake_fetch, record_fn=fake_record)
        watcher._poll_round()
        time.sleep(0.05)

        assert recorded_calls == []

    def test_recorder_not_called_on_insufficient_depth(self):
        """Recorder is NOT invoked when near-edge but depth is below min_depth."""
        resolved = _resolved("market-shallow")
        recorded_calls: list = []

        def fake_fetch(r):
            return _asks(0.49, 5), _asks(0.50, 5)  # near-edge but only 5 shares

        def fake_record(r, tape_dir, **kw):
            recorded_calls.append(r.slug)

        watcher = _make_watcher([resolved], fetch_fn=fake_fetch, record_fn=fake_record)
        watcher._poll_round()
        time.sleep(0.05)

        assert recorded_calls == []

    def test_recorder_not_called_in_dry_run(self):
        """Recorder is NOT invoked in dry-run mode even when trigger fires."""
        resolved = _resolved("market-dry")
        recorded_calls: list = []

        def fake_fetch(r):
            return _asks(0.49, 100), _asks(0.50, 100)  # triggers

        def fake_record(r, tape_dir, **kw):
            recorded_calls.append(r.slug)

        watcher = _make_watcher(
            [resolved],
            fetch_fn=fake_fetch,
            record_fn=fake_record,
            dry_run=True,
        )
        watcher._poll_round()
        time.sleep(0.05)

        assert recorded_calls == []

    def test_recorder_not_called_when_max_concurrent_reached(self):
        """Recorder is NOT invoked when max_concurrent recordings are already running."""
        r1 = _resolved("market-alpha")
        r2 = _resolved("market-beta")
        recorded_calls: list = []

        def fake_fetch(r):
            # Both markets are near-edge with sufficient depth
            return _asks(0.49, 100), _asks(0.50, 100)

        def fake_record(r, tape_dir, **kw):
            recorded_calls.append(r.slug)

        watcher = _make_watcher(
            [r1, r2],
            fetch_fn=fake_fetch,
            record_fn=fake_record,
            max_concurrent=1,
        )
        # Manually mark r1 as already recording to fill the slot
        with watcher._lock:
            watcher._recording_slugs.add(r1.slug)

        watcher._poll_round()
        time.sleep(0.05)

        # r1 skipped (already recording), r2 skipped (max_concurrent=1 already reached)
        assert recorded_calls == []

    def test_already_recording_market_skips_poll(self):
        """A market that is currently recording is not polled again."""
        resolved = _resolved("market-in-flight")
        fetch_calls: list = []
        recorded_calls: list = []

        def fake_fetch(r):
            fetch_calls.append(r.slug)
            return _asks(0.49, 100), _asks(0.50, 100)

        def fake_record(r, tape_dir, **kw):
            recorded_calls.append(r.slug)

        watcher = _make_watcher(
            [resolved],
            fetch_fn=fake_fetch,
            record_fn=fake_record,
        )
        # Mark the market as already recording
        with watcher._lock:
            watcher._recording_slugs.add(resolved.slug)

        watcher._poll_round()
        time.sleep(0.05)

        assert fetch_calls == []       # no poll because already recording
        assert recorded_calls == []    # no additional recording started

    def test_recorder_releases_lock_after_completion(self):
        """Recording thread removes the slug from _recording_slugs after finishing."""
        resolved = _resolved("market-lock-release")
        done_event = threading.Event()

        def fake_fetch(r):
            return _asks(0.49, 100), _asks(0.50, 100)

        def fake_record(r, tape_dir, **kw):
            done_event.set()

        watcher = _make_watcher(
            [resolved],
            fetch_fn=fake_fetch,
            record_fn=fake_record,
        )
        watcher._poll_round()
        done_event.wait(timeout=2.0)
        time.sleep(0.05)  # give the finally block a moment

        with watcher._lock:
            assert resolved.slug not in watcher._recording_slugs


# ---------------------------------------------------------------------------
# Watchlist-file ingest
# ---------------------------------------------------------------------------


class TestWatchlistFileInput:
    def test_valid_watchlist_file_ingest(self, tmp_path):
        now = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
        watchlist_path = _write_watchlist(
            tmp_path,
            [
                {
                    "market_slug": "report-market-a",
                    "reason": "surfaced in report",
                    "priority": 1,
                    "provenance": {"source_type": "report", "source_id": "abc123"},
                    "timestamp_utc": "2026-03-07T11:45:00Z",
                }
            ],
        )

        targets = _load_watchlist_file(watchlist_path, now=now)

        assert [target.slug for target in targets] == ["report-market-a"]
        assert targets[0].metadata["reason"] == "surfaced in report"
        assert targets[0].metadata["priority"] == 1
        assert targets[0].metadata["provenance"]["source_id"] == "abc123"

    def test_missing_market_slug_rejected(self, tmp_path):
        watchlist_path = _write_watchlist(
            tmp_path,
            [
                {
                    "reason": "missing slug",
                    "priority": 2,
                }
            ],
        )

        with pytest.raises(ValueError, match="market_slug"):
            _load_watchlist_file(watchlist_path)

    def test_duplicate_slugs_deduped(self, tmp_path):
        watchlist_path = _write_watchlist(
            tmp_path,
            [
                {"market_slug": "dup-market", "reason": "first"},
                {"market_slug": "dup-market", "reason": "second"},
                {"market_slug": "unique-market"},
            ],
        )

        targets = _collect_watch_targets(
            markets=None,
            watchlist_file=str(watchlist_path),
            now=datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc),
        )

        assert [target.slug for target in targets] == ["dup-market", "unique-market"]
        assert targets[0].metadata["reason"] == "first"

    def test_expired_entries_skipped(self, tmp_path):
        now = datetime(2026, 3, 7, 12, 0, tzinfo=timezone.utc)
        watchlist_path = _write_watchlist(
            tmp_path,
            [
                {
                    "market_slug": "expired-market",
                    "expiry_utc": (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                },
                {
                    "market_slug": "fresh-market",
                    "expiry_utc": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                },
            ],
        )

        targets = _load_watchlist_file(watchlist_path, now=now)

        assert [target.slug for target in targets] == ["fresh-market"]

    def test_markets_and_watchlist_file_coexist(self, tmp_path):
        watchlist_path = _write_watchlist(
            tmp_path,
            [
                {"market_slug": "shared-market", "reason": "from report"},
                {"market_slug": "watchlist-only-market", "priority": 1},
            ],
        )
        captured: dict[str, list[str]] = {}

        def fake_run(self):
            captured["slugs"] = [resolved.slug for resolved in self.resolved_markets]

        with (
            patch("tools.cli.watch_arb_candidates._resolve_market", side_effect=_resolved),
            patch.object(ArbWatcher, "run", fake_run),
        ):
            rc = main(
                [
                    "--markets",
                    "direct-market,shared-market",
                    "--watchlist-file",
                    str(watchlist_path),
                    "--dry-run",
                ]
            )

        assert rc == 0
        assert captured["slugs"] == [
            "direct-market",
            "shared-market",
            "watchlist-only-market",
        ]


# ---------------------------------------------------------------------------
# CLI argument validation
# ---------------------------------------------------------------------------


class TestMain:
    """CLI main() — uses dry-run and injectable dependencies to avoid network."""

    def test_rejects_invalid_near_edge(self):
        rc = main(["--markets", "test-slug", "--near-edge", "0"])
        assert rc == 1

    def test_rejects_invalid_min_depth(self):
        rc = main(["--markets", "test-slug", "--min-depth", "-1"])
        assert rc == 1

    def test_rejects_empty_markets(self):
        rc = main(["--markets", ",,,"])
        assert rc == 1

    def test_resolve_failure_skips_market_and_returns_error_when_all_fail(self):
        """When all slugs fail to resolve, main returns exit code 1."""
        with patch(
            "tools.cli.watch_arb_candidates._resolve_market",
            side_effect=Exception("resolve failed"),
        ):
            rc = main(["--markets", "nonexistent-slug", "--dry-run"])
        assert rc == 1

    def test_dry_run_succeeds_with_resolved_markets(self, capsys):
        """Dry-run resolves markets and prints status without recording."""
        resolved = _resolved("fake-market")

        def fake_resolve(slug):
            return resolved

        def fake_fetch(r):
            return _asks(0.49, 100), _asks(0.50, 100)  # triggers

        with (
            patch("tools.cli.watch_arb_candidates._resolve_market", side_effect=fake_resolve),
            patch("tools.cli.watch_arb_candidates._fetch_books", side_effect=fake_fetch),
        ):
            # We can't run the full blocking loop, so test the watcher directly
            watcher = ArbWatcher(
                resolved_markets=[resolved],
                near_edge_threshold=1.00,
                min_depth=50.0,
                poll_interval=0.0,
                duration_seconds=60.0,
                tapes_base_dir=Path("artifacts/simtrader/tapes"),
                ws_url="wss://test",
                max_concurrent=2,
                dry_run=True,
                _fetch_fn=fake_fetch,
                _record_fn=None,  # should never be called
            )
            watcher._poll_round()

        out = capsys.readouterr().out
        assert "TRIGGER" in out
        assert "DRY-RUN" in out
