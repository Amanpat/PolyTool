"""Tests for RIS Phase 5: Controlled Provider Enablement with Replay-Grade Auditability.

All tests are deterministic and offline — no network calls.
Uses tmp_path fixture for artifacts_dir and monkeypatch for env var manipulation.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Cloud provider guard tests (4 tests)
# ---------------------------------------------------------------------------


def test_local_providers_no_guard_needed(monkeypatch):
    """manual and ollama work without RIS_ENABLE_CLOUD_PROVIDERS env var."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)

    from packages.research.evaluation.providers import get_provider

    # ManualProvider: no exception
    p_manual = get_provider("manual")
    assert p_manual.name == "manual"

    # OllamaProvider: instantiates fine (no network call during construction)
    p_ollama = get_provider("ollama")
    assert p_ollama.name == "ollama"


def test_cloud_provider_blocked_without_env_var(monkeypatch):
    """get_provider('gemini') raises PermissionError without env var."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)

    from packages.research.evaluation.providers import get_provider

    with pytest.raises(PermissionError) as exc_info:
        get_provider("gemini")

    assert "RIS_ENABLE_CLOUD_PROVIDERS" in str(exc_info.value)
    assert "gemini" in str(exc_info.value)


def test_cloud_provider_env_var_set_but_not_implemented(monkeypatch):
    """With RIS_ENABLE_CLOUD_PROVIDERS=1, get_provider('gemini') raises ValueError
    (not implemented), NOT PermissionError."""
    monkeypatch.setenv("RIS_ENABLE_CLOUD_PROVIDERS", "1")

    from packages.research.evaluation.providers import get_provider

    with pytest.raises(ValueError) as exc_info:
        get_provider("gemini")

    # Must be ValueError, not PermissionError
    assert "not yet implemented" in str(exc_info.value).lower() or "recognized" in str(exc_info.value).lower()


def test_cloud_guard_env_var_name_is_correct():
    """_CLOUD_GUARD_ENV_VAR must equal 'RIS_ENABLE_CLOUD_PROVIDERS'."""
    from packages.research.evaluation.providers import _CLOUD_GUARD_ENV_VAR

    assert _CLOUD_GUARD_ENV_VAR == "RIS_ENABLE_CLOUD_PROVIDERS"


# ---------------------------------------------------------------------------
# Provider metadata tests (2 tests)
# ---------------------------------------------------------------------------


def test_manual_provider_metadata():
    """get_provider_metadata(ManualProvider()) returns correct dict."""
    from packages.research.evaluation.providers import ManualProvider, get_provider_metadata

    p = ManualProvider()
    meta = get_provider_metadata(p)

    assert meta["provider_name"] == "manual"
    assert meta["model_id"] == "manual_placeholder"
    assert meta["generation_params"] == {}


def test_ollama_provider_metadata():
    """get_provider_metadata(OllamaProvider()) returns model_id and generation_params."""
    from packages.research.evaluation.providers import OllamaProvider, get_provider_metadata

    p = OllamaProvider(model="qwen3:30b")
    meta = get_provider_metadata(p)

    assert meta["provider_name"] == "ollama"
    assert meta["model_id"] == "qwen3:30b"
    assert meta["generation_params"]["format"] == "json"
    assert meta["generation_params"]["stream"] is False


# ---------------------------------------------------------------------------
# Replay metadata in artifacts tests (3 tests)
# ---------------------------------------------------------------------------


_LONG_BODY = (
    "This document discusses Avellaneda-Stoikov market making strategies "
    "on Polymarket prediction markets. It covers spread calculations, "
    "inventory risk, and the logit transformation for probability space. "
    "Empirical results from the BTC/ETH crypto pair show consistent edge. "
    "The approach involves careful calibration of kappa and gamma parameters."
)


def test_eval_artifact_has_provider_event(tmp_path):
    """evaluate_document with artifacts_dir persists EvalArtifact with provider_event fields."""
    from packages.research.evaluation.types import EvalDocument
    from packages.research.evaluation.evaluator import evaluate_document
    from packages.research.evaluation.artifacts import load_eval_artifacts

    doc = EvalDocument(
        doc_id="test_pe_001",
        title="Market Making Strategy",
        author="Test Author",
        source_type="manual",
        source_url="",
        source_publish_date=None,
        body=_LONG_BODY,
    )

    decision = evaluate_document(doc, provider_name="manual", artifacts_dir=tmp_path)
    assert decision.gate == "ACCEPT"

    arts = load_eval_artifacts(tmp_path)
    assert len(arts) == 1

    art = arts[0]
    pe = art.get("provider_event")
    assert pe is not None, "provider_event should be set for scoring path"
    assert pe["provider_name"] == "manual"
    assert pe["model_id"] == "manual_placeholder"
    assert pe["prompt_template_id"] == "scoring_v1"
    assert len(pe["output_hash"]) == 16
    assert len(pe["prompt_template_version"]) == 12
    assert pe["source_chunk_refs"] == ["test_pe_001"]
    assert pe["generation_params"] == {}

    event_id = art.get("event_id")
    assert event_id is not None and len(event_id) == 16


def test_eval_artifact_event_id_deterministic(tmp_path, monkeypatch):
    """Same doc + same timestamp + same provider always produces the same event_id."""
    from packages.research.evaluation.artifacts import generate_event_id

    eid1 = generate_event_id("doc_abc", "2026-04-02T12:00:00+00:00", "manual")
    eid2 = generate_event_id("doc_abc", "2026-04-02T12:00:00+00:00", "manual")
    assert eid1 == eid2
    assert len(eid1) == 16

    # Different provider -> different event_id
    eid3 = generate_event_id("doc_abc", "2026-04-02T12:00:00+00:00", "ollama")
    assert eid3 != eid1


def test_eval_artifact_backward_compat(tmp_path):
    """Old-style EvalArtifact without provider_event/event_id persists and loads correctly."""
    from packages.research.evaluation.artifacts import (
        EvalArtifact,
        persist_eval_artifact,
        load_eval_artifacts,
    )

    # Construct an artifact the Phase 3 way (no provider_event or event_id)
    artifact = EvalArtifact(
        doc_id="old_style_001",
        timestamp="2026-01-01T00:00:00+00:00",
        gate="ACCEPT",
        hard_stop_result=None,
        near_duplicate_result=None,
        family_features={"word_count": 50},
        scores={"relevance": 3, "novelty": 3, "actionability": 3, "credibility": 3, "total": 12},
        source_family="manual",
        source_type="manual",
        # provider_event and event_id intentionally omitted — use defaults
    )
    assert artifact.provider_event is None
    assert artifact.event_id is None

    persist_eval_artifact(artifact, tmp_path)
    loaded = load_eval_artifacts(tmp_path)

    assert len(loaded) == 1
    art = loaded[0]
    # Old-style artifacts load correctly; provider_event and event_id are None
    assert art["doc_id"] == "old_style_001"
    assert art.get("provider_event") is None
    assert art.get("event_id") is None


# ---------------------------------------------------------------------------
# Replay/compare workflow tests (4 tests)
# ---------------------------------------------------------------------------


def test_compare_eval_events_detects_diffs():
    """Two artifacts with different scores produce ReplayDiff with correct diff_fields."""
    from packages.research.evaluation.replay import compare_eval_events

    a1 = {
        "doc_id": "x",
        "event_id": "evt_original",
        "gate": "ACCEPT",
        "scores": {"relevance": 3, "novelty": 3, "actionability": 3, "credibility": 3, "total": 12},
        "provider_event": {"provider_name": "manual", "prompt_template_id": "scoring_v1"},
    }
    a2 = {
        "doc_id": "x",
        "event_id": "evt_replay",
        "gate": "REVIEW",
        "scores": {"relevance": 2, "novelty": 3, "actionability": 2, "credibility": 3, "total": 10},
        "provider_event": {"provider_name": "ollama", "prompt_template_id": "scoring_v1"},
    }

    diff = compare_eval_events(a1, a2)

    assert diff.gate_changed is True
    assert diff.original_gate == "ACCEPT"
    assert diff.replay_gate == "REVIEW"
    assert diff.provider_original == "manual"
    assert diff.provider_replay == "ollama"
    assert "relevance" in diff.diff_fields
    assert "actionability" in diff.diff_fields
    assert "total" in diff.diff_fields
    assert diff.diff_fields["relevance"] == {"original": 3, "replay": 2}
    # novelty and credibility unchanged — should NOT be in diff_fields
    assert "novelty" not in diff.diff_fields
    assert "credibility" not in diff.diff_fields


def test_compare_eval_events_no_diff():
    """Two identical artifacts produce empty diff_fields and gate_changed=False."""
    from packages.research.evaluation.replay import compare_eval_events

    a1 = {
        "doc_id": "x",
        "event_id": "evt_a",
        "gate": "ACCEPT",
        "scores": {"relevance": 4, "novelty": 3, "actionability": 3, "credibility": 4, "total": 14},
        "provider_event": {"provider_name": "manual", "prompt_template_id": "scoring_v1"},
    }
    # Identical scores
    a2 = dict(a1)
    a2["event_id"] = "evt_b"

    diff = compare_eval_events(a1, a2)

    assert diff.diff_fields == {}
    assert diff.gate_changed is False
    assert diff.original_gate == "ACCEPT"
    assert diff.replay_gate == "ACCEPT"


def test_persist_and_load_replay_diff(tmp_path):
    """persist_replay_diff writes JSON; load_replay_diffs reads it back correctly."""
    from packages.research.evaluation.replay import (
        ReplayDiff,
        persist_replay_diff,
        load_replay_diffs,
    )

    diff = ReplayDiff(
        original_event_id="evt_abc123",
        replay_timestamp="2026-04-02T12:00:00+00:00",
        original_output={"relevance": 3, "total": 12},
        replay_output={"relevance": 2, "total": 10},
        diff_fields={"relevance": {"original": 3, "replay": 2}, "total": {"original": 12, "replay": 10}},
        provider_original="manual",
        provider_replay="ollama",
        prompt_template_original="scoring_v1",
        prompt_template_replay="scoring_v1",
        original_gate="ACCEPT",
        replay_gate="REVIEW",
        gate_changed=True,
    )

    path = persist_replay_diff(diff, tmp_path)
    assert path.exists()
    assert path.suffix == ".json"
    assert "evt_abc123" in path.name

    loaded = load_replay_diffs(tmp_path)
    assert len(loaded) == 1
    d = loaded[0]
    assert d["original_event_id"] == "evt_abc123"
    assert d["gate_changed"] is True
    assert d["provider_original"] == "manual"
    assert d["provider_replay"] == "ollama"
    assert "relevance" in d["diff_fields"]


def test_find_artifact_by_event_id(tmp_path):
    """Persist two artifacts; find_artifact_by_event_id returns the correct one."""
    from packages.research.evaluation.artifacts import (
        EvalArtifact,
        persist_eval_artifact,
    )
    from packages.research.evaluation.replay import find_artifact_by_event_id

    a1 = EvalArtifact(
        doc_id="doc_find_1",
        timestamp="2026-04-01T00:00:00+00:00",
        gate="ACCEPT",
        hard_stop_result=None,
        near_duplicate_result=None,
        family_features={},
        scores=None,
        source_family="manual",
        source_type="manual",
        provider_event=None,
        event_id="aaaa1111bbbb2222",
    )
    a2 = EvalArtifact(
        doc_id="doc_find_2",
        timestamp="2026-04-01T01:00:00+00:00",
        gate="REVIEW",
        hard_stop_result=None,
        near_duplicate_result=None,
        family_features={},
        scores=None,
        source_family="manual",
        source_type="manual",
        provider_event=None,
        event_id="cccc3333dddd4444",
    )
    persist_eval_artifact(a1, tmp_path)
    persist_eval_artifact(a2, tmp_path)

    found1 = find_artifact_by_event_id("aaaa1111bbbb2222", tmp_path)
    assert found1 is not None
    assert found1["doc_id"] == "doc_find_1"

    found2 = find_artifact_by_event_id("cccc3333dddd4444", tmp_path)
    assert found2 is not None
    assert found2["doc_id"] == "doc_find_2"

    not_found = find_artifact_by_event_id("nonexistent1234", tmp_path)
    assert not_found is None


# ---------------------------------------------------------------------------
# CLI tests (3 tests)
# ---------------------------------------------------------------------------


def test_cli_eval_backward_compat(monkeypatch):
    """main(['--title', 'T', '--body', 'B...']) returns 0 (backward compat)."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    from tools.cli.research_eval import main

    rc = main(["--title", "Test Title", "--body", _LONG_BODY])
    assert rc == 0


def test_cli_cloud_guard_blocks(monkeypatch, capsys):
    """main(['eval', '--title', 'T', '--body', 'B', '--provider', 'gemini']) returns non-zero
    without cloud env var."""
    monkeypatch.delenv("RIS_ENABLE_CLOUD_PROVIDERS", raising=False)
    from tools.cli.research_eval import main

    rc = main(["eval", "--title", "Test", "--body", _LONG_BODY, "--provider", "gemini"])
    assert rc != 0

    captured = capsys.readouterr()
    assert "RIS_ENABLE_CLOUD_PROVIDERS" in captured.err or "cloud" in captured.err.lower()


def test_cli_replay_no_args_fails(capsys):
    """main(['replay']) with no required args returns non-zero."""
    from tools.cli.research_eval import main

    rc = main(["replay"])
    assert rc != 0


# ---------------------------------------------------------------------------
# Scoring template ID test (1 test)
# ---------------------------------------------------------------------------


def test_scoring_prompt_template_id():
    """SCORING_PROMPT_TEMPLATE_ID must equal 'scoring_v1'."""
    from packages.research.evaluation.scoring import SCORING_PROMPT_TEMPLATE_ID

    assert SCORING_PROMPT_TEMPLATE_ID == "scoring_v1"


# ---------------------------------------------------------------------------
# Output hash test (1 additional test, for completeness)
# ---------------------------------------------------------------------------


def test_output_hash_is_sha256_of_raw_output():
    """compute_output_hash returns sha256(raw_output)[:16]."""
    import hashlib
    from packages.research.evaluation.artifacts import compute_output_hash

    raw = '{"relevance": 3, "total": 12}'
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    assert compute_output_hash(raw) == expected
    assert len(compute_output_hash(raw)) == 16


def test_prompt_hash_in_provider_event(tmp_path):
    """score_document_with_metadata prompt_hash matches sha256(prompt)[:12]."""
    import hashlib
    from packages.research.evaluation.types import EvalDocument
    from packages.research.evaluation.providers import ManualProvider
    from packages.research.evaluation.scoring import build_scoring_prompt, score_document_with_metadata

    doc = EvalDocument(
        doc_id="hash_test",
        title="Hash Test",
        author="A",
        source_type="manual",
        source_url="",
        source_publish_date=None,
        body=_LONG_BODY,
    )
    provider = ManualProvider()
    result, raw_output, prompt_hash = score_document_with_metadata(doc, provider)

    prompt = build_scoring_prompt(doc)
    expected_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    assert prompt_hash == expected_hash
    assert len(prompt_hash) == 12


def test_document_evaluator_records_provider_event(tmp_path):
    """DocumentEvaluator.evaluate() records provider_event in persisted artifact."""
    from packages.research.evaluation.types import EvalDocument
    from packages.research.evaluation.providers import ManualProvider
    from packages.research.evaluation.evaluator import DocumentEvaluator
    from packages.research.evaluation.artifacts import load_eval_artifacts

    doc = EvalDocument(
        doc_id="eval_pe_test",
        title="Evaluator PE Test",
        author="A",
        source_type="manual",
        source_url="",
        source_publish_date=None,
        body=_LONG_BODY,
    )
    evaluator = DocumentEvaluator(provider=ManualProvider(), artifacts_dir=tmp_path)
    decision = evaluator.evaluate(doc)

    assert decision.gate == "ACCEPT"

    arts = load_eval_artifacts(tmp_path)
    assert len(arts) == 1
    art = arts[0]

    # provider_event must be present and populated
    pe = art.get("provider_event")
    assert pe is not None
    assert pe["provider_name"] == "manual"
    assert pe["prompt_template_id"] == "scoring_v1"
    assert pe["output_hash"] is not None

    # event_id must be present
    assert art.get("event_id") is not None
