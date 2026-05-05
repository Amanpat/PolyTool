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

import pytest


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
        # marker output but too short for RAG
        assert r["marker_ready"] is False
        # Note: the fetcher returned "marker" source so rejected=False, queue=done
        assert r["rejected"] is False
        assert r["queue_status"] == "done"


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
