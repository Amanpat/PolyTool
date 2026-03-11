---
date_utc: 2026-03-05
run_type: docs
subject: Align Track A scope/gates with Track B completion
---

# Track A/Track B Docs Alignment

## Objective

Align core docs so Track B foundation is explicitly complete and Track A is
explicitly in-scope but gated.

Scope: documentation only. No Python code changes.

## What changed

- Added Track alignment language to `docs/PLAN_OF_RECORD.md`:
  - Track B foundation complete (`wallet-scan` v0, `alpha-distill` v0, RAG/hypothesis scaffolding baseline).
  - Track A optional and gated (`replay -> scenario sweeps -> shadow -> dry-run live`).
  - No live capital before gates; research outputs are not signals.
- Added Track A optional execution section to `docs/ARCHITECTURE.md`:
  - Gated execution loop.
  - Explicit rule that execution runs only operator-supplied, gate-passing strategies.
  - Pointer to new live execution spec.
- Added status and Track A gating section to `docs/CURRENT_STATE.md`.
- Updated `docs/ROADMAP.md`:
  - Kept Track B marked complete with explicit summary.
  - Added `Track A - Optional Execution Layer [IN SCOPE, GATED]`.
  - Added global stop-condition bullet: no live capital before Track A gates.
- Updated `docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md`:
  - Refreshed implementation-status date to 2026-03-05.
  - Added cross-spec alignment note for Track A gating and non-signal policy.
- Added new spec `docs/specs/SPEC-0011-live-execution-layer.md`:
  - Purpose/scope.
  - Interfaces: `LiveExecutor`, `RiskManager`, `KillSwitch`, `LiveRunner` (dry-run default).
  - Non-goals: no market orders, no alpha logic, no live by default.
  - Hard friction checklist: fees, spread/slippage logging, conservative queue, rate limit, latency scenarios, WS disconnect handling, kill switch, daily loss cap, inventory limits, capital stages.

## Why

Previous docs described SimTrader and Track B progress but did not consistently
frame Track A as optional, gated execution work. This update removes that
ambiguity and keeps the research-vs-execution boundary explicit.

## Guardrails

- Docs-only patch.
- No Python source edits.
