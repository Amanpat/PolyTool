---
title: Ris Operational Readiness Phase2A
type: reference
status: implementation-complete; e2e-validation-pending
feature: RIS Operational Readiness — Phase 2A
date: 2026-04-23
track: Research Intelligence System
authoritative-roadmap: docs/obsidian-vault/Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md
source_zone: repo
mirror_of: docs/features/ris_operational_readiness_phase2a.md
last_synced: '2026-05-25T22:14:18Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS Operational Readiness — Phase 2A

## Summary

Phase 2A brings the Research Intelligence System from "all evaluation is auto-accepted"
(ManualProvider hardcodes 3 everywhere) to a functional autonomous ingestion loop on the
operator machine: cloud LLM evaluation with a two-provider cascade, budget enforcement,
n8n workflow visual improvements, a ClickHouse + Grafana monitoring layer, and an expanded
retrieval benchmark with Precision@5.

**Implementation complete:** 2026-04-23
**End-to-end validation status:** Pending operator run (see acceptance dev log)

---

## What Ships in Phase 2A

### WP1: Foundation Fixes

- Scoring weights corrected: novelty/actionability 0.25→0.20, credibility 0.20→0.30
  (per `Decision - RIS Evaluation Scoring Policy`)
- Per-dimension floor of 2 on novelty and actionability
- `provider_event` → `provider_events` (list) in evaluator contract
- R0 foundational seed: 11 `book_foundational` docs ingested (`research-seed`)
- Knowledge store confirmed at 59 total docs, 7 `external_knowledge` docs

### WP2: Cloud LLM Providers (Core)

- `OpenAICompatibleProvider` base class in `packages/research/evaluation/providers.py`
- `GeminiFlashProvider` — Google Generative AI SDK, 1,500 req/day free tier, `gemini-2.5-flash`
- `DeepSeekV3Provider` — subclass of base, `deepseek-chat` model
- Multi-provider routing: Gemini primary → DeepSeek escalation on REVIEW → fail-closed REJECT
- Budget enforcement: `artifacts/research/budget_tracker.json`, caps from `config/ris_eval_config.json`
- CLI: `--provider`, `--compare`, `list-providers` (`RIS_EVAL_PROVIDER` for n8n/scheduler)

**Deferred to Phase 2B:** OpenRouterProvider, GroqProvider, OllamaCloudProvider, OllamaLocalProvider
(needed for Phase 2B friends without Google accounts; CLI marks them "not yet implemented")

### WP3: n8n Workflow Visual Improvements

- Structured output parsing: Code nodes emit JSON with `docs_fetched`, `docs_accepted`,
  `docs_rejected`, `docs_review`, `new_claims`, `duration_seconds`, `errors`
- Visual success/failure indicators: `✅ Pipeline: N docs ingested` / `❌ Pipeline: error`
- Health monitor rich summary: `overallCategory`, `pipelineStatuses` array, `knowledgeStore`,
  `reviewQueue`, `providerRouting`, `operatorSummary`
- Discord embeds with per-pipeline color-coded fields and doc counts
- Daily digest at 09:00 UTC — WP3-C structured embed sent to Discord

### WP4: Monitoring Infrastructure

- ClickHouse table: `polytool.n8n_execution_metrics` (ReplacingMergeTree, 90-day TTL)
  — `infra/clickhouse/initdb/28_n8n_execution_metrics.sql`
- n8n metrics collector workflow — `infra/n8n/workflows/ris-n8n-metrics-collector.json`
  (ships `active: false`; operator activates after `N8N_API_KEY` provisioned)
- Grafana dashboard — `infra/grafana/dashboards/ris-pipeline-health.json`
  — 4 panels: success rate, duration, failure frequency, last-run table
  — auto-provisioned at `docker compose up`
- Stale pipeline alert — `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml`
  — fires when a periodic workflow goes >6h without success; explicit IN filter for 2 workflows only

### WP5: Retrieval Benchmark

- Golden query set expanded from 9 → 31 queries across 5 classes:
  `docs/eval/ris_retrieval_benchmark.jsonl`
  — factual×6, conceptual×7, cross-document×6, paraphrase×6, negative-control×6
- Precision@5 metric with correct fetch-depth (`max(k, 5)` even when operator sets k < 5)
- Per-class segmented reporting: `per_class_modes` in `EvalReport`, CLI table per class
- `--save-baseline` flag: writes `artifacts/research/baseline_metrics.json` (explicit opt-in)
- Schema: `asdict(EvalReport)` + `frozen_at` timestamp; `corpus_hash` for reproducibility checks

---

## Key Files

| Path | Role |
|---|---|
| `packages/research/evaluation/providers.py` | Gemini, DeepSeek providers + OpenAICompatibleProvider base |
| `packages/research/evaluation/evaluator.py` | Fail-closed DocumentEvaluator with routed provider chain |
| `config/ris_eval_config.json` | Gate weights, floors, thresholds, routing defaults, budget caps |
| `artifacts/research/budget_tracker.json` | Daily provider request tracking (runtime artifact) |
| `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` | ClickHouse DDL |
| `infra/n8n/workflows/ris-n8n-metrics-collector.json` | Hourly metrics collector (ships inactive) |
| `infra/grafana/dashboards/ris-pipeline-health.json` | Grafana RIS dashboard |
| `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml` | Stale alert rule |
| `packages/polymarket/rag/eval.py` | Retrieval evaluator — P@5, save_baseline, per-class metrics |
| `tools/cli/rag_eval.py` | CLI — `--suite`, `--k`, `--save-baseline` |
| `docs/eval/ris_retrieval_benchmark.jsonl` | 31-query golden set |

---

## Test Coverage

| Scope | Test file | Count |
|---|---|---|
| Retrieval eval (WP5-A/B/C/D) | `tests/test_rag_eval.py` | 67 (all pass) |
| Cloud provider routing (WP2-H) | `tests/test_ris_phase2_cloud_provider_routing.py` | 8 |
| Provider CLI truth sync (WP2-J) | included in research CLI tests | 21 new tests |
| Full suite (regression check) | `tests/` | 4423 pass, 3 pre-existing failures in `test_ris_claim_extraction.py` |

---

## Deferred Items (Non-Blocking)

- **WP2-D/E/F/G** — OpenRouter, Groq, Ollama variants. Phase 2B providers for friends.
- **Metrics collector activation** — manual step; requires `N8N_API_KEY` first.
- **Baseline save first run** — `--save-baseline` is opt-in; operator must trigger once.
- **Non-zero exit on `--save-baseline` failure** — currently logs warning and exits 0.
  Low-priority hardening for automation workflows.

---

## Outstanding Operator Steps

1. Commit WP5 dirty worktree changes (`eval.py`, `rag_eval.py`, `test_rag_eval.py`,
   `ris_retrieval_benchmark.jsonl`)
2. Run end-to-end validation (11 steps documented in
   `docs/dev_logs/2026-04-23_ris_phase2a_acceptance_pass.md`)
3. Provision `N8N_API_KEY` and activate the metrics collector workflow
4. Run `rag-eval --save-baseline` to freeze the retrieval baseline

---

## Phase 2B Trigger

Phase 2B (WP6 — manual friend contribution via GitHub) starts only when:
1. Phase 2A e2e validation passes
2. At least one friend explicitly agrees to contribute

Do not design or implement WP6 before both conditions are met.
