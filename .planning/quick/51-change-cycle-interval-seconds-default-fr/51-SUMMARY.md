---
phase: quick-051
plan: "01"
subsystem: crypto-pair-bot
tags: [config, cycle-interval, paper-runner, quick]
dependency_graph:
  requires: [quick-049]
  provides: [faster-cycle-interval]
  affects: [paper-runner, cli, tape-integrity-audit]
key_files:
  modified:
    - packages/polymarket/crypto_pairs/paper_runner.py
    - tools/cli/crypto_pair_run.py
    - tools/gates/tape_integrity_audit.py
metrics:
  completed: "2026-03-29"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 3
  tests_added: 0
  regression_suite: "2767 passed, 0 failed"
---

# Quick Task 051: cycle_interval_seconds default 5 → 0.5

Changed the crypto pair paper runner cycle interval from 5 seconds to 500ms.

## Changes

| File | Change |
|------|--------|
| `paper_runner.py:125` | `int = 5` → `float = 0.5` |
| `paper_runner.py:300` | `int(payload.get(..., 5))` → `float(payload.get(..., 0.5))` |
| `crypto_pair_run.py:273` | `Optional[int]` → `Optional[float]` |
| `crypto_pair_run.py:81` | argparse `type=int` → `type=float`, help `or 5` → `or 0.5` |
| `tape_integrity_audit.py` | `_get_runner_scan_cadence()` return type `Optional[int]` → `Optional[float]`, matches `float` in line, uses `float(val_str)` |

`asyncio.sleep(self.settings.cycle_interval_seconds)` at `paper_runner.py:696` accepts float natively — no integer casting in the sleep path.

## Regression

2767 passed, 0 failed.
