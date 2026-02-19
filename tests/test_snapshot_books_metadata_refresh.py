import asyncio
import os
import sys
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi")
pytestmark = pytest.mark.optional_dep

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.api import main


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouseClient:
    def __init__(self, metadata_rows_by_call):
        self.metadata_rows_by_call = metadata_rows_by_call
        self.metadata_calls = 0

    def query(self, query, parameters=None):
        if "FROM user_positions_snapshots" in query:
            return _FakeResult([])
        if "FROM user_trades" in query and "GROUP BY token_id" in query:
            return _FakeResult([[
                "token1",
                "0xabc",
                "Yes",
                datetime(2026, 1, 1, 0, 0, 0),
            ]])
        if "FROM market_tokens mt" in query and "LEFT JOIN markets_enriched" in query:
            if self.metadata_calls < len(self.metadata_rows_by_call):
                rows = self.metadata_rows_by_call[self.metadata_calls]
            else:
                rows = []
            self.metadata_calls += 1
            return _FakeResult(rows)
        if "SELECT count() FROM market_tokens" in query:
            return _FakeResult([[1]])
        return _FakeResult([])

    def insert(self, *args, **kwargs):
        return None


class SnapshotBooksMetadataRefreshTests(unittest.TestCase):
    def _run_snapshot(self, client, backfill_stats):
        request = main.SnapshotBooksRequest(
            user="@tester",
            max_tokens=1,
            lookback_days=90,
            require_active_market=True,
            include_inactive=False,
        )

        with patch.object(main, "get_clickhouse_client", return_value=client), \
            patch.object(
                main.gamma_client,
                "resolve",
                return_value=SimpleNamespace(proxy_wallet="0xabc", username="@tester", raw_json={}),
            ), \
            patch.object(main, "backfill_missing_mappings", return_value=backfill_stats), \
            patch.object(main, "BOOK_SNAPSHOT_MAX_PREFLIGHT", 0), \
            patch.object(main, "BOOK_SNAPSHOT_404_TTL_HOURS", 0):
            return asyncio.run(main.snapshot_books(request))

    def test_metadata_requery_after_backfill(self):
        metadata_rows = [
            [],
            [["token1", 1, 1, 1, 1, datetime.utcnow() + timedelta(days=1)]],
        ]
        client = _FakeClickhouseClient(metadata_rows)
        response = self._run_snapshot(
            client,
            {"missing_found": 1, "markets_fetched": 1, "tokens_inserted": 1},
        )

        self.assertEqual(response.backfill_tokens_inserted, 1)
        self.assertEqual(response.tokens_with_market_metadata, 1)
        self.assertEqual(response.tokens_after_active_filter, 1)
        self.assertEqual(response.tokens_selected_total, 1)

    def test_backfill_inserted_but_metadata_still_missing_sets_reason(self):
        metadata_rows = [[], []]
        client = _FakeClickhouseClient(metadata_rows)
        response = self._run_snapshot(
            client,
            {"missing_found": 1, "markets_fetched": 1, "tokens_inserted": 1},
        )

        self.assertEqual(response.tokens_with_market_metadata, 0)
        self.assertIsNotNone(response.no_ok_reason)
        self.assertIn("Backfill inserted tokens but metadata join still returned 0", response.no_ok_reason)


if __name__ == "__main__":
    unittest.main()
