# FEATURE: RIS v1 Data Foundation

**Shipped:** quick-055 (2026-04-01)
**Status:** Complete (data-plane only; not yet wired into Chroma query path)

## What Shipped

A lightweight SQLite persistence layer for the `external_knowledge` RAG partition.
Provides structured storage for source documents, derived claims, claim evidence
links, and claim relations, with query-time freshness decay.

## Modules

| Module | Purpose |
|--------|---------|
| `packages/polymarket/rag/knowledge_store.py` | SQLite CRUD + query layer |
| `packages/polymarket/rag/freshness.py` | Freshness decay computation |
| `config/freshness_decay.json` | Source-family half-life configuration |
| `tests/test_knowledge_store.py` | 38 offline deterministic tests |

## Tables (4-table schema)

### source_documents

Stores ingested source materials from external research (papers, blog posts,
wallet analyses, news articles, etc.).

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | Deterministic SHA-256 from source_url + content_hash |
| `title` | TEXT | Human-readable title |
| `source_url` | TEXT | Origin URL or internal reference |
| `source_family` | TEXT | One of the families in freshness_decay.json |
| `content_hash` | TEXT | SHA-256 of the raw content |
| `chunk_count` | INTEGER | Number of RAG chunks derived from this doc |
| `published_at` | TEXT | ISO-8601 original publication date |
| `ingested_at` | TEXT | ISO-8601 ingest timestamp |
| `confidence_tier` | TEXT | PEER_REVIEWED / PRACTITIONER / COMMUNITY |
| `metadata_json` | TEXT | Arbitrary JSON for additional metadata |

### derived_claims

Structured claims extracted from source documents (manually or via LLM).

**Required fields:**

| Column | Type | Notes |
|--------|------|-------|
| `id` | TEXT PK | Deterministic SHA-256 |
| `claim_text` | TEXT | Human-readable claim statement |
| `claim_type` | TEXT | e.g. empirical, normative, structural |
| `confidence` | REAL | Confidence in [0, 1] |
| `trust_tier` | TEXT | PEER_REVIEWED / PRACTITIONER / COMMUNITY |
| `validation_status` | TEXT | UNTESTED (default) / CONSISTENT_WITH_RESULTS / CONTRADICTED |
| `lifecycle` | TEXT | active (default) / archived / superseded |
| `actor` | TEXT | Agent that created the claim |
| `created_at` | TEXT | ISO-8601 |
| `updated_at` | TEXT | ISO-8601 |

**Optional fields:**

| Column | Type | Notes |
|--------|------|-------|
| `source_document_id` | TEXT | FK to source_documents |
| `scope` | TEXT | e.g. crypto, sports, politics |
| `tags` | TEXT | Comma-separated tags |
| `notes` | TEXT | Free-form notes |
| `superseded_by` | TEXT | Claim ID that supersedes this one |

### claim_evidence

Links claims to the specific source documents (and excerpts) that support them.
Enables the provenance chain: `get_provenance(claim_id)` returns all source docs
via this table.

### claim_relations

Directed relationships between claims.

**Allowed relation_type values:**

| Type | Meaning |
|------|---------|
| `SUPPORTS` | Source claim provides evidence for target claim |
| `CONTRADICTS` | Source claim contradicts target claim |
| `SUPERSEDES` | Source claim replaces (supersedes) target claim |
| `EXTENDS` | Source claim extends / refines target claim |

## Freshness Decay

Freshness is computed at query time via `compute_freshness_modifier()` -- it never
mutates stored records.

**Formula:** `modifier = max(floor, 2 ^ (-age_months / half_life_months))`

**Default floor:** 0.3 (configured in `config/freshness_decay.json`)

### Source-Family Half-Lives

| Family | Half-life (months) |
|--------|--------------------|
| `academic_foundational` | null (timeless) |
| `book_foundational` | null (timeless) |
| `academic_empirical` | 18 |
| `preprint` | 12 |
| `github` | 12 |
| `blog` | 9 |
| `reddit` | 6 |
| `twitter` | 6 |
| `youtube` | 6 |
| `wallet_analysis` | 6 |
| `news` | 3 |

`null` half-life = timeless, always returns modifier=1.0 regardless of age.

## Retrieval Behavior (query_claims defaults)

| Behavior | Default | Override |
|----------|---------|---------|
| Exclude archived claims | Yes | `include_archived=True` |
| Exclude superseded claims | Yes | `include_superseded=True` |
| Apply freshness modifier | Yes | `apply_freshness=False` |
| Downrank contradicted claims | Yes (0.5x penalty) | Always applied when freshness active |
| Sort order | `effective_score` DESC | n/a |

`effective_score = freshness_modifier * confidence * contradiction_penalty`

## Deliberate Simplifications

- **No graph DB.** Tabular SQLite only. The 4-table schema covers the current
  use cases without the overhead of a dedicated graph store.
- **No Chroma integration yet.** This is a data-plane addition. The knowledge
  store is not wired into the existing Chroma/FTS5 hybrid retrieval pipeline.
  That wiring is deferred to a future plan.
- **No LLM provider enabled by default.** See the authority conflict section below.

## Authority Conflict (Unresolved)

**Roadmap v5.1, Section "LLM Policy":**
> Tier 1: Free cloud APIs (DeepSeek V3/R1, Gemini 2.5 Flash) — allowed per v5.1
> for hypothesis generation and scraper evaluation.

**PLAN_OF_RECORD, Section 0 "Roadmap Authority and Open Deltas":**
> Current toolchain policy remains no external LLM API calls.

These two documents disagree. The `KnowledgeStore._llm_provider` attribute is
included as an integration point for future claim extraction, but it defaults to
`None` (disabled). Cloud LLM calls are not enabled by this feature.

**Operator action required:** Before enabling cloud LLM calls for claim extraction
or scraper evaluation, the operator must explicitly resolve this conflict and update
either PLAN_OF_RECORD or ROADMAP v5.1 to reflect the agreed policy.

## Ingestion Pipeline (quick-260401-n1w)

**Shipped:** quick-260401-n1w (2026-04-01)

### New Modules

| Module | Purpose |
|--------|---------|
| `packages/research/ingestion/extractors.py` | `Extractor` ABC + `PlainTextExtractor` |
| `packages/research/ingestion/pipeline.py` | `IngestPipeline` orchestrating extract -> hard-stop -> eval-gate -> store |
| `packages/research/ingestion/retriever.py` | `query_knowledge_store` + `format_provenance` helpers |
| `tools/cli/research_ingest.py` | `research-ingest` CLI entrypoint |

### Architecture

```
source (file or text)
  -> PlainTextExtractor.extract()
  -> check_hard_stops()            [always runs; rejects empty/garbage docs]
  -> DocumentEvaluator.evaluate()  [optional; skip with --no-eval]
  -> KnowledgeStore.add_source_document()
  -> IngestResult (doc_id, chunk_count, gate_decision, rejected)
```

### CLI Usage

```bash
# Ingest a Markdown research doc (skip eval gate)
python -m polytool research-ingest --file path/to/paper.md --no-eval

# Ingest with JSON output
python -m polytool research-ingest --file path/to/paper.md --no-eval --json

# Ingest with eval gate (ManualProvider default -- always ACCEPT)
python -m polytool research-ingest --file path/to/paper.md

# Ingest raw inline text
python -m polytool research-ingest --text "Body text here..." --title "My Doc" --no-eval

# Use custom source type (affects freshness decay)
python -m polytool research-ingest --file analysis.txt --source-type dossier --no-eval
```

### Architecture Notes

- **No Chroma integration**: retriever.py queries the SQLite `derived_claims` table
  directly. The knowledge store remains a separate data plane from the Chroma/FTS5
  hybrid retrieval pipeline. Chroma integration is a follow-up task.
- **No automatic claim extraction**: the pipeline stores `source_documents` only.
  `derived_claims` must be created manually or by a future claim-extraction plan.
  (Authority conflict between Roadmap v5.1 and PLAN_OF_RECORD blocks LLM extraction.)
- **Hard-stop always runs**: `check_hard_stops()` is unconditional; `--no-eval` only
  skips the LLM scoring gate.

## Next Steps

1. **Seed Jon-Becker findings.** Roadmap v5.1 Phase 1 describes seeding the
   knowledge store with wallet analysis findings from the Jon-Becker dataset.
2. **Wire into RAG query pipeline.** Integrate with Chroma/FTS5 hybrid retrieval
   so that `external_knowledge` claims augment wallet-analysis context during
   alpha distillation.
3. **LLM-assisted claim extraction.** After the authority conflict above is
   resolved, implement automatic claim extraction from ingested source docs.
4. **Phase 2 research scraper.** The knowledge store is the data foundation for
   the Phase 2 automated research ingestion pipeline.
