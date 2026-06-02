---
title: Academic One Paper Retrieval Quality
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# One-Paper RIS Retrieval Quality Validation

**Date:** 2026-05-23
**Track:** RIS L2 — Retrieval quality audit
**Paper:** arxiv:2510.05533 — "The New Quant: A Survey of Large Language Models in Financial Prediction and Trading" (Weilong Fu)
**Type:** Observational / no code changes

---

## Objective

Validate that the paper indexed during WP-1 (34 chunks, 167 claims, body_source=marker) is
queryable in practice. Identify retrieval strengths and weaknesses before declaring
RIS demo-ready for a one-paper subset.

---

## KnowledgeStore State at Session Start

Confirmed via direct SQLite inspection:

| Field              | Value                                        |
|--------------------|----------------------------------------------|
| KS path            | `kb/rag/knowledge/knowledge.sqlite3`         |
| source_documents   | 131 rows total                               |
| derived_claims     | 1,598 rows total                             |
| Paper doc_id       | `987d4883...` (64-char SHA256)               |
| source_family      | `academic`                                   |
| chunk_count        | 34                                           |
| Claims for paper   | 167                                          |
| body_source        | `marker`                                     |
| body_length        | 93,720 chars                                 |
| source_url         | `https://arxiv.org/abs/2510.05533`           |

**ChromaDB note:** The index at `kb/rag/index/chroma.sqlite3` has 24,502 embeddings,
but `research-query` does **not** use ChromaDB in the current L2 implementation.
`query_academic_corpus()` routes through `query_knowledge_store_for_rrf()` only
(SQLite substring match). This was confirmed by reading `packages/research/synthesis/academic_query.py`.

---

## Retrieval Mechanism

`research-query` → `query_academic_corpus()` → `query_knowledge_store_for_rrf()`:

```python
if query_lower in c.get("claim_text", "").lower():  # verbatim case-insensitive substring
```

Multi-angle expansion via `_build_sub_queries()` generates 3–4 variants
(primary, normalized via `_normalize_question()`, plan_queries output).
All variants use the same substring match — different angles increase chance
one angle hits but do not enable semantic matching.

---

## Commands Run

All commands executed from repo root `D:\Coding Projects\Polymarket\PolyTool`:

```bash
# Verify paper is indexed
python -m polytool research-stats summary

# Systematic query probes
python -m polytool research-query --question "language model"
python -m polytool research-query --question "sentiment"
python -m polytool research-query --question "hallucination"
python -m polytool research-query --question "temporal leakage"
python -m polytool research-query --question "portfolio construction"
python -m polytool research-query --question "time series"
python -m polytool research-query --question "fine-tuning"
python -m polytool research-query --question "risk management"
python -m polytool research-query --question "retrieval augmented"
python -m polytool research-query --question "benchmark evaluation"
python -m polytool research-query --question "language model financial prediction"
python -m polytool research-query --question "weather forecast"

# Direct SQLite inspection
sqlite3 kb/rag/knowledge/knowledge.sqlite3 "SELECT COUNT(*) FROM derived_claims ..."
```

---

## Full Probe Table

| # | Query                              | had_fallback | Claims | Notes                                        |
|---|------------------------------------|:------------:|:------:|----------------------------------------------|
| 1 | `language model`                   | False        | 20     | Best hit; broad 2-gram in many claims        |
| 2 | `sentiment`                        | False        | 8      | Good coverage; "sentiment analysis" in paper |
| 3 | `temporal leakage`                 | False        | 3      | Specific term used verbatim in paper         |
| 4 | `portfolio construction`           | False        | 3      | Verbatim bigram appears in claims            |
| 5 | `time series`                      | False        | 3      | Common 2-gram; hits relevant claims          |
| 6 | `fine-tuning`                      | False        | 2      | Hyphenated form matches                      |
| 7 | `hallucination`                    | False        | 2      | Domain-critical term; 2 claims only          |
| 8 | `risk management`                  | False        | 1      | Exists but sparse coverage                   |
| 9 | `retrieval augmented`              | False        | 1      | Verbatim substring; RAG mention in paper     |
|10 | `benchmark evaluation`             | **True**     | 0      | Fails — "benchmark" not adjacent to "evaluation" as substring |
|11 | `language model financial prediction` | **True** | 0      | 4-word phrase not contiguous in any claim    |
|12 | `weather forecast`                 | **True**     | 0      | Control: unrelated topic; correct rejection  |

**Known additional failures from mechanical testing (not shown in table):**
- `LLM` → had_fallback=True (abbreviation blindness — claims say "Large Language Models")
- Conversational queries ("what does this paper say about...") → had_fallback=True
- `quantitative finance neural network` → had_fallback=True (multi-word conjunction)
- `hallucination overfitting limitation` → had_fallback=True (multi-word conjunction)

**Hit rate on substantive (non-control) queries:** 9/11 = 82% when queries are
single-token or narrow 2-grams. Drops sharply for 3+ word phrases or abbreviations.

---

## paper_score Behavior

Every returning query returns `paper_score=0.7` regardless of how many claims matched
or how central the topic is to the paper.

```
Q="language model"  → paper_score=0.7, 20 claims
Q="temporal leakage" → paper_score=0.7, 3 claims
Q="retrieval augmented" → paper_score=0.7, 1 claim
```

The score is `max(effective_score)` across matching claims, and `effective_score`
appears to be a fixed default from the claim ingestion pipeline rather than a
query-relevance score. There is no semantic ranking — all hits are treated equally.

---

## Snippet Quality

Claim snippets (first 400 chars of `claim_text`) contain Marker OCR artifacts:

```
"<sup>∗</sup> Work was done while the author was working at JP Morgan Chase.\n\n
#### **Abstract**\n\nWe provide a comprehensive survey..."
```

```
"(#page-18-0) (Li et al., 2024b; Wang et al., 2023) can be used to significantly 
improve the generation quality of LLMs (Gao et al., 2023) from 22.5% to 47.1% on 
Open-Book QA (Mihaylov et al., 2018)."
```

Issues present in returned snippets:
- HTML tags: `<sup>`, `<br>`, `####`
- Internal citation refs: `(#page-18-0)` (Marker cross-reference format)
- Footnote text intermixed with abstract
- Raw markdown formatting from Marker's chunking

These artifacts would surface directly to an operator or downstream LLM consumer.

---

## Operator Mini-Report: What Did RIS Learn from This Paper?

**Paper:** "The New Quant: A Survey of Large Language Models in Financial Prediction and Trading" (Weilong Fu, 2024)

This survey covers 5+ years of LLM applications in quantitative finance, including:

1. **Sentiment analysis** — LLMs outperform traditional NLP methods (BERT-era) for
   financial text. RIS can answer: `research-query --question "sentiment"` (8 claims).

2. **Temporal leakage** — Papers using training data that overlaps test periods
   systematically overstate performance. RIS can answer: `research-query --question "temporal leakage"` (3 claims).

3. **Portfolio construction** — Survey covers LLM applications in portfolio
   optimization. RIS can answer: `research-query --question "portfolio construction"` (3 claims).

4. **Time series forecasting** — LLMs applied to price prediction; mixed results
   vs specialized models. RIS can answer: `research-query --question "time series"` (3 claims).

5. **Hallucination risk** — Survey flags hallucination as a primary concern for
   live trading applications. Only 2 claims indexed (sparse). RIS can answer:
   `research-query --question "hallucination"` (2 claims).

6. **Fine-tuning vs prompting** — Survey compares instruction-tuning and
   prompt-engineering approaches. RIS can answer: `research-query --question "fine-tuning"` (2 claims).

**What RIS cannot answer from this paper:**
- Anything requiring LLM abbreviations: "LLM strategies" → no match
- Multi-factor questions: "what are the main limitations" → no match
- Specific model comparisons: "GPT-4 vs smaller models" → match only if those
  exact strings appear contiguously in claims

**Relevance to PolyTool:** The paper's hallucination-risk and temporal-leakage
findings directly apply to RIS itself — using LLM-generated claim extractions
without grounding is the failure mode the survey warns about. The survey's
portfolio-construction and risk-management claims are also relevant to Gate 2
strategy validation framing.

---

## Retrieval Weaknesses Identified

### W1 — Abbreviation Blindness (High Impact)
`LLM` fails when claims say "Large Language Models". This breaks the most natural
query pattern for this paper. Affects all abbreviations: `RAG`, `NLP`, `LLM`, `GPT`.

### W2 — Multi-Word Conjunction Failure (High Impact)
Three or more words must appear as a contiguous substring. "benchmark evaluation"
fails because "benchmark" and "evaluation" don't appear adjacent in any claim.
Operators naturally write multi-word queries.

### W3 — HTML Artifacts in Snippets (Medium Impact)
`<sup>`, `####`, `(#page-18-0)` appear in returned snippets. These are Marker
OCR artifacts that should be stripped at claim-write time or in the snippet
formatter. They degrade usability for operator review and LLM consumers.

### W4 — Fixed paper_score (Medium Impact)
`paper_score=0.7` for all queries that return any claims. No semantic ranking
means an operator can't distinguish a highly relevant query (20 claims on core topic)
from a barely-relevant one (1 claim on a peripheral mention).

### W5 — No Semantic Fallback (Low Impact for single-paper demo, High for at scale)
ChromaDB has 24,502 embeddings but is not wired to `research-query`. The current
L2 comment explicitly defers: *"Does NOT query ChromaDB vector index in this version
(body_source not stored in Chroma metadata; future L2.1 can add that path)."*
With one paper, substring search is workable. With 29+ papers, semantic retrieval
becomes essential for cross-paper synthesis.

### W6 — No Page-Level Citations
Returned citations include `arxiv_id` and `title` but not page/section numbers.
Operators cannot verify claims against the source PDF.

---

## Demo-Ready Verdict

**NOT DEMO-READY** for public or operator-facing use.

| Criterion                          | Status | Note                                  |
|------------------------------------|--------|---------------------------------------|
| Paper indexed with body_source=marker | PASS | 34 chunks, 167 claims, 93,720 chars  |
| Basic topic retrieval works        | PASS   | 9/11 substantive single/2-gram queries succeed |
| Abbreviation queries work          | FAIL   | "LLM" → had_fallback=True             |
| Multi-word queries work            | FAIL   | 3+ word phrases regularly fail        |
| Snippet quality acceptable         | FAIL   | HTML artifacts in returned snippets   |
| Semantic ranking present           | FAIL   | paper_score fixed at 0.7             |
| Unrelated queries correctly rejected | PASS | "weather forecast" → had_fallback=True |

**Acceptable for internal dev validation** (confirming pipeline end-to-end).
**Not acceptable for operator demo or downstream LLM consumption** without W1–W4 fixes.

---

## Recommended Next Fixes (Priority Order)

1. **[L2.1] Wire ChromaDB semantic search** — `academic_query.py` already has
   the path commented as deferred. Add vector search fallback when substring fails.
   This fixes W1, W2, W5 in one change. Prerequisite: confirm ChromaDB doc_id
   linkage to KS doc_id (currently mismatched: 49-char Chroma vs 64-char KS).

2. **[Claim ingestion] Strip Marker HTML artifacts** — Post-process claim text
   at `index-done` write time: strip `<sup>`, `<br>`, `####`, `(#page-N-M)` refs.
   Fixes W3 without touching retrieval.

3. **[Retrieval] Abbreviation expansion** — Add lightweight synonym/abbreviation
   map at `_build_sub_queries()` time: LLM→"large language model", RAG→"retrieval
   augmented generation". Fixes W1 without semantic search.

4. **[Score] Query-relevance scoring** — Replace fixed `effective_score` with
   claim count or BM25-style score to produce meaningful paper ranking. Fixes W4.

---

## Files Changed

None — this is an observational run only.

```
docs/dev_logs/2026-05-23_academic-one-paper-retrieval-quality.md  ← this file
```

All probes executed against the existing indexed KnowledgeStore. No queue items
modified. No parser calls. No new papers ingested.

---

## Codex Review

Not required — docs-only session, no code changed.
