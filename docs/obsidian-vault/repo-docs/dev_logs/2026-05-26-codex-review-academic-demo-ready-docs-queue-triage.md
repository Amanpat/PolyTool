---
title: Codex Review Academic Demo Ready Docs Queue Triage
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-26_codex-review-academic-demo-ready-docs-queue-triage.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Codex Review - Academic Demo-Ready Docs Queue Triage

**Date:** 2026-05-26
**Reviewer:** Codex
**Scope:** Review only. No implementation, parser/retrieval behavior, benchmark baseline, GPU parse, corpus validation, or 29-paper artifact changes.
**Verdict:** BLOCK

---

## Files Reviewed

- `CLAUDE.md`
- `AGENTS.md`
- `docs/CURRENT_DEVELOPMENT.md`
- `docs/CURRENT_STATE.md`
- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`
- `docs/dev_logs/2026-05-09_ris-academic-pipeline-3paper-operator-validation.md`
- `docs/dev_logs/2026-05-25_codex-review-academic-3paper-and-operator-tests.md`
- `docs/dev_logs/2026-05-25_academic-3paper-category-sample.md`
- `docs/dev_logs/2026-05-25_academic-demo-ready-docs-queue-triage.md`

Artifacts inspected through CLI evidence only:

- `kb/rag/index` via `check-chroma-links`
- `artifacts/research/scaled_validation_queue_v2` via `status-report`

---

## Commands Run

```text
git status --short
```

Result: dirty tree was not narrow overall. It includes modified root docs (`AGENTS.md`, `claude.md`), `docs/CURRENT_STATE.md`, `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`, many `docs/obsidian-vault` modifications/deletions/untracked files, and multiple untracked RIS dev logs. This review did not modify or revert those files.

```text
git log --oneline -5
```

Result:

```text
c249ff5 docs(ris): operator-path simplicity test - 9 runbook corrections, readiness verdict
b921857 fix(ris): L2.1 one-paper acceptance repair - Chroma embed, span strip, NTFS fallback
7fc6bf2 fix(ris): L2.1 Deliverable B - offline-safe semantic fallback, resolves Codex BLOCK
15ef471 docs(ris): repo hygiene before L2.1 Deliverable A - closeout log
3348e79 feat(ris): L2.1 Deliverable C - display-only snippet sanitation
```

```text
python -m polytool --help
```

Result: exit 0; CLI loaded and listed `research-marker-queue` and `research-query`.

```text
git diff -- docs/CURRENT_STATE.md docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
```

Result: narrow targeted doc diff in these two files: `docs/CURRENT_STATE.md` adds/updates L2.1 complete language; `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` adds path routing, semantic retrieval wording, L2.1 Known-Good correction, and NTFS caveat.

```text
git diff --name-only b921857..HEAD
```

Result:

```text
docs/dev_logs/2026-05-25_academic-operator-path-test.md
docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md
```

```text
python -m polytool research-marker-queue check-chroma-links --json
```

Result:

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

```text
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

Result summary:

```text
pending=18
processing=1
done=5
failed=5
total=29
processing_items=["arxiv:1011.6402"]
stuck_warning=true
prefetch_stats.cached=0
prefetch_stats.failed=0
sidecar_count=5
indexed_count=0
failed attempts=3 for all 5 failed items
```

Failed items:

```text
arxiv:1206.4810 - metadata timeout, attempts=3
arxiv:2003.05958 - metadata timeout, attempts=3
arxiv:2203.13053 - HTTP 429, attempts=3
arxiv:1810.04383 - HTTP 429, attempts=3
arxiv:2409.02025 - metadata timeout, attempts=3
```

```text
rg -n "L2\\.1|ChromaDB|deferred|not semantic|vector retrieval|Known-Good|56,856|51,370|60,814|79|373|had_fallback|production-ready|demo-ready|operator-ready|non-coder|validation" docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md docs/CURRENT_STATE.md docs/dev_logs/2026-05-25_academic-demo-ready-docs-queue-triage.md
```

Result: found the runbook L2.1/Chroma corrections, matching Known-Good counts, and one remaining stale `docs/CURRENT_STATE.md` line saying retrieval is "not semantic or vector retrieval."

---

## Docs Verdict

**BLOCK.** The runbook correction itself is mostly sound, but stale state-doc text remains.

Passing checks:

- `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` no longer says L2.1/ChromaDB academic retrieval is deferred in the Querying or Known-Good 3-Paper sections.
- The Known-Good 3-paper section matches the actual 2026-05-09 sample: 3 done / 0 failed; paper body lengths 56,856 / 51,370 / 60,814; chunks 25 / 23 / 31; claims 125 / 115 / 133; totals 79 chunks and 373 claims; both query checks had `had_fallback=false`.
- The runbook now includes the Windows/NTFS caveat and Docker `index-done` requirement.
- The docs do not overstate full production readiness for the 29-paper run; they continue to call the large corpus paused/not yet safe.

Blocking issue:

- `docs/CURRENT_STATE.md` still says: `Retrieval remains conservative substring/phrase matching - not semantic or vector retrieval.` This is now stale and contradicts the new L2.1 complete section plus observed `retrieval_mode=semantic` evidence. Fix this named state-doc issue before treating the stale-doc correction as closed.

Concern:

- The overall working tree is not narrow. The targeted RIS docs diff is narrow, but `git status --short` shows substantial unrelated vault/root-doc churn. I did not inspect or validate that churn.

---

## Queue Recommendation Verdict

**PASS for RESET, BLOCK for scheduling validation.**

The recommendation to avoid a blind resume is evidence-backed:

- One item is stuck in `processing` (`arxiv:1011.6402`) with `stuck_warning=true`.
- Five failed items have exhausted attempts (`attempts=3`) on metadata fetch timeout/HTTP 429 failures.
- `prefetch_stats.cached=0`, so the queue has not been converted to the cached validation path.
- `indexed_count=0`, so the five successful parses in this queue have not been counted as indexed validation results.

RESET is safer than resume because resume would mix stale `processing`, terminal failed, unprefetched pending, and unindexed done states. That would contaminate validation metrics by treating a partial interrupted run as a clean 29-paper cached validation.

RESET is safer than full rebuild because the five done papers have body sidecars (`sidecar_count=5`), so rebuilding would discard valid parse work and spend unnecessary GPU time. The queue does not look structurally corrupt; it looks interrupted and unprepared for cached validation.

---

## Required Fixes

1. Update `docs/CURRENT_STATE.md` in the RIS L2 Academic Query / Query normalization paragraph so it no longer says retrieval is "not semantic or vector retrieval." It should describe that normalization is lexical/string preprocessing, while primary retrieval is now ChromaDB semantic retrieval with lexical fallback.
2. Before any 29-paper validation, execute the queue RESET plan: index/reindex the 5 done papers, force-reset the stuck and failed items, prefetch pending PDFs with delay, then process in controlled cached batches.
3. Keep the timeout-risk/JIT-cache caveats explicit before running a long GPU batch.

---

## Exact Next Action

**Fix named docs/state issues first.** Specifically, fix the remaining stale `docs/CURRENT_STATE.md` sentence, then re-run:

```text
python -m polytool research-marker-queue check-chroma-links --json
python -m polytool research-marker-queue --queue-dir artifacts/research/scaled_validation_queue_v2 status-report --json
```

After that, the next operational step is queue RESET, not scheduling the 29-paper cached validation and not rebuilding from scratch.
