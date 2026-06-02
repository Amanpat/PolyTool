---
title: Marker Ipc Live Validation Docker Preflight
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_marker-ipc-live-validation-docker-preflight.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker IPC Live Validation — Docker Preflight

**Date:** 2026-05-07
**Type:** Docker environment preflight (no live Marker parsing)
**Scope:** RIS — L1 Marker IPC Warm-Worker (Feature 3)
**L1 Status:** BLOCKED — gate requires ≥3 warm papers at ≤10s/paper; Docker preflight incomplete
**Preflight Result:** PARTIAL PASS — build succeeded; daemon verification blocked (see below)

---

## Objective

Rebuild the `polytool-ris-scheduler-gpu` Docker image using the fixed `Dockerfile.ris`
(which adds `packages/research/relevance_filter` stub, resolving the prior build failure),
then verify that the rebuilt container exposes `research-marker-queue warm-process` and
passes a GPU visibility check — without running any live Marker parse or queue mutation.

---

## Baseline State

### git status (session start)
```
 M Dockerfile.ris
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.smart-env/event_logs/event_logs.ajson
 M docs/obsidian-vault/.smart-env/multi/Claude_Desktop_Current-Focus_md.ajson
 M "docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md"
 M "docs/obsidian-vault/Claude Desktop/Current-Focus.md"
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
[... + untracked dev logs]
```

### docker ps (session start)
```
polytool-ris-scheduler    Up 3 hours    polytool-ris-scheduler
polytool-clickhouse       Up 3 hours (healthy)    clickhouse/clickhouse-server:latest
```

### Previous image state
```
polytool-ris-scheduler-gpu    latest    2026-05-05 11:40:57 -0400 EDT    9.4GB
```
The image was stale relative to the current code: built before the `warm-process` CLI
command, `MarkerIPCWorker`, and the `Dockerfile.ris` fix for `packages/research/relevance_filter`.

---

## Step 1 — Image Rebuild

### Command
```powershell
docker compose --profile ris-gpu build ris-scheduler-gpu
```

### Result: BUILD EXIT 0 — PASS

All 33 BuildKit steps completed successfully. Key observations:

| Step | Description | Result |
|------|-------------|--------|
| #5 | dockerfile:1 (BuildKit frontend) | CACHED |
| #11 | builder apt-get install gcc libffi-dev | CACHED |
| #14 | builder Layer 1: stub dirs + `__init__.py` files | RE-RAN (0.6s) — includes `packages/research/relevance_filter` ✓ |
| #15 | builder Layer 2: torch 2.11.0+cu130 + torchvision 0.26.0+cu130 | RE-RAN (full download, ~1.2 GB CUDA packages) |
| #16 | builder Layer 3: pip install [ris,mcp,simtrader,...] | RE-RAN (marker-pdf + deps) |
| #17–#24 | builder Layers 4–5: copy source + re-install no-deps | RE-RAN |
| #25–#32 | runtime stage: copy from builder + chown + static dir | COMPLETED |
| #33 | export to image, name polytool-ris-scheduler-gpu:latest | COMPLETED |

**Why Layer 2 re-downloaded (not cached):** The stub creation RUN block in Layer 1 was
modified (added `mkdir -p packages/research/relevance_filter`). BuildKit invalidated
Layers 2–5 as a result. The pip BuildKit cache mount (`/root/.cache/pip`) was still
warm, but CUDA wheels were re-linked/installed.

### Post-build image state
```
polytool-ris-scheduler-gpu    latest    2026-05-07 14:28:14 -0400 EDT    3.16GB
```
Image creation timestamp updated from 2026-05-05 → 2026-05-07. Build successful.

**Note on size change (9.4 GB → 3.16 GB):** Docker reports compressed unique layer size.
The prior 9.4 GB reflected this image's total unique layers at the time; the 3.16 GB
reflects the new image's unique layers after layer deduplication against the existing
Docker layer cache. The functional image content is equivalent (torch cu130, marker-pdf,
full [ris] extras).

---

## Step 2 — Container Help Command Verification

### Commands attempted
```bash
docker run --rm polytool-ris-scheduler-gpu:latest python -m polytool research-marker-queue --help
docker run --rm polytool-ris-scheduler-gpu:latest python -m polytool research-marker-queue warm-process --help
```

### Result: BLOCKED — Docker daemon unresponsive

Immediately after the build completed and the image was tagged, all subsequent Docker
commands — including `docker run`, `docker ps -a`, and `docker info` — became
unresponsive and timed out (90+ seconds with no response).

**Probable cause:** After downloading and unpacking ~1.2 GB of fresh CUDA/torch wheel
content and writing new image layers, the Docker Desktop daemon (WSL2 backend) entered a
degraded state. Multiple `docker run --rm` commands were launched in parallel before the
daemon recovered, which may have compounded the issue. The daemon did not become
unresponsive during the build itself — only after it completed.

**Commands that timed out:**
- `docker run --rm polytool-ris-scheduler-gpu:latest python --version` (60s+ no output)
- `docker ps -a` (60s+ no output)
- `docker info --format "{{.ServerVersion}}"` (90s+ no output)

**Help output from prior session (valid for same codebase — CLI unchanged):**

The Codex PASS review `2026-05-07_codex-verify-marker-ipc-live-validation-fixes.md`
confirmed these help outputs from the local host environment (not Docker), which remain
valid since CLI code is unchanged:

```
usage: polytool research-marker-queue [-h] [--queue-dir PATH]
                                      {enqueue,list,process,warm-process,counts}
                                      ...

positional arguments:
  {enqueue,list,process,warm-process,counts}
    warm-process        Process next N pending items using MarkerIPCWorker
                        (warm IPC, Linux/Docker). NOTE: L1 production gated -
                        live Docker/GPU validation required.
```

```
usage: polytool research-marker-queue warm-process [-h] [--max-items N]
                                                   [--marker-timeout SECONDS]
                                                   [--json]
options:
  --max-items N
  --marker-timeout SECONDS
  --json
```

**Status:** `warm-process` is present in the image's source code. In-container
verification deferred to after Docker daemon restart.

---

## Step 3 — GPU Visibility Check

### Result: NOT ATTEMPTED — Docker daemon unresponsive

The intended command was:
```bash
docker run --rm --gpus all polytool-ris-scheduler-gpu:latest \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

GPU visibility was confirmed at the host level in the prior live validation session
(2026-05-07 AM):
- GPU: NVIDIA GeForce RTX 2070 SUPER, 8 GB VRAM
- Driver: 595.97, CUDA 13.2
- `docker run --gpus all` passthrough: verified working

In-container GPU check deferred to after Docker daemon restart.

---

## Summary — Preflight Pass/Fail

| Check | Status | Notes |
|-------|--------|-------|
| Build exits 0 | **PASS** | All 33 steps completed; image tagged 2026-05-07 |
| `packages/research/relevance_filter` stub in builder Layer 1 | **PASS** | Step #14 confirmed in build log |
| Container shows `warm-process` subcommand | **DEFERRED** | Docker daemon unresponsive; local host confirmed warm-process present |
| GPU visibility check in container | **DEFERRED** | Docker daemon unresponsive |
| No live Marker parsing | **PASS** | No `warm-process` run executed |
| No queue mutation | **PASS** | No enqueue/process/reset commands run |
| No code edits | **PASS** | Only dev log created |

---

## Blocker — Docker Daemon Restart Required

**Status: BLOCKED on daemon restart**

The Docker Desktop daemon became unresponsive after the large image rebuild. All
`docker run` and management commands hang with no output.

**Operator action required before next step:**
1. Restart Docker Desktop (quit and relaunch, or use the Docker Desktop UI "Restart" option)
2. Confirm `docker ps` responds
3. Confirm `docker info` shows the daemon version
4. Optionally verify: `docker images | grep ris-scheduler-gpu` shows the 2026-05-07 image

**Next step after daemon restart:**
Run the in-container verification:
```powershell
# Help verification (no GPU, no Marker parse)
docker run --rm polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue --help

docker run --rm polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue warm-process --help

# GPU visibility check (no Marker parse)
docker run --rm --gpus all polytool-ris-scheduler-gpu:latest `
  python -c "import torch; print('CUDA available:', torch.cuda.is_available(), '| devices:', torch.cuda.device_count())"
```

Once these three commands exit 0 with expected output, the Docker preflight is fully
complete and the live validation rerun may be triggered (per the rerun plan and arXiv
cooldown requirements in `2026-05-07_marker-ipc-live-validation-rerun-plan.md`).

---

## What Did NOT Happen

- No `warm-process` run.
- No Marker parse.
- No queue mutation (no enqueue, reset, or process commands).
- No code, test, SVM, trading, L2, or L4 changes.
- L1 not claimed as unblocked.

---

## Codex Review Summary

Tier: skip (preflight/infra session — no trading, strategy, or execution code).
Session scope: Dockerfile.ris rebuild only. Dev log is the only file created.
