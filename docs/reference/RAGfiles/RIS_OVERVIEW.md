# PolyTool Research Intelligence System (RIS) — Overview
**Version:** 1.1 · **Date:** April 2026 · **Status:** Approved Draft  
**Parent:** PolyTool Master Roadmap v5.1  
**Companion Files:** `RIS_01` through `RIS_07` (detailed subsystem specs)

---

## Changelog

### v1.1 (2026-04-07) — Phase 2 Contract Freeze

Additions accepted by Director before implementation:

1. **Fail-closed evaluation rule** — documents that fail LLM scoring default to REJECT, never silent pass-through. (RIS_03)
2. **Weighted composite gate** — canonical gate uses dimension weights (relevance=0.30, novelty=0.25, actionability=0.25, credibility=0.20); simple sum retained as diagnostic only. Per-dimension floor of 2 on relevance and credibility. (RIS_03)
3. **Novelty dedup pre-step** — deduplicate by canonical doc_id / source_url before nearest-neighbor embedding injection into the evaluation prompt. (RIS_03)
4. **Review queue contract** — KnowledgeStore SQLite `pending_review` table + CLI `research-review` flow for YELLOW-zone documents. (RIS_03, RIS_04)
5. **Budget controls** — global daily cap, per-source daily cap, manual-reserve hold-back for operator-submitted URLs. (RIS_06)
6. **Per-priority acceptance gates** — explicit pass/fail thresholds per source priority tier. (RIS_03)
7. **Segmented retrieval benchmark** — benchmark metrics reported by query class (factual, analytical, exploratory). (RIS_05)
8. **n8n env-var-primary config** — environment variables are the primary config source; n8n Variables are optional convenience only. (RIS_06)
9. **ClickHouse idempotency** — `execution_id` column + ReplacingMergeTree at storage level; code-level prefilter before INSERT. (RIS_06)
10. **Research-only posture statement** — added to Overview. (RIS_OVERVIEW)

---

## Why This System Exists

The pair accumulation pivot cost weeks of development. gabagool22's on-chain behavior
(directional trading with hedges, average pair cost $1.0274) contradicted the blog-described
strategy (risk-free pair accumulation below $1.00). A research system that had already
analyzed that wallet's behavior would have flagged this before a single line of code was
written.

**Problem:** PolyTool development burns time on dead or unfeasible ideas. Research happens
ad-hoc during dev sessions. Knowledge from past sessions isn't retained in a queryable form.
External knowledge (papers, community strategies, market data) isn't indexed.

**Solution:** A research intelligence system that continuously ingests, evaluates, and
organizes knowledge — then makes it instantly queryable. Before building anything, the first
step becomes: *"What does the research system already know about this?"*

**What RIS is NOT:** It is not a trading bot. It does not execute trades or generate revenue
directly. It generates *knowledge* that prevents wasted development and informs better
strategy design.

---

## Posture Statement

RIS is a research-only system. It ingests, evaluates, and organizes knowledge.
It does NOT generate trading signals, place orders, or recommend positions.
Outputs from RIS (research reports, precheck verdicts, knowledge-base entries)
are informational inputs to human decision-making and strategy design processes.
No RIS output should be interpreted as a trading recommendation.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RESEARCH INTELLIGENCE SYSTEM                         │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  LAYER 1 — INGESTION                                              │  │
│  │                                                                    │  │
│  │  Pipeline A (Academic)          Pipeline B (Social)                │  │
│  │  ├─ ArXiv API                   ├─ Reddit (PRAW)                  │  │
│  │  ├─ SSRN RSS                    ├─ Twitter/X                      │  │
│  │  ├─ Books (free/CC ebooks)      ├─ YouTube transcripts            │  │
│  │  ├─ PDF extraction              ├─ Blog/RSS feeds                 │  │
│  │  │  (MinerU or Marker)          ├─ GitHub READMEs                 │  │
│  │  └─ Manual URL submission       └─ Partner news project (v2)      │  │
│  │                                                                    │  │
│  │  All sources → Content Normalizer → standard document format      │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                              │                                          │
│  ┌──────────────────────────▼────────────────────────────────────────┐  │
│  │  LAYER 2 — EVALUATION GATE                         [RIS_03]       │  │
│  │                                                                    │  │
│  │  Binary pre-gate: "Is this about prediction markets/trading?"     │  │
│  │       ↓ YES                                                        │  │
│  │  Gemini Flash (fast scorer) → 4 dimensions × 1-5 scale = /20     │  │
│  │       ↓ Score 8-12 (gray zone)                                    │  │
│  │  DeepSeek V3 (escalation scorer) → re-evaluate borderline docs   │  │
│  │       ↓                                                            │  │
│  │  Decision: GREEN (≥12) → ingest                                   │  │
│  │            YELLOW (8-12) → human review queue                     │  │
│  │            RED (<8) → reject + log to JSONL                       │  │
│  │                                                                    │  │
│  │  Calibration: HITL feedback loop on gold set of 100-300 docs      │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                              │                                          │
│  ┌──────────────────────────▼────────────────────────────────────────┐  │
│  │  LAYER 3 — KNOWLEDGE STORE                         [RIS_04]       │  │
│  │                                                                    │  │
│  │  polytool_brain (Chroma) — external_knowledge partition           │  │
│  │  Embedding model: BGE-M3 (dense + sparse hybrid, MIT license)    │  │
│  │  Query enhancement: HyDE + query decomposition + step-back        │  │
│  │                                                                    │  │
│  │  Metadata per document:                                            │  │
│  │  ├─ source_type, source_url, source_publish_date                  │  │
│  │  ├─ freshness_tier (computed), confidence_tier, validation_status │  │
│  │  ├─ eval_score (per-dimension breakdown)                          │  │
│  │  └─ summary, key_findings, related_strategy_tracks                │  │
│  │                                                                    │  │
│  │  Existing partitions (user_data, research, signals) untouched     │  │
│  └──────────────────────────┬────────────────────────────────────────┘  │
│                              │                                          │
│  ┌──────────────────────────▼────────────────────────────────────────┐  │
│  │  LAYER 4 — SYNTHESIS + ACTION                      [RIS_05]       │  │
│  │                                                                    │  │
│  │  Query Planner (Gemini Flash)                                      │  │
│  │  └─ Topic → 3-5 diverse retrieval queries                         │  │
│  │  └─ v2: iterative queries via orchestrator                        │  │
│  │                                                                    │  │
│  │  RAG Retrieval (existing Chroma + FTS5 + RRF + cross-encoder)    │  │
│  │  └─ HyDE expansion for each query                                 │  │
│  │  └─ Cross-partition search (external_knowledge + user_data)       │  │
│  │                                                                    │  │
│  │  Report Synthesizer (DeepSeek V3)                                 │  │
│  │  └─ Cited markdown brief with confidence + actionability          │  │
│  │  └─ Pre-development check: GO / CAUTION / STOP                   │  │
│  │                                                                    │  │
│  │  Consumers: Human devs · Claude Code / ChatGPT · Autoresearch    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  INFRASTRUCTURE                                    [RIS_06]       │  │
│  │  n8n orchestration · APScheduler (v1) · Grafana panels            │  │
│  │  CLI: python -m polytool research-{ingest,acquire,report,precheck,stats,health,scheduler,dossier-extract} (standalone hyphenated commands) │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  INTEGRATION                                       [RIS_07]       │  │
│  │  Dossier pipeline upgrade (v1 shipped) · SimTrader bridge (v1 shipped, auto-loop v2) │  │
│  │  Auto-discovery → findings → external_knowledge                  │  │
│  │  LLM fast-research complement (GLM / Gemini for on-demand)       │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Summary

```
Sources → Normalizer → Binary Gate → LLM Scorer → Threshold → Chroma
                                                       ↓
                                              Rejected → JSONL log
                                              Gray zone → Human review
                                              Accepted → external_knowledge

Query → Query Planner → HyDE Expansion → RAG Retrieval → DeepSeek V3 → Report
                                                                          ↓
                                                              artifacts/research/reports/

Feedback: Human ratings on reports → update eval prompt → better scoring over time
Future:   Research findings → hypothesis registry → SimTrader auto-test → research partition
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Single vs separate RAG databases | Single Chroma collection with partition tags | One backup path, one migration path, one query interface. Partition tags are metadata, not separate collections. |
| Scoring scale | 1-5 per dimension (4 dimensions, max 20) | Research confirms 0-25 granularity creates false precision. 1-5 is reliably distinguishable by LLMs. |
| Evaluation model strategy | Gemini Flash primary, DeepSeek V3 for borderline | 1,500 free Gemini requests/day covers bulk eval. DeepSeek reserved for hard cases. |
| PDF extraction tool | MinerU (primary) or Marker (alternative) | MinerU: best multi-column + math. Marker: best RAG-ready chunk output. Both handle academic papers well. |
| Embedding model | BGE-M3 (primary), e5-base-instruct (dev fallback) | BGE-M3: hybrid dense+sparse retrieval, MIT license, 100+ languages, runs on modest hardware. |
| Query enhancement | HyDE + query decomposition + step-back prompting | Addresses the "right info, wrong question" problem. Research validates this combination for technical KBs. |
| Report storage | Markdown files in artifacts/, NOT in RAG | Reports are derived content. Storing them in RAG creates circular retrieval. |
| Rejected document storage | JSONL flat file, NOT in RAG | Prevents rejected content from surfacing in queries via missed filter parameters. |
| Books | Included (free/CC-licensed only) | Valid use case: LLM agents querying full Avellaneda-Stoikov derivations when modifying spread formulas. |
| Orchestration | APScheduler (v1), n8n (v2) | Start fast with APScheduler, migrate to n8n when workflow shapes are stable. |

---

## Development Phases

### Phase R0 — Foundation Seed (1-2 days, no new code)
Manually seed Jon-Becker findings, academic paper summaries, gabagool22 analysis, and
open-source repo findings into existing Chroma as `external_knowledge`. Immediately useful
for every dev agent session.
**Details:** `RIS_04_KNOWLEDGE_STORE.md` §Phase R0

### Phase R1 — Academic Pipeline + Evaluation Gate (5-7 days)
Build ArXiv/SSRN ingestion, PDF extraction (MinerU/Marker), content normalizer, and the
full LLM evaluation gate. The evaluation gate is the core reusable component — all future
sources flow through it.
**Details:** `RIS_01_INGESTION_ACADEMIC.md`, `RIS_03_EVALUATION_GATE.md`

> **v1.1 note:** Phase R1 deliverables now include the weighted composite gate,
> fail-closed rule, novelty dedup pre-step, review queue contract, per-priority
> acceptance gates, and budget controls. See RIS_03 and RIS_06 for full specifications.

### Phase R2 — Social Pipeline (3-5 days)
Reddit (PRAW), Twitter/X, YouTube transcripts, blog RSS, GitHub READMEs. Reuses the
evaluation gate from R1. New work is source-specific scrapers and the content normalizer.
**Details:** `RIS_02_INGESTION_SOCIAL.md`

### Phase R3 — Synthesis Engine (3-5 days)
Query planner, HyDE expansion, report synthesizer, pre-development check command.
This is the payoff — `python -m polytool research-precheck run --idea "..." --no-ledger` prevents another
pair-accumulation-level wasted effort.
**Details:** `RIS_05_SYNTHESIS_ENGINE.md`

### Phase R4 — Infrastructure Hardening (2-3 days)
n8n migration, Grafana panels, health checks, scheduled weekly digest.
**Details:** `RIS_06_INFRASTRUCTURE.md`

### Phase R5 — Integration + v2 Features (ongoing)
Dossier pipeline upgrade, SimTrader bridge, iterative query planner, auto-discovery
feeding into external_knowledge, LLM fast-research complement.
**Details:** `RIS_07_INTEGRATION.md`

---

## Parallel Execution with Trading Tracks

RIS runs alongside Phase 1A/1B/1C, not instead of them:

```
Week 1:  R0 (seed foundations)        + Phase 1A crypto pair work continues
Week 2:  R1 (academic + eval gate)    + Phase 1A paper testing
Week 3:  R2 (social pipeline)         + Phase 1C sports model data ingestion
Week 4:  R3 (synthesis engine)        + Phase 1B tape recording
Week 5:  R4 (infrastructure)          + all trading tracks continue
Week 6+: RIS on maintenance (cron)    + full dev effort on trading tracks
```

After Phase R4, RIS runs autonomously. Operator time: ~30 min/week reviewing the
weekly digest and calibrating the evaluation prompt.

---

## LLM Fast-Research Complement

The built RIS system works 24/7 on slow, systematic ingestion and evaluation. But
for on-demand research during development sessions, LLMs like GLM-5 Turbo, Gemini,
or ChatGPT provide fast research that the built system cannot match.

These are complementary, not competing:
- **RIS (built system):** Continuous background ingestion. Accumulates a growing,
  queryable knowledge base. Slow but comprehensive. Gets better over time.
- **LLM fast-research:** On-demand, session-specific deep dives. Fast but ephemeral
  (results exist only in chat context unless manually saved).

The bridge: when an LLM fast-research session produces valuable findings, the operator
can save them to the RIS via `python -m polytool research-acquire --url "..." --source-family blog --no-eval` or manual submission via `python -m polytool research-ingest --text "..." --source-type manual --no-eval`.
Over time, the RIS absorbs the best findings from ad-hoc research sessions, building
institutional memory that outlasts any single chat conversation.

---

## Companion File Index

| File | Covers | Key Deliverables |
|------|--------|-----------------|
| `RIS_01_INGESTION_ACADEMIC.md` | Pipeline A: ArXiv, SSRN, books, PDF extraction | ArXiv ingestion module, PDF extractor, book ingestion, manual URL submission |
| `RIS_02_INGESTION_SOCIAL.md` | Pipeline B: Reddit, Twitter/X, YouTube, blogs, GitHub | Source scrapers, content normalizer, transcript cleaning |
| `RIS_03_EVALUATION_GATE.md` | LLM scoring system, multi-model panel, calibration | Evaluator module, rubric, calibration workflow, rejection review system |
| `RIS_04_KNOWLEDGE_STORE.md` | Chroma architecture, BGE-M3 embedding, metadata schema | Embedding setup, metadata schema, Phase R0 seed procedure, query enhancement |
| `RIS_05_SYNTHESIS_ENGINE.md` | Query planner, HyDE, report generation, precheck | Report synthesizer, precheck command, v2 iterative planner |
| `RIS_06_INFRASTRUCTURE.md` | n8n, scheduling, CLI commands, Grafana, monitoring | APScheduler setup, CLI registration, dashboard panels, health checks |
| `RIS_07_INTEGRATION.md` | Master roadmap connections, SimTrader bridge, dossier upgrade | Dossier → external_knowledge flow, auto-discovery loop, hypothesis generation |

---

## Dependencies (All Free)

```
# Ingestion
arxiv>=2.0              # ArXiv API client
praw>=7.0               # Reddit API
yt-dlp>=2024.0          # YouTube transcript extraction
feedparser>=6.0         # RSS feed parsing
beautifulsoup4>=4.12    # HTML content extraction

# PDF extraction (choose one)
magic-pdf               # MinerU — best multi-column + math
# OR
marker-pdf              # Marker — best RAG-ready chunks

# LLM evaluation (free tier APIs)
google-generativeai     # Gemini Flash (1500 free req/day)
openai                  # DeepSeek V3 via OpenAI-compatible endpoint

# Embedding
FlagEmbedding           # BGE-M3 (MIT license, hybrid retrieval)

# Storage (already in project)
chromadb                # Vector store (existing)
# sentence-transformers already used for embeddings

# Optional
snscrape                # Twitter/X scraping (no API key, less reliable)
```

---

## File Structure

```
packages/research/
├── __init__.py
├── cli.py                          # CLI command registration
├── ingestion/
│   ├── arxiv_ingest.py             # ArXiv API scraper
│   ├── ssrn_ingest.py              # SSRN RSS scraper
│   ├── reddit_ingest.py            # Reddit PRAW scraper
│   ├── twitter_ingest.py           # Twitter/X scraper
│   ├── youtube_ingest.py           # YouTube transcript extractor
│   ├── github_ingest.py            # GitHub README scraper
│   ├── blog_ingest.py              # RSS/blog scraper
│   ├── book_ingest.py              # Book/ebook ingestion
│   └── manual_ingest.py            # URL submission
├── extraction/
│   ├── pdf_extractor.py            # MinerU/Marker PDF extraction
│   ├── normalizer.py               # All sources → standard format
│   └── transcript_cleaner.py       # YouTube noise removal
├── evaluation/
│   ├── evaluator.py                # Multi-LLM evaluation gate
│   ├── deduplicator.py             # Embedding similarity check
│   ├── rejection_logger.py         # JSONL rejection log
│   └── review_system.py            # Periodic rejection audit
├── storage/
│   ├── knowledge_writer.py         # Chroma writer with metadata
│   └── embedding_manager.py        # BGE-M3 setup and management
├── synthesis/
│   ├── query_planner.py            # Topic → diverse queries
│   ├── hyde_expander.py            # Hypothetical document embedding
│   ├── retriever.py                # Cross-partition RAG retrieval
│   ├── synthesizer.py              # DeepSeek V3 report generation
│   └── precheck.py                 # GO/CAUTION/STOP pre-dev check
├── scheduling/
│   └── scheduler.py                # APScheduler cron jobs
└── config/
    ├── research_eval_prompt.md      # Evaluation rubric + examples
    ├── reddit_subreddits.json       # Monitored subreddits
    ├── twitter_watchlist.json       # Monitored accounts
    ├── blog_feeds.json              # RSS feed URLs
    └── book_sources.json            # Curated book/ebook list
```

---

*End of RIS Overview — Version 1.1 — April 2026*
*For detailed specifications, see companion files RIS_01 through RIS_07.*
