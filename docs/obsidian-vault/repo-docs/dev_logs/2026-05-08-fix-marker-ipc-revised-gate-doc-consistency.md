---
title: Fix Marker Ipc Revised Gate Doc Consistency
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Fix: Marker IPC Revised Gate — Doc Consistency

Date: 2026-05-08
Type: docs-only fix
Scope: Feature 3 — Marker Docker IPC Warm-Worker v1
Verdict: **COMPLETE** — all docs now consistently show Feature 3 as Active pending closeout; no current doc requires ≤10s/paper for full academic PDFs

---

## Codex Blockers Addressed

Codex FAIL (`docs/dev_logs/2026-05-08_codex-verify-marker-ipc-revised-gate-and-result-evidence.md`)
identified two blocking doc inconsistencies:

1. `docs/CURRENT_DEVELOPMENT.md` still listed Marker Docker IPC warm-worker under
   Paused / Deferred instead of Active Feature 3 pending closeout.
2. Active `<=10s/paper` warm-paper gate language remained in 4 documents
   (CURRENT_DEVELOPMENT, Current-Focus, INDEX, Work Packet).

Both blockers are resolved by this session. No code, tests, or artifacts were touched.

---

## Files Changed and Why

### `docs/CURRENT_DEVELOPMENT.md`

**Why:** Primary Director-level gate doc. Codex found it still showed warm-worker as
Paused/Deferred rather than Active Feature 3, and still had ≤10s/paper resume trigger language.

**Changes:**
- Added **Feature 3 block** under Active Features: Marker Docker IPC Warm-Worker v1.
  Status: implementation complete, all revised functional gates PASS, pending Codex closeout
  verification. Definition-of-done with [x]/[ ] checkboxes reflecting current state.
- **Paused/Deferred row** for "RIS Marker Queue — Docker IPC Warm-Worker (v1)": changed
  from Paused to `ACTIVATED 2026-05-07`; resume trigger column updated to "N/A — now Active Feature 3".
- **Paused/Deferred row** for "RIS L1 Marker Production Rollout — Validation": resume trigger
  updated from `parse_seconds ≤10s for papers 2+` to `Docker IPC warm-worker (v1) Feature 3 closeout
  verification passes`.
- **Architect Notes** (Parse Queue v0 note): updated trailing text from "deferred — Feature 3 slot
  available" to "now Active Feature 3"; removed old ≤10s warm validation language.
- **Architect Notes** (L3 SVM closeout note): updated "one Feature 3 slot is available" and
  "must be revisited" to "activated as Feature 3 (2026-05-07) — active count is now 3 (max-3)".
- **Architect Notes** (REMINDER note): changed from "DEFERRED, NOT CANCELED" to "NOW ACTIVE as
  Feature 3"; updated with revised gate summary and "do NOT start L2 or L4".

### `docs/obsidian-vault/Claude Desktop/Current-Focus.md`

**Why:** Living priority doc. Codex found three locations with active ≤10s language.

**Changes:**
- **Active Priority #1**: replaced "warm-worker still deferred; must be revisited before L2" with
  "Marker Docker IPC warm-worker v1 is now Active Feature 3 (2026-05-07); all revised functional
  gates PASS (2026-05-08); pending Codex closeout verification."
- **L1 row in RIS Scientific RAG Status table**: replaced `validates ≥3 papers warm (≤10s/paper for
  papers 2+)` with "v1 is Active Feature 3; revised functional gates PASS; blocked until Feature 3
  closeout verification."
- **Key Blockers table**: warm-worker row updated from "deferred; L1 blocked until ≤10s/paper" to
  "warm-worker v1 implemented and validated; PASS; Active Feature 3; L1 blocked until closeout."
- **Open Decisions**: academic pipeline hosting row — removed `>=3 warm papers, <=10s/paper` phrase;
  replaced with "Feature 3 closeout verification."
- **Frontmatter** `updated` date: 2026-05-07 → 2026-05-08.
- **Session context**: entry added for this session at top of Recent Session Context.
- **Last updated footer**: date and description updated.

### `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md`

**Why:** Codex found two locations with active ≤10s language in the Goal and Context sections.

**Changes:**
- **Goal section item 2**: removed `≤10s/paper for papers 2+`; replaced with revised gate
  language (papers 2+ delta ≤5s, cold-load overhead eliminated).
- **Context section (v1 fix paragraph)**: removed `papers 2+ parse from warm VRAM at ≤10s/paper`;
  replaced with "cold-load overhead eliminated (delta ≤5s); per-paper inference ~45–70s is a
  hardware constant — see Director Gate Revision section."

Note: The `Director Gate Revision (2026-05-08)` section, strikethrough gates in the Acceptance
Gates table, and status callout block were already correct from the prior session — not re-edited.

### `docs/INDEX.md`

**Why:** Codex found one location with active ≤10s language; also needed new dev log entries.

**Changes:**
- **Academic Pipeline Hosting Decision dev log row**: removed `>=3 warm papers, <=10s/paper for
  papers 2+`; replaced with "L1 remains blocked pending Marker Docker IPC warm-worker (v1) Feature 3
  closeout."
- **New dev log rows added** (most-recent-first before existing 2026-05-07 L3 SVM entry):
  - `2026-05-08_fix-marker-ipc-revised-gate-doc-consistency.md` (this session)
  - `2026-05-08_codex-verify-marker-ipc-revised-gate-and-result-evidence.md` (Codex FAIL — docs)
  - `2026-05-08_marker-ipc-revised-gate-and-result-evidence.md` (persistence fix, PASS)
  - `2026-05-07_codex-verify-marker-docker-ipc-warm-worker-live-validation.md` (Codex PASS — live)
  - `2026-05-07_fix-marker-historical-l1-unblocked-claims.md` (stale L1 claims fix)

---

## Revised Gate (current canonical form)

Director-approved 2026-05-08. Replaces all prior `≤10s/paper` gate language.

| Criterion | Threshold | Evidence |
|-----------|-----------|----------|
| ≥3 full academic PDFs in one warm session | all done | done=3, failed=0 |
| Papers 2+ delta (total_seconds − parse_seconds) ≤5s | cold-load not repeated | paper 2: 0.13s, paper 3: 0.22s |
| `body_source=marker` all papers | true | all 3 |
| `ipc_warm_worker_used=true` all papers | true | all 3 |
| No pdfplumber fallback | none | confirmed |
| No daemon-process error | none | confirmed |
| Clean shutdown / no orphans | exit_code=0 | confirmed |
| `ipc_warm_worker_used` persisted in `results.jsonl` | fix applied 2026-05-08 | 4 new tests pass |

Actual measured timings (preserved, not hidden):

| Paper | parse_seconds | total_seconds | delta |
|-------|--------------|--------------|-------|
| arxiv:2604.24366 (paper 1) | 45.55s | 72.31s | 26.76s (cold-load) |
| arxiv:2109.07581 (paper 2) | 69.73s | 69.86s | **0.13s** (warm) |
| arxiv:1910.08858 (paper 3) | 48.31s | 48.53s | **0.22s** (warm) |

---

## Commands Run and Outputs

### Pre-fix grep to confirm blockers (matching Codex report)

```
git grep -n "<=10s\|≤10s\|10s/paper\|10 seconds" docs
```

Expected matches before fix (per Codex report):
- `docs/CURRENT_DEVELOPMENT.md:114` and `:115`
- `docs/obsidian-vault/Claude Desktop/Current-Focus.md:20`, `:29`, `:72`
- `docs/obsidian-vault/Claude Desktop/12-Ideas/Work-Packet - Marker Docker IPC Warm-Worker v1.md:38`, `:57`
- `docs/INDEX.md:181`

### Post-fix verification

Run after this session:
```
git grep -n "<=10s\|≤10s\|10s/paper" docs
```

Expected: any remaining hits are in historical/completed dev logs only (not in living state docs
CURRENT_DEVELOPMENT, Current-Focus, INDEX, or the active Work Packet sections).

```
git grep -n "Marker Docker IPC Warm-Worker\|Marker IPC" docs/CURRENT_DEVELOPMENT.md
```

Expected: Feature 3 in Active Features section; ACTIVATED in Paused/Deferred; Active Feature 3
in Architect Notes.

```
git diff --stat
```

Expected: only docs/ files modified; no packages/, tests/, tools/, infra/, artifacts/ changes.

---

## Remaining Closeout Blocker

Feature 3 is **NOT closed by this session.** All revised functional gates PASS and docs are now
consistent. The sole remaining blocker before Feature 3 can move to Recently Completed is:

- **Codex closeout verification** — a fresh Codex review of the full Feature 3 state (code +
  tests + docs) must return PASS before the completion protocol runs (feature doc creation,
  CURRENT_STATE.md update, move to Recently Completed).

---

## Confirmation: No Code / Tests / Artifacts Touched

- No changes to `packages/`, `tools/`, `tests/`, `infra/`, `config/`, or `artifacts/`.
- No Docker rebuild, prune, or container modification.
- No queue mutations.
- No SVM labels, models, or trading files touched.
- No L2 (PaperQA2) or L4 (multi-source harvesters) work started.
- Feature 3 NOT moved to Recently Completed.
- No feature closeout doc created (deferred to post-Codex-verification).

---

## Codex Review Summary

Tier: docs-only session. No implementation code in scope.

Issues found: documentation blockers from prior Codex FAIL (2026-05-08_codex-verify-marker-ipc-
revised-gate-and-result-evidence.md) — active ≤10s language in 4 files; warm-worker shown as
Paused not Active Feature 3 in CURRENT_DEVELOPMENT.

Issues addressed: all blocking documentation inconsistencies resolved. Active ≤10s/paper gate
language removed. Feature 3 shown as Active in CURRENT_DEVELOPMENT.md.
