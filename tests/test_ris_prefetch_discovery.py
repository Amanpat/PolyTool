"""Tests for L3.2 Prefetch Label Discovery Mode.

All tests are offline and deterministic.  The arXiv HTTP call is replaced with
a _http_fn fixture that returns pre-built Atom XML.  No network calls, no PDF
downloads, no Marker, no ingestion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from tools.cli.research_prefetch_discover import (
    arxiv_search_metadata_only,
    main,
    _parse_decision_filter,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ATOM_HEADER = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
)
_ATOM_FOOTER = "</feed>"


def _atom_entry(
    arxiv_id: str,
    title: str,
    summary: str,
    author: str = "Test Author",
    published: str = "2024-01-15T00:00:00Z",
) -> str:
    return (
        f"<entry>"
        f"<id>http://arxiv.org/abs/{arxiv_id}v1</id>"
        f"<title>{title}</title>"
        f"<summary>{summary}</summary>"
        f"<author><name>{author}</name></author>"
        f"<published>{published}</published>"
        f"</entry>"
    )


def _make_atom_xml(*entries: str) -> bytes:
    return (_ATOM_HEADER + "".join(entries) + _ATOM_FOOTER).encode("utf-8")


# Three papers that hit different decision buckets with the real v1.1 config:
#   ALLOW  : prediction market + avellaneda-stoikov (two strong_positive = raw 4.0)
#   REVIEW : trading strategy alone (+1, sigmoid=0.731 < 0.80)
#   REJECT : hastelloy + slm fabricated + fatigue life (three strong_negative = raw -9)
_ENTRY_ALLOW = _atom_entry(
    "2401.00001",
    "Prediction Market Microstructure and Avellaneda-Stoikov Optimal Quoting",
    "We derive optimal quoting strategies in prediction markets using the Avellaneda-Stoikov "
    "framework for limit order book dynamics.",
)
_ENTRY_REVIEW = _atom_entry(
    "2401.00002",
    "A Novel Trading Strategy for Binary Options",
    "We propose a trading strategy for binary options with improved risk characteristics.",
)
_ENTRY_REJECT = _atom_entry(
    "2401.00003",
    "Hastelloy SLM Fabricated Fatigue Life Prediction",
    "We study hastelloy alloy fatigue life under SLM fabricated conditions.",
)

_THREE_PAPER_XML = _make_atom_xml(_ENTRY_ALLOW, _ENTRY_REVIEW, _ENTRY_REJECT)
_EMPTY_XML = _make_atom_xml()  # zero entries


def _make_http_fn(xml_bytes: bytes) -> Callable:
    """Return an injectable HTTP function that always returns xml_bytes."""
    calls: list[str] = []

    def _fn(url: str, timeout: int) -> bytes:
        calls.append(url)
        return xml_bytes

    _fn.calls = calls  # type: ignore[attr-defined]
    return _fn


def _write_filter_config(tmp_path: Path) -> Path:
    """Write a minimal deterministic filter config to tmp_path."""
    cfg = {
        "version": "test-v1",
        "strong_positive_weight": 2.0,
        "positive_weight": 1.0,
        "strong_negative_weight": -3.0,
        "negative_weight": -1.5,
        "allow_threshold": 0.80,
        "review_threshold": 0.35,
        "strong_positive_terms": ["prediction market", "avellaneda-stoikov"],
        "positive_terms": ["trading strategy", "liquidity"],
        "strong_negative_terms": ["hastelloy", "slm fabricated", "fatigue life"],
        "negative_terms": ["e-commerce"],
    }
    path = tmp_path / "filter_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestArxivSearchMetadataOnly
# ---------------------------------------------------------------------------


class TestArxivSearchMetadataOnly:
    """Unit tests for the standalone metadata-only search function."""

    def test_parses_three_entries(self):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        results = arxiv_search_metadata_only("test query", _http_fn=http_fn)
        assert len(results) == 3

    def test_canonical_url_extracted(self):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        results = arxiv_search_metadata_only("test query", _http_fn=http_fn)
        assert results[0]["url"] == "https://arxiv.org/abs/2401.00001"
        assert results[1]["url"] == "https://arxiv.org/abs/2401.00002"
        assert results[2]["url"] == "https://arxiv.org/abs/2401.00003"

    def test_title_and_abstract_populated(self):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        results = arxiv_search_metadata_only("test query", _http_fn=http_fn)
        assert "Prediction Market" in results[0]["title"]
        assert "avellaneda-stoikov" in results[0]["abstract"].lower()

    def test_published_date_extracted(self):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        results = arxiv_search_metadata_only("test query", _http_fn=http_fn)
        assert results[0]["published_date"] == "2024-01-15"

    def test_author_extracted(self):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        results = arxiv_search_metadata_only("test query", _http_fn=http_fn)
        assert results[0]["authors"] == ["Test Author"]

    def test_empty_feed_returns_empty_list(self):
        http_fn = _make_http_fn(_EMPTY_XML)
        results = arxiv_search_metadata_only("test query", _http_fn=http_fn)
        assert results == []

    def test_no_pdf_url_called(self):
        """The HTTP function must ONLY be called for the Atom API, never for a PDF URL."""
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        arxiv_search_metadata_only("test query", _http_fn=http_fn)
        for url in http_fn.calls:  # type: ignore[attr-defined]
            assert ".pdf" not in url, f"PDF URL was called: {url}"
            assert "arxiv.org/pdf" not in url, f"PDF URL was called: {url}"

    def test_network_error_raises_runtime_error(self):
        def _fail(url, timeout):
            raise RuntimeError("Network failure")

        with pytest.raises(RuntimeError, match="Network failure"):
            arxiv_search_metadata_only("test", _http_fn=_fail)

    def test_malformed_xml_raises_runtime_error(self):
        def _bad_xml(url, timeout):
            return b"<not valid xml <<<"

        with pytest.raises(RuntimeError):
            arxiv_search_metadata_only("test", _http_fn=_bad_xml)

    def test_api_url_includes_query(self):
        """The API URL must include the search query."""
        http_fn = _make_http_fn(_EMPTY_XML)
        arxiv_search_metadata_only("prediction markets", _http_fn=http_fn)
        assert any(
            "prediction+markets" in url or "prediction%20markets" in url
            for url in http_fn.calls  # type: ignore[attr-defined]
        ), "Search query not found in API URL"

    def test_max_results_in_url(self):
        """max_results is passed through to the API URL."""
        http_fn = _make_http_fn(_EMPTY_XML)
        arxiv_search_metadata_only("test", max_results=7, _http_fn=http_fn)
        assert any("max_results=7" in url for url in http_fn.calls)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# TestParseDecisionFilter
# ---------------------------------------------------------------------------


class TestParseDecisionFilter:
    def test_review_only(self):
        assert _parse_decision_filter("review") == {"review"}

    def test_allow_only(self):
        assert _parse_decision_filter("allow") == {"allow"}

    def test_reject_only(self):
        assert _parse_decision_filter("reject") == {"reject"}

    def test_all(self):
        assert _parse_decision_filter("all") == {"allow", "review", "reject"}

    def test_comma_separated(self):
        assert _parse_decision_filter("allow,review") == {"allow", "review"}

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown decision"):
            _parse_decision_filter("unknown")

    def test_mixed_valid_and_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_decision_filter("review,bogus")


# ---------------------------------------------------------------------------
# TestDiscoverMainDefaultBehavior
# ---------------------------------------------------------------------------


class TestDiscoverMainDefaultBehavior:
    """Default mode: only REVIEW candidates are queued."""

    def test_review_candidate_queued_by_default(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        q = ReviewQueueStore(queue_path)
        records = q.all_records()
        # Only REVIEW should be queued by default
        decisions = {r["decision"] for r in records}
        assert decisions == {"review"}
        assert len(records) == 1

    def test_allow_not_queued_by_default(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        titles = {r["title"] for r in records}
        assert not any("Prediction Market" in t for t in titles), \
            "ALLOW candidate should not be queued by default"

    def test_reject_not_queued_by_default(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        titles = {r["title"] for r in records}
        assert not any("Hastelloy" in t for t in titles), \
            "REJECT candidate should not be queued by default"

    def test_queue_record_has_required_fields(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "prediction markets",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        assert len(records) >= 1
        rec = records[0]
        required = {
            "candidate_id", "source_url", "title", "abstract", "score",
            "raw_score", "decision", "reason_codes", "matched_terms",
            "allow_threshold", "review_threshold", "config_version",
            "created_at", "discovery_query", "source_family",
        }
        for field in required:
            assert field in rec, f"Missing field: {field}"

    def test_discovery_query_stored_in_record(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "my specific query",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        for rec in records:
            assert rec["discovery_query"] == "my specific query"


# ---------------------------------------------------------------------------
# TestIncludeAllow
# ---------------------------------------------------------------------------


class TestIncludeAllow:
    """--include-allow also queues ALLOW candidates."""

    def test_allow_queued_with_include_allow(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--include-allow",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        decisions = {r["decision"] for r in records}
        assert "allow" in decisions
        assert "review" in decisions

    def test_reject_still_excluded_with_include_allow(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--include-allow",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        assert all(r["decision"] != "reject" for r in records)


# ---------------------------------------------------------------------------
# TestDecisionFilter
# ---------------------------------------------------------------------------


class TestDecisionFilter:
    def test_decision_filter_all_queues_everything(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--decision-filter", "all",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        decisions = {r["decision"] for r in records}
        assert decisions == {"allow", "review", "reject"}

    def test_decision_filter_reject_only(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--decision-filter", "reject",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        assert len(records) == 1
        assert records[0]["decision"] == "reject"

    def test_decision_filter_allow_review(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--decision-filter", "allow,review",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        decisions = {r["decision"] for r in records}
        assert decisions == {"allow", "review"}

    def test_invalid_decision_filter_returns_1(self, tmp_path, capsys):
        http_fn = _make_http_fn(_EMPTY_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--decision-filter", "bogus",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Unknown decision" in err or "bogus" in err


# ---------------------------------------------------------------------------
# TestIdempotency
# ---------------------------------------------------------------------------


class TestIdempotency:
    def test_second_run_skips_duplicates(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        args = [
            "--search", "test",
            "--decision-filter", "all",
            "--filter-config", str(cfg_path),
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ]

        main(args, _http_fn=_make_http_fn(_THREE_PAPER_XML))
        main(args, _http_fn=_make_http_fn(_THREE_PAPER_XML))

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        assert len(records) == 3, \
            f"Expected 3 records (no duplicates), got {len(records)}"

    def test_second_run_with_force_creates_duplicates(self, tmp_path):
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        base_args = [
            "--search", "test",
            "--decision-filter", "all",
            "--filter-config", str(cfg_path),
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ]

        main(base_args, _http_fn=_make_http_fn(_THREE_PAPER_XML))
        main(base_args + ["--force"], _http_fn=_make_http_fn(_THREE_PAPER_XML))

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        records = ReviewQueueStore(queue_path).all_records()
        assert len(records) == 6, \
            f"Expected 6 records (force re-queued), got {len(records)}"


# ---------------------------------------------------------------------------
# TestDryRun
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_writes_nothing(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--decision-filter", "all",
                "--dry-run",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0
        assert not queue_path.exists(), "Queue file must not be created during --dry-run"

    def test_dry_run_json_includes_would_queue(self, tmp_path, capsys):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--decision-filter", "all",
                "--dry-run",
                "--json",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["dry_run"] is True
        assert "would_queue" in data
        assert len(data["would_queue"]) == 3


# ---------------------------------------------------------------------------
# TestJsonOutput
# ---------------------------------------------------------------------------


class TestJsonOutput:
    def test_json_output_structure(self, tmp_path, capsys):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "prediction markets",
                "--decision-filter", "all",
                "--json",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)

        assert data["query"] == "prediction markets"
        assert data["source_family"] == "academic"
        assert data["discovered"] == 3
        assert data["queued"] == 3
        assert data["skipped_duplicate"] == 0
        assert data["dry_run"] is False
        assert set(data["decision_filter"]) == {"allow", "review", "reject"}
        assert "decisions" in data
        assert "label_counts" in data
        assert "queue_stats" in data
        assert "svm_trigger" in data
        svm = data["svm_trigger"]
        assert svm["target"] == 30
        assert "allow_gap" in svm
        assert "reject_gap" in svm

    def test_json_skipped_duplicate_counted(self, tmp_path, capsys):
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        args = [
            "--search", "test",
            "--decision-filter", "all",
            "--json",
            "--filter-config", str(cfg_path),
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ]
        main(args, _http_fn=_make_http_fn(_THREE_PAPER_XML))
        capsys.readouterr()  # discard first run output

        main(args, _http_fn=_make_http_fn(_THREE_PAPER_XML))
        data = json.loads(capsys.readouterr().out)
        assert data["skipped_duplicate"] == 3
        assert data["queued"] == 0


# ---------------------------------------------------------------------------
# TestEmptyResults
# ---------------------------------------------------------------------------


class TestEmptyResults:
    def test_empty_api_response_zero_queued(self, tmp_path):
        http_fn = _make_http_fn(_EMPTY_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "xkcd-quantum-nanohastelloy-nothing",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0
        assert not queue_path.exists() or queue_path.stat().st_size == 0

    def test_empty_results_json_shows_zero(self, tmp_path, capsys):
        http_fn = _make_http_fn(_EMPTY_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "nothing",
                "--json",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["discovered"] == 0
        assert data["queued"] == 0


# ---------------------------------------------------------------------------
# TestNetworkError
# ---------------------------------------------------------------------------


class TestNetworkError:
    def test_network_error_returns_1(self, tmp_path, capsys):
        def _fail(url, timeout):
            raise RuntimeError("Connection refused")

        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        rc = main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=_fail,
        )
        assert rc == 1
        err = capsys.readouterr().err
        assert "Error" in err


# ---------------------------------------------------------------------------
# TestHumanReadableOutput
# ---------------------------------------------------------------------------


class TestHumanReadableOutput:
    def test_output_shows_discovered_count(self, tmp_path, capsys):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test query",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        out = capsys.readouterr().out
        assert "discovered" in out
        assert "3" in out

    def test_output_shows_svm_progress(self, tmp_path, capsys):
        http_fn = _make_http_fn(_EMPTY_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )
        out = capsys.readouterr().out
        assert "SVM trigger" in out

    def test_help_exits_zero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0

    def test_missing_search_exits_nonzero(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# TestNoPDFDownload
# ---------------------------------------------------------------------------


class TestNoPDFDownload:
    """Regression guard: ensure the discover command never downloads PDFs."""

    def test_pdf_url_never_called(self, tmp_path):
        pdf_called = []

        def _http_fn(url: str, timeout: int) -> bytes:
            if ".pdf" in url or "arxiv.org/pdf" in url:
                pdf_called.append(url)
            return _THREE_PAPER_XML

        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "prediction markets",
                "--decision-filter", "all",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=_http_fn,
        )
        assert pdf_called == [], f"PDF URLs were called: {pdf_called}"

    def test_only_atom_api_called(self, tmp_path):
        """Only the arXiv Atom search API endpoint should be called."""
        all_urls = []

        def _http_fn(url: str, timeout: int) -> bytes:
            all_urls.append(url)
            return _THREE_PAPER_XML

        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=_http_fn,
        )
        assert len(all_urls) == 1, f"Expected exactly 1 HTTP call, got {len(all_urls)}: {all_urls}"
        assert "export.arxiv.org/api/query" in all_urls[0]


# ---------------------------------------------------------------------------
# TestQueueRecordIntegration
# ---------------------------------------------------------------------------


class TestQueueRecordIntegration:
    """Verify the enqueued records are compatible with research-prefetch-review."""

    def test_queued_records_visible_in_review_list(self, tmp_path, capsys):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from tools.cli.research_prefetch_review import main as review_main
        rc = review_main([
            "list",
            "--all",
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ])
        assert rc == 0
        out = capsys.readouterr().out
        # REVIEW candidate title appears in list
        assert "Trading Strategy" in out or "Binary Options" in out

    def test_discovered_record_can_be_labeled(self, tmp_path):
        http_fn = _make_http_fn(_THREE_PAPER_XML)
        cfg_path = _write_filter_config(tmp_path)
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"

        main(
            [
                "--search", "test",
                "--filter-config", str(cfg_path),
                "--queue-path", str(queue_path),
                "--label-path", str(label_path),
            ],
            _http_fn=http_fn,
        )

        from packages.research.relevance_filter.queue_store import ReviewQueueStore, LabelStore
        q = ReviewQueueStore(queue_path)
        ls = LabelStore(label_path)
        records = q.all_records()
        assert len(records) >= 1
        rec = records[0]
        cid = rec["candidate_id"]
        ls.append_label(
            candidate_id=cid,
            source_url=rec["source_url"],
            title=rec["title"],
            label="allow",
        )
        counts = ls.counts()
        assert counts["allow"] == 1
