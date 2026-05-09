# Marker Docker IPC Warm-Worker v1 — Live Validation FAIL (GPU Image Missing)

Date: 2026-05-08
Type: live-validation failure report
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Verdict: **FAIL — GPU Docker image missing; validation could not run**

---

## Summary

The live Docker warm-worker validation could not complete. The GPU image
`polytool-ris-scheduler-gpu:latest` is absent from both accessible Docker
contexts (`default` and `desktop-linux`). Docker exit code 125 was returned
immediately — the warm-process command never started. The validation queue is
intact (3 pending, 0 done, 0 failed). The constraint prohibiting Docker rebuild
is in effect; this session stopped immediately per hard-stop protocol.

Feature 3 remains ACTIVE. L1 Marker production rollout remains BLOCKED.

---

## Commands Run and Outputs

### Baseline checks (before attempt)

**C drive free space:**
```
C drive free: 2.05 GB
```

**docker --context default ps:**
```
NAMES                    STATUS          IMAGE
polytool-ris-scheduler   Up 38 minutes   polytool-ris-scheduler
```

**Queue counts before attempt:**
```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
  "failed": 0,
  "total": 3
}
```

**Queue list before attempt:**
```
  candidate_id                 status       att   title
  -------------------------------------------------------------------------------------------
  arxiv:2604.24366             pending      0     The Anatomy of a Decentralized Predictio
  arxiv:1910.08858             pending      0     Beating the House: Identifying Inefficie
  arxiv:2109.07581             pending      0     The Impact of COVID-19 on Sports Betting

Total: 3 item(s)
```

No `results.jsonl` existed before the attempt. All checks matched preflight expectations.

### Validation command attempted

```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  warm-process --max-items 3 --json
```

**Exit code:** 125

**Docker stderr output:**
```
Unable to find image 'polytool-ris-scheduler-gpu:latest' locally
docker: Error response from daemon: pull access denied for polytool-ris-scheduler-gpu,
repository does not exist or may require 'docker login'
```

### Image investigation

**docker --context default image ls:**
```
REPOSITORY               TAG       IMAGE ID       CREATED AT
polytool-ris-scheduler   latest    f4c23a2ea9ac   2026-05-04 14:37:45 -0400 EDT
```

**docker --context desktop-linux image ls:**
```
REPOSITORY               TAG       IMAGE ID       CREATED AT
polytool-ris-scheduler   latest    f4c23a2ea9ac   2026-05-04 14:37:45 -0400 EDT
```

**Conclusion:** `polytool-ris-scheduler-gpu:latest` is absent from both contexts.
Only the CPU image `polytool-ris-scheduler:latest` is present.

### Post-attempt state

**C drive free after attempt:** 1.87 GB (still above 1 GB hard stop)

**Queue counts after attempt (unmodified):**
```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
  "failed": 0,
  "total": 3
}
```

No queue mutation occurred. The warm-process command never ran.

---

## Gate-by-Gate Verdict

| # | Gate | Status | Evidence |
|---|------|--------|----------|
| 1 | Docker daemon healthy | PASS | `docker --context default ps` exit 0; scheduler container Up 38 min |
| 2 | GPU image present | **FAIL** | `polytool-ris-scheduler-gpu:latest` absent from both contexts |
| 3 | warm-process command runs | **BLOCKED** | Docker exit 125 before command started |
| 4 | ≥3 papers completed, warm | **BLOCKED** | warm-process never ran |
| 5 | Papers 2+ ≤10s | **BLOCKED** | warm-process never ran |
| 6 | `ipc_warm_worker_used=true` | **BLOCKED** | warm-process never ran |
| 7 | `body_source=marker` | **BLOCKED** | warm-process never ran |
| 8 | No pdfplumber fallback | **BLOCKED** | warm-process never ran |
| 9 | Clean shutdown | **BLOCKED** | warm-process never ran |
| 10 | Queue intact after run | PASS | 3 pending, 0 done, 0 failed — unmodified |

**Overall: FAIL on Gate 2. All subsequent gates blocked.**

---

## Disk Space

| Point | C Drive Free |
|-------|-------------|
| Before attempt | 2.05 GB |
| After attempt | 1.87 GB |

Remained above the 1 GB hard stop. No Docker prune or rebuild was run.

---

## Root Cause

The GPU image `polytool-ris-scheduler-gpu:latest` was built on 2026-05-07 (confirmed
in prior preflight: `sha256:c28202a3ebfafb2f5a0f1371f54c4060f44f832173c3b84eda465c6cc696aae0`,
created `2026-05-07T18:28:14`). It was still present at the time of the final Codex
preflight review earlier today (`2026-05-08_codex-verify-marker-ipc-live-validation-final-preflight.md`).

**Hypothesis:** Docker Desktop was restarted between the preflight session and this
validation session. Docker Desktop on Windows sometimes resets its WSL2 VM, which can
lose locally-built images if the Docker data root is on a volatile backing store or if
a reset/prune occurred. The CPU image `polytool-ris-scheduler:latest` also vanished
from both contexts (replaced by a different ID `f4c23a2ea9ac` vs the GPU image's
`c28202a3eb...`), which is consistent with a full Docker reset.

The constraint "No Docker rebuild" was in force for this session; this session stopped
immediately on detecting the missing image.

---

## Per-Paper Timing Table

No papers were processed. warm-process command never ran.

| Paper | arXiv ID | parse_seconds | Status |
|-------|----------|---------------|--------|
| 1 | 2604.24366 | — | NOT RUN |
| 2 | 1910.08858 | — | NOT RUN |
| 3 | 2109.07581 | — | NOT RUN |

---

## Files Changed

| File | Change |
|------|--------|
| `artifacts/research/marker_ipc_validation/` | Directory created; `validation_run.json` created (empty — Docker failed before output) |
| `docs/dev_logs/2026-05-08_marker-docker-ipc-warm-worker-live-validation-rerun.md` | This file |

No implementation code, tests, queue state, SVM labels, trading files, L2, or L4 paths
were modified.

---

## Feature 3 Status

**Feature 3 (Marker Docker IPC Warm-Worker v1) remains ACTIVE and BLOCKED.**

All 7 acceptance gates are unmet. The warm-process command never ran.
L1 Marker production rollout remains BLOCKED.
Closeout protocol was NOT executed — Feature 3 does NOT move to Recently Completed.

---

## Next Action for Operator

1. **Rebuild the GPU image:**
   ```powershell
   docker compose --profile ris-gpu build ris-scheduler-gpu
   ```
   This was explicitly out of scope for this session (constraint: "No Docker rebuild")
   but is the required fix. C drive space must be verified before building — the
   image build requires ~2-3 GB of temporary space.

2. **Verify image after rebuild:**
   ```powershell
   docker --context default image ls
   # or
   docker --context desktop-linux image ls
   ```
   Confirm `polytool-ris-scheduler-gpu:latest` appears.

3. **Re-run the preflight warm-process --help check:**
   ```powershell
   docker --context default run --rm polytool-ris-scheduler-gpu:latest `
     python -m polytool research-marker-queue warm-process --help
   ```

4. **Re-run the live validation (one attempt):**
   ```powershell
   docker --context default run --rm --gpus all `
     -v "${PWD}/artifacts:/app/artifacts" `
     polytool-ris-scheduler-gpu:latest `
     python -m polytool research-marker-queue `
     --queue-dir artifacts/research/marker_validation_queue `
     warm-process --max-items 3 --json
   ```
   Queue is still at 3 pending — no re-enqueue needed.

5. **Check C drive free space before rebuild** — currently at 1.87 GB.
   Recommend ensuring at least 3 GB free before rebuilding the GPU image.

---

## Codex Review Summary

Not required — validation did not run. No code, tests, implementation, or queue
state was modified. This log and the empty `artifacts/research/marker_ipc_validation/`
directory are the only outputs.
