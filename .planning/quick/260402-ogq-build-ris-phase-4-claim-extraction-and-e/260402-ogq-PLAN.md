---
phase: quick-260402-ogq
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/ingestion/claim_extractor.py
  - packages/research/ingestion/__init__.py
  - packages/research/ingestion/pipeline.py
  - tools/cli/research_extract_claims.py
  - polytool/__main__.py
  - tests/test_ris_claim_extraction.py
  - docs/dev_logs/2026-04-02_ris_phase4_claim_extraction.md
  - docs/features/FEATURE-ris-v1-data-foundation.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "Ingested source documents produce structured DERIVED_CLAIM records via a heuristic extractor"
    - "Each extracted claim links to its originating chunk via CLAIM_EVIDENCE rows with chunk_id, excerpt, and position"
    - "Lightweight SUPPORTS and CONTRADICTS relations are created between claims sharing key terms from the same document"
    - "Claims inherit trust_tier from their source document and carry extractor_id provenance"
    - "CLI command research-extract-claims runs claim extraction on already-seeded documents"
    - "Extracted claims surface through the existing retrieval path (query_knowledge_store_enriched, RRF) with provenance"
  artifacts:
    - path: "packages/research/ingestion/claim_extractor.py"
      provides: "HeuristicClaimExtractor class, extract_claims_from_document(), build_intra_doc_relations()"
      min_lines: 120
    - path: "tools/cli/research_extract_claims.py"
      provides: "research-extract-claims CLI entrypoint"
      exports: ["main"]
    - path: "tests/test_ris_claim_extraction.py"
      provides: "Deterministic offline tests for claim extraction, evidence linking, relation insertion, retrieval"
      min_lines: 100
  key_links:
    - from: "packages/research/ingestion/claim_extractor.py"
      to: "packages/polymarket/rag/knowledge_store.py"
      via: "add_claim, add_evidence, add_relation CRUD methods"
      pattern: "store\\.add_claim|store\\.add_evidence|store\\.add_relation"
    - from: "packages/research/ingestion/claim_extractor.py"
      to: "packages/polymarket/rag/chunker.py"
      via: "chunk_text to split document body into TextChunks for evidence linking"
      pattern: "chunk_text"
    - from: "tools/cli/research_extract_claims.py"
      to: "packages/research/ingestion/claim_extractor.py"
      via: "imports extract_claims_from_document"
      pattern: "extract_claims_from_document"
---

<objective>
Build the RIS Phase 4 claim extraction pipeline: a heuristic-based extractor that
processes already-ingested source documents into structured DERIVED_CLAIM records with
chunk-level evidence links, lightweight typed relations (SUPPORTS/CONTRADICTS), and
retrieval-ready trust/lifecycle metadata. No graph database, no LLM calls.

Purpose: Populate the existing but empty derived_claims/claim_evidence/claim_relations
tables so that the KnowledgeStore becomes a live claim-level knowledge base, not just
a document store. This enables the existing RRF retrieval pipeline to surface
structured claims with provenance during research queries.

Output: claim_extractor.py module, research-extract-claims CLI command, comprehensive
tests, dev log, updated feature doc.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/polymarket/rag/knowledge_store.py
@packages/research/ingestion/extractors.py
@packages/research/ingestion/pipeline.py
@packages/research/ingestion/retriever.py
@packages/research/ingestion/seed.py
@packages/polymarket/rag/chunker.py
@docs/features/FEATURE-ris-v1-data-foundation.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/polymarket/rag/knowledge_store.py:
```python
class KnowledgeStore:
    def add_claim(self, *, claim_text: str, claim_type: str, confidence: float,
                  trust_tier: str, validation_status: str = "UNTESTED",
                  lifecycle: str = "active", actor: str,
                  created_at: Optional[str] = None, updated_at: Optional[str] = None,
                  source_document_id: Optional[str] = None, scope: Optional[str] = None,
                  tags: Optional[str] = None, notes: Optional[str] = None,
                  superseded_by: Optional[str] = None) -> str: ...

    def add_evidence(self, *, claim_id: str, source_document_id: str,
                     excerpt: Optional[str] = None, location: Optional[str] = None,
                     created_at: Optional[str] = None) -> int: ...

    def add_relation(self, source_claim_id: str, target_claim_id: str,
                     relation_type: str, *, created_at: Optional[str] = None) -> int: ...

    def get_source_document(self, doc_id: str) -> Optional[dict]: ...
    def get_claim(self, claim_id: str) -> Optional[dict]: ...
    def get_provenance(self, claim_id: str) -> list[dict]: ...
    def get_relations(self, claim_id: str, relation_type: Optional[str] = None) -> list[dict]: ...
    def query_claims(self, *, include_archived=False, include_superseded=False,
                     apply_freshness=True) -> list[dict]: ...
```

From packages/polymarket/rag/chunker.py:
```python
@dataclass(frozen=True)
class TextChunk:
    chunk_id: int
    text: str
    start_word: int
    end_word: int

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> List[TextChunk]: ...
```

From packages/research/ingestion/extractors.py:
```python
@dataclass
class ExtractedDocument:
    title: str
    body: str
    source_url: str
    source_family: str
    author: str = "unknown"
    publish_date: Optional[str] = None
    metadata: dict = field(default_factory=dict)

EXTRACTOR_REGISTRY: dict[str, type[Extractor]]
```

From packages/research/ingestion/retriever.py:
```python
def query_knowledge_store_enriched(store, *, source_family=None, min_freshness=None,
                                    top_k=20, include_contradicted=False) -> list[dict]: ...
def query_knowledge_store_for_rrf(store, *, text_query=None, source_family=None,
                                   min_freshness=None, top_k=25) -> list[dict]: ...
```

KnowledgeStore claim_evidence schema:
```sql
CREATE TABLE IF NOT EXISTS claim_evidence (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id            TEXT NOT NULL REFERENCES derived_claims(id),
    source_document_id  TEXT NOT NULL REFERENCES source_documents(id),
    excerpt             TEXT,
    location            TEXT,
    created_at          TEXT NOT NULL
);
```

claim_relations allowed types: SUPPORTS, CONTRADICTS, SUPERSEDES, EXTENDS
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement HeuristicClaimExtractor and evidence-linking pipeline</name>
  <files>
    packages/research/ingestion/claim_extractor.py,
    packages/research/ingestion/__init__.py,
    tests/test_ris_claim_extraction.py
  </files>
  <behavior>
    - Test: extract_claims_from_document on a multi-section Markdown doc produces >= 1 DERIVED_CLAIM per assertive section
    - Test: each claim has claim_text, claim_type, confidence, trust_tier, validation_status="UNTESTED", lifecycle="active", actor="heuristic_v1"
    - Test: confidence is 0.85 for claims from PEER_REVIEWED docs, 0.70 for PRACTITIONER, 0.55 for COMMUNITY, 0.70 default
    - Test: each claim has a CLAIM_EVIDENCE row linking it to the source_document_id with excerpt (chunk text truncated to 500 chars) and location (JSON string: {"chunk_id": N, "start_word": M, "end_word": K, "document_id": "...", "section_heading": "..."})
    - Test: build_intra_doc_relations creates SUPPORTS between claims sharing 3+ non-stopword terms from the same doc
    - Test: build_intra_doc_relations creates CONTRADICTS when one claim has negation qualifiers (not, never, no, cannot, unlikely, incorrect, false, fail, reject) for subject terms shared with another claim
    - Test: claims with no assertive content (empty chunk, only code blocks, only table data) are skipped
    - Test: duplicate extraction is idempotent (running twice on same doc does not double claims, because KnowledgeStore uses INSERT OR IGNORE with deterministic IDs)
    - Test: extraction context preserved in claim notes field as JSON with keys: extractor_id, chunk_id, document_id, section_heading
    - Test: scope field inherited from source_document metadata if available (e.g., "crypto" from tags)
    - Test: retrieval via query_knowledge_store_enriched returns extracted claims with provenance_docs populated
    - Test: retrieval via query_knowledge_store_for_rrf returns extracted claims in RRF-compatible format
  </behavior>
  <action>
    Create `packages/research/ingestion/claim_extractor.py` with:

    1. **Claim sentence detection** — `_extract_assertive_sentences(text: str) -> list[str]`:
       - Split chunk text into sentences (period/exclamation/newline boundaries).
       - Filter to sentences that are assertive: length >= 30 chars, contain a verb-like
         pattern (heuristic: not all-caps, not a heading line, not a code line, not just
         a table row, not a URL). Regex: skip lines matching `^\s*[#|>\`~]` or `^\s*[-*]\s*$`
         or lines that are entirely code/URL.
       - Return up to 5 assertive sentences per chunk (cap to avoid claim explosion on
         dense technical docs).

    2. **Confidence tier mapping** — `_confidence_for_tier(trust_tier: str) -> float`:
       - PEER_REVIEWED -> 0.85, PRACTITIONER -> 0.70, COMMUNITY -> 0.55, default -> 0.70

    3. **Claim type heuristic** — `_classify_claim_type(sentence: str) -> str`:
       - Contains numbers/percentages/measurements -> "empirical"
       - Contains "should"/"must"/"recommend"/"best practice" -> "normative"
       - Contains "architecture"/"system"/"design"/"structure"/"layer" -> "structural"
       - Default -> "empirical" (most research corpus content is empirical)

    4. **Negation detection** — `_has_negation(sentence: str) -> bool`:
       - Returns True if sentence contains negation qualifiers: "not ", " no ", "never",
         "cannot", "unlikely", "incorrect", "false", " fail", "reject", "don't", "doesn't",
         "won't", "shouldn't". Case-insensitive word boundary matching.

    5. **Key term extraction** — `_extract_key_terms(sentence: str) -> set[str]`:
       - Lowercase, split on whitespace/punctuation, filter stopwords (the, a, an, is, are,
         was, were, be, been, has, have, had, do, does, did, will, would, could, should, can,
         may, might, shall, to, of, in, for, on, at, by, with, from, and, or, but, if, then,
         that, this, it, its, they, them, their, we, our, you, your, he, she, him, her).
       - Return set of remaining terms with len >= 3.

    6. **Main extraction function** — `extract_claims_from_document(store: KnowledgeStore, doc_id: str) -> list[str]`:
       - Load source document via `store.get_source_document(doc_id)`.
       - If doc not found, return empty list.
       - Retrieve body text: parse metadata_json for body, OR re-read from source_url if
         file:// path. (The pipeline stores content_hash but not body text in the DB.
         Re-read the file to get the text.)
       - Chunk body via `chunk_text(body)`.
       - Determine trust_tier from source doc's `confidence_tier` field (default "PRACTITIONER").
       - Determine scope from metadata_json tags if available.
       - For each chunk:
         - Determine section_heading from chunk position (scan body for heading lines, map
           chunk start_word to nearest preceding heading).
         - Extract assertive sentences via `_extract_assertive_sentences(chunk.text)`.
         - For each sentence:
           - Compute claim_type via `_classify_claim_type`.
           - Compute confidence via `_confidence_for_tier`.
           - Build notes JSON: `{"extractor_id": "heuristic_v1", "chunk_id": chunk.chunk_id, "document_id": doc_id, "section_heading": heading}`.
           - Call `store.add_claim(claim_text=sentence, claim_type=claim_type, confidence=confidence, trust_tier=trust_tier, validation_status="UNTESTED", lifecycle="active", actor="heuristic_v1", source_document_id=doc_id, scope=scope, tags=None, notes=json.dumps(notes_dict))`.
           - Call `store.add_evidence(claim_id=claim_id, source_document_id=doc_id, excerpt=chunk.text[:500], location=json.dumps({"chunk_id": chunk.chunk_id, "start_word": chunk.start_word, "end_word": chunk.end_word, "document_id": doc_id, "section_heading": heading}))`.
           - Collect claim_id.
       - Return list of claim_ids created.

    7. **Relation builder** — `build_intra_doc_relations(store: KnowledgeStore, claim_ids: list[str]) -> int`:
       - For each pair (i, j) where i < j in claim_ids:
         - Load both claims via `store.get_claim()`.
         - Extract key terms from both claim_texts.
         - Compute shared_terms = terms_i & terms_j.
         - If len(shared_terms) >= 3:
           - If one claim `_has_negation` and the other does not -> CONTRADICTS.
           - Else -> SUPPORTS.
           - Call `store.add_relation(claim_ids[i], claim_ids[j], relation_type)`.
           - Increment counter.
       - Return count of relations created.

    8. **Convenience wrapper** — `extract_and_link(store: KnowledgeStore, doc_id: str) -> dict`:
       - Calls `extract_claims_from_document` then `build_intra_doc_relations`.
       - Returns `{"doc_id": doc_id, "claims_extracted": N, "relations_created": M, "claim_ids": [...]}`.

    Update `packages/research/ingestion/__init__.py`:
    - Add imports: `extract_claims_from_document`, `build_intra_doc_relations`, `extract_and_link`, `HeuristicClaimExtractor` (if you wrap functions in a class for registry consistency).
    - Add to `__all__`.

    Create `tests/test_ris_claim_extraction.py` with all behavior tests above (no network,
    no LLM, all using KnowledgeStore(":memory:") and temporary fixture files via tmp_path).
    Use a fixture Markdown document with:
    - Multiple H2 sections with assertive prose
    - A section with negation ("X does not support Y")
    - A code-only section (should produce no claims)
    - A table-only section (should produce no claims)
    - At least two sections sharing key terms (to test SUPPORTS relation)
    - At least one pair where one has negation of shared terms (to test CONTRADICTS)

    Target: >= 15 tests covering extraction shape, evidence linking, relations, idempotency,
    retrieval surfacing, edge cases.
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_claim_extraction.py -v --tb=short</automated>
  </verify>
  <done>
    - claim_extractor.py exists with extract_claims_from_document, build_intra_doc_relations, extract_and_link
    - All claims written to derived_claims with actor="heuristic_v1", proper trust_tier, confidence, lifecycle, validation_status
    - Every claim has at least one claim_evidence row with chunk excerpt and structured location JSON
    - SUPPORTS/CONTRADICTS relations created between claims sharing key terms
    - Extraction is idempotent (deterministic IDs via KnowledgeStore INSERT OR IGNORE)
    - All tests pass with zero network calls
  </done>
</task>

<task type="auto">
  <name>Task 2: CLI command and integration wiring</name>
  <files>
    tools/cli/research_extract_claims.py,
    polytool/__main__.py,
    packages/research/ingestion/pipeline.py,
    docs/dev_logs/2026-04-02_ris_phase4_claim_extraction.md,
    docs/features/FEATURE-ris-v1-data-foundation.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
    1. Create `tools/cli/research_extract_claims.py` following the existing CLI pattern
       (see `tools/cli/research_ingest.py`, `tools/cli/research_seed.py` for reference):
       - `main(argv: list[str] | None = None) -> int`
       - argparse with:
         - `--doc-id DOC_ID` — extract claims from a single document by ID
         - `--all` — extract claims from ALL source_documents in the store
         - `--db-path PATH` — optional KnowledgeStore DB path (default: kb/rag/knowledge/knowledge.sqlite3)
         - `--dry-run` — report what would be extracted without writing
         - `--json` — JSON output format
       - When `--all`: iterate all source_documents in the store (query the table), call
         `extract_and_link` for each, collect aggregate results.
       - When `--doc-id`: call `extract_and_link` for the single document.
       - Print human-readable summary: documents processed, claims extracted, relations created.
       - With `--json`: print JSON dict with keys: documents_processed, total_claims, total_relations, per_doc_results.
       - Return 0 on success, 1 on error.

    2. Wire CLI into `polytool/__main__.py`:
       - Add `research-extract-claims` to the command router following the existing pattern.
       - Import pattern: `from tools.cli.research_extract_claims import main as research_extract_claims_main`

    3. Optionally add a `post_ingest_extract` parameter to `IngestPipeline.ingest()`:
       - If True, after successful source_document storage, automatically call
         `extract_claims_from_document` and `build_intra_doc_relations`.
       - Default False (backward compatible, existing tests unaffected).
       - This enables future `research-ingest --extract-claims` one-pass workflow.

    4. Write `docs/dev_logs/2026-04-02_ris_phase4_claim_extraction.md`:
       - Standard dev log format (Date, Plan, Branch, Objective, Files Changed, Commands Run,
         Decisions Made, Open Questions, Codex Review: Skip tier).
       - Document the heuristic claim extraction approach, confidence mapping, relation logic,
         and the design decision to keep it local-first / no-LLM.

    5. Update `docs/features/FEATURE-ris-v1-data-foundation.md`:
       - Add a "## Claim Extraction Pipeline (Phase 4)" section documenting:
         - HeuristicClaimExtractor: sentence-level extraction from chunks
         - Confidence tier mapping
         - Evidence linking via claim_evidence with chunk-level location
         - Typed relations: SUPPORTS (shared terms), CONTRADICTS (negation + shared terms)
         - CLI: `python -m polytool research-extract-claims --all`
         - Extractor provenance: actor="heuristic_v1", notes JSON with extraction context

    6. Update `docs/CURRENT_STATE.md`:
       - Add a bullet under the RIS section noting Phase 4 claim extraction is complete.
       - Note total test count.
  </action>
  <verify>
    <automated>python -m polytool research-extract-claims --help && python -m pytest tests/ -x -q --tb=short</automated>
  </verify>
  <done>
    - `python -m polytool research-extract-claims --help` prints usage and exits 0
    - `python -m polytool research-extract-claims --all --db-path :memory:` runs without error (no docs to extract = 0 claims)
    - Full regression suite passes with no regressions
    - Dev log exists at docs/dev_logs/2026-04-02_ris_phase4_claim_extraction.md
    - Feature doc updated with Phase 4 claim extraction section
    - CURRENT_STATE.md updated with Phase 4 status
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_ris_claim_extraction.py -v --tb=short` — all claim extraction tests pass
2. `python -m pytest tests/ -x -q --tb=short` — full regression suite passes (expect ~3120+ tests)
3. `python -m polytool --help` — CLI loads, research-extract-claims visible in command list
4. `python -m polytool research-extract-claims --help` — prints usage, exits 0
5. `python -c "from packages.research.ingestion.claim_extractor import extract_claims_from_document, build_intra_doc_relations, extract_and_link; print('OK')"` — imports succeed
</verification>

<success_criteria>
- HeuristicClaimExtractor extracts structured claims from ingested documents without LLM calls
- Every claim links to its source chunk via claim_evidence with excerpt and structured location
- SUPPORTS and CONTRADICTS relations are deterministically created between related claims
- Claims carry extractor provenance (actor="heuristic_v1", notes JSON with extraction context)
- CLI command research-extract-claims works for single-doc and batch extraction
- Existing retrieval paths (query_knowledge_store_enriched, RRF) surface extracted claims with provenance
- All existing tests continue to pass
- No graph database, no network calls, no LLM dependency
</success_criteria>

<output>
After completion, create `.planning/quick/260402-ogq-build-ris-phase-4-claim-extraction-and-e/260402-ogq-SUMMARY.md`
</output>
