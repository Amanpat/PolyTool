---
date: 2026-04-22
work_packet: WP1-B (follow-up)
phase: RIS Phase 2A
slug: ris_wp1b_prompt_floor_drift_fix
---

# WP1-B Follow-up: Prompt Floor Drift Fix

## Problem

`build_scoring_prompt()` hardcoded floor text to `>= 2` for all four dimensions
regardless of what the gate actually enforces at runtime. When an operator sets
`RIS_EVAL_NOVELTY_FLOOR=3`, the gate rejects at `novelty < 3` but the prompt
told the LLM `novelty >= 2 are required for acceptance`. The model was therefore
given incorrect guidance about the acceptance criteria.

This was identified by Codex adversarial review
(`docs/dev_logs/2026-04-22_ris_wp1b_codex_verification.md`), which produced
this runtime proof:

```text
cfg_floors= {'relevance': 2, 'novelty': 3, 'actionability': 3, 'credibility': 2}
prompt_line=   Per-dimension floors: relevance >= 2, novelty >= 2, actionability >= 2, and credibility >= 2 are required for acceptance.
gate= REJECT
```

## Fix

`build_scoring_prompt()` in `packages/research/evaluation/scoring.py` now derives
floor text from `get_eval_config()` at call time, using the same lazy-import
pattern already established by `_compute_composite()`.

Before:
```python
"  Per-dimension floors: relevance >= 2, novelty >= 2, actionability >= 2, and credibility >= 2 are required for acceptance.",
```

After:
```python
from packages.research.evaluation.config import get_eval_config
_cfg = get_eval_config()
_floor_parts = [f"{dim} >= {val}" for dim, val in _cfg.floors.items()]
_floor_text = (
    ", ".join(_floor_parts[:-1]) + ", and " + _floor_parts[-1]
    if len(_floor_parts) > 1
    else (_floor_parts[0] if _floor_parts else "")
)
...
f"  Per-dimension floors: {_floor_text} are required for acceptance.",
```

## Files changed

| File | Change |
|---|---|
| `packages/research/evaluation/scoring.py` | `build_scoring_prompt()` derives floor text from live config instead of hardcoded `>= 2` |
| `tests/test_ris_wp1b_prompt_floor_drift.py` | New targeted test file (9 tests) |

## What was NOT touched

- `config.py` — no change; env-var overrides already wired from WP1-B
- `config/ris_eval_config.json` — no change
- `types.py` — no change; gate logic already correct
- Weights, seed behavior, provider routing, n8n / infra / Hermes

## Commands run + results

```text
Targeted (84 tests):
  tests/test_ris_wp1b_prompt_floor_drift.py    9 passed   (new)
  tests/test_ris_wp1b_dimension_floors.py     24 passed
  tests/test_ris_phase2_weighted_gate.py      51 passed
  Total: 84 passed (0.31s)

Full suite:
  4218 passed, 11 failed, 3 deselected (99s)
```

The 11 full-suite failures are pre-existing:
- 3 in `test_ris_claim_extraction.py` — pre-existing from commit `2d926c6` (heuristic extractor v2 bump)
- 8 in `test_ris_phase2_cloud_provider_routing.py` — pre-existing cloud provider routing failures

None caused by this change.

## Codex review

Tier: Skip (prompt text plumbing, no execution path). No review required
per CLAUDE.md policy.

## Open questions / next steps

- WP1-B is now fully closed: gate enforcement, prompt text, and tests are all
  aligned across default config and env-var override paths.
- WP1-D (R0 seed, 11+ docs) is unblocked.
