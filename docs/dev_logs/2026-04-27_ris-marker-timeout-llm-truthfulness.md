# 2026-04-27 — RIS Marker Timeout Hardening and LLM Truthfulness (Prompt C)

## Objective

Two residual risks from Prompt B:
1. ThreadPoolExecutor timeout returns control to the caller but cannot kill the
   underlying Marker thread on Windows. Multiple timed-out calls accumulate
   zombie threads consuming CPU/memory.
2. `_enable_llm=True` / `RIS_MARKER_LLM=1` set `body_source="marker_llm_boost"`
   while no LLM call is wired — misleading metadata.

---

## Issue 1: ThreadPoolExecutor Timeout — Before/After

### Before (Prompt B state)

```python
_pool = _cf.ThreadPoolExecutor(max_workers=1)
_fut = _pool.submit(extractor.extract, tmp_path)
try:
    doc = _fut.result(timeout=self._marker_timeout_seconds)
except _cf.TimeoutError:
    _pool.shutdown(wait=False)
    raise TimeoutError(...)
finally:
    _pool.shutdown(wait=False)
```

**Problem:** `shutdown(wait=False)` stops the pool from accepting new work but
does NOT kill the running thread. On Windows, threads cannot be forcibly
terminated after a timeout. If many requests time out in sequence, each spawns a
thread that runs for 5–10+ minutes (the actual Marker conversion time), growing
memory and CPU usage unboundedly.

### After (Prompt C)

**Module-level semaphore added to `fetchers.py`:**

```python
_MARKER_WORK_SEMAPHORE = threading.Semaphore(1)
```

**Gate in `_try_marker_or_fallback`:**

```python
if not _MARKER_WORK_SEMAPHORE.acquire(blocking=False):
    return self._pdfplumber_extract(
        tmp_path,
        fallback_reason="marker_busy: conversion already running",
    )
# ... run Marker in thread ...
finally:
    _MARKER_WORK_SEMAPHORE.release()
```

**Result:** At most one Marker thread runs at a time. If a second request arrives
while a Marker job is in flight, it falls through to pdfplumber immediately with
`body_source="pdfplumber_fallback"` and `fallback_reason="marker_busy: ..."`.

### Residual limitation (explicitly documented)

The underlying thread after a timeout **cannot be killed** on Windows. The
timeout bounds caller latency but the worker continues until Marker finishes or
crashes. The semaphore prevents stacking: one zombie at a time, not N.

The timeout error message now starts with `"marker_timeout:"` for grepping.

---

## Issue 2: LLM Mode Truthfulness — Before/After

### Before

```python
body_source = "marker_llm_boost" if self._enable_llm else "marker"
```

`body_source="marker_llm_boost"` was emitted even though no LLM call is made.
An operator seeing this label would believe LLM enrichment was applied.

### After (`extractors.py`)

```python
# Always report body_source="marker"
metadata_out["body_source"] = "marker"
if self._enable_llm:
    # Record intent without false label
    metadata_out["marker_llm_requested"] = True
    metadata_out["marker_llm_applied"] = False
    _logger.warning("RIS_MARKER_LLM set but no LLM is wired ...")
```

`marker_llm_boost` is no longer emitted anywhere.  When `_enable_llm=True`:
- `body_source` = `"marker"` (honest)
- `marker_llm_requested` = `True` (intent visible)
- `marker_llm_applied` = `False` (actual state visible)
- Warning logged

`marker_llm_boost` remains reserved for the Layer 2 deliverable that actually
wires a Marker LLM backend.

---

## Default Parser Change

Changed `LiveAcademicFetcher.__init__` default `_pdf_parser` from `"auto"` to
`"pdfplumber"`.

**Before:** Marker was attempted silently if installed, even on CPU machines
where it would time out every run.

**After:** pdfplumber is always used unless the caller or operator explicitly
sets `RIS_PDF_PARSER=auto` or `RIS_PDF_PARSER=marker` (or passes
`_pdf_parser="auto"/"marker"` to the constructor). Marker is now opt-in.

---

## Files Changed

| File | Change |
|---|---|
| `packages/research/ingestion/fetchers.py` | `import threading`; `_MARKER_WORK_SEMAPHORE`; semaphore gate in `_try_marker_or_fallback`; default `_pdf_parser="pdfplumber"`; timeout message prefixed `marker_timeout:` |
| `packages/research/ingestion/extractors.py` | `body_source` always `"marker"`; `marker_llm_requested`/`marker_llm_applied` fields when `_enable_llm=True`; warning log |
| `tests/test_ris_academic_pdf.py` | Renamed + updated `test_llm_flag_records_intent_not_llm_boost`; updated timeout assertion; added `test_marker_busy_falls_back_immediately` |

---

## Commands Run

```
python -m pytest tests/test_ris_academic_pdf.py tests/test_ris_academic_ingest_v1.py tests/test_ris_research_acquire_cli.py -v --tb=short
```
**72 passed, 0 failed** (was 71 — new busy test adds 1).

```
python -m pytest tests/ -x -q --tb=short
```
**2396 passed, 1 failed** — sole failure is
`test_ris_claim_extraction.py::TestExtractClaimsFromDocument::test_each_claim_has_required_fields`
(pre-existing, unrelated to this change).

---

## Remaining Limitations

1. **Thread not killable after timeout.** The ThreadPoolExecutor worker thread
   continues running after `_fut.result(timeout=...)` raises. The semaphore
   caps this to 1 zombie thread, but the thread cannot be killed short of
   process exit. True isolation requires `multiprocessing` (deferred to Layer 2
   or a future hardening pass if Marker reaches production use on GPU).

2. **Marker LLM not wired.** `RIS_MARKER_LLM=1` is now a tracer only —
   metadata shows intent without false label. Wire-up is a Layer 2 deliverable.

3. **CPU Marker unusable.** 300s timeout fires for all tested papers on CPU.
   Marker requires a GPU for practical use. Default is now `pdfplumber` to
   prevent accidental CPU Marker attempts.
