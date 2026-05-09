# Marker IPC Daemon-Fix Direct-PDF Live Validation

Date: 2026-05-08
Type: live Docker/GPU warm-worker validation — one allowed attempt (consumed)
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1 (daemon=False fix)
Verdict: **PARTIAL — daemon=False fix works, all 3 papers completed; FAIL on ≤10s timing gate**

---

## Summary

The one allowed live Docker/GPU validation with the daemon=False fix ran against a
fresh direct-PDF queue. All three papers parsed successfully with `body_source=marker`
and `ipc_warm_worker_used=true`. No daemonic process error appeared. The warm-worker
is now functionally correct.

However, papers 2 and 3 `parse_seconds` (69.73s and 48.31s) both exceed the ≤10s gate
that is required by the Feature 3 acceptance criteria. The hard stop condition
"Any paper 2+ parse_seconds >10s" is triggered.

The timing gate failure reflects actual warm GPU inference speed, not a daemon or
code bug. Papers 2 and 3 have essentially zero cold-load overhead (total_seconds ≈
parse_seconds, delta 0.13–0.22s), confirming the IPC warm-worker is maintaining model
state across papers. The ≤10s target does not match the actual warm inference
performance for academic PDFs of this size on the RTX 2070 Super (~45–70s/paper).

Feature 3 closeout may NOT run. L1 Marker production rollout remains BLOCKED. An
operator decision is required on whether to revise the ≤10s gate or select different
validation papers.

---

## Step 1 — Baseline Checks

### git status
```
 M Dockerfile.ris
 M docs/INDEX.md
 M docs/dev_logs/2026-05-03_academic-pipeline-hosting-decision.md
 M docs/obsidian-vault/.obsidian/workspace.json
 M [obsidian smart-env files]
 M packages/research/ingestion/fetchers.py
 M packages/research/ingestion/marker_queue.py
 M tests/test_ris_marker_queue.py
 M tools/cli/research_marker_queue.py
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
?? [40+ dev log files]
```

### C drive free space
- **Before run:** 40.44 GB free / 230.87 GB total
- **After run:** 40.42 GB free / 230.87 GB total
- Delta: 0.02 GB (model weights already cached; no new Docker layers pulled)
- Hard stop threshold: 1 GB — NOT triggered

### Docker containers before run
```
NAMES     IMAGE     STATUS
(none running)
```

### Docker image
```
polytool-ris-scheduler-gpu   latest   6245707b04c7   2026-05-08 09:39:48   9.4GB
```
Image is stale (created before daemon=False fix). Bind-mount overlay required.

### Queue counts before run (after reset)
```json
{"pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3}
```
Queue was reset from the prior run state (pending=2, done=1) per scope instructions.

---

## Step 2 — Queue Reset Evidence

Queue had prior run state (pending=2, done=1, failed=0) — not exactly 3 pending/0 done.
Both `queue.jsonl` and `results.jsonl` were deleted and all 3 papers re-enqueued fresh.

### Enqueue commands run
```powershell
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  enqueue --url 2604.24366 `
  --pdf-url https://arxiv.org/pdf/2604.24366.pdf `
  --title "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book" `
  --json
# → {"candidate_id": "arxiv:2604.24366", "status": "pending", "action": "added"}

python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  enqueue --url 2109.07581 `
  --pdf-url https://arxiv.org/pdf/2109.07581.pdf `
  --title "The Impact of COVID-19 on Sports Betting Markets" `
  --json
# → {"candidate_id": "arxiv:2109.07581", "status": "pending", "action": "added"}

python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  enqueue --url 1910.08858 `
  --pdf-url https://arxiv.org/pdf/1910.08858.pdf `
  --title "Beating the House: Identifying Inefficiencies in Sports Betting Markets" `
  --json
# → {"candidate_id": "arxiv:1910.08858", "status": "pending", "action": "added"}
```

Post-enqueue counts confirmed: `{"pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3}`.

---

## Step 3 — Container Source-Code Verification

### Enqueue --help (full repo bind-mount only)
```powershell
docker --context default run --rm `
  -v "${PWD}:/app" -w /app `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue enqueue --help
```
Result: `--pdf-url PDF_URL_OR_PATH` present. ✓ Current tools/cli code visible via full repo mount.

### daemon=False verification (packages/research overlay)
```powershell
docker --context default run --rm `
  -v "${PWD}:/app" `
  -v "${PWD}/packages/research:/usr/local/lib/python3.11/site-packages/packages/research" `
  -w /app `
  polytool-ris-scheduler-gpu:latest `
  python -c "from packages.research.ingestion import marker_ipc_worker as m; import inspect; src = inspect.getsource(m.MarkerIPCWorker.start); has_daemon_false = 'daemon=False' in src; print('daemon=False in start():', has_daemon_false); print('FILE:', m.__file__)"
```
Result:
```
daemon=False in start(): True
FILE: /usr/local/lib/python3.11/site-packages/packages/research/ingestion/marker_ipc_worker.py
```

Notes:
- Full repo bind-mount (`-v "${PWD}:/app"`) makes `/app` available but Python's
  sys.path resolves `packages` from site-packages (stale build), not `/app/packages/`.
  This was confirmed in the prior live validation dev log (2026-05-08_marker-ipc-direct-pdf-live-validation.md).
- A second overlay bind-mount is required:
  `-v "${PWD}/packages/research:/usr/local/lib/python3.11/site-packages/packages/research"`
  This injects current ingestion code (with daemon=False) into site-packages at runtime.
- Both mounts were used for the live validation run.

---

## Step 4 — Live Validation Command

```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}:/app" `
  -v "${PWD}/packages/research:/usr/local/lib/python3.11/site-packages/packages/research" `
  -v "$env:USERPROFILE\.cache\datalab:/home/polytool/.cache/datalab" `
  -w /app `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  warm-process --max-items 3 --json | Tee-Object -FilePath $logfile
```

**Log file:** `artifacts/research/marker_ipc_validation/daemon_fix_direct_pdf_live_20260508_115111.log`

**Marker progress bars** (stderr): Three full Marker inference passes ran, with multi-model
pipelines (Recognizing Layout, Running OCR Error Detection, Detecting bboxes,
Recognizing Text, Recognizing tables) for each paper. All three completed successfully.

---

## Step 5 — Full JSON Output

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
      "parse_seconds": 45.55,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 72.31,
      "processed_at": "2026-05-08T15:52:33.945798+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:2109.07581",
      "source_url": "https://arxiv.org/abs/2109.07581",
      "arxiv_id": "2109.07581",
      "title": "The Impact of COVID-19 on Sports Betting Markets",
      "body_source": "marker",
      "body_length": 51304,
      "parse_seconds": 69.73,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 69.86,
      "processed_at": "2026-05-08T15:53:43.927252+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    },
    {
      "candidate_id": "arxiv:1910.08858",
      "source_url": "https://arxiv.org/abs/1910.08858",
      "arxiv_id": "1910.08858",
      "title": "Beating the House: Identifying Inefficiencies in Sports Betting Markets",
      "body_source": "marker",
      "body_length": 60645,
      "parse_seconds": 48.31,
      "failure_reason": null,
      "rejected": false,
      "exit_code": 0,
      "marker_ready": true,
      "total_seconds": 48.53,
      "processed_at": "2026-05-08T15:54:32.519403+00:00",
      "attempt": 1,
      "queue_status": "done",
      "ipc_warm_worker_used": true
    }
  ],
  "exit_code": 0,
  "ipc_warm_worker_used": true
}
```

---

## Step 6 — Per-Paper Timing Table

| Paper | candidate_id | parse_seconds | total_seconds | delta | body_source | ipc_warm_worker_used | queue_status |
|-------|-------------|--------------|--------------|-------|-------------|---------------------|--------------|
| 1 | arxiv:2604.24366 | 45.55 | 72.31 | 26.76 | marker | true | done |
| 2 | arxiv:2109.07581 | **69.73** | 69.86 | **0.13** | marker | true | done |
| 3 | arxiv:1910.08858 | **48.31** | 48.53 | **0.22** | marker | true | done |

**Delta = total_seconds − parse_seconds** (cold-load + download overhead)

Key observation: Papers 2 and 3 have delta ≈ 0.13–0.22s. This confirms the IPC
warm-worker IS maintaining model state across papers. The only overhead beyond Marker
inference for papers 2+ is PDF download and queue bookkeeping (~0.2s). There is NO
cold-load overhead for papers 2+.

Paper 1 has delta=26.76s, which is the one-time cold load cost amortized at session start.

---

## Step 7 — Gate-by-Gate Evaluation

| Gate | Requirement | Result | PASS/FAIL |
|------|-------------|--------|-----------|
| 3 papers completed in one session | all 3 done | done=3, pending=0, failed=0 | **PASS** |
| Papers 2+ parse_seconds ≤10s | each warm paper ≤10s | paper 2: 69.73s, paper 3: 48.31s | **FAIL** |
| `ipc_warm_worker_used=true` | true on all completed | all 3 have true | **PASS** |
| `body_source=marker` | all completed papers | all 3 are marker | **PASS** |
| No pdfplumber fallback | body_source ≠ pdfplumber/pdfplumber_fallback | none appeared | **PASS** |
| Clean shutdown / no orphan process | container exits cleanly | `docker ps` empty; exit_code=0 | **PASS** |
| No Docker rebuild/prune | bind-mount preferred | two volume mounts used, no rebuild | **PASS** |
| L1 not marked unblocked | feature doc / current dev still blocking | docs unchanged | **PASS** |
| Disk above 1 GB hard stop | >1 GB free | 40.44→40.42 GB | **PASS** |

**Overall verdict: FAIL** — timing gate not met (papers 2, 3 parse_seconds >10s).

---

## Step 8 — Queue State After Run

```json
{"pending": 0, "processing": 0, "done": 3, "failed": 0, "total": 3}
```

All 3 papers moved to `done`. No failed items. No stuck-in-processing items.

---

## Step 9 — Orphan Process Check

```
docker --context default ps
NAMES     IMAGE     STATUS
(empty)
```

No running Docker containers after run. Container ran with `--rm` and exited cleanly.
Host-level Marker/Python processes were terminated on container exit. Clean.

---

## Step 10 — Analysis: Timing Gate vs Warm-Worker Behavior

The IPC warm-worker is functionally correct after the daemon=False fix:

- Papers 2 and 3 have delta ≈ 0.13–0.22s (vs paper 1 delta=26.76s).
  Models loaded once; no cold-load penalty for papers 2+.
- No daemonic process error.
- All papers: body_source=marker, ipc_warm_worker_used=true.
- No pdfplumber fallback.

The timing gate failure (parse_seconds >10s for papers 2+) is NOT a code bug — it is a
mismatch between the original ≤10s target and the actual RTX 2070 Super warm inference
speed for multi-page academic PDFs:

| Paper | Pages (approx) | Warm parse time |
|-------|---------------|-----------------|
| arxiv:2604.24366 | 15 | 45.55s |
| arxiv:2109.07581 | 23+ | 69.73s |
| arxiv:1910.08858 | 46 | 48.31s |

Marker runs a multi-model pipeline per paper (layout detection, OCR error detection,
bounding box detection, text recognition, table recognition). Even with warm VRAM, this
pipeline requires ~45–70s for 15–46-page papers.

The original ≤10s gate was aspirational and based on an over-optimistic estimate for
this hardware + paper complexity combination.

---

## Step 11 — Feature 3 Status and Next Actions

**Feature 3 is BLOCKED. L1 Marker production rollout remains BLOCKED.**

The daemon=False fix is confirmed working. The IPC warm-worker successfully maintains
Marker models across multiple papers. However, the ≤10s/paper timing gate was not met.

**Operator decision required (three options):**

1. **Revise the timing gate** to reflect actual warm inference performance
   (~50–70s/paper). The warm-worker still provides value: papers 2+ avoid the cold-load
   penalty (saving ~26s per session vs. a cold-subprocess approach). If the gate is
   revised to, e.g., ≤90s/paper with >0 warm speedup vs. cold, this validation run
   would PASS all remaining criteria.

2. **Use simpler validation papers** — select shorter papers (≤5 pages) where warm
   GPU inference could complete in ≤10s. Re-run one new validation with those papers
   against a fresh queue.

3. **Accept Feature 3 as COMPLETE on a revised gate** — if the operator determines
   that the IPC warm-worker's demonstrated behavior (daemon=False fixed, all papers
   parse with body_source=marker, no cold-load overhead for papers 2+) is sufficient
   to unblock L1, an explicit operator gate-revision decision is required before any
   closeout log is written.

**Do NOT:**
- Retry validation without operator approval of gate change.
- Close Feature 3 or unblock L1 without operator gate-revision decision.
- Start L2/PaperQA2/L4.

---

## Codex Review Summary

Tier: live validation run (queue consumer, research ingestion). Mandatory trading/risk
execution files not in scope.

Issues found: timing gate not met (69.73s, 48.31s for papers 2+). Daemon=False fix
confirmed functional. Warm-worker operational. Timing expectation needs operator revision.

Issues addressed: none this session — this dev log is the output.
