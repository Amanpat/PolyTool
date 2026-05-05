---
tags: [decision, hosting, ris, infrastructure]
date: 2026-04-29
decided: 2026-05-02
status: accepted
topics: [academic-pipeline, marker, gpu, hosting]
related-work-packets:
  - "[[Work-Packet - Marker Structural Parser Integration]]"
---

# Decision — Academic Pipeline Hosting

## Status

**ACCEPTED — 2026-05-02. All open questions answered. Docker GPU passthrough verified. L1 Marker production rollout is unblocked.**

## Context

The Marker production rollout (Layer 1 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]]) requires GPU hardware. Marker on CPU times out at 300 seconds per paper; on a modest GPU (NVIDIA 2070 Super or better) it runs in 5-10 seconds. Production cannot run on CPU.

This is a hosting question that the prior architecture deferred. With L1 production rollout activated, it must be answered.

## Operator-confirmed facts

- Operator's dev machine has an NVIDIA 2070 Super GPU.
- Operator confirmed (2026-04-29 chat session): "we are good with gpu requirement."
- Operator's dev machine specs (per memory): i7-8700K, 6-core, 32GB RAM, 2070 Super.

## Open questions for operator

The following must be answered before the Marker packet ships:

1. **Where does the academic pipeline run in production?** Options:
   - **A)** Operator's dev machine, bare metal (Python venv, no Docker for academic ingest)
   - **B)** Operator's dev machine, Docker with GPU passthrough (`nvidia-container-toolkit` configured)
   - **C)** Partner's machine — assumes partner machine has a GPU. Operator must confirm with partner.
   - **D)** A new dedicated host (e.g., a small GPU VPS) — adds infrastructure cost
2. **If option B (Docker on dev machine), is `nvidia-container-toolkit` installed?** If no, this is a prerequisite setup task.
3. **If option C (partner machine), does it have a GPU?** If no, option C is invalid; reconsider A, B, or D.
4. **Does the academic pipeline still run on `ris-scheduler` (the current Docker service), or does it move?** The scheduler currently runs on the partner's machine per the existing decision doc on n8n pilot scope. If the academic pipeline moves to dev machine, the scheduler split-brain question arises: does academic schedule on dev, while reddit/blog/youtube/github stay on partner? This is solvable but is an explicit choice.
5. **What is the model-weight handling strategy?** Marker's model weights are several GB. Options:
   - **a)** Download at first run, cache on host (slow first run, fast subsequent runs)
   - **b)** Bake into Docker image (fast first run, large image)
   - **c)** Volume-mount from a host directory (medium image, manual setup)

## Decision Record (2026-05-02)

### Selected answers

| Question | Answer | Evidence |
|---|---|---|
| Q1 — Where does academic pipeline run? | **B — dev machine, Docker with GPU passthrough** | Docker GPU passthrough verified (see commands below) |
| Q2 — Is nvidia-container-toolkit functional? | **YES — confirmed working** | `docker run --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi` executed successfully inside container |
| Q3 — Partner GPU? | **Moot** — Q1 = B | N/A |
| Q4 — Scheduler split? | **Academic ingest moves to dev machine; all other pipelines (reddit/blog/youtube/github) remain on partner machine unaffected** | Clean GPU-required / CPU-fine split |
| Q5 — Model weight handling? | **C — volume-mount from host directory** | Dev machine Docker Desktop + WSL2; host cache at `~/.cache/datalab/`; image stays lean; operator mounts the cache dir at first run |

### Rollout strategy

- **New ingests**: hard cutover — next ingest run uses Marker for every PDF download.
- **Existing pdfplumber papers**: remain as-is until a separate cleanup/re-ingest packet walks the cache and re-parses through Marker. L1 does not include that cleanup task.

### Verified environment (2026-05-02)

```
Host OS: Windows 11 Pro 10.0.26200
GPU: NVIDIA GeForce RTX 2070 Super — Driver 595.97, CUDA 13.2, 8192 MiB VRAM
Docker: 29.0.1 (build eedd969)
Docker Compose: v2.40.3-desktop.1

GPU passthrough test:
  docker run --rm --gpus all nvidia/cuda:12.4.1-base-ubuntu22.04 nvidia-smi
  → NVIDIA-SMI 595.58.02 (WSL2 driver), RTX 2070 Super visible inside container ✓
  → CUDA Version: 13.2 ✓
```

### What L1 implementation may assume

1. Docker with `--gpus all` is available and functional on the dev machine.
2. `nvidia-container-toolkit` does not need a separate installation — Docker Desktop 29.x on Windows provides GPU passthrough via WSL2 automatically.
3. Model weights are volume-mounted from `~/.cache/datalab/` on the host. The production `docker-compose.yml` must add a volume mount for this path. First run downloads weights (~1–3 GB) into the host cache; subsequent runs hit the cache.
4. Marker dependencies (`marker-pdf`, `torch`) move from `[ris-marker]` optional extra into `[ris]` base extra and are baked into the Docker image (without the model weights themselves).
5. The academic ingest scheduler runs as a separate Docker Compose stack on the dev machine. Partner machine scheduler is unaffected.

### What remains blocked if GPU passthrough fails in production

If `docker run --gpus all` stops working on the dev machine (driver update, Docker Desktop regression, etc.):

- L1 Marker production rollout is blocked — 300 s CPU timeout makes production ingest infeasible.
- Fallback path: bare-metal Python venv on dev machine with `RIS_PDF_PARSER=marker` (Option A from Q1), bypassing Docker GPU passthrough entirely.
- Fallback is opt-in by operator; it is not implemented in L1.

### Prerequisite checklist for L1 implementation

- [x] GPU hardware confirmed: RTX 2070 Super on dev machine
- [x] Docker GPU passthrough verified: `docker run --gpus all` succeeds, `nvidia-smi` visible in container
- [ ] Host cache directory exists: `~/.cache/datalab/` (or WSL2 equivalent) — created automatically on first Marker run
- [ ] Docker Compose production file updated with `--gpus all` and `~/.cache/datalab` volume mount
- [ ] `pyproject.toml` updated: Marker deps moved from `[ris-marker]` into `[ris]` extra
- [ ] `Dockerfile` updated to install `[ris]` extra (picks up Marker deps)
- [ ] `tests/test_ris_marker_extractor.py` written (≥4 tests per acceptance gate 8)
- [ ] GPU performance baseline run: ≤10 s/paper on the production host

---

## Recommended answer (operator confirms or adjusts)

Based on the operator's confirmation and the operational context:

- **Question 1 → B (Docker with GPU passthrough on dev machine)**. Reason: matches existing Docker-based deployment pattern; scheduler stays unified; only requires one-time `nvidia-container-toolkit` setup.
- **Question 2 → architect verifies or installs `nvidia-container-toolkit`** as part of the Marker packet's Docker prep. Standard procedure on Ubuntu/WSL2 hosts.
- **Question 3 → moot if Q1 answer is B**. If Q1 answer becomes C, partner GPU status must be confirmed.
- **Question 4 → academic ingest moves to dev machine; reddit/blog/youtube/github schedules are unaffected**. This is a clean split: academic = GPU-required = dev machine; everything else = CPU-fine = partner machine. Two separate scheduler instances, each with their own pipelines.
- **Question 5 → b (bake into Docker image)** for v1, with the option to revisit if image size becomes painful. Bake is simpler than volume mounts; first-run download is unpredictable in production.

These recommendations are **suggestions for the operator to confirm or override**. The decision is not final until the operator signs off.

## Consequences of this decision

- **Scheduler split.** Two scheduler instances: one on dev machine (academic), one on partner machine (other pipelines). Each has its own Docker compose, its own logs, its own kill switch. This is an operational complication. Mitigation: clear documentation in operator runbook.
- **Dev machine as production.** The dev machine is now part of the production pipeline. If it goes down, academic ingest stops. Risk: tolerable for current scale; revisit at Stage 1 capital deployment.
- **Marker dependencies in `[ris]` extras.** PyTorch and Marker model weights become required for any RIS install, not optional. Operators without GPU cannot run the academic pipeline. This is acceptable given the architectural decision but worth documenting in the operator setup guide.
- **GPU-required tag in operator setup guide.** The setup guide must clearly flag academic ingest as GPU-required. Operators with CPU-only machines should run only non-academic pipelines.

## Alternatives considered

- **Stay with pdfplumber as primary parser.** Rejected — operator confirmed quality matters, two-parser inconsistency is bad for embeddings. The architectural decision in [[Decision - Scientific RAG Architecture Adoption]] is final on this.
- **CPU-only Marker with longer timeouts.** Rejected — 300s per paper means a 100-paper backfill takes 8+ hours, blocking ingestion of subsequent papers. Throughput too low for production.
- **Cloud GPU (Modal, Replicate, RunPod).** Rejected for v1 — adds external API cost, latency, and vendor dependency. Reconsider only if dev-machine hosting becomes operationally painful.

## Cross-references

- [[Decision - Scientific RAG Architecture Adoption]] — establishes Marker as primary parser
- [[Work-Packet - Marker Structural Parser Integration]] — the packet this decision unblocks
- [[11-Scientific-RAG-Target-Architecture]] — broader design context
- [[Decision - RIS n8n Pilot Scope]] — current scheduler/n8n setup; this decision creates a split
