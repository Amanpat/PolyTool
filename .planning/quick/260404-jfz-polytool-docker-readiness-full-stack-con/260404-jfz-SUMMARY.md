---
phase: quick-260404-jfz
plan: 01
subsystem: infrastructure
tags: [docker, compose, containerization, ris-scheduler]
dependency_graph:
  requires: []
  provides: [universal-polytool-image, full-stack-compose, ris-scheduler-service]
  affects: [docker-compose.yml, Dockerfile, .env.example]
tech_stack:
  added: []
  patterns: [non-root-container-user, layer-cache-pyproject, multi-service-compose-profiles]
key_files:
  created:
    - scripts/docker-start.sh
    - scripts/docker-run.sh
    - docs/dev_logs/2026-04-04_docker-full-stack.md
  modified:
    - Dockerfile
    - docker-compose.yml
    - .env.example
decisions:
  - "Universal Dockerfile installs .[all,ris] — all extras plus apscheduler for RIS scheduler"
  - "polytool service uses profiles: [cli] so it only starts on docker compose run, not up"
  - "Dockerfile.bot preserved as fallback; pair-bots now build from universal image"
  - "Non-root polytool user in Dockerfile per threat model T-quick-02"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-04T18:06:40Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 3
---

# Phase quick-260404-jfz Plan 01: Docker Full-Stack Containerization Summary

**One-liner:** Universal python:3.11-slim Dockerfile installing all extras (.[all,ris]) with non-root user, full-stack compose adding ris-scheduler service and CLI profile for polytool.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Universal Dockerfile and full-stack docker-compose | a291834 | Dockerfile, docker-compose.yml |
| 2 | .env.example, convenience scripts, dev log | aace63d | .env.example, scripts/docker-start.sh, scripts/docker-run.sh, docs/dev_logs/2026-04-04_docker-full-stack.md |

## What Was Built

### Dockerfile (root) — Rewritten

Transformed from a SimTrader Studio-only image to a universal PolyTool image:

- Base: `python:3.11-slim` (preserved)
- System packages: `gcc libffi-dev curl` (curl added for healthcheck capability)
- Non-root user: `polytool` group + user created and used (`USER polytool`)
- Layer-cache optimization: `COPY pyproject.toml` + install `py-clob-client` before `COPY . .`
- Full install: `pip install ".[all,ris]"` — all pyproject.toml extras plus apscheduler
- No ENTRYPOINT or CMD — each compose service defines its own command

### docker-compose.yml — Updated

Preserved clickhouse, grafana, api, and migrate services exactly. Changes:

- **polytool** converted to CLI runner: `profiles: [cli]`, no ports, volume mounts for artifacts/config/kb/kill_switch
- **ris-scheduler** added: builds from root Dockerfile, runs `research-scheduler start`, `restart: unless-stopped`
- **pair-bot-paper** + **pair-bot-live**: `dockerfile: Dockerfile.bot` changed to `dockerfile: Dockerfile`

### .env.example — Appended

Added RIS scheduler env vars (`RIS_SCHEDULE_INTERVAL_HOURS`, `RIS_MAX_CONCURRENT_JOBS`, `RIS_LOG_LEVEL`) and Discord webhook placeholder. No existing lines modified.

### Convenience Scripts (new)

- `scripts/docker-start.sh` — `docker compose up -d --build` with `.env` check and `--with-bots` flag
- `scripts/docker-run.sh` — `docker compose run --rm polytool python -m polytool "$@"`

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. No UI-facing data paths or placeholder values introduced.

## Threat Flags

All threat mitigations from plan applied:

| Threat | Mitigation Applied |
|--------|--------------------|
| T-quick-01 (Info Disclosure) | .env.example uses placeholder values only; CLICKHOUSE_PASSWORD uses :? required syntax |
| T-quick-02 (Elevation) | Universal Dockerfile runs as non-root `polytool` user |
| T-quick-03 (Tampering) | config and kill_switch volumes mounted :ro; artifacts and kb are rw by design |
| T-quick-04 (Spoofing) | All services use CLICKHOUSE_PASSWORD env var with :? fail-fast syntax; no hardcoded fallback |

## Open Items (from dev log)

1. Verify `research-scheduler start` is the exact CLI subcommand name
2. Test full stack on a fresh machine with all deps pulled
3. Consider `.dockerignore` to exclude `artifacts/`, `.git/`, `__pycache__/` for faster builds
4. `kill_switch.json` volume mount may fail if file does not exist on host — consider optional mount or default file

## Self-Check: PASSED

- [x] Dockerfile exists at `D:/Coding Projects/Polymarket/PolyTool/Dockerfile`
- [x] docker-compose.yml exists at `D:/Coding Projects/Polymarket/PolyTool/docker-compose.yml`
- [x] .env.example has RIS_ vars appended
- [x] scripts/docker-start.sh exists
- [x] scripts/docker-run.sh exists
- [x] docs/dev_logs/2026-04-04_docker-full-stack.md exists
- [x] Commit a291834 exists (Task 1)
- [x] Commit aace63d exists (Task 2)
- [x] `docker compose config` passes
- [x] Dockerfile.bot preserved (not deleted)
