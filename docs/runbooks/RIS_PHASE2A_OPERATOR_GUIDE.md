# RIS Phase 2A — Operator Guide

Last verified: 2026-04-23
Applies to: RIS Phase 2A (WP1–WP5)

This guide answers one question: **how do I use what Phase 2A built?**
It covers first-time activation, validation, daily use, and monitoring.
It does not cover Hermes, SimTrader, or anything outside RIS.

---

## What Phase 2A Includes

| Work packet | What it delivers |
|---|---|
| WP1: Foundation Fixes | Corrected scoring weights, per-dimension floors, `provider_events` list contract, 11 foundational docs seeded |
| WP2: Cloud LLM Providers | Gemini Flash (primary) + DeepSeek V3 (escalation) with budget enforcement; `--provider`, `--compare`, `list-providers` CLI |
| WP3: n8n Workflow Visuals | Structured JSON output in Code nodes, ✅/❌ indicators, rich health monitor summary, Discord embeds, daily 09:00 UTC digest |
| WP4: Monitoring | `polytool.n8n_execution_metrics` ClickHouse table, hourly n8n metrics collector, Grafana "RIS Pipeline Health" dashboard, stale-pipeline alert |
| WP5: Retrieval Benchmark | 31-query golden set (5 classes), Precision@5, per-class reporting, `--save-baseline` flag |

**Deferred to Phase 2B:** OpenRouter, Groq, Ollama providers (needed for friends without Google accounts).

---

## Prerequisites

Before activation, verify these are in your `.env`:

```
CLICKHOUSE_PASSWORD=<your password>
GEMINI_API_KEY=<Google AI Studio key>
DEEPSEEK_API_KEY=<DeepSeek platform key>
DISCORD_WEBHOOK_URL=<Discord webhook>
# N8N_API_KEY is generated from the n8n UI — see Step 3 below
```

Docker Desktop must be running.

---

## First-Time Activation

Run these steps once, in order. They cannot be automated because `N8N_API_KEY` is generated post-login from the n8n UI.

### Step 1 — Bring the stack up

```bash
docker compose up -d
docker compose ps
```

All services should show `Up` / `healthy`. ClickHouse, n8n, and Grafana must be running.

The `polytool.n8n_execution_metrics` ClickHouse table is created automatically by the init SQL at container start (`infra/clickhouse/initdb/28_n8n_execution_metrics.sql`).

The Grafana "RIS Pipeline Health" dashboard is auto-provisioned at startup — no manual import needed.

### Step 2 — Import n8n workflows

```bash
python infra/n8n/import_workflows.py --no-activate
```

This imports three canonical RIS workflows into n8n:
- `ris-unified-dev` (main ingestion + health pipeline)
- `ris-health-webhook` (webhook-triggered health check)
- `ris-n8n-metrics-collector` (hourly execution metrics — **imported inactive**)

The metrics collector ships `active: false` intentionally. Do not activate it yet.

### Step 3 — Generate and add the n8n API key

The metrics collector calls the n8n API to read execution history. This key is machine-local and cannot be shipped in the repo.

1. Open `http://localhost:5678` in a browser
2. Complete the n8n owner setup wizard if first time
3. Go to **Settings → API → Create API Key**
4. Copy the generated key
5. Add it to your `.env`:
   ```
   N8N_API_KEY=<generated key>
   ```
6. Restart n8n so the env var is injected:
   ```bash
   docker compose up -d n8n
   ```

### Step 4 — Activate the metrics collector

In the n8n UI, find the `ris-n8n-metrics-collector` workflow and toggle it **Active**.

On the next hourly tick, it will query the n8n execution API and write results to `polytool.n8n_execution_metrics`.

### Step 5 — Restart Grafana to load the stale-pipeline alert

```bash
docker compose restart grafana
```

This picks up `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`. After restart:
- Navigate to `http://localhost:3000` → **Alerting → Alert Rules**
- Confirm the group `ris-pipeline-health` and rule `ris-stale-pipeline-alert` are visible

### Step 6 — Wire the Grafana Discord contact point

This step cannot be provisioned in git (avoids committing the webhook URL).

1. In Grafana: **Alerting → Contact Points → Add contact point**
2. Name: `discord-ris`
3. Type: Discord
4. Webhook URL: paste your Discord webhook URL
5. Save
6. Go to **Alerting → Notification Policies → Edit default policy → Contact point: `discord-ris`**

The stale-pipeline alert will now deliver to Discord when a workflow goes more than 6 hours without a successful execution.

---

## Validation Run

Run this once after activation to confirm Phase 2A is end-to-end operational.
These steps require live Docker, API keys, and Discord observation.

### Commit the WP5 changes first (if not already committed)

```bash
git add packages/polymarket/rag/eval.py tools/cli/rag_eval.py tests/test_rag_eval.py docs/eval/ris_retrieval_benchmark.jsonl
git commit -m "feat(ris): WP5 retrieval benchmark — 31 queries, P@5, per-class reporting, baseline save"
```

### V1 — ClickHouse table exists

```bash
curl "http://localhost:8123/?query=SELECT+name,type+FROM+system.columns+WHERE+table='n8n_execution_metrics'+FORMAT+TSVWithNames"
```

Expected: columns including `workflow_id`, `workflow_name`, `status`, `duration_ms`, `started_at`.

### V2 — Grafana dashboard renders

Open `http://localhost:3000` → Dashboards → **PolyTool - RIS Pipeline Health**.
Four panels must be present (they may show "No data" until the collector has run).

### V3 — Retrieval benchmark + baseline save

```bash
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --save-baseline
```

Expected:
- Exits 0
- Prints per-class metrics table (factual, conceptual, cross-document, paraphrase, negative-control)
- Prints aggregate Recall@k, MRR@k, P@5 for each mode (vector, lexical, hybrid, hybrid+rerank)
- File `artifacts/research/baseline_metrics.json` exists and contains valid JSON

### V4 — Cloud provider smoke test

With `RIS_ENABLE_CLOUD_PROVIDERS=1` set in your shell and `GEMINI_API_KEY` in `.env`:

```bash
echo "Polymarket uses a 2% fee model for market makers." | python -m polytool research-eval --provider gemini --enable-cloud
```

Expected: returns a scored result with `gate=ACCEPT` or `gate=REVIEW`, `eval_provider=gemini`,
`composite_score` between 1.0 and 5.0. No Python exception.

### V5 — System health check

```bash
python -m polytool research-health
```

Expected: exits without error. `overall_category` is GREEN or YELLOW. Provider routing fields present.

### V6 — n8n pipeline visual observation (manual)

In the n8n UI, manually trigger the `ris-unified-dev` pipeline.
- Code node output should show structured JSON with `docs_fetched`, `docs_accepted`, etc.
- Discord embed should appear with per-pipeline color-coded fields

### V7 — Daily digest (manual or wait)

Either wait for 09:00 UTC or manually trigger `ris-daily-digest` in the n8n UI.
Discord channel should receive an embed with the prior day's summary fields.

**Phase 2A is operationally validated when V1–V5 all pass.** V6–V7 are best-effort (logic is Codex-verified at commit time).

---

## Day-to-Day Usage

### Pipeline health and research ingestion

```bash
# System health snapshot
python -m polytool research-health

# Document and claim counts
python -m polytool research-stats summary

# Review queue (docs evaluated as REVIEW by cloud providers)
python -m polytool research-review list
python -m polytool research-review accept <doc_id>
python -m polytool research-review reject <doc_id>

# Pre-build idea check (GO / CAUTION / STOP)
python -m polytool research-precheck run --idea "description of planned work" --no-ledger

# Query the knowledge store
python -m polytool rag-query --question "relevant topic" --hybrid --knowledge-store default
```

### Manual research ingestion

```bash
# From a URL
python -m polytool research-acquire --url URL --source-family academic --no-eval

# From a file
python -m polytool research-ingest --file path/to/notes.md --source-type manual --no-eval

# Inline text (e.g., from a ChatGPT session)
python -m polytool research-ingest --text "finding text" --title "Finding Title" --source-type manual --no-eval
```

### Cloud provider evaluation

```bash
# Check provider status and routing config
python -m polytool research-eval list-providers

# Evaluate a document with the routed provider (Gemini primary → DeepSeek on REVIEW)
python -m polytool research-eval --file paper.txt --enable-cloud

# Evaluate with a specific provider
python -m polytool research-eval --file paper.txt --provider gemini --enable-cloud

# Compare two providers side-by-side
python -m polytool research-eval compare --provider-a gemini --provider-b deepseek --file paper.txt --enable-cloud
```

The routing mode uses `RIS_EVAL_PROVIDER` env var for n8n/scheduler automation.
Budget caps are in `config/ris_eval_config.json`; daily call counts are in `artifacts/research/budget_tracker.json`.

### Retrieval benchmark

```bash
# Run benchmark without saving baseline (dry run)
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl

# Run benchmark and freeze the baseline (first time, or after a knowledge store change)
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --save-baseline

# Save to a custom path
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --save-baseline /path/to/snapshot.json
```

Baseline artifact: `artifacts/research/baseline_metrics.json`.
Compare `corpus_hash` between runs to verify the query set has not changed.

---

## Monitoring Surfaces

### n8n UI (`http://localhost:5678`)

- **Execution history**: view per-workflow run status and Code node output
- **Structured output**: each Code node emits JSON with `docs_fetched`, `docs_accepted`, `docs_rejected`, `docs_review`, `new_claims`, `duration_seconds`, `errors`
- **Status indicators**: ✅ on success, ❌ on error — visible in the workflow canvas

### Grafana (`http://localhost:3000`)

Dashboard: **PolyTool - RIS Pipeline Health** (4 panels)

| Panel | What it shows |
|---|---|
| Execution Success Rate | Hourly success % across all RIS workflows |
| Avg Execution Duration | Average run time for successful executions |
| Failure Count by Workflow | Failure frequency by pipeline (bar chart) |
| Latest Run Status per Workflow | Last status per pipeline with color mapping |

The stale-pipeline alert (`ris-stale-pipeline-alert`) fires when any periodic workflow goes
more than 6 hours without a successful execution. Alert fires per-workflow so you can see
exactly which pipeline is stale.

### Discord

- Per-pipeline embeds fire after each ingestion run (color-coded by result)
- Daily digest at 09:00 UTC with previous day's summary
- Stale-pipeline alerts fire from Grafana when threshold is breached

---

## Key Files

| File | Role |
|---|---|
| `config/ris_eval_config.json` | Gate weights, floors, routing defaults, budget caps |
| `artifacts/research/budget_tracker.json` | Daily provider call counts (runtime artifact) |
| `artifacts/research/baseline_metrics.json` | Frozen retrieval benchmark baseline |
| `docs/eval/ris_retrieval_benchmark.jsonl` | 31-query golden set |
| `infra/n8n/workflows/ris-n8n-metrics-collector.json` | Hourly metrics collector (ships inactive) |
| `infra/grafana/dashboards/ris-pipeline-health.json` | Grafana RIS dashboard (auto-provisioned) |
| `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml` | Stale alert rule (provisioned on Grafana restart) |

---

## Deferred / Not in Phase 2A

| Item | Deferred to |
|---|---|
| OpenRouter, Groq, Ollama variants | Phase 2B — needed for friends without Google accounts |
| WP6 manual friend contribution | Phase 2B — starts only after Phase 2A e2e validation passes and a friend agrees |
| Non-zero exit on `--save-baseline` failure | Low-priority hardening; currently logs warning and exits 0 |

**Pre-existing test failures (unrelated to Phase 2A):**
3 failures in `test_ris_claim_extraction.py` — actor name mismatch from an earlier WP. These do not affect Phase 2A functionality.

---

## Troubleshooting

**`rag-eval` exits with import error:** Verify `pip install -e ".[rag]"` (or equivalent) is done.

**Metrics collector shows no data in Grafana:** Confirm `N8N_API_KEY` is in `.env` and the n8n container was restarted after adding it. Check that the workflow is toggled Active in the n8n UI.

**Cloud provider returns "guard not set" error:** Set `RIS_ENABLE_CLOUD_PROVIDERS=1` in your shell before running `research-eval`.

**Stale alert rule not visible in Grafana:** Run `docker compose restart grafana` so the provisioning file is picked up.

**n8n workflows not visible:** Run `python infra/n8n/import_workflows.py --no-activate` to re-import.

---

## Related Docs

| Doc | Purpose |
|---|---|
| [RIS Operator Guide](RIS_OPERATOR_GUIDE.md) | Full pre-Phase 2A operator guide: research loop, pipeline health, n8n pilot |
| [RIS + n8n Operator SOP](RIS_N8N_OPERATOR_SOP.md) | Quick-reference cheat sheet: startup, import, health, ingest, monitoring |
| [RIS Discord Alerts](RIS_DISCORD_ALERTS.md) | Discord alert format reference, severity meaning, verification procedure |
| [Local RAG Workflow](LOCAL_RAG_WORKFLOW.md) | RAG index, query, eval, scoping, retrieval modes |
| [RIS Phase 2A Acceptance Pass](../dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md) | Full 11-step acceptance procedure with exact expected output |
| [RIS Operational Readiness Phase 2A](../features/ris_operational_readiness_phase2a.md) | Feature completion summary for WP1–WP5 |
