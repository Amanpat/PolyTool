"""Focused tests for WP2-H multi-provider routing in RIS Phase 2A.

Tests cover:
- RoutingConfig loading from JSON and env-var overrides
- Direct mode: escalation never triggers regardless of primary gate result
- Route mode: ACCEPT from primary skips escalation
- Route mode: REVIEW from primary triggers escalation provider
- Fail-closed: primary exception → REJECT, no escalation
- Fail-closed: escalation exception → REJECT, two provider_events in artifact
"""

from __future__ import annotations

import json


def _make_doc(**kwargs):
    from packages.research.evaluation.types import EvalDocument

    defaults = dict(
        doc_id="cloud_route_doc",
        title="Cloud Provider Routing",
        author="Test Author",
        source_type="manual",
        source_url="https://example.com/cloud",
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


# ---------------------------------------------------------------------------
# Config-level tests
# ---------------------------------------------------------------------------

def test_routing_config_loads_from_json():
    """Routing section in ris_eval_config.json is parsed into RoutingConfig."""
    from packages.research.evaluation.config import load_eval_config, reset_eval_config

    reset_eval_config()
    try:
        cfg = load_eval_config()
        assert cfg.routing.mode == "direct"
        assert cfg.routing.primary_provider == "gemini"
        assert cfg.routing.escalation_provider == "deepseek"
    finally:
        reset_eval_config()


def test_routing_config_env_overrides(monkeypatch):
    """RIS_EVAL_ROUTING_MODE / _PRIMARY_PROVIDER / _ESCALATION_PROVIDER override JSON values."""
    monkeypatch.setenv("RIS_EVAL_ROUTING_MODE", "route")
    monkeypatch.setenv("RIS_EVAL_PRIMARY_PROVIDER", "ollama")
    monkeypatch.setenv("RIS_EVAL_ESCALATION_PROVIDER", "manual")

    from packages.research.evaluation.config import load_eval_config, reset_eval_config

    reset_eval_config()
    try:
        cfg = load_eval_config()
        assert cfg.routing.mode == "route"
        assert cfg.routing.primary_provider == "ollama"
        assert cfg.routing.escalation_provider == "manual"
    finally:
        reset_eval_config()


# ---------------------------------------------------------------------------
# Direct mode — escalation must never be called
# ---------------------------------------------------------------------------

def test_direct_mode_primary_accepted():
    """Direct mode: ACCEPT from primary is returned; escalation provider is never called."""
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini-2.5-flash"))
    never_call = _StaticProvider(
        "deepseek", "deepseek-chat",
        exc=AssertionError("escalation must not be called in direct mode"),
    )
    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="direct",
        escalation_provider=never_call,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="direct_accept"))

    assert decision.gate == "ACCEPT"
    assert decision.scores is not None
    assert decision.scores.eval_model == "gemini-2.5-flash"


def test_direct_mode_primary_review_no_escalation():
    """Direct mode: REVIEW from primary is returned as-is; escalation provider is never called."""
    from packages.research.evaluation.evaluator import DocumentEvaluator

    # 3,3,3,3 → composite=3.0 < P3 threshold 3.2 → REVIEW (floors pass: all >=2)
    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(3, 3, 3, 3, "gemini-2.5-flash"))
    never_call = _StaticProvider(
        "deepseek", "deepseek-chat",
        exc=AssertionError("escalation must not be called in direct mode"),
    )
    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="direct",
        escalation_provider=never_call,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="direct_review"))

    assert decision.gate == "REVIEW"
    assert decision.scores.eval_model == "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# Route mode — escalation only on REVIEW
# ---------------------------------------------------------------------------

def test_route_mode_primary_accepted_no_escalation():
    """Route mode: ACCEPT from primary short-circuits; escalation provider is never called."""
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(4, 4, 4, 4, "gemini-2.5-flash"))
    never_call = _StaticProvider(
        "deepseek", "deepseek-chat",
        exc=AssertionError("escalation called when primary already accepted"),
    )
    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="route",
        escalation_provider=never_call,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="route_accept"))

    assert decision.gate == "ACCEPT"
    assert decision.scores.eval_model == "gemini-2.5-flash"


def test_route_mode_primary_review_escalates_and_accepts(tmp_path):
    """Route mode: primary REVIEW escalates to secondary; ACCEPT from escalation wins.

    Artifact must record both attempts in order: primary (gemini) then escalation (deepseek).
    """
    from packages.research.evaluation.artifacts import load_eval_artifacts
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(3, 3, 3, 3, "gemini-2.5-flash"))
    escalation = _StaticProvider("deepseek", "deepseek-chat", _payload(4, 4, 4, 4, "deepseek-chat"))

    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="route",
        escalation_provider=escalation,
        artifacts_dir=tmp_path,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="route_escalate_accept"))

    assert decision.gate == "ACCEPT"
    assert decision.scores is not None
    assert decision.scores.eval_model == "deepseek-chat"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    assert len(events) == 2
    assert events[0]["provider_name"] == "gemini"
    assert events[1]["provider_name"] == "deepseek"


def test_route_mode_primary_exception_fails_closed(tmp_path):
    """Route mode: exception from primary → fail-closed REJECT; escalation is never triggered."""
    from packages.research.evaluation.artifacts import load_eval_artifacts
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider(
        "gemini", "gemini-2.5-flash",
        exc=ConnectionError("simulated network failure"),
    )
    never_call = _StaticProvider(
        "deepseek", "deepseek-chat",
        exc=AssertionError("escalation must not be called after primary exception"),
    )
    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="route",
        escalation_provider=never_call,
        artifacts_dir=tmp_path,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="route_primary_exception"))

    assert decision.gate == "REJECT"
    assert decision.scores is not None
    assert decision.scores.reject_reason == "scorer_failure"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    assert len(events) == 1
    assert events[0]["provider_name"] == "gemini"


def test_route_mode_escalation_exception_fails_closed(tmp_path):
    """Route mode: primary REVIEW + escalation exception → fail-closed REJECT with two events."""
    from packages.research.evaluation.artifacts import load_eval_artifacts
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(3, 3, 3, 3, "gemini-2.5-flash"))
    escalation = _StaticProvider(
        "deepseek", "deepseek-chat",
        exc=RuntimeError("deepseek unavailable"),
    )
    evaluator = DocumentEvaluator(
        provider=primary,
        routing_mode="route",
        escalation_provider=escalation,
        artifacts_dir=tmp_path,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="route_esc_exception"))

    assert decision.gate == "REJECT"
    assert decision.scores is not None
    assert decision.scores.reject_reason == "scorer_failure"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    events = artifacts[0]["provider_events"]
    assert len(events) == 2
    assert events[0]["provider_name"] == "gemini"
    assert events[1]["provider_name"] == "deepseek"


# ---------------------------------------------------------------------------
# Config-wiring tests — evaluate_document() public API
# ---------------------------------------------------------------------------

def test_evaluate_document_route_mode_two_provider_events(tmp_path, monkeypatch):
    """evaluate_document() with no explicit provider honors RIS_EVAL_ROUTING_MODE=route.

    Uses manual for both primary and escalation to avoid real cloud API calls.
    ManualProvider returns (3,3,3,3) → composite 3.0 < P3 threshold 3.2 → REVIEW,
    which triggers escalation. Artifact must contain 2 provider_events.
    """
    monkeypatch.setenv("RIS_EVAL_ROUTING_MODE", "route")
    monkeypatch.setenv("RIS_EVAL_PRIMARY_PROVIDER", "manual")
    monkeypatch.setenv("RIS_EVAL_ESCALATION_PROVIDER", "manual")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import evaluate_document
    from packages.research.evaluation.artifacts import load_eval_artifacts

    reset_eval_config()
    try:
        decision = evaluate_document(_make_doc(doc_id="route_wiring_test"), artifacts_dir=tmp_path)

        # ManualProvider → REVIEW → escalation fires → second ManualProvider → REVIEW again
        assert decision.gate == "REVIEW"
        arts = load_eval_artifacts(tmp_path)
        assert len(arts) == 1
        events = arts[0]["provider_events"]
        assert len(events) == 2, "route mode must record both primary and escalation attempts"
    finally:
        reset_eval_config()


def test_evaluate_document_explicit_provider_bypasses_route_mode(tmp_path, monkeypatch):
    """Explicit provider_name forces direct mode even when route mode is configured."""
    monkeypatch.setenv("RIS_EVAL_ROUTING_MODE", "route")
    monkeypatch.setenv("RIS_EVAL_PRIMARY_PROVIDER", "manual")
    monkeypatch.setenv("RIS_EVAL_ESCALATION_PROVIDER", "manual")

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import evaluate_document
    from packages.research.evaluation.artifacts import load_eval_artifacts

    reset_eval_config()
    try:
        # Explicit provider_name → direct mode; escalation must not fire
        decision = evaluate_document(
            _make_doc(doc_id="explicit_provider_test"),
            provider_name="manual",
            artifacts_dir=tmp_path,
        )
        assert decision.gate == "REVIEW"
        arts = load_eval_artifacts(tmp_path)
        assert len(arts) == 1
        events = arts[0]["provider_events"]
        assert len(events) == 1, "explicit provider must use direct mode (no escalation)"
    finally:
        reset_eval_config()


def test_escalation_construction_fails_closed_via_config(tmp_path, monkeypatch):
    """Escalation construction failure (PermissionError) → fail-closed REJECT, 2 events.

    primary=manual (succeeds → REVIEW), escalation=deepseek without cloud guard
    → _get_escalation_provider() raises PermissionError → caught → REJECT.
    """
    monkeypatch.setenv("RIS_EVAL_ROUTING_MODE", "route")
    monkeypatch.setenv("RIS_EVAL_PRIMARY_PROVIDER", "manual")
    monkeypatch.setenv("RIS_EVAL_ESCALATION_PROVIDER", "deepseek")
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)

    from packages.research.evaluation.config import reset_eval_config
    from packages.research.evaluation.evaluator import evaluate_document
    from packages.research.evaluation.artifacts import load_eval_artifacts

    reset_eval_config()
    try:
        decision = evaluate_document(
            _make_doc(doc_id="esc_construction_fail_test"),
            artifacts_dir=tmp_path,
        )

        assert decision.gate == "REJECT"
        assert decision.scores is not None
        assert decision.scores.reject_reason == "scorer_failure"

        arts = load_eval_artifacts(tmp_path)
        assert len(arts) == 1
        events = arts[0]["provider_events"]
        assert len(events) == 2, "both primary attempt and failed escalation must be recorded"
        assert events[0]["provider_name"] == "manual"
        assert events[1]["provider_name"] == "deepseek"
    finally:
        reset_eval_config()
