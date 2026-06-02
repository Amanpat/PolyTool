---
title: Codex Verify Marker Docker Ipc Worker Implementation
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-worker-implementation.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Verify Marker Docker IPC Worker Implementation

Date: 2026-05-07
Type: review / verification
Scope: review-only; no code changes
Verdict: FAIL

## Objective

Verify whether the mocked Marker Docker/Linux IPC warm-worker v1 implementation
and CLI harness are correct enough to run the next Docker/live warm-worker
validation.

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`
- `docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md`
- `docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md`
- `packages/research/ingestion/marker_ipc_worker.py`
- `packages/research/ingestion/fetchers.py`
- `packages/research/ingestion/marker_queue.py`
- `tools/cli/research_marker_queue.py`
- `tests/test_ris_marker_ipc_worker.py`
- `tests/test_ris_marker_queue.py`

## Review Findings

Blocking:

1. The standalone IPC worker core exists and is covered by offline tests, but it
   is not wired into the queue/fetcher/CLI path in the checked-out files.
   `packages/research/ingestion/marker_queue.py` still says Linux/Docker spawns
   a fresh Marker process per paper and that warm IPC is deferred to v1.

2. `tools/cli/research_marker_queue.py` does not expose an explicit warm-worker
   path. The actual help output only lists `enqueue`, `list`, `process`, and
   `counts`. There is no `warm-process` subcommand or equivalent Docker
   validation harness.

3. `packages/research/ingestion/fetchers.py` has no `_marker_ipc_worker`
   constructor parameter or IPC delegation path. Its Linux/Docker subprocess
   timeout path still sets global `_MARKER_DISABLED`, so the production queue
   path remains the pre-v1 cold subprocess behavior.

4. The integration dev log claims queue/CLI integration and `warm-process`
   tests were added, but the checked-out source and tests do not contain those
   symbols (`warm-process`, `_ipc_worker_cls`, `TestProcessNextIPCWorker`,
   `TestCLIWarmProcess`). This is a repo-state/content mismatch that blocks
   live validation.

Non-blocking / passed checks:

- `packages/research/ingestion/marker_ipc_worker.py` has a module-level
  `_marker_ipc_worker_main` entry point and uses spawn context by default.
- IPC worker tests prove `create_model_dict()` is called once across multiple
  mocked parse requests in one worker session.
- The standalone IPC worker returns structured error dicts on startup failure,
  per-paper errors, and timeout; it does not set `_MARKER_DISABLED` itself.
- No new pdfplumber production fallback was found in the IPC worker.
- Queue v0 semantics remain intact because `marker_queue.py` is unchanged:
  pending/processing/done/failed, retry attempts, `results.jsonl`, and
  `is_marker_ready()` behavior are still covered by tests.
- Windows thread mode remains unchanged.
- L2/PaperQA2 and L4 remain blocked/stubbed in the reviewed state.
- SVM labels/models and trading/execution files were not touched by the
  current git status.
- Live Docker validation is still pending; no live Marker jobs were run.

## Checklist

1. Worker entrypoint is module-level and spawn-safe: PASS for standalone core.
2. Marker models loaded once per worker session in tests: PASS.
3. Multiple parse requests can reuse one IPC worker: PASS for standalone core.
4. Timeout/error handling explicit and does not set global `_MARKER_DISABLED`:
   PARTIAL. Standalone IPC core passes; current production Linux/Docker path is
   not wired to IPC and still sets `_MARKER_DISABLED` on subprocess timeout.
5. No pdfplumber production fallback was added: PASS.
6. Queue v0 state/result semantics remain intact: PASS.
7. CLI exposes an explicit warm-worker path and does not imply L1 is unblocked:
   FAIL. No explicit warm-worker command is exposed.
8. Windows thread mode remains unchanged: PASS.
9. Linux/Docker IPC path is gated/explicit: FAIL. It exists only as an
   untracked standalone module/test path, not as queue/CLI harness wiring.
10. L2/PaperQA2 and L4 remain blocked/stubbed: PASS.
11. SVM labels/models and trading files are untouched: PASS.
12. Live validation is still pending: PASS.

## Commands Run

### `git status --short`

Exit code: 0

```text
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-clean.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation-fixed.md
?? docs/dev_logs/2026-05-07_codex-verify-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_fix-marker-historical-l1-unblocked-claims.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-activation.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-warm-worker-v1-context-map.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-core.md
?? docs/dev_logs/2026-05-07_marker-docker-ipc-worker-queue-cli-integration.md
?? "docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md"
?? packages/research/ingestion/marker_ipc_worker.py
?? tests/test_ris_marker_ipc_worker.py
```

After creating this review log, this file is additionally untracked.

### `git log --oneline -5`

Exit code: 0

```text
4b57400 SVM scoring complete
e482a6d L3 handoff
be8b4f2 fix(ris): resolve Codex FAIL blockers - Marker queue v0
7b81a7a Marker Parser added
a4fdcac docs(ris): close out Marker control surface validation - L1 still blocked
```

### `python -m polytool --help`

Exit code: 0

Key result: CLI loaded successfully and listed `research-marker-queue` as an
available RIS command.

### `python -m pytest tests/test_ris_marker_ipc_worker.py tests/test_ris_marker_queue.py -q`

Exit code: 0

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 103 items

tests\test_ris_marker_ipc_worker.py .................................    [ 32%]
tests\test_ris_marker_queue.py ......................................... [ 71%]
...................s.........                                            [100%]

======================= 102 passed, 1 skipped in 2.01s ========================
```

### `python -m polytool research-marker-queue --help`

Exit code: 0

```text
usage: polytool research-marker-queue [-h] [--queue-dir PATH]
                                      {enqueue,list,process,counts} ...

Marker Canonical Academic Parse Queue v0. Enqueue arXiv papers, process them
with Marker, and track which papers are RAG-ready (marker_ready=true). On
Windows, Marker models are pre-loaded once per batch (warm). On Linux/Docker,
models reload per paper (subprocess mode; warm IPC worker is v1).

positional arguments:
  {enqueue,list,process,counts}
    enqueue             Add one arXiv paper to the parse queue
    list                Show queue items
    process             Process next N pending items using Marker. Warm batch
                        on Windows (thread mode); cold per paper on
                        Linux/Docker.
    counts              Show item counts by status

options:
  -h, --help            show this help message and exit
  --queue-dir PATH      Override artifact queue directory (default:
                        artifacts/research/marker_parse_queue)
```

### `git diff --stat`

Exit code: 0

```text
```

No tracked diff was present before writing this review log. The implementation
under review is currently represented by untracked files and unchanged tracked
queue/fetcher/CLI files.

### Targeted searches

`rg` could not run in this sandbox:

```text
Program 'rg.exe' failed to run: Access is denied
```

Fallback `Select-String` checks found:

- `MarkerIPCWorker` only in `marker_ipc_worker.py` and
  `tests/test_ris_marker_ipc_worker.py`.
- No `warm-process`, `_ipc_worker_cls`, `_marker_ipc_worker`, or
  `TestProcessNextIPCWorker` in the checked-out queue/CLI/test integration
  files.
- `marker_queue.py` lines 261-262 still document Linux/Docker subprocess mode
  as one fresh process per paper, with warm IPC deferred.
- `tools/cli/research_marker_queue.py` parser dispatch only routes
  `enqueue`, `list`, `process`, and `counts`.
- `fetchers.py` still sets `_MARKER_DISABLED` in existing timeout paths and has
  no IPC worker delegation hook.

## Decision

FAIL. The mocked standalone IPC worker core is plausible and its tests pass, but
the CLI/queue/fetcher harness is not present in the checked-out implementation.
Docker/live warm-worker validation should not run next because there is no
explicit warm-worker CLI path to exercise, and the current Linux/Docker queue
path still cold-loads Marker per paper.

## Blockers / Fixes Needed Before Docker Validation

1. Wire `MarkerIPCWorker` into `MarkerParseQueue.process_next()` behind an
   explicit Linux/Docker IPC path with injectable test hooks.
2. Add a `LiveAcademicFetcher` IPC delegation hook so Marker parsing goes
   through the warm worker and bypasses the old `_MARKER_DISABLED` subprocess
   timeout behavior.
3. Add an explicit CLI command such as `research-marker-queue warm-process`
   that reports IPC usage and states that L1 remains blocked until live Docker
   timing validates.
4. Add integration tests covering queue IPC lifecycle, shutdown on exception,
   retry semantics on IPC timeout/error, Windows thread-mode preservation, and
   CLI help/output for the warm-worker path.
5. Re-run the targeted pytest command and CLI help after those fixes. Only then
   should the Docker/live validation prompt run.

## Codex Review Summary

Tier: Recommended review. The reviewed files are RIS queue/fetcher/CLI and IPC
worker code, not trading execution or mandatory live-capital files.

Issues found: blocking harness mismatch; no checked-out CLI/queue/fetcher IPC
integration despite the integration dev log claiming it exists.

Issues addressed: none. Review-only task; no code changes were made.
