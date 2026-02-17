"""Tests for polytool.reports.coverage — Coverage & Reconciliation Report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from polytool.reports.coverage import (
    PENDING_COVERAGE_INVALID_WARNING,
    REPORT_VERSION,
    build_coverage_report,
    normalize_fee_fields,
    write_coverage_report,
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
    assert pending is not None, f"No PENDING sell_count==0 position found in {dossier_path}"
    return dict(pending)


class TestNormalizeFeeFields:
    def test_actual_fee_sets_source(self):
        pos = {"fees_actual": 1.5, "fees_estimated": 0.0}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "actual"

    def test_estimated_fee_sets_source(self):
        pos = {"fees_actual": 0.0, "fees_estimated": 0.5}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "estimated"

    def test_no_fees_sets_unknown(self):
        pos = {"fees_actual": 0.0, "fees_estimated": 0.0}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "unknown"

    def test_missing_fields_default(self):
        pos = {}
        normalize_fee_fields(pos)
        assert pos["fees_actual"] == 0.0
        assert pos["fees_estimated"] == 0.0
        assert pos["fees_source"] == "unknown"

    def test_actual_takes_precedence(self):
        pos = {"fees_actual": 2.0, "fees_estimated": 1.0}
        normalize_fee_fields(pos)
        assert pos["fees_source"] == "actual"


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
        # 10.5 + (-3.2) + 7.0 + (-1.0) + 0.0 = 13.3  (None is skipped)
        assert abs(pnl["realized_pnl_net_total"] - 13.3) < 0.001
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
        assert fees["fees_source_counts"]["actual"] == 1
        assert fees["fees_source_counts"]["estimated"] == 1
        assert fees["fees_source_counts"]["unknown"] == 4
        assert fees["fees_actual_present_count"] == 1
        assert fees["fees_estimated_present_count"] == 1

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
            "fees", "resolution_coverage", "segment_analysis", "warnings",
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
        assert segment_analysis["by_market_type"]["unknown"]["count"] == 1

        assert segment_analysis["by_league"]["nba"]["count"] == 1
        assert segment_analysis["by_league"]["unknown"]["count"] == 2

        assert segment_analysis["by_sport"]["basketball"]["count"] == 1
        assert segment_analysis["by_sport"]["unknown"]["count"] == 2

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
