"""Tests for Gate 2 corpus visibility helpers.

Covers:
  - classify_tape_confidence (all tier branches)
  - classify_reject_code (all code branches)
  - enrich_tape_diagnostics (field population)
  - print_table / print_ranked_table column header presence
"""

from __future__ import annotations

import io
import sys

import pytest

from tools.cli.tape_manifest import (
    TapeRecord,
    CorpusSummary,
    classify_reject_code,
    classify_tape_confidence,
    enrich_tape_diagnostics,
    print_corpus_quality_breakdown,
)
from tools.cli.scan_gate2_candidates import (
    CandidateResult,
    print_table,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_record(
    recorded_by: str = "unknown",
    eligible: bool = False,
    reject_reason: str = "",
    evidence: dict | None = None,
) -> TapeRecord:
    return TapeRecord(
        tape_dir="/fake/tape",
        slug="test-market",
        regime="politics",
        recorded_by=recorded_by,
        eligible=eligible,
        executable_ticks=0,
        reject_reason=reject_reason,
        evidence=evidence or {},
    )


# ---------------------------------------------------------------------------
# classify_tape_confidence
# ---------------------------------------------------------------------------


class TestClassifyTapeConfidence:
    def test_unknown_when_no_events(self):
        assert classify_tape_confidence("watch-arb-candidates", 0, 0) == "UNKNOWN"

    def test_unknown_when_events_negative(self):
        assert classify_tape_confidence("watch-arb-candidates", -1, 0) == "UNKNOWN"

    def test_gold_gold_source_adequate_density(self):
        # watch-arb-candidates + 50+ events + 20+ BBO ticks → GOLD
        assert classify_tape_confidence("watch-arb-candidates", 50, 20) == "GOLD"

    def test_gold_shadow_source(self):
        assert classify_tape_confidence("simtrader-shadow", 100, 30) == "GOLD"

    def test_silver_gold_source_thin_bbo(self):
        # Gold source but BBO below threshold → SILVER (events>=50 fallback)
        assert classify_tape_confidence("watch-arb-candidates", 50, 5) == "SILVER"

    def test_silver_any_source_high_events(self):
        # Non-gold/silver source but 50+ events → SILVER
        assert classify_tape_confidence("unknown", 50, 0) == "SILVER"

    def test_silver_silver_source_moderate_events(self):
        # prepare-gate2 with 20-49 events → SILVER
        assert classify_tape_confidence("prepare-gate2", 20, 0) == "SILVER"

    def test_silver_quickrun_source_moderate_events(self):
        assert classify_tape_confidence("simtrader-quickrun", 30, 0) == "SILVER"

    def test_bronze_has_bbo_but_below_silver(self):
        # Unknown source, <20 events, but has some BBO ticks → BRONZE
        assert classify_tape_confidence("unknown", 5, 3) == "BRONZE"

    def test_unknown_no_bbo_below_thresholds(self):
        # <20 events, no BBO, non-silver source → UNKNOWN
        assert classify_tape_confidence("unknown", 5, 0) == "UNKNOWN"


# ---------------------------------------------------------------------------
# classify_reject_code
# ---------------------------------------------------------------------------


class TestClassifyRejectCode:
    def test_eligible_when_both_exist(self):
        ev = {
            "ticks_with_depth_ok": 10,
            "ticks_with_edge_ok": 5,
            "ticks_with_depth_and_edge": 3,
        }
        assert classify_reject_code(ev) == "ELIGIBLE"

    def test_no_overlap_depth_and_edge_never_simultaneous(self):
        ev = {
            "ticks_with_depth_ok": 10,
            "ticks_with_edge_ok": 5,
            "ticks_with_depth_and_edge": 0,
        }
        assert classify_reject_code(ev) == "NO_OVERLAP"

    def test_depth_only(self):
        ev = {
            "ticks_with_depth_ok": 10,
            "ticks_with_edge_ok": 0,
            "ticks_with_depth_and_edge": 0,
        }
        assert classify_reject_code(ev) == "DEPTH_ONLY"

    def test_edge_only(self):
        ev = {
            "ticks_with_depth_ok": 0,
            "ticks_with_edge_ok": 8,
            "ticks_with_depth_and_edge": 0,
        }
        assert classify_reject_code(ev) == "EDGE_ONLY"

    def test_no_depth_no_edge(self):
        ev = {
            "ticks_with_depth_ok": 0,
            "ticks_with_edge_ok": 0,
            "ticks_with_depth_and_edge": 0,
        }
        assert classify_reject_code(ev) == "NO_DEPTH_NO_EDGE"

    def test_no_events_from_reason(self):
        assert classify_reject_code({}, "no events.jsonl found in tape directory") == "NO_EVENTS"

    def test_no_assets_from_reason(self):
        assert classify_reject_code({}, "could not determine asset_id from tape") == "NO_ASSETS"

    def test_unknown_fallback(self):
        assert classify_reject_code({}, "some other reason") == "UNKNOWN"

    def test_empty_evidence_empty_reason(self):
        assert classify_reject_code({}) == "UNKNOWN"


# ---------------------------------------------------------------------------
# enrich_tape_diagnostics
# ---------------------------------------------------------------------------


class TestEnrichTapeDiagnostics:
    def test_eligible_tape_returns_eligible_code(self):
        ev = {
            "events_scanned": 100,
            "ticks_with_both_bbo": 50,
            "ticks_with_depth_ok": 20,
            "ticks_with_edge_ok": 15,
            "ticks_with_depth_and_edge": 8,
        }
        rec = _make_record(
            recorded_by="watch-arb-candidates",
            eligible=True,
            evidence=ev,
        )
        d = enrich_tape_diagnostics(rec)
        assert d["reject_code"] == "ELIGIBLE"
        assert d["confidence_class"] == "GOLD"
        assert d["events_scanned"] == 100
        assert d["ticks_with_bbo"] == 50

    def test_depth_only_reject_code(self):
        ev = {
            "events_scanned": 80,
            "ticks_with_both_bbo": 40,
            "ticks_with_depth_ok": 15,
            "ticks_with_edge_ok": 0,
            "ticks_with_depth_and_edge": 0,
        }
        rec = _make_record(
            recorded_by="simtrader-shadow",
            eligible=False,
            evidence=ev,
        )
        d = enrich_tape_diagnostics(rec)
        assert d["reject_code"] == "DEPTH_ONLY"
        assert d["confidence_class"] == "GOLD"

    def test_edge_gap_computed_when_data_present(self):
        ev = {
            "events_scanned": 60,
            "ticks_with_both_bbo": 25,
            "min_sum_ask_seen": 0.97,
            "required_edge_threshold": 0.99,
            "ticks_with_depth_ok": 0,
            "ticks_with_edge_ok": 5,
            "ticks_with_depth_and_edge": 0,
        }
        rec = _make_record(recorded_by="watch-arb-candidates", eligible=False, evidence=ev)
        d = enrich_tape_diagnostics(rec)
        assert d["best_edge_gap"] is not None
        assert abs(d["best_edge_gap"] - 0.02) < 1e-5

    def test_edge_gap_none_when_missing(self):
        rec = _make_record(recorded_by="unknown", eligible=False, evidence={"events_scanned": 10, "ticks_with_both_bbo": 5})
        d = enrich_tape_diagnostics(rec)
        assert d["best_edge_gap"] is None

    def test_empty_evidence_returns_unknown(self):
        rec = _make_record(recorded_by="unknown", eligible=False, reject_reason="no events.jsonl found")
        d = enrich_tape_diagnostics(rec)
        assert d["confidence_class"] == "UNKNOWN"
        assert d["reject_code"] == "NO_EVENTS"
        assert d["events_scanned"] == 0


# ---------------------------------------------------------------------------
# print_table column headers
# ---------------------------------------------------------------------------


class TestPrintTableHeaders:
    def _capture(self, results, top=5, mode="tape"):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            print_table(results, top=top, mode=mode)
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    def _make_result(self, events=60, conf="GOLD", exec_ticks=0):
        return CandidateResult(
            slug="test-market",
            total_ticks=100,
            depth_ok_ticks=10,
            edge_ok_ticks=5,
            executable_ticks=exec_ticks,
            best_edge=-0.01,
            max_depth_yes=30.0,
            max_depth_no=25.0,
            source="tape",
            events_scanned=events,
            confidence_class=conf,
            recorded_by="watch-arb-candidates",
        )

    def test_events_column_in_header(self):
        output = self._capture([self._make_result()])
        assert "Events" in output

    def test_conf_column_in_header(self):
        output = self._capture([self._make_result()])
        assert "Conf" in output

    def test_gold_abbrev_in_row(self):
        output = self._capture([self._make_result(conf="GOLD")])
        assert "GOLD" in output

    def test_silver_abbrev_in_row(self):
        output = self._capture([self._make_result(conf="SILVER")])
        assert "SILV" in output

    def test_events_count_in_row(self):
        output = self._capture([self._make_result(events=123)])
        assert "123" in output

    def test_empty_results_prints_no_signal(self):
        output = self._capture([])
        assert "No candidate signal found" in output


# ---------------------------------------------------------------------------
# TestGate2RankScorePassthrough
# ---------------------------------------------------------------------------


class TestGate2RankScorePassthrough:
    def test_events_scanned_on_gate2_rank_score(self):
        """Gate2RankScore carries events_scanned from score_gate2_candidate."""
        from packages.polymarket.market_selection.scorer import score_gate2_candidate
        score = score_gate2_candidate(
            "test-slug",
            executable_ticks=0,
            edge_ok_ticks=0,
            depth_ok_ticks=0,
            best_edge_raw=-99.0,
            depth_yes=0.0,
            depth_no=0.0,
            events_scanned=150,
            confidence_class="GOLD",
        )
        assert score.events_scanned == 150
        assert score.confidence_class == "GOLD"

    def test_defaults_none_when_not_passed(self):
        """Gate2RankScore defaults to None when fields not provided."""
        from packages.polymarket.market_selection.scorer import score_gate2_candidate
        score = score_gate2_candidate(
            "test-slug",
            executable_ticks=0,
            edge_ok_ticks=0,
            depth_ok_ticks=0,
            best_edge_raw=-99.0,
            depth_yes=0.0,
            depth_no=0.0,
        )
        assert score.events_scanned is None
        assert score.confidence_class is None

    def test_score_and_rank_passes_through(self):
        """score_and_rank_candidates forwards events_scanned from CandidateResult."""
        from tools.cli.scan_gate2_candidates import (
            CandidateResult,
            score_and_rank_candidates,
        )
        cr = CandidateResult(
            slug="test-slug",
            total_ticks=100,
            depth_ok_ticks=10,
            edge_ok_ticks=5,
            executable_ticks=0,
            best_edge=-0.02,
            max_depth_yes=30.0,
            max_depth_no=25.0,
            source="tape",
            events_scanned=200,
            confidence_class="SILVER",
        )
        ranked = score_and_rank_candidates([cr])
        assert len(ranked) == 1
        assert ranked[0].events_scanned == 200
        assert ranked[0].confidence_class == "SILVER"


# ---------------------------------------------------------------------------
# TestCorpusQualityBreakdown
# ---------------------------------------------------------------------------


class TestCorpusQualityBreakdown:
    def _capture_breakdown(self, records, summary):
        """Capture stdout from print_corpus_quality_breakdown."""
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            print_corpus_quality_breakdown(records, summary)
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    def _make_summary(self, eligible=0, total=5):
        return CorpusSummary(
            total_tapes=total,
            eligible_count=eligible,
            ineligible_count=total - eligible,
            by_regime={
                "politics": {"total": 2, "eligible": 0},
                "sports": {"total": 2, "eligible": 0},
                "new_market": {"total": 1, "eligible": 0},
                "unknown": {"total": 0, "eligible": 0},
            },
            mixed_regime_eligible=False,
            gate2_eligible_tapes=[],
            generated_at="2026-04-14T00:00:00+00:00",
            corpus_note="BLOCKED",
            regime_coverage={
                "covered_regimes": [],
                "missing_regimes": ["politics", "sports", "new_market"],
            },
        )

    def test_reject_code_distribution_printed(self):
        records = [
            _make_record(evidence={"ticks_with_depth_ok": 5, "ticks_with_edge_ok": 0, "ticks_with_depth_and_edge": 0}),
            _make_record(evidence={"ticks_with_depth_ok": 0, "ticks_with_edge_ok": 3, "ticks_with_depth_and_edge": 0}),
            _make_record(reject_reason="no events.jsonl found in tape directory"),
        ]
        for r in records:
            if not r.diagnostics:
                r.diagnostics = enrich_tape_diagnostics(r)
        summary = self._make_summary(total=3)
        output = self._capture_breakdown(records, summary)
        assert "DEPTH_ONLY" in output
        assert "EDGE_ONLY" in output
        assert "NO_EVENTS" in output

    def test_confidence_tier_distribution_printed(self):
        records = [
            _make_record(recorded_by="watch-arb-candidates", evidence={"events_scanned": 100, "ticks_with_both_bbo": 50}),
            _make_record(recorded_by="prepare-gate2", evidence={"events_scanned": 30, "ticks_with_both_bbo": 0}),
        ]
        for r in records:
            if not r.diagnostics:
                r.diagnostics = enrich_tape_diagnostics(r)
        summary = self._make_summary(total=2)
        output = self._capture_breakdown(records, summary)
        assert "GOLD" in output
        assert "SILV" in output or "SILVER" in output

    def test_silver_warning_when_blocked(self):
        records = [
            _make_record(recorded_by="prepare-gate2", evidence={"events_scanned": 30, "ticks_with_both_bbo": 0}),
        ]
        for r in records:
            r.diagnostics = enrich_tape_diagnostics(r)
        summary = self._make_summary(eligible=0, total=1)
        output = self._capture_breakdown(records, summary)
        assert "Silver" in output or "SILVER" in output or "structurally unusable" in output

    def test_no_silver_warning_when_eligible_exists(self):
        records = [
            _make_record(
                recorded_by="watch-arb-candidates",
                eligible=True,
                evidence={
                    "events_scanned": 100,
                    "ticks_with_both_bbo": 50,
                    "ticks_with_depth_and_edge": 5,
                    "ticks_with_depth_ok": 10,
                    "ticks_with_edge_ok": 8,
                },
            ),
        ]
        for r in records:
            r.diagnostics = enrich_tape_diagnostics(r)
        summary = self._make_summary(eligible=1, total=1)
        output = self._capture_breakdown(records, summary)
        assert "structurally unusable" not in output

    def test_next_action_capture_gold(self):
        records = [_make_record(reject_reason="no events.jsonl found in tape directory")]
        for r in records:
            r.diagnostics = enrich_tape_diagnostics(r)
        summary = self._make_summary(eligible=0, total=1)
        output = self._capture_breakdown(records, summary)
        assert "NEXT" in output or "scan-gate2-candidates" in output
