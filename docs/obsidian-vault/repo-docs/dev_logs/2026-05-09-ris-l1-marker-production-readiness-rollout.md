---
title: Ris L1 Marker Production Readiness Rollout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# RIS L1 Marker Production Readiness Rollout — Closeout

**Date:** 2026-05-09
**Track:** Research Intelligence System — Layer 1
**Feature doc:** `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md`
**Runbook:** `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md`

---

## Context

Director approved continuing academic pipeline only. The Marker Docker IPC warm-worker v1
closed 2026-05-08 (Feature 3) under the revised functional gate. L1 Marker Production
Readiness Rollout was declared UNBLOCKED and is now Feature 3 in this session. Scope:
confirm and document that the infrastructure shipped across prior work packets is
production-usable; close L1 so L2/L4 can begin.

---

## Academic Workpacket Dependency Matrix

| Work Packet | Status | Notes |
|------------|--------|-------|
| L0: Academic Pipeline PDF Download Fix | ✅ SHIPPED 2026-04-27 | pdfplumber wired; real arXiv ingests confirmed |
| L1: Marker Single-Paper Validation Control Surface | ✅ SHIPPED 2026-05-05 | `run-academic-url`; body_source=marker validated |
| L1: Marker Canonical Academic Parse Queue v0 | ✅ SHIPPED 2026-05-05 | File-backed queue, CLI, is_marker_ready(), Marker-only gate, 43 tests |
| L1: Marker Docker IPC Warm-Worker v1 | ✅ CLOSED 2026-05-08 (prior Feature 3) | Revised gate PASS; timings 45.55s/69.73s/48.31s; delta 0.13s/0.22s |
| **L1: Marker Production Readiness Rollout** | **✅ COMPLETE 2026-05-09 (this session)** | **Runbook, DoD, operator path, stale-text fix** |
| L2: PaperQA2 RAG Control Flow | Stub | **NOW UNBLOCKED** by L1 completion |
| L3: Pre-fetch SVM Topic Filter | ✅ CLOSED 2026-05-07 | Default-off; dry-run/hold-review ready; enforce deferred |
| L4: Multi-source Academic Harvesters | Stub | **NOW UNBLOCKED** (gated on L1 + L3; both complete) |
| L5: Scientific RAG Evaluation Benchmark | ✅ SHIPPED 2026-05-02 | Baseline: corpus=23, P@5=1.0 |

---

## L1 DoD Assessment

| Criterion | Pass? | Evidence |
|-----------|-------|----------|
| One documented path to enqueue/process academic PDFs | ✅ | `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` |
| Marker-only accepted docs (`body_source=marker`) | ✅ | `IngestPipeline.ingest_external()` academic Marker-only gate |
| No pdfplumber production fallback | ✅ | `marker` mode → rejection on failure; no downgrade |
| Queue states understandable and recoverable | ✅ | State machine + recovery procedures in runbook |
| Bad/short parses rejected or retryable, not silently RAG-ready | ✅ | `MIN_MARKER_BODY_LENGTH=5000`; MAX_ATTEMPTS=3; retryable then terminal |
| Output location and inspection commands documented | ✅ | Artifacts at `artifacts/research/marker_parse_queue/`; CLI documented |
| Smoke test proves path (existing evidence sufficient) | ✅ | Feature 3 validation: 3 papers, body_source=marker, ipc_warm_worker_used=true |
| Stale "L1 gated" CLI text removed | ✅ | research_marker_queue.py: warm-process handler and subparser updated |
| Tests pass | ✅ | 158 passed, 1 skipped (Linux-only platform skip, correct on Windows) |

**L1 DoD: PASS**

---

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `tools/cli/research_marker_queue.py` | Removed "L1 production remains gated until live Docker/GPU validation passes." note from `_cmd_warm_process` (×2) and updated warm-process subparser help text | Stale — IPC warm-worker validation (Feature 3) was complete 2026-05-08; note was misleading |
| `docs/runbooks/RIS_MARKER_QUEUE_RUNBOOK.md` | **NEW** | Missing piece for L1 DoD: documented operator path, queue states, recovery, output locations, performance expectations, platform behavior |
| `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md` | **NEW** | Completion protocol — feature doc required |
| `docs/dev_logs/2026-05-09_ris-l1-marker-production-readiness-rollout.md` | **NEW** | This file — mandatory dev log |
| `docs/INDEX.md` | Added feature row, runbook row, dev log row | Completion protocol |
| `docs/CURRENT_DEVELOPMENT.md` | Added Feature 3 entry (activate + immediately complete); added Recently Completed row; updated Paused row for L1 Validation; added Architect Note for L1 completion | Completion protocol |
| `docs/CURRENT_STATE.md` | Updated deferred items list (L2 now unblocked); added L1 Production Readiness Rollout section with DoD table and CLI surface | State truth update |
| `docs/obsidian-vault/Claude Desktop/Current-Focus.md` | Updated L1 row to COMPLETE; updated Active Priorities blurb; added Key Blockers row; added Recent Session Context entry; updated footer timestamp | State truth update |

---

## Commands Run and Outputs

### Targeted test run (before CLI fix)
```
python -m pytest tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py -x -q --tb=short
```
Result: **158 passed, 1 skipped** — baseline confirmed.

### Targeted test run (after CLI fix)
```
python -m pytest tests/test_ris_marker_queue.py tests/test_ris_marker_ipc_worker.py -x -q --tb=short
```
Result: **158 passed, 1 skipped** — no regressions from CLI text changes.

### CLI help smoke (confirming warm-process description updated)
The `warm-process` subparser now reads:
> "L1 production path — IPC warm-worker validated 2026-05-08 (Feature 3 closed)."

---

## Stale Text Removed

Two instances in `_cmd_warm_process()` removed:
- `"NOTE: L1 production remains gated until live Docker/GPU validation passes."` — printed before processing
- Same note printed after results summary

One instance updated in `_build_parser()`:
- Old: `"NOTE: L1 production gated — live Docker/GPU validation required."`
- New: `"L1 production path — IPC warm-worker validated 2026-05-08 (Feature 3 closed)."`

These notes were written before the IPC warm-worker (Feature 3) was validated. Feature 3
closed 2026-05-08 with all revised functional gates PASS — the live Docker/GPU validation
they referred to is complete.

---

## L1 DoD: PASS — Completion Protocol Executed

All three steps complete:
1. ✅ `docs/features/FEATURE-ris-l1-marker-production-readiness-rollout.md` created
2. ✅ `docs/INDEX.md` updated (feature row + runbook row + dev log row)
3. ✅ Feature 3 moved to Recently Completed in `docs/CURRENT_DEVELOPMENT.md`

---

## Remaining Gated Work (L2 and L4)

Both are now unblocked by L1 completion.

| Item | Gate | Status |
|------|------|--------|
| L2 PaperQA2 RAG Control Flow | L1 completion | **UNBLOCKED** — requires Director workpacket activation |
| L4 Multi-source Academic Harvesters | L1 + L3 | **UNBLOCKED** — requires Director workpacket activation |
| Automatic warm-worker startup on container boot | Post-v1 hardening | Deferred |
| IPC crash recovery / reconnect | Post-v1 hardening | Deferred |
| Bulk re-ingest of pdfplumber-parsed corpus | Separate cleanup task | Deferred |
| SVM enforce mode | Future Director approval | Hard-blocked at rc=1 |

L2 and L4 are stubs in the codebase. Neither is activated by this session. They require
explicit Director workpacket decisions before implementation begins.

---

## Codex Review Policy

This session changed only:
- CLI text (non-functional help strings and print statements in `research_marker_queue.py`)
- New docs files (runbook, feature doc, dev log)
- Docs updates (INDEX, CURRENT_DEVELOPMENT, CURRENT_STATE, Current-Focus)

Per the Codex review policy in CLAUDE.md: docs and CLI formatting changes are **Skip** tier.
No mandatory or recommended Codex review required.
