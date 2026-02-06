# PDR-0001: User Examination MVP

**Product Design Record**
**Status**: Accepted
**Created**: 2026-02-05

## Overview

This PDR defines the "PolyTool working state" - a reliable, standardized workflow for
examining Polymarket users' trading activity and generating hypothesis-driven analysis.

## Problem Statement

Before this MVP:
- No standardized workflow for examining user trading activity
- Dossier exports lacked resolution outcomes and net PnL
- No clear contract for LLM-generated hypothesis outputs
- Manual, error-prone process for building evidence bundles

## Success Metrics

1. **Single Command Examination**: `polytool examine --user "@DrPufferfish"` produces
   all required artifacts without manual steps
2. **Resolution Coverage**: Dossier includes resolution_outcome for positions with
   settlement data
3. **Schema Compliance**: Generated hypothesis.json validates against
   `docs/specs/hypothesis_schema_v1.json`
4. **RAG Surfacing**: LLM_notes are indexed and retrievable via `rag-query`

## MVP Scope

### In Scope
- Single golden case: @DrPufferfish (wallet 0xdb27bf2ac5d428a9c63dbc914611036855a6c56e)
- Sports-first categorization (minimal for MVP)
- Resolution handling: best-effort, UNKNOWN_RESOLUTION acceptable
- Outcome taxonomy: WIN, LOSS, PROFIT_EXIT, LOSS_EXIT, PENDING, UNKNOWN_RESOLUTION

### Out of Scope
- Multi-user comparison
- Backtesting infrastructure
- Real-time monitoring
- External LLM API integration (local-only)

## Workflow

```
polytool examine --user "@DrPufferfish" --days 30
```

Produces:
1. **Dossier** (artifacts/): memo.md, dossier.json, manifest.json
2. **Bundle** (kb/): bundle.md with RAG excerpts
3. **Prompt** (kb/): prompt.txt for LLM paste
4. **Manifest** (kb/): examine_manifest.json with metadata

## Artifacts Structure

```
artifacts/dossiers/users/drpufferfish/<wallet>/<date>/<run_id>/
  memo.md
  dossier.json
  manifest.json

kb/users/drpufferfish/llm_bundles/<date>/<run_id>/
  bundle.md
  prompt.txt
  examine_manifest.json
  bundle_manifest.json
  rag_queries.json
```

## User Journey

1. **Scan**: Data ingested into ClickHouse (prerequisite)
2. **Examine**: `polytool examine --user "@DrPufferfish"`
3. **Review**: Open bundle.md and prompt.txt
4. **Analyze**: Paste to LLM, generate hypothesis.md + hypothesis.json
5. **Save**: `polytool llm-save --user drpufferfish --model opus-4.5 --report-path ...`
6. **Index**: `polytool rag-index --rebuild` (optional, for future retrieval)

## References

- `docs/specs/SPEC-0001-dossier-resolution-enrichment.md`: Resolution spec
- `docs/specs/hypothesis_schema_v1.json`: Output schema
- `docs/STRATEGY_PLAYBOOK.md`: Validation methodology
