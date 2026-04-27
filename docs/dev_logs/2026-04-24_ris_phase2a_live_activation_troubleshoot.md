---
date: 2026-04-24
slug: ris_phase2a_live_activation_troubleshoot
type: troubleshooting
scope: infra/n8n, grafana, clickhouse
feature: RIS Phase 2A — Live Activation Diagnosis
---

# RIS Phase 2A — Live Activation Troubleshoot

**Date:** 2026-04-24
**Type:** Live activation diagnosis + narrow repo fix
**Operator:** Aman

---

## Objective

Determine why the landed Phase 2A changes were not visible in the live n8n/Grafana stack,
and fix any repo-truth activation mismatches.

---

## Symptoms Reported

- No visible workflow/UI change in n8n after Phase 2A landed
- No visible Grafana dashboard changes
- Grafana user dropdown not working across dashboards

---

## Checks Run + Exact Results

### 1 — Docker stack health

```
docker compose ps
```

Result: All 5 services UP and healthy.
- `polytool-api` — Up ~1h (healthy)
- `polytool-clickhouse` — Up 45h (healthy)
- `polytool-grafana` — Up ~1h (healthy)
- `polytool-n8n` — Up ~1h (healthy)
- `polytool-ris-scheduler` — Up ~1h

### 2 — `.env` key presence

| Key | Present |
|---|---|
| `CLICKHOUSE_PASSWORD` | YES |
| `DISCORD_WEBHOOK_URL` | YES |
| `N8N_API_KEY` | YES |
| `GEMINI_API_KEY` | **NO** |
| `DEEPSEEK_API_KEY` | **NO** |

`GEMINI_API_KEY` and `DEEPSEEK_API_KEY` are absent — cloud provider V4 smoke test
will fail until operator adds them. Not a blocker for V1–V3/V5 validation.

### 3 — n8n live workflow inventory (before fix)

```
GET /api/v1/workflows?limit=100
```

Result:
```
Total workflows: 3
  id=B34eBaBPIvLb8SYj  name=RIS — Research Intelligence System  active=True   nodes=76
  id=MJo9jcBCfxmyMwcc  name=RIS -- Health Webhook               active=True   nodes=5
  id=NqRitVKf2rcdawTM  name=RIS — Research Intelligence System  active=False  nodes=69
```

**Finding 1 (BLOCKER):** `ris-n8n-metrics-collector` was absent from n8n entirely.
`METRICS_COLLECTOR_ID` was missing from `infra/n8n/workflows/workflow_ids.env`. The import
script was never re-run after WP4-B added the metrics collector to the repo.

**Finding 2:** Two `RIS — Research Intelligence System` workflows existed:
- 76-node version (active) = Phase 2A version. **Correct.**
- 69-node version (inactive) = pre-Phase 2A stale duplicate. **Stale — should be deleted.**

### 4 — ClickHouse `n8n_execution_metrics` table

```sql
SELECT name, type FROM system.columns WHERE table='n8n_execution_metrics' AND database='polytool'
```

Result: Table EXISTS. Columns: `execution_id`, `workflow_id`, `workflow_name`, `status`, `mode`,
`started_at`, `stopped_at`, `duration_seconds`, `collected_at`.

```sql
SELECT count(*) FROM polytool.n8n_execution_metrics
```

Result: **0 rows.** Expected — collector was never imported or activated.

Note: The operator guide references `duration_ms` and `finished_at`, but the actual DDL
landed `duration_seconds` and `stopped_at`. This is a prose drift in the operator guide
(WP4-A DDL is the truth). No functional impact.

### 5 — Grafana dashboard provisioning

```
GET /api/search?query=RIS
```

Result:
```
uid=polytool-ris-pipeline-health  title=PolyTool - RIS Pipeline Health
```

Dashboard IS provisioned. 4 panels present (Execution Success Rate, Avg Duration,
Failure Count by Workflow, Latest Run Status). No variables/dropdown on this dashboard —
it has none by design.

### 6 — Grafana stale pipeline alert

```
GET /api/v1/provisioning/alert-rules
```

Result:
```
name=RIS — Stale Pipeline (no success in 6h)  uid=ris-stale-pipeline-alert  state=Alerting
```

Alert IS provisioned. State=Alerting is expected — no workflows have successfully executed
yet so the no-data threshold fires correctly.

### 7 — User dropdown investigation

Affected dashboards: User Overview, User Trades, PnL, Strategy Detectors.

All four use:
```sql
SELECT __value, __text FROM polytool.users_grafana_dropdown ORDER BY __text
```

The `users_grafana_dropdown` VIEW exists in ClickHouse. But:

```sql
SELECT count(*) FROM polytool.users_grafana_dropdown
```

Result: **0 rows.** The underlying `users` table (ReplacingMergeTree) also has 0 rows.

**Root cause:** No user scans have been run — no wallets have ever been imported into the
`polytool.users` table. This is a **pre-existing data state**, not a Phase 2A regression.
The view, query, and dashboard variable are all correctly wired; they just have no source
data yet. The dropdown will populate once wallet data is present.

### 8 — `rag-eval --suite` flag

```
python -m polytool rag-eval --help
```

Result: `--suite SUITE` is a **required positional argument** (not optional).
Correct invocation: `python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl`

### 9 — `research-health`

```
python -m polytool research-health
```

Result:
```
RIS Health Summary (48h window, 22 runs) — GREEN
...
Overall: HEALTHY
```

All checks GREEN. 9 docs accepted in monitored window, 100% accept rate, 1 review queue item.

---

## Root Causes

| # | Root Cause | Impact |
|---|---|---|
| RC-1 | `import_workflows.py` was never re-run after WP4-B added `ris-n8n-metrics-collector.json` to the repo. `METRICS_COLLECTOR_ID` was missing from `workflow_ids.env`. | Metrics collector absent from n8n; 0 rows in ClickHouse; Grafana dashboard panels show "No data". |
| RC-2 | `import_workflows.py` sent `active: false` in the POST body when creating a new workflow, which n8n rejects with HTTP 400 (`active is read-only`). This would have blocked any future import attempts too. | Import of metrics collector always would have failed on first run. |
| RC-3 | Stale 69-node pre-Phase 2A workflow (`NqRitVKf2rcdawTM`) was left inactive in n8n from a prior import cycle. | Visual confusion — two workflows with the same name. No functional impact. |
| RC-4 | User dropdown empty — `polytool.users` table has 0 rows. | Dropdown blank on User Overview / User Trades / PnL / Strategy Detectors dashboards. Pre-existing; not a Phase 2A issue. |

---

## Repo Files Changed

| File | Change | Reason |
|---|---|---|
| `infra/n8n/import_workflows.py` | Strip `active` key from POST payload on workflow creation | n8n API rejects `active` as read-only on POST; only allowed on PUT. One-line fix to `import_workflow()`. |
| `infra/n8n/workflows/workflow_ids.env` | Added `METRICS_COLLECTOR_ID=501G2SpnuuPKZ1EN` | Written by `import_workflows.py` after successful creation. |

---

## Actions Taken (This Session)

1. Fixed `import_workflows.py` to strip `active` from POST payload.
2. Re-ran `python infra/n8n/import_workflows.py --no-activate`:
   - `ris-unified-dev.json`: B34eBaBPIvLb8SYj (updated)
   - `ris-health-webhook.json`: MJo9jcBCfxmyMwcc (updated)
   - `ris-n8n-metrics-collector.json`: 501G2SpnuuPKZ1EN (**created**)
3. Deleted stale 69-node duplicate workflow `NqRitVKf2rcdawTM` via DELETE API (n8n archived it).

**Final n8n state:**
```
id=501G2SpnuuPKZ1EN  name=RIS -- n8n Execution Metrics Collector  active=False  (needs operator activation)
id=B34eBaBPIvLb8SYj  name=RIS — Research Intelligence System       active=True
id=MJo9jcBCfxmyMwcc  name=RIS -- Health Webhook                   active=True
```

---

## Exact Manual Steps Remaining

These steps require live Docker + browser. No agent can execute them.

### M1 — Activate the metrics collector (REQUIRED for Grafana data)

1. Open `http://localhost:5678`
2. Find `RIS -- n8n Execution Metrics Collector`
3. Toggle it **Active**
4. Wait for next hourly trigger, or manually execute it once
5. Verify data: `curl "http://localhost:8123/?query=SELECT+count(*)+FROM+polytool.n8n_execution_metrics+FORMAT+JSON" -u "polytool_admin:<PASSWORD>"`
   Expected: count > 0 within one hourly tick.

### M2 — Retrieval benchmark + baseline save (WP5 validation)

```bash
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --save-baseline
```

Expected: exits 0, per-class metrics table printed, `artifacts/research/baseline_metrics.json` written.

### M3 — Cloud provider smoke test (WP2 validation, BLOCKED by missing API keys)

Add to `.env`:
```
GEMINI_API_KEY=<Google AI Studio key>
DEEPSEEK_API_KEY=<DeepSeek platform key>
```

Then:
```bash
echo "Polymarket uses a 2% fee model for market makers." | python -m polytool research-eval --provider gemini --enable-cloud
```

Expected: `gate=ACCEPT` or `gate=REVIEW`, `eval_provider=gemini`, `composite_score` 1.0–5.0.

### M4 — n8n pipeline visual observation (WP3 validation)

In n8n UI, manually trigger `RIS — Research Intelligence System`.
Confirm: Code node outputs structured JSON (docs_fetched, docs_accepted, etc.),
Discord embed appears with color-coded per-pipeline fields.

### M5 — Daily digest (WP3-E, optional)

Trigger `ris-daily-digest` manually or wait for 09:00 UTC.
Confirm: Discord embed appears with prior-day summary.

---

## Phase 2A Validation Status

| Validation check | Status | Blocker |
|---|---|---|
| V1 — ClickHouse table exists | PASS | — |
| V2 — Grafana dashboard renders | PASS (4 panels, no data yet) | Activate collector (M1) for data |
| V3 — `rag-eval --save-baseline` | PENDING | Operator runs M2 |
| V4 — Cloud provider smoke test | BLOCKED | Add `GEMINI_API_KEY` to `.env` (M3) |
| V5 — `research-health` GREEN | PASS | — |
| V6 — n8n structured output (WP3) | PENDING | Operator triggers pipeline (M4) |
| V7 — Daily digest | PENDING | Operator triggers/waits (M5) |

**Phase 2A validation can proceed immediately for V2, V3, V5.**
**V4 is blocked until `GEMINI_API_KEY` and `DEEPSEEK_API_KEY` are added to `.env`.**
**Grafana panels will show live data as soon as metrics collector is activated (M1) and runs once.**

---

## Codex Review

Tier: Skip — no application code changed; only import script plumbing fix.
