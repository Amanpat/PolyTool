"""WP1-B follow-up: prompt floor drift fix tests.

Verifies that build_scoring_prompt() derives floor text from live config/env
so the model-facing prompt stays aligned with gate enforcement under overrides.

All tests are fully offline (no network, no Ollama, no file I/O beyond the live config).
"""

from __future__ import annotations

import pytest


def _make_doc():
    from packages.research.evaluation.types import EvalDocument
    return EvalDocument(
        doc_id="test_doc",
        title="Test Document",
        author="Test Author",
        source_type="manual",
        source_url="https://example.com",
        source_publish_date=None,
        body="Test body content.",
    )


def _make_scoring(relevance=3, novelty=3, actionability=3, credibility=3, priority_tier="priority_3"):
    from packages.research.evaluation.types import ScoringResult
    from packages.research.evaluation.scoring import _compute_composite
    composite_score = _compute_composite(relevance, novelty, actionability, credibility)
    return ScoringResult(
        relevance=relevance,
        novelty=novelty,
        actionability=actionability,
        credibility=credibility,
        total=relevance + novelty + actionability + credibility,
        composite_score=composite_score,
        priority_tier=priority_tier,
        reject_reason=None,
        epistemic_type="EMPIRICAL",
        summary="Test.",
        key_findings=["Finding 1"],
        eval_model="test_model",
    )


# ---------------------------------------------------------------------------
# Prompt floor text reflects live config
# ---------------------------------------------------------------------------

class TestPromptFloorTextMatchesConfig:
    def test_default_floors_in_prompt(self):
        """Default config: prompt floor text contains all four dims at value 2."""
        from packages.research.evaluation.scoring import build_scoring_prompt
        prompt = build_scoring_prompt(_make_doc())
        assert "relevance >= 2" in prompt
        assert "novelty >= 2" in prompt
        assert "actionability >= 2" in prompt
        assert "credibility >= 2" in prompt

    def test_novelty_override_reflected_in_prompt(self, monkeypatch):
        """RIS_EVAL_NOVELTY_FLOOR=3 -> prompt shows novelty >= 3, not novelty >= 2."""
        from packages.research.evaluation.config import reset_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        monkeypatch.setenv("RIS_EVAL_NOVELTY_FLOOR", "3")
        reset_eval_config()
        try:
            prompt = build_scoring_prompt(_make_doc())
            assert "novelty >= 3" in prompt
            assert "novelty >= 2" not in prompt
        finally:
            reset_eval_config()

    def test_actionability_override_reflected_in_prompt(self, monkeypatch):
        """RIS_EVAL_ACTIONABILITY_FLOOR=4 -> prompt shows actionability >= 4, not actionability >= 2."""
        from packages.research.evaluation.config import reset_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        monkeypatch.setenv("RIS_EVAL_ACTIONABILITY_FLOOR", "4")
        reset_eval_config()
        try:
            prompt = build_scoring_prompt(_make_doc())
            assert "actionability >= 4" in prompt
            assert "actionability >= 2" not in prompt
        finally:
            reset_eval_config()

    def test_both_overrides_reflected_simultaneously(self, monkeypatch):
        """Both env-var floor overrides appear in prompt at the same time."""
        from packages.research.evaluation.config import reset_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        monkeypatch.setenv("RIS_EVAL_NOVELTY_FLOOR", "3")
        monkeypatch.setenv("RIS_EVAL_ACTIONABILITY_FLOOR", "3")
        reset_eval_config()
        try:
            prompt = build_scoring_prompt(_make_doc())
            assert "novelty >= 3" in prompt
            assert "actionability >= 3" in prompt
            assert "novelty >= 2" not in prompt
            assert "actionability >= 2" not in prompt
        finally:
            reset_eval_config()


# ---------------------------------------------------------------------------
# Prompt floor text and gate behavior agree for the same config state
# ---------------------------------------------------------------------------

class TestPromptGateAlignment:
    def test_default_floors_prompt_matches_config(self):
        """Default config: every cfg.floors value appears in the prompt."""
        from packages.research.evaluation.config import load_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        cfg = load_eval_config()
        prompt = build_scoring_prompt(_make_doc())
        for dim, val in cfg.floors.items():
            assert f"{dim} >= {val}" in prompt, f"Expected '{dim} >= {val}' in prompt"

    def test_novelty_override_prompt_and_gate_agree(self, monkeypatch):
        """novelty floor=3: prompt reflects >= 3 and gate rejects novelty=2."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        monkeypatch.setenv("RIS_EVAL_NOVELTY_FLOOR", "3")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            prompt = build_scoring_prompt(_make_doc())
            assert cfg.floors["novelty"] == 3
            assert f"novelty >= {cfg.floors['novelty']}" in prompt
            r = _make_scoring(relevance=4, novelty=2, actionability=4, credibility=4,
                              priority_tier="priority_3")
            assert r.gate == "REJECT"
        finally:
            reset_eval_config()

    def test_actionability_override_prompt_and_gate_agree(self, monkeypatch):
        """actionability floor=3: prompt reflects >= 3 and gate rejects actionability=2."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        monkeypatch.setenv("RIS_EVAL_ACTIONABILITY_FLOOR", "3")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            prompt = build_scoring_prompt(_make_doc())
            assert cfg.floors["actionability"] == 3
            assert f"actionability >= {cfg.floors['actionability']}" in prompt
            r = _make_scoring(relevance=4, novelty=4, actionability=2, credibility=4,
                              priority_tier="priority_3")
            assert r.gate == "REJECT"
        finally:
            reset_eval_config()

    def test_unoverridden_dims_still_match_defaults(self, monkeypatch):
        """When only novelty is overridden, relevance/credibility still show default values."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        from packages.research.evaluation.scoring import build_scoring_prompt
        monkeypatch.setenv("RIS_EVAL_NOVELTY_FLOOR", "3")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            prompt = build_scoring_prompt(_make_doc())
            assert "relevance >= 2" in prompt
            assert "credibility >= 2" in prompt
            assert f"novelty >= {cfg.floors['novelty']}" in prompt
        finally:
            reset_eval_config()
