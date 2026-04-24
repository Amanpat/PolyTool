---
status: complete
completed: 2026-04-23
track: operator-tooling
scope: read-only
skill-host: vera-hermes-agent
---

# Feature: polytool-status Hermes Skill

Read-only Hermes skill for the `vera-hermes-agent` operator profile. Answers questions about active features, gate status, current track, recently completed work, and paused items — all grounded in the two canonical live-state docs.

---

## What Was Built

| Item | Detail |
|---|---|
| Skill name | `polytool-status` |
| Skill category | `polytool-operator` |
| Skill type | external / local (in-repo) |
| Host profile | `vera-hermes-agent` |
| Source location | `skills/polytool-operator/polytool-status/SKILL.md` |
| Discovery | via `external_dirs` already set in vera-hermes-agent `config.yaml` |
| Source files (reads) | `docs/CURRENT_DEVELOPMENT.md`, `docs/CURRENT_STATE.md` |
| Writes to | nothing — strictly read-only |

---

## Source Document Authority

| File | Role | When to use |
|---|---|---|
| `CURRENT_DEVELOPMENT.md` | Living planning state | Active features, current step, paused table, recently completed, Awaiting Decision |
| `CURRENT_STATE.md` | Implemented repo truth | What is actually built, gate outcomes (Gate 2 FAILED 7/50), artifact paths |

**Priority rule (from AGENTS.md):** `CURRENT_STATE.md` is above `CURRENT_DEVELOPMENT.md` in the document authority chain for *implemented facts*. `CURRENT_DEVELOPMENT.md` is the primary source for *current planning state*.

If the two docs disagree, the skill surfaces the conflict explicitly rather than picking one silently.

---

## Capability Summary

| Query | Works |
|---|---|
| "What's active right now?" | ✓ — Active Features section from CURRENT_DEVELOPMENT |
| "What track are we on?" | ✓ — track field from Active Features entries |
| "What's blocking Gate 2?" | ✓ — Awaiting Decision + CURRENT_STATE Gate 2 block |
| "What was recently completed?" | ✓ — Recently Completed table |
| "What's paused or deferred?" | ✓ — Paused/Deferred table with resume triggers |
| "What's the repo's current state?" | ✓ — CURRENT_STATE.md overview |
| "Are the two status docs consistent?" | ✓ — reads both, reports agreement or flags conflict |
| "Show me the Active Features section" | ✓ — grep-extracted verbatim section |
| "What's the next step for RIS?" | ✓ — Feature 2 current step from CURRENT_DEVELOPMENT |
| "Edit CURRENT_DEVELOPMENT.md" | ✓ refused — "This instance is read-only" |

---

## Security Boundaries

| Boundary | State |
|---|---|
| File scope | Two approved paths only — refuses all others |
| Allowed commands | `cat`, `head`, `grep`, `sed`, `wc`, `tail` |
| Modifications | None — read-only enforced by SOUL.md + approvals.mode: deny |
| Live system queries | Not supported — refers to polytool-grafana (future) |
| Secret printing | Prohibited by SKILL.md guardrail |

---

## Conflict Handling

The skill has an explicit conflict table:

| Scenario | Action |
|---|---|
| Docs agree | Report normally |
| Disagree on implemented fact | Trust CURRENT_STATE, flag discrepancy |
| CURRENT_DEVELOPMENT has info CURRENT_STATE doesn't | Note: "recorded in CURRENT_DEVELOPMENT but not reflected in CURRENT_STATE — may be stale" |
| Doc has no last_verified | Note freshness cannot be confirmed |
| Info absent from both | Say "not recorded in these docs" — never guess |

---

## Known Active State (as of 2026-04-23)

From CURRENT_DEVELOPMENT.md (`last_verified: 2026-04-22`):

- **Feature 1:** Track 2 Paper Soak — 24h Run (Track 1A) — ready to launch, no blockers
- **Feature 2:** RIS Operational Readiness Phase 2A — WP1-WP4 complete, current step WP5 retrieval benchmark
- **Feature 3:** empty slot

From CURRENT_STATE.md:

- **Gate 2:** FAILED — 7/50 positive (14%), threshold 70%, re-confirmed 2026-04-14
- **Gate 2 path forward:** Awaiting Director Decision (Options 1–4 documented)
- **Option 4 (re-run with corrected fee model):** now unblocked since Deliverable A complete 2026-04-21

---

## File Structure

```
skills/
└── polytool-operator/
    ├── polytool-dev-logs/
    │   └── SKILL.md
    └── polytool-status/
        └── SKILL.md    ← this skill
```

```
scripts/
├── test_vera_status_commands.sh     ← validates command patterns
├── test_vera_dev_logs_commands.sh   ← previous skill's test
└── vera_hermes_healthcheck.sh       ← baseline healthcheck
```

---

## Test Suite

### Command pattern test (offline — does not require agent)

```bash
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/test_vera_status_commands.sh"
```

Runs 10 checks:
1. Both source files accessible (CURRENT_DEVELOPMENT.md: 130 lines, CURRENT_STATE.md: 1729 lines)
2. CURRENT_DEVELOPMENT.md frontmatter (last_verified: 2026-04-22)
3. CURRENT_STATE.md frontmatter (no last_verified frontmatter — raw doc)
4. Active Features section extraction
5. Awaiting Director Decision extraction
6. Gate 2 status from CURRENT_STATE
7. Recently Completed table
8. Paused/Deferred table
9. Cross-check: Gate 2 FAILED in CURRENT_STATE
10. Cross-check: Gate 2 path forward in CURRENT_DEVELOPMENT

Expected: all PASS.

### Agent round-trip test (requires Ollama Cloud quota)

```bash
wsl bash -lc "vera-hermes-agent chat -Q -q 'What is active right now in PolyTool? Concise bullets.'"
```

Expected: Feature 1 + Feature 2 with track and status, sourced from CURRENT_DEVELOPMENT.md.

**Note:** Ollama Cloud free tier has a session usage limit. If the agent returns 429, wait for quota reset before running agent tests.

---

## Discovered Consistency Gap (2026-04-23)

`CURRENT_STATE.md` does not have a `last_verified` frontmatter field — it has no frontmatter at all. The skill handles this by checking `head -10` of the file and noting if no frontmatter is present ("freshness cannot be confirmed from frontmatter").

`CURRENT_DEVELOPMENT.md` has `last_verified: 2026-04-22` and `last_updated` timestamps per-feature. The skill uses the feature-level `last_updated` field for freshness checks within Active Features.

---

## Related Files

- `skills/polytool-operator/polytool-status/SKILL.md` — the skill itself
- `scripts/test_vera_status_commands.sh` — command pattern test suite
- `docs/features/vera_hermes_operator_baseline.md` — baseline profile doc
- `docs/features/polytool_dev_logs_skill.md` — previous skill doc
- `docs/dev_logs/2026-04-23_polytool-status-skill.md` — this session's dev log
