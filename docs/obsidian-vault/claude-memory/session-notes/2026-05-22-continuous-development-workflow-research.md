---
title: "Continuous Development Workflow — Research Thread"
type: session_note
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
session_date: 2026-05-22
participants: [operator, claude]
tags: [session-note, workflow, research-thread, continuous-development]
---
# Continuous Development Workflow — Research Thread

## What This Is

Ongoing research and discussion thread on Aman's vision for a 24/7 PolyTool development workflow. Goal: continuous development, testing, and planning while Aman is away or sleeping, with Discord notifications for status and decision points. Aman checks in daily for brainstorming and orchestration.

**Approach:** Aman explicitly asked Claude to slow down, not jump to conclusions, and use deep research via GLM/ChatGPT to ground the discussion in current (May 2026) tooling reality. The AI dev landscape has moved significantly since Claude's January 2026 training cutoff.

This note will be appended to as research returns and we iterate.

---

## What Claude Already Knew (and Was Wrong About)

First response over-constrained the problem space. Assumptions that turned out to be outdated or wrong:

- **"Conversational agents can't run 24/7"** — partly false. `/bg` command and Agent View in Claude Code (added since Jan 2026) allow background sessions. Agent SDK gets a separate monthly credit starting June 15, 2026 on subscription plans. `claude -p` headless mode is mature.
- **"Hermes ≠ orchestrator was settled"** — Aman's past self decided against Hermes driving Claude Code via Discord. Worth revisiting given new patterns, but the decision still stands as a starting constraint.
- **"Architect overclaim must be solved manually"** — there are now dedicated tools: AgentDoG, AgentGuard, agenttrace. Schema-driven verification has matured.
- **"WIP=3 is the right governance primitive"** — possibly still right, but unexamined against current multi-agent orchestrator patterns (Emdash, Cyrus, Claude-Flow, etc.).

---

## Quick Web-Search Grounding (2026-05-22)

Selected findings from initial searches to anchor the research:

- **Claude Code `/bg` + Agent View** (April-May 2026) — background session management built into Claude Code.
- **Claude Agent SDK** — separate monthly credit on subscription plans starting 2026-06-15. May enable headless `claude -p` workflows without burning interactive limits.
- **"Remote Control" + Dispatch** (Q1 2026 Anthropic release) — REST API for Claude Code, scheduling/routing layer for multi-instance dispatch.
- **Sub-agents pattern** — separate context windows for research/exploration without polluting main session.
- **Git worktree-based parallel agents** — Emdash, Cyrus, others ship this as standard primitive.
- **22+ CLI agents** available (Claude Code, Codex, Gemini CLI, Cursor, Amp, Goose, Kiro, Pi, Qwen Code, Droid, CCR, Hermes Agent, OpenCode, others).
- **"Context engineering"** has crystallized as a discipline. CLAUDE.md / AGENTS.md / SOUL.md are the recognized primitive.
- **Solo-founder "one-person unicorn" pattern documented** — evening queue, overnight execution, morning review. Real warning: "The most successful solo founders I know right now are actually just exhausted bottlenecks."

---

## Open Questions to Research (Pre-Prompt Draft)

Six research directions identified. Each maps to a deep-research prompt for GLM-5 or ChatGPT (specified below). Sequencing: Tier 1 first (essential), then Tier 2 (informed by Tier 1).

### Tier 1 — Essential foundation

**R1: Anthropic native capabilities for unattended workflows (Pro plan budget)**
What can Claude Code, Agent SDK, Skills, Hooks, Sub-agents, and Remote Control actually do as of May 2026, on a $20/mo Pro plan vs requiring Max plan or API? Specific focus: composable patterns for overnight unattended execution.

**R2: Multi-agent orchestrator landscape — survey for solo/small-team**
Battle-test comparison: Emdash, Cyrus, Claude-Flow, Swarms, PraisonAI, OpenClaw, agent-zero. For each: setup cost, learning curve, free/paid tier, work it handles well, breakdown modes. Particular interest: coordinators of Claude Code + Codex + Gemini CLI with git worktree isolation, and which ones don't require enterprise pricing.

**R3: Verification & anti-overclaim patterns for autonomous coding agents**
How are teams actually solving the "AI confidently claims completion when work isn't done" problem in production? Tools: AgentDoG, AgentGuard, agenttrace, eval-driven dev, schema-enforced outputs. Case studies of teams that diagnosed and fixed overclaim. Includes the question: how does Codex-adversarial-review-loop pattern compare to dedicated verification tools?

### Tier 2 — Informed by Tier 1 findings

**R4: Self-improving / autoresearch loops in practice**
Karpathy-style autoresearch and descendants in production. Where deployed, failure modes documented. Adjacent: autonomous test generation, AI-driven parameter optimization, agentic benchmark sweeps. Specific interest: examples in algorithmic trading, ML research, quant — domains with quantifiable success metrics. Realistic time-to-improvement ratios.

**R5: Async approval & notification patterns for solo operators**
How do solo founders manage the firehose of agent activity? Discord/Slack bot patterns, digest tools, tiered alerting (info / decision / urgent). Linear-based PR workflows (Cyrus), Notion-as-task-queue. What does the morning check-in look like and how is the queue managed overnight?

**R6: Context & memory engineering for long-running agent fleets**
"Context engineering" as a discipline — patterns (CLAUDE.md, AGENTS.md, MCP-based memory, vector RAG over project history) most effective for keeping multiple parallel/sequential sessions consistent over weeks. Compare: Memarch vs Hermes memory, MemPalace, autoresearch ledger memory, Notion/Linear as state stores. Cross-session continuity without context bloat.

---

## Critical Considerations to Carry Forward

Things Claude wants to flag for ongoing attention regardless of research findings:

1. **Safety-critical code still needs guardrails.** Per existing CLAUDE.md rules: kill_switch.py, risk_manager.py, execution/, EIP-712 signing, order placement get mandatory Codex adversarial review. No autonomous workflow can touch these without explicit gates. This is non-negotiable for any plan.

2. **"Continuous progress" ≠ "Continuous new-feature development."** Tape recording, benchmarks, paper soaks, autoresearch sweeps, scraper jobs, RIS pipelines — these can genuinely run 24/7 with minimal human supervision because outputs are quantifiable. New feature work is different.

3. **Architect overclaim has happened before.** Documented in vault (2026-04-10 RIS Phase 2 audit). Any 24/7 plan must defend against this *better* than current process, not the same.

4. **Bottleneck is work-packet supply, not execution capacity.** Aman has multiple execution lanes. The supply of well-scoped tasks is what runs dry overnight.

5. **The "exhausted bottleneck" warning from solo-founder literature.** Every decision through Aman = scaling problem. Need explicit "what doesn't reach Aman" rules.

---

## Action Items

- [ ] Aman reviews proposed research prompts (file at `/mnt/user-data/outputs/Research-Prompts-Continuous-Workflow.md`)
- [ ] Aman runs Tier 1 prompts (R1, R2, R3) on GLM-5 and/or ChatGPT deep research
- [ ] Claude reviews findings, updates this log, identifies next round of unknowns
- [ ] Run Tier 2 prompts (R4, R5, R6) after Tier 1 synthesized
- [ ] Generate concrete workflow proposal only after all research synthesized

---

## Cross-References

- [[claude-memory/decisions/decision-workflow-harness-refresh-2026-04]] — current workflow primitives this builds on
- [[legacy/Claude Desktop/09-Decisions/Decision - Agent Parallelism Strategy for RIS Phase 2]] — Hermes constraints already decided
- [[claude-memory/session-notes/2026-04-21-workflow-harness-refresh]] — last major workflow session
- [[legacy/Claude Desktop/10-Session-Notes/2026-04-10 RIS Phase 2 Audit Results]] — overclaim case study to defend against
- [[legacy/Claude Desktop/08-Research/Hermes Agent - PolyTool Integration Setup Guide]] — Hermes-not-orchestrator decision
- Research prompts deliverable: `/mnt/user-data/outputs/Research-Prompts-Continuous-Workflow.md`

---

*Active. Updated as research returns.*


---

## Update 2026-05-22 — Research Returned (R1–R6 all six)

All six prompts came back in a single dump. Saved as condensed summary archive: `/mnt/user-data/outputs/Research-Results-Continuous-Workflow-2026-05-22.md` (for manual placement in `08-Research/` — split into R1–R6 files when convenient). Full verbatim outputs preserved.

### Headline shifts vs Claude's pre-research model

1. **24/7 work on Pro plan IS possible** — `/bg` + Agent View + hooks + sub-agents + skills + `/goal` is a real working stack. Claude's earlier "conversational agents can't run 24/7" framing was wrong.
2. **Routines (cloud-scheduled, runs when laptop closed) is on Pro** — the most genuinely autonomous primitive in the current Anthropic stack. Missed in Claude's earlier search.
3. **June 15 Agent SDK credit split** — separate $20/month programmable envelope on Pro. This is the budget change that actually opens the door.
4. **Anthropic ships an OFFICIAL Discord channel plugin** — bidirectional commands and permission relay. Native, not third-party.
5. **The AGENTS.md paper (Feb 2026)** — context files often REDUCE success rates while increasing cost 20%. Validates "less is more" — the current vault structure may already be near-optimal, just needs auditing for bloat.
6. **The architect-overclaim problem has a known protocol** — R3's executor JSON schema + Codex audit JSON schema + 6-condition fail-closed gate is more rigorous than current Codex adversarial review. This is a copy-paste win.

### Research quality assessment

R1, R3, R4, R5, R6 = high quality, well-cited, actionable.
R2 = WEAK. The recommended tool "Ruflo" with conveniently-named "neural-trader" plugin smells like AI-generated marketing copy. Search couldn't verify Emdash, Cyrus, Swarms, PraisonAI, OpenClaw. Treat R2 as candidate list, not validated picks. May need to re-run with stricter sourcing or accept that the orchestrator category is less mature than expected and orchestrators may not be the right primitive at all.

### New unknowns to research

- **R7 candidate**: cost reality check on `claude -p` vs Agent SDK vs background sessions for specific PolyTool workloads. Need numbers, not hand-waves.
- **R8 candidate**: deep dive on Anthropic's Routines specifically — is it included in Pro plan billing? What's the GitHub Actions integration model? Can it run unmodified Python like `claude -p` can?
- **R9 candidate**: validate R2's orchestrator claims via direct repo inspection — does Cyrus actually exist? Emdash? Or is the field smaller than R2 implied?

### Action items updated

- [ ] Aman reviews Claude's section-by-section analysis (in chat)
- [ ] Aman decides: re-run R2 with stricter sourcing, or accept and move on?
- [ ] Aman decides: which R7/R8/R9 to add to research backlog
- [ ] After alignment: identify which patterns from R1/R3/R5/R6 to adopt FIRST (no plan yet)
- [ ] Only after pattern shortlist is locked: design the actual workflow proposal


---

## Correction 2026-05-22 — Plan tier is Claude Max $100/mo, not Pro $20/mo

Aman clarified: subscription is **Claude Max 5x ($100/month)**, not Pro. The research dump and Claude's analysis above were framed against Pro budget assumptions. The Pro-specific numbers in R1, R5, and R6 still describe what's possible, but Aman has roughly **5x that headroom**.

### What this changes (high level)

- **Concurrent background sessions**: R1 capped Pro at "2–3 concurrent before quota fights"; Max can support more parallel `/bg` + Agent View sessions
- **Headless `claude -p` workloads**: less risk of cannibalizing interactive bucket pre-June-15
- **Agent SDK credit on June 15**: Max's credit will be higher than Pro's $20/month (exact figure TBD — Anthropic announced the model but per-tier amounts may differ)
- **Opus access in Claude Code**: Max includes priority access to most advanced features per Anthropic's tier definitions; this was already noted as a "post-profit upgrade path" in the master roadmap, and apparently Aman already made the jump
- **Agent teams for parallel workstreams**: available on Max per the roadmap; opens up multi-agent coordination natively

### What this does NOT change

- The verification/anti-overclaim protocol from R3 still applies — capacity ≠ correctness
- The notification tier discipline from R5 still applies — more capacity makes alert fatigue easier to fall into, not harder
- The AGENTS.md / context engineering caution from R6 still applies — more tokens doesn't mean dumping more context
- Safety-critical code guardrails still apply — Max doesn't change the rules around `execution/`, `kill_switch.py`, `risk_manager.py`
- The architect overclaim problem still exists — this is a process problem, not a capacity problem

### What to verify

- Exact Agent SDK credit amount for Max tier on June 15 (Anthropic announced model; per-tier amounts may need a docs check)
- Whether Routines on Anthropic-managed cloud have any extra capacity on Max vs Pro

This correction is now in Claude's persistent memory and won't need to be re-stated next session.


---

## Update 2026-05-22 — Round 2 Research Returned (R7 + R8)

Both came back from ChatGPT Deep Research; Perplexity was not available for cross-check. Quality is high on both. Archive: `/mnt/user-data/outputs/Research-Results-R7-R8-2026-05-22.md`.

### Headline shifts from R7

1. **Routines bill from subscription usage, NOT the Agent SDK credit.** This is the single biggest correction. The most architecturally convenient outcome (Routines on the new programmable budget) did not happen. Routines drain the same interactive bucket as daytime work. This dampens enthusiasm for Routines as the central 24/7 primitive.
2. **Agent SDK credit on Max 5x = $100/month** (matches plan price). Covers `claude -p`, Agent SDK, GitHub Actions integration. Does NOT cover Routines. Per-user, not pooled. Refreshes monthly, no rollover.
3. **The Discord channel plugin is a local subprocess.** Cannot be used from Routines. For cloud-routine notifications, must use webhook or remote MCP.
4. **Local `claude -p` without `--bare` is the recommended subscription-auth path.** All hooks/skills/MCP/CLAUDE.md auto-loaded. Use `/login` or `claude setup-token` for one-year OAuth.
5. **1-hour minimum schedule interval on Routines.** Sub-hour cadence requires local cron.
6. **Routines = fresh clone, fresh VM every run.** No persistent workspace. Artifacts must go to Git branches/PRs/commits or external systems.
7. **Architectural recommendation: hybrid.** Routines for GitHub-native repo work (code review, dependency refresh, docs sync, deploy verification). Local cron for machine-bound work (Discord, Obsidian, trading checks, sub-hour refresh).

### Headline shifts from R8

1. **Jamie Watters is the closest documented parallel to PolyTool's situation** — solo founder running a 24/7 portfolio agent AND a crypto trading bot ("Trader-7"), with public post-mortems on the same failure modes Aman could hit. His "Trader-7 spent 30 days without a single trade because safety checks compounded into 1.4% pass rate" is the canonical cautionary tale.
2. **Watters' best rule: "The overnight agent cannot do UAT."** Agent works on develop, ONLY human merges to main. This is a copy-paste discipline rule.
3. **Jamon Holmgren's "Night Shift" is the strongest verification design.** 6 review personas critique BOTH plan AND implementation. Lint/types/compiler/tests all run before human sees. Morning review rule: if agent misbehaved, fix the docs/workflow/validation FIRST, then the code.
4. **McManus's "Boring is the feature"** — fixed-format morning briefings beat creative ones. This validates R5's tier-1 digest design exactly.
5. **Convergent best practice across all cases:** durable file memory + scheduled small loops + scope constraints + explicit verifier + human gate on irreversible work.
6. **Realistic overnight output:** replaces a human's 1-4 hour block of repetitive ops work, OR produces a reviewed batch of specs/tests/partial implementations. NOT a feature shipping itself.
7. **The disclosure gap analysis is brutal and accurate:** the secret sauce is not prompts, it is prior systems thinking, repo hygiene, error-recovery ritual, and domain taste.
8. **The Cowork failure cluster (Kiraki, McCrorey, Spinner, Illingworth) is a clear pattern.** Cowork = files and tasks; Claude Code = codebases and systems. Unattended workflows break on rapid debugging, stateful iteration, open-ended reasoning.

### What's now well-grounded enough to design from

- Architecture pattern: hybrid Routines + local cron
- Authentication path: `claude -p` without `--bare`, `claude setup-token` for scheduled scripts
- Discord integration: webhook (for Routines) + official channel plugin (for local Claude Code, OPTIONAL)
- Notification tier discipline: from R5
- Verification protocol: from R3 + Holmgren's "Night Shift" review personas + Grigorev's PM/SWE/QA/PM pipeline
- Hard rule from Watters: overnight agent cannot do UAT, never autonomous merges to main
- Reasonable expected output: 1-4 human-hours equivalent per overnight cycle

### What's still open

- Should we adopt Holmgren's `REVIEW_PERSONAS.md` pattern verbatim?
- Should we mirror Grigorev's PM/SWE/QA/PM pipeline, or stick with current architect/Codex split?
- How heavily should we lean on Routines given they don't get the SDK credit budget?
- What's the right Discord topology — single server with categories (R5 recommendation) OR Watters-style Telegram-as-only-channel?

### Status

We have enough research to design. Next decision point is Aman's choice of which patterns to adopt before any actual plan generation.


---

## Update 2026-05-22 — Discussion Phase Begins (Aman's Answers + Context File Review)

### Aman's answers to Claude's 7 questions

1. **Time budget: 4+ hours/day, any time of day.** Aman can work on this whenever; the "24/7" goal is specifically about continuing development when he's away from his computer for other work. NOT the constraint.
2. **Solo developer.** Partner is "willing aid if needed" — design for solo. Watters-style pattern most applicable.
3. **CLAUDE.md and AGENTS.md uploaded for Claude review.** See observations below.
4. **Codex catches things.** Current cycle: architect generates work packet → Claude Code implements → Codex reviews (almost always finds something missing/wrong) → results paste back to architect → architect generates FIX prompts → cycle continues → architect decides "good to finish, feature complete." Aman is satisfied this works at the feature level.
5. **"Meta work" framing was unclear.** Aman correctly notes the actual building of new workflow tooling would be done by Claude Code/Codex. The real question Claude was asking: how much investment in workflow infrastructure before resuming feature dev. Needs reframing.
6. **CRYPTO PAIR BOT IS DROPPED.** Aman proved no profitability. This is a major roadmap update — v5.1's "Phase 1A: fastest path to first dollar" is dead. Aman wants more rock-solid approach + deploy main features + collect data + iterate on improvements.
7. **The 5 specific decisions are deferred.** Aman wants to think on these first.

### CRITICAL: Roadmap is stale

CLAUDE.md (lines 36, 61-78) and AGENTS.md still position Crypto Pair Bot as the central Phase 1A revenue path. v5.1 master roadmap also positions it heavily. ALL of these are now stale.

The "Triple Track" framing in v5.1 is now effectively a "Dual Track" (Market Maker + Sports Directional). The "first dollar before perfect system" principle was anchored to the crypto pair bot. With that gone, the first-dollar path itself is unclear.

This is significant. The foundational context files Aman uses every dev session contain confidently-stated stale strategy direction. Any agent reading CLAUDE.md gets misinformation about what the project is trying to do.

### Claude's observations on CLAUDE.md and AGENTS.md

**Length issues (per R6's AGENTS.md paper findings):**
- CLAUDE.md is **568 lines**. Anthropic's own guidance is <200 lines for always-loaded files. The Token Savior benchmark example is 75 lines.
- AGENTS.md is ~280 lines. Better but still above target.
- Substantial duplication between the two files (ClickHouse auth rule, kill-switch model, document priority, Windows gotchas, don't-do list, dev log requirement, smoke test).

**Content quality observations:**
- Both files contain real, hard-won content (the ClickHouse auth fail-fast rule with date evidence is excellent — that's "three bugs in two days" learning preserved).
- Both contain meaningful safety rules (mandatory adversarial review files, human-in-the-loop categorization).
- BUT: both contain content that should be elsewhere — RIS workflows, CLI command reference, full repo structure listings. Per R6's four-layer pattern, these belong in scoped subsystem files, not in the always-loaded layer.
- Stale content is present (crypto pair bot, benchmark_v2 escalation deadline of 2026-04-12 which has passed).

### What's structurally interesting in Aman's answer #4

The cycle Aman described is THE canonical overclaim risk surface, played out in his actual process:

- **The architect generates BOTH the work packet AND decides when the work is complete.**
- This is the same pattern Anthropic's own multi-agent QA writeup flagged as failure-prone ("reviewer talks itself into approving real issues").
- This is the same pattern that produced the 2026-04-10 RIS Phase 2 audit failure (architect claimed completion when 2/6 capabilities were missing).
- The Codex catch rate is high at the IMPLEMENTATION level. But Codex reviews diffs and code, not "does the work match the original intent." Intent-vs-implementation match is being judged by the architect alone.

This doesn't mean the process is broken. It produces working features. It means the process has a STRUCTURAL weakness at the phase/capability/intent level that scaling autonomy will expose.

### Where to start discussion

Multiple candidate "first pieces":
- The workflow cycle and architect's completion authority (most foundational)
- The dropped crypto pair bot and the stale roadmap (most urgent)
- What "continuous development" actually means now (target undefined)
- The CLAUDE.md / AGENTS.md state (most concrete)

Proposing: **start with what "continuous development" actually means for PolyTool now**, because we cannot critique the workflow until we know what work it's serving. The crypto pair bot drop invalidates the prior target.

Then: workflow cycle and architect authority. Then: context files. Then: the 5 deferred decisions.

This is the proposed order. Aman to confirm or redirect.
