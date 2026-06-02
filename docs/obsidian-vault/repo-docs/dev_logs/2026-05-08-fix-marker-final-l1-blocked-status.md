---
title: Fix Marker Final L1 Blocked Status
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_fix-marker-final-l1-blocked-status.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker Final L1-Blocked Status References

**Date:** 2026-05-08
**Type:** Docs-only fix
**Scope:** `docs/features/ris-marker-structural-parser-scaffold.md`, `docs/INDEX.md`, `docs/CURRENT_DEVELOPMENT.md`

---

## Codex Blockers Addressed

Codex FAILed the Marker Docker IPC Warm-Worker v1 closeout verification because three current
docs still asserted L1 is blocked awaiting warm-worker Feature 3 closeout — contradicting the
completed closeout recorded in `docs/features/FEATURE-marker-docker-ipc-warm-worker-v1.md`.

| Location | Stale text | Resolution |
|---|---|---|
| `ris-marker-structural-parser-scaffold.md:3` | "L1 PRODUCTION BLOCKED (pending Marker Docker IPC Warm-Worker v1 Feature 3 closeout, 2026-05-07)" | Replaced with: warm-worker v1 closed 2026-05-08 under revised functional gate; L1 can proceed to next explicit rollout step. |
| `ris-marker-structural-parser-scaffold.md:7` | "see Active Feature 3 in `docs/CURRENT_DEVELOPMENT.md`" (dangling pointer — Feature 3 now closed) | Replaced with pointer to `FEATURE-marker-docker-ipc-warm-worker-v1.md` (closed 2026-05-08). |
| `ris-marker-structural-parser-scaffold.md:13–14` | "Docker IPC warm-worker v1 is Active Feature 3 (2026-05-07)" / "L1 production rollout resumes when Feature 3 closeout verification passes" | Updated: warm-worker v1 closed under revised gate; L1 can proceed; L2/L4 remain stubs. |
| `docs/INDEX.md:118` | "L1 PRODUCTION BLOCKED (awaiting Docker IPC warm-worker v1)" | Replaced with: Docker IPC warm-worker v1 closed 2026-05-08; L1 can proceed to next explicit rollout/readiness step. |
| `docs/CURRENT_DEVELOPMENT.md:95` | "Docker IPC warm-worker deferred to v1. L1 Marker production rollout still blocked on IPC warm-worker." | Replaced with: Queue v0 shipped; IPC warm-worker v1 closed 2026-05-08; next L1 step requires separate workpacket/Director decision. |

---

## What Was NOT Changed

- No implementation code, tests, Docker files, validation queues, artifacts, SVM labels/models, or trading files were touched.
- `docs/CURRENT_STATE.md` was not touched (no direct contradiction found in scope).
- The full academic/RIS pipeline is not claimed complete — docs explicitly note L2/L4 remain stubs.
- L2/PaperQA2 and L4 are not declared unblocked.
- No feature was activated.

---

## Commands Run

```
# Stale-status search across docs/
rg -n "blocked awaiting Docker IPC|blocked pending warm-worker|blocked on IPC warm-worker|blocked on Feature 3 closeout|Active Feature 3|NOT yet closed" docs/
# → Remaining hits: only historical dev logs (recording past state) and Obsidian vault (out of scope)

# Targeted clean check on three edited files
rg -n "blocked awaiting Docker IPC|blocked pending warm-worker|blocked on IPC warm-worker|blocked on Feature 3 closeout|Active Feature 3|NOT yet closed|L1 PRODUCTION BLOCKED" docs/features/ris-marker-structural-parser-scaffold.md
# → No matches

rg -n "blocked awaiting Docker IPC|blocked pending warm-worker|blocked on IPC warm-worker|L1 PRODUCTION BLOCKED" docs/INDEX.md
# → No matches (line 171 hit is a historical dev log title, not a current status claim)

rg -n "blocked on IPC warm-worker|still blocked on IPC warm-worker" docs/CURRENT_DEVELOPMENT.md
# → No matches

# Implementation-path diff to confirm no code touched
git diff --name-status -- packages tools tests polytool config infra docker-compose.yml Dockerfile.ris artifacts
# → Dockerfile.ris, packages/research/ingestion/fetchers.py, packages/research/ingestion/marker_queue.py,
#    tests/test_ris_marker_queue.py, tools/cli/research_marker_queue.py
# → All pre-existing modifications from prior sessions; none introduced by this fix
```

---

## Completion Protocol

The completion protocol (revised functional gate: ≥3 full PDFs/session, papers 2+ delta ≤5s,
`body_source=marker`, `ipc_warm_worker_used=true`, no pdfplumber fallback, no daemon error,
clean shutdown) was already present and accepted before this fix. This fix only removes stale
"still blocked" language that contradicted the already-accepted closeout.

---

## Codex Closeout Verification

Codex closeout verification may rerun. The three blocking doc references that caused the FAIL
have been resolved. No implementation paths were changed.
