# Dev Log: RIS Phase 2 Evaluation Gate Core

**Date:** 2026-04-08
**Task:** 260408-i0y — Implement Phase 2 RIS Evaluation Gate Core Contract

---

## Objective

Replace the simple sum /20 gate (total >= 12 = ACCEPT) with a weighted composite gate that is:
- Config-driven (weights, floors, thresholds from `config/ris_eval_config.json`)
- Fail-closed (any provider exception or parse failure -> REJECT)
- Per-dimension floor enforced (relevance >= 2, credibility >= 2)
- Per-priority threshold applied (P1=2.5, P2=3.0, P3=3.2, P4=3.5)
- Floor-waivable for priority_1 tier (trusted sources)

---

## What Was Built

### New Files

**`config/ris_eval_config.json`**
Canonical gate parameter file. Contains scoring weights, per-dimension floors,
floor_waive_tiers, per-priority acceptance thresholds, and defaults. Env vars
override these values at runtime (RIS_EVAL_*).

**`packages/research/evaluation/config.py`**
EvalConfig frozen dataclass. `load_eval_config()` reads the JSON file and applies
env-var overrides. `get_eval_config()` returns a module-level cached instance.
`reset_eval_config()` clears the cache for test isolation. Config path resolves
relative to the package file so it works regardless of cwd.

**`tests/test_ris_phase2_weighted_gate.py`**
51 TDD tests covering: composite formula, priority thresholds, floor enforcement,
floor waiver for priority_1, scorer failure handling, ManualProvider -> REVIEW,
config loading + env-var overrides + cache behavior, evaluator fail-closed,
artifact field presence, and priority_tier kwarg on evaluate_document().

### Modified Files

**`packages/research/evaluation/types.py`**
- ScoringResult: added `composite_score: float = 0.0`, `priority_tier: str = "priority_3"`,
  `reject_reason: Optional[str] = None`
- `simple_sum_score` property: diagnostic alias for `total` (never drives gate)
- `gate` property: replaced `total >= 12` with weighted composite + floor + threshold logic

**`packages/research/evaluation/scoring.py`**
- `SCORING_PROMPT_TEMPLATE_ID` bumped to `"scoring_v2"` (prompt gate rubric changed)
- `_compute_composite()`: reads weights from config at call time (respects env-var overrides)
- `parse_scoring_response()`: on parse failure returns `reject_reason="scorer_failure"`,
  `composite_score=_compute_composite(1,1,1,1)`; on success computes composite
- `build_scoring_prompt()`: GATE THRESHOLDS section updated to describe weighted composite

**`packages/research/evaluation/evaluator.py`**
- `DocumentEvaluator.__init__()`: added `priority_tier: Optional[str] = None` param
- Scoring step: wrapped in `try/except Exception`; on exception constructs fail-closed
  ScoringResult with `reject_reason="scorer_failure"` instead of propagating
- After scoring: applies `priority_tier` to `scores` via `dataclasses.replace()`
- `scores_dict` for artifact persistence: added `composite_score`, `simple_sum_score`,
  `priority_tier`, `reject_reason`
- `evaluate_document()`: added `priority_tier` kwarg, passed to `DocumentEvaluator`

**`tools/cli/research_eval.py`**
- Added `--priority-tier` arg (choices: priority_1..priority_4)
- Wired to `evaluate_document()` call
- JSON output `scores` dict now includes: `composite_score`, `simple_sum_score`,
  `priority_tier`, `reject_reason`

**`tools/cli/research_ingest.py`**
- Added `--priority-tier` arg
- Wired to `DocumentEvaluator(priority_tier=...)`
- JSON output `scores` dict now includes Phase 2 fields

**`tools/cli/research_acquire.py`**
- Added `--priority-tier` arg
- Wired to `DocumentEvaluator(priority_tier=...)`

### Test Files Updated (behavior change)

- `tests/test_ris_evaluation.py`: `TestScoringResultGate` rewritten to use composite-based
  assertions; `test_valid_doc_with_manual_provider_returns_accept` renamed and updated to
  assert `gate == "REVIEW"` (ManualProvider all-3s -> composite=3.0 < P3 threshold 3.2)
- `tests/test_ris_phase5_provider_enablement.py`: three assertions updated:
  `scoring_v1` -> `scoring_v2`, `gate == "ACCEPT"` -> `gate == "REVIEW"` (2 occurrences)
- `tests/test_ris_ingestion_integration.py`: `test_pipeline_ingest_with_eval` updated
  to assert `gate == "REVIEW"` (same ManualProvider behavior change)

---

## Key Design Decisions

### ManualProvider now gates as REVIEW

ManualProvider returns all-3s (composite = 3*0.30 + 3*0.25 + 3*0.25 + 3*0.20 = 3.0).
This is below the P3 threshold of 3.2, so documents evaluated with ManualProvider
now gate as REVIEW instead of ACCEPT. This is intentional — it forces human review
rather than silently accepting documents with placeholder scores. To accept a document
via ManualProvider, use `--priority-tier priority_1` (threshold 2.5, floor-waived).

### Config-driven, not hardcoded

All gate parameters live in `config/ris_eval_config.json`. Env vars (RIS_EVAL_*)
override file values at runtime. The config cache is reset between tests that manipulate
env vars. This means gate behavior can be tuned without code changes.

### Fail-closed on both parse failure and provider exception

Two independent fail-closed paths:
1. `parse_scoring_response()`: malformed JSON -> returns ScoringResult with reject_reason="scorer_failure"
2. `DocumentEvaluator.evaluate()`: any exception from `score_document_with_metadata()` ->
   constructs a fail-closed ScoringResult in the except block

This means network errors, timeouts, and provider bugs all result in REJECT, not crashes.

### SCORING_PROMPT_TEMPLATE_ID bumped to scoring_v2

The gate rubric in the prompt changed (simple sum -> weighted composite). Bumping the
template ID enables drift detection in replay artifacts — comparing an old artifact
(scoring_v1) against a new eval (scoring_v2) will surface the rubric change in diffs.

---

## Verification

```
pytest tests/test_ris_phase2_weighted_gate.py tests/test_ris_evaluation.py \
       tests/test_ris_phase5_provider_enablement.py -q
# 112 passed

pytest tests/ -q
# 3750 passed, 0 failed
```

Config verified:
```python
cfg = get_eval_config()
# weights: {'relevance': 0.3, 'novelty': 0.25, 'actionability': 0.25, 'credibility': 0.2}
# floors: {'relevance': 2, 'credibility': 2}
# floor_waive_tiers: ('priority_1',)
# thresholds: {'priority_1': 2.5, 'priority_2': 3.0, 'priority_3': 3.2, 'priority_4': 3.5}
```

Gate logic verified:
```python
_compute_composite(3,3,3,3)  # -> 3.0 (all-3s -> REVIEW for P3)
_compute_composite(5,5,5,5)  # -> 5.0

# floor-fail (rel=1): REJECT even with composite=3.5
# composite=3.0 P3: REVIEW
# composite=3.0 P1: ACCEPT (floor waived, threshold 2.5)
```

---

## Codex Review

Tier: Recommended (evaluator.py modified).
Result: Not run (evaluation module, not execution/risk path). No execution, kill-switch,
or order placement code touched.

---

## Commits

- `c87bc04` feat(260408-i0y): implement Phase 2 RIS weighted composite gate core
- `74d2af6` feat(260408-i0y): evaluator fail-closed + CLI priority_tier + Phase 2 output fields
