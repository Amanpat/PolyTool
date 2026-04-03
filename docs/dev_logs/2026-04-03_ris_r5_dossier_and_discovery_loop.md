# Dev Log: 2026-04-03 — RIS R5 Dossier Pipeline and Discovery Loop

**Task:** quick-260403-jy8 — Complete the dossier pipeline and discovery loop
**Status:** Complete

## Objective

Convert locked-away wallet-scan dossier artifacts into queryable research memory.
The `wallet-scan -> export-dossier -> KnowledgeStore` discovery flow is now real
and repo-traceable. Any dossier in `artifacts/dossiers/users/` can be extracted
and ingested in a single CLI call.

## Files Changed

### Created

- `packages/research/integration/dossier_extractor.py` — core parsing + ingest logic
- `tools/cli/research_dossier_extract.py` — CLI entrypoint
- `tests/test_ris_dossier_extractor.py` — 31 offline deterministic tests

### Modified

- `packages/research/ingestion/adapters.py` — added `DossierAdapter` + `ADAPTER_REGISTRY["dossier"]`
- `packages/research/integration/__init__.py` — added dossier pipeline exports
- `polytool/__main__.py` — registered `research-dossier-extract` command
- `docs/features/FEATURE-ris-v1-data-foundation.md` — Phase R5 section added

## Implementation Notes

### Parse pipeline

`dossier.json` → `_parse_dossier_json()`: extracts header (user_slug, wallet,
window, export_id), detector labels from `detectors.latest`, and pnl_summary
(pricing_confidence, trend_30d).

`memo.md` → `_parse_memo()`: strips bullet lines that start with `- TODO:` and
standalone `TODO` lines, then checks if the remaining content is substantive
(>50 chars after removing boilerplate headers). Returns empty string if
the memo is all-TODO placeholders.

`hypothesis_candidates.json` → `_parse_hypothesis_candidates()`: extracts top
candidates with CLV metrics (avg_clv_pct, beat_close_rate, win_rate, count).

### Document types per run (1-3 docs)

1. "Dossier Detectors: {slug}" — always produced (from dossier.json)
2. "Dossier Hypothesis Candidates: {slug}" — only if candidates exist
3. "Dossier Memo: {slug}" — only if memo has non-TODO real content

### Circular import avoidance

`DossierAdapter` lives in `packages/research/ingestion/adapters.py` alongside
the other adapters (not in `dossier_extractor.py`). `dossier_extractor.py`
imports `DossierAdapter` from `adapters.py`. This avoids:
- `adapters.py -> dossier_extractor.py -> adapters.py` circular import

### Dedup

Content-hash pre-check (SHA-256) before calling `IngestPipeline.ingest()`.
On second extraction of the same dossier, all findings hit the dedup path and
return synthetic `IngestResult(chunk_count=0, rejected=False)`.

### source_url note

`PlainTextExtractor` raw-text mode hardcodes `source_url = "internal://manual"`.
The `file://` URI is stored in the finding dict's `metadata.dossier_path` field,
not in `source_documents.source_url`. This is a known limitation documented
in the feature doc's Deferred Items section.

## Commands Run and Output

```
python -m pytest tests/test_ris_dossier_extractor.py -x -q --tb=short
>>> 31 passed in 0.65s

python -m pytest tests/ -q --tb=short
>>> 3660 passed, 3 deselected, 25 warnings in 95.22s

python -m polytool --help | grep research-dossier
>>> research-dossier-extract  Parse dossier artifacts -> KnowledgeStore (source_family=dossier_report)

python -m polytool research-dossier-extract --help
>>> (full help text — single-dir and batch modes shown)

python -m polytool research-dossier-extract \
  --dossier-dir "artifacts/dossiers/users/anoin123/0x96489.../2026-02-20/a5a3e49c..." \
  --dry-run
>>> Extracted 3 finding(s) from artifacts\dossiers\users\anoin123\...
>>> [1] Dossier Detectors: anoin123 | ... | family=dossier_report | body_len=588
>>> [2] Dossier Hypothesis Candidates: anoin123 | ... | family=dossier_report | body_len=595
>>> [3] Dossier Memo: anoin123 | ... | family=dossier_report | body_len=43238
```

## What Is Now Real

- Parsing `dossier.json` (header, detectors, pnl_summary) into structured findings
- Parsing `memo.md` with TODO stripping (pure TODO memos produce no memo document)
- Parsing `hypothesis_candidates.json` into CLV metric summaries
- Building 1-3 finding documents per dossier run with wallet provenance in metadata
- DossierAdapter registered in ADAPTER_REGISTRY — source_family="dossier_report"
- Batch extraction via `rglob("dossier.json")` over any dossier base directory
- Content-hash dedup (idempotent re-ingestion)
- CLI: `research-dossier-extract --dossier-dir DIR` and `--batch`

## What Remains Deferred

| Item | Reason |
|------|--------|
| Auto-trigger after wallet-scan | Not wired into `wallet-scan` end-of-run hook |
| Wallet watchlist integration | No scheduled cadence yet |
| LLM-assisted memo extraction | Authority conflict (PLAN_OF_RECORD vs Roadmap v5.1) |
| source_url in source_documents | PlainTextExtractor raw-text mode hardcodes "internal://manual" |
| RAG query integration | Chroma/FTS5 hybrid pipeline not wired to KnowledgeStore yet |

## Codex Review

- Tier: Skip (no execution/risk code modified)
- Files: adapters.py, dossier_extractor.py, research_dossier_extract.py, polytool/__main__.py
- Issues found: None (offline parsing + SQLite writes only)
