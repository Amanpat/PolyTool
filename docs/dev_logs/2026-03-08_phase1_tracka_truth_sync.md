# Dev Log: Phase 1 Track A Truth Sync

**Date:** 2026-03-08
**Type:** Docs-only truth sync
**Scope:** No code changes, no test changes, no runtime config changes

---

## Purpose

Unify the Track A story across all docs so they describe one canonical
live-bot program instead of conflicting variants. This sync resolves four
classes of contradiction and creates SPEC-0012 as the durable canonical spec.

---

## Contradictions resolved

### 1. Canonical strategy identity

**Problem:** Several docs (CURRENT_STATE.md, ROADMAP.md) described
`binary_complement_arb` tape capture as "the current next step" without
clearly marking it as a Gate 2 scouting vehicle. This left it ambiguous
whether `binary_complement_arb` was the Phase 1 live strategy.

**Resolution:** `market_maker_v0` is the Phase 1 mainline live strategy.
`binary_complement_arb` is a Gate 2 scouting/detection vehicle used to
identify complement-arb dislocations in tapes; it is not the strategy that
runs in Stage 0 or Stage 1.

**Files updated:**
- `docs/CURRENT_STATE.md` — added explicit Phase 1 mainline callout; clarified
  binary_complement_arb role in Track A execution layer section and gate status
  note
- `docs/ROADMAP.md` — added inline clarification on current next step note
- `docs/features/FEATURE-trackA-live-clob-wiring.md` — added mainline/scouting
  vehicle distinction in summary

### 2. Alerting system: Telegram → Discord

**Problem:** `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` referenced Telegram
alerts three times (prerequisites, monitor, daily review). Canonical alerting
system for Track A is Discord.

**Resolution:** All three Telegram references replaced with Discord.

**Files updated:**
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` — three replacements

### 3. Gate status in FEATURE doc was outdated

**Problem:** `docs/features/FEATURE-trackA-live-clob-wiring.md` contained a
gate status table dated 2026-03-05 showing Gates 1 and 2 as "OPEN" and Gate 3
as "90% COMPLETE." The authoritative gate status (ROADMAP.md, CURRENT_STATE.md,
both dated 2026-03-07) shows Gate 1 PASSED, Gate 2 NOT PASSED, Gate 3 BLOCKED,
Gate 4 PASSED.

**Resolution:** Feature doc gate table replaced with current status. Historical
note preserved explaining the 2026-03-05 snapshot is superseded.

**Files updated:**
- `docs/features/FEATURE-trackA-live-clob-wiring.md` — gate table replaced

### 4. No single canonical Track A spec

**Problem:** SPEC-0011 defines the execution layer interfaces and gate model
but does not define the full Phase 1 program (strategy identity, validation
corpus, market selection policy, alerting, FastAPI/n8n rules, evidence
artifacts). Track A information was distributed across ROADMAP.md,
CURRENT_STATE.md, LIVE_DEPLOYMENT_STAGE1.md, and SPEC-0011 with no single
authoritative reference.

**Resolution:** SPEC-0012 created as the canonical Track A live bot program
spec. All 10 required sections are present.

---

## New artifacts

| File | Purpose |
|------|---------|
| `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` | Canonical Phase 1 Track A spec |
| `docs/dev_logs/2026-03-08_phase1_tracka_truth_sync.md` | This log |

---

## Index updates

- SPEC-0011 added to Specs table (was missing)
- SPEC-0012 added to Specs table
- This dev log added to Dev Logs table

---

## Post-sync verification

### Telegram grep across touched docs
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`: 0 matches (3 replaced)
- `docs/CURRENT_STATE.md`: 0 matches
- `docs/ROADMAP.md`: 0 matches
- `docs/features/FEATURE-trackA-live-clob-wiring.md`: 0 matches
- `docs/INDEX.md`: 0 matches
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md`: 0 matches

### binary_complement_arb grep across touched docs
- All occurrences are in context of "Gate 2 scouting vehicle" or "secondary
  experimental/detection strategy" — none describe it as the Phase 1 mainline.

### 30-day shadow grep across touched docs
- `docs/ROADMAP.md`: "Historical note" dismissal already present (not introduced
  by this sync, retained as-is)
- `docs/CURRENT_STATE.md`: "Historical note" dismissal already present
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`: "Historical note" dismissal already
  present
- No new "30-day shadow" language introduced by this sync

### Gate ladder consistency
All touched docs use the same ladder:
`Gate 1 → Gate 2 → Gate 3 → Gate 4 → Stage 0 → Stage 1`

### SPEC-0012 in INDEX.md
Confirmed: SPEC-0012 link present in Specs table in `docs/INDEX.md`.

---

## Remaining risks

- **Mixed-regime corpus**: SPEC-0012 §4 introduces the mixed-regime validation
  requirement (politics, sports, new markets). This requirement is new. Existing
  gate closure scripts do not yet enforce it; it is currently an operator-verified
  manual checklist item documented in SPEC-0012 and Gate 3 / Stage 0 artifacts.
  A future gate harness update could add automated regime tagging.

- **Discord wiring not yet confirmed**: SPEC-0012 and LIVE_DEPLOYMENT_STAGE1.md
  now reference Discord as the canonical alerting system, but no Discord webhook
  or bot is confirmed wired into the runtime. This is an operator setup task
  before Stage 0 starts, documented as a Stage 0 prerequisite in SPEC-0012 §8.

- **SPEC-0011 gate model is a subset of SPEC-0012**: SPEC-0011 defines the
  gate model as `replay -> scenario sweeps -> shadow -> dry-run live` (four
  gates). SPEC-0012 extends this with Stage 0 and Stage 1 promotion requirements
  and the mixed-regime corpus. The two specs are compatible; SPEC-0012 governs
  the full program.
