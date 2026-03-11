# Dev Log: LLM Bundle Manifest Precedence Fix

Date: 2026-03-04
Work packet: llm-bundle dossier manifest precedence

## What Changed
- Added this dev log documenting verification and outcomes.
- No code changes were required in `tools/cli/llm_bundle.py` or `tests/test_llm_bundle.py` because the requested behavior is already implemented in the current branch.

## Why
- `llm-bundle` already resolves manifests with deterministic precedence:
  1. `<run_root>/run_manifest.json`
  2. `<run_root>/manifest.json`
  3. Raises `FileNotFoundError` with both expected full paths and guidance to run `export-dossier` or `scan`.
- Regression tests covering:
  - preference for `run_manifest.json` when both exist,
  - fallback to `manifest.json`,
  - clear error when neither exists,
  are already present and passing.

## Files Touched
- `docs/dev_logs/2026-03-04_llm_bundle_manifest_precedence_fix.md`

## Commands Run
- `Get-Content docs/debug/DEBUG-llm-bundle-manifest-precedence.md`
- `Get-Content docs/LLM_BUNDLE_WORKFLOW.md`
- `rg --files | rg 'llm[_-]bundle|llm_bundle|llm-bundle'`
- `rg -n "run_manifest.json|manifest.json|llm-bundle|llm_bundle|dossier" packages tools polytool tests`
- `Get-Content tools/cli/llm_bundle.py`
- `Get-Content tests/test_llm_bundle.py`
- `pytest -q tests/test_llm_bundle.py`
- `pytest -q`

## Test Results
- `pytest -q tests/test_llm_bundle.py`: **12 passed**
- `pytest -q`: **938 passed**, 25 warnings, 0 failures

