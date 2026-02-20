import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

import polymarket.backfill as backfill_module
from polymarket.backfill import backfill_missing_mappings
from polymarket.gamma import GammaClient, Market


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouse:
    def __init__(self, existing_taxonomy_by_token=None):
        self.inserts = []
        self.existing_taxonomy_by_token = existing_taxonomy_by_token or {}

    def query(self, query, parameters=None):
        if "argMax(subcategory, ingested_at) AS subcategory" in query:
            tokens = list((parameters or {}).get("tokens", []))
            rows = []
            for token_id in tokens:
                existing = self.existing_taxonomy_by_token.get(str(token_id))
                if not existing:
                    continue
                rows.append([
                    str(token_id),
                    existing.get("category", ""),
                    existing.get("subcategory", ""),
                    existing.get("category_source", "none"),
                    existing.get("subcategory_source", "none"),
                ])
            return _FakeResult(rows)
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


def _market_from_payload() -> Market:
    payload = {
        "conditionId": "0xabc",
        "slug": "test-market",
        "question": "Test?",
        "description": "",
        "category": "Politics",
        "events": [
            {
                "id": "evt-1",
                "slug": "election-2026",
                "category": "Politics",
                "subcategory": "Elections",
            }
        ],
        "outcomes": '["Yes", "No"]',
        "clobTokenIds": '["token_yes", "token_no"]',
        "closed": False,
        "liquidityNum": 0,
        "volumeNum": 0,
    }
    market = GammaClient()._parse_market(payload)
    if market is None:
        raise AssertionError("Expected mock payload to parse into a Market")
    return market


class MarketBackfillTests(unittest.TestCase):
    def setUp(self):
        backfill_module._BACKFILL_CACHE.clear()

    def test_condition_id_backfill_inserts_market_tokens(self):
        market = _market_from_payload()
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
        market_tokens_insert = next(
            (insert for insert in clickhouse.inserts if insert[0] == "market_tokens"),
            None,
        )
        self.assertIsNotNone(market_tokens_insert)
        _, rows, column_names = market_tokens_insert
        self.assertIn("category", column_names)
        self.assertIn("subcategory", column_names)
        self.assertIn("category_source", column_names)
        self.assertIn("subcategory_source", column_names)
        category_index = column_names.index("category")
        subcategory_index = column_names.index("subcategory")
        category_source_index = column_names.index("category_source")
        subcategory_source_index = column_names.index("subcategory_source")
        self.assertEqual(rows[0][category_index], "Politics")
        self.assertEqual(rows[0][subcategory_index], "Elections")
        self.assertEqual(rows[0][category_source_index], "market")
        self.assertEqual(rows[0][subcategory_source_index], "event")

    def test_condition_id_backfill_does_not_overwrite_existing_taxonomy(self):
        market = _market_from_payload()
        gamma = _FakeGamma(market)
        clickhouse = _FakeClickhouse(
            existing_taxonomy_by_token={
                "token_yes": {
                    "category": "ExistingCategory",
                    "subcategory": "ExistingSubcategory",
                    "category_source": "event",
                    "subcategory_source": "event",
                },
            }
        )

        stats = backfill_missing_mappings(
            clickhouse_client=clickhouse,
            gamma_client=gamma,
            proxy_wallet="0xabc",
            candidate_condition_ids=["0xABC"],
            request_delay_seconds=0.0,
        )

        self.assertGreater(stats.get("tokens_inserted", 0), 0)
        market_tokens_insert = next(
            (insert for insert in clickhouse.inserts if insert[0] == "market_tokens"),
            None,
        )
        self.assertIsNotNone(market_tokens_insert)
        _, rows, column_names = market_tokens_insert

        category_index = column_names.index("category")
        subcategory_index = column_names.index("subcategory")
        category_source_index = column_names.index("category_source")
        subcategory_source_index = column_names.index("subcategory_source")
        token_index = column_names.index("token_id")
        row_by_token = {row[token_index]: row for row in rows}

        self.assertEqual(
            row_by_token["token_yes"][category_index],
            "ExistingCategory",
        )
        self.assertEqual(
            row_by_token["token_yes"][subcategory_index],
            "ExistingSubcategory",
        )
        self.assertEqual(
            row_by_token["token_yes"][category_source_index],
            "event",
        )
        self.assertEqual(
            row_by_token["token_yes"][subcategory_source_index],
            "event",
        )
        self.assertEqual(row_by_token["token_no"][category_index], "Politics")
        self.assertEqual(row_by_token["token_no"][subcategory_index], "Elections")

    def test_parse_market_prefers_top_level_category(self):
        payload = {
            "conditionId": "0xshape1",
            "slug": "shape-1",
            "question": "Shape 1?",
            "category": "Sports",
            "outcomes": '["Yes", "No"]',
            "clobTokenIds": '["shape1_yes", "shape1_no"]',
            "closed": False,
        }
        market = GammaClient()._parse_market(payload)
        self.assertIsNotNone(market)
        assert market is not None
        self.assertEqual(market.category, "Sports")
        self.assertEqual(market.category_source, "market")
        self.assertEqual(market.subcategory, "")
        self.assertEqual(market.subcategory_source, "none")

    def test_parse_market_uses_events_when_market_category_empty(self):
        payload = {
            "conditionId": "0xshape2",
            "slug": "shape-2",
            "question": "Shape 2?",
            "category": "",
            "events": [
                {
                    "id": "evt-shape2",
                    "slug": "evt-shape2",
                    "category": "Politics",
                    "subcategory": "Elections",
                }
            ],
            "outcomes": '["Yes", "No"]',
            "clobTokenIds": '["shape2_yes", "shape2_no"]',
            "closed": False,
        }
        market = GammaClient()._parse_market(payload)
        self.assertIsNotNone(market)
        assert market is not None
        self.assertEqual(market.category, "Politics")
        self.assertEqual(market.category_source, "event")
        self.assertEqual(market.subcategory, "Elections")
        self.assertEqual(market.subcategory_source, "event")

    def test_parse_market_leaves_taxonomy_empty_when_unavailable(self):
        payload = {
            "conditionId": "0xshape3",
            "slug": "shape-3",
            "question": "Shape 3?",
            "category": "",
            "outcomes": '["Yes", "No"]',
            "clobTokenIds": '["shape3_yes", "shape3_no"]',
            "closed": False,
        }
        market = GammaClient()._parse_market(payload)
        self.assertIsNotNone(market)
        assert market is not None
        self.assertEqual(market.category, "")
        self.assertEqual(market.category_source, "none")
        self.assertEqual(market.subcategory, "")
        self.assertEqual(market.subcategory_source, "none")

    def test_fetch_all_markets_backfills_taxonomy_from_events_endpoint(self):
        class _FakeHttp:
            def __init__(self):
                self.calls = []
                self.base_url = "https://gamma-api.polymarket.com"

            def get_json(self, path, params=None):
                self.calls.append((path, params))
                if path == "/markets":
                    return [
                        {
                            "conditionId": "0xevtfallback",
                            "slug": "event-fallback-market",
                            "question": "Fallback?",
                            "category": "",
                            "events": [{"id": "evt-42", "slug": "evt-42"}],
                            "outcomes": '["Yes", "No"]',
                            "clobTokenIds": '["evt_yes", "evt_no"]',
                            "closed": False,
                        }
                    ]
                if path == "/events":
                    return [
                        {
                            "id": "evt-42",
                            "slug": "evt-42",
                            "category": "Politics",
                            "subcategory": "Elections",
                        }
                    ]
                raise AssertionError(f"unexpected path: {path}")

        gamma = GammaClient()
        gamma.client = _FakeHttp()
        result = gamma.fetch_all_markets(max_pages=1, capture_debug_sample=True)
        self.assertEqual(result.total_markets, 1)
        self.assertEqual(len(result.market_tokens), 2)
        self.assertEqual(result.markets[0].category, "Politics")
        self.assertEqual(result.markets[0].subcategory, "Elections")
        self.assertEqual(result.markets[0].category_source, "event")
        self.assertEqual(result.markets[0].subcategory_source, "event")


if __name__ == "__main__":
    unittest.main()
