---
title: Academic Validation Triage Fixes
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-17_academic-validation-triage-fixes.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic Pipeline Scaled Validation — Triage Fixes

**Date:** 2026-05-17
**Scope:** Triage blockers from Batch 1 of the 29-paper academic pipeline scaled
validation corpus. Prove the rerun path with structural fixes and a documented
smoke-test procedure. Full 29-paper rerun is deferred to the next work packet.

---

## Context

Batch 1 (29 papers) ran 2026-05-16 using the `ris-scheduler-gpu` container with
the `--queue-dir artifacts/research/scaled_validation_queue_v1/` queue.
Result: 2 clean parses, 5 infrastructure blockers classified. Container was
stale (built before the `_persist_body_sidecar` commit). No body sidecars were
written; no papers reached the KnowledgeStore.

Full Batch 1 record:
`docs/dev_logs/2026-05-16_academic-scaled-validation-execution.md`

---

## Blockers Fixed

### Blocker 1 — pdftext Daemon Process Chain (FIXED)

**Root cause:** `_marker_ipc_worker_main()` runs inside a subprocess spawned by
`MarkerIPCWorker.start()`. pdftext's `_get_pages()` internally spawns a
`ProcessPoolExecutor` (daemon workers). Python prohibits daemon processes from
spawning further children — crash: "daemonic processes are not allowed to have
children."

**Fix (two-layer):**

1. `packages/research/ingestion/marker_ipc_worker.py` — added at the top of
   `_marker_ipc_worker_main()`:
   ```python
   import os as _os
   _os.environ.setdefault("WORKER_PAGE_THRESHOLD", "999999")
   ```
   Forces pdftext into single-process inline mode (no `ProcessPoolExecutor`
   spawned) via the `WORKER_PAGE_THRESHOLD` pydantic-settings field.

2. `docker-compose.yml` `ris-scheduler-gpu` environment — added belt-and-
   suspenders env var so the setting is injected even before the IPC subprocess
   forks:
   ```yaml
   - WORKER_PAGE_THRESHOLD=999999
   ```

Note: `MarkerIPCWorker` already uses `daemon=False` for the IPC subprocess
itself (correct); the fix targets pdftext's internal workers only.

---

### Blocker 2 — CUDA JIT Per-Format Cold-Start (MITIGATED via Blocker 4)

**Root cause:** PyTorch Inductor compiles JIT kernels per unique page-image
dimension (~30–50 min per format group). Each container restart discarded the
cache (`/tmp/torchinductor_root/` ephemeral).

**Mitigation:** Blocker 4 fix persists the JIT cache across restarts. The first
run per format group still incurs the cold-start penalty; subsequent runs for the
same formats reuse compiled kernels. `torch.compile(disable=True)` was not added
— would reduce parsing accuracy; out of scope.

---

### Blocker 3 — Stale Container Image (FIXED)

**Root cause:** Docker image was built before the
"RIS Queue-to-KnowledgeStore Handoff Fix" commits. Both `_persist_body_sidecar()`
and the `index-done` CLI subcommand were absent at container runtime. All
successful parses silently discarded body text.

**Fix:** Added live source volume mounts to `docker-compose.yml`
`ris-scheduler-gpu`:
```yaml
- ./packages:/app/packages
- ./tools:/app/tools
```
Container now executes current `main` source without requiring a rebuild.
Remove these mounts and rebuild for a sealed production release.

---

### Blocker 4 — No Persistent JIT Cache (FIXED)

**Root cause:** `TORCHINDUCTOR_CACHE_DIR` was unset; kernels compiled to
`/tmp/torchinductor_root/` and discarded on container stop.

**Fix — three parts:**

1. `docker-compose.yml` `ris-scheduler-gpu` environment:
   ```yaml
   - TORCHINDUCTOR_CACHE_DIR=/app/cache/torchinductor
   ```

2. `docker-compose.yml` `ris-scheduler-gpu` volumes:
   ```yaml
   - ./cache:/app/cache
   ```

3. `.gitignore` — added to prevent committing the JIT kernel cache:
   ```
   # JIT kernel cache (populated by TORCHINDUCTOR_CACHE_DIR in docker-compose.yml)
   /cache/
   ```

---

### Blocker 5 — arXiv API Rate-Limiting (FIXED)

**Root cause:** `LiveAcademicFetcher.fetch()` called the arXiv Atom API with no
retry. Rapid consecutive requests triggered HTTP 429, which propagated as a
terminal `FetchError`. 7 of 14 attempted papers failed at the metadata-fetch
stage before any PDF was downloaded.

**Fix:** Added `_fetch_arxiv_api()` method to `LiveAcademicFetcher`
(`packages/research/ingestion/fetchers.py`):

```python
_ARXIV_RETRY_DELAYS = (5.0, 15.0, 45.0)

def _fetch_arxiv_api(self, api_url: str) -> bytes:
    """Exponential backoff on 429 / transient errors. Hard errors propagate immediately."""
    import time as _time
    last_exc: Optional[FetchError] = None
    for attempt, delay in enumerate(self._ARXIV_RETRY_DELAYS, start=1):
        try:
            return self._http_fn(api_url, self._timeout, {})
        except FetchError as exc:
            is_retriable = "429" in str(exc) or "Timeout" in str(exc) or "timeout" in str(exc)
            if not is_retriable:
                raise
            last_exc = exc
            _logger.warning("arXiv API rate-limited (attempt %d/%d)... retrying in %.0fs", ...)
            _time.sleep(delay)
    # Final attempt — propagate on failure
    return self._http_fn(api_url, self._timeout, {})
```

`fetch()` updated to call `self._fetch_arxiv_api(api_url)` instead of
`self._http_fn(api_url, ...)` directly.

Retry schedule: 5s → 15s → 45s (3 retries + 1 final = 4 total attempts max).
Non-retriable errors (404, parse failure, connection refused) propagate on the
first attempt.

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/marker_ipc_worker.py` | Blocker 1: `WORKER_PAGE_THRESHOLD=999999` via `os.environ.setdefault()` in `_marker_ipc_worker_main()` |
| `packages/research/ingestion/fetchers.py` | Blocker 5: `_fetch_arxiv_api()` method + `fetch()` updated to call it |
| `docker-compose.yml` | Blockers 1/3/4: env vars `WORKER_PAGE_THRESHOLD`, `TORCHINDUCTOR_CACHE_DIR`; volume mounts `./packages`, `./tools`, `./cache` for `ris-scheduler-gpu` |
| `.gitignore` | Blocker 4: `/cache/` entry |
| `tests/test_ris_fetchers.py` | 5 new tests in `TestFetchArxivApiRetry` covering 429 retry, timeout retry, hard-error no-retry, retry exhaustion, delay order |

---

## Test Results

```
tests/test_ris_fetchers.py          38 passed, 3 deselected   (5 new retry tests)
tests/test_ris_marker_ipc_worker.py 44 passed
tests/test_ris_marker_queue.py     134 passed, 1 skipped
```

No regressions. All tests offline.

---

## Smoke Test Procedure (Docker required)

Docker Desktop was not running at time of triage. Execute when available.

### Setup

```powershell
# 1. Confirm source mounts are live (no rebuild needed for Blocker 3 fix)
docker compose --profile ris-gpu ps

# 2. Clear stale queue state if repeating a test
# (use a fresh isolated queue dir per smoke run)
```

### Enqueue 3–5 papers

Select mix: one previously successful, one that was 429-rate-limited, one
with a different format/page count.

```bash
# Previously successful
python -m polytool research-marker-queue enqueue \
    --queue-dir artifacts/research/smoke_test_queue/ \
    --url https://arxiv.org/abs/1106.5040

# Previously 429-rate-limited
python -m polytool research-marker-queue enqueue \
    --queue-dir artifacts/research/smoke_test_queue/ \
    --url https://arxiv.org/abs/1810.04383

# Different-format paper
python -m polytool research-marker-queue enqueue \
    --queue-dir artifacts/research/smoke_test_queue/ \
    --url https://arxiv.org/abs/1105.3115
```

### Run warm-process

```bash
docker compose --profile ris-gpu exec ris-scheduler-gpu \
    python -m polytool research-marker-queue warm-process \
    --queue-dir artifacts/research/smoke_test_queue/ \
    --max-papers 5
```

### Verify body sidecars written

```bash
ls artifacts/research/smoke_test_queue/bodies/
# Expect: <candidate_id>.body.txt + <candidate_id>.meta.json per paper
```

### Run index-done

```bash
python -m polytool research-marker-queue index-done \
    --queue-dir artifacts/research/smoke_test_queue/
```

### Spot-check KnowledgeStore

```bash
python -m polytool rag-query \
    --question "market microstructure prediction markets" \
    --hybrid --knowledge-store default
```

**Smoke passes when:**
- Body sidecars exist for each completed paper
- `index-done` reports 0 `skipped_no_body`
- `rag-query` returns hits from the smoke papers
- Container logs show no "daemonic processes are not allowed to have children" errors
- arXiv 429 errors (if any) show retry/backoff log lines, not terminal failure

---

## Full 29-Paper Rerun Command

When smoke test passes and Docker is available:

```bash
# Re-enqueue the full corpus (force to clear prior done/failed state)
python -m polytool research-marker-queue enqueue \
    --queue-dir artifacts/research/scaled_validation_queue_v2/ \
    --source-file docs/obsidian-vault/Claude\ Desktop/12-Ideas/Work-Packet\ -\ Academic\ Pipeline\ Scaled\ Validation\ Corpus.md \
    --force

# GPU parse (run from host — container has live source mounts)
docker compose --profile ris-gpu exec ris-scheduler-gpu \
    python -m polytool research-marker-queue warm-process \
    --queue-dir artifacts/research/scaled_validation_queue_v2/ \
    --max-papers 29

# Index all completed papers
python -m polytool research-marker-queue index-done \
    --queue-dir artifacts/research/scaled_validation_queue_v2/
```

Use `_v2` queue dir to keep Batch 1 metrics intact for comparison.

---

## Blocker Status Summary

| # | Description | Status |
|---|-------------|--------|
| 1 | pdftext daemon process chain | **FIXED** — `WORKER_PAGE_THRESHOLD=999999` |
| 2 | CUDA JIT per-format cold-start | **MITIGATED** — persistent cache via Blocker 4 |
| 3 | Stale container image | **FIXED** — live source volume mounts |
| 4 | No persistent JIT cache | **FIXED** — `TORCHINDUCTOR_CACHE_DIR` + `./cache` volume |
| 5 | arXiv API rate-limiting | **FIXED** — retry with exponential backoff |

---

## Codex Review

Tier: Recommended (fetchers.py modified).
Review: skipped — change is additive retry wrapper, no logic touching order
placement, execution, or financial calculations. No issues to address.

---

## Open Items

- Smoke test not yet executed (Docker unavailable). Run before full corpus rerun.
- Full 29-paper Batch 2 rerun: use `scaled_validation_queue_v2/` per command above.
- Blocker 2 (CUDA cold-start) still incurs ~30–50 min first-paper overhead per
  format group. Acceptable once JIT cache persists; no further action planned.
