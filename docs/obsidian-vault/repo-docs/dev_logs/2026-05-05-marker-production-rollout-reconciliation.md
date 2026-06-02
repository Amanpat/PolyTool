---
title: Marker Production Rollout Reconciliation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# L1 Marker Production Rollout — Reconciliation

Date: 2026-05-05
Scope: Reconcile L1 Marker production rollout after validation failure. Update docs to reflect blocked state; create next safe work packet.
Status: COMPLETE (docs-only — no code changes)

---

## What Failed

### One-shot benchmark timeouts (systematic)

Two papers were submitted to `research-parser-benchmark` inside the GPU
container (`ris-scheduler-gpu`) after the Docker site-packages/static
permission fix confirmed the pipeline stages execute correctly:

| Paper | Pages | Timeout set | Result | Root cause |
|-------|-------|-------------|--------|------------|
| `2604.21675` (ML with equations) | 6 | 1200s | `marker_failed` — timed out at 1200.5s | Box 114 alone consumed 273s (dense math); 6/121 boxes unfinished |
| `2510.15205` (math-heavy ML) | 25 | 1800s | `marker_failed` — timed out at 1800.2s | Last ~2% of boxes not completed |

**Pattern confirmed across both papers:**

1. Layout recognition and early/middle text recognition run at expected speed
   (2-13s/box for prose content).
2. The final 5-15% of boxes in ML/quant papers are math-dense and spike to
   100-300s per box individually, consuming most of the remaining budget.
3. Cold model load (~136-270s) consumes 11-23% of any per-paper timeout budget
   before a single character of text is processed.
4. Page count is not predictive of processing time. A 6-page paper produced
   121 text recognition boxes and timed out.
5. Zombie containers after timeout degrade subsequent runs (GPU contention
   caused 16× slower layout recognition in prior runs).

**Conclusion:** The one-shot `docker compose run --rm` benchmark path is not a
reliable validation path for Marker when papers contain significant math
content. This is a structural limitation of the one-shot approach, not a
Marker bug. Marker itself executes correctly — layout, OCR, bbox, and text
recognition all run.

---

## Why Scheduler Validation Is Not Safe As-Is

From the read-only scheduler safety audit
(`2026-05-05_context-ris-gpu-scheduler-marker-validation.md`):

### No single-paper submit path
`research-scheduler run-job` accepts only `job_id`. Running
`run-job academic_ingest` invokes two hardcoded topic searches and can process
up to 10 papers — it cannot accept `--url` or `--arxiv-id`. There is no way
to target one known paper through the scheduler path today.

### Thread-based cancel is not a hard cancel
`LiveAcademicFetcher` runs Marker in a `ThreadPoolExecutor(max_workers=1)` and
calls `pool.shutdown(wait=False)` on `concurrent.futures.TimeoutError`. On
Windows, threads cannot be killed with `SIGKILL` — the Marker worker continues
running in the background until it completes (or the process exits). Code
comment in `extractors.py` explicitly acknowledges this:
> "True cancellation requires a process boundary (`multiprocessing`) — explicitly deferred."

After the first timeout, `_MARKER_DISABLED` is set and Marker is disabled for
the entire scheduler process lifetime until restart.

### Scheduler metadata is too coarse
`run_job --json` exposes only `job_id` and `exit_code`. There is no
`body_source`, `body_length`, `parse_seconds`, or `failure_reason` visible
in the scheduler output. Validating "did Marker succeed on this paper?"
requires manually inspecting raw source cache files.

### Scheduler registers all 8 RIS jobs
The GPU scheduler service registers all 8 jobs (academic, reddit ×2, blog,
YouTube, GitHub, freshness, weekly digest). Running it for validation also
schedules unrelated RIS ingestion. An academic-only mode does not exist.

### Scheduler success is overreported
`_job_run_academic_ingestion()` ignores return codes from
`research_acquire.main()`. `run_job()` can write `exit_status="ok"` even when
inner acquisition returned nonzero without raising.

---

## Status Changes Made

| Document | Change |
|----------|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Structural Parser Integration.md` | `status: ready` → `status: blocked`; added DANGER callout with full failure evidence; updated Open Questions (hosting resolved; new Q6 for math-heavy timeout); added new packet as prerequisite |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | L1 entry updated to BLOCKED; RIS table updated; new blocker row added; 2026-05-05 session context entry added; last-updated bumped |
| `docs/CURRENT_DEVELOPMENT.md` | Feature 3 (RIS L1 Marker) removed from Active; added to Paused/Deferred with resume trigger; architect note added: Feature 3 slot now free, do not resume L1 until control surface ships |
| `docs/features/ris-marker-structural-parser-scaffold.md` | Status updated to "CODE COMPLETE — VALIDATION BLOCKED"; blocked callout added at top; 5-10s/paper performance claim qualified (not yet validated); new dev logs added to Dev Log Trail |
| `docs/INDEX.md` | Feature doc entry updated to show blocked status; three new dev log rows added |

---

## New Packet Created

**`docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Single-Paper Validation Control Surface.md`**

Goal: validate one known arXiv ID through a controlled path before any
production rollout resumes.

Key deliverables:
1. `research-scheduler run-academic-url --url <id>` — scheduler-owned one-paper
   trigger using the same production code path (`LiveAcademicFetcher` +
   `IngestPipeline`), no APScheduler loop started
2. Process-boundary Marker timeout/cancel (`multiprocessing` subprocess, not
   `ThreadPoolExecutor`) — worker process killed on timeout, no zombie GPU
3. Per-paper structured JSON output: `body_source`, `body_length`,
   `parse_seconds`, `page_count`, `failure_reason`, `rejected`
4. Academic-only scheduler mode / guard (no unrelated jobs registered during
   validation)

Acceptance gates:
- One-paper controlled run completes without hanging or zombie containers
- Timeout kills the worker process (verify with `nvidia-smi` / `docker stats`)
- No zombie after kill — second paper succeeds in same warm container
- Per-paper parse metadata present in JSON output
- Failure case surfaced with `marker_failed` and `failure_reason`
- No scheduler loop started
- Existing test suite still passes (currently 2403 + 1 pre-existing failure)

---

## Next Recommended Work

**Option A (recommended if L1 is priority):**
Implement [[Work-Packet - Marker Single-Paper Validation Control Surface]].
This is the prerequisite that unblocks L1 production rollout. Estimated scope:
`research_scheduler.py` + `scheduler.py` + `extractors.py` multiprocessing
change + new tests.

**Option B (parallel path, always safe):**
Resume L3 label accumulation. Run `research-acquire` with
`--prefetch-filter-mode hold-review` in live sessions and use
`research-prefetch-review label` to accumulate toward ≥30 allow + ≥30 reject
labels for the SVM trigger. L3 label accumulation does not depend on L1.

**Do NOT start L2.** L2 is gated on L1 production validation. Until L1 ships,
L2 has no validated corpus to build on.

---

## What Was NOT Changed

Per the scope constraints:
- No parser runtime code changed
- No Docker configuration changed
- No scheduler implementation changed
- No L2/PaperQA2 work touched
- No L3/SVM/label store changed
- No L4 harvester work touched
- No trading or n8n code touched

---

## Codex Review

Tier: Skip — docs-only session. No code review requested and no code changes made.
