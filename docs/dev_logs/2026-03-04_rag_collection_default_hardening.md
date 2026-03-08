# Dev Log: RAG Collection Default Hardening

Date: 2026-03-04
Work packet: rag collection default hardening

## What Changed
- Added a shared RAG defaults module and centralized the collection default to `polytool_rag`.
- Updated all target CLI entrypoints to use the shared default when `--collection` is not provided:
  - `rag-index`
  - `rag-query`
  - `llm-bundle`
  - `rag-run`
- Fixed `llm-bundle` fallback behavior to avoid emitting `collection: "polytool"` when RAG imports are unavailable.
- Added regression tests for:
  - cross-entrypoint default consistency (`defaults_are_consistent`)
  - `rag-run` manifest precedence where `rag_query_settings.collection` overrides the default.

## Files Touched
- `packages/polymarket/rag/defaults.py`
- `packages/polymarket/rag/index.py`
- `tools/cli/rag_index.py`
- `tools/cli/rag_query.py`
- `tools/cli/rag_run.py`
- `tools/cli/llm_bundle.py`
- `tests/test_rag_collection_defaults.py`
- `docs/dev_logs/2026-03-04_rag_collection_default_hardening.md`

## Commands Run
- `rg -n --hidden --glob '!**/.git/**' "polyttool_rag|polytool_rag" .`
- `Get-Content docs/RAG_IMPLEMENTATION_REPORT.md`
- `Get-Content docs/adr/ADR-0001-cli-and-module-rename.md`
- `Get-Content docs/specs/LLM_BUNDLE_CONTRACT.md`
- `rg -n "collection|persist_dir|rag_query_settings|DEFAULT_COLLECTION" tools/cli/rag_index.py tools/cli/rag_query.py tools/cli/rag_run.py tools/cli/llm_bundle.py packages/polymarket/rag/index.py tests/test_rag_run.py tests/test_llm_bundle.py`
- `pytest -q`

## Test Results
- `pytest -q`: **965 passed**, 25 warnings, 0 failures
