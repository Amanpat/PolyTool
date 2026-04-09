# RIS Operator Guide

Last verified: 2026-04-09
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
| `python -m polytool research-review list` | List pending review queue items |
| `python -m polytool research-review accept <doc_id>` | Accept and ingest a queued document |
| `python -m polytool research-review reject <doc_id>` | Reject a queued document |
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

### Evaluation Gate

The shipped weighted composite gate scores documents across four dimensions and routes to a disposition:

**Formula:** `composite = relevance*0.30 + novelty*0.25 + actionability*0.25 + credibility*0.20`

**Per-dimension floors (waived for priority_1):**
- `relevance >= 2`
- `credibility >= 2`

**Priority tier thresholds:**
| Priority | Minimum composite |
|----------|------------------|
| priority_1 | >= 2.5 |
| priority_2 | >= 3.0 |
| priority_3 | >= 3.2 |
| priority_4 | >= 3.5 |

**Provider routing:** gemini (primary) -> deepseek (escalation) -> ollama (fallback). Configurable via `RIS_EVAL_PRIMARY_PROVIDER`, `RIS_EVAL_ESCALATION_PROVIDER`, `RIS_EVAL_FALLBACK_PROVIDER`.

**Fail-closed behavior:** Any provider error, timeout, or malformed JSON response results in a REJECT with `reject_reason="scorer_failure"` and queues the document to `pending_review` as BLOCKED.

**Run evaluation from CLI:**
```bash
python -m polytool research-eval eval \
  --title "Document title" \
  --body "Document body text" \
  [--provider gemini] \
  [--enable-cloud] \
  [--json]
```

**Cloud providers require:**
- `RIS_ENABLE_CLOUD_PROVIDERS=1`
- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) for Gemini
- `DEEPSEEK_API_KEY` for DeepSeek

Without `--enable-cloud`, the ManualProvider is used (all dimensions = 3, deterministic).

### Review Queue

After evaluation, documents land in one of four dispositions:

| Disposition | Gate | Action |
|-------------|------|--------|
| `accepted` | ACCEPT | Ingested into knowledge store immediately |
| `queued_for_review` | REVIEW | Queued to `pending_review` for operator action |
| `rejected` | REJECT | Not ingested; no queue entry |
| `blocked` | scorer failure | Queued to `pending_review` with failure reason |

**Review queue CLI:**

```bash
# List all pending review items
python -m polytool research-review list

# Inspect a specific document
python -m polytool research-review inspect <doc_id>

# Accept a queued document (triggers ingest)
python -m polytool research-review accept <doc_id>

# Reject a queued document (removes from queue, no ingest)
python -m polytool research-review reject <doc_id>

# Defer a queued document (keeps in queue for later)
python -m polytool research-review defer <doc_id>
```

Use `--db <path>` to point at a specific knowledge store if not using the default path.

The `pending_review` table has an append-only audit history (`pending_review_history`). All operator actions (accept/reject/defer) are recorded with timestamps.

### Health Monitoring

#### research-health

```bash
python -m polytool research-health
```

Returns a snapshot of 7 health check results. Sample output:

```
CHECK                                    STATUS   MESSAGE
--------------------------------------------------------------------
pipeline_failed                          GREEN    No current pipeline failures detected.
no_new_docs_48h                          GREEN    3 document(s) accepted in the monitored window.
accept_rate_low                          GREEN    Accept rate is healthy: 85.0% (17/20).
accept_rate_high                         GREEN    Accept rate is 85.0% (17/20) -- within expected bounds.
model_unavailable                        GREEN    No provider failures detected.
review_queue_backlog                     GREEN    Review queue manageable: 5 items pending.
rejection_audit_disagreement             GREEN    [DEFERRED] Rejection audit check requires audit runner. Not yet wired.

Overall: HEALTHY
```

The overall status field distinguishes four states:
- **HEALTHY** -- all checks GREEN, no issues.
- **DEGRADED** -- at least one YELLOW, no RED (e.g. accept rate low, queue growing).
- **BLOCKED_ON_SETUP** -- RED is caused by unconfigured providers (no API keys set).
- **FAILURE** -- at least one RED from a real operational issue.

`model_unavailable` is now a real check driven by provider failure data from eval artifacts.
`rejection_audit_disagreement` remains deferred (requires audit runner).

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

# Check scheduler status (registered jobs + last run times)
python -m polytool research-scheduler status

# Trigger a job immediately without waiting for cron
python -m polytool research-scheduler run-job <job_name>
```

Note: `research-scheduler stop` and `research-scheduler list` are not implemented.
To stop APScheduler, stop the container: `docker compose stop ris-scheduler`.

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

### Retrieval Benchmark

Run the Phase 2 segmented retrieval benchmark to evaluate knowledge store retrieval quality:

```bash
# Run against the Phase 2 benchmark suite
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl

# Run with reranker
python -m polytool rag-eval \
  --suite docs/eval/ris_retrieval_benchmark.jsonl \
  --rerank-model cross-encoder/ms-marco-MiniLM-L-6-v2

# Verify corpus identity without running eval
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --suite-hash-only
```

**Query classes:** `factual` (direct lookup), `analytical` (multi-doc synthesis), `exploratory` (open-ended research).

**8 required metrics tracked per class and retrieval mode:**

| Metric | Description |
|--------|-------------|
| `query_count` | Number of cases in this aggregate |
| `mean_recall_at_k` | Mean recall@k across cases |
| `mean_mrr_at_k` | Mean MRR@k |
| `total_scope_violations` | Total must_exclude_any matches |
| `queries_with_violations` | Cases with at least one violation |
| `mean_latency_ms` | Mean query latency |
| `p50_latency_ms` | Median latency |
| `p95_latency_ms` | P95 latency |

**Artifacts written to:** `kb/rag/eval/reports/<timestamp>/report.json` and `summary.md`. The `report.json` includes `per_class_modes`, `corpus_hash`, and `eval_config` for reproducibility.

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
- **Cloud LLM evaluation providers (partial)** — Gemini and DeepSeek are now implemented
  (requires `RIS_ENABLE_CLOUD_PROVIDERS=1` plus API keys). OpenAI and Anthropic are not
  implemented and remain deferred.
- **LLM-based report synthesis** — DeepSeek V3 narrative generation is v2.
- **Discord alert integration** — `packages/polymarket/notifications/discord.py` exists
  but is NOT wired to the research alert sink. Research uses `LogSink` by default. To
  use Discord, configure `WebhookSink` manually.
- **Grafana panels** — No RIS metrics panels exist in Grafana dashboards.
- **ClickHouse tables** — No RIS data in ClickHouse. Everything is SQLite or JSONL.
- **Multi-hop query planning** — Query planner is single-hop only.
- **past_failures in precheck** — Field exists but is always empty; populated in v2.
- **Auto-promotion from research to hypothesis** — Manual bridge calls required.
- **rejection_audit_disagreement health check** — Returns GREEN stub (deferred until audit runner is implemented).

---

## Troubleshooting

### Common errors and fixes

**"No module named praw"**
Reddit ingestion requires praw: `pip install praw`

**"No module named yt_dlp"**
YouTube ingestion requires yt-dlp: `pip install yt-dlp`

**"No module named pdfplumber"**
PDF extraction requires pdfplumber: `pip install pdfplumber`

**Provider unavailable / timeout**
If a cloud provider times out or is rate-limited, the evaluator routes to the next provider
in the chain (gemini -> deepseek -> ollama). Check `research-health` for provider failure
counts. Ensure `RIS_ENABLE_CLOUD_PROVIDERS=1` and the relevant API key env vars are set
(`GEMINI_API_KEY` or `GOOGLE_API_KEY` for Gemini; `DEEPSEEK_API_KEY` for DeepSeek).
Use `--provider ollama` if you only have a local Ollama instance available.

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
| `RIS_ENABLE_CLOUD_PROVIDERS` | Optional | Set to `1` to enable Gemini/DeepSeek cloud routing for evaluation gate scoring |
| `GEMINI_API_KEY` | Required for Gemini | Gemini API key (also accepted as `GOOGLE_API_KEY`) |
| `DEEPSEEK_API_KEY` | Required for DeepSeek | DeepSeek API key |
| `RIS_EVAL_PRIMARY_PROVIDER` | Optional | Override primary eval provider (default: `gemini`) |
| `RIS_EVAL_ESCALATION_PROVIDER` | Optional | Override escalation provider (default: `deepseek`) |
| `RIS_EVAL_FALLBACK_PROVIDER` | Optional | Override fallback provider (default: `ollama`) |
| `RIS_EVAL_ESCALATE_REVIEW_DECISIONS` | Optional | Set to `1` to escalate REVIEW-gated results to next provider |
| `RIS_EVAL_FALLBACK_ON_PROVIDER_UNAVAILABLE` | Optional | Set to `1` to fall through to next provider on unavailability |

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

## n8n RIS Pilot (Opt-In)

**Scope boundary:** n8n is approved for RIS ingestion jobs only per ADR 0013
(`docs/adr/0013-ris-n8n-pilot-scoped.md`). It is not a Phase 3 automation layer and
does not grant access to strategy, gate, risk, or live capital surfaces.

### Scheduler selection

Current operator truth:

- APScheduler remains the default scheduler.
- n8n is an opt-in sidecar for the RIS pilot, not the default scheduler handoff.
- Use `python infra/n8n/import_workflows.py` as the canonical import command.
- Use `GET /webhook/ris-health` and `POST /webhook/ris-ingest` as the smoke path.
- n8n Execute Command nodes run through `docker exec polytool-ris-scheduler python -m polytool ...`.
- Only stop APScheduler if you intentionally enable n8n schedule triggers in the UI and want n8n to own recurring runs.

The repo has two scheduling options for RIS background jobs. They are mutually exclusive:

| Option | Mechanism | When active |
|--------|-----------|-------------|
| APScheduler | `ris-scheduler` container (no profile) | Default — always starts with `docker compose up` |
| n8n | `n8n` container (profile: `ris-n8n`) | Opt-in — started with `--with-n8n` flag |

Use `docker compose --profile ris-n8n up -d n8n` for the current startup path. Older
`--with-n8n` wrapper references are historical.

**Running both simultaneously causes double-scheduling** (each RIS job runs twice per
period). This is an operator error. The system does not auto-prevent it.

Use n8n alongside APScheduler for the normal operator path. Only if you deliberately
enable n8n schedule triggers should you stop APScheduler first:

```bash
docker compose stop ris-scheduler
```

### Start / import / smoke (step-by-step)

1. Copy `.env.example` n8n section into `.env`. Set real values for:
   - `N8N_API_KEY` (required by `python infra/n8n/import_workflows.py`)
   - `N8N_BASIC_AUTH_PASSWORD` (use a strong password)
   - `N8N_ENCRYPTION_KEY` (minimum 32 characters — used to encrypt stored credentials)
   - `N8N_MCP_BEARER_TOKEN` (compose-side env var read by n8n at startup; operative
     when instance-level MCP is enabled in n8n Settings UI; see MCP section below)
   Keep `N8N_BASIC_AUTH_USER=admin` or change to your preferred username.

2. Start the default stack and leave APScheduler running:
   ```bash
   docker compose up -d
   ```

3. Start n8n:
   ```bash
   docker compose --profile ris-n8n up -d n8n
   ```

4. Verify n8n is up:
   ```bash
   curl -s http://localhost:5678/healthz
   # Expected: {"status":"ok"}
   ```

5. Import the canonical RIS pilot workflow set:
   ```bash
   python infra/n8n/import_workflows.py
   ```
   This imports `workflows/n8n/ris-unified-dev.json` plus
   `workflows/n8n/ris-health-webhook.json`, updates `workflows/n8n/workflow_ids.env`,
   and activates both workflows. `infra/n8n/workflows/` is legacy/reference-only and is
   not the default import target.

6. Log in to http://localhost:5678 with your admin credentials.

7. Review the imported `RIS -- Research Intelligence System` workflow and the
   `RIS -- Health Webhook` support workflow.

8. Leave schedule triggers disabled unless you explicitly want n8n to replace
   APScheduler for recurring runs.

### Manual verification

After import:
- Smoke the dedicated health workflow:
  ```bash
  curl http://localhost:5678/webhook/ris-health
  ```
- Smoke the unified ingest webhook:
  ```bash
  curl -X POST "http://localhost:5678/webhook/ris-ingest" \
    -H "Content-Type: application/json" \
    -d '{"url":"https://arxiv.org/abs/2106.01345","source_family":"academic"}'
  ```
- If you inspect the UI, confirm Execute Command nodes use:
  `docker exec polytool-ris-scheduler python -m polytool ...`

If a section fails:
- Open the failed execution and check the Execute Command node output.
- Common causes:
  - `python` not found: this is expected if the command runs directly in the n8n
    container. All workflow commands use the docker-exec bridge pattern:
    `docker exec polytool-ris-scheduler python -m polytool ...`. If a command is
    missing the `docker exec polytool-ris-scheduler` prefix, add it.
  - CLOB credentials not set: this should not affect RIS-only workflows; if it does,
    check that the correct container is being targeted.
  - `--source-family` invalid (manual acquire): must be one of `academic`, `github`,
    `blog`, `news`, `book`, `reddit`, `youtube`.

### Webhook usage (URL Ingestion section)

The unified workflow includes a URL Ingestion section that accepts a POST request to
trigger URL ingestion without CLI access:

```bash
curl -X POST "http://localhost:5678/webhook/ris-ingest" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/2106.01345", "source_family": "academic"}'
```

**Operator note:** This local smoke path uses the fixed dev endpoint
`http://localhost:5678/webhook/ris-ingest`. Keep n8n on the trusted local network only.

### Unified Workflow Sections

The canonical file `workflows/n8n/ris-unified-dev.json` contains one unified workflow
with 9 sections on one canvas. The scheduled/manual sections still call the same RIS
CLI surfaces as APScheduler.

| Section | Trigger | CLI command | Schedule / Notes |
|--------|---------|-------------|------------------|
| Health Monitor | Schedule | `research-health` + `research-stats summary` | Every 30 min |
| Academic | Manual + Schedule | `research-scheduler run-job academic_ingest` | every 12h |
| Reddit | Manual + Schedule | `research-scheduler run-job reddit_polymarket` | every 6h |
| Blog/RSS | Manual + Schedule | `research-scheduler run-job blog_ingest` | every 4h |
| YouTube | Manual + Schedule | `research-scheduler run-job youtube_ingest` | Mondays 04:00 UTC |
| GitHub | Manual + Schedule | `research-scheduler run-job github_ingest` | Wednesdays 04:00 UTC |
| Freshness | Manual + Schedule | `research-scheduler run-job freshness_refresh` | Sundays 02:00 UTC |
| Weekly Digest | Manual + Schedule | `research-report digest --window 7` + `research-stats summary` | Sundays 08:00 UTC |
| URL Ingestion | Webhook | `research-acquire --url ... --source-family ...` | POST `/webhook/ris-ingest` |

Historical multi-file JSONs in `workflows/n8n/*.json` and `infra/n8n/workflows/*.json`
are reference-only and are not imported by default.

**Scheduler mutual exclusion:** When n8n scheduled sections are active, stop APScheduler
first (`docker compose stop ris-scheduler`) to avoid double-scheduling. The normal
operator path leaves APScheduler running because the committed workflow keeps n8n
schedule triggers disabled by default.

**Repo truth note:** Earlier smoke tests imported the older 11-workflow pilot. The
current canonical repo source is the unified single-canvas workflow above, and
`python infra/n8n/import_workflows.py` now imports the canonical workflow set by default.

### Claude Code MCP connection

#### polytool MCP server (stdio — for Claude Desktop)

The polytool MCP server uses **stdio transport only** (not HTTP). It is designed for
Claude Desktop integration via a stdio pipe — not for HTTP access from n8n or other
network-connected services.

To start the MCP server for Claude Desktop:

```bash
python -m polytool mcp
# Optional: add --log-level DEBUG for verbose output to stderr
```

The server only accepts `--log-level`. There is no `--port`, `--host`, or HTTP endpoint.
Run `python -m polytool mcp --help` to confirm.

**n8n does NOT use polytool MCP.** All n8n workflows call CLI commands directly via the
docker-exec bridge pattern:
```
docker exec polytool-ris-scheduler python -m polytool <command>
```
This is the only supported integration path for n8n and is documented in the workflow
templates section above.

#### n8n 2.x built-in MCP server (HTTP — bearer token auth)

n8n 2.x ships with an instance-level MCP server at `/mcp-server/http`. The HTTP
backend works on **community edition n8n >= 2.14.2** — it is NOT Enterprise-only.

Probing results from 2026-04-06 (community edition, n8n 2.14.2):
- `GET /mcp-server/http` → 200 HTML (SPA catch-all — GET with no body hits the frontend)
- `POST /mcp-server/http` with `Content-Type: application/json` + `Accept: application/json,
  text/event-stream` + valid JWT → 200 OK, MCP initialize response:
  `{"serverInfo":{"name":"n8n MCP Server","version":"1.1.0"}}`
- `POST /mcp-server/http` without `Accept` header → 406 Not Acceptable
- `POST /mcp-server/http` with malformed token → 401 Unauthorized: jwt malformed

Authentication requires a JWT bearer token generated from the n8n UI
(Settings -> Instance-level MCP). The token is a static HS256-signed JWT
with `iss=n8n`, `aud=mcp-server-api`.

**N8N_MCP_BEARER_TOKEN** in `docker-compose.yml` and `.env.example` is the
compose-side env var that n8n reads at container startup.

**Important note on Claude Code env-var expansion:** Claude Code does NOT expand
`${VAR}` template strings in HTTP-type `.mcp.json` entries. The `n8n-instance-mcp`
entry has been removed from `.mcp.json`. Use `claude mcp add` with the `-s local`
scope (see "Instance-level MCP setup" below) — this keeps the token out of tracked
files entirely.

To summarize the two distinct MCP paths:

| MCP Path | Transport | Available | Auth |
|----------|-----------|-----------|------|
| polytool MCP (`python -m polytool mcp`) | stdio | YES (n8n >= 2.14.2, community) | Claude Desktop config |
| n8n built-in MCP (`/mcp-server/http`) | HTTP | YES (n8n >= 2.14.2, community) | Bearer token (JWT from n8n UI) |

#### Instance-level MCP setup

Follow these manual steps to enable Claude Code's n8n MCP connection:

1. **Enable instance-level MCP in n8n UI:**
   Settings -> Instance-level MCP -> toggle ON

2. **Generate or copy the Access Token** from the same settings page.

3. **Enable MCP access per workflow:**
   Open each workflow you want Claude Code to access -> Settings -> toggle
   "Allow MCP access" ON. Only enabled workflows are visible via MCP.

4. **Register the MCP server using `claude mcp add`** (use `-s local` to keep
   the token out of `.mcp.json` and git-tracked files):
   ```bash
   claude mcp add --transport http \
     --header "Authorization: Bearer <paste-token-from-step-2>" \
     n8n-instance-mcp http://localhost:5678/mcp-server/http \
     -s local
   ```
   The `-s local` flag stores the config in a user-local file, not `.mcp.json`.

5. **Restart or reopen Claude Code** from the repo root. Run as: `claude` from
   the repo directory.

6. **Verify** by running `claude mcp list`. The entry should show:
   `n8n-instance-mcp: http://localhost:5678/mcp-server/http (HTTP) - Connected`

**Env var distinction:** `N8N_MCP_BEARER_TOKEN` (in `docker-compose.yml` /
`.env.example`) is the compose-side env var that n8n reads at container startup.
The Claude Code side token is passed directly via `claude mcp add --header` (not
via env-var expansion in `.mcp.json`, which does not work for HTTP servers).

See `infra/n8n/README.md` for the workflow layout and further n8n infrastructure
details.

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
