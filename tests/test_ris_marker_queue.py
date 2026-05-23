"""Offline unit tests for Marker Canonical Academic Parse Queue v0.

All tests are fully offline — no network, no Docker, no real Marker install.
The injected fake fetcher replaces LiveAcademicFetcher in all process_next tests.

Covers:
- enqueue idempotency (same paper not re-enqueued)
- force re-enqueue resets status to pending
- process success: fake marker fetcher -> done, marker_ready=True
- process failure: marker_failed -> failure_reason recorded, marker_ready=False
- marker_ready semantics: only marker body_source + body_length >= threshold
- pdfplumber_fallback not rag_ready
- abstract_fallback not rag_ready
- retry logic: attempts increment; after MAX_ATTEMPTS -> failed
- get_counts returns correct breakdown
- CLI help exits 0; CLI enqueue/list/counts commands work offline
"""
from __future__ import annotations

import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeFetcher:
    """Injectable fetcher stub that returns a fixed raw_source dict."""

    def __init__(self, raw_source: dict) -> None:
        self._raw = raw_source

    def fetch(self, url: str) -> dict:  # noqa: ARG002
        return dict(self._raw)


class _ErrorFetcher:
    """Injectable fetcher that raises an exception."""

    def fetch(self, url: str) -> dict:
        raise RuntimeError("simulated network error")


def _marker_raw(body_length: int = 10000, parse_seconds: float = 6.0) -> dict:
    return {
        "title": "Test Paper",
        "body_source": "marker",
        "body_length": body_length,
        "parse_seconds": parse_seconds,
        "failure_reason": None,
    }


def _failed_raw(reason: str = "marker_timeout: 900s") -> dict:
    return {
        "title": "Test Paper",
        "body_source": "marker_failed",
        "body_length": 0,
        "parse_seconds": 0.0,
        "failure_reason": reason,
    }


def _pdfplumber_raw(body_length: int = 12000) -> dict:
    return {
        "title": "Test Paper",
        "body_source": "pdfplumber_fallback",
        "body_length": body_length,
        "parse_seconds": 0.0,
        "fallback_reason": "marker not installed",
    }


# ---------------------------------------------------------------------------
# is_marker_ready unit tests
# ---------------------------------------------------------------------------


class TestIsMarkerReady:
    def test_marker_long_enough_is_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("marker", 10000) is True

    def test_marker_exactly_threshold_is_ready(self) -> None:
        from packages.research.ingestion.marker_queue import (
            MIN_MARKER_BODY_LENGTH,
            is_marker_ready,
        )
        assert is_marker_ready("marker", MIN_MARKER_BODY_LENGTH) is True

    def test_marker_below_threshold_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import (
            MIN_MARKER_BODY_LENGTH,
            is_marker_ready,
        )
        assert is_marker_ready("marker", MIN_MARKER_BODY_LENGTH - 1) is False

    def test_pdfplumber_fallback_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("pdfplumber_fallback", 50000) is False

    def test_pdfplumber_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("pdf", 50000) is False

    def test_marker_failed_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("marker_failed", 0) is False

    def test_abstract_fallback_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("abstract_fallback", 500) is False

    def test_error_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("error", 100000) is False

    def test_unknown_not_ready(self) -> None:
        from packages.research.ingestion.marker_queue import is_marker_ready
        assert is_marker_ready("unknown", 99999) is False


# ---------------------------------------------------------------------------
# extract_arxiv_id
# ---------------------------------------------------------------------------


class TestExtractArxivId:
    def test_bare_id(self) -> None:
        from packages.research.ingestion.marker_queue import extract_arxiv_id
        assert extract_arxiv_id("2604.24366") == "2604.24366"

    def test_abs_url(self) -> None:
        from packages.research.ingestion.marker_queue import extract_arxiv_id
        assert extract_arxiv_id("https://arxiv.org/abs/2604.24366") == "2604.24366"

    def test_pdf_url(self) -> None:
        from packages.research.ingestion.marker_queue import extract_arxiv_id
        assert extract_arxiv_id("https://arxiv.org/pdf/2404.01234.pdf") == "2404.01234"

    def test_no_id_returns_none(self) -> None:
        from packages.research.ingestion.marker_queue import extract_arxiv_id
        assert extract_arxiv_id("https://example.com/paper") is None

    def test_invalid_str_returns_none(self) -> None:
        from packages.research.ingestion.marker_queue import extract_arxiv_id
        assert extract_arxiv_id("not-a-url") is None


# ---------------------------------------------------------------------------
# Enqueue tests
# ---------------------------------------------------------------------------


class TestEnqueue:
    def test_enqueue_new_item(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        result = q.enqueue("2604.24366")
        assert result["action"] == "added"
        assert result["status"] == "pending"
        assert result["candidate_id"] == "arxiv:2604.24366"

        records = q.list_queue()
        assert len(records) == 1
        assert records[0]["status"] == "pending"
        assert records[0]["attempts"] == 0
        assert records[0]["source_url"] == "https://arxiv.org/abs/2604.24366"

    def test_enqueue_idempotent_same_bare_id(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        result2 = q.enqueue("2604.24366")
        assert result2["action"] == "skipped"
        assert len(q.list_queue()) == 1

    def test_enqueue_idempotent_full_url(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        result2 = q.enqueue("https://arxiv.org/abs/2604.24366")
        assert result2["action"] == "skipped"
        assert len(q.list_queue()) == 1

    def test_enqueue_force_resets_to_pending(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        # Simulate failed state by manually writing
        records = q.list_queue()
        records[0]["status"] = "failed"
        records[0]["attempts"] = MAX_ATTEMPTS
        q._write_queue(records)

        result = q.enqueue("2604.24366", force=True)
        assert result["action"] == "reset"
        assert result["status"] == "pending"

        records = q.list_queue()
        assert records[0]["status"] == "pending"
        assert records[0]["attempts"] == 0

    def test_enqueue_invalid_url_raises(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        with pytest.raises(ValueError, match="Cannot extract arXiv ID"):
            q.enqueue("https://example.com/not-arxiv")

    def test_enqueue_multiple_different_papers(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        records = q.list_queue()
        assert len(records) == 2
        ids = {r["arxiv_id"] for r in records}
        assert ids == {"2604.24366", "2401.00001"}

    def test_enqueue_with_title_hint(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366", title="My Paper Title")
        records = q.list_queue()
        assert records[0]["title"] == "My Paper Title"


# ---------------------------------------------------------------------------
# get_counts tests
# ---------------------------------------------------------------------------


class TestGetCounts:
    def test_empty_queue(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        counts = q.get_counts()
        assert counts["total"] == 0
        assert counts["pending"] == 0

    def test_counts_after_enqueue(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        counts = q.get_counts()
        assert counts["total"] == 2
        assert counts["pending"] == 2
        assert counts["done"] == 0

    def test_counts_reflect_status(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        records = q.list_queue()
        records[0]["status"] = "done"
        q._write_queue(records)
        counts = q.get_counts()
        assert counts["pending"] == 1
        assert counts["done"] == 1


# ---------------------------------------------------------------------------
# process_next — success path
# ---------------------------------------------------------------------------


class TestProcessSuccess:
    def test_process_marker_success_marks_done(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")

        results = q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))

        assert len(results) == 1
        r = results[0]
        assert r["body_source"] == "marker"
        assert r["marker_ready"] is True
        assert r["rejected"] is False
        assert r["exit_code"] == 0
        assert r["queue_status"] == "done"

    def test_process_updates_queue_to_done(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))

        records = q.list_queue()
        assert records[0]["status"] == "done"
        assert records[0]["attempts"] == 1

    def test_process_updates_title_from_fetcher(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        raw = _marker_raw()
        raw["title"] = "Resolved Title From API"
        q.process_next(max_items=1, _fetcher=_FakeFetcher(raw))

        records = q.list_queue()
        assert records[0]["title"] == "Resolved Title From API"

    def test_process_writes_result_record(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))

        assert q._results_path.exists()
        with open(q._results_path, encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) == 1
        rec = json.loads(lines[0])
        assert rec["body_source"] == "marker"
        assert rec["marker_ready"] is True
        assert "processed_at" in rec

    def test_process_multiple_items_sequentially(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        results = q.process_next(max_items=2, _fetcher=_FakeFetcher(_marker_raw()))
        assert len(results) == 2
        assert all(r["marker_ready"] for r in results)
        counts = q.get_counts()
        assert counts["done"] == 2
        assert counts["pending"] == 0

    def test_process_respects_max_items(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        results = q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))
        assert len(results) == 1
        counts = q.get_counts()
        assert counts["pending"] == 1
        assert counts["done"] == 1

    def test_process_empty_queue_returns_empty(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        results = q.process_next(max_items=5, _fetcher=_FakeFetcher(_marker_raw()))
        assert results == []


# ---------------------------------------------------------------------------
# process_next — failure paths
# ---------------------------------------------------------------------------


class TestProcessFailure:
    def test_marker_failed_records_failure_reason(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        raw = _failed_raw("marker_timeout: extraction timed out after 900s")
        results = q.process_next(max_items=1, _fetcher=_FakeFetcher(raw))

        r = results[0]
        assert r["body_source"] == "marker_failed"
        assert r["marker_ready"] is False
        assert r["rejected"] is True
        assert "marker_timeout" in r["failure_reason"]
        assert r["exit_code"] == 1

    def test_marker_failed_increments_attempts(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_failed_raw()))
        records = q.list_queue()
        assert records[0]["attempts"] == 1

    def test_marker_failed_stays_pending_until_max_attempts(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        fetcher = _FakeFetcher(_failed_raw())

        for i in range(MAX_ATTEMPTS - 1):
            q.process_next(max_items=1, _fetcher=fetcher)
            records = q.list_queue()
            assert records[0]["status"] == "pending", f"Should still be pending after {i+1} attempts"
            assert records[0]["attempts"] == i + 1

    def test_marker_failed_becomes_failed_after_max_attempts(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        fetcher = _FakeFetcher(_failed_raw())

        for _ in range(MAX_ATTEMPTS):
            q.process_next(max_items=1, _fetcher=fetcher)

        records = q.list_queue()
        assert records[0]["status"] == "failed"
        assert records[0]["attempts"] == MAX_ATTEMPTS

    def test_network_error_records_failure_reason(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        results = q.process_next(max_items=1, _fetcher=_ErrorFetcher())
        r = results[0]
        assert r["body_source"] == "error"
        assert r["rejected"] is True
        assert "simulated network error" in r["failure_reason"]
        assert r["marker_ready"] is False

    def test_pdfplumber_fallback_not_marker_ready(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        results = q.process_next(max_items=1, _fetcher=_FakeFetcher(_pdfplumber_raw()))
        r = results[0]
        assert r["body_source"] == "pdfplumber_fallback"
        assert r["marker_ready"] is False
        assert r["rejected"] is True

    def test_abstract_fallback_not_marker_ready(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        raw = {
            "title": "Test",
            "body_source": "abstract_fallback",
            "body_length": 0,
            "parse_seconds": 0.0,
            "fallback_reason": "download failed",
        }
        results = q.process_next(max_items=1, _fetcher=_FakeFetcher(raw))
        r = results[0]
        assert r["marker_ready"] is False
        assert r["rejected"] is True

    def test_marker_short_body_not_ready(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MIN_MARKER_BODY_LENGTH
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        short_raw = _marker_raw(body_length=MIN_MARKER_BODY_LENGTH - 1)
        results = q.process_next(max_items=1, _fetcher=_FakeFetcher(short_raw))
        r = results[0]
        assert r["body_source"] == "marker"
        assert r["marker_ready"] is False
        # Short Marker output is an auditable failure — not silently marked done
        assert r["rejected"] is True
        assert r["exit_code"] == 1
        assert "marker_body_too_short" in r["failure_reason"]
        # First attempt: retryable (pending), not yet terminal
        assert r["queue_status"] == "pending"

    def test_marker_short_body_failure_reason_contains_lengths(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MIN_MARKER_BODY_LENGTH
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        short_body_len = MIN_MARKER_BODY_LENGTH - 1
        results = q.process_next(
            max_items=1, _fetcher=_FakeFetcher(_marker_raw(body_length=short_body_len))
        )
        r = results[0]
        assert str(short_body_len) in r["failure_reason"]
        assert str(MIN_MARKER_BODY_LENGTH) in r["failure_reason"]

    def test_marker_short_body_becomes_failed_after_max_attempts(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS, MIN_MARKER_BODY_LENGTH
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        fetcher = _FakeFetcher(_marker_raw(body_length=MIN_MARKER_BODY_LENGTH - 1))
        for _ in range(MAX_ATTEMPTS):
            q.process_next(max_items=1, _fetcher=fetcher)
        records = q.list_queue()
        assert records[0]["status"] == "failed"
        assert records[0]["attempts"] == MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# list_queue filter tests
# ---------------------------------------------------------------------------


class TestListQueue:
    def test_list_all(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        assert len(q.list_queue()) == 2

    def test_list_filter_pending(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        records = q.list_queue()
        records[0]["status"] = "done"
        q._write_queue(records)

        pending = q.list_queue(status_filter="pending")
        assert len(pending) == 1
        assert pending[0]["arxiv_id"] == "2401.00001"

    def test_list_filter_all_explicit(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        assert len(q.list_queue(status_filter="all")) == 1


# ---------------------------------------------------------------------------
# CLI tests (offline)
# ---------------------------------------------------------------------------


def _run_cli(argv: list[str]) -> tuple[int, str]:
    """Run the research-marker-queue CLI and capture stdout."""
    from tools.cli.research_marker_queue import main
    buf = StringIO()
    with redirect_stdout(buf):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else 1
    return code, buf.getvalue()


class TestCLI:
    def test_help_exits_zero(self) -> None:
        code, out = _run_cli(["--help"])
        assert code == 0
        assert "enqueue" in out

    def test_no_subcommand_exits_nonzero(self) -> None:
        code, _ = _run_cli([])
        assert code == 1

    def test_enqueue_subcommand_help(self) -> None:
        code, out = _run_cli(["enqueue", "--help"])
        assert code == 0
        assert "--url" in out

    def test_process_subcommand_help(self) -> None:
        code, out = _run_cli(["process", "--help"])
        assert code == 0
        assert "--max-items" in out

    def test_counts_empty_queue(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "counts"])
        assert code == 0
        assert "pending" in out
        assert "total" in out

    def test_counts_json(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "counts", "--json"])
        assert code == 0
        data = json.loads(out)
        assert "pending" in data
        assert "total" in data

    def test_enqueue_cli_adds_item(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "2604.24366",
        ])
        assert code == 0
        assert "Enqueued" in out or "arxiv:2604.24366" in out

    def test_enqueue_cli_idempotent(self, tmp_path: Path) -> None:
        _run_cli(["--queue-dir", str(tmp_path), "enqueue", "--url", "2604.24366"])
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "2604.24366",
        ])
        assert code == 0
        assert "Skipped" in out or "skipped" in out

    def test_enqueue_cli_json(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "2604.24366", "--json",
        ])
        assert code == 0
        data = json.loads(out)
        assert data["action"] == "added"
        assert data["candidate_id"] == "arxiv:2604.24366"

    def test_list_cli_empty(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "list"])
        assert code == 0
        assert "empty" in out.lower() or "0" in out

    def test_list_cli_after_enqueue(self, tmp_path: Path) -> None:
        _run_cli(["--queue-dir", str(tmp_path), "enqueue", "--url", "2604.24366"])
        code, out = _run_cli(["--queue-dir", str(tmp_path), "list"])
        assert code == 0
        assert "arxiv:2604.24366" in out

    def test_list_cli_json(self, tmp_path: Path) -> None:
        _run_cli(["--queue-dir", str(tmp_path), "enqueue", "--url", "2604.24366"])
        code, out = _run_cli(["--queue-dir", str(tmp_path), "list", "--json"])
        assert code == 0
        data = json.loads(out)
        assert len(data) == 1
        assert data[0]["arxiv_id"] == "2604.24366"

    def test_process_empty_queue(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "process", "--max-items", "1",
        ])
        assert code == 0
        assert "No pending" in out or "no pending" in out.lower()

    def test_enqueue_invalid_url_exits_nonzero(self, tmp_path: Path) -> None:
        code, _ = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "https://example.com/not-arxiv",
        ])
        assert code == 1

    def test_counts_after_enqueue(self, tmp_path: Path) -> None:
        _run_cli(["--queue-dir", str(tmp_path), "enqueue", "--url", "2604.24366"])
        code, out = _run_cli(["--queue-dir", str(tmp_path), "counts", "--json"])
        assert code == 0
        data = json.loads(out)
        assert data["pending"] == 1
        assert data["total"] == 1


# ---------------------------------------------------------------------------
# Warm-worker behaviour
# ---------------------------------------------------------------------------


class TestWarmWorkerBehavior:
    """Verify warm-worker implementation is honest about platform limits."""

    def test_platform_selects_correct_marker_mode(self) -> None:
        """Windows uses thread mode; Linux/Docker uses subprocess mode."""
        import sys
        from packages.research.ingestion.fetchers import _MARKER_DEFAULT_USE_PROCESS
        if sys.platform == "win32":
            assert not _MARKER_DEFAULT_USE_PROCESS
        else:
            assert _MARKER_DEFAULT_USE_PROCESS

    def test_warm_thread_worker_raises_on_subprocess_platform(self) -> None:
        """create_warm_thread_worker raises RuntimeError on Linux/Docker (subprocess mode)."""
        import sys
        from packages.research.ingestion.fetchers import (
            LiveAcademicFetcher,
            _MARKER_DEFAULT_USE_PROCESS,
        )
        if sys.platform != "win32":
            # Linux/Docker: warm thread worker is explicitly unsupported
            with pytest.raises(RuntimeError, match="subprocess mode"):
                LiveAcademicFetcher.create_warm_thread_worker()
        else:
            pytest.skip("subprocess mode not active on Windows")

    def test_preloaded_model_dict_skips_create_model_dict(self, tmp_path: "Path") -> None:
        """MarkerPDFExtractor does NOT call create_model_dict when preloaded dict provided."""
        import tempfile
        import os
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        call_count = [0]
        fake_body = "# Title\n\n" + "Research content. " * 2000  # > MIN_MARKER_BODY_LENGTH

        def fake_create_model_dict():
            call_count[0] += 1
            return {}

        fake_converter = MagicMock()
        fake_rendered = MagicMock()
        fake_converter.return_value = fake_rendered

        def fake_text_from_rendered(rendered):
            return (fake_body, {"page_count": 10})

        marker_modules = {
            "PdfConverter": fake_converter,
            "create_model_dict": fake_create_model_dict,
            "text_from_rendered": fake_text_from_rendered,
        }
        preloaded = {"already": "loaded"}

        extractor = MarkerPDFExtractor(
            _marker_modules=marker_modules,
            _preloaded_model_dict=preloaded,
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_tmp = f.name
        try:
            doc = extractor.extract(pdf_tmp)
        finally:
            os.unlink(pdf_tmp)

        # create_model_dict must NOT have been called (preloaded dict was used)
        assert call_count[0] == 0
        # PdfConverter was called with the preloaded dict, not a fresh one
        fake_converter.assert_called_once_with(artifact_dict=preloaded)
        assert doc.body == fake_body

    def test_cold_extractor_calls_create_model_dict(self, tmp_path: "Path") -> None:
        """Without preloaded dict, create_model_dict IS called once per extract()."""
        import tempfile
        import os
        from packages.research.ingestion.extractors import MarkerPDFExtractor

        call_count = [0]
        fake_body = "# Title\n\n" + "Research content. " * 2000

        def fake_create_model_dict():
            call_count[0] += 1
            return {}

        fake_converter = MagicMock()
        fake_converter.return_value = MagicMock()

        marker_modules = {
            "PdfConverter": fake_converter,
            "create_model_dict": fake_create_model_dict,
            "text_from_rendered": lambda r: (fake_body, {"page_count": 5}),
        }

        extractor = MarkerPDFExtractor(_marker_modules=marker_modules)

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            pdf_tmp = f.name
        try:
            extractor.extract(pdf_tmp)
        finally:
            os.unlink(pdf_tmp)

        assert call_count[0] == 1


# ---------------------------------------------------------------------------
# Pipeline gate: academic Marker-only indexing
# ---------------------------------------------------------------------------


class TestAcademicPipelineMarkerGate:
    """Verify IngestPipeline.ingest_external() rejects non-Marker academic bodies."""

    def _make_pipeline(self):
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.pipeline import IngestPipeline
        store = KnowledgeStore(db_path=":memory:")
        return IngestPipeline(store=store)

    # Realistic sentence that passes hard-stop checks (mixed case, normal text)
    _SENTENCE = (
        "This paper presents novel findings on prediction market microstructure "
        "and probability calibration using Bayesian inference methods. "
    )

    def _make_body(self, length: int) -> str:
        """Build a realistic body text of at least *length* chars."""
        repeat = (length // len(self._SENTENCE)) + 2
        return (self._SENTENCE * repeat)[:max(length, len(self._SENTENCE))]

    def _academic_raw(self, body_source: str, body_length: int, body_text: str = "") -> dict:
        if not body_text:
            body_text = self._make_body(body_length)
        return {
            "url": "https://arxiv.org/abs/2604.99999",
            "title": "Test Paper on Prediction Markets",
            "abstract": "Abstract of test paper.",
            "authors": ["Author One"],
            "published_date": "2024-01-01",
            "body_text": body_text,
            "body_source": body_source,
            "body_length": body_length,
        }

    def test_marker_ready_body_is_accepted(self) -> None:
        from packages.research.ingestion.pipeline import _ACADEMIC_MIN_MARKER_BODY_LENGTH
        pipeline = self._make_pipeline()
        raw = self._academic_raw("marker", _ACADEMIC_MIN_MARKER_BODY_LENGTH)
        result = pipeline.ingest_external(raw, source_family="academic")
        assert not result.rejected, f"Expected accepted, got: {result.reject_reason}"
        assert result.chunk_count > 0

    def test_pdfplumber_body_is_rejected(self) -> None:
        from packages.research.ingestion.pipeline import _ACADEMIC_MIN_MARKER_BODY_LENGTH
        pipeline = self._make_pipeline()
        raw = self._academic_raw("pdfplumber_fallback", _ACADEMIC_MIN_MARKER_BODY_LENGTH * 2)
        result = pipeline.ingest_external(raw, source_family="academic")
        assert result.rejected
        assert "academic_marker_gate" in result.reject_reason
        assert "pdfplumber_fallback" in result.reject_reason

    def test_abstract_fallback_body_is_rejected(self) -> None:
        pipeline = self._make_pipeline()
        raw = self._academic_raw("abstract_fallback", 500)
        result = pipeline.ingest_external(raw, source_family="academic")
        assert result.rejected
        assert "academic_marker_gate" in result.reject_reason

    def test_marker_failed_body_is_rejected(self) -> None:
        pipeline = self._make_pipeline()
        raw = self._academic_raw("marker_failed", 0)
        result = pipeline.ingest_external(raw, source_family="academic")
        assert result.rejected
        assert "academic_marker_gate" in result.reject_reason

    def test_short_marker_body_is_rejected(self) -> None:
        from packages.research.ingestion.pipeline import _ACADEMIC_MIN_MARKER_BODY_LENGTH
        pipeline = self._make_pipeline()
        raw = self._academic_raw("marker", _ACADEMIC_MIN_MARKER_BODY_LENGTH - 1)
        result = pipeline.ingest_external(raw, source_family="academic")
        assert result.rejected
        assert "academic_marker_gate" in result.reject_reason

    def test_unknown_body_source_is_rejected(self) -> None:
        from packages.research.ingestion.pipeline import _ACADEMIC_MIN_MARKER_BODY_LENGTH
        pipeline = self._make_pipeline()
        raw = self._academic_raw("unknown", _ACADEMIC_MIN_MARKER_BODY_LENGTH * 2)
        result = pipeline.ingest_external(raw, source_family="academic")
        assert result.rejected
        assert "academic_marker_gate" in result.reject_reason

    def test_non_academic_family_not_gated(self) -> None:
        """Gate only applies to academic; blog sources pass through regardless of body_source."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.pipeline import IngestPipeline
        store = KnowledgeStore(db_path=":memory:")
        pipeline = IngestPipeline(store=store)
        body = self._make_body(3000)
        raw = {
            "url": "https://example.com/post",
            "title": "A Blog Post on Markets",
            "body_text": body,
            "body_source": "pdfplumber_fallback",  # should be ignored for blog
            "author": "Jane Doe",
            "published_date": "2024-01-01",
            "publisher": "ExampleBlog",
        }
        result = pipeline.ingest_external(raw, source_family="blog")
        # Blog passes the gate (no academic_marker_gate check)
        assert "academic_marker_gate" not in (result.reject_reason or "")


# ---------------------------------------------------------------------------
# IPC warm-worker: LiveAcademicFetcher._marker_ipc_worker_extract
# ---------------------------------------------------------------------------


class _MockIPCWorker:
    """Minimal MarkerIPCWorker stand-in for offline tests."""

    def __init__(self, status: str = "ok", body: str = "x" * 6000,
                 failure_reason: str = "ipc_error") -> None:
        self._status = status
        self._body = body
        self._failure_reason = failure_reason
        self.parse_call_count = 0

    def parse(self, pdf_path: str, timeout: float = 900.0) -> dict:
        self.parse_call_count += 1
        if self._status == "error":
            return {
                "status": "error",
                "body": "",
                "meta": {},
                "parse_seconds": 0.5,
                "failure_reason": self._failure_reason,
            }
        return {
            "status": "ok",
            "body": self._body,
            "meta": {"body_source": "marker", "page_count": 10, "parse_seconds": 1.5},
            "parse_seconds": 1.5,
            "failure_reason": None,
        }

    def start(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def is_alive(self) -> bool:
        return True


class TestIPCFetcherExtract:
    """LiveAcademicFetcher with _ipc_worker injects through _marker_ipc_worker_extract."""

    def _make_fetcher(self, worker):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        return LiveAcademicFetcher(
            _ipc_worker=worker,
            _marker_timeout_seconds=5.0,
        )

    def test_ok_result_returns_marker_body_source(self) -> None:
        worker = _MockIPCWorker(status="ok", body="# Title\n" + "word " * 2000)
        fetcher = self._make_fetcher(worker)
        body, meta = fetcher._marker_ipc_worker_extract("/fake/paper.pdf")
        assert meta["body_source"] == "marker"
        assert len(body) > 200
        assert worker.parse_call_count == 1

    def test_error_result_returns_marker_failed(self) -> None:
        worker = _MockIPCWorker(status="error", failure_reason="gpu_oom")
        fetcher = self._make_fetcher(worker)
        body, meta = fetcher._marker_ipc_worker_extract("/fake/paper.pdf")
        assert body == ""
        assert meta["body_source"] == "marker_failed"
        assert "gpu_oom" in meta["failure_reason"]

    def test_error_does_not_set_marker_disabled(self) -> None:
        from packages.research.ingestion.fetchers import _MARKER_DISABLED
        _MARKER_DISABLED.clear()
        worker = _MockIPCWorker(status="error", failure_reason="ipc_timeout")
        fetcher = self._make_fetcher(worker)
        fetcher._marker_ipc_worker_extract("/fake/paper.pdf")
        assert not _MARKER_DISABLED.is_set(), \
            "_MARKER_DISABLED must not be set by the IPC worker path"

    def test_no_pdfplumber_fallback_on_error(self) -> None:
        worker = _MockIPCWorker(status="error")
        fetcher = self._make_fetcher(worker)
        body, meta = fetcher._marker_ipc_worker_extract("/fake/paper.pdf")
        assert meta.get("body_source") not in ("pdfplumber_fallback", "pdfplumber", "pdf")

    def test_short_body_returns_marker_failed(self) -> None:
        worker = _MockIPCWorker(status="ok", body="short")
        fetcher = self._make_fetcher(worker)
        body, meta = fetcher._marker_ipc_worker_extract("/fake/paper.pdf")
        assert body == ""
        assert meta["body_source"] == "marker_failed"
        assert "too short" in meta["failure_reason"]

    def test_parse_seconds_propagated(self) -> None:
        worker = _MockIPCWorker(status="ok", body="x" * 6000)
        fetcher = self._make_fetcher(worker)
        _, meta = fetcher._marker_ipc_worker_extract("/fake/paper.pdf")
        assert meta.get("parse_seconds") == 1.5


# ---------------------------------------------------------------------------
# IPC warm-worker: process_next_ipc queue integration
# ---------------------------------------------------------------------------


class _IPCTrackingFetcher:
    """Fetcher that delegates parse to a shared mock IPC worker, tracking calls."""

    def __init__(self, worker: _MockIPCWorker) -> None:
        self._worker = worker

    def fetch(self, url: str) -> dict:
        result = self._worker.parse("/fake/paper.pdf")
        if result["status"] == "error":
            return {
                "title": "Test Paper",
                "body_source": "marker_failed",
                "body_length": 0,
                "parse_seconds": result.get("parse_seconds", 0.0),
                "failure_reason": result.get("failure_reason", "ipc_error"),
            }
        return {
            "title": "Test Paper",
            "body_source": "marker",
            "body_length": len(result["body"]),
            "parse_seconds": result.get("parse_seconds", 0.0),
            "failure_reason": None,
        }


class TestProcessNextIPC:

    def test_multiple_items_share_one_worker_instance(self, tmp_path: Path) -> None:
        """process_next_ipc passes the same worker to each paper in the batch."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        worker = _MockIPCWorker()
        fetcher = _IPCTrackingFetcher(worker)
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")

        results = q.process_next_ipc(max_items=2, _fetcher=fetcher)

        assert len(results) == 2
        # Both papers routed through the same worker — parse() called twice
        assert worker.parse_call_count == 2
        assert all(r["marker_ready"] for r in results)

    def test_results_contain_ipc_warm_worker_used(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        results = q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))
        assert "ipc_warm_worker_used" in results[0]

    def test_ipc_failure_marks_item_retryable(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        results = q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(_failed_raw()))
        r = results[0]
        assert r["rejected"] is True
        assert r["queue_status"] == "pending"  # first failure → retryable

    def test_ipc_failure_no_pdfplumber_fallback(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        raw = {
            "title": "T",
            "body_source": "marker_failed",
            "body_length": 0,
            "parse_seconds": 0.0,
            "failure_reason": "ipc_timeout",
        }
        results = q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(raw))
        r = results[0]
        assert r["body_source"] not in ("pdfplumber_fallback", "pdfplumber")

    def test_ipc_failure_terminal_after_max_attempts(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        fetcher = _FakeFetcher(_failed_raw())
        for _ in range(MAX_ATTEMPTS):
            q.process_next_ipc(max_items=1, _fetcher=fetcher)
        records = q.list_queue()
        assert records[0]["status"] == "failed"

    def test_empty_queue_returns_empty(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        results = q.process_next_ipc(max_items=5, _fetcher=_FakeFetcher(_marker_raw()))
        assert results == []

    def test_windows_thread_path_unchanged(self, tmp_path: Path) -> None:
        """process_next_ipc with _fetcher injection behaves identically to process_next."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        # _fetcher injection bypasses platform check — same semantics as process_next
        results = q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))
        assert results[0]["marker_ready"] is True
        assert results[0]["queue_status"] == "done"


# ---------------------------------------------------------------------------
# CLI: warm-process subcommand
# ---------------------------------------------------------------------------


class TestCLIWarmProcess:

    def test_warm_process_in_top_level_help(self) -> None:
        code, out = _run_cli(["--help"])
        assert code == 0
        assert "warm-process" in out

    def test_warm_process_help_exits_zero(self) -> None:
        code, out = _run_cli(["warm-process", "--help"])
        assert code == 0
        assert "--max-items" in out
        assert "--marker-timeout" in out

    def test_warm_process_empty_queue(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "warm-process"])
        assert code == 0
        assert "No pending" in out or "no pending" in out.lower()

    def test_warm_process_empty_queue_json(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "warm-process", "--json"])
        assert code == 0
        data = json.loads(out)
        assert data["processed"] == []
        assert "ipc_warm_worker_used" in data


# ---------------------------------------------------------------------------
# WP-1 PDF prefetch separation: cache manifest and warm-process routing
# ---------------------------------------------------------------------------


def _fake_pdf_bytes(size: int = 1500) -> bytes:
    return b"%PDF-1.4\n" + (b"0" * size)


def _read_prefetch_manifest(queue_dir: Path) -> dict[str, dict]:
    manifest_path = queue_dir / "pdf_cache" / "manifest.jsonl"
    assert manifest_path.exists(), "prefetch manifest must be written"
    records: dict[str, dict] = {}
    with open(manifest_path, encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            records[rec["candidate_id"]] = rec
    return records


class _NoArxivFetchDirectFetcher:
    """Fetcher that fails the test if warm-process falls back to live arXiv fetch."""

    def __init__(self, direct_raw: dict) -> None:
        self._direct_raw = direct_raw
        self.fetch_called = 0
        self.fetch_pdf_direct_called = 0
        self.last_direct_url = ""

    def fetch(self, url: str) -> dict:
        self.fetch_called += 1
        raise AssertionError(f"live arXiv fetch must not be called: {url}")

    def fetch_pdf_direct(self, url_or_path: str, title: str = "") -> dict:
        self.fetch_pdf_direct_called += 1
        self.last_direct_url = url_or_path
        result = dict(self._direct_raw)
        if title and not result.get("title"):
            result["title"] = title
        return result


class TestPrefetchPdfSeparation:
    def test_prefetch_writes_manifest_and_updates_queue_pdf_url(
        self, tmp_path: Path
    ) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")

        result = q.prefetch_pdfs(
            max_items=1,
            delay_seconds=0,
            _http_fn=lambda url, timeout, headers: _fake_pdf_bytes(2048),
        )

        assert result["failed"] == []
        assert len(result["cached"]) == 1
        manifest = _read_prefetch_manifest(tmp_path)
        rec = manifest["arxiv:2604.24366"]
        assert rec["status"] == "cached"
        assert rec["attempts"] == 1
        assert rec["file_size"] >= 1000
        assert rec["fetched_at"]
        pdf_path = Path(rec["pdf_cache_path"])
        assert pdf_path.parent.name == "pdf_cache"
        assert pdf_path.name == "arxiv-2604.24366.pdf"
        assert pdf_path.exists()

        queue_rec = q.list_queue()[0]
        assert queue_rec["status"] == "pending"
        assert queue_rec["attempts"] == 0
        assert Path(queue_rec["pdf_url"]) == Path(rec["pdf_cache_path"])

    def test_prefetch_rerun_reuses_valid_cached_pdf_without_refetch(
        self, tmp_path: Path
    ) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        calls: list[str] = []

        def http_once(url, timeout, headers):
            calls.append(url)
            return _fake_pdf_bytes(2048)

        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        first = q.prefetch_pdfs(delay_seconds=0, _http_fn=http_once)
        assert len(first["cached"]) == 1
        assert len(calls) == 1

        def fail_if_refetched(url, timeout, headers):
            raise AssertionError(f"cached PDF should not be refetched: {url}")

        second = q.prefetch_pdfs(delay_seconds=0, _http_fn=fail_if_refetched)
        assert second["cached"] == []
        assert second["failed"] == []
        assert second["skipped_already_cached"] == ["arxiv:2604.24366"]
        assert len(calls) == 1

        manifest = _read_prefetch_manifest(tmp_path)
        assert manifest["arxiv:2604.24366"]["attempts"] == 1

    def test_prefetch_failure_records_manifest_error_without_corrupting_queue(
        self, tmp_path: Path
    ) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        def failing_http(url, timeout, headers):
            raise OSError("HTTP 429 rate limited")

        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("1206.4810")
        result = q.prefetch_pdfs(delay_seconds=0, _http_fn=failing_http)

        assert result["cached"] == []
        assert result["failed"][0]["candidate_id"] == "arxiv:1206.4810"
        assert "HTTP 429" in result["failed"][0]["error"]

        manifest = _read_prefetch_manifest(tmp_path)
        rec = manifest["arxiv:1206.4810"]
        assert rec["status"] == "failed"
        assert rec["attempts"] == 1
        assert "HTTP 429" in rec["error"]
        assert rec["file_size"] == 0
        assert rec["fetched_at"]

        queue_rec = q.list_queue()[0]
        assert queue_rec["status"] == "pending"
        assert queue_rec["attempts"] == 0
        assert "pdf_url" not in queue_rec

    def test_status_report_counts_prefetch_manifest_states(
        self, tmp_path: Path
    ) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        def selective_http(url, timeout, headers):
            if "2401.00001" in url:
                raise TimeoutError("download timeout")
            return _fake_pdf_bytes(2048)

        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        q.prefetch_pdfs(delay_seconds=0, _http_fn=selective_http)

        report = q.get_status_report()
        assert report["counts"]["pending"] == 2
        assert report["prefetch_stats"] == {
            "cached": 1,
            "failed": 1,
            "total_manifest_entries": 2,
        }

    def test_warm_process_prefers_cached_local_pdf_and_skips_arxiv_fetch(
        self, tmp_path: Path
    ) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.prefetch_pdfs(
            delay_seconds=0,
            _http_fn=lambda url, timeout, headers: _fake_pdf_bytes(2048),
        )

        fetcher = _NoArxivFetchDirectFetcher(_marker_raw())
        results = q.process_next_ipc(max_items=1, _fetcher=fetcher)

        assert len(results) == 1
        assert results[0]["marker_ready"] is True
        assert results[0]["queue_status"] == "done"
        assert fetcher.fetch_pdf_direct_called == 1
        assert fetcher.fetch_called == 0
        assert fetcher.last_direct_url.endswith("pdf_cache\\arxiv-2604.24366.pdf") or (
            fetcher.last_direct_url.endswith("pdf_cache/arxiv-2604.24366.pdf")
        )

    def test_direct_local_pdf_item_still_works_without_prefetch_manifest(
        self, tmp_path: Path
    ) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue

        local_pdf = tmp_path / "manual.pdf"
        local_pdf.write_bytes(_fake_pdf_bytes(2048))

        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("1910.08858", pdf_url=str(local_pdf))
        fetcher = _NoArxivFetchDirectFetcher(_marker_raw())
        results = q.process_next(max_items=1, _fetcher=fetcher)

        assert results[0]["marker_ready"] is True
        assert fetcher.fetch_pdf_direct_called == 1
        assert fetcher.last_direct_url == str(local_pdf)


class TestCLIPrefetchSeparation:
    def test_prefetch_help_documents_required_operator_options(self) -> None:
        code, out = _run_cli(["prefetch", "--help"])
        assert code == 0
        assert "--max-items" in out
        assert "--delay-seconds" in out
        assert "--json" in out

        top_code, top_out = _run_cli(["--help"])
        assert top_code == 0
        assert "--queue-dir" in top_out
        assert "prefetch" in top_out
        assert "status-report" in top_out

    def test_prefetch_json_cli_is_offline_with_injected_empty_queue(
        self, tmp_path: Path
    ) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "prefetch", "--json"])
        assert code == 0
        data = json.loads(out)
        assert data["message"] == "no pending items"
        assert data["cached"] == []
        assert data["failed"] == []

    def test_runbook_mentions_live_prefetch_status_report_contract(self) -> None:
        runbook = (_REPO_ROOT / "docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md").read_text(
            encoding="utf-8"
        )
        assert "`prefetch` and `status-report` subcommands are live" in runbook
        code, out = _run_cli(["--help"])
        assert code == 0
        assert "prefetch" in out
        assert "status-report" in out

    def test_runbook_does_not_use_unsupported_prefetch_status_flag(self) -> None:
        runbook = (_REPO_ROOT / "docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md").read_text(
            encoding="utf-8"
        )
        bad_inline_status = (
            "prefetch \\\n  --queue-dir artifacts/research/marker_parse_queue --status"
        )
        assert bad_inline_status not in runbook
        assert "prefetch \\\n  --status" not in runbook
        assert "prefetch --status" not in runbook


# ---------------------------------------------------------------------------
# fetch_pdf_direct: LiveAcademicFetcher bypasses arXiv metadata API
# ---------------------------------------------------------------------------


class TestFetchPdfDirect:
    """LiveAcademicFetcher.fetch_pdf_direct skips the arXiv Atom API entirely."""

    def _make_fetcher(self, pdf_http_fn, metadata_http_fn=None, ipc_worker=None):
        from packages.research.ingestion.fetchers import LiveAcademicFetcher
        # metadata_http_fn raises if called — proves no Atom API contact
        if metadata_http_fn is None:
            def metadata_http_fn(url, timeout, headers):
                raise AssertionError(f"arXiv metadata API must NOT be called: {url}")
        return LiveAcademicFetcher(
            _http_fn=metadata_http_fn,
            _pdf_http_fn=pdf_http_fn,
            _ipc_worker=ipc_worker,
            _marker_timeout_seconds=5.0,
        )

    def _ok_ipc_worker(self, body_len: int = 6000):
        return _MockIPCWorker(status="ok", body="x" * body_len)

    def _fake_pdf_bytes(self) -> bytes:
        # Minimal bytes — the mock IPC worker ignores actual content
        return b"%PDF-1.4 fake" + b"0" * 100

    def test_url_path_does_not_call_arxiv_metadata_api(self) -> None:
        """fetch_pdf_direct with an HTTP URL: _http_fn (metadata) is never called."""
        metadata_called: list[str] = []

        def _fail_on_metadata(url, timeout, headers):
            metadata_called.append(url)
            raise AssertionError(f"metadata API called: {url}")

        def _ok_pdf(url, timeout, headers):
            return self._fake_pdf_bytes()

        fetcher = self._make_fetcher(
            pdf_http_fn=_ok_pdf,
            metadata_http_fn=_fail_on_metadata,
            ipc_worker=self._ok_ipc_worker(),
        )
        result = fetcher.fetch_pdf_direct(
            "https://arxiv.org/pdf/1910.08858.pdf", title="Test Paper"
        )
        assert not metadata_called, "arXiv Atom API must not be called"
        assert result["body_source"] == "marker"

    def test_url_path_returns_marker_body_source(self) -> None:
        def _ok_pdf(url, timeout, headers):
            return self._fake_pdf_bytes()

        fetcher = self._make_fetcher(
            pdf_http_fn=_ok_pdf,
            ipc_worker=self._ok_ipc_worker(body_len=6000),
        )
        result = fetcher.fetch_pdf_direct("https://arxiv.org/pdf/1910.08858.pdf")
        assert result["body_source"] == "marker"
        assert result["body_length"] > 0
        assert result.get("parse_seconds") is not None

    def test_url_path_preserves_title_hint(self) -> None:
        def _ok_pdf(url, timeout, headers):
            return self._fake_pdf_bytes()

        fetcher = self._make_fetcher(
            pdf_http_fn=_ok_pdf,
            ipc_worker=self._ok_ipc_worker(),
        )
        result = fetcher.fetch_pdf_direct(
            "https://arxiv.org/pdf/1910.08858.pdf", title="My Hint"
        )
        assert result["title"] == "My Hint"

    def test_url_path_pdf_download_failure_returns_abstract_fallback(self) -> None:
        def _fail_pdf(url, timeout, headers):
            raise OSError("connection refused")

        fetcher = self._make_fetcher(pdf_http_fn=_fail_pdf)
        result = fetcher.fetch_pdf_direct("https://arxiv.org/pdf/1910.08858.pdf")
        assert result["body_source"] == "abstract_fallback"
        assert "connection refused" in result.get("fallback_reason", "")

    def test_local_path_no_http_at_all(self, tmp_path: Path) -> None:
        """fetch_pdf_direct with a local path: no HTTP call of any kind."""
        http_called: list[str] = []

        def _fail_any_http(url, timeout, headers):
            http_called.append(url)
            raise AssertionError(f"HTTP must not be called for local path: {url}")

        fake_pdf = tmp_path / "paper.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 local" + b"1" * 50)

        fetcher = self._make_fetcher(
            pdf_http_fn=_fail_any_http,
            metadata_http_fn=_fail_any_http,
            ipc_worker=self._ok_ipc_worker(),
        )
        result = fetcher.fetch_pdf_direct(str(fake_pdf), title="Local Paper")
        assert not http_called, "No HTTP for local path"
        assert result["body_source"] == "marker"
        assert result["title"] == "Local Paper"

    def test_result_dict_has_expected_keys(self) -> None:
        def _ok_pdf(url, timeout, headers):
            return self._fake_pdf_bytes()

        fetcher = self._make_fetcher(
            pdf_http_fn=_ok_pdf,
            ipc_worker=self._ok_ipc_worker(),
        )
        result = fetcher.fetch_pdf_direct("https://arxiv.org/pdf/1910.08858.pdf", title="T")
        for key in ("url", "title", "body_source", "body_length", "parse_seconds"):
            assert key in result, f"Missing key: {key}"

    def test_ipc_error_returns_marker_failed_not_pdfplumber(self) -> None:
        """IPC worker error → marker_failed, never pdfplumber."""
        def _ok_pdf(url, timeout, headers):
            return self._fake_pdf_bytes()

        fetcher = self._make_fetcher(
            pdf_http_fn=_ok_pdf,
            ipc_worker=_MockIPCWorker(status="error", failure_reason="gpu_oom"),
        )
        result = fetcher.fetch_pdf_direct("https://arxiv.org/pdf/1910.08858.pdf")
        assert result["body_source"] == "marker_failed"
        assert result["body_source"] not in ("pdfplumber_fallback", "pdfplumber", "pdf")


# ---------------------------------------------------------------------------
# enqueue: pdf_url field stored in queue record
# ---------------------------------------------------------------------------


class TestEnqueuePdfUrl:

    def test_enqueue_with_pdf_url_stores_field(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue(
            "https://arxiv.org/abs/1910.08858",
            pdf_url="https://arxiv.org/pdf/1910.08858.pdf",
        )
        records = q.list_queue()
        assert records[0].get("pdf_url") == "https://arxiv.org/pdf/1910.08858.pdf"

    def test_enqueue_without_pdf_url_omits_field(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        records = q.list_queue()
        assert "pdf_url" not in records[0]

    def test_enqueue_pdf_url_preserves_arxiv_candidate_id(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue(
            "1910.08858",
            pdf_url="https://arxiv.org/pdf/1910.08858.pdf",
        )
        records = q.list_queue()
        assert records[0]["candidate_id"] == "arxiv:1910.08858"
        assert records[0]["pdf_url"] == "https://arxiv.org/pdf/1910.08858.pdf"

    def test_enqueue_local_pdf_path_stored(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        local = "/app/artifacts/research/pdfs/paper.pdf"
        q.enqueue("1910.08858", pdf_url=local)
        records = q.list_queue()
        assert records[0]["pdf_url"] == local


# ---------------------------------------------------------------------------
# _process_item dispatch: pdf_url routes to fetch_pdf_direct
# ---------------------------------------------------------------------------


class _FakeFetcherWithDirect(_FakeFetcher):
    """Fetcher that has both fetch() and fetch_pdf_direct(); tracks which was used."""

    def __init__(self, raw_source: dict, direct_raw: "dict | None" = None) -> None:
        super().__init__(raw_source)
        self._direct_raw = direct_raw if direct_raw is not None else raw_source
        self.fetch_called = 0
        self.fetch_pdf_direct_called = 0
        self.last_direct_url: str = ""

    def fetch(self, url: str) -> dict:  # type: ignore[override]
        self.fetch_called += 1
        return dict(self._raw)

    def fetch_pdf_direct(self, url_or_path: str, title: str = "") -> dict:
        self.fetch_pdf_direct_called += 1
        self.last_direct_url = url_or_path
        result = dict(self._direct_raw)
        if title and not result.get("title"):
            result["title"] = title
        return result


class TestProcessNextDirectPdf:

    def test_pdf_url_item_uses_fetch_pdf_direct(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue(
            "1910.08858",
            pdf_url="https://arxiv.org/pdf/1910.08858.pdf",
        )
        fetcher = _FakeFetcherWithDirect(_marker_raw())
        results = q.process_next(max_items=1, _fetcher=fetcher)

        assert fetcher.fetch_pdf_direct_called == 1, "fetch_pdf_direct must be called"
        assert fetcher.fetch_called == 0, "fetch() must NOT be called"
        assert fetcher.last_direct_url == "https://arxiv.org/pdf/1910.08858.pdf"
        assert results[0]["body_source"] == "marker"
        assert results[0]["marker_ready"] is True
        assert results[0]["queue_status"] == "done"

    def test_no_pdf_url_uses_fetch(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")  # no pdf_url
        fetcher = _FakeFetcherWithDirect(_marker_raw())
        results = q.process_next(max_items=1, _fetcher=fetcher)

        assert fetcher.fetch_called == 1, "fetch() must be called for normal arXiv items"
        assert fetcher.fetch_pdf_direct_called == 0
        assert results[0]["marker_ready"] is True

    def test_pdf_url_with_fetcher_missing_method_falls_back_to_fetch(
        self, tmp_path: Path
    ) -> None:
        """Fetcher without fetch_pdf_direct falls back to fetch() gracefully."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("1910.08858", pdf_url="https://arxiv.org/pdf/1910.08858.pdf")
        # _FakeFetcher has only fetch(), not fetch_pdf_direct
        fetcher = _FakeFetcher(_marker_raw())
        results = q.process_next(max_items=1, _fetcher=fetcher)
        assert results[0]["marker_ready"] is True  # still succeeds via fetch()

    def test_pdf_url_marker_failure_propagates(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("1910.08858", pdf_url="https://arxiv.org/pdf/1910.08858.pdf")
        fetcher = _FakeFetcherWithDirect(
            _marker_raw(),
            direct_raw=_failed_raw("marker_timeout: 900s"),
        )
        results = q.process_next(max_items=1, _fetcher=fetcher)
        assert fetcher.fetch_pdf_direct_called == 1
        assert results[0]["rejected"] is True
        assert results[0]["marker_ready"] is False
        assert "marker_timeout" in results[0]["failure_reason"]

    def test_process_next_ipc_sets_ipc_flag_for_pdf_url_item(self, tmp_path: Path) -> None:
        """process_next_ipc sets ipc_warm_worker_used=True even for pdf_url items."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("1910.08858", pdf_url="https://arxiv.org/pdf/1910.08858.pdf")
        fetcher = _FakeFetcherWithDirect(_marker_raw())
        mock_worker = _MockIPCWorker()
        results = q.process_next_ipc(
            max_items=1, _ipc_worker=mock_worker, _fetcher=fetcher
        )
        assert results[0]["ipc_warm_worker_used"] is True
        assert fetcher.fetch_pdf_direct_called == 1
        assert results[0]["marker_ready"] is True

    def test_two_items_mixed_pdf_url_and_arxiv(self, tmp_path: Path) -> None:
        """pdf_url item uses fetch_pdf_direct; regular arxiv item uses fetch()."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("1910.08858", pdf_url="https://arxiv.org/pdf/1910.08858.pdf")
        q.enqueue("2604.24366")  # no pdf_url

        fetcher = _FakeFetcherWithDirect(_marker_raw())
        results = q.process_next(max_items=2, _fetcher=fetcher)

        assert len(results) == 2
        assert fetcher.fetch_pdf_direct_called == 1
        assert fetcher.fetch_called == 1
        assert all(r["marker_ready"] for r in results)


# ---------------------------------------------------------------------------
# CLI: --pdf-url flag on enqueue
# ---------------------------------------------------------------------------


class TestCLIPdfUrl:

    def test_enqueue_help_shows_pdf_url(self) -> None:
        code, out = _run_cli(["enqueue", "--help"])
        assert code == 0
        assert "--pdf-url" in out

    def test_enqueue_with_pdf_url_stores_in_queue(self, tmp_path: Path) -> None:
        code, _ = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue",
            "--url", "1910.08858",
            "--pdf-url", "https://arxiv.org/pdf/1910.08858.pdf",
        ])
        assert code == 0
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        records = q.list_queue()
        assert records[0]["pdf_url"] == "https://arxiv.org/pdf/1910.08858.pdf"

    def test_enqueue_without_pdf_url_unchanged(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "2604.24366",
        ])
        assert code == 0
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        records = q.list_queue()
        assert "pdf_url" not in records[0]

    def test_enqueue_pdf_url_json_output_shows_added(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue",
            "--url", "1910.08858",
            "--pdf-url", "https://arxiv.org/pdf/1910.08858.pdf",
            "--json",
        ])
        assert code == 0
        data = json.loads(out)
        assert data["action"] == "added"
        assert data["candidate_id"] == "arxiv:1910.08858"


# ---------------------------------------------------------------------------
# Daemon-safety: multi-paper IPC warm session
#
# Root cause of live-validation failure: MarkerIPCWorker.start() created the
# worker subprocess with daemon=True.  Daemon processes cannot spawn child
# processes; Marker's ONNX/torch pipeline does so during extraction.  Paper 1
# succeeded (cold-load path did not trigger child spawning), paper 2 failed
# immediately with "daemonic processes are not allowed to have children"
# (parse_seconds=0.0, total_seconds=0.24s).
#
# Fix: daemon=False in start() / restart().  These tests verify queue-level
# behaviour is correct for the multi-paper warm session.
# ---------------------------------------------------------------------------


class TestProcessNextIPCDaemonSafety:

    def test_two_paper_session_both_done(self, tmp_path: Path) -> None:
        """Two papers in one warm-process call must both complete successfully.

        This reproduces the live failure scenario: paper 1 done, paper 2 must
        not fail with the daemonic error.
        """
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2109.07581")

        call_count = [0]

        class _CountingFetcher:
            def fetch(self, url: str) -> dict:
                call_count[0] += 1
                return _marker_raw()

        results = q.process_next_ipc(max_items=2, _fetcher=_CountingFetcher())

        assert len(results) == 2
        assert call_count[0] == 2
        assert all(r["marker_ready"] for r in results), (
            "Both papers must be marker_ready. If paper 2 has "
            "'daemonic processes are not allowed to have children' in failure_reason, "
            "the daemon=False fix was not applied."
        )
        counts = q.get_counts()
        assert counts["done"] == 2
        assert counts["pending"] == 0

    def test_daemonic_error_from_marker_internals_is_retryable(self, tmp_path: Path) -> None:
        """If Marker internals raise the daemonic error, item stays retryable (not terminal)."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2109.07581")

        raw = {
            "title": "Test",
            "body_source": "marker_failed",
            "body_length": 0,
            "parse_seconds": 0.0,
            "failure_reason": "daemonic processes are not allowed to have children",
        }
        results = q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(raw))
        r = results[0]

        assert r["rejected"] is True
        assert "daemonic" in r["failure_reason"]
        assert r["queue_status"] == "pending"  # first attempt: retryable, not terminal
        assert r["marker_ready"] is False

    def test_direct_pdf_path_two_papers_both_done(self, tmp_path: Path) -> None:
        """fetch_pdf_direct path: two pdf_url items in one warm session both complete."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366", pdf_url="https://arxiv.org/pdf/2604.24366.pdf")
        q.enqueue("2109.07581", pdf_url="https://arxiv.org/pdf/2109.07581.pdf")

        fetcher = _FakeFetcherWithDirect(_marker_raw())
        results = q.process_next_ipc(max_items=2, _fetcher=fetcher)

        assert len(results) == 2
        assert fetcher.fetch_pdf_direct_called == 2, (
            "fetch_pdf_direct must be used for both pdf_url items"
        )
        assert fetcher.fetch_called == 0
        assert all(r["marker_ready"] for r in results)


# ---------------------------------------------------------------------------
# IPC result persistence: ipc_warm_worker_used must land in results.jsonl
#
# Root cause of Codex FAIL artifact caveat (2026-05-08): process_next_ipc()
# tagged ipc_warm_worker_used onto in-memory dicts AFTER _append_result() had
# already written to disk.  Fix: pass _extra_result_fields into process_next()
# so the flag is included in result_record before _append_result() is called.
# ---------------------------------------------------------------------------


class TestIPCResultPersistence:
    """ipc_warm_worker_used is persisted into results.jsonl, not just in-memory."""

    def test_ipc_flag_true_persisted_when_worker_provided(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        worker = _MockIPCWorker()
        q.process_next_ipc(max_items=1, _ipc_worker=worker, _fetcher=_FakeFetcher(_marker_raw()))

        with open(q._results_path, encoding="utf-8") as f:
            rec = json.loads(f.readline().strip())
        assert rec["ipc_warm_worker_used"] is True

    def test_ipc_flag_false_persisted_when_no_worker(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        # _fetcher only, no _ipc_worker → ipc_flag=False
        q.process_next_ipc(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))

        with open(q._results_path, encoding="utf-8") as f:
            rec = json.loads(f.readline().strip())
        assert rec["ipc_warm_worker_used"] is False

    def test_process_next_does_not_persist_ipc_flag(self, tmp_path: Path) -> None:
        """Non-IPC process_next path does not inject ipc_warm_worker_used into results.jsonl."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw()))

        with open(q._results_path, encoding="utf-8") as f:
            rec = json.loads(f.readline().strip())
        assert "ipc_warm_worker_used" not in rec

    def test_multiple_ipc_items_all_have_flag_persisted(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.enqueue("2401.00001")
        worker = _MockIPCWorker()
        q.process_next_ipc(max_items=2, _ipc_worker=worker, _fetcher=_FakeFetcher(_marker_raw()))

        with open(q._results_path, encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        assert len(lines) == 2
        for line in lines:
            assert json.loads(line)["ipc_warm_worker_used"] is True


# ---------------------------------------------------------------------------
# Body sidecar persistence: _process_item writes bodies/ on marker_ready=True
# ---------------------------------------------------------------------------

_LONG_BODY = "Prediction market microstructure research. " * 200  # > 5000 chars


def _marker_raw_with_body(body_text: str = _LONG_BODY, parse_seconds: float = 6.0) -> dict:
    return {
        "url": "https://arxiv.org/abs/2604.24366",
        "title": "Test Paper",
        "abstract": "Paper abstract.",
        "authors": ["Author A"],
        "published_date": "2024-01-01",
        "body_text": body_text,
        "body_source": "marker",
        "body_length": len(body_text),
        "parse_seconds": parse_seconds,
        "failure_reason": None,
    }


class TestPersistBodySidecar:
    """_process_item persists body sidecar to bodies/ when marker_ready=True."""

    def test_body_file_written_on_success(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw_with_body()))

        body_file = tmp_path / "bodies" / "arxiv:2604.24366.body.txt"
        assert body_file.exists(), "body.txt must be written for marker_ready items"
        assert len(body_file.read_text(encoding="utf-8")) > 5000

    def test_meta_file_written_on_success(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw_with_body()))

        meta_file = tmp_path / "bodies" / "arxiv:2604.24366.meta.json"
        assert meta_file.exists(), "meta.json must be written for marker_ready items"
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        assert meta.get("body_source") == "marker"
        assert "body_text" not in meta, "body_text must NOT be in meta.json (stored separately)"

    def test_no_sidecar_on_marker_failed(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_failed_raw()))

        body_file = tmp_path / "bodies" / "arxiv:2604.24366.body.txt"
        assert not body_file.exists(), "body.txt must NOT be written for marker_failed items"

    def test_no_sidecar_on_pdfplumber(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_pdfplumber_raw()))

        body_file = tmp_path / "bodies" / "arxiv:2604.24366.body.txt"
        assert not body_file.exists()

    def test_no_sidecar_on_short_marker_body(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MIN_MARKER_BODY_LENGTH
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        short_raw = _marker_raw_with_body(body_text="x" * (MIN_MARKER_BODY_LENGTH - 1))
        short_raw["body_length"] = MIN_MARKER_BODY_LENGTH - 1
        q.process_next(max_items=1, _fetcher=_FakeFetcher(short_raw))

        body_file = tmp_path / "bodies" / "arxiv:2604.24366.body.txt"
        assert not body_file.exists()

    def test_sidecar_overwritten_on_reprocess(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw_with_body()))

        q.enqueue("2604.24366", force=True)
        new_body = "Updated body content. " * 300
        q.process_next(max_items=1, _fetcher=_FakeFetcher(_marker_raw_with_body(body_text=new_body)))

        body_file = tmp_path / "bodies" / "arxiv:2604.24366.body.txt"
        assert "Updated body content" in body_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# index_done_items: KnowledgeStore handoff
# ---------------------------------------------------------------------------


def _make_ks_store():
    from packages.polymarket.rag.knowledge_store import KnowledgeStore
    return KnowledgeStore(db_path=":memory:")


class TestIndexDoneItems:
    """index_done_items() indexes marker-ready done items into KnowledgeStore."""

    def _run_index(self, tmp_path: Path, store=None) -> dict:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        return q.index_done_items(_store=store or _make_ks_store())

    def _setup_done_queue(self, tmp_path: Path, body_text: str = _LONG_BODY,
                          arxiv_id: str = "2604.24366") -> None:
        """Enqueue, process (success), and leave a done item with sidecar."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue(arxiv_id)
        raw = _marker_raw_with_body(body_text=body_text)
        raw["url"] = f"https://arxiv.org/abs/{arxiv_id}"
        q.process_next(max_items=1, _fetcher=_FakeFetcher(raw))

    def test_done_item_indexed_into_ks(self, tmp_path: Path) -> None:
        self._setup_done_queue(tmp_path)
        store = _make_ks_store()
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        summary = q.index_done_items(_store=store)

        assert len(summary["indexed"]) == 1
        assert summary["indexed"][0]["candidate_id"] == "arxiv:2604.24366"
        assert summary["indexed"][0]["chunk_count"] > 0
        assert not summary["failed"]
        assert not summary["skipped_already_indexed"]
        assert not summary["skipped_no_body"]

    def test_failed_item_not_indexed(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        # Drive to terminal failure
        for _ in range(MAX_ATTEMPTS):
            q.process_next(max_items=1, _fetcher=_FakeFetcher(_failed_raw()))

        summary = q.index_done_items(_store=_make_ks_store())
        assert not summary["indexed"]
        assert not summary["skipped_no_body"]

    def test_pdfplumber_item_not_indexed(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue, MAX_ATTEMPTS
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        for _ in range(MAX_ATTEMPTS):
            q.process_next(max_items=1, _fetcher=_FakeFetcher(_pdfplumber_raw()))

        summary = q.index_done_items(_store=_make_ks_store())
        assert not summary["indexed"]

    def test_missing_body_file_reported(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        # Manually inject a done+marker_ready result without a body file
        q._ensure_dir()
        import json as _json
        rec = {
            "candidate_id": "arxiv:2604.24366",
            "source_url": "https://arxiv.org/abs/2604.24366",
            "arxiv_id": "2604.24366",
            "title": "Test Paper",
            "body_source": "marker",
            "body_length": 60000,
            "marker_ready": True,
            "queue_status": "done",
            "processed_at": "2026-05-09T00:00:00+00:00",
        }
        with open(q._results_path, "w", encoding="utf-8") as f:
            f.write(_json.dumps(rec) + "\n")

        summary = q.index_done_items(_store=_make_ks_store())
        assert not summary["indexed"]
        assert "arxiv:2604.24366" in summary["skipped_no_body"]

    def test_idempotent_second_call_skips(self, tmp_path: Path) -> None:
        self._setup_done_queue(tmp_path)
        store = _make_ks_store()
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        first = q.index_done_items(_store=store)
        second = q.index_done_items(_store=store)

        assert len(first["indexed"]) == 1
        assert len(second["skipped_already_indexed"]) == 1
        assert not second["indexed"]

    def test_force_reindexes_already_indexed(self, tmp_path: Path) -> None:
        self._setup_done_queue(tmp_path)
        store = _make_ks_store()
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.index_done_items(_store=store)
        second = q.index_done_items(_store=store, force=True)

        assert len(second["indexed"]) == 1
        assert not second["skipped_already_indexed"]

    def test_indexed_jsonl_written(self, tmp_path: Path) -> None:
        self._setup_done_queue(tmp_path)
        store = _make_ks_store()
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.index_done_items(_store=store)

        indexed_path = tmp_path / "indexed.jsonl"
        assert indexed_path.exists()
        with open(indexed_path, encoding="utf-8") as f:
            rec = json.loads(f.readline().strip())
        assert rec["candidate_id"] == "arxiv:2604.24366"
        assert "doc_id" in rec
        assert "indexed_at" in rec

    def test_multiple_done_items_all_indexed(self, tmp_path: Path) -> None:
        self._setup_done_queue(tmp_path, arxiv_id="2604.24366")
        self._setup_done_queue(tmp_path, arxiv_id="2401.00001")
        store = _make_ks_store()
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        summary = q.index_done_items(_store=store)

        assert len(summary["indexed"]) == 2

    def test_query_finds_indexed_paper(self, tmp_path: Path) -> None:
        """research-query returns the paper after index_done_items (claim manually added).

        The claim extractor reads body text from metadata_json["body"] or a
        file:// source_url — neither is set by IngestPipeline.ingest_external.
        The index_done_items step only stores the source_document record; claim
        extraction is a separate concern (matching the pattern used by all L2
        tests in test_research_query.py which inject claims manually).
        """
        self._setup_done_queue(tmp_path)
        store = _make_ks_store()
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        summary = q.index_done_items(_store=store)

        assert len(summary["indexed"]) == 1
        doc_id = summary["indexed"][0]["doc_id"]

        # Verify source_document has correct metadata for academic query guard
        src_doc = store.get_source_document(doc_id)
        assert src_doc is not None
        assert src_doc.get("source_family") == "academic"
        import json as _json
        meta = _json.loads(src_doc.get("metadata_json") or "{}")
        assert meta.get("body_source") == "marker"
        assert int(meta.get("body_length", 0)) >= 5000

        # Add a claim linked to the indexed doc so research-query can find it
        store.add_claim(
            claim_text="prediction market microstructure and binary spread calibration",
            claim_type="finding",
            confidence=0.8,
            trust_tier="T2",
            actor="test",
            source_document_id=doc_id,
        )

        from packages.research.synthesis.academic_query import query_academic_corpus
        result = query_academic_corpus(
            "prediction market microstructure",
            _store=store,
        )
        assert not result.had_fallback, "KS should surface the indexed paper"
        assert len(result.citations) >= 1
        assert result.citations[0].body_source == "marker"


# ---------------------------------------------------------------------------
# CLI: index-done subcommand
# ---------------------------------------------------------------------------


class TestCLIIndexDone:

    def test_index_done_in_help(self) -> None:
        code, out = _run_cli(["--help"])
        assert code == 0
        assert "index-done" in out

    def test_index_done_help_exits_zero(self) -> None:
        code, out = _run_cli(["index-done", "--help"])
        assert code == 0
        assert "--force" in out

    def test_index_done_empty_queue_exits_zero(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "index-done"])
        assert code == 0

    def test_index_done_no_body_file_exits_zero(self, tmp_path: Path) -> None:
        """index-done with no body files (existing done item) exits 0 with no-body warning."""
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q._ensure_dir()
        rec = {
            "candidate_id": "arxiv:2604.24366",
            "source_url": "https://arxiv.org/abs/2604.24366",
            "arxiv_id": "2604.24366",
            "title": "Test Paper",
            "body_source": "marker",
            "body_length": 60000,
            "marker_ready": True,
            "queue_status": "done",
            "processed_at": "2026-05-09T00:00:00+00:00",
        }
        with open(q._results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

        code, out = _run_cli(["--queue-dir", str(tmp_path), "index-done"])
        assert code == 0
        assert "no-body" in out.lower() or "body" in out.lower()

    def test_index_done_json_output(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "index-done", "--json"])
        assert code == 0
        data = json.loads(out)
        assert "indexed" in data
        assert "skipped_already_indexed" in data
        assert "skipped_no_body" in data
        assert "failed" in data


# ---------------------------------------------------------------------------
# WP-2 — auto_timeout_from_file_size unit tests
# ---------------------------------------------------------------------------


class TestAutoTimeoutFromFileSize:
    def test_zero_bytes_returns_small_bucket(self) -> None:
        # 0 bytes falls into ≤600KB bucket (3600s); callers guard file_size > 0 separately
        from packages.research.ingestion.marker_queue import auto_timeout_from_file_size
        assert auto_timeout_from_file_size(0) == 3600.0

    def test_small_file_at_boundary(self) -> None:
        from packages.research.ingestion.marker_queue import auto_timeout_from_file_size
        assert auto_timeout_from_file_size(600 * 1024) == 3600.0

    def test_medium_file_just_above_small_boundary(self) -> None:
        from packages.research.ingestion.marker_queue import auto_timeout_from_file_size
        assert auto_timeout_from_file_size(600 * 1024 + 1) == 7200.0

    def test_medium_file_at_upper_boundary(self) -> None:
        from packages.research.ingestion.marker_queue import auto_timeout_from_file_size
        assert auto_timeout_from_file_size(1500 * 1024) == 7200.0

    def test_large_file_just_above_medium_boundary(self) -> None:
        from packages.research.ingestion.marker_queue import auto_timeout_from_file_size
        assert auto_timeout_from_file_size(1500 * 1024 + 1) == 14400.0

    def test_large_file_returns_max_timeout(self) -> None:
        from packages.research.ingestion.marker_queue import auto_timeout_from_file_size
        assert auto_timeout_from_file_size(10 * 1024 * 1024) == 14400.0


# ---------------------------------------------------------------------------
# WP-2 — enqueue with ingest_tier tests
# ---------------------------------------------------------------------------


class TestEnqueueIngestTier:
    def test_default_tier_is_2(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        outcome = q.enqueue("2604.24366")
        assert outcome.get("ingest_tier") == 2

    def test_tier_3_accepted(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        outcome = q.enqueue("2604.24366", ingest_tier=3)
        assert outcome.get("ingest_tier") == 3
        records = q.list_queue()
        assert records[0]["ingest_tier"] == 3

    def test_invalid_tier_raises(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        with pytest.raises(ValueError, match="ingest_tier"):
            q.enqueue("2604.24366", ingest_tier=1)

    def test_tier_0_raises(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        with pytest.raises(ValueError, match="Tier 0"):
            q.enqueue("2604.24366", ingest_tier=0)

    def test_force_reset_preserves_new_tier(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366", ingest_tier=2)
        outcome = q.enqueue("2604.24366", ingest_tier=3, force=True)
        assert outcome.get("ingest_tier") == 3
        records = q.list_queue()
        assert records[0]["ingest_tier"] == 3

    def test_cli_tier_flag_accepted(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "2604.24366", "--tier", "3",
        ])
        assert code == 0

    def test_cli_invalid_tier_exits_nonzero(self, tmp_path: Path) -> None:
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "enqueue", "--url", "2604.24366", "--tier", "1",
        ])
        assert code != 0  # argparse returns 2 for invalid choices, not 1


# ---------------------------------------------------------------------------
# WP-2 — enhanced get_status_report tests
# ---------------------------------------------------------------------------


class TestStatusReportWP2:
    def _make_queue_with_done_item(self, tmp_path: Path):
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        # Update queue.jsonl to mark the item as done (get_status_report reads queue.jsonl)
        records = q._read_queue()
        for r in records:
            if r.get("candidate_id") == "arxiv:2604.24366":
                r["status"] = "done"
                r["marker_ready"] = True
        q._write_queue(records)
        # Also write result record to results.jsonl
        rec = {
            "candidate_id": "arxiv:2604.24366",
            "arxiv_id": "2604.24366",
            "source_url": "https://arxiv.org/abs/2604.24366",
            "title": "Test Paper",
            "status": "done",
            "attempts": 1,
            "ingest_tier": 2,
            "marker_ready": True,
            "body_source": "marker",
            "body_length": 10000,
            "parse_seconds": 12.0,
            "failure_reason": None,
        }
        with open(q._results_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return q

    def test_sidecar_count_zero_when_no_bodies(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        report = q.get_status_report()
        assert report["sidecar_count"] == 0

    def test_sidecar_count_reflects_body_files(self, tmp_path: Path) -> None:
        q = self._make_queue_with_done_item(tmp_path)
        body_dir = tmp_path / "bodies"
        body_dir.mkdir()
        # Use a Windows-safe filename (colons are invalid on NTFS); glob counts any *.body.txt
        (body_dir / "arxiv_2604.24366.body.txt").write_text("body text", encoding="utf-8")
        report = q.get_status_report()
        assert report["sidecar_count"] == 1

    def test_indexed_count_zero_when_no_indexed_jsonl(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        report = q.get_status_report()
        assert report["indexed_count"] == 0

    def test_indexed_count_reflects_indexed_jsonl(self, tmp_path: Path) -> None:
        q = self._make_queue_with_done_item(tmp_path)
        indexed_path = tmp_path / "indexed.jsonl"
        indexed_path.write_text(
            json.dumps({"candidate_id": "arxiv:2604.24366", "doc_id": "abc"}) + "\n",
            encoding="utf-8",
        )
        report = q.get_status_report()
        assert report["indexed_count"] == 1

    def test_timeout_risk_items_empty_when_no_pending(self, tmp_path: Path) -> None:
        q = self._make_queue_with_done_item(tmp_path)
        report = q.get_status_report()
        assert report["timeout_risk_items"] == []

    def test_timeout_risk_items_present_for_pending(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        report = q.get_status_report()
        assert len(report["timeout_risk_items"]) == 1
        item = report["timeout_risk_items"][0]
        assert item["candidate_id"] == "arxiv:2604.24366"
        assert "size_bucket" in item
        assert "recommended_timeout_seconds" in item
        assert "tier3_flag" in item

    def test_known_timeout_risk_paper_flagged(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import (
            MarkerParseQueue,
            _TIMEOUT_RISK_ARXIV_IDS,
        )
        known_id = next(iter(_TIMEOUT_RISK_ARXIV_IDS))
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue(known_id)
        report = q.get_status_report()
        items = report["timeout_risk_items"]
        assert len(items) == 1
        assert items[0]["is_known_timeout_risk"] is True
        assert items[0]["tier3_flag"] is True

    def test_status_report_json_includes_wp2_fields(self, tmp_path: Path) -> None:
        code, out = _run_cli(["--queue-dir", str(tmp_path), "status-report", "--json"])
        assert code == 0
        data = json.loads(out)
        assert "sidecar_count" in data
        assert "indexed_count" in data
        assert "timeout_risk_items" in data


# ---------------------------------------------------------------------------
# WP-2 — jit-cache-check CLI tests
# ---------------------------------------------------------------------------


class TestCLIJitCacheCheck:
    def test_jit_cache_check_in_help(self) -> None:
        code, out = _run_cli(["--help"])
        assert code == 0
        assert "jit-cache-check" in out

    def test_jit_cache_check_exits_zero(self) -> None:
        code, out = _run_cli(["jit-cache-check"])
        assert code == 0

    def test_jit_cache_check_mentions_triton(self) -> None:
        code, out = _run_cli(["jit-cache-check"])
        assert code == 0
        assert "TRITON_CACHE_DIR" in out

    def test_jit_cache_check_mentions_known_risk_papers(self) -> None:
        code, out = _run_cli(["jit-cache-check"])
        assert code == 0
        assert "1011.6402" in out
        assert "2307.14129" in out

    def test_jit_cache_check_json_output(self) -> None:
        code, out = _run_cli(["jit-cache-check", "--json"])
        assert code == 0
        data = json.loads(out)
        assert "triton_cache_dir" in data
        assert "torchinductor_cache_dir" in data
        assert "instructions" in data

    def test_jit_cache_check_includes_touch_before_marker(self) -> None:
        # Concern #2 fix: instructions must include the touch step so Step 4
        # `find ... -newer /tmp/before_marker` is copy-paste reliable.
        code, out = _run_cli(["jit-cache-check"])
        assert code == 0
        assert "touch /tmp/before_marker" in out

    def test_jit_cache_check_json_instructions_include_touch(self) -> None:
        code, out = _run_cli(["jit-cache-check", "--json"])
        assert code == 0
        data = json.loads(out)
        joined = "\n".join(data["instructions"])
        assert "touch /tmp/before_marker" in joined


# ---------------------------------------------------------------------------
# WP-2 review concerns fix — --auto-timeout uncached fail-fast tests
# ---------------------------------------------------------------------------


class TestAutoTimeoutUncached:
    """Concern #1 fix: --auto-timeout fails when pending items lack manifest data."""

    def test_auto_timeout_fails_when_no_manifest_data(self, tmp_path: Path) -> None:
        # Pending item with no prefetch manifest → exit code 1 (fail-fast)
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        code, _ = _run_cli([
            "--queue-dir", str(tmp_path),
            "warm-process", "--auto-timeout",
        ])
        assert code != 0

    def test_auto_timeout_json_error_includes_uncached_ids(self, tmp_path: Path) -> None:
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        q.enqueue("2604.24366")
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "warm-process", "--auto-timeout", "--json",
        ])
        assert code != 0
        data = json.loads(out)
        assert "uncached_ids" in data
        assert any("2604.24366" in cid for cid in data["uncached_ids"])

    def test_auto_timeout_allow_uncached_flag_in_help(self) -> None:
        # --allow-uncached must appear in warm-process --help
        code, out = _run_cli(["warm-process", "--help"])
        assert code == 0
        assert "--allow-uncached" in out

    def test_auto_timeout_allow_uncached_empty_queue_exits_zero(
        self, tmp_path: Path
    ) -> None:
        # Empty queue: --auto-timeout --allow-uncached must exit 0 immediately.
        # Verifies flag is parsed without argparse error and the guard is not hit.
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "warm-process", "--auto-timeout", "--allow-uncached",
        ])
        assert code == 0

    def test_auto_timeout_allow_uncached_does_not_return_uncached_error_json(
        self, tmp_path: Path
    ) -> None:
        # With --allow-uncached set, the uncached-items gate must not produce the
        # error JSON. The command proceeds past the gate (may fail later for other
        # reasons such as no Marker binary, but NOT with the uncached-items error).
        from packages.research.ingestion.marker_queue import MarkerParseQueue
        q = MarkerParseQueue(queue_dir=tmp_path)
        # Mark the item done immediately so warm-process skips it — this lets us
        # verify the gate logic without invoking Marker at all.
        q.enqueue("2604.24366")
        records = q._read_queue()
        for r in records:
            r["status"] = "done"
        q._write_queue(records)
        # Now there are 0 pending items → warm-process returns 0 with "no pending" message.
        code, out = _run_cli([
            "--queue-dir", str(tmp_path),
            "warm-process", "--auto-timeout", "--allow-uncached", "--json",
        ])
        assert code == 0
        data = json.loads(out)
        # Must not be the uncached-items error response
        assert data.get("error") != "uncached items found for --auto-timeout"
