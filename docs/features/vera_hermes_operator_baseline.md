---
status: complete
completed: 2026-04-23
track: operator-tooling
scope: read-only
---

# Feature: vera-hermes-agent Operator Baseline

Read-only Hermes operator instance on the main local machine. Gives the operator a named, isolated personal assistant profile that can later be extended with PolyTool query skills. Does NOT connect to messaging, does NOT touch live trading paths, does NOT run scheduled jobs.

---

## What Was Built

| Item | Detail |
|---|---|
| Profile name | `vera-hermes-agent` |
| Alias binary | `/home/patel/.local/bin/vera-hermes-agent` (WSL) |
| Profile path | `/home/patel/.hermes/profiles/vera-hermes-agent/` |
| Hermes version | v0.10.0 (2026.4.16) |
| Model | deepseek-v3.2 via Ollama Cloud |
| Backend | local (no Docker, no SSH, no Modal) |
| Gateway | stopped — not configured |
| Cron jobs | none |
| Messaging integrations | none |
| SOUL.md | read-only scope declaration — Vera identity |

---

## Install Path

Hermes is installed in WSL2 (Ubuntu on Windows). The Windows-native `hermes` binary does not exist; all Hermes commands run through WSL.

```
Host: Windows 11 (D:\Coding Projects\Polymarket\PolyTool)
WSL: Ubuntu — /home/patel/.local/bin/hermes
Profile: /home/patel/.hermes/profiles/vera-hermes-agent/
Alias: /home/patel/.local/bin/vera-hermes-agent
```

---

## Startup / Shutdown / Status Commands

All commands are run from Windows terminal via `wsl bash -lc "..."` or directly inside a WSL shell.

### Start a chat session (operator use)

```bash
# From Windows terminal
wsl bash -lc "vera-hermes-agent chat"

# From inside WSL
vera-hermes-agent chat
```

### Quick one-shot query (non-interactive)

```bash
wsl bash -lc "vera-hermes-agent chat -Q -q 'What is the current Gate 2 status?'"
```

### View profile status

```bash
wsl bash -lc "hermes -p vera-hermes-agent status"
```

### View profile details

```bash
wsl bash -lc "hermes profile show vera-hermes-agent"
```

### List all profiles

```bash
wsl bash -lc "hermes profile list"
```

### Run healthcheck

```bash
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/vera_hermes_healthcheck.sh"
```

### Start gateway (future — not needed yet)

```bash
# When messaging integration is added later:
wsl bash -lc "hermes -p vera-hermes-agent gateway run"
# Or persistent via tmux:
wsl bash -lc "tmux new -s vera-hermes 'hermes -p vera-hermes-agent gateway run'"
```

There is no "stop" command needed for the baseline because the gateway is not running. The process exits automatically after a non-interactive `-Q` chat.

---

## Backend Choice and Why

**Backend: local (WSL2)**

- Hermes was pre-installed in WSL Ubuntu on this machine before this session.
- The Windows binary does not exist; WSL is the only available path.
- Docker Desktop v29 / 4.52.0 is available on the machine and is the preferred backend for future containerized backend work (adds stronger isolation), but is not needed for the current read-only baseline.
- No VPS or cloud backend required at this stage.

---

## Security Boundaries

| Boundary | State |
|---|---|
| Read-only by default | YES — SOUL.md explicitly declares no trades, no bot control |
| Messaging gateway | NOT configured — gateway is stopped |
| Command allowlist | Empty — no commands pre-approved (safe default) |
| Cron jobs | None |
| Live execution access | NONE — profile has no PolyTool CLI wiring yet |
| Secret injection | NONE — no PolyTool secrets in vera-hermes-agent .env |
| Delegation / subagents | Disabled for now (default `max_spawn_depth: 1` applies) |

The SOUL.md for this profile contains an explicit prohibition:
- No trade execution
- No live bot start/stop/modify
- No strategy config changes
- No ClickHouse schema writes
- No secret access or relay

---

## Profile Directory Layout

```
/home/patel/.hermes/profiles/vera-hermes-agent/
├── SOUL.md          # Read-only scope declaration + Vera identity
├── config.yaml      # Cloned from default; model=deepseek-v3.2, backend=local
├── .env             # Cloned from default; OLLAMA_API_KEY set
├── auth.json        # Provider auth state
├── skills/          # No custom skills yet
├── memories/        # Agent memory (empty)
├── sessions/        # Chat session history
├── logs/            # Hermes internal logs
└── workspace/       # Working dir for tool calls
```

---

## What Skills Will Go Here (Next Session)

These skills are the next-session target. Do not build them in this session.

| Skill | Purpose |
|---|---|
| `polytool-status` | Query CURRENT_DEVELOPMENT.md and CURRENT_STATE.md |
| `polytool-dev-logs` | Grep recent dev logs for status |
| `polytool-grafana` | Read-only ClickHouse queries via grafana_ro |
| `polytool-files` | Read specific project files on demand |

Each skill will be a `SKILL.md` file placed under:
```
/home/patel/.hermes/profiles/vera-hermes-agent/skills/<skill-name>/SKILL.md
```

Skills do NOT require gateway activation. They work in `chat` mode.

---

## Healthcheck

Script: `scripts/vera_hermes_healthcheck.sh`

Checks:
1. `hermes` binary accessible
2. `vera-hermes-agent` profile exists
3. SOUL.md contains read-only scope declaration
4. Gateway is not running (expected for baseline)
5. No cron jobs scheduled
6. Live chat round-trip returns expected string

Run:

```bash
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/vera_hermes_healthcheck.sh"
```

Expected output: `=== PASS — vera-hermes-agent is healthy ===`

---

## Relationship to RIS and Hermes Integration Guide

This baseline corresponds to **Stage 4-A** in the Hermes Integration Setup Guide (`docs/obsidian-vault/Claude Desktop/08-Research/Hermes Agent - PolyTool Integration Setup Guide.md`). Stage 4-A is "Install Hermes on operator machine" — complete.

Stage 4-B (operator query skills) is the next step.

**Hermes is NOT on the critical path for Phase 2A or Phase 2B base case.** Per the v1.1 roadmap, Phase 2B base (WP6) uses a manual one-shot contribution script with no Hermes. Hermes becomes relevant for WP7 (continuous mode for committed friends) and for the operator interface. This baseline enables the operator interface path without blocking or touching Phase 2A.

---

## Related Files

- `docs/dev_logs/2026-04-22_hermes-vera-agent.md` — initial profile creation session
- `docs/dev_logs/2026-04-23_operator-hermes-baseline.md` — this session's dev log
- `docs/obsidian-vault/Claude Desktop/08-Research/Hermes Agent - PolyTool Integration Setup Guide.md` — integration guide
- `docs/obsidian-vault/Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md` — Phase 2B placement
- `scripts/vera_hermes_healthcheck.sh` — healthcheck script
