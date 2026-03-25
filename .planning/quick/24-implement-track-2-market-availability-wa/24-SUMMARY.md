---
phase: quick-24
plan: 01
subsystem: crypto-pair-bot
tags: [track2, market-watch, availability, phase-1a, cli]
dependency_graph:
  requires: [market_discovery.py, crypto_pair_scan.py patterns]
  provides: [crypto-pair-watch command, market_watch.py, AvailabilitySummary]
  affects: [polytool CLI, crypto pair operator workflow]
tech_stack:
  added: []
  patterns: [injectable _sleep_fn/_check_fn for offline testing, dataclasses.asdict for JSON, same module layout as crypto_pair_scan.py]
key_files:
  created:
    - packages/polymarket/crypto_pairs/market_watch.py
    - tools/cli/crypto_pair_watch.py
    - tests/test_crypto_pair_watch.py
    - docs/features/FEATURE-crypto-pair-watch-v0.md
    - docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md
  modified:
    - polytool/__main__.py
decisions:
  - No classifier fork: run_availability_check delegates to discover_crypto_pair_markets directly
  - Injectable _sleep_fn/_check_fn enables full offline testing without real time.sleep
  - One-shot mode exits 0 always (informational); only watch timeout exits 1
  - --symbol/--duration flags reserved in v0, accepted but do not filter Gamma query
  - dataclasses.asdict for canonical AvailabilitySummary JSON serialization
metrics:
  duration: 323s
  completed: 2026-03-25T22:24:20Z
  tasks_completed: 2
  files_created: 5
  files_modified: 1
---

# Phase quick-24 Plan 01: Crypto Pair Market Availability Watcher Summary

**One-liner:** Lightweight `crypto-pair-watch` CLI that polls Gamma for active BTC/ETH/SOL 5m/15m markets, writes dated artifact bundles, and exits 0 (found) or 1 (timeout) — closing the operational gap while markets are offline.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | market_watch.py: AvailabilitySummary, run_availability_check, run_watch_loop | 54be7be |
| 2 | CLI, __main__ registration, 20 tests, feature doc, dev log | 6c2c0e9 |

## Verification Results

```
python -m polytool crypto-pair-watch --help   # exits 0, shows all flags
python -m pytest tests/test_crypto_pair_watch.py tests/test_crypto_pair_scan.py -q
# 80 passed in 2.44s

python -m pytest tests/ -x -q --tb=short
# 921 passed, 1 pre-existing failure (test_scan_gate2_parser_accepts_enrich_flag — unrelated)
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- packages/polymarket/crypto_pairs/market_watch.py: FOUND
- tools/cli/crypto_pair_watch.py: FOUND
- tests/test_crypto_pair_watch.py: FOUND
- docs/features/FEATURE-crypto-pair-watch-v0.md: FOUND
- docs/dev_logs/2026-03-25_phase1a_crypto_pair_watch_v0.md: FOUND
- polytool/__main__.py: modified (crypto_pair_watch_main registered)
- Commits 54be7be and 6c2c0e9: FOUND
