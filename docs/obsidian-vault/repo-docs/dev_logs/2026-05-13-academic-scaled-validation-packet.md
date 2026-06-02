---
title: Academic Scaled Validation Packet
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-13_academic-scaled-validation-packet.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log: Academic Pipeline Scaled Validation — Work Packet Draft

**Date:** 2026-05-13  
**Objective:** Draft a scoped work packet for the 20–30 paper scaled validation corpus and
run plan. No ingestion, benchmarking, or code changes were executed.  
**Scope:** Planning-only. Two new docs created; no implementation files touched.

---

## Files Changed

| File | Action | Reason |
|------|--------|--------|
| `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Academic Pipeline Scaled Validation Corpus.md` | **Created** | Canonical work packet at the established `12-Ideas/Work-Packet - *.md` convention |
| `docs/dev_logs/2026-05-13_academic-scaled-validation-packet.md` | **Created** | This dev log |

No implementation code, benchmark baselines, config files, or test files were modified.

---

## Conventions Check

Work packets in this repo live at:
```
docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - <Title>.md
```
Confirmed by inspecting existing examples:
- `Work-Packet - Marker Canonical Academic Parse Queue.md`
- `Work-Packet - Scientific RAG Evaluation Benchmark.md`
- `Work-Packet - PaperQA2 RAG Control Flow.md`
- (and 10+ others)

Alternative: `docs/specs/SPEC-phase1b-gate2-shadow-packet.md` is used for Gate/SPEC
documents. Since this is a validation run packet (not a technical spec or gate definition),
`12-Ideas/Work-Packet - *.md` is the correct location.

---

## Commands Run

```
git status --short
→ ? docs/dev_logs/2026-05-13_l5-v0-1-current-marker-rerun.md (untracked, from prior session)

python -m polytool research-eval-benchmark --discover-corpus (output previewed; not saved)
→ 74 academic records in KS; 3 with body_source=marker; 21 with chunk_count=1 (stubs)
```

No benchmark or ingestion commands were run. The discover output was read for context only.

---

## Packet Scope Summary

The work packet defines:

1. **Prerequisites** — L5 v0.1 rerun (today), L1/L2 production readiness, 3-paper validation
2. **Purpose** — Scale the 3-paper operator validation to 20–30 papers to surface real-world
   Marker parse failures and validate retrieval quality across diverse PDF structures
3. **KS health pre-checks** — 0838c7de desync (stub in KS, body in raw cache), bad51e5d
   missing body cache, 3 pre-existing academic_marker_gate test failures
4. **Operator corpus table** — 29-row template (10 eq-heavy / 10 table-heavy / 5 prose /
   4 outlier) with suggested arXiv IDs; operator must fill before execution starts
5. **Execution flow** — 7 steps: pre-flight → enqueue → warm-process → inspect → index-done
   → verify KS → research-query probes → metrics table
6. **Metrics** — 7 per-paper parse metrics, 3 per-paper KS metrics, 2 per-paper claim
   metrics, 5 corpus-level summary metrics
7. **Acceptance criteria** — 6 criteria: no silent fallbacks, all failures classified,
   ≥4/5 probes with Marker citations, corpus metrics within range, production-ready vs
   demo-ready classification, explicit no-premature-promotion guard
8. **Output artifacts** — results.jsonl, discover snapshots, execution dev log, optional
   v1 corpus manifest draft
9. **Don't-Do list** — 10 explicit scope guards (L2 semantic retrieval, SVM enforce,
   SSRN/NBER, Docker IPC perf, bulk QA, baseline modification, etc.)
10. **Open questions** — 6 questions for Aman: URL selection, queue dir name, batch size,
    0838c7de repair, v1 manifest promotion criteria, pre-existing test fix scope

---

## Context from v0.1 Rerun (2026-05-13)

Key findings that informed this packet:

- KS grew from ~23 to 74 academic records between v0 baseline (2026-05-02) and today
- 3 Marker-indexed papers in KS (`2c26902b`, `a1921b9a`, `d023674c`) — none in v0 corpus manifest
- All 9 benchmark metrics identical to v0 — v0.1 is a stability confirmation, not a delta signal
- `0838c7de` now has body text in raw_source_cache (39 chunks indexed in lexical DB) but KS entry
  still shows `chunk_count=1, body_source=unknown` — KS desync
- `bad51e5db` body cache file is absent — paper was skipped in lexical refresh
- 3 pre-existing test failures in `test_ris_phase4_source_acquisition.py::TestEndToEnd`
  due to `academic_marker_gate` rejecting abstract-only fixtures (introduced in `03c9546`)

---

## Open Questions for Aman

1. **Primary blocker — URL selection:** The work packet has a 29-row operator input table
   in Section 3. It needs 20–30 real arXiv URLs across 4 categories before execution can
   start. Candidate suggestions are included as starting points.

2. **Queue dir name:** The packet uses `scaled_validation_queue_v1` as the isolation queue
   dir. Confirm or rename.

3. **Pre-existing test failures:** Three `TestEndToEnd` tests in
   `test_ris_phase4_source_acquisition.py` fail due to `academic_marker_gate` rejecting
   abstract-only fixtures. Should these be fixed in a separate session before the scaled
   validation run, or tolerated as known pre-existing failures? Recommendation: fix
   separately to keep the validation run's test count clean.

4. **`0838c7de` desync repair:** Should this be fixed before or during the scaled run?
   It does not block the run, but fixing it first gives a cleaner baseline.

5. **v1 corpus manifest:** If ≥20 papers parse cleanly, should the execution session
   write `config/research_eval_benchmark_v1_corpus.draft.json`? Or defer that decision
   to after reviewing parse quality?

6. **Docker GPU readiness:** The 3-paper validation used `ipc_warm_worker_used=false`
   (Windows local warm-thread). For 20-30 papers, the Docker/GPU path is strongly
   preferred for throughput. Confirm the Docker GPU container is available before
   scheduling the execution session.

---

## Confirmation: No Validation Executed

- No `research-marker-queue enqueue` commands were run
- No `warm-process` commands were run
- No `index-done` commands were run
- No `research-query` commands were run
- No benchmark commands (other than `--discover-corpus` for context) were run
- No code files were modified
- No baseline files were modified
- No config files were modified

This dev log and the work packet are the only outputs of this session.

---

## Codex Review

Tier: Skip — docs-only session, no code changes.
