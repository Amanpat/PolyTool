from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from polymarket.resolution import Resolution
from polymarket.resolution_enrichment import (
    DEFAULT_MAX_CANDIDATES,
    enrich_market_resolutions,
    select_resolution_candidates,
)


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


class _SelectionClickhouseClient:
    def __init__(self, all_tokens, lifecycle_tokens, position_tokens=None, positions_total=None):
        self._all_tokens = list(all_tokens)
        self._lifecycle_tokens = list(lifecycle_tokens)
        self._position_tokens = list(position_tokens or [])
        if positions_total is None:
            self._positions_total = len(self._position_tokens)
        else:
            self._positions_total = int(positions_total)

    def query(self, query, parameters=None):
        parameters = parameters or {}
        if "FROM user_positions_snapshots" in query and "countDistinct(token_id)" in query:
            return _FakeResult([[self._positions_total]])
        if "FROM user_positions_snapshots" in query:
            limit = int(parameters.get("limit") or len(self._position_tokens))
            rows = [[token_id] for token_id in self._position_tokens[:limit]]
            return _FakeResult(rows)
        if "countDistinct(resolved_token_id)" in query:
            return _FakeResult([[len(self._all_tokens)]])
        if "FROM user_trade_lifecycle_enriched" in query:
            limit = int(parameters.get("limit") or len(self._lifecycle_tokens))
            rows = [[token_id] for token_id in self._lifecycle_tokens[:limit]]
            return _FakeResult(rows)
        if "FROM user_trade_lifecycle" in query:
            return _FakeResult([])
        if "FROM user_trades_resolved" in query:
            include_tokens = set(parameters.get("include_tokens") or [])
            exclude_tokens = set(parameters.get("exclude_tokens") or [])
            limit = int(parameters.get("limit") or 0)
            if include_tokens:
                ordered = [token for token in self._all_tokens if token in include_tokens]
            else:
                ordered = [token for token in self._all_tokens if token not in exclude_tokens]
            rows = [
                _candidate(
                    token,
                    f"0xcond-{token}",
                    0,
                    market_slug=f"market-{token}",
                    outcome_name="Yes",
                )
                for token in ordered[:limit]
            ]
            return _FakeResult(rows)
        raise AssertionError(f"Unexpected query: {query}")


def test_select_resolution_candidates_prioritizes_lifecycle_tokens_when_truncated():
    all_tokens = [f"tok-{idx:04d}" for idx in range(DEFAULT_MAX_CANDIDATES + 80)]
    lifecycle_priority = ["tok-0579", "tok-0550", "tok-0520"]
    client = _SelectionClickhouseClient(
        all_tokens=all_tokens,
        lifecycle_tokens=lifecycle_priority,
    )

    selection = select_resolution_candidates(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        max_candidates=DEFAULT_MAX_CANDIDATES,
    )

    selected_tokens = [candidate.outcome_token_id for candidate in selection.candidates]

    assert selection.candidates_total == len(all_tokens)
    assert selection.candidates_selected == DEFAULT_MAX_CANDIDATES
    assert selection.truncated is True
    assert selected_tokens[: len(lifecycle_priority)] == lifecycle_priority
    for token_id in lifecycle_priority:
        assert token_id in selected_tokens


def test_select_resolution_candidates_includes_all_when_under_limit():
    """When total candidates <= max_candidates, selection must include ALL tokens (no truncation)."""
    all_tokens = [f"tok-{idx:03d}" for idx in range(50)]
    lifecycle_priority = ["tok-049", "tok-048"]
    client = _SelectionClickhouseClient(
        all_tokens=all_tokens,
        lifecycle_tokens=lifecycle_priority,
    )

    selection = select_resolution_candidates(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        max_candidates=DEFAULT_MAX_CANDIDATES,
    )

    selected_tokens = [candidate.outcome_token_id for candidate in selection.candidates]

    assert selection.candidates_total == 50
    assert selection.candidates_selected == 50
    assert selection.truncated is False
    # All tokens from the universe must be included.
    for token_id in all_tokens:
        assert token_id in selected_tokens


def test_select_resolution_candidates_no_truncation_below_positions_total():
    """Candidate selection must not truncate when max_candidates >= total tokens."""
    total = 200
    all_tokens = [f"tok-{idx:04d}" for idx in range(total)]
    client = _SelectionClickhouseClient(
        all_tokens=all_tokens,
        lifecycle_tokens=[],
    )

    selection = select_resolution_candidates(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        max_candidates=500,
    )

    assert selection.candidates_selected == total
    assert selection.truncated is False
    assert selection.candidates_total == total


def test_select_resolution_candidates_warns_when_token_universe_empty_but_positions_exist():
    all_tokens = [f"tok-{idx:03d}" for idx in range(20)]
    client = _SelectionClickhouseClient(
        all_tokens=all_tokens,
        lifecycle_tokens=[],
        position_tokens=[],
        positions_total=3,
    )

    selection = select_resolution_candidates(
        clickhouse_client=client,
        proxy_wallet="0xwallet",
        max_candidates=10,
    )

    assert selection.lifecycle_token_universe_size_used_for_selection == 0
    assert selection.positions_total == 3
    assert selection.candidates_selected == 10
    assert any("token universe empty; enrichment likely too early" in warning for warning in selection.warnings)
