---
phase: quick-260405-jyv
plan: "01"
subsystem: docker
tags: [docker, image-slimming, root-image, extras, deps]
dependency_graph:
  requires: [quick-260405-jle]
  provides: [narrowed-root-image-extras]
  affects: [Dockerfile, docs/CURRENT_STATE.md]
tech_stack:
  added: []
  patterns: [multi-stage-docker, selective-extras]
key_files:
  created:
    - docs/dev_logs/2026-04-05_root_image_final_slimming.md
  modified:
    - Dockerfile
    - docs/CURRENT_STATE.md
decisions:
  - "Drop [rag] from root image: all sentence-transformers/chromadb imports are lazy; no top-level import in polytool/ or tools/; ~450MB savings"
  - "Drop [studio] from root image: API service has its own Dockerfile; no root image consumer needs fastapi/uvicorn"
  - "Drop [dev] from root image: pytest/pytest-cov are test tooling only; not for production runtime images"
  - "Keep [ris,mcp,simtrader,historical,historical-import,live]: all used by polytool CLI or ris-scheduler at runtime"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-05"
  tasks_completed: 2
  files_changed: 3
---

# Phase quick-260405-jyv Plan 01: Root Image Final Slimming Summary

**One-liner:** Narrowed root Dockerfile from `.[all,ris]` to `.[ris,mcp,simtrader,historical,historical-import,live]`, dropping sentence-transformers/chromadb/fastapi/uvicorn/pytest (~475MB) from the polytool and ris-scheduler images.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Narrow root Dockerfile extras and fix stale CURRENT_STATE docs | 8333988 | Dockerfile, docs/CURRENT_STATE.md |
| 2 | Write dev log | 8333988 | docs/dev_logs/2026-04-05_root_image_final_slimming.md |

## What Changed

### Dockerfile

Both pip install lines changed from:
```
pip install ".[all,ris]"
```
to:
```
pip install ".[ris,mcp,simtrader,historical,historical-import,live]"
```

Comment block added above the first pip install explaining what each kept extra provides and why rag/studio/dev are excluded.

### docs/CURRENT_STATE.md

Stale bullet about "Dockerfile.bot identified as orphaned" replaced with accurate description of current state: `Dockerfile.bot` is adopted for pair-bot services, and the root image has been narrowed to remove heavy extras.

## Extras Removed (~475MB savings)

| Extra | Key packages | Size estimate | Reason removed |
|-------|-------------|---------------|----------------|
| `rag` | sentence-transformers, chromadb | ~450MB | All imports lazy/guarded; zero top-level imports in polytool/ or tools/ |
| `studio` | fastapi, uvicorn | ~15MB | API service has own Dockerfile; no root image consumer needs a web server |
| `dev` | pytest, pytest-cov | ~10MB | Test tooling has no place in production runtime images |

## Verification

| Check | Result |
|-------|--------|
| `python -m polytool --help` | PASS — CLI loads, no import errors |
| `docker compose config --quiet` | PASS — exit 0, topology unchanged |
| Dockerfile pip lines grep | PASS — no `all`/`rag`/`studio`/`dev` in pip install lines |
| CURRENT_STATE.md audit | PASS — "orphaned" claim removed |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — dependency narrowing only, no new network exposure, no new code paths.

## Self-Check: PASSED

- [x] `Dockerfile` modified — pip install lines use narrowed extras
- [x] `docs/CURRENT_STATE.md` modified — stale orphan bullet replaced
- [x] `docs/dev_logs/2026-04-05_root_image_final_slimming.md` created
- [x] Commit `8333988` exists: `feat(quick-260405-jyv): narrow root image extras — drop rag/studio/dev (~475MB)`
