# Dev Log: Track 2 Operator Runbook Creation

**Date:** 2026-04-15
**Task:** quick-260415-pqc
**Author:** Claude Code (executor)

---

## Summary

Created `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` -- the single operator-facing doc for
running the Track 2 crypto pair bot end-to-end. Covers preflight checks, market
availability, dry-run scan, 24h paper soak launch, safety checklist, stop conditions,
and what Track 2 approval means (and does not mean) regarding Gate 2.

---

## Files Changed

| File | Action |
|------|--------|
| `docs/runbooks/TRACK2_OPERATOR_RUNBOOK.md` | Created (354 lines) |
| `docs/dev_logs/2026-04-15_track2_operator_runbook.md` | Created (this file) |

---

## Context

Option 3 (Track 2 focus) was approved per the Gate 2 decision packet
(`docs/dev_logs/2026-04-15_gate2_decision_packet.md`). Track 2 is the active revenue
path as of 2026-04-15. The operator needed a single runbook to execute Track 2 paper
soaks without hunting across 30+ feature docs and dev logs.

Gate 2 remains FAILED (7/50 = 14%, threshold 70%). No gate thresholds, benchmark
manifests, or policy documents were changed.

---

## Commands Run and Output

### 1. CLI loads without import errors

```
python -m polytool --help
```

Output (truncated to first 5 subcommands):
```
PolyTool - Polymarket analysis toolchain

Usage: polytool <command> [options]
       python -m polytool <command> [options]

--- Research Loop (Track B) -------------------------------------------
  wallet-scan           Batch-scan many wallets/handles -> ranked leaderboard
  alpha-distill         Distill wallet-scan data -> ranked edge candidates (no LLM)
  ...
```
Result: PASS -- CLI loads, no import errors.

### 2. crypto-pair-watch --help

```
python -m polytool crypto-pair-watch --help
```

Output:
```
usage: __main__.py [-h] [--symbol {BTC,ETH,SOL}] [--duration {5,15}] [--watch]
                   [--poll-interval POLL_INTERVAL] [--timeout TIMEOUT]
                   [--output OUTPUT]

Market availability watcher for crypto pair bot -- Track 2 / Phase 1A. Checks
whether eligible BTC/ETH/SOL 5m/15m binary markets exist. No orders are
submitted. No wallet credentials required.

options:
  -h, --help            show this help message and exit
  --symbol {BTC,ETH,SOL}
                        Reserved for future filter wiring (v0: accepted but
                        does not filter the Gamma query; all eligible symbols
                        are always returned).
  --duration {5,15}     Reserved for future filter wiring (v0: accepted but
                        does not filter the Gamma query; all eligible
                        durations are always returned).
  --watch               Enter watch mode: poll until eligible markets appear
                        or --timeout elapses.
  --poll-interval POLL_INTERVAL
                        Seconds between polls in watch mode (default: 60).
  --timeout TIMEOUT     Watch mode timeout in seconds (default: 3600). Exit 1
                        when reached.
  --output OUTPUT       Base artifact directory (default:
                        artifacts/crypto_pairs/watch).
```
Result: PASS -- command exists, flags verified.

### 3. crypto-pair-scan --help

```
python -m polytool crypto-pair-scan --help
```

Output:
```
usage: __main__.py [-h] [--top TOP] [--symbol {BTC,ETH,SOL}]
                   [--duration {5,15}] [--output OUTPUT]

Dry-run crypto pair opportunity scanner -- Track 2 / Phase 1A. No orders are
submitted. No wallet credentials required.

options:
  -h, --help            show this help message and exit
  --top TOP             Number of rows to print in the summary table (default: 20).
  --symbol {BTC,ETH,SOL}
                        Restrict scan to one symbol (default: all).
  --duration {5,15}     Restrict scan to one duration in minutes: 5 or 15 (default: all).
  --output OUTPUT       Base artifact directory (default: artifacts/crypto_pairs/scan).
```
Result: PASS -- command exists, flags verified.

### 4. crypto-pair-run --help

```
python -m polytool crypto-pair-run --help
```

Key flags confirmed (full output available via --help):
- `--duration-hours`, `--duration-minutes`, `--duration-seconds` (additive)
- `--cycle-interval-seconds` (default from config or 0.5)
- `--reference-feed-provider {binance,coinbase,auto}` (default: binance)
- `--heartbeat-minutes` (disabled by default)
- `--auto-report` (paper mode only)
- `--sink-enabled` (requires CLICKHOUSE_PASSWORD)
- `--sink-streaming` (incremental writes, requires --sink-enabled)
- `--live` + `--confirm CONFIRM` (live scaffold; NOT used in paper mode)
- `--kill-switch PATH` (default: artifacts/crypto_pairs/kill_switch.txt)
- `--use-ws-clob` / `--no-use-ws-clob` (WS CLOB feed toggle)

Result: PASS -- command exists, all expected flags verified.

---

## What the Runbook Enables

The operator can now run the full Track 2 paper soak lifecycle from one document:

1. Preflight checks (CLI, Docker, ClickHouse, no-credential paper mode)
2. Market availability check (`crypto-pair-watch`)
3. Dry-run edge scan (`crypto-pair-scan`)
4. 24h paper soak launch (verified bash + PowerShell commands)
5. Safety checklist audit (8 concrete pass/fail criteria)
6. Kill switch procedure (both bash and PowerShell)
7. Promote/rerun/reject decision with cross-references to rubric spec
8. Troubleshooting for 7 known failure modes

---

## What the Runbook Does NOT Do

- Does not change Gate 2 thresholds (70% pass criterion intact)
- Does not edit shared truth files: `CLAUDE.md`, `docs/CURRENT_STATE.md`, `STATE.md`
- Does not touch benchmark manifests or corpus tooling
- Does not define the live deployment path (EU VPS, oracle mismatch, micro-live scaffold)

---

## Remaining Operator Gaps

The live deployment path (Track 2 to live capital) is NOT covered by this runbook.
Those steps require:

1. Successful paper soak with promote verdict
2. EU VPS evaluation (deployment latency assumptions from quick-022/023)
3. Oracle mismatch validation (Coinbase reference feed vs Chainlink on-chain settlement)
4. Micro-live scaffold wiring (CLOB client, EIP-712 signing, production order routing)

These are gated behind the paper soak result and are future work items.

---

## Notes on Flag Verification

One verification finding: `--reference-feed-provider` default is `binance` per --help
output, not `coinbase`. The runbook explicitly calls out that operators should use
`coinbase` as the geo-restriction workaround, consistent with quick-022/023 findings.
This is correct -- the default is binance but the recommended flag value for the paper
soak command is coinbase.

---

## Codex Review

Tier: Skip (docs-only -- no execution layer code, no live-capital logic, no API calls).
