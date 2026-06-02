---
title: Ris Marker Single Paper Validation Control Surface
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-05_ris-marker-single-paper-validation-control-surface.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS Marker Single-Paper Validation Control Surface

Date: 2026-05-05
Scope: Add `run-academic-url` CLI subcommand + process-boundary Marker cancel for single-paper controlled validation.
Status: COMPLETE

---

## What Was Built

### `research-scheduler run-academic-url` (new subcommand)

```powershell
# Success path
python -m polytool research-scheduler run-academic-url \
  --url https://arxiv.org/abs/2604.24366 \
  --marker-timeout 900 \
  --json

# Also accepts bare arXiv IDs
python -m polytool research-scheduler run-academic-url \
  --url 2604.24366 \
  --marker-timeout 900 \
  --json
```

**Output fields (JSON)**:

| Field | Type | Description |
|-------|------|-------------|
| `url` | str | Full arXiv URL |
| `arxiv_id` | str | Bare arXiv ID (e.g. `2604.24366`) |
| `title` | str | Paper title from arXiv API |
| `body_source` | str | `"marker"`, `"marker_failed"`, or `"error"` |
| `body_length` | int | Characters in extracted body (0 on failure) |
| `page_count` | int | Page count from Marker (0 if not extracted) |
| `parse_seconds` | float | Marker extraction time in seconds |
| `failure_reason` | str\|null | Failure details (null on success) |
| `rejected` | bool | True if body_source != marker |
| `marker_timeout` | float | Timeout passed to fetcher |
| `total_seconds` | float | Wall-clock time for full fetch + parse |
| `exit_code` | int | 0 on success, 1 on failure |

**Behavior**:
- Does NOT start APScheduler
- Does NOT register any scheduled jobs
- Uses the same `LiveAcademicFetcher` as production (identical code path)
- `--marker-timeout` controls Marker's extraction timeout directly
- `--no-eval` accepted (no-op, for compatibility)
- Bare arXiv IDs (e.g. `2604.24366`) are expanded to full URLs automatically

### Process-Boundary Marker Cancel (Linux/Docker)

`_marker_production_extract_subprocess` in `packages/research/ingestion/fetchers.py`:

- Uses `multiprocessing.get_context("spawn")` to spawn a fresh process
- Passes the PDF path and a `multiprocessing.Queue` to the worker
- On timeout: calls `proc.terminate()` → `proc.join(5.0)` → `proc.kill()` → sets `_MARKER_DISABLED`
- On success: reads result from queue, includes `parse_seconds`
- On worker crash (empty queue after exit): returns `marker_failed` with reason

The worker function `_marker_process_worker` is module-level (required for `spawn` pickling).
Returns `{"status": "ok"|"error", "body": ..., "meta": {...}, "parse_seconds": ...}`.

**Platform dispatch**:
```python
_MARKER_DEFAULT_USE_PROCESS = sys.platform != "win32"
```
- Linux/Docker (production): subprocess path (process-boundary kill)
- Windows/dev machine: thread path (existing behavior; `_MARKER_DEFAULT_USE_PROCESS=False`)

This means all existing tests in `test_ris_academic_pdf.py` continue to run on Windows using the thread path unchanged. No test file modifications required.

### `parse_seconds` propagated through result

Added to both subprocess and thread paths. Flows through `_build_marker_result` into the `raw_source` dict. Visible in `run-academic-url` JSON output. Existing tests unaffected (they don't assert `parse_seconds` is absent).

---

## Acceptance Gate Status

| Gate | Status | Evidence |
|------|--------|----------|
| Single-paper controlled run | **READY** | `run-academic-url` subcommand added; runs against live arXiv when Docker is up |
| Timeout kills worker process | **READY on Linux** | `proc.terminate()` → `proc.kill()` in `_marker_production_extract_subprocess`; verify with `nvidia-smi` in Docker |
| No zombie after kill | **READY on Linux** | Process-boundary kill via `SIGTERM`/`SIGKILL` frees GPU VRAM; verify with `docker stats` |
| Per-paper parse metadata present | **READY** | `body_source`, `body_length`, `parse_seconds`, `page_count` all in JSON output |
| Failure case surfaced | **READY** | `marker_failed` → `rejected=true`, `failure_reason` with `marker_timeout:` prefix |
| No scheduler loop | **READY** | `run-academic-url` does not call `start_research_scheduler` (test `test_run_academic_url_no_scheduler_started` verifies) |
| Existing tests pass | **PASS** | 2403 passed, 1 pre-existing failure (`test_ris_claim_extraction` actor mismatch) |

**Gates requiring Docker/GPU validation (manual, in container):**
- Timeout kills worker process (run `nvidia-smi` during a timeout)
- No zombie after kill (run second paper after first times out)

---

## Test Coverage

New `TestRunAcademicUrl` class in `tests/test_ris_scheduler.py` (5 tests):

| Test | What it verifies |
|------|-----------------|
| `test_run_academic_url_success_json_fields` | body_source=marker, body_length, parse_seconds, exit_code=0 in JSON |
| `test_run_academic_url_marker_failed_json` | marker_failed → rejected=True, exit_code=1, failure_reason present |
| `test_run_academic_url_bare_id_normalised` | `2604.24366` expanded to `https://arxiv.org/abs/2604.24366` |
| `test_run_academic_url_no_scheduler_started` | `start_research_scheduler` is never called |
| `test_run_academic_url_fetch_exception_returns_1` | FetchError → exit_code=1, body_source="error" |

Targeted: **43 passed** (all scheduler tests). Full suite: **2403 passed**, 1 pre-existing failure.

---

## Operator Usage Guide

### Validate a single paper through Marker (Docker):

```powershell
# Start ClickHouse only (required by docker-compose healthcheck)
docker compose --profile ris-gpu up -d clickhouse

# Run single-paper validation
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-scheduler run-academic-url `
    --url 2604.24366 `
    --marker-timeout 900 `
    --json
```

Expected success output:
```json
{
  "body_source": "marker",
  "body_length": 45000,
  "parse_seconds": 12.4,
  "page_count": 15,
  "rejected": false,
  "exit_code": 0
}
```

### Test timeout kill:

```powershell
docker compose --profile ris-gpu run --rm --no-deps ris-scheduler-gpu `
  python -m polytool research-scheduler run-academic-url `
    --url 2604.21675 `
    --marker-timeout 60 `
    --json
```

In a second terminal during the run: `docker exec polytool-ris-scheduler-gpu nvidia-smi`
After timeout: `docker exec polytool-ris-scheduler-gpu nvidia-smi` (GPU memory should be freed)

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/fetchers.py` | `_marker_process_worker`, `_MARKER_DEFAULT_USE_PROCESS`, `_marker_use_process` param, `_marker_production_extract_subprocess`, dispatcher refactor, `parse_seconds` in results |
| `tools/cli/research_scheduler.py` | `run-academic-url` subcommand, `_cmd_run_academic_url` handler |
| `tests/test_ris_scheduler.py` | `TestRunAcademicUrl` (5 tests) |

No changes to: `test_ris_academic_pdf.py`, Docker, scheduler jobs, chunker, embedder, trading code.

---

## L1 Production Rollout Status

This packet provides the missing control surface. It does NOT ship Marker production.
L1 production rollout (`Work-Packet - Marker Structural Parser Integration`) can resume
once the Docker acceptance gates above are validated manually.

## Codex Review

Tier: Recommended — strategy files, scheduler, new CLI surface.
Run: `/codex:review --background`
