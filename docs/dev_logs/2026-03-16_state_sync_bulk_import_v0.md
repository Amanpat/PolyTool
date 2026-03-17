# Dev Log: State Sync — Bulk Import v0 (2026-03-16)

**Date**: 2026-03-16
**Branch**: phase-1
**Type**: Docs-only state sync — no code changes

---

## Context

End-of-session state sync. The purpose of this log is to record the verified
import state as of 2026-03-16 and summarize what changed in docs so future
sessions do not need to reconstruct this from chat history.

---

## Verified Import State

### pmxt archive

| Run | Mode | Rows loaded | Files | Status | Timestamp | Artifact |
|-----|------|-------------|-------|--------|-----------|---------|
| Sample | sample | 1,000 | 5 | complete | 2026-03-15T18:13–18:14Z | `artifacts/imports/pmxt_sample_run.json` |
| Full batch 1 | full | 78,264,878 | 5 | complete | 2026-03-15T18:17–18:38Z | `artifacts/imports/pmxt_full_batch1.json` |

Zero errors. Zero rows rejected. ClickHouse table: `polytool.pmxt_l2_snapshots`.
Full import ran ~21 minutes. `rows_loaded` field confirms CH writes, not just
attempted inserts.

### Jon-Becker dataset

| Run | Mode | Rows attempted | Files discovered | Status | Timestamp | Artifact |
|-----|------|----------------|-----------------|--------|-----------|---------|
| Dry-run | dry-run | 0 | 68,646 | dry-run | 2026-03-15T19:40Z | `artifacts/imports/jon_dry_run.json` |
| Sample | sample | 1,000 | 40,454 | complete | 2026-03-16T16:04Z | `artifacts/imports/jon_sample_run.json` |

Zero errors. Zero rows rejected. Import path is operational and confirmed
working against the real Jon-Becker dataset on disk. ClickHouse table:
`polytool.jb_trades`.

**Full import not yet run** — no `jon_full_run.json` artifact exists.

### price_history_2min

Not yet started. Step 3 of `docs/runbooks/BULK_HISTORICAL_IMPORT_V0.md` has
not been executed.

---

## What Changed in Docs

### `docs/CURRENT_STATE.md`

Four targeted edits, no code touched:

1. **"Status as of" date** updated 2026-03-07 → 2026-03-16. Status bullet list
   replaced "Current blocker: edge scarcity" with verified import progress
   bullets for pmxt, Jon-Becker, price_history_2min, and Silver reconstruction.

2. **"Current operator focus"** section updated 2026-03-07 → 2026-03-16.
   Replaced stale live-watcher narrative with completed/pending split:
   completed = pmxt sample + full, Jon dry-run + sample;
   pending = Jon full, price_history_2min, Silver tapes, Gate 2 sweep.

3. **"Gate status"** section updated 2026-03-07 → 2026-03-16. Gate 2 bullet
   now describes the import progress state rather than the live-capture
   failure state.

4. **Historical snapshot cross-reference** updated to point to the 2026-03-16
   gate status block.

### New: this dev log

`docs/dev_logs/2026-03-16_state_sync_bulk_import_v0.md`

---

## Handoff State

| Component | State |
|-----------|-------|
| Import engine (Packet 1 + 2) | Shipped, tested, operational |
| pmxt sample import | **COMPLETE** — 1,000 rows, zero errors |
| pmxt full import (batch 1) | **COMPLETE** — 78,264,878 rows, zero errors |
| Jon-Becker dry-run | **COMPLETE** — 68,646 files discovered, zero errors |
| Jon-Becker sample import | **COMPLETE** — 1,000 rows, zero errors |
| Jon-Becker full import | **NOT YET RUN** |
| price_history_2min | **NOT STARTED** |
| Silver tape reconstruction | **NOT STARTED** |
| Gate 2 | **NOT PASSED** |
| Gate 3 | Blocked behind Gate 2 |
| Gate 1 | PASSED |
| Gate 4 | PASSED |

---

## Next Steps (Packet 3 scope)

1. Run Jon-Becker full import:
   ```bash
   python -m polytool import-historical import \
       --source-kind jon_becker \
       --local-path /data/jbecker \
       --import-mode full \
       --out artifacts/imports/jon_full_run.json
   ```
2. Fetch price_history_2min for Gate 2 candidate tokens (Step 3 of runbook)
3. Implement Silver tape reconstruction from `pmxt_l2_snapshots` + `jb_trades`
   + `price_history_2min` → `events.jsonl` in SimTrader replay format
4. Verify reconstructed tapes pass `sweeps/eligibility.py` (`executable_ticks > 0`)
5. Run Gate 2 scenario sweep; if ≥70%, close via `tools/gates/close_sweep_gate.py`
