# 2026-04-22 — Deliverable C Context Fetch: RIS Knowledge Seeding

**Type:** Context fetch (read-only)  
**Scope:** Map the RIS ingest surface for PMXT Deliverable C  
**Changed:** Zero code files  

---

## Files Inspected

| File | Purpose |
|------|---------|
| `config/seed_manifest.json` | Existing manifest schema (v3, 11 entries) |
| `tools/cli/research_ingest.py` | Single-document ingest CLI surface |
| `tools/cli/research_seed.py` | Manifest-driven batch ingest CLI |
| `tools/cli/rag_query.py` | Query CLI — flag surface and retrieval path |
| `packages/research/ingestion/pipeline.py` | IngestPipeline.ingest() implementation |
| `packages/research/ingestion/seed.py` | SeedEntry dataclass |
| `packages/polymarket/rag/knowledge_store.py` | SQLite schema, add_source_document() |
| `packages/polymarket/rag/defaults.py` | RAG_DEFAULT_COLLECTION constant |
| `packages/polymarket/rag/index.py` | Chroma index, DEFAULT_COLLECTION resolution |
| `config/freshness_decay.json` | Source family half-lives |
| `docs/audits/RIS_AUDIT_REPORT.md` | Spec vs. implementation discrepancy table |
| `docs/dev_logs/2026-04-04_ris-audit.md` | Surprise findings from RIS audit |

---

## Schema Findings

### SQLite `source_documents` table (knowledge_store.py)
```
id, title, source_url, source_family, content_hash, chunk_count,
published_at, ingested_at, confidence_tier, metadata_json
```
- No `partition` column — `source_family` is the partition analog
- `confidence_tier` column exists; `IngestPipeline.ingest()` passes `None` unconditionally
- Idempotent: `INSERT OR IGNORE` on (source_url, content_hash) SHA-256 ID

### SeedEntry dataclass (ingestion/seed.py)
```python
path: str           # repo-relative path
title: str
source_type: str    # "manual", "reference_doc", "roadmap"
source_family: str  # must match key in freshness_decay.json
author: str = "unknown"
publish_date: Optional[str] = None
tags: list = []
evidence_tier: Optional[str] = None
notes: Optional[str] = None
extractor: Optional[str] = None  # "structured_markdown" for .md files
```
- `source_family` is applied via SQL `UPDATE source_documents SET source_family = ?` after pipeline ingest, overriding whatever the extractor inferred
- `confidence_tier` is NOT a SeedEntry field — cannot be set via manifest as-shipped

### freshness_decay.json — current families
```
academic_foundational: null (no decay)
book_foundational: null
academic_empirical: 18 months
preprint: 12
github: 12
blog: 9
reddit/twitter/youtube: 6
wallet_analysis: 6
news: 3
```
`external_knowledge` is **not defined**.

### Chroma collection naming
- `packages/polymarket/rag/defaults.py`: `RAG_DEFAULT_COLLECTION = "polytool_rag"`
- `packages/polymarket/rag/index.py`: `DEFAULT_COLLECTION = RAG_DEFAULT_COLLECTION`
- `docs/audits/RIS_AUDIT_REPORT.md` line 220: `[IMPLEMENTED] — Collection name: polytool_brain`
- Resolution: The RIS audit confirmed Chroma is wired as `polytool_brain` per spec, but `defaults.py` shows `polytool_rag` as the code default. The audit may be referencing the spec claim rather than the active runtime name.
- **Operational impact:** `IngestPipeline.ingest()` writes to SQLite only — no Chroma call. Retrieval via `rag-query --hybrid --knowledge-store default` uses SQLite FTS5 + Chroma; the Deliverable C acceptance criterion is reachable via the FTS5 path regardless of Chroma collection naming.

---

## Implementation Map

### Step 1 — Add `external_knowledge` to freshness_decay.json

Edit `config/freshness_decay.json`, add one entry to `source_families`:
```json
"external_knowledge": 12
```
12-month half-life: appropriate for practitioner docs updated roughly annually.  
**Must do before seeding**, or use an existing family (e.g., `"blog"`) as a stopgap.

### Step 2 — Create 7 markdown docs

Place in `docs/external_knowledge/` (new directory):

| File | Title | Confidence |
|------|-------|-----------|
| `polymarket_fee_structure_april2026.md` | Polymarket Fee Structure (April 2026) | PRACTITIONER |
| `kalshi_fee_structure_april2026.md` | Kalshi Fee Structure (April 2026) | PRACTITIONER |
| `pmxt_sdk_operational_gotchas.md` | pmxt SDK Operational Gotchas | PRACTITIONER |
| `sports_strategy_catalogue.md` | Sports Strategy Catalogue | PRACTITIONER |
| `simtrader_known_limitations.md` | SimTrader Known Limitations | PRACTITIONER |
| `cross_platform_price_divergence_empirics.md` | Cross-Platform Price Divergence Empirics | COMMUNITY |
| `cross_platform_market_matching.md` | Cross-Platform Market Matching | COMMUNITY |

### Step 3 — Create manifest

New file: `config/seed_manifest_external_knowledge.json`  
Do NOT modify `config/seed_manifest.json` (v3, 11 foundational entries).

Example entry structure:
```json
{
  "version": "1",
  "description": "External knowledge seed corpus v1: practitioner and community docs for Deliverable C.",
  "entries": [
    {
      "path": "docs/external_knowledge/polymarket_fee_structure_april2026.md",
      "title": "Polymarket Fee Structure (April 2026)",
      "source_type": "reference_doc",
      "source_family": "external_knowledge",
      "author": "PolyTool Team",
      "publish_date": "2026-04-22T00:00:00+00:00",
      "tags": ["polymarket", "fees", "maker-rebate", "taker-fee"],
      "evidence_tier": "tier_1_internal",
      "notes": "Practitioner-level fee reference. freshness_tier: CURRENT, confidence_tier: PRACTITIONER, validation_status: UNTESTED.",
      "extractor": "structured_markdown"
    }
  ]
}
```

Note: `confidence_tier` and `freshness_tier` values from the work packet have no SeedEntry fields —
store them in the `notes` field as prose (as shown above) until a future manifest schema extension.

### Step 4 — Commands to run

```bash
# Dry run first (no writes)
python -m polytool research-seed \
  --manifest config/seed_manifest_external_knowledge.json \
  --no-eval --dry-run

# Seed for real
python -m polytool research-seed \
  --manifest config/seed_manifest_external_knowledge.json \
  --no-eval

# Verify retrieval (corrected acceptance criterion command)
python -m polytool rag-query \
  --question "Polymarket maker rebate formula" \
  --hybrid --knowledge-store default
```

### Step 5 — Optional: set confidence_tier post-seed

The pipeline stores `confidence_tier=NULL`. If PRACTITIONER/COMMUNITY tiers need to be
queryable, run a post-seed SQL UPDATE directly on the SQLite store:
```sql
UPDATE source_documents
SET confidence_tier = 'PRACTITIONER'
WHERE source_family = 'external_knowledge'
  AND title LIKE '%Fee Structure%';
```
This is a Director decision — not required for Deliverable C acceptance criterion.

---

## Gotchas / Operator Cautions

1. **`external_knowledge` not in freshness_decay.json**: Adding this family before `research-seed`
   is required. Without it, the freshness decay code will throw or silently apply wrong decay.
   Simple fix: add `"external_knowledge": 12` to `config/freshness_decay.json`.

2. **`polytool_brain` vs `polytool_rag` collection name mismatch**: Work packet says
   "ChromaDB `polytool_brain`". `defaults.py` has `polytool_rag`. The RIS audit says
   `polytool_brain` is implemented. Irrelevant for Deliverable C because `research-seed`
   writes to SQLite only (no Chroma call in IngestPipeline). Retrieval works via FTS5 path
   with `--knowledge-store default`. If Chroma-only retrieval is needed, this discrepancy
   needs investigation before implementation.

3. **`partition: external_knowledge` doesn't exist in schema**: No `partition` column in
   `source_documents`. `source_family` is the partition analog. Work packet language is
   aspirational (v4.2 roadmap framing). Use `source_family: "external_knowledge"` in manifest.

4. **`freshness_tier` field doesn't exist in schema**: Work packet says `freshness_tier: CURRENT`.
   No such column in `source_documents`. Store as prose in the document body or manifest `notes`.

5. **`confidence_tier` not set by pipeline**: `IngestPipeline.ingest()` always passes
   `confidence_tier=None`. PRACTITIONER/COMMUNITY values from work packet won't be stored
   automatically. Store as prose in `notes` field, or apply post-seed SQL UPDATE (see Step 5).

6. **Acceptance criterion command is wrong in work packet**: Work packet says:
   `python -m polytool rag query "..."` (space between `rag` and `query`)
   Actual CLI: `python -m polytool rag-query "..."` (hyphen).
   Also needs `--hybrid --knowledge-store default` to hit the SQLite store where seed writes.

7. **`--source-family` CLI flag unavailable for standard path**: `research-ingest --file` has no
   `--source-family` flag. That flag exists only for `--from-adapter`. For standalone doc
   ingestion, use `research-seed` with a manifest (which overrides source_family via SQL).

8. **Do not modify `config/seed_manifest.json`**: That file is v3 (11 foundational RIS docs).
   Create a new `config/seed_manifest_external_knowledge.json` for Deliverable C.

---

## Resume Trigger

Per `docs/CURRENT_DEVELOPMENT.md`, Deliverable C is **Paused** — resume trigger is
"RIS audit gaps resolved". Before implementation begins, Director must:
- (a) confirm the freshness_decay.json addition of `external_knowledge: 12` is acceptable, and
- (b) decide whether `confidence_tier` values need to be machine-queryable (post-seed SQL) or
  prose-only in `notes` is sufficient for this deliverable.

---

## Open Questions

- [ ] Is `external_knowledge: 12` the right half-life, or should it be `null` (timeless)?
- [ ] Does Deliverable C acceptance criterion require Chroma-based retrieval (polytool_brain)
  or is SQLite FTS5 via `--knowledge-store default` sufficient?
- [ ] Should `confidence_tier` be extended in SeedEntry for Deliverable C, or deferred?

---

*Codex review: N/A — read-only context fetch, no code changed.*
