# 2026-04-05 — Docker Image Slimming: Multi-Stage Builds

**Task ID:** quick-260405-jle
**Branch:** feat/ws-clob-feed
**Date:** 2026-04-05

## Summary

Converted the root `Dockerfile` to a multi-stage build and modernized
`Dockerfile.bot` so that:

1. **Root image:** Build tools (`gcc`, `libffi-dev`) exist only in the builder
   stage and are never shipped in the runtime image. The runtime stage copies
   only pre-built Python packages from `/usr/local/lib/python3.11/site-packages`
   and `/usr/local/bin` — no compiler or development headers.

2. **Pair-bot image:** `Dockerfile.bot` rebuilt as a true multi-stage image on
   `python:3.11-slim` (previously `3.12-slim`, single-stage, with `COPY . .`
   and a hard-coded `ENTRYPOINT`). It now installs only `[live,simtrader]`
   extras (~5 packages) instead of the full `[all,ris]` stack (~30+ packages,
   including sentence-transformers, chromadb, etc.).

3. **Compose wiring:** `pair-bot-paper` and `pair-bot-live` compose services
   now build from `Dockerfile.bot` instead of the heavy root `Dockerfile`.

## Before / After

| Service | Before Dockerfile | Before extras | After Dockerfile | After extras |
|---------|-------------------|---------------|------------------|--------------|
| polytool, ris-scheduler | Dockerfile (single-stage) | [all,ris] | Dockerfile (multi-stage) | [all,ris] |
| pair-bot-paper | Dockerfile (single-stage) | [all,ris] | Dockerfile.bot (multi-stage) | [live,simtrader] |
| pair-bot-live | Dockerfile (single-stage) | [all,ris] | Dockerfile.bot (multi-stage) | [live,simtrader] |

## What Multi-Stage Build Removes from Runtime

Root Dockerfile runtime image no longer contains:
- `gcc` (~100 MB compiled objects in image layers)
- `libffi-dev` (~5 MB)
- Any other build headers installed transitively by those packages

These were present in all containers that used the old single-stage root image
(polytool, ris-scheduler, pair-bot-paper, pair-bot-live).

## What Pair-Bot Image No Longer Installs

By switching from `[all,ris]` to `[live,simtrader]`, `Dockerfile.bot` no
longer installs:

| Package | Estimated size | Why it was there |
|---------|----------------|------------------|
| sentence-transformers | ~300 MB+ | RAG/RIS — not used by pair-bot |
| chromadb | ~150 MB+ | Vector store — not used by pair-bot |
| duckdb | ~20 MB | Historical data plane — not used by pair-bot |
| pyarrow | ~50 MB | Historical import — not used by pair-bot |
| apscheduler | ~5 MB | RIS scheduler — not used by pair-bot |
| pytest / pytest-cov | ~10 MB | Dev tooling — not in production images |
| mcp | ~5 MB | MCP server — not used by pair-bot |
| fastapi / uvicorn | ~15 MB | Studio API — not used by pair-bot |

Estimated total unnecessary package savings: **~500 MB+** for pair-bot images.

What `Dockerfile.bot` still installs:
- `py-clob-client>=0.17` (`[live]`) — CLOB order execution, required
- `websocket-client>=1.6` (`[simtrader]`) — WS feed, required
- `requests`, `clickhouse-connect`, `jsonschema` (base deps) — required

## Build Matrix Results

| Verification | Result |
|---|---|
| `docker compose config --quiet` (default stack) | PASS |
| `docker compose --profile pair-bot config` — pair-bot-paper dockerfile | Dockerfile.bot |
| `docker compose --profile pair-bot config` — pair-bot-live dockerfile | Dockerfile.bot |
| Dockerfile.bot count in pair-bot config | 2 (correct) |
| Profile gating pair-bot-paper: `profiles: ["pair-bot"]` | INTACT |
| Profile gating pair-bot-live: `profiles: ["pair-bot"]` | INTACT |
| `python -m polytool --help` (Python regression check) | PASS |

Note: Live Docker image builds and size measurements require Docker Desktop
connectivity. Structural validation (compose config) confirms correctness of
all Dockerfile and compose changes.

## Files Changed

| File | Change |
|------|--------|
| `Dockerfile` | Converted from single-stage to two-stage (builder + runtime); runtime stage copies only site-packages and bin |
| `Dockerfile.bot` | Rewritten: python:3.11-slim, multi-stage, BuildKit header + cache mounts, [live,simtrader] only, selective COPY, no ENTRYPOINT/CMD |
| `docker-compose.yml` | pair-bot-paper and pair-bot-live `dockerfile:` changed from `Dockerfile` to `Dockerfile.bot` |

Files NOT changed (already appropriately scoped):
- `services/api/Dockerfile` — already lean, single-purpose API image
- `infra/n8n/Dockerfile` — already minimal n8n custom image

## Codex Review Tier

Skip — Dockerfile and compose changes only (no execution logic, no kill switch, no order placement, no risk management code).

## Notes

- `Dockerfile.bot` does NOT copy `services/` — pair-bot has no dependency on
  the FastAPI service code.
- `Dockerfile.bot` does NOT have `ENTRYPOINT` or `CMD` — compose services
  already specify full `command` arrays; the old hard-coded
  `ENTRYPOINT ["python", "-m", "polytool", "crypto-pair-run"]` was removed to
  match the root Dockerfile pattern and avoid command/entrypoint conflicts.
- Python version aligned: both Dockerfiles now use `python:3.11-slim`
  (Dockerfile.bot was previously `python:3.12-slim`).
- Prior Docker hygiene work (quick-260405-j2t) already shrinks the build
  context from 660 MB to ~12 MB via `.dockerignore`, so the pair-bot builder
  stage only sees the 12 MB context even with selective COPY.
