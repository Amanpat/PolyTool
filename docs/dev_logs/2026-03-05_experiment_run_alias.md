# Dev Log: experiment-run Alias for Track B Lifecycle Naming

Date: 2026-03-05

## Summary

Aligned the Track B hypothesis lifecycle naming by adding an offline-only
`experiment-run` command that wraps the existing experiment skeleton flow.

Implementation choices:

- Keep `experiment-init` for explicit/manual experiment directory names.
- Add `experiment-run` as the preferred lifecycle alias for creating a new
  attempt under a generated experiment ID directory.
- Reuse the same `experiment.json` schema (`experiment_init_v0`) for both
  commands today.
- Add a `planned_execution` placeholder block with `tape_path`,
  `sweep_config`, and `notes`.

## Files Touched

- `packages/research/hypotheses/registry.py`
- `tools/cli/hypotheses.py`
- `polytool/__main__.py`
- `tests/test_experiment_init.py`
- `tests/test_experiment_run.py`
- `tests/test_hypotheses_cli.py`
- `docs/specs/SPEC-hypothesis-registry-v0.md`
- `docs/dev_logs/2026-03-05_experiment_run_alias.md`

## Verification

- `python -m polytool --help` now lists `experiment-run`.
- `python -m polytool experiment-run --id <hypothesis_id> --registry <registry.jsonl> --outdir <experiments_root>` creates `exp-YYYYMMDDTHHMMSSZ/experiment.json`.
- Added focused tests for generated attempt directory creation, collision
  suffixing, planned execution placeholders, and top-level help output.

### pytest -q Summary

- Focused: `pytest -q tests/test_hypothesis_registry.py tests/test_experiment_init.py tests/test_experiment_run.py tests/test_hypotheses_cli.py`
- Result: `10 passed in 2.44s`
- Full suite: `pytest -q`
- Result: `1176 passed, 25 warnings in 57.35s`
