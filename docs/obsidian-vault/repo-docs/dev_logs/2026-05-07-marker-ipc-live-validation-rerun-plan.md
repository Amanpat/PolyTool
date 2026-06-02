---
title: Marker Ipc Live Validation Rerun Plan
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker IPC Live Validation — Rerun Plan

**Date:** 2026-05-07
**Type:** Planning doc (no live Docker run)
**Track:** RIS — L1 Marker IPC Warm-Worker (Feature 3)
**L1 Status:** BLOCKED — gate requires ≥3 warm papers at ≤10s/paper in one session
**Codex review:** Skip — docs-only

---

## Objective

Prepare a precise, executable rerun of the `research-marker-queue warm-process` live Docker/GPU
validation. Prior run (2026-05-07 AM) failed entirely due to arXiv metadata API rate limiting
(HTTP 429/timeout on all 3 papers in Run 4). The rerun plan must minimize API failure risk by
waiting for the rate limit to clear and using confirmed-simple papers.

**This doc does NOT run live validation.** It exists so the next prompt can trigger the rerun
without discovery overhead.

---

## CLI Surface Verified (read-only)

```
python -m polytool research-marker-queue --help
python -m polytool research-marker-queue warm-process --help
python -m polytool research-marker-queue counts --json
python -m polytool research-marker-queue list --status all --json
```

**Findings:**

| Command | Result |
|---------|--------|
| `--help` | CLI loads; `warm-process` subcommand present; L1 gate language intact |
| `warm-process --help` | Flags: `--max-items N` (default 1), `--marker-timeout SECONDS` (default 900), `--json` |
| `counts --json` | `{"pending": 2, "processing": 0, "done": 0, "failed": 1, "total": 3}` |
| `list --status all --json` | 3 items (see Current Queue State below) |

---

## Current Queue State

```
pending : 2
done    : 0
failed  : 1  (3 attempts exhausted)
total   : 3
```

| candidate_id | status | attempts | last_failure |
|-------------|--------|----------|-------------|
| arxiv:2604.24366 | failed | 3 | Timeout fetching export.arxiv.org/api/query |
| arxiv:2412.14173 | pending | 2 | HTTP 429 on export.arxiv.org/api/query |
| arxiv:2204.05149 | pending | 0 | (never attempted) |

**All failures were arXiv metadata API rate-limiting, not OCR complexity.**
No PDF was ever downloaded in Run 4.

`MAX_ATTEMPTS = 3` (in `marker_queue.py`). `arxiv:2412.14173` has 1 attempt remaining before
it permanently transitions to `failed`.

---

## Root Cause of Prior Failure

`LiveAcademicFetcher.fetch()` **always** calls `http://export.arxiv.org/api/query?id_list=...`
before downloading the PDF (line 699, `fetchers.py`). There is no bypass, even when the
`title` field is pre-populated in the queue record. After ~15 cumulative API calls in the prior
session (across 3 earlier runs), arXiv rate-limited the IP for 60+ minutes. Run 4 hit the
blocked window immediately on all 3 papers.

**This is not a code bug in scope for this session.** A direct-PDF path that bypasses the
metadata API would require a code change. The plan works around this by waiting for the
rate limit to clear.

---

## Fixes Already Applied (do not re-apply)

These two blockers were fixed in `2026-05-07_fix-marker-ipc-live-validation-blockers.md`:

| Fix | File | Status |
|-----|------|--------|
| Dockerfile.ris rebuild gap | `Dockerfile.ris` — added `mkdir -p packages/research/relevance_filter` | **APPLIED** |
| Worker restart after timeout | `packages/research/ingestion/fetchers.py` — restart IPC worker after `marker_timeout` | **APPLIED** |

---

## Prerequisites Before Issuing Rerun

1. **arXiv API cooldown:** Last API call was `2026-05-07T16:42:17 UTC`. Must wait ≥60 min from
   that time. Earliest safe retry: **2026-05-07 ~17:45 UTC** or the next session (recommended).
   The longer the wait (2–3 hours), the more reliable the rate-limit recovery.

2. **Rebuild Docker image:** `Dockerfile.ris` was patched but the image was NOT rebuilt in the
   blockers-fix session (intentionally deferred). The image must be rebuilt before the rerun.
   ```powershell
   docker compose --profile ris-gpu build ris-scheduler-gpu
   ```
   Expected: build completes without `error: package directory ./packages/research/relevance_filter
   does not exist`. If this fails, stop and diagnose.

3. **Reset queue anchor paper:** `arxiv:2604.24366` is in `status=failed` (3 attempts exhausted).
   Reset it via `enqueue --force`:
   ```powershell
   python -m polytool research-marker-queue enqueue --url 2604.24366 --force
   ```
   This resets `status → pending` and `attempts → 0`.

4. **Verify or replace papers 2-3** (see Candidate Papers section below).

---

## Candidate Papers

### Anchor — Paper 1 (mandatory)

**`arxiv:2604.24366`** — "The Anatomy of a Decentralized Prediction Market: Microstructure
Evidence from the Polymarket Order Book"

- **Why:** PROVEN in 2026-05-05 single-paper validation: cold OCR = 85.9s total, body_length
  = 56,923 chars, body_source = "marker", exit_code = 0. 15 pages, economics prose, minimal
  figures, no heavy math equations.
- **Expected warm time:** ~6s (prior warm-worker estimate; model already loaded from paper 1's
  cold run). If used as paper 1, subsequent papers pay the cold-load cost.
- **Action required:** `enqueue --force` to reset from `failed`.
- **Risk:** None for OCR. API rate-limit is the only risk — eliminated by cooldown wait.

---

### Papers 2-3 — CANDIDATE SELECTION REQUIRED (live validation blocked until complete)

**Status:** Neither paper in the current main queue (`2204.05149`, `2412.14173`) has
verified content. Both have empty titles — arXiv API was rate-limited before metadata
was ever fetched. No local evidence exists for either paper's complexity, page count,
or prose density.

**`arxiv:2412.14173` is EXCLUDED from the rerun.** It has 2 attempts consumed, 1 remaining
before permanent `failed`. If the rerun cooldown is insufficient and the next API call hits
429, it transitions to `failed` with no recovery path (without a code-level queue edit).
Do not use it.

**`arxiv:2204.05149` is UNVERIFIED.** April 2022 paper. Title unknown. Could be a
long ML paper or a short empirical econ paper. Do not use it without operator verification.

**The rerun uses a fresh isolated validation queue (`--queue-dir`) and does NOT touch
the main queue (`artifacts/research/marker_parse_queue`).** This avoids contaminating the
main queue and eliminates the `2412.14173` permanently-failing risk entirely.

---

### Candidate Profile for Papers 2-3

The operator must identify 2 papers meeting ALL of the following before proceeding:

- arXiv category: `econ.GN`, `econ.EM`, `econ.TH`, `q-fin.GN`, `q-fin.TR`, or `stat.AP`
  (these categories are prose-heavy with low figure density)
- Page count: **8–18 pages** as rendered in a PDF viewer (not counting appendix pages)
- Content check: scroll through the PDF in a browser — acceptable if:
  - Mostly prose paragraphs and tables
  - Fewer than 3 full-figure pages
  - No dense multi-line equation blocks
- Not a methods/ML paper (avoid `cs.*`, `stat.ML`, `math.*` unless clearly empirical)
- Known to be on arXiv (has an arXiv ID you can pass to `--url`)

Enqueue into the fresh validation queue with a title hint:
```powershell
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url <arxiv_id> --title "Paper title here"
```

Short empirical prediction-market or financial microstructure papers in the same family as
`2604.24366` are the safest choice. NBER / SSRN working papers that are cross-posted to
arXiv also work well if they are in the 10–15 page range.

**Do not fill in PAPER2_ID / PAPER3_ID in the Step 2 commands until both papers are
verified by the operator and you have their arXiv IDs confirmed.**

---

## Exact Rerun Command

### Step 1 — Build the image (run on host, PowerShell)

```powershell
docker compose --profile ris-gpu build ris-scheduler-gpu
```

Expected: exits 0, no package directory errors.

### Step 2 — Prepare queue (run on host, PowerShell)

```powershell
# Build fresh validation queue (isolated from main queue; avoids 2412.14173 contamination)
# Replace PAPER2_ID and PAPER3_ID with verified candidates (see Candidate Selection section)
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url 2604.24366
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url PAPER2_ID --title "Paper 2 title hint"
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url PAPER3_ID --title "Paper 3 title hint"

# Verify queue state before continuing
python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue counts --json
# Expected: {"pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3}
```

**STOP:** Do not proceed to Step 3 if counts show anything other than `pending: 3, failed: 0`.
PAPER2_ID and PAPER3_ID must be filled in from the verified candidate list below before
running these commands.

### Step 3 — Run warm-process in Docker (PowerShell)

```powershell
# Create log directory if absent
New-Item -ItemType Directory -Force -Path artifacts/research/marker_ipc_validation | Out-Null

# Run warm-process, capture output
$logFile = "artifacts/research/marker_ipc_validation/warm_process_rerun_$(Get-Date -Format yyyyMMdd_HHmm).log"

docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-marker-queue `
    --queue-dir artifacts/research/marker_validation_queue `
    warm-process `
    --max-items 3 `
    --marker-timeout 900 `
    --json `
  2>&1 | Tee-Object -FilePath $logFile

Write-Host "Log written to: $logFile"
```

**If `docker compose run` cannot see the queue files** (volume not mounted in compose profile):
use `docker run` with an explicit bind mount:

```powershell
$queuePath = (Resolve-Path "artifacts/research/marker_validation_queue").Path
$logFile = "artifacts/research/marker_ipc_validation/warm_process_rerun_$(Get-Date -Format yyyyMMdd_HHmm).log"

docker run --rm --gpus all `
  -v "${queuePath}:/app/artifacts/research/marker_validation_queue" `
  polytool-ris-scheduler-gpu `
  python -m polytool research-marker-queue `
    --queue-dir artifacts/research/marker_validation_queue `
    warm-process `
    --max-items 3 `
    --marker-timeout 900 `
    --json `
  2>&1 | Tee-Object -FilePath $logFile
```

Replace `polytool-ris-scheduler-gpu` with the actual image name from `docker images` if
the compose file uses a different tag.

**STOP immediately if Paper 1 returns `failure_reason` containing `"429"` or `"Timeout fetching"`.
The arXiv rate limit has not cleared. Wait 60–120 more minutes and retry from Step 1.**

---

## Expected Sequence of Events (if all goes well)

1. Container starts, Python imports load.
2. Paper 1 (`2604.24366`): arXiv API call resolves metadata (~1-2s if rate limit cleared).
3. IPC worker subprocess starts, loads Marker GPU models once (~50s cold load).
4. Paper 1 OCR runs: expected ~85s (proven).
5. Paper 1 result emitted: `body_source=marker`, `parse_seconds≈85`, `ipc_warm_worker_used=true`.
6. Paper 2: arXiv API call (~1s). IPC worker is warm (models already loaded).
7. Paper 2 OCR runs: expected **≤10s** (warm, no model reload) if it is simple prose.
8. Paper 3: same as paper 2.
9. Three results emitted in JSON. Container exits cleanly.

Total expected wall time: ~200–300s (model load + 3 papers).

---

## Pass/Fail Table Template

Fill this in after the rerun:

| # | candidate_id | queue_id | parse_seconds | ipc_warm_worker_used | body_source | body_length | status | notes |
|---|-------------|----------|--------------|---------------------|-------------|-------------|--------|-------|
| 1 | arxiv:2604.24366 | — | — | — | — | — | — | Cold load; model load time included |
| 2 | arxiv:XXXXXXX | — | — | — | — | — | — | Warm; must be ≤10s |
| 3 | arxiv:XXXXXXX | — | — | — | — | — | — | Warm; must be ≤10s |

**Pass criteria:**
- All 3: `body_source = "marker"` (not `error`, not `pdfplumber`, not `marker_failed`)
- All 3: `ipc_warm_worker_used = true`
- Papers 2-3: `parse_seconds <= 10.0`
- Paper 1: `parse_seconds <= 900.0` (any reasonable cold value is OK)
- Zero `worker_not_running` failures (validates the restart-after-timeout fix, indirectly)

---

## Acceptance Gates

| Gate | Pass condition |
|------|---------------|
| G1 | ≥3 papers processed successfully in one warm-process session |
| G2 | Papers 2+ show `parse_seconds <= 10s` (warm, model already loaded) |
| G3 | `ipc_warm_worker_used: true` on all result records |
| G4 | No `pdfplumber` body_source (Marker-only gate holds) |
| G5 | No orphan subprocesses after container exit |
| G6 | Queue v0 semantics intact (status transitions, results.jsonl appends) |

All 6 must pass to declare L1 unblocked.

---

## Guardrails

1. **No more than one retry per paper.** If a paper fails, mark it and continue. Do not
   re-enqueue and retry within the same validation run.

2. **Stop immediately on arXiv API rate-limit.** If paper 1 returns
   `failure_reason: "Timeout fetching http://export.arxiv.org/api/query..."` or
   `"HTTP 429 ..."`, the cooldown window has not cleared. Stop the run, wait another
   60-120 min, and retry the entire run. Do not proceed to paper 2 with a rate-limited API.

3. **Stop if paper 1 exceeds 900s timeout AND restart behavior fails.** If paper 1 hits the
   `marker_timeout` error AND the subsequent papers immediately return `worker_not_running`
   (which should no longer happen after the fetchers.py restart fix), something is wrong with
   the deployed code. Stop, diagnose, and do NOT count this as a paper toward the gate.

4. **No closeout unless ≥3 papers complete AND papers 2+ are ≤10s.** Partial passes (1-2 papers,
   or papers 2-3 at 60-80s) do NOT unblock L1. The warm-worker speed guarantee is the core
   of the gate. A slow paper 2 means either the model reloaded (IPC failed) or the paper is
   too complex.

5. **No more than one full validation run before diagnosing.** If the run fails again, write a
   follow-up dev log diagnosing the new failure before a second attempt.

---

## Known Risks

| Risk | Likelihood | Mitigation |
|------|-----------|-----------|
| arXiv API still rate-limited | Medium if cooldown is <60 min | Wait full cooldown; check with a manual curl before running |
| Papers 2-3 are complex PDFs | Medium (`2204.05149` unknown, any replacement) | Verify page count + content in browser before enqueue |
| IPC worker restart fix not in image | Low (fix was applied to source) | Image rebuild picks it up; verify with `docker exec ... python -c "from packages.research.ingestion.fetchers import _marker_ipc_worker_extract; print('ok')"` |
| Dockerfile.ris rebuild fails again for different reason | Low | Build output will show the error; stop and diagnose |
| `arxiv:2412.14173` permanently fails before reset | Low (not being used in preferred plan) | Exclude it; replace with a known paper |
| GPU not available in rebuilt container | Low | Check `nvidia-smi` and `docker info --format '{{json .Runtimes}}'` |

---

## Rate Limit Pre-Check (optional but recommended)

Before triggering the Docker run, verify arXiv API is accessible from the host:

```powershell
curl -s "http://export.arxiv.org/api/query?id_list=2604.24366&max_results=1" | Select-String "entry"
```

Expected: XML with `<entry>` element for the paper. If it returns empty XML or times out:
the rate limit has not cleared. Wait longer.

---

## Preflight Checklist (all items must be checked with evidence before rerun)

No item may be checked without running the stated command and observing the stated output.

```
[ ] 1. arXiv API cooldown cleared
        Command: curl -s "http://export.arxiv.org/api/query?id_list=2604.24366&max_results=1" | Select-String "entry"
        Evidence required: XML response contains <entry> with title text.
        If output is empty or times out: wait 60–120 more minutes and re-run.

[ ] 2. Papers 2-3 selected and verified by operator
        Evidence required: operator has viewed both PDFs in a browser and confirmed:
          - each is 8–18 pages, prose-heavy, fewer than 3 full-figure pages
          - arXiv IDs are noted (fill into PAPER2_ID, PAPER3_ID in Step 2)
        No command — operator visual verification only.

[ ] 3. Docker image rebuilt with Dockerfile.ris fix
        Command: docker compose --profile ris-gpu build ris-scheduler-gpu
        Evidence required: build exits 0, no "package directory does not exist" error.
        If build fails: diagnose before continuing.

[ ] 4. Fresh validation queue created with 3 verified papers
        Commands (fill in PAPER2_ID, PAPER3_ID from step 2 above):
          python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url 2604.24366
          python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url PAPER2_ID --title "Paper 2 title"
          python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue enqueue --url PAPER3_ID --title "Paper 3 title"
        Evidence required: each enqueue exits 0.

[ ] 5. Validation queue counts verified
        Command: python -m polytool research-marker-queue --queue-dir artifacts/research/marker_validation_queue counts --json
        Evidence required: {"pending": 3, "processing": 0, "done": 0, "failed": 0, "total": 3}
        If pending != 3 or failed != 0: stop and diagnose before issuing Docker run.
```

**Live validation is BLOCKED until all 5 items above are checked with evidence.**

---

## Rerun Prompt Readiness

**Rerun prompt CAN be issued after all 5 preflight items above are checked.**

**Rerun prompt text (copy-paste when ready):**

> Run the Marker IPC warm-worker live validation rerun.
> Prerequisites are complete: rate limit cleared, image rebuilt, validation queue has 3 pending
> verified simple papers in artifacts/research/marker_validation_queue.
> Issue the exact Docker command from `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md` (Step 3).
> Use `--queue-dir artifacts/research/marker_validation_queue --max-items 3 --marker-timeout 900 --json`.
> Stop immediately if Paper 1 returns arXiv API 429 or timeout — do not proceed to Paper 2.
> Fill in the pass/fail table and write a dev log with the outcome.
> Declare L1 unblocked only if all 6 gates pass.

---

## Artifact Paths

- Validation queue files: `artifacts/research/marker_validation_queue/queue.jsonl`, `results.jsonl`
  (fresh isolated queue — NOT the main queue at `artifacts/research/marker_parse_queue`)
- Validation logs: `artifacts/research/marker_ipc_validation/warm_process_rerun_YYYYMMDD_HHMM.log`
- Prior run logs (reference): `artifacts/research/marker_ipc_validation/warm_process_20260507*.log`
- This plan: `docs/dev_logs/2026-05-07_marker-ipc-live-validation-rerun-plan.md`

---

## L1 Production Status

**BLOCKED.** This doc is a planning-only artifact. L1 production remains blocked until the
live Docker/GPU validation passes all 6 gates above in a single `warm-process --max-items 3`
session.
