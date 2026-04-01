# RIS_05 — Synthesis Engine (Pipeline C)
**System:** PolyTool Research Intelligence System  
**Covers:** Query planner, HyDE expansion, report generation, pre-development check

---

## Purpose

The synthesis engine is the consumer-facing layer of the RIS. It takes a natural language
topic, retrieves relevant knowledge across all partitions, and generates a cited research
brief. This is what makes the research system useful in daily development work.

The most important command: `polytool research precheck --idea "..."` — the "pair
accumulation prevention" tool that checks existing knowledge before development begins.

---

## Architecture

```
Topic / Question
      │
      ▼
┌─────────────────────┐
│  Query Planner       │  Gemini Flash: topic → 3-5 retrieval queries
│  (+ step-back query) │  v2: iterative, orchestrator-driven
└─────────┬───────────┘
          │ queries
          ▼
┌─────────────────────┐
│  HyDE Expander       │  Each query → hypothetical document → embedding
│                      │  Searches in "document space" not "query space"
└─────────┬───────────┘
          │ expanded queries
          ▼
┌─────────────────────┐
│  RAG Retrieval       │  Chroma query (dense + sparse via BGE-M3)
│  + Cross-encoder     │  Cross-partition: external_knowledge + user_data
│    Reranking         │  Deduplication + reranking → top-k results
└─────────┬───────────┘
          │ retrieved documents with metadata
          ▼
┌─────────────────────┐
│  Report Synthesizer  │  DeepSeek V3: synthesize cited research brief
│  (DeepSeek V3)       │  Confidence assessment + actionability rating
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Output              │  Markdown file → artifacts/research/reports/
│                      │  Precheck: GO / CAUTION / STOP recommendation
└─────────────────────┘
```

---

## Query Planner

### v1: Single-pass decomposition

The query planner takes a topic and generates 3-5 diverse retrieval queries using Gemini
Flash. It's a one-shot LLM call that decomposes broad topics into specific searches.

```python
# packages/research/synthesis/query_planner.py

def plan_queries(topic: str, llm, max_queries: int = 5) -> list[str]:
    """Generate diverse retrieval queries for a research topic.
    
    Args:
        topic: Natural language topic or question
        llm: LLM client (Gemini Flash)
        max_queries: Maximum number of queries to generate
    
    Returns:
        List of specific retrieval queries
    """
    prompt = f"""You are a research librarian for a prediction market trading system.

Given a research topic, generate {max_queries} diverse search queries that would find
relevant documents in our knowledge base. The knowledge base contains:
- Academic papers on market microstructure and prediction markets
- Wallet analysis reports from profitable Polymarket traders
- Reddit/Twitter discussions about trading strategies
- Open-source bot documentation and analysis
- Quantitative finance reference material

Each query should approach the topic from a different angle. Use technical terminology
where appropriate. One query per line, no numbering.

Topic: {topic}

Queries:"""
    
    response = llm.generate(prompt, temperature=0.3)
    queries = [line.strip() for line in response.strip().splitlines() if line.strip()]
    return queries[:max_queries]
```

**Example:**

Input: `"Is crypto pair accumulation viable on Polymarket?"`

Generated queries:
1. `"pair cost below $1.00 polymarket binary crypto"`
2. `"gabagool strategy wallet analysis directional hedge"`
3. `"5-minute crypto market maker-taker spread binary"`
4. `"complement arbitrage binary prediction market"`
5. `"asymmetric accumulation YES NO position cost"`

### v2: Iterative query planner (future)

The v1 planner generates queries once and retrieves. The v2 planner is iterative:

```
Query Planner generates initial queries
    → RAG retrieves documents
    → Orchestrator evaluates: "Do we have enough information to answer?"
        → If YES: proceed to synthesis
        → If NO: "What's missing? Generate follow-up queries."
            → RAG retrieves again with new queries
            → Orchestrator re-evaluates
            → Repeat until satisfied or max iterations reached
```

This addresses your concern about 3-5 queries not being enough. The orchestrator (an LLM
call) reads the retrieved documents and identifies gaps: "I found information about pair
costs but nothing about fill rates on maker orders in 5-minute markets. Generate a query
for that."

**Implementation approach (v2):**
```python
def iterative_query_plan(topic: str, collection, llm, max_rounds: int = 3):
    """Iterative query planning with gap detection."""
    all_docs = []
    used_queries = []
    
    for round_num in range(max_rounds):
        if round_num == 0:
            queries = plan_queries(topic, llm)
        else:
            # Ask the LLM what's missing
            context = format_retrieved_docs(all_docs)
            gap_prompt = f"""Given the topic "{topic}" and these retrieved documents:

{context}

What important aspects of this topic are NOT covered by these documents?
Generate 2-3 specific queries to fill the gaps. If the coverage is
sufficient, respond with "SUFFICIENT".

Queries:"""
            gap_response = llm.generate(gap_prompt)
            if "SUFFICIENT" in gap_response.upper():
                break
            queries = [l.strip() for l in gap_response.splitlines() if l.strip()]
        
        # Retrieve for each query
        for q in queries:
            if q not in used_queries:
                results = enhanced_retrieve(q, collection, llm)
                all_docs.extend(results)
                used_queries.append(q)
        
        all_docs = deduplicate_docs(all_docs)
    
    return all_docs
```

---

## Report Synthesizer

### Report Types

**1. Research Brief** — general topic exploration

```bash
polytool research report --topic "market making on low-volume Polymarket markets"
```

Output: 1-2 page cited markdown with findings, contradictions, gaps, and actionability.

**2. Pre-Development Check (Precheck)** — the pair-accumulation prevention tool

```bash
polytool research precheck --idea "Build a momentum-based crypto pair signal"
```

Output: GO / CAUTION / STOP recommendation with supporting evidence.

**3. Weekly Digest** — automated summary of new knowledge

Generated automatically every Sunday at 08:00 via cron. Summarizes: what was ingested
this week, notable new findings, changes to the knowledge base.

### Report Format

```markdown
# Research Brief: [Topic]
**Generated:** 2026-03-30 14:22 UTC  
**Sources queried:** 47 documents across 2 partitions  
**Sources cited:** 12  
**Overall confidence:** HIGH | MEDIUM | LOW

---

## Summary

2-3 paragraph synthesis of what the knowledge base knows about this topic. Written
in the operator's voice, not academic language. Prioritizes actionable insights.

## Key Findings

1. **[Finding title]** — [1-2 sentence description]
   - Source: [doc_id] ([source_type], [confidence_tier])
   - Confidence: PEER_REVIEWED | PRACTITIONER | COMMUNITY
   
2. **[Finding title]** — [1-2 sentence description]
   - Source: [doc_id] ([source_type], [confidence_tier])

## Contradictions & Unresolved Questions

- [What the evidence disagrees on, with citations to both sides]
- [Important questions the knowledge base cannot answer yet]

## Actionability Assessment

- **Can this inform a current strategy track?** YES / NO
  - If YES: [which track and how]
- **Suggested next step:** [specific action the operator should take]
- **Estimated development impact:** [what changes if we act on this]

## Knowledge Gaps

- [Topics where we need more information]
- [Suggested ingestion queries to fill gaps]

## Sources Cited

| # | Doc ID | Title | Type | Confidence | Date |
|---|--------|-------|------|-----------|------|
| 1 | ext_2026... | ... | arxiv | PEER_REVIEWED | 2026-01 |
| 2 | ext_2026... | ... | reddit | COMMUNITY | 2026-03 |
```

### Precheck Format

```markdown
# Pre-Development Check: [Idea]
**Generated:** 2026-03-30 14:22 UTC

## Recommendation: 🟢 GO / 🟡 CAUTION / 🔴 STOP

## Evidence

### Supporting evidence (why this might work)
- [Evidence from knowledge base with citations]

### Contradicting evidence (why this might fail)
- [Evidence from knowledge base with citations]

### Past failures (has something similar been tried?)
- [Search the research partition for failed strategies with similar approaches]

## Risk Assessment
- [What could go wrong]
- [What we don't know]

## If proceeding, recommended approach
- [How to validate this idea cheaply before full development]
```

### Synthesis Implementation

```python
# packages/research/synthesis/synthesizer.py

class ReportSynthesizer:
    """Generate research briefs from RAG-retrieved documents."""
    
    def __init__(self):
        self.llm = DeepSeekV3Client()  # best free reasoning model
    
    def generate_report(self, topic: str, documents: list[dict]) -> str:
        """Synthesize a research brief from retrieved documents."""
        context = self._format_documents(documents)
        
        prompt = f"""You are a research analyst for PolyTool, a prediction market
trading system. Generate a research brief on the topic below.

RULES:
- Cite sources by doc_id. Every factual claim must have a citation.
- Distinguish between PEER_REVIEWED findings (high confidence) and
  COMMUNITY sources (lower confidence) in your synthesis.
- Explicitly note contradictions between sources.
- End with actionable recommendations, not just summaries.
- If the evidence is insufficient, say so clearly.

TOPIC: {topic}

RETRIEVED DOCUMENTS:
{context}

Generate the research brief in the format specified."""
        
        report = self.llm.generate(prompt, temperature=0.3, max_tokens=4000)
        return report
    
    def generate_precheck(self, idea: str, documents: list[dict],
                          failed_strategies: list[dict]) -> str:
        """Generate a GO/CAUTION/STOP pre-development check."""
        context = self._format_documents(documents)
        failures = self._format_failures(failed_strategies)
        
        prompt = f"""You are a senior technical advisor for a prediction market
trading system. A developer wants to build the following:

IDEA: {idea}

RELEVANT KNOWLEDGE:
{context}

PAST FAILED STRATEGIES (from research partition):
{failures}

Based on the evidence, provide a GO / CAUTION / STOP recommendation.
- GO: Evidence supports this idea, proceed with development.
- CAUTION: Mixed evidence, proceed but with specific validation gates.
- STOP: Evidence strongly suggests this will fail. Explain why.

Be direct. If this is a bad idea, say so clearly with citations."""
        
        return self.llm.generate(prompt, temperature=0.2, max_tokens=3000)
```

---

## Report Storage

Reports are saved as markdown files. They are NOT stored in the RAG (they're derived
content — storing them would create circular retrieval).

```
artifacts/research/reports/
├── 2026-03-30_crypto-pair-accumulation-viability.md
├── 2026-03-30_market-making-low-volume.md
├── weekly-digests/
│   ├── 2026-W13_digest.md
│   └── 2026-W14_digest.md
└── prechecks/
    ├── 2026-03-30_momentum-crypto-pair-signal.md
    └── 2026-04-01_sports-model-logistic-regression.md
```

Reports are indexed in ClickHouse for searching past reports by topic and date:

```sql
CREATE TABLE research_reports (
    report_id     String,
    report_type   Enum('brief', 'precheck', 'digest'),
    topic         String,
    generated_at  DateTime,
    confidence    Enum('HIGH', 'MEDIUM', 'LOW'),
    recommendation Nullable(Enum('GO', 'CAUTION', 'STOP')),
    file_path     String,
    sources_cited Int32,
    summary       String
) ENGINE = MergeTree()
ORDER BY generated_at;
```

---

## CLI Commands

```bash
# Generate a research brief
polytool research report --topic "market making on polymarket"
polytool research report --topic "crypto pair strategies" --output /path/to/report.md

# Pre-development check (the most important command)
polytool research precheck --idea "Build a momentum-based crypto pair signal"
polytool research precheck --idea "Use Avellaneda-Stoikov on 5-minute crypto markets"

# Query the knowledge base directly (without report generation)
polytool research query "What is the maker-taker gap in sports markets?"
polytool research query "gabagool strategy analysis" --partition external_knowledge

# List past reports
polytool research list-reports --type precheck --days 30

# Search past reports
polytool research search-reports "crypto pair"
```

---

## Testing DeepSeek V3 and Model Alternatives

As discussed, DeepSeek V3 is the default synthesis model but should be tested against
alternatives before committing. The evaluation approach:

1. Generate the same report using 3 different models
2. Human evaluates: citation accuracy, insight quality, actionability
3. Best model becomes the default

**Models to test:**
- DeepSeek V3 (free API, strong reasoning)
- Gemini 2.5 Flash (free, fast but potentially less depth)
- Ollama Qwen3-30B (local, no API dependency)

**Multi-model synthesis (v2 idea):** Use a "big model governed by smaller models" pattern:
- DeepSeek V3 generates the report
- Gemini Flash fact-checks each citation against the source documents
- If Gemini finds a citation that doesn't match its source, flag it
- Final report includes only verified citations

This is the "smaller models can't lie" pattern — the checker model only needs to verify
factual alignment, not generate new content. Cheaper and more reliable than having the
generator self-check.

---

## v1 vs v2 Features

| Feature | v1 | v2 |
|---------|----|----|
| Query planning | Single-pass, 3-5 queries | Iterative with gap detection |
| HyDE | Applied to all queries | Adaptive: HyDE for vague queries, direct for specific |
| Synthesis model | DeepSeek V3 only | Multi-model synthesis with citation verification |
| Precheck | Search external_knowledge + user_data | Also search research partition for past failures |
| Weekly digest | Generated, saved to file | Also sent via Discord webhook |
| Report format | Markdown file | Markdown + optional HTML for interactive elements |
| Self-updating | Manual topic selection | Auto-identify knowledge gaps from project state |

---

*End of RIS_05 — Synthesis Engine*
