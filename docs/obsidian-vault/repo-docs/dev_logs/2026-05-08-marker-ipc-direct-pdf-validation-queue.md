---
title: Marker Ipc Direct Pdf Validation Queue
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_marker-ipc-direct-pdf-validation-queue.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Marker IPC Direct-PDF Validation Queue — Preparation

Date: 2026-05-08
Type: queue preparation (no live parsing)
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Status: **READY — fresh isolated direct-PDF queue prepared; warm-process NOT run; L1 still blocked**

---

## Purpose

Prepare a fresh isolated validation queue that uses direct PDF URLs (`arxiv.org/pdf/`)
instead of the arXiv Atom API (`export.arxiv.org/api/query`). This unblocks the IPC
warm-worker validation that stalled on 2026-05-08 when papers 2–3 hit arXiv rate limits
before ever reaching Marker.

---

## Prompt A Dev Log

Source: `docs/dev_logs/2026-05-08_fix-marker-ipc-validation-direct-pdf-path.md`

Key findings:
- `fetch_pdf_direct(url_or_path, title="")` added to `LiveAcademicFetcher`
- `enqueue(pdf_url=...)` parameter added to `MarkerParseQueue`
- `--pdf-url` flag added to `research-marker-queue enqueue` CLI
- When `pdf_url` is set in a queue record, `_process_item` calls `fetch_pdf_direct`
  instead of `fetch()` — no Atom API call made
- 146 tests pass, 1 skipped

---

## Local PDF Cache Check

No persistent PDF files exist on disk. `_fetch_pdf_body` downloads to a temp file and
deletes it after parsing. The `raw_source_cache/academic/` stores pdfplumber-body JSON,
not PDF bytes.

Therefore: all candidates use `--pdf-url https://arxiv.org/pdf/<ID>.pdf`. The PDF is
downloaded by the Docker container directly from arxiv.org/pdf/ — a different endpoint
from the Atom API that caused the rate-limit failure.

---

## Candidate Table

| # | arXiv ID | Title | Pages | Eq refs | Rationale |
|---|----------|-------|-------|---------|-----------|
| 1 | `2604.24366` | The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book | 15 | low | **Anchor** — already successfully parsed via IPC in live run (body_source=marker, parse_seconds=39.19s, body_length=56923). Mandatory. |
| 2 | `2109.07581` | The Impact of COVID-19 on Sports Betting Markets | 23 | 0 | **Simplest candidate** — 0 equation/theorem refs, 6,231 words, pure empirical. Prior pdfplumber body_length=41926. Prose-heavy. |
| 3 | `1910.08858` | Beating the House: Identifying Inefficiencies in Sports Betting Markets | 46 | 8 | **Prose-heavy betting paper** — 8,979 words, 8 eq refs, filter_decision=allow, score=0.880797. Prior pdfplumber body_length=58604. Failed in prior run only due to arXiv Atom API timeout/429. |

**Why these three:** All pre-verified as simple/prose-heavy candidates. Paper 1 is the
IPC-validated anchor. Papers 2 and 3 are the same candidates from the prior failed run —
they failed on Atom API rate-limiting, not on Marker parsing. With `pdf_url` set,
no Atom API call is made and papers 2–3 should parse from warm VRAM in ≤10s.

---

## Evidence: arXiv Metadata API Not Required

The `pdf_url` field in each queue record triggers `fetch_pdf_direct()` at process time.
Code path confirmed in `packages/research/ingestion/marker_queue.py`:

```python
pdf_url = item.get("pdf_url", "")
if pdf_url and hasattr(fetcher, "fetch_pdf_direct"):
    raw = fetcher.fetch_pdf_direct(pdf_url, title=item.get("title", ""))
else:
    raw = fetcher.fetch(source_url)
```

`fetch_pdf_direct` docs: "Does NOT call `export.arxiv.org/api/query`"

All three queue records have `pdf_url` set (confirmed below). The Atom API is NOT called.

---

## Exact Enqueue Commands Used

```powershell
# Paper 1 — anchor (IPC-validated in prior live run)
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  enqueue `
  --url https://arxiv.org/abs/2604.24366 `
  --pdf-url https://arxiv.org/pdf/2604.24366.pdf `
  --title "The Anatomy of a Decentralized Prediction Market: Microstructure Evidence from the Polymarket Order Book" `
  --json

# Paper 2 — 23 pages, 0 eq refs (simplest candidate)
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  enqueue `
  --url https://arxiv.org/abs/2109.07581 `
  --pdf-url https://arxiv.org/pdf/2109.07581.pdf `
  --title "The Impact of COVID-19 on Sports Betting Markets" `
  --json

# Paper 3 — 46 pages, prose-heavy betting paper
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  enqueue `
  --url https://arxiv.org/abs/1910.08858 `
  --pdf-url https://arxiv.org/pdf/1910.08858.pdf `
  --title "Beating the House: Identifying Inefficiencies in Sports Betting Markets" `
  --json
```

**Outputs:**
```json
{"candidate_id": "arxiv:2604.24366", "status": "pending", "action": "added"}
{"candidate_id": "arxiv:2109.07581", "status": "pending", "action": "added"}
{"candidate_id": "arxiv:1910.08858", "status": "pending", "action": "added"}
```

---

## Queue Counts / List Verification

### counts --json

```json
{
  "pending": 3,
  "processing": 0,
  "done": 0,
  "failed": 0,
  "total": 3
}
```

### list --status all

```
  candidate_id                 status       att   title
  -------------------------------------------------------------------------------------------
  arxiv:2604.24366             pending      0     The Anatomy of a Decentralized Predictio
  arxiv:2109.07581             pending      0     The Impact of COVID-19 on Sports Betting
  arxiv:1910.08858             pending      0     Beating the House: Identifying Inefficie

Total: 3 item(s)
```

### results.jsonl exists: False

No live parsing has occurred. Queue is clean.

### pdf_url in every record (confirmed from queue.jsonl):

```
candidate=arxiv:2604.24366  pdf_url=https://arxiv.org/pdf/2604.24366.pdf  attempts=0
candidate=arxiv:2109.07581  pdf_url=https://arxiv.org/pdf/2109.07581.pdf  attempts=0
candidate=arxiv:1910.08858  pdf_url=https://arxiv.org/pdf/1910.08858.pdf  attempts=0
```

---

## Exact Next Docker Validation Command

```powershell
docker --context default run --rm --gpus all `
  -v "${PWD}/artifacts:/app/artifacts" `
  polytool-ris-scheduler-gpu:latest `
  python -m polytool research-marker-queue `
  --queue-dir artifacts/research/marker_validation_queue_direct `
  warm-process --max-items 3 --json
```

Notes:
- `--max-items 3` is correct: 3 fresh candidates, all attempts=0, no retries anticipated
- `--context default` required (desktop-linux context is unavailable)
- `--gpus all` required for RTX 2070 Super VRAM
- Volume mount exposes `D:\...\artifacts` as `/app/artifacts` inside container
- The `--queue-dir` path is relative inside the container: `artifacts/research/marker_validation_queue_direct`

**Expected acceptance gates:**
- Paper 1: `body_source=marker`, `ipc_warm_worker_used=true` (model cold load ~140s amortized into total_seconds; parse_seconds expected 30–85s for first paper)
- Papers 2–3: `body_source=marker`, `ipc_warm_worker_used=true`, `parse_seconds ≤ 10s` (warm VRAM)
- All 3: `queue_status=done`, `marker_ready=true`
- No `export.arxiv.org` contact (bypassed by `pdf_url` dispatch)
- No pdfplumber fallback
- Clean exit (`exit_code=0`)

---

## Warm-Process Not Run

No Docker containers were started. No live Marker parsing occurred. The queue file
`artifacts/research/marker_validation_queue_direct/queue.jsonl` contains only the
three enqueued records written by the CLI enqueue commands above. No results.jsonl exists.

---

## L1 Status

**L1 Marker production rollout remains BLOCKED.**

Acceptance gates require live Docker/GPU validation: ≥3 papers warm, papers 2+ ≤10s,
`ipc_warm_worker_used=true`, `body_source=marker`. This queue preparation session only
creates the validated input for that run.

---

## Readiness Verdict for Next Session

| Check | Status |
|-------|--------|
| Fresh isolated queue path | `artifacts/research/marker_validation_queue_direct` |
| 3 pending candidates | PASS |
| 0 done / 0 failed / results.jsonl absent | PASS |
| pdf_url set in every record | PASS |
| No arXiv Atom API calls required | PASS |
| Candidates pre-verified as prose-heavy/simple | PASS |
| Exact Docker command written | PASS |
| warm-process not run | PASS |

**READY FOR CODEX / NEXT LIVE VALIDATION SESSION.**
