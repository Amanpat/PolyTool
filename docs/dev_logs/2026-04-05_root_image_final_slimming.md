# 2026-04-05 — Root Image Final Slimming: Narrow Extras

**Task ID:** quick-260405-jyv
**Branch:** feat/ws-clob-feed
**Date:** 2026-04-05

## Summary

Narrowed root `Dockerfile` extras from `.[all,ris]` to
`.[ris,mcp,simtrader,historical,historical-import,live]`, dropping ~475MB of
packages that no root-image consumer uses. Fixed stale `CURRENT_STATE.md`
documentation that incorrectly described `Dockerfile.bot` as orphaned.

## Context

Prior work `quick-260405-jle` already converted the root image to a multi-stage
build and migrated pair-bot services to `Dockerfile.bot`. The root image was
left on `.[all,ris]` — the full extras stack including sentence-transformers,
chromadb, fastapi, uvicorn, and pytest. This pass completes the slimming by
dropping those unused extras from the root image.

Root image consumers (from `docker-compose.yml`):
1. `polytool` service (profile: cli) — general-purpose CLI container
2. `ris-scheduler` service — runs `research-scheduler start`

Neither consumer needs RAG, Studio UI, or dev tooling.

## Before / After

| Attribute | Before | After |
|-----------|--------|-------|
| Extras | `.[all,ris]` | `.[ris,mcp,simtrader,historical,historical-import,live]` |
| Dropped | — | `[rag]` (~450MB), `[studio]` (~15MB), `[dev]` (~10MB) |
| Estimated savings | — | ~475MB+ |

### What `[all]` Expanded To (Before)

`[all]` = rag + mcp + simtrader + studio + dev + historical + historical-import + live

Specifically:

| Extra | Key packages | Why removed |
|-------|-------------|-------------|
| `rag` | sentence-transformers (~300MB+), chromadb (~150MB+) | All imports lazy/guarded inside function bodies; no top-level import in polytool/ or tools/; scheduler jobs use --no-eval |
| `studio` | fastapi, uvicorn (~15MB) | API service has its own `services/api/Dockerfile`; no root image consumer needs a web server |
| `dev` | pytest, pytest-cov (~10MB) | Test tooling has no place in production runtime images |

### What Stays in Root Image (After)

| Extra | Key packages | Why kept |
|-------|-------------|---------|
| `ris` | apscheduler | ris-scheduler service requires it |
| `mcp` | mcp SDK | Lightweight; available for ad-hoc CLI use |
| `simtrader` | websocket-client | CLI replay/shadow commands |
| `historical` | duckdb | CLI historical queries |
| `historical-import` | pyarrow | CLI historical import |
| `live` | py-clob-client | CLI live execution commands |

## Audit Methodology

Before removing `[rag]`, verified all RAG imports are lazy:

- Grep for top-level `import chromadb` and `from chromadb` in `polytool/` and `tools/`: **zero results**
- Grep for top-level `import sentence_transformers` and `from sentence_transformers` in `polytool/` and `tools/`: **zero results**
- RAG imports exist only inside function bodies and are guarded by try/except or conditional checks
- RIS scheduler jobs all run with `--no-eval` flag, which bypasses LLM/embedding calls entirely

Before removing `[studio]`:

- `services/api/Dockerfile` is a separate, purpose-built image for the FastAPI service
- The `polytool` CLI container and `ris-scheduler` container have no need for uvicorn or fastapi at runtime
- The `services/api/` compose service already builds from its own Dockerfile

Before removing `[dev]`:

- pytest and pytest-cov are test tooling; they should never appear in production images
- No compose service runs tests as part of its startup command

## CURRENT_STATE.md Fix

The `quick-260405-j2t` pass left a bullet in `CURRENT_STATE.md` describing
`Dockerfile.bot` as orphaned. This was accurate at that moment, but
`quick-260405-jle` then adopted `Dockerfile.bot` for pair-bot services and the
bullet was never updated.

The stale bullet claimed:
> "No compose service references Dockerfile.bot. It uses Python 3.12
>  (inconsistent with 3.11 elsewhere) and installs [live,simtrader] extras
>  (pair-bot services use root Dockerfile with [all,ris])."

All three claims were outdated:
- `pair-bot-paper` and `pair-bot-live` now reference `Dockerfile.bot`
- `Dockerfile.bot` was updated to `python:3.11-slim` by `quick-260405-jle`
- Root Dockerfile no longer uses `[all,ris]` after this pass

Replaced with accurate description of current state.

## Files Changed

| File | Change |
|------|--------|
| `Dockerfile` | Both pip install lines changed from `.[all,ris]` to `.[ris,mcp,simtrader,historical,historical-import,live]`; comment block added explaining each extra and why rag/studio/dev are excluded |
| `docs/CURRENT_STATE.md` | Stale "Dockerfile.bot orphaned" bullet replaced with accurate description of adopted state and root image narrowing |
| `docs/dev_logs/2026-04-05_root_image_final_slimming.md` | This file |

Files NOT changed:
- `pyproject.toml` — extras definitions unchanged
- `Dockerfile.bot` — pair-bot image already correct from `quick-260405-jle`
- `docker-compose.yml` — compose topology unchanged

## Verification Results

| Check | Command | Result |
|-------|---------|--------|
| Python CLI regression | `python -m polytool --help` | PASS — CLI loads, no import errors |
| Compose validation | `docker compose config --quiet` | PASS (exit 0) — compose topology unchanged |
| Dockerfile pip lines audit | `grep "pip install" Dockerfile` | PASS — both lines use `.[ris,mcp,simtrader,historical,historical-import,live]`, no `all`/`rag`/`studio`/`dev` |
| CURRENT_STATE.md audit | Read lines 60-68 | PASS — "orphaned" claim removed, accurate bullet present |

## Codex Review Tier

Skip — Dockerfile and documentation changes only (no execution logic, no kill switch, no order placement, no risk management code).
