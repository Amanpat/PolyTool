---
date: 2026-04-22
work_packet: WP1-B (verification)
phase: RIS Phase 2A
slug: ris_wp1b_prompt_drift_codex_verification
---

# WP1-B Prompt Drift Codex Verification

## Scope

Read-only verification of the WP1-B prompt drift fix after landing in the working
tree. No code, config, workflow, or infra files were modified. This dev log is
the only file added.

Verification was performed against the current dirty working tree, which already
contained changes in the RIS evaluation stack and related tests.

## Files inspected

- `packages/research/evaluation/scoring.py`
- `packages/research/evaluation/config.py`
- `packages/research/evaluation/types.py`
- `config/ris_eval_config.json`
- `tests/test_ris_wp1b_prompt_floor_drift.py`
- `tests/test_ris_wp1b_dimension_floors.py`
- `tests/test_ris_phase2_weighted_gate.py`
- `tests/test_ris_evaluation.py`
- `docs/dev_logs/2026-04-22_ris_wp1b_codex_verification.md`
- `docs/dev_logs/2026-04-22_ris_wp1b_prompt_floor_drift_fix.md`
- `docs/dev_logs/2026-04-22_ris_wp1b_dimension_floors.md`

## What matched

- Live default floors are `2/2/2/2` for `relevance`, `novelty`,
  `actionability`, and `credibility` in both the persisted config and the
  loader path:
  - `config/ris_eval_config.json`
  - `packages/research/evaluation/config.py:41`
  - `packages/research/evaluation/config.py:111`
- Env-var overrides exist for all four floor dimensions:
  - `packages/research/evaluation/config.py:144`
  - `packages/research/evaluation/config.py:145`
  - `packages/research/evaluation/config.py:146`
  - `packages/research/evaluation/config.py:147`
- `build_scoring_prompt()` now derives the floor text from live config at call
  time rather than hardcoding `>= 2`:
  - `packages/research/evaluation/scoring.py:58`
  - `packages/research/evaluation/scoring.py:72`
  - `packages/research/evaluation/scoring.py:73`
  - `packages/research/evaluation/scoring.py:132`
- Gate enforcement uses the same live `cfg.floors` surface and iterates all
  configured dimensions for non-waived tiers:
  - `packages/research/evaluation/types.py:70`
  - `packages/research/evaluation/types.py:92`
- Dedicated prompt-drift tests cover:
  - default prompt floor text: `tests/test_ris_wp1b_prompt_floor_drift.py:52`
  - novelty override reflected in prompt: `tests/test_ris_wp1b_prompt_floor_drift.py:61`
  - actionability override reflected in prompt: `tests/test_ris_wp1b_prompt_floor_drift.py:74`
  - prompt/gate agreement for default and override states:
    `tests/test_ris_wp1b_prompt_floor_drift.py:109`,
    `:118`, `:135`, `:152`
- Dedicated floor-contract tests cover:
  - four-dimension default floor contract:
    `tests/test_ris_wp1b_dimension_floors.py:54`,
    `:63`
  - novelty and actionability override enforcement in the gate:
    `tests/test_ris_wp1b_dimension_floors.py:210`,
    `:222`
  - floor-at-threshold and floor-waive behavior:
    `tests/test_ris_wp1b_dimension_floors.py:175`,
    `:261`
- Weighted-gate regression coverage remains green around the floor contract:
  - floor enforcement section starts at `tests/test_ris_phase2_weighted_gate.py:175`
  - default four-floor assertion: `tests/test_ris_phase2_weighted_gate.py:337`
  - credibility floor env override wiring: `tests/test_ris_phase2_weighted_gate.py:389`
- Additional read-only runtime checks confirmed that the two dimensions not
  explicitly covered by the dedicated prompt-drift tests also update the prompt
  text correctly under env overrides:
  - `RIS_EVAL_RELEVANCE_FLOOR=4` -> prompt showed `relevance >= 4`
  - `RIS_EVAL_CREDIBILITY_FLOOR=3` -> prompt showed `credibility >= 3`

## Blocking issues

None.

## Non-blocking issues

None for substantive correctness on this verification target.

## Commands run + exact results

### Repo state

```text
git status --short
 M config/ris_eval_config.json
 M docs/CURRENT_DEVELOPMENT.md
 M docs/obsidian-vault/.obsidian/graph.json
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
?? docs/dev_logs/2026-04-22_ris_wp1b_codex_verification.md
?? docs/dev_logs/2026-04-22_ris_wp1b_dimension_floors.md
?? docs/dev_logs/2026-04-22_ris_wp1b_prompt_floor_drift_fix.md
?? docs/dev_logs/2026-04-22_ris_wp1c_provider_events_contract.md
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_08-Research_10-Roadmap-v6_0-Master-Draft_md.ajson
?? docs/obsidian-vault/.smart-env/multi/Claude_Desktop_09-Decisions_Decision_-_Roadmap_v6_0_Slim_Master_Restructure_md.ajson
?? "docs/obsidian-vault/Claude Desktop/08-Research/10-Roadmap-v6.0-Master-Draft.md"
?? "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Roadmap v6.0 Slim Master Restructure.md"
?? tests/test_ris_wp1a_scoring_weights.py
?? tests/test_ris_wp1b_dimension_floors.py
?? tests/test_ris_wp1b_prompt_floor_drift.py
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
Result: CLI loaded successfully and listed the RIS command set, including research-eval.
```

### Targeted tests

```text
python -m pytest -q tests/test_ris_wp1b_prompt_floor_drift.py --tb=short
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 8 items

tests\test_ris_wp1b_prompt_floor_drift.py ........                       [100%]

============================== 8 passed in 0.14s ==============================
```

```text
python -m pytest -q tests/test_ris_wp1b_dimension_floors.py --tb=short
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 24 items

tests\test_ris_wp1b_dimension_floors.py ........................         [100%]

============================= 24 passed in 0.16s ==============================
```

```text
python -m pytest -q tests/test_ris_phase2_weighted_gate.py --tb=short
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 52 items

tests\test_ris_phase2_weighted_gate.py ................................. [ 63%]
...................                                                      [100%]

============================= 52 passed in 0.22s ==============================
```

Targeted verification total: `84 passed, 0 failed`.

### Additional runtime override check

```text
RIS_EVAL_RELEVANCE_FLOOR=4: True
  Per-dimension floors: relevance >= 4, novelty >= 2, actionability >= 2, and credibility >= 2 are required for acceptance.
RIS_EVAL_CREDIBILITY_FLOOR=3: True
  Per-dimension floors: relevance >= 2, novelty >= 2, actionability >= 2, and credibility >= 3 are required for acceptance.
```

## Recommendation

Proceed to WP1-D.

For this issue, the prompt text, live default floors, env-var override behavior,
and gate enforcement are aligned in the working tree, the targeted RIS suites
pass (`84 passed, 0 failed`), and I found no remaining blocker for WP1-D from
the WP1-B prompt drift issue.
