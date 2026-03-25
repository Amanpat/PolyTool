---
phase: quick-23
plan: 01
subsystem: crypto-pair-track2
tags: [smoke-soak, coinbase, reference-feed, market-availability, paper-mode]
dependency_graph:
  requires: [quick-022, coinbase-reference-feed-v1]
  provides: [coinbase-smoke-soak-evidence, track2-unblock-status]
  affects: [phase-1a-track2]
tech_stack:
  added: []
  patterns: [paper-runner, market-discovery, crypto-pair-report]
key_files:
  created:
    - docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md
  modified: []
decisions:
  - Outcome classified as BLOCKED (not THIN BUT VALID) because markets_seen=0 indicates no market availability, not just low economic activity
  - Coinbase feed implementation confirmed correct — blocker has shifted from reference feed to Polymarket market schedule
metrics:
  duration: "~30 minutes (20m soak + preflight + report + dev log)"
  completed: "2026-03-25"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 0
---

# Phase Quick-23 Plan 01: Coinbase Smoke Soak Rerun Summary

Executed the Coinbase-based rerun smoke soak for Phase 1A Track 2. The Coinbase reference feed implementation is confirmed working at the code level, but Track 2 remains blocked due to Polymarket having zero active BTC/ETH/SOL 5m/15m binary pair markets.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Preflight, visibility check, and smoke soak execution | 1c73cec | artifacts/crypto_pairs/paper_runs/2026-03-25/5f2044680e59/* |
| 2 | Generate report and write dev log with verdict | 1c73cec | docs/dev_logs/2026-03-25_phase1a_coinbase_smoke_soak_rerun.md |

## Run Evidence

**Run ID**: `5f2044680e59`
**Artifact Path**: `artifacts/crypto_pairs/paper_runs/2026-03-25/5f2044680e59/`
**Duration**: 20 minutes (1200 seconds, 240 cycles)
**Stopped Reason**: completed

| Metric | Value |
|--------|-------|
| reference_feed_provider | coinbase (confirmed in config_snapshot.json) |
| markets_seen | 0 |
| markets_discovered (per cycle) | 0 (all 240 cycles) |
| runtime_events | 748 |
| opportunities_observed | 0 |
| order_intents_generated | 0 |
| paired_exposure_count | 0 |
| settled_pair_count | 0 |
| rubric verdict | RERUN PAPER SOAK |
| rubric_pass | false |
| safety_count | 0 |
| sink_enabled | no (CLICKHOUSE_PASSWORD not set) |

## Outcome Classification

**BLOCKED**

The Coinbase feed unblock (quick-022's blocker: Binance HTTP 451) is confirmed resolved. The `--reference-feed-provider coinbase` flag is accepted, `config_snapshot.json` records `reference_feed_provider = "coinbase"`, and the runner completed 240 cycles cleanly. However, `markets_discovered = 0` every cycle because Polymarket currently has no active BTC/ETH/SOL 5m/15m binary pair markets.

Direct verification: `discover_crypto_pair_markets()` returned 0 markets. A broader check of 1000 active Polymarket markets found 8 crypto-related markets, all long-duration (price milestones, FDV targets). Zero matched the 5m/15m binary pair pattern.

## Track 2 Status

**STILL BLOCKED** — Market availability blocker

The nature of the blocker has changed:
- Previous blocker: Binance HTTP 451 geo-restriction (RESOLVED by Coinbase implementation)
- Current blocker: Polymarket has no active BTC/ETH/SOL 5m/15m binary markets

When markets reappear, the smoke soak command is ready to go:
```bash
python -m polytool crypto-pair-run \
  --reference-feed-provider coinbase \
  --duration-seconds 1800 \
  --heartbeat-seconds 60
```

## Deviations from Plan

None — plan executed exactly as written. The BLOCKED outcome is consistent with the outcome classification rules in the plan: `markets_seen = 0` with no feed data in runtime observations qualifies as BLOCKED. The specific reason (market availability vs feed failure) is documented in the dev log.

## Self-Check

- [x] run_manifest.json confirms stopped_reason = "completed"
- [x] config_snapshot.json confirms reference_feed_provider = "coinbase"
- [x] paper_soak_summary.json exists (produced by crypto-pair-report)
- [x] Dev log exists with verdict and Track 2 status line
- [x] No code changes made (git diff clean except new dev log)
- [x] Artifact files are gitignored and do not appear in git status
