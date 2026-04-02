---
phase: quick-260402-ivb
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/rag/query.py
  - packages/research/ingestion/retriever.py
  - tools/cli/rag_query.py
  - tests/test_ris_query_spine.py
  - docs/features/FEATURE-ris-v2-query-spine.md
  - docs/dev_logs/2026-04-02_ris_phase2_query_spine_wiring.md
  - docs/CURRENT_STATE.md
autonomous: true
must_haves:
  truths:
    - "Seeded RIS corpus docs and claims are queryable through the canonical rag-query --hybrid path"
    - "KnowledgeStore claims merge into hybrid retrieval results alongside Chroma vector and FTS5 lexical hits"
    - "Contradicted claims are visibly downranked and annotated in output"
    - "Stale evidence is annotated with staleness notes in output"
    - "Provenance chain (claim -> source documents) survives the merge and is visible in output"
    - "Existing rag-query behavior is unchanged when --knowledge-store is not active"
  artifacts:
    - path: "packages/polymarket/rag/query.py"
      provides: "query_index() with knowledge_store retrieval as third RRF source"
      exports: ["query_index", "build_chroma_where"]
    - path: "packages/research/ingestion/retriever.py"
      provides: "query_knowledge_store_for_rrf() returning RRF-compatible result dicts"
      exports: ["query_knowledge_store_for_rrf", "query_knowledge_store_enriched", "format_enriched_report"]
    - path: "tools/cli/rag_query.py"
      provides: "CLI with --knowledge-store, --source-family, --min-freshness, --evidence-mode flags"
    - path: "tests/test_ris_query_spine.py"
      provides: "Offline tests for hybrid+KS retrieval, contradiction ranking, staleness, provenance"
      min_lines: 80
  key_links:
    - from: "packages/polymarket/rag/query.py"
      to: "packages/research/ingestion/retriever.py"
      via: "query_knowledge_store_for_rrf import in hybrid path"
      pattern: "query_knowledge_store_for_rrf"
    - from: "tools/cli/rag_query.py"
      to: "packages/polymarket/rag/query.py"
      via: "query_index() call with knowledge_store_path param"
      pattern: "knowledge_store"
    - from: "packages/research/ingestion/retriever.py"
      to: "packages/polymarket/rag/knowledge_store.py"
      via: "KnowledgeStore.query_claims() and get_provenance()"
      pattern: "KnowledgeStore"
---

<objective>
Wire the seeded RIS corpus into the canonical rag-query hybrid retrieval path.

Purpose: The RIS v1 data foundation (KnowledgeStore), ingestion pipeline, and
corpus seeder are all shipped, but KnowledgeStore claims exist as a sidecar
disconnected from the real retrieval path. This plan merges KnowledgeStore
derived-claim retrieval into the existing Chroma+FTS5 hybrid flow as a third
RRF source, so operators can query seeded RIS material through `rag-query
--hybrid --knowledge-store` and see provenance, contradiction annotations, and
freshness-aware ranking in the output.

Output: Modified query.py with KS-as-third-source, updated retriever.py with
RRF-compatible adapter, updated rag_query.py CLI with evidence/provenance flags,
new test file, feature doc, dev log, CURRENT_STATE update.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/PLAN_OF_RECORD.md
@docs/ARCHITECTURE.md
@docs/CURRENT_STATE.md
@docs/features/FEATURE-ris-v1-data-foundation.md
@docs/features/FEATURE-ris-v2-seed-and-benchmark.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/polymarket/rag/query.py:
```python
def query_index(
    *,
    question: str,
    embedder: Optional[BaseEmbedder] = None,
    k: int = 8,
    persist_directory: Path = DEFAULT_PERSIST_DIR,
    collection_name: str = DEFAULT_COLLECTION,
    filter_prefixes: Optional[List[str]] = None,
    user_slug: Optional[str] = None,
    doc_types: Optional[List[str]] = None,
    private_only: bool = True,
    public_only: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_archive: bool = False,
    hybrid: bool = False,
    lexical_only: bool = False,
    lexical_db_path: Optional[Path] = None,
    top_k_vector: int = 25,
    top_k_lexical: int = 25,
    rrf_k: int = RRF_K,
    reranker: Optional[BaseReranker] = None,
    rerank_top_n: int = 50,
) -> List[dict]:
    # Returns list of dicts with keys: file_path, chunk_id, chunk_index, doc_id, score, snippet, metadata
```

From packages/polymarket/rag/lexical.py:
```python
def reciprocal_rank_fusion(
    vector_results: List[dict],
    lexical_results: List[dict],
    rrf_k: int = RRF_K,
) -> List[dict]:
    # Combines two ranked lists by chunk_id, merging scores
```

From packages/polymarket/rag/knowledge_store.py:
```python
class KnowledgeStore:
    def query_claims(self, *, include_archived=False, include_superseded=False, apply_freshness=True) -> list[dict]:
        # Returns claim dicts with freshness_modifier and effective_score
    def get_provenance(self, claim_id: str) -> list[dict]:
        # Returns source_document dicts linked via claim_evidence
    def get_relations(self, claim_id: str, relation_type: Optional[str] = None) -> list[dict]:
        # Returns claim_relations dicts

DEFAULT_KNOWLEDGE_DB_PATH = Path("kb") / "rag" / "knowledge" / "knowledge.sqlite3"
```

From packages/research/ingestion/retriever.py:
```python
def query_knowledge_store(store, *, source_family=None, min_freshness=None, top_k=20) -> list[dict]
def query_knowledge_store_enriched(store, *, source_family=None, min_freshness=None, top_k=20, include_contradicted=False) -> list[dict]
    # Returns claim dicts enriched with provenance_docs, contradiction_summary, is_contradicted, staleness_note, lifecycle
def format_enriched_report(claims: list[dict]) -> str
def format_provenance(claim: dict, source_docs: list[dict]) -> str
```

From packages/polymarket/rag/lexical.py reciprocal_rank_fusion:
```python
# RRF merges by "chunk_id" key: score_rrf = sum(1/(rrf_k + rank)) across lists
# Each input result dict must have "chunk_id" and "score" keys
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add KnowledgeStore-as-third-source to hybrid retrieval + RRF-compatible adapter</name>
  <files>
    packages/research/ingestion/retriever.py,
    packages/polymarket/rag/query.py,
    packages/polymarket/rag/lexical.py,
    tests/test_ris_query_spine.py
  </files>
  <behavior>
    - Test: query_knowledge_store_for_rrf returns dicts with chunk_id, score, snippet, file_path, metadata keys matching RRF contract
    - Test: query_knowledge_store_for_rrf filters by source_family when provided
    - Test: query_knowledge_store_for_rrf filters by min_freshness when provided
    - Test: query_knowledge_store_for_rrf excludes lifecycle=archived by default
    - Test: contradicted claims have lower score than non-contradicted claims in RRF output
    - Test: stale claims (freshness_modifier < 0.5) have STALE annotation in metadata
    - Test: provenance_docs list is populated in metadata for claims with evidence links
    - Test: query_index with knowledge_store_path returns merged results from all three sources (vector mock, lexical mock, KS)
    - Test: query_index without knowledge_store_path behaves identically to current behavior (backward compat)
    - Test: RRF three-way fusion produces correct rank ordering when KS results are included
    - Test: text_query parameter on query_knowledge_store_for_rrf filters claims whose claim_text contains the query substring (case-insensitive)
  </behavior>
  <action>
    1. In `packages/research/ingestion/retriever.py`, add `query_knowledge_store_for_rrf()`:
       - Accepts `store: KnowledgeStore`, `text_query: Optional[str]`, `source_family: Optional[str]`,
         `min_freshness: Optional[float]`, `top_k: int = 25`
       - Calls `query_knowledge_store_enriched()` internally
       - For each enriched claim, produces a dict matching the RRF contract:
         `chunk_id`: claim["id"], `score`: claim["effective_score"],
         `snippet`: claim["claim_text"] (truncated to 400 chars),
         `file_path`: f"knowledge_store://claim/{claim['id']}"  (virtual path for KS results),
         `chunk_index`: 0, `doc_id`: claim.get("source_document_id", ""),
         `metadata`: dict with keys `source="knowledge_store"`, `claim_type`, `confidence`,
         `freshness_modifier`, `staleness_note`, `is_contradicted`,
         `contradiction_summary` (list), `provenance_docs` (list of dicts with title/source_url/source_family),
         `lifecycle`
       - If `text_query` is provided, filter claims where claim_text contains the query
         (case-insensitive substring match; this is NOT semantic search -- just a basic
         keyword filter to avoid returning all claims for every query). If text_query is None,
         return all claims (existing behavior for claim browsing).
       - Returns sorted by score descending, limited to top_k

    2. In `packages/polymarket/rag/lexical.py`, generalize `reciprocal_rank_fusion` to accept
       a list of ranked lists (not just two). Add a new function:
       `reciprocal_rank_fusion_multi(ranked_lists: List[List[dict]], rrf_k: int = RRF_K) -> List[dict]`
       that takes N ranked lists and merges them. The existing 2-list `reciprocal_rank_fusion`
       function remains unchanged (backward compat) but can be reimplemented as a thin wrapper
       around the multi version. Each result dict is merged by `chunk_id` key. Final list is
       sorted by fused score descending.

    3. In `packages/polymarket/rag/query.py`, add optional KnowledgeStore integration to `query_index()`:
       - Add new params: `knowledge_store_path: Optional[Path] = None`,
         `source_family: Optional[str] = None`, `min_freshness: Optional[float] = None`,
         `top_k_knowledge: int = 25`
       - When `knowledge_store_path is not None` and `hybrid=True`:
         a. Import KnowledgeStore and query_knowledge_store_for_rrf (deferred import to avoid
            import overhead when KS is not used)
         b. Open KnowledgeStore(knowledge_store_path)
         c. Call query_knowledge_store_for_rrf with text_query=question, source_family, min_freshness, top_k=top_k_knowledge
         d. Use `reciprocal_rank_fusion_multi([vector_results, lexical_results, ks_results], rrf_k=rrf_k)` instead of the two-list fusion
         e. Close KnowledgeStore after query
       - When `knowledge_store_path is None`: behavior is IDENTICAL to current code (two-list RRF)
       - When `hybrid=False` and `knowledge_store_path is not None`: raise ValueError
         ("knowledge_store requires --hybrid mode")
       - Do NOT change the lexical_only path

    4. Write `tests/test_ris_query_spine.py`:
       - All tests use KnowledgeStore(":memory:") -- no disk, no network
       - Seed a small corpus: 2 source docs, 3 claims (1 contradicted, 1 stale, 1 fresh),
         1 CONTRADICTS relation, 1 evidence link
       - Test query_knowledge_store_for_rrf output shape and content
       - Test filtering by source_family, min_freshness, text_query
       - Test that contradicted claim has lower score
       - Test that stale claim has staleness_note="STALE"
       - Test provenance_docs present for claims with evidence
       - Mock the vector and lexical paths in query_index to test three-way fusion
         (use unittest.mock.patch on _run_vector_query and _run_lexical_query)
       - Test backward compat: query_index without knowledge_store_path does not import KS
       - Verify reciprocal_rank_fusion_multi merges three lists correctly
  </action>
  <verify>
    <automated>python -m pytest tests/test_ris_query_spine.py -v --tb=short</automated>
  </verify>
  <done>
    KnowledgeStore claims merge into the hybrid retrieval path via three-way RRF fusion.
    Contradicted claims rank lower. Stale claims annotated. Provenance survives the merge.
    All new tests pass. Existing query_index behavior unchanged when knowledge_store_path is None.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire CLI flags + evidence output mode + docs + regression</name>
  <files>
    tools/cli/rag_query.py,
    docs/features/FEATURE-ris-v2-query-spine.md,
    docs/dev_logs/2026-04-02_ris_phase2_query_spine_wiring.md,
    docs/CURRENT_STATE.md
  </files>
  <action>
    1. In `tools/cli/rag_query.py`, add CLI flags to `build_parser()`:
       - `--knowledge-store`: Optional path to KnowledgeStore SQLite DB. When provided,
         enables KS as third retrieval source in hybrid mode. Defaults to None (not active).
         Special value "default" resolves to `kb/rag/knowledge/knowledge.sqlite3`.
       - `--source-family`: Optional source_family filter for KS claims (e.g. "book_foundational",
         "wallet_analysis", "news"). Only effective when --knowledge-store is active.
       - `--min-freshness`: Optional float [0,1] minimum freshness modifier for KS claims.
         Only effective when --knowledge-store is active.
       - `--evidence-mode`: Flag. When set, output includes enriched provenance/contradiction
         annotations for KS-sourced results. Without this flag, KS results appear as normal
         snippets (claim_text as snippet, score as score). With this flag, each KS result
         includes a provenance section and contradiction annotations in the JSON output.
       - `--top-k-knowledge`: int, default 25. Number of KS candidates for RRF fusion.

    2. In `main()`, wire the new flags:
       - If `--knowledge-store` is "default", resolve to DEFAULT_KNOWLEDGE_DB_PATH from
         knowledge_store module
       - If `--knowledge-store` is provided but `--hybrid` is not set, print error and return 1
       - Pass knowledge_store_path, source_family, min_freshness, top_k_knowledge to query_index()
       - In the JSON output payload, add a `knowledge_store` section:
         `{"active": bool, "path": str|null, "source_family": str|null, "min_freshness": float|null}`

    3. When `--evidence-mode` is active, post-process KS-sourced results in the output:
       - For results where metadata.source == "knowledge_store", add enriched fields to the
         JSON output: provenance_docs, contradiction_summary, staleness_note, lifecycle, is_contradicted
       - These fields already exist in the metadata dict from query_knowledge_store_for_rrf;
         promote them to top-level keys in the result dict for readability

    4. Create `docs/features/FEATURE-ris-v2-query-spine.md`:
       - Status: Implemented
       - What shipped: KnowledgeStore as third hybrid retrieval source via three-way RRF
       - Architecture diagram: vector(Chroma) + lexical(FTS5) + claims(KnowledgeStore) -> RRF -> rerank -> output
       - CLI usage examples (basic hybrid+KS, with evidence-mode, with source-family filter)
       - How contradiction downranking works (0.5x penalty in effective_score -> lower RRF rank)
       - How freshness affects ranking (exponential decay -> lower effective_score -> lower RRF rank)
       - How provenance is surfaced (metadata.provenance_docs in evidence-mode)
       - What is NOT included: semantic search over claims (keyword filter only), automatic claim extraction, Qdrant migration
       - Tests section listing test file and count

    5. Create `docs/dev_logs/2026-04-02_ris_phase2_query_spine_wiring.md`:
       - Files changed and why (all files in this plan)
       - Commands run + output (pytest results, CLI smoke test)
       - Decisions: three-way RRF over separate sidecar, keyword filter over semantic, evidence-mode as opt-in
       - Note: This closes the previously deferred "Chroma wiring" gap from FEATURE-ris-v1-data-foundation.md
       - Remaining limitations: no semantic matching on claims (keyword only), no automatic claim extraction

    6. Update `docs/CURRENT_STATE.md`:
       - Add RIS Phase 2 query spine section after existing RIS entries
       - Note: KnowledgeStore wired into hybrid retrieval as third RRF source
       - Note: `rag-query --hybrid --knowledge-store default --evidence-mode` is the canonical query path
       - Note: Previously deferred Chroma wiring gap is now closed

    7. Run full regression: `python -m pytest tests/ -x -q --tb=short`
       Report exact pass/fail counts. All existing tests must pass.

    8. CLI smoke test:
       `python -m polytool rag-query --question "market microstructure" --hybrid --lexical-only` should error (mutually exclusive)
       `python -m polytool --help` should list rag-query with no import errors
  </action>
  <verify>
    <automated>python -m pytest tests/ -x -q --tb=short</automated>
  </verify>
  <done>
    CLI exposes --knowledge-store, --source-family, --min-freshness, --evidence-mode, --top-k-knowledge flags.
    Evidence mode shows provenance and contradiction annotations for KS-sourced results.
    Feature doc, dev log, and CURRENT_STATE are updated with exact shipped truth.
    Full regression suite passes with zero new failures.
    The previously deferred "Chroma wiring" gap from RIS v1 data foundation is explicitly closed.
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_ris_query_spine.py -v --tb=short` -- all new spine tests pass
2. `python -m pytest tests/ -x -q --tb=short` -- full regression, zero new failures
3. `python -m polytool --help` -- CLI loads cleanly, no import errors
4. Spot-check: KS-sourced results in rag-query output include `metadata.source: "knowledge_store"`
</verification>

<success_criteria>
- Seeded RIS docs/claims are queryable through `rag-query --hybrid --knowledge-store default`
- Three-way RRF fusion (vector + lexical + KS claims) produces merged ranked results
- Contradicted claims rank lower and are annotated
- Stale claims are annotated with STALE/AGING notes
- Provenance chain (claim -> source_documents) is visible in evidence-mode output
- Existing rag-query behavior is unchanged when --knowledge-store is not provided
- All existing tests pass (regression)
- Feature doc, dev log, CURRENT_STATE updated
</success_criteria>

<output>
After completion, create `.planning/quick/260402-ivb-complete-ris-phase-2-retrieval-query-spi/260402-ivb-SUMMARY.md`
</output>
