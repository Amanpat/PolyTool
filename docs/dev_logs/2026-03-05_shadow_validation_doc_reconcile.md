# Shadow Validation Doc Reconcile - 2026-03-05

## Reason for change

Operator documentation was describing two different validation models:

- a historical "30-day shadow validation" concept
- the current gate harness plus Stage 0 paper-live flow

This update reconciles the docs to a single canonical pipeline so operators
follow one process:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

Historical clarification added across the touched docs:

- The old "30-day shadow validation" wording is obsolete.
- The replacement is Gate 3 shadow validation, Gate 4 dry-run live, and a
  separate 72 hour Stage 0 paper-live run before Stage 1 capital.

## Files changed

### `README.md`

- Updated quick status wording to show Stage 0 as the 72 hour paper-live step
  and Stage 1 as blocked on a clean Stage 0, not just gate closure.
- Clarified Part 4 / Part 5 boundary so Stage 0 is separate from the four
  gates.
- Clarified Gate 3 as the shadow validation gate rather than a long shadow
  period.
- Added `Validation Pipeline (Canonical)`.

Lines updated:

- `README.md:20-22`
- `README.md:272-275`
- `README.md:317-320`
- `README.md:1081-1095`

### `docs/ROADMAP.md`

- Reframed Track A promotion steps to include Stage 0 and Stage 1 explicitly.
- Added `Validation Pipeline (Canonical)`.
- Updated the hard promotion order and the gate-status interpretation text.
- Updated the global kill condition so "no live capital" now means gates plus
  Stage 0, not just the four gates.

Lines updated:

- `docs/ROADMAP.md:262-287`
- `docs/ROADMAP.md:318-320`
- `docs/ROADMAP.md:474-475`

### `docs/CURRENT_STATE.md`

- Updated the sprint summary so Stage 1 remains blocked until gates close and
  Stage 0 completes cleanly.
- Added `Validation Pipeline (Canonical)`.
- Expanded the optional execution path to include Stage 0 and Stage 1.
- Updated the validation-order summary and Stage 1 readiness wording.

Lines updated:

- `docs/CURRENT_STATE.md:9-11`
- `docs/CURRENT_STATE.md:44-58`
- `docs/CURRENT_STATE.md:161-170`
- `docs/CURRENT_STATE.md:185-187`

### `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md`

- Added Stage 0 completion to the Stage 1 prerequisites.
- Added `Validation Pipeline (Canonical)`.
- Clarified that the runbook assumes Stage 0 operator sign-off even though the
  CLI itself only enforces gate artifacts.

Lines updated:

- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md:5-7`
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md:13-27`
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md:40-41`

## Final validation pipeline

Use this as the canonical operator sequence:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

## Notes

- No Python code, trading logic, or gate scripts were modified.
- The reconciliation was limited to the approved documentation files plus this
  dev log.
