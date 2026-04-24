# 2026-04-23 Operator Hermes Baseline — vera-hermes-agent

## Scope

- Objective: normalize the `vera-hermes-agent` Hermes profile into a clean, documented, explicitly read-only operator baseline on the main local machine.
- Picks up from `docs/dev_logs/2026-04-22_hermes-vera-agent.md` which created the profile and verified the first chat round-trip.
- This session: SOUL.md scope, helper script, feature doc, dev log. No live path changes.

## Files Changed and Why

| File | Change | Why |
|---|---|---|
| `/home/patel/.hermes/profiles/vera-hermes-agent/SOUL.md` (WSL) | Written — was empty template | Explicitly declares read-only scope, prohibited actions, Vera identity |
| `scripts/vera_hermes_healthcheck.sh` | Created | Reproducible 6-step healthcheck for the instance |
| `docs/features/vera_hermes_operator_baseline.md` | Created | Feature documentation: paths, commands, security boundaries, next targets |
| `docs/dev_logs/2026-04-23_operator-hermes-baseline.md` | Created (this file) | Mandatory per repo convention |

No Python code changed. No test files changed. No live execution paths touched.

## Machine Findings

| Check | Result |
|---|---|
| WSL2 available | YES — Ubuntu on Windows 11 |
| Hermes binary | `/home/patel/.local/bin/hermes`, v0.10.0 (2026.4.16) |
| Hermes in Windows PATH | NO — WSL only |
| Docker available | YES — Docker Desktop 29.0.1 / Desktop 4.52.0 |
| vera-hermes-agent profile | EXISTS from 2026-04-22 session |
| Profile alias | `/home/patel/.local/bin/vera-hermes-agent` |
| Model | deepseek-v3.2 via Ollama Cloud |
| OLLAMA_API_KEY | SET in profile .env |
| Gateway state | stopped |
| Cron jobs | none |
| Messaging integrations | none configured |

## Commands Run and Output

### 1. Version and profile state
```
$ wsl bash -lc "hermes --version 2>&1; hermes profile list 2>&1"
Hermes Agent v0.10.0 (2026.4.16)
...
 ◆vera-hermes-agent  deepseek-v3.2  stopped  vera-hermes-agent
```
Result: profile active, gateway stopped. ✓

### 2. Profile details
```
$ wsl bash -lc "hermes profile show vera-hermes-agent"
Profile: vera-hermes-agent
Path:    /home/patel/.hermes/profiles/vera-hermes-agent
Model:   deepseek-v3.2 (ollama-cloud)
Gateway: stopped
Skills:  72
.env:    exists
SOUL.md: exists
Alias:   /home/patel/.local/bin/vera-hermes-agent
```
Result: consistent with 2026-04-22 state. ✓

### 3. SOUL.md update (WSL heredoc)
```
$ wsl bash -lc "cat > /home/patel/.hermes/profiles/vera-hermes-agent/SOUL.md << 'SOUL_EOF'
# Vera — PolyTool Operator Assistant
...
SOUL_EOF
echo 'SOUL.md written'"
SOUL.md written
```
Result: written, verified read-only scope lines present. ✓

### 4. Healthcheck script
```
$ wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/vera_hermes_healthcheck.sh"
=== vera-hermes-agent healthcheck ===
1. Hermes binary...         Hermes Agent v0.10.0 (2026.4.16)
2. Profile presence...      OK — vera-hermes-agent found
3. SOUL.md scope...         OK — read-only scope declared
4. Gateway state...         ✗ Gateway is not running (expected: stopped)
5. Scheduled jobs...        No scheduled jobs. (expected: none)
6. Chat round-trip...       OK — got: vera hermes agent ready
=== PASS — vera-hermes-agent is healthy ===
```
Result: all 6 checks pass. Exit 0. ✓

## Validation Results

| Check | Result |
|---|---|
| `hermes --version` | Hermes Agent v0.10.0 (2026.4.16) ✓ |
| `vera-hermes-agent` profile listed | ✓ |
| SOUL.md read-only scope present | ✓ |
| Gateway stopped (expected) | ✓ |
| No cron jobs | ✓ |
| Chat round-trip | "vera hermes agent ready" ✓ |
| Healthcheck exit code | 0 ✓ |
| Repo tests | No Python files changed; test suite not re-run (no Python changes to validate) |

## Paths Used for vera-hermes-agent

| Item | Path |
|---|---|
| Profile root | `/home/patel/.hermes/profiles/vera-hermes-agent/` (WSL) |
| SOUL.md | `/home/patel/.hermes/profiles/vera-hermes-agent/SOUL.md` |
| config.yaml | `/home/patel/.hermes/profiles/vera-hermes-agent/config.yaml` |
| .env | `/home/patel/.hermes/profiles/vera-hermes-agent/.env` |
| Alias binary | `/home/patel/.local/bin/vera-hermes-agent` |
| Hermes binary | `/home/patel/.local/bin/hermes` |
| Healthcheck script | `scripts/vera_hermes_healthcheck.sh` (repo root) |

## Decisions Made

1. **Did not create a Windows-side wrapper script.** The WSL alias already works from any Windows terminal via `wsl bash -lc "vera-hermes-agent ..."`. A Windows `.bat` or `.ps1` wrapper would add surface area for no immediate gain.

2. **SOUL.md written directly via WSL heredoc.** The file is on the WSL filesystem; WSL bash is the correct write path. Content does not contain secrets.

3. **No gateway started.** The operator baseline does not need the gateway until messaging is configured. "Stopped" is the correct state for now.

4. **No skills added.** Skills require deliberate design (what queries to support, what ClickHouse credentials to use). Deferring to next session per scope constraints.

5. **Feature doc created at `docs/features/vera_hermes_operator_baseline.md`** rather than under `docs/specs/` (which is read-only by convention) or the obsidian vault (which is for planning notes, not shipped-feature documentation).

6. **Backend stays local.** Docker is available and is the right future isolation choice, but adding a Docker backend now would require additional config work with no operational benefit at the read-only baseline stage.

## Open Questions / Follow-Ups for Next Session

| Item | Notes |
|---|---|
| Operator query skills | Build 4 skills: `polytool-status`, `polytool-dev-logs`, `polytool-grafana`, `polytool-files` |
| Messaging gateway | Configure Discord or Telegram when skills are ready and messaging access is desired |
| Docker backend | Revisit when gateway is started; adds stronger isolation |
| `hermes update` | Binary is 204 commits behind as of 2026-04-23; test update in a fresh session to avoid mid-feature disruption |
| Grafana read-only queries | Decide whether skills use grafana_ro ClickHouse credentials directly or via `polytool` CLI |
| Healthcheck in CI | Not integrated; run manually for now |

## Codex Review

Not required. No execution-path files changed. Doc-only session with one shell script.
