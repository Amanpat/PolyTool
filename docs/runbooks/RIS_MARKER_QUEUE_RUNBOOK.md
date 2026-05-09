# RIS Marker Parse Queue — L1 Operator Runbook

**Status:** Production-ready as of 2026-05-09 (L1 Marker Production Readiness Rollout complete)
**Track:** Research Intelligence System — Layer 1
**Feature doc:** `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
**IPC warm-worker doc:** `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`

---

## Overview

The Marker parse queue is the canonical production path for ingesting academic PDFs into
the RIS knowledge store. Papers enqueued here are parsed by Marker (GPU-accelerated,
structure-preserving), and only `body_source=marker` papers are eligible for ChromaDB
indexing.

**pdfplumber is legacy/debug only.** `RIS_PDF_PARSER=pdfplumber` is a debug override, not a
production path.

---

## Prerequisites

- Docker Desktop with GPU passthrough enabled on the dev machine
- RTX 2070 Super, CUDA 13.2 (validated 2026-05-08)
- `docker compose --profile ris-gpu up -d` running (or use `run --rm`)
- Marker model weights volume-mounted from `~/.cache/datalab/` on the host

Verify GPU passthrough before first use:
```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu nvidia-smi
```

---

## Operator Path (end-to-end)

### Step 1 — Enqueue one or more arXiv papers

```bash
# By arXiv ID
python -m polytool research-marker-queue enqueue --url 2604.24366

# By full URL
python -m polytool research-marker-queue enqueue \
  --url https://arxiv.org/abs/2604.24366

# With optional title hint (skips arXiv API resolution)
python -m polytool research-marker-queue enqueue \
  --url 2604.24366 --title "Polymarket microstructure"

# Enqueue multiple papers
python -m polytool research-marker-queue enqueue --url 2604.24366
python -m polytool research-marker-queue enqueue --url 2109.07581
python -m polytool research-marker-queue enqueue --url 1910.08858

# Force re-enqueue (resets existing entry to pending)
python -m polytool research-marker-queue enqueue --url 2604.24366 --force
```

Output: `Enqueued: arxiv:2604.24366  (status=pending)`

### Step 2 — Check the queue

```bash
# Item counts by status
python -m polytool research-marker-queue counts

# List all items
python -m polytool research-marker-queue list

# Filter by status
python -m polytool research-marker-queue list --status pending
python -m polytool research-marker-queue list --status done
python -m polytool research-marker-queue list --status failed
```

### Step 3 — Process with IPC warm-worker (Linux/Docker — production path)

Run the warm-process command inside the GPU Docker container:

```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue warm-process \
  --max-items 5 \
  --marker-timeout 900
```

- `--max-items N` — process up to N pending items in one session (default: 1)
- `--marker-timeout SECONDS` — per-paper Marker extraction timeout (default: 900s)
- Models load once at session start (paper 1 ~72s total); papers 2+ pay only inference (~45-70s)

**Expected output (per paper):**
```
[PASS] arxiv:2604.24366
       body_source:          marker
       body_length:          56,923 chars
       parse_seconds:        45.6s
       queue_status:         done  marker_ready=True
       ipc_warm_worker_used: True
```

### Step 4 — Inspect results

```bash
# Count by status
python -m polytool research-marker-queue counts

# View completed papers
python -m polytool research-marker-queue list --status done

# View failed papers (inspect failure_reason)
python -m polytool research-marker-queue list --status failed

# Raw results log (gitignored)
# Each line is a JSON result record with body_source, body_length, parse_seconds, etc.
type artifacts\research\marker_parse_queue\results.jsonl
```

Key fields in results.jsonl:
- `body_source`: `"marker"` (success) or `"marker_failed"` / `"error"` (failure)
- `body_length`: character count of extracted body
- `parse_seconds`: Marker extraction time
- `ipc_warm_worker_used`: true when IPC warm-worker was active
- `marker_ready`: canonical RAG-readiness flag (`body_source=marker` AND `body_length >= 5000`)
- `failure_reason`: why the paper was rejected (null on success)
- `queue_status`: final queue state after processing (`done` | `pending` | `failed`)

---

## Queue States

| State | Meaning | Operator action |
|-------|---------|-----------------|
| `pending` | Enqueued; not yet picked up by worker | None — worker will process on next run |
| `processing` | Worker actively parsing this paper | Wait. If stuck (worker crashed mid-paper), re-enqueue with `--force` |
| `done` | Parse complete; result written to results.jsonl | Check `marker_ready` in results.jsonl |
| `failed` | Max retries (3) exceeded; terminal failure | Inspect `failure_reason` in results.jsonl; paper is not RAG-eligible |

**Note on retries:** A paper returns to `pending` on transient failure (timeout, container
restart) until `attempts >= MAX_ATTEMPTS=3`, then becomes `failed`. Use `--force` on
`enqueue` to reset attempts to 0 and return to `pending`.

---

## RAG-Readiness Rule

```
marker_ready = body_source == "marker" AND body_length >= 5000 chars
```

Only `marker_ready=True` papers are eligible for ChromaDB embedding and indexing.
Papers with `body_source=marker_failed`, `pdfplumber`, `abstract_fallback`, or
`error` are **not** RAG-eligible regardless of body length.

This rule is enforced by `is_marker_ready()` in `packages/research/ingestion/marker_queue.py`
and the `IngestPipeline.ingest_external()` academic gate in `packages/research/ingestion/pipeline.py`.

---

## Output Locations

All artifacts are gitignored.

| Artifact | Path |
|----------|------|
| Queue state | `artifacts/research/marker_parse_queue/queue.jsonl` |
| Results log (append-only) | `artifacts/research/marker_parse_queue/results.jsonl` |
| Custom queue dir | `--queue-dir PATH` flag on all subcommands |

---

## Recovery Procedures

### Paper stuck in `processing` (worker crashed)
```bash
python -m polytool research-marker-queue enqueue --url ARXIV_ID --force
```
Resets attempts to 0 and returns the paper to `pending`.

### Paper in `failed` (max retries exceeded)
1. Inspect failure reason:
   ```bash
   type artifacts\research\marker_parse_queue\results.jsonl
   # Find the candidate_id and read failure_reason
   ```
2. If the failure was transient (timeout, container restart): re-enqueue with `--force`
3. If the failure is permanent (image-only PDF, corrupted file, missing text): the paper
   is not suitable for Marker. Leave as `failed`.

### No GPU available
- The warm IPC worker requires a CUDA-capable GPU inside the container.
- Without GPU, Marker falls back to CPU (very slow: 300+ s/page on complex papers).
- Check GPU passthrough with `nvidia-smi` before starting a batch.

---

## Platform Behavior

| Platform | Worker mode | Production? |
|----------|-------------|-------------|
| Windows local dev | Thread warm worker — pre-loads model dict once | Dev/debug only |
| Linux/Docker | **IPC warm-worker** — models in GPU VRAM across all papers | **Production target** |

On Windows, `warm-process` falls back to the thread warm worker automatically.
The IPC warm-worker (Linux/Docker) is the production path validated on 2026-05-08.

---

## Performance Expectations

| Scenario | Expected time |
|----------|--------------|
| Paper 1 (cold model load) | ~45-70s inference + ~27s cold-load overhead ≈ 72-97s total |
| Papers 2+ (warm) | ~45-70s inference, ≤1s overhead (models stay in GPU VRAM) |
| Short prose paper (15 pages) | ~45-55s warm |
| Dense math/ML paper (25-46 pages) | ~60-70s warm |

These times are hardware constants for the RTX 2070 Super with Marker's five-model
pipeline. They cannot be reduced by queue design. The IPC warm-worker eliminates only
the cold-load overhead (27s) for papers 2+.

Validated timings from 2026-05-08 live session:
- arxiv:2604.24366 (15p) — 45.55s parse, 72.31s total (cold)
- arxiv:2109.07581 (COVID-19 sports betting) — 69.73s parse, 69.86s total (warm, delta=0.13s)
- arxiv:1910.08858 (Sports betting inefficiencies) — 48.31s parse, 48.53s total (warm, delta=0.22s)

---

## Scope Notes

- **L2 PaperQA2** remains a stub. Gated on L1 production rollout closeout.
- **L4 Multi-source harvesters** remain stubs. Gated on L1 + L3.
- **SVM enforce** remains hard-blocked at rc=1. Default lexical filter is active.
- **pdfplumber** is legacy/debug only. Never used in the production canonical path.
- **Bulk re-ingest** of existing pdfplumber-parsed ChromaDB entries is a separate cleanup
  task — not part of this runbook.
