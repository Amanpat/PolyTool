---
title: Academic Demo Ready Docs Queue Triage
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_academic-demo-ready-docs-queue-triage.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic RIS Demo-Ready v1 — Docs Triage and Queue Decision

**Date:** 2026-05-25
**Author:** Claude Code (Sonnet 4.6)
**Track:** Research Intelligence System — Operator Readiness
**Status:** COMPLETE — docs corrected; queue decision issued; 29-paper validation NOT yet safe

---

## Objective

Close the Academic RIS demo-ready v1 Codex PASS WITH CONCERNS without running the 29-paper
validation. Two goals:

1. Correct four stale-text issues in the runbook and CURRENT_STATE.md identified by Codex.
2. Inspect `scaled_validation_queue_v2` and produce an explicit RESUME / RESET / REBUILD
   recommendation.

Scope: docs and triage only. No implementation, no GPU parsing, no retrieval/parser behavior
changes, no benchmark baseline edits, no 29-paper execution.

---

## Prior Context

- **L2.1 semantic retrieval shipped** (commit `b921857`, 2026-05-25): ChromaDB `academic_papers`
  vector search is now the primary path for `research-query`. Lexical KS fallback activates only
  when no Chroma chunk exceeds `min_similarity=0.18`.
- **3-paper category sample PASS** (commit `c249ff5`, 2026-05-25): prose/survey, equation-heavy,
  and table-heavy categories all retrieve correctly with `retrieval_mode=semantic`.
- **Codex PASS WITH CONCERNS**: 4 runbook inaccuracies flagged. Operator-path fix commits
  (flag order, delay-seconds, docker exec→run --rm) already applied. Four remaining issues
  were all documentation accuracy only.

---

## Stale Text Corrected

### 1. `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` — Routing box

**Issue:** The runbook presented two parallel operator paths (Quick Start / WP-1 prefetch and
Operator Path / pre-WP-1 end-to-end) with no guidance on which to follow for a first-time run.
A non-coder opening the document sees two full sets of numbered steps with the distinction buried
in a blockquote.

**Fix:** Added a "Which path to follow" routing section immediately before the Quick Start
procedure:

```
> **First run or 1–3 papers** → skip to [Operator Path (end-to-end)] below.
> **Batches of 5+ papers** → use the [Prefetch then Parse] section immediately after this Quick Start.
```

### 2. `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` — Querying section retrieval description

**Issue:** The Querying section read:

> **Retrieval is conservative substring/phrase matching — not semantic or vector retrieval.**

This was accurate before L2.1. After L2.1, `retrieval_mode=semantic` is the normal case in the
3-paper category sample. The description was now incorrect.

**Fix:** Updated to:

> **Primary retrieval is semantic (ChromaDB `academic_papers` vector search — L2.1, complete
> 2026-05-25). Lexical KnowledgeStore fallback activates only when no Chroma chunks exceed the
> similarity threshold (`had_fallback=true`, `retrieval_mode=lexical`).**

### 3. `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` — Known-Good 3-Paper section caveats

**Issue A:** The Known-Good section still listed:

> - ChromaDB academic retrieval (L2.1) deferred.

L2.1 shipped on 2026-05-25.

**Fix:** Changed to:

> - ChromaDB academic retrieval (L2.1) — **COMPLETE 2026-05-25**. Semantic retrieval confirmed
>   in 3-paper category sample (prose/survey, equation-heavy, table-heavy).

**Issue B:** The Known-Good section documented the 2026-05-09 run which executed `index-done`
on the Windows host. The current runbook requires `index-done` to run inside Docker (NTFS colon
restriction discovered 2026-05-17). A reader using the Known-Good section as their reference
would reproduce a step that now fails on Windows.

**Fix:** Added NTFS caveat:

> - **NTFS caveat:** This 2026-05-09 run executed `index-done` on the Windows host, predating
>   the NTFS colon restriction discovery (2026-05-17). arXiv candidate IDs like `arxiv:1106.5040`
>   contain a colon; Windows Python cannot open `bodies/arxiv:1106.5040.body.txt`. The 2026-05-09
>   run succeeded because it used a queue without colon-bearing IDs. **Always run `index-done`
>   inside Docker** when using the GPU parse path on Windows.

### 4. `docs/CURRENT_STATE.md` — L2 Academic Query stale line

**Issue:** The "RIS L2 Academic Query" section still contained:

> **Still deferred:** ChromaDB academic retrieval, page-level citations, and LLM synthesis.

The ChromaDB academic retrieval line contradicted the L2.1 COMPLETE section elsewhere in the
same document.

**Fix:** Changed to:

> **ChromaDB academic retrieval (L2.1) — COMPLETE 2026-05-25** (see L2.1 section below).
> **Still deferred:** page-level citations and LLM synthesis.

---

## CLI Checks Run

### Chroma link-check

```
python -m polytool research-marker-queue check-chroma-links --json
```

Output:

```json
{
  "collection": "academic_papers",
  "chroma_path": "kb\\rag\\index",
  "total_chunks": 162,
  "unique_papers": 5,
  "valid_ks_doc_id": 162,
  "missing_ks_doc_id": 0,
  "ks_doc_id_not_in_ks": 0,
  "not_in_ks_doc_ids": []
}
```

**PASS.** All 162 chunks across 5 papers resolve to live KS documents. Zero orphans.

### `scaled_validation_queue_v2` counts

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 counts
```

Output:

```
pending: 18
processing: 1
done: 5
failed: 5
total: 29
```

### `scaled_validation_queue_v2` status-report

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Key fields from the output:

| Field | Value |
|---|---|
| pending | 18 |
| processing (stuck) | 1 — `arxiv:1011.6402` |
| done | 5 |
| failed | 5 |
| prefetch_stats.cached | 0 (no PDFs prefetched) |
| sidecar_count | 5 (done papers have body sidecars) |
| indexed_count | 0 (done papers NOT yet indexed into KS) |

**Stuck item:** `arxiv:1011.6402` is in `processing` state with no active worker. This item
has already triggered the `marker_timeout` guard in a prior session (confirmed 3600s timeout).
It will not self-recover; manual `--force` re-enqueue is required.

**Failure pattern:** All 5 failures are arXiv API metadata fetch failures (HTTP 429 / timeout
on `export.arxiv.org/api/query?...`). Not PDF parse or download failures. One of the 5 failed
items (`arxiv:1810.04383`) is already indexed via `smoke_test_queue` (44 Chroma chunks).

**Already-indexed papers in pending:** Two papers in the pending list (`arxiv:1609.03471`,
`arxiv:2510.05533`) are already indexed from other queues and present in Chroma. Running
`warm-process` on them again would re-parse (wasted GPU time) but `index-done` would skip them
as already indexed (idempotent).

---

## Queue Decision: RESET

### Why not RESUME

- The 5 failed items have exhausted their retry budget (3 attempts each). They will not
  auto-retry without `--force` re-enqueue.
- The 1 stuck processing item (`arxiv:1011.6402`) has no active worker and blocks queue counts.
- `prefetch_stats.cached = 0`: no prefetch has been run yet; all 18 pending papers are
  at risk of HTTP 429 during warm-process without prefetch.
- `indexed_count = 0`: the 5 done papers have valid body sidecars but have never been indexed
  into KS. Before scaling up, these should be indexed first (inside Docker for NTFS safety).

### Why not REBUILD

- The 5 done papers have valid body sidecars. Rebuilding would discard them and require
  re-parsing (GPU time, model reload overhead, arXiv rate limit exposure).
- The queue mechanism is intact; the failures are network-origin (metadata API), not queue
  corruption.

### RESET steps (operator action required, do not execute automatically)

**Prerequisites before any warm-process:**

1. **Index the 5 already-done papers** (inside Docker to avoid NTFS colon issue):
   ```
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
     sh -c "cd /app && python -m polytool research-marker-queue \
     --queue-dir /app/artifacts/research/scaled_validation_queue_v2 index-done"
   ```
   Expected: `5 indexed, 0 already-indexed, 0 no-body, 0 failed`.
   Then embed into Chroma:
   ```
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
     sh -c "cd /app && python -m polytool research-marker-queue \
     --queue-dir /app/artifacts/research/scaled_validation_queue_v2 index-done --reindex-chroma"
   ```

2. **Re-enqueue stuck item:**
   ```
   python -m polytool research-marker-queue \
     --queue-dir artifacts/research/scaled_validation_queue_v2 \
     enqueue --url arxiv:1011.6402 --force
   ```

3. **Re-enqueue 5 failed papers** (metadata fetch failures — safe to retry with delay):
   ```
   python -m polytool research-marker-queue \
     --queue-dir artifacts/research/scaled_validation_queue_v2 \
     enqueue --url arxiv:XXXXX --force
   ```
   (For each of the 5 failed arXiv IDs from `status-report`.)

4. **Prefetch all pending** with conservative delay to avoid 429:
   ```
   python -m polytool research-marker-queue \
     --queue-dir artifacts/research/scaled_validation_queue_v2 \
     prefetch --delay-seconds 15
   ```

5. **Warm-process** inside Docker (IPC GPU path, VRAM persistence):
   ```
   docker compose --profile ris-gpu run --rm ris-scheduler-gpu \
     sh -c "cd /app && python -m polytool research-marker-queue \
     --queue-dir /app/artifacts/research/scaled_validation_queue_v2 \
     warm-process --max-items 5 --auto-timeout"
   ```
   (Run in batches of 5; verify counts between batches.)

---

## Is 29-Paper Validation Safe to Schedule Next?

**No. The following must be resolved first:**

1. **RESET not yet executed.** The queue is in a partial state with 5 unindexed done papers,
   1 stuck item, 5 failed items, and 0 prefetched PDFs. The RESET steps above must complete
   before any validation run is meaningful.

2. **JIT cache persistence (WP-2) unresolved.** `TORCHINDUCTOR_CACHE_DIR` was confirmed empty
   in the batch 2 session. `TRITON_CACHE_DIR` has not yet been tested. Without confirmed JIT
   persistence, each warm-process session may incur full kernel recompilation overhead, adding
   10–15 minutes per paper for the first paper in each Docker session. The 29-paper run's
   elapsed time estimate is unreliable until this is measured.

3. **Timeout-risk papers require explicit Tier-3 handling:**
   - `arxiv:1011.6402` — confirmed 3600s timeout; must be assigned `--tier 3` with operator
     awareness before inclusion.
   - `arxiv:2307.14129` — confirmed 2947s in prior session; borderline; monitor closely.
   - `arxiv:2409.02025` — metadata fetch failures; confirm PDF accessibility before inclusion.
   These 3 should be staged separately from the main 26-paper batch and given explicit
   operator sign-off.

4. **`indexed_count = 0` for done papers.** The 5 already-parsed papers must be indexed and
   Chroma-embedded before the 29-paper count can be tracked correctly.

**When it is safe:** After RESET completes, JIT cache behavior is confirmed (or explicitly
accepted as unknown), and the 3 timeout-risk papers have a handling plan.

---

## Demo-Readiness Verdict (Unchanged from Codex)

**Developer/operator demo-ready v1.**

The following work for a developer demo today:

- Marker-ready papers already indexed (5 papers, 162 Chroma chunks).
- `check-chroma-links` confirms zero orphans.
- Semantic `research-query` works: `retrieval_mode=semantic`, `had_fallback=False` for
  relevant queries.
- Out-of-domain query rejection works: `had_fallback=True`, `citation_count=0`.
- 3-paper category discrimination confirmed: prose/survey, equation-heavy, table-heavy.

The runbook is now accurate for the current pipeline state. A developer can follow it,
read error messages, and adapt. A non-coder still needs the routing box guidance (now added)
and awareness of the NTFS Docker requirement (now documented).

---

## Files Changed

| File | Change |
|---|---|
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | Routing box added; Querying section retrieval description updated; Known-Good section L2.1/NTFS caveats updated |
| `docs/CURRENT_STATE.md` | L2 Academic Query stale "ChromaDB deferred" line corrected |
| `docs/dev_logs/2026-05-25_academic-demo-ready-docs-queue-triage.md` | This file (new) |

No code changes. No tests changed. No parser/retrieval behavior changes. No benchmark baselines
touched. No GPU parsing executed. No 29-paper validation run.

---

## Open Items

1. **Queue RESET** — operator action required (Steps 1–5 above).
2. **WP-2 JIT cache measurement** — `TRITON_CACHE_DIR` test pending.
3. **Timeout-risk paper handling** — explicit Tier-3 plan for `1011.6402`, `2307.14129`,
   `2409.02025` before 29-paper run.
4. **Snippet quality pass** — references-section snippet pattern (probe 3a from 3-paper sample)
   deferred; tracked open item, does not block indexing or retrieval validation.
5. **Orphaned dev logs** — several 2026-05-23 and 2026-05-25 dev logs remain uncommitted. Commit
   in a standalone `docs(ris): commit orphaned L2.1 dev logs` before starting the 29-paper run.
6. **Root-doc dirty state** (`AGENTS.md`, `claude.md`) — still dirty per git status; Director
   review required before committing.
