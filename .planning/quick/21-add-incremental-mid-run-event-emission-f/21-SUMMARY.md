---
phase: quick
plan: 21
subsystem: crypto-pairs
tags: [sink, streaming, track2, clickhouse, paper-runner]
dependency_graph:
  requires: [quick-020]
  provides: [PHASE1A-INCREMENTAL-SINK]
  affects: [paper_runner, clickhouse_sink, crypto_pair_run_cli]
tech_stack:
  added: []
  patterns: [sink_flush_mode_field, write_event_helper, consecutive_fail_guard, streamed_transition_dedup]
key_files:
  created:
    - docs/features/FEATURE-crypto-pair-runner-v2.md
    - docs/dev_logs/2026-03-23_phase1a_incremental_sink_streaming_v0.md
  modified:
    - packages/polymarket/crypto_pairs/clickhouse_sink.py
    - packages/polymarket/crypto_pairs/paper_runner.py
    - tools/cli/crypto_pair_run.py
    - tests/test_crypto_pair_runner_events.py
decisions:
  - "sink_flush_mode lives on CryptoPairRunnerSettings not the sink — runner owns when/how often the sink is called"
  - "write_event() is a distinct method (not a wrapper) so the consecutive-fail guard can apply per-event in streaming mode"
  - "RunSummaryEvent always in finalization write_events() batch because it requires the final run_summary dict"
  - "_streamed_transition_ids uses composite key to match finalization list which reconstructs from raw dicts"
metrics:
  duration_minutes: ~90
  tasks_completed: 3
  files_changed: 6
  tests_added: 8
  completed_date: "2026-03-24"
---

# Phase quick Plan 21: Add Incremental Mid-Run Event Emission Summary

**One-liner:** Opt-in streaming flush mode for the crypto-pair paper runner that calls `sink.write_event()` per Track 2 event during `_process_opportunity()` instead of one `write_events()` batch at finalization, enabling Grafana visibility during long soak runs.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add write_event() + consecutive-fail guard to sink | 593edfe | clickhouse_sink.py |
| 2 | sink_flush_mode field + streaming emission in runner + CLI | 48795f4 | paper_runner.py, crypto_pair_run.py |
| 3 | Tests, feature doc, dev log | ddca74b | test_crypto_pair_runner_events.py, FEATURE-crypto-pair-runner-v2.md, dev log |

## What Was Built

### CryptoPairClickHouseSink.write_event()

- Added `write_event(event)` single-event helper to `CryptoPairClickHouseEventWriter` Protocol
- `DisabledCryptoPairClickHouseSink.write_event()` delegates to `write_events([event])` as a no-op
- `CryptoPairClickHouseSink.write_event()` adds a consecutive-failure guard:
  - `_consecutive_fail_count` and `_max_consecutive_failures` (default 5) instance vars
  - Returns `skipped_reason="consecutive_fail_limit"` once limit is reached
  - Resets counter on any successful write

### CryptoPairRunnerSettings.sink_flush_mode

- New field `sink_flush_mode: str = "batch"` (validated in `__post_init__`)
- `build_runner_settings()` reads from config payload
- `to_dict()` and `with_artifact_base_dir()` both propagate the field

### Streaming emission in _process_opportunity()

When `sink_flush_mode == "streaming"`, the runner calls `sink.write_event()` immediately after:

1. `store.record_observation()` → `OpportunityObservedEvent`
2. `store.record_intent()` → `IntentGeneratedEvent`
3. Each `store.record_fill()` → `SimulatedFillRecordedEvent`
4. `store.record_exposure()` → `PartialExposureUpdatedEvent`
5. Feed state change detection → `SafetyStateTransitionEvent`

Failures log a `logger.warning` but never abort the run loop.

### Deduplication of safety transitions

`self._streamed_transition_ids: set[str]` tracks which transitions were already emitted
via `write_event()`. At finalization, the runner excludes those from the `write_events()` batch.

### Finalization always calls write_events() once

- Batch mode: full event list from `build_events_from_paper_records()` + all transitions + RunSummaryEvent
- Streaming mode: unstreamed transitions only + RunSummaryEvent
- `sink_write_result` in manifest always reflects this single finalization call

### CLI --sink-streaming flag

`--sink-streaming` (requires `--sink-enabled`). Warning printed to stderr if used without
`--sink-enabled`. Passes `sink_flush_mode="streaming"` through to `build_runner_settings()`.

## Verification

Targeted suite: **19 passed, 0 failed** (test_crypto_pair_runner_events.py + test_crypto_pair_run.py + test_crypto_pair_clickhouse_sink.py)

Full regression: **878 passed, 1 failed** — the 1 failure is `test_scan_gate2_parser_accepts_enrich_flag` which is a pre-existing regression from quick-020/gate2-ranking (expects `--enrich` flag on `scan_gate2_candidates` that was never added). Deferred.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

Files exist:
- `packages/polymarket/crypto_pairs/clickhouse_sink.py` — confirmed (modified)
- `packages/polymarket/crypto_pairs/paper_runner.py` — confirmed (modified)
- `tools/cli/crypto_pair_run.py` — confirmed (modified)
- `tests/test_crypto_pair_runner_events.py` — confirmed (modified)
- `docs/features/FEATURE-crypto-pair-runner-v2.md` — confirmed (created)
- `docs/dev_logs/2026-03-23_phase1a_incremental_sink_streaming_v0.md` — confirmed (created)

Commits exist:
- `593edfe` — Task 1
- `48795f4` — Task 2
- `ddca74b` — Task 3
