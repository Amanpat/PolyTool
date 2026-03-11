# Docs Sync: SimTrader Status (2026-03-07)

## Summary

Updated the repo docs so the written status now matches the current SimTrader
and gate reality: Gate 1 and Gate 4 are passed, Gate 2 tooling is implemented
and working but the gate is not yet passed, Gate 3 remains blocked behind Gate
2, and the current blocker is edge scarcity rather than SimTrader plumbing.

No code or strategy logic was changed.

## Files changed

- `README.md`
- `docs/CURRENT_STATE.md`
- `docs/ROADMAP.md`
- `docs/INDEX.md`
- `docs/dev_logs/2026-03-07_bounded_dislocation_capture_trial.md`
- `docs/dev_logs/2026-03-07_docs_sync_simtrader_status.md`

## Stale statements corrected

- Replaced stale language that implied Gate 1 was still open.
- Replaced stale language that implied Gate 4 was the only passed gate.
- Updated Gate 2 wording from "open / in progress" to "tooling implemented and
  working, but gate not yet passed because no eligible tape has been captured."
- Updated the blocker description from missing plumbing to opportunity / edge
  scarcity.
- Added explicit mention of the current Gate 2 toolchain:
  `scan-gate2-candidates`, `prepare-gate2`, presweep eligibility checks,
  `watch-arb-candidates`, and `--watchlist-file` ingest.
- Restated that Opportunity Radar is deferred.

## Final high-level repo status

- Gate 1: PASSED
- Gate 2: not passed yet; the watcher path produced no trigger/new tapes, and
  the recent acquisition cycle produced only ineligible tapes
- Gate 3: blocked behind Gate 2
- Gate 4: PASSED
- Current next step: bounded live dislocation trials for
  `binary_complement_arb`
- Current blocker: opportunity scarcity / lack of qualifying edge

## Operator checklist

Added `docs/dev_logs/2026-03-07_bounded_dislocation_capture_trial.md` as a
short operator checklist covering:

- how to choose 3-5 markets
- when to start the watcher
- which commands to run
- how to scan tapes afterward
- what counts as success
- what counts as evidence to deprioritize the strategy
