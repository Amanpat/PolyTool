---
status: complete
completed: 2026-04-23
track: operator-tooling
scope: read-only
skill-host: vera-hermes-agent
---

# Feature: polytool-dev-logs Hermes Skill

Read-only Hermes skill for the `vera-hermes-agent` operator profile. Lets the operator query and summarize PolyTool dev logs via natural language, without accessing live system state, live execution paths, or the polytool CLI.

---

## What Was Built

| Item | Detail |
|---|---|
| Skill name | `polytool-dev-logs` |
| Skill category | `polytool-operator` |
| Skill type | external / local (in-repo) |
| Host profile | `vera-hermes-agent` |
| Source location | `skills/polytool-operator/polytool-dev-logs/SKILL.md` |
| Discovery path | `external_dirs` in vera-hermes-agent `config.yaml` |
| WSL external dir | `/mnt/d/Coding Projects/Polymarket/PolyTool/skills` |
| Reads from | `docs/dev_logs/*.md` only |
| Writes to | nothing — strictly read-only |

---

## Skill Discovery

The skill lives in the repo and is registered in the vera-hermes-agent profile via `config.yaml`:

```yaml
skills:
  external_dirs:
    - "/mnt/d/Coding Projects/Polymarket/PolyTool/skills"
```

Hermes discovers `SKILL.md` files recursively under that directory. The skill directory structure determines category and name:

```
skills/
└── polytool-operator/        ← category
    └── polytool-dev-logs/    ← skill name
        └── SKILL.md
```

Verify it's loaded:
```bash
wsl bash -lc "hermes -p vera-hermes-agent skills list 2>&1 | grep polytool"
# Expected: polytool-dev-logs  |  polytool-operator  |  local  |  local
```

---

## Capability Summary

| Query pattern | Works |
|---|---|
| "What are the 5 most recent dev logs?" | ✓ — lists filenames sorted by mtime |
| "Show brief summaries of last 3 logs" | ✓ — reads headers, produces per-file bullets |
| "Filter logs by keyword: RIS" | ✓ — grep filename, return sorted list |
| "Filter logs by keyword: Hermes" | ✓ — filename + content grep |
| "What changed on 2026-04-23?" | ✓ — date-prefix filter |
| "How many logs this week?" | ✓ — count by date prefix |
| "Delete dev logs" | ✓ refused — "This skill is read-only" |
| "Run python -m polytool ..." | ✓ refused — "Use polytool-status skill" |
| "Read config/benchmark_v1.lock.json" | ✓ refused — "Only reads docs/dev_logs/" |

---

## Security Boundaries

| Boundary | State |
|---|---|
| File scope | `docs/dev_logs/*.md` only — skill refuses all other paths |
| Allowed shell commands | `ls`, `cat`, `head`, `grep`, `basename`, `wc`, `sort`, `uniq`, `cut`, `sed`, `xargs` |
| Modifications | None — read-only strictly enforced by SKILL.md guardrails |
| CLI commands | No `python -m polytool` or live system commands |
| Secret extraction | Skill explicitly prohibits printing credentials even if they appear in a log |
| Scope expansion | Refused with pointer to correct skill (polytool-status, polytool-files) |

---

## File Structure

```
skills/
└── polytool-operator/
    └── polytool-dev-logs/
        └── SKILL.md    ← skill definition, procedure, guardrails
```

```
scripts/
├── test_vera_dev_logs_commands.sh   ← validates command patterns work
└── vera_hermes_healthcheck.sh       ← existing baseline healthcheck
```

---

## Example Queries (tested)

```
"What are the 5 most recent dev logs? List filenames only."
→ Lists correct filenames sorted by modification time.

"Show me brief summaries of the last 3 dev logs. 2-3 bullets each max."
→ Reads file headers, produces per-file summary with scope/changed/decisions.

"Filter dev logs with RIS in the filename. List 5 most recent."
→ Returns ris_wp4d, ris_parallel, ris_wp4d_stale filenames.

"Delete all the old dev logs from this year."
→ Declined: "This skill is read-only. No file modifications allowed."
```

---

## Test Suite

### Command pattern test (offline — validates shell commands work)

```bash
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/test_vera_dev_logs_commands.sh"
```

Checks 8 patterns: path access, latest 5, filename filter (ris), filename filter (hermes), date filter, content grep, count-by-date, header read.

Expected: `=== All command pattern tests complete ===` with all PASS.

### Agent round-trip test (live — requires vera-hermes-agent)

```bash
wsl bash -lc "vera-hermes-agent chat -Q -q 'What are the 5 most recent dev logs? Filenames only.'"
```

Expected: 5 filenames from `docs/dev_logs/`, most recent first.

---

## Adding Future Operator Skills

The `skills/polytool-operator/` directory is the home for all PolyTool operator skills. Upcoming skills to add:

| Skill | Purpose | Directory |
|---|---|---|
| `polytool-status` | Query CURRENT_DEVELOPMENT.md + CURRENT_STATE.md | `skills/polytool-operator/polytool-status/` |
| `polytool-files` | Read specific project docs on demand | `skills/polytool-operator/polytool-files/` |
| `polytool-grafana` | Read-only ClickHouse queries via grafana_ro | `skills/polytool-operator/polytool-grafana/` |

Each skill needs only a `SKILL.md` in its directory. Hermes discovers it automatically on next startup.

---

## Related Files

- `skills/polytool-operator/polytool-dev-logs/SKILL.md` — the skill itself
- `scripts/test_vera_dev_logs_commands.sh` — command pattern test suite
- `docs/features/vera_hermes_operator_baseline.md` — baseline profile feature doc
- `docs/dev_logs/2026-04-23_polytool-dev-logs-skill.md` — this session's dev log
- `docs/dev_logs/2026-04-23_operator-hermes-baseline.md` — previous session dev log
