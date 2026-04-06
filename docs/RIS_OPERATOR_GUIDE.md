# RIS Operator Guide

Last verified: 2026-04-06
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

## n8n RIS Pilot (Opt-In)

**Scope boundary:** n8n is approved for RIS ingestion jobs only per ADR 0013
(`docs/adr/0013-ris-n8n-pilot-scoped.md`). It is not a Phase 3 automation layer and
does not grant access to strategy, gate, risk, or live capital surfaces.

### Scheduler selection

The repo has two scheduling options for RIS background jobs. They are mutually exclusive:

| Option | Mechanism | When active |
|--------|-----------|-------------|
| APScheduler | `ris-scheduler` container (no profile) | Default — always starts with `docker compose up` |
| n8n | `n8n` container (profile: `ris-n8n`) | Opt-in — started with `--with-n8n` flag |

**Running both simultaneously causes double-scheduling** (each RIS job runs twice per
period). This is an operator error. The system does not auto-prevent it.

To use n8n as the scheduler:
1. Stop APScheduler: `docker compose stop ris-scheduler`
2. Start n8n: `bash scripts/docker-start.sh --with-n8n`
3. Set `RIS_SCHEDULER_BACKEND=n8n` in `.env` to document the active choice (informational only).

To switch back to APScheduler:
```bash
docker compose stop n8n
docker compose up -d ris-scheduler
```
Then set `RIS_SCHEDULER_BACKEND=apscheduler` in `.env`.

### Start / import / activate (step-by-step)

1. Copy `.env.example` n8n section into `.env`. Set real values for:
   - `N8N_BASIC_AUTH_PASSWORD` (use a strong password)
   - `N8N_ENCRYPTION_KEY` (minimum 32 characters — used to encrypt stored credentials)
   - `N8N_MCP_BEARER_TOKEN` (compose-side env var read by n8n at startup; operative
     when instance-level MCP is enabled in n8n Settings UI; see MCP section below)
   Keep `N8N_BASIC_AUTH_USER=admin` or change to your preferred username.

2. Stop APScheduler if switching to n8n:
   ```bash
   docker compose stop ris-scheduler
   ```

3. Start n8n:
   ```bash
   bash scripts/docker-start.sh --with-n8n
   ```
   The script prints a warning if double-scheduling is possible.

4. Verify n8n is up:
   ```bash
   curl -s http://localhost:5678/healthz
   # Expected: {"status":"ok"}
   ```

5. Import workflow templates:
   ```bash
   bash infra/n8n/import-workflows.sh
   ```
   The script uses `docker exec polytool-n8n n8n import:workflow --input=<file>` (no
   curl or REST API required). Pass an alternative container name as the first positional
   arg if you renamed the container.

6. Log in to http://localhost:5678 with your admin credentials.

7. Review each imported workflow. All workflows import with `"active": false`.
   Activate only the workflows you want running by toggling the Active switch in the UI.

8. For cron-triggered workflows: confirm the trigger interval does not overlap with any
   manual `research-scheduler` runs you have scheduled elsewhere.

### Manual verification

After import:
- Open the `RIS Health Check` workflow in the n8n UI.
- Click `Execute workflow` (manual trigger button).
- In the Execute Command node output, confirm you see `research-health` CLI output with
  health check results (`pipeline_failed`, `no_new_docs_48h`, etc.).

After activating a cron trigger:
- Check the `Executions` tab after the first scheduled run.
- Confirm exit code `0` in the Execute Command node output.

If a workflow fails:
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

### Webhook usage (ris_manual_acquire)

The `RIS Manual Acquire (Webhook)` workflow accepts a POST request to trigger URL
ingestion without CLI access:

```bash
# After activating the workflow and copying the webhook URL from the n8n UI:
curl -X POST "http://localhost:5678/webhook/ris-acquire" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://arxiv.org/abs/2106.01345", "source_family": "academic"}'
```

**Security note:** The webhook URL contains an n8n-generated path token. Treat it as
a secret. Do not share or commit it. If compromised, delete and recreate the workflow
in n8n to generate a new token.

### Scheduled Job Workflows

Eight workflow templates cover every job in the JOB_REGISTRY. All use `research-scheduler run-job <id>` so n8n and APScheduler call the same job logic.

| Job ID | n8n Workflow File | CLI Command | Cron Schedule | Caveats |
|--------|------------------|-------------|---------------|---------|
| academic_ingest | ris_academic_ingest.json | `research-scheduler run-job academic_ingest` | every 12h | ArXiv only |
| reddit_polymarket | ris_reddit_polymarket.json | `research-scheduler run-job reddit_polymarket` | every 6h | Requires praw + Reddit API creds |
| reddit_others | ris_reddit_others.json | `research-scheduler run-job reddit_others` | daily 03:00 | Requires praw + Reddit API creds |
| blog_ingest | ris_blog_ingest.json | `research-scheduler run-job blog_ingest` | every 4h | None |
| youtube_ingest | ris_youtube_ingest.json | `research-scheduler run-job youtube_ingest` | Mondays 04:00 | Requires yt-dlp |
| github_ingest | ris_github_ingest.json | `research-scheduler run-job github_ingest` | Wednesdays 04:00 | Optional: GITHUB_TOKEN for rate limits |
| freshness_refresh | ris_freshness_refresh.json | `research-scheduler run-job freshness_refresh` | Sundays 02:00 | Re-scans ArXiv only |
| weekly_digest | ris_weekly_digest.json | `research-scheduler run-job weekly_digest` | Sundays 08:00 | Internally calls research-report digest --window 7 |

**Scheduler mutual exclusion:** When n8n cron workflows are active, stop APScheduler first (`docker compose stop ris-scheduler`) to avoid double-scheduling. Running both simultaneously causes each RIS job to run twice per period. See the scheduler selection table above for the full switching procedure.

**Runtime verification note:** These workflows ARE runtime-verified. Smoke test results
from quick-260406-ido (2026-04-06, n8n 2.14.2): build OK, docker-cli v29.3.1 confirmed
inside n8n container, exec bridge to `polytool-ris-scheduler` verified, 11/11 workflows
imported successfully via `bash infra/n8n/import-workflows.sh`.

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
