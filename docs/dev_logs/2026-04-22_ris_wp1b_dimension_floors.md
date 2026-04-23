---
date: 2026-04-22
work_packet: WP1-B
phase: RIS Phase 2A
slug: ris_wp1b_dimension_floors
---

# WP1-B: Four-dimension floor contract

## Objective

Extend the RIS gate floor contract from two dimensions (relevance, credibility) to all
four scoring dimensions (relevance, novelty, actionability, credibility), each at floor
value 2. This closes the gap where a document with novelty=1 or actionability=1 could
still pass the gate as ACCEPT or REVIEW despite being obviously weak on those axes.

## Root cause

The initial Phase 2 implementation wired only relevance and credibility into the floor
contract at three surfaces:

1. `_DEFAULT_FLOORS` in `config.py` — two-key dict
2. File-loading loop in `load_eval_config()` — iterated only `("relevance", "credibility")`
3. `config/ris_eval_config.json` — `floors` block had two keys only
4. Scoring prompt text in `scoring.py` — named only relevance and credibility floors

The `gate` property in `types.py` was already generic (`for dim, floor_val in cfg.floors.items()`)
so no change to evaluation logic was needed — only the contract/config surfaces.

## Before / after floor contract

| Dimension     | Before | After |
|---------------|--------|-------|
| relevance     | 2      | 2     |
| novelty       | —      | 2     |
| actionability | —      | 2     |
| credibility   | 2      | 2     |

## Files changed

| File | Change |
|---|---|
| `packages/research/evaluation/config.py` | `_DEFAULT_FLOORS` expanded to 4 dims; file-loading loop expanded to all 4 dims; env-var overrides added for `RIS_EVAL_NOVELTY_FLOOR` and `RIS_EVAL_ACTIONABILITY_FLOOR`; module docstring updated |
| `config/ris_eval_config.json` | `scoring.floors` block now has all 4 dimensions |
| `packages/research/evaluation/scoring.py` | Prompt text updated from "relevance >= 2 and credibility >= 2" to all four dimensions |
| `tests/test_ris_phase2_weighted_gate.py` | `test_default_config_floors` updated to assert all four floor keys |
| `tests/test_ris_wp1b_dimension_floors.py` | New targeted test file (24 tests) |

## Where runtime truth lived before the fix

All three surfaces had to agree for the floor to be enforced. The JSON file was the
persisted runtime contract (loaded on startup); `_DEFAULT_FLOORS` was the fallback when
the file was absent or malformed; the file-loading loop gated what the file could
override; and the env-var section allowed per-deployment overrides. All four were
two-dimensional before WP1-B.

## What was NOT touched

- `types.py` — gate logic already iterated `cfg.floors.items()` generically
- Scoring weights (WP1-A already closed)
- Provider events contract (WP1-C/WP1-D scope)
- Research seed behavior
- Cloud provider routing
- n8n / monitoring / Hermes files

## Commands run + results

```
Targeted (96 tests):
  tests/test_ris_wp1b_dimension_floors.py   24 passed
  tests/test_ris_phase2_weighted_gate.py    52 passed  (+1 from floor assertion update)
  tests/test_ris_wp1a_scoring_weights.py    22 passed  (no change, no regression)
  Total: 96 passed (0.46s)

Full suite:
  2332 passed, 1 failed, 3 deselected (65s)
```

The 1 full-suite failure (`test_each_claim_has_required_fields`) is pre-existing
from commit `2d926c6` (heuristic extractor v2 bump). Not caused by WP1-B.

## Codex review

Tier: Skip (config and evaluation plumbing, no execution path). No review required
per CLAUDE.md policy.

## Open questions / next steps

- **WP1-D**: R0 seed (11+ docs). Verify `research-seed` works end-to-end with the
  now-complete four-floor contract before committing seed content.
- **WP1-E**: 5 open-source docs seeded into the knowledge store.
- Neither WP1-D nor WP1-E touch the floor/weight/config surfaces — the contract is now
  stable for seeding.
