---
tags:
  - roadmap
  - ris
  - phase-2-fixes
date: 2026-04-22
status: superseded
supersedes: 07-RIS-Phase2-Gap-Closure-Roadmap.md (2026-04-10 version)
---
# RIS Operational Readiness — Updated Roadmap

> [!WARNING] SUPERSEDED by v1.1 (2026-04-22 evening)
> This document's body plus three appended updates contain contradictions that were resolved on 2026-04-22 evening. The authoritative version is [[RIS_OPERATIONAL_READINESS_ROADMAP_v1.1]]. This file is retained as historical record of the planning evolution but should NOT be used for implementation.
>
> **Key corrections in v1.1:**
> - Phase 2B WP6 base case is manual-with-GitHub, NOT Hermes
> - Hermes moved to deferred WP7 (conditional)
> - 3-friend cap explicit in scope
> - WP2 provider list consolidated (Gemini, DeepSeek, OpenRouter, Groq, Ollama Cloud, Ollama local)
> - Auto-install and fleet dashboard stretch paths removed from Phase 2B base


**Source:** Phase 2 audit (April 10), architect review, workflow harness refresh (April 21),
CURRENT_DEVELOPMENT.md state, Obsidian vault review (April 22)
**Goal:** Get RIS to a truly autonomous state where it collects, evaluates, stores, and
organizes knowledge with zero operator intervention beyond watching it work.

---

## Current Project Context (as of April 22, 2026)

**Active features (per CURRENT_DEVELOPMENT.md):**
- Feature 1: Track 2 Paper Soak — 24h run (passive, partner machine)
- Feature 2: SimTrader Fee Model Overhaul (PMXT Deliverable A) — near completion, last phase
- Slot 3: EMPTY — RIS will fill this when Feature 2 completes

**RIS status:** Paused in CURRENT_DEVELOPMENT.md. Last active work: April 10.
**Workflow harness:** AGENTS.md rebuilt, CURRENT_DEVELOPMENT.md enforcing WIP limit of 3.
**Vault sync:** Folders 00-07 stale (last updated April 10). This roadmap accounts for that.

**What's changed since the original gap closure roadmap (April 10):**
- Fee model work packet corrected: Polymarket formula exponent was 2 (wrong), should be 1.
  Category-specific feeRates discovered. This is being handled in PMXT Deliverable A.
- Wallet Discovery Loop A shipped (2026-04-10)
- Workflow harness refresh introduced docs cleanup and active-feature gates
- No RIS code changes since April 10

---

## What "Truly Working" Means

When RIS is operational, this is what happens with zero human intervention:

**Every 4-12 hours (per source schedule):**
1. n8n triggers each ingestion pipeline (ArXiv, Reddit, Blog/RSS, YouTube, GitHub)
2. Pipeline fetches new content from the source
3. Each document hits the evaluation gate — Gemini Flash scores it on 4 dimensions
4. GREEN (≥3.5 composite) → auto-ingested into ChromaDB + SQLite knowledge store
5. YELLOW (2.5-3.5) → escalated to DeepSeek V3 → re-scored → ACCEPT or REVIEW queue
6. RED (<2.5) → rejected to JSONL log, never enters knowledge store
7. Discord alert fires on pipeline failure

**Every 30 minutes:**
8. n8n health monitor checks all pipelines, sends Discord alert only on RED status

**Weekly (Sunday):**
9. Digest report generated and sent to Discord — what was learned this week
10. Freshness tiers recomputed (old Reddit posts decay, foundational papers don't)

**On demand (any time):**
11. `polytool research-precheck --idea "..."` → GO/CAUTION/STOP verdict with citations
12. `polytool rag-query --question "..."` → retrieves relevant knowledge with sources
13. Webhook URL accepts manual URL submissions for immediate ingestion

**What the operator does:**
- Watch the Discord channel for alerts and weekly digests
- Review the YELLOW queue once a week (`polytool research-review list`)
- Occasionally submit URLs for manual ingestion
- That's it

---

## Phase 2A: Core RIS Operational (YOUR machine)

### WP1: Foundation Fixes (Day 1 — no dependencies, pure corrections)

These are fast fixes to existing code. Each is 5-15 minutes of work.

**WP1-A: Fix scoring weights**
File: `packages/research/evaluation/scoring.py`
Change: `novelty*0.25 + actionability*0.25 + credibility*0.20` →
`novelty*0.20 + actionability*0.20 + credibility*0.30`
Per [[Decision - RIS Evaluation Scoring Policy]].

**WP1-B: Fix per-dimension floor**
File: `packages/research/evaluation/config.py`
Change: Add floor of 2 on novelty and actionability (currently only relevance + credibility).

**WP1-C: Fix provider_event field mismatch**
File: `packages/research/evaluation/evaluator.py`
Change: `provider_event` → `provider_events` (list). One-line fix.
File: `packages/research/metrics.py` reads `provider_events` — will now find data.

**WP1-D: Run Phase R0 seed**
Command: `python -m polytool research-seed`
Verification: `research-stats` shows 11+ docs with source_family `book_foundational`.
Operator action, not code change. 30 minutes including verification.

**WP1-E: Seed open-source integration findings**
Per Sub-Task C of the Unified Integration packet: ingest 5 documents from recent research:
- hermes-pmxt LEARNINGS.md (pmxt SDK gotchas)
- Sports strategy catalogue (3 strategies with parameters)
- Execution modeling limitations
- Cross-platform divergence frequency (AhaSignals data)
- Polymarket fee structure (verified April 2026)
Use: `polytool research-acquire --url <path> --source-family practitioner`

**Acceptance:** All existing tests pass. `research-stats` shows 16+ docs. Scoring weights match decision doc.

---

### WP2: Cloud LLM Providers (Days 2-4 — the biggest piece)

This is the single most important work packet. Without cloud providers, the evaluation
gate auto-accepts everything (ManualProvider hardcodes all scores to 3).

**WP2-A: OpenAICompatibleProvider base class**
File: `packages/research/evaluation/providers.py`
Design: Generic class with `api_key`, `base_url`, `model` params. Uses `openai` Python
package. JSON mode, strict post-validation, retry with backoff.
Any future OpenAI-compatible endpoint (Groq, Together, local vLLM) = one-line subclass.

**WP2-B: GeminiFlashProvider**
Uses `google-generativeai` package. Constrained decoding via `response_schema`.
Rate limiting: target 12 RPM. Model: config param, default `gemini-2.5-flash-preview-05-20`.
Implementation reference: [[11-Prompt-Archive/2026-04-09 GLM5 - Gemini Flash Structured Evaluation]].

**WP2-C: DeepSeekV3Provider**
Subclass of OpenAICompatibleProvider. `base_url="https://api.deepseek.com"`, `model="deepseek-chat"`.
No constrained decoding — strict post-validation (float→int, field checks, JSON extraction fallback).

**WP2-D: Multi-provider routing**
Config: `config/ris_eval_config.json` (already has placeholder structure).
Flow: Primary (Gemini) → score zones → Escalation (DeepSeek) for YELLOW → Fallback (Ollama).
All fail → REJECT with `reject_reason="all_providers_failed"` (fail-closed).
Artifact writes `provider_events` list recording every attempt.

**WP2-E: Budget enforcement**
Track daily request count in `artifacts/research/budget_tracker.json`.
Read caps from existing `config/ris_eval_config.json` budget section.
Budget exhausted → fall to next provider or queue for next day.

**WP2-F: CLI --provider and --compare**
`polytool research-eval --provider gemini|deepseek|ollama|all --compare`
Env var `RIS_EVAL_PROVIDER` for scheduler/n8n use.

**Acceptance:**
- `--provider gemini` returns valid scores (not ValueError)
- Known-bad doc rejected, known-good doc accepted
- Provider failure → fallback chain works
- All providers fail → fail-closed REJECT
- Budget cap blocks >1500 Gemini calls/day

---

### WP3: n8n Workflow Visual Improvements (Days 3-5 — parallel with WP2)

Make the n8n workflow show the data flow visually. Currently nodes show raw docker exec
output. After this, each node shows structured data you can click to inspect.

**WP3-A: Structured output parsing in Code nodes**
Every pipeline section gets a Code node after Execute Command that parses stdout into:
```json
{
  "pipeline": "academic",
  "docs_fetched": 5,
  "docs_evaluated": 5,
  "docs_accepted": 3,
  "docs_rejected": 1,
  "docs_review": 1,
  "new_claims": 7,
  "duration_seconds": 45,
  "errors": []
}
```
When you click the Code node in n8n, you see this structured data — not raw text.

**WP3-B: Visual success/failure indicators**
Add Set nodes after the IF branch that display clear status:
- Success path: `✅ Academic: 3 docs ingested, 7 claims extracted`
- Failure path: `❌ Academic: API timeout after 30s`
These are visible in n8n's execution view without clicking into individual nodes.

**WP3-C: Health monitor rich output**
The health monitor section's Parse node shows a table-like summary:
```json
{
  "status": "HEALTHY",
  "pipelines": {
    "academic": {"last_run": "2h ago", "status": "ok"},
    "reddit": {"last_run": "4h ago", "status": "ok"},
    "blog": {"last_run": "1h ago", "status": "ok"},
    "youtube": {"last_run": "3d ago", "status": "warning"},
    "github": {"last_run": "5d ago", "status": "ok"}
  },
  "knowledge_store": {"total_docs": 47, "this_week": 12},
  "review_queue": {"pending": 3}
}
```

**WP3-D: Discord embeds with pipeline metrics**
Replace plain-text Discord alerts with rich embeds showing per-pipeline status:
- Color: green (all ok), yellow (partial failure), red (all failed)
- Fields: one per pipeline with doc count and status
- Footer: timestamp + knowledge store size

**WP3-E: Daily summary section (new, Section 10)**
Add a daily summary trigger (09:00 UTC) that aggregates yesterday's results:
- How many docs ingested per source
- How many rejected, how many in review queue
- Knowledge store growth trend
- Sent to Discord as a green/yellow digest embed

**Acceptance:**
- Clicking any pipeline node in n8n shows structured JSON (not raw text)
- Health monitor shows per-pipeline status table
- Discord alerts include per-pipeline fields with doc counts
- Daily summary fires at 09:00 and sends digest to Discord

---

### WP4: Monitoring Infrastructure (Days 4-6 — parallel)

**WP4-A: ClickHouse DDL**
File: `infra/clickhouse/initdb/n8n_execution_metrics.sql`
ReplacingMergeTree with execution_id for idempotent inserts. 90-day TTL.

**WP4-B: n8n metrics collector**
Separate workflow (not in unified dev workflow): hourly schedule → GET n8n executions API →
transform → POST ClickHouse. Code-level prefilter for already-seen execution IDs.

**WP4-C: Grafana RIS dashboard**
File: `infra/grafana/dashboards/ris-pipeline-health.json`
Four panels: success rate, duration, failure frequency, last run status table.

**WP4-D: Stale pipeline alert**
Grafana alert: any pipeline hasn't succeeded in 6+ hours. No Data → Alerting.

**Acceptance:**
- Dashboard imports cleanly on fresh `docker compose up`
- Stale pipeline alert fires when a pipeline is disabled for >6h

---

### WP5: Retrieval Benchmark (Day 7+ — after seed is complete)

**WP5-A: Expand golden test set** from 5 to 30+ queries across 5 classes
(factual, conceptual, cross-document, paraphrase, negative-control).

**WP5-B: Add Precision@5** metric to eval harness.

**WP5-C: Add segmented per-class reporting** (not just global averages).

**WP5-D: Save baseline** to `artifacts/research/baseline_metrics.json`.

**Acceptance:**
- 30+ queries across all 5 classes
- Metrics reported per class
- Baseline artifact saved and reproducible

---

## Phase 2B: Distributed RIS (friend machines)

**Prerequisites:** Phase 2A complete. Core RIS working autonomously on your machine.

### Concept

Friends run lightweight RIS workers that fetch and evaluate documents. Results sync
to your machine for import. Each friend adds their own Gemini free tier (1,500 calls/day).
3 friends = 4× evaluation capacity = 4× knowledge growth rate.

### Architecture

```
Friend Worker (lightweight):
  - Python + research ingestion package (pip install)
  - Gemini API key (their own free tier)
  - Config: which sources to scrape, evaluation settings
  - Output: scored document packages (JSON files) → shared folder

Your Machine (full stack):
  - Import worker: watches shared folder, dedup, import to Chroma/SQLite
  - Existing RIS infrastructure unchanged
  - Cross-references with existing knowledge store
```

### Worker Package Design

```
polytool-ris-worker/
  ├── worker.py           # Main loop: fetch → evaluate → export
  ├── config.json          # Sources, schedule, API keys
  ├── requirements.txt     # Minimal: google-generativeai, requests, feedparser
  └── README.md            # "pip install -r requirements.txt && python worker.py"
```

No Docker required. No ClickHouse. No Grafana. No n8n. Just Python.

### Sync Options (simplest first)

1. **Google Drive shared folder** — worker writes JSON to a Drive folder, your machine
   has Drive sync pointing at the same folder. Free, zero config.
2. **Git repo** — worker commits JSON files, your machine pulls. Version controlled.
3. **rsync over SSH** — worker pushes to your machine. Requires SSH access.
4. **Dropbox/OneDrive** — same as Drive.

### Import Command

```bash
# Your machine: import all new document packages from sync folder
polytool research-import-worker --folder /path/to/sync/folder

# Dedup: content-hash checks prevent double-ingestion
# Already-seen documents are skipped silently
```

### Work Packets

**WP6-A:** Extract ingestion + evaluation into standalone worker package
**WP6-B:** Build `research-import-worker` CLI command
**WP6-C:** Write friend setup guide (5-minute install)
**WP6-D:** Test with one friend machine

### Scaling Math

| Friends | Gemini calls/day | Docs evaluated/day (est.) | Knowledge growth |
|---------|-----------------|--------------------------|-----------------|
| 0 (you only) | 1,500 | ~200-400 | 1× |
| 1 friend | 3,000 | ~400-800 | 2× |
| 3 friends | 6,000 | ~800-1,600 | 4× |
| 5 friends | 9,000 | ~1,200-2,400 | 6× |

Each friend can also cover different sources — one does ArXiv, another does Reddit,
another does YouTube channels. Source parallelism + evaluation parallelism.

---

## Execution Sequence

```
[PMXT Deliverable A completes] ← you are here
         │
         ▼
WP1: Foundation Fixes (Day 1, 2-3 hours)
  ├── WP1-A: Fix scoring weights (15 min)
  ├── WP1-B: Fix dimension floors (15 min)
  ├── WP1-C: Fix field mismatch (15 min)
  ├── WP1-D: Run R0 seed (30 min)
  └── WP1-E: Seed integration findings (30 min)
         │
    ┌────┴────┐
    ▼         ▼
WP2: Cloud    WP3: n8n Visual     WP4: Monitoring
Providers     Improvements        Infrastructure
(Days 2-4)    (Days 3-5)          (Days 4-6)
    │              │                    │
    └──────┬───────┘                    │
           ▼                            │
    Test end-to-end:                    │
    ingest → evaluate →                 │
    store → query → precheck            │
           │                            │
           └────────────┬───────────────┘
                        ▼
                  WP5: Benchmark
                  (Day 7+)
                        │
                        ▼
                  Phase 2A COMPLETE
                  RIS runs autonomously
                        │
                        ▼
                  Phase 2B: Distributed
                  (when ready)
```

---

## Governance

- **CURRENT_DEVELOPMENT.md:** Add "RIS Operational Readiness" as Feature 3 when
  PMXT Deliverable A completes and frees Slot 2.
- **PLAN_OF_RECORD.md:** One-line update authorizing Tier 1 free APIs for RIS evaluation
  (must happen before WP2 implementation starts).
- **02-Modules/RIS.md:** Correct status from "done" to "partial" until WP1+WP2 pass.
- **Fail-closed contract:** No provider path can silently accept without a scored artifact.
- **Research-only posture:** Scores classify quality, not strategy recommendations.

---

## n8n Workflow — What It Should Look Like

After WP3, here's what each pipeline section shows when you click through execution:

```
Section 2: Academic Pipeline
┌─────────────────────────────────────────────────────────────────────────┐
│ [Academic Schedule] → [Run academic_ingest] → [Parse Results]          │
│ [Academic Manual ↗]     stdout: "..."          {                       │
│                         exitCode: 0              docs_fetched: 5,      │
│                                                  docs_accepted: 3,     │
│                                                  docs_rejected: 1,     │
│                                                  docs_review: 1,       │
│                                                  new_claims: 7         │
│                                                }                       │
│                                                                        │
│                    → [Academic OK?] → true  → [✅ Academic: 3 ingested] │
│                                    → false → [Format Error]            │
│                                             → [🔴 Discord Alert]       │
│                                               {                        │
│                                                 title: "RIS: academic  │
│                                                         failed",       │
│                                                 color: red,            │
│                                                 error: "API timeout"   │
│                                               }                        │
└─────────────────────────────────────────────────────────────────────────┘
```

You see the data at every stage. Click any node → see its input/output JSON.
The "Parse Results" node turns raw text into structured metrics.
The Discord Alert node shows exactly what embed will be sent.

---

## Cross-References
- [[10-Session-Notes/2026-04-10 RIS Phase 2 Audit Results]] — audit findings
- [[Decision - RIS Evaluation Gate Model Swappability]] — provider architecture
- [[Decision - RIS Evaluation Scoring Policy]] — scoring weights and thresholds
- [[Decision - RIS n8n Pilot Scope]] — n8n boundary (ADR 0013)
- [[Decision - Workflow Harness Refresh 2026-04]] — WIP limits, CURRENT_DEVELOPMENT.md
- [[12-Ideas/Work-Packet - Unified Open Source Integration]] — fee model + RIS seeding
- [[11-Prompt-Archive/2026-04-09 GLM5 - Gemini Flash Structured Evaluation]]
- [[11-Prompt-Archive/2026-04-09 GLM5 - n8n ClickHouse Grafana Metrics]]
- [[11-Prompt-Archive/2026-04-09 GLM5 - RAG Retrieval Quality Testing]]



---

## Update 2026-04-22 Late — Hermes Integration Integrated Into Plan

Director decided during the 2026-04-22 Hermes session to adopt Hermes Agent for Phase 2B distributed workers. Full setup guide at [[08-Research/Hermes Agent - PolyTool Integration Setup Guide]]. This update folds Hermes into the roadmap's Phase 2B and adjusts Phase 2A WP2 accordingly.

### What Changes in Phase 2A

**WP2 (Cloud LLM Providers) — small scope addition.** In addition to the originally planned Gemini Flash + DeepSeek subclasses, WP2 now builds:
- `GeminiFlashProvider` (was planned)
- `DeepSeekV3Provider` (was planned)
- `OpenRouterProvider` (new) — `base_url=https://openrouter.ai/api/v1`
- `GroqProvider` (new) — `base_url=https://api.groq.com/openai/v1`
- `OllamaCloudProvider` (new) — per Ollama Cloud endpoint
- `OllamaLocalProvider` (already planned as fallback)

All five subclasses use the same `OpenAICompatibleProvider` base class. Estimated additional effort: 30-45 minutes on top of original WP2 work. Reason: Phase 2B friends will use any of these; having them already available means the friend worker just imports from `packages/research/evaluation/providers.py` rather than implementing its own adapters.

**No other Phase 2A changes.** WP1, WP3, WP4, WP5 unchanged. n8n stays per ADR 0013. CC+Codex stays as the agent allocation.

### What Changes in Phase 2B

**WP6 is significantly simplified.** Original plan assumed building a custom `polytool-ris-worker` Python package with its own runtime, scheduler, and messaging. With Hermes, WP6 becomes:

- **WP6-A (revised):** Write `~/.hermes/skills/polytool-ris-worker/` — a Hermes skill. Contents:
  - `SKILL.md` (skill definition, invocation triggers, procedure)
  - `worker.py` (provider-agnostic; reads config.json; imports evaluator from `packages/research/evaluation`)
  - `providers/` (thin wrappers for each supported provider)
  - `config.sample.json` (template)
  - `SETUP-GEMINI.md`, `SETUP-OPENROUTER.md`, `SETUP-GROQ.md`, `SETUP-OLLAMA-LOCAL.md` (per-provider setup; friend reads only their chosen one)
  - `README.md` (overview + branching flow)
- **WP6-B (unchanged):** `polytool research-import-worker` CLI on operator machine.
- **WP6-C (simplified):** 5-minute friend install guide. Three paths (Gemini / OpenRouter / Ollama local).
- **WP6-D (unchanged):** Test with one friend machine.

Estimated effort reduction: 40-50% vs custom Python worker because Hermes bundles runtime + cron + messaging + memory.

### Provider Strategy (Phase 2B)

Per Director direction 2026-04-22:
- **Default:** Gemini Flash (1,500 req/day free, Google account required)
- **Fallback for no-Google-account friends:** OpenRouter free models
- **Secondary fallback:** Groq free tier (very fast)
- **Tertiary:** Ollama Cloud (if friend prefers)
- **Last resort:** Ollama local (100% free, 16GB RAM min, Qwen3-14B class model)

Swapping provider = editing two fields in `config.json`. No code change.

### Quality Calibration (Phase 2B)

Provider-specific GREEN thresholds to compensate for evaluation quality differences:
- Gemini / OpenRouter / Groq: GREEN ≥3.5 (original)
- Ollama Cloud: GREEN ≥3.75 (one step stricter)
- Ollama local: GREEN ≥4.0 (two steps stricter)

Every 100 accepted docs from a friend+provider combo, operator re-scores a sample with Gemini as reference. Agreement <80% → raise threshold. Agreement >95% over 300+ docs → may relax threshold.

### What Operator Does During Phase 2B

Beyond the original "watch Discord, review YELLOW queue weekly":
- Run `polytool research-import-worker --folder <sync>` periodically (can be n8n-scheduled on operator machine)
- Review first N docs from each new friend+provider combo to calibrate
- Accept PRs to the skill if friends contribute source adapters

### Execution Triggers for Phase 2B (unchanged from setup guide)

Do NOT begin Phase 2B work until ALL of:
1. Fee Model Overhaul complete
2. Phase 2A WP1-WP5 complete
3. WP6 is next in sequence
4. At least one friend has explicitly agreed to run a worker

### Optional: Operator Hermes Instance (separate from Phase 2B)

Independent track documented in [[08-Research/Hermes Agent - PolyTool Integration Setup Guide]]. Gives operator read-only Discord/Telegram access to PolyTool state. Can ship before, alongside, or after Phase 2B. Not a dependency.

### Updated Execution Sequence

```
[PMXT Deliverable A completes] ← you are here
         │
         ▼
Phase 2A: WP1 Foundation Fixes (Day 1)
         │
    ┌────┴────┐
    ▼         ▼
WP2: Cloud    WP3: n8n Visual     WP4: Monitoring
Providers     Improvements        Infrastructure
(includes     (Days 3-5)          (Days 4-6)
OpenRouter
+Groq now)
(Days 2-4)
    │              │                    │
    └──────┬───────┘                    │
           ▼                            │
    Test end-to-end                     │
           │                            │
           └────────────┬───────────────┘
                        ▼
                  WP5: Benchmark (Day 7+)
                        │
                        ▼
                  Phase 2A COMPLETE
                  RIS runs autonomously on operator machine
                        │
                        ▼
                  [TRIGGER: At least one friend agrees]
                        │
                        ▼
                  Phase 2B: Hermes-based distributed RIS
                    WP6-A: Hermes skill
                    WP6-B: Import CLI
                    WP6-C: Friend install guide (3 provider paths)
                    WP6-D: Test with one friend
                        │
                        ▼
                  Phase 2B COMPLETE
                  Distributed RIS producing 2-5× knowledge growth
```

### Governance Updates

- **CURRENT_DEVELOPMENT.md:** When Feature 2 (Fee Model) completes, Feature 3 becomes "RIS Operational Readiness — Phase 2A." When Phase 2A completes, Feature 3 becomes "RIS Phase 2B — Hermes Distributed Workers."
- **AGENTS.md:** No changes needed. Rules still apply.
- **Architect custom instructions:** Add the 2-line awareness for Phase 2B Hermes evaluation (see [[Decision - Agent Parallelism Strategy for RIS Phase 2]]).
- **PLAN_OF_RECORD.md:** One-line update authorizing multi-provider free-tier API usage for RIS (not just Gemini — also OpenRouter, Groq, Ollama).

### Cross-References Added

- [[08-Research/Hermes Agent - PolyTool Integration Setup Guide]] — full Phase 2B setup guide
- [[Decision - Agent Parallelism Strategy for RIS Phase 2]] — parent decision (Hermes sequenced to Phase 2B, not Phase 2A)
- [[12-Ideas/Idea - Hermes Agent Platform Evaluation]] — original Hermes evaluation (partially superseded by the setup guide)
