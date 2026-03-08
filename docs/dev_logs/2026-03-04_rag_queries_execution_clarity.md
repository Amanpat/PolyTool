---
date_utc: 2026-03-04
run_type: implementation
subject: RAG query execution clarity + rag-run command
---

# RAG Queries Execution Clarity

## Objective

Make `rag_queries.json` never silently empty without explanation, and add a
`rag-run` command so operators can re-execute bundle queries after `rag-index`.

## Problem Statement

All existing bundles had `rag_queries.json` with `results: []` for every entry.
Worse, when the RAG library was unavailable, the file was written as `[]` — an
empty list with no indication of why. Operators had no way to distinguish:
- "RAG never ran" from "RAG ran but found nothing"
- Whether the queries were even attempted

## Changes Made

### 1. `tools/cli/llm_bundle.py` — explicit execution_status on every entry

Added `_build_query_template_entry()` helper. Modified `_run_rag_queries()`:

- **When RAG unavailable** (was `return []`): now returns template entries with
  `execution_status="not_executed"` and `execution_reason="rag_unavailable"`.
  File is never silently empty.

- **When RAG executes**: each entry now carries `execution_status="executed"`
  and `execution_reason=None` (results present) or `"no_matches_under_filters"`
  (empty results).

### 2. `tools/cli/rag_run.py` — new `rag-run` command

```bash
polytool rag-run --rag-queries <bundle_dir>/rag_queries.json
polytool rag-run --rag-queries <path>/rag_queries.json --out <path>  # separate output
```

Behavior:
- Reads `rag_queries.json` and auto-detects `bundle_manifest.json` in same dir
- Loads RAG settings (model, collection, persist_dir) from manifest; falls back
  to safe defaults if manifest missing
- Re-executes each query using stored filters (private-only, user scoping,
  prefix_backstop) — no privacy logic bypassed
- Respects top-k from each entry's `k` field — results are bounded
- Writes updated entries with `execution_status`, `execution_reason`,
  `executed_at_utc` back to the file
- Prints a clear summary: N executed, M with results, K empty, E errors
- Warns explicitly when any query returns empty results
- Returns exit code 0 on success, 1 on RAG unavailable or any query error

### 3. `polytool/__main__.py` — registered `rag-run` command

Added import and routing for `rag-run`.

### 4. `tests/test_rag_run.py` — 24 new tests

Coverage:
- `_load_rag_queries`: list format, non-list rejection, empty list
- `_load_bundle_settings`: loads from manifest, missing/corrupt fallback, None
- `_parse_mode`: all 5 mode strings
- `main`: writes results, `--out` path, empty results, RAG unavailable,
  missing file, empty queries, explicit manifest path, autodetect manifest,
  no manifest uses defaults, preserves existing entry fields

### 5. `tests/test_llm_bundle.py` — updated one test

`test_bundle_rag_unavailable_still_succeeds`: updated assertion from
`rag_queries == []` to check for explicit `execution_status="not_executed"` entries.

Also added `TestLlmBundleRagUnavailable` class in test_rag_run.py:
- Tests that `_run_rag_queries` returns template entries (not `[]`) when unavailable
- Tests that executed path adds `execution_status="executed"`

### 6. `docs/specs/LLM_BUNDLE_CONTRACT.md` — documented behavior and rag-run

Added §4 subsection: execution_status field table, rag-run usage, empty-results
causes, and note that running rag-run does not rebuild bundle.md.

## Test Results

- 963 tests passing (up from 926 pre-packet + test_rag_run.py new 24 + updated 1)
- All new tests pass; no regressions

## Follow-up Items

- **bundle.md does not auto-update after rag-run**: Operator must re-run
  `llm-bundle` to get fresh excerpts into bundle.md. Could add `--refresh-excerpts`
  flag to llm-bundle that reads an existing bundle dir and rebuilds bundle.md
  using a pre-existing rag_queries.json. Deferred.
- **Collection name mismatch (legacy)**: Older bundles reference `polyttool_rag`
  (double-t) while current index uses `polytool_rag`. The `rag-run --bundle-manifest`
  flag lets operators override; could also add a `--collection` override flag.
  Deferred.
