# Dev Log — Academic Pipeline Hosting Decision

**Date:** 2026-05-03
**Type:** Decision close-out / docs-only
**Track:** RIS — Academic Pipeline (L1 prerequisite)
**Codex review:** N/A — no code changed

---

## Summary

The [[Decision - Academic Pipeline Hosting]] blocking L1 Marker production rollout has been
answered and accepted. All five open questions are resolved. Docker GPU passthrough was
verified by running `nvidia-smi` inside a CUDA container with `--gpus all`. Hosting blocker
resolved. *(The "L1 is unblocked" claim below was correct at this decision point. It is now
stale — Docker IPC warm-worker live validation failed 2026-05-07; L1 remains blocked pending
>=3 warm papers at <=10s/paper (historical gate — **≤10s/paper rejected as unrealistic 2026-05-08; revised functional gate accepted — see Feature 3**). See `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md`.)*

---

## Commands run and outputs

### 1. Docker version check

```
$ docker --version
Docker version 29.0.1, build eedd969

$ docker compose version
Docker Compose version v2.40.3-desktop.1
```

### 2. Host GPU check

```
$ nvidia-smi
Sat May  2 21:23:41 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 595.97   Driver Version: 595.97   CUDA Version: 13.2                        |
| GPU 0: NVIDIA GeForce RTX 2070 Super  WDDM  |  0% Compute  | 8192 MiB total            |
+-----------------------------------------------------------------------------------------+
```

GPU: RTX 2070 Super, Driver 595.97, CUDA 13.2, 8192 MiB VRAM, 0% Compute utilization.

### 3. Docker GPU passthrough test

```
$ docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi

Sun May  3 01:23:54 2026
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 595.58.02   Driver Version: 595.97   CUDA Version: 13.2                     |
| GPU 0: NVIDIA GeForce RTX 2070 Super  Persistence-M On  | 8192 MiB total               |
+-----------------------------------------------------------------------------------------+
```

**PASS** — RTX 2070 Super is visible inside the container. CUDA 13.2 available. No
`nvidia-container-toolkit` installation was required; Docker Desktop 29.x on Windows
provides GPU passthrough via WSL2 automatically.

---

## Decision answers

| Question | Answer |
|---|---|
| Q1 — Production host | **B: dev machine, Docker with GPU passthrough** |
| Q2 — nvidia-container-toolkit installed? | **Confirmed working** — Docker Desktop WSL2 integration provides it |
| Q3 — Partner GPU? | **Moot** — Q1 = B |
| Q4 — Scheduler split | **Academic ingest → dev machine; reddit/blog/youtube/github → partner machine unaffected** |
| Q5 — Model weight handling | **C: volume-mount from host directory** (`~/.cache/datalab/` on the host, mounted into container) |

**Rollout strategy:** hard cutover for new ingests after L1 ships. Existing pdfplumber-parsed
papers remain in the knowledge store until a separate cleanup/re-ingest packet re-parses them
through Marker. L1 does not include that cleanup.

---

## Is L1 unblocked? *(stale — see note below)*

**YES — as of this decision (2026-05-02), the hosting gate was cleared.** The only hosting
gate was this decision. That gate is now cleared:

- GPU hardware confirmed ✓
- Docker GPU passthrough verified ✓
- Weight handling strategy chosen ✓
- Scheduler split documented ✓

[[Work-Packet - Marker Structural Parser Integration]] may proceed to implementation.

> **STALE (2026-05-07):** Docker IPC warm-worker live validation subsequently failed — 0 papers
> completed in any single run. L1 remains blocked until >=3 warm papers parse at <=10s/paper
> (historical gate — **≤10s/paper rejected as unrealistic 2026-05-08; revised functional gate accepted — see Feature 3**).
> The hosting decision itself remains valid and accepted. See
> `docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-live-validation.md`.

---

## Remaining setup tasks before L1 ships

The following are implementation-time prerequisites, not blockers on starting the packet:

1. **Volume mount in docker-compose.yml** — add `~/.cache/datalab:/root/.cache/datalab` (or
   WSL2 equivalent path) and `--gpus all` / `deploy.resources.reservations.devices` to the
   academic ingest service definition.
2. **pyproject.toml update** — move `marker-pdf`, `torch` from `[ris-marker]` extra into the
   `[ris]` base extra so the Docker image picks them up.
3. **Dockerfile update** — install `.[ris]` (which now includes Marker deps) in the image.
   Model weights are NOT baked in — they come via the volume mount.
4. **First-run weight download** — on first container start, Marker will download ~1–3 GB of
   model weights into the host-mounted cache path. This is a one-time operator setup step.
5. **GPU performance baseline** — run `polytool research-parser-benchmark` against a 10-paper
   corpus on the production host to confirm ≤10 s/paper (acceptance gate 2). *(Historical: ≤10s/paper gate rejected as unrealistic 2026-05-08; revised functional gate accepted — see Feature 3.)*

---

## Files changed

| File | Change |
|---|---|
| `docs/obsidian-vault/Claude Desktop/09-Decisions/Decision - Academic Pipeline Hosting.md` | Status `pending-operator-input` → `accepted`; added Decision Record section with answers, verified environment, L1 assumptions, blocked-if-GPU-fails section, prerequisite checklist |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L1 gate cleared; Open Decisions resolved; Blockers table updated; RIS status table L1 row updated; Recent Session Context entry added |
| `docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md` | This file |
