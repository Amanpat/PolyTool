"""Tests for crypto pair market discovery functions."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from packages.polymarket.crypto_pairs.market_discovery import (
    CryptoPairMarket,
    _generate_5m_slugs,
    discover_updown_5m_markets,
    discover_crypto_pair_markets,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_market(
    slug: str = "btc-updown-5m-123",
    question: str = "Will BTC go up in the next 5m?",
    condition_id: str = "cond-001",
    clob_token_ids: list[str] | None = None,
    outcomes: list[str] | None = None,
    active: bool = True,
    accepting_orders: bool | None = True,
) -> MagicMock:
    """Return a MagicMock that looks like a ``packages.polymarket.gamma.Market``."""
    m = MagicMock()
    m.market_slug = slug
    m.question = question
    m.condition_id = condition_id
    m.clob_token_ids = clob_token_ids if clob_token_ids is not None else ["token-yes", "token-no"]
    m.outcomes = outcomes if outcomes is not None else ["Up", "Down"]
    m.active = active
    m.accepting_orders = accepting_orders
    m.end_date_iso = None
    return m


# ---------------------------------------------------------------------------
# _generate_5m_slugs
# ---------------------------------------------------------------------------

class TestGenerate5mSlugs:
    def test_returns_correct_format(self):
        slugs = _generate_5m_slugs(symbols=["btc"], lookahead_slots=0)
        assert len(slugs) == 1
        slug = slugs[0]
        # Format: {sym}-updown-5m-{unix_timestamp}
        parts = slug.split("-")
        assert parts[0] == "btc"
        assert parts[1] == "updown"
        assert parts[2] == "5m"
        ts = int(parts[3])
        # Timestamp must be aligned to 300-second boundary
        assert ts % 300 == 0

    def test_default_symbols_are_btc_eth_sol(self):
        slugs = _generate_5m_slugs(lookahead_slots=0)
        symbols = {s.split("-")[0] for s in slugs}
        assert symbols == {"btc", "eth", "sol"}

    def test_lookahead_count(self):
        # lookahead_slots=2 => 3 slots (current + 2 ahead) × 3 symbols = 9
        slugs = _generate_5m_slugs(lookahead_slots=2)
        assert len(slugs) == 9

    def test_default_lookahead_count(self):
        # Default lookahead_slots=3 => 4 slots × 3 symbols = 12
        slugs = _generate_5m_slugs()
        assert len(slugs) == 12

    def test_slugs_are_consecutive_buckets(self):
        slugs = _generate_5m_slugs(symbols=["btc"], lookahead_slots=2)
        timestamps = [int(s.split("-")[-1]) for s in slugs]
        # Each timestamp should be 300s apart
        diffs = [timestamps[i + 1] - timestamps[i] for i in range(len(timestamps) - 1)]
        assert all(d == 300 for d in diffs)

    def test_current_bucket_is_present(self):
        current_bucket = (int(time.time()) // 300) * 300
        slugs = _generate_5m_slugs(symbols=["btc"], lookahead_slots=0)
        assert slugs[0] == f"btc-updown-5m-{current_bucket}"


# ---------------------------------------------------------------------------
# discover_updown_5m_markets
# ---------------------------------------------------------------------------

class TestDiscoverUpdown5mMarkets:
    def test_returns_pairs_for_active_market(self):
        fake_market = _make_fake_market(
            slug="btc-updown-5m-123",
            question="Will BTC go up in the next 5 min?",
            active=True,
            clob_token_ids=["yes-token", "no-token"],
            outcomes=["Up", "Down"],
        )
        gamma_client = MagicMock()
        gamma_client.fetch_markets_filtered.return_value = [fake_market]

        result = discover_updown_5m_markets(gamma_client=gamma_client)

        assert len(result) == 1
        pair = result[0]
        assert isinstance(pair, CryptoPairMarket)
        assert pair.symbol == "BTC"
        assert pair.duration_min == 5
        assert pair.yes_token_id == "yes-token"
        assert pair.no_token_id == "no-token"
        assert pair.slug == "btc-updown-5m-123"

    def test_skips_inactive_market(self):
        fake_market = _make_fake_market(
            slug="btc-updown-5m-123",
            question="Will BTC go up in the next 5 min?",
            active=False,
        )
        gamma_client = MagicMock()
        gamma_client.fetch_markets_filtered.return_value = [fake_market]

        result = discover_updown_5m_markets(gamma_client=gamma_client)

        assert result == []

    def test_skips_market_not_accepting_orders(self):
        fake_market = _make_fake_market(
            slug="eth-updown-5m-456",
            question="Will ETH go up in the next 5 min?",
            active=True,
            accepting_orders=False,
        )
        gamma_client = MagicMock()
        gamma_client.fetch_markets_filtered.return_value = [fake_market]

        result = discover_updown_5m_markets(gamma_client=gamma_client)

        assert result == []

    def test_skips_market_with_wrong_token_count(self):
        fake_market = _make_fake_market(
            slug="sol-updown-5m-789",
            question="Will SOL go up in the next 5 min?",
            active=True,
            clob_token_ids=["only-one-token"],
        )
        gamma_client = MagicMock()
        gamma_client.fetch_markets_filtered.return_value = [fake_market]

        result = discover_updown_5m_markets(gamma_client=gamma_client)

        assert result == []

    def test_calls_fetch_markets_filtered_with_slugs(self):
        gamma_client = MagicMock()
        gamma_client.fetch_markets_filtered.return_value = []

        discover_updown_5m_markets(gamma_client=gamma_client, lookahead_slots=2)

        gamma_client.fetch_markets_filtered.assert_called_once()
        call_kwargs = gamma_client.fetch_markets_filtered.call_args
        slugs_arg = call_kwargs.kwargs.get("slugs") or call_kwargs.args[0]
        # lookahead_slots=2 => 3 slots × 3 symbols = 9 slugs
        assert len(slugs_arg) == 9

    def test_eth_and_sol_markets_correctly_classified(self):
        markets = [
            _make_fake_market(slug="eth-updown-5m-100", question="Will ETH go up in 5m?"),
            _make_fake_market(slug="sol-updown-5m-100", question="Will SOL go up in 5m?"),
        ]
        gamma_client = MagicMock()
        gamma_client.fetch_markets_filtered.return_value = markets

        result = discover_updown_5m_markets(gamma_client=gamma_client)

        assert len(result) == 2
        symbols = {p.symbol for p in result}
        assert symbols == {"ETH", "SOL"}


# ---------------------------------------------------------------------------
# discover_crypto_pair_markets — targeted path integration
# ---------------------------------------------------------------------------

class TestDiscoverCryptoPairMarketsTargeted:
    def _make_result_mock(self, markets=None):
        """Return a mock MarketsFetchResult."""
        r = MagicMock()
        r.markets = markets if markets is not None else []
        return r

    def test_uses_targeted_path_by_default(self):
        gamma_client = MagicMock()
        gamma_client.fetch_all_markets.return_value = self._make_result_mock()
        gamma_client.fetch_markets_filtered.return_value = []

        discover_crypto_pair_markets(gamma_client=gamma_client)

        # fetch_markets_filtered should be called (targeted path is on by default)
        gamma_client.fetch_markets_filtered.assert_called_once()

    def test_targeted_path_disabled(self):
        gamma_client = MagicMock()
        gamma_client.fetch_all_markets.return_value = self._make_result_mock()

        discover_crypto_pair_markets(gamma_client=gamma_client, use_targeted_for_5m=False)

        gamma_client.fetch_markets_filtered.assert_not_called()

    def test_targeted_results_merged_without_duplicates(self):
        bulk_market = _make_fake_market(
            slug="btc-updown-5m-100",
            question="Will BTC go up in 5m?",
        )
        gamma_client = MagicMock()
        gamma_client.fetch_all_markets.return_value = self._make_result_mock([bulk_market])
        # Targeted path returns same slug (should dedup) + a new one
        targeted_dup = _make_fake_market(
            slug="btc-updown-5m-100",
            question="Will BTC go up in 5m?",
        )
        targeted_new = _make_fake_market(
            slug="eth-updown-5m-100",
            question="Will ETH go up in 5m?",
        )
        gamma_client.fetch_markets_filtered.return_value = [targeted_dup, targeted_new]

        result = discover_crypto_pair_markets(gamma_client=gamma_client)

        slugs = [p.slug for p in result]
        # btc should appear exactly once; eth should appear
        assert slugs.count("btc-updown-5m-100") == 1
        assert "eth-updown-5m-100" in slugs
        assert len(result) == 2
