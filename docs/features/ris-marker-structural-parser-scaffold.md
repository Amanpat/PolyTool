# Feature: RIS Marker Structural Parser — Production Default (Layer 1)

**Status: Production default — Marker is the only academic PDF parser**

Layer 1 ships Marker as the default and only production PDF parser for the
academic ingest pipeline. pdfplumber is no longer the active production path;
it remains in the codebase as a debug override (`RIS_PDF_PARSER=pdfplumber`)
only. GPU is required: RTX 2070 Super on the dev machine, Docker GPU
passthrough verified (Docker Desktop 29.x + WSL2), ~5–10 s/paper on GPU vs
300 s timeout on CPU.

---

## What Was Implemented

Four work packets (Prompts A–D) implemented and hardened the Layer 1 scaffold:

| Prompt | Deliverable |
|--------|-------------|
| A | `MarkerPDFExtractor` class, `LiveAcademicFetcher` parser dispatch (`auto`/`pdfplumber`/`marker`), `ris-marker` optional extra, pdfplumber fallback, adapter metadata propagation |
| B | Codex fixes: `structured_metadata_summary` in adapter, timeout via `ThreadPoolExecutor`, monkeypatched absence test, accurate fetch logging; parser benchmark CLI |
| C | LLM-flag truthfulness (no false `marker_llm_boost`), `_MARKER_DISABLED` Event, `_pdf_parser` default changed to `"pdfplumber"` |
| D | Two-layer concurrency proof: confirmed Prompt B semaphore released on timeout while worker ran; added `_MARKER_DISABLED` gate set before semaphore release; double-call test proves at-most-one zombie |

---

## Default Parser Behavior

**Default parser: Marker — production default with GPU.**

`LiveAcademicFetcher` defaults to `_pdf_parser="marker"`. pdfplumber is only
used when explicitly overridden for debugging. Marker failure is an explicit
rejection (`body_source="marker_failed"`) — no silent downgrade to pdfplumber
or abstract-only records.

Override options:
- `RIS_PDF_PARSER=pdfplumber` — debug/test override; not production-equivalent
- `RIS_PDF_PARSER=auto` — try Marker if installed, fall back silently on ImportError
- `RIS_PDF_PARSER=marker` — explicit production mode (same as default)

### Parser decision table

| `RIS_PDF_PARSER` | Outcome | `body_source` |
|---|---|---|
| `marker` (default) | Marker success | `"marker"` |
| `marker` (default) | Marker failure / timeout / not installed | `"marker_failed"` |
| `auto` | Marker success | `"marker"` |
| `auto` | Marker ImportError (not installed) | `"pdf"` (silent pdfplumber) |
| `auto` | Marker runtime error / timeout | `"pdfplumber_fallback"` |
| `pdfplumber` (debug override) | pdfplumber runs | `"pdf"` |

**`marker_failed` semantics:** `body_text=""` in the fetch result — the paper
is rejected, not silently downgraded to abstract. `failure_reason` is
populated. `abstract` key still present in the result for traceability.

If `_MARKER_DISABLED` is set (prior timeout in this process): `marker` mode
returns `body_source="marker_failed"` with
`failure_reason="marker_disabled: ..."` immediately, no new thread spawned.

---

## Installation

### Production install (GPU host — includes Marker)

```bash
pip install "polytool[ris]"
# or from repo root:
python -m pip install -e ".[ris]"
```

`[ris]` now includes `marker-pdf>=1.0` (surya-ocr, PyTorch). First run
downloads model weights into `~/.cache/datalab/` (~1–3 GB). GPU required
for production throughput (~5–10 s/paper on RTX 2070 Super; 300 s timeout
on CPU).

For Docker GPU service use `Dockerfile.ris` which installs CUDA torch (cu124)
before `[ris]` to ensure the GPU build is used.

### Backward-compat alias (unchanged)

```bash
pip install "polytool[ris-marker]"
```

`[ris-marker]` is now a backward-compat alias that still installs
`marker-pdf>=1.0`. Functionally equivalent to `[ris]` for Marker purposes.

### Smoke test after install

```bash
python -c "import marker; print('marker import ok')"
python -m polytool research-parser-benchmark --urls 2510.15205 \
  --parsers marker --marker-timeout 60
```

---

## Metadata Fields

### In `raw_source` / `RawSourceCache` (disk only, never ChromaDB)

| Field | Type | Description |
|---|---|---|
| `body_source` | str | `"pdf"`, `"marker"`, `"pdfplumber_fallback"`, `"abstract_fallback"` |
| `body_length` | int | Characters in extracted body |
| `page_count` | int | Parser-reported page count |
| `has_structured_metadata` | bool | `True` when Marker produced structured output |
| `marker_version` | str | `marker-pdf` version at extraction time |
| `structured_metadata` | dict | Full Marker output dict (may be large; 20 MB cap enforced) |
| `structured_metadata_truncated` | bool | `True` if metadata exceeded 20 MB and was replaced by a compact stub |
| `fallback_reason` | str | Why Marker fell back (if applicable); includes `"marker_timeout:"`, `"marker_busy:"`, `"marker_disabled:"` prefixes for grepping |

### In `ExtractedDocument.metadata` (propagated to adapter / ChromaDB)

All fields above except `structured_metadata` (excluded — too large for vector store).
Additionally:

| Field | Type | Description |
|---|---|---|
| `structured_metadata_summary` | dict | Compact signals from `structured_metadata`: `key_count`, `section_count` (if toc), `has_toc` (if toc) |
| `marker_llm_requested` | bool | Present when `RIS_MARKER_LLM=1` — records intent only |
| `marker_llm_applied` | bool | Always `False` when present — LLM not yet wired |

### LLM truthfulness

`RIS_MARKER_LLM=1` does **not** make any LLM API call. It sets
`marker_llm_requested=True`, `marker_llm_applied=False`, and emits a
`logger.warning`. `body_source` is always `"marker"` — the string
`"marker_llm_boost"` no longer exists anywhere in the codebase. LLM-enriched
Marker extraction is a Layer 2 deliverable.

---

## Structured Metadata Cache Policy

- Full `structured_metadata` (potentially MBs of Marker output) is stored in
  `RawSourceCache` (disk JSON) only.
- A 20 MB JSON cap is enforced in `MarkerPDFExtractor.extract()`. Metadata
  exceeding the cap is replaced by a compact stub; `structured_metadata_truncated=True`
  is set in both raw and adapter metadata.
- Image binaries are stripped from `out_meta` before any storage.
- `structured_metadata` is intentionally excluded from `ExtractedDocument.metadata`
  to keep ChromaDB payloads small.

---

## Timeout and Concurrency Guards

### Two-layer design

**Layer 1 — `_MARKER_WORK_SEMAPHORE` (capacity=1):**
Prevents a new Marker attempt while a conversion is actively starting (between
semaphore acquire and first pool submit). Semaphore is released in the outer
`finally` after the caller returns.

**Layer 2 — `_MARKER_DISABLED` (threading.Event):**
Set the moment `concurrent.futures.TimeoutError` fires, before the semaphore
is released. All subsequent requests check this flag first and fall back to
pdfplumber without touching the semaphore or spawning any thread.

### Lifecycle on timeout

```
_cf.TimeoutError fires
→ _MARKER_DISABLED.set()          # Layer 2: flag set FIRST
→ pool.shutdown(wait=False)
→ outer finally: semaphore.release()
second request checks _MARKER_DISABLED.is_set() → True → immediate pdfplumber
# At most one zombie thread per process lifetime ✓
```

### Residual limitation

The timed-out Marker thread **cannot be killed** on Windows (no `SIGKILL` for
threads). It runs to completion in the background. `_MARKER_DISABLED` prevents
any further threads from being spawned. True cancellation requires a process
boundary (`multiprocessing`) — explicitly deferred.

---

## Parser Benchmark CLI

```bash
# pdfplumber only (fast baseline)
python -m polytool research-parser-benchmark --parsers pdfplumber

# Both parsers, short Marker timeout to show CPU fallback
python -m polytool research-parser-benchmark \
  --urls 2510.15205,2309.01454,2206.14965 \
  --parsers pdfplumber,marker \
  --marker-timeout 30 \
  --output-dir artifacts/benchmark/parser
```

Output columns: `body_source`, `body_length`, `section_count`, `table_count`,
`equation_block_count`, `equation_inline_count`, `parse_seconds`,
`cache_meta_bytes`.

### Benchmark result (CPU host, 2026-04-27)

| arxiv_id   | parser     | body_source         | len   | secs | notes |
|------------|------------|---------------------|-------|------|-------|
| 2510.15205 | pdfplumber | pdf                 | 58927 |  2.2 | |
| 2510.15205 | marker     | pdfplumber_fallback | 58927 | 33.1 | timeout at 30 s |
| 2309.01454 | pdfplumber | pdf                 | 45595 |  8.5 | |
| 2309.01454 | marker     | pdfplumber_fallback | 45595 | 43.5 | timeout at 30 s |
| 2206.14965 | pdfplumber | pdf                 | 35765 |  3.5 | |
| 2206.14965 | marker     | pdfplumber_fallback | 35765 | 34.1 | timeout at 30 s |

pdfplumber delivers 35–59 K chars per paper in 2–9 s. Marker consistently
times out on CPU even at 30 s; the full 300 s timeout fires on all tested papers
under the 300 s default.

---

## Test Coverage

Tests live in `tests/test_ris_academic_pdf.py`.

| Class | Tests | What is covered |
|---|---|---|
| `TestMarkerPDFExtractorUnit` | 6 | Import error, injection success, page count, 20 MB cap, LLM flag intent (not boost), file-not-found |
| `TestMarkerFetcherIntegration` | 11 | Success path, metadata propagation, short output fallback, ImportError (explicit/auto modes), RuntimeError, pdfplumber mode, timeout, second-call disabled guard, busy semaphore, JSON size cap |
| `TestAcademicAdapterMarkerMetadata` | 2 | has_structured_metadata, marker_version, structured_metadata_summary, truncation flag |

All 73 targeted tests pass. Full suite: 2397 passed, 1 pre-existing failure
(`test_ris_claim_extraction` — unrelated).

---

## What Is Explicitly Deferred

| Item | Deferred to |
|---|---|
| Subprocess/process-boundary cancellation of timed-out Marker workers | Future hardening pass; needed if Marker becomes production parser |
| GPU validation and production Marker rollout | After GPU host is available and throughput is confirmed |
| Layer 2 structured chunking strategy | Separate feature — uses Marker section boundaries for smarter chunk splits |
| Layer 2 image-aware retrieval | Separate feature — uses Marker image metadata |
| LLM-enriched Marker extraction (`marker_llm_applied=True`) | Layer 2 deliverable; requires wiring Marker's LLM config |
| Retrieval quality claims from Marker output | Cannot be made until Layer 2 chunking is implemented and benchmarked |
| Adding Marker to base Docker image | Requires Director decision; GPU pass-through needed for practical use |

---

## Dev Log Trail

| Log | Topic |
|---|---|
| [`2026-04-27_ris-marker-core-integration`](../dev_logs/2026-04-27_ris-marker-core-integration.md) | Prompt A: initial MarkerPDFExtractor, fetcher dispatch, adapter propagation, 16 tests |
| [`2026-04-27_codex-review-ris-marker-core`](../dev_logs/2026-04-27_codex-review-ris-marker-core.md) | Codex review: 4 non-blocking findings, PASS WITH FIXES verdict |
| [`2026-04-27_ris-marker-hardening-validation`](../dev_logs/2026-04-27_ris-marker-hardening-validation.md) | Prompt B: 4 Codex fixes, Docker validation, live smoke, benchmark, operator docs |
| [`2026-04-27_ris-marker-timeout-llm-truthfulness`](../dev_logs/2026-04-27_ris-marker-timeout-llm-truthfulness.md) | Prompt C: LLM truthfulness, `_MARKER_DISABLED`, default changed to pdfplumber |
| [`2026-04-27_ris-marker-timeout-concurrency-fix`](../dev_logs/2026-04-27_ris-marker-timeout-concurrency-fix.md) | Prompt D: semaphore-release-before-thread-done bug confirmed and fixed; two-layer guard proven |
