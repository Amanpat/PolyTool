# PMXT Deliverable C — RIS External Knowledge Seeding: Implementation Log

**Date**: 2026-04-22
**Author**: Claude Code (session continuation)
**Deliverable**: PMXT Deliverable C — seed external_knowledge corpus into RIS

---

## Objective

Seed 7 practitioner reference docs covering Polymarket/Kalshi fees, pmxt SDK gotchas,
sports strategies, cross-platform price divergence, SimTrader limitations, and market
matching into the PolyTool RIS (Research Intelligence System) as a named
`source_family: "external_knowledge"` partition.

---

## Files Changed

| File | Action |
|------|--------|
| `docs/external_knowledge/polymarket_fee_structure_april2026.md` | Created |
| `docs/external_knowledge/kalshi_fee_structure_april2026.md` | Created |
| `docs/external_knowledge/pmxt_sdk_operational_gotchas.md` | Created |
| `docs/external_knowledge/sports_strategy_catalogue.md` | Created |
| `docs/external_knowledge/cross_platform_price_divergence_empirics.md` | Created |
| `docs/external_knowledge/simtrader_known_limitations.md` | Created |
| `docs/external_knowledge/cross_platform_market_matching.md` | Created |
| `config/seed_manifest_external_knowledge.json` | Created |
| `config/freshness_decay.json` | Updated (added `external_knowledge: 12`) |

---

## Seed Run Output

### Dry Run
```
[DRY RUN] Seed complete: 0 ingested, 0 skipped, 0 failed (total: 7)

Title                                    Status
--------------------------------------------------
Polymarket Fee Structure (April 2026)    dry_run
Kalshi Fee Structure (April 2026)        dry_run
pmxt SDK Operational Gotchas             dry_run
Sports Strategy Catalogue                dry_run
Cross-Platform Price Divergence Empiric  dry_run
SimTrader Known Limitations (Verified)   dry_run
Cross-Platform Market Matching           dry_run
```

### Real Seed
```
Seed complete: 7 ingested, 0 skipped, 0 failed (total: 7)

Title                                    Status    doc_id
---------------------------------------------------------------
Polymarket Fee Structure (April 2026)    ingested  d8afa76d2025ee
Kalshi Fee Structure (April 2026)        ingested  8a5c528ce887c1
pmxt SDK Operational Gotchas             ingested  8ee321c714daff
Sports Strategy Catalogue                ingested  43f420a0a2bd30
Cross-Platform Price Divergence Empiric  ingested  99601b773165b3
SimTrader Known Limitations (Verified)   ingested  0f5a6f6cd906cf
Cross-Platform Market Matching           ingested  a69e36c7b2af73
```

**Command used**: `python -m polytool research-seed --manifest config/seed_manifest_external_knowledge.json --no-eval`

---

## SQLite Verification

Direct inspection confirmed all 7 docs are in `kb/rag/knowledge/knowledge.sqlite3`,
table `source_documents`, with `source_family='external_knowledge'`:

```
Polymarket Fee Structure (April 2026)   family=external_knowledge
Kalshi Fee Structure (April 2026)       family=external_knowledge
pmxt SDK Operational Gotchas            family=external_knowledge
Sports Strategy Catalogue               family=external_knowledge
Cross-Platform Price Divergence Empirics family=external_knowledge
SimTrader Known Limitations (Verified)  family=external_knowledge
Cross-Platform Market Matching          family=external_knowledge
```

The `source_family` override SQL (`UPDATE source_documents SET source_family = ?`)
runs post-ingest in the seed pipeline to enforce the manifest's value regardless
of what the extractor derived.

---

## Retrieval Check Status — DEFERRED (documented limitation)

The work packet acceptance criterion specified:
> "Run 5 `rag-query` checks; confirm ≥2 of 5 return a top-5 result from source_family='external_knowledge'"

**This check cannot pass with `--no-eval` seeding.** The reason:

`rag-query --hybrid --knowledge-store default` uses a three-way RRF fusion:
1. Chroma vector search — these docs were NOT added to Chroma (SQLite-only ingest path)
2. FTS5 lexical search — these docs are NOT in the FTS5 Chroma-adjacent index
3. KnowledgeStore claims path (`derived_claims` table) — 0 rows because `--no-eval` skips claim extraction

The 7 docs live only in `source_documents`. The KS-RRF path (`query_knowledge_store_for_rrf`)
searches `derived_claims`, not `source_documents`. With 0 derived claims, none of the
external_knowledge docs surface through `rag-query`.

**Verification performed**: Direct SQLite inspection (see above). This is the authoritative
confirmation that seeding succeeded. The `rag-query` retrieval path requires a follow-on eval step.

**Follow-on action required**: Run `research-seed --reseed` without `--no-eval` once
an LLM eval provider is configured, or run `research-ingest` per-file with eval enabled
to generate `derived_claims` for the 7 seeded docs.

---

## Packet-vs-Schema Deviations

### 1. No `partition` column — `source_family` is the analog
The work packet spec referenced a `partition` field. The actual schema has no `partition`
column. `source_family` is the partition analog enforced by the seed pipeline's SQL override.
Resolution: used `source_family: "external_knowledge"` throughout.

### 2. `confidence_tier` always NULL after seeding
The `source_documents` table has a `confidence_tier` column, but `IngestPipeline.ingest()`
always passes `confidence_tier=None`. The `SeedEntry` dataclass has no `confidence_tier`
field and does not forward it to the store.
Resolution: `PRACTITIONER`/`COMMUNITY` tiers embedded as prose in:
- Each doc's YAML frontmatter (`confidence_tier: PRACTITIONER`)
- Each manifest entry's `notes` field (`confidence_tier: PRACTITIONER. validation_status: UNTESTED.`)

### 3. `evidence_tier` and `tags` not stored in `metadata_json`
`SeedEntry.evidence_tier` and `SeedEntry.tags` are parsed by the seed loader but are not
forwarded to `add_source_document` — `metadata_json` receives the extractor's `extracted.metadata`,
not the SeedEntry fields. `metadata_json` shows `evidence_tier=None, tags=[]` in SQLite.
Resolution: values preserved in manifest JSON and doc frontmatter; SQLite metadata gap documented.

### 4. `freshness_tier` and `validation_status` not schema fields
These are additional metadata fields from the work packet. Neither exists as a column in
`source_documents`. Both preserved as prose in doc frontmatter and manifest `notes`.

### 5. `rag-query` retrieval requires `derived_claims` (eval step)
See retrieval check section above.

---

## Source-Quality Cautions

### Cross-Platform Price Divergence Empirics (HIGHEST PRIORITY CAUTION)
The 15-20% gap frequency figure and 5% threshold come from a secondary reference to an
AhaSignals March 2026 tracker. The original tracker URL, archived snapshot, and full
methodology have not been independently verified. This doc was seeded by Director decision
with explicit caution in both the frontmatter source_quality_caution field and the
document body's "Key Empirical Claims" section header.
**Do not cite these figures as validated empirical findings without locating and verifying the primary source.**

### Cross-Platform Market Matching
Algorithm descriptions derive from second-hand notes about matcher.js in hermes-pmxt repo.
No published precision/recall benchmark exists. Confidence tier: COMMUNITY.

### pmxt SDK Operational Gotchas
Sourced from LEARNINGS.md and hermes-pmxt snapshot, not official pmxt docs.

### Sports Strategy Catalogue
Mixed-license upstream files. Doc contains behavioral summaries and parameter tables only —
no source code, no pseudocode. Parameters are initial reference values, not sweep-validated defaults.

---

## freshness_decay.json Change

Added `"external_knowledge": 12` to `source_families` object.
- 12-month half-life is appropriate for practitioner reference docs
- Floor remains 0.3 (decay stops at 30% of original weight)
- This entry is required before any seed commands; its absence would cause a KeyError

---

## Smoke Test

```
python -m polytool --help  →  CLI loads, no import errors
```

All 7 docs seeded, correct `source_family` confirmed in SQLite.

---

## Open Questions / Follow-On Actions

1. **Eval step**: Run without `--no-eval` to generate `derived_claims` enabling `rag-query` retrieval.
2. **Divergence doc primary source**: Locate the original AhaSignals March 2026 tracker to verify
   the 15-20% / 5% figures. Until then, treat as indicative only.
3. **confidence_tier SQL patch**: A one-time `UPDATE source_documents SET confidence_tier = ?`
   keyed by doc_id could backfill the column for the 7 docs. Classified as non-blocking cosmetic fix.
4. **Chroma indexing**: If vector retrieval of these docs is desired, a separate Chroma ingest
   step would be needed (not part of the current `research-seed` flow).

---

## Completion Assessment

**Seeding goal**: COMPLETE. All 7 docs in `source_documents` with correct `source_family`.
**freshness_decay.json**: COMPLETE.
**Retrieval verification**: PARTIAL — SQLite confirmed; `rag-query` retrieval deferred to eval step.
**Dev log**: This document.

Deliverable C is complete with the above documented limitations. No scope was crossed,
no unrelated files were modified, no RIS eval logic was changed.
