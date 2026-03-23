from __future__ import annotations

from datetime import datetime, timedelta, timezone

from packages.polymarket.market_selection.regime_policy import (
    NEW_MARKET,
    OTHER,
    POLITICS,
    SPORTS,
    UNKNOWN,
    TapeRegimeIntegrity,
    check_mixed_regime_coverage,
    classify_market_regime,
    coverage_from_classified_regimes,
    derive_tape_regime,
)


FIXED_NOW = datetime(2026, 3, 8, 18, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def test_classify_market_regime_detects_politics_from_question_and_tags():
    market = {
        "slug": "will-the-senate-pass-the-budget",
        "question": "Will the Senate pass the budget before Friday?",
        "tags": ["US politics", "congress"],
    }

    assert classify_market_regime(market) == POLITICS


def test_classify_market_regime_prefers_category_signal_for_ambiguous_market():
    market = {
        "question": "Will the president attend the Super Bowl?",
        "category": "Sports",
        "tags": ["NFL", "events"],
    }

    assert classify_market_regime(market) == SPORTS


def test_classify_market_regime_detects_new_market_from_created_at():
    market = {
        "slug": "brand-new-launch-market",
        "question": "Will this new market stay above 55c?",
        "created_at": _iso(FIXED_NOW - timedelta(hours=6)),
    }

    assert classify_market_regime(market, reference_time=FIXED_NOW) == NEW_MARKET


def test_classify_market_regime_treats_48_hour_boundary_as_not_new():
    market = {
        "slug": "mature-market",
        "question": "Will this mature market resolve yes?",
        "created_at": _iso(FIXED_NOW - timedelta(hours=48)),
    }

    assert classify_market_regime(market, reference_time=FIXED_NOW) == OTHER


def test_classify_market_regime_returns_other_for_unmatched_market():
    market = {
        "slug": "crypto-sentiment-check",
        "question": "Will BTC close above 100k this week?",
        "tags": ["crypto"],
    }

    assert classify_market_regime(market) == OTHER


def test_check_mixed_regime_coverage_reports_missing_regimes():
    markets = [
        {
            "question": "Will the Lakers win tonight?",
            "tags": ["NBA", "basketball"],
        },
        {
            "question": "Will the Celtics game total go over 220.5?",
            "tags": ["sports"],
            "created_at": _iso(FIXED_NOW - timedelta(hours=12)),
        },
    ]

    result = check_mixed_regime_coverage(markets, reference_time=FIXED_NOW)

    assert result == {
        "satisfies_policy": False,
        "covered_regimes": (SPORTS, NEW_MARKET),
        "missing_regimes": (POLITICS,),
        "regime_counts": {
            POLITICS: 0,
            SPORTS: 2,
            NEW_MARKET: 1,
        },
    }


def test_check_mixed_regime_coverage_accepts_full_mixed_regime_corpus():
    markets = [
        {
            "question": "Will the governor win reelection?",
            "tags": ["politics"],
        },
        {
            "question": "Will Arsenal win the match?",
            "tags": ["soccer"],
        },
        {
            "question": "Will this market stay above 40c in its first day?",
            "age_hours": 10,
        },
    ]

    result = check_mixed_regime_coverage(markets)

    assert result == {
        "satisfies_policy": True,
        "covered_regimes": (POLITICS, SPORTS, NEW_MARKET),
        "missing_regimes": (),
        "regime_counts": {
            POLITICS: 1,
            SPORTS: 1,
            NEW_MARKET: 1,
        },
    }


def test_check_mixed_regime_coverage_counts_new_market_alongside_primary_category():
    markets = [
        {
            "question": "Will the Maple Leafs win tonight?",
            "tags": ["NHL", "hockey"],
            "created_at": _iso(FIXED_NOW - timedelta(hours=4)),
        }
    ]

    result = check_mixed_regime_coverage(markets, reference_time=FIXED_NOW)

    assert result["covered_regimes"] == (SPORTS, NEW_MARKET)
    assert result["regime_counts"][SPORTS] == 1
    assert result["regime_counts"][NEW_MARKET] == 1


class TestDeriveTapeRegime:
    def test_derives_politics_from_slug(self):
        metadata = {"market_slug": "will-the-senate-vote-on-the-budget-bill"}
        result = derive_tape_regime(metadata, operator_regime="unknown")
        assert result.derived_regime == POLITICS
        assert result.final_regime == POLITICS
        assert result.regime_source == "derived"
        assert result.regime_mismatch is False

    def test_derives_sports_from_slug(self):
        metadata = {"market_slug": "will-the-nba-finals-go-to-game-7"}
        result = derive_tape_regime(metadata, operator_regime="unknown")
        assert result.derived_regime == SPORTS
        assert result.final_regime == SPORTS
        assert result.regime_source == "derived"

    def test_mismatch_flagged_when_operator_and_derived_disagree(self):
        metadata = {"market_slug": "will-the-senate-vote-on-immigration"}
        result = derive_tape_regime(metadata, operator_regime="sports")
        assert result.derived_regime == POLITICS
        assert result.operator_regime == "sports"
        assert result.regime_mismatch is True
        assert result.final_regime == POLITICS  # derived wins

    def test_no_mismatch_when_derived_is_other(self):
        # Slug has no regime signal; derived = "other"
        metadata = {"market_slug": "will-btc-close-above-100k"}
        result = derive_tape_regime(metadata, operator_regime="sports")
        assert result.derived_regime == OTHER
        assert result.regime_mismatch is False
        assert result.final_regime == "sports"
        assert result.regime_source == "operator"

    def test_no_mismatch_when_operator_is_unknown(self):
        metadata = {"market_slug": "will-the-senate-vote-on-immigration"}
        result = derive_tape_regime(metadata, operator_regime="unknown")
        assert result.regime_mismatch is False
        assert result.final_regime == POLITICS  # derived wins

    def test_fallback_unknown_when_both_weak(self):
        metadata = {"market_slug": "will-btc-close-above-100k"}
        result = derive_tape_regime(metadata, operator_regime="unknown")
        assert result.derived_regime == OTHER
        assert result.final_regime == UNKNOWN
        assert result.regime_source == "fallback_unknown"
        assert result.regime_mismatch is False

    def test_returns_tape_regime_integrity_instance(self):
        metadata = {"market_slug": "test-market"}
        result = derive_tape_regime(metadata)
        assert isinstance(result, TapeRegimeIntegrity)

    def test_derives_from_question_field(self):
        metadata = {
            "market_slug": "some-generic-slug",
            "question": "Will the presidential election result in a Democratic win?",
        }
        result = derive_tape_regime(metadata, operator_regime="unknown")
        assert result.derived_regime == POLITICS

    def test_operator_regime_preserved_in_output(self):
        metadata = {"market_slug": "crypto-market"}
        result = derive_tape_regime(metadata, operator_regime="sports")
        assert result.operator_regime == "sports"


class TestCoverageFromClassifiedRegimes:
    def test_full_coverage(self):
        regimes = [POLITICS, SPORTS, NEW_MARKET]
        result = coverage_from_classified_regimes(regimes)
        assert result["satisfies_policy"] is True
        assert result["missing_regimes"] == ()
        assert set(result["covered_regimes"]) == {POLITICS, SPORTS, NEW_MARKET}

    def test_partial_coverage_missing_politics(self):
        regimes = [SPORTS, NEW_MARKET]
        result = coverage_from_classified_regimes(regimes)
        assert result["satisfies_policy"] is False
        assert POLITICS in result["missing_regimes"]

    def test_unknown_not_counted_toward_coverage(self):
        regimes = [UNKNOWN, UNKNOWN, UNKNOWN]
        result = coverage_from_classified_regimes(regimes)
        assert result["satisfies_policy"] is False
        assert result["regime_counts"][POLITICS] == 0
        assert result["regime_counts"][SPORTS] == 0
        assert result["regime_counts"][NEW_MARKET] == 0

    def test_other_not_counted_toward_coverage(self):
        regimes = [OTHER, SPORTS]
        result = coverage_from_classified_regimes(regimes)
        assert result["regime_counts"][SPORTS] == 1
        # "other" is not in REQUIRED_REGIMES, so it's ignored
        assert result["satisfies_policy"] is False

    def test_empty_input(self):
        result = coverage_from_classified_regimes([])
        assert result["satisfies_policy"] is False
        assert result["covered_regimes"] == ()

    def test_counts_multiple_tapes_same_regime(self):
        regimes = [SPORTS, SPORTS, SPORTS]
        result = coverage_from_classified_regimes(regimes)
        assert result["regime_counts"][SPORTS] == 3
        assert result["satisfies_policy"] is False  # missing politics and new_market

    def test_regime_counts_dict_returned(self):
        regimes = [POLITICS, SPORTS, NEW_MARKET, POLITICS]
        result = coverage_from_classified_regimes(regimes)
        assert result["regime_counts"][POLITICS] == 2
        assert result["regime_counts"][SPORTS] == 1
        assert result["regime_counts"][NEW_MARKET] == 1
