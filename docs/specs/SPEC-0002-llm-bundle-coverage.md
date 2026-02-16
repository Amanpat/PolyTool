# SPEC-0002: LLM Bundle Coverage Section

**Status**: Accepted
**Created**: 2026-02-16

## Overview

The `polytool llm-bundle` command includes a "Coverage & Reconciliation" section in
the generated `bundle.md`. This provides the LLM with trust-artifact context about
data quality without requiring the user to manually locate and paste coverage reports.

## Behavior

### Coverage source selection

1. Search `artifacts/dossiers/users/<slug>/` for `run_manifest.json` files.
2. Prefer runs where `command_name = "scan"` (canonical trust-artifact producer).
3. Select the latest by `started_at` timestamp (or file mtime fallback).
4. If no scan runs exist, fall back to the latest `run_manifest.json` of any type.
5. If no runs exist at all, emit a "coverage not found" note.

### Coverage content inclusion

Within the selected run directory:

1. If `coverage_reconciliation_report.md` exists, include it verbatim with a
   `[file_path: ...]` header (forward-slash normalized).
2. Else if `coverage_reconciliation_report.json` exists, produce a deterministic
   text summary including:
   - Positions total
   - Outcome counts
   - Deterministic UID coverage percentage
   - Fallback UID coverage percentage
   - Unknown resolution rate
   - Warnings list
3. Else emit a "coverage report not found in scan run directory" note.

### Bundle section ordering

```
## memo.md
## dossier.json
## manifest.json
## Coverage & Reconciliation    <-- NEW
## RAG excerpts
```

### Path normalization

All `[file_path: ...]` headers use forward slashes via `Path.as_posix()`,
even on Windows.

## RAG dependency

Coverage inclusion does NOT depend on RAG. When RAG modules are unavailable:
- Coverage section is still populated.
- RAG excerpts section shows "_RAG unavailable; excerpts omitted._".
- `rag_queries.json` is written as an empty list.
- `bundle_manifest.json` is still written.
- Exit code is 0.
