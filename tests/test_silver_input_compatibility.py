"""Regression tests for Silver input-loading compatibility fixes.

Covers:
  - price_2min ClickHouse query uses epoch integer timestamps (not ISO strings)
    to avoid HTTP 400 errors from toDateTime() parsing failures.
  - Jon-Becker maker/taker schema (maker_asset_id + taker_asset_id) is detected
    and an OR query is issued instead of failing with token_col=None.
  - Silver close-benchmark path smoke: SilverReconstructor with all three sources
    stubbed returns a valid result with no error.
"""
from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is on sys.path
import sys
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from packages.polymarket.silver_reconstructor import (
    ReconstructConfig,
    SilverReconstructor,
    _real_fetch_jon_fills,
    _real_fetch_price_2min,
)

_TOKEN = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_WIN_START = 1700000000.0   # 2023-11-14T22:13:20Z
_WIN_END   = 1700007200.0   # 2023-11-15T00:13:20Z  (2 hours later)


# ---------------------------------------------------------------------------
# price_2min ClickHouse epoch-integer fix
# ---------------------------------------------------------------------------


class TestPrice2MinEpochQuery:
    """_real_fetch_price_2min must use toDateTime(int) not toDateTime('ISO')."""

    def _make_mock_response(self, rows: List[Dict[str, Any]]):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.text = "\n".join(json.dumps(r) for r in rows)
        return mock_resp

    def test_query_uses_epoch_integers(self):
        """Verify the query string contains toDateTime(int), not toDateTime('...')."""
        captured_queries: List[str] = []

        def _fake_get(url, params=None, auth=None, timeout=None):
            q = (params or {}).get("query", "")
            captured_queries.append(q)
            return self._make_mock_response([])

        with patch("requests.get", side_effect=_fake_get):
            _real_fetch_price_2min(
                token_id=_TOKEN,
                window_start=_WIN_START,
                window_end=_WIN_END,
            )

        assert len(captured_queries) == 1, "Expected exactly one HTTP GET"
        q = captured_queries[0]

        # Must use integer epoch, not ISO string
        assert f"toDateTime({int(_WIN_START)})" in q, (
            f"Query should use toDateTime({int(_WIN_START)}) but got: {q!r}"
        )
        assert f"toDateTime({int(_WIN_END)})" in q, (
            f"Query should use toDateTime({int(_WIN_END)}) but got: {q!r}"
        )

        # Must NOT contain ISO-style timestamps (T separator or +00:00 suffix)
        assert "T" not in q.split("toDateTime")[1], (
            "Query should not contain ISO string with T separator"
        )
        assert "+00:00" not in q, "Query should not contain +00:00 timezone suffix"

    def test_returns_parsed_rows(self):
        """Verify rows are parsed from JSONEachRow response."""
        rows = [
            {"ts": int(_WIN_START) + 120, "price": 0.55},
            {"ts": int(_WIN_START) + 240, "price": 0.56},
        ]

        with patch("requests.get", return_value=self._make_mock_response(rows)):
            result = _real_fetch_price_2min(
                token_id=_TOKEN,
                window_start=_WIN_START,
                window_end=_WIN_END,
            )

        assert result == rows

    def test_returns_empty_on_http_error(self):
        """HTTP errors must return [] not raise."""
        import requests

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("400 Bad Request")

        with patch("requests.get", return_value=mock_resp):
            result = _real_fetch_price_2min(
                token_id=_TOKEN,
                window_start=_WIN_START,
                window_end=_WIN_END,
            )

        assert result == []

    def test_returns_empty_on_connection_error(self):
        """Connection errors must return [] not raise."""
        import requests

        with patch("requests.get", side_effect=requests.ConnectionError("refused")):
            result = _real_fetch_price_2min(
                token_id=_TOKEN,
                window_start=_WIN_START,
                window_end=_WIN_END,
            )

        assert result == []


# ---------------------------------------------------------------------------
# Jon maker/taker schema detection
# ---------------------------------------------------------------------------


def _make_jon_root_with_csv(tmp_path: Path, rows: List[Dict[str, Any]], columns: List[str]) -> str:
    """Create a minimal Jon-Becker directory structure with a CSV file."""
    trades_dir = tmp_path / "data" / "polymarket" / "trades"
    trades_dir.mkdir(parents=True)
    csv_path = trades_dir / "fills.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return str(tmp_path)


class TestJonMakerTakerSchema:
    """_real_fetch_jon_fills must handle the real maker/taker column schema."""

    def test_maker_taker_schema_returns_rows(self, tmp_path):
        """Real Jon-Becker maker/taker schema should return matching rows."""
        duckdb = pytest.importorskip("duckdb", reason="duckdb not installed")

        columns = [
            "block_number", "transaction_hash", "log_index", "order_hash",
            "maker", "taker",
            "maker_asset_id", "taker_asset_id",
            "maker_amount", "taker_amount", "fee",
            "timestamp", "_fetched_at", "_contract",
        ]
        OTHER_TOKEN = "0x" + "b" * 64
        rows = [
            # token is the maker
            {
                "block_number": 1, "transaction_hash": "0xabc", "log_index": 0,
                "order_hash": "0xh1", "maker": "0xmaker", "taker": "0xtaker",
                "maker_asset_id": _TOKEN, "taker_asset_id": OTHER_TOKEN,
                "maker_amount": 100, "taker_amount": 55, "fee": 1,
                "timestamp": "2023-11-14T23:00:00+00:00",
                "_fetched_at": "2023-11-15T00:00:00+00:00", "_contract": "0xctrt",
            },
            # token is the taker
            {
                "block_number": 2, "transaction_hash": "0xdef", "log_index": 0,
                "order_hash": "0xh2", "maker": "0xmaker2", "taker": "0xtaker2",
                "maker_asset_id": OTHER_TOKEN, "taker_asset_id": _TOKEN,
                "maker_amount": 50, "taker_amount": 28, "fee": 0,
                "timestamp": "2023-11-14T23:30:00+00:00",
                "_fetched_at": "2023-11-15T00:00:00+00:00", "_contract": "0xctrt",
            },
            # unrelated row — should be excluded
            {
                "block_number": 3, "transaction_hash": "0xghi", "log_index": 0,
                "order_hash": "0xh3", "maker": "0xmaker3", "taker": "0xtaker3",
                "maker_asset_id": OTHER_TOKEN, "taker_asset_id": OTHER_TOKEN,
                "maker_amount": 10, "taker_amount": 5, "fee": 0,
                "timestamp": "2023-11-14T23:45:00+00:00",
                "_fetched_at": "2023-11-15T00:00:00+00:00", "_contract": "0xctrt",
            },
        ]

        jon_root = _make_jon_root_with_csv(tmp_path, rows, columns)
        result = _real_fetch_jon_fills(
            jon_root=jon_root,
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
        )

        assert len(result) == 2, (
            f"Expected 2 rows (maker+taker), got {len(result)}: {result}"
        )
        returned_order_hashes = {r["order_hash"] for r in result}
        assert returned_order_hashes == {"0xh1", "0xh2"}

    def test_maker_taker_schema_no_false_negatives(self, tmp_path):
        """Does NOT return rows with neither maker_asset_id nor taker_asset_id = token."""
        duckdb = pytest.importorskip("duckdb", reason="duckdb not installed")

        columns = [
            "maker_asset_id", "taker_asset_id", "timestamp",
        ]
        OTHER_TOKEN = "0x" + "c" * 64
        rows = [
            {
                "maker_asset_id": OTHER_TOKEN,
                "taker_asset_id": OTHER_TOKEN,
                "timestamp": "2023-11-14T23:00:00+00:00",
            },
        ]

        jon_root = _make_jon_root_with_csv(tmp_path, rows, columns)
        result = _real_fetch_jon_fills(
            jon_root=jon_root,
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
        )

        assert result == [], f"Expected [], got {result}"

    def test_single_asset_id_schema_still_works(self, tmp_path):
        """Legacy single asset_id column schema still works after the fix."""
        duckdb = pytest.importorskip("duckdb", reason="duckdb not installed")

        columns = ["asset_id", "timestamp", "price", "size", "side"]
        rows = [
            {
                "asset_id": _TOKEN,
                "timestamp": "2023-11-14T23:00:00+00:00",
                "price": 0.55, "size": 10.0, "side": "BUY",
            },
            {
                "asset_id": "0x" + "d" * 64,
                "timestamp": "2023-11-14T23:30:00+00:00",
                "price": 0.60, "size": 5.0, "side": "SELL",
            },
        ]

        jon_root = _make_jon_root_with_csv(tmp_path, rows, columns)
        result = _real_fetch_jon_fills(
            jon_root=jon_root,
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
        )

        assert len(result) == 1
        assert result[0]["asset_id"] == _TOKEN

    def test_no_files_returns_empty(self, tmp_path):
        """Empty directory returns [] without error."""
        (tmp_path / "data" / "polymarket" / "trades").mkdir(parents=True)
        result = _real_fetch_jon_fills(
            jon_root=str(tmp_path),
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
        )
        assert result == []


# ---------------------------------------------------------------------------
# Silver close-benchmark path smoke
# ---------------------------------------------------------------------------


class TestSilverCloseBenchmarkSmoke:
    """SilverReconstructor with all sources stubbed should succeed end-to-end."""

    _PMXT_ROW = {
        "token_id": _TOKEN,
        "snapshot_ts": "2023-11-14T22:00:00+00:00",
        "best_bid": 0.54,
        "best_ask": 0.56,
    }
    _JON_ROWS = [
        {"asset_id": _TOKEN, "timestamp": "2023-11-14T22:30:00+00:00",
         "price": 0.55, "size": 10.0, "side": "BUY"},
    ]
    _PRICE_ROWS = [
        {"ts": int(_WIN_START) + 120, "price": 0.55},
        {"ts": int(_WIN_START) + 240, "price": 0.56},
    ]

    def _make_reconstructor(self):
        config = ReconstructConfig(
            pmxt_root="/fake/pmxt",
            jon_root="/fake/jon",
            skip_price_2min=False,
        )
        return SilverReconstructor(
            config,
            _pmxt_fetch_fn=lambda *_: dict(self._PMXT_ROW),
            _jon_fetch_fn=lambda *_: list(self._JON_ROWS),
            _price_2min_fetch_fn=lambda *_: list(self._PRICE_ROWS),
        )

    def test_reconstruct_returns_no_error(self, tmp_path):
        """reconstruct() completes with no error field."""
        rec = self._make_reconstructor()
        result = rec.reconstruct(
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
            out_dir=tmp_path / "out",
            dry_run=False,
        )
        assert result.error is None, f"Expected no error, got: {result.error}"

    def test_reconstruct_confidence_high(self, tmp_path):
        """All three sources present -> confidence = high."""
        rec = self._make_reconstructor()
        result = rec.reconstruct(
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
            out_dir=tmp_path / "out",
            dry_run=False,
        )
        assert result.reconstruction_confidence == "high", (
            f"Expected 'high', got '{result.reconstruction_confidence}'"
        )

    def test_reconstruct_price_2min_stub_returns_correct_count(self, tmp_path):
        """price_2min rows are counted in result."""
        rec = self._make_reconstructor()
        result = rec.reconstruct(
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
            out_dir=tmp_path / "out",
            dry_run=False,
        )
        assert result.price_2min_count == len(self._PRICE_ROWS), (
            f"Expected {len(self._PRICE_ROWS)} price rows, got {result.price_2min_count}"
        )

    def test_reconstruct_dry_run_no_files_written(self, tmp_path):
        """dry_run=True must not write any files."""
        out_dir = tmp_path / "out"
        rec = self._make_reconstructor()
        rec.reconstruct(
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
            out_dir=out_dir,
            dry_run=True,
        )
        assert not out_dir.exists(), "out_dir should not be created in dry_run mode"

    def test_reconstruct_writes_both_output_files(self, tmp_path):
        """reconstruct() writes silver_events.jsonl and silver_meta.json."""
        out_dir = tmp_path / "out"
        rec = self._make_reconstructor()
        result = rec.reconstruct(
            token_id=_TOKEN,
            window_start=_WIN_START,
            window_end=_WIN_END,
            out_dir=out_dir,
            dry_run=False,
        )
        assert result.events_path is not None and result.events_path.exists()
        assert result.meta_path is not None and result.meta_path.exists()

        meta = json.loads(result.meta_path.read_text())
        assert "reconstruction_confidence" in meta
        assert "event_count" in meta
