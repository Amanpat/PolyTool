---
date: 2026-04-22
work_packet: WP1-A
phase: RIS Phase 2A
slug: ris_wp1a_scoring_weights
---

# WP1-A: Scoring weights update

## Objective

Update the canonical RIS scoring weights to the values ratified in
`Decision - RIS Evaluation Scoring Policy`:

| Dimension     | Old   | New   |
|---------------|-------|-------|
| relevance     | 0.30  | 0.30  |
| credibility   | 0.20  | 0.30  |
| novelty       | 0.25  | 0.20  |
| actionability | 0.25  | 0.20  |

## Root cause

The scoring policy was ratified after the initial implementation was written.
All three live runtime surfaces still held the old weights — the hardcoded
defaults, the JSON config file, and the inline fallbacks and prompt text in
`scoring.py`.

## Files changed

| File | Change |
|---|---|
| `packages/research/evaluation/config.py` | `_DEFAULT_WEIGHTS` updated; module docstring env-var defaults corrected |
| `config/ris_eval_config.json` | `scoring.weights` block updated to new canonical values |
| `packages/research/evaluation/scoring.py` | `_compute_composite()` docstring + fallback defaults updated; `build_scoring_prompt()` formula string updated |
| `tests/test_ris_phase2_weighted_gate.py` | `test_composite_formula_mixed_dims` expected value 3.50→3.60; `test_default_config_weights` assertions updated; 3 inline comments corrected |
| `tests/test_ris_evaluation.py` | Formula in docstring updated (result unchanged — all-3s composite = 3.0 regardless of weights that sum to 1.0) |
| `tests/test_ris_wp1a_scoring_weights.py` | New targeted WP1-A contract test file (22 tests) |

## Key invariants preserved

- **All-3s composite is still 3.0.** Weights sum to 1.0, so uniform-dim
  scores are weight-invariant. ManualProvider REVIEW behavior is unchanged.
- **`test_floor_at_minimum_passes` still ACCEPT.** Old: 3.50 >= 3.2.
  New: 2*0.30+5*0.20+5*0.20+2*0.30 = 3.20, exactly at the P3 threshold.
  Gate logic is `>=`, so ACCEPT is preserved.
- **`test_priority_1_floor_waived_low_dims` still ACCEPT.** New composite:
  1*0.30+1*0.20+5*0.20+5*0.30 = 3.00 >= 2.5 (P1 threshold).

## Test results

```
Targeted (112 tests):
  tests/test_ris_wp1a_scoring_weights.py   22 passed
  tests/test_ris_phase2_weighted_gate.py   51 passed
  tests/test_ris_evaluation.py             39 passed
  Total: 112 passed (0.44s)

Full suite:
  2332 passed, 1 failed, 3 deselected (63s)
```

The 1 full-suite failure (`test_each_claim_has_required_fields`) is pre-existing
from commit `2d926c6` (heuristic extractor v2 bump changed actor name). Not
caused by WP1-A.

## Codex review

Tier: Skip (config and evaluation plumbing, no execution path). No review
required per CLAUDE.md policy.

## Open questions / next steps

- WP1-B: per-dimension novelty/actionability floors still pending
- WP1-D: R0 seed (11+ docs) still pending
- WP1-E: 5 open-source docs seeded still pending
