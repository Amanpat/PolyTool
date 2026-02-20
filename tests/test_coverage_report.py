"""Tests for polytool.reports.coverage — Coverage & Reconciliation Report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from polytool.reports.coverage import (
    PENDING_COVERAGE_INVALID_WARNING,
    REPORT_VERSION,
    TOP_SEGMENT_MIN_COUNT,
    MAX_ROBUST_VALUES,
    backfill_market_metadata,
    build_coverage_report,
    extract_position_notional_usd,
    normalize_fee_fields,
    write_coverage_report,
    _get_category_key,
    _collect_top_segments_by_metric,
    _compute_median,
    _compute_robust_stats,
    _build_clv_coverage,
    _build_hypothesis_candidates,
    write_hypothesis_candidates,
)


def _make_positions():
    """Build a synthetic set of positions for testing."""
    return [
        {
            "resolved_token_id": "tok_001",
            "resolution_outcome": "WIN",
            "realized_pnl_net": 10.5,
            "fees_actual": 0.25,
            "fees_estimated": 0.0,
            "fees_source": "actual",
            "position_remaining": 5.0,
        },
        {
            "resolved_token_id": "tok_002",
            "resolution_outcome": "LOSS",
            "realized_pnl_net": -3.2,
            "fees_actual": 0.0,
            "fees_estimated": 0.12,
            "fees_source": "estimated",
            "position_remaining": 2.0,
        },
        {
            "resolved_token_id": "tok_003",
            "resolution_outcome": "PROFIT_EXIT",
            "realized_pnl_net": 7.0,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "tok_004",
            "resolution_outcome": "LOSS_EXIT",
            "realized_pnl_net": -1.0,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "tok_005",
            "resolution_outcome": "PENDING",
            "realized_pnl_net": 0.0,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 10.0,
        },
        {
            "resolved_token_id": "tok_006",
            "resolution_outcome": "UNKNOWN_RESOLUTION",
            "realized_pnl_net": None,
            "fees_actual": 0.0,
            "fees_estimated": 0.0,
            "fees_source": "unknown",
            "position_remaining": 0.0,
        },
    ]


def _make_segment_fixture_positions():
    """Roadmap 4.2 fixture: all outcomes + tier/league/market-type coverage."""
    return [
        {
            "resolved_token_id": "seg_001",
            "entry_price": 0.12,  # deep_underdog
            "market_slug": "nba-lal-bos-2026-01-01-lal",
            "question": "Will Los Angeles Lakers win on 2026-01-01?",
            "resolution_outcome": "WIN",
            "realized_pnl_net": 4.0,
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "seg_002",
            "entry_price": 0.35,  # underdog
            "market_slug": "nfl-kc-buf-2026-01-10-kc",
            "question": "Will Kansas City Chiefs win on 2026-01-10?",
            "resolution_outcome": "WIN",
            "realized_pnl_net": 3.0,
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "seg_003",
            "entry_price": 0.50,  # coinflip
            "market_slug": "mls-mia-nyc-2026-01-12-mia",
            "question": "Will Inter Miami cover the spread?",
            "resolution_outcome": "LOSS",
            "realized_pnl_net": -2.0,
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "seg_004",
            "entry_price": 0.72,  # favorite
            "market_slug": "nhl-nyr-bos-2026-01-12-nyr",
            "question": "How many goals will be scored?",
            "resolution_outcome": "LOSS_EXIT",
            "realized_pnl_net": -1.0,
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "seg_005",
            "entry_price": 0.33,  # underdog
            "market_slug": "mystery-market-5",  # unknown league
            "question": "Outcome pending?",
            "resolution_outcome": "PENDING",
            "realized_pnl_net": 0.0,
            "position_remaining": 1.0,
        },
        {
            "resolved_token_id": "seg_006",
            "entry_price": 0.34,  # underdog
            "market_slug": "mystery-market-6",  # unknown league
            "question": "Unknown market type text",
            "resolution_outcome": "UNKNOWN_RESOLUTION",
            "realized_pnl_net": 0.0,
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "seg_007",
            "entry_price": None,  # unknown tier
            "market_slug": "atp-djokovic-alcaraz-2026-01-13-djokovic",
            "question": "Will Novak Djokovic win on 2026-01-13?",
            "resolution_outcome": "PROFIT_EXIT",
            "realized_pnl_net": 1.5,
            "position_remaining": 0.0,
        },
        {
            "resolved_token_id": "seg_008",
            "entry_price": 0.28,  # deep_underdog
            "market_slug": "elc-qpr-bbr-2026-01-14-qpr",
            "question": "Will Queens Park Rangers FC win with a handicap?",
            "resolution_outcome": "PROFIT_EXIT",
            "realized_pnl_net": 2.25,
            "position_remaining": 0.0,
        },
    ]


def _latest_drpufferfish_dossier_path() -> Path:
    root = Path(__file__).resolve().parents[1] / "artifacts" / "dossiers" / "users" / "drpufferfish"
    candidates = sorted(root.rglob("dossier.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    assert candidates, f"No dossier artifacts found under {root}"
    return candidates[0]


def _load_latest_pending_no_sell_position() -> dict:
    dossier_path = _latest_drpufferfish_dossier_path()
    dossier = json.loads(dossier_path.read_text(encoding="utf-8"))
    positions = dossier.get("positions", {}).get("positions", [])
    pending = next(
        (
            pos
            for pos in positions
            if pos.get("resolution_outcome") == "PENDING" and int(pos.get("sell_count") or 0) == 0
        ),
        None,
    )
    if pending is not None:
        return dict(pending)
    return {
        "resolved_token_id": "tok-pending-fallback",
        "market_slug": "fallback-pending-market",
        "question": "Fallback pending position fixture",
        "outcome_name": "Yes",
        "entry_ts": "2026-01-10T00:00:00Z",
        "entry_price": 0.45,
        "total_bought": 5.0,
        "total_cost": 2.25,
        "exit_ts": "",
        "exit_price": None,
        "total_sold": 0.0,
        "total_proceeds": 0.0,
        "hold_duration_seconds": 3600,
        "position_remaining": 5.0,
        "trade_count": 1,
        "buy_count": 1,
        "sell_count": 0,
        "settlement_price": None,
        "resolved_at": "",
        "resolution_source": "",
        "resolution_outcome": "PENDING",
        "gross_pnl": 0.0,
        "realized_pnl_net": 0.0,
        "fees_actual": 0.0,
        "fees_estimated": 0.0,
        "fees_source": "not_applicable",
    }


class TestNormalizeFeeFields:
    def test_positive_gross_estimates_fee(self):
        pos = {"gross_pnl": 10.0, "fees_actual": 1.5}
        normalize_fee_fields(pos)
        assert pos["fees_actual"] == 1.5
        assert pos["fees_estimated"] == 0.2
        assert pos["fees_source"] == "estimated"
        assert pos["realized_pnl_net_estimated_fees"] == 9.8

    def test_zero_gross_marks_not_applicable(self):
        pos = {"gross_pnl": 0.0}
        normalize_fee_fields(pos)
        assert pos["fees_estimated"] == 0.0
        assert pos["fees_source"] == "not_applicable"
        assert pos["realized_pnl_net_estimated_fees"] == 0.0

    def test_negative_gross_marks_not_applicable(self):
        pos = {"gross_pnl": -4.5}
        normalize_fee_fields(pos)
        assert pos["fees_estimated"] == 0.0
        assert pos["fees_source"] == "not_applicable"
        assert pos["realized_pnl_net_estimated_fees"] == -4.5

    def test_configurable_rate_and_source_label(self):
        pos = {"gross_pnl": 20.0}
        normalize_fee_fields(
            pos,
            fee_config={"profit_fee_rate": 0.05, "source_label": "heuristic"},
        )
        assert pos["fees_estimated"] == 1.0
        assert pos["fees_source"] == "heuristic"
        assert pos["realized_pnl_net_estimated_fees"] == 19.0


class TestBuildCoverageReport:
    def test_outcome_counts(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run-001",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["totals"]["positions_total"] == 6
        assert report["outcome_counts"]["WIN"] == 1
        assert report["outcome_counts"]["LOSS"] == 1
        assert report["outcome_counts"]["PROFIT_EXIT"] == 1
        assert report["outcome_counts"]["LOSS_EXIT"] == 1
        assert report["outcome_counts"]["PENDING"] == 1
        assert report["outcome_counts"]["UNKNOWN_RESOLUTION"] == 1

    def test_outcome_percentages_sum_to_one(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        total_pct = sum(report["outcome_percentages"].values())
        assert abs(total_pct - 1.0) < 0.001

    def test_deterministic_trade_uid_coverage_no_duplicates(self):
        positions = _make_positions()
        for idx, pos in enumerate(positions):
            pos["trade_uid"] = f"uid_{idx}"
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        deterministic = report["deterministic_trade_uid_coverage"]
        fallback = report["fallback_uid_coverage"]
        assert deterministic["total"] == 6
        assert deterministic["with_trade_uid"] == 6
        assert deterministic["duplicate_trade_uid_count"] == 0
        assert fallback["with_fallback_uid"] == 6
        assert fallback["fallback_only_count"] == 0

    def test_fallback_uid_not_counted_as_deterministic_trade_uid(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        deterministic = report["deterministic_trade_uid_coverage"]
        fallback = report["fallback_uid_coverage"]
        assert deterministic["with_trade_uid"] == 0
        assert fallback["with_fallback_uid"] == 6
        assert fallback["fallback_only_count"] == 6

    def test_trade_uid_duplicates_detected(self):
        positions = [
            {"trade_uid": "dup1", "resolved_token_id": "tok1", "resolution_outcome": "WIN",
             "realized_pnl_net": 1.0, "position_remaining": 0.0},
            {"trade_uid": "dup1", "resolved_token_id": "tok2", "resolution_outcome": "LOSS",
             "realized_pnl_net": -1.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        deterministic = report["deterministic_trade_uid_coverage"]
        fallback = report["fallback_uid_coverage"]
        assert deterministic["duplicate_trade_uid_count"] == 1
        assert "dup1" in deterministic["duplicate_sample"]
        assert fallback["with_fallback_uid"] == 2

    def test_pnl_totals(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        pnl = report["pnl"]
        # gross = 13.3, estimated fees on positives = 0.21 + 0.14 = 0.35
        assert abs(pnl["gross_pnl_total"] - 13.3) < 0.001
        assert abs(pnl["realized_pnl_net_total"] - 12.95) < 0.001
        assert abs(pnl["realized_pnl_net_estimated_fees_total"] - 12.95) < 0.001
        assert abs(pnl["reported_realized_pnl_net_total"] - 13.3) < 0.001
        assert pnl["missing_realized_pnl_count"] == 1  # tok_006 has None

    def test_pending_no_sells_realized_is_zero(self):
        pending = _load_latest_pending_no_sell_position()
        report = build_coverage_report(
            positions=[pending],
            run_id="pending-fix",
            user_slug="drpufferfish",
            wallet="0xabc",
        )

        assert pending["settlement_price"] is None
        assert pending["resolved_at"] is None
        assert pending["gross_pnl"] == 0.0
        assert pending["realized_pnl_net"] == 0.0
        assert pending["fees_estimated"] == 0.0
        assert pending["fees_source"] == "not_applicable"
        assert pending["realized_pnl_net_estimated_fees"] == 0.0
        assert report["pnl"]["realized_pnl_net_by_outcome"]["PENDING"] == 0.0
        assert report["pnl"]["realized_pnl_net_total"] == 0.0

    def test_fee_source_counts(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        fees = report["fees"]
        assert fees["fees_source_counts"]["estimated"] == 2
        assert fees["fees_source_counts"]["not_applicable"] == 4
        assert fees["fees_actual_present_count"] == 1
        assert fees["fees_estimated_present_count"] == 2

    def test_fee_estimation_handles_positive_zero_negative_and_pending(self):
        positions = [
            {
                "resolved_token_id": "fee-pos",
                "resolution_outcome": "PROFIT_EXIT",
                "gross_pnl": 10.0,
                "realized_pnl_net": 10.0,
                "position_remaining": 0.0,
            },
            {
                "resolved_token_id": "fee-zero",
                "resolution_outcome": "LOSS_EXIT",
                "gross_pnl": 0.0,
                "realized_pnl_net": 0.0,
                "position_remaining": 0.0,
            },
            {
                "resolved_token_id": "fee-neg",
                "resolution_outcome": "LOSS",
                "gross_pnl": -5.0,
                "realized_pnl_net": -5.0,
                "position_remaining": 1.0,
            },
            {
                "resolved_token_id": "fee-pending",
                "resolution_outcome": "PENDING",
                "gross_pnl": 3.0,
                "realized_pnl_net": 3.0,
                "sell_count": 0,
                "position_remaining": 2.0,
            },
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="fee-cases",
            user_slug="testuser",
            wallet="0xabc",
        )

        profitable = positions[0]
        assert profitable["fees_estimated"] == 0.2
        assert profitable["fees_source"] == "estimated"
        assert profitable["realized_pnl_net_estimated_fees"] == 9.8

        pending = positions[3]
        assert pending["gross_pnl"] == 0.0
        assert pending["fees_estimated"] == 0.0
        assert pending["fees_source"] == "not_applicable"

        fees = report["fees"]
        assert fees["fees_estimated_present_count"] == 1
        assert fees["fees_source_counts"]["estimated"] == 1
        assert fees["fees_source_counts"]["not_applicable"] == 3

        pnl = report["pnl"]
        assert pnl["gross_pnl_total"] == 5.0
        assert pnl["realized_pnl_net_estimated_fees_total"] == 4.8

        by_entry = report["segment_analysis"]["by_entry_price_tier"]
        total_segment_net = sum(bucket["total_pnl_net"] for bucket in by_entry.values())
        total_segment_gross = sum(bucket["total_pnl_gross"] for bucket in by_entry.values())
        assert total_segment_net == 4.8
        assert total_segment_gross == 5.0

    def test_resolution_coverage(self):
        positions = _make_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        res = report["resolution_coverage"]
        # resolved = total - PENDING = 6 - 1 = 5
        assert res["resolved_total"] == 5
        assert res["unknown_resolution_total"] == 1
        # held_to_resolution: position_remaining > 0 AND not PENDING/UNKNOWN
        # tok_001 (WIN, remaining=5) and tok_002 (LOSS, remaining=2) = 2
        assert res["held_to_resolution_total"] == 2
        # WIN + LOSS = 2, held_to_resolution = 2 -> rate = 1.0
        assert res["win_loss_covered_rate"] == 1.0

    def test_warnings_for_unknown_resolution(self):
        # 2/3 = 66% unknown -> should trigger warning
        positions = [
            {"resolved_token_id": "a", "resolution_outcome": "UNKNOWN_RESOLUTION",
             "realized_pnl_net": 0.0, "position_remaining": 0.0},
            {"resolved_token_id": "b", "resolution_outcome": "UNKNOWN_RESOLUTION",
             "realized_pnl_net": 0.0, "position_remaining": 0.0},
            {"resolved_token_id": "c", "resolution_outcome": "WIN",
             "realized_pnl_net": 1.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert any("UNKNOWN_RESOLUTION" in w for w in report["warnings"])

    def test_warning_for_all_pending_with_strong_fallback_coverage(self):
        positions = [
            {
                "resolved_token_id": f"tok-{idx}",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            }
            for idx in range(20)
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="pending-invalid",
            user_slug="testuser",
            wallet="0xabc",
        )

        assert report["totals"]["positions_total"] > 0
        assert report["fallback_uid_coverage"]["pct_with_fallback_uid"] >= 0.95
        assert report["resolution_coverage"]["resolved_total"] == 0
        assert report["outcome_counts"]["PENDING"] == report["totals"]["positions_total"]
        assert PENDING_COVERAGE_INVALID_WARNING in report["warnings"]

    def test_warning_mentions_truncation_when_enrichment_truncated(self):
        positions = [
            {
                "resolved_token_id": f"tok-{idx}",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            }
            for idx in range(10)
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="pending-invalid-truncated",
            user_slug="testuser",
            wallet="0xabc",
            resolution_enrichment_response={"truncated": True},
        )

        warning = next(
            (w for w in report["warnings"] if PENDING_COVERAGE_INVALID_WARNING in w),
            "",
        )
        assert warning
        assert "truncated=true" in warning

    def test_empty_positions(self):
        report = build_coverage_report(
            positions=[],
            run_id="empty-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["totals"]["positions_total"] == 0
        assert report["pnl"]["realized_pnl_net_total"] == 0.0
        assert report["warnings"] == []

    def test_report_has_required_fields(self):
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="test-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        required = [
            "report_version", "generated_at", "run_id", "user_slug",
            "wallet", "proxy_wallet", "totals", "outcome_counts",
            "outcome_percentages", "deterministic_trade_uid_coverage",
            "fallback_uid_coverage", "pnl",
            "fees", "resolution_coverage", "market_metadata_coverage",
            "category_coverage", "clv_coverage", "entry_context_coverage",
            "segment_analysis", "warnings",
        ]
        for field in required:
            assert field in report, f"Missing required field: {field}"

    def test_no_network_required(self):
        """Building a report must not require any network/service access."""
        # This test simply verifies the function completes without error
        # when given purely synthetic data and no external dependencies.
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="offline-run",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["report_version"] == REPORT_VERSION

    def test_segment_fixture_roadmap_4_2_invariants(self):
        positions = _make_segment_fixture_positions()
        report = build_coverage_report(
            positions=positions,
            run_id="segment-fixture",
            user_slug="testuser",
            wallet="0xabc",
        )

        segment_analysis = report["segment_analysis"]
        positions_total = report["totals"]["positions_total"]

        # a) Entry tier counts sum to total positions
        tier_total = sum(
            bucket["count"] for bucket in segment_analysis["by_entry_price_tier"].values()
        )
        assert tier_total == positions_total

        # b) Win rate excludes PENDING + UNKNOWN_RESOLUTION
        underdog = segment_analysis["by_entry_price_tier"]["underdog"]
        assert underdog["count"] == 3  # WIN + PENDING + UNKNOWN_RESOLUTION
        assert underdog["wins"] == 1
        assert underdog["losses"] == 0
        assert underdog["profit_exits"] == 0
        assert underdog["loss_exits"] == 0
        assert underdog["win_rate"] == 1.0

        # d) Unknown buckets exist and are counted
        assert "unknown" in segment_analysis["by_entry_price_tier"]
        assert "unknown" in segment_analysis["by_market_type"]
        assert "unknown" in segment_analysis["by_league"]
        assert "unknown" in segment_analysis["by_sport"]
        assert segment_analysis["by_entry_price_tier"]["unknown"]["count"] == 1
        assert segment_analysis["by_market_type"]["unknown"]["count"] >= 2
        assert segment_analysis["by_league"]["unknown"]["count"] >= 2
        assert segment_analysis["by_sport"]["unknown"]["count"] >= 2

    def test_segment_analysis_classification_and_unknown_buckets(self):
        positions = [
            {
                "entry_price": 0.22,
                "market_slug": "nba-lal-bos-2026-01-01-lal",
                "question": "Will Los Angeles Lakers win on 2026-01-01?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 5.0,
                "position_remaining": 0.0,
            },
            {
                "entry_price": 0.51,
                "market_slug": "mystery-market-1",
                "question": "Will Team X cover the spread?",
                "resolution_outcome": "LOSS_EXIT",
                "realized_pnl_net": -2.0,
                "position_remaining": 0.0,
            },
            {
                "market_slug": "mystery-market-2",
                "question": "Outcome pending?",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            },
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="segment-classify",
            user_slug="testuser",
            wallet="0xabc",
        )

        segment_analysis = report["segment_analysis"]
        assert segment_analysis["by_entry_price_tier"]["deep_underdog"]["count"] == 1
        assert segment_analysis["by_entry_price_tier"]["coinflip"]["count"] == 1
        assert segment_analysis["by_entry_price_tier"]["unknown"]["count"] == 1

        assert segment_analysis["by_market_type"]["moneyline"]["count"] == 1
        assert segment_analysis["by_market_type"]["spread"]["count"] == 1
        assert segment_analysis["by_market_type"]["total"]["count"] == 0
        assert segment_analysis["by_market_type"]["unknown"]["count"] == 1

        assert segment_analysis["by_league"]["nba"]["count"] == 1
        assert segment_analysis["by_league"]["unknown"]["count"] == 2

        assert segment_analysis["by_sport"]["basketball"]["count"] == 1
        assert segment_analysis["by_sport"]["unknown"]["count"] == 2

    def test_market_type_vs_default_rule_conservative(self):
        positions = [
            {
                "market_slug": "nba-nets-vs-magic-spread",
                "question": "Nets vs Magic spread -1.5",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "market_slug": "nba-nets-vs-magic-total-points",
                "question": "Nets vs Magic total points over/under 220.5?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "market_slug": "nba-nets-vs-magic-2026-02-19",
                "question": "Brooklyn Nets vs Orlando Magic",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "market_slug": "mystery-nets-vs-magic-2026-02-19",
                "question": "Nets vs Magic",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="segment-vs-moneyline-default",
            user_slug="testuser",
            wallet="0xabc",
        )
        by_market_type = report["segment_analysis"]["by_market_type"]
        assert by_market_type["spread"]["count"] == 1
        assert by_market_type["total"]["count"] == 1
        assert by_market_type["moneyline"]["count"] == 1
        assert by_market_type["unknown"]["count"] == 1

    def test_segment_analysis_win_rate_denominator_excludes_pending_unknown_resolution(self):
        positions = [
            {
                "entry_price": 0.40,
                "market_slug": "nba-test-1",
                "question": "Will Team A win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "entry_price": 0.41,
                "market_slug": "nba-test-2",
                "question": "Will Team B win?",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            },
            {
                "entry_price": 0.42,
                "market_slug": "nba-test-3",
                "question": "Will Team C win?",
                "resolution_outcome": "UNKNOWN_RESOLUTION",
                "realized_pnl_net": 0.0,
                "position_remaining": 0.0,
            },
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="segment-winrate",
            user_slug="testuser",
            wallet="0xabc",
        )

        entry_segment = report["segment_analysis"]["by_entry_price_tier"]["underdog"]
        assert entry_segment["count"] == 3
        assert entry_segment["wins"] == 1
        assert entry_segment["losses"] == 0
        assert entry_segment["profit_exits"] == 0
        assert entry_segment["loss_exits"] == 0
        assert entry_segment["win_rate"] == 1.0

    def test_segment_analysis_uses_custom_entry_price_tiers(self):
        custom_tiers = [
            {"name": "cheap", "max": 0.4},
            {"name": "expensive", "min": 0.4},
        ]
        positions = [
            {
                "entry_price": 0.2,
                "market_slug": "nba-a",
                "question": "Will Team A win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "entry_price": 0.8,
                "market_slug": "nba-b",
                "question": "Will Team B win?",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
            {
                "entry_price": None,
                "market_slug": "nba-c",
                "question": "Will Team C win?",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            },
        ]

        report = build_coverage_report(
            positions=positions,
            run_id="segment-custom-tiers",
            user_slug="testuser",
            wallet="0xabc",
            entry_price_tiers=custom_tiers,
        )
        default_report = build_coverage_report(
            positions=positions,
            run_id="segment-custom-tiers-default",
            user_slug="testuser",
            wallet="0xabc",
        )
        by_entry = report["segment_analysis"]["by_entry_price_tier"]
        assert set(by_entry.keys()) == {"cheap", "expensive", "unknown"}
        assert by_entry["cheap"]["count"] == 1
        assert by_entry["expensive"]["count"] == 1
        assert by_entry["unknown"]["count"] == 1

        # c) Custom tiers deterministically change assignment vs defaults
        default_by_entry = default_report["segment_analysis"]["by_entry_price_tier"]
        assert default_by_entry["deep_underdog"]["count"] == 1
        assert default_by_entry["favorite"]["count"] == 1
        assert default_by_entry["unknown"]["count"] == 1
        assert default_by_entry["underdog"]["count"] == 0


class TestWriteCoverageReport:
    def test_writes_json_and_md(self):
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="write-test",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_cov_json_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            assert "json" in paths
            assert "md" in paths

            # Verify JSON is valid
            json_data = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
            assert json_data["run_id"] == "write-test"

            # Verify Markdown contains key sections
            md_text = Path(paths["md"]).read_text(encoding="utf-8")
            assert "# Coverage & Reconciliation Report" in md_text
            assert "Outcome Distribution" in md_text
            assert "Market Metadata Coverage" in md_text
            assert "Segment Highlights" in md_text
            assert "entry_price_tier:unknown:" in md_text
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_json_only(self):
        report = build_coverage_report(
            positions=_make_positions(),
            run_id="json-only",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_cov_json_only"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=False)
            assert "json" in paths
            assert "md" not in paths
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


class TestResolutionEnrichmentParity:
    """Tests for enrichment-parity coverage diagnostics."""

    def test_all_pending_no_enrichment_response_still_warns(self):
        """All-PENDING with strong fallback coverage should warn even without enrichment response."""
        positions = [
            {"resolved_token_id": f"tok-{i}", "resolution_outcome": "PENDING",
             "realized_pnl_net": 0.0, "position_remaining": 1.0}
            for i in range(15)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="parity-test",
            user_slug="testuser",
            wallet="0xabc",
            resolution_enrichment_response=None,
        )
        assert PENDING_COVERAGE_INVALID_WARNING in report["warnings"]

    def test_all_pending_with_non_truncated_enrichment_no_truncation_text(self):
        """When enrichment is NOT truncated but all positions are PENDING, warning should
        NOT mention truncation."""
        positions = [
            {"resolved_token_id": f"tok-{i}", "resolution_outcome": "PENDING",
             "realized_pnl_net": 0.0, "position_remaining": 1.0}
            for i in range(10)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="parity-no-trunc",
            user_slug="testuser",
            wallet="0xabc",
            resolution_enrichment_response={"truncated": False, "candidates_total": 10,
                                             "candidates_selected": 10},
        )
        pending_warning = next(
            (w for w in report["warnings"] if PENDING_COVERAGE_INVALID_WARNING in w), ""
        )
        assert pending_warning
        assert "truncated=true" not in pending_warning


class TestMarketMetadataCoverage:
    """Tests for Roadmap 4.4: market metadata backfill + coverage reporting."""

    def test_all_positions_with_metadata_counts_as_ingested(self):
        """Positions already carrying market_slug are counted as ingested."""
        positions = [
            {
                "token_id": "tok-a",
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-b",
                "market_slug": "nfl-kc-buf-2026",
                "question": "Will KC win?",
                "outcome_name": "Yes",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="meta-ingested",
            user_slug="testuser",
            wallet="0xabc",
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["present_count"] == 2
        assert mmc["missing_count"] == 0
        assert mmc["coverage_rate"] == 1.0
        assert mmc["source_counts"]["ingested"] == 2
        assert mmc["source_counts"]["backfilled"] == 0
        assert mmc["source_counts"]["unknown"] == 0
        assert mmc["top_unmappable"] == []

    def test_backfill_fills_missing_fields_when_map_provided(self):
        """Positions missing market metadata are backfilled from the provided map."""
        positions = [
            {
                "token_id": "tok-x",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 2.0,
                "position_remaining": 0.0,
                # market_slug/question/outcome_name intentionally absent
            },
            {
                "token_id": "tok-y",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
                # No metadata, no mapping either
            },
        ]
        mapping = {
            "tok-x": {
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "outcome_name": "Yes",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="meta-backfill",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        mmc = report["market_metadata_coverage"]
        # tok-x gets backfilled, tok-y stays unknown
        assert mmc["present_count"] == 1
        assert mmc["missing_count"] == 1
        assert mmc["source_counts"]["backfilled"] == 1
        assert mmc["source_counts"]["ingested"] == 0
        assert mmc["source_counts"]["unknown"] == 1
        # tok-x should now carry the metadata
        assert positions[0]["market_slug"] == "nba-lal-bos-2026"
        assert positions[0]["question"] == "Will LAL win?"
        assert positions[0]["outcome_name"] == "Yes"
        # tok-y metadata should remain absent
        assert not positions[1].get("market_slug")

    def test_backfill_source_label_is_backfilled_in_source_counts(self):
        """source_counts.backfilled increments for each backfilled position."""
        positions = [
            {"token_id": f"tok-{i}", "resolution_outcome": "WIN",
             "realized_pnl_net": 1.0, "position_remaining": 0.0}
            for i in range(3)
        ]
        mapping = {
            f"tok-{i}": {"market_slug": f"market-{i}", "question": f"Q{i}?", "outcome_name": "Yes"}
            for i in range(3)
        }
        report = build_coverage_report(
            positions=positions,
            run_id="meta-backfill-all",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["source_counts"]["backfilled"] == 3
        assert mmc["source_counts"]["ingested"] == 0
        assert mmc["source_counts"]["unknown"] == 0
        assert mmc["present_count"] == 3
        assert mmc["missing_count"] == 0

    def test_unmappable_positions_land_in_top_unmappable(self):
        """Positions without metadata and no mapping entry appear in top_unmappable."""
        positions = [
            {
                "token_id": "unmapped-tok",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            }
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="meta-unmappable",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map={},  # empty map — no mapping available
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["missing_count"] == 1
        assert mmc["present_count"] == 0
        assert len(mmc["top_unmappable"]) == 1
        entry = mmc["top_unmappable"][0]
        assert entry["token_id"] == "unmapped-tok"
        assert entry["count"] == 1

    def test_missing_rate_above_20pct_adds_warning(self):
        """When >20% of positions lack metadata, a warning is added."""
        positions = [
            # 1 with metadata
            {
                "token_id": "tok-ok",
                "market_slug": "known-market",
                "question": "Will it?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
        ] + [
            # 4 without metadata — 80% missing rate
            {
                "token_id": f"tok-missing-{i}",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            }
            for i in range(4)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="meta-warning",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert any("market_metadata_coverage missing rate" in w for w in report["warnings"])

    def test_missing_rate_at_or_below_20pct_no_warning(self):
        """When ≤20% of positions lack metadata, no metadata warning is added."""
        positions = [
            {
                "token_id": "tok-ok",
                "market_slug": "market",
                "question": "Will it?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-ok-2",
                "market_slug": "market-2",
                "question": "Will it 2?",
                "outcome_name": "No",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-ok-3",
                "market_slug": "market-3",
                "question": "Will it 3?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-ok-4",
                "market_slug": "market-4",
                "question": "Will it 4?",
                "outcome_name": "No",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
            # 1 missing out of 5 = 20% — not above the threshold
            {
                "token_id": "tok-missing",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="meta-no-warning",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert not any("market_metadata_coverage missing rate" in w for w in report["warnings"])

    def test_empty_positions_coverage_is_zero(self):
        """Empty position list produces zero coverage with no unmappable entries."""
        report = build_coverage_report(
            positions=[],
            run_id="meta-empty",
            user_slug="testuser",
            wallet="0xabc",
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["present_count"] == 0
        assert mmc["missing_count"] == 0
        assert mmc["coverage_rate"] == 0.0
        assert mmc["top_unmappable"] == []

    def test_backfill_uses_resolved_token_id_as_fallback_key(self):
        """resolved_token_id is used as a lookup key when token_id is absent."""
        positions = [
            {
                "resolved_token_id": "rtok-1",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "rtok-1": {
                "market_slug": "mapped-market",
                "question": "Mapped question?",
                "outcome_name": "Yes",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="meta-rtok",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["present_count"] == 1
        assert mmc["source_counts"]["backfilled"] == 1
        assert positions[0]["market_slug"] == "mapped-market"

    def test_backfill_uses_condition_id_as_last_resort_key(self):
        """condition_id is used as a lookup key when token_id and resolved_token_id are absent."""
        positions = [
            {
                "condition_id": "cond-abc",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -0.5,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "cond-abc": {
                "market_slug": "cond-market",
                "question": "Condition question?",
                "outcome_name": "No",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="meta-condid",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["present_count"] == 1
        assert mmc["source_counts"]["backfilled"] == 1
        assert positions[0]["market_slug"] == "cond-market"

    def test_backfill_never_overwrites_existing_fields(self):
        """Backfill does not overwrite a field that already has a value."""
        positions = [
            {
                "token_id": "tok-z",
                "market_slug": "existing-slug",  # already set
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "tok-z": {
                "market_slug": "map-slug",  # should NOT overwrite
                "question": "Map question?",
                "outcome_name": "Yes",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="meta-no-overwrite",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        # existing-slug must be preserved
        assert positions[0]["market_slug"] == "existing-slug"
        # question/outcome_name were absent so they may be filled
        assert positions[0].get("question") == "Map question?"
        assert positions[0].get("outcome_name") == "Yes"
        mmc = report["market_metadata_coverage"]
        # Position had partial metadata before backfill, so it's counted as present.
        # It was partially backfilled so it should show in backfilled count.
        assert mmc["present_count"] == 1

    def test_markdown_includes_market_metadata_coverage_section(self):
        """The rendered Markdown report includes a Market Metadata Coverage section."""
        import shutil
        positions = [
            {
                "token_id": "tok-md",
                "market_slug": "slug",
                "question": "Q?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="meta-md",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_meta_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## Market Metadata Coverage" in md
            assert "Coverage:" in md
            assert "Sources:" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_includes_warning_when_missing_rate_high(self):
        """When missing rate >20%, the Markdown report includes a warning callout."""
        import shutil
        # 4 of 5 positions missing metadata = 80%
        positions = [
            {
                "token_id": "tok-ok",
                "market_slug": "slug",
                "question": "Q?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
        ] + [
            {
                "token_id": f"tok-m-{i}",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            }
            for i in range(4)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="meta-md-warn",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_meta_md_warn"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "Warning" in md
            assert "market metadata" in md.lower()
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


class TestBackfillMarketMetadata:
    """Unit tests for the standalone backfill_market_metadata() function."""

    def test_returns_empty_set_when_no_map(self):
        positions = [{"token_id": "tok", "resolution_outcome": "WIN"}]
        result = backfill_market_metadata(positions)
        assert result == set()

    def test_returns_empty_set_when_map_is_empty(self):
        positions = [{"token_id": "tok", "resolution_outcome": "WIN"}]
        result = backfill_market_metadata(positions, {})
        assert result == set()

    def test_fills_all_three_fields(self):
        pos = {"token_id": "tok-1"}
        mapping = {"tok-1": {"market_slug": "s", "question": "q?", "outcome_name": "Yes"}}
        backfilled = backfill_market_metadata([pos], mapping)
        assert 0 in backfilled
        assert pos["market_slug"] == "s"
        assert pos["question"] == "q?"
        assert pos["outcome_name"] == "Yes"

    def test_partial_fill_only_missing_fields(self):
        pos = {"token_id": "tok-2", "market_slug": "existing"}
        mapping = {"tok-2": {"market_slug": "other", "question": "q?", "outcome_name": "No"}}
        backfilled = backfill_market_metadata([pos], mapping)
        assert 0 in backfilled
        assert pos["market_slug"] == "existing"  # not overwritten
        assert pos["question"] == "q?"
        assert pos["outcome_name"] == "No"

    def test_skips_position_without_identifier(self):
        pos = {"resolution_outcome": "WIN"}  # no token_id/resolved_token_id/condition_id
        mapping = {"any": {"market_slug": "s", "question": "q?", "outcome_name": "Y"}}
        backfilled = backfill_market_metadata([pos], mapping)
        assert backfilled == set()
        assert "market_slug" not in pos

    def test_no_match_leaves_position_unchanged(self):
        pos = {"token_id": "tok-unknown"}
        mapping = {"tok-other": {"market_slug": "s", "question": "q?", "outcome_name": "Y"}}
        backfilled = backfill_market_metadata([pos], mapping)
        assert backfilled == set()
        assert "market_slug" not in pos

    def test_returns_correct_index_set_for_multiple_positions(self):
        positions = [
            {"token_id": "tok-a"},              # index 0 — will be backfilled
            {"token_id": "tok-b", "market_slug": "existing"},  # index 1 — partially backfilled
            {"token_id": "tok-c"},              # index 2 — no mapping, stays missing
        ]
        mapping = {
            "tok-a": {"market_slug": "ma", "question": "qa?", "outcome_name": "Yes"},
            "tok-b": {"market_slug": "mb", "question": "qb?", "outcome_name": "No"},
        }
        backfilled = backfill_market_metadata(positions, mapping)
        assert 0 in backfilled  # tok-a had no metadata
        assert 1 in backfilled  # tok-b was missing question + outcome_name
        assert 2 not in backfilled  # tok-c has no mapping

    def test_condition_id_fills_slug_and_question_but_not_outcome_name(self):
        """condition_id lookup fills market_slug and question but MUST NOT fill outcome_name.

        A condition_id identifies a market (shared across all outcome tokens).
        We cannot determine which specific outcome the position backs from the
        condition alone, so outcome_name must be left empty.
        """
        pos = {
            "condition_id": "cond-xyz",
            # No token_id or resolved_token_id
        }
        mapping = {
            "cond-xyz": {
                "market_slug": "market-from-cond",
                "question": "Who wins?",
                "outcome_name": "Team A",  # MUST be ignored for condition_id lookups
            }
        }
        backfilled = backfill_market_metadata([pos], mapping)
        assert 0 in backfilled
        assert pos["market_slug"] == "market-from-cond"
        assert pos["question"] == "Who wins?"
        assert "outcome_name" not in pos  # must not be set via condition_id

    def test_token_id_fills_all_three_fields_including_outcome_name(self):
        """token_id lookup may fill outcome_name because it identifies a specific outcome token."""
        pos = {"token_id": "tok-outcome"}
        mapping = {
            "tok-outcome": {
                "market_slug": "market-tok",
                "question": "Who wins?",
                "outcome_name": "Team B",
            }
        }
        backfilled = backfill_market_metadata([pos], mapping)
        assert 0 in backfilled
        assert pos["market_slug"] == "market-tok"
        assert pos["question"] == "Who wins?"
        assert pos["outcome_name"] == "Team B"

    def test_resolved_token_id_fills_outcome_name(self):
        """resolved_token_id is treated like token_id and may fill outcome_name."""
        pos = {"resolved_token_id": "rtok-outcome"}
        mapping = {
            "rtok-outcome": {
                "market_slug": "market-rtok",
                "question": "Match result?",
                "outcome_name": "Draw",
            }
        }
        backfilled = backfill_market_metadata([pos], mapping)
        assert 0 in backfilled
        assert pos["outcome_name"] == "Draw"

    def test_condition_id_position_counted_as_present_without_outcome_name(self):
        """A position backfilled via condition_id still counts as 'present' (slug/question filled)."""
        positions = [
            {
                "condition_id": "cond-1",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "cond-1": {
                "market_slug": "market-cond",
                "question": "Q cond?",
                "outcome_name": "Yes",  # silently skipped
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cond-present",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["present_count"] == 1
        assert mmc["source_counts"]["backfilled"] == 1
        assert positions[0].get("market_slug") == "market-cond"
        assert positions[0].get("question") == "Q cond?"
        assert "outcome_name" not in positions[0]


class TestMetadataConflictDetection:
    """Tests for Roadmap 4.4 hardening: conflict detection in coverage report."""

    def test_no_conflicts_when_entries_agree(self):
        """metadata_conflicts_count is 0 when all positions have consistent metadata."""
        report = build_coverage_report(
            positions=[
                {
                    "token_id": "tok-a",
                    "market_slug": "market-a",
                    "question": "Q a?",
                    "outcome_name": "Yes",
                    "resolution_outcome": "WIN",
                    "realized_pnl_net": 1.0,
                    "position_remaining": 0.0,
                }
            ],
            run_id="no-conflict",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert report["market_metadata_coverage"]["metadata_conflicts_count"] == 0

    def test_conflicts_count_surfaced_in_report(self):
        """Passing metadata_conflicts_count > 0 is reflected in the report."""
        report = build_coverage_report(
            positions=[
                {
                    "token_id": "tok-a",
                    "market_slug": "market-a",
                    "question": "Q?",
                    "outcome_name": "Yes",
                    "resolution_outcome": "WIN",
                    "realized_pnl_net": 1.0,
                    "position_remaining": 0.0,
                }
            ],
            run_id="conflict-count",
            user_slug="testuser",
            wallet="0xabc",
            metadata_conflicts_count=3,
        )
        assert report["market_metadata_coverage"]["metadata_conflicts_count"] == 3

    def test_conflict_sample_appears_in_report(self):
        """metadata_conflict_sample is included in the report when provided."""
        sample = [
            {
                "identifier": "tok-x",
                "first": {"market_slug": "m1", "question": "q1", "outcome_name": "Y"},
                "second": {"market_slug": "m2", "question": "q2", "outcome_name": "N"},
            }
        ]
        report = build_coverage_report(
            positions=[
                {
                    "token_id": "tok-any",
                    "market_slug": "slug",
                    "question": "Q?",
                    "outcome_name": "Yes",
                    "resolution_outcome": "WIN",
                    "realized_pnl_net": 1.0,
                    "position_remaining": 0.0,
                }
            ],
            run_id="conflict-sample",
            user_slug="testuser",
            wallet="0xabc",
            metadata_conflicts_count=1,
            metadata_conflict_sample=sample,
        )
        mmc = report["market_metadata_coverage"]
        assert mmc["metadata_conflicts_count"] == 1
        assert "metadata_conflict_sample" in mmc
        assert mmc["metadata_conflict_sample"][0]["identifier"] == "tok-x"

    def test_conflict_sample_capped_at_five(self):
        """metadata_conflict_sample is limited to 5 entries even if more are passed."""
        sample = [
            {"identifier": f"tok-{i}", "first": {}, "second": {}}
            for i in range(10)
        ]
        report = build_coverage_report(
            positions=[],
            run_id="conflict-cap",
            user_slug="testuser",
            wallet="0xabc",
            metadata_conflicts_count=10,
            metadata_conflict_sample=sample,
        )
        mmc = report["market_metadata_coverage"]
        assert len(mmc["metadata_conflict_sample"]) == 5

    def test_no_conflict_sample_key_when_none_provided(self):
        """metadata_conflict_sample key is absent from the report when not provided."""
        report = build_coverage_report(
            positions=[],
            run_id="no-sample",
            user_slug="testuser",
            wallet="0xabc",
            metadata_conflicts_count=0,
        )
        assert "metadata_conflict_sample" not in report["market_metadata_coverage"]

    def test_markdown_warns_when_conflicts_detected(self):
        """Markdown report includes a conflict warning line when conflicts_count > 0."""
        import shutil
        report = build_coverage_report(
            positions=[
                {
                    "token_id": "tok-md-c",
                    "market_slug": "slug",
                    "question": "Q?",
                    "outcome_name": "Yes",
                    "resolution_outcome": "WIN",
                    "realized_pnl_net": 1.0,
                    "position_remaining": 0.0,
                }
            ],
            run_id="conflict-md",
            user_slug="testuser",
            wallet="0xabc",
            metadata_conflicts_count=2,
        )
        output_dir = Path("artifacts") / "_pytest_conflict_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "collision" in md.lower() or "conflict" in md.lower()
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_no_conflict_warning_when_zero_conflicts(self):
        """Markdown report does NOT include a conflict warning when conflicts_count == 0."""
        import shutil
        report = build_coverage_report(
            positions=[
                {
                    "token_id": "tok-md-nc",
                    "market_slug": "slug",
                    "question": "Q?",
                    "outcome_name": "Yes",
                    "resolution_outcome": "WIN",
                    "realized_pnl_net": 1.0,
                    "position_remaining": 0.0,
                }
            ],
            run_id="no-conflict-md",
            user_slug="testuser",
            wallet="0xabc",
            metadata_conflicts_count=0,
        )
        output_dir = Path("artifacts") / "_pytest_no_conflict_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "collision" not in md.lower()
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


    def test_clv_coverage_counts_and_missing_reasons(self):
        positions = [
            {
                "resolved_token_id": "tok_clv_1",
                "resolution_outcome": "WIN",
                "entry_price": 0.40,
                "clv": 0.06,
                "clv_pct": 0.15,
                "beat_close": True,
                "close_ts_source": "onchain_resolved_at",
                "clv_source": "prices_history|onchain_resolved_at",
            },
            {
                "resolved_token_id": "tok_clv_2",
                "resolution_outcome": "LOSS",
                "entry_price": 0.55,
                "clv": None,
                "clv_pct": None,
                "beat_close": None,
                "clv_missing_reason": "NO_CLOSE_TS",
            },
            {
                "resolved_token_id": "tok_not_eligible",
                "resolution_outcome": "PENDING",
                "entry_price": 1.25,
                "clv": None,
                "clv_missing_reason": "INVALID_ENTRY_PRICE_RANGE",
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="clv-coverage",
            user_slug="testuser",
            wallet="0xabc",
        )
        clv = report["clv_coverage"]
        assert clv["eligible_positions"] == 2
        assert clv["clv_present_count"] == 1
        assert clv["clv_missing_count"] == 1
        assert clv["coverage_rate"] == 0.5
        assert clv["missing_reason_counts"] == {"NO_CLOSE_TS": 1}
        assert clv["close_ts_source_counts"] == {"onchain_resolved_at": 1}
        assert clv["clv_source_counts"] == {"prices_history|onchain_resolved_at": 1}

    def test_entry_context_coverage_counts_and_missing_reasons(self):
        positions = [
            {
                "resolved_token_id": "tok_ctx_1",
                "entry_price": 0.40,
                "open_price": 0.32,
                "price_1h_before_entry": 0.38,
                "price_at_entry": 0.41,
                "movement_direction": "up",
                "minutes_to_close": 120,
            },
            {
                "resolved_token_id": "tok_ctx_2",
                "entry_price": 0.55,
                "open_price": None,
                "open_price_missing_reason": "NO_PRICE_IN_LOOKBACK_WINDOW",
                "price_1h_before_entry": None,
                "price_1h_before_entry_missing_reason": "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW",
                "price_at_entry": 0.52,
                "movement_direction": None,
                "movement_direction_missing_reason": "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW",
                "minutes_to_close": None,
                "minutes_to_close_missing_reason": "NO_CLOSE_TS",
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="entry-context-coverage",
            user_slug="testuser",
            wallet="0xabc",
        )
        context = report["entry_context_coverage"]
        assert context["eligible_positions"] == 2
        assert context["open_price_present_count"] == 1
        assert context["price_1h_before_entry_present_count"] == 1
        assert context["price_at_entry_present_count"] == 2
        assert context["movement_direction_present_count"] == 1
        assert context["minutes_to_close_present_count"] == 1
        assert context["missing_reason_counts"] == {
            "NO_CLOSE_TS": 1,
            "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW": 2,
            "NO_PRICE_IN_LOOKBACK_WINDOW": 1,
        }

    def test_segment_analysis_includes_avg_clv_pct_and_beat_close_rate(self):
        positions = [
            {
                "resolved_token_id": "seg_clv_1",
                "entry_price": 0.40,
                "market_slug": "nba-a-b-2026-01-01-a",
                "question": "Will Team A win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 2.0,
                "clv_pct": 0.10,
                "beat_close": True,
            },
            {
                "resolved_token_id": "seg_clv_2",
                "entry_price": 0.42,
                "market_slug": "nba-a-b-2026-01-01-b",
                "question": "Will Team B win?",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "clv_pct": -0.05,
                "beat_close": False,
            },
            {
                "resolved_token_id": "seg_clv_3",
                "entry_price": 0.41,
                "market_slug": "nba-a-b-2026-01-01-c",
                "question": "Will Team C win?",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "clv_pct": None,
                "beat_close": None,
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="segment-clv",
            user_slug="testuser",
            wallet="0xabc",
        )
        underdog = report["segment_analysis"]["by_entry_price_tier"]["underdog"]
        assert underdog["avg_clv_pct"] == pytest.approx(0.025, rel=0, abs=1e-9)
        assert underdog["beat_close_rate"] == pytest.approx(0.5, rel=0, abs=1e-9)


class TestCategoryCoverage:
    """Roadmap 4.5: category coverage section tests."""

    def test_report_version_is_1_5_0(self):
        assert REPORT_VERSION == "1.5.0"

    def test_get_category_key_returns_category_when_present(self):
        pos = {"category": "Sports"}
        assert _get_category_key(pos) == "Sports"

    def test_get_category_key_strips_whitespace(self):
        pos = {"category": "  Politics  "}
        assert _get_category_key(pos) == "Politics"

    def test_get_category_key_returns_unknown_when_empty(self):
        assert _get_category_key({}) == "Unknown"
        assert _get_category_key({"category": ""}) == "Unknown"
        assert _get_category_key({"category": None}) == "Unknown"

    def test_category_present_ingested(self):
        """Position with category already set counts as ingested."""
        positions = [
            {
                "token_id": "tok-a",
                "category": "Sports",
                "market_slug": "nba-lal-2026",
                "question": "Will LAL win?",
                "outcome_name": "Yes",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 2.0,
                "position_remaining": 0.0,
            }
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-ingested",
            user_slug="testuser",
            wallet="0xabc",
        )
        cc = report["category_coverage"]
        assert cc["present_count"] == 1
        assert cc["missing_count"] == 0
        assert cc["coverage_rate"] == 1.0
        assert cc["source_counts"]["ingested"] == 1
        assert cc["source_counts"]["backfilled"] == 0
        assert cc["source_counts"]["unknown"] == 0

    def test_category_backfilled_via_token_id(self):
        """Category missing in position is filled from map via token_id."""
        positions = [
            {
                "token_id": "tok-b",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "tok-b": {
                "market_slug": "nfl-kc-2026",
                "question": "Will KC win?",
                "outcome_name": "Yes",
                "category": "Sports",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cat-backfill-tok",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        cc = report["category_coverage"]
        assert cc["present_count"] == 1
        assert cc["missing_count"] == 0
        assert cc["source_counts"]["backfilled"] == 1
        assert cc["source_counts"]["ingested"] == 0
        assert positions[0]["category"] == "Sports"

    def test_category_backfilled_via_resolved_token_id(self):
        """Category filled from map via resolved_token_id."""
        positions = [
            {
                "resolved_token_id": "rtok-c",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -0.5,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "rtok-c": {
                "market_slug": "mlb-game",
                "question": "Will team win?",
                "outcome_name": "Yes",
                "category": "Baseball",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cat-backfill-rtok",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        cc = report["category_coverage"]
        assert cc["present_count"] == 1
        assert cc["source_counts"]["backfilled"] == 1
        assert positions[0]["category"] == "Baseball"

    def test_category_backfill_updates_position_and_by_category_bucket(self):
        """Backfilled category flows into segment_analysis.by_category."""
        positions = [
            {
                "resolved_token_id": "tok-politics",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 2.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "tok-politics": {
                "market_slug": "election-market",
                "question": "Will candidate win?",
                "outcome_name": "Yes",
                "category": "Politics",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cat-backfill-politics-segment",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )

        assert positions[0]["category"] == "Politics"

        cc = report["category_coverage"]
        assert cc["source_counts"]["backfilled"] == 1
        assert cc["source_counts"]["ingested"] == 0
        assert cc["source_counts"]["unknown"] == 0

        by_category = report["segment_analysis"]["by_category"]
        assert by_category["Politics"]["count"] == 1
        assert by_category["Unknown"]["count"] == 0

    def test_category_backfilled_via_condition_id(self):
        """Category (market-level) can be filled from condition_id unlike outcome_name."""
        positions = [
            {
                "condition_id": "cond-xyz",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "cond-xyz": {
                "market_slug": "market-cond",
                "question": "Who wins?",
                "outcome_name": "Team A",  # should NOT be applied via condition_id
                "category": "Politics",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cat-backfill-cond",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        cc = report["category_coverage"]
        assert cc["present_count"] == 1
        assert cc["source_counts"]["backfilled"] == 1
        assert positions[0]["category"] == "Politics"
        # outcome_name must NOT be set from condition_id
        assert "outcome_name" not in positions[0]

    def test_category_missing_and_unmappable(self):
        """Position with no category and no mapping entry is counted as unknown."""
        positions = [
            {
                "token_id": "unmapped-cat",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            }
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-unmappable",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map={},
        )
        cc = report["category_coverage"]
        assert cc["missing_count"] == 1
        assert cc["present_count"] == 0
        assert cc["coverage_rate"] == 0.0
        assert cc["source_counts"]["unknown"] == 1
        assert len(cc["top_unmappable"]) == 1
        assert cc["top_unmappable"][0]["token_id"] == "unmapped-cat"

    def test_category_missing_and_unmappable_condition_id(self):
        """Unmappable condition-level rows surface condition_id in top_unmappable."""
        positions = [
            {
                "condition_id": "cond-only-unmapped",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            }
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-unmappable-cond",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map={},
        )
        cc = report["category_coverage"]
        assert cc["missing_count"] == 1
        assert len(cc["top_unmappable"]) == 1
        entry = cc["top_unmappable"][0]
        assert entry["condition_id"] == "cond-only-unmapped"
        assert "token_id" not in entry

    def test_category_never_overwrites_existing(self):
        """Backfill does not overwrite an existing non-empty category."""
        positions = [
            {
                "token_id": "tok-existing-cat",
                "category": "ExistingCategory",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        mapping = {
            "tok-existing-cat": {
                "market_slug": "some-market",
                "question": "Q?",
                "outcome_name": "Yes",
                "category": "ShouldNotOverwrite",
            }
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cat-no-overwrite",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        assert positions[0]["category"] == "ExistingCategory"
        cc = report["category_coverage"]
        # Was ingested (not backfilled for category)
        assert cc["source_counts"]["ingested"] == 1
        assert cc["source_counts"]["backfilled"] == 0

    def test_category_coverage_source_counts_mixed(self):
        """Mixed ingested / backfilled / unknown positions."""
        positions = [
            # ingested
            {
                "token_id": "tok-1",
                "category": "Sports",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            # backfillable
            {
                "token_id": "tok-2",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
            # unmappable
            {
                "token_id": "tok-3",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            },
        ]
        mapping = {
            "tok-2": {"market_slug": "m2", "question": "Q2?", "outcome_name": "Yes", "category": "Politics"},
        }
        report = build_coverage_report(
            positions=positions,
            run_id="cat-mixed",
            user_slug="testuser",
            wallet="0xabc",
            market_metadata_map=mapping,
        )
        cc = report["category_coverage"]
        assert cc["present_count"] == 2
        assert cc["missing_count"] == 1
        assert cc["source_counts"]["ingested"] == 1
        assert cc["source_counts"]["backfilled"] == 1
        assert cc["source_counts"]["unknown"] == 1
        assert abs(cc["coverage_rate"] - 2 / 3) < 0.001

    def test_by_category_segment_structure(self):
        """segment_analysis.by_category groups positions by Polymarket category."""
        positions = [
            {
                "token_id": "tok-sports-1",
                "category": "Sports",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 3.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-sports-2",
                "category": "Sports",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-politics",
                "category": "Politics",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 5.0,
                "position_remaining": 0.0,
            },
            {
                "token_id": "tok-no-cat",
                "resolution_outcome": "PENDING",
                "realized_pnl_net": 0.0,
                "position_remaining": 1.0,
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="by-cat-seg",
            user_slug="testuser",
            wallet="0xabc",
        )
        by_cat = report["segment_analysis"]["by_category"]

        # Sports bucket — fee estimation: WIN 3.0 -> 2% fee -> net 2.94; LOSS -1.0 -> net -1.0
        assert "Sports" in by_cat
        sports = by_cat["Sports"]
        assert sports["count"] == 2
        assert sports["wins"] == 1
        assert sports["losses"] == 1
        # total_pnl_net uses realized_pnl_net_estimated_fees: 2.94 + (-1.0) = 1.94
        assert abs(sports["total_pnl_net"] - 1.94) < 0.001
        assert sports["win_rate"] == 0.5

        # Politics bucket
        assert "Politics" in by_cat
        assert by_cat["Politics"]["count"] == 1
        assert by_cat["Politics"]["wins"] == 1

        # Unknown bucket must always be present
        assert "Unknown" in by_cat
        assert by_cat["Unknown"]["count"] == 1  # the PENDING with no category

    def test_by_category_sum_reconciles_with_total_positions(self):
        """Sum of all category bucket counts equals total positions."""
        positions = [
            {"token_id": f"tok-{i}", "category": f"Cat{i % 3}",
             "resolution_outcome": "WIN", "realized_pnl_net": float(i),
             "position_remaining": 0.0}
            for i in range(9)
        ] + [
            {"token_id": "tok-nocat", "resolution_outcome": "LOSS",
             "realized_pnl_net": -1.0, "position_remaining": 0.0}
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-sum",
            user_slug="testuser",
            wallet="0xabc",
        )
        by_cat = report["segment_analysis"]["by_category"]
        total_count = sum(b["count"] for b in by_cat.values())
        assert total_count == report["totals"]["positions_total"]

    def test_unknown_category_bucket_always_present(self):
        """The 'Unknown' bucket is present even if all positions have a category."""
        positions = [
            {
                "token_id": "tok-a",
                "category": "Sports",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-all-known",
            user_slug="testuser",
            wallet="0xabc",
        )
        by_cat = report["segment_analysis"]["by_category"]
        assert "Unknown" in by_cat
        assert by_cat["Unknown"]["count"] == 0

    def test_by_category_win_rate_excludes_pending_and_unknown_resolution(self):
        """Win-rate denominator excludes PENDING and UNKNOWN_RESOLUTION outcomes."""
        positions = [
            {"token_id": "tok-win", "category": "Sports",
             "resolution_outcome": "WIN", "realized_pnl_net": 1.0, "position_remaining": 0.0},
            {"token_id": "tok-loss", "category": "Sports",
             "resolution_outcome": "LOSS", "realized_pnl_net": -1.0, "position_remaining": 0.0},
            {"token_id": "tok-profit-exit", "category": "Sports",
             "resolution_outcome": "PROFIT_EXIT", "realized_pnl_net": 2.0, "position_remaining": 0.0},
            {"token_id": "tok-loss-exit", "category": "Sports",
             "resolution_outcome": "LOSS_EXIT", "realized_pnl_net": -0.5, "position_remaining": 0.0},
            {"token_id": "tok-pending", "category": "Sports",
             "resolution_outcome": "PENDING", "realized_pnl_net": 0.0, "position_remaining": 1.0},
            {"token_id": "tok-unknown", "category": "Sports",
             "resolution_outcome": "UNKNOWN_RESOLUTION", "realized_pnl_net": 0.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-win-rate-denominator",
            user_slug="testuser",
            wallet="0xabc",
        )
        sports = report["segment_analysis"]["by_category"]["Sports"]
        # Numerator = WIN + PROFIT_EXIT = 2. Denominator excludes pending/unknown => 4.
        assert sports["count"] == 6
        assert sports["win_rate"] == 0.5

    def test_by_market_slug_top_pnl_ordering(self):
        """by_market_slug.top_by_total_pnl_net is ordered by pnl desc then slug asc."""
        positions = [
            {"token_id": f"t{i}", "market_slug": f"market-{chr(65+i)}",
             "resolution_outcome": "WIN", "realized_pnl_net": float(10 - i),
             "position_remaining": 0.0}
            for i in range(5)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="slug-order",
            user_slug="testuser",
            wallet="0xabc",
        )
        top = report["segment_analysis"]["by_market_slug"]["top_by_total_pnl_net"]
        pnl_values = [row["total_pnl_net"] for row in top]
        assert pnl_values == sorted(pnl_values, reverse=True)

    def test_by_market_slug_top_count_ordering(self):
        """by_market_slug.top_by_count is ordered by count desc then slug asc."""
        positions = [
            {"token_id": f"t-{slug}-{i}", "market_slug": slug,
             "resolution_outcome": "WIN", "realized_pnl_net": 1.0,
             "position_remaining": 0.0}
            for slug, count in [("market-A", 3), ("market-B", 1), ("market-C", 5)]
            for i in range(count)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="slug-count",
            user_slug="testuser",
            wallet="0xabc",
        )
        top = report["segment_analysis"]["by_market_slug"]["top_by_count"]
        counts = [row["count"] for row in top]
        assert counts == sorted(counts, reverse=True)

    def test_by_market_slug_top_rows_use_required_fields_only(self):
        positions = [
            {"token_id": "tok-1", "market_slug": "slug-1",
             "resolution_outcome": "WIN", "realized_pnl_net": 2.0, "position_remaining": 0.0},
            {"token_id": "tok-2", "market_slug": "slug-2",
             "resolution_outcome": "LOSS", "realized_pnl_net": -1.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="slug-fields",
            user_slug="testuser",
            wallet="0xabc",
        )
        top_by_pnl = report["segment_analysis"]["by_market_slug"]["top_by_total_pnl_net"]
        top_by_count = report["segment_analysis"]["by_market_slug"]["top_by_count"]
        expected_keys = {"market_slug", "count", "win_rate", "total_pnl_net"}
        assert set(top_by_pnl[0].keys()) == expected_keys
        assert set(top_by_count[0].keys()) == expected_keys

    def test_category_missing_rate_above_20pct_adds_warning(self):
        """When >20% of positions lack category, a warning is emitted."""
        positions = [
            {"token_id": "tok-ok", "category": "Sports",
             "resolution_outcome": "WIN", "realized_pnl_net": 1.0, "position_remaining": 0.0},
        ] + [
            {"token_id": f"tok-m-{i}", "resolution_outcome": "LOSS",
             "realized_pnl_net": -1.0, "position_remaining": 0.0}
            for i in range(4)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-warning",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert any("category_coverage missing rate" in w for w in report["warnings"])

    def test_category_missing_rate_at_or_below_20pct_no_warning(self):
        """When ≤20% lack category, no category warning."""
        positions = [
            {"token_id": f"tok-ok-{i}", "category": "Sports",
             "resolution_outcome": "WIN", "realized_pnl_net": 1.0, "position_remaining": 0.0}
            for i in range(4)
        ] + [
            {"token_id": "tok-missing", "resolution_outcome": "PENDING",
             "realized_pnl_net": 0.0, "position_remaining": 1.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-no-warning",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert not any("category_coverage missing rate" in w for w in report["warnings"])

    def test_markdown_includes_category_coverage_section(self):
        """Rendered markdown includes ## Category Coverage section."""
        positions = [
            {"token_id": "tok-md-cat", "category": "Sports",
             "market_slug": "nba-a", "question": "Q?", "outcome_name": "Yes",
             "resolution_outcome": "WIN", "realized_pnl_net": 1.0, "position_remaining": 0.0}
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-md",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_cat_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## Category Coverage" in md
            assert "Coverage:" in md
            assert "Sources:" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_includes_clv_coverage_section(self):
        positions = [
            {
                "resolved_token_id": "tok-md-clv-1",
                "entry_price": 0.45,
                "resolution_outcome": "WIN",
                "clv": 0.05,
                "clv_pct": 0.111111,
                "beat_close": True,
                "close_ts_source": "onchain_resolved_at",
                "clv_source": "prices_history|onchain_resolved_at",
            },
            {
                "resolved_token_id": "tok-md-clv-2",
                "entry_price": 0.52,
                "resolution_outcome": "LOSS",
                "clv": None,
                "clv_missing_reason": "OFFLINE",
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="clv-md",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_clv_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## CLV Coverage" in md
            assert "Top missing reasons" in md
            assert "OFFLINE" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_includes_entry_context_coverage_section(self):
        positions = [
            {
                "resolved_token_id": "tok-md-ctx-1",
                "entry_price": 0.45,
                "open_price": 0.41,
                "price_1h_before_entry": 0.43,
                "price_at_entry": 0.46,
                "movement_direction": "up",
                "minutes_to_close": 180,
                "resolution_outcome": "WIN",
            },
            {
                "resolved_token_id": "tok-md-ctx-2",
                "entry_price": 0.52,
                "open_price": None,
                "open_price_missing_reason": "NO_PRICE_IN_LOOKBACK_WINDOW",
                "price_1h_before_entry": None,
                "price_1h_before_entry_missing_reason": "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW",
                "price_at_entry": None,
                "price_at_entry_missing_reason": "NO_PRIOR_PRICE_BEFORE_ENTRY",
                "movement_direction": None,
                "movement_direction_missing_reason": "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW",
                "minutes_to_close": None,
                "minutes_to_close_missing_reason": "NO_CLOSE_TS",
                "resolution_outcome": "LOSS",
            },
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="entry-context-md",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_entry_context_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## Entry Context Coverage" in md
            assert "open_price_present_count" in md
            assert "NO_PRICE_1H_BEFORE_ENTRY_IN_WINDOW" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_includes_top_categories_table(self):
        """Rendered markdown includes ## Top Categories table."""
        positions = [
            {"token_id": f"tok-{i}", "category": f"Cat{i % 2}",
             "market_slug": f"market-{i}", "question": f"Q{i}?", "outcome_name": "Yes",
             "resolution_outcome": "WIN", "realized_pnl_net": float(i + 1),
             "position_remaining": 0.0}
            for i in range(4)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-top-md",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_cat_top_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## Top Categories" in md
            assert "Win Rate" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_includes_top_markets_table(self):
        """Rendered markdown includes ## Top Markets table."""
        positions = [
            {"token_id": f"tok-{i}", "category": "Sports",
             "market_slug": f"slug-{i}", "question": f"Q{i}?", "outcome_name": "Yes",
             "resolution_outcome": "WIN", "realized_pnl_net": float(i + 1),
             "position_remaining": 0.0}
            for i in range(4)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="markets-top-md",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_markets_top_md"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## Top Markets" in md
            assert "Market Slug" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_markdown_category_warning_when_missing_rate_high(self):
        """Markdown includes category warning blockquote when missing rate > 20%."""
        positions = [
            {"token_id": "tok-ok", "category": "Sports",
             "resolution_outcome": "WIN", "realized_pnl_net": 1.0, "position_remaining": 0.0},
        ] + [
            {"token_id": f"tok-m-{i}", "resolution_outcome": "LOSS",
             "realized_pnl_net": -1.0, "position_remaining": 0.0}
            for i in range(4)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-md-warn",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_cat_md_warn"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "Warning" in md
            assert "category" in md.lower()
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_top_categories_deterministic_ordering(self):
        """Top categories ordering is deterministic (pnl desc, name asc on ties)."""
        # Two categories with same pnl to test tie-breaking by name
        positions = [
            {"token_id": "tok-z", "category": "Zzz",
             "resolution_outcome": "WIN", "realized_pnl_net": 5.0, "position_remaining": 0.0},
            {"token_id": "tok-a", "category": "Aaa",
             "resolution_outcome": "WIN", "realized_pnl_net": 5.0, "position_remaining": 0.0},
            {"token_id": "tok-b", "category": "Bbb",
             "resolution_outcome": "WIN", "realized_pnl_net": 3.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="cat-order",
            user_slug="testuser",
            wallet="0xabc",
        )
        by_cat = report["segment_analysis"]["by_category"]
        # After 2% fee estimation: 5.0 * 0.98 = 4.9
        assert abs(by_cat["Aaa"]["total_pnl_net"] - 4.9) < 0.001
        assert abs(by_cat["Zzz"]["total_pnl_net"] - 4.9) < 0.001
        # In top categories, Aaa should come before Zzz (same pnl, alphabetical)
        output_dir = Path("artifacts") / "_pytest_cat_order"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            idx_aaa = md.find("Aaa")
            idx_zzz = md.find("Zzz")
            assert idx_aaa < idx_zzz, "Aaa should appear before Zzz when pnl is equal"
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_top_markets_deterministic_ordering(self):
        """Top markets ordering is deterministic (pnl desc, slug asc on ties)."""
        positions = [
            {"token_id": "tok-z", "market_slug": "zzz-market",
             "resolution_outcome": "WIN", "realized_pnl_net": 5.0, "position_remaining": 0.0},
            {"token_id": "tok-a", "market_slug": "aaa-market",
             "resolution_outcome": "WIN", "realized_pnl_net": 5.0, "position_remaining": 0.0},
            {"token_id": "tok-b", "market_slug": "bbb-market",
             "resolution_outcome": "WIN", "realized_pnl_net": 3.0, "position_remaining": 0.0},
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="market-order",
            user_slug="testuser",
            wallet="0xabc",
        )
        output_dir = Path("artifacts") / "_pytest_market_order"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            idx_aaa = md.find("aaa-market")
            idx_zzz = md.find("zzz-market")
            assert idx_aaa < idx_zzz, "aaa-market should appear before zzz-market when pnl is equal"
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


class TestHypothesisReadyAggregations:
    """Roadmap 5.3: entry_drift_pct, notional-weighted metrics, movement rates, top segments."""

    # ------------------------------------------------------------------
    # 1. entry_drift_pct math and missingness (no divide by zero)
    # ------------------------------------------------------------------

    def test_entry_drift_pct_computed_correctly(self):
        """Standard case: (price_at_entry - price_1h_before_entry) / price_1h_before_entry."""
        positions = [
            {
                "resolved_token_id": "drift-ok",
                "entry_price": 0.60,
                "price_at_entry": 0.55,
                "price_1h_before_entry": 0.50,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        report = build_coverage_report(
            positions=positions, run_id="drift-math", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        # (0.55 - 0.50) / 0.50 = 0.1
        assert bucket["avg_entry_drift_pct"] is not None
        assert abs(bucket["avg_entry_drift_pct"] - 0.1) < 1e-9
        assert bucket["avg_entry_drift_pct_count_used"] == 1

    def test_entry_drift_pct_missing_price_at_entry(self):
        """When price_at_entry is absent, avg_entry_drift_pct must be None."""
        positions = [
            {
                "resolved_token_id": "drift-missing-at",
                "entry_price": 0.60,
                "price_at_entry": None,
                "price_1h_before_entry": 0.50,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        report = build_coverage_report(
            positions=positions, run_id="drift-no-at", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        assert bucket["avg_entry_drift_pct"] is None
        assert bucket["avg_entry_drift_pct_count_used"] == 0

    def test_entry_drift_pct_zero_denominator_no_divide_by_zero(self):
        """When price_1h_before_entry == 0, entry_drift_pct must be None (no ZeroDivisionError)."""
        positions = [
            {
                "resolved_token_id": "drift-zero-denom",
                "entry_price": 0.50,
                "price_at_entry": 0.50,
                "price_1h_before_entry": 0.0,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        # Must not raise
        report = build_coverage_report(
            positions=positions, run_id="drift-zero-denom", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        assert bucket["avg_entry_drift_pct"] is None
        assert bucket["avg_entry_drift_pct_count_used"] == 0

    # ------------------------------------------------------------------
    # 2. Notional-weighted average math
    # ------------------------------------------------------------------

    def test_notional_weighted_avg_clv_pct_two_positions(self):
        """Weighted avg = sum(clv_pct * notional) / sum(notional)."""
        # pos A: clv_pct=0.10, notional=100  → contributes 10.0
        # pos B: clv_pct=0.30, notional=200  → contributes 60.0
        # expected weighted avg = 70.0 / 300 = 0.23333...
        positions = [
            {
                "resolved_token_id": "w-a",
                "entry_price": 0.50,
                "clv_pct": 0.10,
                "beat_close": False,
                "position_notional_usd": 100.0,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "resolved_token_id": "w-b",
                "entry_price": 0.50,
                "clv_pct": 0.30,
                "beat_close": True,
                "position_notional_usd": 200.0,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -1.0,
                "position_remaining": 0.0,
            },
        ]
        report = build_coverage_report(
            positions=positions, run_id="notional-math", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        expected_w_avg = (0.10 * 100 + 0.30 * 200) / 300.0
        assert bucket["notional_weighted_avg_clv_pct"] is not None
        assert bucket["notional_weighted_avg_clv_pct"] == pytest.approx(expected_w_avg, rel=1e-5)
        assert abs(bucket["notional_weighted_avg_clv_pct_weight_used"] - 300.0) < 1e-6

        # beat_close: pos A=False (0), pos B=True (1)
        # weighted = (0*100 + 1*200) / 300 = 200/300 = 0.666...
        expected_w_beat = (0.0 * 100 + 1.0 * 200) / 300.0
        assert bucket["notional_weighted_beat_close_rate"] is not None
        assert bucket["notional_weighted_beat_close_rate"] == pytest.approx(expected_w_beat, rel=1e-5)

    def test_notional_weighted_skips_missing_or_zero_notional(self):
        """Positions with None or 0 notional must not affect weighted metrics."""
        positions = [
            {
                "resolved_token_id": "nw-skip",
                "entry_price": 0.40,
                "clv_pct": 0.99,  # large value — should be excluded
                "beat_close": True,
                "position_notional_usd": None,  # missing
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
            {
                "resolved_token_id": "nw-zero",
                "entry_price": 0.40,
                "clv_pct": 0.99,  # large value — should be excluded
                "beat_close": True,
                "position_notional_usd": 0.0,  # zero
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            },
        ]
        report = build_coverage_report(
            positions=positions, run_id="notional-skip", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        # No valid notional → weighted metrics should be None, weight_used = 0
        assert bucket["notional_weighted_avg_clv_pct"] is None
        assert bucket["notional_weighted_avg_clv_pct_weight_used"] == 0.0
        assert bucket["notional_w_total_weight_used"] == 0.0

        # Global notional weight should also be 0
        hyp_meta = report["segment_analysis"]["hypothesis_meta"]
        assert hyp_meta["notional_weight_total_global"] == 0.0

    # ------------------------------------------------------------------
    # 3. Movement distribution sums to 1.0 (within float tolerance)
    # ------------------------------------------------------------------

    def test_movement_distribution_sums_to_one(self):
        """movement_up + movement_down + movement_flat + movement_unknown == 1.0 when count > 0."""
        positions = [
            {
                "resolved_token_id": f"mv-{i}",
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
                "movement_direction": direction,
            }
            for i, direction in enumerate(["up", "down", "flat", "up", None, "unknown_val"])
        ]
        report = build_coverage_report(
            positions=positions, run_id="movement-sum", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        assert bucket["count"] == 6

        up = bucket["movement_up_rate"]
        down = bucket["movement_down_rate"]
        flat = bucket["movement_flat_rate"]
        unknown = bucket["movement_unknown_rate"]

        assert all(v is not None for v in (up, down, flat, unknown))
        total = up + down + flat + unknown
        assert abs(total - 1.0) < 1e-9, f"Rates sum to {total}, expected 1.0"

        # Verify exact counts: 2 up, 1 down, 1 flat, 2 unknown (rounded to 6 dp)
        assert up == pytest.approx(2 / 6, rel=1e-5)
        assert down == pytest.approx(1 / 6, rel=1e-5)
        assert flat == pytest.approx(1 / 6, rel=1e-5)
        assert unknown == pytest.approx(2 / 6, rel=1e-5)

    def test_movement_rates_none_when_count_zero(self):
        """Empty bucket returns None for movement rates (no division by zero)."""
        report = build_coverage_report(
            positions=[], run_id="movement-empty", user_slug="u", wallet="0xabc"
        )
        # by_league "unknown" bucket should have count=0
        bucket = report["segment_analysis"]["by_league"]["unknown"]
        assert bucket["count"] == 0
        assert bucket["movement_up_rate"] is None
        assert bucket["movement_down_rate"] is None
        assert bucket["movement_flat_rate"] is None
        assert bucket["movement_unknown_rate"] is None

    # ------------------------------------------------------------------
    # 4. Top segments ordering is deterministic and respects min_count
    # ------------------------------------------------------------------

    def test_top_segments_ordering_deterministic_desc_by_metric_asc_by_name(self):
        """Top segments sort by metric descending, break ties by segment name ascending."""
        # Build a segment_analysis stub with two buckets having same metric value
        segment_analysis = {
            "by_market_type": {
                "zzz_type": {"count": 10, "notional_weighted_avg_clv_pct": 0.50},
                "aaa_type": {"count": 10, "notional_weighted_avg_clv_pct": 0.50},
                "top_type": {"count": 10, "notional_weighted_avg_clv_pct": 0.80},
            }
        }
        rows = _collect_top_segments_by_metric(
            segment_analysis,
            "notional_weighted_avg_clv_pct",
            min_count=5,
        )
        # top_type first (highest metric), then aaa_type before zzz_type (same metric, alpha)
        assert len(rows) == 3
        assert rows[0]["segment"] == "market_type:top_type"
        assert rows[1]["segment"] == "market_type:aaa_type"
        assert rows[2]["segment"] == "market_type:zzz_type"

    def test_top_segments_min_count_respected(self):
        """Segments with count < TOP_SEGMENT_MIN_COUNT are excluded."""
        segment_analysis = {
            "by_market_type": {
                "big_segment": {"count": TOP_SEGMENT_MIN_COUNT, "notional_weighted_avg_clv_pct": 0.30},
                "small_segment": {"count": TOP_SEGMENT_MIN_COUNT - 1, "notional_weighted_avg_clv_pct": 0.90},
            }
        }
        rows = _collect_top_segments_by_metric(
            segment_analysis,
            "notional_weighted_avg_clv_pct",
            min_count=TOP_SEGMENT_MIN_COUNT,
        )
        segment_names = [r["segment"] for r in rows]
        assert "market_type:big_segment" in segment_names
        assert "market_type:small_segment" not in segment_names

    def test_top_segments_none_metric_excluded(self):
        """Buckets where the metric is None are excluded (no crashes)."""
        segment_analysis = {
            "by_market_type": {
                "has_metric": {"count": 10, "notional_weighted_avg_clv_pct": 0.25},
                "no_metric": {"count": 10, "notional_weighted_avg_clv_pct": None},
            }
        }
        rows = _collect_top_segments_by_metric(
            segment_analysis,
            "notional_weighted_avg_clv_pct",
            min_count=5,
        )
        assert len(rows) == 1
        assert rows[0]["segment"] == "market_type:has_metric"

    def test_top_segments_integration_end_to_end(self):
        """Full build_coverage_report: segments with enough positions appear in top-segments."""
        # Create 6 positions in the 'nba' league with notional + CLV data
        # so nba should appear in top segments (count >= 5)
        positions = [
            {
                "resolved_token_id": f"top-seg-{i}",
                "entry_price": 0.40,
                "clv_pct": 0.20,
                "beat_close": True,
                "position_notional_usd": 50.0,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
            for i in range(6)
        ]
        report = build_coverage_report(
            positions=positions, run_id="top-seg-e2e", user_slug="u", wallet="0xabc"
        )
        hyp_meta = report["segment_analysis"]["hypothesis_meta"]
        assert hyp_meta["notional_weight_total_global"] == pytest.approx(6 * 50.0)

        # Verify nba bucket has notional_weighted_avg_clv_pct
        nba_bucket = report["segment_analysis"]["by_league"]["nba"]
        assert nba_bucket["notional_weighted_avg_clv_pct"] == pytest.approx(0.20)
        assert nba_bucket["count"] == 6

        # Markdown should include Hypothesis Signals section
        import shutil
        output_dir = Path("artifacts") / "_pytest_hyp_signals"
        shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            paths = write_coverage_report(report, output_dir, write_markdown=True)
            md = Path(paths["md"]).read_text(encoding="utf-8")
            assert "## Hypothesis Signals" in md
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # 5. _compute_median helper
    # ------------------------------------------------------------------

    def test_compute_median_odd_count(self):
        assert _compute_median([3.0, 1.0, 2.0]) == 2.0

    def test_compute_median_even_count(self):
        assert _compute_median([1.0, 2.0, 3.0, 4.0]) == pytest.approx(2.5)

    def test_compute_median_empty(self):
        assert _compute_median([]) is None

    def test_median_minutes_to_close_per_segment(self):
        """Median and avg minutes_to_close are computed correctly per bucket."""
        positions = [
            {
                "resolved_token_id": f"mtc-{i}",
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
                "minutes_to_close": mtc,
            }
            for i, mtc in enumerate([60, 120, 180])
        ]
        report = build_coverage_report(
            positions=positions, run_id="mtc-test", user_slug="u", wallet="0xabc"
        )
        bucket = report["segment_analysis"]["by_league"]["nba"]
        assert bucket["avg_minutes_to_close"] == pytest.approx(120.0)
        assert bucket["median_minutes_to_close"] == pytest.approx(120.0)
        assert bucket["minutes_to_close_count_used"] == 3

    # ------------------------------------------------------------------
    # 6. Notional source fallback (total_cost, size*entry_price)
    # ------------------------------------------------------------------

    def test_notional_fallback_total_cost_only(self):
        """When only total_cost is present it is used as notional weight."""
        # pos A: clv_pct=0.20, total_cost=100  -> weight 100, contributes 20.0
        # pos B: clv_pct=0.60, total_cost=50   -> weight 50, contributes 30.0
        # weighted avg = 50.0 / 150 = 0.3333...
        positions = [
            {
                "resolved_token_id": f"tc-{i}",
                "entry_price": 0.50,
                "clv_pct": clv,
                "beat_close": True,
                "total_cost": cost,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
            for i, (clv, cost) in enumerate([(0.20, 100.0), (0.60, 50.0)])
        ]
        report = build_coverage_report(
            positions=positions, run_id="notional-total-cost", user_slug="u", wallet="0xabc"
        )
        hyp_meta = report["segment_analysis"]["hypothesis_meta"]
        assert hyp_meta["notional_weight_total_global"] == pytest.approx(150.0)

        bucket = report["segment_analysis"]["by_league"]["nba"]
        expected = (0.20 * 100.0 + 0.60 * 50.0) / 150.0
        assert bucket["notional_weighted_avg_clv_pct"] == pytest.approx(expected, rel=1e-5)
        assert bucket["notional_weighted_avg_clv_pct_weight_used"] == pytest.approx(150.0)

    def test_notional_position_notional_usd_preferred_over_total_cost(self):
        """position_notional_usd wins over total_cost when both are present."""
        # position_notional_usd=200, total_cost=50 -> 200 should be used
        pos = {
            "position_notional_usd": 200.0,
            "total_cost": 50.0,
            "entry_price": 0.50,
            "size": 40.0,
        }
        assert extract_position_notional_usd(pos) == pytest.approx(200.0)

        # Full integration: only position_notional_usd should count
        positions = [
            {
                "resolved_token_id": "pref-test",
                "entry_price": 0.50,
                "clv_pct": 0.30,
                "beat_close": True,
                "position_notional_usd": 200.0,
                "total_cost": 50.0,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
        ]
        report = build_coverage_report(
            positions=positions, run_id="notional-pref", user_slug="u", wallet="0xabc"
        )
        hyp_meta = report["segment_analysis"]["hypothesis_meta"]
        assert hyp_meta["notional_weight_total_global"] == pytest.approx(200.0)

    def test_notional_no_source_skips_weight(self):
        """When neither position_notional_usd nor total_cost nor size*price is present,
        notional metrics remain None and global denom stays 0."""
        positions = [
            {
                "resolved_token_id": "no-notional",
                "entry_price": 0.50,
                "clv_pct": 0.40,
                "beat_close": True,
                "market_slug": "nba-lal-bos-2026",
                "question": "Will LAL win?",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
                # no position_notional_usd, no total_cost, no size
            }
        ]
        report = build_coverage_report(
            positions=positions, run_id="notional-none", user_slug="u", wallet="0xabc"
        )
        hyp_meta = report["segment_analysis"]["hypothesis_meta"]
        assert hyp_meta["notional_weight_total_global"] == 0.0

        bucket = report["segment_analysis"]["by_league"]["nba"]
        assert bucket["notional_w_total_weight_used"] == 0.0
        assert bucket["notional_weighted_avg_clv_pct"] is None
        assert bucket["notional_weighted_beat_close_rate"] is None


class TestBuildHypothesisCandidates:
    """Unit tests for _build_hypothesis_candidates and write_hypothesis_candidates."""

    def test_empty_segment_analysis_returns_empty_list(self):
        result = _build_hypothesis_candidates({})
        assert result == []

    def test_candidates_below_min_count_excluded(self):
        seg = {
            "by_entry_price_tier": {
                "coinflip": {
                    "count": 2,  # Below TOP_SEGMENT_MIN_COUNT=5
                    "notional_weighted_avg_clv_pct": 0.5,
                    "notional_weighted_avg_clv_pct_weight_used": 50.0,
                    "notional_weighted_beat_close_rate": 0.6,
                    "notional_weighted_beat_close_rate_weight_used": 50.0,
                    "avg_clv_pct": 0.4,
                    "avg_clv_pct_count_used": 2,
                    "beat_close_rate": 0.5,
                    "beat_close_rate_count_used": 2,
                    "avg_entry_drift_pct": None,
                    "avg_entry_drift_pct_count_used": 0,
                    "avg_minutes_to_close": None,
                    "median_minutes_to_close": None,
                    "minutes_to_close_count_used": 0,
                    "win_rate": 0.5,
                }
            }
        }
        result = _build_hypothesis_candidates(seg)
        assert result == []

    def test_candidates_ranked_by_notional_clv_desc(self):
        seg = {
            "by_entry_price_tier": {
                "coinflip": {
                    "count": 10,
                    "notional_weighted_avg_clv_pct": 0.15,
                    "notional_weighted_avg_clv_pct_weight_used": 100.0,
                    "notional_weighted_beat_close_rate": 0.6,
                    "notional_weighted_beat_close_rate_weight_used": 100.0,
                    "avg_clv_pct": 0.12,
                    "avg_clv_pct_count_used": 10,
                    "beat_close_rate": 0.55,
                    "beat_close_rate_count_used": 10,
                    "avg_entry_drift_pct": None,
                    "avg_entry_drift_pct_count_used": 0,
                    "avg_minutes_to_close": None,
                    "median_minutes_to_close": None,
                    "minutes_to_close_count_used": 0,
                    "win_rate": 0.6,
                },
                "favorite": {
                    "count": 10,
                    "notional_weighted_avg_clv_pct": 0.05,
                    "notional_weighted_avg_clv_pct_weight_used": 80.0,
                    "notional_weighted_beat_close_rate": 0.5,
                    "notional_weighted_beat_close_rate_weight_used": 80.0,
                    "avg_clv_pct": 0.04,
                    "avg_clv_pct_count_used": 10,
                    "beat_close_rate": 0.45,
                    "beat_close_rate_count_used": 10,
                    "avg_entry_drift_pct": None,
                    "avg_entry_drift_pct_count_used": 0,
                    "avg_minutes_to_close": None,
                    "median_minutes_to_close": None,
                    "minutes_to_close_count_used": 0,
                    "win_rate": 0.5,
                },
            }
        }
        result = _build_hypothesis_candidates(seg)
        assert len(result) == 2
        assert result[0]["segment_key"] == "entry_price_tier:coinflip"
        assert result[1]["segment_key"] == "entry_price_tier:favorite"

    def test_candidate_has_required_fields(self):
        seg = {
            "by_entry_price_tier": {
                "coinflip": {
                    "count": 10,
                    "notional_weighted_avg_clv_pct": 0.15,
                    "notional_weighted_avg_clv_pct_weight_used": 100.0,
                    "notional_weighted_beat_close_rate": 0.6,
                    "notional_weighted_beat_close_rate_weight_used": 100.0,
                    "avg_clv_pct": 0.12,
                    "avg_clv_pct_count_used": 10,
                    "beat_close_rate": 0.55,
                    "beat_close_rate_count_used": 10,
                    "avg_entry_drift_pct": None,
                    "avg_entry_drift_pct_count_used": 0,
                    "avg_minutes_to_close": None,
                    "median_minutes_to_close": None,
                    "minutes_to_close_count_used": 0,
                    "win_rate": 0.6,
                },
                "favorite": {
                    "count": 10,
                    "notional_weighted_avg_clv_pct": 0.05,
                    "notional_weighted_avg_clv_pct_weight_used": 80.0,
                    "notional_weighted_beat_close_rate": 0.5,
                    "notional_weighted_beat_close_rate_weight_used": 80.0,
                    "avg_clv_pct": 0.04,
                    "avg_clv_pct_count_used": 10,
                    "beat_close_rate": 0.45,
                    "beat_close_rate_count_used": 10,
                    "avg_entry_drift_pct": None,
                    "avg_entry_drift_pct_count_used": 0,
                    "avg_minutes_to_close": None,
                    "median_minutes_to_close": None,
                    "minutes_to_close_count_used": 0,
                    "win_rate": 0.5,
                },
            }
        }
        candidates = _build_hypothesis_candidates(seg)
        c = candidates[0]
        assert "segment_key" in c
        assert "rank" in c
        assert "metrics" in c
        assert "denominators" in c
        assert "falsification_plan" in c
        assert c["rank"] == 1
        assert c["denominators"]["weighting"] == "notional"
        assert c["falsification_plan"]["min_sample_size"] >= 30
        assert len(c["falsification_plan"]["stop_conditions"]) >= 1

    def test_write_hypothesis_candidates_produces_valid_json(self, tmp_path):
        path = write_hypothesis_candidates(
            candidates=[{"segment_key": "x"}],
            output_dir=tmp_path,
            generated_at="2026-02-20T00:00:00+00:00",
            run_id="r1",
            user_slug="testuser",
            wallet="0xabc",
        )
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["candidates"] == [{"segment_key": "x"}]
        for key in ("generated_at", "run_id", "user_slug", "wallet", "candidates"):
            assert key in data

    def test_build_coverage_report_includes_hypothesis_candidates_key(self):
        positions = [
            {
                "resolved_token_id": f"tok_{i:03d}",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 1.0,
                "position_remaining": 0.0,
            }
            for i in range(10)
        ] + [
            {
                "resolved_token_id": f"tok_{i:03d}",
                "resolution_outcome": "LOSS",
                "realized_pnl_net": -0.5,
                "position_remaining": 0.0,
            }
            for i in range(10, 20)
        ]
        report = build_coverage_report(
            positions=positions,
            run_id="test-hyp",
            user_slug="u",
            wallet="0xabc",
        )
        assert "hypothesis_candidates" in report


class TestExtractPositionNotionalUsd:
    """Unit tests for extract_position_notional_usd fallback chain."""

    def test_total_cost_used_when_no_explicit_notional(self):
        """Positions with total_cost but no position_notional_usd should yield a positive weight."""
        pos = {
            "token_id": "tok_tc_001",
            "total_cost": 47.50,
            "resolution_outcome": "WIN",
            "clv_pct": 0.12,
            "beat_close": True,
        }
        result = extract_position_notional_usd(pos)
        assert result == pytest.approx(47.50), (
            "Expected total_cost to be returned when position_notional_usd absent"
        )

    def test_string_total_cost_coerces_to_float(self):
        """total_cost stored as a numeric string should coerce cleanly; non-numeric should return None."""
        pos_numeric_str = {"total_cost": "25.00"}
        assert extract_position_notional_usd(pos_numeric_str) == pytest.approx(25.0)

        pos_bad_str = {"total_cost": "N/A"}
        assert extract_position_notional_usd(pos_bad_str) is None, (
            "Non-numeric string total_cost should return None, not raise"
        )


class TestNotionalWeightInCoverageReport:
    """Integration: build_coverage_report produces non-null notional metrics when total_cost present."""

    def _make_positions_with_total_cost(self):
        """Positions that have total_cost but NOT position_notional_usd."""
        base = [
            {
                "resolved_token_id": f"tok_{i:03d}",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 5.0,
                "total_cost": 20.0 + i,
                "clv_pct": 0.10 + i * 0.01,
                "beat_close": True,
                "fees_actual": 0.0,
                "fees_estimated": 0.0,
                "fees_source": "unknown",
                "position_remaining": 0.0,
            }
            for i in range(6)  # 6 positions > TOP_SEGMENT_MIN_COUNT=5
        ]
        return base

    def test_notional_weight_total_global_nonzero_with_total_cost(self):
        """After injecting position_notional_usd from total_cost, hypothesis_meta weight > 0."""
        from tools.cli.scan import _normalize_position_notional

        positions = self._make_positions_with_total_cost()
        # Simulate scan.py normalization step
        _normalize_position_notional(positions)

        # All positions should now have position_notional_usd set
        for pos in positions:
            assert "position_notional_usd" in pos and pos["position_notional_usd"] > 0

        report = build_coverage_report(positions=positions, run_id="test-run", user_slug="testuser", wallet="0xabc")
        hyp_meta = report.get("segment_analysis", {}).get("hypothesis_meta", {})
        weight = hyp_meta.get("notional_weight_total_global", 0.0)
        assert weight > 0, (
            f"Expected notional_weight_total_global > 0, got {weight}. "
            "Likely total_cost normalization did not propagate."
        )

    def test_notional_weighted_metrics_non_null_after_normalization(self):
        """Segment metrics include non-null notional-weighted fields after normalization."""
        from tools.cli.scan import _normalize_position_notional

        positions = self._make_positions_with_total_cost()
        _normalize_position_notional(positions)

        report = build_coverage_report(positions=positions, run_id="test-run2", user_slug="testuser2", wallet="0xdef")
        segment_analysis = report.get("segment_analysis", {})
        # At least one segment bucket should have a non-null notional_weighted_avg_clv_pct
        any_weighted = any(
            v.get("notional_weighted_avg_clv_pct") is not None
            for bucket_group in segment_analysis.values()
            if isinstance(bucket_group, dict)
            for v in bucket_group.values()
            if isinstance(v, dict)
        )
        assert any_weighted, (
            "Expected at least one segment bucket to have non-null notional_weighted_avg_clv_pct "
            "after total_cost normalization."
        )
        assert isinstance(report["hypothesis_candidates"], list)


class TestDualClvVariantCoverage:
    """Unit tests for dual CLV variant sub-dicts in _build_clv_coverage."""

    def _make_positions_with_variants(self):
        return [
            {
                "resolved_token_id": "tok_s1",
                "entry_price": 0.42,
                "clv": 0.09,
                "clv_pct": 0.214,
                "clv_source": "prices_history|onchain_resolved_at",
                "clv_missing_reason": None,
                "clv_pct_settlement": 0.214,
                "clv_missing_reason_settlement": None,
                "clv_source_settlement": "prices_history|onchain_resolved_at",
                "clv_pct_pre_event": None,
                "clv_missing_reason_pre_event": "NO_PRE_EVENT_CLOSE_TS",
                "clv_source_pre_event": None,
            },
            {
                "resolved_token_id": "tok_s2",
                "entry_price": 0.35,
                "clv": None,
                "clv_pct": None,
                "clv_source": None,
                "clv_missing_reason": "NO_CLOSE_TS",
                "clv_pct_settlement": None,
                "clv_missing_reason_settlement": "NO_SETTLEMENT_CLOSE_TS",
                "clv_source_settlement": None,
                "clv_pct_pre_event": 0.05,
                "clv_missing_reason_pre_event": None,
                "clv_source_pre_event": "prices_history|gamma_closedTime",
            },
        ]

    def test_build_clv_coverage_includes_settlement_and_pre_event_sub_dicts(self):
        positions = self._make_positions_with_variants()
        result = _build_clv_coverage(positions)
        assert "settlement" in result
        assert "pre_event" in result
        settlement = result["settlement"]
        pre_event = result["pre_event"]
        assert settlement["clv_present_count"] == 1
        assert settlement["clv_missing_count"] == 1
        assert pre_event["clv_present_count"] == 1
        assert pre_event["clv_missing_count"] == 1

    def test_clv_variant_coverage_rate_computed_correctly(self):
        positions = self._make_positions_with_variants()
        result = _build_clv_coverage(positions)
        settlement = result["settlement"]
        assert settlement["eligible_positions"] == 2
        assert settlement["coverage_rate"] == 0.5


class TestDualClvHypothesisCandidates:
    """Unit tests for pre_event preference and settlement fallback in hypothesis ranking."""

    def _seg_with_pre_event(self, pre_event_nw=0.20, pre_event_weight=100.0,
                             settlement_nw=0.10, settlement_weight=100.0):
        return {
            "by_entry_price_tier": {
                "coinflip": {
                    "count": 10,
                    "notional_weighted_avg_clv_pct": 0.10,
                    "notional_weighted_avg_clv_pct_weight_used": 100.0,
                    "notional_weighted_beat_close_rate": 0.6,
                    "notional_weighted_beat_close_rate_weight_used": 100.0,
                    "avg_clv_pct": 0.08,
                    "avg_clv_pct_count_used": 10,
                    "beat_close_rate": 0.55,
                    "beat_close_rate_count_used": 10,
                    "avg_entry_drift_pct": None,
                    "avg_entry_drift_pct_count_used": 0,
                    "avg_minutes_to_close": None,
                    "median_minutes_to_close": None,
                    "minutes_to_close_count_used": 0,
                    "win_rate": 0.6,
                    "notional_weighted_avg_clv_pct_pre_event": pre_event_nw,
                    "notional_weighted_avg_clv_pct_pre_event_weight_used": pre_event_weight,
                    "notional_weighted_avg_clv_pct_settlement": settlement_nw,
                    "notional_weighted_avg_clv_pct_settlement_weight_used": settlement_weight,
                    "avg_clv_pct_pre_event": 0.18,
                    "avg_clv_pct_settlement": 0.09,
                }
            }
        }

    def test_build_hypothesis_candidates_prefers_pre_event_when_denom_positive(self):
        """When pre_event weight > 0, clv_variant_used should be 'pre_event'."""
        seg = self._seg_with_pre_event(pre_event_nw=0.20, pre_event_weight=100.0)
        candidates = _build_hypothesis_candidates(seg)
        assert len(candidates) == 1
        c = candidates[0]
        assert c["clv_variant_used"] == "pre_event"
        assert c["rank"] == 1

    def test_build_hypothesis_candidates_falls_back_to_settlement(self):
        """When pre_event weight == 0 and settlement weight > 0, uses settlement."""
        seg = self._seg_with_pre_event(
            pre_event_nw=None, pre_event_weight=0.0,
            settlement_nw=0.10, settlement_weight=100.0
        )
        # pre_event_nw=None means it won't match the pre_event condition
        seg["by_entry_price_tier"]["coinflip"]["notional_weighted_avg_clv_pct_pre_event"] = None
        candidates = _build_hypothesis_candidates(seg)
        assert len(candidates) == 1
        c = candidates[0]
        assert c["clv_variant_used"] == "settlement"

    def test_build_hypothesis_candidates_includes_clv_variant_used_field(self):
        """All candidates include the clv_variant_used field."""
        seg = self._seg_with_pre_event()
        candidates = _build_hypothesis_candidates(seg)
        for c in candidates:
            assert "clv_variant_used" in c


class TestRobustStats:
    def test_median_odd(self):
        r = _compute_robust_stats([3.0, 1.0, 2.0])
        assert r["median"] == 2.0
        assert r["count_used"] == 3

    def test_median_even(self):
        r = _compute_robust_stats([1.0, 2.0, 3.0, 4.0])
        assert r["median"] == 2.5

    def test_trimmed_mean_10pct(self):
        # 10 values: trim floor(10*0.10)=1 from each tail -> 8 values used
        vals = [float(i) for i in range(1, 11)]  # [1..10]
        r = _compute_robust_stats(vals)
        # trimmed slice: [2,3,4,5,6,7,8,9] -> mean = 5.5
        assert r["trimmed_mean"] == 5.5

    def test_trimmed_mean_small_no_trim(self):
        # 5 values: floor(5*0.10)=0 -> no trim, mean = all values
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = _compute_robust_stats(vals)
        assert r["trimmed_mean"] == 3.0

    def test_iqr(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = _compute_robust_stats(vals)
        # p25: ceil(5*0.25)-1 = ceil(1.25)-1 = 2-1 = 1 -> sorted_vals[1] = 2.0
        assert r["p25"] == 2.0
        # p75: ceil(5*0.75)-1 = ceil(3.75)-1 = 4-1 = 3 -> sorted_vals[3] = 4.0
        assert r["p75"] == 4.0

    def test_single_value(self):
        r = _compute_robust_stats([7.5])
        assert r["median"] == 7.5
        assert r["trimmed_mean"] == 7.5
        assert r["p25"] == 7.5
        assert r["p75"] == 7.5

    def test_empty(self):
        r = _compute_robust_stats([])
        assert r["median"] is None
        assert r["trimmed_mean"] is None
        assert r["count_used"] == 0

    def test_cap_deterministic(self):
        # Accumulating MAX_ROBUST_VALUES+10 values should cap at MAX_ROBUST_VALUES
        from polytool.reports.coverage import _accumulate_segment_bucket, _empty_segment_bucket, MAX_ROBUST_VALUES
        b = _empty_segment_bucket()
        for i in range(MAX_ROBUST_VALUES + 10):
            _accumulate_segment_bucket(
                b,
                outcome="WIN",
                pnl_net=0.0,
                pnl_gross=0.0,
                clv_pct=float(i),
                beat_close=None,
            )
        assert len(b["_clv_pct_values"]) == MAX_ROBUST_VALUES

    def test_finalized_bucket_has_robust_fields(self):
        from polytool.reports.coverage import _accumulate_segment_bucket, _empty_segment_bucket, _finalize_segment_bucket
        b = _empty_segment_bucket()
        for v in [0.1, 0.2, 0.3]:
            _accumulate_segment_bucket(b, "WIN", 0.0, 0.0, clv_pct=v, beat_close=None, entry_drift_pct=v * 0.5)
        f = _finalize_segment_bucket(b)
        for field in ["median_clv_pct", "trimmed_mean_clv_pct", "p25_clv_pct", "p75_clv_pct",
                      "robust_clv_pct_count_used", "median_entry_drift_pct",
                      "trimmed_mean_entry_drift_pct", "robust_entry_drift_pct_count_used"]:
            assert field in f, f"Missing: {field}"
        assert f["robust_clv_pct_count_used"] == 3
        assert f["median_clv_pct"] == 0.2

    def test_deterministic_output_ordering(self):
        # Same values appended in same order => same robust stats across two identical runs
        from polytool.reports.coverage import _accumulate_segment_bucket, _empty_segment_bucket, _finalize_segment_bucket
        vals = [0.05, -0.1, 0.3, 0.0, 0.15]
        def _make():
            b = _empty_segment_bucket()
            for v in vals:
                _accumulate_segment_bucket(b, "WIN", 0.0, 0.0, clv_pct=v, beat_close=None)
            return _finalize_segment_bucket(b)
        f1 = _make()
        f2 = _make()
        assert f1["median_clv_pct"] == f2["median_clv_pct"]
        assert f1["trimmed_mean_clv_pct"] == f2["trimmed_mean_clv_pct"]
