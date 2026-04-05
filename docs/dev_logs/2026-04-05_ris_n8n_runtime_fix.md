# 2026-04-05 RIS n8n Runtime Path Fix and Smoke Test

**Task:** quick-260404-t5l
**Branch:** worktree-agent-a9910d5a (based on feat/ws-clob-feed)
**Status:** COMPLETE

## Problem

All 11 n8n workflow JSON templates shipped with bare `python -m polytool ...` commands in their
Execute Command nodes. These commands fail inside the stock n8n container because n8n has no
Python or PolyTool installation. Every cron trigger and manual run would exit non-zero silently.

## Solution: Docker-Beside-Docker

The fix uses a custom n8n image (`polytool-n8n:1.88.0`) that extends `n8nio/n8n:1.88.0` with
`docker-cli` installed, and mounts `/var/run/docker.sock` from the host. All workflow commands
are routed through `docker exec polytool-ris-scheduler python -m polytool ...` so they execute
inside the already-running `polytool-ris-scheduler` container.

## Files Changed (Task 1)

| File | Change |
|------|--------|
| `infra/n8n/Dockerfile` | NEW: custom image extending n8nio/n8n:1.88.0 with docker-cli |
| `docker-compose.yml` | Updated n8n service to build from Dockerfile, mount docker.sock, add `group_add: ["0"]`, add `N8N_EXEC_CONTAINER` env var |
| `infra/n8n/workflows/*.json` (11 files) | Prefixed all `command` fields with `docker exec polytool-ris-scheduler` |
| `.env.example` | Added `N8N_EXEC_CONTAINER=polytool-ris-scheduler` |
| `infra/n8n/import-workflows.sh` | Updated to use `n8n import:workflow` CLI (replaces broken basic-auth REST API path) |

## Smoke Test Commands and Output (Task 2)

### Build custom n8n image

```
$ docker compose --profile ris-n8n build n8n
CLICKHOUSE_USER warning (not set, expected -- CLICKHOUSE_PASSWORD=admin used inline)
#7 [2/2] RUN apk add --no-cache docker-cli
#7 5.631 (49/49) Installing tzdata (2026a-r0)
#7 5.785 OK: 93 MiB in 66 packages
#7 DONE 8.2s
 polytool-n8n:1.88.0  Built
```

Result: BUILD SUCCEEDED

### Start n8n

```
$ docker compose --profile ris-n8n up -d n8n
 Network agent-a9910d5a_polytool  Created
 Volume agent-a9910d5a_n8n_data  Created
 Container polytool-n8n  Started
```

Result: Container started, port 5678 open.

### Verify docker-cli inside n8n container

```
$ docker exec polytool-n8n docker --version
Docker version 27.3.1, build ce1223035ac3ab8922717092e63a184cf67b493d
```

Result: docker-cli 27.3.1 confirmed inside n8n container.

### Verify exec bridge (n8n -> ris-scheduler)

```
$ docker exec polytool-n8n docker exec polytool-ris-scheduler python -m polytool research-health
RIS Health Summary (48h window, 14 runs) -- YELLOW

CHECK                                    STATUS   MESSAGE
--------------------------------------------------------------------------------
pipeline_failed                          GREEN    No pipeline errors detected.
no_new_docs_48h                          GREEN    13 document(s) accepted in the monitored window.
accept_rate_low                          GREEN    Accept rate is healthy: 100.0% (13/13).
accept_rate_high                         YELLOW   Accept rate is suspiciously high: 100.0% (13/13). Gate may be too lenient.
model_unavailable                        GREEN    [DEFERRED] Model availability check requires provider event data. Not yet wired.
rejection_audit_disagreement             GREEN    [DEFERRED] Rejection audit check requires audit runner. Not yet wired.

Note: Checks marked [DEFERRED] are not yet wired to data sources. GREEN = no data, not verified healthy.
[RIS ALERT] YELLOW | accept_rate_high | ...
```

Result: EXEC BRIDGE VERIFIED. research-health output received from inside ris-scheduler container.

### Import all 11 workflows

```
$ bash infra/n8n/import-workflows.sh polytool-n8n
Importing n8n workflows from .../infra/n8n/workflows into container 'polytool-n8n' ...
  Importing: ris_academic_ingest ... Successfully imported 1 workflow. OK
  Importing: ris_blog_ingest ... Successfully imported 1 workflow. OK
  Importing: ris_freshness_refresh ... Successfully imported 1 workflow. OK
  Importing: ris_github_ingest ... Successfully imported 1 workflow. OK
  Importing: ris_health_check ... Successfully imported 1 workflow. OK
  Importing: ris_manual_acquire ... Successfully imported 1 workflow. OK
  Importing: ris_reddit_others ... Successfully imported 1 workflow. OK
  Importing: ris_reddit_polymarket ... Successfully imported 1 workflow. OK
  Importing: ris_scheduler_status ... Successfully imported 1 workflow. OK
  Importing: ris_weekly_digest ... Successfully imported 1 workflow. OK
  Importing: ris_youtube_ingest ... Successfully imported 1 workflow. OK

Import complete: 11 succeeded, 0 failed.
```

Result: ALL 11 WORKFLOWS IMPORTED SUCCESSFULLY.

## Deviations Encountered

### Deviation 1 (Rule 1 - Bug): Docker socket permission denied

- **Found during:** Task 2, exec bridge verification step
- **Issue:** n8n's `node` user (uid=1000, gid=1000) could not connect to `/var/run/docker.sock`
  because the socket was owned by root:root with mode 0660 (Docker Desktop / WSL2 behavior).
  Error: `permission denied while trying to connect to the Docker daemon socket`
- **Fix:** Added `group_add: ["0"]` to the n8n service in docker-compose.yml. This adds the
  `node` user to the root group (GID 0), granting read/write access to the socket without
  changing ownership or making the socket world-accessible.
- **Files modified:** `docker-compose.yml`

### Deviation 2 (Rule 1 - Bug): n8n 1.88.0 import API requires API key, not basic auth

- **Found during:** Task 2, first workflow import attempt
- **Issue:** `import-workflows.sh` used `curl -u user:pass` (basic auth). n8n 1.88.0 deprecated
  basic auth for the REST API and requires `X-N8N-API-KEY` header. Result: HTTP 401 for all 11.
- **Fix:** Rewrote `import-workflows.sh` to use `n8n import:workflow --input=<file>` CLI
  (executed via `docker exec`) instead of the REST API. Native CLI import requires no API key.
- **Files modified:** `infra/n8n/import-workflows.sh`

### Deviation 3 (Rule 1 - Bug): Workflow JSON tags field uses string arrays, fails SQLite constraint

- **Found during:** Task 2, second import attempt (after import script fix)
- **Issue:** All 11 workflow JSONs had `"tags": ["ris", ...]` with string values. n8n 1.88.0
  internal schema expects tag objects with `id` fields. Import failed with:
  `SQLITE_CONSTRAINT: NOT NULL constraint failed: workflows_tags.tagId`
- **Fix:** Changed all 11 `"tags": [...]` fields to `"tags": []`. Tags are display metadata;
  removing them has zero effect on workflow execution.
- **Files modified:** All 11 `infra/n8n/workflows/*.json`

## Security Notes

- `group_add: ["0"]` adds n8n to the root group on Docker Desktop / WSL2. This grants access to
  the Docker socket, which allows executing arbitrary commands on any container. This is the
  intended capability for the docker-beside-docker pattern and matches the documented security
  tradeoff in ADR-0013.
- On production Linux hosts, the docker group GID is typically non-zero (e.g., GID 999). The
  correct value should be verified with `stat /var/run/docker.sock` on the host and updated in
  docker-compose.yml accordingly. See ADR-0013 for the updated security risk entry.

## Codex Review

Tier: Skip (infra config, workflow JSON, import shell script -- no execution/strategy logic).

## Result Summary

| Check | Result |
|-------|--------|
| Build polytool-n8n:1.88.0 | PASS |
| docker-cli inside n8n | PASS (v27.3.1) |
| exec bridge n8n -> ris-scheduler | PASS (research-health output verified) |
| 11/11 workflows imported | PASS |
