"""Tests for packages/polymarket/simtrader/target_resolver.py

All tests are fully offline — no network calls.
Stubs/mocks are injected directly.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import MagicMock

import pytest

from packages.polymarket.simtrader.target_resolver import (
    ChildMarketChoice,
    TargetResolver,
    TargetResolverError,
    _parse_target,
)
from packages.polymarket.simtrader.market_picker import ResolvedMarket


# ---------------------------------------------------------------------------
# Helpers — build fake Market and GammaClient stubs
# ---------------------------------------------------------------------------


@dataclass
class FakeMarket:
    """Minimal Market-like object for tests."""

    market_slug: str
    question: str
    outcomes: list
    clob_token_ids: list
    active: bool = True
    enable_order_book: Optional[bool] = True
    accepting_orders: Optional[bool] = True
    event_slug: str = ""
    event_slugs: list = field(default_factory=list)
    liquidity: float = 1000.0
    volume: float = 5000.0


def _make_binary_market(
    slug: str,
    question: str = "Will it happen?",
    active: bool = True,
    accepting_orders: Optional[bool] = True,
    enable_order_book: Optional[bool] = True,
    clob_token_ids: Optional[list] = None,
    outcomes: Optional[list] = None,
    liquidity: float = 1000.0,
    volume: float = 5000.0,
    event_slug: str = "some-event",
) -> FakeMarket:
    return FakeMarket(
        market_slug=slug,
        question=question,
        outcomes=outcomes if outcomes is not None else ["Yes", "No"],
        clob_token_ids=clob_token_ids if clob_token_ids is not None else ["tok-yes-" + slug, "tok-no-" + slug],
        active=active,
        accepting_orders=accepting_orders,
        enable_order_book=enable_order_book,
        liquidity=liquidity,
        volume=volume,
        event_slug=event_slug,
        event_slugs=[event_slug] if event_slug else [],
    )


def _make_gamma_stub(slugs_map: dict, event_slugs_map: Optional[dict] = None):
    """Return a stub GammaClient.

    slugs_map: { slug_str: [FakeMarket, ...] }
    event_slugs_map: { event_slug_str: [FakeMarket, ...] }
    """
    event_slugs_map = event_slugs_map or {}

    gamma = MagicMock()

    def fetch_markets_filtered(
        condition_ids=None,
        clob_token_ids=None,
        slugs=None,
        closed=None,
        limit=100,
    ):
        if slugs:
            result = []
            for s in slugs:
                result.extend(slugs_map.get(s, []))
            return result
        return []

    gamma.fetch_markets_filtered.side_effect = fetch_markets_filtered

    # fetch_markets_page returns raw dicts; build from event_slugs_map
    def fetch_markets_page(limit=100, offset=0, active_only=True):
        all_markets = []
        seen = set()
        for markets in event_slugs_map.values():
            for m in markets:
                if m.market_slug not in seen:
                    seen.add(m.market_slug)
                    # Return raw dict format
                    all_markets.append(
                        {
                            "slug": m.market_slug,
                            "question": m.question,
                            "outcomes": m.outcomes,
                            "clobTokenIds": m.clob_token_ids,
                            "active": m.active,
                            "enableOrderBook": m.enable_order_book,
                            "acceptingOrders": m.accepting_orders,
                            "liquidity": m.liquidity,
                            "volume": m.volume,
                            "eventSlug": m.event_slug,
                        }
                    )
        return all_markets

    gamma.fetch_markets_page.side_effect = fetch_markets_page
    return gamma


def _make_clob_stub():
    """Return a stub ClobClient that never calls the network."""
    clob = MagicMock()
    # Provide a valid (non-empty) book so resolve_slug succeeds
    clob.fetch_book.return_value = {
        "bids": [{"price": "0.5", "size": "10"}],
        "asks": [{"price": "0.6", "size": "10"}],
    }
    return clob


def _make_resolved(slug: str) -> ResolvedMarket:
    return ResolvedMarket(
        slug=slug,
        yes_token_id="tok-yes-" + slug,
        no_token_id="tok-no-" + slug,
        yes_label="Yes",
        no_label="No",
        question="Will it happen?",
    )


# ---------------------------------------------------------------------------
# _parse_target unit tests
# ---------------------------------------------------------------------------


class TestParseTarget:
    def test_parse_market_url(self):
        slug, hint = _parse_target("https://polymarket.com/market/my-slug")
        assert slug == "my-slug"
        assert hint == "market"

    def test_parse_event_url(self):
        slug, hint = _parse_target("https://polymarket.com/event/my-event")
        assert slug == "my-event"
        assert hint == "event"

    def test_parse_bare_slug(self):
        slug, hint = _parse_target("my-slug")
        assert slug == "my-slug"
        assert hint == "unknown"

    def test_parse_bare_slug_strips_whitespace(self):
        slug, hint = _parse_target("  my-slug  ")
        assert slug == "my-slug"
        assert hint == "unknown"

    def test_market_url_wrong_path(self):
        with pytest.raises(TargetResolverError, match=r"(?i)only /market/ and /event/"):
            _parse_target("https://polymarket.com/faq/something")

    def test_non_polymarket_url_raises(self):
        with pytest.raises(TargetResolverError, match="polymarket.com"):
            _parse_target("https://example.com/market/some-slug")

    def test_parse_market_url_with_trailing_slash(self):
        slug, hint = _parse_target("https://polymarket.com/market/my-slug/")
        assert slug == "my-slug"
        assert hint == "market"


# ---------------------------------------------------------------------------
# TargetResolver.resolve_target tests
# ---------------------------------------------------------------------------


class TestResolveDirect:
    def test_resolve_direct_market_slug(self):
        """Direct slug returns ResolvedMarket."""
        market = _make_binary_market("btc-100k")
        gamma = _make_gamma_stub({"btc-100k": [market]})
        clob = _make_clob_stub()

        resolver = TargetResolver(gamma, clob)
        result = resolver.resolve_target("btc-100k")

        assert isinstance(result, ResolvedMarket)
        assert result.slug == "btc-100k"

    def test_resolve_market_url(self):
        """https://polymarket.com/market/<slug> resolves same as direct slug."""
        market = _make_binary_market("btc-100k")
        gamma = _make_gamma_stub({"btc-100k": [market]})
        clob = _make_clob_stub()

        resolver = TargetResolver(gamma, clob)
        result = resolver.resolve_target("https://polymarket.com/market/btc-100k")

        assert isinstance(result, ResolvedMarket)
        assert result.slug == "btc-100k"


class TestResolveEventUrl:
    def test_resolve_event_url_single_child(self):
        """Event URL with exactly one usable binary child auto-resolves."""
        child = _make_binary_market("btc-100k-dec", event_slug="btc-price-dec-2025")
        gamma = _make_gamma_stub(
            slugs_map={"btc-100k-dec": [child]},
            event_slugs_map={"btc-price-dec-2025": [child]},
        )
        clob = _make_clob_stub()

        resolver = TargetResolver(gamma, clob)
        result = resolver.resolve_target(
            "https://polymarket.com/event/btc-price-dec-2025"
        )

        assert isinstance(result, ResolvedMarket)
        assert result.slug == "btc-100k-dec"

    def test_resolve_event_url_multi_child(self):
        """Multiple usable children -> raises ChildMarketChoice with ranked list."""
        child1 = _make_binary_market(
            "market-a", question="Q A?", liquidity=2000.0, volume=8000.0,
            event_slug="my-event"
        )
        child2 = _make_binary_market(
            "market-b", question="Q B?", liquidity=500.0, volume=1000.0,
            event_slug="my-event"
        )
        gamma = _make_gamma_stub(
            slugs_map={"market-a": [child1], "market-b": [child2]},
            event_slugs_map={"my-event": [child1, child2]},
        )
        clob = _make_clob_stub()

        resolver = TargetResolver(gamma, clob)
        with pytest.raises(ChildMarketChoice) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/my-event")

        choice = exc_info.value
        assert len(choice.candidates) == 2
        # rank 1 = highest liquidity
        assert choice.candidates[0]["slug"] == "market-a"
        assert choice.candidates[1]["slug"] == "market-b"

    def test_resolve_event_slug_direct(self):
        """Bare event slug with hint='unknown' falls back to event lookup."""
        # Direct slug lookup fails (returns no markets)
        child = _make_binary_market("market-a", event_slug="some-event")
        gamma = _make_gamma_stub(
            slugs_map={},  # direct lookup returns nothing
            event_slugs_map={"some-event": [child]},
        )
        # Also make the resolve_slug for the child succeed
        gamma.fetch_markets_filtered.side_effect = lambda **kw: (
            [child] if kw.get("slugs") == ["market-a"] else []
        )
        # Patch to fail direct lookup but succeed child lookup
        call_log = []

        def smart_fetch(condition_ids=None, clob_token_ids=None, slugs=None, closed=None, limit=100):
            if slugs:
                call_log.append(slugs)
                # First call is the direct lookup for "some-event" -> fail
                # Second call is the child slug -> succeed
                if slugs == ["some-event"]:
                    return []
                if slugs == ["market-a"]:
                    return [child]
            return []

        gamma.fetch_markets_filtered.side_effect = smart_fetch

        clob = _make_clob_stub()
        resolver = TargetResolver(gamma, clob)
        result = resolver.resolve_target("some-event")

        assert isinstance(result, ResolvedMarket)
        assert result.slug == "market-a"


class TestRejectChildren:
    def _make_resolver_with_children(self, children: list):
        """Helper: event URL with given children list, direct slug fails."""
        gamma = MagicMock()

        def fetch_markets_filtered(condition_ids=None, clob_token_ids=None, slugs=None, closed=None, limit=100):
            if slugs == ["bad-event"]:
                return []  # direct slug fails -> fall through to event
            # Resolve child slugs
            if slugs:
                for child in children:
                    if child.market_slug in slugs:
                        return [child]
            return []

        gamma.fetch_markets_filtered.side_effect = fetch_markets_filtered

        def fetch_markets_page(limit=100, offset=0, active_only=True):
            return [
                {
                    "slug": c.market_slug,
                    "question": c.question,
                    "outcomes": c.outcomes,
                    "clobTokenIds": c.clob_token_ids,
                    "active": c.active,
                    "enableOrderBook": c.enable_order_book,
                    "acceptingOrders": c.accepting_orders,
                    "liquidity": c.liquidity,
                    "volume": c.volume,
                    "eventSlug": c.event_slug,
                }
                for c in children
            ]

        gamma.fetch_markets_page.side_effect = fetch_markets_page
        clob = _make_clob_stub()
        return TargetResolver(gamma, clob)

    def test_reject_non_binary_child(self):
        """Child with 3 outcomes -> skip reason contains 'not_binary'."""
        bad = _make_binary_market("multi-outcome", outcomes=["A", "B", "C"],
                                  clob_token_ids=["t1", "t2", "t3"],
                                  event_slug="bad-event")
        resolver = self._make_resolver_with_children([bad])
        with pytest.raises(TargetResolverError) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/bad-event")
        assert "not_binary" in str(exc_info.value)

    def test_reject_no_token_ids_child(self):
        """Child with empty clob_token_ids -> skip reason 'no_token_ids'."""
        bad = _make_binary_market("empty-tokens", clob_token_ids=[],
                                  event_slug="bad-event")
        resolver = self._make_resolver_with_children([bad])
        with pytest.raises(TargetResolverError) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/bad-event")
        assert "no_token_ids" in str(exc_info.value)

    def test_reject_not_accepting_orders(self):
        """Child with accepting_orders=False -> skip reason 'not_accepting_orders'."""
        bad = _make_binary_market("halted", accepting_orders=False,
                                  event_slug="bad-event")
        resolver = self._make_resolver_with_children([bad])
        with pytest.raises(TargetResolverError) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/bad-event")
        assert "not_accepting_orders" in str(exc_info.value)

    def test_reject_closed_child(self):
        """Child with active=False -> skip reason 'closed'."""
        bad = _make_binary_market("closed-market", active=False,
                                  event_slug="bad-event")
        resolver = self._make_resolver_with_children([bad])
        with pytest.raises(TargetResolverError) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/bad-event")
        assert "closed" in str(exc_info.value)


class TestRankedShortlist:
    def test_ranked_shortlist_order(self):
        """Usable children ranked by liquidity desc, volume desc as tiebreak."""
        low_liq = _make_binary_market(
            "low-liq", liquidity=100.0, volume=9999.0, event_slug="rank-event"
        )
        high_liq = _make_binary_market(
            "high-liq", liquidity=9000.0, volume=100.0, event_slug="rank-event"
        )
        mid_liq_high_vol = _make_binary_market(
            "mid-liq-high-vol", liquidity=500.0, volume=2000.0, event_slug="rank-event"
        )
        mid_liq_low_vol = _make_binary_market(
            "mid-liq-low-vol", liquidity=500.0, volume=100.0, event_slug="rank-event"
        )

        gamma = _make_gamma_stub(
            slugs_map={
                "low-liq": [low_liq],
                "high-liq": [high_liq],
                "mid-liq-high-vol": [mid_liq_high_vol],
                "mid-liq-low-vol": [mid_liq_low_vol],
            },
            event_slugs_map={
                "rank-event": [low_liq, high_liq, mid_liq_high_vol, mid_liq_low_vol]
            },
        )
        clob = _make_clob_stub()
        resolver = TargetResolver(gamma, clob)

        with pytest.raises(ChildMarketChoice) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/rank-event")

        choice = exc_info.value
        slugs_in_order = [c["slug"] for c in choice.candidates]
        assert slugs_in_order[0] == "high-liq", f"Got: {slugs_in_order}"
        assert slugs_in_order[1] == "mid-liq-high-vol", f"Got: {slugs_in_order}"
        assert slugs_in_order[2] == "mid-liq-low-vol", f"Got: {slugs_in_order}"
        assert slugs_in_order[3] == "low-liq", f"Got: {slugs_in_order}"

    def test_ranked_shortlist_has_rank_field(self):
        """Each candidate has a 'rank' key (1-based)."""
        child1 = _make_binary_market("m1", liquidity=500.0, event_slug="rank-event2")
        child2 = _make_binary_market("m2", liquidity=200.0, event_slug="rank-event2")
        gamma = _make_gamma_stub(
            slugs_map={"m1": [child1], "m2": [child2]},
            event_slugs_map={"rank-event2": [child1, child2]},
        )
        clob = _make_clob_stub()
        resolver = TargetResolver(gamma, clob)

        with pytest.raises(ChildMarketChoice) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/rank-event2")

        choice = exc_info.value
        assert choice.candidates[0]["rank"] == 1
        assert choice.candidates[1]["rank"] == 2

    def test_child_market_choice_has_skipped(self):
        """ChildMarketChoice also includes skipped list when some children rejected."""
        good = _make_binary_market("good-m", event_slug="mix-event", liquidity=1000.0)
        bad = _make_binary_market("bad-m", active=False, event_slug="mix-event")
        good2 = _make_binary_market("good-m2", event_slug="mix-event", liquidity=500.0)

        gamma = _make_gamma_stub(
            slugs_map={"good-m": [good], "good-m2": [good2]},
            event_slugs_map={"mix-event": [good, bad, good2]},
        )
        clob = _make_clob_stub()
        resolver = TargetResolver(gamma, clob)

        with pytest.raises(ChildMarketChoice) as exc_info:
            resolver.resolve_target("https://polymarket.com/event/mix-event")

        choice = exc_info.value
        assert len(choice.candidates) == 2
        assert len(choice.skipped) == 1
        assert choice.skipped[0]["slug"] == "bad-m"
        assert "closed" in choice.skipped[0]["reason"]
