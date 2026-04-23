"""WP1-B targeted tests: four-dimension floor contract.

Covers:
- Default config exposes all four floors (relevance, novelty, actionability, credibility)
- novelty below floor => REJECT for non-waived tiers
- actionability below floor => REJECT for non-waived tiers
- A doc meeting all four floors is not blocked for floor reasons
- Env-var overrides for RIS_EVAL_NOVELTY_FLOOR and RIS_EVAL_ACTIONABILITY_FLOOR
- Floor waive (priority_1) still exempts all four dimensions

All tests are fully offline (no network, no Ollama, no file I/O beyond the live config file).
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scoring(
    relevance=3, novelty=3, actionability=3, credibility=3,
    priority_tier="priority_3",
    reject_reason=None,
    composite_score=None,
):
    from packages.research.evaluation.types import ScoringResult
    from packages.research.evaluation.scoring import _compute_composite
    if composite_score is None:
        composite_score = _compute_composite(relevance, novelty, actionability, credibility)
    return ScoringResult(
        relevance=relevance,
        novelty=novelty,
        actionability=actionability,
        credibility=credibility,
        total=relevance + novelty + actionability + credibility,
        composite_score=composite_score,
        priority_tier=priority_tier,
        reject_reason=reject_reason,
        epistemic_type="EMPIRICAL",
        summary="Test summary.",
        key_findings=["Finding 1"],
        eval_model="test_model",
    )


# ---------------------------------------------------------------------------
# Config contract: four dimensions present in floors
# ---------------------------------------------------------------------------

class TestFourDimensionFloorContract:
    def test_all_four_dims_present_in_default_floors(self):
        """Default config floors include relevance, novelty, actionability, credibility."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert "relevance" in cfg.floors
        assert "novelty" in cfg.floors
        assert "actionability" in cfg.floors
        assert "credibility" in cfg.floors

    def test_all_four_dims_set_to_two(self):
        """All four default floors are exactly 2."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert cfg.floors["relevance"] == 2
        assert cfg.floors["novelty"] == 2
        assert cfg.floors["actionability"] == 2
        assert cfg.floors["credibility"] == 2

    def test_floors_dict_has_exactly_four_keys(self):
        """No extra or missing floor dimensions."""
        from packages.research.evaluation.config import load_eval_config
        cfg = load_eval_config()
        assert set(cfg.floors.keys()) == {"relevance", "novelty", "actionability", "credibility"}


# ---------------------------------------------------------------------------
# Novelty floor enforcement
# ---------------------------------------------------------------------------

class TestNoveltyFloorEnforcement:
    def test_novelty_below_floor_priority_3_rejected(self):
        """novelty=1 for priority_3 -> REJECT regardless of other high dims."""
        r = _make_scoring(relevance=4, novelty=1, actionability=4, credibility=4,
                          priority_tier="priority_3")
        assert r.gate == "REJECT"

    def test_novelty_below_floor_priority_2_rejected(self):
        """novelty=1 for priority_2 -> REJECT."""
        r = _make_scoring(relevance=4, novelty=1, actionability=4, credibility=4,
                          priority_tier="priority_2")
        assert r.gate == "REJECT"

    def test_novelty_below_floor_priority_4_rejected(self):
        """novelty=1 for priority_4 -> REJECT."""
        r = _make_scoring(relevance=5, novelty=1, actionability=5, credibility=5,
                          priority_tier="priority_4")
        assert r.gate == "REJECT"

    def test_novelty_at_floor_not_rejected(self):
        """novelty=2 (exactly at floor) does not trigger floor rejection."""
        # composite = 4*0.30 + 2*0.20 + 4*0.20 + 4*0.30 = 1.20+0.40+0.80+1.20 = 3.60 >= 3.2
        r = _make_scoring(relevance=4, novelty=2, actionability=4, credibility=4,
                          priority_tier="priority_3")
        assert r.gate != "REJECT"

    def test_novelty_above_floor_not_rejected_for_floor_reason(self):
        """novelty=3 is above floor; gate outcome is threshold-driven, not floor-driven."""
        r = _make_scoring(relevance=4, novelty=3, actionability=4, credibility=4,
                          priority_tier="priority_3")
        # composite = 4*0.30 + 3*0.20 + 4*0.20 + 4*0.30 = 1.20+0.60+0.80+1.20 = 3.80 >= 3.2
        assert r.gate == "ACCEPT"


# ---------------------------------------------------------------------------
# Actionability floor enforcement
# ---------------------------------------------------------------------------

class TestActionabilityFloorEnforcement:
    def test_actionability_below_floor_priority_3_rejected(self):
        """actionability=1 for priority_3 -> REJECT regardless of other high dims."""
        r = _make_scoring(relevance=4, novelty=4, actionability=1, credibility=4,
                          priority_tier="priority_3")
        assert r.gate == "REJECT"

    def test_actionability_below_floor_priority_2_rejected(self):
        """actionability=1 for priority_2 -> REJECT."""
        r = _make_scoring(relevance=4, novelty=4, actionability=1, credibility=4,
                          priority_tier="priority_2")
        assert r.gate == "REJECT"

    def test_actionability_below_floor_priority_4_rejected(self):
        """actionability=1 for priority_4 -> REJECT."""
        r = _make_scoring(relevance=5, novelty=5, actionability=1, credibility=5,
                          priority_tier="priority_4")
        assert r.gate == "REJECT"

    def test_actionability_at_floor_not_rejected(self):
        """actionability=2 (exactly at floor) does not trigger floor rejection."""
        # composite = 4*0.30 + 4*0.20 + 2*0.20 + 4*0.30 = 1.20+0.80+0.40+1.20 = 3.60 >= 3.2
        r = _make_scoring(relevance=4, novelty=4, actionability=2, credibility=4,
                          priority_tier="priority_3")
        assert r.gate != "REJECT"

    def test_actionability_above_floor_not_rejected_for_floor_reason(self):
        """actionability=3 is above floor; gate is threshold-driven, not floor-driven."""
        r = _make_scoring(relevance=4, novelty=4, actionability=3, credibility=4,
                          priority_tier="priority_3")
        # composite = 4*0.30 + 4*0.20 + 3*0.20 + 4*0.30 = 1.20+0.80+0.60+1.20 = 3.80 >= 3.2
        assert r.gate == "ACCEPT"


# ---------------------------------------------------------------------------
# All-four-floors meeting -> not blocked for floor reasons
# ---------------------------------------------------------------------------

class TestAllFloorsMetNotBlocked:
    def test_all_dims_at_floor_not_floor_blocked(self):
        """All four dims=2 (exactly at floor) -> gate is threshold-driven only."""
        # composite = 2*0.30 + 2*0.20 + 2*0.20 + 2*0.30 = 0.60+0.40+0.40+0.60 = 2.00
        # 2.00 < 3.2 (P3) -> REVIEW, but NOT REJECT (no floor failure)
        r = _make_scoring(relevance=2, novelty=2, actionability=2, credibility=2,
                          priority_tier="priority_3")
        assert r.gate == "REVIEW"

    def test_all_dims_above_floor_high_composite_accepts(self):
        """All four dims=4, priority_3 -> ACCEPT (above floor and threshold)."""
        # composite = 4*0.30 + 4*0.20 + 4*0.20 + 4*0.30 = 1.20+0.80+0.80+1.20 = 4.00 >= 3.2
        r = _make_scoring(relevance=4, novelty=4, actionability=4, credibility=4,
                          priority_tier="priority_3")
        assert r.gate == "ACCEPT"

    def test_floor_exact_with_high_other_dims_accepts(self):
        """novelty=2, actionability=2 at floor; relevance=4, credibility=4 lifts composite."""
        # composite = 4*0.30 + 2*0.20 + 2*0.20 + 4*0.30 = 1.20+0.40+0.40+1.20 = 3.20 >= 3.2
        r = _make_scoring(relevance=4, novelty=2, actionability=2, credibility=4,
                          priority_tier="priority_3")
        assert r.gate == "ACCEPT"


# ---------------------------------------------------------------------------
# Env-var floor overrides for novelty and actionability
# ---------------------------------------------------------------------------

class TestEnvVarFloorOverrides:
    def test_env_var_overrides_novelty_floor(self, monkeypatch):
        """RIS_EVAL_NOVELTY_FLOOR env var overrides config file value."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        monkeypatch.setenv("RIS_EVAL_NOVELTY_FLOOR", "3")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            assert cfg.floors["novelty"] == 3
        finally:
            reset_eval_config()

    def test_env_var_overrides_actionability_floor(self, monkeypatch):
        """RIS_EVAL_ACTIONABILITY_FLOOR env var overrides config file value."""
        from packages.research.evaluation.config import load_eval_config, reset_eval_config
        monkeypatch.setenv("RIS_EVAL_ACTIONABILITY_FLOOR", "3")
        reset_eval_config()
        try:
            cfg = load_eval_config()
            assert cfg.floors["actionability"] == 3
        finally:
            reset_eval_config()

    def test_env_var_novelty_floor_enforced_in_gate(self, monkeypatch):
        """RIS_EVAL_NOVELTY_FLOOR=3 causes novelty=2 to trigger REJECT."""
        from packages.research.evaluation.config import reset_eval_config
        monkeypatch.setenv("RIS_EVAL_NOVELTY_FLOOR", "3")
        reset_eval_config()
        try:
            r = _make_scoring(relevance=4, novelty=2, actionability=4, credibility=4,
                              priority_tier="priority_3")
            assert r.gate == "REJECT"
        finally:
            reset_eval_config()

    def test_env_var_actionability_floor_enforced_in_gate(self, monkeypatch):
        """RIS_EVAL_ACTIONABILITY_FLOOR=3 causes actionability=2 to trigger REJECT."""
        from packages.research.evaluation.config import reset_eval_config
        monkeypatch.setenv("RIS_EVAL_ACTIONABILITY_FLOOR", "3")
        reset_eval_config()
        try:
            r = _make_scoring(relevance=4, novelty=4, actionability=2, credibility=4,
                              priority_tier="priority_3")
            assert r.gate == "REJECT"
        finally:
            reset_eval_config()


# ---------------------------------------------------------------------------
# Floor waive: priority_1 exempt from all four floors
# ---------------------------------------------------------------------------

class TestFloorWaiveAllFourDims:
    def test_priority_1_novelty_below_floor_not_rejected(self):
        """priority_1 with novelty=1 is floor-waived -> not REJECT from floor."""
        # composite = 4*0.30 + 1*0.20 + 4*0.20 + 4*0.30 = 1.20+0.20+0.80+1.20 = 3.40 >= 2.5
        r = _make_scoring(relevance=4, novelty=1, actionability=4, credibility=4,
                          priority_tier="priority_1")
        assert r.gate == "ACCEPT"

    def test_priority_1_actionability_below_floor_not_rejected(self):
        """priority_1 with actionability=1 is floor-waived -> not REJECT from floor."""
        # composite = 4*0.30 + 4*0.20 + 1*0.20 + 4*0.30 = 1.20+0.80+0.20+1.20 = 3.40 >= 2.5
        r = _make_scoring(relevance=4, novelty=4, actionability=1, credibility=4,
                          priority_tier="priority_1")
        assert r.gate == "ACCEPT"

    def test_priority_1_all_four_below_floor_not_rejected(self):
        """priority_1 with all four dims=1 -> floor waived; gate is composite-driven."""
        # composite = 1*0.30 + 1*0.20 + 1*0.20 + 1*0.30 = 1.0 < 2.5 -> REVIEW
        r = _make_scoring(relevance=1, novelty=1, actionability=1, credibility=1,
                          priority_tier="priority_1", composite_score=1.0)
        assert r.gate == "REVIEW"

    def test_priority_1_novelty_and_actionability_both_below_floor_high_composite_accepts(self):
        """priority_1 with novelty=1, actionability=1 but high rel+cred -> ACCEPT."""
        # composite = 5*0.30 + 1*0.20 + 1*0.20 + 5*0.30 = 1.50+0.20+0.20+1.50 = 3.40 >= 2.5
        r = _make_scoring(relevance=5, novelty=1, actionability=1, credibility=5,
                          priority_tier="priority_1")
        assert r.gate == "ACCEPT"
