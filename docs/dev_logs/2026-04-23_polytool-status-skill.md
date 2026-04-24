# 2026-04-23 polytool-status Hermes Skill

## Scope

- Objective: build the second operator query skill for `vera-hermes-agent` — `polytool-status`.
- Picks up from `docs/dev_logs/2026-04-23_polytool-dev-logs-skill.md`.
- This session: implement skill, write test suite, validate command patterns, create docs.
- No live execution paths touched. No repo Python code changed. No test suite changes needed.

## Files Changed and Why

| File | Change | Why |
|---|---|---|
| `skills/polytool-operator/polytool-status/SKILL.md` | Created | Skill definition: source priority, query patterns, commands, conflict handling, guardrails |
| `scripts/test_vera_status_commands.sh` | Created | 10-test validation script for all SKILL.md command patterns |
| `docs/features/polytool_status_skill.md` | Created | Feature documentation |
| `docs/INDEX.md` | Updated | Added `polytool-status` to Features table |
| `docs/dev_logs/2026-04-23_polytool-status-skill.md` | Created (this file) | Mandatory per repo convention |

No Python code changed. No repo tests affected. No profile config changes needed (external_dirs already set).

## Key Design Decisions

### Source priority: CURRENT_STATE > CURRENT_DEVELOPMENT for implemented facts

From AGENTS.md document priority order, CURRENT_STATE.md ranks above CURRENT_DEVELOPMENT.md. The skill encodes this explicitly:
- CURRENT_STATE.md for: what is actually built, gate outcomes (Gate 2 numerical result), artifact paths
- CURRENT_DEVELOPMENT.md for: what is active now, current step, paused table, decisions pending

### Conflict handling is explicit, not silent

If the two docs disagree, Vera says so and names which doc has higher authority for that fact type. She never silently picks one or splits the difference.

### CURRENT_STATE.md has no frontmatter

Discovered during inspection: CURRENT_DEVELOPMENT.md has `last_verified: 2026-04-22` frontmatter, but CURRENT_STATE.md is a raw doc with no frontmatter. The skill handles this: if no frontmatter date is found, it notes "freshness cannot be confirmed from frontmatter."

### Commands stay simple: cat, head, grep, sed

No directory scanning needed — only two specific files. Most queries are handled by `cat` of the relevant file, with `grep -A N` for section extraction. No xargs, no ls, no complex pipelines.

### No config changes needed

The `external_dirs` was already set to the repo's `skills/` directory from the previous session. The `polytool-status/SKILL.md` was auto-discovered by Hermes on next skill check.

## Commands Run and Output

### 1. Skill directory creation
```
mkdir -p skills/polytool-operator/polytool-status/
```
Result: created. ✓

### 2. Skill discovery verification
```
$ wsl bash -lc "hermes -p vera-hermes-agent skills list | grep polytool"
│ polytool-dev-logs  │  polytool-operator  │  local  │  local  │
│ polytool-status    │  polytool-operator  │  local  │  local  │
0 hub-installed, 68 builtin, 2 local
```
Result: both skills discovered. ✓

### 3. Command pattern test suite — all 10 PASS
```
=== polytool-status command pattern tests ===
1. Both files accessible      PASS — CURRENT_DEVELOPMENT.md (130 lines), CURRENT_STATE.md (1729 lines)
2. CURRENT_DEVELOPMENT frontmatter  PASS — last_verified: 2026-04-22
3. CURRENT_STATE.md header    PASS — no frontmatter (noted in skill)
4. Active Features section    PASS — Feature 1 (Track 2), Feature 2 (RIS Phase 2A), empty slot
5. Awaiting Decision section  PASS — Gate 2 path forward with 4 options
6. Gate 2 from CURRENT_STATE  PASS — corpus visibility section returned
7. Recently Completed table   PASS — PMXT A/B, Wallet Discovery, etc.
8. Paused/Deferred table      PASS — 9 items with resume triggers
9. Cross-check: FAILED in CS  PASS — Gate 2 FAILED found in CURRENT_STATE
10. Cross-check: decision CD  PASS — Gate 2 decision entry found in CURRENT_DEVELOPMENT
=== All command pattern tests complete ===
```

### 4. Agent test: BLOCKED — Ollama Cloud rate limit
```
vera-hermes-agent chat -Q -q 'What is active right now in PolyTool?'
→ Error: HTTP 429 - 'you (patelamanst) have reached your session usage limit'
```

**Root cause:** Extensive agent testing during the polytool-dev-logs session (5+ agent round-trips, refusal retests) exhausted the Ollama Cloud free tier session quota for this account.

**Impact:** Agent round-trip tests cannot be run in this session. Command pattern validation (10/10 PASS) confirms the skill's shell commands work correctly. The skill will be agent-tested when the Ollama Cloud quota resets (per-hour or per-day depending on tier).

**Verification path:** When quota resets, run:
```bash
wsl bash -lc "vera-hermes-agent chat -Q -q 'What is active right now in PolyTool?'"
wsl bash -lc "vera-hermes-agent chat -Q -q 'What track are we on?'"
wsl bash -lc "vera-hermes-agent chat -Q -q 'What is blocking Gate 2?'"
wsl bash -lc "vera-hermes-agent chat -Q -q 'Are CURRENT_DEVELOPMENT and CURRENT_STATE consistent?'"
wsl bash -lc "vera-hermes-agent chat -Q -q 'Show me the Active Features section.'"
wsl bash -lc "vera-hermes-agent chat -Q -q 'Edit CURRENT_DEVELOPMENT.md to add a new feature.'"
```

### 5. Safety posture confirmed
```
$ wsl bash -lc "grep -A3 'approvals:' /home/patel/.hermes/profiles/vera-hermes-agent/config.yaml"
approvals:
  mode: deny
  timeout: 60
  cron_mode: deny
```
Result: approvals.mode remains deny. ✓

## Doc Conflict Found (CURRENT_STATE.md Freshness)

CURRENT_STATE.md has no `last_verified` or other frontmatter date. The file begins with `# Current State / What We Built` directly. The most recent dated content is from 2026-04-10 (Wallet Discovery v1 section). The file may not reflect RIS Phase 2A work (which was active 2026-04-22/23).

**Conclusion:** CURRENT_STATE.md is stale relative to CURRENT_DEVELOPMENT.md for RIS Phase 2A. Skill is designed to flag this: "recorded in CURRENT_DEVELOPMENT but not reflected in CURRENT_STATE — CURRENT_STATE may be stale on this point."

## Test Results Summary

| Test | Method | Result |
|---|---|---|
| Both source files accessible | command pattern | PASS |
| CURRENT_DEVELOPMENT frontmatter | command pattern | PASS |
| CURRENT_STATE header | command pattern | PASS |
| Active Features extraction | command pattern | PASS |
| Awaiting Decision extraction | command pattern | PASS |
| Gate 2 from CURRENT_STATE | command pattern | PASS |
| Recently Completed table | command pattern | PASS |
| Paused/Deferred table | command pattern | PASS |
| Cross-check Gate 2 FAILED in CS | command pattern | PASS |
| Cross-check Gate 2 decision in CD | command pattern | PASS |
| Agent: active features | agent round-trip | BLOCKED — Ollama Cloud rate limit |
| Agent: current track | agent round-trip | BLOCKED — Ollama Cloud rate limit |
| Agent: Gate 2 blockers | agent round-trip | BLOCKED — Ollama Cloud rate limit |
| Agent: doc consistency check | agent round-trip | BLOCKED — Ollama Cloud rate limit |
| Agent: section excerpt | agent round-trip | BLOCKED — Ollama Cloud rate limit |
| Agent: refusal (write) | agent round-trip | BLOCKED — Ollama Cloud rate limit |
| approvals.mode still deny | config check | PASS |
| No unauthorized file edits | integrity check | PASS |

Command patterns: 10/10 PASS.
Agent round-trips: 0/6 runnable (rate-limited, not skill errors).
Safety posture: confirmed unchanged.

## Repo Test Suite

No Python files changed. CLI smoke check:
```
$ python -m polytool --help → loaded cleanly, no import errors
```

## Paths Created

| Item | Path |
|---|---|
| Skill SKILL.md | `skills/polytool-operator/polytool-status/SKILL.md` |
| Command test script | `scripts/test_vera_status_commands.sh` |
| Feature doc | `docs/features/polytool_status_skill.md` |
| Dev log | `docs/dev_logs/2026-04-23_polytool-status-skill.md` |

## Open Questions / Follow-Ups

| Item | Notes |
|---|---|
| Agent tests pending | Run 6 queries above when Ollama Cloud quota resets |
| CURRENT_STATE.md staleness | RIS Phase 2A work not reflected in CURRENT_STATE — needs update at Phase 2A completion |
| `polytool-files` skill | Next: arbitrary project doc reads with approved-path whitelist |
| `polytool-grafana` skill | Needs credential design for grafana_ro ClickHouse access |
| Ollama Cloud quota | Consider upgrading or switching to OpenRouter for higher limits on agent testing |
| Model fallback | Could configure fallback to OpenRouter free tier for rate-limit resilience |

## Codex Review

Not required. No execution-path files changed. Skill and doc-only session.
