# Dev Log: Gate 2 Preflight

**Date:** 2026-03-08
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What was built

Added `python -m polytool gate2-preflight`, a small operator-safety command for
Track A.

It reuses the existing Gate 2 tape-manifest logic and reports:
- `READY` or `BLOCKED`
- eligible tape count and tape list
- mixed-regime coverage and missing regimes
- the exact next action

### Why

Operators had to inspect `tape-manifest` output manually and infer whether the
sweep was truly safe to start. That left too much room for starting
`close_sweep_gate.py` when there were still zero eligible tapes or incomplete
regime coverage.

### Implementation

- Added a new CLI at `tools/cli/gate2_preflight.py`
- Reused `scan_tapes_dir(...)` and `build_corpus_summary(...)` from `tape_manifest`
- Returned exit code `0` for `READY` and `2` for `BLOCKED`
- Kept all existing gate criteria unchanged

---

## Files changed

| File | What changed |
|------|-------------|
| `tools/cli/gate2_preflight.py` | New preflight CLI built on top of existing tape-manifest logic |
| `polytool/__main__.py` | Registered `gate2-preflight` in the main CLI dispatcher |
| `tests/test_gate2_eligible_tape_acquisition.py` | Added READY, zero-eligible BLOCKED, missing-coverage BLOCKED, and stable dispatcher output tests |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Added preflight as the required step before running the sweep |
| `docs/features/FEATURE-gate2-preflight.md` | Feature note |
| `docs/dev_logs/2026-03-08_gate2_preflight.md` | This file |
| `docs/INDEX.md` | Added feature/dev-log index entries |

---

## Test results

```bash
pytest -q tests/test_gate2_eligible_tape_acquisition.py
```

Result: 55 passed.
