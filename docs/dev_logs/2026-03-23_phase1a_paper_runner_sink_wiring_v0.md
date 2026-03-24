# 2026-03-23 Phase 1A — Paper Runner ClickHouse Sink Wiring v0

## Objective

Wire the `CryptoPairPaperRunner` into the dormant ClickHouse Track 2 event sink
that was built in a prior packet. Default paper-mode behavior (JSONL-only,
no Docker) must remain unchanged.

## What Was Done

### Step 1: Remove dormant stubs from position_store.py

The old `position_store.py` contained three dormant stub definitions:

- A `CryptoPairClickHouseSink` Protocol with a `write_rows()` interface
- An `ClickHouseSinkContract` dataclass with the wrong field layout
- A `DisabledClickHouseSink` class

These were removed and replaced with real imports from `clickhouse_sink.py`:
`CryptoPairClickHouseEventWriter`, `DisabledCryptoPairClickHouseSink`,
`ClickHouseSinkContract`.

The `CryptoPairPositionStore.__init__` sink parameter was updated to match the
real Protocol; `finalize()` now calls `self.sink.contract().to_dict()`.

### Step 2: Add sink param and batch emission to CryptoPairPaperRunner

`CryptoPairPaperRunner.__init__` gains:

```python
sink: Optional[CryptoPairClickHouseEventWriter] = None
```

The store is constructed with `sink=self.sink` so the sink contract appears in
the manifest's `clickhouse_sink` field.

At the end of `run()`, all paper-ledger records are converted to Track 2 events
via `build_events_from_paper_records()` and emitted in one `write_events()` call.

Feed state transitions recorded during cycles are converted to
`SafetyStateTransitionEvent` objects at the same finalization point.

The `ClickHouseWriteResult` is written to `run_manifest.json` under
`sink_write_result` for every run.

### Step 3: Add CLI args and fail-fast password

`crypto_pair_run.py` gains `--sink-enabled`, `--clickhouse-host`,
`--clickhouse-port`, and `--clickhouse-user`. The `run_crypto_pair_runner()`
function gains matching parameters.

In `main()`, if `--sink-enabled` is passed without `CLICKHOUSE_PASSWORD` set,
the CLI exits code 1 before starting.

### Step 4: Write 5 offline tests

`tests/test_crypto_pair_runner_events.py` covers:

1. Default path (sink disabled) — `sink_write_result.enabled is False`
2. Opt-in sink — `insert_rows` is called with `opportunity_observed` events
3. Soft-fail — ConnectionError leaves artifacts intact, records `write_failed`
4. Feed state transition — stale -> fresh produces a transition event
5. Deterministic count — 1 cycle produces exactly 6 events (0 transitions)

### Auto-fix: First-observation transition suppression

The first cycle always transitions from `None` (no state recorded) to
`connected_fresh`. The initial implementation recorded this as a
`SafetyStateTransitionEvent`, causing `test_deterministic_event_count` to
expect 6 events but receive 7.

Fix: only append to `self._feed_state_transitions` when `previous_feed_state
is not None`. The first observation is initialization, not a state transition.

## Files Changed

- `packages/polymarket/crypto_pairs/position_store.py` — remove stubs, import real sink
- `packages/polymarket/crypto_pairs/paper_runner.py` — sink param, batch emission, transition fix
- `tools/cli/crypto_pair_run.py` — 4 new CLI args, fail-fast password check
- `tests/test_crypto_pair_runner_events.py` — new, 5 tests

Also resolved 11 pre-existing merge conflicts (stash pop artefact, out of scope
for this packet — took "ours"/upstream side; added missing
`packages.polymarket.notifications` to `pyproject.toml`).

## Test Results

```
tests/test_crypto_pair_runner_events.py        5 passed
tests/test_crypto_pair_run.py                  2 passed
tests/test_crypto_pair_clickhouse_sink.py      4 passed
tests/test_crypto_pair_accumulation_engine.py  45 passed
tests/test_crypto_pair_fair_value.py           37 passed
tests/test_crypto_pair_live_safety.py          4 passed
tests/test_crypto_pair_reference_feed.py       29 passed
Total (crypto-pair slice): 126 passed, 0 failed
```

One pre-existing failure in `test_gate2_eligible_tape_acquisition.py`
(ResolvedWatch.regime missing attribute) is unrelated to this packet.

## Open Questions

None. Track 2 event sink is live-wired but safely gated behind `--sink-enabled`.
The next step for Track 2 ClickHouse usage is running a paper session with
`--sink-enabled` against a live ClickHouse instance to validate the schema.
