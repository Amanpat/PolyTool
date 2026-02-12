from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.resolution import Resolution
from polymarket.resolution_enrichment import enrich_market_resolutions


class _FakeResult:
    def __init__(self, rows):
        self.result_rows = rows


class _FakeClickhouseClient:
    def __init__(self, candidate_rows):
        self._candidate_rows = candidate_rows
        self.insert_calls = []

    def command(self, _sql):
        return None

    def query(self, query, parameters=None):
        if "FROM user_trades_resolved" in query:
            return _FakeResult(self._candidate_rows)
        raise AssertionError(f"Unexpected query: {query}")

    def insert(self, table, rows, column_names=None):
        self.insert_calls.append(
            {
                "table": table,
                "rows": rows,
                "column_names": column_names,
            }
        )


class _FakeCacheProvider:
    def __init__(self, cached):
        self._cached = cached

    def get_resolutions_batch(self, token_ids):
        return {token_id: self._cached[token_id] for token_id in token_ids if token_id in self._cached}


class _FakeProvider:
    def __init__(self, cached, resolved):
        self.clickhouse_provider = _FakeCacheProvider(cached)
        self._resolved = resolved
        self.calls = []

    def get_resolution(
        self,
        condition_id,
        outcome_token_id,
        outcome_index=None,
        skip_clickhouse_cache=False,
    ):
        self.calls.append((condition_id, outcome_token_id, outcome_index))
        return self._resolved.get(outcome_token_id)


def _candidate(token_id: str, condition_id: str, outcome_index, market_slug: str = "", outcome_name: str = ""):
    return [
        token_id,
        condition_id,
        outcome_index,
        market_slug,
        outcome_name,
        datetime(2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc),
    ]


def test_enrichment_writes_resolution_rows_for_uncached_candidates():
    client = _FakeClickhouseClient(
        [
            _candidate("tok-a", "0xcond-a", 0, "market-a", "Yes"),
            _candidate("tok-b", "0xcond-b", 1, "market-b", "No"),
        ]
    )
    provider = _FakeProvider(
        cached={},
        resolved={
            "tok-a": Resolution(
                condition_id="0xcond-a",
                outcome_token_id="tok-a",
                settlement_price=1.0,
                resolved_at=None,
                resolution_source="on_chain_ctf",
                reason="resolved a",
            ),
            "tok-b": Resolution(
                condition_id="0xcond-b",
                outcome_token_id="tok-b",
                settlement_price=0.0,
                resolved_at=None,
                resolution_source="subgraph",
                reason="resolved b",
            ),
        },
    )

    summary = enrich_market_resolutions(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        provider=provider,
        max_candidates=100,
        batch_size=10,
        max_concurrency=2,
    )

    assert summary.candidates_total == 2
    assert summary.candidates_processed == 2
    assert summary.cached_hits == 0
    assert summary.resolved_written == 2
    assert len(provider.calls) == 2
    assert len(client.insert_calls) == 1
    assert client.insert_calls[0]["table"] == "market_resolutions"
    assert len(client.insert_calls[0]["rows"]) == 2


def test_enrichment_uses_cache_and_skips_network_calls():
    client = _FakeClickhouseClient(
        [
            _candidate("tok-a", "0xcond-a", 0, "market-a", "Yes"),
            _candidate("tok-b", "0xcond-b", 1, "market-b", "No"),
        ]
    )
    provider = _FakeProvider(
        cached={
            "tok-a": Resolution(
                condition_id="0xcond-a",
                outcome_token_id="tok-a",
                settlement_price=1.0,
                resolved_at=None,
                resolution_source="clickhouse_cache",
                reason="cached",
            ),
            "tok-b": Resolution(
                condition_id="0xcond-b",
                outcome_token_id="tok-b",
                settlement_price=0.0,
                resolved_at=None,
                resolution_source="clickhouse_cache",
                reason="cached",
            ),
        },
        resolved={},
    )

    summary = enrich_market_resolutions(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        provider=provider,
        max_candidates=100,
        batch_size=10,
        max_concurrency=2,
    )

    assert summary.cached_hits == 2
    assert summary.resolved_written == 0
    assert provider.calls == []
    assert client.insert_calls == []


def test_enrichment_skips_missing_identifiers_with_reason():
    client = _FakeClickhouseClient(
        [
            _candidate("tok-missing-condition", "", 0),
            _candidate("tok-missing-index", "0xcond-x", None),
        ]
    )
    provider = _FakeProvider(cached={}, resolved={})

    summary = enrich_market_resolutions(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        provider=provider,
        max_candidates=100,
        batch_size=10,
        max_concurrency=2,
    )

    assert summary.candidates_total == 2
    assert summary.candidates_processed == 0
    assert summary.skipped_missing_identifiers == 2
    assert summary.skipped_reasons["missing_condition_id"] == 1
    assert summary.skipped_reasons["missing_outcome_index"] == 1
    assert provider.calls == []
    assert client.insert_calls == []
