---
title: Academic Demo Ready Docs Unblock
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-25_academic-demo-ready-docs-unblock.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Academic Demo-Ready Docs Unblock — Stale CURRENT_STATE.md Fix

**Date:** 2026-05-25
**Scope:** Docs/verification only. No implementation, test, parser, queue, or benchmark changes.
**Codex BLOCK:** RESOLVED

---

## What Happened

Codex blocked the docs/queue triage (2026-05-26_codex-review-academic-demo-ready-docs-queue-triage.md)
with a single named issue: `docs/CURRENT_STATE.md` still contained a sentence describing
retrieval as "not semantic or vector retrieval" — a statement that directly contradicted
the L2.1 ChromaDB semantic retrieval COMPLETE status documented in that same file.

---

## Files Changed

### `docs/CURRENT_STATE.md`

**Location:** Query normalization paragraph in the RIS L2 Academic Query section (line 1923–1924 before fix).

**Stale phrase found:**
```
The original question string is preserved in the JSON output. Retrieval remains conservative
substring/phrase matching — not semantic or vector retrieval.
```

**Replacement:**
```
The original question string is preserved in the JSON output. Note: this normalization is
purely lexical/string preprocessing (preamble stripping before retrieval). Primary retrieval
is now ChromaDB semantic vector search (L2.1 — COMPLETE 2026-05-25, see below), with
KnowledgeStore lexical matching as fallback when semantic yields no results.
```

**Why this is the right fix:** The paragraph is about `_normalize_question()` / `_build_sub_queries()`,
which strip preamble words before passing the query to retrieval. That normalization step
is purely lexical/string preprocessing. The retrieval itself (ChromaDB semantic vector search
with lexical fallback) is separate and is correctly described in the L2.1 section below in
the same file. The old sentence conflated normalization with retrieval, making it sound
like the whole retrieval path was non-semantic, which is false since b921857.

---

## Verification: No Other Stale Phrases

Searched `docs/CURRENT_STATE.md` and `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` for:
- `not semantic`
- `not vector`
- `ChromaDB academic retrieval deferred`
- `semantic retrieval deferred`
- `lexical only`

Result: **No matches found in either file.** The runbook was already corrected before this
session (confirmed by Codex's passing checks). No additional fixes needed.

---

## Commands Run

### Chroma Link Check

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

**Result: CLEAN.** 162 chunks across 5 papers. No broken links. Identical to Codex's observation.

### Queue Status Report

```
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Key counts:
- `pending=18`
- `processing=1` (`arxiv:1011.6402`, `stuck_warning=true`)
- `done=5`
- `failed=5` (all at `attempts=3`: 3× timeout, 2× HTTP 429)
- `total=29`
- `prefetch_stats.cached=0`
- `sidecar_count=5`
- `indexed_count=0`

**Result: UNCHANGED from Codex's observation.** No degradation, no improvement. The queue is
in the same interrupted/unprepared state as when Codex reviewed it.

---

## Queue Reset Recommendation: UNCHANGED

The RESET recommendation from the Codex review remains valid and evidence-backed:

- One stuck `processing` item (`arxiv:1011.6402`): cannot safely resume
- Five failed items at `attempts=3`: exhausted, terminal — must be reset
- `prefetch_stats.cached=0`: pending PDFs not prefetched; JIT downloads during a
  long batch create timeout risk
- `indexed_count=0`: 5 done papers have sidecars (`sidecar_count=5`) but have not
  been indexed into KnowledgeStore — blind resume would skip them
- Mixing stale `processing`, terminal `failed`, unprefetched `pending`, and unindexed
  `done` states would contaminate validation metrics

RESET is safer than blind resume. RESET is safer than full rebuild (5 body sidecars
preserve valid Marker parse work; no need to discard them or re-spend GPU time).

**The queue reset is the next operational step. It is NOT being executed in this session.**

---

## Codex BLOCK Status

**RESOLVED.** The single named blocking issue — the stale CURRENT_STATE.md sentence — is fixed.

The Codex review's passing checks remain passing:
- Runbook L2.1/ChromaDB language: no deferred-retrieval language present
- Known-Good 3-paper section: accurate (3 done / 0 failed, body lengths 56,856 / 51,370 / 60,814,
  79 chunks, 373 claims, `had_fallback=false` for both query checks)
- NTFS caveat and Docker `index-done` requirement: present in runbook
- Production readiness: not overstated; 29-paper validation still described as paused/not yet run

---

## Is Queue Reset Safe to Prompt Next?

**Yes.** The Codex review explicitly stated RESET is evidence-backed and the next
operational step. Queue state is confirmed unchanged. No docs contradict the RESET plan.
The next session should execute the queue RESET sequence from the runbook:
1. Index/reindex the 5 done papers: `research-marker-queue index-done`
2. Force-reset stuck item (`arxiv:1011.6402`): `reset-item --candidate-id arxiv:1011.6402`
3. Force-reset 5 failed items: `reset-item` for each, or batch reset
4. Prefetch pending PDFs with delay before re-processing
5. Process in controlled cached batches

**Do not start the 29-paper cached validation without completing steps 1–4 first.**
