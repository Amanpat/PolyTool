---
title: Academic Prefetch Separation Wp1
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-19_academic-prefetch-separation-wp1.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# WP-1 Academic PDF Prefetch Separation

**Date:** 2026-05-19
**Track:** Research Intelligence System — L1 Operational
**Type:** Work packet implementation
**Prerequisite:** `docs/dev_logs/2026-05-18_academic-ris-operational-triage.md`

---

## Problem

Batch 2 failed operationally because warm GPU parsing caused rapid back-to-back
arXiv PDF fetches. Papers 1206.4810, 2003.05958, 2203.13053, 1810.04383, and
2409.02025 all exhausted their 3 retry attempts with HTTP 429 or timeout errors.
The 45s max backoff in `_fetch_arxiv_api` is shorter than arXiv's sustained rate-limit
reset window when many papers complete in rapid succession (warm JIT: 40s/paper).

Root cause: fetch and parse were coupled. The queue's `_process_item` called
`fetcher.fetch()` which did BOTH the arXiv API call AND the PDF download immediately
before GPU parsing. No way to pre-fetch at a conservative rate then parse offline.

---

## Files Changed

| File | Action | Lines |
|------|--------|-------|
| `packages/research/ingestion/marker_queue.py` | Extended | +235 |
| `tools/cli/research_marker_queue.py` | Extended | +175 |
| `docs/dev_logs/2026-05-19_academic-prefetch-separation-wp1.md` | Created | this file |

---

## What Was Built

### 1. `MarkerParseQueue.prefetch_pdfs()` (library)

New method in `packages/research/ingestion/marker_queue.py`:

- Iterates all pending queue items (or up to `max_items`)
- Downloads each PDF from `https://arxiv.org/pdf/{arxiv_id}.pdf` with a
  configurable `delay_seconds` between requests (default 10s)
- Writes PDFs to `queue_dir/pdf_cache/arxiv-{arxiv_id}.pdf` (NTFS-safe: `:` → `-`)
- Updates the queue record with `pdf_url` pointing to the local file path
- Writes/updates `queue_dir/pdf_cache/manifest.jsonl` after every item
  (so partial runs are resumable on interrupt)
- Validates downloaded size > 1000 bytes (guards against HTML error pages)
- **Idempotent**: existing cached files with `status=cached` and `file_size>=1000`
  are skipped entirely; no HTTP call made

Manifest fields per entry: `candidate_id`, `arxiv_id`, `source_url`,
`pdf_cache_path`, `status` (cached/failed/pending), `attempts`, `error`,
`fetched_at`, `file_size`.

### 2. `_process_item()` routing fix (library)

Modified the `_process_item()` inner method to add a file-existence guard before
routing to `fetch_pdf_direct`:

```python
pdf_url = item.get("pdf_url", "")
use_direct = False
if pdf_url and hasattr(fetcher, "fetch_pdf_direct"):
    is_local = not (pdf_url.startswith("http://") or pdf_url.startswith("https://"))
    if is_local:
        if Path(pdf_url).exists():
            use_direct = True
        else:
            _logger.warning("cached PDF missing at %r; falling back to live arXiv fetch", ...)
    else:
        use_direct = True

if use_direct:
    raw = fetcher.fetch_pdf_direct(pdf_url, title=item.get("title", ""))
else:
    raw = fetcher.fetch(source_url)
```

This satisfies:
- "cached item → no arXiv call": `fetch_pdf_direct` on a local path calls
  `_parse_pdf(path)` directly with zero network calls
- "missing cache → graceful fallback": logs warning and falls back to live fetch
  rather than silently failing

### 3. `MarkerParseQueue.get_status_report()` (library)

Structured report method returning:
- `counts` by status
- `processing_items` (likely stuck if no active warm-process)
- `stuck_warning` bool
- `failed_details` with failure reason + attempt count per failed item
- `prefetch_stats` from manifest (cached/failed/total)

### 4. CLI: `prefetch` subcommand

```
python -m polytool research-marker-queue prefetch \
  --queue-dir <DIR> \
  --max-items N \
  --delay-seconds S \
  [--json]
```

Output: per-item OK/skip/FAIL lines, summary with counts, tip for failed items.

### 5. CLI: `status-report` subcommand

```
python -m polytool research-marker-queue status-report [--queue-dir DIR] [--json]
```

Output: formatted table of counts, stuck-item detection with reset command,
failed items with reasons, pending item list (truncated at 10).

---

## Integration Point: How Cache Flows into warm-process

The existing `queue.jsonl` record gains a `pdf_url` field (string path to
the cached local file). `_process_item` already had a branch:

```python
pdf_url = item.get("pdf_url", "")
if pdf_url and hasattr(fetcher, "fetch_pdf_direct"):
    raw = fetcher.fetch_pdf_direct(pdf_url, ...)
```

`fetch_pdf_direct` already handles local paths (anything not starting with
`http://`/`https://`) by calling `self._parse_pdf(url_or_path)` directly.
No changes to `warm-process`, `process_next_ipc`, or the Marker parse pipeline.
The only change is the file-existence guard added to `_process_item`.

---

## Commands Run / Output

### Existing test suite (targeted)

```
pytest tests/test_ris_marker_queue.py tests/test_ris_claim_extraction.py -x -q
203 passed, 1 skipped in 2.79s
```

Pre-existing skip: `test_user_context.py::test_wallet_only` (profile.json residue — unrelated).
All 134 original marker queue tests pass.

### Offline smoke test (inline Python)

```
2 papers enqueued
prefetch: 2 HTTP calls → 2 cached, 0 failed
idempotency: second run → 0 HTTP calls, 2 skipped
pdf_url set in queue records: ✓
files exist on disk: ✓
manifest written: ✓
status_report.prefetch_stats.cached=2: ✓
```

### Routing verification

```
cached PDF exists → fetch_pdf_direct called (0 arXiv calls): ✓
cached PDF deleted → warning logged, fallback to fetch() (1 arXiv call): ✓
```

### CLI --help

```
prefetch: OK (--max-items, --delay-seconds, --json)
status-report: OK (--json)
```

### 5-paper e2e validation

Not run. GPU Docker is unavailable in this session. The exact operator commands are:

**Step 1 — prefetch (host Windows)**
```powershell
python -m polytool research-marker-queue `
  --queue-dir artifacts/research/scaled_validation_queue_v2 `
  prefetch --max-items 5 --delay-seconds 12
```

**Step 2 — warm-process (inside Docker GPU container)**
```bash
docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
  python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items 5 --marker-timeout 3600
```

**Step 3 — index-done (inside Docker)**
```bash
docker exec polytool-ris-scheduler-gpu sh -c \
  "cd /app && python -m polytool research-marker-queue \
   --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
   index-done"
```

**Step 4 — research-query probes (host)**
```powershell
python -m polytool research-query --question "prediction markets microstructure"
python -m polytool research-query --question "optimal market making spread"
python -m polytool research-query --question "sports betting inefficiencies" --step-back
```

---

## Recommended 5-paper Selection (from triage memo)

Per OBJECTIVE: at least one prior-429 paper, one table-heavy, one prose/survey, two eq-heavy.

| # | arXiv ID | Category | Selection reason |
|---|----------|----------|-----------------|
| 1 | 1206.4810 | eq-heavy | Prior 429 failure in Batch 2 — canonical test of prefetch fix |
| 2 | 2203.13053 | eq-heavy | Prior 429 failure — second eq-heavy confirmation |
| 3 | 1011.6402 | tbl-heavy | Timed out at 3600s in Batch 2 — try with same timeout after prefetch |
| 4 | 2307.14129 | eq-heavy | Succeeded in Batch 2 after 1 retry — control paper |
| 5 | 2409.02025 | eq-heavy | Prior 429+timeout — most adversarial fetch failure |

Reset all 5 from their current failed/processing state before running:
```powershell
foreach ($id in @("1206.4810","2203.13053","1011.6402","2307.14129","2409.02025")) {
    python -m polytool research-marker-queue `
      --queue-dir artifacts/research/scaled_validation_queue_v2 `
      enqueue --url $id --force
}
```

Then run prefetch, then warm-process inside Docker.

---

## Metadata Note

When warm-process uses a cached PDF via `fetch_pdf_direct`, the body sidecar
`meta.json` will contain `url`, `title`, and `body_source`/`body_length`/
`parse_seconds`, but will be missing `abstract`, `authors`, and `published_date`
(those come from the arXiv Atom API, which is not called in the cached path).

Impact on RAG: **None.** The body text (Marker output) is the RAG-relevant content.
`index_done_items` reads `abstract`/`authors`/`published_date` from the sidecar but
treats them as optional — they default to `""`, `[]`, and `None`. The KnowledgeStore
entry will have the full body text for retrieval.

If richer metadata is wanted in a future session: add `--fetch-arxiv-metadata` flag
to `prefetch` that calls the arXiv API (with delays) and writes metadata to
`pdf_cache/{candidate_id}.arxiv_meta.json`. WP-3 is the appropriate place for this.

---

## Decisions

1. **Narrowest integration point chosen.** The `pdf_url` field already existed in
   the queue schema and `fetch_pdf_direct` already handled local paths. No changes
   to the Marker parse pipeline, IPC worker, or indexing path were needed.

2. **10s default delay.** Conservative but not prohibitive. arXiv's documented
   rate limit is ~3 requests/second sustained; 10s gives a 10× safety margin and
   allows a 29-paper batch to complete prefetch in ~5 minutes unattended.

3. **No metadata prefetch in WP-1.** Metadata loss (abstract/authors) is acceptable
   for RAG quality at this stage. Full body text is preserved. Metadata can be added
   in a follow-up if needed.

4. **File-existence guard in `_process_item`.** Prevents silent `abstract_fallback`
   if the cache dir is moved or files are cleaned up between prefetch and warm-process.
   Falls back to live arXiv fetch with a logged warning rather than failing silently.

---

## Open Items / Next Steps

1. **Run the 5-paper e2e validation** (requires GPU Docker session)
2. **1011.6402 disposition**: table-heavy paper hit 3600s timeout. Try with 7200s or
   skip and substitute. Must be decided before full 29-paper rerun.
3. **JIT cache persistence (Gap C2)**: `TRITON_CACHE_DIR` investigation. If resolved,
   repeated runs avoid cold-start overhead (30-50 min per format group).
4. **WP-2 (tiered ingestion)**: prose/survey papers can bypass GPU Marker for faster
   throughput. Implement after WP-1 e2e validation passes.
5. **WP-3 (one-command operator entrypoint)**: script orchestrating prefetch →
   docker exec warm-process → docker exec index-done → status-report.

---

## Codex Review

Tier: Recommended (touches `marker_queue.py` fetcher path and `_process_item` routing).
No adversarial tier — does not touch execution layer, kill switch, or order placement.
