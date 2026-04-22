# Fee Model Overhaul — Docs Close-out (Deliverable A Complete)

**Date:** 2026-04-21
**Branch:** main
**Scope:** Docs-only close-out for PMXT Deliverable A. No code changes.

---

## Close-out Steps Completed

### 1. Feature doc finalized — `docs/features/simtrader_fee_model_v2.md`

Added three sections missing from the initial draft:

- **Section 6 — Runtime Propagation:** Table of all 12 production entry points now
  wired with `fee_category`/`fee_role`. Confirms complete propagation across
  `StrategyRunner`, `ShadowRunner`, facade, sweeps, studio (5 call sites),
  Gate 2 sweep tool, and all 4 CLI paths (`_run`, `_sweep`, quickrun sweep,
  quickrun single, `_shadow`).

- **Section 7 — CLI Truthfulness:** Documents the three-way fee label emitted by
  `simtrader run` and `simtrader sweep`: `"category-aware (…)"` / bps value /
  `"null (ledger default)"`.

- **Section 8 — Manifest Truthfulness:** Documents that `run_manifest.json` now
  records `fee_rate_bps: null` (not `"default(200)"`) and includes explicit
  `fee_category`/`fee_role` fields.

- **Test Coverage updated:** Corrected count from 23 to 32 new tests across 3 files
  (23 portfolio + 4 shadow + 5 strategy). Full suite: 200 targeted, 2606 total,
  1 pre-existing unrelated failure.

- **Non-Goals updated:** Added Studio UI form inputs, three diagnostic sweep tools,
  and Deliverable B dynamic role detection to the explicit deferral list.

### 2. INDEX.md updated — `docs/INDEX.md`

- Added `simtrader_fee_model_v2.md` to the Features table.
- Added 5 dev logs to the Recent Dev Logs table (close-out, final Codex gate, CLI
  truthfulness fix, finish pass, core changes), ordered newest-first before the
  2026-04-10 entry.

### 3. CURRENT_DEVELOPMENT.md updated — `docs/CURRENT_DEVELOPMENT.md`

- **Awaiting Director Decision:** Updated Option 4 note — blocker resolved; re-running
  Gate 2 under corrected fees is now unblocked.
- **Active Features:** Feature 2 slot cleared (was SimTrader Fee Model Overhaul).
  Active count is now 1 (Track 2 Paper Soak).
- **Recently Completed:** Added entry for SimTrader Fee Model Overhaul (2026-04-21)
  with completion note and feature doc link.
- **Notes for the Architect:** Replaced "PMXT Deliverable A is Active" with
  "PMXT Deliverable A is COMPLETE (2026-04-21)".

---

## Files Changed (docs only)

| File | Change |
|---|---|
| `docs/features/simtrader_fee_model_v2.md` | Added sections 6–8; updated test coverage count and non-goals |
| `docs/INDEX.md` | Added feature row; added 5 dev log rows |
| `docs/CURRENT_DEVELOPMENT.md` | Option 4 unblocked; Feature 2 cleared; Recently Completed row added; Architect note updated |
| `docs/dev_logs/2026-04-21_fee-model-overhaul_closeout.md` | This file |

---

## Completion Status Summary

PMXT Deliverable A three-step completion protocol is fully satisfied:

- [x] `docs/features/simtrader_fee_model_v2.md` created and finalized
- [x] `docs/INDEX.md` updated (feature + dev logs discoverable)
- [x] `docs/CURRENT_DEVELOPMENT.md` updated (moved to Recently Completed)

---

## Remaining Unrelated Repo-Health Issues

The following issues are **not** part of Deliverable A and are called out explicitly
so they are not confused with any outstanding Deliverable A work:

1. **RIS red test** — `tests/test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success`
   fails with `AttributeError: packages.research.evaluation.providers has no attribute '_post_json'`.
   Pre-existing. Tracked separately. Full suite: 2606 passed, 1 failed.

2. **Docs truth-sync deferred** — SPEC-0004 and ARCHITECTURE still document the
   exponent-2 formula as canonical. Will require a separate pass after human review
   of the formula change.

3. **`fee_role="taker"` hardcoded at all CLI sites** — Dynamic taker/maker role
   detection is Deliverable B. Not a Deliverable A gap.

4. **Studio UI form inputs** — `fee_category`/`fee_role` are not exposed in the
   Studio web form. Deferred.

5. **Completion-doc debt** — Four items from the 2026-04-14/15 shipping sprint still
   have no feature docs (track2 soak infrastructure, gate2 gold capture hardening,
   gate2 post-capture qualification, crypto-pair-reference-feed accuracy check).
   Tracked in `docs/CURRENT_DEVELOPMENT.md` under Completion-Doc Debt.
