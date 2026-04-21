"""Focused tests for RIS Phase 2 cloud providers and routing."""

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
    def __init__(self, name: str, model_id: str, raw_output: str | None = None, exc: Exception | None = None):
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


def test_gemini_provider_success(monkeypatch):
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    from packages.research.evaluation import providers

    calls = {}

    def fake_post_json(endpoint, payload, headers, timeout_seconds):
        calls["endpoint"] = endpoint
        calls["payload"] = payload
        calls["headers"] = headers
        calls["timeout_seconds"] = timeout_seconds
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": _payload(4, 4, 4, 4, "gemini-2.5-flash")}
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(providers, "_post_json", fake_post_json)

    provider = providers.get_provider("gemini")
    raw = provider.score(_make_doc(), "prompt")
    parsed = json.loads(raw)

    assert parsed["total"] == 16
    assert calls["endpoint"].endswith(":generateContent")
    assert calls["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert calls["payload"]["generationConfig"]["responseJsonSchema"]["required"]


def test_deepseek_provider_success(monkeypatch):
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")

    from packages.research.evaluation import providers

    calls = {}

    def fake_post_json(endpoint, payload, headers, timeout_seconds):
        calls["endpoint"] = endpoint
        calls["payload"] = payload
        calls["headers"] = headers
        calls["timeout_seconds"] = timeout_seconds
        return {
            "choices": [
                {
                    "message": {"content": _payload(4, 3, 4, 4, "deepseek-chat")},
                    "finish_reason": "stop",
                }
            ]
        }

    monkeypatch.setattr(providers, "_post_json", fake_post_json)

    provider = providers.get_provider("deepseek")
    raw = provider.score(_make_doc(), "prompt")
    parsed = json.loads(raw)

    assert parsed["total"] == 15
    assert calls["endpoint"].endswith("/chat/completions")
    assert calls["headers"]["Authorization"] == "Bearer test-deepseek-key"
    assert calls["payload"]["response_format"] == {"type": "json_object"}


def test_routing_config_env_overrides(monkeypatch):
    monkeypatch.setenv("RIS_EVAL_PRIMARY_PROVIDER", "deepseek")
    monkeypatch.setenv("RIS_EVAL_FALLBACK_PROVIDER", "manual")
    monkeypatch.setenv("RIS_EVAL_GEMINI_BASE_URL", "https://example.invalid/gemini")
    monkeypatch.setenv("RIS_EVAL_DEEPSEEK_TIMEOUT_SECONDS", "99")

    from packages.research.evaluation.config import load_eval_config, reset_eval_config

    reset_eval_config()
    try:
        cfg = load_eval_config()
        assert cfg.routing.primary_provider == "deepseek"
        assert cfg.routing.fallback_provider == "manual"
        assert cfg.provider_configs["gemini"].base_url == "https://example.invalid/gemini"
        assert cfg.provider_configs["deepseek"].timeout_seconds == 99
    finally:
        reset_eval_config()


def test_routed_gray_zone_escalates_to_deepseek(monkeypatch, tmp_path):
    from packages.research.evaluation.artifacts import load_eval_artifacts
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", _payload(3, 3, 3, 3, "gemini-2.5-flash"))
    escalation = _StaticProvider("deepseek", "deepseek-chat", _payload(4, 4, 4, 4, "deepseek-chat"))

    def fake_get_provider(name, **kwargs):
        if name == "deepseek":
            return escalation
        raise AssertionError(f"unexpected provider lookup: {name}")

    monkeypatch.setattr("packages.research.evaluation.evaluator.get_provider", fake_get_provider)

    evaluator = DocumentEvaluator(
        provider=primary,
        provider_name="gemini",
        artifacts_dir=tmp_path,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="gray_zone_escalation"))

    assert decision.gate == "ACCEPT"
    assert decision.scores is not None
    assert decision.scores.eval_provider == "deepseek"
    assert decision.routing["final_reason"] == "review_escalation"
    assert decision.routing["escalated"] is True

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts) == 1
    assert artifacts[0]["routing_decision"]["selected_provider"] == "deepseek"
    assert [event["provider_name"] for event in artifacts[0]["provider_events"]] == ["gemini", "deepseek"]


def test_routed_unavailable_primary_falls_back_to_ollama(monkeypatch, tmp_path):
    from packages.research.evaluation.artifacts import load_eval_artifacts
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.providers import ProviderUnavailableError

    primary = _StaticProvider("gemini", "gemini-2.5-flash", exc=ProviderUnavailableError("gemini down"))
    escalation = _StaticProvider("deepseek", "deepseek-chat", exc=ProviderUnavailableError("deepseek down"))
    fallback = _StaticProvider("ollama", "qwen3:30b", _payload(4, 3, 4, 3, "qwen3:30b"))

    def fake_get_provider(name, **kwargs):
        if name == "deepseek":
            return escalation
        if name == "ollama":
            return fallback
        raise AssertionError(f"unexpected provider lookup: {name}")

    monkeypatch.setattr("packages.research.evaluation.evaluator.get_provider", fake_get_provider)

    evaluator = DocumentEvaluator(
        provider=primary,
        provider_name="gemini",
        artifacts_dir=tmp_path,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="fallback_chain"))

    assert decision.gate == "ACCEPT"
    assert decision.scores is not None
    assert decision.scores.eval_provider == "ollama"
    assert decision.routing["used_fallback"] is True
    assert decision.routing["final_reason"] == "cloud_unavailable_fallback_selected"

    artifacts = load_eval_artifacts(tmp_path)
    assert [event["provider_name"] for event in artifacts[0]["provider_events"]] == ["gemini", "deepseek", "ollama"]
    assert artifacts[0]["provider_events"][0]["failure_reason"] == "provider_unavailable"
    assert artifacts[0]["provider_events"][1]["failure_reason"] == "provider_unavailable"


def test_routed_invalid_primary_response_fails_closed(monkeypatch, tmp_path):
    from packages.research.evaluation.artifacts import load_eval_artifacts
    from packages.research.evaluation.evaluator import DocumentEvaluator

    primary = _StaticProvider("gemini", "gemini-2.5-flash", "not valid json")

    def fake_get_provider(name, **kwargs):
        raise AssertionError("routing should not escalate on invalid primary output")

    monkeypatch.setattr("packages.research.evaluation.evaluator.get_provider", fake_get_provider)

    evaluator = DocumentEvaluator(
        provider=primary,
        provider_name="gemini",
        artifacts_dir=tmp_path,
    )
    decision = evaluator.evaluate(_make_doc(doc_id="invalid_primary"))

    assert decision.gate == "REJECT"
    assert decision.scores is not None
    assert decision.scores.reject_reason == "scorer_failure"
    assert decision.routing["final_reason"] == "invalid_response"

    artifacts = load_eval_artifacts(tmp_path)
    assert len(artifacts[0]["provider_events"]) == 1
    assert artifacts[0]["provider_event"]["status"] == "invalid"


def test_cli_manual_json_smoke(capsys):
    from tools.cli.research_eval import main

    rc = main(["eval", "--title", "Manual Smoke", "--body", _make_doc().body, "--json"])
    assert rc == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["scores"]["eval_provider"] == "manual"
    assert payload["routing"]["mode"] == "direct"


def test_cli_gemini_mocked_cloud_smoke(monkeypatch, capsys):
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    from packages.research.evaluation import providers
    from tools.cli.research_eval import main

    def fake_post_json(endpoint, payload, headers, timeout_seconds):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": _payload(4, 4, 4, 4, "gemini-2.5-flash")}
                        ]
                    }
                }
            ]
        }

    monkeypatch.setattr(providers, "_post_json", fake_post_json)

    rc = main(
        [
            "eval",
            "--provider",
            "gemini",
            "--enable-cloud",
            "--title",
            "Gemini Smoke",
            "--body",
            _make_doc().body,
            "--json",
        ]
    )
    assert rc == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["scores"]["eval_provider"] == "gemini"
    assert payload["routing"]["selected_provider"] == "gemini"
