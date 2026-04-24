# RIS Phase 2A — Closeout Readiness Pass

**Date:** 2026-04-23
**Scope:** Documentation-only pass to confirm WP1–WP4 completion state and prepare WP5 entry handoff
**Code changes:** None
**Infra changes:** None

---

## Objective

Before entering WP5 (retrieval benchmark), confirm that repo truth accurately reflects
WP1–WP4 state and that `docs/CURRENT_DEVELOPMENT.md` no longer implies unfinished work
in those packets.

---

## WP1–WP4 Completion Summary

### WP1: Foundation Fixes — COMPLETE

All five sub-items landed 2026-04-22:

| Sub-packet | What | Dev log | Result |
|---|---|---|---|
| WP1-A | Scoring weights: novelty/actionability 0.25→0.20, credibility 0.20→0.30 | `2026-04-22_ris_wp1a_scoring_weights.md` | COMPLETE |
| WP1-B | Per-dim floor (2 on novelty + actionability) + prompt drift fix (Codex re-verify) | `2026-04-22_ris_wp1b_dimension_floors.md`, `_prompt_drift_codex_verification.md`, `_prompt_floor_drift_fix.md` | COMPLETE |
| WP1-C | `provider_event` → `provider_events` (list) | `2026-04-22_ris_wp1c_provider_events_contract.md` | COMPLETE |
| WP1-D | R0 foundational seed — 11 `book_foundational` docs ingested | `2026-04-22_ris_wp1d_foundational_seed.md` | COMPLETE — post-seed: 59 total docs, 11 book_foundational |
| WP1-E | 5 open-source docs (external_knowledge family) | Pre-existed from earlier session | COMPLETE — store had 7 external_knowledge docs at WP1-D time |

Acceptance check: `research-stats` showed 59 total docs, `book_foundational: 11`, `external_knowledge: 7`. All existing tests passed.

---

### WP2: Cloud LLM Providers — CORE COMPLETE; WP2-D/E/F/G DEFERRED

| Sub-packet | What | Dev log | Result |
|---|---|---|---|
| WP2-A | OpenAICompatibleProvider base class | `2026-04-22_ris_wp2a_openai_compatible_base.md` | COMPLETE |
| WP2-B | GeminiFlashProvider | `2026-04-22_ris_wp2b_gemini_provider.md`, `2026-04-23_ris_wp2b_codex_verification.md` | COMPLETE |
| WP2-C | DeepSeekV3Provider | `2026-04-22_ris_wp2c_deepseek_provider.md` | COMPLETE |
| WP2-D | OpenRouterProvider | Not implemented | DEFERRED — noted in WP2-H open questions |
| WP2-E | GroqProvider | Not implemented | DEFERRED — noted in WP2-H open questions |
| WP2-F | OllamaCloudProvider | Not implemented | DEFERRED |
| WP2-G | OllamaLocalProvider | Not implemented | DEFERRED |
| WP2-H | Multi-provider routing (Gemini→DeepSeek escalation on REVIEW) | `2026-04-22_ris_wp2h_multi_provider_routing.md`, `2026-04-23_ris_wp2h_codex_verification.md`, `_routing_fix_pass.md` | COMPLETE |
| WP2-I | Budget enforcement (daily call caps, `budget_tracker.json`) | `2026-04-23_ris_wp2i_budget_enforcement.md`, verification + public-path fix logs | COMPLETE |
| WP2-J | CLI `--provider` / `--compare` / `list-providers` truth sync | `2026-04-23_ris_wp2j_cli_truth_sync.md` | COMPLETE — 21 tests; 2332 total tests passing |

**Deferred scope note:** WP2-D/E/F/G (OpenRouter, Groq, Ollama variants) were scoped as Phase 2B provider options (friends without Google accounts). The WP2-J CLI correctly marks them "not yet implemented" with an early guard. Core operator routing (Gemini primary → DeepSeek escalation) is fully operational. Deferred items do not block Phase 2A WP5 or operator use.

---

### WP3: n8n Workflow Visual Improvements — COMPLETE

All five sub-items landed 2026-04-22/23:

| Sub-packet | What | Dev log | Result |
|---|---|---|---|
| WP3-A | Structured output parsing (Code node parses stdout → JSON) | `2026-04-22_ris_wp3a_structured_output.md`, fix logs 2026-04-23 | COMPLETE |
| WP3-B | Visual success/failure indicators (✅ / ❌ per pipeline) | `2026-04-23_ris_wp3b_status_indicators.md` | COMPLETE |
| WP3-C | Health monitor rich summary (overallCategory, pipelineStatuses array, knowledgeStore, reviewQueue, providerRouting, operatorSummary) | `2026-04-23_ris_wp3c_health_monitor_summary.md` | COMPLETE — 76 nodes, 56 connections; JSON valid |
| WP3-D | Discord embeds with per-pipeline fields (color-coded, doc counts per pipeline) | `2026-04-23_ris_wp3d_discord_embeds.md` | COMPLETE |
| WP3-E | Daily digest at 09:00 UTC with WP3-C structured embed | `2026-04-23_ris_wp3e_daily_summary.md` | COMPLETE — commit `d9e9f8b` |

---

### WP4: Monitoring Infrastructure — COMPLETE

All four sub-items landed 2026-04-23:

| Sub-packet | What | Artifact | Result |
|---|---|---|---|
| WP4-A | ClickHouse DDL — `polytool.n8n_execution_metrics` ReplacingMergeTree, 90-day TTL | `infra/clickhouse/initdb/28_n8n_execution_metrics.sql` | COMPLETE |
| WP4-B | n8n metrics collector workflow + activation plumbing (env wiring, CANONICAL_WORKFLOWS) | `infra/n8n/workflows/ris-n8n-metrics-collector.json` | COMPLETE — ships `active: false`; operator activates after N8N_API_KEY provisioned |
| WP4-C | Grafana RIS dashboard (4 panels: success rate, duration, failure freq, last-run table) | `infra/grafana/dashboards/ris-pipeline-health.json` | COMPLETE — auto-provisioned at Grafana container start |
| WP4-D | Stale pipeline alert (fires when periodic workflow >6h without success; `noDataState: Alerting`) | `infra/grafana/provisioning/alerting/ris-stale-pipeline.yaml` | COMPLETE — scope-fixed after Codex: explicit IN filter for 2 periodic workflows only |

Truth-sync cross-check (`2026-04-23_ris_wp4_monitoring_truth_sync.md`): All surfaces consistent — table name, column names, datasource UID, workflow registration, env wiring, ReplacingMergeTree/FINAL pattern.

---

## Files Changed in This Pass

| File | Change | Reason |
|---|---|---|
| `docs/CURRENT_DEVELOPMENT.md` | Updated Feature 2 "Current step" and DoD checkboxes | WP3-C was the last recorded step; WP3-D, WP3-E, and all of WP4 landed since then; status was stale |
| `docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md` | Created (this file) | Mandatory dev log per repo policy |

---

## Contradictions Fixed

One contradiction resolved: Feature 2 "Current step" in `CURRENT_DEVELOPMENT.md` described WP3-C as the current step and listed WP3-D, WP1 remaining items as next actions. Reality: WP3-D, WP3-E (daily digest), and the entire WP4 monitoring stack were all completed in the same 2026-04-23 session. Updated to reflect WP5 as the current entry point.

---

## Commands Run

```
python -m polytool --help
```
**Result:** Exit 0. CLI loads cleanly. No import errors.

Repo diff inspection: only `docs/CURRENT_DEVELOPMENT.md` and this dev log changed.

---

## WP5 Entry Handoff

### What benchmark tooling exists now

The existing retrieval benchmark lives in `packages/research/` and supports:
- `polytool rag-eval` — runs the golden query set against ChromaDB and reports retrieval metrics
- `polytool rag-query --question "..." --hybrid` — ad-hoc retrieval with provider routing
- Golden query set: 5 queries (original) — factual / cross-document / paraphrase mix
- Metrics: precision at current default K, per-query rank of expected doc

Relevant files (verify current paths before WP5 implementation):
- `packages/research/rag/` — retrieval engine (ChromaDB + SentenceTransformers)
- `packages/research/evaluation/` — scoring stack (WP2 providers live here)
- `config/ris_eval_config.json` — routing config
- `kb/rag/knowledge/knowledge.sqlite3` — knowledge store (59 docs, 146 claims post-WP1-D)
- `artifacts/research/` — artifact outputs (budget_tracker, eval outputs)

### What the roadmap wants (WP5 per `RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md`)

- **WP5-A**: Expand golden test set from 5 to 30+ queries across 5 classes:
  - factual (direct lookup)
  - conceptual (abstracted understanding)
  - cross-document (requires combining 2+ sources)
  - paraphrase (same concept, different wording)
  - negative-control (no good answer exists in store; should return low confidence or empty)
- **WP5-B**: Add Precision@5 metric (fraction of top-5 results that are relevant)
- **WP5-C**: Segmented per-class reporting (not just aggregate)
- **WP5-D**: Save baseline to `artifacts/research/baseline_metrics.json` (reproducible)

**Acceptance:** 30+ queries across all 5 classes; per-class metrics; baseline artifact saved.

### First WP5 implementation slice

Before writing any new queries, the first slice should be:

1. **Inspect current `rag-eval` implementation** — understand the existing 5-query golden set format,
   current metric calculation, and output format. Determine if Precision@5 can be added in-place
   or requires a new eval mode.

2. **Extend the golden set to 30+ queries** — distribute across 5 classes, weighted toward
   the knowledge store's actual content (59 docs, families: academic×16, blog×16, book_foundational×11,
   external_knowledge×7, github×5, manual×3, book×1). Negative-control queries require care:
   they should be valid research questions for which the store genuinely has no good answer.

3. **Add Precision@5 + per-class segmented output** — extend the eval runner to:
   - tag each query with its class
   - report P@5 per query and aggregate per class
   - write `artifacts/research/baseline_metrics.json` on exit

4. **Run the benchmark, save the baseline, confirm reproducibility** — second run should
   produce identical metrics if the knowledge store hasn't changed.

**WP5 is documentation + code only. No new ingestion, no provider calls, no infra changes.**

---

## Open Questions for WP5

- Does the current `rag-eval` output format expose enough data to compute P@5, or does it
  need the top-K ranked list with relevance judgments?
- Are relevance judgments for the 30+ queries manual (operator-labeled) or heuristic
  (e.g., doc_id in top-5 = hit)?
- Should negative-control queries produce a score of 0 if ANY result is returned, or only
  if a result above a confidence threshold is returned?

These questions can be answered by reading the `rag-eval` source before writing any new code.

---

**Codex review tier:** Skip — documentation-only pass, no application code changed.
