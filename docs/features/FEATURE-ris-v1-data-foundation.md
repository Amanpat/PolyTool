# FEATURE: RIS v1 Data Foundation

**Shipped:** quick-055 (2026-04-01)
**Status:** Complete (data-plane + query spine wired via quick-260402-ivb, MCP routing via quick-260403-lir)

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
- **Chroma/FTS5 hybrid retrieval wiring shipped** in quick-260402-ivb (query spine)
  and quick-260403-lir (MCP KnowledgeStore routing with `ks_active` flag). The
  original data-plane-only limitation is resolved.
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

## Claim Extraction Pipeline (Phase 4 — quick-260402-ogq)

**Shipped:** quick-260402-ogq (2026-04-02)

Heuristic claim extraction that populates the `derived_claims`, `claim_evidence`,
and `claim_relations` tables from already-ingested source documents. No LLM calls —
entirely regex/heuristic-based.

### New Modules

| Module | Purpose |
|--------|---------|
| `packages/research/ingestion/claim_extractor.py` | `HeuristicClaimExtractor` + extraction functions |
| `tools/cli/research_extract_claims.py` | `research-extract-claims` CLI entrypoint |

### Architecture

```
source_document (already ingested in KnowledgeStore)
  -> _get_document_body()       [re-reads file:// path or metadata_json body]
  -> chunk_text(body)           [400-word chunks, 80-word overlap]
  -> _extract_assertive_sentences(chunk)
      - strips merged heading tokens (chunk_text joins all words inline)
      - strips table-row fragments, code-fence markers
      - filters: len >= 30, not all-caps, not code-looking
      - returns up to 5 sentences per chunk
  -> _classify_claim_type(sentence) -> empirical | normative | structural
  -> _confidence_for_tier(trust_tier) -> 0.85 | 0.70 | 0.55
  -> store.add_claim(claim_text, claim_type, confidence, ...)
  -> store.add_evidence(claim_id, doc_id, excerpt, location_json)
  -> build_intra_doc_relations(claim_ids)
      - pairwise key-term comparison (>= 3 shared non-stopword terms)
      - SUPPORTS: both claims have same negation state
      - CONTRADICTS: one claim has negation, other does not
```

### Confidence Tier Mapping

| Trust Tier | Confidence |
|------------|------------|
| `PEER_REVIEWED` | 0.85 |
| `PRACTITIONER` | 0.70 (default) |
| `COMMUNITY` | 0.55 |

### Claim Types

| Type | Detection |
|------|-----------|
| `empirical` | Contains percentage, float, or 3+ digit number |
| `normative` | Contains should / must / recommend / best practice |
| `structural` | Contains architecture / system / design / structure / layer |

Default fallback is `empirical`.

### Idempotency Design

`_deterministic_created_at(doc_id, sentence, chunk_id)` generates a stable ISO-8601
timestamp from SHA-256 of content (doc_id + sentence + chunk_id + EXTRACTOR_ID).
This ensures `_sha256_id("claim", claim_text, actor, created_at)` in `KnowledgeStore`
produces the same claim ID on every re-run, making `INSERT OR IGNORE` idempotent.

Evidence rows are also deduplicated per `(claim_id, source_document_id)` — checked
before each `add_evidence()` call.

### Extractor Provenance

Every claim carries:
- `actor = "heuristic_v1"` (constant `EXTRACTOR_ID`)
- `notes` JSON: `{"extractor_id": "heuristic_v1", "chunk_id": N, "document_id": "...", "section_heading": "..."}`
- `claim_evidence` row with `excerpt` (first 500 chars of chunk) and `location` JSON:
  `{"chunk_id": N, "start_word": M, "end_word": K, "document_id": "...", "section_heading": "..."}`

### CLI Usage

```bash
# Extract from a single document
python -m polytool research-extract-claims --doc-id <DOC_ID>

# Extract from all documents in the knowledge store
python -m polytool research-extract-claims --all

# Dry run (count only, no writes)
python -m polytool research-extract-claims --all --dry-run

# JSON output
python -m polytool research-extract-claims --all --json

# Custom DB path
python -m polytool research-extract-claims --all --db-path artifacts/ris/knowledge.sqlite3
```

### Post-Ingest Integration

`IngestPipeline.ingest()` accepts `post_ingest_extract=True` for single-pass
ingestion + extraction:

```python
result = pipeline.ingest("paper.md", post_ingest_extract=True)
# Claims extracted automatically after source_document stored
```

Default is `False` (backward compatible).

### Authority Conflict Resolution (Partial)

The heuristic extractor resolves the immediate LLM authority conflict by operating
entirely locally without network or LLM calls. The `KnowledgeStore._llm_provider`
attribute remains `None`. Cloud LLM calls are still blocked pending operator decision
on the Roadmap v5.1 / PLAN_OF_RECORD conflict.

## Phase R5 — Dossier Pipeline (quick-260403-jy8)

**Shipped:** quick-260403-jy8 (2026-04-03)
**Status:** Complete — dossier extractor, adapter, batch path, and CLI all functional.

Converts locked-away wallet-scan dossier artifacts into queryable research memory in
the KnowledgeStore. Closes the `wallet-scan -> dossier -> knowledge` discovery loop.

### New Modules

| Module | Purpose |
|--------|---------|
| `packages/research/integration/dossier_extractor.py` | Parse dossier artifacts + build finding documents + ingest |
| `packages/research/ingestion/adapters.py` (updated) | `DossierAdapter` in `ADAPTER_REGISTRY["dossier"]` |
| `packages/research/integration/__init__.py` (updated) | Re-exports dossier pipeline functions |
| `tools/cli/research_dossier_extract.py` | `research-dossier-extract` CLI entrypoint |
| `tests/test_ris_dossier_extractor.py` | 31 offline deterministic tests |

### Architecture

```
wallet-scan -> export-dossier -> artifacts/dossiers/users/{slug}/{wallet}/{date}/{run_id}/
  dossier.json      header + detector labels + pnl_summary
  memo.md           LLM research packet (executive summary, hypotheses, evidence)
  hypothesis_candidates.json   ranked candidates with CLV metrics

research-dossier-extract [--dossier-dir DIR | --batch]
  -> extract_dossier_findings(dossier_dir)
      _parse_dossier_json()    => detector labels, pricing confidence, PnL trend
      _parse_memo()            => body text with TODOs stripped
      _parse_hypothesis_candidates()  => top candidates by CLV
      _build_finding_documents()      => 1-3 finding dicts per run
  -> ingest_dossier_findings(findings, store)
      DossierAdapter.adapt(finding)   => ExtractedDocument(source_family="dossier_report")
      content_hash dedup check (SHA-256)
      IngestPipeline.ingest(body, source_type="dossier", ...)
      KnowledgeStore.add_source_document()
```

### Document Types (1-3 per dossier run)

| Document Title | Content |
|---------------|---------|
| `Dossier Detectors: {slug}` | Strategy detector labels, pricing confidence, PnL trend |
| `Dossier Hypothesis Candidates: {slug}` | Top candidates with avg_clv_pct, beat_close_rate, count |
| `Dossier Memo: {slug}` | Full LLM research packet (TODO lines stripped) |

### Wallet Provenance in Metadata

Every ingested document carries:
- `wallet` — proxy wallet address
- `user_slug` — user handle (from `user_input` header or directory name)
- `run_id` — unique run identifier
- `dossier_path` — file system path to the run directory
- `export_id` — dossier export ID
- `detector_labels` — dict of detector name -> label
- `document_type` — one of `dossier_detectors`, `dossier_hypothesis_candidates`, `dossier_memo`
- `generated_at` — ISO timestamp of when the dossier was generated

### CLI Usage

```bash
# Single dossier run extraction
python -m polytool research-dossier-extract \
  --dossier-dir artifacts/dossiers/users/gabagool22/0x640a.../2026-03-29/47c5ac46-...

# Preview what would be extracted (no writes)
python -m polytool research-dossier-extract \
  --dossier-dir artifacts/dossiers/users/gabagool22/0x640a.../2026-03-29/47c5ac46-... \
  --dry-run

# Batch extraction — all dossiers under artifacts/dossiers/users/
python -m polytool research-dossier-extract --batch

# Batch with claim extraction enabled
python -m polytool research-dossier-extract --batch --extract-claims

# Custom DB path
python -m polytool research-dossier-extract --batch --db-path kb/rag/knowledge/knowledge.sqlite3
```

### Idempotency

Duplicate ingestion is safe. `ingest_dossier_findings()` pre-checks `content_hash`
against the `source_documents` table and skips any document already stored.
Running `research-dossier-extract` twice on the same dossier directory produces
identical `source_documents` counts.

### Deferred Items

- **Auto-trigger after wallet-scan**: **Shipped** via `--extract-dossier` flag on
  `wallet-scan` (quick-260403-lim). Run manually or pass `--extract-dossier` for
  automatic extraction after each per-wallet scan.
- **Wallet watchlist integration**: no automatic ingestion from the watchlist cadence.
- **LLM-assisted memo extraction**: the current memo parser is regex/heuristic. No LLM
  calls are made. Higher-precision extraction requires resolving the authority conflict.
- **source_url persistence**: `ingest_dossier_findings` stores `source_url = "internal://manual"`
  (PlainTextExtractor raw-text behavior). The `file://` URI is in the finding dict metadata
  but the `source_documents.source_url` column reflects the ingest mode, not the file path.

## Next Steps

1. **Wire into RAG query pipeline.** Integrate with Chroma/FTS5 hybrid retrieval
   so that `external_knowledge` claims augment wallet-analysis context during
   alpha distillation.
2. **LLM-assisted claim extraction.** After the authority conflict above is
   resolved, upgrade to LLM-based extraction for higher-precision claims.
3. **Claim lifecycle management.** Implement the SUPERSEDES relation for updating
   claims when newer evidence arrives.
4. **Phase 5 research scraper.** The knowledge store + claim pipeline is the
   data foundation for the Phase 5 automated research ingestion pipeline.
5. **Auto-trigger dossier extraction.** Wire `research-dossier-extract --batch`
   into the wallet-scan end-of-run hook or scheduler cadence.
