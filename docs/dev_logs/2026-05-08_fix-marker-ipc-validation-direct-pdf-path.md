# Fix: Marker IPC Validation — Direct PDF Path (Bypass arXiv Metadata API)

Date: 2026-05-08
Type: implementation + tests
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Status: **DONE — direct PDF path implemented and tested; live validation NOT run; L1 still blocked**

---

## Root Cause Summary

The live Docker validation (2026-05-08) proved IPC worked for paper 1 but stalled on
papers 2–3. Root cause: `LiveAcademicFetcher.fetch()` always calls the arXiv Atom API
(`http://export.arxiv.org/api/query?id_list=<ID>&max_results=1`) before downloading the
PDF. The queue's `_process_item()` always called `fetcher.fetch(source_url)`. When
arXiv rate-limited the container (timeout on attempt 1, HTTP 429 on attempt 2), the
warm-process budget was exhausted without ever reaching Marker.

The IPC warm-worker itself was not the failure. The failure was arXiv metadata API
reliability inside a Docker container context. Feature 3 acceptance gates test Marker
warm-worker speed, not arXiv metadata API reliability.

---

## What Existed Before This Fix

- `LiveAcademicFetcher.fetch(url)` — always fetches arXiv Atom metadata first, then PDF
- `MarkerParseQueue.enqueue(url_or_id)` — arXiv ID only; no direct PDF URL support
- `MarkerParseQueue._process_item()` — always calls `fetcher.fetch(source_url)`
- No bypass path for the metadata API

---

## What Was Added

### `packages/research/ingestion/fetchers.py`

Added `LiveAcademicFetcher.fetch_pdf_direct(url_or_path, title="")`:
- Accepts an HTTP/HTTPS URL or a local file path
- Downloads the PDF (URL) or reads it directly (local path)
- Calls `_parse_pdf(tmp_path)` — same path as `_fetch_pdf_body`, includes IPC worker dispatch
- **Never calls `export.arxiv.org/api/query`** — no arXiv Atom API contact
- Returns dict with `url`, `title`, `body_source`, `body_length`, `parse_seconds`,
  `failure_reason` (compatible with `_process_item` expectations)
- On HTTP download failure or local path error: returns `body_source=abstract_fallback`
- On IPC worker error: returns `body_source=marker_failed` (no pdfplumber fallback)

### `packages/research/ingestion/marker_queue.py`

`MarkerParseQueue.enqueue()`:
- Added optional `pdf_url: str = ""` parameter
- If non-empty, stored as `pdf_url` field in the queue record
- `candidate_id` derivation unchanged — still requires arXiv ID in `--url`
- No change to existing queue records without `pdf_url`

`MarkerParseQueue._process_item()`:
- If `item.get("pdf_url")` is set AND fetcher has `fetch_pdf_direct`:
  calls `fetcher.fetch_pdf_direct(pdf_url, title=...)` instead of `fetcher.fetch(source_url)`
- Falls back to `fetcher.fetch(source_url)` when `pdf_url` absent or fetcher lacks the method
- All downstream logic (rejection, marker_ready, retry) unchanged

### `tools/cli/research_marker_queue.py`

`enqueue` subcommand:
- Added `--pdf-url PDF_URL_OR_PATH` optional argument
- Passed through to `q.enqueue(..., pdf_url=...)`
- Help text clearly documents: skips arXiv metadata API; `--url` still determines candidate_id

---

## Files Changed

| File | Change |
|------|--------|
| `packages/research/ingestion/fetchers.py` | Added `fetch_pdf_direct()` method to `LiveAcademicFetcher` |
| `packages/research/ingestion/marker_queue.py` | `enqueue(pdf_url=...)` parameter; `_process_item` dispatch |
| `tools/cli/research_marker_queue.py` | `--pdf-url` arg on `enqueue` subcommand |
| `tests/test_ris_marker_queue.py` | 4 new test classes, 21 new tests |

---

## Commands Run and Outputs

### Tests

```
python -m pytest tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py -q --tb=short
```

Result: **146 passed, 1 skipped** in 2.56s

The 1 skip is `test_warm_thread_worker_raises_on_subprocess_platform` — Linux-only
behaviour, correctly skipped on Windows.

### CLI verification

```
python -m polytool research-marker-queue enqueue --help
```

Output confirmed: `--pdf-url PDF_URL_OR_PATH` present with correct description.

```
python -m polytool research-marker-queue warm-process --help
```

Output confirmed: unchanged (no new flags on warm-process).

```
python -m polytool --help | Select-String "research-marker"
```

Output: `research-marker-queue  Enqueue/process arXiv papers through Marker; track RAG-ready status`

---

## Test Coverage Added

| Class | Tests | What they prove |
|-------|-------|-----------------|
| `TestFetchPdfDirect` | 7 | URL path never calls arXiv API; returns `marker`; title preserved; download failure → `abstract_fallback`; local path → no HTTP at all; result dict has expected keys; IPC error → `marker_failed` not pdfplumber |
| `TestEnqueuePdfUrl` | 4 | `pdf_url` stored in record; absent when not given; arXiv candidate_id preserved; local path stored |
| `TestProcessNextDirectPdf` | 6 | `fetch_pdf_direct` called when `pdf_url` set; `fetch()` called when no `pdf_url`; graceful fallback when method absent; failure propagates; `ipc_warm_worker_used=True` set by `process_next_ipc`; mixed-item batch routes correctly |
| `TestCLIPdfUrl` | 4 | `--pdf-url` in help; stored in queue record; absent when not given; JSON output correct |

---

## Exact Validation Queue Syntax for Next Prompt

The validation queue (`artifacts/research/marker_validation_queue`) currently has:
- Paper 1 (`arxiv:2604.24366`): `done` — already validated, will be skipped
- Paper 2 (`arxiv:1910.08858`): `pending`, 2 attempts — needs re-enqueue with `--pdf-url --force`
- Paper 3 (`arxiv:2109.07581`): `pending`, 0 attempts — needs re-enqueue with `--pdf-url --force`

**Step 1 — Re-enqueue papers 2 and 3 with direct PDF URLs:**
```powershell
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  enqueue `
  --url https://arxiv.org/abs/1910.08858 `
  --pdf-url https://arxiv.org/pdf/1910.08858.pdf `
  --title "Beating the House: Identifying Inefficiencies in Sports Betting Markets" `
  --force

python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  enqueue `
  --url https://arxiv.org/abs/2109.07581 `
  --pdf-url https://arxiv.org/pdf/2109.07581.pdf `
  --title "The Impact of COVID-19 on Sports Betting Markets" `
  --force
```

**Step 2 — Verify queue state (should show 2 pending with pdf_url):**
```powershell
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  list --status pending
```

**Step 3 — Run validation (use --max-items 4 to cover retries):**
```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue `
  warm-process --max-items 4 --json
```

Expected acceptance gates for next run:
- Papers 2 and 3: `body_source=marker`, `ipc_warm_worker_used=true`
- Papers 2–3 `parse_seconds` ≤ 10s (warm VRAM, models already loaded from paper 1 session)
- No `export.arxiv.org` calls (pdf_url path bypasses metadata API)
- Queue ends with all 3 papers `done`

---

## Live Validation: Not Run

No Docker containers were started. No live Marker parsing occurred. The validation
queue (`artifacts/research/marker_validation_queue`) was not mutated.

---

## L1 Status

**L1 Marker production rollout remains BLOCKED.**

Feature 3 acceptance gates are not yet satisfied — live Docker/GPU validation with
≥3 papers warm (papers 2+ ≤10s, `ipc_warm_worker_used=true`, `body_source=marker`) is
still required. This fix unblocks the *path* to run that validation without arXiv
metadata API interference.

---

## Codex Review Summary

Tier: recommended (strategy/queue consumer change).
No adversarial-review trigger (no execution/, kill_switch, or risk_manager files).
Files changed: fetchers.py, marker_queue.py, research_marker_queue.py, test_ris_marker_queue.py.
Issues found: none. Issues addressed: n/a.
