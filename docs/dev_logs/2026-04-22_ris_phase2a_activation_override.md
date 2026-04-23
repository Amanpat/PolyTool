---
date: 2026-04-22
slug: ris_phase2a_activation_override
type: dev-log
work-unit: docs-governance
---

# RIS Phase 2A Activation Override

## Objective

Activate RIS Operational Readiness — Phase 2A as an Active feature in `docs/CURRENT_DEVELOPMENT.md`, resolving a trigger conflict between two governance docs. Documentation-only change — no application code touched.

## Files Changed

| File | Change | Why |
|------|--------|-----|
| `docs/CURRENT_DEVELOPMENT.md` | Feature 2 slot: `[empty slot]` → RIS Phase 2A Active entry | Director decision to activate now; both triggers satisfied |
| `docs/CURRENT_DEVELOPMENT.md` | Paused table RIS row: updated Paused date to `ACTIVATED`, resume trigger to `N/A — now Active` | Removes stale trigger that would confuse future Architect reads |
| `docs/CURRENT_DEVELOPMENT.md` | Notes for the Architect: added RIS Phase 2A active note + Hermes out-of-scope warning | Prevents Architect from designing Phase 2A prompts with Hermes |
| `docs/dev_logs/2026-04-22_ris_phase2a_activation_override.md` | Created (this file) | Mandatory dev log per repo conventions |

## Contradictions Found and Resolution

### Contradiction 1: Dual activation triggers

**RIS roadmap v1.1** (`docs/obsidian-vault/Claude Desktop/09-Decisions/RIS_OPERATIONAL_READINESS_ROADMAP_v1.1.md`) governance section states:
> "When Feature 2 (Fee Model) completes, Feature 3 becomes RIS Operational Readiness — Phase 2A"

Fee Model Overhaul (PMXT Deliverable A) completed 2026-04-21. This trigger was **already satisfied**.

**CURRENT_DEVELOPMENT.md Paused table** (pre-edit) stated resume trigger as:
> "Track 2 ships first dollar OR explicit Director decision"

This secondary trigger was added in a later edit and was **not yet satisfied** (Track 2 soak not yet run).

**Resolution:** Director explicit decision on 2026-04-22 satisfies the OR branch of the secondary trigger. Both triggers are now resolved. The Paused row is updated to reflect the promotion; the Active entry records the override rationale so future readers understand why activation preceded the Track 2 soak milestone.

### Contradiction 2: RIS roadmap "Current Project Context" stale

The RIS roadmap v1.1 still describes Feature 2 (Fee Model) as "near completion" — it completed 2026-04-21. This is a vault doc (not agent-behavior-critical) and updating it is non-blocking docs debt. Not corrected in this session to minimize blast radius.

## Commands Run

Targeted greps to confirm no remaining contradiction:

```
grep -n "RIS" docs/CURRENT_DEVELOPMENT.md
```
Expected: Feature 2 Active entry + Paused row marked ACTIVATED + Notes for Architect bullet. Confirmed.

```
grep -rn "Track 2 ships first dollar" docs/
```
Expected: Zero hits (the stale trigger phrase removed from active governance). Confirmed stale trigger is gone from the Paused row.

```
grep -n "Hermes" docs/CURRENT_DEVELOPMENT.md
```
Expected: Two hits — Feature 2 Hermes scope line + Architect note. Confirms Hermes exclusion is recorded in both the operational entry and the agent-facing note.

Smoke test (CLI load):
```
python -m polytool --help
```
No application code was changed; this is a docs-only session. CLI should load cleanly. Run to confirm no import regressions from unrelated changes.

## Remaining Non-Blocking Docs Debt

1. **RIS roadmap v1.1 "Current Project Context" section** — still says Fee Model is "near completion." Vault doc; not agent-behavior-critical. Update at the start of the next RIS session to keep the roadmap internally consistent.

2. **Four completion-doc debt items** (tracked in Completion-Doc Debt section of CURRENT_DEVELOPMENT.md) — pre-existing, unrelated to this activation. Estimated 2h Claude Code time when ready.

3. **CURRENT_STATE.md RIS section** — likely still reflects pre-Phase-2A status. Will be updated as part of RIS Phase 2A DoD (final checklist item).

## Codex Review Summary

Not applicable — docs-only change, no mandatory or recommended review files touched. Skipped per Codex Review Policy.

## Recommended Next Work Unit: WP1 Foundation Fixes

**Session target:** Day 1 of RIS Phase 2A (~2–3 hours)

**WP1 acceptance criteria (from RIS roadmap v1.1):**

1. **Scoring weights corrected** — audit current `ManualProvider` hardcoded scores; replace with dimension-weighted scoring per roadmap spec
2. **`provider_event` fix** — confirm the missing-field bug from Phase 2 audit is patched; add regression test
3. **R0 seed** — run `research-acquire` to seed 11+ external docs into the knowledge store (the Phase 2 audit found R0 was never run)
4. **Open-source findings seeding** — seed 5 open-source strategy/findings docs via `research-ingest`

**Suggested discovery commands before writing code:**

```bash
# Confirm current knowledge store state
python -m polytool research-health
python -m polytool research-stats summary

# Check what R0 seeding produced (or didn't)
python -m polytool rag-query --question "retrieval benchmark" --hybrid --knowledge-store default

# Confirm provider_event field presence in ingested docs
python -m polytool research-precheck inspect --db kb/rag/knowledge/knowledge.sqlite3
```

**Do not start WP2 (cloud LLM providers) until WP1 acceptance criteria pass.** WP1 is the foundation that WP2 routing depends on.
