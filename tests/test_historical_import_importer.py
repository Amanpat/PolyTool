"""Tests for packages/polymarket/historical_import/importer.py (Packet 2)."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from packages.polymarket.historical_import.importer import (
    ImportMode,
    ImportResult,
    JonBeckerImporter,
    PmxtImporter,
    PriceHistoryImporter,
    run_import,
)
from packages.polymarket.historical_import.manifest import (
    ImportRunRecord,
    make_import_run_record,
)


# ---------------------------------------------------------------------------
# Mock CH client
# ---------------------------------------------------------------------------


class MockCHClient:
    """Offline test double for CHInsertClient."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    def insert_rows(self, table: str, column_names: List[str], rows: List[list]) -> int:
        self.calls.append({"table": table, "column_names": column_names, "rows": rows})
        return len(rows)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_pmxt_fixture(root: Path) -> Path:
    """Create a minimal pmxt fixture directory."""
    pm_dir = root / "Polymarket"
    pm_dir.mkdir(parents=True, exist_ok=True)
    # Dummy parquet file (not real parquet, but enough for dry-run)
    (pm_dir / "snap_2026-01.parquet").write_bytes(b"PAR1" + b"\x00" * 100)
    return root


def _make_jb_fixture_csv(root: Path, rows: int = 5) -> Path:
    """Create a minimal Jon-Becker CSV fixture."""
    trades_dir = root / "data" / "polymarket" / "trades"
    trades_dir.mkdir(parents=True, exist_ok=True)
    csv_file = trades_dir / "trades_2024.csv"
    with open(str(csv_file), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["timestamp", "market_id", "token_id", "price", "size",
                        "taker_side", "resolution", "category"],
        )
        writer.writeheader()
        for i in range(rows):
            writer.writerow({
                "timestamp": str(1700000000 + i),
                "market_id": f"market_{i}",
                "token_id": f"token_{i}",
                "price": str(round(0.5 + i * 0.01, 4)),
                "size": str(100 + i),
                "taker_side": "buy" if i % 2 == 0 else "sell",
                "resolution": "WIN" if i % 3 == 0 else "",
                "category": "sports",
            })
    return root


def _make_price_history_fixture(root: Path, token_ids: List[str], rows_per: int = 3) -> Path:
    """Create JSONL price history fixtures."""
    root.mkdir(parents=True, exist_ok=True)
    for tid in token_ids:
        out = root / f"{tid}.jsonl"
        with open(str(out), "w", encoding="utf-8") as fh:
            for i in range(rows_per):
                fh.write(json.dumps({"t": 1700000000 + i * 120, "p": 0.73 + i * 0.01}) + "\n")
    return root


# ---------------------------------------------------------------------------
# TestMockCHClient
# ---------------------------------------------------------------------------


class TestMockCHClient:
    def test_insert_rows_returns_len(self):
        client = MockCHClient()
        n = client.insert_rows("some.table", ["a", "b"], [["x", "y"], ["z", "w"]])
        assert n == 2

    def test_insert_rows_records_calls(self):
        client = MockCHClient()
        client.insert_rows("t1", ["col"], [["v1"]])
        client.insert_rows("t2", ["col2"], [["v2"], ["v3"]])
        assert len(client.calls) == 2
        assert client.calls[0]["table"] == "t1"
        assert client.calls[1]["table"] == "t2"
        assert len(client.calls[1]["rows"]) == 2

    def test_empty_insert_returns_0(self):
        client = MockCHClient()
        n = client.insert_rows("t", [], [])
        assert n == 0


# ---------------------------------------------------------------------------
# TestImportModeDryRun
# ---------------------------------------------------------------------------


class TestImportModeDryRun:
    """All three importers in dry-run mode with fixture directories."""

    def test_pmxt_dry_run_no_ch_calls(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        client = MockCHClient()
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=client, run_id="r1")

        assert len(client.calls) == 0, "dry-run must not call insert_rows"

    def test_pmxt_dry_run_file_count(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        client = MockCHClient()
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=client, run_id="r1")

        assert result.files_processed == 1

    def test_pmxt_dry_run_zero_rows(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        client = MockCHClient()
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=client, run_id="r1")

        assert result.rows_loaded == 0

    def test_pmxt_dry_run_completeness(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="r1")

        assert result.import_completeness == "dry-run"

    def test_pmxt_dry_run_timestamps(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="r1")

        assert result.started_at != ""
        assert result.completed_at != ""

    def test_jb_dry_run_no_ch_calls(self, tmp_path):
        _make_jb_fixture_csv(tmp_path)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=client, run_id="r2")

        assert len(client.calls) == 0

    def test_jb_dry_run_completeness(self, tmp_path):
        _make_jb_fixture_csv(tmp_path)
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="r2")

        assert result.import_completeness == "dry-run"
        assert result.rows_loaded == 0
        assert result.files_processed >= 1

    def test_price_history_dry_run_no_ch_calls(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_abc", "tok_def"])
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=client, run_id="r3")

        assert len(client.calls) == 0

    def test_price_history_dry_run_completeness(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_abc"])
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="r3")

        assert result.import_completeness == "dry-run"
        assert result.rows_loaded == 0
        assert result.files_processed == 1
        assert result.started_at != ""
        assert result.completed_at != ""


# ---------------------------------------------------------------------------
# TestJonBeckerImporterCSV
# ---------------------------------------------------------------------------


class TestJonBeckerImporterCSV:
    """JonBecker importer in sample mode with real CSV fixture."""

    def test_sample_rows_loaded(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=10)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="jb1", sample_rows=5)

        assert result.rows_loaded == 5

    def test_sample_completeness_complete(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=3)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="jb2", sample_rows=1000)

        assert result.import_completeness == "complete"
        assert result.errors == []

    def test_sample_ch_client_called_with_correct_table(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=2)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        importer.run(ImportMode.SAMPLE, ch_client=client, run_id="jb3", sample_rows=1000)

        assert len(client.calls) >= 1
        assert client.calls[0]["table"] == "polytool.jb_trades"

    def test_sample_all_rows_loaded_when_limit_high(self, tmp_path):
        n_rows = 7
        _make_jb_fixture_csv(tmp_path, rows=n_rows)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="jb4", sample_rows=10000)

        assert result.rows_loaded == n_rows

    def test_full_mode_rows_loaded(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=5)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.FULL, ch_client=client, run_id="jb5")

        assert result.rows_loaded == 5
        assert result.import_completeness == "complete"

    def test_destination_tables(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=1)
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="jb6")
        assert "polytool.jb_trades" in result.destination_tables


# ---------------------------------------------------------------------------
# TestPriceHistoryImporterJSONL
# ---------------------------------------------------------------------------


class TestPriceHistoryImporterJSONL:
    def test_sample_rows_loaded(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_abc"], rows_per=5)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="ph1")

        assert result.rows_loaded > 0

    def test_token_id_from_filename(self, tmp_path):
        token_id = "my_special_token_123"
        _make_price_history_fixture(tmp_path, [token_id], rows_per=3)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        importer.run(ImportMode.SAMPLE, ch_client=client, run_id="ph2")

        assert len(client.calls) >= 1
        rows = client.calls[0]["rows"]
        assert all(row[0] == token_id for row in rows), "token_id should come from filename"

    def test_completeness_complete(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_x"], rows_per=2)
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=MockCHClient(), run_id="ph3")

        assert result.import_completeness == "complete"
        assert result.errors == []

    def test_full_mode_multi_file(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_a", "tok_b", "tok_c"], rows_per=4)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.FULL, ch_client=client, run_id="ph4")

        assert result.rows_loaded == 12  # 3 files * 4 rows
        assert result.files_processed == 3

    def test_correct_table_name(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_z"], rows_per=1)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        importer.run(ImportMode.SAMPLE, ch_client=client, run_id="ph5")

        assert len(client.calls) >= 1
        assert client.calls[0]["table"] == "polytool.price_history_2min"

    def test_source_field_is_polymarket_apis(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_src"], rows_per=2)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        importer.run(ImportMode.SAMPLE, ch_client=client, run_id="ph6")

        rows = client.calls[0]["rows"]
        col_names = client.calls[0]["column_names"]
        source_idx = col_names.index("source")
        assert all(row[source_idx] == "polymarket_apis" for row in rows)


# ---------------------------------------------------------------------------
# TestRunImportDispatch
# ---------------------------------------------------------------------------


class TestRunImportDispatch:
    def test_pmxt_dispatch(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="d1",
        )
        assert result.source_kind == "pmxt_archive"
        assert result.import_completeness == "dry-run"

    def test_jb_dispatch(self, tmp_path):
        _make_jb_fixture_csv(tmp_path)
        result = run_import(
            "jon_becker", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="d2",
        )
        assert result.source_kind == "jon_becker"

    def test_price_history_dispatch(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_dispatch"])
        result = run_import(
            "price_history_2min", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="d3",
        )
        assert result.source_kind == "price_history_2min"

    def test_unknown_source_kind_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Unknown source_kind"):
            run_import(
                "nonexistent_kind", str(tmp_path), ImportMode.DRY_RUN,
                ch_client=MockCHClient(),
            )

    def test_auto_run_id_generated(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(),
        )
        assert result.run_id != ""

    def test_snapshot_version_propagated(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), snapshot_version="2026-03",
        )
        assert result.snapshot_version == "2026-03"

    def test_notes_propagated(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["t1"])
        result = run_import(
            "price_history_2min", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), notes="test run",
        )
        assert result.notes == "test run"


# ---------------------------------------------------------------------------
# TestImportResultToDict
# ---------------------------------------------------------------------------


class TestImportResultToDict:
    def test_contains_all_required_fields(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="dict1",
        )
        d = result.to_dict()

        required_fields = [
            "source_kind", "import_mode", "run_id", "resolved_source_path",
            "destination_tables", "files_processed", "files_skipped",
            "rows_loaded", "rows_skipped", "rows_rejected",
            "import_completeness", "errors", "warnings",
            "started_at", "completed_at", "snapshot_version", "notes",
        ]
        for f in required_fields:
            assert f in d, f"Field '{f}' missing from to_dict() output"

    def test_values_match(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="dict2",
        )
        d = result.to_dict()

        assert d["source_kind"] == "pmxt_archive"
        assert d["import_mode"] == "dry-run"
        assert d["run_id"] == "dict2"
        assert d["import_completeness"] == "dry-run"


# ---------------------------------------------------------------------------
# TestMissingPath
# ---------------------------------------------------------------------------


class TestMissingPath:
    def test_pmxt_missing_path_completeness(self, tmp_path):
        missing = str(tmp_path / "does_not_exist")
        importer = PmxtImporter(missing)
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="miss1")

        # dry-run on missing path: importer still returns quickly but with errors or failed
        # The importer checks existence and returns "failed" with error
        assert result.import_completeness == "failed" or len(result.errors) > 0

    def test_jb_missing_path_errors(self, tmp_path):
        missing = str(tmp_path / "no_such_dir")
        importer = JonBeckerImporter(missing)
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="miss2")

        assert result.import_completeness == "failed" or len(result.errors) > 0

    def test_price_history_missing_path(self, tmp_path):
        missing = str(tmp_path / "nope")
        importer = PriceHistoryImporter(missing)
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="miss3")

        assert result.import_completeness == "failed" or len(result.errors) > 0

    def test_run_import_missing_path_no_exception(self, tmp_path):
        """run_import on a missing path should not raise — it should return a result."""
        missing = str(tmp_path / "does_not_exist")
        result = run_import(
            "pmxt_archive", missing, ImportMode.DRY_RUN,
            ch_client=MockCHClient(),
        )
        assert isinstance(result, ImportResult)
        # Should indicate failure
        assert result.import_completeness == "failed" or len(result.errors) > 0


# ---------------------------------------------------------------------------
# TestImportRunRecord (manifest integration)
# ---------------------------------------------------------------------------


class TestImportRunRecord:
    def test_make_import_run_record_dry_run(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="irr1",
        )
        record = make_import_run_record(result, snapshot_version="2026-03")

        assert isinstance(record, ImportRunRecord)
        assert record.schema_version == "import_run_v0"
        assert record.source_kind == "pmxt_archive"
        assert record.import_mode == "dry-run"
        assert record.run_id == "irr1"
        assert record.import_completeness == "dry-run"
        assert record.snapshot_version == "2026-03"

    def test_provenance_hash_populated(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="irr2",
        )
        record = make_import_run_record(result, snapshot_version="2026-03")

        assert record.provenance_hash.startswith("import_manifest_")
        assert len(record.provenance_hash) > 20

    def test_to_json_is_valid_json(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="irr3",
        )
        record = make_import_run_record(result)
        import json
        parsed = json.loads(record.to_json())
        assert parsed["schema_version"] == "import_run_v0"

    def test_to_dict_has_all_fields(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="irr4",
        )
        record = make_import_run_record(result, snapshot_version="v0", notes="test")
        d = record.to_dict()

        expected_keys = [
            "schema_version", "run_id", "source_kind", "import_mode",
            "resolved_source_path", "snapshot_version", "destination_tables",
            "files_processed", "files_skipped", "rows_loaded", "rows_skipped",
            "rows_rejected", "import_completeness", "started_at", "completed_at",
            "errors", "warnings", "notes", "provenance_hash",
        ]
        for key in expected_keys:
            assert key in d, f"Key '{key}' missing from ImportRunRecord.to_dict()"

    def test_notes_from_result(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), notes="from result",
        )
        record = make_import_run_record(result)
        assert record.notes == "from result"

    def test_notes_override(self, tmp_path):
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), notes="from result",
        )
        record = make_import_run_record(result, notes="override note")
        assert record.notes == "override note"
