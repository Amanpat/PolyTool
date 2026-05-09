# Marker Docker IPC Warm-Worker v1 — Context Map

Date: 2026-05-07
Scope: Read-only context map. No code, tests, or state-doc changes.
Status: COMPLETE — dev log only

---

## Session Purpose

Queue v0 shipped 2026-05-05 (Codex re-review PASS). L1 Marker production rollout is
blocked on v1: a persistent IPC subprocess that keeps models warm across papers on
Linux/Docker. This session maps the existing architecture so an implementation prompt
can be written without rediscovery.

---

## Files Inspected

| File | Role |
|------|------|
| `packages/research/ingestion/extractors.py` | `MarkerPDFExtractor` — core Marker wrapper; `_preloaded_model_dict` warm-thread support |
| `packages/research/ingestion/fetchers.py` | `LiveAcademicFetcher` — subprocess path (`_marker_production_extract_subprocess`), thread path (`_marker_production_extract_thread`), `create_warm_thread_worker()` |
| `packages/research/ingestion/marker_queue.py` | `MarkerParseQueue` — file-backed queue, `process_next()`, `is_marker_ready()` |
| `packages/research/ingestion/pipeline.py` | `IngestPipeline.ingest_external()` — Marker-only academic gate |
| `tools/cli/research_marker_queue.py` | CLI: `enqueue`, `list`, `process`, `counts` |
| `tools/cli/research_scheduler.py` | `run-academic-url` one-paper controlled parse |
| `docker-compose.yml` | `ris-scheduler-gpu` service definition, GPU passthrough, volume mounts |
| `Dockerfile.ris` | RIS GPU image build; ~5-6 GB; model weights NOT baked in |
| `tests/test_ris_marker_queue.py` | 43 offline tests, 856 lines |
| `docs/dev_logs/2026-05-05_marker-canonical-parse-queue-v0-closeout.md` | v0 scope/deferred split |
| `docs/dev_logs/2026-05-05_marker-single-paper-control-surface-validation.md` | 85.95s cold-start evidence |
| `docs/dev_logs/2026-05-05_marker-production-rollout-reconciliation.md` | Failure analysis, Option A rationale |
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Canonical Academic Parse Queue.md` | State model, acceptance gates, architecture sketch |

---

## Current Architecture Summary

### Platform Detection

```python
# packages/research/ingestion/fetchers.py, line 49
_MARKER_DEFAULT_USE_PROCESS = _sys.platform != "win32"
```

- **Windows** (`_marker_use_process=False`): thread mode → warm batch via `create_warm_thread_worker()`
- **Linux/Docker** (`_marker_use_process=True`): subprocess mode → cold per paper (v1 target)

### Extractor: `MarkerPDFExtractor` (extractors.py)

```
__init__(_preloaded_model_dict=None)
  └── extract(pdf_path)
        ├── if _preloaded_model_dict: use it directly
        └── else: create_model_dict()   ← ~80s cold load on RTX 2070 Super
        PdfConverter(artifact_dict=model_dict)(pdf_path) → rendered
        text_from_rendered(rendered) → (markdown_text, out_meta)
```

The `_preloaded_model_dict` field is the warm-thread hook: Windows thread mode passes
the pre-loaded dict so `create_model_dict()` is never called again. Subprocess mode
cannot pass Python objects across process boundaries → model reloads on every spawn.

### Fetcher: `LiveAcademicFetcher` (fetchers.py)

```
fetch(url) → raw_source dict
  └── _fetch_pdf_body(arxiv_id)
        └── _parse_pdf(tmp_path)
              └── _marker_production_extract(tmp_path)
                    ├── [Linux] _marker_production_extract_subprocess(tmp_path)
                    └── [Windows] _marker_production_extract_thread(tmp_path)
```

**Linux/Docker subprocess path** (current, cold per paper):
```
ctx = multiprocessing.get_context("spawn")
result_queue = ctx.Queue()
proc = ctx.Process(target=_marker_process_worker, args=(tmp_path, result_queue), daemon=True)
proc.start()
proc.join(timeout=marker_timeout_seconds)
# → if alive: proc.terminate(); proc.kill(); _MARKER_DISABLED.set()
# → else: result_queue.get_nowait()
```

`_marker_process_worker` is a module-level function (spawn-safe):
```python
def _marker_process_worker(tmp_path_str, result_queue):
    extractor = MarkerPDFExtractor()   # ← create_model_dict() called here every time
    doc = extractor.extract(tmp_path_str)
    result_queue.put({"status": "ok", "body": ..., "meta": ..., "parse_seconds": ...})
```

**Windows thread path** (current, warm batch):
```
extractor = MarkerPDFExtractor(_preloaded_model_dict=self._preloaded_model_dict)
ThreadPoolExecutor(max_workers=1).submit(extractor.extract, tmp_path)
```

`create_warm_thread_worker()` raises `RuntimeError` on Linux/Docker:
```python
if _MARKER_DEFAULT_USE_PROCESS:
    raise RuntimeError("create_warm_thread_worker: subprocess mode (Linux/Docker) cannot ...")
```

### Parse Queue: `MarkerParseQueue` (marker_queue.py)

```
artifacts/research/marker_parse_queue/
  queue.jsonl    ← mutable queue state (read-write per operation)
  results.jsonl  ← append-only results log

process_next(max_items, marker_timeout, _fetcher=None)
  ├── [Windows, thread mode, max_items>1] create_warm_thread_worker() → warm fetcher
  ├── [Linux, subprocess mode] LiveAcademicFetcher() → cold fetcher (v1 must change this)
  └── for each pending item:
        → mark processing → _process_item(item, fetcher) → update status → append result
```

`is_marker_ready(body_source, body_length)`:
- `body_source == "marker"` AND `body_length >= 5000` → True
- pdfplumber / abstract_fallback / marker_failed → False regardless of length

Status flow: `pending → processing → done` / `pending` (retry, attempts < 3) / `failed` (terminal)

### Pipeline Gate: `IngestPipeline.ingest_external()` (pipeline.py)

For `source_family == "academic"`:
```python
_marker_ready = (_body_source == "marker" and _body_length >= 5000)
if not _marker_ready:
    return IngestResult(rejected=True, reject_reason="academic_marker_gate: ...")
```

Blocks pdfplumber / abstract_fallback / marker_failed from ChromaDB indexing.

### Docker Service: `ris-scheduler-gpu`

```yaml
ris-scheduler-gpu:
  build: Dockerfile.ris
  container_name: polytool-ris-scheduler-gpu
  environment:
    - RIS_PDF_PARSER=marker
  command: ["python", "-m", "polytool", "research-scheduler", "start"]
  deploy.resources.reservations.devices:
    - driver: nvidia, capabilities: [gpu]
  profiles: [ris-gpu]
  volumes:
    - ./kb:/app/kb
    - ./artifacts:/app/artifacts
    - ${USERPROFILE}/.cache/datalab:/home/polytool/.cache/datalab
```

Model weights: volume-mounted from Windows host `~/.cache/datalab` →
container `/home/polytool/.cache/datalab`. NOT baked into image.

---

## Entrypoints and Commands

| Command | File | Notes |
|---------|------|-------|
| `python -m polytool research-marker-queue enqueue --url <id>` | `tools/cli/research_marker_queue.py` | Adds to queue.jsonl |
| `python -m polytool research-marker-queue list [--status pending]` | same | Read-only |
| `python -m polytool research-marker-queue process --max-items N --marker-timeout 900` | same | Calls `MarkerParseQueue.process_next()` |
| `python -m polytool research-marker-queue counts` | same | Read-only |
| `python -m polytool research-scheduler run-academic-url --url <id> --json` | `tools/cli/research_scheduler.py` | One-paper controlled parse; no APScheduler |
| `docker compose --profile ris-gpu up -d ris-scheduler-gpu` | docker-compose.yml | Long-running GPU scheduler service |
| `docker compose --profile ris-gpu run --rm ris-scheduler-gpu python -m polytool ...` | docker-compose.yml | One-shot GPU run |

---

## Queue/Results Semantics

**queue.jsonl record:**
```json
{"candidate_id": "arxiv:2604.24366", "source_url": "...", "arxiv_id": "...",
 "title": "...", "status": "pending", "attempts": 0, "created_at": "...", "updated_at": "..."}
```

**results.jsonl record (appended on each attempt):**
```json
{"candidate_id": "...", "body_source": "marker", "body_length": 56923,
 "parse_seconds": 85.95, "failure_reason": null, "rejected": false, "exit_code": 0,
 "marker_ready": true, "queue_status": "done", "processed_at": "...", "attempt": 1}
```

**State machine:**
- `pending` → `processing` (worker picks up)
- `processing` → `done` (success, marker_ready=True)
- `processing` → `pending` (retryable failure, attempt < 3)
- `processing` → `failed` (terminal, attempt >= 3)

**Marker-only gate is enforced twice:**
1. `MarkerParseQueue._process_item()` — checks `body_source == "marker"` and sets `rejected=True` otherwise
2. `IngestPipeline.ingest_external()` — checks `body_source == "marker"` AND `body_length >= 5000` before ChromaDB

---

## Platform Behavior: Windows vs Linux/Docker

| Aspect | Windows (current, works) | Linux/Docker (current, broken) |
|--------|--------------------------|-------------------------------|
| Mode | Thread (`ThreadPoolExecutor`) | Subprocess (`multiprocessing.spawn`) |
| Model load | Once via `create_warm_thread_worker()` | **Every paper** (fresh subprocess) |
| Cold-start cost | Amortized across batch | ~80s per paper |
| Timeout cancel | Thread abandon (zombie possible) | `proc.terminate()` / `proc.kill()` (clean) |
| `_MARKER_DISABLED` | Set on timeout | Set on timeout |
| Warm behavior | Yes | **No — v1 required** |

The subprocess cancel is already correct (process-boundary kill, no zombie).
The problem is solely that each paper spawns a fresh subprocess and loses model state.

---

## Implementation Candidates for IPC Warm-Worker v1

### New file: `packages/research/ingestion/marker_ipc_worker.py`

Class `MarkerIPCWorker`:
- Owns a long-lived `multiprocessing.Process` (spawn context)
- Worker loop: `request_queue.get()` → extract → `result_queue.put()`
- `start()`: spawn worker, pre-signal ready
- `extract(tmp_path, timeout)`: send request, `result_queue.get(timeout=timeout)`
- `shutdown()`: send poison pill or `proc.terminate()`
- `is_alive()`: `self._proc.is_alive()`
- `restart()`: terminate + respawn (one more cold load)

Module-level worker entry point (spawn-safe):
```python
def _marker_ipc_worker_main(request_queue, result_queue):
    """Long-lived worker — loads models once, processes many papers."""
    from packages.research.ingestion.extractors import MarkerPDFExtractor
    extractor = MarkerPDFExtractor()
    mods = extractor._load_marker()
    model_dict = mods["create_model_dict"]()      # ← loaded ONCE
    warm_extractor = MarkerPDFExtractor(_preloaded_model_dict=model_dict)

    while True:
        req = request_queue.get()           # blocks
        if req is None:                     # poison pill
            break
        tmp_path = req["tmp_path"]
        t0 = time.monotonic()
        try:
            doc = warm_extractor.extract(tmp_path)
            parse_s = round(time.monotonic() - t0, 2)
            meta = {k: v for k, v in doc.metadata.items()
                    if isinstance(v, (str, int, float, bool, type(None)))}
            result_queue.put({"status": "ok", "body": doc.body or "",
                              "meta": meta, "parse_seconds": parse_s})
        except Exception as exc:
            result_queue.put({"status": "error", "error": str(exc)[:300],
                              "parse_seconds": round(time.monotonic() - t0, 2)})
```

Timeout strategy: parent uses `result_queue.get(timeout=marker_timeout)` — if it
raises `queue.Empty`, the worker is stuck. Parent calls `proc.terminate()` + `proc.kill()`
then restarts. New worker gets one cold load; subsequent papers are warm again.

### Modified: `packages/research/ingestion/fetchers.py`

Add injectable `_marker_ipc_worker` param to `LiveAcademicFetcher.__init__()`.
Modify `_marker_production_extract_subprocess()` to use the IPC worker when available:

```python
if self._marker_ipc_worker is not None:
    return self._marker_ipc_worker_extract(tmp_path)
# fallback: existing cold subprocess path
```

`_marker_ipc_worker_extract(tmp_path)`:
1. Send request to IPC worker
2. `result_queue.get(timeout=self._marker_timeout_seconds)`
3. On `queue.Empty`: restart worker, return `marker_failed`
4. On success: build result via `_build_marker_result(body, meta)`

### Modified: `packages/research/ingestion/marker_queue.py`

Modify `process_next()` Linux/Docker branch to create and reuse `MarkerIPCWorker`:

```python
# Linux/Docker subprocess mode with IPC warm worker
from packages.research.ingestion.marker_ipc_worker import MarkerIPCWorker
ipc_worker = MarkerIPCWorker()
ipc_worker.start()
try:
    fetcher = LiveAcademicFetcher(
        _marker_timeout_seconds=marker_timeout,
        _marker_ipc_worker=ipc_worker,
    )
    # ... existing loop ...
finally:
    ipc_worker.shutdown()
```

Accept `_ipc_worker_cls` injected param for offline tests.

### New CLI subcommand: `tools/cli/research_marker_queue.py`

Add `warm-process` subcommand (alternative to `process` — explicit warm-IPC path):
```
python -m polytool research-marker-queue warm-process --max-items 10 --marker-timeout 900
```
Prints per-paper `parse_seconds` so warm behavior can be confirmed without
manually reading results.jsonl.

### Alternative: `tools/cli/research_scheduler.py`

Add `run-marker-worker` subcommand (work packet suggested this):
```
python -m polytool research-scheduler run-marker-worker --max-items 10
```
Starts IPC worker inside the `ris-scheduler-gpu` container, drains queue, exits.

---

## Test Candidates

### Existing: `tests/test_ris_marker_queue.py` (43 tests)

Add test class `TestProcessNextIPCWorker`:
- `test_ipc_worker_warm_reuse`: inject `_ipc_worker_cls` mock; verify model_dict
  not reconstructed between papers 1 and 2 (mock records call count)
- `test_ipc_worker_timeout_restarts_worker`: worker stub that hangs on first call,
  times out, confirms worker restart, second paper succeeds
- `test_ipc_worker_crash_recovery`: worker stub that raises on first call (simulated
  OOM), confirms restart, second paper succeeds
- `test_process_next_linux_uses_ipc_worker`: mock `_MARKER_DEFAULT_USE_PROCESS=True`,
  confirm `MarkerIPCWorker` is created and `process_next()` routes through it

### New: `tests/test_ris_marker_ipc_worker.py`

- `test_worker_starts_and_shuts_down`: spawn real worker (no GPU), verify is_alive
- `test_worker_processes_request_offline`: inject mock extractor, send request, get result
- `test_worker_poison_pill_exits`: send None, verify worker exits cleanly
- `test_worker_timeout_detection`: inject slow worker stub, confirm `queue.Empty` raised
- `test_worker_restart_after_timeout`: timeout → restart → second request succeeds
- `test_worker_model_loaded_once`: mock `create_model_dict`, confirm call count = 1 across 3 papers

All tests fully offline — no GPU, no Docker, no real Marker. Inject mock extractor class.

---

## Risks and Open Questions

### 1. Process Lifecycle on Spawn Context

`multiprocessing.get_context("spawn")` requires `_marker_ipc_worker_main` to be
module-level and picklable (no closures, no lambdas). This is already the pattern
in the existing `_marker_process_worker`. Extend the same pattern.

**Risk**: If the new function is inside a class or a closure, spawn-pickling fails
with `AttributeError`. Keep it at module level in `marker_ipc_worker.py`.

### 2. Timeout Detection in IPC Worker

Parent: `result_queue.get(timeout=marker_timeout)` raises `queue.Empty` on timeout.
Worker: still stuck on GPU work (no internal cancellation).
Resolution: parent calls `proc.terminate()` then `proc.kill()`, restarts worker.

**Risk**: If GPU work is stuck at CUDA level, `SIGTERM` may not interrupt it immediately.
`proc.kill()` (SIGKILL) is the fallback. Docker containers handle both correctly.
Allow 5s between terminate and kill (same as existing pattern in `_marker_production_extract_subprocess`).

**Risk**: Restarted worker must clear the old `result_queue` — any leftover result from
a timed-out paper must be drained before sending the next request. Use a fresh
`ctx.Queue()` per worker start.

### 3. JSON IPC Protocol

The existing subprocess uses `multiprocessing.Queue` (backed by OS pipes + pickle).
Pickle-safe types only: `str`, `int`, `float`, `bool`, `None`, `list`, `dict`.
`_marker_process_worker` already filters non-primitive metadata. Use the same pattern.

**Risk**: Large `structured_metadata` from Marker (up to 20 MB cap) could slow IPC.
The 20 MB `_MARKER_METADATA_SIZE_LIMIT` truncation in `MarkerPDFExtractor` mitigates this.

### 4. Model Load Reuse Proof

Acceptance gate 3: papers 2+ show `parse_seconds <= 10s` on RTX 2070 Super.
This is observable only in a live Docker run, not in offline tests.

**For offline tests**: mock `create_model_dict` with a call counter. Verify count = 1
across 3 papers to prove no redundant loads.

**For live validation**: run `research-marker-queue warm-process --max-items 3` inside
`ris-scheduler-gpu` and capture `parse_seconds` for papers 1, 2, 3 from results.jsonl.
Paper 1 expected ~80-90s (cold); papers 2+ expected ≤10s (warm).

### 5. Windows Compatibility

IPC warm-worker is explicitly Linux/Docker only. Windows continues to use thread mode
(`create_warm_thread_worker()`). The `_MARKER_DEFAULT_USE_PROCESS` flag already gates this.

**Risk**: Tests that mock `_MARKER_DEFAULT_USE_PROCESS=True` to test the Linux path
must be careful to also restore the flag after the test. Use `unittest.mock.patch`.

### 6. Docker GPU/Cache Mounts

Model weights at `${USERPROFILE}/.cache/datalab:/home/polytool/.cache/datalab`.
The IPC worker process inherits the Docker container filesystem, including the mount.
No additional mount changes needed.

**Risk**: If worker subprocess is spawned before the volume is ready, model load fails.
The worker is started on first paper (lazy), not at container start — volume will be mounted.

### 7. `_MARKER_DISABLED` Flag Interaction

`_MARKER_DISABLED` is a process-level `threading.Event`. In the IPC worker design,
the parent process sets `_MARKER_DISABLED` on timeout — but the IPC worker is a
separate process and does NOT inherit this flag's state.

**Design decision**: `_MARKER_DISABLED` should NOT be set on IPC worker timeout.
Instead, the parent restarts the IPC worker and retries the paper (up to retry limit).
Only after `MAX_ATTEMPTS` failures should the paper be marked `failed` in the queue.

**Risk**: If `_MARKER_DISABLED` is set in the parent after IPC worker timeout, it
prevents subsequent papers from being processed in the same session. Confirm that
`_marker_production_extract_subprocess` doesn't set `_MARKER_DISABLED` when using
the IPC worker path (separate code path handles this).

### 8. Queue File Concurrency

`queue.jsonl` is read/written by a single parent process during `process_next()`.
The IPC worker process never touches queue files. No multi-process file contention.
Current file-backed queue is safe for the v1 design.

### 9. `research-acquire` and Scheduler Integration

The work packet specifies a future `--parse-mode queue` flag on `research-acquire`
for enqueueing without inline parse. This is NOT part of v1 scope — v1 is only
the IPC warm-worker for `research-marker-queue process`.

---

## Recommended Implementation Split for Two Claude Terminals

### Terminal A — IPC Warm-Worker Core (new file + fetcher + queue)

**Files:**
1. `packages/research/ingestion/marker_ipc_worker.py` (new)
   - Module-level `_marker_ipc_worker_main(request_queue, result_queue)` — warm loop
   - `MarkerIPCWorker` class: `start()`, `extract(tmp_path, timeout)`, `is_alive()`,
     `restart()`, `shutdown()`
2. `packages/research/ingestion/fetchers.py` (modify)
   - Add `_marker_ipc_worker: Optional[MarkerIPCWorker] = None` to `LiveAcademicFetcher.__init__()`
   - Add `_marker_ipc_worker_extract(tmp_path)` method
   - Modify `_marker_production_extract_subprocess()`: delegate to `_marker_ipc_worker_extract`
     when `self._marker_ipc_worker is not None`
3. `packages/research/ingestion/marker_queue.py` (modify)
   - Modify `process_next()` Linux branch: create `MarkerIPCWorker`, pass to fetcher,
     wrap in try/finally for shutdown
   - Accept `_ipc_worker_cls` injected param for offline tests (defaults to `MarkerIPCWorker`)

**Test:**
4. `tests/test_ris_marker_ipc_worker.py` (new) — pure offline IPC worker tests

### Terminal B — CLI + Queue Integration Tests (no new modules)

**Files:**
1. `tools/cli/research_marker_queue.py` (modify)
   - Add `warm-process` subcommand: starts IPC worker, processes batch, prints per-paper timing
2. `tests/test_ris_marker_queue.py` (modify)
   - Add `TestProcessNextIPCWorker` test class: IPC worker injection, timeout restart,
     warm-reuse proof via mock call counter

**Dependency**: Terminal B needs Terminal A's `MarkerIPCWorker` class signature to be stable
before writing the queue integration tests. Run Terminal A first, or coordinate the interface
contract explicitly before both start.

---

## Codex Review

Tier: Skip — docs-only session. No code, tests, or state docs changed.
