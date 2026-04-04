# RIS Operator Guide

Last verified: 2026-04-04
Applies to: RIS v1

This guide covers **what works today**. Every feature that is not yet implemented is
labeled [PLANNED]. If you follow this guide and a command fails, check the Troubleshooting
section before assuming a bug.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `python -m polytool research-ingest --file FILE --no-eval` | Ingest document from file, skip LLM scoring |
| `python -m polytool research-ingest --text "..." --title "..." --no-eval` | Ingest inline text |
| `python -m polytool research-acquire --url URL --source-family FAMILY --no-eval` | Fetch and ingest a URL |
| `python -m polytool research-precheck run --idea "..."` | Run GO/CAUTION/STOP precheck |
| `python -m polytool rag-query --question "..." --hybrid --knowledge-store default` | Query knowledge store |
| `python -m polytool research-health` | System health snapshot |
| `python -m polytool research-stats summary` | Document and claim counts |
| `python -m polytool research-scheduler status` | Scheduler job status |
| `python -m polytool research-scheduler start` | Start background ingestion scheduler |
| `python -m polytool research-report --topic "..."` | Generate deterministic research brief |
| `python -m polytool research-extract-claims` | Run claim extraction on stored documents |
| `python -m polytool research-dossier-extract --dossier-dir PATH` | Extract findings from wallet dossier |

---

## Daily Workflows

### Ingesting Research

#### From a URL (academic paper, blog post, GitHub repo)

Use `research-acquire` for any URL-based source. Always specify `--source-family`
so the correct fetcher is used.

```bash
# Academic paper (arXiv only — SSRN fetching not supported)
python -m polytool research-acquire \
  --url https://arxiv.org/abs/2106.01345 \
  --source-family academic \
  --no-eval

# GitHub repository
python -m polytool research-acquire \
  --url https://github.com/polymarket/clob-client \
  --source-family github \
  --no-eval

# Blog post
python -m polytool research-acquire \
  --url https://example.com/my-post \
  --source-family blog \
  --no-eval

# News article
python -m polytool research-acquire \
  --url https://reuters.com/article/... \
  --source-family news \
  --no-eval
```

Valid `--source-family` values: `academic`, `github`, `blog`, `news`, `book`, `reddit`, `youtube`

**Note on SSRN:** The academic adapter only fetches from arXiv. SSRN URLs will not return
content. If you have a PDF from SSRN, save it locally and use `--file` instead.

**Note on optional dependencies:**
- Reddit requires: `pip install praw`
- YouTube requires: `pip install yt-dlp`
- PDF extraction requires: `pip install pdfplumber`
- DOCX extraction requires: `pip install python-docx`

Without these installed, those source families will fail gracefully with a descriptive error.

#### From manual text (AI chat session findings, notes)

```bash
python -m polytool research-ingest \
  --text "Key finding: prediction markets with wide spreads and thin books at resolution show 15-30% price walk-up in final hour. Source: manual observation from 50 crypto markets." \
  --title "Crypto market resolution drift observation" \
  --source-type manual \
  --no-eval
```

#### From a file (notes, exported doc)

```bash
# Markdown or plain text
python -m polytool research-ingest \
  --file docs/my_research_notes.md \
  --source-type manual \
  --no-eval

# With title override
python -m polytool research-ingest \
  --file path/to/paper.txt \
  --title "My Paper Title" \
  --source-type arxiv \
  --no-eval
```

#### From ArXiv topic search (via adapter path)

First, save an ArXiv fixture JSON, then ingest:

```bash
python -m polytool research-ingest \
  --from-adapter tests/fixtures/ris_external_sources/arxiv_sample.json \
  --source-family academic \
  --no-eval \
  --json
```

The JSON file format matches the ArXiv fetcher output: `{url, title, abstract, authors, published_date}`.

#### From Reddit

Requires `praw` installed and REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET env vars configured.

```bash
python -m polytool research-acquire \
  --url https://www.reddit.com/r/PredictionMarkets/ \
  --source-family reddit \
  --no-eval
```

#### From YouTube

Requires `yt-dlp` installed.

```bash
python -m polytool research-acquire \
  --url https://www.youtube.com/watch?v=VIDEOID \
  --source-family youtube \
  --no-eval
```

Extracts VTT transcript if available, falls back to video description.

### Querying the Knowledge Store

#### Simple RAG query

```bash
python -m polytool rag-query \
  --question "What is the optimal spread for a market maker near resolution?" \
  --knowledge-store default
```

#### Hybrid search (semantic + lexical)

```bash
python -m polytool rag-query \
  --question "prediction market liquidity microstructure" \
  --hybrid \
  --knowledge-store default
```

Hybrid uses RRF fusion (k=60) to combine Chroma vector results with FTS5 lexical results.

#### With reranking

```bash
python -m polytool rag-query \
  --question "avellaneda stoikov market making" \
  --hybrid \
  --rerank \
  --knowledge-store default
```

Reranking uses the cross-encoder (cross-encoder/ms-marco-MiniLM-L-6-v2). Adds ~0.5s latency.
Results will be more precisely ordered but the top-K set is the same as hybrid.

### Running Precheck Before Implementation

Before starting any feature or strategy implementation, run a precheck:

```bash
python -m polytool research-precheck run \
  --idea "Implement inventory skew in market maker v2 using Avellaneda-Stoikov gamma parameter" \
  --no-ledger
```

Interpret the result:
- **GO** — No blockers found. Strong supporting evidence, no contradictions.
- **CAUTION** — Mixed or sparse evidence. Note the concerns flagged and proceed carefully.
- **STOP** — A known contradiction or fundamental blocker exists. Do not proceed without operator discussion.

**Note:** With an empty knowledge store or ManualProvider (the default), precheck always returns
CAUTION. This is expected behavior for the placeholder provider. To get meaningful results,
ingest relevant research first and use OllamaProvider if available.

To inspect past precheck records and overrides:

```bash
python -m polytool research-precheck inspect \
  --db kb/rag/knowledge/knowledge.sqlite3
```

### Generating Research Reports

```bash
python -m polytool research-report --topic "market maker spread optimization"
```

Produces a deterministic ResearchBrief from the knowledge store. Includes:
- Key findings (top 5 non-contradicted claims)
- Contradictions section
- Actionability assessment (strategy track routing)
- Knowledge gaps
- Sources cited

Output is plain text / markdown to stdout. Pipe to a file for persistence.

**[PLANNED]** LLM-based narrative synthesis (DeepSeek V3). Currently all report sections
are assembled deterministically from claim metadata.

### Health Monitoring

#### research-health

```bash
python -m polytool research-health
```

Returns a snapshot of 6 health check results. Sample output:

```
pipeline_failed: GREEN (no failures in last 48h)
no_new_docs_48h: GREEN (3 new docs)
accept_rate_low: GREEN (accept rate 85%)
accept_rate_high: GREEN
model_unavailable: GREEN [stub - deferred]
rejection_audit_disagreement: GREEN [stub - deferred]
```

The last two checks (model_unavailable, rejection_audit_disagreement) are stubs that always
return GREEN regardless of state. They are deferred to RIS v2.

#### research-stats

```bash
# Summary counts
python -m polytool research-stats summary

# Document listing
python -m polytool research-stats docs

# Claim listing
python -m polytool research-stats claims
```

#### research-scheduler status

```bash
python -m polytool research-scheduler status
```

Shows which jobs are registered and their last run time.

---

## Scheduler Setup

The scheduler runs background ingestion jobs using APScheduler. It is optional —
all ingestion can be done manually with `research-acquire` and `research-ingest`.

```bash
# Start the scheduler (runs in foreground; use nohup or a process manager for background)
python -m polytool research-scheduler start

# Stop the scheduler
python -m polytool research-scheduler stop

# List all registered jobs
python -m polytool research-scheduler list
```

**Scheduled jobs:**

| Job | Frequency | What it fetches |
|-----|-----------|-----------------|
| academic_ingest | Every 12h | arXiv papers (topic-based) |
| reddit_polymarket | Every 6h | r/PredictionMarkets, r/polymarket |
| reddit_others | Daily | Adjacent subreddits |
| blog_ingest | Every 4h | Configured blog URLs |
| youtube_ingest | Weekly (Mon) | Configured YouTube channels |
| github_ingest | Weekly (Wed) | Configured GitHub repos |
| freshness_refresh | Weekly (Sun) | Recomputes freshness scores |
| weekly_digest | Weekly (Sun) | Digest of week's ingestion |

**Caveats:**
- Reddit jobs require praw + Reddit API credentials
- YouTube jobs require yt-dlp
- Twitter/X is explicitly not scheduled [PLANNED]
- Scheduler writes all run results to `artifacts/research/run_log.jsonl`

---

## Advanced Workflows

### Dossier Extraction

Extract research-grade findings from a wallet dossier bundle (output of `wallet-scan` and
`alpha-distill`):

```bash
python -m polytool research-dossier-extract \
  --dossier-dir artifacts/dossiers/users/wallet_0x1234/ \
  --ingest
```

Without `--ingest`, the command extracts and displays findings. With `--ingest`, it
stores them directly into the knowledge store.

The extractor parses: `dossier.json`, `memo.md`, `hypothesis_candidates.json`,
`segment_analysis.json`. Each parsed section becomes a separate DERIVED_CLAIM.

### SimTrader Bridge

Register a research hypothesis into the hypothesis registry:

```bash
python -m polytool research-bridge \
  --brief-id BRIEF_ID \
  --register
```

The bridge maps a ResearchBrief or PrecheckResult to a hypothesis candidate in the
SimTrader hypothesis registry. Used to connect research findings to strategy validation.

After an experiment concludes, record the validation outcome:

```bash
python -m polytool research-bridge \
  --outcome win|loss|inconclusive \
  --hypothesis-id HYPO_ID
```

**[PLANNED]** Auto-orchestration from precheck to hypothesis registration to Discord
approval flow. Currently requires manual bridge calls.

### Claim Extraction

Run claim extraction on all documents currently in the knowledge store that have not
yet had claims extracted:

```bash
python -m polytool research-extract-claims
```

Claim extraction uses `heuristic_v1` (deterministic, no LLM). For each document:
1. Splits body into candidate sentences
2. Scores by hedging-language and confidence patterns
3. Stores DERIVED_CLAIM records
4. Builds SUPPORTS/CONTRADICTS relations from shared key terms

All claims are viewable via `research-stats claims`.

### Calibration

Track evaluation drift over time:

```bash
python -m polytool research-calibration summary
```

Records when evaluation scoring changes (prompt template updates, provider changes).
Used to detect drift between different evaluation sessions.

---

## What Does NOT Work Yet [PLANNED]

The following features are documented in specs or the roadmap but are **not implemented**:

- **Twitter/X ingestion** — No adapter, no fetcher, not scheduled. Explicitly excluded.
- **SSRN adapter** — No SSRN-specific fetcher. Academic adapter only covers arXiv.
- **Cloud LLM evaluation providers** — Gemini, DeepSeek, OpenAI, Anthropic all raise
  ValueError when called. These are "RIS v2 deliverables."
- **LLM-based report synthesis** — DeepSeek V3 narrative generation is v2.
- **Discord alert integration** — `packages/polymarket/notifications/discord.py` exists
  but is NOT wired to the research alert sink. Research uses `LogSink` by default. To
  use Discord, configure `WebhookSink` manually.
- **Grafana panels** — No RIS metrics panels exist in Grafana dashboards.
- **ClickHouse tables** — No RIS data in ClickHouse. Everything is SQLite or JSONL.
- **Multi-hop query planning** — Query planner is single-hop only.
- **past_failures in precheck** — Field exists but is always empty; populated in v2.
- **Auto-promotion from research to hypothesis** — Manual bridge calls required.
- **model_unavailable health check** — Returns GREEN stub, does not actually detect Ollama outage.
- **rejection_audit_disagreement health check** — Returns GREEN stub.

---

## Troubleshooting

### Common errors and fixes

**"No module named praw"**
Reddit ingestion requires praw: `pip install praw`

**"No module named yt_dlp"**
YouTube ingestion requires yt-dlp: `pip install yt-dlp`

**"No module named pdfplumber"**
PDF extraction requires pdfplumber: `pip install pdfplumber`

**"Provider gemini is a RIS v2 deliverable"**
Cloud LLM providers are not implemented. Use `--provider manual` (default) or
`--provider ollama` if you have Ollama running.

**Precheck always returns CAUTION**
With the default ManualProvider, precheck falls back to CAUTION (hardcoded placeholder).
This is expected. Either:
1. Ingest more relevant research so the evidence base is populated, or
2. Use `--provider ollama` for actual reasoning (requires Ollama running)

**"Duplicate document: already ingested"**
SHA256 dedup detected the same document. If you intentionally want to re-ingest,
use a different title or modify the content slightly. Near-duplicate threshold is 0.85
Jaccard similarity (not 0.92 as some older docs state).

**Knowledge store empty after ingest**
Check that ingest did not hard-stop: look for "Rejected: ..." in stderr. Common causes:
- Body too short (< 50 chars): add more content
- Encoding garbage: ensure UTF-8 input
- Duplicate detection: document already exists

**Scheduler not persisting across restarts**
The scheduler does not auto-restart. Use a process manager (systemd, supervisord) or
run in a persistent terminal. No auto-start on boot is wired.

### Environment variables needed

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Optional | GitHub API token for higher rate limits |
| `REDDIT_CLIENT_ID` | Required for Reddit | Reddit API app ID |
| `REDDIT_CLIENT_SECRET` | Required for Reddit | Reddit API app secret |
| `REDDIT_USER_AGENT` | Optional | Custom user agent string |
| `SENTENCE_TRANSFORMERS_HOME` | Optional | Cache dir for embedding model |
| `RIS_ENABLE_CLOUD_PROVIDERS` | No effect | Cloud providers still raise ValueError |

### Optional dependencies

| Package | When needed | Install |
|---------|-------------|---------|
| `praw` | Reddit ingestion | `pip install praw` |
| `yt-dlp` | YouTube ingestion | `pip install yt-dlp` |
| `pdfplumber` | PDF extraction | `pip install pdfplumber` |
| `python-docx` | DOCX extraction | `pip install python-docx` |
| `chardet` | Encoding detection | `pip install chardet` |

All are optional. RIS works without them, but those source families will be unavailable.

---

## File Layout Reference

```
packages/
  research/
    ingestion/         # Layer 1: adapters, fetchers, pipeline, extractors, claim_extractor
    evaluation/        # Layer 2: evaluator, scoring, providers, dedup, hard_stops
    synthesis/         # Layer 4: query_planner, hyde, retrieval, report, precheck, precheck_ledger
    scheduling/        # APScheduler integration
    monitoring/        # Health checks, run_log, alert_sink
    integration/       # hypothesis_bridge, validation_feedback, dossier_extractor
  polymarket/
    rag/               # Layer 3: knowledge_store (SQLite), index (Chroma), lexical (FTS5),
                       #           chunker, embedder, query, reranker, freshness, metadata

tools/cli/
  research_ingest.py       # research-ingest command
  research_acquire.py      # research-acquire command
  research_precheck.py     # research-precheck command
  research_health.py       # research-health command
  research_stats.py        # research-stats command
  research_report.py       # research-report command
  research_scheduler.py    # research-scheduler command
  research_eval.py         # research-eval command
  research_seed.py         # research-seed command
  research_bridge.py       # research-bridge command
  research_calibration.py  # research-calibration command
  research_dossier_extract.py  # research-dossier-extract command
  research_extract_claims.py   # research-extract-claims command
  research_benchmark.py        # research-benchmark command

kb/
  rag/
    knowledge/
      knowledge.sqlite3        # KnowledgeStore: source_documents, derived_claims, claim_relations
      precheck_ledger.sqlite3  # Precheck override audit trail

artifacts/
  research/
    run_log.jsonl              # Per-run health records
    raw_source_cache/          # Cached raw fetch results

config/
  freshness_decay.json         # Per-source-family freshness half-life values
```
