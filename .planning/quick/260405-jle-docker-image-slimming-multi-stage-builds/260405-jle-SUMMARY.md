---
phase: quick-260405-jle
plan: 01
subsystem: docker
tags: [docker, image-slimming, multi-stage, pair-bot, build-optimization]

dependency_graph:
  requires: [quick-260405-j2t]  # .dockerignore / build perf hygiene
  provides: [multi-stage-root-image, lean-pair-bot-image, compose-bot-wiring]
  affects: [docker-compose.yml, Dockerfile, Dockerfile.bot]

tech_stack:
  added: []
  patterns:
    - Multi-stage Docker build (builder + runtime stages)
    - BuildKit cache mounts (apt, pip)
    - Selective COPY from builder stage (site-packages, bin)
    - Extras-based dependency scoping ([live,simtrader] vs [all,ris])

key_files:
  created:
    - docs/dev_logs/2026-04-05_docker_image_slimming.md
  modified:
    - Dockerfile
    - Dockerfile.bot
    - docker-compose.yml

decisions:
  - Multi-stage pattern: COPY --from=builder /usr/local/lib/python3.11/site-packages and /usr/local/bin (not full /usr/local) to avoid copying compiler binaries
  - Python version aligned at 3.11-slim across both Dockerfiles (Dockerfile.bot was 3.12-slim)
  - Dockerfile.bot excludes services/ (pair-bot has no dependency on FastAPI service code)
  - No ENTRYPOINT/CMD in Dockerfile.bot: compose services already specify full command arrays; removed old hard-coded ENTRYPOINT to match root Dockerfile pattern
  - pair-bot-live and pair-bot-paper profiles: ["pair-bot"] left intact (safety gate, not changed)

metrics:
  duration_seconds: 134
  completed: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
  files_created: 1
---

# Phase quick-260405-jle Plan 01: Docker Image Slimming Summary

**One-liner:** Multi-stage root Dockerfile (gcc/libffi-dev builder-only) + modernized Dockerfile.bot with [live,simtrader]-only deps for pair-bot compose services.

## What Was Built

### Task 1: Multi-stage root Dockerfile + modernize Dockerfile.bot

**Root Dockerfile** converted from single-stage to two-stage build:
- Stage 1 `builder`: installs `gcc`, `libffi-dev`, all Python packages (`[all,ris]`)
- Stage 2 `runtime`: copies only `/usr/local/lib/python3.11/site-packages` and `/usr/local/bin` from builder, installs only `curl` (for healthchecks), creates `polytool` non-root user
- Build tools (`gcc`, `~100 MB`, `libffi-dev`, `~5 MB`) never appear in runtime image

**Dockerfile.bot** rewritten as modern multi-stage:
- `python:3.11-slim` (was `3.12-slim`, aligned with root)
- BuildKit syntax header + apt/pip cache mounts
- Installs only `[live,simtrader]` extras (py-clob-client + websocket-client + base deps)
- Selective COPY: `polytool/`, `packages/`, `tools/` only — no `services/`, no `COPY . .`
- Removes: sentence-transformers, chromadb, duckdb, pyarrow, apscheduler, pytest, mcp, fastapi, uvicorn (~500 MB+ of unnecessary deps)
- No ENTRYPOINT/CMD (compose services set their own command arrays)
- Non-root `botuser` created and used

### Task 2: Point pair-bot compose services to Dockerfile.bot

`docker-compose.yml`: changed `dockerfile: Dockerfile` to `dockerfile: Dockerfile.bot`
for both `pair-bot-paper` and `pair-bot-live` services. All other service definitions,
profiles, volumes, env_file, command, restart unchanged.

Dev log written at `docs/dev_logs/2026-04-05_docker_image_slimming.md`.

## Verification Results

| Check | Result |
|-------|--------|
| `docker compose config --quiet` | PASS |
| pair-bot services: 2x Dockerfile.bot refs in profile config | PASS |
| Root Dockerfile: `FROM python:3.11-slim AS builder` present | PASS |
| Root Dockerfile: runtime `FROM python:3.11-slim` present | PASS |
| Dockerfile.bot: `[live,simtrader]` (not `[all,ris]`) | PASS |
| No `COPY . .` in either Dockerfile | PASS |
| Profile gating: `profiles: ["pair-bot"]` on both services | INTACT |
| `python -m polytool --help` (Python regression) | PASS |

## Commits

| Task | Commit | Files |
|------|--------|-------|
| Task 1: Multi-stage Dockerfiles | `686b1b2` | Dockerfile, Dockerfile.bot |
| Task 2: Compose wiring + dev log | `41b77a3` | docker-compose.yml, docs/dev_logs/2026-04-05_docker_image_slimming.md |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — infrastructure changes only, no product logic.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced.
Multi-stage build is standard pattern; threat model items T-quick-02 (secrets from env_file
only) and T-quick-03 (non-root runtime users) are both satisfied:
- Root image: `USER polytool` in runtime stage
- Dockerfile.bot: `USER botuser` in runtime stage

## Self-Check

Files created/modified:
- `Dockerfile` — modified (multi-stage)
- `Dockerfile.bot` — modified (modernized multi-stage)
- `docker-compose.yml` — modified (pair-bot services point to Dockerfile.bot)
- `docs/dev_logs/2026-04-05_docker_image_slimming.md` — created
- `.planning/quick/260405-jle-docker-image-slimming-multi-stage-builds/260405-jle-SUMMARY.md` — created

## Self-Check: PASSED

All 5 files confirmed present on disk. Both task commits (686b1b2, 41b77a3) confirmed in git log.
