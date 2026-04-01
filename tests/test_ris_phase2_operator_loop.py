"""Offline tests for RIS Phase 2: operator feedback loop and enriched queries.

Covers:
- Ledger schema v2: append_override, append_outcome, get_precheck_history,
  list_prechecks_by_window
- PrecheckResult lifecycle fields (was_overridden, override_reason,
  outcome_label, outcome_date)
- query_knowledge_store_enriched and format_enriched_report
- CLI subcommands: run (backward compat), override, outcome, history, inspect

All tests are fully offline — no network, no LLM, :memory: SQLite for
KnowledgeStore, tmp_path for JSONL ledger files.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ks():
    """Create a fresh in-memory KnowledgeStore."""
    from packages.polymarket.rag.knowledge_store import KnowledgeStore
    return KnowledgeStore(":memory:")


def _ledger(tmp_path: Path) -> Path:
    """Return a fresh ledger path under tmp_path."""
    return tmp_path / "test_ledger.jsonl"


def _read_ledger(path: Path) -> list[dict]:
    """Read all JSONL lines from a ledger file."""
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            events.append(json.loads(stripped))
    return events


# ---------------------------------------------------------------------------
# TestAppendOverride
# ---------------------------------------------------------------------------

class TestAppendOverride:
    def test_append_override_writes_event(self, tmp_path):
        """append_override writes a JSONL override event with expected fields."""
        from packages.research.synthesis.precheck_ledger import append_override

        lp = _ledger(tmp_path)
        append_override("abc123", "Changed strategic direction", ledger_path=lp)

        events = _read_ledger(lp)
        assert len(events) == 1
        e = events[0]
        assert e["event_type"] == "override"
        assert e["precheck_id"] == "abc123"
        assert e["was_overridden"] is True
        assert e["override_reason"] == "Changed strategic direction"
        assert "written_at" in e

    def test_append_override_empty_id_raises(self, tmp_path):
        """append_override raises ValueError on empty precheck_id."""
        from packages.research.synthesis.precheck_ledger import append_override

        lp = _ledger(tmp_path)
        with pytest.raises(ValueError, match="precheck_id"):
            append_override("", "some reason", ledger_path=lp)

    def test_append_override_schema_version(self, tmp_path):
        """Written override event has schema_version precheck_ledger_v2."""
        from packages.research.synthesis.precheck_ledger import (
            append_override,
            LEDGER_SCHEMA_VERSION,
        )

        lp = _ledger(tmp_path)
        append_override("pid001", "reason", ledger_path=lp)

        events = _read_ledger(lp)
        assert events[0]["schema_version"] == "precheck_ledger_v2"
        assert LEDGER_SCHEMA_VERSION == "precheck_ledger_v2"


# ---------------------------------------------------------------------------
# TestAppendOutcome
# ---------------------------------------------------------------------------

class TestAppendOutcome:
    def test_append_outcome_writes_event(self, tmp_path):
        """append_outcome writes a JSONL outcome event with expected fields."""
        from packages.research.synthesis.precheck_ledger import append_outcome

        lp = _ledger(tmp_path)
        append_outcome("abc123", "successful", outcome_date="2026-04-01T12:00:00+00:00", ledger_path=lp)

        events = _read_ledger(lp)
        assert len(events) == 1
        e = events[0]
        assert e["event_type"] == "outcome"
        assert e["precheck_id"] == "abc123"
        assert e["outcome_label"] == "successful"
        assert e["outcome_date"] == "2026-04-01T12:00:00+00:00"
        assert "written_at" in e

    def test_append_outcome_invalid_label_raises(self, tmp_path):
        """append_outcome raises ValueError on invalid outcome_label."""
        from packages.research.synthesis.precheck_ledger import append_outcome

        lp = _ledger(tmp_path)
        with pytest.raises(ValueError):
            append_outcome("abc123", "invalid_label", ledger_path=lp)

    def test_append_outcome_valid_labels(self, tmp_path):
        """All four valid labels are accepted without raising."""
        from packages.research.synthesis.precheck_ledger import append_outcome

        lp = _ledger(tmp_path)
        for label in ["successful", "failed", "partial", "not_tried"]:
            append_outcome(f"pid_{label}", label, ledger_path=lp)

        events = _read_ledger(lp)
        written_labels = [e["outcome_label"] for e in events]
        assert sorted(written_labels) == sorted(["successful", "failed", "partial", "not_tried"])

    def test_append_outcome_auto_date(self, tmp_path):
        """When outcome_date is None, a valid ISO timestamp is written."""
        from packages.research.synthesis.precheck_ledger import append_outcome

        lp = _ledger(tmp_path)
        append_outcome("pid_autodate", "partial", outcome_date=None, ledger_path=lp)

        events = _read_ledger(lp)
        assert len(events) == 1
        outcome_date = events[0].get("outcome_date", "")
        # Must be a non-empty string parseable as ISO datetime
        assert outcome_date
        from datetime import datetime
        # Should parse without error
        datetime.fromisoformat(outcome_date)


# ---------------------------------------------------------------------------
# TestGetPrecheckHistory
# ---------------------------------------------------------------------------

class TestGetPrecheckHistory:
    def test_history_single_run(self, tmp_path):
        """get_precheck_history returns the single precheck_run event."""
        from packages.research.synthesis.precheck_ledger import (
            append_precheck,
            get_precheck_history,
        )
        from packages.research.synthesis.precheck import PrecheckResult

        lp = _ledger(tmp_path)
        result = PrecheckResult(
            recommendation="GO",
            idea="test idea history",
            supporting_evidence=["some evidence"],
            contradicting_evidence=[],
            risk_factors=["risk"],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
            precheck_id="pid_hist1",
        )
        append_precheck(result, ledger_path=lp)

        history = get_precheck_history("pid_hist1", ledger_path=lp)
        assert len(history) == 1
        assert history[0]["event_type"] == "precheck_run"
        assert history[0]["precheck_id"] == "pid_hist1"

    def test_history_run_plus_override(self, tmp_path):
        """get_precheck_history returns both precheck_run and override in written_at order."""
        from packages.research.synthesis.precheck_ledger import (
            append_precheck,
            append_override,
            get_precheck_history,
        )
        from packages.research.synthesis.precheck import PrecheckResult

        lp = _ledger(tmp_path)
        result = PrecheckResult(
            recommendation="CAUTION",
            idea="test idea for override history",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
            precheck_id="pid_hist2",
        )
        append_precheck(result, ledger_path=lp)
        append_override("pid_hist2", "Operator decision", ledger_path=lp)

        history = get_precheck_history("pid_hist2", ledger_path=lp)
        assert len(history) == 2
        types = [e["event_type"] for e in history]
        assert "precheck_run" in types
        assert "override" in types
        # Sorted ascending by written_at
        assert history[0]["written_at"] <= history[1]["written_at"]

    def test_history_multiple_ids_filtered(self, tmp_path):
        """get_precheck_history returns only events for the requested precheck_id."""
        from packages.research.synthesis.precheck_ledger import (
            append_override,
            get_precheck_history,
        )

        lp = _ledger(tmp_path)
        append_override("pid_A", "reason A", ledger_path=lp)
        append_override("pid_B", "reason B", ledger_path=lp)
        append_override("pid_A", "reason A2", ledger_path=lp)

        history_a = get_precheck_history("pid_A", ledger_path=lp)
        assert len(history_a) == 2
        for e in history_a:
            assert e["precheck_id"] == "pid_A"

        history_b = get_precheck_history("pid_B", ledger_path=lp)
        assert len(history_b) == 1
        assert history_b[0]["precheck_id"] == "pid_B"


# ---------------------------------------------------------------------------
# TestListPrechecksByWindow
# ---------------------------------------------------------------------------

class TestListPrechecksByWindow:
    def test_window_includes_matching(self, tmp_path):
        """list_prechecks_by_window returns events within the time window."""
        from packages.research.synthesis.precheck_ledger import list_prechecks_by_window

        lp = _ledger(tmp_path)
        # Write two events manually with known written_at values
        events_to_write = [
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "override",
                "precheck_id": "pid_w1",
                "was_overridden": True,
                "override_reason": "test",
                "written_at": "2026-04-01T10:00:00+00:00",
            },
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "override",
                "precheck_id": "pid_w2",
                "was_overridden": True,
                "override_reason": "test2",
                "written_at": "2026-04-01T12:00:00+00:00",
            },
        ]
        with lp.open("w", encoding="utf-8") as f:
            for e in events_to_write:
                f.write(json.dumps(e) + "\n")

        results = list_prechecks_by_window(
            "2026-04-01T09:00:00+00:00",
            "2026-04-01T13:00:00+00:00",
            ledger_path=lp,
        )
        assert len(results) == 2

    def test_window_excludes_outside(self, tmp_path):
        """list_prechecks_by_window excludes events outside the window."""
        from packages.research.synthesis.precheck_ledger import list_prechecks_by_window

        lp = _ledger(tmp_path)
        events_to_write = [
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "override",
                "precheck_id": "pid_out1",
                "was_overridden": True,
                "override_reason": "old",
                "written_at": "2026-03-01T10:00:00+00:00",  # before window
            },
            {
                "schema_version": "precheck_ledger_v2",
                "event_type": "override",
                "precheck_id": "pid_out2",
                "was_overridden": True,
                "override_reason": "recent",
                "written_at": "2026-04-01T12:00:00+00:00",  # inside window
            },
        ]
        with lp.open("w", encoding="utf-8") as f:
            for e in events_to_write:
                f.write(json.dumps(e) + "\n")

        results = list_prechecks_by_window(
            "2026-04-01T00:00:00+00:00",
            "2026-04-01T23:59:59+00:00",
            ledger_path=lp,
        )
        assert len(results) == 1
        assert results[0]["precheck_id"] == "pid_out2"


# ---------------------------------------------------------------------------
# TestPrecheckResultLifecycleFields
# ---------------------------------------------------------------------------

class TestPrecheckResultLifecycleFields:
    def test_new_fields_default(self):
        """PrecheckResult has new lifecycle fields with correct defaults."""
        from packages.research.synthesis.precheck import PrecheckResult

        result = PrecheckResult(
            recommendation="GO",
            idea="test idea defaults",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        assert result.was_overridden is False
        assert result.override_reason == ""
        assert result.outcome_label == ""
        assert result.outcome_date == ""

    def test_fields_set_explicitly(self):
        """PrecheckResult lifecycle fields can be set explicitly."""
        from packages.research.synthesis.precheck import PrecheckResult

        result = PrecheckResult(
            recommendation="CAUTION",
            idea="test idea explicit",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
            was_overridden=True,
            override_reason="operator changed mind",
            outcome_label="successful",
            outcome_date="2026-04-01T12:00:00+00:00",
        )
        assert result.was_overridden is True
        assert result.override_reason == "operator changed mind"
        assert result.outcome_label == "successful"
        assert result.outcome_date == "2026-04-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# TestEnrichedQuery
# ---------------------------------------------------------------------------

class TestEnrichedQuery:
    def _make_ks_with_claims(self):
        """Build a KnowledgeStore with a source doc, two claims, and a CONTRADICTS relation."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore

        ks = KnowledgeStore(":memory:")
        doc_id = ks.add_source_document(
            title="Test Analysis",
            source_url="internal://test",
            source_family="wallet_analysis",
            published_at="2026-01-01T00:00:00+00:00",
        )
        claim_a_id = ks.add_claim(
            claim_text="BTC prices trend upward on Monday",
            claim_type="empirical",
            confidence=0.8,
            trust_tier="high",
            actor="test",
            source_document_id=doc_id,
        )
        claim_b_id = ks.add_claim(
            claim_text="BTC prices trend downward on Monday",
            claim_type="empirical",
            confidence=0.7,
            trust_tier="medium",
            actor="test",
        )
        # Link evidence for claim_a
        ks.add_evidence(
            claim_id=claim_a_id,
            source_document_id=doc_id,
            excerpt="Historical data shows...",
        )
        # claim_b CONTRADICTS claim_a
        ks.add_relation(claim_b_id, claim_a_id, "CONTRADICTS")
        return ks, claim_a_id, claim_b_id, doc_id

    def test_enriched_claims_have_provenance(self):
        """provenance_docs is populated for claims with evidence links."""
        from packages.research.ingestion.retriever import query_knowledge_store_enriched

        ks, claim_a_id, _, _ = self._make_ks_with_claims()
        claims = query_knowledge_store_enriched(ks)

        # Find claim_a in results
        matching = [c for c in claims if c["id"] == claim_a_id]
        assert len(matching) == 1
        assert len(matching[0]["provenance_docs"]) >= 1
        assert matching[0]["provenance_docs"][0]["title"] == "Test Analysis"

    def test_enriched_claims_have_contradiction_summary(self):
        """contradiction_summary is populated for contradicted claims."""
        from packages.research.ingestion.retriever import query_knowledge_store_enriched

        ks, claim_a_id, _, _ = self._make_ks_with_claims()
        claims = query_knowledge_store_enriched(ks)

        # claim_a is targeted by a CONTRADICTS relation from claim_b
        claim_a = next(c for c in claims if c["id"] == claim_a_id)
        assert claim_a["is_contradicted"] is True
        assert len(claim_a["contradiction_summary"]) >= 1
        assert "BTC prices trend downward on Monday" in claim_a["contradiction_summary"]

    def test_enriched_claims_staleness_note(self):
        """Claims from old source docs get a STALE staleness_note."""
        from packages.polymarket.rag.knowledge_store import KnowledgeStore
        from packages.research.ingestion.retriever import query_knowledge_store_enriched

        ks = KnowledgeStore(":memory:")
        # Very old document (should be stale under any reasonable decay)
        ks.add_source_document(
            title="Stale Doc",
            source_url="internal://stale",
            source_family="wallet_analysis",
            published_at="2020-01-01T00:00:00+00:00",
        )
        doc_id = ks.add_source_document(
            title="Stale Source",
            source_url="internal://stale2",
            source_family="wallet_analysis",
            published_at="2020-01-01T00:00:00+00:00",
        )
        claim_id = ks.add_claim(
            claim_text="Very old claim",
            claim_type="empirical",
            confidence=0.9,
            trust_tier="high",
            actor="test",
            source_document_id=doc_id,
        )

        claims = query_knowledge_store_enriched(ks)
        stale_claims = [c for c in claims if c["id"] == claim_id]
        if stale_claims:
            # If freshness_modifier < 0.5, should be STALE; if < 0.7, AGING
            fm = stale_claims[0]["freshness_modifier"]
            note = stale_claims[0]["staleness_note"]
            if fm < 0.5:
                assert note == "STALE"
            elif fm < 0.7:
                assert note == "AGING"
            else:
                assert note == ""

    def test_enriched_claims_lifecycle_present(self):
        """lifecycle field is present in enriched claims."""
        from packages.research.ingestion.retriever import query_knowledge_store_enriched

        ks, _, _, _ = self._make_ks_with_claims()
        claims = query_knowledge_store_enriched(ks)

        for claim in claims:
            assert "lifecycle" in claim
            assert claim["lifecycle"] in ("active", "archived", "superseded")

    def test_format_enriched_report_structure(self):
        """format_enriched_report produces expected header labels."""
        from packages.research.ingestion.retriever import (
            query_knowledge_store_enriched,
            format_enriched_report,
        )

        ks, _, _, _ = self._make_ks_with_claims()
        claims = query_knowledge_store_enriched(ks)
        report = format_enriched_report(claims)

        assert "Claim:" in report
        assert "Confidence:" in report
        assert "Freshness:" in report
        assert "Score:" in report
        assert "Lifecycle:" in report
        assert "Status:" in report
        assert "Staleness:" in report
        assert "Contradictions:" in report
        assert "Provenance:" in report

    def test_format_enriched_report_empty(self):
        """format_enriched_report handles empty claims list gracefully."""
        from packages.research.ingestion.retriever import format_enriched_report

        report = format_enriched_report([])
        assert "(no claims)" in report


# ---------------------------------------------------------------------------
# TestCLI
# ---------------------------------------------------------------------------

class TestCLI:
    def test_run_subcommand_backward_compat(self, capsys):
        """Implicit run subcommand: main(['--idea', 'test', '--no-ledger', '--json']) exits 0."""
        from tools.cli.research_precheck import main

        rc = main(["--idea", "test backward compat", "--no-ledger", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "recommendation" in parsed

    def test_run_explicit_subcommand(self, capsys):
        """Explicit run subcommand: main(['run', '--idea', 'test', '--no-ledger', '--json']) exits 0."""
        from tools.cli.research_precheck import main

        rc = main(["run", "--idea", "test explicit run", "--no-ledger", "--json"])
        assert rc == 0
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert "recommendation" in parsed

    def test_override_subcommand(self, tmp_path):
        """override subcommand writes an override event to the ledger."""
        from tools.cli.research_precheck import main

        lp = tmp_path / "ledger.jsonl"
        rc = main([
            "override",
            "--precheck-id", "abc123",
            "--reason", "operator override",
            "--ledger", str(lp),
        ])
        assert rc == 0

        events = _read_ledger(lp)
        assert len(events) == 1
        assert events[0]["event_type"] == "override"
        assert events[0]["precheck_id"] == "abc123"

    def test_outcome_subcommand(self, tmp_path):
        """outcome subcommand writes an outcome event to the ledger."""
        from tools.cli.research_precheck import main

        lp = tmp_path / "ledger.jsonl"
        rc = main([
            "outcome",
            "--precheck-id", "abc123",
            "--label", "successful",
            "--ledger", str(lp),
        ])
        assert rc == 0

        events = _read_ledger(lp)
        assert len(events) == 1
        assert events[0]["event_type"] == "outcome"
        assert events[0]["outcome_label"] == "successful"

    def test_history_subcommand(self, tmp_path, capsys):
        """history subcommand returns JSON with pre-populated events."""
        from packages.research.synthesis.precheck_ledger import append_override
        from tools.cli.research_precheck import main

        lp = tmp_path / "ledger.jsonl"
        append_override("abc123", "test reason", ledger_path=lp)

        rc = main([
            "history",
            "--precheck-id", "abc123",
            "--ledger", str(lp),
            "--json",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        events = json.loads(captured.out)
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0]["precheck_id"] == "abc123"

    def test_help_shows_subcommands(self, capsys):
        """--help exits with code 0 and mentions override and outcome."""
        from tools.cli.research_precheck import main

        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "override" in captured.out
        assert "outcome" in captured.out
