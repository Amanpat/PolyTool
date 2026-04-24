# RIS WP1-B Codex Verification

Date: 2026-04-23
Scope: Read-only adversarial verification of the WP1-B four-dimension floor contract
Recommendation: Proceed to WP1-D

Session note: This target log path already existed in the dirty worktree before this verification rerun. The conclusions below were independently re-validated in this session without replacing the original findings.

## Files inspected

- `packages/research/evaluation/config.py`
- `config/ris_eval_config.json`
- `packages/research/evaluation/scoring.py`
- `packages/research/evaluation/types.py`
- `tests/test_ris_wp1b_dimension_floors.py`
- `tests/test_ris_wp1b_prompt_floor_drift.py`

## What matched

- Runtime defaults expose four floors in code. `config.py` defines `_DEFAULT_FLOORS` for `relevance`, `novelty`, `actionability`, and `credibility`, and the loader applies file and env-var overrides across the same four keys.
- Persisted config exposes the same four floors. `config/ris_eval_config.json` sets all four floor values to `2`.
- Model-facing prompt text reflects the live floor config. `build_scoring_prompt()` derives floor text from `get_eval_config().floors`, so prompt wording stays aligned with runtime config and env-var overrides.
- Gate behavior enforces the live floor set, not a hardcoded subset. `ScoringResult.gate` iterates `cfg.floors.items()` and rejects when any non-waived dimension falls below its configured floor.
- No executable two-floor fallback was found in the gate path inspected for this check. The actual enforcement path is data-driven from `cfg.floors`.
- WP1-B targeted tests cover behavior, not just config shape:
  - novelty floor failures reject on non-waived tiers
  - actionability floor failures reject on non-waived tiers
  - `priority_1` floor waiver applies to all four dimensions
  - env-var overrides affect both prompt text and gate behavior
- Dynamic runtime spot-check matched the static read:

```text
{'relevance': 2, 'novelty': 2, 'actionability': 2, 'credibility': 2}
True True True True
```

  The first line is `load_eval_config().floors`. The booleans confirm the prompt contained all four floor strings under current defaults.

## Blocking issues

- None.

## Non-blocking issues

- Internal documentation drift remains in `packages/research/evaluation/types.py`. The top-of-file Phase 2 composite formula still states the old `0.30/0.25/0.25/0.20` split, and the `ScoringResult.gate` docstring still lists only `relevance` and `credibility` as floor examples. The executable code is correct and enforces all four configured floors, so this is not a runtime contract bug.

## Commands run and exact results

- `git status --short`

```text
 M .env.example
 M docker-compose.yml
 M docs/CURRENT_DEVELOPMENT.md
 M docs/INDEX.md
MM docs/dev_logs/2026-04-22_hermes-vera-agent.md
 M docs/eval/ris_retrieval_benchmark.jsonl
 M docs/obsidian-vault/.obsidian/workspace.json
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M infra/n8n/import_workflows.py
 M packages/polymarket/rag/eval.py
 M tests/test_rag_eval.py
 M tools/cli/rag_eval.py
?? .claude/scheduled_tasks.lock
?? docs/dev_logs/2026-04-23_operator-hermes-baseline.md
?? docs/dev_logs/2026-04-23_polytool-dev-logs-skill.md
?? docs/dev_logs/2026-04-23_polytool-files-skill.md
?? docs/dev_logs/2026-04-23_polytool-status-skill.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3d_wp4a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp3e_wp4b_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4c_wp4bactivate_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md
?? docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md
?? docs/dev_logs/2026-04-23_ris_phase2a_closeout_wp5_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4_monitoring_truth_sync.md
?? docs/dev_logs/2026-04-23_ris_wp4a_clickhouse_ddl.md
?? docs/dev_logs/2026-04-23_ris_wp4b_activation_plumbing.md
?? docs/dev_logs/2026-04-23_ris_wp4c_grafana_dashboard.md
?? docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md
?? docs/dev_logs/2026-04-23_ris_wp4d_scope_fix_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp4d_stale_pipeline_alert.md
?? docs/dev_logs/2026-04-23_ris_wp5_context_fetch.md
?? docs/dev_logs/2026-04-23_ris_wp5a_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp5a_queryset_expansion.md
?? docs/dev_logs/2026-04-23_ris_wp5b_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp5b_fix_codex_verification.md
?? docs/dev_logs/2026-04-23_ris_wp5b_precision_at_5.md
?? docs/dev_logs/2026-04-23_ris_wp5b_precision_at_5_fix_pass.md
?? docs/dev_logs/2026-04-23_ris_wp5d_baseline_save.md
?? docs/dev_logs/2026-04-23_ris_wp5d_codex_verification.md
?? docs/features/polytool_dev_logs_skill.md
?? docs/features/polytool_files_skill.md
?? docs/features/polytool_status_skill.md
?? docs/features/ris_operational_readiness_phase2a.md
?? docs/features/vera_hermes_operator_baseline.md
?? infra/clickhouse/initdb/28_n8n_execution_metrics.sql
?? infra/grafana/dashboards/ris-pipeline-health.json
?? infra/grafana/provisioning/alerting/
?? scripts/test_vera_dev_logs_commands.sh
?? scripts/test_vera_files_commands.sh
?? scripts/test_vera_status_commands.sh
?? scripts/vera_hermes_healthcheck.sh
?? skills/
```

- `git log --oneline -5`

```text
d9e9f8b feat(ris): WP3-E -- daily digest path at 09:00 UTC with WP3-C structured embed
b2ad984 feat(ris): WP4-B -- hourly n8n execution metrics collector workflow
2eaefd8 feat(ris): WP3-D -- Discord embed enrichment with per-pipeline fields
129d376 RIS improvement
a610f18 Hermes Agent containerization
```

- `python -m polytool --help`

```text
Exit code: 0
PolyTool - Polymarket analysis toolchain
Usage: polytool <command> [options]
python -m polytool <command> [options]
```

- `python -m pytest tests/test_ris_wp1b_dimension_floors.py tests/test_ris_wp1b_prompt_floor_drift.py -q --tb=short`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 32 items

tests\test_ris_wp1b_dimension_floors.py ........................         [ 75%]
tests\test_ris_wp1b_prompt_floor_drift.py ........                       [100%]

============================= 32 passed in 0.24s ==============================
```

- `python -B -m pytest tests/test_ris_wp1b_dimension_floors.py tests/test_ris_wp1b_prompt_floor_drift.py -q --tb=short`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 32 items

tests\test_ris_wp1b_dimension_floors.py ........................         [ 75%]
tests\test_ris_wp1b_prompt_floor_drift.py ........                       [100%]

============================= 32 passed in 0.23s ==============================
```

- `python -c "from packages.research.evaluation.config import load_eval_config; from packages.research.evaluation.scoring import build_scoring_prompt; from packages.research.evaluation.types import EvalDocument; cfg=load_eval_config(); print(cfg.floors); doc=EvalDocument(doc_id='test', title='t', author='a', source_type='manual', source_url='https://example.com', source_publish_date=None, body='b'); prompt=build_scoring_prompt(doc); print('relevance >= 2' in prompt, 'novelty >= 2' in prompt, 'actionability >= 2' in prompt, 'credibility >= 2' in prompt)"`

```text
{'relevance': 2, 'novelty': 2, 'actionability': 2, 'credibility': 2}
True True True True
```

## Conclusion

WP1-B is live in code, persisted config, prompt text, gate behavior, and targeted tests. I found no executable drift between config, prompt, and gate enforcement, and no hidden two-floor fallback in the inspected runtime path. On the evidence inspected here, WP1-B is ready to clear verification and proceed to WP1-D.
