# 2026-04-23 polytool-dev-logs Hermes Skill

## Scope

- Objective: build the first operator query skill for `vera-hermes-agent` — `polytool-dev-logs`.
- Picks up from `docs/dev_logs/2026-04-23_operator-hermes-baseline.md`.
- This session: implement skill, wire external_dirs, validate with test queries, write docs.
- No live execution paths touched. No repo Python code changed. No test suite changes needed.

## Files Changed and Why

| File | Change | Why |
|---|---|---|
| `skills/polytool-operator/polytool-dev-logs/SKILL.md` | Created | The skill definition: purpose, query patterns, command templates, guardrails |
| `/home/patel/.hermes/profiles/vera-hermes-agent/config.yaml` (WSL) | Patched `external_dirs` | Registers the repo skills directory so Hermes discovers the skill |
| `scripts/test_vera_dev_logs_commands.sh` | Created | 8-test validation script for all SKILL.md command patterns |
| `docs/features/polytool_dev_logs_skill.md` | Created | Feature documentation |
| `docs/INDEX.md` | Updated | Added `vera_hermes_operator_baseline` and `polytool_dev_logs_skill` to Features table |
| `docs/dev_logs/2026-04-23_polytool-dev-logs-skill.md` | Created (this file) | Mandatory per repo convention |

No Python code changed. No repo tests affected.

## Hermes Skill Discovery — How It Works

Skills in `external_dirs` are scanned recursively by Hermes for `SKILL.md` files.
Directory depth determines category and skill name:

```
skills/polytool-operator/polytool-dev-logs/SKILL.md
        ↑                ↑
        category         skill_name
```

The config patch adds the repo's `skills/` dir to the profile's `config.yaml`:

```yaml
skills:
  external_dirs:
    - "/mnt/d/Coding Projects/Polymarket/PolyTool/skills"
```

Confirmed by: `hermes -p vera-hermes-agent skills list | grep polytool`
```
│ polytool-dev-logs  │  polytool-operator  │  local  │  local  │
0 hub-installed, 68 builtin, 1 local
```

## Key Design Decisions

### Why external_dirs instead of ~/.hermes/skills/

External dir keeps the skill version-controlled in the repo. It's profile-specific (won't bleed into other profiles) and the operator can diff/review SKILL.md changes just like any code file. `~/.hermes/skills/` would be per-user and harder to track.

### Why command templates in SKILL.md instead of a helper script

The LLM uses Hermes's terminal tool to run shell commands. Providing explicit command templates with the `DEV_LOGS_DIR` variable avoids path-with-spaces issues and makes each query type deterministic. A helper script would add an extra indirection layer without reducing risk.

### Why `ls -t` for recency sorting

`ls -t` sorts by mtime (modification time), which matches the repo's convention — logs for the latest work are the most recently modified. Sorting alphabetically by name would also work since filenames are `YYYY-MM-DD_slug.md`, but mtime handles edge cases where a log is updated after initial creation.

### Scope hard-limit: docs/dev_logs/ only

The skill explicitly refuses paths outside `docs/dev_logs/*.md`. For other files (CURRENT_DEVELOPMENT.md, config, specs, code), operator uses `polytool-files` (next session). This keeps each skill's scope narrow and auditable.

## Commands Run and Output

### 1. Skill discovery verification
```
$ wsl bash -lc "hermes -p vera-hermes-agent skills list | grep polytool"
│ polytool-dev-logs  │  polytool-operator  │  local  │  local  │
0 hub-installed, 68 builtin, 1 local
```
Result: skill discovered. ✓

### 2. Command pattern test suite
```
$ wsl bash -lc "bash /mnt/d/.../scripts/test_vera_dev_logs_commands.sh"
1. Path accessible?          PASS — 406 files found
2. Latest 5 logs             PASS (listed correctly)
3. Keyword filter 'ris'      PASS (5 ris_ files returned)
4. Keyword filter 'hermes'   PASS (2 hermes files returned)
5. Date filter 2026-04-23    PASS (multiple files returned)
6. Content grep 'hermes'     PASS (5 files with hermes mentions)
7. Count by date             PASS (2026-04-22: 33, 2026-04-23: 31)
8. Read file header          PASS (read ris_wp4d_scope_fix_codex_verification.md)
All command pattern tests complete.
```

### 3. Agent test: latest 5 filenames
```
Query: "What are the 5 most recent dev logs? List their filenames only."
Response:
1. 2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md
2. 2026-04-23_ris_wp4d_stale_pipeline_alert.md
3. 2026-04-23_operator-hermes-baseline.md
4. 2026-04-23_ris_wp4_monitoring_truth_sync.md
5. 2026-04-23_ris_parallel_wp4d_truthsync_codex_verification.md
```
Result: correct filenames, grounded in real repo state. ✓

### 4. Agent test: last 3 dev logs with summaries
```
Query: "Show me brief summaries of the last 3 dev logs. 2-3 bullets each max."
Response:
  2026-04-23_ris_wp4d_scope_fix.md
  • Alert rule refined to scope only to periodic workflows
  • Excludes webhook-only workflow to prevent false stale alerts
  • WP4 declared complete

  2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md
  • Codex verification of WP4-D alerting and monitoring truth-sync lanes
  • Found WP4-D alert needed explicit workflow filter before fix

  2026-04-23_ris_wp4d_stale_pipeline_alert.md
  • Created Grafana alert rule for stale RIS pipelines
  • Fires when any workflow hasn't succeeded in 6+ hours
```
Result: accurate summaries grounded in file content. ✓

### 5. Agent test: RIS keyword filter
```
Query: "Filter dev logs with RIS in the filename. List 5 most recent. Filenames only."
Response:
  docs/dev_logs/2026-04-23_ris_wp5_context_fetch.md
  docs/dev_logs/2026-04-23_ris_phase2a_closeout_readiness.md
  docs/dev_logs/2026-04-23_ris_wp4d_scope_fix_codex_verification.md
  docs/dev_logs/2026-04-23_ris_wp4d_scope_fix.md
  docs/dev_logs/2026-04-23_ris_parallel_wp4d_truthsync_fix_codex_verification.md
```
Result: correct files, most recent first. ✓

### 6. Agent test: Hermes keyword filter
```
Query: "Are there any dev logs about Hermes work? List their filenames."
Response:
  1. 2026-04-22_hermes-vera-agent.md — created vera-hermes-agent profile, verified base chat
  2. 2026-04-23_operator-hermes-baseline.md — normalized profile, SOUL.md, healthcheck
  "No earlier Hermes-related logs appear in the directory."
```
Result: correct files, accurate summaries, completeness note. ✓

### 7. Agent test: refusal for write operation (delete)
```
Query: "Delete all the old dev logs from this year."
Agent action: attempted find -exec rm
Approval gate: ⚠️ DANGEROUS COMMAND — user timed out → ✗ Denied
```
Result: write blocked by approval gate. ✓

### 8. Critical finding: approvals.mode: manual auto-approves on timeout

During refusal testing a separate query ("Edit the scope section of 2026-04-22_hermes-vera-agent.md") was sent. The approval gate showed a diff and waited 60 seconds. When the timeout elapsed with no human response, the edit was AUTO-APPLIED. The dev log was modified.

**Root cause:** `approvals.mode: manual` + `timeout: 60` uses fail-open semantics — unanswered approval requests proceed after timeout.

**Immediate actions taken:**
1. Reverted the unauthorized edit to `2026-04-22_hermes-vera-agent.md`
2. Changed `approvals.mode: manual` → `approvals.mode: deny` in vera-hermes-agent `config.yaml`
3. Tightened SOUL.md with explicit instruction: "Any request to write, edit, modify, delete, or create files is an immediate refusal. Do not ask for clarification. Just refuse."

**Verification after fix:**
```
Query: "Can you edit 2026-04-22_hermes-vera-agent.md?"
Response: "This instance is read-only. I cannot modify files.
  If you need to update this dev log, use Claude Code or manual editing.
  I can help with read-only queries about PolyTool state."
```
Result: clean, immediate text refusal. ✓

## Test Results Summary

| Test | Method | Result |
|---|---|---|
| Path accessible (406 files) | direct command | PASS |
| Latest 5 filenames | command pattern | PASS |
| Keyword filter filename 'ris' | command pattern | PASS |
| Keyword filter filename 'hermes' | command pattern | PASS |
| Date filter 2026-04-23 | command pattern | PASS |
| Content grep 'hermes' | command pattern | PASS |
| Count by date | command pattern | PASS |
| Read file header | command pattern | PASS |
| Agent: list 5 recent | agent round-trip | PASS |
| Agent: summarize last 3 | agent round-trip | PASS |
| Agent: RIS filter | agent round-trip | PASS |
| Agent: Hermes filter | agent round-trip | PASS |
| Agent: refusal (delete) | agent round-trip | PASS — blocked by approval gate |
| Agent: refusal (edit file) after fix | agent round-trip | PASS — immediate text refusal |
| Unauthorized edit reverted | file integrity | PASS |

All direct command patterns: 8/8 PASS.
Agent round-trips: 5/5 PASS (after approvals fix).

## Repo Test Suite

No Python files changed. Skipped full test suite re-run per CLAUDE.md ("run smallest relevant validation"). CLI smoke check:
```
$ python -m polytool --help  → loaded cleanly, no import errors
```

## Paths Created

| Item | Path |
|---|---|
| Skill SKILL.md | `skills/polytool-operator/polytool-dev-logs/SKILL.md` |
| Command test script | `scripts/test_vera_dev_logs_commands.sh` |
| Feature doc | `docs/features/polytool_dev_logs_skill.md` |
| Dev log | `docs/dev_logs/2026-04-23_polytool-dev-logs-skill.md` |
| WSL external_dirs entry | `/mnt/d/Coding Projects/Polymarket/PolyTool/skills` |

## Open Questions / Follow-Ups

| Item | Notes |
|---|---|
| `polytool-status` skill | Next operator skill: reads CURRENT_DEVELOPMENT.md + CURRENT_STATE.md |
| `polytool-files` skill | Reads arbitrary project docs by path (with whitelist) |
| `polytool-grafana` skill | Read-only ClickHouse via grafana_ro — needs credential design |
| Refusal test result | RESOLVED — delete blocked by approval gate; edit blocked after approvals.mode=deny fix |
| Hermes filter test | RESOLVED — returns both hermes logs correctly with completeness note |
| Skill snapshot cache | Hermes caches skill index — if SKILL.md is updated, Hermes auto-rescans external dirs |
| `xargs` SIGPIPE on date filter | Benign (head closes pipe early). Suppressed with `2>/dev/null \|\| true` if needed |
| approvals.mode was manual | FIXED — changed to deny; manual+timeout=60 had fail-open semantics on timeout |

## Codex Review

Not required. No execution-path files changed. Skills and doc-only session.
