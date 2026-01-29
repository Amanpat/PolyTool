import asyncio
import os
import sys
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from services.api import main
from polymarket.opportunities import get_opportunity_bucket_start, normalize_bucket_type


class OpportunitiesBucketingTests(unittest.TestCase):
    def test_opportunity_bucket_start_week(self) -> None:
        sample_dt = datetime(2026, 1, 15, 13, 45, 0)
        bucket_start = get_opportunity_bucket_start(sample_dt, "week")
        self.assertEqual(bucket_start, datetime(2026, 1, 12, 0, 0, 0))

    def test_normalize_bucket_type_invalid(self) -> None:
        with self.assertRaises(ValueError):
            normalize_bucket_type("month")


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouseClient:
    def __init__(self):
        self.inserted_rows = []

    def query(self, query, parameters=None):
        if "FROM user_trades_resolved" in query:
            return _FakeResult([["tokenA"], ["tokenB"]])
        if "orderbook_snapshots_enriched" in query:
            return _FakeResult([
                ["tokenA", "market-a", "Question A", "Yes", 45.0, 600.0, 700.0, "HIGH", "ok"],
                ["tokenB", "market-b", "Question B", "No", 80.0, 300.0, 400.0, "MED", "ok"],
            ])
        return _FakeResult([])

    def insert(self, table, rows, column_names=None):
        self.inserted_rows = rows


class OpportunitiesApiTests(unittest.TestCase):
    def test_compute_opportunities_response_shape(self) -> None:
        client = _FakeClickhouseClient()
        request = main.ComputeOpportunitiesRequest(user="@tester", bucket="day", limit=10)

        with patch.object(main, "get_clickhouse_client", return_value=client), patch.object(
            main.gamma_client,
            "resolve",
            return_value=SimpleNamespace(proxy_wallet="0xabc", username="@tester", raw_json={}),
        ):
            response = asyncio.run(main.compute_opportunities(request))

        self.assertEqual(response.proxy_wallet, "0xabc")
        self.assertEqual(response.bucket_type, "day")
        self.assertEqual(response.candidates_considered, 2)
        self.assertEqual(response.returned_count, 2)
        self.assertEqual(response.buckets_written, 1)
        self.assertIsInstance(response.bucket_start, datetime)
        self.assertEqual(len(client.inserted_rows), 2)


if __name__ == "__main__":
    unittest.main()
