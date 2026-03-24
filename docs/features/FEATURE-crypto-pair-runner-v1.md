# Summary

Track 2 / Phase 1A paper runner is now wired into the ClickHouse Track 2 event
sink. ClickHouse writes are opt-in; the default path is unchanged and requires no
Docker dependency.

This packet supersedes the dormant ClickHouse stub from v0.

# What Shipped

## ClickHouse Sink Wiring

The `CryptoPairPaperRunner` now accepts a `sink: Optional[CryptoPairClickHouseEventWriter]`
parameter. At the end of each run, it batch-emits all collected Track 2 events
to the sink in a single `write_events()` call.

Events emitted per run:

| Event type                   | Count per run                          |
|------------------------------|----------------------------------------|
| `opportunity_observed`       | One per qualifying market per cycle    |
| `intent_generated`           | One per executed intent                |
| `simulated_fill_recorded`    | Two per intent (YES leg + NO leg)      |
| `partial_exposure_updated`   | One per intent after fills             |
| `run_summary`                | One at finalization                    |
| `safety_state_transition`    | Zero or more (genuine state changes only) |

The batch-at-finalization strategy minimises ClickHouse write calls and means
any write failure does not interrupt the run.

## Soft-Fail Behavior

If ClickHouse is unavailable and `soft_fail=True`, the runner:

- completes the full paper cycle as normal
- writes all JSONL artifacts
- records the write failure in `run_manifest.json["sink_write_result"]`
- continues without raising

`skipped_reason` will be `"write_failed"` and the `error` field will carry the
exception message.

## Manifest Reporting

`sink_write_result` is now always present in `run_manifest.json`, whether the
sink is enabled or not:

```json
"sink_write_result": {
    "enabled": false,
    "table_name": "crypto_pair_events",
    "attempted_events": 0,
    "written_rows": 0,
    "skipped_reason": "disabled",
    "error": null
}
```

## Feed State Transition Events

`SafetyStateTransitionEvent` events are emitted when the reference feed state
genuinely changes (e.g., from `stale` to `connected_fresh`). The first
observation of a symbol — going from no state to `connected_fresh` — does NOT
produce a transition event. Only real state changes during a run are recorded.

## CLI Args

Four new flags on `crypto-pair-run`:

| Flag                     | Default         | Description                                   |
|--------------------------|-----------------|-----------------------------------------------|
| `--sink-enabled`         | `False`         | Opt-in to ClickHouse writes                   |
| `--clickhouse-host`      | `localhost`     | ClickHouse host                               |
| `--clickhouse-port`      | `8123`          | ClickHouse HTTP port                          |
| `--clickhouse-user`      | `polytool_admin`| ClickHouse user                               |

Password is read from `CLICKHOUSE_PASSWORD` env var. If `--sink-enabled` is
passed without the env var set, the CLI exits with exit code 1 and a clear
error message before starting the run.

## Dormant Stubs Removed

The old dormant `CryptoPairClickHouseSink` Protocol, `ClickHouseSinkContract`
dataclass, and `DisabledClickHouseSink` stubs in `position_store.py` have been
removed. The real implementations from `clickhouse_sink.py` are now imported
directly.

# Tests

`tests/test_crypto_pair_runner_events.py` — 5 offline tests:

| Test                              | What it verifies                                          |
|-----------------------------------|-----------------------------------------------------------|
| `test_default_path_sink_disabled` | Without `--sink-enabled`, manifest shows disabled result  |
| `test_opt_in_sink_receives_events`| Enabled sink receives `opportunity_observed` events       |
| `test_soft_fail_sink_unavailable` | ConnectionError: artifacts intact, write_failed recorded  |
| `test_feed_state_transition_emitted` | Stale -> fresh transition produces one event           |
| `test_deterministic_event_count`  | One cycle: exactly 6 events, no spurious transitions     |

All 126 crypto-pair tests pass. No regressions.
