---
phase: quick-260414-qre
plan: "01"
subsystem: simtrader/shadow-capture
tags: [gold-capture, tape-validator, path-fix, corpus-audit]
dependency_graph:
  requires: []
  provides: [canonical-shadow-tape-path, tape-quality-verdict]
  affects: [simtrader-shadow-cli, corpus-audit-visibility, gate2-capture-workflow]
tech_stack:
  added: [tape_validator module]
  patterns: [streaming-jsonl-parse, dataclass-result, inline-post-run-validation]
key_files:
  created:
    - packages/polymarket/simtrader/tape_validator.py
    - tests/test_gold_capture_hardening.py
    - docs/dev_logs/2026-04-14_gold_capture_hardening.md
  modified:
    - tools/cli/simtrader.py
decisions:
  - Shadow tape_dir moves to DEFAULT_SHADOW_TAPE_DIR (artifacts/tapes/shadow) so writes are under corpus_audit's default scan roots
  - Validator is a fast structural pre-check only -- arb eligibility (requires strategy config) is a separate heavier check
  - Streaming line-by-line parse to satisfy T-qre-03 DoS threat mitigation
metrics:
  duration: "~20 minutes"
  completed: "2026-04-14"
  tasks_completed: 2
  files_changed: 4
---

# Phase quick-260414-qre Plan 01: Gold Tape Capture Hardening Summary

**One-liner:** Fixed shadow tape write path from `artifacts/simtrader/tapes/` to `artifacts/tapes/shadow/` (corpus-audit visible) and added streaming tape validator that prints PASS/BLOCKED/WARN verdict with L2 book presence check after every capture.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix shadow write path + create tape_validator | cf952a1 | tools/cli/simtrader.py, packages/polymarket/simtrader/tape_validator.py |
| 2 | Wire validator into CLI output + tests + dev log | 93b1484 | tools/cli/simtrader.py, tests/test_gold_capture_hardening.py, docs/dev_logs/2026-04-14_gold_capture_hardening.md |

## Verification Results

- `python -c "from tools.cli.simtrader import DEFAULT_SHADOW_TAPE_DIR; print(DEFAULT_SHADOW_TAPE_DIR)"` → `artifacts\tapes\shadow`
- `python -c "from packages.polymarket.simtrader.tape_validator import validate_captured_tape; print('ok')"` → `ok`
- `python -m pytest tests/test_gold_capture_hardening.py -v` → **10 passed**
- `python -m pytest tests/ -x -q --tb=short` → **2470 passed, 1 pre-existing failure** (test_gemini_provider_success — confirmed pre-existing before this work)
- `python -m polytool --help` → CLI loads without errors
- `config/benchmark_v1.*` files: **not modified**

## What Was Built

### 1. Shadow tape write path fix (tools/cli/simtrader.py)

Added constant:
```python
DEFAULT_SHADOW_TAPE_DIR = Path("artifacts/tapes/shadow")
```

Changed `tape_dir` assignment in `_shadow()`:
```python
# Before: tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / run_id
tape_dir = DEFAULT_SHADOW_TAPE_DIR / run_id
```

This resolves the path drift that made shadow tapes invisible to corpus_audit.
The CLI output already printed `artifacts/tapes/shadow/<run_id>/` -- the actual
write now matches. `DEFAULT_ARTIFACTS_DIR` and `run_dir` were not changed.

### 2. Tape validator module (packages/polymarket/simtrader/tape_validator.py)

`TapeValidationResult` dataclass with: verdict, reason, events_total, effective_events,
asset_count, has_l2_book, has_price_change, has_watch_meta, has_meta_json, event_type_counts.

`validate_captured_tape(tape_dir, min_effective_events=50)` verdict priority:
- BLOCKED: no events.jsonl
- BLOCKED: empty tape (0 parseable events)
- BLOCKED: no `book` events (price-only -- L2Book never initializes)
- WARN: effective_events < min_effective_events
- WARN: missing watch_meta.json
- PASS: all checks clear

Streaming line-by-line JSONL parse. Handles malformed lines with try/except continue.
No network calls, no heavy imports, no file writes.

### 3. Post-capture output block (tools/cli/simtrader.py)

Printed after every shadow capture with tape recording:
```
--- Tape Quality Check ---
  Result     : BLOCKED
  price-only tape -- no L2 book events, fill engine will reject all orders with book_not_initialized
  L2 book    : NO
  Events     : 60 raw, 60 effective (1 assets)
  Event types: price_2min_guide=60
--------------------------
```

### 4. Tests (tests/test_gold_capture_hardening.py)

10 tests across 5 classes:
- TestCanonicalShadowPath (2): path constant value, corpus_audit root coverage
- TestTapeValidatorBlocked (3): no file, price-only, empty file
- TestTapeValidatorPass (2): Gold L2 tape, binary asset effective_events
- TestTapeValidatorWarn (2): low event count, missing watch_meta
- TestOperatorOutput (1): reason contains greppable failure mode text

## Deviations from Plan

None -- plan executed exactly as written.

## What Was NOT Changed (Scope Discipline)

- No changes to `config/benchmark_v1.*` files
- No changes to BrokerSim fill logic
- No changes to Gate 2 sweep logic or thresholds
- No changes to `DEFAULT_ARTIFACTS_DIR` (still `artifacts/simtrader`)
- No changes to `run_dir` (stays at `artifacts/simtrader/shadow_runs/<run_id>`)
- No changes to corpus_audit DEFAULT_TAPE_ROOTS
- No weakening of gate language or validation criteria

## Known Stubs

None.

## Threat Flags

None. All surface changes are local filesystem reads and stdout writes. No new network
endpoints, auth paths, or schema changes.

## Self-Check: PASSED

- `D:/Coding Projects/Polymarket/PolyTool/packages/polymarket/simtrader/tape_validator.py` -- FOUND
- `D:/Coding Projects/Polymarket/PolyTool/tests/test_gold_capture_hardening.py` -- FOUND
- `D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-14_gold_capture_hardening.md` -- FOUND
- Commit cf952a1 -- FOUND
- Commit 93b1484 -- FOUND
