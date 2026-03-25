# Feature: Gate 2 Preflight

**Spec**: `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md`
**Status**: Shipped
**Date**: 2026-03-08
**Branch**: simtrader

---

## What this feature does

Adds a dedicated `gate2-preflight` operator command that answers one question
before the sweep runs:

Is Gate 2 actually ready right now?

The command reuses the existing tape-manifest eligibility and regime-coverage
logic, then prints:
- `READY` or `BLOCKED`
- eligible tape count
- which tapes are eligible
- covered and missing regimes
- the exact next action

Exit codes are operator-safe:
- `0` for `READY`
- `2` for `BLOCKED`
- `1` for CLI or argument errors

---

## Changed files

| File | Change |
|------|--------|
| `tools/cli/gate2_preflight.py` | New small CLI that reuses tape-manifest eligibility + coverage logic and returns `READY`/`BLOCKED` |
| `polytool/__main__.py` | Added `gate2-preflight` command routing and help text |
| `tests/test_gate2_eligible_tape_acquisition.py` | Added READY/BLOCKED and dispatcher/exit-code coverage |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Added the preflight step before running the sweep |

---

## Invariants preserved

- Tape eligibility is unchanged: `eligible` still requires `executable_ticks > 0`
- Mixed-regime policy is unchanged and still uses the shared regime-coverage helper
- The command is visibility-only; it does not soften or override any gate criteria
