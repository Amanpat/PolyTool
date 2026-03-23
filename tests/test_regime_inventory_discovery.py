"""Tests for regime-inventory discovery: enrich_with_regime + filter_by_factual_regime.

All tests are fully offline — no network calls, no live API, no tape files.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from packages.polymarket.market_selection.regime_policy import (
    NEW_MARKET,
    OTHER,
    POLITICS,
    REGIME_CAPTURE_NEAR_EDGE_DEFAULTS,
    REQUIRED_REGIMES,
    SPORTS,
    _DEFAULT_CAPTURE_THRESHOLD,
    enrich_with_regime,
    filter_by_factual_regime,
    get_regime_capture_threshold,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def _politics_market(**kw: Any) -> dict:
    return {
        "slug": "will-senator-win-election",
        "category": "politics",
        "title": "Will the senator win the election?",
        "question": "Will the senator win the election?",
        **kw,
    }


def _new_market_by_age(age_hours: float = 10.0, **kw: Any) -> dict:
    created_at = _FIXED_NOW - timedelta(hours=age_hours)
    return {
        "slug": "brand-new-crypto-market",
        "title": "Will BTC hit 100k?",
        "created_at": _iso(created_at),
        **kw,
    }


def _sports_market(**kw: Any) -> dict:
    return {
        "slug": "nfl-super-bowl",
        "category": "sports",
        "title": "Will the Chiefs win the Super Bowl?",
        **kw,
    }


def _unknown_market(**kw: Any) -> dict:
    return {
        "slug": "random-market",
        "title": "Will something happen?",
        **kw,
    }


# ---------------------------------------------------------------------------
# enrich_with_regime — regime classification
# ---------------------------------------------------------------------------


class TestEnrichWithRegime:
    def test_politics_market_gets_politics_regime(self):
        m = _politics_market()
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == POLITICS

    def test_sports_market_gets_sports_regime(self):
        m = _sports_market()
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == SPORTS

    def test_new_market_by_age_gets_new_market_regime(self):
        m = _new_market_by_age(age_hours=10.0)
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == NEW_MARKET

    def test_old_market_gets_other_regime(self):
        created = _FIXED_NOW - timedelta(hours=100)
        m = {"slug": "old-market", "title": "Some mature market", "created_at": _iso(created)}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == OTHER

    def test_unknown_market_no_metadata_gets_other_regime(self):
        m = _unknown_market()
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == OTHER

    def test_regime_source_is_always_derived(self):
        for market in [_politics_market(), _sports_market(), _unknown_market()]:
            enriched = enrich_with_regime(market, reference_time=_FIXED_NOW)
            assert enriched["regime_source"] == "derived"

    def test_new_market_is_new_market_true(self):
        m = _new_market_by_age(age_hours=5.0)
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["is_new_market"] is True

    def test_old_market_is_new_market_false(self):
        created = _FIXED_NOW - timedelta(hours=96)
        m = {"slug": "old-one", "created_at": _iso(created)}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["is_new_market"] is False

    def test_no_timestamp_no_keywords_is_new_market_none(self):
        m = {"slug": "no-date", "title": "Vague question"}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["is_new_market"] is None

    def test_no_timestamp_new_market_keyword_is_new_market_true(self):
        m = {"slug": "fresh-launch", "tags": ["new market"]}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == NEW_MARKET
        assert enriched["is_new_market"] is True

    def test_age_hours_populated_from_created_at(self):
        created = _FIXED_NOW - timedelta(hours=24)
        m = {"slug": "age-test", "created_at": _iso(created)}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["age_hours"] == pytest.approx(24.0, abs=0.01)

    def test_age_hours_none_when_no_timestamp(self):
        m = {"slug": "no-ts"}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["age_hours"] is None

    def test_original_fields_preserved(self):
        m = _politics_market(extra_field="hello", volume_24h=99999.0)
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["extra_field"] == "hello"
        assert enriched["volume_24h"] == 99999.0
        assert enriched["slug"] == "will-senator-win-election"

    def test_does_not_mutate_input(self):
        m = _politics_market()
        original = dict(m)
        enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert m == original

    def test_politics_detected_via_tags_list(self):
        m = {"slug": "tagged-market", "tags": ["politics", "election"]}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == POLITICS

    def test_new_market_threshold_boundary_just_inside(self):
        created = _FIXED_NOW - timedelta(hours=47.9)
        m = {"slug": "just-new", "created_at": _iso(created)}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == NEW_MARKET
        assert enriched["is_new_market"] is True

    def test_new_market_threshold_boundary_just_outside(self):
        created = _FIXED_NOW - timedelta(hours=48.1)
        m = {"slug": "just-old", "created_at": _iso(created)}
        enriched = enrich_with_regime(m, reference_time=_FIXED_NOW)
        assert enriched["regime"] == OTHER
        assert enriched["is_new_market"] is False


# ---------------------------------------------------------------------------
# filter_by_factual_regime — strict regime filtering
# ---------------------------------------------------------------------------


class TestFilterByFactualRegime:
    def _mixed_markets(self) -> list[dict]:
        return [
            _politics_market(slug="pol-1"),
            _politics_market(slug="pol-2"),
            _sports_market(slug="sport-1"),
            _new_market_by_age(age_hours=12.0, slug="new-1"),
            _unknown_market(slug="unk-1"),
        ]

    def test_filter_politics_returns_only_politics(self):
        markets = self._mixed_markets()
        result = filter_by_factual_regime(markets, POLITICS, reference_time=_FIXED_NOW)
        slugs = [m["slug"] for m in result]
        assert "pol-1" in slugs
        assert "pol-2" in slugs
        assert "sport-1" not in slugs
        assert "new-1" not in slugs
        assert "unk-1" not in slugs

    def test_filter_sports_returns_only_sports(self):
        markets = self._mixed_markets()
        result = filter_by_factual_regime(markets, SPORTS, reference_time=_FIXED_NOW)
        slugs = [m["slug"] for m in result]
        assert "sport-1" in slugs
        assert len(result) == 1

    def test_filter_new_market_returns_only_new_markets(self):
        markets = self._mixed_markets()
        result = filter_by_factual_regime(markets, NEW_MARKET, reference_time=_FIXED_NOW)
        slugs = [m["slug"] for m in result]
        assert "new-1" in slugs
        assert "pol-1" not in slugs
        assert "unk-1" not in slugs

    def test_unknown_markets_never_included(self):
        # Slug and title contain no politics/sports/new_market keywords → excluded
        m = {"slug": "random-prediction-market", "title": "Will something happen soon?"}
        result = filter_by_factual_regime([m], POLITICS, reference_time=_FIXED_NOW)
        assert result == []

    def test_other_regime_markets_excluded(self):
        old_market = {"slug": "mature", "title": "Old boring question",
                      "created_at": _iso(_FIXED_NOW - timedelta(hours=200))}
        result = filter_by_factual_regime([old_market], POLITICS, reference_time=_FIXED_NOW)
        assert result == []

    def test_invalid_target_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="target_regime must be one of"):
            filter_by_factual_regime([], "unknown", reference_time=_FIXED_NOW)

    def test_invalid_target_other_raises_value_error(self):
        with pytest.raises(ValueError, match="target_regime must be one of"):
            filter_by_factual_regime([], "other", reference_time=_FIXED_NOW)

    def test_invalid_target_garbage_raises_value_error(self):
        with pytest.raises(ValueError):
            filter_by_factual_regime([], "crypto", reference_time=_FIXED_NOW)

    def test_empty_input_returns_empty(self):
        result = filter_by_factual_regime([], POLITICS, reference_time=_FIXED_NOW)
        assert result == []

    def test_returned_dicts_have_enrichment_fields(self):
        markets = [_politics_market()]
        result = filter_by_factual_regime(markets, POLITICS, reference_time=_FIXED_NOW)
        assert len(result) == 1
        r = result[0]
        assert "regime" in r
        assert "regime_source" in r
        assert "age_hours" in r
        assert "is_new_market" in r

    def test_new_market_by_age_not_returned_as_politics(self):
        """A new-market (by age) should NOT appear in a politics filter."""
        m = _new_market_by_age(age_hours=5.0)
        result = filter_by_factual_regime([m], POLITICS, reference_time=_FIXED_NOW)
        assert result == []

    def test_politics_market_not_returned_as_new_market(self):
        """A politics market older than 48h should NOT appear in new_market filter."""
        created = _FIXED_NOW - timedelta(hours=120)
        m = _politics_market(created_at=_iso(created))
        result = filter_by_factual_regime([m], NEW_MARKET, reference_time=_FIXED_NOW)
        assert result == []

    def test_all_required_regimes_are_valid_targets(self):
        """filter_by_factual_regime must accept every REQUIRED_REGIME without raising."""
        for regime in REQUIRED_REGIMES:
            result = filter_by_factual_regime([], regime, reference_time=_FIXED_NOW)
            assert result == []


# ---------------------------------------------------------------------------
# api_client.fetch_active_markets — regime fields in returned dicts
# ---------------------------------------------------------------------------


class TestFetchActiveMarketsRegimeFields:
    """Verify that fetch_active_markets includes fields needed for regime classification."""

    def _raw_gamma_market(self) -> dict:
        return {
            "slug": "test-market",
            "best_bid": "0.48",
            "best_ask": "0.52",
            "volume_24h": 10000,
            "endDate": "2026-12-31T00:00:00Z",
            "createdAt": "2026-03-01T00:00:00Z",
            "question": "Will the senator win the election?",
            "title": "Senator Election 2026",
            "category": "politics",
            "subcategory": "US Elections",
            "tags": ["politics", "election"],
            "clobTokenIds": '["tok-abc"]',
        }

    def test_category_included_in_returned_dict(self):
        from packages.polymarket.market_selection.api_client import (
            _markets_from_response,
        )
        from packages.polymarket.market_selection.api_client import fetch_active_markets
        from packages.polymarket.http_client import HttpClient

        raw = self._raw_gamma_market()

        with patch.object(HttpClient, "get_json", return_value=[raw]):
            markets = fetch_active_markets(min_volume=0, limit=10)

        assert len(markets) == 1
        m = markets[0]
        assert m["category"] == "politics"

    def test_question_included_in_returned_dict(self):
        from packages.polymarket.market_selection.api_client import fetch_active_markets
        from packages.polymarket.http_client import HttpClient

        raw = self._raw_gamma_market()

        with patch.object(HttpClient, "get_json", return_value=[raw]):
            markets = fetch_active_markets(min_volume=0, limit=10)

        assert markets[0]["question"] == "Will the senator win the election?"

    def test_tags_included_in_returned_dict(self):
        from packages.polymarket.market_selection.api_client import fetch_active_markets
        from packages.polymarket.http_client import HttpClient

        raw = self._raw_gamma_market()

        with patch.object(HttpClient, "get_json", return_value=[raw]):
            markets = fetch_active_markets(min_volume=0, limit=10)

        assert markets[0]["tags"] == ["politics", "election"]

    def test_regime_enrichment_works_on_fetched_data(self):
        """End-to-end: fetched market enriches to correct regime."""
        from packages.polymarket.market_selection.api_client import fetch_active_markets
        from packages.polymarket.market_selection.regime_policy import enrich_with_regime
        from packages.polymarket.http_client import HttpClient

        raw = self._raw_gamma_market()

        with patch.object(HttpClient, "get_json", return_value=[raw]):
            markets = fetch_active_markets(min_volume=0, limit=10)

        enriched = enrich_with_regime(markets[0], reference_time=_FIXED_NOW)
        assert enriched["regime"] == POLITICS


# ---------------------------------------------------------------------------
# scan_gate2_candidates — regime metadata helpers (offline)
# ---------------------------------------------------------------------------


class TestReadTapeMarketFields:
    def test_reads_regime_from_quickrun_context(self, tmp_path):
        from tools.cli.scan_gate2_candidates import _read_tape_market_fields

        tape_dir = tmp_path / "tape1"
        tape_dir.mkdir()
        meta = {
            "quickrun_context": {
                "market": "some-politics-market",
                "regime": "politics",
                "age_hours": 120.0,
            }
        }
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        fields = _read_tape_market_fields(tape_dir)
        assert fields is not None
        assert fields.get("regime") == "politics"
        assert fields.get("age_hours") == 120.0
        assert fields.get("slug") == "some-politics-market"

    def test_reads_regime_from_shadow_context(self, tmp_path):
        from tools.cli.scan_gate2_candidates import _read_tape_market_fields

        tape_dir = tmp_path / "tape2"
        tape_dir.mkdir()
        meta = {
            "shadow_context": {
                "market_slug": "nfl-playoff",
                "regime": "sports",
            }
        }
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        fields = _read_tape_market_fields(tape_dir)
        assert fields is not None
        assert fields.get("regime") == "sports"
        assert fields.get("slug") == "nfl-playoff"

    def test_returns_none_on_missing_meta(self, tmp_path):
        from tools.cli.scan_gate2_candidates import _read_tape_market_fields

        tape_dir = tmp_path / "empty_tape"
        tape_dir.mkdir()

        assert _read_tape_market_fields(tape_dir) is None

    def test_returns_none_on_corrupt_json(self, tmp_path):
        from tools.cli.scan_gate2_candidates import _read_tape_market_fields

        tape_dir = tmp_path / "bad_tape"
        tape_dir.mkdir()
        (tape_dir / "meta.json").write_text("{not valid json", encoding="utf-8")

        assert _read_tape_market_fields(tape_dir) is None


class TestBuildTapeRegimeMeta:
    def test_unknown_tape_gets_other_regime(self, tmp_path):
        from tools.cli.scan_gate2_candidates import _build_tape_regime_meta

        tape_dir = tmp_path / "unknown_tape"
        tape_dir.mkdir()
        # No meta.json, no context — classifier gets minimal input
        (tape_dir / "events.jsonl").write_text("", encoding="utf-8")

        meta = _build_tape_regime_meta(tmp_path)
        # The tape is present; slug falls back to dir name; regime should be "other"
        assert "unknown_tape" in meta
        assert meta["unknown_tape"]["regime"] == OTHER
        assert meta["unknown_tape"]["regime_source"] == "derived"

    def test_politics_tape_gets_politics_regime(self, tmp_path):
        from tools.cli.scan_gate2_candidates import _build_tape_regime_meta

        tape_dir = tmp_path / "pol-tape"
        tape_dir.mkdir()
        meta = {
            "quickrun_context": {
                "market": "senator-election-2026",
                "regime": "politics",
                "category": "politics",
                "question": "Will senator win election?",
            }
        }
        (tape_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
        (tape_dir / "events.jsonl").write_text("", encoding="utf-8")

        regime_meta = _build_tape_regime_meta(tmp_path)
        assert "senator-election-2026" in regime_meta
        assert regime_meta["senator-election-2026"]["regime"] == POLITICS


# ---------------------------------------------------------------------------
# PART A: Regime-aware capture threshold defaults
# ---------------------------------------------------------------------------


class TestRegimeCaptureThresholds:
    """Tests for get_regime_capture_threshold and REGIME_CAPTURE_NEAR_EDGE_DEFAULTS.

    Verifies that capture/session-planning thresholds are LOOSER (higher) for
    politics and new_market regimes while sports default remains unchanged.
    A higher threshold means more markets qualify (yes_ask + no_ask < threshold),
    enabling near-miss detection before arb is fully profitable.

    Gate 2 pass criteria are NOT affected by these defaults.
    """

    # --- get_regime_capture_threshold —--------------------------------------

    def test_sports_threshold_unchanged(self):
        """Sports regime must return the current default threshold (0.99)."""
        assert get_regime_capture_threshold(SPORTS) == 0.99

    def test_politics_threshold_looser_than_sports(self):
        """Politics must use a higher (looser) threshold than sports."""
        assert get_regime_capture_threshold(POLITICS) > get_regime_capture_threshold(SPORTS)

    def test_new_market_threshold_looser_than_sports(self):
        """new_market must use a higher (looser) threshold than sports."""
        assert get_regime_capture_threshold(NEW_MARKET) > get_regime_capture_threshold(SPORTS)

    def test_new_market_threshold_does_not_exceed_politics(self):
        """new_market threshold may equal politics but must not exceed it."""
        assert get_regime_capture_threshold(NEW_MARKET) <= get_regime_capture_threshold(POLITICS)

    def test_unknown_regime_returns_default(self):
        """Unrecognised regimes must fall back to the global default threshold."""
        assert get_regime_capture_threshold("unknown") == _DEFAULT_CAPTURE_THRESHOLD
        assert get_regime_capture_threshold("other") == _DEFAULT_CAPTURE_THRESHOLD
        assert get_regime_capture_threshold("crypto") == _DEFAULT_CAPTURE_THRESHOLD
        assert get_regime_capture_threshold("") == _DEFAULT_CAPTURE_THRESHOLD

    def test_all_required_regimes_have_entries(self):
        """Every REQUIRED_REGIME must be present in the defaults dict."""
        for regime in REQUIRED_REGIMES:
            assert regime in REGIME_CAPTURE_NEAR_EDGE_DEFAULTS, (
                f"{regime!r} missing from REGIME_CAPTURE_NEAR_EDGE_DEFAULTS"
            )

    def test_all_thresholds_in_valid_range(self):
        """All regime thresholds must be positive and practically bounded."""
        for regime, threshold in REGIME_CAPTURE_NEAR_EDGE_DEFAULTS.items():
            assert 0.0 < threshold < 2.0, f"{regime}: threshold {threshold} out of range (0, 2)"

    def test_politics_threshold_above_one(self):
        """Politics threshold must be > 1.0 to capture near-misses before arb exists."""
        assert get_regime_capture_threshold(POLITICS) > 1.0

    def test_new_market_threshold_above_sports(self):
        """new_market threshold must be > sports threshold (captures wider net)."""
        assert get_regime_capture_threshold(NEW_MARKET) > get_regime_capture_threshold(SPORTS)

    # --- resolve_effective_threshold —---------------------------------------

    def test_resolve_no_args_uses_global_default(self):
        """No explicit buffer, no regime → global-default threshold."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold

        threshold, source = resolve_effective_threshold(None, None)
        assert source == "global-default"
        assert threshold == _DEFAULT_CAPTURE_THRESHOLD

    def test_resolve_regime_sports_uses_regime_default(self):
        """Sports regime without explicit buffer → regime-default (unchanged value)."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold

        threshold, source = resolve_effective_threshold(None, SPORTS)
        assert source == "regime-default"
        assert threshold == get_regime_capture_threshold(SPORTS)

    def test_resolve_regime_politics_uses_politics_threshold(self):
        """Politics regime without explicit buffer → looser (higher) regime threshold."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold

        threshold, source = resolve_effective_threshold(None, POLITICS)
        assert source == "regime-default"
        assert threshold == get_regime_capture_threshold(POLITICS)
        assert threshold > _DEFAULT_CAPTURE_THRESHOLD  # looser than sports default

    def test_resolve_regime_new_market_uses_new_market_threshold(self):
        """new_market regime without explicit buffer → regime threshold."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold

        threshold, source = resolve_effective_threshold(None, NEW_MARKET)
        assert source == "regime-default"
        assert threshold == get_regime_capture_threshold(NEW_MARKET)
        assert threshold > _DEFAULT_CAPTURE_THRESHOLD  # looser than sports default

    def test_resolve_explicit_buffer_overrides_regime(self):
        """Explicit --buffer converts to threshold (1.0 - buffer) and wins over regime."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold
        import pytest

        explicit_buffer = 0.05
        threshold, source = resolve_effective_threshold(explicit_buffer, POLITICS)
        assert source == "user-set"
        assert threshold == pytest.approx(0.95)  # 1.0 - 0.05

    def test_resolve_explicit_buffer_overrides_global(self):
        """Explicit --buffer wins even when no regime is specified."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold
        import pytest

        threshold, source = resolve_effective_threshold(0.02, None)
        assert source == "user-set"
        assert threshold == pytest.approx(0.98)  # 1.0 - 0.02

    # --- No UNKNOWN/off-target promotion —------------------------------------

    def test_unknown_off_target_never_promoted(self):
        """Unrecognised regimes must fall back to the global default threshold."""
        from tools.cli.scan_gate2_candidates import resolve_effective_threshold

        for bad_regime in ("unknown", "other", "crypto", ""):
            threshold, source = resolve_effective_threshold(None, bad_regime)
            assert threshold == _DEFAULT_CAPTURE_THRESHOLD, (
                f"Bad regime {bad_regime!r} produced non-default threshold {threshold}"
            )
