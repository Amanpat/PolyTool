"""Tests for scan_gate2_candidates ranking logic and snapshot scoring.

All tests are fully offline — no network calls, no live API, no tape files.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.cli.scan_gate2_candidates import (
    CandidateResult,
    _best_ask_price_and_size,
    rank_candidates,
    scan_tapes,
    score_snapshot,
)


# ---------------------------------------------------------------------------
# _best_ask_price_and_size
# ---------------------------------------------------------------------------


class TestBestAskPriceAndSize:
    def test_dict_levels(self):
        asks = [{"price": "0.60", "size": "100"}, {"price": "0.55", "size": "75"}]
        price, size = _best_ask_price_and_size(asks)
        assert price == pytest.approx(0.55)
        assert size == pytest.approx(75.0)

    def test_list_levels(self):
        asks = [["0.70", "50"], ["0.65", "120"]]
        price, size = _best_ask_price_and_size(asks)
        assert price == pytest.approx(0.65)
        assert size == pytest.approx(120.0)

    def test_empty_asks(self):
        assert _best_ask_price_and_size([]) == (None, None)

    def test_single_level(self):
        asks = [{"price": "0.42", "size": "200"}]
        price, size = _best_ask_price_and_size(asks)
        assert price == pytest.approx(0.42)
        assert size == pytest.approx(200.0)

    def test_malformed_level_skipped(self):
        asks = [None, {"price": "0.50", "size": "80"}]
        price, size = _best_ask_price_and_size(asks)
        assert price == pytest.approx(0.50)
        assert size == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# score_snapshot
# ---------------------------------------------------------------------------


class TestScoreSnapshot:
    def _yes_asks(self, price: float, size: float) -> list:
        return [{"price": str(price), "size": str(size)}]

    def _no_asks(self, price: float, size: float) -> list:
        return [{"price": str(price), "size": str(size)}]

    def test_executable_both_conditions_met(self):
        # sum_ask = 0.40 + 0.55 = 0.95 < 0.99, both sizes >= 50
        snap = score_snapshot(
            self._yes_asks(0.40, 60),
            self._no_asks(0.55, 60),
            max_size=50,
            buffer=0.01,
        )
        assert snap["executable"] is True
        assert snap["depth_ok"] is True
        assert snap["edge_ok"] is True
        assert snap["sum_ask"] == pytest.approx(0.95)
        assert snap["edge_gap"] == pytest.approx(0.04)

    def test_depth_fail_insufficient_yes(self):
        # YES size 30 < 50 → depth fails
        snap = score_snapshot(
            self._yes_asks(0.40, 30),
            self._no_asks(0.55, 60),
            max_size=50,
            buffer=0.01,
        )
        assert snap["depth_ok"] is False
        assert snap["executable"] is False

    def test_depth_fail_insufficient_no(self):
        snap = score_snapshot(
            self._yes_asks(0.40, 60),
            self._no_asks(0.55, 10),
            max_size=50,
            buffer=0.01,
        )
        assert snap["depth_ok"] is False
        assert snap["executable"] is False

    def test_edge_fail_sum_too_high(self):
        # sum_ask = 0.50 + 0.51 = 1.01 >= 0.99
        snap = score_snapshot(
            self._yes_asks(0.50, 100),
            self._no_asks(0.51, 100),
            max_size=50,
            buffer=0.01,
        )
        assert snap["edge_ok"] is False
        assert snap["executable"] is False

    def test_edge_fail_sum_exactly_at_threshold(self):
        # sum_ask = 0.495 + 0.495 = 0.99 — NOT strictly less than threshold
        snap = score_snapshot(
            self._yes_asks(0.495, 100),
            self._no_asks(0.495, 100),
            max_size=50,
            buffer=0.01,
        )
        assert snap["edge_ok"] is False

    def test_empty_yes_book(self):
        snap = score_snapshot([], self._no_asks(0.55, 100), max_size=50, buffer=0.01)
        assert snap["executable"] is False
        assert snap["yes_ask"] is None

    def test_empty_no_book(self):
        snap = score_snapshot(self._yes_asks(0.40, 100), [], max_size=50, buffer=0.01)
        assert snap["executable"] is False
        assert snap["no_ask"] is None

    def test_edge_gap_is_negative_when_no_edge(self):
        # sum_ask = 1.01, gap = 0.99 - 1.01 = -0.02
        snap = score_snapshot(
            self._yes_asks(0.51, 100),
            self._no_asks(0.50, 100),
            max_size=50,
            buffer=0.01,
        )
        assert snap["edge_gap"] == pytest.approx(-0.02)

    def test_custom_buffer_and_max_size(self):
        # buffer=0.05 → threshold=0.95; sum_ask=0.90 < 0.95 → edge_ok
        snap = score_snapshot(
            self._yes_asks(0.40, 5),
            self._no_asks(0.50, 5),
            max_size=1,
            buffer=0.05,
        )
        assert snap["edge_ok"] is True
        assert snap["depth_ok"] is True
        assert snap["executable"] is True


# ---------------------------------------------------------------------------
# rank_candidates
# ---------------------------------------------------------------------------


def _make_result(
    slug: str,
    executable: int = 0,
    edge: int = 0,
    depth: int = 0,
    best_edge: float = -0.10,
    max_yes: float = 10.0,
    max_no: float = 10.0,
) -> CandidateResult:
    return CandidateResult(
        slug=slug,
        total_ticks=max(executable + edge + depth, 1),
        depth_ok_ticks=depth,
        edge_ok_ticks=edge,
        executable_ticks=executable,
        best_edge=best_edge,
        max_depth_yes=max_yes,
        max_depth_no=max_no,
        source="test",
    )


class TestRankCandidates:
    def test_executable_market_ranks_first(self):
        results = [
            _make_result("depth-only", depth=5),
            _make_result("executable", executable=3, edge=5, depth=5),
            _make_result("edge-only", edge=2),
        ]
        ranked = rank_candidates(results)
        assert ranked[0].slug == "executable"

    def test_edge_only_ranks_above_depth_only(self):
        results = [
            _make_result("depth-only", depth=10),
            _make_result("edge-only", edge=5),
        ]
        ranked = rank_candidates(results)
        assert ranked[0].slug == "edge-only"

    def test_depth_only_ranks_above_no_signal(self):
        results = [
            _make_result("no-signal"),
            _make_result("depth-only", depth=3),
        ]
        ranked = rank_candidates(results)
        assert ranked[0].slug == "depth-only"

    def test_best_edge_breaks_tie(self):
        a = _make_result("close", edge=5, best_edge=-0.001)
        b = _make_result("far", edge=5, best_edge=-0.05)
        ranked = rank_candidates([b, a])
        assert ranked[0].slug == "close"

    def test_depth_breaks_tie_at_same_edge(self):
        a = _make_result("deep", edge=3, depth=10, max_yes=200, max_no=200)
        b = _make_result("shallow", edge=3, depth=10, max_yes=20, max_no=20)
        ranked = rank_candidates([b, a])
        assert ranked[0].slug == "deep"

    def test_empty_input(self):
        assert rank_candidates([]) == []

    def test_single_result_returned(self):
        r = _make_result("solo")
        assert rank_candidates([r]) == [r]

    def test_executable_count_breaks_tie(self):
        a = _make_result("more-exec", executable=10, edge=10, depth=10)
        b = _make_result("less-exec", executable=3, edge=10, depth=10)
        ranked = rank_candidates([b, a])
        assert ranked[0].slug == "more-exec"


# ---------------------------------------------------------------------------
# scan_tapes (offline, using temp tape files)
# ---------------------------------------------------------------------------


def _write_events(path: Path, events: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(e) for e in events),
        encoding="utf-8",
    )


def _book_event(asset_id: str, asks: list[dict], seq: int = 0) -> dict:
    return {
        "event_type": "book",
        "asset_id": asset_id,
        "seq": seq,
        "ts_recv": 1000.0 + seq,
        "bids": [],
        "asks": asks,
    }


def _price_change_event(
    changes: list[dict], seq: int = 1
) -> dict:
    return {
        "event_type": "price_change",
        "price_changes": changes,
        "seq": seq,
        "ts_recv": 1000.0 + seq,
    }


YES_ID = "aaa" * 20 + "1"
NO_ID = "bbb" * 20 + "2"


class TestScanTapes:
    def test_executable_tape_scored(self, tmp_path):
        """Tape with depth >= 50 and sum_ask < 0.99 produces executable_ticks > 0."""
        tape_dir = tmp_path / "tape_executable"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.40", "size": "100"}], seq=0),
            _book_event(NO_ID, [{"price": "0.50", "size": "100"}], seq=1),
            # price_change brings books to: yes=0.40 (100), no=0.50 (100)
            # sum_ask = 0.90 < 0.99, both sizes 100 >= 50 → executable
            _price_change_event([
                {"asset_id": YES_ID, "price": "0.40", "size": "100", "side": "SELL"},
                {"asset_id": NO_ID,  "price": "0.50", "size": "100", "side": "SELL"},
            ], seq=2),
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        r = results[0]
        assert r.executable_ticks > 0
        assert r.edge_ok_ticks > 0
        assert r.depth_ok_ticks > 0
        assert r.best_edge > 0

    def test_no_edge_tape_not_executable(self, tmp_path):
        """Tape with sum_ask > 0.99 has edge_ok_ticks == 0."""
        tape_dir = tmp_path / "tape_no_edge"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.52", "size": "100"}], seq=0),
            _book_event(NO_ID,  [{"price": "0.50", "size": "100"}], seq=1),
            # sum_ask = 1.02 > 0.99
            _price_change_event([
                {"asset_id": YES_ID, "price": "0.52", "size": "100", "side": "SELL"},
                {"asset_id": NO_ID,  "price": "0.50", "size": "100", "side": "SELL"},
            ], seq=2),
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        r = results[0]
        assert r.edge_ok_ticks == 0
        assert r.executable_ticks == 0

    def test_no_depth_tape_not_executable(self, tmp_path):
        """Tape with best-ask sizes < max_size has depth_ok_ticks == 0."""
        tape_dir = tmp_path / "tape_no_depth"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.40", "size": "10"}], seq=0),  # size < 50
            _book_event(NO_ID,  [{"price": "0.50", "size": "10"}], seq=1),  # size < 50
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        r = results[0]
        assert r.depth_ok_ticks == 0
        assert r.executable_ticks == 0

    def test_tape_with_only_one_asset_skipped(self, tmp_path):
        """Tape with only one book asset produces no result (cannot compute sum_ask)."""
        tape_dir = tmp_path / "tape_one_asset"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.40", "size": "100"}], seq=0),
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert results == []

    def test_empty_tapes_dir(self, tmp_path):
        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert results == []

    def test_max_depth_tracked_across_ticks(self, tmp_path):
        """max_depth_yes and max_depth_no reflect the peak sizes seen."""
        tape_dir = tmp_path / "tape_depth_tracking"
        tape_dir.mkdir()
        events = [
            # Initial snapshot: sizes 100 and 80
            _book_event(YES_ID, [{"price": "0.40", "size": "100"}], seq=0),
            _book_event(NO_ID,  [{"price": "0.50", "size": "80"}],  seq=1),
            # Update: YES drops to 20, NO stays 80
            _price_change_event([
                {"asset_id": YES_ID, "price": "0.40", "size": "20", "side": "SELL"},
            ], seq=2),
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        r = results[0]
        assert r.max_depth_yes == pytest.approx(100.0)  # peak was 100 on first book event
        assert r.max_depth_no == pytest.approx(80.0)

    def test_meta_json_slug_used_when_present(self, tmp_path):
        """Slug is read from meta.json shadow_context if available."""
        tape_dir = tmp_path / "20260306T000000Z_some_hash"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.40", "size": "100"}], seq=0),
            _book_event(NO_ID,  [{"price": "0.50", "size": "100"}], seq=1),
        ]
        _write_events(tape_dir / "events.jsonl", events)
        meta = {"shadow_context": {"market": "my-cool-market"}}
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        assert results[0].slug == "my-cool-market"

    def test_slug_falls_back_to_dir_name(self, tmp_path):
        """Without meta.json, slug is the tape directory name."""
        tape_dir = tmp_path / "my-tape-dir-name"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.40", "size": "100"}], seq=0),
            _book_event(NO_ID,  [{"price": "0.50", "size": "100"}], seq=1),
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        assert results[0].slug == "my-tape-dir-name"

    def test_best_edge_negative_when_no_edge(self, tmp_path):
        """best_edge is negative when sum_ask > threshold throughout."""
        tape_dir = tmp_path / "tape_neg_edge"
        tape_dir.mkdir()
        events = [
            _book_event(YES_ID, [{"price": "0.55", "size": "100"}], seq=0),
            _book_event(NO_ID,  [{"price": "0.50", "size": "100"}], seq=1),
        ]
        _write_events(tape_dir / "events.jsonl", events)

        results = scan_tapes(tmp_path, max_size=50, buffer=0.01)
        assert len(results) == 1
        # sum_ask = 1.05, edge_gap = 0.99 - 1.05 = -0.06
        assert results[0].best_edge < 0
