# Dev Log: RIS Phase 4 — Claim Extraction and Evidence Linking

**Date:** 2026-04-02
**Plan:** quick-260402-ogq
**Branch:** feat/ws-clob-feed
**Status:** Complete

## Objective

Implement a heuristic claim extraction pipeline that processes already-ingested
`source_documents` into structured `DERIVED_CLAIM` records with chunk-level
evidence links and typed relations (SUPPORTS/CONTRADICTS). No LLM calls.

## Files Changed

### Created
- `packages/research/ingestion/claim_extractor.py` — Core extraction module
- `tests/test_ris_claim_extraction.py` — 56 offline deterministic tests
- `tools/cli/research_extract_claims.py` — CLI entrypoint

### Modified
- `packages/research/ingestion/__init__.py` — Export HeuristicClaimExtractor + helpers
- `packages/research/ingestion/pipeline.py` — Add `post_ingest_extract` parameter
- `polytool/__main__.py` — Register `research-extract-claims` command
- `docs/features/FEATURE-ris-v1-data-foundation.md` — Phase 4 section

## Architecture

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

## Commands Run

```bash
# RED phase (previous session)
rtk git commit # test(quick-260402-ogq-01): add 56 failing tests for claim extraction

# GREEN phase — implementation
# (claim_extractor.py created, __init__.py updated)
rtk git commit # feat(quick-260402-ogq-01): HeuristicClaimExtractor, extract_and_link, idempotent claim IDs

# Task 2 verification
python -m polytool research-extract-claims --help
python -m polytool research-extract-claims --all --db-path ":memory:"

# Regression
python -m pytest tests/ -x -q --tb=short
```

**Test result:** 3262 passed, 0 failed, 25 warnings (all pre-existing utcnow deprecation).

## Decisions Made

### 1. Idempotency via deterministic created_at

`KnowledgeStore.add_claim()` without an explicit `created_at` calls `_utcnow_iso()`
at insertion time. Since claim IDs are `SHA-256("claim" + text + actor + created_at)`,
any two calls produce different IDs even for identical input.

**Fix:** `_deterministic_created_at(doc_id, sentence, chunk_id)` derives a stable
pseudo-timestamp from `SHA-256(doc_id + sentence + chunk_id + EXTRACTOR_ID)`, formatted
as `2000-01-01T00:00:00.{offset_micros}+00:00`. This is a valid ISO-8601 string and
produces consistent IDs across re-runs.

### 2. Evidence deduplication

`KnowledgeStore.add_evidence()` uses a plain INSERT (no INSERT OR IGNORE). On second
extraction run, this would create duplicate evidence rows for the same
`(claim_id, source_document_id)` pair.

**Fix:** Check for existing `(claim_id, source_document_id)` row before calling
`add_evidence()`. Claim table already deduplicates via INSERT OR IGNORE using
the deterministic ID.

### 3. Empirical regex threshold

Original `_EMPIRICAL_RE = re.compile(r"\d+%|\d+\.\d+|\b\d{2,}\b")` classified
"We recommend a minimum spread of 20 bps" as `empirical` (matched "20") instead
of `normative` (should/recommend takes priority).

**Fix:** Changed to `\b\d{3,}\b` — requires 3+ digit standalone numbers. Two-digit
numbers no longer trigger empirical classification, allowing normative/structural
keywords to win at the typical BPS/percentage ranges used in practitioner text.

### 4. chunk_text() produces inline merged text

`chunk_text()` is a word-level chunker. Markdown headings like `## Market Analysis`
appear inline as `## Market Analysis prose continues...`. The `_extract_assertive_sentences()`
function strips these heading tokens via regex before sentence splitting.

### 5. No LLM

The authority conflict between Roadmap v5.1 (Tier 1 free cloud APIs allowed) and
PLAN_OF_RECORD (no external LLM calls) remains unresolved. This extractor resolves
the immediate implementation need by operating entirely locally. The
`KnowledgeStore._llm_provider` attribute remains None. Cloud LLM calls still require
explicit operator decision.

### 6. post_ingest_extract is opt-in and non-fatal

`IngestPipeline.ingest(..., post_ingest_extract=True)` runs claim extraction after
document storage, but wraps it in `try/except`. Extraction failure never causes
ingest failure — the document is already stored at that point.

## Open Questions

- **Claim precision**: Heuristic sentence extraction is imprecise. A future
  LLM-assisted extractor (post authority-conflict resolution) would significantly
  improve claim quality and reduce false positives.
- **Relation quality**: SUPPORTS/CONTRADICTS based solely on shared key terms and
  negation presence is a rough proxy. Domain-aware relation classification is out
  of scope for Phase 4.
- **Large corpora**: Pairwise relation building is O(n²) per document. For documents
  with many chunks (500+ claims), this may be slow. Not a current problem given
  typical document sizes.

## Codex Review

Tier: Skip — no execution, risk manager, or order placement code touched.
