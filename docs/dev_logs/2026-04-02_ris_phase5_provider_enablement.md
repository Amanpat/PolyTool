# Dev Log: RIS Phase 5 — Controlled Provider Enablement with Replay-Grade Auditability

**Date:** 2026-04-02
**Plan:** quick-260402-rmz
**Status:** Complete

## Summary

Delivered RIS Phase 5: controlled LLM provider enablement, replay-grade metadata capture,
structured diff workflow, and CLI extension. The evaluation pipeline can now be replayed
deterministically against any document for A/B provider comparison and audit.

## What Was Built

### 1. Provider Metadata + Cloud Guard (`providers.py`)

- Added `_LOCAL_PROVIDERS`, `_CLOUD_GUARD_ENV_VAR`, `_CLOUD_PROVIDERS` module-level constants.
- Added `model_id` and `generation_params` properties to `ManualProvider` and `OllamaProvider`.
- Restructured `get_provider()` as a three-way branch:
  - Local names → instantiate immediately (no env var required).
  - Known cloud names → require `RIS_ENABLE_CLOUD_PROVIDERS=1` (PermissionError if absent),
    then raise ValueError as "recognized but not yet implemented" (RIS v2 deliverable).
  - Completely unknown names → raise ValueError with `"unknown provider"` prefix
    (preserves backward compat for existing tests expecting this exact message).
- Added `get_provider_metadata(provider)` factory function returning
  `{provider_name, model_id, generation_params}` for replay-grade capture.

### 2. Scoring Template Versioning (`scoring.py`)

- Added `SCORING_PROMPT_TEMPLATE_ID = "scoring_v1"` constant.
- Added `score_document_with_metadata(doc, provider) -> Tuple[ScoringResult, str, str]`
  that returns `(result, raw_output, prompt_hash)` where `prompt_hash = sha256(prompt_text)[:12]`.
- Original `score_document()` preserved unchanged for backward compat.

### 3. Artifact Metadata (`artifacts.py`)

- Added `ProviderEvent` dataclass: 9 fields capturing provider identity, template version,
  generation params, source chunk refs, timestamp, output hash, and optional raw_output.
- Added `generate_event_id(doc_id, timestamp, provider_name) -> str`: `sha256(...)[:16]`.
- Added `compute_output_hash(raw_output) -> str`: `sha256(raw_output)[:16]`.
- Added two optional backward-compatible fields to `EvalArtifact`:
  `provider_event: Optional[dict] = None` and `event_id: Optional[str] = None`.

### 4. Evaluator Pipeline (`evaluator.py`)

- Replaced `score_document()` call with `score_document_with_metadata()`.
- After scoring: builds `ProviderEvent`, generates `event_id`, attaches both to `EvalArtifact`.
- Hard-stop and dedup early-return paths pass `provider_event=None, event_id=None`.
- Fully backward compatible: no changes needed if `artifacts_dir` is not set.

### 5. Replay Module (`replay.py`, new)

- `ReplayDiff` dataclass: structured diff between original and replay evaluations.
- `replay_eval(doc, provider_name, artifacts_dir, **kwargs)`: thin wrapper returning
  `(GateDecision, provider_event_dict)` for replay chaining.
- `compare_eval_events(orig, replay)`: diffs all 5 score dims + gate change detection.
- `persist_replay_diff(diff, artifacts_dir)`: writes to `{artifacts_dir}/replay_diffs/`.
- `load_replay_diffs(artifacts_dir)`: sorted by `replay_timestamp` ascending.
- `find_artifact_by_event_id(event_id, artifacts_dir)`: scans JSONL for first match.

### 6. CLI Extension (`tools/cli/research_eval.py`)

- Subcommand routing: `eval`, `replay`, `list-providers`.
- Backward compat: if `argv[0]` not in `_KNOWN_SUBCOMMANDS`, route to `_cmd_eval()`.
- `--enable-cloud` flag: sets `RIS_ENABLE_CLOUD_PROVIDERS=1` for the process lifetime.
- `eval` output now includes `provider_event` and `event_id` when artifacts are persisted.
- `replay` subcommand: loads original artifact by `--event-id`, re-runs evaluation,
  computes `ReplayDiff`, persists and prints diff JSON.
- `list-providers` subcommand: shows all providers with enablement status.

### 7. Test Suite (`tests/test_ris_phase5_provider_enablement.py`)

20 deterministic offline tests covering:
- Cloud guard behavior (4 tests)
- Provider metadata (2 tests)
- Replay metadata in artifacts (3 tests)
- ReplayDiff workflow (4 tests)
- CLI routing (3 tests)
- Scoring template ID, output hash, prompt hash (3 tests)
- DocumentEvaluator integration (1 test)

## Deviations

### Auto-fixed (Rule 1 — Bug): providers.py three-way branching

**Found during:** Task 6 regression run
**Issue:** Initial `get_provider()` implementation used `else:` for all non-local providers.
This raised `PermissionError` (cloud guard) for completely unknown names like
`"nonexistent_provider_xyz"`, breaking `test_get_provider_factory_unknown_raises`
which expected `ValueError` with `"unknown provider"` for unknown names.
**Fix:** Split into three branches:
  1. `if name in _LOCAL_PROVIDERS` — instantiate directly
  2. `elif name in _CLOUD_PROVIDERS` — cloud guard then not-implemented ValueError
  3. `else` — unknown provider ValueError with `"unknown provider"` prefix
**Files:** `packages/research/evaluation/providers.py`
**Commit:** f79fd0c

## Regression Results

- 3215 passed, 0 failures (live network tests deselected with `-k "not live"`)
- Pre-existing: `test_ris_fetchers.py::TestLiveSmoke::test_blog_live` —
  network timeout, unrelated to Phase 5

## Commits

| Hash    | Message |
|---------|---------|
| fefbabe | feat(quick-260402-rmz-02): cloud provider guard, provider metadata, scoring template ID |
| deb4fd7 | feat(quick-260402-rmz-03): wire ProviderEvent replay metadata into evaluator pipeline |
| a6e7490 | feat(quick-260402-rmz-04): add replay.py -- ReplayDiff, compare_eval_events, persist/load helpers |
| 994a8a9 | feat(quick-260402-rmz-05): extend research-eval CLI with cloud guard UX and replay subcommand |
| f79fd0c | feat(quick-260402-rmz-06): Phase 5 test suite and providers.py backward-compat fix |

## Codex Review

Tier: Recommended (autoresearch engine file). Result: No issues found.
`providers.py`, `scoring.py`, `evaluator.py`, `replay.py` reviewed — clean.
