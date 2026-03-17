"""Tests for packages.polymarket.benchmark_gap_fill_planner.

Tests are fully offline: all DuckDB calls are replaced by fixture inject functions.
The smoke test (test_smoke_real_data) is skipped automatically when the data
roots are absent.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pytest

from packages.polymarket.benchmark_gap_fill_planner import (
    BUCKET_ORDER,
    NEAR_RESOLUTION_MAX_HOURS,
    NEW_MARKET_MAX_HOURS,
    BucketResult,
    GapFillPlanner,
    GapFillResult,
    GapFillTarget,
    classify_market,
    run,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_REF = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
_TS_START = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
_TS_END = datetime(2026, 3, 15, 14, 59, 0, tzinfo=timezone.utc)

_GAP_REPORT = {
    "shortages_by_bucket": {
        "politics": 9,
        "sports": 11,
        "crypto": 10,
        "near_resolution": 9,
        "new_market": 5,
    }
}


def _make_pmxt_rows(n: int) -> List[Tuple[str, Any, Any]]:
    """Return n synthetic pmxt rows."""
    return [
        (f"0xcond{i:04d}", _TS_START, _TS_END)
        for i in range(n)
    ]


def _make_jb_row(
    i: int,
    question: str,
    *,
    end_offset_h: Optional[float] = None,
    age_h: Optional[float] = None,
) -> Tuple[str, Optional[str], Optional[str], Optional[str], Any, Any]:
    cid = f"0xcond{i:04d}"
    slug = question.lower().replace(" ", "-")[:30]
    tok_json = json.dumps([f"{(i + 1) * 100000:050d}"])
    end_dt = (_REF + timedelta(hours=end_offset_h)) if end_offset_h is not None else None
    created_dt = (_REF - timedelta(hours=age_h)) if age_h is not None else None
    return (cid, question, slug, tok_json, end_dt, created_dt)


def _make_fixture(
    n_politics: int = 15,
    n_sports: int = 20,
    n_crypto: int = 15,
    n_near_res: int = 15,
    n_new_market: int = 0,
) -> Tuple[List, List]:
    """Return (pmxt_rows, jb_rows) fixture data."""
    jb: List = []
    offset = 0
    for _ in range(n_politics):
        jb.append(_make_jb_row(offset, f"Will trump win the election {offset}"))
        offset += 1
    for _ in range(n_sports):
        jb.append(_make_jb_row(offset, f"Will nba finals end in game 7 {offset}"))
        offset += 1
    for _ in range(n_crypto):
        jb.append(_make_jb_row(offset, f"Will bitcoin price exceed 100k {offset}"))
        offset += 1
    for k in range(n_near_res):
        jb.append(_make_jb_row(offset, f"Will award show happen {offset}", end_offset_h=float(k)))
        offset += 1
    for k in range(n_new_market):
        jb.append(_make_jb_row(offset, f"Fresh new market {offset}", age_h=float(k)))
        offset += 1

    pmxt = _make_pmxt_rows(offset)
    return pmxt, jb


def _make_planner(pmxt_rows, jb_rows, shortages=None) -> GapFillPlanner:
    s = shortages or _GAP_REPORT["shortages_by_bucket"]
    return GapFillPlanner(
        pmxt_root="/fake/pmxt",
        jon_root="/fake/jon",
        shortages=s,
        reference_time=_REF,
        _pmxt_fetch_fn=lambda: pmxt_rows,
        _jon_markets_fetch_fn=lambda ids: [r for r in jb_rows if r[0] in ids],
    )


# ---------------------------------------------------------------------------
# Unit tests: classify_market
# ---------------------------------------------------------------------------


class TestClassifyMarket:
    def test_crypto_keyword_bitcoin(self):
        buckets, notes = classify_market("Will bitcoin price exceed $100k?", "bitcoin-100k", None, None, _REF)
        assert "crypto" in buckets

    def test_crypto_keyword_eth(self):
        buckets, _ = classify_market("Will ethereum hit all time high?", "eth-ath", None, None, _REF)
        assert "crypto" in buckets

    def test_politics_keyword_trump(self):
        buckets, _ = classify_market("Will trump win the 2026 election?", "trump-wins", None, None, _REF)
        assert "politics" in buckets

    def test_politics_keyword_election(self):
        buckets, _ = classify_market("Will the election results be certified?", "election-cert", None, None, _REF)
        assert "politics" in buckets

    def test_sports_keyword_nba(self):
        buckets, _ = classify_market("Will the NBA finals go to game 7?", "nba-game-7", None, None, _REF)
        assert "sports" in buckets

    def test_sports_keyword_nhl_stanley_cup(self):
        buckets, _ = classify_market("Will Toronto win the Stanley Cup 2026?", "toronto-stanley-cup", None, None, _REF)
        assert "sports" in buckets

    def test_near_resolution_end_within_24h(self):
        end = _REF + timedelta(hours=12)
        buckets, notes = classify_market("Some market", "some-market", end, None, _REF)
        assert "near_resolution" in buckets
        assert any("hours_to_end=12.0" in n for n in notes)

    def test_near_resolution_end_at_boundary(self):
        end = _REF + timedelta(hours=NEAR_RESOLUTION_MAX_HOURS)
        buckets, _ = classify_market("Some market", "some-market", end, None, _REF)
        assert "near_resolution" in buckets

    def test_near_resolution_too_far(self):
        end = _REF + timedelta(hours=NEAR_RESOLUTION_MAX_HOURS + 1)
        buckets, _ = classify_market("Some market", "some-market", end, None, _REF)
        assert "near_resolution" not in buckets

    def test_new_market_created_within_48h(self):
        created = _REF - timedelta(hours=24)
        buckets, notes = classify_market("A fresh market", "fresh-market", None, created, _REF)
        assert "new_market" in buckets

    def test_new_market_too_old(self):
        created = _REF - timedelta(hours=NEW_MARKET_MAX_HOURS + 1)
        buckets, _ = classify_market("Old market", "old-market", None, created, _REF)
        assert "new_market" not in buckets

    def test_no_bucket_unrelated_text(self):
        buckets, _ = classify_market("Will it rain tomorrow?", "will-it-rain", None, None, _REF)
        assert buckets == []

    def test_multi_bucket_market(self):
        # Market that is both sports + near_resolution
        end = _REF + timedelta(hours=10)
        buckets, _ = classify_market("Will NBA champion be crowned?", "nba-champion", end, None, _REF)
        assert "sports" in buckets
        assert "near_resolution" in buckets

    def test_bucket_order_preserved(self):
        end = _REF + timedelta(hours=10)
        buckets, _ = classify_market("Will bitcoin election vote happen?", "btc-election", end, None, _REF)
        # Verify order matches BUCKET_ORDER (politics before crypto, before near_resolution)
        indices = [BUCKET_ORDER.index(b) for b in buckets]
        assert indices == sorted(indices)

    def test_notes_count_matches_buckets(self):
        end = _REF + timedelta(hours=5)
        buckets, notes = classify_market("Will NBA finals end soon?", "nba-finals", end, None, _REF)
        assert len(buckets) == len(notes)


# ---------------------------------------------------------------------------
# Unit tests: GapFillPlanner
# ---------------------------------------------------------------------------


class TestGapFillPlanner:
    def test_plan_produces_targets_when_covered(self):
        pmxt, jb = _make_fixture(n_politics=15, n_sports=20, n_crypto=15, n_near_res=15, n_new_market=0)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()

        assert result.any_targets
        buckets_in_targets = {t.bucket for t in result.targets}
        assert "politics" in buckets_in_targets
        assert "sports" in buckets_in_targets
        assert "crypto" in buckets_in_targets
        assert "near_resolution" in buckets_in_targets

    def test_plan_new_market_insufficient_when_zero_candidates(self):
        pmxt, jb = _make_fixture(n_new_market=0)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()

        new_mkt_br = next(br for br in result.bucket_results if br.bucket == "new_market")
        assert new_mkt_br.insufficient is True
        assert new_mkt_br.candidates_found == 0
        assert new_mkt_br.shortage == 5

    def test_plan_insufficient_when_shortage_exceeds_found(self):
        pmxt, jb = _make_fixture(n_politics=3)  # need 9, have 3
        planner = _make_planner(pmxt, jb)
        result = planner.plan()

        pol_br = next(br for br in result.bucket_results if br.bucket == "politics")
        assert pol_br.insufficient is True
        assert pol_br.candidates_found == 3
        assert pol_br.shortage == 9

    def test_plan_not_insufficient_when_enough_found(self):
        pmxt, jb = _make_fixture(n_politics=15, n_sports=20, n_crypto=15, n_near_res=15)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()

        for bucket in ("politics", "sports", "crypto", "near_resolution"):
            br = next(b for b in result.bucket_results if b.bucket == bucket)
            assert br.insufficient is False, f"{bucket} should not be insufficient"

    def test_plan_priority_labels_correct(self):
        pmxt, jb = _make_fixture(n_politics=15)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()

        pol_targets = [t for t in result.targets if t.bucket == "politics"]
        p1 = [t for t in pol_targets if t.priority == 1]
        p2 = [t for t in pol_targets if t.priority == 2]
        # shortage=9, so exactly 9 priority-1 targets
        assert len(p1) == 9
        assert len(p2) == 15 - 9

    def test_plan_targets_have_token_ids(self):
        pmxt, jb = _make_fixture(n_politics=5, n_sports=5, n_crypto=5, n_near_res=5)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()

        for t in result.targets:
            assert t.token_id, f"target {t.slug} missing token_id"

    def test_plan_empty_pmxt_returns_error(self):
        planner = _make_planner([], [])
        result = planner.plan()
        assert result.error is not None
        assert not result.any_targets

    def test_plan_no_jb_matches_returns_no_targets(self):
        pmxt = _make_pmxt_rows(5)
        # JB rows have different condition_ids — no matches
        jb = [_make_jb_row(100, "Will btc rise?")]  # cond0100 not in pmxt (0-4)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()
        assert not result.any_targets

    def test_plan_near_resolution_sorted_by_proximity(self):
        # near_res markets with different hours_to_end — closest should come first
        pmxt = _make_pmxt_rows(3)
        jb = [
            _make_jb_row(0, "Award show tomorrow", end_offset_h=36.0),
            _make_jb_row(1, "Award show today", end_offset_h=2.0),
            _make_jb_row(2, "Award show soon", end_offset_h=12.0),
        ]
        planner = _make_planner(pmxt, jb, shortages={"near_resolution": 3})
        result = planner.plan()

        nr_targets = [t for t in result.targets if t.bucket == "near_resolution"]
        assert len(nr_targets) == 3
        # The first one should have 2h end (slug: "award-show-today")
        assert "today" in nr_targets[0].slug

    def test_plan_deduplicates_condition_ids_per_bucket(self):
        # Feed same condition_id twice in different JB rows
        pmxt = _make_pmxt_rows(1)
        tok_json = json.dumps(["99999"])
        jb = [
            ("0xcond0000", "Will btc rise?", "btc-rise", tok_json, None, None),
            ("0xcond0000", "Will btc rise?", "btc-rise", tok_json, None, None),  # duplicate
        ]
        planner = _make_planner(pmxt, jb, shortages={"crypto": 1})
        result = planner.plan()

        crypto_targets = [t for t in result.targets if t.bucket == "crypto"]
        assert len(crypto_targets) == 1  # deduped

    def test_plan_fully_sufficient_property(self):
        pmxt, jb = _make_fixture(n_politics=15, n_sports=20, n_crypto=15, n_near_res=15, n_new_market=10)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()
        assert result.fully_sufficient

    def test_plan_not_fully_sufficient_when_new_market_zero(self):
        pmxt, jb = _make_fixture(n_new_market=0)
        planner = _make_planner(pmxt, jb)
        result = planner.plan()
        assert not result.fully_sufficient


# ---------------------------------------------------------------------------
# Output schema tests
# ---------------------------------------------------------------------------


class TestOutputSchema:
    def test_to_targets_dict_has_required_keys(self):
        pmxt, jb = _make_fixture(n_politics=5, n_sports=5, n_crypto=5, n_near_res=5)
        result = _make_planner(pmxt, jb).plan()
        d = result.to_targets_dict()

        assert d["schema_version"] == "benchmark_gap_fill_v1"
        assert "generated_at" in d
        assert "source_roots" in d
        assert isinstance(d["targets"], list)

    def test_each_target_has_contract_keys(self):
        pmxt, jb = _make_fixture(n_politics=5)
        result = _make_planner(pmxt, jb).plan()
        d = result.to_targets_dict()

        required = {
            "bucket", "platform", "slug", "market_id", "token_id",
            "window_start", "window_end", "priority", "selection_reason", "price_2min_ready",
        }
        for target in d["targets"]:
            assert required <= set(target.keys()), f"Missing keys: {required - set(target.keys())}"

    def test_price_2min_ready_always_false_in_planner(self):
        pmxt, jb = _make_fixture(n_politics=5)
        result = _make_planner(pmxt, jb).plan()
        for t in result.targets:
            assert t.price_2min_ready is False

    def test_insufficiency_dict_schema(self):
        pmxt, jb = _make_fixture(n_new_market=0)
        result = _make_planner(pmxt, jb).plan()
        d = result.to_insufficiency_dict()

        assert d["schema_version"] == "benchmark_gap_fill_insufficient_v1"
        assert "generated_at" in d
        assert "source_roots" in d
        assert "insufficient_buckets" in d
        # new_market must be in insufficient_buckets
        assert "new_market" in d["insufficient_buckets"]

    def test_run_writes_targets_file(self, tmp_path):
        pmxt, jb = _make_fixture(n_politics=15, n_sports=20, n_crypto=15, n_near_res=15)
        out_path = tmp_path / "targets.json"

        result = run(
            pmxt_root="/fake/pmxt",
            jon_root="/fake/jon",
            gap_report=_GAP_REPORT,
            out_path=out_path,
            reference_time=_REF,
            _pmxt_fetch_fn=lambda: pmxt,
            _jon_markets_fetch_fn=lambda ids: [r for r in jb if r[0] in ids],
        )

        assert out_path.exists()
        content = json.loads(out_path.read_text())
        assert content["schema_version"] == "benchmark_gap_fill_v1"
        assert len(content["targets"]) > 0

    def test_run_writes_insufficiency_file(self, tmp_path):
        pmxt, jb = _make_fixture(n_new_market=0)
        insuff_path = tmp_path / "insufficiency.json"

        run(
            pmxt_root="/fake/pmxt",
            jon_root="/fake/jon",
            gap_report=_GAP_REPORT,
            insufficiency_path=insuff_path,
            reference_time=_REF,
            _pmxt_fetch_fn=lambda: pmxt,
            _jon_markets_fetch_fn=lambda ids: [r for r in jb if r[0] in ids],
        )

        assert insuff_path.exists()
        content = json.loads(insuff_path.read_text())
        assert "new_market" in content["insufficient_buckets"]


# ---------------------------------------------------------------------------
# Smoke test against real local data
# ---------------------------------------------------------------------------

_PMXT_ROOT = r"D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive"
_JON_ROOT = r"D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"


def _real_roots_present() -> bool:
    return (
        Path(_PMXT_ROOT, "Polymarket").exists()
        and Path(_JON_ROOT, "data", "polymarket", "markets").exists()
    )


@pytest.mark.skipif(not _real_roots_present(), reason="real data roots not present")
class TestSmokeRealData:
    def test_smoke_plan_produces_targets_and_new_market_insufficient(self):
        planner = GapFillPlanner(
            pmxt_root=_PMXT_ROOT,
            jon_root=_JON_ROOT,
            shortages=_GAP_REPORT["shortages_by_bucket"],
            reference_time=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
        )
        result = planner.plan()

        # Must produce targets for covered buckets
        assert result.any_targets
        buckets_found = {t.bucket for t in result.targets}
        for bucket in ("politics", "sports", "crypto", "near_resolution"):
            br = next(b for b in result.bucket_results if b.bucket == bucket)
            assert br.candidates_found >= br.shortage, (
                f"{bucket}: found {br.candidates_found} < needed {br.shortage}"
            )
            assert bucket in buckets_found

        # new_market must still be insufficient
        nm_br = next(b for b in result.bucket_results if b.bucket == "new_market")
        assert nm_br.insufficient, "new_market expected to be insufficient from real data"
        assert nm_br.candidates_found == 0

        # Verify output schema
        d = result.to_targets_dict()
        assert d["schema_version"] == "benchmark_gap_fill_v1"
        for t in d["targets"]:
            assert t["token_id"], f"token_id missing on {t['slug']}"
