---
title: Docker Storage Optimization
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-04_docker-storage-optimization.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Docker Storage Optimization

Date: 2026-05-04  
Scope: Reduce Docker/WSL footprint to unblock L1 Marker GPU validation  
Status: Complete — runbook written, .dockerignore tightened, Dockerfile.ris annotated

---

## Problem

L1 Marker GPU validation was blocked because Docker + WSL grew to ~73 GB and filled C:.
Docker GPU passthrough confirmed working (RTX 2070 Super visible via nvidia-smi), but the
Marker benchmark could not continue due to disk exhaustion. Root causes were identified
and a prevention runbook was written. L1 is still NOT shipped — it resumes once disk is
healthy and the GPU image rebuilds cleanly.

---

## Root Cause Hypotheses (Confirmed)

### Primary: GPU image is large and repeated failed builds accumulate

The `Dockerfile.ris` runtime image is ~5–6 GB:
- `torch==2.11.0+cu130` alone installs ~2.5 GB (CUDA runtime bundled in wheel)
- `marker-pdf` + `transformers` + `timm` + `surya-ocr` dependency tree: ~2 GB
- Remaining deps and app source: ~300 MB

Each failed rebuild leaves a dangling image of the same size. Three failed builds
(cu124 mismatch → fix → crash) = ~15–18 GB of dangling images before prune.

### Secondary: BuildKit pip cache accumulates separately

The `--mount=type=cache,target=/root/.cache/pip` BuildKit cache is shared across builds
and lives on the Docker host. For the CUDA torch wheel (~2.5 GB compressed), this cache
is correct and efficient (prevents re-download on rebuild), but when Docker Desktop
crashes or is reset, the BuildKit cache is dropped and the next build re-downloads
everything — consuming bandwidth and temporarily expanding the cache again before
old entries expire.

### Tertiary: WSL2 ext4 disk grows but does not shrink

WSL2 stores all Docker data in a virtual ext4 disk (`ext4.vhd`) on C:. When
`docker system prune` runs, it frees logical space inside the ext4 volume, but the
VHD file on the Windows filesystem stays at its maximum allocated size. A `diskpart
compact vdisk` or `Optimize-VHD` operation is required to reclaim C: space after prune.

### Contributing: Two full separate CPU images

`Dockerfile` (CPU ris-scheduler) and `Dockerfile.ris` (GPU ris-scheduler) share no
image layers because one has torch+CUDA and the other does not. Each rebuild is
independent. The CPU image is smaller (~1.5 GB) but still adds to total footprint.

---

## Current State (2026-05-04)

`docker system df` output:
```
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          0         0         0B        0B
Containers      0         0         0B        0B
Local Volumes   0         0         0B        0B
Build Cache     0         0         0B        0B
```

Docker is clean. C: has ~72 GB free. The Desktop crash during the previous session
effectively forced a reset. The WSL Docker data folder
(`C:\Users\patel\AppData\Local\Docker\wsl`) currently sits at ~1.54 GB (metadata only,
no image data).

The GPU image will need to be rebuilt from scratch before L1 validation can resume.
Expected rebuild time: 15–30 min on first run (CUDA wheel download + pip installs).
Expected peak C: usage during build: ~10–12 GB.

---

## Files Changed

### `.dockerignore` (minor tightening)

Added exclusions for directories and root-level files that were present on disk but
not in the build context rules:
- `.opencode/` (5.3 MB on disk) — AI tool data, not needed in build
- `.gemini/` (1.1 MB on disk) — AI tool data, not needed in build
- `.githooks/` — hooks, not needed in build
- `quarantine/` — quarantine staging dir
- `claude.md` — lowercase variant of CLAUDE.md (CLAUDE.md was already excluded; WSL2
  filesystems are case-sensitive)
- `AGENTS.md`, `requirements-rag.txt`, `pyrightconfig.json`, `wf_detail.json` — small
  root-level files not needed in image

Impact: build context was already tiny (~12 MB). These additions are cleanup rather
than size fixes; the Docker context is not the cause of bloat.

### `Dockerfile.ris` (storage budget comment)

Added a storage budget block at the top of the file documenting:
- Approximate size of each major layer
- Total expected runtime image size (~5–6 GB)
- BuildKit pip cache size (host-side, not in image)
- Model weights note
- Minimum free-space requirement before rebuild (15 GB)
- Reference to the new runbook

Also improved the CUDA torch comment to explain why the version mismatch causes
`torchvision::nms` operator failure (the historical root cause of the benchmark failure).

### `docs/runbooks/docker_storage.md` (new)

Comprehensive storage runbook covering:
1. Audit commands (`docker system df -v`, `docker builder du`, etc.)
2. Safe cleanup (image prune, builder prune with `--keep-storage 5GB`)
3. Unsafe cleanup requiring confirmation (volumes — NOT run)
4. WSL2 VHD compact steps (`diskpart compact vdisk` / `Optimize-VHD`)
5. Moving Docker Desktop data off C: to D: (one-time migration steps)
6. One-off GPU benchmark with `--no-deps` to avoid pulling ClickHouse for diagnostics
7. GPU build best practices (prune dangling images immediately after each build)
8. Pre-build checklist (verify ≥ 15 GB free, audit current Docker usage)
9. GPU validation resume steps (Steps 1–5, same as prior dev log)

---

## Cleanup Commands Recommended (not run — disk is already healthy)

Run these only if C: drops below 15 GB before the next GPU rebuild:

```powershell
# Safe: remove dangling images and stopped containers
docker image prune -f
docker container prune -f

# Safe: trim build cache, keep 5 GB of recent entries
docker builder prune --keep-storage 5GB --filter until=24h

# After prune, compact WSL VHD to reclaim C: space
wsl --shutdown
# Then run diskpart compact or Optimize-VHD on the ext4.vhd
```

Do NOT run `docker system prune --volumes` — this deletes ClickHouse, Grafana, and
n8n named volumes.

---

## Docker Build Context Exclusions Added

| Pattern | Reason | Size on disk |
|---|---|---|
| `.opencode/` | AI tool data | 5.3 MB |
| `.gemini/` | AI tool data | 1.1 MB |
| `.githooks/` | Git hooks | ~0 MB |
| `quarantine/` | Quarantine staging | ~0 MB |
| `claude.md` | Case-sensitive variant | ~0 MB |
| `AGENTS.md` | Root docs | ~0 MB |
| `requirements-rag.txt` | Root docs | ~0 MB |
| `pyrightconfig.json` | IDE config | ~0 MB |
| `wf_detail.json` | Workflow detail | ~0 MB |

Build context was already small (~12 MB). These additions are preventive hygiene
and will not materially change build performance.

---

## Remaining Manual Actions

1. **Before next GPU rebuild**: verify C: has ≥ 15 GB free.
   ```powershell
   (Get-PSDrive C).Free / 1GB
   ```

2. **Consider moving Docker to D:**. The project repo and artifacts already live on D:,
   but Docker Desktop WSL data is on C:. Moving it (see runbook Section 5) would
   permanently prevent disk exhaustion on C: regardless of image footprint.
   This is a one-time operator action, ~10–20 min, requires Docker Desktop restart.

3. **After GPU image is rebuilt**: run `docker image prune -f` immediately to remove
   any dangling images from the build.

4. **Compact WSL VHD** after each major prune. See runbook Section 4.

5. **Future optimization**: Add `--include-jobs academic_ingest` flag to the GPU
   scheduler (noted in 2026-05-03 Codex rereview as recommended follow-up). This
   would allow the GPU image to only load Marker-related deps and skip MCP, SimTrader,
   historical, and live extras — potentially reducing image size by ~300–500 MB.

---

## Whether L1 Marker Validation Can Resume

Yes, once the GPU image is rebuilt with the torch/torchvision fix already in place
(`torch==2.11.0+cu130` + `torchvision==0.26.0+cu130`), validation can proceed
immediately. The fix was committed in `3348aef` and confirmed correct by Codex rereview
(2026-05-03). No code changes are needed — only a `docker build` is blocked on disk space.

See `docs/runbooks/docker_storage.md` Section 9 for the exact validation commands.

---

## Codex Review

Tier: Skip (docs, .dockerignore, Dockerfile comment only — no production code changed).
Issues found: None.
Issues addressed: N/A.
