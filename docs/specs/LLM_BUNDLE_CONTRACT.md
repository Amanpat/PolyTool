# LLM Bundle Input Contract

**Status**: Accepted
**Created**: 2026-03-04

## Overview

The `polytool llm-bundle` command assembles an evidence bundle for offline LLM
examination. This document specifies every file written to the bundle directory,
what role each file plays, which files the LLM actually reads, and the known
gaps that affect the quality of LLM inputs today.

---

## 1. Bundle Directory Layout

Output path: `kb/users/<slug>/llm_bundles/<YYYY-MM-DD>/<run_id>/`

```
<run_id>/
├── bundle.md              ← PRIMARY: The file pasted into the LLM UI
├── memo_filled.md         ← FILLED MEMO: TODO placeholders replaced deterministically
├── bundle_manifest.json   ← PROVENANCE: Operator metadata (not read by LLM)
├── rag_queries.json       ← QUERY RECORD: RAG execution log (not read by LLM)
└── [devlog written to kb/devlog/, not the bundle dir]
```

A **report stub** is also written to a separate location every run:

```
kb/users/<slug>/reports/<YYYY-MM-DD>/<run_id>_report.md
```

The stub contains section headings (`## Executive Summary`, `## Data Quality / Coverage Gaps`,
`## Findings`, `## Hypotheses`, `## Next Experiments`, `## Go/No-Go (research-only)`) and a
metadata header linking back to `bundle.md` and `memo_filled.md`. The operator pastes the LLM's
output into this file. The stub is created (or overwritten) on every run — it is intentionally
blank so no toolchain content pollutes the LLM's report.

> **Legacy bundles** (produced by the deprecated `examine` command) also contain
> `prompt.txt` and `examine_manifest.json`. These are not produced by the current
> `llm-bundle` command and should be treated as archive artifacts.

---

## 2. File Roles

### 2.1 `bundle.md` — The LLM's Input

`bundle.md` is the single file pasted into the LLM UI. The LLM reads only this
file. The toolchain builds it by concatenating dossier artifacts in a fixed order:

| Section heading | Source | Notes |
|----------------|--------|-------|
| Header block | Generated at bundle time | User, slug, run_id, created_at_utc, dossier_path |
| `## memo.md` | `artifacts/dossiers/…/memo.md` | See §3: contains TODO placeholders |
| `## dossier.json` | `artifacts/dossiers/…/dossier.json` | Full structured trade/position data |
| `## run_manifest.json` (or `manifest.json`) | `artifacts/dossiers/…/run_manifest.json` | Dossier export metadata |
| `## Coverage & Reconciliation` | Latest scan run's `coverage_reconciliation_report.md/.json` | Trust artifact from latest `scan` run (may differ from dossier run) |
| `## RAG excerpts` | Live RAG query results at bundle time | See §4: currently empty in all known bundles |

The LLM is expected to produce `hypothesis.md` and `hypothesis.json` using only
the content in `bundle.md`. See `docs/HYPOTHESIS_STANDARD.md` for output format.

---

### 2.2 `bundle_manifest.json` — Provenance (not read by LLM)

Records how the bundle was assembled. Not pasted into the LLM.

| Field | Type | Description |
|-------|------|-------------|
| `created_at_utc` | ISO-8601 string | When `llm-bundle` ran |
| `run_id` | 8-hex string | Short unique ID for this bundle run |
| `user_slug` | string | Canonical user slug |
| `dossier_path` | string | Relative path to the dossier directory used |
| `model_hint` | string | Suggested model for this bundle (currently `"opus-4.5"`) |
| `rag_query_settings` | object | Full RAG configuration used (see below) |
| `selected_excerpts` | array | Excerpt references that made it into `bundle.md` |

`rag_query_settings` sub-fields:

| Field | Description |
|-------|-------------|
| `k` | Max excerpts per query |
| `hybrid` | Whether hybrid (vector + lexical) retrieval was used |
| `rerank` | Whether cross-encoder reranking was applied |
| `model` | Embedding model name |
| `rerank_model` | Reranker model name |
| `collection` | Chroma collection name |
| `persist_dir` | Chroma index path |
| `private_only` | Whether only private content was queried |
| `top_k_vector`, `top_k_lexical`, `rrf_k`, `rerank_top_n` | Retrieval tuning |

**Current state**: `selected_excerpts` is `[]` in all known bundles because RAG
queries return no results (see §4).

---

### 2.3 `rag_queries.json` — Query Execution Record (not read by LLM)

Records every RAG query that was attempted, with its parameters and results.
Not pasted into the LLM — it is the operator's audit trail for what RAG returned.

Each entry in the array:

| Field | Description |
|-------|-------------|
| `label` | Logical name for the query (profile, patterns, risk, execution, markets) |
| `question` | Natural-language query sent to the RAG index |
| `k` | Number of results requested |
| `mode` | Retrieval mode string (e.g., `"hybrid+rerank"`) |
| `filters` | User-scope and date filters applied |
| `results` | Array of retrieved chunks; **see §4 — currently always `[]`** |

Default queries (five, defined in `tools/cli/llm_bundle.py:DEFAULT_QUESTIONS`):

| Label | Question |
|-------|---------|
| `profile` | Summarize the user's profile and recent activity context. |
| `patterns` | What trading patterns or strategy signals appear in the evidence? |
| `risk` | What risk signals or anomalies appear in the evidence? |
| `execution` | What evidence exists about execution quality, slippage, or fees? |
| `markets` | Which markets or categories dominate recent activity? |

Custom queries can be provided via `--questions-file <json/yaml>`.

---

## 3. TODO Sections in `memo.md`

The `memo.md` embedded in `bundle.md` is a template generated by
`export-dossier`. It contains pre-populated data (trade counts, PnL buckets,
evidence anchor `trade_uid` list) but the analytical sections are **left as TODO
placeholders** by the toolchain:

| Section | Placeholder |
|---------|------------|
| `## Executive Summary` | `- TODO: Summarize the strategy in 2-3 sentences.` |
| `## Key Observations` | `- TODO: Bullet observations backed by metrics/trade_uids.` |
| `## Hypotheses` | Row of TODO cells in the table |
| `## What changed recently` | `- TODO: Compare to prior exports or recent buckets.` |
| `## Next features to compute` | `- TODO: Add derived metrics that would raise confidence.` |

**The LLM's job is to fill these TODOs using the evidence already in `bundle.md`
(primarily `dossier.json`).**  The toolchain does not fill them. An operator
reviewing a bundle before submission should confirm that the `dossier.json` data
provides enough evidence for the LLM to do so.

The hard rule in `memo.md` enforces this: _"any strategy claim must cite dossier
metrics or trade_uids."_

---

## 4. RAG Query Execution Status — Known Gap

### Execution status field

Every entry in `rag_queries.json` carries an `execution_status` field:

| `execution_status` | Meaning |
|-------------------|---------|
| `"executed"` | Query ran against the RAG index (results may still be `[]`) |
| `"not_executed"` | Query was NOT run — see `execution_reason` |
| `"error"` | Query raised a `RuntimeError` — see `execution_reason` |

When `execution_status` is `"not_executed"`, the possible `execution_reason` values are:

| `execution_reason` | When it occurs |
|-------------------|---------------|
| `"rag_unavailable"` | RAG library not installed; queries were never attempted |

When `execution_status` is `"executed"` and `results` is empty:

| `execution_reason` | When it occurs |
|-------------------|---------------|
| `"no_matches_under_filters"` | Queries ran but no indexed chunks matched |
| `null` | Queries ran and returned results |

**Historical note**: Prior to 2026-03-04, `rag_queries.json` was written as `[]`
(empty list) when RAG was unavailable. This was silently uninformative. The
current behavior always writes template entries with explicit `execution_status`.
See SPEC-0002 §RAG dependency — that spec describes the old `[]` behavior; the
current behavior supersedes it for this field.

---

### Re-executing queries with `rag-run`

After building a bundle, use `rag-run` to re-execute the queries once the index
is populated:

```bash
# Populate the index first
polytool rag-index --roots "kb,artifacts"

# Then re-execute bundle queries and write results back
polytool rag-run --rag-queries kb/users/<slug>/llm_bundles/<date>/<run_id>/rag_queries.json
```

`rag-run` reads `rag_queries.json` and `bundle_manifest.json` from the same
directory, re-executes every query using the stored settings (collection,
model, filters), and overwrites `rag_queries.json` in place with the results.
Use `--out <path>` to write to a different file.

**Output summary** (printed to stdout):

```
rag-run: 5 queries — 5 executed, 3 with results, 2 empty, 0 errors, 0 not_executed
  2 query/queries returned no matches under the stored filters.
  Run 'polytool rag-index' to ensure the index is fresh, then retry.
```

Empty results after `rag-run` most commonly indicate:

| Cause | How to diagnose |
|-------|----------------|
| RAG index not built | Check `kb/rag/index/` for Chroma files; run `polytool rag-index` |
| Collection name mismatch | Compare `bundle_manifest.json.rag_query_settings.collection` with the collection built by `rag-index`. Older bundles may reference `polyttool_rag` (double-t, legacy) while the current index uses `polytool_rag`. |
| No user-scoped content in index | Check that `kb/users/<slug>/` files were indexed; the prefix filter restricts results to user-owned paths |

**Impact on bundle quality**: When RAG excerpts are empty, the LLM receives only
the dossier artifacts (memo, dossier.json, run_manifest, coverage report). This
does not block examination — `dossier.json` is the primary evidence source — but
reduces context depth from historical notes and prior LLM reports.

**Note**: `rag-run` updates `rag_queries.json` but does NOT rebuild `bundle.md`.
After re-running, regenerate the bundle with `polytool llm-bundle` to include the
new excerpts in the file you paste into the LLM.

### RAG excerpt de-noising filter

Before excerpts are selected, results are filtered to exclude self-referential
bundle artifacts. Files matching these patterns are **silently dropped** after
retrieval and will never appear in `selected_excerpts` or `bundle.md`:

| Pattern | Why excluded |
|---------|-------------|
| `kb/users/*/llm_bundles/*/rag_queries.json` | Prior run's query log — not evidence |
| `kb/users/*/llm_bundles/*/prompt.txt` | Legacy examine artifact — not evidence |
| `kb/users/*/llm_bundles/*/bundle.md` | Prior bundle output — circular evidence |

When filtering drops at least one result, `bundle_manifest.json` records
`"rag_denoise_filtered_count": N`. The field is absent when nothing is filtered.

The filter does **not** apply a minimum-threshold fallback. If all retrieved
results are artifacts, `selected_excerpts` will be `[]` and the bundle proceeds
with dossier evidence only (same behaviour as empty RAG results).

---

## 5. What the LLM Does NOT Receive

The following are written to the bundle directory but are NOT included in
`bundle.md` and should NOT be pasted into the LLM:

- `bundle_manifest.json` — operator provenance only
- `rag_queries.json` — query audit trail only
- The devlog entry in `kb/devlog/` — internal run record

---

## 6. Prompt Template

The prompt instructing the LLM what to produce is stored in
`docs/LLM_BUNDLE_WORKFLOW.md` (the "Prompt template" section). It is NOT
automatically written to the bundle directory by `llm-bundle`.

The operator must paste the prompt first, then paste `bundle.md` into the LLM UI.
See `docs/LLM_BUNDLE_WORKFLOW.md` for the full template and ordering.

> **Legacy note**: The deprecated `examine` command wrote a `prompt.txt` file
> into the bundle directory. The current `llm-bundle` command does not. If you
> see `prompt.txt` in a bundle, it was produced by `examine`.

---

## 7. Cross-References

- [LLM Bundle Workflow](../LLM_BUNDLE_WORKFLOW.md) — step-by-step usage, prompt template
- [SPEC-0002: LLM Bundle Coverage Section](SPEC-0002-llm-bundle-coverage.md) — coverage report inclusion logic
- [Hypothesis Standard](../HYPOTHESIS_STANDARD.md) — expected LLM output format
- [Hypothesis Schema v1](hypothesis_schema_v1.json) — hypothesis.json schema
- [Plan of Record §8](../PLAN_OF_RECORD.md) — hypothesis artifact contract
- [Local RAG Workflow](../LOCAL_RAG_WORKFLOW.md) — rag-index and rag-query usage
