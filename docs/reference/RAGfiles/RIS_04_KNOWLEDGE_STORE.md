# RIS_04 — Knowledge Store
**System:** PolyTool Research Intelligence System  
**Covers:** Chroma architecture, BGE-M3 embedding, metadata schema, Phase R0 seed, query enhancement

---

## Purpose

The knowledge store is the persistent, queryable repository of evaluated research material.
It uses the existing `polytool_brain` Chroma collection, adding the `external_knowledge`
partition alongside the existing `user_data` partition. The embedding model choice and
query enhancement techniques determine whether the system can find relevant information
even when the query phrasing differs from the stored content.

---

## Chroma Architecture

### Single Collection, Multiple Partitions

```
polytool_brain (Chroma collection)
├── user_data           ← EXISTS NOW (dossiers, scan artifacts, LLM reports)
├── external_knowledge  ← ADDED BY RIS (papers, social posts, books, findings)
├── research            ← FUTURE (validated strategy specs, post-mortems)
└── signals             ← FUTURE (proven news patterns with measured reactions)
```

**Why single collection:** One backup path, one migration path, one query interface.
Partitions are metadata tags on documents, not separate collections. Cross-partition
queries work natively — when the synthesis engine asks "what do we know about market
making spreads?", it searches both `user_data` (wallet dossiers showing actual MM
behavior) and `external_knowledge` (academic research on optimal spreads).

**Partition enforcement:** The `partition` field is a required metadata key on every
document. The knowledge writer refuses to write a document without it. Queries can
scope to a specific partition via metadata filter or search across all partitions.

---

## Embedding Model

### Primary: BGE-M3 (BAAI)

| Property | Value |
|----------|-------|
| Model | `BAAI/bge-m3` |
| MTEB Score | 63.0 |
| Dimensions | 1024 (configurable) |
| Max Tokens | 8,192 |
| Retrieval Types | Dense + Sparse + Multi-vector (all from single model) |
| License | MIT |
| Languages | 100+ |

**Why BGE-M3:**
- **Hybrid retrieval** — handles both semantic search (dense) and keyword matching (sparse)
  in one model. Academic papers use precise terminology (sparse helps), while social posts
  use casual language (dense helps). One model covers both.
- **MIT license** — no restrictions on commercial use.
- **Runs on modest hardware** — fits on the RTX 2070 Super (8 GB VRAM) alongside other
  processes. CPU inference is available but slower.
- **Strong benchmarks** — competitive with models 2x its size on retrieval tasks.

**Installation:**
```bash
pip install FlagEmbedding --break-system-packages
```

**Setup in Chroma:**
```python
from FlagEmbedding import BGEM3FlagModel

class BGEM3EmbeddingFunction:
    """BGE-M3 embedding function compatible with Chroma."""
    
    def __init__(self, model_name: str = "BAAI/bge-m3", use_fp16: bool = True):
        self.model = BGEM3FlagModel(model_name, use_fp16=use_fp16)
    
    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed a list of texts. Returns dense embeddings."""
        embeddings = self.model.encode(
            input,
            batch_size=12,
            max_length=8192,
        )
        return embeddings["dense_vecs"].tolist()

# Usage with Chroma
import chromadb

client = chromadb.PersistentClient(path="/data/chroma/polytool_brain")
embedding_fn = BGEM3EmbeddingFunction()

collection = client.get_or_create_collection(
    name="polytool_brain",
    embedding_function=embedding_fn,
    metadata={"hnsw:space": "cosine"},
)
```

### Development Fallback: e5-base-instruct

For development and testing on machines without GPU, use `intfloat/e5-base-instruct`:
- 110M parameters (runs fast on CPU)
- 768 dimensions
- Strong retrieval accuracy for its size
- No GPU required

**Important:** The embedding model must be consistent across the entire corpus. If you
index with BGE-M3, you must query with BGE-M3. Switching models requires re-embedding
the entire corpus. Design the system so the model is a config parameter, not hardcoded.

---

## Document Metadata Schema

Every document in `external_knowledge` carries these fields:

```python
METADATA_SCHEMA = {
    # Identity
    "doc_id": str,                  # e.g., "ext_2026-03-30_arxiv_2510.15205"
    "partition": "external_knowledge",
    
    # Source
    "source_type": str,             # arxiv | ssrn | reddit | twitter | youtube
                                    # | blog | github | book | manual | wallet_analysis
    "source_url": str,              # permalink or local path
    "title": str,
    "author": str,
    
    # Timestamps
    "source_publish_date": str,     # when the original was published (ISO 8601)
    "ingest_timestamp": str,        # when we ingested it (ISO 8601)
    
    # Trust tiers (from roadmap v5.1)
    "freshness_tier": str,          # CURRENT | RECENT | HISTORICAL
                                    # Computed from source_publish_date:
                                    #   CURRENT = 2024+
                                    #   RECENT = 2021-2023
                                    #   HISTORICAL = pre-2021
                                    # Recomputed weekly by refresh job
    
    "confidence_tier": str,         # PEER_REVIEWED | PRACTITIONER | COMMUNITY
                                    # Set based on source_type:
                                    #   arxiv/ssrn/academic books → PEER_REVIEWED
                                    #   github (>100 stars)/curated blogs → PRACTITIONER
                                    #   reddit/twitter/youtube → COMMUNITY
    
    "validation_status": str,       # UNTESTED | CONSISTENT_WITH_RESULTS | CONTRADICTED
                                    # Starts as UNTESTED
                                    # Updated by Phase 6 feedback loop when strategies
                                    # that cited this doc are validated or fail
    
    # Evaluation scores
    "eval_score": int,              # total /20
    "eval_relevance": int,          # 1-5
    "eval_novelty": int,            # 1-5
    "eval_actionability": int,      # 1-5
    "eval_credibility": int,        # 1-5
    "eval_model": str,              # which LLM scored this
    "epistemic_type": str,          # EMPIRICAL | THEORETICAL | ANECDOTAL | SPECULATIVE
    
    # Content summaries
    "summary": str,                 # 2-3 sentence LLM summary
    "key_findings": str,            # JSON-encoded list of finding strings
    "related_strategy_tracks": str, # JSON-encoded list: market_maker, crypto_pairs, etc.
    
    # Lifecycle
    "last_referenced": str | None,  # last time this doc appeared in a report
    "reference_count": int,         # how many reports have cited this doc
    
    # Linking (for multi-chunk documents like books)
    "parent_doc_id": str | None,    # e.g., book_id for chapter chunks
    "chunk_index": int | None,      # position within parent document
}
```

**Freshness tier computation:**
```python
from datetime import datetime

def compute_freshness(publish_date: str) -> str:
    """Compute freshness tier from publication date."""
    if not publish_date:
        return "CURRENT"  # assume current if unknown
    year = datetime.fromisoformat(publish_date).year
    if year >= 2024:
        return "CURRENT"
    elif year >= 2021:
        return "RECENT"
    else:
        return "HISTORICAL"
```

**Note on timestamps vs tiers:** Both are stored. The `source_publish_date` field enables
precise date-range queries (`--after 2025-06-01`). The `freshness_tier` field enables
quick categorical filtering (`--freshness CURRENT`). The tier is a convenience label
computed from the date, not a hardcoded value.

---

## Phase R0 — Foundation Seed

**Duration:** 1-2 days, no new code required.

Uses existing `llm-save` CLI or direct Chroma API to manually write foundational documents
into `external_knowledge`. This is immediately useful — every dev agent session can query
this knowledge starting day one.

### Documents to Seed

**Jon-Becker 4 Key Findings (confidence: PEER_REVIEWED):**

1. **Maker-taker edge:** Makers earn +1.12%/trade, takers lose -1.12%, consistent across
   80/99 price levels across 72.1M trades.

2. **Category allocation:** Finance 0.17pp maker edge (near-efficient — avoid). Sports
   2.23pp, Crypto 2.69pp, Entertainment 4.79pp. Prioritize Sports and Entertainment.

3. **Favorite-longshot bias:** At 1-cent markets, YES takers lose 41% in expectation,
   NO buyers earn +23%. YES takers account for 41-47% of 1-10¢ volume.

4. **Regime risk:** Maker edge only emerged post-October 2024. Before that, takers
   outperformed. Monitor for regime reversal.

**Academic Paper Summaries (confidence: PEER_REVIEWED):**

5. Avellaneda & Stoikov (2008): reservation price and optimal spread formulas for
   continuous-time market making under inventory risk.

6. Kelly (1956): optimal bet sizing to maximize log-wealth growth rate.

7. "Toward Black Scholes for Prediction Markets" (arXiv:2510.15205): option pricing
   framework adapted for binary outcome markets.

8. Becker (2026): full 72.1M trade microstructure analysis methodology and findings.

9. Palumbo (2025): SSRN microstructure perspective on prediction markets.

**gabagool22 Wallet Analysis (confidence: PRACTITIONER):**

10. Pair accumulation is NOT the strategy (avg pair cost $1.0274, pairs lose money).

11. Actual edge is directional trading with partial hedges.

12. "Favorite" tier entries (above $0.65) show positive CLV.

13. Hedge legs lose ~90% of the time — edge is entirely directional.

**Open-Source Repo Analysis (confidence: PRACTITIONER):**

14. lorine93s bot: auto_redeem pattern, cancel/replace cycle, "not profitable today" caveat.

15. dylanpersonguy bot: SMI formula, conviction score, 7-phase scanner pipeline, OFI windows.

16. warproxxx poly-maker: poly_merger module for NO→YES conversion.

17. realfishsam: fuzzy market matcher algorithm for cross-platform matching.

### Seed Procedure

```bash
# Option A: Use existing llm-save CLI (if it supports partition tagging)
polytool llm-save --partition external_knowledge --source-type manual \
    --title "Jon-Becker Finding: Maker-Taker Edge" \
    --confidence PEER_REVIEWED --freshness CURRENT

# Option B: Direct Chroma API script
python scripts/seed_foundations.py
```

### Verification

After seeding, run these test queries to verify cross-partition retrieval:

```bash
polytool research query "What is the maker-taker gap in sports markets?"
# Expected: returns Jon-Becker finding #2

polytool research query "Is pair accumulation profitable on Polymarket?"
# Expected: returns gabagool22 findings #10-13

polytool rag-query "market making spread optimization"
# Expected: returns Avellaneda-Stoikov summary + any relevant dossiers from user_data
```

---

## Query Enhancement

### Problem

The "right info, wrong question" problem: the RAG contains a document about "asymmetric
directional accumulation with hedge legs" but the user asks "how does the gabagool strategy
work?" The semantic distance between the query and the document may be too large for the
embedding model to bridge.

### Solution Stack (from Research Report 3)

Three complementary techniques, applied in sequence:

**1. HyDE (Hypothetical Document Embedding)**

Instead of embedding the raw query, generate a hypothetical answer document and embed THAT.
The hypothetical answer uses document-like language that's closer to the stored content
in embedding space.

```python
# packages/research/synthesis/hyde_expander.py

def generate_hypothetical_document(query: str, llm) -> str:
    """Generate a hypothetical answer for HyDE retrieval."""
    prompt = (
        "You are a prediction market research analyst. Write a concise paragraph "
        "that would answer this question. Use technical terminology and specific "
        "details. Do not invent facts beyond common domain knowledge.\n\n"
        f"Question: {query}\n\nAnswer:"
    )
    return llm.generate(prompt, temperature=0.2)

def hyde_retrieve(query: str, collection, llm, k: int = 5):
    """Retrieve using HyDE-expanded query."""
    hyp_doc = generate_hypothetical_document(query, llm)
    # Chroma re-embeds the hypothetical doc using the collection's embedding function
    results = collection.query(query_texts=[hyp_doc], n_results=k)
    return results
```

**When to use HyDE:** Short, vague queries. Questions where the user's phrasing differs
significantly from the stored content's style.

**2. Query Decomposition**

Break complex questions into subqueries, retrieve for each, merge results.

```python
def decompose_query(query: str, llm) -> list[str]:
    """Break a complex question into 3-5 subqueries."""
    prompt = (
        "Break this research question into 3-5 specific subqueries for "
        "searching a prediction market knowledge base. One per line.\n\n"
        f"Question: {query}"
    )
    response = llm.generate(prompt)
    return [line.strip("- ") for line in response.strip().splitlines() if line.strip()]
```

**When to use:** Multi-part questions, comparison queries, investigative debugging.

**3. Step-Back Prompting**

Ask the LLM to abstract the question into broader principles first, then use those
principles as additional retrieval queries.

```python
def step_back_query(query: str, llm) -> str:
    """Generate a broader 'step-back' question."""
    prompt = (
        "What broader principle or concept would help answer this specific question "
        "about prediction market trading?\n\n"
        f"Question: {query}\n\nBroader concept:"
    )
    return llm.generate(prompt)
```

**When to use:** Domain-specific questions where surfacing relevant principles improves
retrieval (e.g., "Why do our crypto pair fills fail?" → "How do maker order fill rates
depend on spread width and queue position in binary markets?").

### Combined Pipeline (v1)

```python
def enhanced_retrieve(query: str, collection, llm, k: int = 10) -> list:
    """Combined query enhancement for maximum retrieval quality."""
    all_results = {}
    
    # Direct query (always)
    direct = collection.query(query_texts=[query], n_results=k)
    _merge(all_results, direct)
    
    # HyDE expansion
    hyde_results = hyde_retrieve(query, collection, llm, k=k)
    _merge(all_results, hyde_results)
    
    # Query decomposition (if query is complex — >10 words)
    if len(query.split()) > 10:
        subqueries = decompose_query(query, llm)
        for sq in subqueries[:5]:
            sub_results = collection.query(query_texts=[sq], n_results=3)
            _merge(all_results, sub_results)
    
    # Deduplicate and re-rank with cross-encoder
    unique_docs = list(all_results.values())
    reranked = cross_encoder_rerank(query, unique_docs, top_k=k)
    
    return reranked
```

---

## Storage Estimates

| Content | Documents | Estimated Size |
|---------|-----------|---------------|
| Phase R0 seed | ~20 | <1 MB |
| ArXiv papers (first year) | 500-1000 | 50-100 MB |
| Social posts (first year) | 2000-5000 | 20-50 MB |
| Books (curated set) | 50-200 chapters | 50-100 MB |
| Embeddings (BGE-M3, 1024d) | ~5000 docs | ~20 MB |
| **Total (first year)** | **~5000-6000** | **<300 MB** |

At this scale, Chroma runs comfortably on the dev machine. TurboQuant-style vector
quantization becomes relevant only at 100K+ documents — a Phase 2+ optimization.

---

*End of RIS_04 — Knowledge Store*
