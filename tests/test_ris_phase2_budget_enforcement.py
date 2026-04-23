"""Focused tests for WP2-I budget enforcement in RIS Phase 2A.

Tests cover:
- No enforcement when budget_tracker_path=None (full backward compat)
- Under-budget: call proceeds, tracker count incremented and saved
- Direct mode: exhausted primary → REJECT budget_exhausted, 1 stub event
- Route mode: exhausted primary → falls to escalation, escalation succeeds
- Route mode: both primary and escalation exhausted → REJECT budget_exhausted, 2 stubs
- Route mode: primary REVIEW + escalation exhausted → REJECT budget_exhausted
- Daily reset: stale date in tracker file → counts reset, call proceeds
- Local providers (manual/ollama) always uncapped regardless of config cap
"""

from __future__ import annotations

import json
from datetime import date


def _today() -> str:
    return date.today().isoformat()


def _make_doc(**kwargs):
    from packages.research.evaluation.types import EvalDocument

    defaults = dict(
        doc_id="budget_test_doc",
        title="Budget Enforcement Test",
        author="Test Author",
        source_type="manual",
        source_url="https://example.com/budget",
        source_publish_date=None,
        body=(
            "This document discusses prediction market microstructure, spread setting, "
            "inventory risk, and calibration details for a market making system."
        ),
    )
    defaults.update(kwargs)
    return EvalDocument(**defaults)


def _payload(relevance: int, novelty: int, actionability: int, credibility: int, model: str) -> str:
    total = relevance + novelty + actionability + credibility
    return json.dumps(
        {
            "relevance": {"score": relevance, "rationale": "Relevant."},
            "novelty": {"score": novelty, "rationale": "Novel."},
            "actionability": {"score": actionability, "rationale": "Actionable."},
            "credibility": {"score": credibility, "rationale": "Credible."},
            "total": total,
            "epistemic_type": "EMPIRICAL",
            "summary": "Structured test payload.",
            "key_findings": ["Finding A"],
            "eval_model": model,
        }
    )


class _StaticProvider:
    def __init__(
        self,
        name: str,
        model_id: str,
        raw_output: str | None = None,
        exc: Exception | None = None,
    ):
        self._name = name
        self._model_id = model_id
        self._raw_output = raw_output
        self._exc = exc

    @property
    def name(self) -> str:
        return self._name

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def generation_params(self) -> dict:
        return {}

    def score(self, doc, prompt) -> str:
        if self._exc is not None:
            raise self._exc
        return self._raw_output or ""


def _write_tracker(path, counts: dict, today: str | None = None) -> None:
    """Write a budget tracker JSON file at path."""
    tracker = {"date": today or _today(), "counts": counts}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tracker), encoding="utf-8")


def _read_tracker(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# No enforcement when budget_tracker_path is None (backward compat)
# ---------------------------------------------------------------------------

def test_no_enforcement_when_tracker_path_none():
    """When budget_tracker_path is None, no budget logic runs — call always proceeds."""
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini-2.5-flash"))
    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="direct",
        budget_tracker_path=None,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="no_enforcement"))

    assert decision.gate == "ACCEPT"
    assert decision.scores is not None
    assert decision.scores.reject_reason is None


# ---------------------------------------------------------------------------
# Under-budget: call proceeds and tracker is incremented
# ---------------------------------------------------------------------------

def test_under_budget_call_proceeds_and_increments(tmp_path, monkeypatch):
    """When provider is under cap, call proceeds and tracker count increments by 1."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "10")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 3})

    reset_eval_config()
    try:
        primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini-2.5-flash"))
        evaluator = DocumentEvaluator(
            provider=primary,
            routing_mode="direct",
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="under_budget"))
    finally:
        reset_eval_config()

    assert decision.gate == "ACCEPT"
    saved = _read_tracker(tracker_path)
    assert saved["counts"]["gemini"] == 4


def test_failed_call_does_not_increment(tmp_path, monkeypatch):
    """A scorer_failure does not increment the provider count."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "10")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 2})

    reset_eval_config()
    try:
        primary = _StaticProvider(
            "gemini", "gemini-2.5-flash",
            exc=RuntimeError("simulated network failure"),
        )
        evaluator = DocumentEvaluator(
            provider=primary,
            routing_mode="direct",
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="failed_call"))
    finally:
        reset_eval_config()

    assert decision.gate == "REJECT"
    assert decision.scores.reject_reason == "scorer_failure"
    saved = _read_tracker(tracker_path)
    assert saved["counts"].get("gemini", 2) == 2


# ---------------------------------------------------------------------------
# Direct mode: primary exhausted → fail-closed REJECT
# ---------------------------------------------------------------------------

def test_direct_mode_primary_exhausted_fails_closed(tmp_path, monkeypatch):
    """Direct mode: primary at cap → REJECT budget_exhausted; provider never called."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "5")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.artifacts import load_eval_artifacts

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 5})  # at cap

    reset_eval_config()
    try:
        never_call = _StaticProvider(
            "gemini", "gemini-2.5-flash",
            exc=AssertionError("provider must not be called when budget exhausted"),
        )
        evaluator = DocumentEvaluator(
            provider=never_call,
            routing_mode="direct",
            artifacts_dir=tmp_path,
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="direct_exhausted"))
    finally:
        reset_eval_config()

    assert decision.gate == "REJECT"
    assert decision.scores is not None
    assert decision.scores.reject_reason == "budget_exhausted"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    assert len(events) == 1
    assert events[0]["provider_name"] == "gemini"


def test_direct_mode_primary_exhausted_does_not_increment(tmp_path, monkeypatch):
    """Budget-exhausted path must not increment the count (count stays at cap)."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "5")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 5})

    reset_eval_config()
    try:
        primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini"))
        evaluator = DocumentEvaluator(
            provider=primary,
            routing_mode="direct",
            budget_tracker_path=tracker_path,
        )
        evaluator.evaluate(_make_doc(doc_id="exhausted_no_increment"))
    finally:
        reset_eval_config()

    saved = _read_tracker(tracker_path)
    assert saved["counts"]["gemini"] == 5  # unchanged


# ---------------------------------------------------------------------------
# Route mode: primary exhausted → escalation proceeds
# ---------------------------------------------------------------------------

def test_route_mode_primary_exhausted_escalation_succeeds(tmp_path, monkeypatch):
    """Route mode: exhausted primary → escalation called directly (skips primary entirely)."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "3")
    monkeypatch.setenv("RIS_EVAL_BUDGET_DEEPSEEK", "10")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.artifacts import load_eval_artifacts

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 3, "deepseek": 1})

    reset_eval_config()
    try:
        never_call_primary = _StaticProvider(
            "gemini", "gemini-2.5-flash",
            exc=AssertionError("primary must not be called when exhausted"),
        )
        escalation = _StaticProvider("deepseek", "deepseek-chat", _payload(4, 4, 4, 4, "deepseek-chat"))
        evaluator = DocumentEvaluator(
            provider=never_call_primary,
            routing_mode="route",
            escalation_provider=escalation,
            artifacts_dir=tmp_path,
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="route_primary_exhausted"))
    finally:
        reset_eval_config()

    assert decision.gate == "ACCEPT"
    assert decision.scores.eval_model == "deepseek-chat"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    # Stub for exhausted primary + real escalation call
    assert len(events) == 2
    assert events[0]["provider_name"] == "gemini"
    assert events[1]["provider_name"] == "deepseek"

    # Escalation count incremented
    saved = _read_tracker(tracker_path)
    assert saved["counts"]["deepseek"] == 2
    # Primary count unchanged
    assert saved["counts"]["gemini"] == 3


# ---------------------------------------------------------------------------
# Route mode: both primary and escalation exhausted → fail-closed
# ---------------------------------------------------------------------------

def test_route_mode_both_exhausted_fails_closed(tmp_path, monkeypatch):
    """Route mode: primary exhausted AND escalation exhausted → REJECT budget_exhausted, 2 stubs."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "5")
    monkeypatch.setenv("RIS_EVAL_BUDGET_DEEPSEEK", "5")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.artifacts import load_eval_artifacts

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 5, "deepseek": 5})

    reset_eval_config()
    try:
        never_call_primary = _StaticProvider(
            "gemini", "gemini-2.5-flash",
            exc=AssertionError("primary must not be called when exhausted"),
        )
        never_call_esc = _StaticProvider(
            "deepseek", "deepseek-chat",
            exc=AssertionError("escalation must not be called when exhausted"),
        )
        evaluator = DocumentEvaluator(
            provider=never_call_primary,
            routing_mode="route",
            escalation_provider=never_call_esc,
            artifacts_dir=tmp_path,
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="both_exhausted"))
    finally:
        reset_eval_config()

    assert decision.gate == "REJECT"
    assert decision.scores.reject_reason == "budget_exhausted"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    assert len(events) == 2
    assert events[0]["provider_name"] == "gemini"
    assert events[1]["provider_name"] == "deepseek"

    # Neither count should increment
    saved = _read_tracker(tracker_path)
    assert saved["counts"]["gemini"] == 5
    assert saved["counts"]["deepseek"] == 5


# ---------------------------------------------------------------------------
# Route mode: primary REVIEW + escalation exhausted → fail-closed
# ---------------------------------------------------------------------------

def test_route_mode_primary_review_escalation_exhausted(tmp_path, monkeypatch):
    """Route mode: primary REVIEW + escalation at cap → REJECT budget_exhausted, 2 events."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "10")
    monkeypatch.setenv("RIS_EVAL_BUDGET_DEEPSEEK", "3")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.artifacts import load_eval_artifacts

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 0, "deepseek": 3})

    reset_eval_config()
    try:
        # 3,3,3,3 → composite 3.0 < P3 threshold 3.2 → REVIEW → triggers escalation check
        primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(3, 3, 3, 3, "gemini-2.5-flash"))
        never_call_esc = _StaticProvider(
            "deepseek", "deepseek-chat",
            exc=AssertionError("escalation must not be called when exhausted"),
        )
        evaluator = DocumentEvaluator(
            provider=primary,
            routing_mode="route",
            escalation_provider=never_call_esc,
            artifacts_dir=tmp_path,
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="review_esc_exhausted"))
    finally:
        reset_eval_config()

    assert decision.gate == "REJECT"
    assert decision.scores.reject_reason == "budget_exhausted"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    # primary real call + escalation stub
    assert len(events) == 2
    assert events[0]["provider_name"] == "gemini"
    assert events[1]["provider_name"] == "deepseek"

    # Primary incremented, escalation unchanged
    saved = _read_tracker(tracker_path)
    assert saved["counts"]["gemini"] == 1
    assert saved["counts"]["deepseek"] == 3


# ---------------------------------------------------------------------------
# Daily reset: stale tracker resets counts
# ---------------------------------------------------------------------------

def test_stale_tracker_resets_on_load(tmp_path, monkeypatch):
    """A tracker with a past date is treated as empty (counts reset to zero)."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "1")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator

    tracker_path = tmp_path / "budget_tracker.json"
    # Write with yesterday's date and a count that would exhaust the cap
    _write_tracker(tracker_path, {"gemini": 1}, today="2020-01-01")

    reset_eval_config()
    try:
        primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini-2.5-flash"))
        evaluator = DocumentEvaluator(
            provider=primary,
            routing_mode="direct",
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="stale_tracker"))
    finally:
        reset_eval_config()

    # Call should succeed because stale tracker is treated as fresh (count=0 < cap=1)
    assert decision.gate == "ACCEPT"
    saved = _read_tracker(tracker_path)
    assert saved["date"] == _today()
    assert saved["counts"]["gemini"] == 1


# ---------------------------------------------------------------------------
# Local providers are always uncapped
# ---------------------------------------------------------------------------

def test_local_provider_manual_always_uncapped(tmp_path, monkeypatch):
    """manual provider is always available regardless of any cap in the config."""
    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import DocumentEvaluator

    tracker_path = tmp_path / "budget_tracker.json"
    # Seed tracker with a huge count for "manual" — should make no difference
    _write_tracker(tracker_path, {"manual": 999999})

    reset_eval_config()
    try:
        primary = _StaticProvider("manual", "manual", _payload(4, 4, 4, 4, "manual"))
        evaluator = DocumentEvaluator(
            provider=primary,
            routing_mode="direct",
            budget_tracker_path=tracker_path,
        )
        decision = evaluator.evaluate(_make_doc(doc_id="manual_uncapped"))
    finally:
        reset_eval_config()

    assert decision.gate == "ACCEPT"
    # Count must not be incremented for local providers
    saved = _read_tracker(tracker_path)
    assert saved["counts"].get("manual", 999999) == 999999


def test_local_provider_ollama_always_uncapped(tmp_path, monkeypatch):
    """ollama provider is always available regardless of any cap."""
    from packages.research.evaluation.budget import is_budget_available, load_budget_tracker

    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, {"ollama": 999999})
    tracker = load_budget_tracker(tracker_path)

    # Even with cap=1, ollama is uncapped
    assert is_budget_available("ollama", 1, tracker) is True
    assert is_budget_available("ollama", 0, tracker) is True


# ---------------------------------------------------------------------------
# budget.py unit tests: load / save / check / increment
# ---------------------------------------------------------------------------

def test_load_budget_tracker_missing_file(tmp_path):
    """Missing tracker file returns fresh tracker for today with empty counts."""
    from packages.research.evaluation.budget import load_budget_tracker

    tracker_path = tmp_path / "nonexistent.json"
    tracker = load_budget_tracker(tracker_path)

    assert tracker["date"] == _today()
    assert tracker["counts"] == {}


def test_load_budget_tracker_current_date(tmp_path):
    """Tracker with today's date is returned as-is."""
    from packages.research.evaluation.budget import load_budget_tracker

    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, {"gemini": 42})
    tracker = load_budget_tracker(tracker_path)

    assert tracker["date"] == _today()
    assert tracker["counts"]["gemini"] == 42


def test_load_budget_tracker_stale_date_resets(tmp_path):
    """Tracker with stale date returns a fresh tracker (counts = {})."""
    from packages.research.evaluation.budget import load_budget_tracker

    tracker_path = tmp_path / "tracker.json"
    _write_tracker(tracker_path, {"gemini": 100}, today="1999-12-31")
    tracker = load_budget_tracker(tracker_path)

    assert tracker["date"] == _today()
    assert tracker["counts"] == {}


def test_is_budget_available_under_cap():
    """is_budget_available returns True when used < cap."""
    from packages.research.evaluation.budget import is_budget_available

    tracker = {"date": _today(), "counts": {"gemini": 3}}
    assert is_budget_available("gemini", 10, tracker) is True


def test_is_budget_available_at_cap():
    """is_budget_available returns False when used == cap."""
    from packages.research.evaluation.budget import is_budget_available

    tracker = {"date": _today(), "counts": {"gemini": 10}}
    assert is_budget_available("gemini", 10, tracker) is False


def test_is_budget_available_no_cap():
    """is_budget_available returns True when cap is None (uncapped)."""
    from packages.research.evaluation.budget import is_budget_available

    tracker = {"date": _today(), "counts": {"gemini": 9999}}
    assert is_budget_available("gemini", None, tracker) is True


def test_increment_provider_count():
    """increment_provider_count increments count in-place and returns tracker."""
    from packages.research.evaluation.budget import increment_provider_count

    tracker = {"date": _today(), "counts": {"gemini": 5}}
    result = increment_provider_count("gemini", tracker)

    assert result is tracker
    assert tracker["counts"]["gemini"] == 6


def test_increment_provider_count_new_key():
    """increment_provider_count handles a provider with no prior count."""
    from packages.research.evaluation.budget import increment_provider_count

    tracker = {"date": _today(), "counts": {}}
    increment_provider_count("deepseek", tracker)

    assert tracker["counts"]["deepseek"] == 1


def test_save_budget_tracker_creates_dirs(tmp_path):
    """save_budget_tracker creates parent dirs if they don't exist."""
    from packages.research.evaluation.budget import save_budget_tracker

    tracker_path = tmp_path / "nested" / "deep" / "tracker.json"
    tracker = {"date": _today(), "counts": {"gemini": 7}}
    save_budget_tracker(tracker, tracker_path)

    assert tracker_path.exists()
    saved = json.loads(tracker_path.read_text(encoding="utf-8"))
    assert saved["counts"]["gemini"] == 7


# ---------------------------------------------------------------------------
# Config: BudgetConfig loads from JSON and env vars
# ---------------------------------------------------------------------------

def test_budget_config_loads_from_json():
    """BudgetConfig per_provider caps are parsed from ris_eval_config.json."""
    from packages.research.evaluation.config import load_eval_config, reset_eval_config

    reset_eval_config()
    try:
        cfg = load_eval_config()
        assert cfg.budget.per_provider["gemini"] == 500
        assert cfg.budget.per_provider["deepseek"] == 500
    finally:
        reset_eval_config()


def test_budget_config_env_override(monkeypatch):
    """RIS_EVAL_BUDGET_GEMINI env var overrides JSON value."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "42")
    monkeypatch.setenv("RIS_EVAL_BUDGET_DEEPSEEK", "99")

    from packages.research.evaluation.config import load_eval_config, reset_eval_config

    reset_eval_config()
    try:
        cfg = load_eval_config()
        assert cfg.budget.per_provider["gemini"] == 42
        assert cfg.budget.per_provider["deepseek"] == 99
    finally:
        reset_eval_config()


# ---------------------------------------------------------------------------
# Public path: evaluate_document() wires budget enforcement automatically
# ---------------------------------------------------------------------------

def test_evaluate_document_public_path_exhausted_fails_closed(tmp_path, monkeypatch):
    """evaluate_document() passes budget_tracker_path to DocumentEvaluator; exhausted → REJECT."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "5")

    import packages.research.evaluation.evaluator as _ev
    from packages.research.evaluation.config import reset_eval_config

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 5})  # at cap

    never_call = _StaticProvider(
        "gemini", "gemini-2.5-flash",
        exc=AssertionError("provider must not be called when budget exhausted"),
    )
    monkeypatch.setattr(_ev, "get_provider", lambda name, **kw: never_call)

    reset_eval_config()
    try:
        decision = _ev.evaluate_document(
            _make_doc(doc_id="public_path_exhausted"),
            provider_name="gemini",
            budget_tracker_path=tracker_path,
        )
    finally:
        reset_eval_config()

    assert decision.gate == "REJECT"
    assert decision.scores.reject_reason == "budget_exhausted"


def test_evaluate_document_public_path_under_budget_proceeds(tmp_path, monkeypatch):
    """evaluate_document() under budget: call proceeds and tracker count increments."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "10")

    import packages.research.evaluation.evaluator as _ev
    from packages.research.evaluation.config import reset_eval_config

    tracker_path = tmp_path / "budget_tracker.json"
    _write_tracker(tracker_path, {"gemini": 2})

    provider = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini-2.5-flash"))
    monkeypatch.setattr(_ev, "get_provider", lambda name, **kw: provider)

    reset_eval_config()
    try:
        decision = _ev.evaluate_document(
            _make_doc(doc_id="public_path_under_budget"),
            provider_name="gemini",
            budget_tracker_path=tracker_path,
        )
    finally:
        reset_eval_config()

    assert decision.gate == "ACCEPT"
    saved = _read_tracker(tracker_path)
    assert saved["counts"]["gemini"] == 3


def test_evaluate_document_default_tracker_path_enforces_budget(tmp_path, monkeypatch):
    """evaluate_document() with no budget_tracker_path uses _DEFAULT_TRACKER_PATH (enforcement on)."""
    monkeypatch.setenv("RIS_EVAL_BUDGET_GEMINI", "5")
    monkeypatch.setattr(
        "packages.research.evaluation.budget._DEFAULT_TRACKER_PATH",
        tmp_path / "budget_tracker.json",
    )

    import packages.research.evaluation.evaluator as _ev
    from packages.research.evaluation.config import reset_eval_config

    _write_tracker(tmp_path / "budget_tracker.json", {"gemini": 5})  # exhausted at redirected path

    never_call = _StaticProvider(
        "gemini", "gemini-2.5-flash",
        exc=AssertionError("must not call exhausted provider"),
    )
    monkeypatch.setattr(_ev, "get_provider", lambda name, **kw: never_call)

    reset_eval_config()
    try:
        # No budget_tracker_path passed — must use _DEFAULT_TRACKER_PATH automatically
        decision = _ev.evaluate_document(
            _make_doc(doc_id="default_path_enforced"),
            provider_name="gemini",
        )
    finally:
        reset_eval_config()

    assert decision.gate == "REJECT"
    assert decision.scores.reject_reason == "budget_exhausted"
