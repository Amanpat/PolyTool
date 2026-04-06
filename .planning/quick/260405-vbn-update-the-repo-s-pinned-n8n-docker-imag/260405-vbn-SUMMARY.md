---
phase: quick-260405-vbn
plan: "01"
subsystem: infra/n8n
tags: [n8n, docker, version-bump, ris-pilot]
dependency_graph:
  requires: []
  provides: [n8n-1.123.28-image]
  affects: [ris-n8n-pilot, docker-compose-ris-n8n-profile]
tech_stack:
  added: [docker-static-binary-install-pattern]
  patterns: [docker-hardened-image-compat, wget-static-binary]
key_files:
  created:
    - docs/dev_logs/2026-04-05_n8n_version_bump.md
  modified:
    - infra/n8n/Dockerfile
    - docs/adr/0013-ris-n8n-pilot-scoped.md
    - docs/CURRENT_STATE.md
decisions:
  - "Replaced apk add docker-cli with Docker static binary download (docker-29.3.1) because n8n 1.123.28 DHI removes the apk binary"
  - "Stayed on 1.x line; 2.x migration deferred (requires new ADR)"
metrics:
  duration: "~22 minutes"
  completed: "2026-04-05"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase quick-260405-vbn Plan 01: n8n Version Bump Summary

**One-liner:** Bumped n8n base image from 1.88.0 to 1.123.28 with Docker static binary fix for DHI Alpine compatibility.

## What Was Done

Updated the pinned n8n Docker base image tag from `n8nio/n8n:1.88.0` to `n8nio/n8n:1.123.28`
(latest stable 1.x release as of 2026-04-05), updated all docs referencing the old version,
and verified the container builds and starts cleanly.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update Dockerfile and docs from 1.88.0 to 1.123.28 | ab8cb5f | infra/n8n/Dockerfile, docs/adr/0013-ris-n8n-pilot-scoped.md, docs/CURRENT_STATE.md |
| 2 | Build, start, verify n8n container, and write dev log | 311e831 | infra/n8n/Dockerfile (auto-fix), docs/dev_logs/2026-04-05_n8n_version_bump.md |

## Success Criteria Met

- [x] `infra/n8n/Dockerfile` FROM line uses `n8nio/n8n:1.123.28`
- [x] `docker compose --profile ris-n8n build n8n` succeeds
- [x] `docker compose --profile ris-n8n up -d n8n` starts a healthy container
- [x] `curl -s http://localhost:5678/healthz` returns `{"status":"ok"}`
- [x] `docker exec polytool-n8n docker --version` returns Docker version 29.3.1
- [x] All docs mentioning 1.88.0 in operational context updated to 1.123.28
- [x] Dev log written with verbatim evidence
- [x] Historical dev logs not modified
- [x] docker-compose.yml unchanged
- [x] polytool CLI still loads (`python -m polytool --help` OK)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docker Hardened Image (DHI) removes apk binary in n8n 1.123.28**

- **Found during:** Task 2 (build step)
- **Issue:** n8n 1.123.28 ships as a Docker Hardened Image (DHI) on Alpine 3.22. Unlike
  earlier 1.x releases, DHI intentionally removes the `apk` package manager binary.
  The original `RUN apk add --no-cache docker-cli` command fails with:
  `/bin/sh: apk: not found` (exit code 127).
- **Fix:** Replaced `apk add docker-cli` with a Docker static binary download pattern:
  ```dockerfile
  RUN wget -q -O /tmp/docker.tgz https://download.docker.com/linux/static/stable/x86_64/docker-29.3.1.tgz \
      && tar -xz -f /tmp/docker.tgz -C /tmp \
      && mv /tmp/docker/docker /usr/local/bin/docker \
      && chmod +x /usr/local/bin/docker \
      && rm -rf /tmp/docker /tmp/docker.tgz
  ```
  Docker static binary version pinned to `29.3.1` (latest stable as of 2026-04-05).
  `wget` is available in DHI (busybox implementation at `/usr/bin/wget`).
- **Files modified:** `infra/n8n/Dockerfile`
- **Commit:** 311e831

## Verification Results

```
docker compose config --quiet            -> exit 0 (valid)
docker compose --profile ris-n8n build  -> polytool-n8n:latest Built
docker compose --profile ris-n8n up -d  -> Container polytool-n8n Started (Up)
curl http://localhost:5678/healthz       -> {"status":"ok"}
docker exec polytool-n8n docker --version -> Docker version 29.3.1, build c2be9cc
bash infra/n8n/import-workflows.sh      -> 11 succeeded, 0 failed
python -m polytool --help               -> loads OK, no import errors
```

## Known Stubs

None. All operational.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes
introduced. The docker.sock mount risk was pre-existing and accepted in ADR-0013 (T-quick-02).

## Notes for Future Bumps

When upgrading n8n beyond 1.123.28:
- DHI images do not have `apk` binary. Continue using Docker static binary pattern.
- Update `docker-29.3.1.tgz` URL if a newer Docker version is desired.
- Check if `wget` is still available in the DHI base before assuming the pattern works.

## Self-Check: PASSED

- [x] `infra/n8n/Dockerfile` exists and contains `1.123.28`
- [x] Commits `ab8cb5f` and `311e831` verified in git log
- [x] Dev log at `docs/dev_logs/2026-04-05_n8n_version_bump.md` exists
- [x] Summary file written to `.planning/quick/260405-vbn-.../260405-vbn-SUMMARY.md`
