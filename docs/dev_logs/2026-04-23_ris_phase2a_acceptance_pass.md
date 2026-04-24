---
date: 2026-04-23
slug: ris_phase2a_acceptance_pass
type: closeout
scope: docs-only
feature: RIS Operational Readiness — Phase 2A
---

# RIS Phase 2A — Acceptance Pass

**Date:** 2026-04-23
**Type:** Acceptance / closeout — documentation-only, no code changes
**Operator:** Aman

---

## Objective

Confirm that repo truth clearly reflects what Phase 2A delivered across WP1–WP5,
call out deferred items explicitly, list remaining manual/operator steps, and define
the exact next end-to-end validation run.

---

## WP1–WP5 Acceptance Table

### WP1: Foundation Fixes — COMPLETE

| Sub-packet | Deliverable | Dev log | Status |
|---|---|---|---|
| WP1-A | Scoring weights: novelty/actionability 0.25→0.20, credibility 0.20→0.30 | `2026-04-22_ris_wp1a_scoring_weights.md` | COMPLETE |
| WP1-B | Per-dim floor (2 on novelty + actionability) + prompt drift fix | `2026-04-22_ris_wp1b_dimension_floors.md`, `_prompt_floor_drift_fix.md`, `_prompt_drift_codex_verification.md` | COMPLETE |
| WP1-C | `provider_event` → `provider_events` (list) in evaluator contract | `2026-04-22_ris_wp1c_provider_events_contract.md` | COMPLETE |
| WP1-D | R0 foundational seed — 11 `book_foundational` docs ingested | `2026-04-22_ris_wp1d_foundational_seed.md` | COMPLETE — post-seed: 59 total docs, 11 book_foundational |
| WP1-E | 5 open-source docs (`external_knowledge` family) | Pre-existed from earlier session | COMPLETE — 7 external_knowledge docs confirmed at WP1-D |

**Acceptance evidence:** `research-stats` at WP1-D time: 59 total docs, `book_foundational: 11`,
`external_knowledge: 7`. All existing tests passed.

---

### WP2: Cloud LLM Providers — CORE COMPLETE; WP2-D/E/F/G DEFERRED TO PHASE 2B

| Sub-packet | Deliverable | Dev log | Status |
|---|---|---|---|
| WP2-A | `OpenAICompatibleProvider` base class | `2026-04-22_ris_wp2a_openai_compatible_base.md` | COMPLETE |
| WP2-B | `GeminiFlashProvider` | `2026-04-22_ris_wp2b_gemini_provider.md`, `2026-04-23_ris_wp2b_codex_verification.md` | COMPLETE |
| WP2-C | `DeepSeekV3Provider` | `2026-04-22_ris_wp2c_deepseek_provider.md` | COMPLETE |
| WP2-D | `OpenRouterProvider` | Not implemented | **DEFERRED — Phase 2B** |
| WP2-E | `GroqProvider` | Not implemented | **DEFERRED — Phase 2B** |
| WP2-F | `OllamaCloudProvider` | Not implemented | **DEFERRED — Phase 2B** |
| WP2-G | `OllamaLocalProvider` | Not implemented | **DEFERRED — Phase 2B** |
| WP2-H | Multi-provider routing (Gemini→DeepSeek escalation on REVIEW) + fix pass | `2026-04-22_ris_wp2h_multi_provider_routing.md`, `2026-04-23_ris_wp2h_codex_verification.md`, `_routing_fix_pass.md` | COMPLETE |
| WP2-I | Budget enforcement (daily call caps, `budget_tracker.json`) + public-path fix | `2026-04-23_ris_wp2i_budget_enforcement.md`, verification + path-fix logs | COMPLETE |
| WP2-J | CLI `--provider` / `--compare` / `list-providers` truth sync | `2026-04-23_ris_wp2j_cli_truth_sync.md` | COMPLETE — 21 tests; 2332 total passing at that point |

**Deferred scope note (non-blocking):** WP2-D/E/F/G are providers for Phase 2B friends without
Google accounts. The WP2-J CLI correctly marks them "not yet implemented" with an early guard.
Core operator routing (Gemini primary → DeepSeek escalation → fail-closed) is fully operational.
WP2-D/E/F/G do not block Phase 2A operation or the end-to-end validation run.

---

### WP3: n8n Workflow Visual Improvements — COMPLETE

| Sub-packet | Deliverable | Dev log | Status |
|---|---|---|---|
| WP3-A | Structured output parsing (Code node parses stdout → JSON) + fix pass | `2026-04-22_ris_wp3a_structured_output.md`, fix + verification logs 2026-04-23 | COMPLETE |
| WP3-B | Visual success/failure indicators (✅ / ❌ per pipeline) | `2026-04-23_ris_wp3b_status_indicators.md`, `_codex_verification.md` | COMPLETE |
| WP3-C | Health monitor rich summary (overallCategory, pipelineStatuses, knowledgeStore, reviewQueue, providerRouting, operatorSummary) | `2026-04-23_ris_wp3c_health_monitor_summary.md`, `_codex_verification.md` | COMPLETE — 76 nodes, 56 connections; JSON valid |
| WP3-D | Discord embeds with per-pipeline fields (color-coded, doc counts) | `2026-04-23_ris_wp3d_discord_embeds.md` | COMPLETE — commit `2eaefd8` |
| WP3-E | Daily digest at 09:00 UTC with WP3-C structured embed | `2026-04-23_ris_wp3e_daily_summary.md` | COMPLETE — commit `d9e9f8b` |

---

### WP4: Monitoring Infrastructure — COMPLETE

| Sub-packet | Deliverable | Artifact | Dev log | Status |
|---|---|---|---|---|
| WP4-A | ClickHouse DDL — `polytool.n8n_execution_metrics` ReplacingMergeTree, 90-day TTL | `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` | `2026-04-23_ris_wp4a_clickhouse_ddl.md` | COMPLETE |
| WP4-B | n8n metrics collector workflow + activation plumbing | `infra/n8n/workflows/ris-n8n-metrics-collector.json` | `2026-04-23_ris_wp4b_metrics_collector.md`, `_activation_plumbing.md` | COMPLETE — ships `active: false`; operator activates after N8N_API_KEY provisioned |
| WP4-C | Grafana RIS dashboard (4 panels: success rate, duration, failure freq, last-run table) | `infra/grafana/dashboards/ris-pipeline-health.json` | `2026-04-23_ris_wp4c_grafana_dashboard.md` | COMPLETE — auto-provisioned at container start |
| WP4-D | Stale pipeline alert (>6h without success, `noDataState: Alerting`) + scope fix | `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml` | `2026-04-23_ris_wp4d_stale_pipeline_alert.md`, `_scope_fix.md`, `_scope_fix_codex_verification.md` | COMPLETE — explicit IN filter for 2 periodic workflows only |

**Truth-sync cross-check:** `2026-04-23_ris_wp4_monitoring_truth_sync.md` verified all surfaces
consistent — table name, column names, datasource UID, workflow registration, env wiring,
ReplacingMergeTree/FINAL pattern. No drift found.

---

### WP5: Retrieval Benchmark — COMPLETE

| Sub-packet | Deliverable | Dev log | Status |
|---|---|---|---|
| WP5-A | 31-query golden set across 5 classes in `docs/eval/ris_retrieval_benchmark.jsonl` | `2026-04-23_ris_wp5a_queryset_expansion.md`, `_codex_verification.md` | COMPLETE — 31 queries: factual×6, conceptual×7, cross-document×6, paraphrase×6, negative-control×6 |
| WP5-B | Precision@5 metric; fetch-depth fix (`max(k, 5)` for P@5 window) | `2026-04-23_ris_wp5b_precision_at_5.md`, `_fix_pass.md`, `_fix_codex_verification.md` | COMPLETE — P@5 in all report surfaces |
| WP5-C | Per-class segmented reporting (`per_class_modes` in report + CLI table) | (landed in same WP5-B surface; WP5-C was already partially present) | COMPLETE — `QueryClassSegmentationTests` (11 methods) all pass |
| WP5-D | `--save-baseline` flag; `save_baseline()` function; `artifacts/research/baseline_metrics.json` | `2026-04-23_ris_wp5d_baseline_save.md`, `_codex_verification.md` | COMPLETE — explicit opt-in; schema = `asdict(EvalReport)` + `frozen_at` |

**WP5 code files modified (in worktree, not yet committed as of this pass):**
- `packages/polymarket/rag/eval.py` — P@5 metric + `save_baseline()`
- `tools/cli/rag_eval.py` — `--save-baseline` flag
- `tests/test_rag_eval.py` — 67 tests total (57 pre-WP5 + 10 WP5-D); all pass
- `docs/eval/ris_retrieval_benchmark.jsonl` — 31 queries (was 9)

---

## Deferred / Non-Blocking Items

| Item | Deferred to | Impact |
|---|---|---|
| WP2-D OpenRouterProvider | Phase 2B | Phase 2B friends without Google accounts. Not needed for operator use. |
| WP2-E GroqProvider | Phase 2B | Same. |
| WP2-F OllamaCloudProvider | Phase 2B | Same. |
| WP2-G OllamaLocalProvider | Phase 2B | Same. |
| WP4-B metrics collector activation | Operator manual step | Ships `active: false`; needs `N8N_API_KEY` provisioned first. |
| WP5-D baseline artifact write | Operator manual step | `--save-baseline` is opt-in; first write must be triggered by operator. |
| Non-zero exit on `--save-baseline` failure | Follow-up | WP5-D Codex noted: save failure logs warning but exits 0. Low priority; affects automation guarantees only if baseline write fails. |
| Pre-existing test failures in `test_ris_claim_extraction.py` | Earlier WP | 3 failures: `test_each_claim_has_required_fields`, `test_notes_json_has_extraction_context`, `test_class_exists_and_has_expected_interface` — all actor name mismatch (`heuristic_v1` vs `heuristic_v2_nofrontmatter`). Unrelated to Phase 2A. |
| Phase 2A closeout dev log (earlier) mentions stale path `packages/research/rag/` | Non-blocking | WP5 closeout verification noted: live harness path is `packages/polymarket/rag/eval.py`, not `packages/research/rag/`. Prose-only stale ref; no code impact. |
| WP5 code changes uncommitted | Operator git action | WP5-A/B/C/D changes to `eval.py`, `rag_eval.py`, `test_rag_eval.py`, `ris_retrieval_benchmark.jsonl` are in dirty worktree. Commit these before or during the validation run. |

---

## Files Changed in This Pass

| File | Change | Reason |
|---|---|---|
| `docs/features/ris_operational_readiness_phase2a.md` | Created | Completion protocol — required DoD item for Feature 2 |
| `docs/INDEX.md` | Added feature doc row | Completion protocol — DoD item |
| `docs/CURRENT_DEVELOPMENT.md` | Tick WP5 DoD checkboxes; update current step; move Feature 2 to Recently Completed | All WP1–WP5 implementation complete; next operator action = validation run |
| `docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md` | Created (this file) | Mandatory dev log per repo policy |

---

## Commands Run + Exact Results

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly. `rag-eval` and `research-benchmark` and `research-eval` all visible.

```
python -m pytest tests/ -q --tb=no
```
**Result:** 3 failed, 4423 passed, 3 deselected, 25 warnings in 111.56s
- All 3 failures are pre-existing in `test_ris_claim_extraction.py` (actor name mismatch, unrelated to Phase 2A)
- No new failures introduced by Phase 2A work

```
python -c "import json; lines=[json.loads(l) for l in open('docs/eval/ris_retrieval_benchmark.jsonl')]; classes={}; [classes.__setitem__(l.get('query_class','?'), classes.get(l.get('query_class','?'),0)+1) for l in lines]; print('Total:', len(lines)); [print(f'  {k}: {v}') for k,v in sorted(classes.items())]"
```
**Result:**
```
Total: 31
  conceptual: 7
  cross-document: 6
  factual: 6
  negative-control: 6
  paraphrase: 6
```

Repo diff inspection: only `docs/CURRENT_DEVELOPMENT.md`, `docs/INDEX.md`,
`docs/features/ris_operational_readiness_phase2a.md`, and this dev log changed in this pass.

---

## Exact Next End-to-End Validation Run

This is the acceptance test that Phase 2A is operationally correct end-to-end.
All steps below are operator-manual. No agent can execute them (require live Docker,
API keys, and Discord observation).

### Prerequisites

- Docker Desktop running
- `.env` file has `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, `DISCORD_WEBHOOK_URL`,
  `N8N_API_KEY` (after provisioning in n8n), `CLICKHOUSE_PASSWORD`
- WP5 dirty worktree changes committed:
  ```bash
  git add packages/polymarket/rag/eval.py tools/cli/rag_eval.py tests/test_rag_eval.py docs/eval/ris_retrieval_benchmark.jsonl
  git commit -m "feat(ris): WP5 retrieval benchmark — 31 queries, P@5, per-class reporting, baseline save"
  ```

### Step 1 — Infra up

```bash
docker compose up -d
docker compose ps
```
**Pass:** All services show `Up` / `healthy`. ClickHouse, n8n, Grafana are running.
**Artifact to paste:** Output of `docker compose ps`.

### Step 2 — Import n8n workflows

```bash
python infra/n8n/import_workflows.py
```
**Pass:** Script exits 0, prints workflow IDs for all imported workflows including
`ris-n8n-metrics-collector` and the daily digest workflow.

### Step 3 — Verify ClickHouse DDL (WP4-A)

```bash
curl "http://localhost:8123/?query=SELECT+name,type+FROM+system.columns+WHERE+table='n8n_execution_metrics'+FORMAT+TSVWithNames"
```
**Pass:** Returns columns including `workflow_id`, `workflow_name`, `status`, `duration_ms`,
`started_at`, `finished_at`, `environment`.
**Artifact to paste:** Column list.

### Step 4 — Verify Grafana RIS dashboard (WP4-C)

Open `http://localhost:3000`. Navigate to Dashboards → "RIS Pipeline Health".
**Pass:** 4 panels render without "No data" errors (they may show empty data if no
metrics have been collected yet; the panels themselves must be present and configured).
**Artifact to paste:** Screenshot of the dashboard.

### Step 5 — Verify stale alert rule exists (WP4-D)

Open `http://localhost:3000/alerting/list`.
**Pass:** "RIS Stale Pipeline" alert rule is visible. State may be "No data" or "Alerting"
depending on whether workflows have run; the rule must exist.

### Step 6 — Activate metrics collector (WP4-B)

In n8n UI: activate the `ris-n8n-metrics-collector` workflow.
**Pass:** Workflow activates without error. On next hourly tick, it will write to ClickHouse.

### Step 7 — Retrieval benchmark with baseline save (WP5)

```bash
python -m polytool rag-eval --suite docs/eval/ris_retrieval_benchmark.jsonl --save-baseline
```
**Pass:**
- Exits 0
- Prints per-class metrics table (factual, conceptual, cross-document, paraphrase, negative-control)
- Prints aggregate metrics (Recall@k, MRR@k, P@5) for each mode (vector, lexical, hybrid, hybrid+rerank)
- File `artifacts/research/baseline_metrics.json` exists and is non-empty JSON
**Artifact to paste:** Full CLI output and `cat artifacts/research/baseline_metrics.json | python -m json.tool | head -40`.

### Step 8 — Cloud provider routing smoke test (WP2-H/I)

With `RIS_ENABLE_CLOUD_PROVIDERS=1` and `GEMINI_API_KEY` set in env:
```bash
echo "Polymarket uses a 2% fee model for market makers." | python -m polytool research-eval --provider gemini
```
Or submit a short text via the CLI. Any 2-3 sentence research summary is valid input.
**Pass:** Returns a scored result with `gate=ACCEPT` or `gate=REVIEW`, `eval_provider=gemini`,
`composite_score` between 1.0 and 5.0. No Python exception.
**Artifact to paste:** CLI output (redact API keys if present).

### Step 9 — System health check (WP1 scoring + WP2 routing reflected)

```bash
python -m polytool research-health
```
**Pass:** Returns without error. `overall_category` is GREEN or YELLOW (not RED unless
a pipeline has a real failure). Provider routing fields present in output.
**Artifact to paste:** Full output.

### Step 10 — n8n pipeline structured output observation (WP3-A/B/C/D)

In n8n UI, manually trigger the academic ingestion pipeline.
**Pass:**
- Code node output shows structured JSON (pipeline, docs_fetched, docs_accepted, etc.)
- Discord embed appears in the webhook channel with per-pipeline fields and color coding
- Health monitor node shows per-pipeline status table

### Step 11 — Daily digest check (WP3-E)

Either wait for 09:00 UTC or manually trigger the `ris-daily-digest` workflow.
**Pass:** Discord channel receives an embed with yesterday's summary fields.

---

### What "Pass" Means for Phase 2A

Phase 2A is operationally validated when Steps 1–9 all pass. Steps 10–11 require
live n8n observation but are not blocking for code correctness (their logic was
Codex-verified at commit time).

**Minimum paste-back to declare Phase 2A done:**
1. `docker compose ps` (all services up)
2. `rag-eval --save-baseline` full output
3. `artifacts/research/baseline_metrics.json` first 40 lines
4. `research-health` full output
5. Grafana dashboard screenshot

---

## Phase 2B Prerequisites (for operator reference)

Phase 2B (manual friend contribution via WP6) starts only when:
1. Phase 2A WP1–WP5 acceptance above is complete (e2e validation passed)
2. At least one friend has explicitly agreed to run the contribution script

Do not design or implement WP6 until both conditions are met.

---

**Codex review tier:** Skip — documentation-only pass, no application code changed.
