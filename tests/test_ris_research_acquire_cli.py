"""Tests for research-acquire CLI — all offline via monkeypatching."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Helpers — canned HTTP responses
# ---------------------------------------------------------------------------

def _arxiv_xml_bytes(arxiv_id: str = "2301.12345") -> bytes:
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/{arxiv_id}v1</id>
    <title>Test Acquire Paper</title>
    <summary>Abstract text for acquire test.</summary>
    <author><name>Acquire Author</name></author>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""
    return xml.encode("utf-8")


def _github_repo_bytes() -> bytes:
    data = {
        "description": "Test GitHub repo",
        "stargazers_count": 10,
        "forks_count": 2,
        "pushed_at": "2024-03-01T00:00:00Z",
        "license": {"spdx_id": "MIT", "name": "MIT License"},
    }
    return json.dumps(data).encode("utf-8")


def _github_readme_bytes() -> bytes:
    content = base64.b64encode(b"# Test README\nHello").decode("ascii")
    return json.dumps({"content": content, "encoding": "base64"}).encode("utf-8")


def _blog_html_bytes() -> bytes:
    return b"""<html><head>
<title>Test Blog Post</title>
<meta name="author" content="Test Author">
<meta property="article:published_time" content="2024-01-01T00:00:00Z">
<meta property="og:site_name" content="Test Site">
</head><body><p>Blog body content here.</p></body></html>"""


def _make_arxiv_http_fn():
    """Return an http_fn that serves canned arXiv XML for any call."""
    return lambda url, timeout, headers: _arxiv_xml_bytes()


def _make_github_http_fn():
    """Return an http_fn that serves canned GitHub API responses."""
    def http_fn(url, timeout, headers):
        if "readme" in url.lower():
            return _github_readme_bytes()
        return _github_repo_bytes()
    return http_fn


def _make_blog_http_fn():
    return lambda url, timeout, headers: _blog_html_bytes()


# ---------------------------------------------------------------------------
# Test: no-args returns 1
# ---------------------------------------------------------------------------


class TestNoArgsReturnsOne:
    def test_no_args(self, capsys):
        from tools.cli.research_acquire import main
        rc = main([])
        assert rc == 1


# ---------------------------------------------------------------------------
# Test: missing --url returns 1
# ---------------------------------------------------------------------------


class TestMissingArgs:
    def test_missing_url(self, capsys):
        """--source-family present but --url missing should return 1."""
        from tools.cli.research_acquire import main
        rc = main(["--source-family", "academic"])
        assert rc == 1

    def test_missing_source_family(self, capsys):
        """--url present but --source-family missing should return 1."""
        from tools.cli.research_acquire import main
        rc = main(["--url", "https://arxiv.org/abs/2301.12345"])
        assert rc == 1


# ---------------------------------------------------------------------------
# Test: invalid --source-family
# ---------------------------------------------------------------------------


class TestInvalidSourceFamily:
    def test_invalid_family_fails(self, capsys):
        from tools.cli.research_acquire import main
        # argparse raises SystemExit for invalid choices
        with pytest.raises(SystemExit) as exc_info:
            main(["--url", "https://arxiv.org/abs/2301.12345", "--source-family", "INVALID"])
        assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# Test: dry-run + json returns 0, has correct keys
# ---------------------------------------------------------------------------


class TestDryRunJson:
    def test_academic_dry_run_json(self, monkeypatch, capsys):
        """Dry-run with JSON output: returns 0, stdout has expected keys."""
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--dry-run",
            "--json",
            "--no-eval",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        expected_keys = {"source_url", "source_id", "source_family", "normalized_title", "dedup_status"}
        assert expected_keys.issubset(set(data.keys()))
        assert data["source_family"] == "academic"

    def test_github_dry_run_json(self, monkeypatch, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_github_http_fn())

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://github.com/polymarket/py-clob-client",
            "--source-family", "github",
            "--dry-run",
            "--json",
            "--no-eval",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["source_family"] == "github"

    def test_blog_dry_run_json(self, monkeypatch, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_blog_http_fn())

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://blog.example.com/article",
            "--source-family", "blog",
            "--dry-run",
            "--json",
            "--no-eval",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["source_family"] == "blog"


# ---------------------------------------------------------------------------
# Test: dry-run does NOT create files
# ---------------------------------------------------------------------------


class TestDryRunNoFiles:
    def test_dry_run_creates_no_cache_or_review_files(self, monkeypatch, tmp_path, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        cache_dir = tmp_path / "cache"
        review_dir = tmp_path / "reviews"

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--dry-run",
            "--json",
            "--no-eval",
            "--cache-dir", str(cache_dir),
            "--review-dir", str(review_dir),
        ])
        assert rc == 0
        # Neither directory should be created
        assert not cache_dir.exists()
        assert not review_dir.exists()


# ---------------------------------------------------------------------------
# Test: full flow (non-dry-run) creates cache + review files
# ---------------------------------------------------------------------------


class TestFullFlow:
    def test_full_flow_creates_cache_and_review(self, monkeypatch, tmp_path, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        cache_dir = tmp_path / "cache"
        review_dir = tmp_path / "reviews"

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--cache-dir", str(cache_dir),
            "--review-dir", str(review_dir),
        ])
        assert rc == 0

        # Cache file should exist
        cache_files = list(cache_dir.rglob("*.json"))
        assert len(cache_files) >= 1

        # Review JSONL should exist with at least one line
        review_file = review_dir / "acquisition_review.jsonl"
        assert review_file.exists()
        lines = review_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) >= 1
        review_record = json.loads(lines[0])
        assert review_record["source_family"] == "academic"
        assert review_record["source_url"] == "https://arxiv.org/abs/2301.12345"

    def test_full_flow_json_output_has_expected_keys(self, monkeypatch, tmp_path, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        expected_keys = {
            "source_url", "source_id", "source_family", "normalized_title",
            "dedup_status", "cached_path", "doc_id", "chunk_count", "rejected",
        }
        assert expected_keys.issubset(set(data.keys()))

    def test_second_run_shows_cached_dedup_status(self, monkeypatch, tmp_path, capsys):
        """Running acquire twice on same URL should show dedup_status='cached' second time."""
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        from tools.cli.research_acquire import main
        cache_dir = str(tmp_path / "cache")
        review_dir = str(tmp_path / "reviews")
        args = [
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--cache-dir", cache_dir,
            "--review-dir", review_dir,
        ]
        # First run
        rc1 = main(args)
        assert rc1 == 0
        out1 = capsys.readouterr()
        data1 = json.loads(out1.out)
        assert data1["dedup_status"] == "new"

        # Second run — same URL
        rc2 = main(args)
        assert rc2 == 0
        out2 = capsys.readouterr()
        data2 = json.loads(out2.out)
        assert data2["dedup_status"] == "cached"


# ---------------------------------------------------------------------------
# Test: custom --cache-dir and --review-dir
# ---------------------------------------------------------------------------


class TestCustomPaths:
    def test_custom_cache_dir(self, monkeypatch, tmp_path, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        custom_cache = tmp_path / "my_cache"
        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--no-eval",
            "--cache-dir", str(custom_cache),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        cache_files = list(custom_cache.rglob("*.json"))
        assert len(cache_files) >= 1

    def test_custom_review_dir(self, monkeypatch, tmp_path, capsys):
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(fetchers_mod, "_default_urlopen", _make_arxiv_http_fn())

        custom_reviews = tmp_path / "my_reviews"
        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.12345",
            "--source-family", "academic",
            "--no-eval",
            "--review-dir", str(custom_reviews),
            "--cache-dir", str(tmp_path / "cache"),
        ])
        assert rc == 0
        assert (custom_reviews / "acquisition_review.jsonl").exists()


# ---------------------------------------------------------------------------
# Test: help works
# ---------------------------------------------------------------------------


class TestHelp:
    def test_help_flag(self, capsys):
        from tools.cli.research_acquire import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "research-acquire" in captured.out.lower() or "url" in captured.out.lower()


# ---------------------------------------------------------------------------
# Test: prefetch filter modes (hold-review, enforce, dry-run)
# ---------------------------------------------------------------------------

def _make_filter_config(tmp_path: Path, allow_threshold: float = 0.80) -> Path:
    """Write a minimal filter config JSON for testing."""
    config = {
        "version": "test",
        "strong_positive_weight": 2.0,
        "positive_weight": 1.0,
        "strong_negative_weight": -3.0,
        "negative_weight": -1.5,
        "allow_threshold": allow_threshold,
        "review_threshold": 0.35,
        "strong_positive_terms": ["prediction market"],
        "positive_terms": ["liquidity"],
        "strong_negative_terms": ["hastelloy"],
        "negative_terms": ["e-commerce"],
    }
    p = tmp_path / "filter_config.json"
    p.write_text(json.dumps(config), encoding="utf-8")
    return p


def _arxiv_xml_for_title(title: str, abstract: str = "") -> bytes:
    """Return arXiv XML bytes with a custom title/abstract."""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/abs/2301.99999v1</id>
    <title>{title}</title>
    <summary>{abstract}</summary>
    <author><name>Test Author</name></author>
    <published>2024-01-01T00:00:00Z</published>
  </entry>
</feed>"""
    return xml.encode("utf-8")


class TestPrefetchFilterModes:
    """Tests for --prefetch-filter-mode: dry-run, enforce, hold-review."""

    def test_dry_run_mode_logs_but_ingests(self, monkeypatch, tmp_path, capsys):
        """dry-run: filter logs decision but proceeds to ingest (returns 0)."""
        import packages.research.ingestion.fetchers as fetchers_mod
        # Title "liquidity paper" matches one positive term → score < 0.80 → review decision
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title("liquidity paper", "some abstract"),
        )
        config_path = _make_filter_config(tmp_path)

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--dry-run",
            "--no-eval",
            "--prefetch-filter-mode", "dry-run",
            "--prefetch-filter-config", str(config_path),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        # dry-run filter logs to stderr; no queue written
        queue_file = tmp_path / "prefetch_review_queue" / "review_queue.jsonl"
        assert not queue_file.exists()

    def test_enforce_skips_reject_only(self, monkeypatch, tmp_path, capsys):
        """enforce: REJECT candidates are skipped; REVIEW candidates are NOT queued."""
        import packages.research.ingestion.fetchers as fetchers_mod
        # "hastelloy" is a strong negative → reject decision
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title(
                "Hastelloy alloy fatigue study", "hastelloy x alloy"
            ),
        )
        config_path = _make_filter_config(tmp_path)

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--prefetch-filter-mode", "enforce",
            "--prefetch-filter-config", str(config_path),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["skipped"] is True
        assert data["filter_decision"] == "reject"
        # No queue file written for enforce mode
        queue_file = tmp_path / "prefetch_review_queue" / "review_queue.jsonl"
        assert not queue_file.exists()

    def test_hold_review_queues_review_decision(self, monkeypatch, tmp_path, capsys):
        """hold-review: REVIEW candidates are queued and NOT ingested."""
        import packages.research.ingestion.fetchers as fetchers_mod
        # "liquidity" is a positive term (+1); sigmoid(1.0)=0.731 < allow_threshold=0.80 → review
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title(
                "A study on market liquidity", "This paper studies liquidity."
            ),
        )
        config_path = _make_filter_config(tmp_path)
        queue_dir = tmp_path / "prefetch_review_queue"

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--prefetch-filter-mode", "hold-review",
            "--prefetch-filter-config", str(config_path),
            "--prefetch-review-queue-dir", str(queue_dir),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["queued_for_review"] is True
        assert data["skipped"] is True
        assert data["filter_decision"] == "review"

        # Queue file must exist with one record
        queue_file = queue_dir / "review_queue.jsonl"
        assert queue_file.exists()
        import json as _json
        records = [_json.loads(line) for line in queue_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(records) == 1
        assert records[0]["decision"] == "review"
        assert "candidate_id" in records[0]

    def test_hold_review_skips_reject(self, monkeypatch, tmp_path, capsys):
        """hold-review: REJECT candidates are also skipped (not queued)."""
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title(
                "Hastelloy X material fatigue", "hastelloy alloy study"
            ),
        )
        config_path = _make_filter_config(tmp_path)
        queue_dir = tmp_path / "prefetch_review_queue"

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--prefetch-filter-mode", "hold-review",
            "--prefetch-filter-config", str(config_path),
            "--prefetch-review-queue-dir", str(queue_dir),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["skipped"] is True
        assert data["filter_decision"] == "reject"
        # REJECT items are not written to the review queue
        queue_file = queue_dir / "review_queue.jsonl"
        assert not queue_file.exists()

    def test_hold_review_idempotent_duplicate_url(self, monkeypatch, tmp_path, capsys):
        """hold-review: same URL queued twice results in only one queue record."""
        import packages.research.ingestion.fetchers as fetchers_mod
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title(
                "A study on market liquidity", "liquidity paper abstract"
            ),
        )
        config_path = _make_filter_config(tmp_path)
        queue_dir = tmp_path / "prefetch_review_queue"
        args = [
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--prefetch-filter-mode", "hold-review",
            "--prefetch-filter-config", str(config_path),
            "--prefetch-review-queue-dir", str(queue_dir),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ]
        from tools.cli.research_acquire import main
        main(args)
        capsys.readouterr()
        main(args)  # second call — same URL
        capsys.readouterr()

        import json as _json
        queue_file = queue_dir / "review_queue.jsonl"
        records = [_json.loads(l) for l in queue_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        assert len(records) == 1

    def test_hold_review_queue_write_failure_reports_error(self, monkeypatch, tmp_path, capsys):
        """hold-review: queue write failure reports queued_for_review=false + queue_error; candidate not ingested."""
        import packages.research.ingestion.fetchers as fetchers_mod
        # "liquidity" → positive term → sigmoid(1.0)=0.731 < 0.80 → review decision
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title(
                "A study on market liquidity", "This paper studies liquidity."
            ),
        )
        config_path = _make_filter_config(tmp_path)
        queue_dir = tmp_path / "prefetch_review_queue"

        # Force enqueue to raise an IOError
        import packages.research.relevance_filter.queue_store as qs_mod

        def _failing_enqueue(self, record):
            raise IOError("simulated disk failure")

        monkeypatch.setattr(qs_mod.ReviewQueueStore, "enqueue", _failing_enqueue)

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--prefetch-filter-mode", "hold-review",
            "--prefetch-filter-config", str(config_path),
            "--prefetch-review-queue-dir", str(queue_dir),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        # rc=0 because candidate is still held out (not ingested), even when queue write fails
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["queued_for_review"] is False
        assert "queue_error" in data
        assert "simulated disk failure" in data["queue_error"]
        # Candidate was not ingested — cache dir must not exist
        assert not (tmp_path / "cache").exists()

    def test_hold_review_allow_proceeds_normally(self, monkeypatch, tmp_path, capsys):
        """hold-review: ALLOW candidates proceed to dry-run as normal (no queue)."""
        import packages.research.ingestion.fetchers as fetchers_mod
        # "prediction market" is strong_positive (+2); sigmoid(2.0)=0.880 >= 0.80 → allow
        monkeypatch.setattr(
            fetchers_mod, "_default_urlopen",
            lambda url, timeout, headers: _arxiv_xml_for_title(
                "Optimal market making in prediction markets",
                "We study prediction market efficiency and liquidity.",
            ),
        )
        config_path = _make_filter_config(tmp_path)
        queue_dir = tmp_path / "prefetch_review_queue"

        from tools.cli.research_acquire import main
        rc = main([
            "--url", "https://arxiv.org/abs/2301.99999",
            "--source-family", "academic",
            "--no-eval",
            "--dry-run",  # dry-run to avoid DB I/O
            "--json",
            "--prefetch-filter-mode", "hold-review",
            "--prefetch-filter-config", str(config_path),
            "--prefetch-review-queue-dir", str(queue_dir),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0
        # Should NOT be queued — this is an ALLOW
        queue_file = queue_dir / "review_queue.jsonl"
        assert not queue_file.exists()


# ---------------------------------------------------------------------------
# Test: research-prefetch-review CLI
# ---------------------------------------------------------------------------

class TestResearchPrefetchReviewCLI:
    """Tests for the research-prefetch-review subcommand CLI."""

    def _write_queue_record(self, queue_path: Path, url: str, title: str, score: float) -> None:
        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        q = ReviewQueueStore(queue_path)
        q.enqueue({
            "source_url": url,
            "title": title,
            "score": score,
            "decision": "review",
            "reason_codes": ["positive:liquidity"],
            "config_version": "test",
        })

    def test_list_empty_queue(self, tmp_path, capsys):
        from tools.cli.research_prefetch_review import main
        rc = main(["list", "--queue-path", str(tmp_path / "queue.jsonl")])
        assert rc == 0
        captured = capsys.readouterr()
        assert "No items" in captured.out

    def test_list_with_items(self, tmp_path, capsys):
        queue_path = tmp_path / "queue.jsonl"
        self._write_queue_record(queue_path, "https://arxiv.org/abs/1111.2222", "Test Paper", 0.65)
        from tools.cli.research_prefetch_review import main
        rc = main(["list", "--queue-path", str(queue_path)])
        assert rc == 0
        captured = capsys.readouterr()
        assert "Test Paper" in captured.out

    def test_list_json_output(self, tmp_path, capsys):
        queue_path = tmp_path / "queue.jsonl"
        self._write_queue_record(queue_path, "https://arxiv.org/abs/2222.3333", "JSON Paper", 0.72)
        from tools.cli.research_prefetch_review import main
        rc = main(["list", "--queue-path", str(queue_path), "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        records = json.loads(captured.out)
        assert isinstance(records, list)
        assert len(records) == 1
        assert records[0]["title"] == "JSON Paper"

    def test_label_allow(self, tmp_path, capsys):
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"
        url = "https://arxiv.org/abs/3333.4444"
        self._write_queue_record(queue_path, url, "Label Test Paper", 0.65)

        from packages.research.relevance_filter.queue_store import ReviewQueueStore, candidate_id_from_url
        q = ReviewQueueStore(queue_path)
        records = q.all_records()
        full_id = records[0]["candidate_id"]

        from tools.cli.research_prefetch_review import main
        rc = main([
            "label", full_id[:12], "allow",
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ])
        assert rc == 0

        from packages.research.relevance_filter.queue_store import LabelStore
        ls = LabelStore(label_path)
        counts = ls.counts()
        assert counts["total"] == 1
        assert counts["allow"] == 1

    def test_label_reject_with_note(self, tmp_path, capsys):
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"
        url = "https://arxiv.org/abs/4444.5555"
        self._write_queue_record(queue_path, url, "Reject Test Paper", 0.55)

        from packages.research.relevance_filter.queue_store import ReviewQueueStore
        q = ReviewQueueStore(queue_path)
        full_id = q.all_records()[0]["candidate_id"]

        from tools.cli.research_prefetch_review import main
        rc = main([
            "label", full_id[:16], "reject",
            "--note", "clearly off-topic for trading",
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ])
        assert rc == 0

        from packages.research.relevance_filter.queue_store import LabelStore
        ls = LabelStore(label_path)
        labels = ls.all_labels()
        assert labels[0]["label"] == "reject"
        assert labels[0]["note"] == "clearly off-topic for trading"

    def test_label_unknown_id_returns_1(self, tmp_path, capsys):
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"
        from tools.cli.research_prefetch_review import main
        rc = main([
            "label", "nonexistentid00", "allow",
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ])
        assert rc == 1

    def test_counts_empty(self, tmp_path, capsys):
        from tools.cli.research_prefetch_review import main
        rc = main([
            "counts",
            "--queue-path", str(tmp_path / "queue.jsonl"),
            "--label-path", str(tmp_path / "labels.jsonl"),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "0" in captured.out

    def test_counts_json(self, tmp_path, capsys):
        queue_path = tmp_path / "queue.jsonl"
        label_path = tmp_path / "labels.jsonl"
        self._write_queue_record(queue_path, "https://arxiv.org/abs/5555.6666", "Count Paper", 0.65)
        from packages.research.relevance_filter.queue_store import LabelStore, candidate_id_from_url
        ls = LabelStore(label_path)
        ls.append_label(candidate_id_from_url("https://x.com/1"), "https://x.com/1", "T", "allow")
        ls.append_label(candidate_id_from_url("https://x.com/2"), "https://x.com/2", "U", "reject")

        from tools.cli.research_prefetch_review import main
        rc = main([
            "counts", "--json",
            "--queue-path", str(queue_path),
            "--label-path", str(label_path),
        ])
        assert rc == 0
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["pending_review_count"] == 1
        assert data["label_count"] == 2
        assert data["allowed_label_count"] == 1
        assert data["rejected_label_count"] == 1

    def test_no_subcommand_returns_1(self, capsys):
        from tools.cli.research_prefetch_review import main
        rc = main([])
        assert rc == 1

    def test_help_flag(self, capsys):
        from tools.cli.research_prefetch_review import main
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# Test: search-mode hold-review
# ---------------------------------------------------------------------------


class TestSearchModeHoldReview:
    """Offline tests for --search + --prefetch-filter-mode hold-review."""

    def test_search_mode_hold_review_queues_review_does_not_ingest(
        self, monkeypatch, tmp_path, capsys
    ):
        """search mode hold-review: REVIEW papers queued; REJECT papers skipped; neither ingested."""
        import packages.research.ingestion.fetchers as fetchers_mod
        import packages.research.ingestion.pipeline as pipeline_mod
        import packages.polymarket.rag.knowledge_store as ks_mod

        # Two papers:
        #   9001.0001 — "liquidity" positive term → sigmoid(1.0)=0.731 < 0.80 → review
        #   9001.0002 — "hastelloy" strong-negative → reject
        papers = [
            {
                "url": "https://arxiv.org/abs/9001.0001",
                "title": "A study of liquidity provision",
                "abstract": "",
                "authors": [],
                "published_date": "2024-01-01",
            },
            {
                "url": "https://arxiv.org/abs/9001.0002",
                "title": "Hastelloy X alloy fatigue study",
                "abstract": "hastelloy x alloy",
                "authors": [],
                "published_date": "2024-01-01",
            },
        ]
        monkeypatch.setattr(
            fetchers_mod.LiveAcademicFetcher,
            "search_by_topic",
            lambda self, query, max_results: papers,
        )

        # Spy on ingest_external — it must never be called for hold-review REVIEW/REJECT papers
        ingest_calls = []
        original_ingest = pipeline_mod.IngestPipeline.ingest_external

        def _spy_ingest(self, raw_source, family, **kwargs):
            ingest_calls.append(raw_source.get("url", ""))
            return original_ingest(self, raw_source, family, **kwargs)

        monkeypatch.setattr(pipeline_mod.IngestPipeline, "ingest_external", _spy_ingest)

        # Stub KnowledgeStore to avoid real DB I/O (both papers are filtered so no writes occur,
        # but KnowledgeStore is still instantiated before the per-paper loop)
        class _FakeStore:
            def close(self):
                pass

        monkeypatch.setattr(ks_mod, "KnowledgeStore", lambda *a, **kw: _FakeStore())

        config_path = _make_filter_config(tmp_path)
        queue_dir = tmp_path / "queue"

        from tools.cli.research_acquire import main
        rc = main([
            "--search", "liquidity market",
            "--source-family", "academic",
            "--no-eval",
            "--json",
            "--prefetch-filter-mode", "hold-review",
            "--prefetch-filter-config", str(config_path),
            "--prefetch-review-queue-dir", str(queue_dir),
            "--cache-dir", str(tmp_path / "cache"),
            "--review-dir", str(tmp_path / "reviews"),
        ])
        assert rc == 0

        # Neither paper should have triggered ingest
        assert ingest_calls == [], f"ingest_external called unexpectedly for: {ingest_calls}"

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        results = data["results"]
        assert len(results) == 2

        # REVIEW paper was queued and held out
        review_r = next(r for r in results if "9001.0001" in r["source_url"])
        assert review_r["queued_for_review"] is True
        assert review_r["skipped_by_filter"] is True
        assert review_r["filter_decision"] == "review"

        # REJECT paper was skipped (not queued)
        reject_r = next(r for r in results if "9001.0002" in r["source_url"])
        assert reject_r["skipped_by_filter"] is True
        assert reject_r["filter_decision"] == "reject"
        assert not reject_r.get("queued_for_review")

        # Queue file has exactly 1 record (the REVIEW paper)
        queue_file = queue_dir / "review_queue.jsonl"
        assert queue_file.exists()
        records = [
            json.loads(line)
            for line in queue_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(records) == 1
        assert "9001.0001" in records[0]["source_url"]
