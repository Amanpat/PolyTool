"""Tests for RIS Phase 5 AcquisitionReviewWriter — all offline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def _make_record(**overrides):
    from packages.research.ingestion.acquisition_review import AcquisitionRecord
    defaults = dict(
        acquired_at="2026-04-02T10:00:00Z",
        source_url="https://arxiv.org/abs/2301.12345",
        source_family="academic",
        source_id="abc123def456abcd",
        canonical_ids={"arxiv_id": "2301.12345"},
        cached_path="artifacts/research/raw_source_cache/academic/abc123def456abcd.json",
        normalized_title="Test Paper Title",
        dedup_status="new",
        error=None,
    )
    defaults.update(overrides)
    return AcquisitionRecord(**defaults)


class TestAcquisitionReviewWriter:
    def test_write_review_creates_file(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        record = _make_record()
        path = writer.write_review(record)
        assert path.exists()
        assert path.name == "acquisition_review.jsonl"

    def test_write_review_appends_json_line(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        record = _make_record()
        writer.write_review(record)
        lines = path_for(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        obj = json.loads(lines[0])
        assert obj["source_url"] == "https://arxiv.org/abs/2301.12345"

    def test_multiple_writes_append_not_overwrite(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        r1 = _make_record(source_url="https://arxiv.org/abs/0001.00001", source_id="id1")
        r2 = _make_record(source_url="https://arxiv.org/abs/0002.00002", source_id="id2")
        r3 = _make_record(source_url="https://github.com/test/repo", source_family="github", source_id="id3")
        writer.write_review(r1)
        writer.write_review(r2)
        writer.write_review(r3)
        lines = path_for(tmp_path).read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 3

    def test_read_reviews_returns_list_of_dicts(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        writer.write_review(_make_record(source_id="aaa"))
        writer.write_review(_make_record(source_id="bbb"))
        reviews = writer.read_reviews()
        assert isinstance(reviews, list)
        assert len(reviews) == 2
        assert all(isinstance(r, dict) for r in reviews)

    def test_read_reviews_empty_on_missing_file(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "no_such_dir" / "reviews")
        reviews = writer.read_reviews()
        assert reviews == []

    def test_record_schema_keys(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        writer.write_review(_make_record())
        reviews = writer.read_reviews()
        obj = reviews[0]
        expected_keys = {
            "acquired_at", "source_url", "source_family", "source_id",
            "canonical_ids", "cached_path", "normalized_title", "dedup_status", "error",
        }
        assert expected_keys.issubset(set(obj.keys()))

    def test_write_creates_parent_dirs(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        deep_dir = tmp_path / "a" / "b" / "c" / "reviews"
        writer = AcquisitionReviewWriter(deep_dir)
        writer.write_review(_make_record())
        assert deep_dir.exists()

    def test_write_with_error_field(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        record = _make_record(error="FetchError: HTTP 503")
        writer.write_review(record)
        reviews = writer.read_reviews()
        assert reviews[0]["error"] == "FetchError: HTTP 503"

    def test_write_with_cached_dedup_status(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        writer.write_review(_make_record(dedup_status="cached"))
        reviews = writer.read_reviews()
        assert reviews[0]["dedup_status"] == "cached"

    def test_read_reviews_round_trips_canonical_ids(self, tmp_path):
        from packages.research.ingestion.acquisition_review import AcquisitionReviewWriter
        writer = AcquisitionReviewWriter(tmp_path / "reviews")
        writer.write_review(_make_record(canonical_ids={"arxiv_id": "2301.12345", "doi": "10.1234/abc"}))
        reviews = writer.read_reviews()
        assert reviews[0]["canonical_ids"] == {"arxiv_id": "2301.12345", "doi": "10.1234/abc"}


# Helper: construct path for the review file
def path_for(tmp_path: Path) -> Path:
    return tmp_path / "reviews" / "acquisition_review.jsonl"
