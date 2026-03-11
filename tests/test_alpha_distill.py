"""Tests for tools.cli.alpha_distill."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from tools.cli.alpha_distill import (
    _SegmentAccumulator,
    _build_candidate,
    _friction_risk_flags,
    _score_accumulator,
    distill,
    load_user_segment_analysis,
    load_wallet_scan_run,
)

FIXED_NOW = datetime(2026, 3, 5, 12, 0, 0, tzinfo=timezone.utc)
FIXED_FEE_ADJ = 0.02
FIXED_MIN_SAMPLE = 10  # low threshold for tests


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, records: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(r) for r in records) + "\n",
        encoding="utf-8",
    )


def _make_segment_bucket(
    *,
    count: int = 20,
    wins: int = 10,
    losses: int = 5,
    profit_exits: int = 3,
    loss_exits: int = 2,
    total_pnl_net: float = 5.0,
    avg_clv_pct: Optional[float] = 0.04,
    avg_clv_pct_count_used: int = 15,
    beat_close_rate: Optional[float] = 0.60,
    beat_close_rate_count_used: int = 15,
    notional_weighted_avg_clv_pct: Optional[float] = 0.05,
    notional_weighted_avg_clv_pct_weight_used: float = 100.0,
    notional_weighted_beat_close_rate: Optional[float] = 0.62,
    notional_weighted_beat_close_rate_weight_used: float = 100.0,
) -> Dict:
    return {
        "count": count,
        "wins": wins,
        "losses": losses,
        "profit_exits": profit_exits,
        "loss_exits": loss_exits,
        "win_rate": (wins + profit_exits) / max(1, wins + losses + profit_exits + loss_exits),
        "total_pnl_net": total_pnl_net,
        "avg_clv_pct": avg_clv_pct,
        "avg_clv_pct_count_used": avg_clv_pct_count_used,
        "beat_close_rate": beat_close_rate,
        "beat_close_rate_count_used": beat_close_rate_count_used,
        "notional_weighted_avg_clv_pct": notional_weighted_avg_clv_pct,
        "notional_weighted_avg_clv_pct_weight_used": notional_weighted_avg_clv_pct_weight_used,
        "notional_weighted_beat_close_rate": notional_weighted_beat_close_rate,
        "notional_weighted_beat_close_rate_weight_used": notional_weighted_beat_close_rate_weight_used,
    }


def _make_segment_analysis_json(
    path: Path,
    *,
    by_entry_price_tier: Optional[Dict] = None,
    by_market_type: Optional[Dict] = None,
    by_league: Optional[Dict] = None,
) -> None:
    inner = {
        "entry_price_tiers": [],
        "by_entry_price_tier": by_entry_price_tier or {},
        "by_market_type": by_market_type or {},
        "by_league": by_league or {},
        "by_sport": {},
        "by_category": {},
        "hypothesis_meta": {"notional_weight_total_global": 200.0},
    }
    _write_json(path, {
        "generated_at": "2026-03-05T12:00:00+00:00",
        "run_id": "test-run",
        "user_slug": "alice",
        "wallet": "0xalice",
        "segment_analysis": inner,
    })


def _make_wallet_scan_run(
    base: Path,
    name: str,
    *,
    per_user: List[Dict],
) -> Path:
    """Create a minimal wallet-scan run directory."""
    run_root = base / name
    run_root.mkdir(parents=True, exist_ok=True)

    leaderboard = {
        "run_id": "test-lb-run",
        "created_at": "2026-03-05T12:00:00+00:00",
        "profile": "lite",
        "scan_flags": {},
        "input_file": "wallets.txt",
        "entries_attempted": len(per_user),
        "entries_succeeded": sum(1 for r in per_user if r.get("status") == "success"),
        "entries_failed": sum(1 for r in per_user if r.get("status") != "success"),
        "ranked": [
            {
                "rank": i + 1,
                "slug": r.get("slug"),
                "identifier": r.get("identifier"),
                "realized_net_pnl": r.get("realized_net_pnl"),
                "run_root": r.get("run_root"),
            }
            for i, r in enumerate(r for r in per_user if r.get("status") == "success")
        ],
    }
    _write_json(run_root / "leaderboard.json", leaderboard)
    _write_jsonl(run_root / "per_user_results.jsonl", per_user)

    return run_root


# ---------------------------------------------------------------------------
# load_wallet_scan_run
# ---------------------------------------------------------------------------


class TestLoadWalletScanRun:
    def test_loads_leaderboard_and_jsonl(self, tmp_path: Path) -> None:
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success", "run_root": "/tmp/alice"},
        ]
        ws_run = _make_wallet_scan_run(tmp_path, "ws_run", per_user=per_user)

        lb, pu = load_wallet_scan_run(ws_run)
        assert lb["run_id"] == "test-lb-run"
        assert len(pu) == 1
        assert pu[0]["slug"] == "alice"

    def test_raises_on_missing_leaderboard(self, tmp_path: Path) -> None:
        ws_run = tmp_path / "empty_run"
        ws_run.mkdir()
        (ws_run / "per_user_results.jsonl").write_text("")
        with pytest.raises(FileNotFoundError, match="leaderboard.json"):
            load_wallet_scan_run(ws_run)

    def test_raises_on_missing_jsonl(self, tmp_path: Path) -> None:
        ws_run = tmp_path / "empty_run"
        ws_run.mkdir()
        _write_json(ws_run / "leaderboard.json", {"run_id": "x"})
        with pytest.raises(FileNotFoundError, match="per_user_results.jsonl"):
            load_wallet_scan_run(ws_run)


# ---------------------------------------------------------------------------
# load_user_segment_analysis
# ---------------------------------------------------------------------------


class TestLoadUserSegmentAnalysis:
    def test_loads_inner_segment_analysis(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "alice_run"
        scan_root.mkdir()
        _make_segment_analysis_json(
            scan_root / "segment_analysis.json",
            by_entry_price_tier={"deep_underdog": _make_segment_bucket()},
        )
        result = load_user_segment_analysis(scan_root.as_posix())
        assert result is not None
        assert "by_entry_price_tier" in result
        assert "deep_underdog" in result["by_entry_price_tier"]

    def test_returns_none_on_missing_file(self, tmp_path: Path) -> None:
        result = load_user_segment_analysis((tmp_path / "no_such_dir").as_posix())
        assert result is None

    def test_returns_none_on_corrupt_json(self, tmp_path: Path) -> None:
        scan_root = tmp_path / "corrupt_run"
        scan_root.mkdir()
        (scan_root / "segment_analysis.json").write_text("not json", encoding="utf-8")
        result = load_user_segment_analysis(scan_root.as_posix())
        assert result is None


# ---------------------------------------------------------------------------
# _SegmentAccumulator
# ---------------------------------------------------------------------------


class TestSegmentAccumulator:
    def test_accumulates_single_user(self) -> None:
        acc = _SegmentAccumulator("entry_price_tier", "deep_underdog")
        bucket = _make_segment_bucket(count=20, avg_clv_pct=0.05, avg_clv_pct_count_used=15)
        acc.add("alice", "/tmp/alice", bucket)

        assert acc.total_count == 20
        assert acc.users_contributing == 1
        assert acc.aggregate_avg_clv_pct() == pytest.approx(0.05)

    def test_accumulates_two_users_weighted_clv(self) -> None:
        acc = _SegmentAccumulator("entry_price_tier", "deep_underdog")
        # User 1: 10 positions, avg_clv=0.04 (count_used=10)
        acc.add("alice", "/tmp/alice", _make_segment_bucket(
            count=10, avg_clv_pct=0.04, avg_clv_pct_count_used=10,
            wins=5, losses=2, profit_exits=2, loss_exits=1,
        ))
        # User 2: 20 positions, avg_clv=0.06 (count_used=20)
        acc.add("bob", "/tmp/bob", _make_segment_bucket(
            count=20, avg_clv_pct=0.06, avg_clv_pct_count_used=20,
            wins=10, losses=5, profit_exits=3, loss_exits=2,
        ))

        assert acc.total_count == 30
        assert acc.users_contributing == 2
        # Weighted avg = (0.04*10 + 0.06*20) / 30 = (0.4 + 1.2) / 30 = 0.053333...
        assert acc.aggregate_avg_clv_pct() == pytest.approx(0.053333, abs=1e-4)

    def test_skips_zero_count_bucket(self) -> None:
        acc = _SegmentAccumulator("entry_price_tier", "deep_underdog")
        bucket = _make_segment_bucket(count=0)
        acc.add("alice", "/tmp/alice", bucket)
        assert acc.total_count == 0
        assert acc.users_contributing == 0

    def test_win_rate_aggregation(self) -> None:
        acc = _SegmentAccumulator("league", "nfl")
        # 10 WIN + 5 PROFIT_EXIT = 15 numerator; 10+5+5+5 = 25 denominator
        acc.add("alice", "/tmp/alice", _make_segment_bucket(
            count=25, wins=10, losses=5, profit_exits=5, loss_exits=5,
            avg_clv_pct=None, avg_clv_pct_count_used=0,
        ))
        assert acc.aggregate_win_rate() == pytest.approx(15 / 25)

    def test_nw_clv_aggregation(self) -> None:
        acc = _SegmentAccumulator("sport", "basketball")
        acc.add("alice", "/tmp/alice", _make_segment_bucket(
            count=10,
            notional_weighted_avg_clv_pct=0.03,
            notional_weighted_avg_clv_pct_weight_used=100.0,
        ))
        acc.add("bob", "/tmp/bob", _make_segment_bucket(
            count=10,
            notional_weighted_avg_clv_pct=0.07,
            notional_weighted_avg_clv_pct_weight_used=200.0,
        ))
        # Weighted: (0.03*100 + 0.07*200) / 300 = (3 + 14) / 300 = 0.05667
        assert acc.aggregate_nw_clv_pct() == pytest.approx(17 / 300, abs=1e-5)


# ---------------------------------------------------------------------------
# _friction_risk_flags
# ---------------------------------------------------------------------------


class TestFrictionRiskFlags:
    def _acc(self, count: int, clv_count: int, users: int) -> _SegmentAccumulator:
        acc = _SegmentAccumulator("entry_price_tier", "deep_underdog")
        bucket = _make_segment_bucket(
            count=count,
            avg_clv_pct_count_used=clv_count,
        )
        for i in range(users):
            acc.add(f"user{i}", f"/tmp/user{i}", bucket)
        return acc

    def test_always_includes_fee_estimate_only(self) -> None:
        acc = self._acc(count=50, clv_count=40, users=3)
        flags = _friction_risk_flags(acc, min_sample=10)
        assert "fee_estimate_only" in flags

    def test_small_sample_flag(self) -> None:
        # count=3 × 2 users = total_count=6 < min_sample=10
        acc = self._acc(count=3, clv_count=2, users=2)
        flags = _friction_risk_flags(acc, min_sample=10)
        assert "small_sample" in flags

    def test_no_small_sample_flag_when_sufficient(self) -> None:
        acc = self._acc(count=50, clv_count=40, users=2)
        flags = _friction_risk_flags(acc, min_sample=10)
        assert "small_sample" not in flags

    def test_single_user_only_flag(self) -> None:
        acc = _SegmentAccumulator("entry_price_tier", "deep_underdog")
        acc.add("alice", "/tmp/alice", _make_segment_bucket(count=50))
        flags = _friction_risk_flags(acc, min_sample=10)
        assert "single_user_only" in flags

    def test_no_single_user_flag_with_two_users(self) -> None:
        acc = _SegmentAccumulator("entry_price_tier", "deep_underdog")
        acc.add("alice", "/tmp/alice", _make_segment_bucket(count=30))
        acc.add("bob", "/tmp/bob", _make_segment_bucket(count=30))
        flags = _friction_risk_flags(acc, min_sample=10)
        assert "single_user_only" not in flags

    def test_clv_data_sparse_flag(self) -> None:
        acc = _SegmentAccumulator("league", "nfl")
        # count=50, clv_count_used=5 → coverage=10% < 30%
        acc._clv_count_used = 5
        acc.total_count = 50
        acc.users.append("alice")
        flags = _friction_risk_flags(acc, min_sample=10)
        assert "clv_data_sparse" in flags


# ---------------------------------------------------------------------------
# _score_accumulator
# ---------------------------------------------------------------------------


class TestScoreAccumulator:
    def test_more_users_scores_higher(self) -> None:
        acc1 = _SegmentAccumulator("league", "nfl")
        acc1.add("alice", "/tmp/a", _make_segment_bucket(count=20))

        acc2 = _SegmentAccumulator("league", "nfl")
        acc2.add("alice", "/tmp/a", _make_segment_bucket(count=20))
        acc2.add("bob", "/tmp/b", _make_segment_bucket(count=20))

        s1 = _score_accumulator(acc1, conservative_fee_adj=FIXED_FEE_ADJ)
        s2 = _score_accumulator(acc2, conservative_fee_adj=FIXED_FEE_ADJ)
        assert s2 > s1

    def test_positive_clv_scores_higher(self) -> None:
        # Same users and count; differ in CLV
        acc_pos = _SegmentAccumulator("league", "nfl")
        acc_pos.add("alice", "/tmp/a", _make_segment_bucket(
            count=20, notional_weighted_avg_clv_pct=0.10,
        ))
        acc_neg = _SegmentAccumulator("league", "nfl")
        acc_neg.add("alice", "/tmp/a", _make_segment_bucket(
            count=20, notional_weighted_avg_clv_pct=-0.10,
        ))
        s_pos = _score_accumulator(acc_pos, conservative_fee_adj=FIXED_FEE_ADJ)
        s_neg = _score_accumulator(acc_neg, conservative_fee_adj=FIXED_FEE_ADJ)
        assert s_pos > s_neg


# ---------------------------------------------------------------------------
# distill — full integration (fixture-based, no network/ClickHouse)
# ---------------------------------------------------------------------------


class TestDistill:
    def _make_scan_run_root(
        self,
        base: Path,
        name: str,
        *,
        by_entry_price_tier: Optional[Dict] = None,
        by_league: Optional[Dict] = None,
    ) -> Path:
        scan_root = base / name
        scan_root.mkdir(parents=True, exist_ok=True)
        _make_segment_analysis_json(
            scan_root / "segment_analysis.json",
            by_entry_price_tier=by_entry_price_tier,
            by_league=by_league,
        )
        # Also write a minimal coverage_reconciliation_report.json (wallet_scan reads this)
        _write_json(
            scan_root / "coverage_reconciliation_report.json",
            {"positions_total": 50, "pnl": {"realized_pnl_net_estimated_fees_total": 5.0}},
        )
        return scan_root

    def test_produces_candidates_with_required_fields(self, tmp_path: Path) -> None:
        scan_root_alice = self._make_scan_run_root(
            tmp_path / "scans",
            "alice",
            by_entry_price_tier={
                "deep_underdog": _make_segment_bucket(count=20),
            },
        )
        scan_root_bob = self._make_scan_run_root(
            tmp_path / "scans",
            "bob",
            by_entry_price_tier={
                "deep_underdog": _make_segment_bucket(count=15),
            },
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root_alice.as_posix(), "realized_net_pnl": 5.0},
            {"slug": "bob", "identifier": "@Bob", "status": "success",
             "run_root": scan_root_bob.as_posix(), "realized_net_pnl": 2.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(
            ws_run,
            min_sample=FIXED_MIN_SAMPLE,
            conservative_fee_adj=FIXED_FEE_ADJ,
            now_provider=lambda: FIXED_NOW,
        )

        assert result["schema_version"] == "alpha_distill_v0"
        candidates = result["candidates"]
        assert len(candidates) > 0

        # Every candidate must have all required fields
        required_fields = {
            "candidate_id", "rank", "label", "mechanism_hint",
            "evidence_refs", "sample_size", "required_min_sample",
            "measured_edge", "friction_risk_flags", "next_test", "stop_condition",
        }
        for c in candidates:
            assert required_fields.issubset(c.keys()), f"Missing fields in {c.get('candidate_id')}"

    def test_segments_below_min_sample_excluded(self, tmp_path: Path) -> None:
        # count=3 — below FIXED_MIN_SAMPLE=10
        scan_root = self._make_scan_run_root(
            tmp_path / "scans",
            "alice",
            by_entry_price_tier={
                "deep_underdog": _make_segment_bucket(count=3),
            },
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root.as_posix(), "realized_net_pnl": 1.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(ws_run, min_sample=FIXED_MIN_SAMPLE, now_provider=lambda: FIXED_NOW)
        # deep_underdog count=3 < 10, must not appear
        candidate_ids = [c["candidate_id"] for c in result["candidates"]]
        assert not any("deep_underdog" in cid for cid in candidate_ids)

    def test_failed_users_excluded_from_analysis(self, tmp_path: Path) -> None:
        scan_root_alice = self._make_scan_run_root(
            tmp_path / "scans", "alice",
            by_entry_price_tier={"deep_underdog": _make_segment_bucket(count=20)},
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root_alice.as_posix(), "realized_net_pnl": 5.0},
            {"slug": "bob", "identifier": "@Bob", "status": "failure",
             "run_root": None, "error": "Network error", "realized_net_pnl": None},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(ws_run, min_sample=FIXED_MIN_SAMPLE, now_provider=lambda: FIXED_NOW)
        assert result["summary"]["total_users_analyzed"] == 1

    def test_candidates_sorted_by_score(self, tmp_path: Path) -> None:
        # Two segments: nfl (2 users) and nba (1 user). nfl should rank higher.
        scan_root_alice = self._make_scan_run_root(
            tmp_path / "scans", "alice",
            by_league={"nfl": _make_segment_bucket(count=20), "nba": _make_segment_bucket(count=20)},
        )
        scan_root_bob = self._make_scan_run_root(
            tmp_path / "scans", "bob",
            by_league={"nfl": _make_segment_bucket(count=20)},  # bob only has nfl
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root_alice.as_posix(), "realized_net_pnl": 5.0},
            {"slug": "bob", "identifier": "@Bob", "status": "success",
             "run_root": scan_root_bob.as_posix(), "realized_net_pnl": 3.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(ws_run, min_sample=FIXED_MIN_SAMPLE, now_provider=lambda: FIXED_NOW)
        candidates = result["candidates"]
        # nfl appears in 2 users, nba in 1 — nfl should rank 1
        top = candidates[0]
        assert "nfl" in top["candidate_id"]

    def test_measured_edge_net_clv_after_fee(self, tmp_path: Path) -> None:
        nw_clv = 0.06
        scan_root = self._make_scan_run_root(
            tmp_path / "scans", "alice",
            by_entry_price_tier={
                "deep_underdog": _make_segment_bucket(
                    count=20,
                    notional_weighted_avg_clv_pct=nw_clv,
                    notional_weighted_avg_clv_pct_weight_used=200.0,
                ),
            },
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root.as_posix(), "realized_net_pnl": 5.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(
            ws_run, min_sample=FIXED_MIN_SAMPLE,
            conservative_fee_adj=FIXED_FEE_ADJ,
            now_provider=lambda: FIXED_NOW,
        )
        candidates = [c for c in result["candidates"] if "deep_underdog" in c["candidate_id"]]
        assert len(candidates) == 1
        edge = candidates[0]["measured_edge"]
        assert edge["net_clv_after_fee_adj"] == pytest.approx(nw_clv - FIXED_FEE_ADJ)

    def test_unknown_segment_keys_excluded(self, tmp_path: Path) -> None:
        scan_root = self._make_scan_run_root(
            tmp_path / "scans", "alice",
            by_league={"unknown": _make_segment_bucket(count=50)},
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root.as_posix(), "realized_net_pnl": 5.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(ws_run, min_sample=FIXED_MIN_SAMPLE, now_provider=lambda: FIXED_NOW)
        candidate_ids = [c["candidate_id"] for c in result["candidates"]]
        assert not any("__unknown__" in cid for cid in candidate_ids)

    def test_summary_fields_present(self, tmp_path: Path) -> None:
        scan_root = self._make_scan_run_root(
            tmp_path / "scans", "alice",
            by_entry_price_tier={"favorite": _make_segment_bucket(count=20)},
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root.as_posix(), "realized_net_pnl": 3.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(ws_run, min_sample=FIXED_MIN_SAMPLE, now_provider=lambda: FIXED_NOW)
        summary = result["summary"]
        assert "total_users_in_leaderboard" in summary
        assert "total_users_analyzed" in summary
        assert "users_with_segment_data" in summary
        assert "total_segments_evaluated" in summary
        assert "candidates_generated" in summary

    def test_rank_field_starts_at_1_and_is_contiguous(self, tmp_path: Path) -> None:
        scan_root = self._make_scan_run_root(
            tmp_path / "scans", "alice",
            by_entry_price_tier={
                "deep_underdog": _make_segment_bucket(count=20),
                "favorite": _make_segment_bucket(count=20),
            },
            by_league={"nfl": _make_segment_bucket(count=15)},
        )
        per_user = [
            {"slug": "alice", "identifier": "@Alice", "status": "success",
             "run_root": scan_root.as_posix(), "realized_net_pnl": 3.0},
        ]
        ws_run = _make_wallet_scan_run(tmp_path / "ws", "run1", per_user=per_user)

        result = distill(ws_run, min_sample=FIXED_MIN_SAMPLE, now_provider=lambda: FIXED_NOW)
        ranks = [c["rank"] for c in result["candidates"]]
        assert ranks == list(range(1, len(ranks) + 1))
