# L3.2 Prefetch Label Discovery — Implementation Log

**Date:** 2026-05-05  
**Track:** Research Intelligence System (L3)  
**Work packet:** L3.2 — Prefetch Label Discovery Mode  
**Status:** Complete

---

## Objective

Enable label accumulation without downloading PDFs.  The existing
`research-acquire` pipeline downloads PDFs and runs Marker before any
relevance scoring.  This blocked fast label accumulation for SVM training.

L3.2 adds a metadata-only discovery path: search arXiv title + abstract via
the Atom API, score each candidate with the existing `RelevanceScorer`, and
enqueue matching candidates to the existing `ReviewQueueStore`.

---

## Files Changed

| File | Change |
|------|--------|
| `tools/cli/research_prefetch_discover.py` | **New** — CLI for L3.2 discovery |
| `packages/research/relevance_filter/queue_store.py` | `force: bool = False` param added to `enqueue()` |
| `polytool/__main__.py` | Registered `research-prefetch-discover` command |
| `tests/test_ris_prefetch_discovery.py` | **New** — 36 offline tests |

---

## Command Syntax

```bash
# Minimal — queue REVIEW candidates from arXiv metadata search
python -m polytool research-prefetch-discover --search "prediction markets microstructure"

# Also queue ALLOW candidates (positive labels for SVM)
python -m polytool research-prefetch-discover \
  --search "limit order book dynamics" \
  --include-allow \
  --max-results 30

# Queue everything for bulk labeling
python -m polytool research-prefetch-discover \
  --search "market making strategy" \
  --decision-filter all

# Re-discover with updated filter config (override idempotency)
python -m polytool research-prefetch-discover \
  --search "avellaneda-stoikov" \
  --force

# Dry-run: see what would be queued without writing
python -m polytool research-prefetch-discover \
  --search "prediction market microstructure" \
  --dry-run

# JSON output for scripting
python -m polytool research-prefetch-discover \
  --search "prediction markets" \
  --json

# After discovery, label via existing tool
python -m polytool research-prefetch-review counts
python -m polytool research-prefetch-review list
python -m polytool research-prefetch-review label <CANDIDATE_ID> allow
```

---

## Metadata-Only Guarantee

`arxiv_search_metadata_only()` is a standalone function in `research_prefetch_discover.py`
that calls only:

```
http://export.arxiv.org/api/query?search_query=all:<encoded>&max_results=N
```

It parses the Atom XML for title, abstract, canonical URL, authors, and
published\_date.  It **never** calls `_fetch_pdf_body()`, never imports
`LiveAcademicFetcher`, and never touches Marker or pdfplumber.

The `TestNoPDFDownload` test class enforces this: it injects a tracking
HTTP function and asserts no `.pdf` URLs are called, and that exactly one
HTTP call is made per run.

---

## Queue Record Schema (compatible with existing format)

Existing required fields preserved:
`candidate_id`, `source_url`, `title`, `abstract`, `score`, `raw_score`,
`decision`, `reason_codes`, `matched_terms`, `allow_threshold`,
`review_threshold`, `config_version`, `created_at`

Discovery-specific additions (informational, non-breaking):
- `discovery_query` — the search string used
- `source_family` — always `"academic"` in v0
- `published_date` — arXiv publication date (if returned)
- `authors` — author list (if returned)

---

## Idempotency and `--force`

Default behavior: `ReviewQueueStore.enqueue()` skips records whose
`candidate_id` (`sha256(source_url)`) already exists in the queue.

The `force: bool = False` addition to `enqueue()` allows bypassing this
check.  With `--force`, each run writes a fresh record even if the URL was
previously queued.  This is useful after updating the filter config to
re-score candidates with new thresholds.

---

## Decision Filter Logic

| Flag | Queued decisions |
|------|-----------------|
| (default) | `review` |
| `--include-allow` | `review`, `allow` |
| `--decision-filter review` | `review` |
| `--decision-filter allow,review` | `review`, `allow` |
| `--decision-filter all` | `allow`, `review`, `reject` |
| `--decision-filter reject` | `reject` |

`--decision-filter` takes full precedence over `--include-allow`.

---

## Tests Run

```
python -m pytest tests/test_ris_relevance_filter.py tests/test_ris_prefetch_discovery.py -v
```

Target: all pass, 0 failures.  36 new tests in `test_ris_prefetch_discovery.py`:

- `TestArxivSearchMetadataOnly` (11 tests) — search function unit tests
- `TestParseDecisionFilter` (7 tests) — decision filter parsing
- `TestDiscoverMainDefaultBehavior` (5 tests) — default REVIEW-only mode
- `TestIncludeAllow` (2 tests) — --include-allow flag
- `TestDecisionFilter` (4 tests) — --decision-filter override
- `TestIdempotency` (2 tests) — duplicate skipping and --force re-queue
- `TestDryRun` (2 tests) — --dry-run writes nothing
- `TestJsonOutput` (2 tests) — JSON summary structure
- `TestEmptyResults` (2 tests) — zero-result arXiv response
- `TestNetworkError` (1 test) — HTTP failure returns exit code 1
- `TestHumanReadableOutput` (4 tests) — console output
- `TestNoPDFDownload` (2 tests) — PDF regression guard
- `TestQueueRecordIntegration` (2 tests) — compatibility with research-prefetch-review

---

## Remaining Path to SVM Trigger

1. Use `research-prefetch-discover` to accumulate REVIEW candidates in queue.
2. Use `--include-allow` sessions to accumulate ALLOW candidates too.
3. Label via `research-prefetch-review label <ID> allow|reject`.
4. Monitor progress: `research-prefetch-review counts`.
5. SVM trigger: `research-health` shows ≥30 allow AND ≥30 reject in
   `artifacts/research/svm_filter_labels/labels.jsonl`.
6. L3 v1 training: SPECTER2 + S2FOS embeddings + SVM (future work packet).

---

## Codex Review

Scope: new CLI file + enqueue() force param.  No execution-layer code touched.
Codex review: SKIP (docs/config/CLI + queue utility — not in mandatory tier).
