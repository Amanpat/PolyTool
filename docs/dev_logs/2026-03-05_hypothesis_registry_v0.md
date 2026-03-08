# Dev Log: Hypothesis Registry v0 + Experiment-init Skeleton

Date: 2026-03-05

## Summary

Implemented an offline-only hypothesis registry with deterministic
`hypothesis_id` generation, append-only JSONL persistence, status updates, and
an `experiment-init` skeleton that writes `experiment.json`. Added minimal CLI
wiring for:

- `hypothesis-register`
- `hypothesis-status`
- `experiment-init`

Implementation choice for v0:

- Append-only full-snapshot JSONL events
- Stable ID generation from candidate identity fields, ignoring rank suffixes
- No network calls and no LLM calls

## Files Touched

- `docs/specs/SPEC-hypothesis-registry-v0.md`
- `docs/dev_logs/2026-03-05_hypothesis_registry_v0.md`
- `packages/research/__init__.py`
- `packages/research/hypotheses/__init__.py`
- `packages/research/hypotheses/registry.py`
- `tools/cli/hypotheses.py`
- `polytool/__main__.py`
- `pyproject.toml`
- `tests/test_hypothesis_registry.py`
- `tests/test_experiment_init.py`
- `tests/test_hypotheses_cli.py`

## pytest -q Summary

Focused new tests:

- `pytest -q tests/test_hypothesis_registry.py tests/test_experiment_init.py tests/test_hypotheses_cli.py`
- Result: `8 passed in 1.29s`

Full suite:

- `pytest -q`
- Result: `1102 passed, 25 warnings in 32.38s`

Warnings were pre-existing deprecation warnings in unrelated modules; no test
failures or new regressions were introduced.
