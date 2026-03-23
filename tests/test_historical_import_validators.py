"""Tests for packages/polymarket/historical_import/validators.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from packages.polymarket.historical_import.validators import (
    validate_jon_becker_layout,
    validate_pmxt_layout,
    validate_price_history_layout,
)


def _make_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestValidatePmxtLayout:
    def test_missing_path(self):
        result = validate_pmxt_layout("/nonexistent/path/xyz_99999")
        assert not result.valid
        assert any("does not exist" in e for e in result.errors)

    def test_not_a_directory(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        result = validate_pmxt_layout(str(f))
        assert not result.valid
        assert any("not a directory" in e for e in result.errors)

    def test_missing_polymarket_dir(self, tmp_path):
        result = validate_pmxt_layout(str(tmp_path))
        assert not result.valid
        assert any("Polymarket" in e for e in result.errors)

    def test_empty_polymarket_dir(self, tmp_path):
        (tmp_path / "Polymarket").mkdir()
        result = validate_pmxt_layout(str(tmp_path))
        assert not result.valid
        assert any("no .parquet files" in e for e in result.errors)

    def test_valid_polymarket_only(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "snapshot_2026.parquet", "")
        result = validate_pmxt_layout(str(tmp_path))
        assert result.valid
        assert result.file_count == 1
        assert result.checksum != ""
        assert not result.errors

    def test_valid_with_optional_dirs(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "a.parquet", "")
        _make_file(tmp_path / "Kalshi" / "b.parquet", "")
        _make_file(tmp_path / "Opinion" / "c.parquet", "")
        result = validate_pmxt_layout(str(tmp_path))
        assert result.valid
        assert result.file_count == 3

    def test_source_kind(self, tmp_path):
        result = validate_pmxt_layout(str(tmp_path))
        assert result.source_kind == "pmxt_archive"

    def test_deterministic_checksum(self, tmp_path):
        _make_file(tmp_path / "Polymarket" / "x.parquet", "")
        r1 = validate_pmxt_layout(str(tmp_path))
        r2 = validate_pmxt_layout(str(tmp_path))
        assert r1.checksum == r2.checksum


class TestValidateJonBeckerLayout:
    def test_missing_path(self):
        result = validate_jon_becker_layout("/nope_xyz_99999")
        assert not result.valid
        assert any("does not exist" in e for e in result.errors)

    def test_missing_polymarket_trades(self, tmp_path):
        result = validate_jon_becker_layout(str(tmp_path))
        assert not result.valid
        assert any("data/polymarket/trades" in e for e in result.errors)

    def test_empty_polymarket_trades(self, tmp_path):
        (tmp_path / "data" / "polymarket" / "trades").mkdir(parents=True)
        result = validate_jon_becker_layout(str(tmp_path))
        assert not result.valid
        assert any("no trade files" in e for e in result.errors)

    def test_valid_csv(self, tmp_path):
        _make_file(tmp_path / "data" / "polymarket" / "trades" / "trades.csv", "")
        result = validate_jon_becker_layout(str(tmp_path))
        assert result.valid
        assert result.file_count == 1

    def test_valid_parquet(self, tmp_path):
        _make_file(tmp_path / "data" / "polymarket" / "trades" / "trades.parquet", "")
        result = validate_jon_becker_layout(str(tmp_path))
        assert result.valid

    def test_valid_with_kalshi(self, tmp_path):
        _make_file(tmp_path / "data" / "polymarket" / "trades" / "pm.parquet", "")
        _make_file(tmp_path / "data" / "kalshi" / "trades" / "kal.parquet", "")
        result = validate_jon_becker_layout(str(tmp_path))
        assert result.valid
        assert result.file_count == 2

    def test_zst_not_extracted_warning(self, tmp_path):
        (tmp_path / "data.tar.zst").write_bytes(b"")
        result = validate_jon_becker_layout(str(tmp_path))
        assert not result.valid
        assert any("data.tar.zst" in w for w in result.warnings)

    def test_source_kind(self, tmp_path):
        result = validate_jon_becker_layout(str(tmp_path))
        assert result.source_kind == "jon_becker"

    def test_deterministic_checksum(self, tmp_path):
        _make_file(tmp_path / "data" / "polymarket" / "trades" / "x.parquet", "")
        r1 = validate_jon_becker_layout(str(tmp_path))
        r2 = validate_jon_becker_layout(str(tmp_path))
        assert r1.checksum == r2.checksum


class TestValidatePriceHistoryLayout:
    def test_missing_path(self):
        result = validate_price_history_layout("/nope_xyz_99999")
        assert not result.valid

    def test_empty_directory(self, tmp_path):
        result = validate_price_history_layout(str(tmp_path))
        assert not result.valid
        assert any("No price history files" in e for e in result.errors)

    def test_valid_jsonl(self, tmp_path):
        _make_file(tmp_path / "token_abc123.jsonl", "")
        result = validate_price_history_layout(str(tmp_path))
        assert result.valid
        assert result.file_count == 1

    def test_valid_csv(self, tmp_path):
        _make_file(tmp_path / "token_abc123.csv", "")
        result = validate_price_history_layout(str(tmp_path))
        assert result.valid

    def test_multiple_files(self, tmp_path):
        for i in range(5):
            _make_file(tmp_path / f"token_{i}.jsonl", "")
        result = validate_price_history_layout(str(tmp_path))
        assert result.valid
        assert result.file_count == 5

    def test_source_kind(self, tmp_path):
        result = validate_price_history_layout(str(tmp_path))
        assert result.source_kind == "price_history_2min"

    def test_deterministic_checksum(self, tmp_path):
        _make_file(tmp_path / "a.jsonl", "")
        r1 = validate_price_history_layout(str(tmp_path))
        r2 = validate_price_history_layout(str(tmp_path))
        assert r1.checksum == r2.checksum
