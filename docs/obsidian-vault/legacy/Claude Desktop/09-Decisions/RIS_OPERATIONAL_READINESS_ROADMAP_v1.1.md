---
tags: [roadmap, ris, phase-2, authoritative]
date: 2026-04-22
status: authoritative
version: 1.1
supersedes: RIS_OPERATIONAL_READINESS_ROADMAP.md (original + three appended updates)
scope: 3-friend-max distributed RIS
---

# RIS Operational Readiness — Consolidated Roadmap v1.1

**This document supersedes `RIS_OPERATIONAL_READINESS_ROADMAP.md`.** That file's original body plus its three appended updates (Hermes integration, provider strategy, auto-install stretch, manual-with-GitHub correction) are consolidated here into a single clean document. The previous file is retained as historical record but is no longer the authority for Phase 2 planning.

**Goal:** Get RIS to an autonomous state where it collects, evaluates, stores, and organizes knowledge with minimal operator intervention. Scoped for **up to 3 friends** running manual contribution scripts on their own schedule.

---

## Executive Summary

- **Phase 2A** (7 days, operator machine): fix existing bugs, wire cloud LLM providers, improve n8n visibility, add monitoring, expand retrieval benchmark.
- **Phase 2B** (distributed, small-scale): up to 3 friends run a one-shot contribution script that commits scored JSON packages to a GitHub repo. Operator machine pulls and imports on its own schedule. No Hermes in base case. No auto-install, no fleet dashboards, no continuous runners.
- **Sequencing:** Phase 2B only starts after Phase 2A is complete AND at least one friend has explicitly agreed to run the script.

---

## Current Project Context (2026-04-22)

**Active features (per CURRENT_DEVELOPMENT.md):**
- Feature 1: Track 2 Paper Soak — 24h run (passive, partner machine)
- Feature 2: SimTrader Fee Model Overhaul (PMXT Deliverable A) — near completion, last phase
- Slot 3: EMPTY — reserved for RIS Phase 2A when Feature 2 completes

**RIS status:** Paused. Last active work was 2026-04-10.
**Friend count target:** Maximum 3. This informs base-case scope.
**Sync strategy:** GitHub repo with per-friend branches. Google Drive is alternate.

---

## What "Truly Working" Means

When Phase 2A is complete, this happens with zero operator intervention on the operator machine:

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
10. Freshness tiers recomputed

**On demand:**
11. `polytool research-precheck --idea "..."` → GO/CAUTION/STOP verdict with citations
12. `polytool rag-query --question "..."` → retrieves relevant knowledge with sources
13. Webhook URL accepts manual URL submissions for immediate ingestion

**What the operator does:**
- Watch the Discord channel for alerts and weekly digests
- Review the YELLOW queue once a week (`polytool research-review list`)
- Periodically run `polytool research-import-worker --git-remote <url>` to pull friend contributions
- Occasionally submit URLs for manual ingestion
- That's it

---

## Phase 2A: Operator Machine Work

### WP1: Foundation Fixes (Day 1 — ~2-3 hours)

Fast corrections to existing code.

**WP1-A: Fix scoring weights**
File: `packages/research/evaluation/scoring.py`
Change: `novelty*0.25 + actionability*0.25 + credibility*0.20` → `novelty*0.20 + actionability*0.20 + credibility*0.30`
Per [[Decision - RIS Evaluation Scoring Policy]].

**WP1-B: Fix per-dimension floor**
File: `packages/research/evaluation/config.py`
Change: Add floor of 2 on novelty and actionability.

**WP1-C: Fix provider_event field mismatch**
File: `packages/research/evaluation/evaluator.py`
Change: `provider_event` → `provider_events` (list). One-line fix.

**WP1-D: Run Phase R0 seed**
Command: `python -m polytool research-seed`
Verification: `research-stats` shows 11+ docs with `source_family: book_foundational`.

**WP1-E: Seed open-source integration findings**
Ingest 5 documents per Sub-Task C of the Unified Integration packet:
- hermes-pmxt LEARNINGS.md (pmxt SDK gotchas)
- Sports strategy catalogue (3 strategies with parameters)
- Execution modeling limitations
- Cross-platform divergence frequency (AhaSignals data)
- Polymarket fee structure (verified April 2026)

**Acceptance:**
- All existing tests pass
- `research-stats` shows 16+ docs
- Scoring weights match decision doc

---

### WP2: Cloud LLM Providers (Days 2-4 — the biggest WP)

Without cloud providers, the evaluation gate auto-accepts everything (ManualProvider hardcodes all scores to 3).

**WP2-A: OpenAICompatibleProvider base class**
File: `packages/research/evaluation/providers.py`
Generic class with `api_key`, `base_url`, `model` params. Uses `openai` Python package. JSON mode, strict post-validation, retry with backoff.

**WP2-B: GeminiFlashProvider**
Uses `google-generativeai` package. Constrained decoding via `response_schema`. Rate limit 12 RPM. Default model `gemini-2.5-flash`.

**WP2-C: DeepSeekV3Provider**
Subclass of base. `base_url="https://api.deepseek.com"`, `model="deepseek-chat"`.

**WP2-D: OpenRouterProvider** (new, supports Phase 2B friends without Google account)
Subclass of base. `base_url="https://openrouter.ai/api/v1"`. Supports free `:free` model variants.

**WP2-E: GroqProvider** (new, secondary fallback)
Subclass of base. `base_url="https://api.groq.com/openai/v1"`. Llama/Mixtral models.

**WP2-F: OllamaCloudProvider** (new)
Per Ollama Cloud endpoint. Cloud-hosted, requires Ollama account.

**WP2-G: OllamaLocalProvider**
For friends running Ollama locally (last-resort option).

**WP2-H: Multi-provider routing**
Config: `config/ris_eval_config.json`.
Flow: Primary (Gemini) → score zones → Escalation (DeepSeek) for YELLOW → Fallback (Ollama).
All fail → REJECT with `reject_reason="all_providers_failed"` (fail-closed).
Artifact writes `provider_events` list recording every attempt.

**WP2-I: Budget enforcement**
Track daily request count in `artifacts/research/budget_tracker.json`.
Read caps from `config/ris_eval_config.json`.
Budget exhausted → fall to next provider or queue for next day.

**WP2-J: CLI --provider and --compare**
`polytool research-eval --provider gemini|deepseek|openrouter|groq|ollama-cloud|ollama-local|all --compare`
Env var `RIS_EVAL_PROVIDER` for scheduler/n8n use.

**Scope addition note:** WP2-D, WP2-E, WP2-F are additions to original roadmap (original had only Gemini, DeepSeek, Ollama local). Added because Phase 2B friend worker will reuse this module — having all providers as first-class subclasses means the friend script just imports from this file. Additional effort: ~30-45 minutes on top of original WP2.

**Acceptance:**
- All provider subclasses return valid scores for a known-good test document
- Known-bad doc rejected, known-good accepted
- Provider failure → fallback chain works
- All providers fail → fail-closed REJECT with artifact
- Budget cap blocks >1500 Gemini calls/day

---

### WP3: n8n Workflow Visual Improvements (Days 3-5, parallel with WP2)

Make n8n nodes show structured data instead of raw exec output.

**WP3-A: Structured output parsing**
Code nodes parse stdout into:
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

**WP3-B: Visual success/failure indicators**
Set nodes display `✅ Academic: 3 docs ingested` or `❌ Academic: API timeout`.

**WP3-C: Health monitor rich output**
Parse node shows table-like summary with per-pipeline status, knowledge_store growth, review_queue depth.

**WP3-D: Discord embeds with pipeline metrics**
Replace plain-text alerts with color-coded embeds showing per-pipeline fields.

**WP3-E: Daily summary section**
New trigger at 09:00 UTC aggregates yesterday's results, sends Discord digest embed.

**Acceptance:**
- Clicking any pipeline node shows structured JSON
- Health monitor shows per-pipeline status table
- Discord alerts include per-pipeline fields with doc counts
- Daily summary fires at 09:00

---

### WP4: Monitoring Infrastructure (Days 4-6, parallel with WP2)

**WP4-A: ClickHouse DDL**
File: `infra/clickhouse/initdb/n8n_execution_metrics.sql`
ReplacingMergeTree, 90-day TTL.

**WP4-B: n8n metrics collector**
Separate workflow: hourly schedule → GET n8n executions API → transform → POST ClickHouse.

**WP4-C: Grafana RIS dashboard**
File: `infra/grafana/dashboards/ris-pipeline-health.json`
Four panels: success rate, duration, failure frequency, last run status table.

**WP4-D: Stale pipeline alert**
Grafana alert: pipeline hasn't succeeded in 6+ hours.

**Acceptance:**
- Dashboard imports cleanly on fresh `docker compose up`
- Stale pipeline alert fires when a pipeline is disabled for >6h

---

### WP5: Retrieval Benchmark (Day 7+)

**WP5-A:** Expand golden test set from 5 to 30+ queries across 5 classes (factual, conceptual, cross-document, paraphrase, negative-control).
**WP5-B:** Add Precision@5 metric.
**WP5-C:** Segmented per-class reporting.
**WP5-D:** Save baseline to `artifacts/research/baseline_metrics.json`.

**Acceptance:**
- 30+ queries across all 5 classes
- Per-class metrics reported
- Baseline artifact saved and reproducible

---

## Phase 2B: Distributed RIS (Manual Contribution, Max 3 Friends)

**Prerequisites:**
1. Phase 2A complete (WP1-WP5 acceptance criteria all passed)
2. At least one friend has explicitly agreed to contribute
3. Fee Model Overhaul completed

**Scope discipline:** Maximum 3 friends. This informs every design decision below. If friend count grows past 3, re-evaluate architecture (consider Hermes-continuous via WP7).

### Architecture

Friend machines do NOT run continuously. Friend runs a one-shot contribution script when they want to contribute. Script fetches, evaluates, commits results to their own branch of a GitHub repo, exits.

```
Friend Machine                                  Operator Machine
──────────────                                  ─────────────────

1. Friend runs `polytool-ris-contribute`        1. Periodic (or manual):
2. Script prompts for provider + API key           `polytool research-import-worker \
   (first run only)                                   --git-remote <repo-url>`
3. Script fetches N docs from sources           2. Pulls all friend branches
4. Script evaluates each via provider           3. For each new commit, reads JSONs
5. Script writes scored JSONs locally           4. Dedups via content hash
6. Script commits to friend's branch of         5. Imports accepted docs to
   `polytool-ris-data` GitHub repo                 ChromaDB + SQLite
7. Script pushes, exits                         6. Updates budget tracker +
                                                   provider_events metrics
Friend can run the script whenever they want.
Nothing runs in background. Nothing to forget.
```

### Why Manual (not Hermes)

- **3-friend cap:** The continuous-runner benefits of Hermes don't justify the complexity at this scale. Throughput multiplier is for many friends, not 3.
- **Zero attack surface:** Nothing persistent on friend's machine. No bot tokens loaded. No background processes.
- **No OS-specific setup:** No WSL2 for Windows friends. No systemd/launchd configuration. No service management.
- **Proof-of-success in git:** If the script exits 0 with a commit, it worked. No separate health check needed.
- **Friend controls participation:** Run when they want, stop any time. Low-pressure social contract.
- **Simpler to debug:** One script, linear flow, clear error messages.

### Work Packets

**WP6-A: Build `polytool-ris-contribute` CLI**
One-shot Python entry point. Single command. Flow:
1. Load config (sync repo URL, provider, API key from env)
2. Fetch N documents from configured sources (default: 50 across all enabled sources)
3. Evaluate each via configured provider (imports from `packages/research/evaluation/providers.py`)
4. Write scored JSONs to local temp dir
5. `git clone` friend's branch of `polytool-ris-data` repo (or `git pull` if already cloned)
6. Copy JSONs in, commit with message `"batch: N docs from <friend-alias> at <timestamp>"`, push
7. Print summary, exit

**WP6-B: Build `polytool research-import-worker --git-remote <url>` CLI**
On operator machine. Clones the sync repo locally if not present, pulls all friend branches, reads new JSONs per-branch, dedups via content hash, imports accepted docs into ChromaDB + SQLite, updates budget tracker.

**WP6-C: Friend install guide**
5-minute path from zero to first commit. Three branching provider paths:

```
Step 1: Set up GitHub account (if needed). Generate fine-grained PAT
        scoped to your branch only. Operator sends you the repo URL.

Step 2: Clone the contribution script repo:
        git clone <polytool-ris-contribute-repo-url>
        cd polytool-ris-contribute
        pip install -r requirements.txt

Step 3: Choose your LLM provider
   [A] I have a Google account → use Gemini (recommended, 1,500 req/day)
       → Follow SETUP-GEMINI.md (5 min)
   [B] I prefer not to sign up for Google → use OpenRouter
       → Follow SETUP-OPENROUTER.md (3 min)
   [C] I want to run everything locally → use Ollama local
       → Follow SETUP-OLLAMA-LOCAL.md (20-60 min, 16GB RAM min)

Step 4: Run the script
        ./polytool-ris-contribute
        (answer 2-3 prompts on first run; remembered for next time)

Step 5: See your commit appear in the GitHub repo. That's proof of success.

Run again whenever you feel like contributing.
```

**WP6-D: Test with one friend**
Friend runs the script 3 times over the course of a week. Verify:
- Each run produces a clean commit
- Operator machine imports successfully
- Content hash dedup prevents double-imports
- Budget tracker reflects friend's provider events
- No silent failures

**Acceptance:**
- One friend successfully contributes 3 batches over 1 week
- All commits are in their own branch, no conflicts
- Operator imports all batches, no errors
- Provider-specific GREEN thresholds applied correctly

---

### Provider Strategy (Phase 2B)

Config-driven. Swap provider = edit two fields in `config.json`. No code change.

| Provider | Account | Free tier | GREEN threshold | Notes |
|---|---|---|---|---|
| Gemini Flash | Google | 1,500 req/day | ≥3.5 | **Default.** Highest quality + quota. |
| OpenRouter free models | Email signup | Rate-limited | ≥3.5 | No-Google-account fallback. |
| Groq free tier | Email signup | 30 req/min | ≥3.5 | Fast inference fallback. |
| Ollama Cloud | Ollama account | Free tier | ≥3.75 | One-step stricter threshold. |
| Ollama local | None | 100% free | ≥4.0 | Two-step stricter. 16GB RAM + Qwen3-14B class. |

**Threshold rationale:** Weaker evaluators get stricter GREEN thresholds to prevent low-quality docs from entering the knowledge store. YELLOW ranges shift accordingly.

**"Ollama" disambiguation:**
- **Ollama Cloud** — hosted on Ollama infrastructure, requires Ollama account
- **Ollama local** — runs on friend's machine, no account, no network, needs hardware

These are distinct provider options.

---

### Quality Calibration Loop

Every 100 accepted docs from a friend+provider combo, operator machine re-scores a sample using Gemini as reference standard.

- Agreement <80% → raise that setup's GREEN threshold one step (→ GREEN ≥4.0)
- Agreement >95% over 300+ docs → may relax threshold one step

Self-correcting. No manual intervention needed unless something goes catastrophically wrong.

---

### Sync Infrastructure

**Primary:** GitHub repo (`polytool-ris-data`), private or public.
- Operator creates repo
- Each friend gets their own branch: `friend-<alias>/data`
- Fine-grained PAT per friend, scoped to write-only on their own branch
- No merge conflicts (branches don't overlap)
- Instant token revocation if needed
- GitHub Actions optional for JSON schema validation on each commit

**Alternative:** Google Drive shared folder (if friend can't use GitHub for any reason).
- Same scored-JSON format
- Operator's import CLI supports both `--git-remote` and `--folder` flags

---

### Scaling Math (3-Friend Cap)

| Friends | Gemini calls/day available | Realistic docs/day (assuming 1 run/day) |
|---|---|---|
| 0 (operator only) | 1,500 | ~200-400 |
| 1 friend | 3,000 | ~400-800 |
| 3 friends | 6,000 | ~800-1,600 |

Friends likely run less than once/day. Realistic range: 1-3 runs per friend per week.
3 friends × 2 runs/week × 50 docs/run = ~300 docs/week from friends, on top of operator.

---

## Optional: Operator Hermes Instance

Completely separate from Phase 2B. Independent track.

Gives operator read-only Discord/Telegram access to PolyTool state from a phone:
- "What's Track 2 soak status in the last 4 hours?"
- "Any red alerts in RIS pipelines?"
- "Show me today's Fee Model dev log"

**Can ship anytime** — before, alongside, or after Phase 2B. Not a dependency. Requires WSL2 on Windows operator machine, or any Linux/macOS machine.

Full setup in [[08-Research/Hermes Agent - PolyTool Integration Setup Guide]] under "Track 1: Operator Hermes Instance" section.

---

## WP7+ (Deferred): Continuous Mode for Committed Friends

**Only build if all of:**
- At least one friend has been contributing via WP6 manually for 2+ weeks
- That friend explicitly asks for continuous/background mode
- 3-friend cap is NOT a blocker

If triggered: wrap the same `polytool-ris-contribute` logic in a Hermes skill that runs on a schedule. Same output format (JSON in GitHub branch). Operator's import CLI works unchanged. Full setup guide already exists in [[08-Research/Hermes Agent - PolyTool Integration Setup Guide]].

**Effort if triggered:** 2-3 days.

**Likelihood given 3-friend cap:** Low. Base case covers the realistic need.

---

## Execution Sequence

```
[PMXT Deliverable A completes] ← near, "last phase"
         │
         ▼
Phase 2A: WP1 Foundation Fixes (Day 1)
         │
    ┌────┼────┐
    ▼    ▼    ▼
WP2      WP3      WP4
Cloud    n8n      Monitoring
Prov     Visual   Infra
(D2-4)   (D3-5)   (D4-6)
    │    │    │
    └────┼────┘
         ▼
    WP5 Benchmark (D7+)
         │
         ▼
Phase 2A COMPLETE
(RIS autonomous on operator machine)
         │
         ▼
[TRIGGER: first friend agrees]
         │
         ▼
Phase 2B: WP6 Manual Contribution
  WP6-A: polytool-ris-contribute CLI
  WP6-B: research-import-worker CLI
  WP6-C: Friend install guide (3 provider paths)
  WP6-D: Test with one friend
         │
         ▼
Phase 2B COMPLETE
(Up to 3 friends contributing manually to GitHub)
         │
         ▼
[Only if someone explicitly wants continuous mode]
         │
         ▼
WP7 (deferred): Hermes-based continuous wrapper
```

---

## Agent Allocation

**Phase 2A:** CC#1 + CC#2 + Codex running in parallel.
- CC#1: WP2 (cloud providers — heavy Python work)
- CC#2 or Codex: WP3 (n8n JSON + Code nodes)
- Codex: WP4 (ClickHouse DDL + Grafana dashboard JSON)

**Phase 2B:** Single CC for WP6. Not a parallel-agent phase.

**No Hermes in Phase 2A or WP6 base.** If WP7 is ever triggered, Hermes enters then.

Per [[Decision - Agent Parallelism Strategy for RIS Phase 2]].

---

## Governance

**CURRENT_DEVELOPMENT.md:** When Feature 2 (Fee Model) completes, Feature 3 becomes "RIS Operational Readiness — Phase 2A." When Phase 2A completes, Feature 3 updates to "RIS Phase 2B — Manual Contribution." No "Hermes Distributed Workers" title unless WP7 is ever triggered.

**AGENTS.md:** No changes needed. Existing rules apply.

**Architect custom instructions:** Add 3-line awareness (already drafted):
```
For RIS Phase 2A (WP1-WP5): CC/Codex only.
For RIS Phase 2B WP6 (manual contribution): single CC.
Hermes only if WP7 triggered.
```

**PLAN_OF_RECORD.md:** One-line addition authorizing multi-provider free-tier API usage (Gemini, OpenRouter, Groq, Ollama Cloud, Ollama local).

**02-Modules/RIS.md:** Correct status from "done" to "partial" until WP1+WP2 pass.

**Fail-closed contract:** No provider path silently accepts without a scored artifact.

**Research-only posture:** Scores classify quality, not strategy recommendations.

---

## Execution Triggers Summary

| Stage | Trigger | Do NOT start before |
|---|---|---|
| Phase 2A WP1 | Fee Model Overhaul complete | Feature 2 moved to Recently Completed |
| Phase 2A WP2-WP5 | WP1 acceptance passed | - |
| Phase 2B WP6 | Phase 2A WP1-WP5 complete + one friend explicitly agrees | Both conditions met |
| WP7 continuous | WP6 stable 2+ weeks + explicit friend request for continuous mode + 3-friend cap re-evaluated | All three |
| Operator Hermes (optional) | Operator wants phone-based status queries | - (independent track) |

---

## Risks

**Low throughput** if friends forget to run the script. Mitigation: periodic friendly nudge from operator (not automated). Acceptable at 3-friend scale.

**Friend forgetfulness.** Most casual friends will run it once or twice then forget. With max 3 friends, this is fine — one reliable friend provides most of the value.

**No liveness signal.** Without continuous running, operator has no way to know if a friend is "still participating" vs "lost interest." At 3-friend scale, this is a feature (low-pressure) not a bug.

**Provider quota exhaustion.** Rare at 3-friend scale with 1,500/day free Gemini each. Mitigation: budget tracker flags when a friend hits 80% of daily cap.

**GitHub PAT leak.** Friend's PAT gets compromised. Mitigation: scoped write-only to their own branch. Revocation is instant. Blast radius limited to that branch.

**Low quality from weaker providers.** Ollama local in particular. Mitigation: stricter GREEN thresholds + calibration loop.

---

## What This Roadmap Explicitly Does NOT Include

- Hermes Agent in Phase 2A (ever)
- Hermes in WP6 base (moved to deferred WP7)
- Auto-install for friend machines
- Fleet dashboards for friend monitoring
- Continuous background services on friend machines
- >3 friends architecture (re-plan if that happens)
- Claude Code / ChatGPT orchestration via messaging
- Live bot execution path changes

---

## Cross-References

- [[RIS_OPERATIONAL_READINESS_ROADMAP]] — original roadmap (superseded by this document)
- [[08-Research/Hermes Agent - PolyTool Integration Setup Guide]] — reference for optional operator Hermes instance and deferred WP7
- [[Decision - Agent Parallelism Strategy for RIS Phase 2]] — agent allocation and Hermes sequencing
- [[Decision - RIS Evaluation Gate Model Swappability]] — provider architecture
- [[Decision - RIS Evaluation Scoring Policy]] — scoring weights and thresholds
- [[Decision - RIS n8n Pilot Scope]] — ADR 0013
- [[Decision - Workflow Harness Refresh 2026-04]] — WIP limits, CURRENT_DEVELOPMENT.md
- [[12-Ideas/Work-Packet - Unified Open Source Integration]] — fee model + RIS seeding
- [[11-Prompt-Archive/2026-04-09 GLM5 - Gemini Flash Structured Evaluation]]
- [[11-Prompt-Archive/2026-04-09 GLM5 - n8n ClickHouse Grafana Metrics]]
- [[11-Prompt-Archive/2026-04-09 GLM5 - RAG Retrieval Quality Testing]]
- [[11-Prompt-Archive/2026-04-21 Architect Custom Instructions v2]]

---

## Handoff Notes for RIS Chat

When this document is handed to the RIS chat for review:

1. **This is the authoritative version.** The original `RIS_OPERATIONAL_READINESS_ROADMAP.md` with its three appended updates is historical. Do not merge planning from the old document.
2. **3-friend cap is a scope decision**, not a technical constraint. It informs the manual-vs-continuous architecture choice. If that cap changes, Phase 2B plan should be reconsidered.
3. **Phase 2A is unchanged from original except WP2 scope.** WP2 now builds 5 provider subclasses (Gemini, DeepSeek, OpenRouter, Groq, Ollama Cloud) plus Ollama local, not just 3. Adds ~30-45 min.
4. **Phase 2B base is manual-with-GitHub.** Not Hermes. Hermes is deferred to WP7 (conditional).
5. **Push back on anything that expands scope beyond what's written.** The whole point of the workflow refresh was to prevent scope creep; this roadmap reflects hard-won simplification.
6. **Don't re-litigate past decisions.** The Hermes-vs-manual question, the 3-friend cap, the multi-provider strategy — all decided. Ask about implementation details only.

---

*Consolidated 2026-04-22. Supersedes layered updates from same day.*
