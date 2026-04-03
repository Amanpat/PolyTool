---
phase: quick-260402-rmz
plan: "01"
subsystem: research-evaluation
tags: [ris, evaluation, provider-guard, replay, auditability, cloud-guard]
dependency_graph:
  requires: [artifacts.py, providers.py, scoring.py, evaluator.py]
  provides: [replay.py, cloud-guard, provider-metadata, ReplayDiff, research-eval CLI subcommands]
  affects: [evaluation pipeline, artifact JSONL schema, research-eval CLI]
tech_stack:
  added: [hashlib (stdlib), dataclasses.field defaults]
  patterns: [three-way factory routing, replay-grade metadata capture, backward-compat optional fields]
key_files:
  created:
    - packages/research/evaluation/replay.py
    - tests/test_ris_phase5_provider_enablement.py
    - docs/dev_logs/2026-04-02_ris_phase5_provider_enablement.md
  modified:
    - packages/research/evaluation/artifacts.py
    - packages/research/evaluation/providers.py
    - packages/research/evaluation/scoring.py
    - packages/research/evaluation/evaluator.py
    - tools/cli/research_eval.py
decisions:
  - "Cloud providers gated behind RIS_ENABLE_CLOUD_PROVIDERS=1 env var; recognized but not-yet-implemented raises ValueError after guard passes"
  - "Three-way get_provider() branch preserves existing ValueError('unknown provider') behavior for completely unknown names"
  - "prompt_template_version = sha256(prompt_text)[:12] — lightweight identity, not full hash"
  - "event_id = sha256(doc_id + timestamp + provider_name)[:16] — deterministic and unique per run"
  - "raw_output=None in ProviderEvent by default to keep artifact JSONL lightweight"
  - "Backward compat for CLI: argv[0] not in _KNOWN_SUBCOMMANDS routes to legacy _cmd_eval()"
metrics:
  duration: ~90 minutes
  completed: "2026-04-03T00:19:57Z"
  tasks_completed: 6
  tasks_planned: 6
  files_created: 3
  files_modified: 5
---

# Phase quick-260402-rmz Plan 01: RIS Phase 5 Provider Enablement Summary

**One-liner:** Cloud provider guard (RIS_ENABLE_CLOUD_PROVIDERS=1) with replay-grade ProviderEvent metadata, ReplayDiff workflow, and research-eval CLI subcommands (eval/replay/list-providers).

## What Was Built

### Cloud Provider Guard

`providers.py` now routes `get_provider()` through a three-way branch:
1. Local providers (`manual`, `ollama`) — instantiate directly, no env vars required.
2. Known cloud providers (`gemini`, `deepseek`, `openai`, `anthropic`) — require `RIS_ENABLE_CLOUD_PROVIDERS=1`; raise PermissionError if absent; raise ValueError as "recognized but not yet implemented" when env var is set (RIS v2 deliverable).
3. Completely unknown names — raise ValueError with `"unknown provider"` prefix (backward compat preserved).

`get_provider_metadata(provider)` returns `{provider_name, model_id, generation_params}` for any provider instance.

### Replay-Grade Artifact Metadata

`artifacts.py` gains:
- `ProviderEvent` dataclass (9 fields): `provider_name`, `model_id`, `prompt_template_id`, `prompt_template_version` (sha256[:12] of prompt), `generation_params`, `source_chunk_refs`, `timestamp`, `output_hash` (sha256[:16] of raw output), `raw_output` (Optional, default None).
- `generate_event_id(doc_id, timestamp, provider_name) -> str`: sha256[:16] — unique per scoring run.
- `compute_output_hash(raw_output) -> str`: sha256[:16] — integrity fingerprint.
- `EvalArtifact` extended with two Optional fields (`provider_event`, `event_id`) defaulting to None for full backward compat.

`scoring.py` gains `SCORING_PROMPT_TEMPLATE_ID = "scoring_v1"` and `score_document_with_metadata()` returning `(ScoringResult, raw_output, prompt_hash)`.

### Evaluator Pipeline

`evaluator.py` wires everything together: calls `score_document_with_metadata()`, builds `ProviderEvent`, generates `event_id`, attaches both to persisted `EvalArtifact`. Hard-stop and dedup paths pass `provider_event=None, event_id=None` for backward compat.

### Replay Module (`replay.py`)

New module providing:
- `ReplayDiff` dataclass: structured diff with `diff_fields`, `gate_changed`, provider/template identity for both sides.
- `replay_eval(doc, provider_name, artifacts_dir, **kwargs)` — evaluate and return `(GateDecision, provider_event_dict)`.
- `compare_eval_events(orig, replay)` — compares all 5 score dims, detects gate change.
- `persist_replay_diff(diff, artifacts_dir)` — writes to `{artifacts_dir}/replay_diffs/`.
- `load_replay_diffs(artifacts_dir)` — sorted ascending by `replay_timestamp`.
- `find_artifact_by_event_id(event_id, artifacts_dir)` — JSONL scan helper.

### CLI Extension (`research_eval.py`)

Subcommand routing with backward compat fallback:
- `eval` — full evaluation with `--provider`, `--enable-cloud`; output includes `provider_event` and `event_id`.
- `replay` — requires `--event-id` and `--artifacts-dir`; produces and prints `ReplayDiff` JSON.
- `list-providers` — shows all providers with enablement status.

Backward compat: invocation without a recognized subcommand routes to `_cmd_eval()`.

## Test Suite

`tests/test_ris_phase5_provider_enablement.py` — 20 deterministic offline tests, no network calls.

Coverage:
- Cloud guard: blocked without env var, passes with env var, known cloud names, env var name constant
- Provider metadata: ManualProvider and OllamaProvider metadata dicts
- Artifacts: provider_event persisted, event_id is deterministic, backward compat (old EvalArtifact without new fields)
- Replay workflow: compare_eval_events detects diffs and no-diff, persist+load round trip, find_artifact_by_event_id
- CLI: backward compat routing, cloud guard block, replay fails on missing args
- Hashing: SCORING_PROMPT_TEMPLATE_ID constant, output_hash sha256[:16], prompt_hash in provider_event

All 3215 offline tests pass (3215 passed, 0 failed; 137 live network tests deselected).

## Commits

| Hash    | Description |
|---------|-------------|
| fefbabe | feat(quick-260402-rmz-02): cloud provider guard, provider metadata, scoring template ID |
| deb4fd7 | feat(quick-260402-rmz-03): wire ProviderEvent replay metadata into evaluator pipeline |
| a6e7490 | feat(quick-260402-rmz-04): add replay.py -- ReplayDiff, compare_eval_events, persist/load helpers |
| 994a8a9 | feat(quick-260402-rmz-05): extend research-eval CLI with cloud guard UX and replay subcommand |
| f79fd0c | feat(quick-260402-rmz-06): Phase 5 test suite and providers.py backward-compat fix |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed get_provider() backward compat for unknown provider names**
- **Found during:** Task 6 (regression suite)
- **Issue:** Initial Task 2 implementation used a single `else:` branch for all non-local providers, raising `PermissionError` for completely unknown names. This broke `test_get_provider_factory_unknown_raises` which expected `ValueError("unknown provider")` for unrecognized names.
- **Fix:** Split into three branches: local providers (direct instantiate), known cloud providers (guard + not-implemented), unknown names (ValueError with "unknown provider" prefix).
- **Files modified:** `packages/research/evaluation/providers.py`
- **Commit:** f79fd0c

## Known Stubs

None. All evaluation, replay, and CLI paths are fully wired. Cloud provider implementations are explicitly deferred as RIS v2 deliverables (not stubs — they raise descriptive errors by design).

## Self-Check: PASSED

Files verified:
- packages/research/evaluation/replay.py — EXISTS
- packages/research/evaluation/artifacts.py — EXISTS (modified)
- packages/research/evaluation/providers.py — EXISTS (modified)
- packages/research/evaluation/scoring.py — EXISTS (modified)
- packages/research/evaluation/evaluator.py — EXISTS (modified)
- tools/cli/research_eval.py — EXISTS (modified)
- tests/test_ris_phase5_provider_enablement.py — EXISTS
- docs/dev_logs/2026-04-02_ris_phase5_provider_enablement.md — EXISTS

Commits verified: fefbabe, deb4fd7, a6e7490, 994a8a9, f79fd0c — all present in git log.
