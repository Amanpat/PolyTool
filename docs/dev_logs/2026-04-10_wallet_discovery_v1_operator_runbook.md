# Dev Log: Wallet Discovery v1 Operator Runbook

**Date:** 2026-04-10
**Task:** quick-260410-iif
**Type:** Docs-only

---

## What Was Done

Created the operator runbook for Wallet Discovery v1 and cross-linked it from
the feature doc and docs README.

The runbook covers the complete v1 operator path:
- Prerequisites (Docker, ClickHouse, env vars, CLI smoke, DDL table check)
- Loop A dry-run and live run with expected output annotations
- Quick scan with MVF fingerprint (`--quick` flag)
- Human review gate and lifecycle state machine explanation
- ClickHouse table reference (watchlist, leaderboard_snapshots, scan_queue)
- v1 non-goals and blockers for phases beyond v1
- Troubleshooting table (8 common failure modes)
- Related docs table

All commands were verified against the live CLI before finalizing:
- `python -m polytool discovery --help` — confirmed subcommand structure
- `python -m polytool discovery run-loop-a --help` — confirmed all flag names
- `python -m polytool scan --help` — confirmed `--quick` flag description
- `python -m polytool discovery run-loop-a --dry-run` — confirmed real output shape
  (rows_fetched: 250, dry_run: True, all result fields present)

---

## Files Changed

- `docs/runbooks/WALLET_DISCOVERY_V1_OPERATOR_RUNBOOK.md` — Created (304 lines)
- `docs/features/wallet-discovery-v1.md` — Added "Operator Runbook" section with link
- `docs/README.md` — Added runbook entry to Workflows section

---

## Files NOT Changed

No code, tests, infra, migrations, or config files were modified. This is a
docs-only work unit.

---

## Codex Review

Skip — docs-only. No execution, kill-switch, risk manager, or strategy files
were touched.
