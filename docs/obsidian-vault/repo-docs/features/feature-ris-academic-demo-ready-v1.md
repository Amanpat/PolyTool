---
title: Ris Academic Demo Ready V1
type: reference
status: complete
completed: 2026-05-28
track: Research Intelligence System
layer: L1-L4 Academic
codex_verdict: PASS WITH CONCERNS
source_zone: repo
mirror_of: docs/features/FEATURE-ris-academic-demo-ready-v1.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Feature: RIS Academic Pipeline — Developer/Operator Demo-Ready v1

**Completed:** 2026-05-28
**Track:** Research Intelligence System — Academic PDF Ingestion + Semantic Retrieval
**Codex verdict:** PASS WITH CONCERNS — demo-ready v1 approved with named caveats
**Readiness level:** Developer/operator demo-ready. **NOT production-ready.** See caveats.

---

## What This Feature Delivers

Developer/operator demo-ready v1 of the full Academic RIS pipeline:

| Layer | Component | Status |
|-------|-----------|--------|
| L1 | Marker PDF parse queue (enqueue → warm-process → inspect) | Complete 2026-05-09 |
| L1 | IPC warm-worker (persistent GPU session across papers) | Complete 2026-05-08 |
| L1 | PDF prefetch separation (WP-1) | Complete 2026-05-22 |
| L2 | `research-query` CLI with KS lexical retrieval | Complete 2026-05-09 |
| L2.1 | ChromaDB semantic vector retrieval as primary path | Complete 2026-05-25 |
| L4 | Multi-source harvesters (arXiv, Semantic Scholar, Crossref, OpenReview) | Complete 2026-05-09 |

This closeout consolidates evidence across all prior work packets (WP-1, WP-2/L2.1, 3-paper
validation, Batch A, Batch B) into a single demo-ready v1 milestone record.

---

## Operator Path Summary

```text
# Step 1 — Enqueue papers (Windows host)
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  enqueue --url arxiv:XXXX.XXXXX

# Step 2 — Prefetch PDFs (Windows host, before GPU session)
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  prefetch

# Step 3 — Parse with IPC warm-worker (inside Docker GPU container)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu sh -c \
  "cd /app && python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  warm-process --max-items N --marker-timeout 7200"

# Step 4a — Index into KnowledgeStore (inside Docker GPU container)
docker compose --profile ris-gpu run --rm ris-scheduler-gpu sh -c \
  "cd /app && python -m polytool research-marker-queue \
  --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
  index-done"

# Step 4b — Embed into Chroma (Windows host — Docker image lacks chromadb)
python -m polytool research-marker-queue \
  --queue-dir artifacts/research/scaled_validation_queue_v2 \
  index-done --reindex-chroma --force

# Step 5 — Verify Chroma links (Windows host)
python -m polytool research-marker-queue check-chroma-links --json

# Step 6 — Query
python -m polytool research-query --question "market microstructure limit order book"
```

Full runbook: `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`

---

## Evidence Chain

### Original 3-Paper Operator Validation (2026-05-09)

First functional end-to-end pass using the Windows/local warm-thread path
(`ipc_warm_worker_used=false`).

- Queue: 3 done, 0 failed
- 79 chunks, 373 claims
- `research-query` returned `had_fallback=false` for both test queries

### WP-1 — PDF Prefetch Separation (2026-05-22)

Separated arXiv PDF download from GPU parse to eliminate arXiv API rate-limit failures
during warm-process. Verified with arxiv:2510.05533: prefetch → 16.4s parse (no arXiv
API call during parse) → 34 chunks, 167 claims → query returns `had_fallback=False`.

### WP-2 / L2.1 — ChromaDB Semantic Retrieval (2026-05-25)

ChromaDB vector search shipped as the primary retrieval path. `_embed_body_into_chroma()`,
`--reindex-chroma` CLI flag, and `check-chroma-links` subcommand added.

3-paper category sample PASS:

| Category | arXiv ID | Top-1 hit rate | had_fallback | Verdict |
|----------|----------|----------------|--------------|---------|
| Prose / survey | 2510.05533 | 3/3 | False all | PASS |
| Equation-heavy | 1106.5040 | 2/3 | False all | PASS |
| Table-heavy | 1609.03471 | 2/3 | False all | PASS |
| Rejection guard | — | n/a | True | PASS |

Chroma link-check at sample completion: 162 chunks / 5 papers / 0 missing / 0 orphaned.

### Batch A — Small Papers (5 papers, pre-Batch-B)

5 small papers parsed and indexed into `scaled_validation_queue_v2`. All `status=done`,
`marker_ready=True`. Accumulated in queue before Batch B run.

### Batch B — Medium Papers (2026-05-28)

10 medium-complexity arXiv papers parsed, indexed, Chroma-embedded, and query-verified.

| arXiv ID | body_length | parse_seconds | marker_ready | KS chunks | KS claims |
|----------|-------------|--------------|-------------|-----------|-----------|
| 1206.4810 | 89,163 | 1245.3 | True | 44 | 214 |
| 2003.05958 | 130,920 | 3248.9 | True | 53 | 249 |
| 2203.13053 | 97,745 | 3055.9 | True | 39 | 194 |
| 1810.04383 | 116,221 | 2269.7 | True | 44 | 215 |
| 1609.03471 | 61,281 | 58.5 | True | 29 | 145 |
| 2605.11640 | 181,670 | 73.0 | True | 69 | 345 |
| 2605.02286 | 42,701 | 31.0 | True | 18 | 86 |
| 2605.00493 | 138,768 | 33.4 | True | 58 | 288 |
| 2208.13564 | 42,256 | 53.9 | True | 20 | 100 |
| 2605.10400 | 313,516 | 2132.4 | True | 131 | 654 |
| **TOTAL** | **1,214,241** | **12,202s** | **10/10** | **505** | **2490** |

---

## Batch B Metrics Summary

| Metric | Value |
|--------|-------|
| Queue: done | 20 (10 pre-existing + 10 Batch B) |
| Queue: failed | 0 |
| Queue: sidecar_count | 20 |
| Batch B: marker_ready=True | 10/10 |
| Batch B: ipc_warm_worker_used=True | 10/10 |
| Batch B: KS chunks | 505 |
| Batch B: KS claims | 2490 |
| Chroma: total_chunks | 917 |
| Chroma: unique_papers | 21 |
| Chroma: missing_ks_doc_id | 0 |
| Chroma: ks_doc_id_not_in_ks | 0 |
| Topic probes (7) had_fallback | False (all) |
| Topic probes (7) retrieval_mode | semantic (all) |
| Unrelated rejection (protein folding) | had_fallback=True ✅ |

---

## Demo-Ready Scope

"Developer/operator demo-ready v1" means:

- Full pipeline from arXiv URL to semantic retrieval works end-to-end on the dev machine.
- An operator can enqueue papers, run warm-process in Docker GPU, index into KnowledgeStore,
  embed into Chroma on the Windows host, and query with semantic results.
- 20 papers, 917 Chroma chunks, 21 unique papers, clean link-check — corpus is meaningful
  enough to demonstrate retrieval quality.
- Codex independently verified parse evidence, Chroma state, and 5 query probes.
- Result quality is suitable for operator review and research investigation.

This is NOT a production service. The pipeline requires operator supervision for each
batch, manual Chroma embedding on the Windows host, and human-in-the-loop Tier-3 approval.

---

## Explicit Caveats

**Caveat 1 — Lexical false positive (`weather forecast`)**

`research-query --question "weather forecast"` returns 1 lexical citation from
`arxiv:2605.00493` because that paper explicitly mentions weather forecasts as a control
category in a prediction market experiment. The semantic guard is working correctly
(retrieval_mode=lexical, not semantic). The false positive is in the lexical fallback path
over real relevant paper text. This is a post-v1 hardening item — not a v1 blocker.

**Caveat 2 — Chroma embedding requires Windows host**

The `ris-scheduler-gpu` Docker image lacks `chromadb` and `sentence-transformers`
(removed from `[rag]` extras in quick-260405-jyv). Chroma embedding must run on the
Windows host via `index-done --reindex-chroma --force`. The NTFS colon restriction in
body file names is handled by the `cid.replace(":", "")` fallback in `index_done_items`.
This is operational friction, not a corpus correctness defect.

**Caveat 3 — JIT cache persistence unresolved**

`TORCHINDUCTOR_CACHE_DIR` was confirmed empty after batch runs in prior sessions.
In-session JIT reuse works (fast papers 2+ in the same warm-process run), but
cross-restart persistence is not confirmed. Run `jit-cache-check` before large batches.
This affects Batch C/D planning, not demo-ready v1.

**Caveat 4 — Batch C/D deferred; Tier-3 approval required**

9 pending papers remain in `scaled_validation_queue_v2` (Tier-3/large):
`arxiv:2409.02025` (HTTP 429 failures), `arxiv:1011.6402` (3600s timeout), and 7 others.
Do NOT run Batch C/D without JIT cache verification and Tier-3 operator approval for
`arxiv:2409.02025` and `arxiv:1011.6402`. Batch C/D is post-v1 work.

---

## Post-v1 Hardening Backlog

| Item | Priority | Description |
|------|----------|-------------|
| Lexical false positive fix | Medium | Improve unrelated-query rejection in lexical fallback path |
| Chroma Docker gap | Medium | Add `chromadb` to `ris-scheduler-gpu` image or document Windows-host path permanently |
| JIT cache persistence | Low | Verify TRITON_CACHE_DIR and confirm cross-restart cache reuse |
| Batch C/D | Low | 7 large papers after Tier-3 approval and JIT cache verification |
| Snippet quality | Low | Table-heavy papers return reference-section snippets; post-v1 cleanup |
| Bulk pdfplumber corpus cleanup | Deferred | Re-ingest legacy pdfplumber-parsed docs as Marker |

---

## Related Docs

| Doc | Purpose |
|-----|---------|
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Full operator path, queue states, recovery |
| `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md` | L1 DoD evidence |
| `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md` | IPC warm-worker v1 |
| `docs/features/FEATURE-ris-l2-academic-query.md` | research-query control flow |
| `docs/features/FEATURE-ris-l4-multisource-academic-harvesters.md` | L4 harvesters |
| `docs/dev_logs/2026-05-28_academic-scaled-validation-batch-b.md` | Batch B validation evidence |
| `docs/dev_logs/2026-05-28_codex-review-academic-batch-b-closeout.md` | Codex PASS WITH CONCERNS verdict |
| `docs/dev_logs/2026-05-28_academic-ris-demo-ready-v1-closeout.md` | This closeout log |
