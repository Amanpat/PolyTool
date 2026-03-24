# Summary

The crypto-pair paper runner now supports incremental per-event ClickHouse emission
during the run loop (streaming mode) in addition to the existing end-of-run batch
flush (batch mode, unchanged default). This enables Grafana visibility during long
soak runs without waiting for finalization.

# What Shipped

## Sink `write_event()` Single-Event API

`packages/polymarket/crypto_pairs/clickhouse_sink.py`:

- `CryptoPairClickHouseEventWriter` Protocol gains a `write_event()` method signature
- `DisabledCryptoPairClickHouseSink.write_event()` delegates to `write_events([event])` as a no-op
- `CryptoPairClickHouseSink.write_event()` adds a consecutive-failure guard:
  - Tracks `_consecutive_fail_count` and `_max_consecutive_failures` (default 5)
  - Once the guard triggers, returns `skipped_reason="consecutive_fail_limit"` to
    prevent error storms when ClickHouse is down during a long run
  - Resets the counter on any successful write

## Runner `sink_flush_mode` Field

`packages/polymarket/crypto_pairs/paper_runner.py`:

`CryptoPairRunnerSettings` gains:

```
sink_flush_mode: str = "batch"
```

Valid values: `"batch"` (default, unchanged) or `"streaming"`.
`__post_init__` raises `ValueError` on any other value.
`build_runner_settings()` reads `sink_flush_mode` from the config payload.

### Streaming emission points

When `sink_flush_mode == "streaming"`, each `_process_opportunity()` call emits:

1. `OpportunityObservedEvent` immediately after `store.record_observation()`
2. `IntentGeneratedEvent` immediately after `store.record_intent()`
3. `SimulatedFillRecordedEvent` per fill immediately after each `store.record_fill()`
4. `PartialExposureUpdatedEvent` immediately after `store.record_exposure()`
5. `SafetyStateTransitionEvent` when a feed state change is detected in the cycle

Each streaming call soft-fails with a `logger.warning` on error — the run loop
continues regardless of sink availability.

### Finalization (both modes)

`run()` finalization always calls `write_events()` exactly once:

- Batch mode: all events from `build_events_from_paper_records()` + all transition events
- Streaming mode: only unstreamed safety transitions + `RunSummaryEvent`

`_streamed_transition_ids: set[str]` prevents duplicate emission of safety transitions
across the streaming channel and the finalization batch.

`RunSummaryEvent` is always in the finalization batch regardless of flush mode.

## CLI `--sink-streaming` Flag

`tools/cli/crypto_pair_run.py`:

```
--sink-streaming    Enable incremental per-event sink writes during the run loop
                    instead of batching all events at finalization.
                    Requires --sink-enabled. Allows Grafana visibility during long runs.
```

If `--sink-streaming` is given without `--sink-enabled`, a warning is printed to
stderr and the flag has no effect.

# Invariants

- Default batch mode behavior is unchanged (zero regressions)
- `write_events()` is called exactly once at finalization in both modes
- `write_event()` is never called in batch mode
- Sink failures never abort the run loop
- Transition IDs are globally unique and never duplicated across emission channels

# Not Yet

- Live runner does not yet support streaming mode (paper-only for now)
- No Grafana provisioning or dashboard JSON in this packet
- Historical backfill from existing JSONL artifacts not included
