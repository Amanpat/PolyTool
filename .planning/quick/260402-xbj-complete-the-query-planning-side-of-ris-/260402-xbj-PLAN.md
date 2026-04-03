---
phase: quick-260402-xbj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/research/synthesis/query_planner.py
  - packages/research/synthesis/hyde.py
  - packages/research/synthesis/retrieval.py
  - packages/research/synthesis/__init__.py
  - tests/test_ris_query_planner.py
  - docs/features/FEATURE-ris-query-planner.md
  - docs/dev_logs/2026-04-03_ris_query_planner.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements: [RIS_05]
must_haves:
  truths:
    - "A research topic string produces 3-5 diverse retrieval queries deterministically when no provider is available"
    - "A research topic string produces LLM-expanded queries when an ollama or future cloud provider is available"
    - "HyDE expansion produces a hypothetical document snippet from a query, with deterministic fallback"
    - "Combined retrieval merges direct + HyDE + decomposed results through the existing query_index RRF spine"
    - "All modules fall back to deterministic behavior when no LLM provider is reachable"
  artifacts:
    - path: "packages/research/synthesis/query_planner.py"
      provides: "QueryPlan dataclass, plan_queries() function, step-back query support"
      exports: ["QueryPlan", "plan_queries"]
    - path: "packages/research/synthesis/hyde.py"
      provides: "HyDE hypothetical document expansion utility"
      exports: ["HydeResult", "expand_hyde"]
    - path: "packages/research/synthesis/retrieval.py"
      provides: "Combined retrieval helper merging direct + HyDE + decomposed queries via existing spine"
      exports: ["RetrievalPlan", "retrieve_for_research"]
    - path: "tests/test_ris_query_planner.py"
      provides: "Deterministic offline tests for query planning, HyDE, combined retrieval, fallback behavior"
      min_lines: 100
  key_links:
    - from: "packages/research/synthesis/query_planner.py"
      to: "packages/research/evaluation/providers.py"
      via: "get_provider() for LLM-based query expansion; ManualProvider as deterministic fallback"
      pattern: "get_provider"
    - from: "packages/research/synthesis/hyde.py"
      to: "packages/research/evaluation/providers.py"
      via: "get_provider() for hypothetical document generation; deterministic template fallback"
      pattern: "get_provider"
    - from: "packages/research/synthesis/retrieval.py"
      to: "packages/polymarket/rag/query.py"
      via: "query_index() for actual retrieval, reusing hybrid/vector/lexical spine"
      pattern: "query_index"
---

<objective>
Complete the query-planning side of RIS_05 Synthesis Engine by implementing a real
query planner, HyDE expansion utility, and combined retrieval helper that integrate
with the existing canonical retrieval spine (packages/polymarket/rag/query.py).

Purpose: The RIS synthesis layer currently has precheck, calibration, and ledger
modules but no query decomposition or expansion capabilities. Research briefs and
prechecks need multi-angle retrieval to produce comprehensive evidence. This plan
adds query planning (topic -> diverse queries), HyDE (hypothetical document expansion
for better retrieval recall), and a combined retrieval helper that merges results
through the existing RRF-based query_index() pipeline.

Output: Three new modules in packages/research/synthesis/, comprehensive offline
tests, feature doc, dev log, CURRENT_STATE.md update.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md

<interfaces>
<!-- Key types and contracts the executor needs. Extracted from codebase. -->

From packages/research/evaluation/providers.py:
```python
class EvalProvider(ABC):
    @property
    def name(self) -> str: ...
    def score(self, doc: EvalDocument, prompt: str) -> str: ...

class ManualProvider(EvalProvider):
    # Returns all dims=3, total=12. name="manual"
    def score(self, doc: EvalDocument, prompt: str) -> str: ...

class OllamaProvider(EvalProvider):
    # Sends prompt to local Ollama. name="ollama"
    def score(self, doc: EvalDocument, prompt: str) -> str: ...

def get_provider(name: str = "manual", **kwargs) -> EvalProvider:
    # "manual" -> ManualProvider(), "ollama" -> OllamaProvider(**kwargs)
    # Cloud providers raise PermissionError/ValueError
```

From packages/research/evaluation/types.py:
```python
@dataclass
class EvalDocument:
    doc_id: str
    title: str
    author: str
    source_type: str
    source_url: str
    source_publish_date: Optional[str]
    body: str
    metadata: dict = field(default_factory=dict)
```

From packages/polymarket/rag/query.py:
```python
def query_index(
    *, question: str, embedder=None, k: int = 8,
    persist_directory=DEFAULT_PERSIST_DIR, collection_name=DEFAULT_COLLECTION,
    filter_prefixes=None, user_slug=None, doc_types=None,
    private_only=True, public_only=False, date_from=None, date_to=None,
    include_archive=False,
    hybrid: bool = False, lexical_only: bool = False,
    lexical_db_path=None, top_k_vector=25, top_k_lexical=25, rrf_k=RRF_K,
    reranker=None, rerank_top_n=50,
    knowledge_store_path=None, source_family=None, min_freshness=None,
    top_k_knowledge=25,
) -> List[dict]:
    # Returns list of dicts with keys: file_path, chunk_id, chunk_index, doc_id, score, snippet, metadata
```

From packages/research/synthesis/precheck.py (existing pattern for provider usage):
```python
def run_precheck(idea, provider_name="manual", ledger_path=None, knowledge_store=None, **kwargs):
    # Uses get_provider(provider_name, **kwargs)
    # Builds prompt, calls provider.score() with synthetic EvalDocument
    # Falls back gracefully when provider returns invalid JSON
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement query planner and HyDE expansion modules</name>
  <files>
    packages/research/synthesis/query_planner.py,
    packages/research/synthesis/hyde.py,
    packages/research/synthesis/__init__.py,
    tests/test_ris_query_planner.py (partial: planner + HyDE tests)
  </files>
  <behavior>
    Query Planner:
    - plan_queries("crypto pair bot profitability on Polymarket") returns QueryPlan with 3-5 queries
    - plan_queries with provider_name="manual" (default) returns deterministic template-based queries
    - plan_queries with provider_name="ollama" sends LLM prompt requesting JSON array of queries, parses response
    - plan_queries with include_step_back=True adds a broader contextual query (e.g., "What factors affect profitability in prediction markets?")
    - plan_queries falls back to deterministic queries when LLM returns unparseable JSON
    - QueryPlan dataclass has fields: topic (str), queries (list[str]), step_back_query (Optional[str]), provider_used (str), was_fallback (bool)
    - Deterministic fallback produces queries by combining topic with angle prefixes: evidence for, risks of, alternatives to, recent developments in, and optionally a step-back query

    HyDE:
    - expand_hyde("What is the optimal spread for market making on low-liquidity markets?") returns HydeResult
    - expand_hyde with provider_name="manual" returns a deterministic template document
    - expand_hyde with provider_name="ollama" sends LLM prompt asking for a hypothetical expert paragraph, returns raw text
    - HydeResult dataclass has fields: query (str), hypothetical_document (str), provider_used (str), was_fallback (bool)
    - Deterministic fallback generates a template: "Research indicates that {topic}. Key considerations include empirical evidence, domain constraints, and practical implementation factors."
    - expand_hyde falls back to deterministic template when LLM call fails
  </behavior>
  <action>
    1. Create packages/research/synthesis/query_planner.py:
       - Import get_provider from packages.research.evaluation.providers and EvalDocument from types
       - Define QueryPlan dataclass: topic, queries, step_back_query, provider_used, was_fallback
       - Define ANGLE_PREFIXES = ["evidence for", "risks of", "alternatives to", "recent developments in", "key assumptions behind"]
       - Define _deterministic_queries(topic, include_step_back) that produces queries by prepending each prefix to the topic, plus an optional step-back
       - Define _build_planner_prompt(topic, include_step_back) that instructs LLM to return JSON {"queries": [...], "step_back_query": "..."}
       - Define plan_queries(topic, provider_name="manual", include_step_back=False, max_queries=5, **kwargs) -> QueryPlan:
         - If provider_name == "manual", return deterministic queries immediately (was_fallback=False since it is the intended behavior)
         - Otherwise, get_provider(provider_name, **kwargs), build prompt, call provider.score() with synthetic EvalDocument
         - Parse JSON response; on parse failure or missing "queries" key, fall back to _deterministic_queries (was_fallback=True)
         - Clamp len(queries) to max_queries
       - Follow the same provider-usage pattern as run_precheck in precheck.py: synthetic EvalDocument, try/except around provider.score(), JSON parse with fallback

    2. Create packages/research/synthesis/hyde.py:
       - Import get_provider, EvalDocument
       - Define HydeResult dataclass: query, hypothetical_document, provider_used, was_fallback
       - Define _deterministic_hyde(query) that returns a template string incorporating the query text
       - Define _build_hyde_prompt(query) instructing the LLM: "Write a short (2-3 sentence) expert paragraph that would be found in a high-quality document answering: {query}. Return plain text only, no JSON."
       - Define expand_hyde(query, provider_name="manual", **kwargs) -> HydeResult:
         - If provider_name == "manual", return deterministic template (was_fallback=False)
         - Otherwise get_provider, call provider.score(), use raw response as hypothetical_document
         - On any exception, fall back to _deterministic_hyde (was_fallback=True)

    3. Update packages/research/synthesis/__init__.py:
       - Add imports for QueryPlan, plan_queries, HydeResult, expand_hyde
       - Add to __all__

    4. Write tests in tests/test_ris_query_planner.py (at least the planner and HyDE sections):
       Test classes: TestQueryPlanner, TestHyDE
       - test_plan_queries_manual_default: default call returns QueryPlan with 3-5 queries, was_fallback=False
       - test_plan_queries_manual_with_step_back: include_step_back=True returns non-None step_back_query
       - test_plan_queries_manual_max_queries: max_queries=3 clamps output
       - test_plan_queries_provider_fallback: monkeypatch provider.score to return garbage, verify was_fallback=True and queries still valid
       - test_plan_queries_provider_success: monkeypatch provider.score to return valid JSON, verify queries from LLM response
       - test_plan_queries_empty_topic: empty string still produces valid output (defensive)
       - test_hyde_manual_default: default call returns HydeResult with template text containing query words
       - test_hyde_manual_result_shape: verify all HydeResult fields populated
       - test_hyde_provider_fallback: monkeypatch provider.score to raise, verify was_fallback=True
       - test_hyde_provider_success: monkeypatch provider.score to return text, verify hypothetical_document matches
       All tests are offline, no network calls.
  </action>
  <verify>
    <automated>rtk python -m pytest tests/test_ris_query_planner.py::TestQueryPlanner tests/test_ris_query_planner.py::TestHyDE -v --tb=short</automated>
  </verify>
  <done>
    QueryPlan and HydeResult dataclasses exist. plan_queries() returns 3-5 diverse queries with deterministic fallback.
    expand_hyde() returns a hypothetical document. Both use existing provider infrastructure. At least 10 offline tests pass.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Implement combined retrieval helper + remaining tests + docs</name>
  <files>
    packages/research/synthesis/retrieval.py,
    packages/research/synthesis/__init__.py,
    tests/test_ris_query_planner.py (additional: retrieval + integration tests),
    docs/features/FEATURE-ris-query-planner.md,
    docs/dev_logs/2026-04-03_ris_query_planner.md,
    docs/CURRENT_STATE.md
  </files>
  <behavior>
    Combined Retrieval:
    - retrieve_for_research(topic="crypto pair profitability", query_index_kwargs={...}) returns RetrievalPlan with merged results
    - RetrievalPlan dataclass: topic, query_plan (QueryPlan), hyde_result (Optional[HydeResult]), results (list[dict]), result_sources (dict mapping chunk_id -> set of query labels)
    - With use_hyde=True, runs HyDE expansion on each planned query and includes HyDE-expanded queries in retrieval
    - With use_hyde=False, only runs direct queries from the query planner
    - Merges all result lists by chunk_id, keeping highest score per chunk (dedup)
    - Does NOT create a parallel retrieval stack: calls query_index() for each sub-query
    - Falls back gracefully: if query_index raises (e.g., no Chroma DB), returns empty results with the QueryPlan still populated
    - query_index_kwargs allows caller to pass through all query_index parameters (hybrid, lexical_only, embedder, etc.)
    - retrieve_for_research accepts provider_name for the planner/HyDE provider (default "manual")

    Tests:
    - test_retrieve_for_research_shape: verify RetrievalPlan fields populated
    - test_retrieve_dedup: two queries returning overlapping chunk_ids -> deduplicated
    - test_retrieve_no_hyde: use_hyde=False -> hyde_result is None
    - test_retrieve_fallback_no_index: monkeypatch query_index to raise, verify empty results but valid QueryPlan
    - test_retrieve_result_sources: verify result_sources tracks which queries found each chunk
    - test_full_pipeline_manual: plan_queries + expand_hyde + retrieve_for_research in sequence with manual provider
  </behavior>
  <action>
    1. Create packages/research/synthesis/retrieval.py:
       - Import plan_queries, QueryPlan from .query_planner
       - Import expand_hyde, HydeResult from .hyde
       - Import query_index from packages.polymarket.rag.query (deferred import inside function to avoid import-time Chroma dep)
       - Define RetrievalPlan dataclass: topic (str), query_plan (QueryPlan), hyde_result (Optional[HydeResult]), results (list[dict]), result_sources (dict[str, set[str]])
       - Define retrieve_for_research(
           topic: str,
           provider_name: str = "manual",
           use_hyde: bool = False,
           include_step_back: bool = False,
           max_queries: int = 5,
           query_index_kwargs: dict | None = None,
           **provider_kwargs,
         ) -> RetrievalPlan:
         - Step 1: plan = plan_queries(topic, provider_name, include_step_back, max_queries, **provider_kwargs)
         - Step 2: if use_hyde, hyde = expand_hyde(plan.queries[0] if plan.queries else topic, provider_name, **provider_kwargs)
         - Step 3: build sub_queries list = plan.queries + ([plan.step_back_query] if plan.step_back_query else []) + ([hyde.hypothetical_document] if hyde else [])
         - Step 4: for each sub_query, try: results = query_index(question=sub_query, **(query_index_kwargs or {})) except: results = []
         - Step 5: merge results by chunk_id (keep highest score), track result_sources
         - Step 6: sort merged results by score descending
         - Return RetrievalPlan(topic, plan, hyde, merged_results, result_sources)

    2. Update packages/research/synthesis/__init__.py:
       - Add RetrievalPlan, retrieve_for_research to imports and __all__

    3. Add remaining tests to tests/test_ris_query_planner.py in TestCombinedRetrieval class:
       - All tests monkeypatch query_index to return controlled mock results (list of dicts with chunk_id, score, snippet, file_path, chunk_index, doc_id, metadata)
       - test_retrieve_for_research_shape: verify all RetrievalPlan fields
       - test_retrieve_dedup: two sub-queries return overlapping chunk_ids, verify merged list has no duplicates and highest score kept
       - test_retrieve_no_hyde: use_hyde=False, hyde_result is None
       - test_retrieve_with_hyde: use_hyde=True, query_index called with extra hyde-expanded query
       - test_retrieve_fallback_no_index: query_index raises RuntimeError, results=[] but query_plan populated
       - test_retrieve_result_sources: verify result_sources dict tracks query labels correctly
       - test_full_pipeline_manual: end-to-end with manual provider, verify non-empty QueryPlan and valid structure
       At least 7 additional tests. Total file should have 17+ tests across three classes.

    4. Create docs/features/FEATURE-ris-query-planner.md:
       - Architecture overview: query_planner.py, hyde.py, retrieval.py
       - Provider compatibility: manual (deterministic), ollama (LLM-expanded), cloud (future via provider guard)
       - API reference for plan_queries, expand_hyde, retrieve_for_research
       - Fallback behavior documentation
       - Deferred: semantic query similarity dedup, multi-hop reasoning, parallel sub-query execution

    5. Create docs/dev_logs/2026-04-03_ris_query_planner.md:
       - Standard dev log format per CLAUDE.md convention
       - Files changed table, key decisions, commands run with results, deviations, next steps

    6. Update docs/CURRENT_STATE.md:
       - Add entry in RIS section for query planner + HyDE + combined retrieval shipped
       - Note deferred items

    7. Run full regression suite and report exact counts.
  </action>
  <verify>
    <automated>rtk python -m pytest tests/test_ris_query_planner.py -v --tb=short && rtk python -m pytest tests/ -x -q --tb=short</automated>
  </verify>
  <done>
    retrieve_for_research() produces merged, deduplicated results from multiple planned queries through the existing
    query_index() spine. At least 17 total offline tests pass across TestQueryPlanner, TestHyDE, TestCombinedRetrieval.
    Full regression suite passes with zero new failures. Feature doc, dev log, and CURRENT_STATE.md all updated.
  </done>
</task>

</tasks>

<verification>
1. All new tests pass: `rtk python -m pytest tests/test_ris_query_planner.py -v --tb=short`
2. Full regression passes: `rtk python -m pytest tests/ -x -q --tb=short`
3. CLI still loads: `python -m polytool --help`
4. No network calls in test suite (all provider calls mocked)
5. New modules importable: `python -c "from packages.research.synthesis import plan_queries, expand_hyde, retrieve_for_research; print('OK')"`
</verification>

<success_criteria>
- packages/research/synthesis/query_planner.py exists with plan_queries() returning 3-5 diverse queries
- packages/research/synthesis/hyde.py exists with expand_hyde() returning hypothetical documents
- packages/research/synthesis/retrieval.py exists with retrieve_for_research() merging results through query_index()
- All three modules use get_provider() from the existing provider infrastructure
- All three modules fall back to deterministic behavior when provider is unavailable or returns garbage
- 17+ offline tests pass in tests/test_ris_query_planner.py
- Full regression suite passes with zero new failures
- Feature doc and dev log written
- CURRENT_STATE.md updated
</success_criteria>

<output>
After completion, create `.planning/quick/260402-xbj-complete-the-query-planning-side-of-ris-/260402-xbj-SUMMARY.md`
</output>
