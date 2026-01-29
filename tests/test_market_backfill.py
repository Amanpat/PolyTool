import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.backfill import backfill_missing_mappings
from polymarket.gamma import Market


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouse:
    def __init__(self):
        self.inserts = []

    def query(self, query, parameters=None):
        if "FROM polyttool.market_tokens" in query:
            return _FakeResult([])
        if "FROM polyttool.token_aliases" in query:
            return _FakeResult([])
        if "FROM polyttool.markets" in query:
            return _FakeResult([])
        return _FakeResult([])

    def insert(self, table, rows, column_names=None):
        self.inserts.append((table, rows, column_names))


class _FakeGamma:
    def __init__(self, market):
        self.market = market
        self.condition_calls = []
        self.token_calls = []
        self.slug_calls = []

    def get_markets_by_condition_ids(self, condition_ids, batch_size=10):
        self.condition_calls.append(condition_ids)
        return [self.market]

    def get_markets_by_clob_token_ids(self, clob_token_ids, batch_size=20):
        self.token_calls.append(clob_token_ids)
        return []

    def get_markets_by_slugs(self, slugs, batch_size=20):
        self.slug_calls.append(slugs)
        return []


class MarketBackfillTests(unittest.TestCase):
    def test_condition_id_backfill_inserts_market_tokens(self):
        market = Market(
            condition_id="0xabc",
            market_slug="test-market",
            question="Test?",
            description="",
            category="",
            tags=[],
            event_slug="",
            event_title="",
            outcomes=["Yes", "No"],
            clob_token_ids=["token_yes", "token_no"],
            alias_token_ids=[],
            enable_order_book=True,
            accepting_orders=True,
            start_date_iso=None,
            end_date_iso=None,
            close_date_iso=None,
            active=True,
            liquidity=0.0,
            volume=0.0,
            raw_json={},
        )
        gamma = _FakeGamma(market)
        clickhouse = _FakeClickhouse()

        stats = backfill_missing_mappings(
            clickhouse_client=clickhouse,
            gamma_client=gamma,
            proxy_wallet="0xabc",
            candidate_condition_ids=["0xABC"],
            request_delay_seconds=0.0,
        )

        self.assertGreater(stats.get("tokens_inserted", 0), 0)
        self.assertGreater(stats.get("markets_inserted", 0), 0)
        self.assertEqual(len(gamma.condition_calls), 1)
        self.assertTrue(any(insert[0] == "market_tokens" for insert in clickhouse.inserts))


if __name__ == "__main__":
    unittest.main()
