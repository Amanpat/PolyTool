---
tags: [work-packet, ris, ingestion, filtering, completed]
date: 2026-05-05
activated: 2026-05-05
completed: 2026-05-05
status: completed
priority: high
phase: 2
target-layer: 3.2
parent-architecture: "[[11-Scientific-RAG-Target-Architecture]]"
parent-decision: "[[Decision - Scientific RAG Architecture Adoption]]"
prerequisites:
  - "[[Work-Packet - Pre-fetch SVM Topic Filter]] (L3 + L3.1 — shipped 2026-05-02)"
  - "Label store and ReviewQueueStore shipped (L3.1 — `artifacts/research/svm_filter_labels/labels.jsonl`)"
---

# Work Packet (completed) — L3.2 Prefetch Label Discovery Mode

> [!SUCCESS] Completed — 2026-05-05
> L3.2 shipped and SVM trigger reached.
> Final label state: **30 allow / 31 reject / 1 pending unlabeled** (pending does not block SVM readiness).
> SVM trigger (≥30 allow + ≥30 reject): **MET**.
> Next packet: L3 v1 SVM Topic Filter Readiness + Training.

> [!NOTE] Activation context — 2026-05-05
> Activated because `research-acquire` is no longer an effective label accumulation path.
> The Marker-only academic indexing gate (shipped in queue v0, 2026-05-05) blocks
> non-Marker candidates from indexing — meaning many candidates that would be
> useful label examples are rejected before they ever reach the review queue.
>
> Activation label state: **7 allow / 20 reject**. SVM trigger: **≥30 allow + ≥30 reject**.
> L3.2 provided a dedicated metadata-only discovery path that populated the review queue
> directly, without touching PDF download, Marker, or the ingest/index pipeline.

---

## Layer

Layer 3.2 of the [[11-Scientific-RAG-Target-Architecture|four-layer scientific RAG target]].
This is a sub-mode of L3, not a new layer. It extends the existing `ReviewQueueStore`
and `LabelStore` infrastructure shipped in L3.1.

---

## Goal

Build a metadata-only candidate discovery command that:

1. Searches arXiv (or equivalent academic metadata API) for candidate papers.
2. Scores each candidate using the existing `RelevanceScorer` (same filter logic as L3/L3.1).
3. Enqueues ALLOW and REVIEW candidates to the `ReviewQueueStore` for operator label decisions.
4. Operates without any PDF download, Marker parse, indexing, or document record creation.

This is a **label accumulation path**, not an ingestion path.

---

## Why This, Why Now

The problem with using `research-acquire --prefetch-filter-mode hold-review` for label accumulation:

- `research-acquire` downloads PDFs, calls Marker, and creates document records.
- The Marker-only academic gate (`IngestPipeline.ingest_external()`) now blocks all non-Marker
  bodies from reaching canonical embeddings — this is correct for production ingest but means
  many borderline-relevant candidates never generate a useful label example.
- Cold Marker parse takes ~85s per paper minimum (cold-start GPU). Running the full ingest
  pipeline to collect labels is expensive and slow.
- REVIEW candidates (borderline score 0.35–0.80) are the most valuable for SVM training.
  These are also the papers most likely to be caught by Marker's structural parser requirements.

L3.2 fixes this by decoupling label collection from ingestion. A paper can become a label
example without ever being ingested.

---

## Non-Goals

The following are explicitly out of scope for L3.2:

- **No PDF download** — metadata only (title, abstract, authors, arXiv ID).
- **No Marker parse** — no `MarkerPDFExtractor`, no `research-marker-queue` interaction.
- **No ingest / index** — no new document records, no chunks, no embeddings.
- **No SVM training** — labels accumulate; model training is the L3.3/v1 trigger.
- **No L2 activation** — PaperQA2 RAG Control Flow remains a stub; do not touch it.
- **No L4 harvesters** — Multi-source Academic Harvesters remain a stub; do not touch them.
- **No n8n / trading / Docker** — this packet is pure Python core + CLI.

---

## Acceptance Gates

All five gates must pass before L3.2 is declared shipped:

| Gate | Description |
|------|-------------|
| 1 | Command discovers candidates from arXiv metadata (title + abstract available without PDF fetch) |
| 2 | Every discovered candidate is scored using the existing `RelevanceScorer` with the live `config/research_relevance_filter_v1.json` config |
| 3 | Candidates are enqueued to `ReviewQueueStore` with `score`, `raw_score`, `decision`, `reason_codes`, `matched_terms`, and `source_url` fields |
| 4 | Duplicate candidate IDs (same arXiv ID or SHA-256 of URL) are idempotent — re-discovery does not create duplicate queue entries |
| 5 | No new document records or chunk records are created as a side effect of discovery |

**Operator success condition:** After running L3.2 discovery sessions, operator can use
`research-prefetch-review label` to reach ≥30 allow + ≥30 reject labels in
`artifacts/research/svm_filter_labels/labels.jsonl`, satisfying the SVM trigger.

---

## Design Sketch

New CLI command (suggested name): `research-prefetch-discover`

```
python -m polytool research-prefetch-discover \
  --query "prediction market microstructure" \
  --source arxiv \
  --max-candidates 50 \
  [--filter-config config/research_relevance_filter_v1.json] \
  [--review-queue-dir artifacts/research/prefetch_review_queue] \
  [--dry-run]
```

Internal flow:

1. Call arXiv Search API (or arXiv metadata API) — title + abstract, no PDF.
2. For each result: construct `CandidateInput(title=..., abstract=...)`.
3. Call `RelevanceScorer.score(candidate)` → `FilterDecision`.
4. If `decision == "allow"` or `decision == "review"`: call `ReviewQueueStore.enqueue(...)`.
5. If `decision == "reject"`: log to stderr, do NOT enqueue.
6. Print summary: N discovered, N allow-enqueued, N review-enqueued, N rejected, N duplicates.

Dry-run mode: score and print decisions; do not write to queue.

---

## Artifact Paths (unchanged from L3.1)

| Artifact | Path | Purpose |
|----------|------|---------|
| Hold-review queue | `artifacts/research/prefetch_review_queue/review_queue.jsonl` | ALLOW + REVIEW candidates held for operator labeling |
| Label store | `artifacts/research/svm_filter_labels/labels.jsonl` | Operator allow/reject labels for SVM training |
| Filter audit | `artifacts/research/acquisition_reviews/filter_decisions.jsonl` | All filter decisions (optional for L3.2 discovery) |

---

## Deferred: Marker Docker/Linux IPC Warm-Worker (Option A)

> [!SUCCESS] Marker Docker IPC Warm-Worker v1 — Feature 3 Closed 2026-05-08
> The Marker Docker/Linux IPC warm-worker (Queue v1, Option A) was deferred 2026-05-05
> when queue v0 shipped. It was subsequently activated as Feature 3 on 2026-05-07 and
> **closed 2026-05-08** under the revised functional gate.
>
> **Original ≤10s/paper timing gate rejected as unrealistic (Director 2026-05-08).** Revised
> gate: ≥3 full PDFs in one warm session; papers 2+ delta (total_seconds − parse_seconds) ≤5s;
> `body_source=marker`; `ipc_warm_worker_used=true`; no pdfplumber fallback; clean shutdown.
> Measured timings preserved: paper 1 delta=26.76s (cold-load), paper 2 delta=0.13s, paper 3 delta=0.22s.
>
> **L1 warm-worker blocker resolved. Next L1 rollout/readiness step requires a separate workpacket/Director decision.**
> See `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`.

---

## Cross-References

- [[11-Scientific-RAG-Target-Architecture]] — parent design
- [[Work-Packet - Pre-fetch SVM Topic Filter]] — L3 + L3.1 base infrastructure (shipped)
- `docs/features/FEATURE-ris-prefetch-relevance-filter-v0.md` — canonical L3/L3.1 feature doc
- `packages/research/relevance_filter/scorer.py` — `RelevanceScorer`, `CandidateInput`, `FilterDecision`
- `packages/research/relevance_filter/queue_store.py` — `ReviewQueueStore`, `LabelStore`
- `tools/cli/research_prefetch_review.py` — `research-prefetch-review list/label/counts`
- `config/research_relevance_filter_v1.json` — active filter config (v1.1)
- `docs/dev_logs/2026-05-05_l3-2-prefetch-label-discovery-activation.md` — activation dev log
