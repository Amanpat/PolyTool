---
phase: quick-052
plan: 01
subsystem: crypto-pair-bot
tags: [dashboard, terminal-ui, duration-bug-fix, verbose-flag, paper-mode]
dependency_graph:
  requires: []
  provides: [crypto-pair-paper-mode-dashboard, duration-bug-fix]
  affects: [packages/polymarket/crypto_pairs/paper_runner.py, tools/cli/crypto_pair_run.py]
tech_stack:
  added: []
  patterns: [module-level-helper-functions, flush=True-print-output, wall-clock-duration-guard]
key_files:
  created: []
  modified:
    - packages/polymarket/crypto_pairs/paper_runner.py
    - tools/cli/crypto_pair_run.py
    - tests/test_crypto_pair_run.py
decisions:
  - Dashboard functions are module-level helpers (not methods) to keep them testable in isolation without runner construction
  - Stats line printed every 10 seconds by wall-clock elapsed check (not cycle count) to match non-uniform cycle timing
  - Verbose market line limit of 8 per cycle prevents terminal flooding on large discovery sets
  - Duration wall-clock guard added after sleep at end of each cycle; pre-computed total_cycles remains as upper bound safety net
metrics:
  duration_minutes: 45
  completed_date: "2026-03-29"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 3
  tests_added: 8
  tests_total: 2775
---

# Phase quick-052 Plan 01: Live Terminal Dashboard + Duration Bug Fix Summary

**One-liner:** Added real-time terminal dashboard to paper mode runner (startup header, per-cycle market lines in verbose mode, stats every 10s, highlighted signals/intents) and fixed duration timer to use wall-clock elapsed check instead of pre-computed cycle count.

## Tasks Completed

| Task | Name | Commit | Files |
| ---- | ---- | ------ | ----- |
| 1 | Fix duration timer bug and implement dashboard module in paper_runner.py | cef8f3a | packages/polymarket/crypto_pairs/paper_runner.py, tests/test_crypto_pair_run.py |
| 2 | Wire --verbose flag through CLI and add tests | c6f3909 | tools/cli/crypto_pair_run.py |

## What Was Built

### Duration Bug Fix
The pre-existing bug: `cycle_count_from_settings()` pre-computes `math.ceil(duration_seconds / cycle_interval_seconds)`, but each cycle takes longer than `cycle_interval_seconds` due to discovery and scan time. A 30-second run with 0.5s intervals would be allocated 60 cycles but each cycle took 5-10s in practice, meaning the run lasted far longer than requested.

Fix: Added a wall-clock elapsed check at the end of each cycle body (after the sleep call):
```python
_elapsed = (self.now_fn() - self.store.started_at).total_seconds()
if self.settings.duration_seconds > 0 and _elapsed >= self.settings.duration_seconds:
    break
```
The pre-computed `total_cycles` remains as an upper-bound safety net for fast discovery paths.

### Dashboard Module
Five module-level helper functions added to `paper_runner.py` after `format_elapsed_runtime`:

- `_dashboard_header(settings, market_count, started_at_str)` — startup banner with symbols/feed/cycle/threshold/market-count
- `_dashboard_market_line(*, ts, opportunity, ref_price, price_change_pct, signal_direction, action)` — one status line per market per cycle; includes `>>> SIGNAL: UP/DOWN <<<` annotation when signal fires
- `_dashboard_intent_line(*, ts, intent)` — `*** INTENT: ... ***` line with leg prices and notionals
- `_dashboard_stats_line(*, cycle, observations, signals, intents, elapsed_seconds, duration_seconds)` — `[STATS] Cycles: N | ... | Duration: Xm Ys | Remaining: Xm Ys`
- `_fmt_duration(secs)` — internal helper for Xm Ys formatting

### CryptoPairPaperRunner Wiring
- `__init__` accepts `verbose: bool = False` and stores `self._verbose`
- Dashboard state: `self._dashboard_signal_count`, `self._dashboard_last_stats_at`, `self._dashboard_markets_found`, `self._dashboard_cycle_market_count`
- `run()` prints startup header once before loop; resets cycle market count each iteration; prints stats every 10 seconds; applies wall-clock duration guard
- `_process_opportunity()` captures rationale keys (`signal_direction`, `reference_price`, `price_change_pct`); prints market line when verbose or signal active; increments `_dashboard_signal_count`; prints intent line unconditionally after `record_intent()`
- Verbose market line limited to 8 per cycle (cycle counter reset each iteration)

### CLI Flag
`--verbose` added to `build_parser()`, `verbose: bool = False` param added to `run_crypto_pair_runner()`, wired through to `CryptoPairPaperRunner` constructor, passed as `verbose=args.verbose` in `main()`.

## Tests Added (8 new)

| Test | What It Covers |
| ---- | -------------- |
| `test_duration_stops_on_elapsed_time` | Runner stops early when advancing clock exceeds duration_seconds mid-range |
| `test_duration_runs_all_cycles_when_fast` | Runner completes all cycle_limit cycles when elapsed never exceeds duration |
| `test_dashboard_header_format` | Header contains market count, started-at, separator |
| `test_dashboard_market_line_no_signal` | Market line shows "Signal: NONE", no ">>>" |
| `test_dashboard_market_line_signal` | Signal line shows ">>> SIGNAL: UP", "BUY YES" |
| `test_dashboard_stats_line` | Stats line shows correct remaining time "12m 30s" |
| `test_verbose_flag_parsed` | `--verbose` parses to `args.verbose is True` |
| `test_verbose_flag_default_false` | Default parse gives `args.verbose is False` |

## Deviations from Plan

None — plan executed exactly as written. The `test_simtrader_batch::test_batch_time_budget_stops_launching_new_markets` failure that surfaced during full-suite run was confirmed to be a pre-existing flaky test (threading race condition / `StopIteration` in background thread). It passes consistently in isolation and also passed during the final full-suite run (2775 passed, 0 failed).

## Verification Results

```
python -m pytest tests/ -q --tb=short   => 2775 passed, 0 failed, 25 warnings
python -m pytest tests/test_crypto_pair_run.py -q  => 17 passed
python -m polytool crypto-pair-run --help | grep verbose  => --verbose flag shown
```

## Known Stubs

None — all dashboard output paths are wired to live runner state.

## Self-Check: PASSED
