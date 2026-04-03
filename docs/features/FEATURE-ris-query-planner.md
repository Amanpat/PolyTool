# Feature: RIS Query Planner, HyDE Expansion, and Combined Retrieval

**Status:** Shipped (2026-04-03)
**Task:** quick-260402-xbj
**Requirement:** RIS_05 (Synthesis Engine — query planning side)

---

## Overview

Three new modules in `packages/research/synthesis/` that complete the query-planning
side of the RIS_05 Synthesis Engine. They enable multi-angle evidence retrieval for
research briefs and prechecks by decomposing a topic into diverse queries, optionally
expanding with HyDE (Hypothetical Document Embedding), and merging results through
the existing RRF-based `query_index()` spine.

---

## Architecture

```
Research Topic
      │
      ▼
 query_planner.py  ──► QueryPlan
      │                  (queries, step_back_query)
      │
      ├──► hyde.py ──────► HydeResult
      │       (optional)    (hypothetical_document)
      │
      ▼
  retrieval.py ──► RetrievalPlan
      │              (merged, deduped results)
      │
      ▼
  query_index()  ◄─── packages/polymarket/rag/query.py
  (existing RRF spine)
```

### Module responsibilities

| Module | Exports | Responsibility |
|--------|---------|----------------|
| `query_planner.py` | `QueryPlan`, `plan_queries()` | Topic -> diverse retrieval queries |
| `hyde.py` | `HydeResult`, `expand_hyde()` | Query -> hypothetical document passage |
| `retrieval.py` | `RetrievalPlan`, `retrieve_for_research()` | Multi-query retrieval with dedup/merge |

---

## Provider Compatibility

All three modules follow the same provider pattern as `precheck.py`:

| Provider | Behavior |
|----------|----------|
| `"manual"` (default) | Fully deterministic, offline, no LLM required. `was_fallback=False`. |
| `"ollama"` | Sends prompt to local Ollama. Falls back to deterministic on failure. `was_fallback=True` on fallback. |
| Cloud providers | Not yet implemented (RIS v2 deliverable). Gated by `RIS_ENABLE_CLOUD_PROVIDERS=1`. |

---

## API Reference

### `plan_queries(topic, provider_name="manual", include_step_back=False, max_queries=5, **kwargs) -> QueryPlan`

Generates diverse retrieval queries for a research topic.

**QueryPlan fields:**
- `topic: str` — original topic string
- `queries: list[str]` — 3-5 diverse retrieval queries
- `step_back_query: Optional[str]` — broader contextual query (if `include_step_back=True`)
- `provider_used: str` — provider identifier
- `was_fallback: bool` — True if LLM failed and deterministic fallback was used

**Deterministic query generation** uses ANGLE_PREFIXES:
- `"evidence for {topic}"`
- `"risks of {topic}"`
- `"alternatives to {topic}"`
- `"recent developments in {topic}"`
- `"key assumptions behind {topic}"`

```python
from packages.research.synthesis import plan_queries

# Offline (deterministic)
qp = plan_queries("crypto pair bot profitability on Polymarket")
# qp.queries = ["evidence for crypto pair bot...", "risks of crypto pair bot...", ...]

# With step-back
qp = plan_queries("market making strategies", include_step_back=True)
# qp.step_back_query = "What broader factors affect market making strategies?"

# LLM-expanded (requires Ollama)
qp = plan_queries("prediction market arbitrage", provider_name="ollama")
```

---

### `expand_hyde(query, provider_name="manual", **kwargs) -> HydeResult`

Generates a hypothetical document passage that answers the query. The passage
can be used as a retrieval query — its embedding is typically closer to relevant
documents than the original query embedding (HyDE paper technique).

**HydeResult fields:**
- `query: str` — original query
- `hypothetical_document: str` — generated passage
- `provider_used: str` — provider identifier
- `was_fallback: bool` — True if LLM failed

**Deterministic template:**
```
Research indicates that {query}. Key considerations include empirical evidence,
domain constraints, and practical implementation factors. Studies in this area
show that careful analysis of underlying assumptions and risk factors is essential
for deriving actionable conclusions.
```

```python
from packages.research.synthesis import expand_hyde

hr = expand_hyde("What is the optimal spread for market making on low-liquidity markets?")
# hr.hypothetical_document = "Research indicates that What is the optimal spread..."
```

---

### `retrieve_for_research(topic, provider_name="manual", use_hyde=False, include_step_back=False, max_queries=5, query_index_kwargs=None, **provider_kwargs) -> RetrievalPlan`

Runs multi-angle retrieval for a research topic by calling `query_index()` for
each planned query and merging results.

**RetrievalPlan fields:**
- `topic: str` — original topic
- `query_plan: QueryPlan` — from plan_queries()
- `hyde_result: Optional[HydeResult]` — None if `use_hyde=False`
- `results: list[dict]` — deduplicated, score-sorted retrieval results
- `result_sources: dict[str, set[str]]` — chunk_id -> set of query labels

**Deduplication:** Results from multiple sub-queries are merged by `chunk_id`.
When a chunk appears in multiple results, the highest score is kept.

**Fallback behavior:** If `query_index()` raises (e.g., no Chroma DB), returns
empty `results` with `query_plan` still populated. Never raises.

```python
from packages.research.synthesis import retrieve_for_research

# Offline (no Chroma needed for plan structure)
plan = retrieve_for_research("crypto pair bot profitability")

# With HyDE expansion for better recall
plan = retrieve_for_research("market making spreads", use_hyde=True)

# With step-back query
plan = retrieve_for_research("prediction market edge", include_step_back=True)

# Custom query_index parameters
plan = retrieve_for_research(
    "arbitrage opportunities",
    query_index_kwargs={"hybrid": True, "k": 12, "private_only": False},
)
```

---

## Fallback Behavior Summary

| Scenario | Behavior |
|----------|----------|
| `provider_name="manual"` | Always deterministic. `was_fallback=False`. |
| LLM returns unparseable JSON | Falls back to deterministic. `was_fallback=True`. |
| LLM returns JSON missing `"queries"` | Falls back to deterministic. `was_fallback=True`. |
| LLM raises exception | Falls back to deterministic. `was_fallback=True`. |
| `query_index()` raises | Returns `results=[]`, `query_plan` still populated. |
| Empty topic string | Returns minimal valid output (no crash). |

---

## Deferred Items

The following are explicitly deferred to future plans:

- **Semantic query similarity dedup**: Deduplicate sub-queries by cosine similarity
  before issuing retrieval calls (reduces redundant Chroma queries).
- **Multi-hop reasoning**: Chain retrieved snippets as context for follow-up queries.
- **Parallel sub-query execution**: Run `query_index()` calls concurrently with
  `ThreadPoolExecutor` for faster retrieval on large query plans.
- **Cloud provider HyDE**: LLM-quality hypothetical documents via OpenAI/Anthropic
  (RIS v2 deliverable).

---

## Files

| File | Role |
|------|------|
| `packages/research/synthesis/query_planner.py` | QueryPlan, plan_queries() |
| `packages/research/synthesis/hyde.py` | HydeResult, expand_hyde() |
| `packages/research/synthesis/retrieval.py` | RetrievalPlan, retrieve_for_research() |
| `packages/research/synthesis/__init__.py` | Updated exports |
| `tests/test_ris_query_planner.py` | 27 offline tests |
