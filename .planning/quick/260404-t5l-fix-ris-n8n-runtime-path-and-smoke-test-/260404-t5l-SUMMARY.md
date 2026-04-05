---
phase: quick
plan: 260404-t5l
subsystem: infra/n8n
tags: [n8n, docker, ris, workflow, smoke-test]
dependency_graph:
  requires: [quick-260404-sb4]
  provides: [working-n8n-workflow-runtime]
  affects: [docs/RIS_OPERATOR_GUIDE.md, docs/adr/0013-ris-n8n-pilot-scoped.md, infra/n8n/]
tech_stack:
  added: [docker-beside-docker, docker-cli in n8n image, n8n import:workflow CLI]
  patterns: [custom docker image build, group_add socket permissions]
key_files:
  created:
    - infra/n8n/Dockerfile
    - docs/dev_logs/2026-04-05_ris_n8n_runtime_fix.md
  modified:
    - docker-compose.yml
    - infra/n8n/import-workflows.sh
    - infra/n8n/workflows/ris_academic_ingest.json
    - infra/n8n/workflows/ris_blog_ingest.json
    - infra/n8n/workflows/ris_freshness_refresh.json
    - infra/n8n/workflows/ris_github_ingest.json
    - infra/n8n/workflows/ris_health_check.json
    - infra/n8n/workflows/ris_manual_acquire.json
    - infra/n8n/workflows/ris_reddit_others.json
    - infra/n8n/workflows/ris_reddit_polymarket.json
    - infra/n8n/workflows/ris_scheduler_status.json
    - infra/n8n/workflows/ris_weekly_digest.json
    - infra/n8n/workflows/ris_youtube_ingest.json
    - .env.example
    - docs/RIS_OPERATOR_GUIDE.md
    - docs/adr/0013-ris-n8n-pilot-scoped.md
    - docs/CURRENT_STATE.md
decisions:
  - "Docker-beside-docker pattern: n8n uses docker-cli + socket mount to exec into ris-scheduler instead of installing Python/PolyTool in the n8n image"
  - "group_add: ['0'] required on Docker Desktop/WSL2 because docker.sock is owned root:root (GID 0); production Linux should use the actual docker group GID"
  - "Workflow import uses n8n import:workflow CLI (not REST API) because n8n 1.88.0 requires X-N8N-API-KEY header for REST API, which is unavailable without UI login"
  - "Workflow JSON tags changed from string arrays to empty arrays; string tags cause SQLITE_CONSTRAINT violation in n8n 1.88.0 schema"
metrics:
  duration: "~35 minutes"
  completed: "2026-04-05"
  tasks_completed: 3
  files_changed: 17
---

# Phase quick Plan 260404-t5l: Fix RIS n8n Runtime Path and Smoke Test Summary

Custom n8n image with docker-cli for docker-beside-docker pattern: all 11 workflow commands now route through `docker exec polytool-ris-scheduler`; smoke test confirmed build, socket bridge, and 11/11 workflow imports.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Build custom n8n image, update workflow commands | `1a648b1` | Dockerfile, docker-compose.yml, 11 workflow JSONs, .env.example |
| 2 | Smoke test: build, start, verify bridge, import workflows | `8a6524c` | docker-compose.yml, import-workflows.sh, 11 workflow JSONs, dev log |
| 3 | Fix stale doc commands, update ADR-0013, update CURRENT_STATE | `80b707e` | RIS_OPERATOR_GUIDE.md, ADR-0013, CURRENT_STATE.md |

## What Changed

### Task 1: Custom Image and Workflow Command Fix

- `infra/n8n/Dockerfile`: New file. Extends `n8nio/n8n:1.88.0` with `apk add docker-cli`.
- `docker-compose.yml`: n8n service now builds from Dockerfile, mounts `/var/run/docker.sock`,
  adds `N8N_EXEC_CONTAINER` env var, adds `group_add: ["0"]` for socket access on Docker Desktop.
- All 11 workflow JSON `command` fields prefixed with `docker exec polytool-ris-scheduler`.
- `.env.example`: Added `N8N_EXEC_CONTAINER=polytool-ris-scheduler`.

### Task 2: Smoke Test

Smoke test commands and verbatim output captured in `docs/dev_logs/2026-04-05_ris_n8n_runtime_fix.md`.

Results:
- `docker compose --profile ris-n8n build n8n`: BUILD SUCCEEDED (docker-cli 27.3.1 installed)
- `docker compose --profile ris-n8n up -d n8n`: Container started, port 5678 open
- `docker exec polytool-n8n docker --version`: Docker version 27.3.1 confirmed
- `docker exec polytool-n8n docker exec polytool-ris-scheduler python -m polytool research-health`: PASS (health output received)
- `bash infra/n8n/import-workflows.sh polytool-n8n`: 11/11 imported successfully

### Task 3: Doc Fixes

- `docs/RIS_OPERATOR_GUIDE.md`: Removed stale `research-scheduler stop` and `research-scheduler list`
  commands (not implemented). Added `research-scheduler status` and `run-job` as correct alternatives.
- `docs/adr/0013-ris-n8n-pilot-scoped.md`: Updated workflow table from 3 to 11 entries,
  updated "Image and versioning" to describe custom build + docker-beside-docker pattern,
  added Docker socket security risk row with `group_add` caveat.
- `docs/CURRENT_STATE.md`: Added quick-260404-t5l entry with smoke test results.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docker socket permission denied inside n8n container**
- **Found during:** Task 2, exec bridge verification
- **Issue:** n8n's `node` user (uid=1000) could not connect to `/var/run/docker.sock` (owned root:root mode 0660 on Docker Desktop/WSL2). Error: `permission denied while trying to connect to the Docker daemon socket`
- **Fix:** Added `group_add: ["0"]` to the n8n service block in docker-compose.yml, adding the node user to the root group for socket access.
- **Files modified:** `docker-compose.yml`
- **Commit:** `8a6524c`

**2. [Rule 1 - Bug] import-workflows.sh used basic auth (deprecated in n8n 1.88.0)**
- **Found during:** Task 2, first workflow import attempt
- **Issue:** n8n 1.88.0 REST API requires `X-N8N-API-KEY` header; basic auth returns HTTP 401. All 11 imports failed.
- **Fix:** Rewrote `import-workflows.sh` to use `n8n import:workflow --input=<file>` CLI via `docker exec`. Native CLI requires no API key.
- **Files modified:** `infra/n8n/import-workflows.sh`
- **Commit:** `8a6524c`

**3. [Rule 1 - Bug] Workflow JSON tags were string arrays; n8n 1.88.0 expects tag objects**
- **Found during:** Task 2, second import attempt
- **Issue:** All 11 workflow JSONs had `"tags": ["ris", ...]`. n8n 1.88.0 SQLite schema stores tags as relational objects with `id` field. String tags caused `SQLITE_CONSTRAINT: NOT NULL constraint failed: workflows_tags.tagId` on all imports.
- **Fix:** Changed all 11 `"tags": [...]` to `"tags": []`. Tags are display metadata with no effect on workflow execution.
- **Files modified:** All 11 `infra/n8n/workflows/*.json`
- **Commit:** `8a6524c`

## Smoke Test: PASS

| Check | Result |
|-------|--------|
| Build polytool-n8n:1.88.0 | PASS |
| docker-cli version inside n8n | PASS (v27.3.1) |
| docker exec bridge n8n -> ris-scheduler | PASS (research-health output received) |
| 11/11 workflows imported | PASS (all OK, 0 failed) |

## Self-Check: PASSED

- `infra/n8n/Dockerfile`: FOUND
- `docs/dev_logs/2026-04-05_ris_n8n_runtime_fix.md`: FOUND
- Commit `1a648b1`: task 1 confirmed
- Commit `8a6524c`: task 2 confirmed
- Commit `80b707e`: task 3 confirmed
