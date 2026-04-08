---
phase: quick
plan: 260408-i0y
subsystem: ris-evaluation
tags: [ris, evaluation, gate, scoring, phase2, weighted-composite, config, fail-closed]
dependency_graph:
  requires: []
  provides: [ris-phase2-weighted-gate, ris-eval-config, ris-fail-closed-scoring]
  affects: [research-ingest, research-acquire, research-eval-cli, ris-artifacts]
tech_stack:
  added: [config/ris_eval_config.json, packages/research/evaluation/config.py]
  patterns: [frozen-dataclass-config, module-level-cache, fail-closed-exception-handling, tdd-red-green]
key_files:
  created:
    - config/ris_eval_config.json
    - packages/research/evaluation/config.py
    - tests/test_ris_phase2_weighted_gate.py
  modified:
    - packages/research/evaluation/types.py
    - packages/research/evaluation/scoring.py
    - packages/research/evaluation/evaluator.py
    - tools/cli/research_eval.py
    - tools/cli/research_ingest.py
    - tools/cli/research_acquire.py
    - tests/test_ris_evaluation.py
    - tests/test_ris_phase5_provider_enablement.py
    - tests/test_ris_ingestion_integration.py
decisions:
  - ManualProvider all-3s (composite=3.0) now gates as REVIEW not ACCEPT -- forces operator review
  - SCORING_PROMPT_TEMPLATE_ID bumped to scoring_v2 for replay drift detection
  - Fail-closed in two layers: parse_scoring_response and DocumentEvaluator.evaluate
  - Config-driven gate params with env-var overrides and reset_eval_config() for test isolation
  - priority_tier="priority_1" waives floor checks (trusted internal sources)
metrics:
  duration: ~45 minutes
  completed: 2026-04-08
  tasks_completed: 2
  tasks_planned: 2
  files_created: 3
  files_modified: 9
  tests_added: 51
  tests_total_after: 3750
---

# Phase quick Plan 260408-i0y: RIS Phase 2 Weighted Composite Gate Core Summary

**One-liner:** Weighted composite gate (rel*0.30 + nov*0.25 + act*0.25 + cred*0.20) with per-dimension floors, per-priority thresholds, fail-closed evaluation, and config-driven defaults replacing the simple sum /20 gate.

---

## What Was Built

### Task 1: Config, Types, Scoring Core (TDD)

**`config/ris_eval_config.json`** — canonical gate parameter file with weights, floors, floor_waive_tiers, per-priority acceptance thresholds (P1=2.5, P2=3.0, P3=3.2, P4=3.5), and defaults.

**`packages/research/evaluation/config.py`** — `EvalConfig` frozen dataclass, `load_eval_config()` with file + env-var override chain, `get_eval_config()` module-level cache, `reset_eval_config()` for test isolation.

**`packages/research/evaluation/types.py`** — `ScoringResult` gains `composite_score`, `priority_tier`, `reject_reason`. The `gate` property now uses weighted composite + floor check + priority threshold instead of `total >= 12`.

**`packages/research/evaluation/scoring.py`** — `_compute_composite()` uses weights from config. `SCORING_PROMPT_TEMPLATE_ID` bumped to `"scoring_v2"`. `parse_scoring_response()` is fail-closed: malformed JSON returns `reject_reason="scorer_failure"`. Prompt gate section updated to describe weighted composite.

**`tests/test_ris_phase2_weighted_gate.py`** — 51 TDD tests: composite formula, all four priority tiers, floor enforcement, floor waiver (priority_1), scorer failure, ManualProvider->REVIEW, config loading, env-var overrides, evaluator fail-closed (ConnectionError, ValueError, garbage output), artifact field presence, priority_tier kwarg.

### Task 2: Evaluator Fail-Closed + CLI

**`packages/research/evaluation/evaluator.py`** — `DocumentEvaluator` gains `priority_tier` param. Scoring step wrapped in `try/except Exception`; provider exceptions construct a fail-closed `ScoringResult` instead of propagating. `scores_dict` for artifact persistence includes `composite_score`, `simple_sum_score`, `priority_tier`, `reject_reason`.

**`tools/cli/research_eval.py`** — `--priority-tier` arg; JSON output includes Phase 2 score fields.

**`tools/cli/research_ingest.py`** — `--priority-tier` arg wired to evaluator; JSON output includes Phase 2 score fields.

**`tools/cli/research_acquire.py`** — `--priority-tier` arg wired to evaluator.

---

## Decisions Made

1. **ManualProvider -> REVIEW**: All-3s composite (3.0) falls below P3 threshold (3.2). This is intentional — forces operator review instead of silent acceptance. Use `--priority-tier priority_1` to accept ManualProvider output (threshold 2.5).

2. **Template ID bump**: `SCORING_PROMPT_TEMPLATE_ID` changed from `"scoring_v1"` to `"scoring_v2"` because the gate rubric in the prompt changed. Replay artifacts comparing old (v1) to new (v2) evals will surface the rubric change.

3. **Two fail-closed layers**: Parse failure in `parse_scoring_response()` and provider exception in `DocumentEvaluator.evaluate()` both produce REJECT with `reject_reason="scorer_failure"`. Belt-and-suspenders.

4. **Config-driven, not hardcoded**: All gate parameters in `config/ris_eval_config.json`. Env vars override. Module-level cache with `reset_eval_config()` for test isolation. Gate behavior tunable without code changes.

5. **Floor waiver for priority_1**: Internal/trusted sources (reference_doc, roadmap mapped to book_foundational) can use `priority_tier="priority_1"` to bypass floor checks and apply the lower 2.5 threshold.

---

## Test Results

```
pytest tests/test_ris_phase2_weighted_gate.py tests/test_ris_evaluation.py \
       tests/test_ris_phase5_provider_enablement.py -q
# 112 passed

pytest tests/ -q
# 3750 passed, 0 failed
```

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing] test_ris_ingestion_integration.py also had stale ACCEPT assertion**
- **Found during:** Task 2 full suite run
- **Issue:** `test_pipeline_ingest_with_eval` asserted `gate == "ACCEPT"` for ManualProvider; broke with Phase 2 behavior change
- **Fix:** Updated assertion to `gate == "REVIEW"` with explanatory comment
- **Files modified:** `tests/test_ris_ingestion_integration.py`
- **Commit:** c87bc04

None other — plan executed as written.

---

## Known Stubs

None. All gate logic is wired through config. ManualProvider is a deliberate placeholder that gates as REVIEW by design.

---

## Threat Flags

None. No new network endpoints, auth paths, or trust boundary changes introduced. Config file is read-only at runtime (no writes).

---

## Commits

| Hash | Message |
|------|---------|
| c87bc04 | feat(260408-i0y): implement Phase 2 RIS weighted composite gate core |
| 74d2af6 | feat(260408-i0y): evaluator fail-closed + CLI priority_tier + Phase 2 output fields |

---

## Self-Check: PASSED

- config/ris_eval_config.json: EXISTS
- packages/research/evaluation/config.py: EXISTS
- packages/research/evaluation/types.py: MODIFIED (composite_score, priority_tier, reject_reason, gate rewrite)
- packages/research/evaluation/scoring.py: MODIFIED (scoring_v2, _compute_composite, fail-closed parse)
- packages/research/evaluation/evaluator.py: MODIFIED (fail-closed, priority_tier param, Phase 2 artifact fields)
- tests/test_ris_phase2_weighted_gate.py: EXISTS (51 tests)
- All 3750 tests: PASSED
- Commits c87bc04, 74d2af6: EXIST
