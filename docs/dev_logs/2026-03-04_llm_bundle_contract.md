---
date_utc: 2026-03-04
run_type: research
subject: LLM Bundle Input Contract
---

# LLM Bundle Input Contract — Research & Documentation

## Objective

Define and document the LLM Bundle Input Contract so future work (and future
operators) have a clear reference for what files the LLM receives, what each
file does, and what gaps exist today.

## Artifacts Inspected

Examined real bundle directories across multiple runs:

- `kb/users/drpufferfish/llm_bundles/2026-03-04/79fd7eeb/`
- `kb/users/drpufferfish/llm_bundles/2026-02-21/ffb6701d/`
- `kb/users/drpufferfish/llm_bundles/2026-02-10/c47a1e75/`
- `kb/users/0xdb27bf2a___/llm_bundles/2026-02-05/34ba1da9/`

Source code reviewed: `tools/cli/llm_bundle.py` (full read).
Spec reviewed: `docs/specs/SPEC-0002-llm-bundle-coverage.md`.

## Key Findings

### 1. The LLM reads exactly one file: `bundle.md`

`bundle.md` embeds everything in a fixed order:
- memo.md (with TODO placeholders — see §3)
- dossier.json (primary evidence)
- run_manifest.json / manifest.json (export metadata)
- Coverage & Reconciliation (from latest `scan` run, not necessarily the dossier run)
- RAG excerpts (currently always empty — see §4)

### 2. `bundle_manifest.json` and `rag_queries.json` are NOT pasted into the LLM

Both files are operator audit trails. `bundle_manifest.json` records provenance
and RAG settings. `rag_queries.json` records the five queries attempted and their
results. Neither belongs in the LLM prompt.

### 3. RAG queries return empty results in all known bundles

Across every bundle directory inspected, `rag_queries.json` has `results: []`
for all five default queries. `bundle_manifest.json` has `selected_excerpts: []`.
The `## RAG excerpts` section in `bundle.md` always shows
`_No RAG excerpts returned._`.

Root cause is unknown without running diagnostics, but the most likely cause is
that `rag-index` has not been run (or the index is scoped to a collection name
that doesn't match the one used by `llm-bundle`). Note: one older bundle uses
collection name `polyttool_rag` (double-t, legacy); the latest bundle uses
`polytool_rag` — this mismatch may explain persistent empty results.

This is a significant quality gap: the LLM is operating without any historical
context from prior reports or notes.

### 4. `memo.md` has TODO sections that the LLM must fill

The `export-dossier` command generates `memo.md` as a template. The analytical
sections (executive summary, key observations, hypotheses, what changed, next
features) are placeholder TODOs. The LLM uses `dossier.json` to fill them.
The toolchain does not fill them. This is by design.

### 5. `prompt.txt` is legacy only

Older bundles (from the `examine` command) included `prompt.txt`. The current
`llm-bundle` command does not write it. The prompt template lives in
`docs/LLM_BUNDLE_WORKFLOW.md`.

## Action Taken

Created `docs/specs/LLM_BUNDLE_CONTRACT.md` documenting:
- All files in the bundle directory with their roles
- Exact sections in `bundle.md` and their sources
- TODO section semantics
- RAG empty-results gap with likely causes and impact
- What the LLM does NOT receive
- Cross-references

Added a link row to `docs/INDEX.md` under the Specs table.

## Follow-up Items

- **RAG empty results**: Investigate collection name mismatch (`polyttool_rag`
  vs `polytool_rag`). Run `rag-index` against a fresh scan and verify that
  `rag_queries.json` results are populated in the next bundle.
- **memo.md TODO fill step**: Consider whether `export-dossier` should auto-fill
  the summary fields from computed metrics, or whether a separate
  `memo-fill` pipeline step is needed.
- **prompt.txt**: Decide whether to have `llm-bundle` write a `prompt.txt` for
  convenience (or document clearly that the prompt lives in the workflow doc).
