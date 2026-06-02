---
tags: [guide, setup, hermes, phase-2b, architect-input]
date: 2026-04-22
status: draft
purpose: Architect input for Hermes integration into PolyTool. Phase 2B trigger.
audience: Architect chat (ChatGPT Project) to generate agent prompts from
resume-trigger: All of [Fee Model complete, RIS Phase 2A complete, WP6 is next, at least one friend willing]
---

# Hermes Agent — PolyTool Integration Setup Guide

Guide for integrating Hermes Agent (NousResearch) into PolyTool. This document is input for the Architect chat — it generates agent prompts from this guide to execute the integration. It is NOT an operator runbook to follow line-by-line today.

**Status:** DRAFT. Execution triggers are documented below. Do not begin execution until all trigger conditions are met.

---

## What Hermes Is (Calibrated Understanding)

Hermes Agent is a **personal assistant runtime**, not a coding agent, not a Claude Code alternative, and not an orchestrator. It is:

- A long-running Python agent process reachable from Telegram/Discord/Slack/WhatsApp/Signal/CLI
- A cron scheduler for natural-language scheduled tasks
- A skills system (SKILL.md-compatible) that saves successful procedures as reusable routines
- A persistent memory store (agent-curated, cross-session)
- A subagent delegation mechanism for parallel workstreams
- A six-backend runtime (local, Docker, SSH, Daytona, Singularity, Modal)
- Model-agnostic (OpenRouter, OpenAI, Anthropic, Nous Portal, your endpoint)

It is **not**:
- A coding agent
- A Claude Code replacement
- A Codex replacement
- An Architect replacement
- An orchestrator for other AI agents

---

## Why Hermes in PolyTool

### Primary use: Phase 2B distributed RIS workers

Per [[RIS_OPERATIONAL_READINESS_ROADMAP]] Phase 2B, friend machines run lightweight RIS workers that fetch, evaluate, and sync documents back. The original roadmap (WP6-A/B/C/D) assumed building a custom `polytool-ris-worker` Python package from scratch.

With Hermes:
- Friend installs Hermes (one command: `curl | bash`)
- Friend installs PolyTool RIS-worker skill (from your skill repo or PyPI)
- Friend provides their Gemini API key and sync folder
- Hermes handles: scheduled fetches, evaluation, retry/backoff, Discord alerts on failure, sync to shared folder

Build effort drops ~40-50% versus custom worker because Hermes bundles runtime + messaging + cron + memory + skills standard.

### Secondary use (optional): Operator remote interface

A Hermes instance on operator's own machine, connected to Discord or Telegram, gives read-only operator access to PolyTool state from a phone:

- "What's Track 2 soak status in the last 4 hours?"
- "Any red alerts in RIS pipelines?"
- "Show me today's Fee Model dev log"
- "When does the next 5m crypto market open?"

This is NEW capability — nothing in the current roadmap provides it. Optional add-on, often bundled with Phase 2B because infra is similar.

### Explicitly NOT a Hermes use case

- Running Claude Code prompts from Discord (bypasses Architect, violates workflow refresh)
- Running Codex work from messaging (same)
- Replacing n8n for RIS Phase 2A pipelines (n8n stays per ADR 0013)
- Running live bot execution (adds latency, live execution stays pure Python)
- Driving ChatGPT web UI (not technically viable; browser automation is fragile)

---

## Execution Triggers

Do NOT begin Hermes integration work until ALL of these are true:

1. Fee Model Overhaul complete (Feature 2 moved to Recently Completed in CURRENT_DEVELOPMENT.md)
2. RIS Phase 2A complete (WP1-WP5 acceptance criteria all passed)
3. WP6 is the next planned work in Director's sequence
4. At least one friend has explicitly agreed to run a RIS worker

When all four are met, this guide becomes the Architect's input for prompt generation.

---

## Integration Scope (What Gets Built)

### Track 1: Operator Hermes Instance (optional, can ship first)

Goal: Remote operator interface for PolyTool state queries.

**Infrastructure:**
- Hermes installed on operator's Windows machine via WSL2, OR on the partner's Linux machine, OR on a dedicated VPS
- Chose deployment by: operator preference and whether operator wants 24/7 availability
- Local Docker backend if on operator machine; SSH or Modal backend if on VPS

**Skills required:**
- `polytool-status` — queries PolyTool CLI for state (positions, fills, gate status)
- `polytool-grafana` — queries Grafana/ClickHouse for metrics via MCP or direct SQL
- `polytool-dev-logs` — greps recent dev logs for status summaries
- `polytool-files` — reads specific files (CURRENT_DEVELOPMENT.md, CURRENT_STATE.md, specific dev logs)

**Messaging:**
- Telegram OR Discord bot connected to Hermes gateway
- Allowlist: operator's Telegram/Discord user ID only (DM-based auth)
- No command approval required for read-only queries; approval required for any action

**Security boundaries:**
- Read-only by default
- No ability to execute trades, start/stop bots, or modify state
- Kill switch action allowed ONLY if wrapped in strict command approval (Hermes has command allowlist)

### Track 2: RIS-Worker Skill (required for Phase 2B)

Goal: Replace custom `polytool-ris-worker` package with Hermes skill.

**Skill: `polytool-ris-worker`**

Structure:
```
~/.hermes/skills/polytool-ris-worker/
├── SKILL.md           # Skill definition, triggers, and procedure
├── worker.py          # Python entry point: fetch → evaluate → export
├── config.json        # Sources, schedule, API key paths
└── README.md          # Friend-facing docs
```

SKILL.md describes to Hermes:
- When to invoke (scheduled trigger: every 4-12 hours per source)
- What to do (fetch from sources, evaluate via Gemini, write scored JSON to sync folder)
- What tools to use (HTTP fetch, Python subprocess for worker.py)
- How to report (Discord embed on failure, no alert on success unless daily summary)

worker.py is a standalone Python module that:
- Reads config.json for sources, API keys, sync folder path
- Fetches documents from configured sources (ArXiv, Reddit, YouTube, Blog/RSS, GitHub)
- Calls Gemini Flash for evaluation (reuses `packages/research/evaluation/providers.py` logic, stripped to minimum dependencies)
- Writes scored JSON packages to sync folder with content-hash-based names
- Returns structured summary to Hermes (docs_fetched, docs_evaluated, docs_accepted, etc.)

**Dependency minimization:**
- No Docker required
- No ClickHouse required
- No n8n required
- No Grafana required
- Just Python + Gemini SDK + feedparser + requests + PolyTool evaluation provider module

**Scheduling:**
- Hermes cron: `"Every 4 hours, run polytool-ris-worker skill with source=academic"`
- Different source schedules per Hermes's natural-language cron
- Failure: Discord embed to pre-configured channel

### Track 3: Operator Machine Import Command (required, no Hermes)

Goal: Import scored packages from sync folder into main RIS knowledge store.

Built on operator machine. Does NOT use Hermes. Pure Python/CLI.

```
polytool research-import-worker --folder /path/to/sync/folder
```

- Reads all new JSON packages in sync folder
- Dedups via content hash
- Imports accepted docs into ChromaDB + SQLite
- Updates budget tracker with friend's provider events
- Writes summary to daily digest

---

## Integration Sequence (Architect Prompt Generation Order)

When triggers fire, Architect should generate prompts in this order:

### Stage 1: Prerequisites (Operator Machine)

1. **Stage 1-A: Verify `packages/research/evaluation/providers.py` is production-ready from RIS Phase 2A WP2.** If not complete, stop. Phase 2B cannot ship without Phase 2A.
2. **Stage 1-B: Build `polytool research-import-worker` CLI** (part of Track 3). Requires sync folder path argument, reads JSON packages, imports to knowledge store.
3. **Stage 1-C: Set up sync folder infrastructure.** Default: Google Drive shared folder mounted via Drive sync on operator machine. Alternative: Git repo or rsync over SSH.

### Stage 2: Hermes Installation (Worker Machine)

4. **Stage 2-A: Document Hermes installation for friend machines.** One-liner plus Gemini API key config plus sync folder config. Include Windows/macOS/Linux variants.
5. **Stage 2-B: Build `polytool-ris-worker` skill** — SKILL.md + worker.py + config.json template.
6. **Stage 2-C: Write friend install guide.** 5-minute path from zero to running worker.

### Stage 3: First-Friend Integration Test

7. **Stage 3-A: Install Hermes + skill on one friend's machine.** Start simple — single source (e.g., ArXiv only).
8. **Stage 3-B: Observe for 48 hours.** Confirm: fetches run on schedule, evaluations use friend's Gemini quota, scored JSON appears in sync folder, operator machine imports successfully, Discord alerts on failure work.
9. **Stage 3-C: Add remaining sources and 2nd friend.** Gradual scaling.

### Stage 4 (optional): Operator Hermes Instance

10. **Stage 4-A: Install Hermes on operator machine.** WSL2 if Windows.
11. **Stage 4-B: Build operator query skills** (`polytool-status`, `polytool-grafana`, `polytool-dev-logs`, `polytool-files`).
12. **Stage 4-C: Configure Discord/Telegram bot + allowlist.**
13. **Stage 4-D: Test read-only queries.**

---

## Architect Prompt Generation Notes

When generating prompts from this guide:

- **Apply workflow-refresh rules.** Each prompt gets HEADER with ACTIVE: line, must match RIS Operational Readiness feature.
- **Split by stage boundaries.** Stage 1 is Python code work (Claude Code). Stage 2 is skill authoring + docs (mix of CC + Codex). Stage 3 is operator runbook (not a code prompt — Director execution). Stage 4 is setup + skill authoring.
- **Do not combine operator Hermes + friend worker Hermes setup in a single prompt.** They are independent.
- **Explicitly exclude orchestration use cases from any prompt.** SKILL.md definitions and Hermes config must not include "run Claude Code" or "query ChatGPT" actions. If Director requests these capabilities, Architect must refuse and explain why.
- **Always include "no code changes to live execution paths" constraint.** Hermes is NOT on the live bot code path.

---

## Risk and Guardrails

**Security:**
- Friend machines get only their own Gemini API key. No PolyTool secrets.
- Sync folder is one-way (friend writes, operator reads). Friends cannot import to operator's ChromaDB directly.
- Content hash dedup prevents malicious or accidental re-imports.
- Operator import command validates JSON schema before accepting packages.

**Cost:**
- Hermes itself: free, open source, MIT.
- Friend compute: Hermes runs in ~100MB RAM idle. Fine on any modern laptop. On Modal/Daytona, hibernates to near-zero when idle.
- LLM: Friend uses their own free Gemini tier. No cost to operator.
- Storage: Sync folder typically Google Drive free tier (15GB plenty).

**Privacy:**
- Friend's Hermes only ever sees: sources from config, Gemini responses, scored JSON it wrote. No PolyTool trading data, no strategy configs, no capital info.
- Discord/Telegram bot on operator side: DM-only, allowlisted to operator user ID.

**Failure modes:**
- Friend machine goes offline → scheduled fetches simply don't run → import command sees no new files. No impact on operator machine.
- Friend Gemini quota exhausted → worker reports "budget_exceeded" → Discord alert → skill pauses until next day.
- Hermes process crashes → restart via systemd (Linux) / launchd (macOS) / Task Scheduler (Windows). Standard.
- Sync folder conflicts → content hash dedup handles it.

**Known issues to validate:**
- Hermes native Windows is NOT supported. Operator machine setup requires WSL2 or skip Track 4.
- Hermes CLI is `hermes` binary; `install.sh` does platform detection.
- Hermes v0.10.0 released 2026-04-16; expect rapid minor versions.
- SKILL.md standard is agentskills.io-compatible; cross-pollinates with Claude Skills ecosystem.

---

## What This Guide Does NOT Cover (explicitly)

- **Phase 2A changes.** None. Phase 2A stays on CC/Codex with n8n per ADR 0013.
- **Live bot automation via Hermes.** Not allowed. Live execution remains pure Python.
- **Architect replacement.** Not allowed. Hermes does not drive Claude Code or Codex from messaging.
- **Replacing n8n.** Not for Phase 2A. Possibly revisit in later phase once Hermes track record is established.
- **Skill marketplace integration (agentskills.io).** Nice-to-have for later; not part of initial Phase 2B scope.

---

## Cross-References

- [[09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP]] — Phase 2B WPs being replaced/simplified by this guide
- [[09-Decisions/Decision - Agent Parallelism Strategy for RIS Phase 2]] — parent decision record (updated 2026-04-22)
- [[12-Ideas/Idea - Hermes Agent Platform Evaluation]] — original Hermes evaluation (partially superseded)
- [[09-Decisions/Decision - Workflow Harness Refresh 2026-04]] — governance framework
- [[09-Decisions/Decision - RIS n8n Pilot Scope]] — ADR 0013 (why n8n stays for Phase 2A)
- CURRENT_DEVELOPMENT.md — Active Features gate
- AGENTS.md — engineering standards
- [Hermes v0.10.0 release notes](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.4.16)
- [Hermes documentation](https://hermes-agent.nousresearch.com/docs/)


---

## Update 2026-04-22 — Provider Strategy Revised

Director confirmed constraints:
- Default provider: Gemini Flash (Google account required)
- Hardware floor: 16GB RAM, Qwen3-14B class models if local fallback used
- **Models must be swappable via config** — if a friend doesn't have a Google account, switching providers should be one-line change

This section supersedes any earlier mention of "Ollama as primary" or "Gemini-only" strategy.

### Provider Architecture

Friend worker reads `config.json` to determine provider. Base class `OpenAICompatibleProvider` from RIS Phase 2A WP2-A handles any OpenAI-compatible endpoint. Swapping providers = editing two fields.

**Supported providers (all free or near-free):**

| Provider | Account type | Free tier | Quality | Primary use |
|---|---|---|---|---|
| Gemini Flash | Google account | 1,500 req/day | Excellent | **Default.** Friends with Google accounts. |
| OpenRouter free models | Email signup | Rate-limited free | Good | Fallback for friends without Google account. |
| Groq free tier | Email signup | 30 req/min | Good, very fast | Secondary fallback. |
| Ollama Cloud | Ollama account | Free tier | Good | Tertiary option if friend prefers. |
| Ollama local | No account | 100% free | Varies by model | Last resort. Requires 16GB RAM + model download. |

**Hardware floor:** 16GB RAM minimum. Only enforced if friend chooses Ollama local. Cloud-hosted providers (Gemini/OpenRouter/Groq/Ollama Cloud) have no hardware requirement.

### Config File Design

Each friend gets a `config.json` file in their Hermes skill directory:

```json
{
  "sync_folder": "/path/to/polytool-ris-sync",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "api_key_env": "GEMINI_API_KEY",
  "sources": ["academic", "reddit"],
  "budget": {
    "daily_request_cap": 1200,
    "reserve_margin": 300
  }
}
```

To switch providers, friend edits two fields:

```json
{
  "provider": "openrouter",
  "model": "meta-llama/llama-3.3-70b-instruct:free",
  "api_key_env": "OPENROUTER_API_KEY"
}
```

No code changes. Restart Hermes worker.

### Provider-Specific Setup Docs

The friend install guide includes a branching flow:

```
Step 3: Choose your LLM provider

[A] I have a Google account → use Gemini (recommended, highest free quota)
    → Follow Gemini setup (5 min)
[B] I prefer not to sign up for Google → use OpenRouter
    → Follow OpenRouter setup (3 min)
[C] I want to run everything locally → use Ollama local
    → Follow Ollama setup (20-60 min depending on download speed)
```

Each path is a separate 1-page doc. Friend reads only the one they chose. No flipping between options.

### Scoring Threshold Adjustments

Different providers have different quality ceilings. Since the friend worker exports scored JSON packages (not raw documents), the operator machine import step can apply provider-aware threshold adjustments.

| Provider class | Default GREEN threshold | Default YELLOW range |
|---|---|---|
| Gemini Flash | ≥3.5 (per original scoring policy) | 2.5–3.5 |
| OpenRouter free / Groq free | ≥3.5 (assumed comparable) | 2.5–3.5 |
| Ollama Cloud | ≥3.75 (one-step stricter) | 2.75–3.75 |
| Ollama local (any model) | ≥4.0 (two-step stricter) | 3.0–4.0 |

Written to scored package metadata so operator import can sort. Operator reviews first N docs from each new provider+model combo to calibrate before raising trust.

### Quality Calibration Loop

Every 100 docs accepted from a given friend+provider combo, operator machine runs a sample through a second evaluation pass using Gemini Flash (as reference standard). If agreement is <80%, the threshold for that friend's setup is raised one step. If agreement is >95% for 300+ docs, the threshold may be relaxed one step.

This means Friend C running Ollama local with a weak model doesn't pollute the knowledge store — their threshold stays high, and the calibration loop catches drift.

### Stage 2-B Skill Scope Update

The `polytool-ris-worker` skill now includes:
- `worker.py` — provider-agnostic, reads config.json, imports evaluator from packages/research/evaluation
- `providers/` — thin wrappers for each supported provider (Gemini, OpenRouter, Groq, Ollama Cloud, Ollama local)
- `config.sample.json` — template showing all fields
- `SETUP-GEMINI.md`, `SETUP-OPENROUTER.md`, `SETUP-GROQ.md`, `SETUP-OLLAMA-LOCAL.md` — per-provider setup docs
- `README.md` — overview plus the Step 3 branching flow above

### Architect Prompt Generation Note

When Architect generates prompts for Stage 2-B, the default provider wiring prompt should:
- Require that all supported providers (Gemini, OpenRouter, Groq, Ollama Cloud, Ollama local) work from the same worker.py with only config.json changes
- Require per-provider test cases in the skill's tests/
- Forbid hard-coded provider names outside the provider factory

### Impact on Phase 2A

Minimal. Phase 2A WP2 (Cloud LLM Providers) already builds the `OpenAICompatibleProvider` abstraction. One addition:
- WP2 should include OpenRouter and Groq as first-class subclasses, not just Gemini + DeepSeek. This is ~30 min of additional work. Architect should note this in the WP2 prompt generation.



---

## Update 2026-04-22 Evening — Auto-Install + GitHub Sync (Stretch Path)

Director asked whether Phase 2B could extend to fully automated friend setup with GitHub-based data sync ("friend runs one command, walks away, data appears in operator's knowledge store automatically"). Answer: yes, possible. Staged as enhancement path AFTER WP6 base completes.

### Why Staged (Not Day-One)

Director does not yet have even one friend committed to Phase 2B. Building auto-install before the manual-install base case is over-engineering. The staged path ships incremental value and can be stopped at any stage if friend count stays small.

### Stage 1 (WP6, base) — Manual Interactive Install

This is the original Phase 2B plan. Friend runs `polytool-ris-setup.sh`, answers prompts, verifies first run. Sync via Google Drive OR GitHub (friend's choice). Ship first, observe one friend for 48h, iterate.

### Stage 2 (WP7, new) — GitHub-First Sync

Replace Google Drive assumption with GitHub as default sync mechanism. Architecture:

- Operator creates `polytool-ris-data` repo (private or public — scored docs aren't secret)
- Each friend gets a dedicated branch (`friend-<alias>/data`)
- Friend's worker commits scored JSON packages to their branch per run
- Fine-grained PAT per friend, scoped to write-only on their own branch
- Batch commits: 1 commit/day/friend with N files, not 1 commit/file
- Operator machine: `polytool research-import-worker --git-remote <url>` pulls from all branches, imports via existing content-hash dedup

**Advantages over Drive:**
- Natural version history
- No merge conflicts (branches don't overlap)
- Friend-visible contribution record
- Instant revocation via token
- GitHub Actions validates JSON schema on each commit
- Works over restrictive networks that block Drive

**Cost:** $0 (GitHub free tier handles the volume for realistic friend count).

**Effort:** 1-2 days.

### Stage 3 (WP8, new) — One-Touch Auto-Install

Installer script handles everything after OS-level prerequisites (WSL2 on Windows). Flow:

```
curl -fsSL <operator-signed-url>/polytool-ris-install.sh | bash
→ Detects OS, installs Hermes via official install.sh
→ Downloads polytool-ris-worker skill from pinned git commit
→ Prompts ONLY for: LLM provider choice + API key
→ Generates skill config.json
→ Sets up systemd (Linux) / launchd (macOS) / Task Scheduler (Windows/WSL)
→ Runs single test evaluation to verify end-to-end
→ Prints "you're done" + Discord channel link for status
```

Friend effort: one command, 2-3 interactive prompts, walk away.

**Security considerations that require real attention:**
- Install script must be operator-signed (GPG) or served from operator-controlled HTTPS endpoint with pinned TLS cert
- Skill version pinning — friend does NOT auto-update without operator-approved manifest
- Auto-update policy: opt-in, operator publishes signed manifest of approved skill versions
- Scoped GitHub PAT generation — friend gets a token limited to their branch, cannot escalate
- Discord bot allowlist — friend's Hermes can ONLY notify operator's pre-configured channel

**Autorecovery requirements:**
- Hermes service auto-restart on crash (systemd Restart=always)
- Quota tracking persists across restarts (write to disk per successful call)
- Graceful handling of: friend machine sleep/wake, network drops, API quota exhaustion, expired tokens
- Daily heartbeat to operator — if no heartbeat in 48h, Discord alert

**Effort:** 2-3 days.

### Stage 4 (WP9, optional) — Operator Fleet Dashboard

Grafana dashboard showing all friend workers:
- Last successful run per friend
- Daily doc counts per friend
- Quota usage per friend
- Recent failures per friend
- Knowledge store growth attributable to each friend

Built on existing Grafana + ClickHouse stack. Friend workers ping a minimal `/api/friend-heartbeat` endpoint on operator machine (simple FastAPI route). ClickHouse stores heartbeats + aggregated metrics.

**Effort:** 1 day.

### Updated Phase 2B Sequence

```
[Phase 2A complete + one friend agrees]
         │
         ▼
WP6: Manual install, Drive sync, one friend (BASE, ships first)
         │
         ▼
[Base case works, 2+ friends want in, OR Drive is wrong for network]
         │
         ▼
WP7: GitHub-based sync (1-2 days)
         │
         ▼
[3+ friends, each install is painful]
         │
         ▼
WP8: Auto-install (2-3 days)
         │
         ▼
[Scale past 5 friends, need visibility]
         │
         ▼
WP9: Fleet dashboard (1 day)
```

### Decision Criteria for Each Stage

- **WP7 trigger:** Google Drive sync proves painful (sync delays, conflicts) OR second friend requests different storage
- **WP8 trigger:** Manual install takes >15 min for a non-technical friend, OR 3rd friend is recruited
- **WP9 trigger:** Friend count >= 5, OR operator spends more than 10 min/week checking individual friend status

Do NOT build Stages 7/8/9 pre-emptively. Each has a clear trigger based on observed pain.

### Honest Risks

- **Auto-install attack surface.** If install script is compromised, all friend machines run compromised code. Mitigations: GPG signing, pinned versions, scoped tokens. But attack surface is real.
- **GitHub private repo costs beyond free tier.** Unlikely at realistic friend counts but worth monitoring.
- **Autorecovery edge cases.** "Friend leaves laptop sleeping for a month" is hard to handle gracefully. Worth testing against real long-idle scenarios.
- **Quota exhaustion coordination.** If all friends use same Gemini tier day (unlikely since they use their own keys), coordinated quota exhaustion. Not actually a risk with separate keys.

### What This Does NOT Change

- WP6 base still ships first. Auto-install is NOT Day One.
- Trigger conditions for starting Phase 2B unchanged.
- Provider strategy unchanged (Gemini default, OpenRouter/Groq/Ollama fallbacks).
- Operator machine role unchanged (pulls, imports, calibrates).

### Architect Prompt Generation Impact

When Architect generates prompts for Phase 2B stages 7/8/9, each stage's prompt must:
- Verify prior stage's acceptance criteria passed (WP7 requires WP6 stable for 2+ weeks; WP8 requires WP7 stable; etc.)
- Include the security considerations listed above
- NOT combine stages into a single prompt
- Reference this section explicitly

### Cross-References
- [[Hermes Agent - PolyTool Integration Setup Guide]] — parent doc
- [[RIS_OPERATIONAL_READINESS_ROADMAP]] — Phase 2B placement



---

## Update 2026-04-22 Evening #2 — Manual-With-GitHub as WP6 Base (Major Correction)

Director proposed: instead of Hermes-continuous as the default, offer a simpler manual path first — friend runs a one-shot contribution script whenever they want, script commits results to GitHub, operator machine pulls on its own schedule. Hermes becomes an optional upgrade for friends who want "leave it running" continuous mode.

This is a significantly better framing than the previous Hermes-first approach. Simpler base case, lower friend burden, less operator complexity, strict subset of the original architecture. Hermes remains valuable for committed friends but is no longer on the critical path.

### Why This is Better

- **Ship WP6 in ~1 day instead of ~3 days.** No Hermes skill to write, no background service, no Discord gateway for status.
- **Zero friend hardware requirements.** 8GB laptop works fine for a one-shot run if friend uses cloud provider.
- **No Windows WSL2 requirement** unless friend chooses Ollama local.
- **No "friend's machine fell over at 3am" failure modes.** If script exits 0, commit happened. Proof-of-success is in git.
- **Friend onboarding is genuinely zero-touch:** clone → run → done.
- **Attack surface drops to near-zero.** Nothing persistent on friend's machine.

### Updated Phase 2B Work Packets

**WP6 (revised base) — Manual One-Shot Contribution Script**

- **WP6-A:** Build `polytool-ris-contribute` CLI or standalone script. Single command. Flow:
  1. Load config (sync repo URL, provider, API key from env)
  2. Fetch N documents from configured sources (defaults: 50 across all enabled sources)
  3. Evaluate each via configured provider (imports from `packages/research/evaluation/providers.py`)
  4. Write scored JSONs to local temp dir
  5. `git clone` friend's branch of `polytool-ris-data` repo
  6. Copy JSONs in, commit with message `"batch: N docs from <friend-alias> at <timestamp>"`, push
  7. Print summary, exit
- **WP6-B:** `polytool research-import-worker` on operator machine. Pulls all friend branches periodically (cron or manual), imports via existing content-hash dedup. Same command whether data came from manual or continuous path.
- **WP6-C:** Friend install guide. Three paths (Gemini/OpenRouter/Ollama-local). Under 5 minutes from zero to first commit.
- **WP6-D:** Test with one friend. Friend runs the script three times over a week. Verify each run produces a clean commit and operator imports successfully.

**Scope removed from WP6 base:**
- No Hermes skill
- No background service setup
- No Discord gateway
- No cron configuration
- No "health monitoring" (git commits are the monitoring)

**WP7 (new optional upgrade) — Hermes-Continuous for Committed Friends**

- **Trigger:** At least one friend has run the manual version for 2+ weeks AND explicitly asks for continuous mode.
- **Scope:** Wrap the same `polytool-ris-contribute` logic in a Hermes skill that runs on a schedule. Output format identical (same JSON structure, same git commits). Operator's import CLI doesn't know or care which mode produced the data.
- **Additional setup:** Hermes install, systemd/launchd/Task Scheduler setup, quota persistence across restarts, Discord alerts on failures.
- **Effort:** 2-3 days.

**WP8 / WP9 / fleet dashboard:** Unchanged from previous plan but only relevant if WP7 gains adopters.

### Provider Strategy (unchanged)

- Default: Gemini Flash (Google account, 1,500 req/day free)
- No-Google-account: OpenRouter free models (email signup)
- Fast-inference: Groq free tier
- Local-only: Ollama local (16GB RAM)
- Cloud-hosted non-Google: Ollama Cloud (Ollama account)

Swap via two config fields. No code change.

**Clarification vs earlier draft:** "Ollama" covered TWO different products:
- **Ollama local** — runs on friend's machine, no network, no account, needs hardware
- **Ollama Cloud** — hosted on Ollama infrastructure, requires Ollama account, network-dependent

These are distinct rows in the provider matrix.

### Updated Sequence

```
[Phase 2A complete + one friend agrees]
         │
         ▼
WP6: Manual one-shot contribution script + import CLI (1 day)
         │
         ▼
[2+ weeks of manual operation, friend asks for continuous mode]
         │
         ▼
WP7 (optional): Hermes-continuous wrapper (2-3 days)
         │
         ▼
[3+ continuous friends]
         │
         ▼
WP8 (optional): Auto-install for continuous path (2-3 days)
         │
         ▼
WP9 (optional): Fleet dashboard (1 day)
```

### What Doesn't Change

- Phase 2A scope (WP1-WP5 unchanged except the 30-min WP2 addition for OpenRouter/Groq subclasses)
- Phase 2B trigger conditions (Phase 2A complete + one friend)
- Provider strategy
- Quality calibration loop
- GitHub as sync layer (now mandatory, not optional)

### Hermes Status After This Correction

Hermes is NO LONGER on the critical path for Phase 2B. Hermes is:
- Still valuable for friends who want continuous operation (WP7)
- Still the right choice for operator remote interface (optional Track in the setup guide, unchanged)
- Still the right platform for Phase 2+ scheduling/automation when that phase arrives
- NOT required for the distributed RIS base case

The setup guide's "Track 2: RIS-Worker Skill" section still applies but becomes WP7 content, not WP6.

### Risks of Manual-First

- **Low throughput.** Friend runs once a week → low data rate. Acceptable if operator expectations are calibrated. If operator wants high throughput immediately, WP7 earlier.
- **Friend forgetfulness.** Most friends will run it once or twice then forget. Mitigation: periodic friendly nudge from operator (not automated).
- **No liveness signal.** Without continuous running, operator has no way to know if friend is "still participating" vs "lost interest." Could be desirable (low pressure) or undesirable (no visibility). Direction depends on operator preference.

### Governance

- CURRENT_DEVELOPMENT.md (when Phase 2B becomes Feature 3): title should be "RIS Phase 2B — Manual Distributed Contribution" to reflect base case.
- Original "RIS Phase 2B — Hermes Distributed Workers" title moves to WP7.
- Architect custom instructions line about Hermes for WP6 should be corrected: Hermes is for WP7+, not WP6 base.

### Cross-References
- [[RIS_OPERATIONAL_READINESS_ROADMAP]] — parent roadmap (2026-04-22 Late update applies; this further revises Phase 2B)
- [[Decision - Agent Parallelism Strategy for RIS Phase 2]] — Hermes sequencing
