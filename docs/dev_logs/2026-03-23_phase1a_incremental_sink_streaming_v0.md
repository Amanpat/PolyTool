# Dev Log — 2026-03-23: Phase 1A Incremental Sink Streaming v0

## Objective

Add opt-in streaming (incremental per-event) ClickHouse emission to the
crypto-pair paper runner so Grafana can show live data during long soak runs,
without changing the existing batch-flush default.

## Work Summary

### Task 1 — Sink `write_event()` + consecutive-fail guard

`packages/polymarket/crypto_pairs/clickhouse_sink.py`:

- `CryptoPairClickHouseEventWriter` Protocol: added `write_event()` method signature
- `DisabledCryptoPairClickHouseSink`: `write_event()` delegates to `write_events([event])`
- `CryptoPairClickHouseSink`:
  - `__init__` adds `max_consecutive_failures: int = 5` parameter
  - `_consecutive_fail_count: int = 0` instance var
  - `write_event()` checks `_consecutive_fail_count >= _max_consecutive_failures` and
    returns `skipped_reason="consecutive_fail_limit"` to avoid error storms
  - Counter increments on error, resets to 0 on success

Committed: `593edfe` — `feat(quick-021): add write_event + consecutive-fail guard to sink`

### Task 2 — `sink_flush_mode` field + streaming emission in paper runner + CLI flag

`packages/polymarket/crypto_pairs/paper_runner.py`:

- `CryptoPairRunnerSettings.sink_flush_mode: str = "batch"` (validated in `__post_init__`)
- `_streamed_transition_ids: set[str]` tracks which safety transitions were already
  emitted in the run loop to prevent finalization double-emit
- `_process_opportunity()`: in streaming mode, calls `sink.write_event()` after each
  `store.record_*()` call — observation, intent, fills, exposure, and transitions
- `run()` finalization: streaming mode sends only unstreamed transitions + RunSummaryEvent;
  batch mode sends all events as before

`tools/cli/crypto_pair_run.py`:

- `--sink-streaming` flag added (requires `--sink-enabled` to have any effect)
- `run_crypto_pair_runner()` accepts `sink_flush_mode: str = "batch"`
- Warning printed to stderr when `--sink-streaming` without `--sink-enabled`

Committed: `48795f4` — `feat(quick-021): add sink_flush_mode + streaming emission to paper runner and CLI`

### Task 3 — Tests, feature doc, dev log

`tests/test_crypto_pair_runner_events.py` additions:

- `CaptureSink.write_event()` method added (records to `self.captured`)
- `_SpySink`: separate `write_event_calls` and `write_events_calls` lists
- `_CyclingStaleFeed`: returns fresh on first call, stale on subsequent calls
- `_make_paper_obs()`: builds minimal `PaperOpportunityObservation` for unit tests

New tests (8):

1. `test_batch_mode_default_unchanged` — write_event never called; write_events once
2. `test_streaming_mode_emits_incrementally` — >= 5 write_event calls per opportunity
3. `test_streaming_mode_sink_failure_soft_fails` — run completes despite all write_event errors
4. `test_streaming_mode_consecutive_fail_guard` — limit guard triggers at count threshold
5. `test_streaming_mode_safety_transition_no_duplicate` — transition_id unique across channels
6. `test_streaming_mode_run_summary_always_at_finalization` — RunSummaryEvent in batch
7. `test_write_event_disabled_sink_noop` — DisabledSink returns enabled=False, skipped=disabled
8. `test_write_event_enabled_sink_delegates` — enabled sink calls insert_rows with 1 row

## Test Results

Targeted (3 files): **19 passed, 0 failed**

Full regression: **878 passed, 1 failed, 1 warning**

The 1 failure (`test_scan_gate2_parser_accepts_enrich_flag`) is a pre-existing
regression unrelated to this packet — it expects `--enrich` on `scan_gate2_candidates`
which was never added. Logged to deferred-items.

## Design Decisions

- `sink_flush_mode` lives on `CryptoPairRunnerSettings` rather than on the sink itself
  because the runner controls when and how often the sink is called
- `write_event()` is a separate method on the sink (not just repeated calls to `write_events()`)
  so the consecutive-fail guard can be applied per-event in streaming mode
- `RunSummaryEvent` is always in the finalization `write_events()` batch — it requires
  the final `run_summary` dict which is not available until after the run loop ends
- `_streamed_transition_ids` uses the `transition_id` composite key (not event_id) to match
  against the finalization list which reconstructs from raw transition dicts

## Open Items

- Live runner streaming mode not yet implemented (paper-only)
- No Grafana provisioning for the `crypto_pair_events` table
