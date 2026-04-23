---
date: 2026-04-22
work_packet: WP1-B
phase: RIS Phase 2A
slug: ris_wp1b_codex_verification
---

# WP1-B Codex Verification

## Scope

Read-only adversarial verification of the WP1-B four-dimension floor contract after landing.
No code, config, workflow, or infra files were modified. This log is the only file added.

## Files inspected

- `packages/research/evaluation/config.py`
- `config/ris_eval_config.json`
- `packages/research/evaluation/scoring.py`
- `packages/research/evaluation/types.py`
- `packages/research/evaluation/evaluator.py`
- `tools/cli/research_eval.py`
- `tests/test_ris_wp1b_dimension_floors.py`
- `tests/test_ris_phase2_weighted_gate.py`
- `tests/test_ris_evaluation.py`
- `tests/test_ris_wp1a_scoring_weights.py`
- `docs/dev_logs/2026-04-22_ris_wp1b_dimension_floors.md`

## What matched

- Runtime defaults expose all four floors in `packages/research/evaluation/config.py:41-46`.
- Runtime config loading reads all four persisted floor keys in `packages/research/evaluation/config.py:110-116`.
- Env-var overrides exist for novelty and actionability floors in `packages/research/evaluation/config.py:144-147`.
- Persisted config exposes all four floors in `config/ris_eval_config.json:10-15`.
- The default scorer prompt text names all four floors in `packages/research/evaluation/scoring.py:119-123`.
- Gate behavior is generic over `cfg.floors.items()` in `packages/research/evaluation/types.py:90-94`; I found no executable two-floor fallback in `packages/`, `config/`, `tests/`, or `tools/`.
- WP1-B tests cover actual novelty/actionability floor failures, not just config shape:
  - novelty rejection cases: `tests/test_ris_wp1b_dimension_floors.py:83-114`
  - actionability rejection cases: `tests/test_ris_wp1b_dimension_floors.py:121-152`
  - env-var override gate enforcement: `tests/test_ris_wp1b_dimension_floors.py:187-232`
  - weighted-gate config assertions updated for four floors: `tests/test_ris_phase2_weighted_gate.py:327-344`

## Blocking issues

### 1. Prompt text is not sourced from live floor config, so config and gate behavior can drift at runtime

The gate uses live config and env-var overrides:

- config/env source of truth: `packages/research/evaluation/config.py:110-116`, `:144-147`
- gate enforcement path: `packages/research/evaluation/types.py:90-97`

But the model-facing prompt hardcodes floor text to `>= 2`:

- `packages/research/evaluation/scoring.py:119-123`

That means the prompt can disagree with the actual gate as soon as an operator sets `RIS_EVAL_NOVELTY_FLOOR` or `RIS_EVAL_ACTIONABILITY_FLOOR`. I verified this with a read-only runtime check:

```text
cfg_floors= {'relevance': 2, 'novelty': 3, 'actionability': 3, 'credibility': 2}
prompt_line=   Per-dimension floors: relevance >= 2, novelty >= 2, actionability >= 2, and credibility >= 2 are required for acceptance.
gate= REJECT
```

That is contract drift between config, prompt text, and gate behavior.

The current WP1-B test slice does not catch this. The only prompt assertions I found are:

- `tests/test_ris_evaluation.py:316-335` which checks source guidance, body inclusion, and dimension names
- `tests/test_ris_wp1a_scoring_weights.py:136-183` which checks prompt weight strings

I found no test asserting that prompt floor text reflects live config or env-var floor overrides.

## Non-blocking issues

### 1. `types.py` comments still describe the old contract

`packages/research/evaluation/types.py` still contains stale contract text:

- old weight split in the module header: `packages/research/evaluation/types.py:3-8`
- floor-check bullets mentioning only relevance and credibility: `packages/research/evaluation/types.py:73-78`

The executable gate path is generic and correct, so this did not affect runtime verification, but the comments no longer match the landed contract.

## Commands run + exact results

### Repo state

```text
git status --short
 M config/ris_eval_config.json
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M packages/research/evaluation/artifacts.py
 M packages/research/evaluation/config.py
 M packages/research/evaluation/evaluator.py
 M packages/research/evaluation/replay.py
 M packages/research/evaluation/scoring.py
 M packages/research/metrics.py
 M tests/test_ris_evaluation.py
 M tests/test_ris_phase2_weighted_gate.py
 M tests/test_ris_phase5_provider_enablement.py
 M tools/cli/research_eval.py
?? docs/dev_logs/2026-04-22_ris_phase2a_activation_override.md
?? docs/dev_logs/2026-04-22_ris_wp1_context_fetch.md
?? docs/dev_logs/2026-04-22_ris_wp1a_scoring_weights.md
?? docs/dev_logs/2026-04-22_ris_wp1b_dimension_floors.md
?? docs/dev_logs/2026-04-22_ris_wp1c_provider_events_contract.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Roadmap_v6_0_Slim_Master_Restructure_md.ajson
?? docs/obsidian-vault/Claude Desktop/08-Research/10-Roadmap-v6.0-Master-Draft.md
?? docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Roadmap v6.0 Slim Master Restructure.md
?? tests/test_ris_wp1a_scoring_weights.py
?? tests/test_ris_wp1b_dimension_floors.py
```

```text
git log --oneline -5
a610f18 Hermes Agent containerization
05389a8 docs(quick-260422-ll0): PMXT Deliverable C close-out artifacts
0efd895 fix(ris): remove retriever over-fetch truncation for text_query path; Deliverable C gap1 fix
2d926c6 feat(ris): strip YAML frontmatter in heuristic claim extractor (v2)
5962d46 docs(simtrader): PMXT Deliverable B docs close-out
```

### CLI smoke

```text
python -m polytool --help
Exit code: 0
Result: CLI loaded successfully and listed the RIS commands, including research-eval.
```

### Targeted WP1-B tests

```text
pytest -q tests/test_ris_wp1b_dimension_floors.py tests/test_ris_phase2_weighted_gate.py --tb=short
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 76 items

tests\test_ris_wp1b_dimension_floors.py ........................         [ 31%]
tests\test_ris_phase2_weighted_gate.py ................................. [ 75%]
...................                                                      [100%]

============================= 76 passed in 0.30s ==============================
```

### Runtime drift proof

```text
python - <<runtime check>>
cfg_floors= {'relevance': 2, 'novelty': 3, 'actionability': 3, 'credibility': 2}
prompt_line=   Per-dimension floors: relevance >= 2, novelty >= 2, actionability >= 2, and credibility >= 2 are required for acceptance.
gate= REJECT
```

## Recommendation

Do not proceed to WP1-D yet.

WP1-B is mostly live: defaults, persisted config, gate enforcement, and targeted gate tests all reflect four floors. But there is still a substantive contract mismatch between live config/env overrides and model-facing prompt text, and the current test slice does not catch it. That should be closed before treating the four-dimension floor contract as fully verified.
