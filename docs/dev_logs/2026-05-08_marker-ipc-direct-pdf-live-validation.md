# Marker IPC Direct-PDF Live Validation — FAIL

Date: 2026-05-08
Type: live Docker/GPU warm-worker validation (one allowed attempt — consumed)
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Verdict: **FAIL — Paper 2 hit "daemonic processes are not allowed to have children"; only 1 of 3 required papers parsed**

---

## Summary

The one allowed live Docker warm-worker validation against the fresh direct-PDF
queue was run. Paper 1 (anchor) parsed successfully via Marker and IPC. Paper 2
failed immediately with `daemonic processes are not allowed to have children` on
both internal attempts. Paper 3 was never reached (queue exhausted max attempts
for paper 2 and stopped processing further items). Feature 3 gates are NOT met.
L1 Marker production rollout remains BLOCKED. No retry may occur in this prompt
scope.

---

## Step 1 — Baseline Checks

### git status

```
~ Modified: 14 files
  Dockerfile.ris
  packages/research/ingestion/fetchers.py
  packages/research/ingestion/marker_queue.py
  tests/test_ris_marker_queue.py
  tools/cli/research_marker_queue.py
  [+ obsidian/docs files]
? Untracked: 36+ dev log files
```

### C drive free space

- **Before run:** 40.49 GB free / 230.87 GB total
- **After run:** 40.49 GB free (no measurable change)
- Hard stop threshold: 1 GB — NOT triggered

### Docker containers before run

```
CONTAINER ID   IMAGE   COMMAND   CREATED   STATUS   PORTS   NAMES
(none running)
```

### Queue counts before run

```json
{"pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3}
```

All checks matched expected preflight state.

---

## Step 2 — Container Source-Code Verification

Two cheap container runs confirmed the bind mount serves current code:

**Full repo mount (`-v "${PWD}:/app" -w /app`) + enqueue --help:**
```
--pdf-url PDF_URL_OR_PATH
    Direct PDF URL or local file path. When set, warm-process skips the
    arXiv metadata API (no export.arxiv.org query) ...
```
→ `--pdf-url` present: current code is visible.

**Python path diagnostic:** The container's sys.path does not include `/app`
by default. Running `python -c "import packages"` showed that `packages` was
resolved from `/usr/local/lib/python3.11/site-packages/packages/__init__.py`
(the Docker image's stale installed version), NOT from `/app/packages/`. This
stale version has no `packages/research/ingestion/` subdirectory — it predates
the IPC/ingestion commit (`be8b4f2`).

**Fix applied (no code edit, no rebuild):** Added a second volume mount:
```
-v "${PWD}/packages/research:/usr/local/lib/python3.11/site-packages/packages/research"
```
This injects the current repo's `packages/research/` tree into site-packages,
overriding the stale build. Test confirmed:
```
IMPORT OK
fetch_pdf_direct: FOUND
```

---

## Step 3 — Live Validation Command

```powershell
docker --context default run --rm --gpus all `
  -v "D:\Coding Projects\Polymarket\PolyTool:/app" `
  -v "D:\Coding Projects\Polymarket\PolyTool/packages/research:/usr/local/lib/python3.11/site-packages/packages/research" `
  -v "C:\Users\patel\.cache\datalab:/home/polytool/.cache/datalab" `
  -w /app `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  warm-process --max-items 3 --json
```

**Run time:** 2026-05-08 10:53:02 – 10:54:58 (wall clock, ~1m56s total)
**Output log:** `artifacts/research/marker_ipc_validation/direct_pdf_live_20260508_105302.log`

---

## Step 4 — Full Output (captured)

```json
{
  "processed": [
    {
      "candidate_id": "arxiv:2604.24366",
      "source_url": "https://arxiv.org/abs/2604.24366",
      "arxiv_id": "2604.24366",
      "title": "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book",
      "body_source": "marker",
      "body_length": 56923,
      "parse_seconds": 51.62,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 112.27,
      "processed_at": "2026-05-08T14:54:56.254278+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:2109.07581",
      "source_url": "https://arxiv.org/abs/2109.07581",
      "arxiv_id": "2109.07581",
      "title": "The Impact of COVID-19 on Sports Betting Markets",
      "body_source": "marker_failed",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "daemonic processes are not allowed to have children",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 0.24,
      "processed_at": "2026-05-08T14:54:56.521825+00:00",
      "attempt": 1,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:2109.07581",
      "source_url": "https://arxiv.org/abs/2109.07581",
      "arxiv_id": "2109.07581",
      "title": "The Impact of COVID-19 on Sports Betting Markets",
      "body_source": "marker_failed",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "daemonic processes are not allowed to have children",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 0.15,
      "processed_at": "2026-05-08T14:54:56.696248+00:00",
      "attempt": 2,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    }
  ],
  "exit_code": 0,
  "ipc_warm_worker_used": true
}
```

Marker progress bars (from stderr — model warm successfully):
- `Recognizing Layout`: 15 pages, completed
- `Running OCR Error Detection`: 2 batches, completed
- `Recognizing Text`: 16 batches + additional passes, completed
- Model was warm for paper 1. Paper 2 failed before any Marker inference.

---

## Step 5 — Evidence Extraction

### Per-paper timing table

| Paper | candidate_id | parse_seconds | total_seconds | body_source | ipc_warm_worker_used | queue_status |
|-------|-------------|--------------|--------------|-------------|---------------------|--------------|
| 1 | arxiv:2604.24366 | **51.62s** | 112.27s | **marker** | **true** | **done** |
| 2 (attempt 1) | arxiv:2109.07581 | 0.0s | 0.24s | marker_failed | true | pending |
| 2 (attempt 2) | arxiv:2109.07581 | 0.0s | 0.15s | marker_failed | true | pending |
| 3 | arxiv:1910.08858 | — | — | never attempted | — | pending |

### Gate-by-gate evaluation

| Gate | Requirement | Result | PASS/FAIL |
|------|-------------|--------|-----------|
| 3 completed papers | 3 done in one warm session | 1 done (arxiv:2604.24366); 2 pending | **FAIL** |
| Papers 2+ parse_seconds ≤ 10s | Each warm paper ≤ 10s | Paper 2 failed at 0.0s parse (before any Marker call) | **FAIL** |
| `ipc_warm_worker_used=true` | All papers true | True for paper 1; true for paper 2 (reported even on failure) | Partial |
| `body_source=marker` | All completed papers | Paper 1: marker ✓; Paper 2: marker_failed ✗ | **FAIL** |
| No pdfplumber fallback | body_source ≠ pdfplumber for any paper | Not triggered (failure before parse, not fallback) | PASS |
| Clean shutdown, no orphan worker | Container exits cleanly | `docker ps` empty after run; exit_code=0 from CLI | **PASS** |

**Overall:** **FAIL** — three gates not met.

---

## Step 6 — Root Cause

**Failure:** `"daemonic processes are not allowed to have children"`

This is a Python `multiprocessing` constraint. Daemon processes (those started with
`daemon=True`) cannot spawn child processes. The error fires immediately on paper 2
before any Marker inference begins (`parse_seconds=0.0`, `total_seconds=0.24s`).

**Probable cause:** The IPC warm worker (`MarkerIPCWorker`) spawns a subprocess for
the Marker model server. After paper 1 completes, when attempting to serve paper 2,
the worker tries to spawn a new process (or restart the worker subprocess). If the
calling context is a daemonic process (e.g., the multiprocessing pool worker that runs
warm-process), Python raises this error.

In Docker, `warm-process` may run the processing loop inside a daemon thread or
daemon process. After paper 1 finishes and the worker state transitions, the IPC worker
attempt to spawn for paper 2 conflicts with the daemon constraint.

**Why paper 1 succeeded:** Paper 1 is processed before any daemon-child conflict can
arise — the initial spawn of the Marker model server subprocess occurs from a
non-daemonic context.

This is a code bug in `marker_ipc_worker.py` or `marker_queue.py`. Investigation and
a fix are required. Operator-authorized code edit + new validation run needed.

---

## Queue State After Run

```json
{"pending": 2, "processing": 0, "done": 1, "failed": 0, "total": 3}
```

```
candidate_id          status   attempts
arxiv:2604.24366      done     1
arxiv:2109.07581      pending  2
arxiv:1910.08858      pending  0
```

No `failed` status — paper 2 is still `pending` (exhausted max_items slot but
not marked failed). Paper 3 untouched.

---

## Orphan Process Check

```
docker --context default ps
(no containers running)
```

No orphan Docker container. No orphan Marker worker visible at the container
level (container was `--rm` and exited cleanly).

**Host-level check:** No persistent Python/Marker processes visible to the operator.
The container's internal process tree was destroyed on container exit. Clean.

---

## Disk Space

- Before: 40.49 GB free
- After: 40.49 GB free
- Delta: 0.00 GB (model weights were already cached; no new Docker layers pulled)

---

## Feature 3 Status

**Feature 3 is ACTIVE. L1 Marker production rollout remains BLOCKED.**

The live validation was the one allowed attempt. Acceptance gates were NOT met:
- Only 1 of 3 papers completed
- Papers 2–3 did not demonstrate warm IPC throughput

The root cause ("daemonic processes are not allowed to have children") is a new
blocker that was not present in the prior single-paper validation (where paper 1
completed successfully). It manifests when the warm worker attempts to serve
paper 2 onward.

---

## Hard Stop Confirmation

Hard stop condition triggered: **gate failure with one live validation attempt consumed.**

Per scope constraints:
- Do NOT retry the validation
- Do NOT rebuild/prune Docker
- Do NOT edit code in this prompt

---

## Exact Next Action

**Operator decision required.** Present this failure log to the operator with the
following decision packet:

1. Root cause: `daemonic processes are not allowed to have children` when IPC
   worker tries to serve paper 2+ in the same warm-process session.
2. Fix direction: investigate `marker_ipc_worker.py` — the worker process or its
   spawn mechanism must not run in a daemonic context when serving sequential
   papers. Likely fix: use `multiprocessing.Process(daemon=False)` for the
   model-server subprocess, or restructure to avoid daemon-child spawning.
3. After fix: rebuild Docker image (image is stale — baked packages don't include
   `packages/research/ingestion/`), re-prepare the direct-PDF queue, run one new
   validation.
4. Do not close Feature 3 or unblock L1 until the warm-worker session proves ≥3
   papers with papers 2+ at ≤10s parse_seconds.

**Codex investigation is the recommended next step** for root-cause diagnosis and
fix implementation in `marker_ipc_worker.py`.
