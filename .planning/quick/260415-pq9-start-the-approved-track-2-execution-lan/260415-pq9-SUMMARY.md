---
phase: quick
plan: 260415-pq9
subsystem: crypto-pair-run CLI
tags: [track2, dry-run, preflight, cli, testing]
dependency_graph:
  requires: []
  provides: [crypto-pair-run --dry-run preflight mode]
  affects: [tools/cli/crypto_pair_run.py, tests/test_crypto_pair_run.py]
tech_stack:
  added: []
  patterns: [argparse flag, early-return dry-run pattern, operator-readable summary formatter]
key_files:
  created:
    - docs/dev_logs/2026-04-15_track2_execution_lane_a.md
  modified:
    - tools/cli/crypto_pair_run.py
    - tests/test_crypto_pair_run.py
decisions:
  - Dry-run early-return placed after build_runner_settings() so config validation always fires before discovery
  - format_preflight_summary() kept as a separate public function to enable direct testing without CLI invocation
  - _make_gamma_client_with_targeted() helper added to tests to mock both discovery paths (fetch_all_markets + fetch_markets_filtered)
  - Dry-run path exits before ClickHouse password check — operators can preview without credentials
metrics:
  duration_minutes: 45
  completed_date: "2026-04-15T22:43:59Z"
  tasks_completed: 3
  tasks_planned: 3
  files_created: 1
  files_modified: 2
---

# Quick 260415-pq9: --dry-run preflight mode for crypto-pair-run Summary

**One-liner:** Added `--dry-run` argparse flag to `crypto-pair-run` CLI with market discovery, symbol/duration filtering, and operator-readable targeting summary — no cycles, no artifacts, no credentials required.

## Objective

Add a `--dry-run` preflight mode so operators can validate config and preview
eligible BTC/ETH/SOL markets before committing to a paper soak, without
connecting reference feeds, writing artifacts, or needing a ClickHouse password.

## Tasks Completed

| Task | Description | Commit | Files |
|---|---|---|---|
| 1 | Implement --dry-run in crypto_pair_run.py | `50abcb1` | tools/cli/crypto_pair_run.py |
| 2 | Add 6 deterministic tests | `e899171` | tests/test_crypto_pair_run.py |
| 3 | Write dev log | `8052861` | docs/dev_logs/2026-04-15_track2_execution_lane_a.md |

## What Was Built

### `tools/cli/crypto_pair_run.py`

- `--dry-run` flag added to `build_parser()` (boolean, default False)
- `format_preflight_summary(preflight: dict) -> str` — new public function rendering:
  - Mode, active filters, ref feed, duration, cycle interval
  - Operator safety caps (from paper_runner module-level constants)
  - Eligible markets list with slug, symbol, duration, active/accepting status
  - WARNING line when markets list is empty
- `run_crypto_pair_runner(dry_run=False, ...)` — added `dry_run` parameter; early return after `build_runner_settings()` returning `{"dry_run": True, "preflight": {...}}`
- `main()` — dry-run branch before ClickHouse password check; catches `ConfigLoadError`/`ValueError`, prints summary, exits 0

### `tests/test_crypto_pair_run.py`

Six new tests (file total: 23 passing):

| Test | Coverage |
|---|---|
| `test_dry_run_flag_parsed` | Parser wires flag and defaults to False |
| `test_dry_run_returns_preflight_without_running_cycles` | Returns preflight dict; clob.get_best_bid_ask call count = 0 |
| `test_dry_run_applies_symbol_filter` | BTC filter excludes ETH markets |
| `test_dry_run_shows_zero_markets_warning` | Empty gamma → format_preflight_summary warns |
| `test_dry_run_does_not_create_artifacts` | output_base dir stays empty |
| `test_dry_run_validates_config_errors` | duration_seconds=-1 raises ValueError |

## Verification Results

```
tests/test_crypto_pair_run.py: 23 passed in 1.57s
Full suite: 2510 passed, 1 failed (pre-existing: test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success — AttributeError on missing _post_json attribute, confirmed pre-existing on clean state)
```

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — format_preflight_summary renders real data from discover_crypto_pair_markets().

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. Dry-run is read-only.

## Self-Check: PASSED

- [x] `tools/cli/crypto_pair_run.py` — exists and importable
- [x] `tests/test_crypto_pair_run.py` — 23 tests pass
- [x] `docs/dev_logs/2026-04-15_track2_execution_lane_a.md` — created
- [x] Commits `50abcb1`, `e899171`, `8052861` — all present in git log
