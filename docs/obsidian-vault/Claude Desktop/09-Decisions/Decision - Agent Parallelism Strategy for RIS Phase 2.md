---
tags: [decision, agent-workflow, hermes, parallelism, ris-phase-2]
date: 2026-04-22
status: active
supersedes-considerations-in: [[12-Ideas/Idea - Hermes Agent Platform Evaluation]]
---

# Decision — Agent Parallelism Strategy for RIS Phase 2

## Context

RIS Operational Readiness Roadmap (2026-04-22 draft) calls for three parallel work streams during Phase 2A (WP2, WP3, WP4) and a distributed worker architecture in Phase 2B (WP6). Operator wants to leverage multiple agents to run work in parallel. Hermes Agent (NousResearch, 101k stars, MIT, v0.10.0) was evaluated as a potential third execution lane.

The question: add Hermes for Phase 2A parallelism, or sequence it to Phase 2B where it's uniquely suited?

## Options Considered

**Option 1 — 3 code agents equally** (CC#1 + CC#2 + Codex + Hermes-as-coder): Max parallelism. Max orchestration cost. Hermes is a freight train for groceries when used as a coding agent — underutilizes its messaging/cron/subagent runtime.

**Option 2 — Specialized roles today** (CC for code; Hermes for Discord/cron/distributed): Plays to each tool's strength. But Phase 2A's Discord/scheduling work is already being done in n8n per ADR 0013. Swapping n8n for Hermes mid-Phase-2A means shipping Phase 2A twice.

**Option 3 — Start with CC#1 + CC#2 + Codex, add Hermes at Phase 2B**: Proves 3-agent parallelism on familiar tools first. Adds Hermes where it's uniquely suited (distributed workers, messaging gateway, cron on friend machines). 2-3 week horizon.

## Decision

**Option 3.**

## Reasoning

1. **The RIS roadmap draws the line.** Phase 2A is code-heavy (edit Python, run tests, verify artifacts). Phase 2B is runtime-heavy (worker process on friend machines, cross-machine sync, Discord embeds). The roadmap itself sequences these.
2. **Two-variable risk.** Going from (CC + Codex) to (CC#1 + CC#2 + Codex) introduces orchestration overhead. Adding Hermes on top introduces two new variables at once. If parallelism breaks, you can't isolate which change caused it.
3. **n8n already owns the Phase 2A scheduling/Discord work.** Per ADR 0013 (RIS n8n Pilot Scope), unified RIS workflow handles it. Replacing n8n mid-phase doubles work.
4. **Phase 2B is where Hermes earns its place convincingly.** WP6 reads like Hermes's product specification: lightweight worker, scheduled fetch, messaging on failure, cross-machine sync. You'd reinvent 60% of Hermes building WP6 in pure Python.
5. **Sequencing, not deferring.** Hermes gets evaluated and set up at a specific trigger (Phase 2A complete + about to start WP6), not "someday."

## Immediate Implications

- For Fee Model Overhaul (current Active Feature 2): keep CC + Codex. No change.
- For RIS Phase 2A (activates when Fee Model closes, fills Slot 3 per [[RIS_OPERATIONAL_READINESS_ROADMAP]]):
  - WP1 (Foundation Fixes): single CC session, Day 1
  - WP2 (Cloud Providers): CC#1 primary, Days 2-4
  - WP3 (n8n Visual): CC#2 or Codex, Days 3-5
  - WP4 (Monitoring): Codex primary (DDL + JSON work), Days 4-6
  - Three parallel streams, three lanes: CC#1, CC#2, Codex. No Hermes yet.
- For RIS Phase 2B (after Phase 2A ships): Hermes evaluation triggered. Open dedicated Hermes setup chat.

## Architect Instruction Addendum

The Architect custom instructions need one awareness sentence added before the PMXT chat closes, so the next RIS prompt generator knows this decision exists. Proposed addition to the AGENT SELECTION section:

> For RIS Phase 2A (WP1-WP5): use CC/Codex. For RIS Phase 2B (WP6 distributed workers): evaluate Hermes Agent (NousResearch) before building from scratch. See [[Decision - Agent Parallelism Strategy for RIS Phase 2]].

This is a 2-line addition, not a rewrite. Same pattern as the Hermes-for-Phase-2+ awareness we already agreed to add.

## Phase 2B Hermes Resume Trigger (explicit)

Open a Hermes setup chat when ALL of these are true:
1. Fee Model Overhaul is complete (Feature 2 moved to Recently Completed)
2. RIS Phase 2A is complete (WP1-WP5 acceptance criteria all passed)
3. WP6 is the next planned work in the Director's sequence
4. At least one friend has expressed willingness to run a RIS worker

Don't open the Hermes chat before all four conditions are met. This is the forcing function that prevents speculative tool adoption.

## Cross-References

- [[09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP]] — the roadmap this decision supports
- [[09-Decisions/Decision - Workflow Harness Refresh 2026-04]] — parent framework
- [[09-Decisions/Decision - RIS n8n Pilot Scope]] — ADR 0013 (why n8n stays during Phase 2A)
- [[12-Ideas/Idea - Hermes Agent Platform Evaluation]] — original Hermes evaluation, now superseded by this decision
- [[11-Prompt-Archive/2026-04-21 Architect Custom Instructions v2]] — needs AGENT SELECTION addendum (see above)
- CURRENT_DEVELOPMENT.md Rule 2 — First Dollar Before Perfect System



---

## Update 2026-04-22 — Correction on Hermes role

Initial framing of "three execution lanes for parallel development" was based on a misunderstanding. Hermes is NOT a coding agent. It is a personal-assistant runtime (messaging gateway + cron + persistent memory + skills + subagents). Re-reviewed the repo and corrected the framing.

### What this changes

- **Phase 2A plan unchanged.** CC#1 + CC#2 + Codex was and remains the right answer. Hermes plays no role.
- **Phase 2B plan simplified.** Instead of building the custom `polytool-ris-worker` package from scratch, install Hermes on friend machines and run a RIS-worker skill inside it. Phase 2B WPs reduce to: (a) write the RIS worker skill, (b) build the import CLI on your machine, (c) friend install guide, (d) test.
- **Orchestration clarification.** Hermes CAN be told via Discord/Telegram to trigger Claude Code (shell out to `claude -p`). It SHOULD NOT be used this way — it bypasses the Architect gate and breaks the workflow refresh. Hermes is for observing, summarizing, and triggering pre-defined safe tasks. Not for driving other agents.
- **Operator interface = new optional use case.** A Hermes instance on operator's machine enables "check PolyTool status from phone via Discord/Telegram." Not required for Phase 2B to work, but often bundled.

### What does NOT change

- Phase 2A sequencing and agent allocation (CC#1 + CC#2 + Codex)
- Hermes trigger point (Phase 2B start, all four conditions as listed above)
- Forcing function preventing speculative Hermes setup

### Updated Phase 2B build scope (supersedes "Work Packets" section of roadmap)

- **WP6-A (revised):** Write `~/.hermes/skills/polytool-ris-worker/SKILL.md` — the skill Hermes invokes to fetch from sources, evaluate via Gemini, export scored JSON to sync folder.
- **WP6-B (unchanged):** Build `research-import-worker` CLI command on operator machine.
- **WP6-C (simplified):** Friend setup guide collapses to: install Hermes, install skill, configure Gemini key + sync folder.
- **WP6-D (unchanged):** Test with one friend machine.

Estimated effort reduction: 40-50% vs custom Python worker path.
