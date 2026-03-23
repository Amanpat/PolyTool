"""Tests for packages/polymarket/historical_import/importer.py (Packet 2)."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
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


def _make_jb_fixture_csv(
    root: Path,
    rows: int = 5,
    *,
    filename: str = "trades_2024.csv",
    start_index: int = 0,
) -> Path:
    """Create a minimal Jon-Becker CSV fixture."""
    trades_dir = root / "data" / "polymarket" / "trades"
    trades_dir.mkdir(parents=True, exist_ok=True)
    csv_file = trades_dir / filename
    with open(str(csv_file), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["timestamp", "market_id", "token_id", "price", "size",
                        "taker_side", "resolution", "category"],
        )
        writer.writeheader()
        for i in range(start_index, start_index + rows):
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


def _assert_dry_run_result(
    result: ImportResult,
    client: MockCHClient,
    *,
    source_kind: str,
    destination_table: str,
    files_processed: int,
) -> None:
    assert result.source_kind == source_kind
    assert result.import_completeness == "dry-run"
    assert result.destination_tables == [destination_table]
    assert result.files_processed == files_processed
    assert result.rows_attempted == 0
    assert result.errors == []
    assert result.started_at != ""
    assert result.completed_at != ""
    assert client.calls == []


def _assert_single_sample_insert(
    client: MockCHClient,
    *,
    table: str,
    expected_rows: int,
    distinct_column: str,
) -> None:
    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["table"] == table
    assert len(call["rows"]) == expected_rows
    distinct_idx = call["column_names"].index(distinct_column)
    assert len({row[distinct_idx] for row in call["rows"]}) == 1


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

        _assert_dry_run_result(
            result,
            client,
            source_kind="pmxt_archive",
            destination_table="polytool.pmxt_l2_snapshots",
            files_processed=1,
        )

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

        assert result.rows_attempted == 0

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

        _assert_dry_run_result(
            result,
            client,
            source_kind="jon_becker",
            destination_table="polytool.jb_trades",
            files_processed=1,
        )

    def test_jb_dry_run_completeness(self, tmp_path):
        _make_jb_fixture_csv(tmp_path)
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="r2")

        assert result.import_completeness == "dry-run"
        assert result.rows_attempted == 0
        assert result.files_processed >= 1

    def test_price_history_dry_run_no_ch_calls(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_abc", "tok_def"])
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=client, run_id="r3")

        _assert_dry_run_result(
            result,
            client,
            source_kind="price_history_2min",
            destination_table="polytool.price_history_2min",
            files_processed=2,
        )

    def test_price_history_dry_run_completeness(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_abc"])
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.DRY_RUN, ch_client=MockCHClient(), run_id="r3")

        assert result.import_completeness == "dry-run"
        assert result.rows_attempted == 0
        assert result.files_processed == 1
        assert result.started_at != ""
        assert result.completed_at != ""


# ---------------------------------------------------------------------------
# TestPmxtImporter
# ---------------------------------------------------------------------------


class TestPmxtImporter:
    def test_empty_string_timestamp_rejected(self, tmp_path):
        importer = PmxtImporter(str(tmp_path))

        with pytest.raises(ValueError, match="missing snapshot_ts"):
            importer._row_from_record(
                {
                    "timestamp": "",
                    "market_id": "m1",
                    "token_id": "t1",
                    "side": "buy",
                    "price": "0.51",
                    "size": "100",
                },
                "polymarket",
                "fixture.parquet",
                "pmxt-empty",
            )

    def test_whitespace_timestamp_rejected(self, tmp_path):
        importer = PmxtImporter(str(tmp_path))

        with pytest.raises(ValueError, match="missing snapshot_ts"):
            importer._row_from_record(
                {
                    "timestamp": "   ",
                    "market_id": "m1",
                    "token_id": "t1",
                    "side": "buy",
                    "price": "0.51",
                    "size": "100",
                },
                "polymarket",
                "fixture.parquet",
                "pmxt-space",
            )

    def test_valid_timestamp_normalized_to_utc_datetime(self, tmp_path):
        importer = PmxtImporter(str(tmp_path))

        row = importer._row_from_record(
            {
                "timestamp_received": " 2026-03-15T10:00:27.343Z ",
                "market_id": "m1",
                "token_id": "t1",
                "side": "buy",
                "price": "0.51",
                "size": "100",
            },
            "polymarket",
            "fixture.parquet",
            "pmxt-valid",
        )

        assert row[0] == datetime(2026, 3, 15, 10, 0, 27, 343000, tzinfo=timezone.utc)

    def test_bad_row_does_not_abort_good_rows_in_same_file(self, tmp_path, monkeypatch):
        _make_pmxt_fixture(tmp_path)
        records = [
            {
                "timestamp_received": "",
                "market_id": "m_bad",
                "token_id": "t_bad",
                "side": "buy",
                "price": "0.40",
                "size": "50",
            },
            {
                "timestamp_received": "2026-03-15T10:00:27.343Z",
                "market_id": "m_good_1",
                "token_id": "t_good_1",
                "side": "buy",
                "price": "0.51",
                "size": "100",
            },
            {
                "timestamp_received": "2026-03-15T10:01:27.343Z",
                "market_id": "m_good_2",
                "token_id": "t_good_2",
                "side": "sell",
                "price": "0.49",
                "size": "120",
            },
        ]
        monkeypatch.setattr(
            "packages.polymarket.historical_import.importer._read_parquet_rows",
            lambda _path: iter(records),
        )

        client = MockCHClient()
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(ImportMode.FULL, ch_client=client, run_id="pmxt-mixed")

        assert result.rows_attempted == 2
        assert result.rows_rejected == 1
        assert result.import_completeness == "partial"
        assert len(client.calls) == 1
        assert len(client.calls[0]["rows"]) == 2
        assert "rejected 1 row(s) with invalid snapshot_ts" in result.errors[0]
        assert "row 1: missing snapshot_ts" in result.errors[0]

    def test_sample_import_continues_after_first_invalid_timestamp(self, tmp_path, monkeypatch):
        _make_pmxt_fixture(tmp_path)
        records = [
            {
                "timestamp_received": "   ",
                "timestamp_created_at": None,
                "market_id": "m_bad",
            },
            {
                "timestamp_received": datetime(2026, 3, 15, 10, 0, 27, 343000, tzinfo=timezone.utc),
                "timestamp_created_at": datetime(2026, 3, 15, 10, 0, 27, 369000, tzinfo=timezone.utc),
                "market_id": "m_good_1",
            },
            {
                "timestamp_received": datetime(2026, 3, 15, 10, 2, 26, 286000, tzinfo=timezone.utc),
                "timestamp_created_at": datetime(2026, 3, 15, 10, 2, 26, 303000, tzinfo=timezone.utc),
                "market_id": "m_good_2",
            },
        ]
        monkeypatch.setattr(
            "packages.polymarket.historical_import.importer._read_parquet_rows",
            lambda _path: iter(records),
        )

        client = MockCHClient()
        importer = PmxtImporter(str(tmp_path))
        result = importer.run(
            ImportMode.SAMPLE,
            ch_client=client,
            run_id="pmxt-sample",
            sample_rows=2,
        )

        assert result.rows_attempted == 2
        assert result.rows_rejected == 1
        assert result.import_completeness == "partial"
        assert len(client.calls) == 1
        assert len(client.calls[0]["rows"]) == 2
        assert client.calls[0]["rows"][0][0] == datetime(
            2026, 3, 15, 10, 0, 27, 343000, tzinfo=timezone.utc
        )


# ---------------------------------------------------------------------------
# TestJonBeckerImporterCSV
# ---------------------------------------------------------------------------


class TestJonBeckerImporterTimestamps:
    @pytest.mark.parametrize("timestamp_value", [None, "None", "", "   "])
    def test_null_like_timestamp_rejected_without_fallback(self, tmp_path, timestamp_value):
        importer = JonBeckerImporter(str(tmp_path))

        with pytest.raises(ValueError, match="missing ts"):
            importer._row_from_record(
                {"timestamp": timestamp_value, "market_id": "m1", "token_id": "t1"},
                "fixture.csv",
                "jb-null-like",
            )

    def test_valid_timestamp_normalized_to_utc_datetime(self, tmp_path):
        importer = JonBeckerImporter(str(tmp_path))

        row = importer._row_from_record(
            {
                "timestamp": "1700000000",
                "market_id": "m1",
                "token_id": "t1",
            },
            "fixture.csv",
            "jb-valid",
        )

        assert row[0] == datetime.fromtimestamp(1700000000, tz=timezone.utc)

    def test_missing_primary_timestamp_uses_fetched_at_fallback(self, tmp_path):
        importer = JonBeckerImporter(str(tmp_path))

        row = importer._row_from_record(
            {
                "timestamp": None,
                "_fetched_at": datetime(2026, 1, 29, 15, 48, 12, 728779),
                "market_id": "m1",
                "token_id": "t1",
            },
            "fixture.parquet",
            "jb-fallback",
        )

        assert row[0] == datetime(2026, 1, 29, 15, 48, 12, 728779, tzinfo=timezone.utc)

    def test_bad_row_does_not_abort_good_rows_in_same_file(self, tmp_path, monkeypatch):
        _make_jb_fixture_csv(tmp_path, rows=1)
        records = [
            {"timestamp": "   ", "market_id": "m_bad", "token_id": "t_bad"},
            {"timestamp": "1700000000", "market_id": "m_good_1", "token_id": "t_good_1"},
            {
                "timestamp": None,
                "_fetched_at": datetime(2026, 1, 29, 15, 48, 12, 728779),
                "market_id": "m_good_2",
                "token_id": "t_good_2",
            },
        ]
        monkeypatch.setattr(
            JonBeckerImporter,
            "_iter_file",
            lambda self, _path: iter(records),
        )

        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.FULL, ch_client=client, run_id="jb-mixed")

        assert result.rows_attempted == 2
        assert result.rows_rejected == 1
        assert result.import_completeness == "partial"
        assert len(client.calls) == 1
        assert len(client.calls[0]["rows"]) == 2
        assert client.calls[0]["rows"][0][0] == datetime.fromtimestamp(
            1700000000, tz=timezone.utc
        )
        assert "rejected 1 row(s) with invalid ts" in result.errors[0]
        assert "row 1: missing ts" in result.errors[0]

    def test_sample_import_continues_after_first_invalid_timestamp(self, tmp_path, monkeypatch):
        _make_jb_fixture_csv(tmp_path, rows=1)
        records = [
            {"timestamp": "None", "market_id": "m_bad", "token_id": "t_bad"},
            {"timestamp": "1700000000", "market_id": "m_good_1", "token_id": "t_good_1"},
            {
                "timestamp": None,
                "_fetched_at": datetime(2026, 1, 29, 15, 48, 12, 728779),
                "market_id": "m_good_2",
                "token_id": "t_good_2",
            },
        ]
        monkeypatch.setattr(
            JonBeckerImporter,
            "_iter_file",
            lambda self, _path: iter(records),
        )

        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(
            ImportMode.SAMPLE,
            ch_client=client,
            run_id="jb-sample-mixed",
            sample_rows=2,
        )

        assert result.rows_attempted == 2
        assert result.rows_rejected == 1
        assert result.import_completeness == "partial"
        assert len(client.calls) == 1
        assert len(client.calls[0]["rows"]) == 2
        assert client.calls[0]["rows"][0][0] == datetime.fromtimestamp(
            1700000000, tz=timezone.utc
        )
        assert client.calls[0]["rows"][1][0] == datetime(
            2026, 1, 29, 15, 48, 12, 728779, tzinfo=timezone.utc
        )


class TestJonBeckerImporterCSV:
    """JonBecker importer in sample mode with real CSV fixture."""

    def test_sample_rows_loaded(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=10)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="jb1", sample_rows=5)

        assert result.rows_attempted == 5

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

        assert result.rows_attempted == n_rows

    def test_sample_limit_loads_single_file_subset(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=5, filename="trades_a.csv", start_index=0)
        _make_jb_fixture_csv(tmp_path, rows=5, filename="trades_b.csv", start_index=10)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="jb4b", sample_rows=3)

        assert result.import_completeness == "complete"
        assert result.rows_attempted == 3
        _assert_single_sample_insert(
            client,
            table="polytool.jb_trades",
            expected_rows=3,
            distinct_column="source_file",
        )

    def test_full_mode_rows_loaded(self, tmp_path):
        _make_jb_fixture_csv(tmp_path, rows=5)
        client = MockCHClient()
        importer = JonBeckerImporter(str(tmp_path))
        result = importer.run(ImportMode.FULL, ch_client=client, run_id="jb5")

        assert result.rows_attempted == 5
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

        assert result.rows_attempted > 0

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

    def test_sample_limit_loads_single_token_subset(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_a", "tok_b"], rows_per=5)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.SAMPLE, ch_client=client, run_id="ph3b", sample_rows=2)

        assert result.import_completeness == "complete"
        assert result.rows_attempted == 2
        _assert_single_sample_insert(
            client,
            table="polytool.price_history_2min",
            expected_rows=2,
            distinct_column="token_id",
        )

    def test_full_mode_multi_file(self, tmp_path):
        _make_price_history_fixture(tmp_path, ["tok_a", "tok_b", "tok_c"], rows_per=4)
        client = MockCHClient()
        importer = PriceHistoryImporter(str(tmp_path))
        result = importer.run(ImportMode.FULL, ch_client=client, run_id="ph4")

        assert result.rows_attempted == 12  # 3 files * 4 rows
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
            "rows_attempted", "rows_skipped", "rows_rejected",
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
            "files_processed", "files_skipped", "rows_attempted", "rows_skipped",
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

    def test_provenance_hash_deterministic_across_non_manifest_fields(self, tmp_path):
        resolved = str(tmp_path.resolve())
        left = ImportResult(
            source_kind="pmxt_archive",
            import_mode="dry-run",
            run_id="irr5a",
            resolved_source_path=resolved,
            destination_tables=[
                "polytool.pmxt_l2_snapshots",
                "artifacts/imports/pmxt_manifest.json",
            ],
            import_completeness="dry-run",
            started_at="2026-03-13T00:00:00+00:00",
            completed_at="2026-03-13T00:00:01+00:00",
            notes="first note",
        )
        right = ImportResult(
            source_kind="pmxt_archive",
            import_mode="dry-run",
            run_id="irr5b",
            resolved_source_path=resolved,
            destination_tables=[
                "artifacts/imports/pmxt_manifest.json",
                "polytool.pmxt_l2_snapshots",
            ],
            import_completeness="dry-run",
            started_at="2026-03-14T00:00:00+00:00",
            completed_at="2026-03-14T00:00:01+00:00",
            notes="second note",
        )

        left_record = make_import_run_record(left, snapshot_version="2026-03")
        right_record = make_import_run_record(right, snapshot_version="2026-03")

        assert left_record.provenance_hash == right_record.provenance_hash


# ---------------------------------------------------------------------------
# TestPmxtRowsAttemptedAccounting
# Regression suite for the rows_attempted metric.
#
# Root cause of the pmxt_full_batch1 discrepancy (2026-03-15):
#   run record: rows_attempted = 78,264,878
#   SELECT count(*) FROM pmxt_l2_snapshots: 35,498,946
#
# rows_attempted = rows sent to ch_client.insert_rows(), i.e. len(rows_batch).
# ClickHouse reports fewer rows because ReplacingMergeTree(imported_at) merges
# rows sharing the same ORDER BY key (platform, market_id, token_id, side,
# price, snapshot_ts) in the background. This is expected and correct; the
# metric name "rows_attempted" now truthfully captures what was sent.
# ---------------------------------------------------------------------------


class TestPmxtRowsAttemptedAccounting:
    """rows_attempted = rows sent to insert(); rows_rejected = rows skipped before insert."""

    def test_all_valid_rows_counted_in_rows_attempted(self, tmp_path, monkeypatch):
        """rows_attempted equals the total valid row count sent to CH."""
        _make_pmxt_fixture(tmp_path)
        records = [
            {
                "timestamp_received": datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
                "market_id": "m1", "token_id": "t1", "side": "buy",
                "price": "0.50", "size": "100",
            },
            {
                "timestamp_received": datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
                "market_id": "m1", "token_id": "t1", "side": "ask",
                "price": "0.51", "size": "150",
            },
            {
                "timestamp_received": datetime(2026, 3, 15, 11, 0, 0, tzinfo=timezone.utc),
                "market_id": "m1", "token_id": "t1", "side": "buy",
                "price": "0.50", "size": "100",
            },
        ]
        monkeypatch.setattr(
            "packages.polymarket.historical_import.importer._read_parquet_rows",
            lambda _path: iter(records),
        )
        client = MockCHClient()
        result = PmxtImporter(str(tmp_path)).run(
            ImportMode.FULL, ch_client=client, run_id="ra-all-valid"
        )

        assert result.rows_attempted == 3
        assert result.rows_rejected == 0

    def test_rows_attempted_excludes_rejected_invalid_ts_rows(self, tmp_path, monkeypatch):
        """rows_attempted does not count rows rejected before the insert batch."""
        _make_pmxt_fixture(tmp_path)
        records = [
            # invalid — will be rejected
            {"timestamp_received": "", "market_id": "bad", "token_id": "tbad"},
            # valid
            {
                "timestamp_received": datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
                "market_id": "m1", "token_id": "t1", "side": "buy",
                "price": "0.50", "size": "100",
            },
            # invalid — will be rejected
            {"timestamp_received": "nat", "market_id": "bad2", "token_id": "tbad2"},
            # valid
            {
                "timestamp_received": datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
                "market_id": "m2", "token_id": "t2", "side": "ask",
                "price": "0.51", "size": "200",
            },
        ]
        monkeypatch.setattr(
            "packages.polymarket.historical_import.importer._read_parquet_rows",
            lambda _path: iter(records),
        )
        client = MockCHClient()
        result = PmxtImporter(str(tmp_path)).run(
            ImportMode.FULL, ch_client=client, run_id="ra-mixed"
        )

        assert result.rows_attempted == 2
        assert result.rows_rejected == 2
        assert result.rows_attempted + result.rows_rejected == 4

    def test_rows_attempted_counts_duplicate_key_rows_sent_to_ch(self, tmp_path, monkeypatch):
        """rows_attempted equals sent rows even when CH would deduplicate via ReplacingMergeTree.

        This models the production scenario: pmxt_full_batch1 sent 78,264,878 rows
        to CH insert() but SELECT count(*) returned 35,498,946 because background
        merges deduplicated rows with matching (platform, market_id, token_id, side,
        price, snapshot_ts). rows_attempted correctly reports what was sent, not
        what CH persists post-merge.
        """
        _make_pmxt_fixture(tmp_path)
        # Same (market_id, token_id, side, price, snapshot_ts) across 5 records —
        # CH ReplacingMergeTree would keep only 1 after a merge.
        ts = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
        duplicate_records = [
            {
                "timestamp_received": ts,
                "market_id": "mX", "token_id": "tX", "side": "buy",
                "price": "0.50", "size": str(100 + i),
            }
            for i in range(5)
        ]
        monkeypatch.setattr(
            "packages.polymarket.historical_import.importer._read_parquet_rows",
            lambda _path: iter(duplicate_records),
        )
        client = MockCHClient()
        result = PmxtImporter(str(tmp_path)).run(
            ImportMode.FULL, ch_client=client, run_id="ra-dedup"
        )

        # All 5 rows were sent to CH insert() — rows_attempted is truthful
        assert result.rows_attempted == 5
        # MockCHClient received 5 rows (it does not deduplicate, unlike CH)
        assert len(client.calls) == 1
        assert len(client.calls[0]["rows"]) == 5
        # rows_rejected = 0: all rows had valid timestamps
        assert result.rows_rejected == 0

    def test_run_record_rows_attempted_matches_import_result(self, tmp_path, monkeypatch):
        """ImportRunRecord.rows_attempted mirrors ImportResult.rows_attempted exactly."""
        _make_pmxt_fixture(tmp_path)
        records = [
            {
                "timestamp_received": datetime(2026, 3, 15, 10, i, 0, tzinfo=timezone.utc),
                "market_id": f"m{i}", "token_id": f"t{i}", "side": "buy",
                "price": str(0.5 + i * 0.01), "size": "100",
            }
            for i in range(7)
        ]
        monkeypatch.setattr(
            "packages.polymarket.historical_import.importer._read_parquet_rows",
            lambda _path: iter(records),
        )
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.FULL,
            ch_client=MockCHClient(), run_id="ra-record",
        )
        record = make_import_run_record(result, snapshot_version="2026-03")

        assert record.rows_attempted == result.rows_attempted == 7
        assert record.rows_rejected == result.rows_rejected == 0

    def test_rows_attempted_field_present_in_to_dict(self, tmp_path):
        """rows_attempted appears in ImportResult.to_dict() output."""
        _make_pmxt_fixture(tmp_path)
        result = run_import(
            "pmxt_archive", str(tmp_path), ImportMode.DRY_RUN,
            ch_client=MockCHClient(), run_id="ra-dict",
        )
        d = result.to_dict()
        assert "rows_attempted" in d
        assert "rows_loaded" not in d, "old field name must not appear"
