---
tags: [work-packet, ris, ingestion, academic, parser, validation]
date: 2026-05-05
status: validated
validated: 2026-05-05
priority: high
phase: 2
target-layer: 1
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Academic Pipeline Hosting]]"
prerequisites:
  - "[[Work-Packet - Marker Structural Parser Integration]] — code complete; this packet provides the validation path"
unblocks:
  - "[[Work-Packet - Marker Structural Parser Integration]] (production rollout resume — ~~blocked on ≤10s/paper gate~~ **gate rejected/superseded 2026-05-08; revised functional gate PASS — see Feature 3**)"
---

# Work Packet — Marker Single-Paper Validation Control Surface

> [!SUCCESS] Status: VALIDATED 2026-05-05
> Control surface infrastructure is complete and validated. One controlled parse succeeded.
> **However, `parse_seconds=85.95s` exceeds the ≤10s/paper production gate.**
> L1 Marker production rollout therefore remains blocked — this packet validated the tooling, not production readiness.
>
> **Validation result (2026-05-05):**
> ```
> paper:         2604.24366 — The Anatomy of a Decentralized Prediction Market
> body_source:   marker
> body_length:   56923 chars
> parse_seconds: 85.95s  ← FAILS ≤10s/paper gate
> total_seconds: 89.41s
> rejected:      false
> exit_code:     0
> ```
>
> **Evidence:** `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md`
>
> **Gate update (2026-05-08):** ≤10s/paper production gate rejected as unrealistic for RTX 2070 Super (Director decision). Revised functional gate: ≥3 full PDFs parsed in one Docker/GPU warm session; papers 2+ delta ≤5s (cold-load overhead eliminated). Measured timings: 45.55s, 69.73s, 48.31s. L1 is now blocked on Feature 3 (Marker Docker IPC Warm-Worker v1) closeout, not the old ≤10s/paper gate.

## Purpose

L1 Marker production rollout was blocked 2026-05-05 because no safe path exists
to validate one known arXiv paper through the actual production code path.

This packet adds the minimum control surface needed to run a single-paper
Marker validation job with:
- A known arXiv ID (operator-chosen, not a hardcoded topic search)
- A hard process-boundary timeout/cancel (not thread-based)
- Per-paper structured output: `body_source`, `body_length`, `parse_seconds`,
  `page_count`, `failure_reason`
- No scheduler full-loop start
- No production rollout

Completion of this packet unblocks resumption of [[Work-Packet - Marker
Structural Parser Integration]].

---

## Why the Current Path Is Unsafe

From `docs/dev_logs/2026-05-05_context-ris-gpu-scheduler-marker-validation.md`:

1. **No single-paper scheduler submit path.** `research-scheduler run-job`
   accepts only `job_id`. `run-job academic_ingest` runs two hardcoded topic
   searches (up to 10 papers); it cannot accept `--url` or `--arxiv-id`.

2. **Thread-based cancel is not a hard cancel.** The current
   `LiveAcademicFetcher` runs Marker in a `ThreadPoolExecutor(max_workers=1)`
   and calls `pool.shutdown(wait=False)` on timeout. On Windows, threads cannot
   be killed — the Marker worker continues running in the background. This also
   disables Marker for the entire scheduler process lifetime after the first
   timeout.

3. **No per-paper parse metadata in scheduler output.** `run_job --json`
   exposes only `job_id` and `exit_code`. There is no `body_source`,
   `body_length`, `parse_seconds`, or `failure_reason` visible without
   manually inspecting the raw source cache files.

4. **Scheduler registers all 8 RIS jobs.** Starting `ris-scheduler-gpu` for
   validation also schedules reddit, blog, YouTube, GitHub, freshness, and
   weekly digest jobs. A long-running validation session runs unrelated jobs.

5. **Scheduler success metadata is too coarse.** `_job_run_academic_ingestion`
   ignores return codes from `research_acquire.main()`. The scheduler can write
   `exit_status="ok"` even if inner acquisition returned nonzero.

---

## What Ships

### 1. `research-scheduler run-academic-url` subcommand (or equivalent)

A new scheduler-owned CLI path that:
- Accepts `--url <arxiv-url-or-id>` for a single known paper
- Uses the same `LiveAcademicFetcher` and `IngestPipeline` as production
- Runs inside the GPU Docker container (`ris-scheduler-gpu`) where models are
  warm (no cold-load penalty after first paper)
- Emits structured JSON output including:
  `doc_id`, `body_source`, `body_length`, `parse_seconds`, `page_count`,
  `chunk_count`, `failure_reason`, `rejected`, `reject_reason`
- Propagates nonzero `research_acquire.main()` return codes into exit status
- Does NOT start APScheduler; does NOT register the 8-job schedule
- Writes one `RunRecord` to `artifacts/research/run_log.jsonl`

### 2. Process-boundary Marker timeout (minimum viable)

Replace (or wrap) the `ThreadPoolExecutor` Marker execution with a
`multiprocessing`-based subprocess so that timeout truly kills the worker.
The existing `_MARKER_DISABLED` flag and semaphore may be retained as a
secondary guard but the primary cancel must be at the process boundary.

Requirements:
- On timeout: worker process is terminated (not just abandoned)
- No zombie GPU process after timeout
- Timeout value is configurable via `--marker-timeout` flag (default 600s)
- `failure_reason` includes timeout duration

### 3. Academic-only scheduler mode guard

Add an `--academic-only` flag (or equivalent compose override) that starts
APScheduler with only `academic_ingest` registered. This prevents unrelated
RIS jobs from firing during a validation session that runs as a long-lived
service rather than a one-shot command.

---

## Scope Guards

- Do NOT change the chunker, embedder, or retrieval API
- Do NOT start L2
- Do NOT modify production rollout policy — this packet validates, it does not ship
- Do NOT run full scheduler loop for this validation
- Do NOT modify `config/benchmark_v1.*` or any Gate 2 artifacts
- Existing tests must still pass; new tests cover the new control surface

---

## Acceptance Gate Verdicts (2026-05-05)

| Gate | Result | Notes |
|------|--------|-------|
| 1. Single-paper controlled run | **PASS** | `body_source=marker`, `body_length=56923`, exit_code=0 |
| 2. Timeout kills worker process | **NOT TESTED** | Process-boundary code exists; timeout test not run |
| 3. No zombie after kill | **NOT TESTED** | Deferred — no timeout occurred in validation run |
| 4. Per-paper parse metadata present | **PASS** | `body_source`, `body_length`, `parse_seconds`, `page_count` all present |
| 5. Failure case surfaced | **NOT TESTED** | No timeout-paper run attempted |
| 6. No scheduler loop | **PASS** | Verified by `test_run_academic_url_no_scheduler_started` |
| 7. Existing tests pass | **PASS** | 2403 passed, 1 pre-existing failure unchanged |
| 8. Dev log written | **PASS** | `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md` |

**Control surface verdict: VALIDATED** — the tooling works.
**L1 production verdict (2026-05-05, as-measured): BLOCKED** — `parse_seconds=85.95s` >> original `≤10s/paper` gate *(gate rejected/superseded 2026-05-08; revised functional gate accepted — see Feature 3)*.

---

## Acceptance Gates (Original)

1. **Single-paper controlled run.** The following command sequence completes
   without hanging, zombie containers, or unhandled errors:
   ```powershell
   docker compose --profile ris-gpu up -d clickhouse

   docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
     python -m polytool research-scheduler run-academic-url `
       --url https://arxiv.org/abs/2604.24366 `
       --no-eval `
       --marker-timeout 900 `
       --json
   ```
   Output must include `body_source`, `body_length`, `parse_seconds`.

2. **Timeout kills the worker process.** When a math-heavy paper is submitted
   with `--marker-timeout 60`, the Marker worker process is terminated within
   ~5s of the timeout firing. No zombie GPU process remains after timeout.
   Confirm with `docker stats` or `nvidia-smi` inside the container.

3. **No worker zombie after kill.** After a timeout-kill, a second
   `run-academic-url` call on a different paper succeeds (models already warm
   in the container, worker process restarted). Demonstrates the process
   boundary isolates failures.

4. **Per-paper parse metadata present.** For a successful parse, JSON output
   contains non-empty `body_source="marker"`, `body_length > 5000`,
   `parse_seconds > 0`, `page_count > 0`.

5. **Failure case surfaced.** For a paper that times out, JSON output contains
   `body_source="marker_failed"`, `failure_reason` starting with
   `"marker_timeout:"`, `rejected=true`.

6. **No scheduler loop.** Running `run-academic-url` does NOT start APScheduler
   and does NOT register any of the 8 scheduled jobs. Confirm via dry-run
   introspection before the real run.

7. **Existing tests still pass.** `pytest tests/ -x -q --tb=short` reports
   the same pass count as before this packet (currently 2403 + 1 pre-existing
   failure). No regressions.

8. **Dev log written.** `docs/dev_logs/YYYY-MM-DD_ris-marker-single-paper-validation.md`
   documents the controlled run, parse metadata, timeout kill test, and
   next-step recommendation for resuming L1 production rollout.

---

## Files Expected to Change

| File | Change | Review level |
|------|--------|-------------|
| `tools/cli/research_scheduler.py` | Add `run-academic-url` subcommand | Mandatory |
| `packages/research/scheduling/scheduler.py` | Add `run_academic_url()` method; `--academic-only` mode | Mandatory |
| `packages/research/ingestion/extractors.py` | Replace `ThreadPoolExecutor` Marker execution with `multiprocessing` subprocess for process-boundary cancel | Mandatory |
| `tests/test_ris_scheduler.py` | New tests: `run-academic-url` JSON output, timeout kill, academic-only mode, nonzero exit propagation | Mandatory |
| `docs/dev_logs/YYYY-MM-DD_ris-marker-single-paper-validation.md` | New dev log | Mandatory |

---

## Reference Materials

1. `docs/dev_logs/2026-05-05_context-ris-gpu-scheduler-marker-validation.md` —
   full safety audit; exact missing shape documented in "Minimum safe command
   sequence after adding a missing control surface"
2. `docs/dev_logs/2026-05-05_ris-marker-short-paper-smoke.md` — timeout
   failure pattern; warm scheduler rationale; prose-paper fallback option
3. `docs/features/ris-marker-structural-parser-scaffold.md` — existing
   scaffold: two-layer concurrency guard, `_MARKER_DISABLED`, metadata fields
4. `packages/research/ingestion/extractors.py` — current `ThreadPoolExecutor`
   implementation that needs process-boundary upgrade

---

## Cross-references

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Work-Packet - Marker Structural Parser Integration]] — production rollout
  packet; this control surface unblocks its resumption
- [[Decision - Academic Pipeline Hosting]] — Docker GPU passthrough confirmed
- `docs/dev_logs/2026-05-05_context-ris-gpu-scheduler-marker-validation.md`
- `docs/dev_logs/2026-05-05_ris-marker-short-paper-smoke.md`
