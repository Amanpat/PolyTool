# Dev Log: README Academic RIS How-To Section

**Date:** 2026-05-29
**Scope:** Docs-only. No implementation code, tests, runtime artifacts, Batch C/D, benchmark baselines, or unrelated files changed.
**Triggered by:** Academic RIS developer/operator demo-ready v1 formally closed (2026-05-28).

---

## Objective

Add a concise operator how-to section to `README.md` so a Director/operator can understand what the Academic RIS pipeline does, how to run the happy path, how to verify success, and where to find the full runbook — without reading dev logs.

---

## Files Changed

| File | Change |
|------|--------|
| `README.md` | Added "Academic RIS: research paper ingestion and querying" section under Quick Workflows |

No other files were changed.

---

## Section Added

**Heading:** `### Academic RIS: research paper ingestion and querying`

**Location in README:** After the existing "RIS pre-build precheck" workflow block, before the "Crypto pair bot" block.

**Content:**
1. **What it does** — plain-English description: ingest arXiv papers, parse with Marker (GPU), index into KnowledgeStore, embed into ChromaDB, query with semantic retrieval + lexical fallback.
2. **Status** — explicitly stated: developer/operator demo-ready v1; NOT production-ready. Link to feature doc.
3. **Prerequisites** — `pip install -e ".[all]"`, Docker with GPU for Marker, `kb/` and `artifacts/` created by bootstrap.
4. **Happy-path commands** — 8 numbered steps covering enqueue, prefetch, status-report, warm-process reference (Docker — linked to runbook), index-done, index-done --reindex-chroma, check-chroma-links, research-query.
5. **Success checks** — marker_ready=True, body sidecar exists, check-chroma-links 0 missing/orphaned, query returns retrieval_mode semantic or lexical.
6. **Known caveats** — all 4 Codex-verified caveats included: not production-ready, Chroma Docker gap, lexical false positive, JIT cache, Batch C/D deferred.
7. **Links** — feature doc and runbook linked.

---

## Commands Documented

All CLI names verified against `python -m polytool research-marker-queue --help` and `python -m polytool research-query --help` before writing:

- `research-marker-queue ... enqueue`
- `research-marker-queue ... prefetch`
- `research-marker-queue ... status-report`
- `research-marker-queue ... index-done`
- `research-marker-queue ... index-done --reindex-chroma`
- `research-marker-queue check-chroma-links --json`
- `research-marker-queue jit-cache-check`
- `research-query --question "..."`

The Docker `warm-process` and container-side `index-done` commands were referenced with a pointer to the runbook rather than duplicating the full `docker compose` invocation.

---

## Links Verified

| Link | Status |
|------|--------|
| `docs/features/FEATURE-ris-academic-demo-ready-v1.md` | EXISTS |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | EXISTS |
| `docs/CURRENT_STATE.md` | EXISTS |

---

## Caveats Included

All four Codex-verified caveats from the feature doc are preserved:
1. Not production-ready (operator supervision required for each batch).
2. Chroma embedding requires Windows host (Docker image lacks chromadb).
3. Lexical false positive (weather forecast / prediction-market paper — post-v1 item).
4. JIT cache persistence unconfirmed; Batch C/D deferred pending Tier-3 approval.

---

## What Was NOT Touched

- No implementation code.
- No tests.
- No runtime artifacts.
- No Batch C/D trigger.
- No benchmark baselines.
- No validation runs.
- No other docs or vault files.
- No new behavior or speculative commands added.

---

## Confirmation

`README.md` grep confirms section present at line 311. All referenced doc links confirmed to exist on disk.
