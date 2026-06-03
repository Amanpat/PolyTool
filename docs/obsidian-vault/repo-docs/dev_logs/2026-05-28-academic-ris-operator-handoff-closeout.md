---
title: Academic Ris Operator Handoff Closeout
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-28_academic-ris-operator-handoff-closeout.md
last_synced: '2026-06-03T02:26:56Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log: Academic RIS Operator Handoff Closeout

**Date:** 2026-05-28
**Scope:** Docs-only. Mark Academic RIS developer/operator demo-ready v1 closed in operator handoff.
**No code, tests, runtime artifacts, Batch C/D, or benchmark baselines touched.**

---

## Objective

Final Codex review (PASS) confirmed Academic RIS demo-ready v1 is formally closed.
Exact next action from Codex: mark Academic RIS developer/operator demo-ready v1 closed in
the operator handoff so future agents clearly see v1 is complete, Batch C/D are post-v1
hardening, and the next hardening item is Docker jit-cache-check.

---

## Handoff Document Located

`docs/CURRENT_DEVELOPMENT.md` is the operator handoff/current focus document for this repo.

**Pre-edit state:**
- "Recently Completed" table (line 92): Academic RIS v1 entry was already present with
  Batch B metrics summary, caveats, and feature doc link. ✅
- "Notes for the Architect" section (lines 132–155): All other completed milestones had
  explicit COMPLETE/CLOSED notes (PMXT A, PMXT B, PMXT C, Phase 2A, SVM, Marker Docker,
  L1, L2, L4). Academic RIS demo-ready v1 did NOT yet have such a note. ❌

**Gap:** No standalone bullet explicitly stating "FORMALLY CLOSED" with the final Codex review
reference, caveats reminder, and next-work designation. Future agents would have to infer
closure from the Recently Completed table alone.

---

## Status Added

Added the following bullet to the "Notes for the Architect" section of
`docs/CURRENT_DEVELOPMENT.md`, immediately after the existing operator-tested v1 note (line 155):

> **RIS Academic Pipeline — Developer/Operator Demo-Ready v1 is FORMALLY CLOSED (2026-05-28).**
> Final Codex review: PASS. Feature doc: `docs/features/FEATURE-ris-academic-demo-ready-v1.md`.
> Caveats (MUST remain visible): weather lexical false positive, Docker Chroma gap, JIT cache
> persistence unresolved, Batch C/D deferred (Tier-3 approval required for arxiv:2409.02025 and
> arxiv:1011.6402). Not production-ready. Next work: post-v1 hardening only. First item: Docker
> jit-cache-check before any Batch C/D planning.

---

## Searches Run

The following verification steps were performed:

1. Read `docs/CURRENT_DEVELOPMENT.md` lines 88–156 to confirm the Recently Completed entry
   and the tail of Notes for the Architect before the edit.

2. Read `docs/CURRENT_STATE.md` lines 2090–2169 to confirm the RIS demo-ready v1 section
   is present and caveats are intact.

3. Read `docs/features/FEATURE-ris-academic-demo-ready-v1.md` (full) to confirm the feature
   doc is complete, caveats are preserved, and the Batch B evidence chain is recorded.

4. Read `docs/dev_logs/2026-05-28_codex-final-review-academic-ris-demo-ready-v1.md` (full)
   to confirm the Codex final review PASS verdict and the "exact next action" language.

5. Verified `.planning/STATE.md` — GSD tracking doc; no RIS v1 handoff close entry was
   required there (quick task log, not the operator handoff doc).

---

## Files Changed

| File | Change |
|------|--------|
| `docs/CURRENT_DEVELOPMENT.md` | Added FORMALLY CLOSED note to "Notes for the Architect" |
| `docs/dev_logs/2026-05-28_academic-ris-operator-handoff-closeout.md` | This dev log |

---

## Confirmation: Nothing Else Touched

- No Python files modified.
- No tests added or removed.
- No Batch C/D triggered or planned.
- No benchmark baselines changed.
- No `warm-process`, `index-done`, or `research-query` commands run.
- No Docker GPU sessions initiated.
- No vault documents written (not required by this handoff scope).
- `docs/CURRENT_STATE.md` not modified — the RIS section already contains the full
  demo-ready v1 entry with all caveats (lines 2117–2169, confirmed current).

---

## Caveats Confirmed Preserved

The following caveats are preserved in both the "Notes for the Architect" bullet
and in `docs/features/FEATURE-ris-academic-demo-ready-v1.md`:

1. Weather lexical false positive — `weather forecast` returns 1 lexical citation from
   `arxiv:2605.00493`. Non-blocking; post-v1 hardening item.
2. Docker Chroma gap — `ris-scheduler-gpu` image lacks `chromadb`; Chroma embedding must
   run on Windows host. Operational friction only.
3. JIT cache persistence unresolved — `TORCHINDUCTOR_CACHE_DIR` confirmed empty after
   batch runs. In-session reuse works; cross-restart not confirmed.
4. Batch C/D deferred — 9 pending Tier-3/large papers. `arxiv:2409.02025` and
   `arxiv:1011.6402` require explicit Tier-3 operator approval.
5. Not production-ready — operator supervision required for each batch; manual Chroma
   embedding on Windows host.

---

## Next Recommended Work Item

**Docker `jit-cache-check`** — verify `TORCHINDUCTOR_CACHE_DIR` / `TRITON_CACHE_DIR`
cross-restart persistence before planning any Batch C/D run. This is the blocking
pre-condition for post-v1 hardening batches.

After jit-cache-check confirms cross-restart reuse, Batch C/D still requires explicit
Tier-3 operator approval for the two named hard papers:
- `arxiv:2409.02025` (HTTP 429 failures in prior sessions)
- `arxiv:1011.6402` (3600s timeout in prior sessions)

Do NOT plan Batch C/D without both jit-cache-check result and Tier-3 approval.
