---
name: polytool-status
description: Read current PolyTool project status from CURRENT_DEVELOPMENT and CURRENT_STATE. Read-only.
version: 1.0.0
category: polytool-operator
metadata:
  hermes:
    tags: [polytool, status, read-only, operator, active-features, gate2]
---

# polytool-status

## Purpose

Provides read-only access to the two PolyTool live-state documents so the operator can ask questions about what is active, what is implemented, what is blocked, and what the current track is.

**Source files (WSL absolute paths):**
```
/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md
/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
```

---

## Document Authority and Priority

These two files serve different purposes and have different scopes:

| File | Authority | Use for |
|---|---|---|
| `CURRENT_DEVELOPMENT.md` | Active planning state | Active features, paused items, recently completed, notes to Architect, current step |
| `CURRENT_STATE.md` | Implemented repo truth | What is actually built, shipped facts, gate outcomes, artifact paths |

**Priority rule (from AGENTS.md document priority order):**
- `CURRENT_STATE.md` is higher authority than `CURRENT_DEVELOPMENT.md` for **implemented facts** (e.g., Gate 2 numerical result, what is actually built).
- `CURRENT_DEVELOPMENT.md` is the primary source for **active planning state** (e.g., which features are Active, what is paused, current next step).

**When they conflict:** Say so explicitly. Do not pick one silently. Example: "CURRENT_STATE says X; CURRENT_DEVELOPMENT says Y. CURRENT_STATE has higher authority for implemented facts."

**When status docs appear stale or incomplete:** Say so. If a doc has a `last_verified` frontmatter date older than 7 days, note it. If information is absent, say "not recorded in these docs" rather than guessing.

---

## When to Use

Use when the operator asks:
- "What's active right now?" / "What are we working on?"
- "What track are we on?"
- "What's blocking Gate 2?"
- "What's paused or deferred?"
- "What was recently completed?"
- "What's the current RIS status?"
- "What's the overall repo state?"
- "Are the two status docs consistent?"
- "Show me the Active Features section."
- "What's the next action for Track 2?"

---

## Hard Boundaries

**ONLY read from:**
- `/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md`
- `/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md`

**NEVER:**
- Modify either file
- Read files outside these two paths (for dev logs use polytool-dev-logs, for arbitrary docs use polytool-files)
- Run `python -m polytool` commands or any live system command
- Print API keys, credentials, secrets, or private keys
- Use shell commands beyond: `cat`, `head`, `grep`, `sed`, `wc`, `tail`

If asked for anything outside this scope, decline and name the right skill.

---

## Procedure

### Step 1 — Choose the right source

| Query type | Primary source | Secondary source |
|---|---|---|
| What is active / being built now | CURRENT_DEVELOPMENT.md | — |
| Current track / next step | CURRENT_DEVELOPMENT.md | — |
| What is paused or deferred | CURRENT_DEVELOPMENT.md | — |
| Recently completed features | CURRENT_DEVELOPMENT.md | — |
| Gate 2 status and artifacts | CURRENT_STATE.md | CURRENT_DEVELOPMENT.md Awaiting Decision |
| What is actually implemented | CURRENT_STATE.md | — |
| Repo-level architecture facts | CURRENT_STATE.md | — |
| Cross-check consistency | Both | — |

### Step 2 — Read the file(s)

Read the full file for most queries (files are ~200–350 lines):
```bash
cat "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md"
```
```bash
cat "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md"
```

For targeted section extraction, use grep to find the section header then read from there:
```bash
grep -n "## Active Features" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md"
# Note the line number N, then:
sed -n 'N,/^## /p' "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md" | head -80
```

Common section greps:
```bash
# Active Features section
grep -A 60 "## Active Features" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md" | head -60

# Awaiting Decision section
grep -A 25 "## Awaiting Director Decision" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md" | head -25

# Recently Completed table
grep -A 20 "## Recently Completed" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md" | head -20

# Paused/Deferred table
grep -A 25 "## Paused" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md" | head -25

# Gate 2 status block in CURRENT_STATE
grep -A 40 "Gate 2" "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md" | head -40
```

### Step 3 — Check frontmatter for staleness

```bash
head -10 "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_DEVELOPMENT.md"
head -10 "/mnt/d/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md"
```

If `last_verified:` date is older than 7 days from today, note: "⚠ CURRENT_STATE.md was last verified on [date] — some details may be stale."

### Step 4 — Answer with source attribution

Always cite which file the information came from. Example format:

```
[From CURRENT_DEVELOPMENT.md]
Active features (as of last_updated 2026-04-23):
- Feature 1: Track 2 Paper Soak — 24h Run (Track 1A) — Ready to launch, no blockers.
- Feature 2: RIS Operational Readiness Phase 2A — WP1-WP4 complete, current step: WP5.
- Feature 3: Empty slot.

[From CURRENT_STATE.md]
Gate 2 status: FAILED (2026-04-14) — 7/50 positive tapes (14%), threshold 70%.
Root cause: silver tapes produce zero fills; crypto 5m tapes (10) are 7/10 positive.
```

---

## Output Modes

### Concise direct answer

For simple factual queries ("What's blocking Gate 2?"), give 2-4 sentences citing the source.

### Bullet summary

For "what's active / what's the status":
```
Active features [CURRENT_DEVELOPMENT.md, last_updated 2026-04-23]:
• Feature 1: Track 2 Paper Soak — 24h Run — Track 1A — Ready to launch
• Feature 2: RIS Operational Readiness Phase 2A — WP5 retrieval benchmark next
• Feature 3: [empty]

Awaiting Director Decision:
• Gate 2 path forward — options 1-4 documented; no decision recorded yet

Gate 2 status [CURRENT_STATE.md]:
• FAILED 7/50 = 14% (need 70%) as of 2026-04-14
```

### Relevant-section excerpt

When operator says "show me the X section", read the full section and return it verbatim (with file attribution).

### Blocker-focused summary

For "what's blocked" or "what's the next step":
- List items with explicit blockers from CURRENT_DEVELOPMENT.md
- Include Awaiting Decision items (they are not Active — do not advance them without operator direction)
- Note the defined "Resume trigger" from the Paused table

### Consistency check

When operator asks "are these docs consistent?":
1. Read both files
2. Find the same topic in each (Gate 2, active tracks, RIS phase)
3. Report agreement or flag the disagreement with the priority rule applied

---

## Conflict Handling Rules

| Scenario | Action |
|---|---|
| CURRENT_STATE and CURRENT_DEVELOPMENT agree | Report normally |
| They disagree on an implemented fact | Trust CURRENT_STATE; flag the discrepancy |
| CURRENT_DEVELOPMENT says something CURRENT_STATE doesn't cover | Report it with source note: "recorded in CURRENT_DEVELOPMENT but not reflected in CURRENT_STATE — CURRENT_STATE may be stale on this point" |
| A doc has no `last_verified` date | Note that freshness cannot be confirmed |
| Information is absent from both docs | Say "not recorded in these docs" — never guess |

---

## Guardrails Checklist

Before executing any command, confirm:
- [ ] Target path is one of the two approved files (or a `grep -A` on those files)
- [ ] Command is read-only: `cat` / `head` / `grep` / `sed` / `wc` / `tail`
- [ ] Output does not contain API keys, passwords, or private credentials

If any check fails: do not execute. Explain the refusal.

---

## Out-of-Scope Refusal Examples

**"Edit the CURRENT_DEVELOPMENT.md Active Features section"**
→ "This instance is read-only. I cannot modify files."

**"Run python -m polytool research-health to check RIS status"**
→ "This skill reads status docs only. For live system health, use polytool-grafana (when available) or run the command manually."

**"What does Gate 2 code look like in run_recovery_corpus_sweep.py?"**
→ "This skill reads CURRENT_DEVELOPMENT.md and CURRENT_STATE.md only. For code inspection, use Claude Code directly."

**"What's in the last dev log about Gate 2?"**
→ "Use polytool-dev-logs for dev log queries. This skill only reads the two status docs."

**"Start the Track 2 soak"**
→ "This instance is read-only and operator-facing only. I cannot start processes. Use Claude Code or the operator runbook at docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md."
