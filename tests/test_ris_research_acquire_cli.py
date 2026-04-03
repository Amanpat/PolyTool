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
