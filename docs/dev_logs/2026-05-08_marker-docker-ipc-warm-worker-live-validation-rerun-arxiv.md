# Marker Docker IPC Warm-Worker v1 — Live Validation FAIL (arXiv Rate Limit on Paper 2)

Date: 2026-05-08
Type: live-validation failure report
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Verdict: **PARTIAL PASS / HARD STOP — Paper 1 IPC validated; papers 2-3 blocked by arXiv 429**

---

## Summary

The live Docker warm-worker validation ran successfully for paper 1 and proved the IPC
warm worker works end-to-end (`body_source=marker`, `ipc_warm_worker_used=true`,
`parse_seconds=39.19s`). Paper 2 (arxiv:1910.08858) hit an arXiv metadata API timeout
on attempt 1 and HTTP 429 on attempt 2. The warm-process exhausted its max-items=3
budget on paper 2's two retry attempts; paper 3 was never reached. Hard stop triggered:
**"arXiv API returns 429 or repeated timeout before parsing."**

Feature 3 remains ACTIVE. L1 Marker production rollout remains BLOCKED.
Closeout protocol was NOT executed.

**Key positive finding:** The IPC warm worker itself is validated as working. The failure
root cause is arXiv API rate limiting during metadata fetch inside the container — not
an IPC, Marker parse, or GPU failure.

---

## Session Sequence

### Step 1 — Baseline checks

**C drive free:** 65.22 GB (after operator freed space)

**Docker images (default context):**
```
REPOSITORY                   TAG       IMAGE ID       CREATED AT
polytool-ris-scheduler-gpu   latest    6245707b04c7   2026-05-08 09:39:48 -0400 EDT
```
(GPU image freshly rebuilt; prior image was lost in Docker reset)

**Queue state before run:**
```json
{ "pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3 }
```

No `results.jsonl` existed before the run.

### Step 2 — Validation command

```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  warm-process --max-items 3 --json
```

**Exit code:** 0  
**Output captured to:** `artifacts/research/marker_ipc_validation/validation_run.json`

### Step 3 — Post-run queue state

```json
{ "pending": 2, "processing": 0, "done": 1, "failed": 0, "total": 3 }
```

```
arxiv:2604.24366   done      1 att   The Anatomy of a Decentralized Predictio
arxiv:1910.08858   pending   2 att   Beating the House: Identifying Inefficie
arxiv:2109.07581   pending   0 att   The Impact of COVID-19 on Sports Betting
```

---

## Full JSON Output

Decoded from `artifacts/research/marker_ipc_validation/validation_run.json`
(file was written UTF-16 LE by Tee-Object; content verified by read):

```json
{
  "processed": [
    {
      "candidate_id": "arxiv:2604.24366",
      "arxiv_id": "2604.24366",
      "title": "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book",
      "body_source": "marker",
      "body_length": 56923,
      "parse_seconds": 39.19,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 179.91,
      "processed_at": "2026-05-08T13:47:57.171881+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "arxiv_id": "1910.08858",
      "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
      "body_source": "error",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "Timeout fetching http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 15.11,
      "processed_at": "2026-05-08T13:48:12.323443+00:00",
      "attempt": 1,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "arxiv_id": "1910.08858",
      "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
      "body_source": "error",
      "body_length": 0,
      "parse_seconds": 0.0,
      "failure_reason": "HTTP 429 Unknown Error for http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1",
      "rejected": true,
      "exit_code": 1,
      "marker_ready": false,
      "total_seconds": 0.81,
      "processed_at": "2026-05-08T13:48:13.151436+00:00",
      "attempt": 2,
      "queue_status": "pending",
      "ipc_warm_worker_used": true
    }
  ],
  "exit_code": 0,
  "ipc_warm_worker_used": true
}
```

---

## Per-Paper Timing Table

| Paper | arXiv ID | Attempt | parse_seconds | total_seconds | body_source | ipc_warm_worker_used | Outcome |
|-------|----------|---------|---------------|---------------|-------------|----------------------|---------|
| 1 | 2604.24366 | 1 | 39.19s | 179.91s | marker | true | **PASS** |
| 2 | 1910.08858 | 1 | 0.0s | 15.11s | error | true | **FAIL — arXiv timeout** |
| 2 | 1910.08858 | 2 | 0.0s | 0.81s | error | true | **FAIL — arXiv HTTP 429** |
| 3 | 2109.07581 | — | — | — | — | — | **NOT RUN** |

Paper 1 `total_seconds=179.91s` includes IPC warm worker startup (model load ~140s) +
`parse_seconds=39.19s` + queue overhead. Paper 1 parse_seconds=39.19s reflects first-paper
overhead on warm VRAM; papers 2+ were expected to be ≤10s but never reached Marker.

---

## Gate-by-Gate Verdict

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | IPC worker process exists | **PASS** | `ipc_warm_worker_used=true` on all 3 result entries; warm worker launched and served paper 1 |
| 2 | Models stay warm (papers 2+ ≤10s) | **INCONCLUSIVE** | Paper 1 parse_seconds=39.19s (first-paper overhead expected); papers 2-3 never reached Marker parsing |
| 3 | ≥3 papers in one session | **FAIL** | Only 1 paper completed (`done`); 2 failed due to arXiv API; 1 never attempted |
| 4 | Queue semantics intact | **PASS** | Paper 1 transitioned correctly to `done`; paper 2 remains `pending` with attempts=2 (retryable); paper 3 at `pending` attempts=0 |
| 5 | No pdfplumber fallback | **PASS** | Paper 1 is `body_source=marker`; no pdfplumber path was triggered |
| 6 | Windows unchanged | N/A | Not tested in Docker run |
| 7 | Dev log with timing evidence | **PARTIAL** | Paper 1 timing documented; papers 2-3 not available |

**Hard stop triggered:** "arXiv API returns 429 or repeated timeout before parsing" — on paper 2, attempts 1 and 2.

**Overall: FAIL — gates 3 and 7 not met; gate 2 inconclusive. Closeout protocol NOT executed.**

---

## Root Cause Analysis

Paper 2 (1910.08858) triggered two arXiv metadata API failures inside the Docker container:

1. **Attempt 1:** `Timeout fetching http://export.arxiv.org/api/query?id_list=1910.08858&max_results=1`
   — The export.arxiv.org ATOM API timed out. The container may have briefly lost network
   connectivity, or arXiv rate-limiting kicked in after paper 1's fetch earlier in the session.

2. **Attempt 2 (immediate retry):** `HTTP 429 Unknown Error` — arXiv confirmed rate limiting.
   The immediate retry after a timeout made the 429 certain.

**Why paper 1 succeeded:** Paper 2604.24366 is the "anchor paper" from the prior single-paper
validation (2026-05-05). Its PDF and metadata may have been served from a container-internal
cache, or arXiv had no rate limit at that moment.

**Why the warm-process budget was consumed:** `--max-items 3` counts process invocations
(including retries) against the budget, not unique papers. Paper 2 consumed 2 of the 3 slots
via its two attempts; paper 3 never ran.

**IPC warm worker is NOT the failure.** The IPC warm worker started successfully, loaded
models once, processed paper 1 end-to-end via IPC, and remained alive across the paper 2
attempts (ipc_warm_worker_used=true on all entries, including the arXiv-failed ones).

---

## Positive Evidence from This Run

Despite the FAIL verdict, this run provides strong IPC warm worker validation evidence:

| Evidence | Value |
|----------|-------|
| IPC warm worker launched | Confirmed (`ipc_warm_worker_used=true`) |
| Paper 1 parsed via IPC | `body_source=marker`, `body_length=56923` |
| Paper 1 parse_seconds | 39.19s (first paper; model already warm in VRAM) |
| Paper 1 total_seconds | 179.91s (model load ~140s + parse 39.19s + overhead) |
| No pdfplumber fallback | Confirmed |
| Clean container exit | exit_code=0 |
| Queue semantics correct | Paper 1 done, paper 2 pending/retryable, paper 3 pending/untouched |

The IPC warm worker unblocked paper 1 in ~39s from warm VRAM vs 85.95s cold-process
(prior single-paper validation). Model loading happened once (~140s) and was amortized.

---

## Files Changed This Session

| File | Change |
|------|--------|
| `artifacts/research/marker_ipc_validation/validation_run.json` | JSON output from warm-process run |
| `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md` | Prior failure log (Docker image missing) |
| `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun-arxiv.md` | This file |

No implementation code, tests, SVM labels, trading files, L2, or L4 paths were modified.

---

## Feature 3 Status

**Feature 3 (Marker Docker IPC Warm-Worker v1) remains ACTIVE.**

Gates 3 and 7 are unmet. Gate 2 is inconclusive. Closeout protocol was NOT executed.
L1 Marker production rollout remains BLOCKED.

Queue state for next attempt:
- Paper 1 (2604.24366): already `done` — will be skipped
- Paper 2 (1910.08858): `pending`, attempts=2 — needs arXiv cooldown before retry
- Paper 3 (2109.07581): `pending`, attempts=0 — untouched, ready

---

## Next Action for Operator

The validation needs papers 2 and 3 to parse successfully. Two paths:

### Option A — Wait for arXiv cooldown and retry (simplest)

arXiv rate limits typically reset within a few hours. Retry tomorrow morning:

```powershell
# Verify queue state first (paper 1 should still be done)
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  counts --json

# Re-run — paper 1 will be skipped (already done), papers 2-3 will attempt
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  warm-process --max-items 2 --json
```

Expected: paper 2 (46 pages, 8 eq refs) and paper 3 (23 pages, 0 eq refs) both parse
from warm VRAM in ≤10s each.

### Option B — Replace paper 2 with a paper already in local PDF cache

If arXiv cooldown is inconvenient, swap 1910.08858 for another paper whose PDF and
metadata are already cached locally (so no arXiv API call needed during warm-process):

```powershell
# First check what's cached
Get-ChildItem artifacts/research/raw_source_cache/academic/ | Sort-Object Length -Descending | Select-Object -First 10 Name, Length

# Then re-enqueue using --url for a known-cached paper ID
# (check the cache files to find a second suitable candidate)
```

### Important: max-items budget accounting

The max-items budget counts invocations including retries. Use `--max-items 4` if there
is any risk of a single paper retrying:

```powershell
warm-process --max-items 4 --json
```

This ensures papers 2 AND 3 both get attempted even if one has an initial retry.
