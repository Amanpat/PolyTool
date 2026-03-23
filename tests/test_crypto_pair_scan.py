"""Tests for Track 2 / Phase 1A — crypto pair opportunity scanner.

All tests are offline; no network calls are made.  GammaClient and ClobClient
are stubbed with MagicMock / minimal fakes.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock

import pytest

from packages.polymarket.clob import OrderBookTop
from packages.polymarket.crypto_pairs.market_discovery import (
    CryptoPairMarket,
    _detect_duration,
    _detect_symbol,
    _resolve_yes_no_tokens,
    discover_crypto_pair_markets,
)
from packages.polymarket.crypto_pairs.opportunity_scan import (
    PairOpportunity,
    compute_pair_opportunity,
    rank_opportunities,
    scan_opportunities,
)
from tools.cli.crypto_pair_scan import run_crypto_pair_scan


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _make_mock_market(
    slug: str,
    question: str,
    clob_token_ids: list[str],
    outcomes: list[str],
    active: bool = True,
    accepting_orders: Optional[bool] = True,
) -> MagicMock:
    m = MagicMock()
    m.market_slug = slug
    m.question = question
    m.clob_token_ids = clob_token_ids
    m.outcomes = outcomes
    m.active = active
    m.accepting_orders = accepting_orders
    m.condition_id = f"cond_{slug}"
    m.end_date_iso = None
    return m


def _make_gamma_client(markets: list) -> MagicMock:
    result = MagicMock()
    result.markets = markets
    client = MagicMock()
    client.fetch_all_markets.return_value = result
    return client


def _make_clob_client(
    book_tops: dict[str, tuple[Optional[float], Optional[float]]]
) -> MagicMock:
    """Build a ClobClient stub.

    book_tops maps token_id -> (best_bid, best_ask).  Pass None for the whole
    entry to simulate get_best_bid_ask returning None (fetch_error).
    """

    def _side_effect(token_id: str) -> Optional[OrderBookTop]:
        if token_id not in book_tops:
            return None
        bid, ask = book_tops[token_id]
        return OrderBookTop(token_id=token_id, best_bid=bid, best_ask=ask, raw_json={})

    client = MagicMock()
    client.get_best_bid_ask.side_effect = _side_effect
    return client


def _make_pair_market(
    slug: str = "btc-5m-up",
    symbol: str = "BTC",
    duration_min: int = 5,
    yes_token_id: str = "yes_tok",
    no_token_id: str = "no_tok",
) -> CryptoPairMarket:
    return CryptoPairMarket(
        slug=slug,
        condition_id=f"cond_{slug}",
        question=f"Will {symbol} be up in {duration_min}m?",
        symbol=symbol,
        duration_min=duration_min,
        yes_token_id=yes_token_id,
        no_token_id=no_token_id,
    )


# ---------------------------------------------------------------------------
# _detect_symbol
# ---------------------------------------------------------------------------

class TestDetectSymbol:
    def test_btc_full(self):
        assert _detect_symbol("Bitcoin 5m") == "BTC"

    def test_btc_abbrev(self):
        assert _detect_symbol("BTC price 5m") == "BTC"

    def test_eth_full(self):
        assert _detect_symbol("Ethereum 15 min up") == "ETH"

    def test_eth_abbrev(self):
        assert _detect_symbol("ETH/USD up") == "ETH"

    def test_sol_full(self):
        assert _detect_symbol("Solana 5m up") == "SOL"

    def test_sol_abbrev(self):
        assert _detect_symbol("SOL 15m higher") == "SOL"

    def test_no_match(self):
        assert _detect_symbol("DOGE moon") is None

    def test_case_insensitive(self):
        assert _detect_symbol("btc-5m-up-or-down") == "BTC"

    def test_ether_keyword(self):
        assert _detect_symbol("Will ether go up?") == "ETH"


# ---------------------------------------------------------------------------
# _detect_duration
# ---------------------------------------------------------------------------

class TestDetectDuration:
    def test_5m_abbrev(self):
        assert _detect_duration("btc-5m-up") == 5

    def test_15m_abbrev(self):
        assert _detect_duration("eth-15m-higher") == 15

    def test_5_min_full(self):
        assert _detect_duration("5 minute up or down") == 5

    def test_15_minutes_full(self):
        assert _detect_duration("15 minutes SOL") == 15

    def test_hyphenated_5(self):
        assert _detect_duration("5-min BTC") == 5

    def test_hyphenated_15(self):
        assert _detect_duration("15-min BTC") == 15

    def test_no_match(self):
        assert _detect_duration("1 hour BTC") is None

    def test_30m_not_matched(self):
        assert _detect_duration("30m BTC") is None


# ---------------------------------------------------------------------------
# _resolve_yes_no_tokens
# ---------------------------------------------------------------------------

class TestResolveYesNoTokens:
    def test_yes_no_by_name(self):
        yes, no = _resolve_yes_no_tokens(["tok_y", "tok_n"], ["Yes", "No"])
        assert yes == "tok_y"
        assert no == "tok_n"

    def test_up_down_names(self):
        yes, no = _resolve_yes_no_tokens(["up_tok", "down_tok"], ["Up", "Down"])
        assert yes == "up_tok"
        assert no == "down_tok"

    def test_higher_lower_names(self):
        yes, no = _resolve_yes_no_tokens(["h_tok", "l_tok"], ["Higher", "Lower"])
        assert yes == "h_tok"
        assert no == "l_tok"

    def test_fallback_index_order(self):
        # Unknown outcome names -> fall back to index 0=YES, 1=NO
        yes, no = _resolve_yes_no_tokens(["tok0", "tok1"], ["Alpha", "Beta"])
        assert yes == "tok0"
        assert no == "tok1"

    def test_reversed_names(self):
        yes, no = _resolve_yes_no_tokens(["tok_n", "tok_y"], ["No", "Yes"])
        assert yes == "tok_y"
        assert no == "tok_n"

    def test_fewer_than_two_tokens(self):
        yes, no = _resolve_yes_no_tokens(["only_one"], ["Yes"])
        assert yes is None
        assert no is None

    def test_empty_tokens(self):
        yes, no = _resolve_yes_no_tokens([], [])
        assert yes is None
        assert no is None

    def test_true_false_names(self):
        yes, no = _resolve_yes_no_tokens(["t", "f"], ["True", "False"])
        assert yes == "t"
        assert no == "f"


# ---------------------------------------------------------------------------
# discover_crypto_pair_markets
# ---------------------------------------------------------------------------

class TestDiscoverCryptoPairMarkets:
    def _valid_btc_5m(self) -> MagicMock:
        return _make_mock_market(
            "btc-5m-up",
            "Will BTC be higher in 5 minutes?",
            ["yes_btc", "no_btc"],
            ["Yes", "No"],
        )

    def _valid_eth_15m(self) -> MagicMock:
        return _make_mock_market(
            "eth-15m-higher",
            "Will ETH go up in 15 minutes?",
            ["yes_eth", "no_eth"],
            ["Yes", "No"],
        )

    def _valid_sol_5m(self) -> MagicMock:
        return _make_mock_market(
            "sol-5m-up",
            "Solana 5 minute up?",
            ["yes_sol", "no_sol"],
            ["Up", "Down"],
        )

    def _no_symbol(self) -> MagicMock:
        return _make_mock_market(
            "doge-5m-up",
            "Will DOGE be up in 5m?",
            ["y", "n"],
            ["Yes", "No"],
        )

    def _no_duration(self) -> MagicMock:
        return _make_mock_market(
            "btc-hourly",
            "Will BTC go up today?",
            ["y", "n"],
            ["Yes", "No"],
        )

    def _single_token(self) -> MagicMock:
        return _make_mock_market(
            "btc-5m-multi",
            "BTC 5m up",
            ["only_one"],
            ["Yes"],
        )

    def _not_accepting_orders(self) -> MagicMock:
        return _make_mock_market(
            "btc-5m-closed",
            "BTC 5m closed",
            ["y", "n"],
            ["Yes", "No"],
            active=True,
            accepting_orders=False,
        )

    def _not_active(self) -> MagicMock:
        return _make_mock_market(
            "btc-5m-inactive",
            "BTC 5m inactive",
            ["y", "n"],
            ["Yes", "No"],
            active=False,
        )

    def test_discovers_valid_markets(self):
        mocks = [self._valid_btc_5m(), self._valid_eth_15m(), self._valid_sol_5m()]
        gc = _make_gamma_client(mocks)
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 3
        slugs = {m.slug for m in result}
        assert slugs == {"btc-5m-up", "eth-15m-higher", "sol-5m-up"}

    def test_filters_no_symbol(self):
        gc = _make_gamma_client([self._valid_btc_5m(), self._no_symbol()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 1
        assert result[0].slug == "btc-5m-up"

    def test_filters_no_duration(self):
        gc = _make_gamma_client([self._valid_eth_15m(), self._no_duration()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 1
        assert result[0].slug == "eth-15m-higher"

    def test_filters_single_token(self):
        gc = _make_gamma_client([self._valid_btc_5m(), self._single_token()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 1

    def test_filters_not_accepting_orders(self):
        gc = _make_gamma_client([self._valid_btc_5m(), self._not_accepting_orders()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 1

    def test_filters_not_active(self):
        gc = _make_gamma_client([self._valid_btc_5m(), self._not_active()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 1

    def test_correct_token_ids(self):
        gc = _make_gamma_client([self._valid_btc_5m()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        m = result[0]
        assert m.yes_token_id == "yes_btc"
        assert m.no_token_id == "no_btc"

    def test_correct_symbol_and_duration(self):
        gc = _make_gamma_client([self._valid_eth_15m()])
        result = discover_crypto_pair_markets(gamma_client=gc)
        m = result[0]
        assert m.symbol == "ETH"
        assert m.duration_min == 15

    def test_empty_market_list(self):
        gc = _make_gamma_client([])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert result == []

    def test_accepting_orders_none_is_allowed(self):
        """accepting_orders=None means not explicitly rejecting — should be kept."""
        m = _make_mock_market(
            "btc-5m-none",
            "BTC 5m",
            ["y", "n"],
            ["Yes", "No"],
            accepting_orders=None,
        )
        gc = _make_gamma_client([m])
        result = discover_crypto_pair_markets(gamma_client=gc)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# compute_pair_opportunity
# ---------------------------------------------------------------------------

class TestComputePairOpportunity:
    def _market(self) -> CryptoPairMarket:
        return _make_pair_market()

    def test_opportunity_found(self):
        """YES_ask + NO_ask < 1.00 → has_opportunity=True."""
        clob = _make_clob_client({"yes_tok": (0.45, 0.47), "no_tok": (0.45, 0.48)})
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.yes_ask == pytest.approx(0.47)
        assert opp.no_ask == pytest.approx(0.48)
        assert opp.paired_cost == pytest.approx(0.95)
        assert opp.gross_edge == pytest.approx(0.05)
        assert opp.has_opportunity is True
        assert opp.book_status == "ok"

    def test_no_opportunity_at_exactly_one(self):
        """paired_cost == 1.00 → gross_edge == 0 → NOT an opportunity."""
        clob = _make_clob_client({"yes_tok": (None, 0.50), "no_tok": (None, 0.50)})
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.gross_edge == pytest.approx(0.0)
        assert opp.has_opportunity is False

    def test_no_opportunity_above_one(self):
        """paired_cost > 1.00 → gross_edge < 0 → NOT an opportunity."""
        clob = _make_clob_client({"yes_tok": (None, 0.55), "no_tok": (None, 0.52)})
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.gross_edge < 0.0
        assert opp.has_opportunity is False

    def test_missing_yes_book(self):
        clob = _make_clob_client({"no_tok": (None, 0.48)})  # yes_tok absent
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.book_status == "missing_yes"
        assert opp.has_opportunity is False
        assert opp.yes_ask is None

    def test_missing_no_book(self):
        clob = _make_clob_client({"yes_tok": (None, 0.47)})  # no_tok absent
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.book_status == "missing_no"
        assert opp.has_opportunity is False

    def test_yes_ask_is_none(self):
        """Best ask missing from the book response."""
        clob = _make_clob_client({"yes_tok": (0.45, None), "no_tok": (None, 0.48)})
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.book_status == "missing_yes"

    def test_no_ask_is_none(self):
        clob = _make_clob_client({"yes_tok": (None, 0.47), "no_tok": (0.45, None)})
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert opp.book_status == "missing_no"

    def test_assumptions_always_present(self):
        clob = _make_clob_client({"yes_tok": (None, 0.47), "no_tok": (None, 0.48)})
        opp = compute_pair_opportunity(self._market(), clob_client=clob)
        assert "maker_rebate_20bps" in opp.assumptions
        assert "no_slippage" in opp.assumptions
        assert "fills_not_guaranteed" in opp.assumptions
        assert "rapid_resolution" in opp.assumptions

    def test_market_fields_propagated(self):
        m = _make_pair_market(slug="eth-15m-up", symbol="ETH", duration_min=15)
        clob = _make_clob_client({"yes_tok": (None, 0.47), "no_tok": (None, 0.48)})
        opp = compute_pair_opportunity(m, clob_client=clob)
        assert opp.slug == "eth-15m-up"
        assert opp.symbol == "ETH"
        assert opp.duration_min == 15


# ---------------------------------------------------------------------------
# scan_opportunities
# ---------------------------------------------------------------------------

class TestScanOpportunities:
    def test_returns_one_per_market(self):
        markets = [
            _make_pair_market("btc-5m-up", yes_token_id="y1", no_token_id="n1"),
            _make_pair_market("eth-5m-up", yes_token_id="y2", no_token_id="n2"),
        ]
        clob = _make_clob_client(
            {"y1": (None, 0.47), "n1": (None, 0.48), "y2": (None, 0.50), "n2": (None, 0.51)}
        )
        result = scan_opportunities(markets, clob_client=clob)
        assert len(result) == 2

    def test_empty_list(self):
        clob = _make_clob_client({})
        assert scan_opportunities([], clob_client=clob) == []


# ---------------------------------------------------------------------------
# rank_opportunities
# ---------------------------------------------------------------------------

class TestRankOpportunities:
    def _opp(
        self,
        slug: str,
        gross_edge: Optional[float],
        has_opportunity: bool,
    ) -> PairOpportunity:
        return PairOpportunity(
            slug=slug,
            symbol="BTC",
            duration_min=5,
            question="q",
            condition_id="c",
            yes_token_id="y",
            no_token_id="n",
            gross_edge=gross_edge,
            has_opportunity=has_opportunity,
        )

    def test_opportunities_before_no_opps(self):
        opps = [
            self._opp("b-market", -0.05, False),
            self._opp("a-market", 0.05, True),
        ]
        ranked = rank_opportunities(opps)
        assert ranked[0].slug == "a-market"
        assert ranked[1].slug == "b-market"

    def test_higher_edge_first_within_group(self):
        opps = [
            self._opp("low-edge", 0.02, True),
            self._opp("high-edge", 0.08, True),
        ]
        ranked = rank_opportunities(opps)
        assert ranked[0].slug == "high-edge"
        assert ranked[1].slug == "low-edge"

    def test_slug_tiebreaker(self):
        opps = [
            self._opp("z-market", 0.05, True),
            self._opp("a-market", 0.05, True),
        ]
        ranked = rank_opportunities(opps)
        assert ranked[0].slug == "a-market"
        assert ranked[1].slug == "z-market"

    def test_stable_with_none_edge(self):
        opps = [
            self._opp("b-no-edge", None, False),
            self._opp("a-no-edge", None, False),
        ]
        ranked = rank_opportunities(opps)
        assert ranked[0].slug == "a-no-edge"

    def test_empty(self):
        assert rank_opportunities([]) == []

    def test_mixed_ordering(self):
        """Three opps + two non-opps, stable sort verified end-to-end."""
        opps = [
            self._opp("c-opp", 0.01, True),
            self._opp("no-a", -0.03, False),
            self._opp("a-opp", 0.10, True),
            self._opp("no-b", -0.01, False),
            self._opp("b-opp", 0.05, True),
        ]
        ranked = rank_opportunities(opps)
        slugs = [o.slug for o in ranked]
        # First three must be the has_opportunity=True entries in edge descending order
        assert slugs[:3] == ["a-opp", "b-opp", "c-opp"]
        # Last two: no-b (-0.01 → key 0.01) before no-a (-0.03 → key 0.03)
        # Secondary sort is -(gross_edge), so less-negative edge ranks first
        assert slugs[3:] == ["no-b", "no-a"]


# ---------------------------------------------------------------------------
# run_crypto_pair_scan (CLI orchestrator)
# ---------------------------------------------------------------------------

class TestRunCryptoPairScan:
    def _setup(
        self,
        yes_ask: float = 0.47,
        no_ask: float = 0.48,
    ):
        """Build a gamma+clob stub pair for a single BTC-5m-up market."""
        mock_mkt = _make_mock_market(
            "btc-5m-up",
            "Will BTC be higher in 5 minutes?",
            ["yes_tok", "no_tok"],
            ["Yes", "No"],
        )
        gamma = _make_gamma_client([mock_mkt])
        clob = _make_clob_client(
            {"yes_tok": (None, yes_ask), "no_tok": (None, no_ask)}
        )
        return gamma, clob

    def test_artifacts_created(self, tmp_path):
        gamma, clob = self._setup()
        run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        date_dir = next(tmp_path.iterdir())  # YYYY-MM-DD
        run_dir = next(date_dir.iterdir())   # run_id hex
        assert (run_dir / "scan_manifest.json").exists()
        assert (run_dir / "opportunities.json").exists()
        assert (run_dir / "opportunities.md").exists()

    def test_manifest_structure(self, tmp_path):
        gamma, clob = self._setup()
        manifest = run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["mode"] == "dry_run"
        assert "run_id" in manifest
        assert "generated_at" in manifest
        assert manifest["summary"]["markets_discovered"] == 1
        assert manifest["summary"]["markets_scanned"] == 1
        assert manifest["filters"]["symbol"] is None
        assert manifest["filters"]["duration_min"] is None

    def test_opportunity_detected(self, tmp_path):
        """YES_ask 0.47 + NO_ask 0.48 = 0.95 → has_opportunity."""
        gamma, clob = self._setup(yes_ask=0.47, no_ask=0.48)
        manifest = run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["summary"]["opportunities_found"] == 1

    def test_no_opportunity_at_parity(self, tmp_path):
        """YES_ask 0.50 + NO_ask 0.50 = 1.00 → NOT an opportunity."""
        gamma, clob = self._setup(yes_ask=0.50, no_ask=0.50)
        manifest = run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["summary"]["opportunities_found"] == 0

    def test_opportunities_json_schema(self, tmp_path):
        gamma, clob = self._setup()
        run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        date_dir = next(tmp_path.iterdir())
        run_dir = next(date_dir.iterdir())
        data = json.loads((run_dir / "opportunities.json").read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        rec = data[0]
        for key in ("slug", "symbol", "duration_min", "yes_ask", "no_ask",
                    "paired_cost", "gross_edge", "has_opportunity",
                    "book_status", "assumptions"):
            assert key in rec, f"Missing key: {key}"

    def test_symbol_filter(self, tmp_path):
        """Filtering by symbol=ETH should return 0 markets (only BTC available)."""
        gamma, clob = self._setup()
        manifest = run_crypto_pair_scan(
            symbol_filter="ETH",
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["summary"]["markets_discovered"] == 0
        assert manifest["summary"]["markets_scanned"] == 0
        assert manifest["filters"]["symbol"] == "ETH"

    def test_duration_filter(self, tmp_path):
        """Filtering by duration=15 should exclude our 5m market."""
        gamma, clob = self._setup()
        manifest = run_crypto_pair_scan(
            duration_filter=15,
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["summary"]["markets_discovered"] == 0
        assert manifest["filters"]["duration_min"] == 15

    def test_manifest_json_on_disk_matches_return(self, tmp_path):
        gamma, clob = self._setup()
        manifest = run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        date_dir = next(tmp_path.iterdir())
        run_dir = next(date_dir.iterdir())
        on_disk = json.loads((run_dir / "scan_manifest.json").read_text())
        assert on_disk["run_id"] == manifest["run_id"]
        assert on_disk["mode"] == manifest["mode"]

    def test_top_parameter_recorded(self, tmp_path):
        gamma, clob = self._setup()
        manifest = run_crypto_pair_scan(
            top=5,
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["summary"]["top_requested"] == 5

    def test_no_markets_does_not_crash(self, tmp_path):
        gamma = _make_gamma_client([])
        clob = _make_clob_client({})
        manifest = run_crypto_pair_scan(
            output_base=tmp_path,
            gamma_client=gamma,
            clob_client=clob,
        )
        assert manifest["summary"]["markets_discovered"] == 0
        assert manifest["summary"]["opportunities_found"] == 0
