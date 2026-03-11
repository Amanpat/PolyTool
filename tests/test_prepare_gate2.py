"""Tests for Gate 2 preparation orchestrator (tools/cli/prepare_gate2.py).

Coverage targets:
  - Scanner output consumed correctly and top N selected.
  - Recorder invoked for each selected candidate with correct arguments.
  - Eligibility results summarized correctly (eligible and ineligible paths).
  - Dry-run skips recording and eligibility.
  - Tapes-dir mode skips scan and record, runs eligibility on existing tapes.
  - Failures (resolve, record, check) are captured as ineligible results.
  - Empty candidate list produces no results.

All tests use injectable functions — no live network, no WebSocket, no file I/O
beyond temporary directories.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.cli.prepare_gate2 import (
    PrepResult,
    check_existing_tapes,
    prepare_candidates,
    print_summary,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_candidate(slug: str, edge_ticks: int = 1, depth_ticks: int = 1):
    """Return a minimal CandidateResult-compatible object."""

    class _Cand:
        pass

    c = _Cand()
    c.slug = slug
    c.edge_ok_ticks = edge_ticks
    c.depth_ok_ticks = depth_ticks
    c.executable_ticks = min(edge_ticks, depth_ticks)
    c.best_edge = 0.01
    c.max_depth_yes = 100.0
    c.max_depth_no = 100.0
    c.total_ticks = 100
    c.source = "live"
    return c


@dataclass
class _FakeEligResult:
    eligible: bool
    reason: str = ""
    stats: dict = None

    def __post_init__(self):
        if self.stats is None:
            self.stats = {
                "ticks_with_depth_and_edge": 1 if self.eligible else 0,
                "ticks_with_depth_ok": 1 if self.eligible else 0,
                "ticks_with_edge_ok": 1 if self.eligible else 0,
            }


def _noop_record(slug, yes_id, no_id, tape_dir, *, duration_seconds, ws_url):
    """Fake recorder: creates tape dir and an empty events.jsonl."""
    tape_dir.mkdir(parents=True, exist_ok=True)
    (tape_dir / "events.jsonl").touch()


def _eligible_check(tape_dir, yes_id, no_id, max_size, buffer):
    return _FakeEligResult(eligible=True)


def _ineligible_check(tape_dir, yes_id, no_id, max_size, buffer):
    return _FakeEligResult(eligible=False, reason="no positive edge: sum_ask=1.05 >= 0.99")


def _fake_resolve(slug):
    return f"YES_{slug}", f"NO_{slug}"


# ---------------------------------------------------------------------------
# 1. Scanner output consumed correctly
# ---------------------------------------------------------------------------


class TestScannerOutputConsumed(unittest.TestCase):
    """Top N candidates are selected from the ranked list."""

    def test_top_n_candidates_selected(self):
        candidates = [_make_candidate(f"market-{i}") for i in range(10)]
        resolve_calls: list[str] = []

        def tracking_resolve(slug):
            resolve_calls.append(slug)
            return f"Y_{slug}", f"N_{slug}"

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=3,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=tracking_resolve,
                _record_fn=_noop_record,
                _check_fn=_eligible_check,
            )

        self.assertEqual(len(results), 3)
        self.assertEqual(len(resolve_calls), 3)
        selected_slugs = [r.slug for r in results]
        self.assertIn("market-0", selected_slugs)
        self.assertIn("market-1", selected_slugs)
        self.assertIn("market-2", selected_slugs)
        self.assertNotIn("market-3", selected_slugs)

    def test_top_capped_at_candidate_count(self):
        """When fewer candidates exist than top N, all are processed."""
        candidates = [_make_candidate("market-only")]
        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=5,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=_noop_record,
                _check_fn=_eligible_check,
            )
        self.assertEqual(len(results), 1)

    def test_empty_candidates_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                [],
                top=3,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
            )
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# 2. Recorder invoked for selected candidates
# ---------------------------------------------------------------------------


class TestRecorderInvoked(unittest.TestCase):
    """Recorder is called with correct slug, IDs, duration, and ws_url."""

    def test_recorder_receives_correct_args(self):
        candidates = [_make_candidate("eth-over-4k")]
        recorder_calls: list[dict] = []

        def tracking_record(slug, yes_id, no_id, tape_dir, *, duration_seconds, ws_url):
            recorder_calls.append(
                {
                    "slug": slug,
                    "yes_id": yes_id,
                    "no_id": no_id,
                    "duration_seconds": duration_seconds,
                    "ws_url": ws_url,
                }
            )
            tape_dir.mkdir(parents=True, exist_ok=True)
            (tape_dir / "events.jsonl").touch()

        def resolve(slug):
            return "YES_TOKEN_42", "NO_TOKEN_99"

        with tempfile.TemporaryDirectory() as tmpdir:
            prepare_candidates(
                candidates,
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=180.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://custom-endpoint",
                dry_run=False,
                _resolve_fn=resolve,
                _record_fn=tracking_record,
                _check_fn=_eligible_check,
            )

        self.assertEqual(len(recorder_calls), 1)
        call = recorder_calls[0]
        self.assertEqual(call["slug"], "eth-over-4k")
        self.assertEqual(call["yes_id"], "YES_TOKEN_42")
        self.assertEqual(call["no_id"], "NO_TOKEN_99")
        self.assertAlmostEqual(call["duration_seconds"], 180.0)
        self.assertEqual(call["ws_url"], "ws://custom-endpoint")

    def test_recorder_called_once_per_candidate(self):
        candidates = [_make_candidate(f"m-{i}") for i in range(4)]
        record_slugs: list[str] = []

        def tracking_record(slug, yes_id, no_id, tape_dir, *, duration_seconds, ws_url):
            record_slugs.append(slug)
            tape_dir.mkdir(parents=True, exist_ok=True)
            (tape_dir / "events.jsonl").touch()

        with tempfile.TemporaryDirectory() as tmpdir:
            prepare_candidates(
                candidates,
                top=4,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=tracking_record,
                _check_fn=_eligible_check,
            )

        self.assertEqual(len(record_slugs), 4)

    def test_tape_dir_created_under_tapes_base(self):
        candidates = [_make_candidate("test-mkt")]

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "tapes"
            results = prepare_candidates(
                candidates,
                top=1,
                tapes_base_dir=base,
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=_noop_record,
                _check_fn=_eligible_check,
            )

        self.assertIsNotNone(results[0].tape_dir)
        # tape_dir should be a child of tapes_base_dir
        self.assertEqual(results[0].tape_dir.parent, base)


# ---------------------------------------------------------------------------
# 3. Eligibility results summarized correctly
# ---------------------------------------------------------------------------


class TestEligibilityResultsSummarized(unittest.TestCase):
    """PrepResult correctly reflects eligible and ineligible outcomes."""

    def _run_single(self, check_fn) -> PrepResult:
        candidates = [_make_candidate("test-market")]
        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=_noop_record,
                _check_fn=check_fn,
            )
        return results[0]

    def test_eligible_result(self):
        r = self._run_single(_eligible_check)
        self.assertEqual(r.slug, "test-market")
        self.assertTrue(r.eligible)
        self.assertEqual(r.reject_reason, "")
        self.assertIsNotNone(r.tape_dir)

    def test_ineligible_result_captures_reason(self):
        r = self._run_single(_ineligible_check)
        self.assertFalse(r.eligible)
        self.assertIn("no positive edge", r.reject_reason)

    def test_ineligible_reason_blank_for_eligible(self):
        r = self._run_single(_eligible_check)
        self.assertEqual(r.reject_reason, "")

    def test_mixed_results(self):
        candidates = [_make_candidate("market-good"), _make_candidate("market-bad")]
        call_n = [0]

        def alternating_check(tape_dir, yes_id, no_id, max_size, buffer):
            call_n[0] += 1
            return _FakeEligResult(eligible=(call_n[0] % 2 == 1))

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=2,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=_noop_record,
                _check_fn=alternating_check,
            )

        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].eligible)
        self.assertFalse(results[1].eligible)


# ---------------------------------------------------------------------------
# 4. Dry-run path
# ---------------------------------------------------------------------------


class TestDryRun(unittest.TestCase):
    """Dry-run skips recording and eligibility but returns slugs."""

    def test_dry_run_skips_recorder(self):
        candidates = [_make_candidate("market-a"), _make_candidate("market-b")]
        record_calls: list = []
        check_calls: list = []

        def tracking_record(*args, **kwargs):
            record_calls.append(args)

        def tracking_check(*args, **kwargs):
            check_calls.append(args)
            return _FakeEligResult(eligible=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=2,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=True,
                _resolve_fn=_fake_resolve,
                _record_fn=tracking_record,
                _check_fn=tracking_check,
            )

        self.assertEqual(len(record_calls), 0, "recorder must not be called in dry-run")
        self.assertEqual(len(check_calls), 0, "eligibility check must not be called in dry-run")

    def test_dry_run_result_eligible_is_none(self):
        candidates = [_make_candidate("dry-mkt")]
        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=True,
            )
        self.assertIsNone(results[0].eligible)

    def test_dry_run_result_has_slug(self):
        candidates = [_make_candidate("dry-market-x")]
        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=True,
            )
        self.assertEqual(results[0].slug, "dry-market-x")


# ---------------------------------------------------------------------------
# 5. Tapes-dir mode (offline path)
# ---------------------------------------------------------------------------


class TestTapesDirMode(unittest.TestCase):
    """check_existing_tapes() reads existing tapes, no scan or record."""

    def _make_tape_dir(self, base: Path, slug: str, yes_id: str, no_id: str) -> Path:
        """Create a minimal tape directory with prep_meta.json and empty events.jsonl."""
        td = base / f"tape_{slug}"
        td.mkdir(parents=True)
        (td / "prep_meta.json").write_text(
            json.dumps({"market_slug": slug, "yes_asset_id": yes_id, "no_asset_id": no_id}),
            encoding="utf-8",
        )
        (td / "events.jsonl").write_text("", encoding="utf-8")
        return td

    def test_eligible_tape_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            self._make_tape_dir(base, "good-market", "YES1", "NO1")

            results = check_existing_tapes(
                base,
                max_size=50.0,
                buffer=0.01,
                _check_fn=_eligible_check,
            )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].eligible)
        self.assertEqual(results[0].slug, "good-market")

    def test_ineligible_tape_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            self._make_tape_dir(base, "bad-market", "YES2", "NO2")

            results = check_existing_tapes(
                base,
                max_size=50.0,
                buffer=0.01,
                _check_fn=_ineligible_check,
            )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].eligible)

    def test_multiple_tapes_all_checked(self):
        call_count = [0]

        def counting_check(tape_dir, yes_id, no_id, max_size, buffer):
            call_count[0] += 1
            return _FakeEligResult(eligible=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            for i in range(3):
                self._make_tape_dir(base, f"mkt-{i}", f"YES{i}", f"NO{i}")

            results = check_existing_tapes(
                base,
                max_size=50.0,
                buffer=0.01,
                _check_fn=counting_check,
            )

        self.assertEqual(len(results), 3)
        self.assertEqual(call_count[0], 3)

    def test_tape_without_asset_ids_reports_error(self):
        """Tape with no metadata produces an ineligible result with a clear reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            td = base / "tape_no_meta"
            td.mkdir()
            (td / "events.jsonl").write_text("", encoding="utf-8")
            # No prep_meta.json and no meta.json

            results = check_existing_tapes(
                base,
                max_size=50.0,
                buffer=0.01,
                _check_fn=_eligible_check,
            )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].eligible)
        self.assertIn("asset IDs", results[0].reject_reason)

    def test_asset_id_fallback_from_event_stream(self):
        """When metadata is absent, asset IDs are discovered from events.jsonl."""
        events = [
            json.dumps({
                "event_type": "book",
                "asset_id": "ASSET_YES",
                "market": "test",
                "asks": [],
                "bids": [],
                "seq": 1,
                "ts_recv": 1000,
            }),
            json.dumps({
                "event_type": "book",
                "asset_id": "ASSET_NO",
                "market": "test",
                "asks": [],
                "bids": [],
                "seq": 2,
                "ts_recv": 1001,
            }),
        ]
        check_calls: list[dict] = []

        def tracking_check(tape_dir, yes_id, no_id, max_size, buffer):
            check_calls.append({"yes_id": yes_id, "no_id": no_id})
            return _FakeEligResult(eligible=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            td = base / "tape_events_only"
            td.mkdir()
            (td / "events.jsonl").write_text("\n".join(events), encoding="utf-8")
            # No prep_meta.json, no meta.json

            results = check_existing_tapes(
                base,
                max_size=50.0,
                buffer=0.01,
                _check_fn=tracking_check,
            )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].eligible)
        self.assertEqual(check_calls[0]["yes_id"], "ASSET_YES")
        self.assertEqual(check_calls[0]["no_id"], "ASSET_NO")

    def test_empty_tapes_dir_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = check_existing_tapes(
                Path(tmpdir),
                max_size=50.0,
                buffer=0.01,
                _check_fn=_eligible_check,
            )
        self.assertEqual(results, [])


# ---------------------------------------------------------------------------
# 6. Failure handling
# ---------------------------------------------------------------------------


class TestFailureHandling(unittest.TestCase):
    """Resolve and record failures are captured as ineligible results."""

    def test_resolve_failure_captured(self):
        def fail_resolve(slug):
            raise RuntimeError("network timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                [_make_candidate("bad-mkt")],
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=fail_resolve,
            )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].eligible)
        self.assertIn("resolve failed", results[0].reject_reason)
        self.assertIn("network timeout", results[0].reject_reason)

    def test_record_failure_captured(self):
        def fail_record(slug, yes_id, no_id, tape_dir, *, duration_seconds, ws_url):
            raise ConnectionRefusedError("WS connection refused")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                [_make_candidate("ws-fail-mkt")],
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=fail_record,
            )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].eligible)
        self.assertIn("record failed", results[0].reject_reason)

    def test_check_failure_captured(self):
        def fail_check(tape_dir, yes_id, no_id, max_size, buffer):
            raise ValueError("unexpected tape format")

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                [_make_candidate("check-fail-mkt")],
                top=1,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=_fake_resolve,
                _record_fn=_noop_record,
                _check_fn=fail_check,
            )

        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].eligible)
        self.assertIn("eligibility check error", results[0].reject_reason)

    def test_resolve_failure_does_not_stop_subsequent_candidates(self):
        """A resolve failure for one candidate does not abort the rest."""
        candidates = [_make_candidate("bad-mkt"), _make_candidate("good-mkt")]
        bad_slugs = {"bad-mkt"}

        def selective_resolve(slug):
            if slug in bad_slugs:
                raise RuntimeError("resolve failed")
            return f"YES_{slug}", f"NO_{slug}"

        with tempfile.TemporaryDirectory() as tmpdir:
            results = prepare_candidates(
                candidates,
                top=2,
                tapes_base_dir=Path(tmpdir),
                duration_seconds=60.0,
                max_size=50.0,
                buffer=0.01,
                ws_url="ws://test",
                dry_run=False,
                _resolve_fn=selective_resolve,
                _record_fn=_noop_record,
                _check_fn=_eligible_check,
            )

        self.assertEqual(len(results), 2)
        self.assertFalse(results[0].eligible)  # bad-mkt
        self.assertTrue(results[1].eligible)   # good-mkt


# ---------------------------------------------------------------------------
# 7. print_summary formatting
# ---------------------------------------------------------------------------


class TestPrintSummary(unittest.TestCase):
    """print_summary produces correct table output."""

    def _capture_summary(self, results, *, dry_run=False) -> str:
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            print_summary(results, dry_run=dry_run)
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    def test_eligible_shows_eligible_status(self):
        r = PrepResult(slug="good-market", eligible=True, tape_dir=Path("/some/tape"))
        output = self._capture_summary([r])
        self.assertIn("ELIGIBLE", output)
        self.assertIn("good-market", output)

    def test_ineligible_shows_reject_reason(self):
        r = PrepResult(
            slug="bad-market",
            eligible=False,
            reject_reason="no positive edge",
        )
        output = self._capture_summary([r])
        self.assertIn("INELIGIBLE", output)
        self.assertIn("no positive edge", output)

    def test_dry_run_shows_dry_run_status(self):
        r = PrepResult(slug="dry-market")
        output = self._capture_summary([r], dry_run=True)
        self.assertIn("DRY-RUN", output)

    def test_summary_counts_eligible(self):
        results = [
            PrepResult(slug="a", eligible=True, tape_dir=Path("/t/a")),
            PrepResult(slug="b", eligible=False, reject_reason="no edge"),
            PrepResult(slug="c", eligible=True, tape_dir=Path("/t/c")),
        ]
        output = self._capture_summary(results)
        self.assertIn("Eligible: 2", output)

    def test_empty_results(self):
        output = self._capture_summary([])
        self.assertIn("No candidates processed", output)

    def test_eligible_tape_shows_sweep_command(self):
        tape_dir = Path("/artifacts/simtrader/tapes/some_tape")
        r = PrepResult(slug="my-market", eligible=True, tape_dir=tape_dir)
        output = self._capture_summary([r])
        self.assertIn("simtrader sweep", output)
        self.assertIn(str(tape_dir / "events.jsonl"), output)

    def test_no_sweep_command_for_dry_run(self):
        r = PrepResult(slug="my-market")
        output = self._capture_summary([r], dry_run=True)
        self.assertNotIn("simtrader sweep", output)


if __name__ == "__main__":
    unittest.main()
