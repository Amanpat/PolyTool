# Quick Task 20 — Wire Paper Runner Into Dormant Event Sink

## Goal

Add an opt-in `--sink-enabled` path to the crypto-pair paper runner that emits Track 2 events to ClickHouse at finalization, while leaving the default artifact-first paper run behavior entirely unchanged.

---

## Steps

### Step 1: Clean up dormant stubs in `position_store.py`

**File(s):** `packages/polymarket/crypto_pairs/position_store.py`

**Action:** Remove the old dormant sink stubs and replace the store's sink parameter with the real Protocol type from `clickhouse_sink.py`. Update `finalize()` to emit the new-style sink contract in the manifest.

**Details:**

1. Remove the entire `CryptoPairClickHouseSink` Protocol class (lines 30-43) — this is the old stub with `write_rows(stream_name, rows)`. The real Protocol is `CryptoPairClickHouseEventWriter` in `clickhouse_sink.py`.

2. Remove the entire `ClickHouseSinkContract` dataclass (lines 45-65) — this is the old stub. The real one lives in `clickhouse_sink.py`.

3. Remove the `DisabledClickHouseSink` class (lines 67-80) — the old stub that raises `RuntimeError`.

4. Add the import at the top of `position_store.py`, after the existing `.paper_ledger` import:
   ```python
   from .clickhouse_sink import (
       ClickHouseSinkContract,
       CryptoPairClickHouseEventWriter,
       DisabledCryptoPairClickHouseSink,
   )
   ```

5. In `CryptoPairPositionStore.__init__`, replace the two old parameters:
   - Remove: `clickhouse_contract: Optional[ClickHouseSinkContract] = None`
   - Remove: `clickhouse_sink: Optional[CryptoPairClickHouseSink] = None`
   - Add one new parameter: `sink: Optional[CryptoPairClickHouseEventWriter] = None`

6. In `__init__`, replace the two old field assignments:
   - Remove: `self.clickhouse_contract = clickhouse_contract or ClickHouseSinkContract()`
   - Remove: `self.clickhouse_sink = clickhouse_sink`
   - Add: `self.sink: CryptoPairClickHouseEventWriter = sink or DisabledCryptoPairClickHouseSink()`

7. In `finalize()`, the line:
   ```python
   "clickhouse_sink": self.clickhouse_contract.to_dict(),
   ```
   becomes:
   ```python
   "clickhouse_sink": self.sink.contract().to_dict(),
   ```
   The rest of `finalize()` is unchanged — the store still does NOT call `write_events()`.

**Verify:** `grep -n "write_rows\|DisabledClickHouseSink\|CryptoPairClickHouseSink" packages/polymarket/crypto_pairs/position_store.py` should return nothing after this step.

---

### Step 2: Wire the sink into `CryptoPairPaperRunner` and emit events at finalization

**File(s):** `packages/polymarket/crypto_pairs/paper_runner.py`

**Action:** Add a `sink` parameter to `CryptoPairPaperRunner.__init__`, collect feed-state transitions during the run, and emit a single batch of Track 2 events to the sink at finalization.

**Details:**

1. Add imports at the top of `paper_runner.py`, after the existing `.position_store` import:
   ```python
   from .clickhouse_sink import (
       CryptoPairClickHouseEventWriter,
       DisabledCryptoPairClickHouseSink,
   )
   from .event_models import (
       SafetyStateTransitionEvent,
       build_events_from_paper_records,
   )
   ```

2. In `CryptoPairPaperRunner.__init__`, add one new parameter after `execution_adapter`:
   ```python
   sink: Optional[CryptoPairClickHouseEventWriter] = None,
   ```

3. In `__init__`, add these two field assignments after `self.kill_switch = ...`:
   ```python
   self.sink: CryptoPairClickHouseEventWriter = sink or DisabledCryptoPairClickHouseSink()
   self._feed_state_transitions: list[dict] = []
   ```

4. Update the store construction inside `__init__` (the `store or CryptoPairPositionStore(...)` block) to pass the sink through:
   ```python
   self.store = store or CryptoPairPositionStore(
       mode="paper",
       artifact_base_dir=settings.artifact_base_dir,
       sink=self.sink,
   )
   ```
   Note: when a pre-built `store` is passed in from the outside (e.g., in tests), the caller is responsible for wiring the sink into it. The runner does not re-inject its sink into a caller-provided store.

5. In `_process_opportunity()`, after the existing `feed_state_changed` runtime event recording block (lines 594-602 in the original), append to `self._feed_state_transitions`:
   ```python
   if previous_feed_state != current_feed_state:
       self.store.record_runtime_event(
           "feed_state_changed",
           ...  # existing code, unchanged
       )
       self._feed_states[opportunity.symbol] = current_feed_state
       # NEW: record transition for batch sink emission
       self._feed_state_transitions.append({
           "transition_id": f"fst-{self.store.run_id}-{opportunity.symbol}-{event_at}",
           "event_ts": event_at,
           "symbol": opportunity.symbol,
           "from_state": previous_feed_state,
           "to_state": current_feed_state,
           "market_id": opportunity.slug,
           "condition_id": opportunity.condition_id,
           "slug": opportunity.slug,
           "duration_min": opportunity.duration_min,
           "cycle": cycle,
       })
   ```

6. In `run()`, after `self.store.record_run_summary(run_summary)` and before `manifest = self.store.finalize(...)`, add the batch sink emission block:
   ```python
   # Build SafetyStateTransitionEvent objects from collected transitions
   transition_events = [
       SafetyStateTransitionEvent.from_feed_state_change(
           transition_id=t["transition_id"],
           event_ts=t["event_ts"],
           run_id=self.store.run_id,
           mode="paper",
           symbol=t["symbol"],
           from_state=t["from_state"],
           to_state=t["to_state"],
           market_id=t["market_id"],
           condition_id=t["condition_id"],
           slug=t["slug"],
           duration_min=t["duration_min"],
           cycle=t["cycle"],
       )
       for t in self._feed_state_transitions
   ]
   events = build_events_from_paper_records(
       observations=self.store.observations,
       intents=self.store.intents,
       fills=self.store.fills,
       exposures=self.store.latest_exposures(),
       settlements=self.store.settlements,
       run_summary=run_summary,
       mode="paper",
       stopped_reason=stopped_reason,
   )
   events.extend(transition_events)
   write_result = self.sink.write_events(events)
   self.store.record_runtime_event(
       "sink_write_result",
       enabled=write_result.enabled,
       attempted_events=write_result.attempted_events,
       written_rows=write_result.written_rows,
       skipped_reason=write_result.skipped_reason,
       error=write_result.error,
   )
   ```

7. Pass `write_result` into `extra_manifest_fields` in the `self.store.finalize(...)` call:
   ```python
   manifest = self.store.finalize(
       stopped_reason=stopped_reason,
       completed_at=self.now_fn(),
       extra_manifest_fields={
           "runner_result": PaperRunnerResult(...).to_dict(),
           "sink_write_result": write_result.to_dict(),
       },
   )
   ```

**Verify:** The `run()` method still returns a manifest dict. `sink_write_result` appears in that dict. For the default (no sink) path, `manifest["sink_write_result"]["skipped_reason"] == "disabled"`.

---

### Step 3: Add CLI args and wire sink config through `run_crypto_pair_runner`

**File(s):** `tools/cli/crypto_pair_run.py`

**Action:** Add four new arguments to `build_parser()`, extend `run_crypto_pair_runner()` to accept and apply sink config, and add fail-fast env-var reading for the ClickHouse password when sink is enabled.

**Details:**

1. Add these imports at the top of `crypto_pair_run.py` (after existing imports):
   ```python
   import os
   from packages.polymarket.crypto_pairs.clickhouse_sink import (
       CryptoPairClickHouseSinkConfig,
       build_clickhouse_sink,
   )
   ```

2. In `build_parser()`, add four arguments after the `--confirm` argument:
   ```python
   parser.add_argument(
       "--sink-enabled",
       action="store_true",
       default=False,
       help="Enable the ClickHouse Track 2 event sink (opt-in). Requires CLICKHOUSE_PASSWORD env var.",
   )
   parser.add_argument(
       "--clickhouse-host",
       default="localhost",
       help="ClickHouse host for the event sink (default: localhost).",
   )
   parser.add_argument(
       "--clickhouse-port",
       type=int,
       default=8123,
       help="ClickHouse HTTP port for the event sink (default: 8123).",
   )
   parser.add_argument(
       "--clickhouse-user",
       default="polytool_admin",
       help="ClickHouse user for the event sink (default: polytool_admin).",
   )
   ```

3. In `run_crypto_pair_runner()`, add these parameters after `cycle_limit`:
   ```python
   sink_enabled: bool = False,
   clickhouse_host: str = "localhost",
   clickhouse_port: int = 8123,
   clickhouse_user: str = "polytool_admin",
   clickhouse_password: str = "",
   ```

4. In `run_crypto_pair_runner()`, before the `if live:` block, add sink construction:
   ```python
   sink_config = CryptoPairClickHouseSinkConfig(
       enabled=sink_enabled,
       clickhouse_host=clickhouse_host,
       clickhouse_port=clickhouse_port,
       clickhouse_user=clickhouse_user,
       clickhouse_password=clickhouse_password,
   )
   sink = build_clickhouse_sink(sink_config)
   ```

5. In `run_crypto_pair_runner()`, in the `else:` branch where `CryptoPairPaperRunner` is constructed, add `sink=sink`:
   ```python
   runner = CryptoPairPaperRunner(
       settings,
       gamma_client=gamma_client,
       clob_client=clob_client,
       reference_feed=reference_feed,
       store=store,
       execution_adapter=execution_adapter,
       sink=sink,
   )
   ```
   Note: `CryptoPairLiveRunner` does not get a sink parameter in this task — leave the live branch unchanged.

6. In `main()`, add the fail-fast password resolution before calling `run_crypto_pair_runner`. Place it after `args = parser.parse_args(argv)` and before the `if args.duration_seconds < 0:` check:
   ```python
   ch_password = ""
   if args.sink_enabled:
       ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "")
       if not ch_password:
           print(
               "Error: --sink-enabled requires the CLICKHOUSE_PASSWORD environment variable to be set.",
               file=sys.stderr,
           )
           return 1
   ```

7. Pass the new args into the `run_crypto_pair_runner(...)` call inside `main()`:
   ```python
   manifest = run_crypto_pair_runner(
       live=args.live,
       confirm=args.confirm,
       config_path=args.config,
       duration_seconds=args.duration_seconds,
       cycle_interval_seconds=args.cycle_interval_seconds,
       symbol_filters=tuple(args.symbol or ()),
       duration_filters=tuple(args.market_duration or ()),
       output_base=Path(args.output) if args.output else None,
       kill_switch_path=Path(args.kill_switch),
       sink_enabled=args.sink_enabled,
       clickhouse_host=args.clickhouse_host,
       clickhouse_port=args.clickhouse_port,
       clickhouse_user=args.clickhouse_user,
       clickhouse_password=ch_password,
   )
   ```

**Verify:** `python -m polytool crypto-pair-run --help` shows `--sink-enabled`, `--clickhouse-host`, `--clickhouse-port`, `--clickhouse-user` in the output.

---

### Step 4: Write `tests/test_crypto_pair_runner_events.py`

**File(s):** `tests/test_crypto_pair_runner_events.py` (new file)

**Action:** Write 5 offline tests covering the sink integration path. All tests use mock clients, `StaticFeed`, and a `tmp_path`-scoped artifact directory. No Docker or real ClickHouse required.

**Details:**

Copy the helper factories from `test_crypto_pair_run.py` into this new file: `_make_mock_market`, `_make_gamma_client`, `_make_clob_client`, `_fresh_snapshot`, `_stale_snapshot`, `StaticFeed`, `_read_jsonl`. Import `run_crypto_pair_runner` from `tools.cli.crypto_pair_run`.

Also import at the top of the new test file:
```python
from unittest.mock import MagicMock
from packages.polymarket.crypto_pairs.clickhouse_sink import (
    CryptoPairClickHouseSink,
    CryptoPairClickHouseSinkConfig,
    DisabledCryptoPairClickHouseSink,
    build_clickhouse_sink,
)
from packages.polymarket.crypto_pairs.event_models import (
    EVENT_TYPE_OPPORTUNITY_OBSERVED,
    EVENT_TYPE_INTENT_GENERATED,
    EVENT_TYPE_SIMULATED_FILL_RECORDED,
    EVENT_TYPE_PARTIAL_EXPOSURE_UPDATED,
    EVENT_TYPE_SAFETY_STATE_TRANSITION,
    EVENT_TYPE_RUN_SUMMARY,
)
```

**Test 1 — `test_default_path_sink_disabled`:**
Run `run_crypto_pair_runner(...)` without passing `sink_enabled=True`. Assert:
- `manifest["sink_write_result"]["enabled"] is False`
- `manifest["sink_write_result"]["skipped_reason"] == "disabled"`
- `manifest["sink_write_result"]["written_rows"] == 0`

Use a fresh-snapshot feed and a market that generates at least one intent (prices `yes=0.47`, `no=0.48`).

**Test 2 — `test_opt_in_sink_receives_events`:**
Create a `MagicMock()` client where `client.insert_rows.return_value = 0`. Build an enabled sink:
```python
config = CryptoPairClickHouseSinkConfig(
    enabled=True, clickhouse_host="localhost", clickhouse_port=8123,
    clickhouse_user="polytool_admin", clickhouse_password="test", soft_fail=True,
)
sink = CryptoPairClickHouseSink(config, client=mock_client)
```
Pass `sink` directly to `CryptoPairPaperRunner` (not through `run_crypto_pair_runner`, to avoid CLI password logic). Construct `CryptoPairPaperRunner(settings, ..., sink=sink)` and call `.run()`. Assert:
- `mock_client.insert_rows.called is True`
- The args to `insert_rows` include rows where at least one row has `event_type == EVENT_TYPE_OPPORTUNITY_OBSERVED`

**Test 3 — `test_soft_fail_sink_unavailable`:**
Build an enabled sink whose client raises `ConnectionError("ch down")` on `insert_rows`. Assert:
- `manifest["sink_write_result"]["skipped_reason"] == "write_failed"`
- `manifest["sink_write_result"]["error"]` contains `"ch down"`
- The artifact dir still contains `run_manifest.json` and `observations.jsonl` (JSONL artifacts unaffected)

**Test 4 — `test_feed_state_transition_emitted`:**
Use a two-call feed: the first call returns a stale snapshot; the second returns a fresh snapshot. Implement as a simple class with a call counter. Run with `cycle_limit=2`. Build a sink that captures events passed to `write_events`. Assert:
- At least one event in the captured batch has `event_type == EVENT_TYPE_SAFETY_STATE_TRANSITION`
- That event's `to_state` is `"stale"` (from first cycle) or `"connected_fresh"` (from second cycle), depending on order

The simplest approach: use a `DisabledCryptoPairClickHouseSink` subclass that records the events list passed to `write_events`:
```python
class CaptureSink:
    def __init__(self):
        self.captured = []
    def write_events(self, events):
        self.captured.extend(events)
        from packages.polymarket.crypto_pairs.clickhouse_sink import ClickHouseWriteResult, CRYPTO_PAIR_EVENTS_TABLE
        return ClickHouseWriteResult(enabled=False, table_name=CRYPTO_PAIR_EVENTS_TABLE,
                                     attempted_events=len(self.captured), written_rows=0,
                                     skipped_reason="disabled")
    def contract(self):
        from packages.polymarket.crypto_pairs.clickhouse_sink import DisabledCryptoPairClickHouseSink
        return DisabledCryptoPairClickHouseSink().contract()
```
Wire `CaptureSink()` as the sink and check that `SafetyStateTransitionEvent` objects appear.

**Test 5 — `test_deterministic_event_count`:**
Run with a fresh feed and one market that generates exactly 1 intent. Use `CaptureSink`. After run, count events by type:
- `opportunity_observed` count = 1 (one observation)
- `intent_generated` count = 1
- `simulated_fill_recorded` count = 2 (YES fill + NO fill)
- `partial_exposure_updated` count = 1
- `run_summary` count = 1
- `safety_state_transition` count = 0 (feed stayed fresh throughout)
- total = 6

Assert each count is exactly as expected. This pins the emission contract so future changes are detected.

---

### Step 5: Verify existing tests still pass, then write docs

**File(s):**
- `tests/test_crypto_pair_run.py` — no changes needed; verify still passes
- `tests/test_crypto_pair_clickhouse_sink.py` — no changes needed; verify still passes
- `docs/features/FEATURE-crypto-pair-runner-v1.md` (new)
- `docs/dev_logs/2026-03-23_phase1a_paper_runner_sink_wiring_v0.md` (new)

**Action:** Run the full test suite for crypto-pair modules to confirm no regressions, then write the feature doc and dev log.

**Details for feature doc (`FEATURE-crypto-pair-runner-v1.md`):**
Document these facts:
- Default behavior: `CryptoPairPaperRunner` uses `DisabledCryptoPairClickHouseSink` by default. No network calls. No behavior change from v0.
- Opt-in path: Pass `sink` to `CryptoPairPaperRunner(settings, ..., sink=sink)` or use `--sink-enabled` CLI flag.
- CLI flags added: `--sink-enabled`, `--clickhouse-host`, `--clickhouse-port`, `--clickhouse-user`. Password from `CLICKHOUSE_PASSWORD` env var (fail-fast if missing when enabled).
- Emission strategy: batch-at-finalization via `build_events_from_paper_records()` + feed-state transitions collected as `self._feed_state_transitions` during run.
- `sink_write_result` key appears in `run_manifest.json` in all runs (disabled or active).
- `clickhouse_sink` key in manifest now reflects the real sink's `contract().to_dict()` (no longer the old dormant stub format).

**Details for dev log:**
Use slug `phase1a_paper_runner_sink_wiring_v0`. Record: what changed in each file, what tests were added, exact test command and pass count, any notable decisions (batch-at-finalization chosen over per-record, old stubs removed cleanly).

---

## Verification

Run these commands in order:

```bash
# 1. CLI help shows new flags
python -m polytool crypto-pair-run --help

# 2. Targeted new tests
python -m pytest tests/test_crypto_pair_runner_events.py -v --tb=short

# 3. Existing tests that must remain green
python -m pytest tests/test_crypto_pair_run.py tests/test_crypto_pair_clickhouse_sink.py -v --tb=short

# 4. Full crypto-pair regression suite
python -m pytest tests/test_crypto_pair_scan.py tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_run.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_reference_feed.py tests/test_crypto_pair_fair_value.py tests/test_crypto_pair_accumulation_engine.py tests/test_crypto_pair_backtest.py tests/test_crypto_pair_clickhouse_sink.py tests/test_crypto_pair_runner_events.py -q

# 5. Smoke test: CLI still loads
python -m polytool --help
```

Expected: all tests pass, no import errors. The `--sink-enabled` flag appears in `crypto-pair-run --help` output.

---

## Definition of Done

- `position_store.py` contains no `write_rows`, no `DisabledClickHouseSink`, no old `CryptoPairClickHouseSink` Protocol stub. `CryptoPairPositionStore.__init__` accepts `sink: Optional[CryptoPairClickHouseEventWriter] = None`. `finalize()` writes `self.sink.contract().to_dict()` under the `"clickhouse_sink"` manifest key.
- `paper_runner.py` `CryptoPairPaperRunner.__init__` accepts `sink: Optional[CryptoPairClickHouseEventWriter] = None`. Feed-state transitions collected in `self._feed_state_transitions` during `_process_opportunity()`. `run()` calls `self.sink.write_events(events)` once after `record_run_summary`, records `sink_write_result` as a runtime event, and embeds `write_result.to_dict()` in the manifest under `"sink_write_result"`.
- `crypto_pair_run.py` parser exposes `--sink-enabled`, `--clickhouse-host`, `--clickhouse-port`, `--clickhouse-user`. `main()` reads `CLICKHOUSE_PASSWORD` from env and exits 1 with a clear error if `--sink-enabled` is set but the variable is absent.
- `tests/test_crypto_pair_runner_events.py` exists with 5 passing tests.
- `tests/test_crypto_pair_run.py` and `tests/test_crypto_pair_clickhouse_sink.py` are unchanged and still pass.
- `docs/features/FEATURE-crypto-pair-runner-v1.md` and `docs/dev_logs/2026-03-23_phase1a_paper_runner_sink_wiring_v0.md` exist.
- No Docker or live ClickHouse is required for any test to pass.
- No live trading logic is touched.
