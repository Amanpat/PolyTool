"""Offline tests for RIS v1 precheck runner, ledger, and CLI.

All tests are fully offline — no network, no LLM, no Chroma.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LONG_ENOUGH_IDEA = (
    "Will crypto pair directional momentum on 5m BTC markets remain profitable "
    "through 2026 given the Coinbase reference feed used for Polymarket settlement?"
)


# ---------------------------------------------------------------------------
# PrecheckResult dataclass
# ---------------------------------------------------------------------------

class TestPrecheckResult:
    def test_dataclass_fields_and_defaults(self):
        from packages.research.synthesis.precheck import PrecheckResult
        r = PrecheckResult(
            recommendation="CAUTION",
            idea="test idea",
            supporting_evidence=["evidence 1"],
            contradicting_evidence=[],
            risk_factors=["risk 1"],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        assert r.recommendation == "CAUTION"
        assert r.stale_warning is False  # default
        assert r.raw_response == ""     # default
        assert r.idea == "test idea"

    def test_all_recommendation_values(self):
        from packages.research.synthesis.precheck import PrecheckResult
        for rec in ("GO", "CAUTION", "STOP"):
            r = PrecheckResult(
                recommendation=rec,
                idea="test",
                supporting_evidence=[],
                contradicting_evidence=[],
                risk_factors=[],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used="manual",
            )
            assert r.recommendation == rec


# ---------------------------------------------------------------------------
# build_precheck_prompt
# ---------------------------------------------------------------------------

class TestBuildPrecheckPrompt:
    def test_includes_contradiction_detection_language(self):
        from packages.research.synthesis.precheck import build_precheck_prompt
        prompt = build_precheck_prompt("test idea about crypto")
        # Must include contradiction detection instructions
        assert "contradict" in prompt.lower() or "contradicting" in prompt.lower()

    def test_includes_risk_factor_instruction(self):
        from packages.research.synthesis.precheck import build_precheck_prompt
        prompt = build_precheck_prompt("test idea")
        assert "risk" in prompt.lower()

    def test_includes_idea_text(self):
        from packages.research.synthesis.precheck import build_precheck_prompt
        idea = "unique xyz idea phrase abc123"
        prompt = build_precheck_prompt(idea)
        assert "abc123" in prompt

    def test_includes_go_caution_stop_guidance(self):
        from packages.research.synthesis.precheck import build_precheck_prompt
        prompt = build_precheck_prompt("test idea")
        upper = prompt.upper()
        assert "GO" in upper or "CAUTION" in upper or "STOP" in upper


# ---------------------------------------------------------------------------
# parse_precheck_response
# ---------------------------------------------------------------------------

class TestParsePrecheckResponse:
    def test_valid_json_parses_correctly(self):
        from packages.research.synthesis.precheck import parse_precheck_response
        data = {
            "recommendation": "GO",
            "supporting_evidence": ["Strong momentum signal"],
            "contradicting_evidence": ["Possible oracle mismatch"],
            "risk_factors": ["Market liquidity risk"],
        }
        result = parse_precheck_response(json.dumps(data), "test idea", "manual")
        assert result.recommendation == "GO"
        assert "Strong momentum signal" in result.supporting_evidence
        assert "Possible oracle mismatch" in result.contradicting_evidence
        assert "Market liquidity risk" in result.risk_factors
        assert result.idea == "test idea"
        assert result.provider_used == "manual"

    def test_invalid_json_returns_caution_default(self):
        from packages.research.synthesis.precheck import parse_precheck_response
        result = parse_precheck_response("not valid json !@#$", "test idea", "manual")
        assert result.recommendation == "CAUTION"
        assert result.idea == "test idea"
        # Should have a fallback manual message
        assert len(result.supporting_evidence) > 0 or len(result.risk_factors) > 0

    def test_missing_recommendation_returns_caution(self):
        from packages.research.synthesis.precheck import parse_precheck_response
        data = {
            "supporting_evidence": ["Some evidence"],
            "risk_factors": ["Some risk"],
        }
        result = parse_precheck_response(json.dumps(data), "test idea", "manual")
        assert result.recommendation == "CAUTION"


# ---------------------------------------------------------------------------
# run_precheck with ManualProvider
# ---------------------------------------------------------------------------

class TestRunPrecheck:
    def test_returns_precheck_result(self, tmp_path):
        from packages.research.synthesis.precheck import run_precheck
        result = run_precheck(
            LONG_ENOUGH_IDEA,
            provider_name="manual",
            ledger_path=None,  # skip ledger
        )
        assert result.recommendation in ("GO", "CAUTION", "STOP")
        assert result.idea == LONG_ENOUGH_IDEA

    def test_manual_provider_returns_caution_with_fallback_message(self, tmp_path):
        from packages.research.synthesis.precheck import run_precheck
        result = run_precheck(
            "Test precheck idea",
            provider_name="manual",
            ledger_path=None,
        )
        # ManualProvider output is not valid precheck JSON, so fallback applies
        assert result.recommendation == "CAUTION"
        assert any("manual" in e.lower() or "no automated" in e.lower()
                   for e in result.risk_factors + result.supporting_evidence)

    def test_run_precheck_with_ledger_path_none_skips_append(self, tmp_path):
        from packages.research.synthesis.precheck import run_precheck
        ledger = tmp_path / "test_ledger.jsonl"
        run_precheck("test idea", provider_name="manual", ledger_path=None)
        # ledger_path=None means no file should be created
        assert not ledger.exists()

    def test_run_precheck_appends_to_ledger(self, tmp_path):
        from packages.research.synthesis.precheck import run_precheck
        ledger = tmp_path / "precheck_ledger.jsonl"
        run_precheck("test idea", provider_name="manual", ledger_path=ledger)
        assert ledger.exists()
        lines = [l for l in ledger.read_text().splitlines() if l.strip()]
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# Precheck Ledger
# ---------------------------------------------------------------------------

class TestPrecheckLedger:
    def test_append_precheck_writes_jsonl(self, tmp_path):
        from packages.research.synthesis.precheck import PrecheckResult
        from packages.research.synthesis.precheck_ledger import append_precheck
        ledger = tmp_path / "ledger.jsonl"
        r = PrecheckResult(
            recommendation="CAUTION",
            idea="test",
            supporting_evidence=["e1"],
            contradicting_evidence=[],
            risk_factors=["r1"],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        append_precheck(r, ledger_path=ledger)
        assert ledger.exists()
        data = json.loads(ledger.read_text().strip())
        assert data["recommendation"] == "CAUTION"
        assert data["idea"] == "test"

    def test_list_prechecks_reads_back_entries(self, tmp_path):
        from packages.research.synthesis.precheck import PrecheckResult
        from packages.research.synthesis.precheck_ledger import append_precheck, list_prechecks
        ledger = tmp_path / "ledger.jsonl"
        for i in range(3):
            r = PrecheckResult(
                recommendation="GO",
                idea=f"idea {i}",
                supporting_evidence=[],
                contradicting_evidence=[],
                risk_factors=[],
                timestamp="2026-04-01T00:00:00+00:00",
                provider_used="manual",
            )
            append_precheck(r, ledger_path=ledger)
        entries = list_prechecks(ledger_path=ledger)
        assert len(entries) == 3
        assert entries[0]["idea"] == "idea 0"

    def test_list_prechecks_nonexistent_returns_empty(self, tmp_path):
        from packages.research.synthesis.precheck_ledger import list_prechecks
        missing = tmp_path / "missing.jsonl"
        result = list_prechecks(ledger_path=missing)
        assert result == []

    def test_append_precheck_creates_parent_dirs(self, tmp_path):
        from packages.research.synthesis.precheck import PrecheckResult
        from packages.research.synthesis.precheck_ledger import append_precheck
        ledger = tmp_path / "nested" / "deep" / "ledger.jsonl"
        r = PrecheckResult(
            recommendation="STOP",
            idea="nested test",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        append_precheck(r, ledger_path=ledger)
        assert ledger.exists()

    def test_append_includes_schema_version(self, tmp_path):
        from packages.research.synthesis.precheck import PrecheckResult
        from packages.research.synthesis.precheck_ledger import append_precheck
        ledger = tmp_path / "ledger.jsonl"
        r = PrecheckResult(
            recommendation="GO",
            idea="schema test",
            supporting_evidence=[],
            contradicting_evidence=[],
            risk_factors=[],
            timestamp="2026-04-01T00:00:00+00:00",
            provider_used="manual",
        )
        append_precheck(r, ledger_path=ledger)
        data = json.loads(ledger.read_text().strip())
        assert "schema_version" in data
        assert "event_type" in data


# ---------------------------------------------------------------------------
# CLI: research_precheck
# ---------------------------------------------------------------------------

class TestResearchPrecheckCLI:
    def test_main_returns_0_with_no_ledger(self, tmp_path, monkeypatch):
        from tools.cli.research_precheck import main
        # Prevent any ledger writes
        exit_code = main(["--idea", "Test precheck idea for CLI", "--no-ledger"])
        assert exit_code == 0

    def test_main_returns_1_without_idea(self):
        from tools.cli.research_precheck import main
        # With subcommand refactor, main([]) prints help and returns 1
        # (no SystemExit; argparse subparsers don't error on missing subcommand).
        rc = main([])
        assert rc == 1

    def test_main_writes_to_custom_ledger(self, tmp_path):
        from tools.cli.research_precheck import main
        ledger = tmp_path / "test_ledger.jsonl"
        exit_code = main([
            "--idea", "CLI ledger write test idea",
            "--ledger", str(ledger),
        ])
        assert exit_code == 0
        assert ledger.exists()


# ---------------------------------------------------------------------------
# CLI: research_eval
# ---------------------------------------------------------------------------

class TestResearchEvalCLI:
    def test_main_returns_0_with_inline_body(self):
        from tools.cli.research_eval import main
        exit_code = main([
            "--title", "Test Doc",
            "--body", "This is a sufficiently long test body for evaluation gate testing. "
                      "It contains enough text to pass the hard stop minimum length check.",
            "--source-type", "manual",
        ])
        assert exit_code == 0

    def test_main_returns_1_with_no_input(self):
        from tools.cli.research_eval import main
        result = main([])
        assert result == 1

    def test_main_reads_from_file(self, tmp_path):
        from tools.cli.research_eval import main
        doc_file = tmp_path / "test_doc.md"
        doc_file.write_text(
            "# Test Document\n\n"
            "This is a test document body with sufficient content for evaluation. "
            "It contains relevant information about prediction market strategies and "
            "market making approaches that should pass the hard stop length check."
        )
        exit_code = main(["--file", str(doc_file)])
        assert exit_code == 0

    def test_main_json_output_mode(self):
        from tools.cli.research_eval import main
        exit_code = main([
            "--title", "T",
            "--body", "This is a sufficiently long test body for evaluation gate testing purposes. "
                      "It passes the 50-character minimum length requirement easily.",
            "--source-type", "arxiv",
            "--json",
        ])
        assert exit_code == 0
