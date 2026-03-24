---
phase: quick
plan: 21
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/crypto_pairs/clickhouse_sink.py
  - packages/polymarket/crypto_pairs/paper_runner.py
  - tools/cli/crypto_pair_run.py
  - tests/test_crypto_pair_runner_events.py
  - tests/test_crypto_pair_run.py
  - docs/features/FEATURE-crypto-pair-runner-v2.md
autonomous: true
requirements: [PHASE1A-INCREMENTAL-SINK]

must_haves:
  truths:
    - "Default runs (no --sink-streaming) behave identically to quick-020: one batch write at finalization"
    - "Streaming runs (--sink-streaming) emit each Track 2 event to the sink immediately when it is produced during the run loop"
    - "A sink write failure in streaming mode logs a warning and continues the run — artifacts remain complete"
    - "Safety state transitions are emitted once per genuine state change in streaming mode, no duplicate storm"
    - "The run summary event is always emitted at finalization regardless of flush mode"
    - "No ClickHouse or Docker dependency is required for any test to pass"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/clickhouse_sink.py"
      provides: "write_event() single-event helper for incremental streaming"
    - path: "packages/polymarket/crypto_pairs/paper_runner.py"
      provides: "CryptoPairPaperRunner with sink_flush_mode='batch'|'streaming'"
    - path: "tools/cli/crypto_pair_run.py"
      provides: "--sink-streaming CLI flag"
    - path: "tests/test_crypto_pair_runner_events.py"
      provides: "offline tests for streaming mode, soft-fail, and dedup behavior"
  key_links:
    - from: "paper_runner.py _process_opportunity()"
      to: "sink.write_event(event)"
      via: "immediate call after each observation/intent/fill/exposure build"
      pattern: "sink_flush_mode.*streaming"
    - from: "paper_runner.py run() finalization block"
      to: "sink.write_events([run_summary_event])"
      via: "always emits run_summary at end regardless of flush mode"
      pattern: "RunSummaryEvent"
---

<objective>
Add opt-in incremental mid-run event emission to the Phase 1A paper runner sink.

Purpose: Allow Track 2 events (opportunity observed, intent generated, simulated fill,
partial exposure updated, safety state transition) to be emitted to ClickHouse
incrementally during the run loop rather than only in a single batch at finalization.
This enables Grafana visibility during long runs without breaking default behavior.

Output:
- `clickhouse_sink.py`: adds `write_event()` single-event convenience helper and `_consecutive_fail_count` guard
- `paper_runner.py`: adds `sink_flush_mode` field to `CryptoPairRunnerSettings`; runner calls sink incrementally in streaming mode
- `tools/cli/crypto_pair_run.py`: adds `--sink-streaming` flag
- `tests/test_crypto_pair_runner_events.py`: new test file covering streaming vs batch, soft-fail, dedup
- `tests/test_crypto_pair_run.py`: one regression test verifying default behavior unchanged
- `docs/features/FEATURE-crypto-pair-runner-v2.md`: feature doc
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/polymarket/crypto_pairs/paper_runner.py
@packages/polymarket/crypto_pairs/clickhouse_sink.py
@packages/polymarket/crypto_pairs/event_models.py
@tools/cli/crypto_pair_run.py
@tests/test_crypto_pair_clickhouse_sink.py
@tests/test_crypto_pair_run.py

<interfaces>
<!-- Key contracts the executor needs. No codebase exploration required. -->

From clickhouse_sink.py:
```python
class CryptoPairClickHouseEventWriter(Protocol):
    def write_events(self, events: Sequence[CryptoPairTrack2Event]) -> ClickHouseWriteResult: ...
    def contract(self) -> ClickHouseSinkContract: ...

@dataclass(frozen=True)
class ClickHouseWriteResult:
    enabled: bool
    table_name: str
    attempted_events: int
    written_rows: int
    skipped_reason: str = ""
    error: str = ""

@dataclass(frozen=True)
class CryptoPairClickHouseSinkConfig:
    enabled: bool = False
    soft_fail: bool = True
    # ... clickhouse_host, port, user, password, table_name
```

From paper_runner.py:
```python
@dataclass(frozen=True)
class CryptoPairRunnerSettings:
    # existing fields — add sink_flush_mode: str = "batch"

class CryptoPairPaperRunner:
    sink: CryptoPairClickHouseEventWriter  # injected
    # run() calls sink.write_events(events) ONCE at end
    # _process_opportunity() builds observation, intent, fills, exposure

    # Feed state transitions are collected in self._feed_state_transitions list
    # and converted to SafetyStateTransitionEvent objects at end of run()
```

From event_models.py:
```python
# Constructors for immediate emission in streaming mode:
OpportunityObservedEvent.from_observation(observation, mode="paper")
IntentGeneratedEvent.from_intent(intent, mode="paper")
SimulatedFillRecordedEvent.from_fill(fill, mode="paper")
PartialExposureUpdatedEvent.from_exposure(exposure, mode="paper")
SafetyStateTransitionEvent.from_feed_state_change(...)  # already in _process_opportunity
RunSummaryEvent.from_summary(run_summary, mode="paper", stopped_reason=stopped_reason)
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add write_event() helper and consecutive-fail guard to clickhouse_sink.py</name>
  <files>packages/polymarket/crypto_pairs/clickhouse_sink.py</files>
  <behavior>
    - write_event(event) on DisabledCryptoPairClickHouseSink returns a disabled ClickHouseWriteResult (same as write_events([event]))
    - write_event(event) on CryptoPairClickHouseSink calls write_events([event]) internally
    - write_event returns the same ClickHouseWriteResult shape as write_events
    - CryptoPairClickHouseSink gains _consecutive_fail_count: int instance attribute (starts at 0)
    - After a successful write, _consecutive_fail_count resets to 0
    - After a failed write (soft_fail=True), _consecutive_fail_count increments
    - If _consecutive_fail_count >= max_consecutive_failures (default 5), write_event is a no-op (returns skipped_reason="consecutive_fail_limit")
    - This prevents duplicate-error storms when ClickHouse is down during a long streaming run
    - CryptoPairClickHouseEventWriter Protocol gains write_event() method signature
  </behavior>
  <action>
    In clickhouse_sink.py:

    1. Add `write_event()` to the `CryptoPairClickHouseEventWriter` Protocol:
       ```python
       def write_event(self, event: CryptoPairTrack2Event) -> ClickHouseWriteResult: ...
       ```

    2. Add `write_event()` to `DisabledCryptoPairClickHouseSink`:
       ```python
       def write_event(self, event: CryptoPairTrack2Event) -> ClickHouseWriteResult:
           return self.write_events([event])
       ```

    3. Add `_consecutive_fail_count: int = 0` and `_max_consecutive_failures: int` to
       `CryptoPairClickHouseSink.__init__()`. Accept `max_consecutive_failures: int = 5`
       as a constructor param. Store as `self._max_consecutive_failures`.
       Note: `CryptoPairClickHouseSink` is NOT frozen (it's a regular class), so instance
       mutation is fine.

    4. Add `write_event()` to `CryptoPairClickHouseSink`:
       ```python
       def write_event(self, event: CryptoPairTrack2Event) -> ClickHouseWriteResult:
           if self._consecutive_fail_count >= self._max_consecutive_failures:
               return ClickHouseWriteResult(
                   enabled=True,
                   table_name=self.config.table_name,
                   attempted_events=1,
                   written_rows=0,
                   skipped_reason="consecutive_fail_limit",
               )
           result = self.write_events([event])
           if result.error:
               self._consecutive_fail_count += 1
           else:
               self._consecutive_fail_count = 0
           return result
       ```

    5. Update `__all__` to include the new methods are accessible (no changes needed to
       `__all__` for methods, but verify `CryptoPairClickHouseSink` is listed).

    Tests to write first in a new file `tests/test_crypto_pair_clickhouse_sink.py` additions:
    Actually write tests in Task 3's test file `tests/test_crypto_pair_runner_events.py` since
    Task 3 covers all new sink behavior tests. Verify existing
    `tests/test_crypto_pair_clickhouse_sink.py` still passes unchanged.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_clickhouse_sink.py -q --tb=short</automated>
  </verify>
  <done>
    DisabledCryptoPairClickHouseSink.write_event() exists and returns disabled ClickHouseWriteResult.
    CryptoPairClickHouseSink.write_event() exists, delegates to write_events(), increments
    _consecutive_fail_count on error, no-ops after limit is reached.
    Protocol has write_event() in its interface.
    Existing sink tests pass unchanged.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Add sink_flush_mode to CryptoPairRunnerSettings and streaming emission in CryptoPairPaperRunner</name>
  <files>packages/polymarket/crypto_pairs/paper_runner.py, tools/cli/crypto_pair_run.py</files>
  <behavior>
    - CryptoPairRunnerSettings gains sink_flush_mode: str = "batch" field
    - Valid values are "batch" and "streaming"; __post_init__ raises ValueError for anything else
    - In "batch" mode: behavior is identical to quick-020 (single write_events() call at finalization)
    - In "streaming" mode: after each call to store.record_observation(), store.record_intent(),
      store.record_fill(), store.record_exposure() in _process_opportunity(), the runner immediately
      builds the corresponding Track 2 event and calls sink.write_event(event)
    - Safety state transitions in streaming mode: when a genuine state change is detected
      (_feed_state_transitions.append), immediately build and emit the SafetyStateTransitionEvent
      via sink.write_event() — do NOT also include it in the finalization batch (prevents duplicates)
    - In streaming mode, the finalization block still emits the RunSummaryEvent via
      sink.write_events([run_summary_event]) after building run_summary
    - In streaming mode, sink.write_event() result is logged via store.record_runtime_event()
      with event_type "sink_stream_write" only when there is an error (avoids log flooding
      on each successful event)
    - The final sink_write_result in the manifest reflects ONLY the finalization batch call
      (run_summary + any remaining events not streamed), consistent with the existing manifest key
    - cli: --sink-streaming flag added; passed through run_crypto_pair_runner() as sink_flush_mode="streaming"
    - --sink-streaming is only meaningful when --sink-enabled is also set; if --sink-streaming
      is given without --sink-enabled, emit a warning to stderr but do not fail
    - to_dict() on CryptoPairRunnerSettings includes sink_flush_mode
    - build_runner_settings() reads "sink_flush_mode" from config payload
  </behavior>
  <action>
    In paper_runner.py:

    1. Add `sink_flush_mode: str = "batch"` to `CryptoPairRunnerSettings` dataclass after `cycle_limit`.

    2. In `__post_init__`, add validation:
       ```python
       if self.sink_flush_mode not in ("batch", "streaming"):
           raise ValueError(f"sink_flush_mode must be 'batch' or 'streaming', got {self.sink_flush_mode!r}")
       ```

    3. Add `sink_flush_mode` to `to_dict()` return value.

    4. In `build_runner_settings()`, read `sink_flush_mode` from payload:
       ```python
       sink_flush_mode=payload.get("sink_flush_mode", "batch"),
       ```

    5. In `with_artifact_base_dir()`, pass through `sink_flush_mode=self.sink_flush_mode`.

    6. In `CryptoPairPaperRunner._process_opportunity()`, after each store.record_* call that
       produces a Track 2 event, add streaming emission guarded by `if self.settings.sink_flush_mode == "streaming":`.

       Specifically, add after `self.store.record_observation(observation)`:
       ```python
       if self.settings.sink_flush_mode == "streaming":
           _evt = OpportunityObservedEvent.from_observation(observation, mode="paper")
           _r = self.sink.write_event(_evt)
           if _r.error:
               import logging as _logging
               _logging.getLogger(__name__).warning("sink stream write failed: %s", _r.error)
               self.store.record_runtime_event("sink_stream_write_failed", event_type=_evt.event_type, error=_r.error)
       ```

       Same pattern after `self.store.record_intent(intent)` (IntentGeneratedEvent),
       after each `self.store.record_fill(fill)` (SimulatedFillRecordedEvent),
       after `self.store.record_exposure(exposure)` (PartialExposureUpdatedEvent).

       For safety state transitions, in the block where `previous_feed_state is not None` and
       `self._feed_state_transitions.append(...)` is called, also immediately emit in streaming mode:
       ```python
       if self.settings.sink_flush_mode == "streaming":
           _fst_evt = SafetyStateTransitionEvent.from_feed_state_change(
               transition_id=...,  # same values just appended to _feed_state_transitions
               ...
           )
           _r = self.sink.write_event(_fst_evt)
           if _r.error:
               self.store.record_runtime_event("sink_stream_write_failed", event_type="safety_state_transition", error=_r.error)
       ```

       To avoid duplicates, track streamed transition_ids in a set `self._streamed_transition_ids`.
       At finalization, the `transition_events` list is still built for batch mode compatibility,
       but in streaming mode skip transitions already in `_streamed_transition_ids` before passing
       to `self.sink.write_events(events)`.

    7. In `run()` finalization block, update the events list and sink.write_events() call:
       - In streaming mode: `events` list is only `[run_summary_event]` plus any un-streamed transitions
       - In batch mode: `events` is the full list as before (unchanged)
       - The `write_result` from `sink.write_events(events)` is recorded in manifest as before

    8. In `CryptoPairPaperRunner.__init__()`, add:
       ```python
       self._streamed_transition_ids: set[str] = set()
       ```

    In tools/cli/crypto_pair_run.py:

    9. Add to `build_parser()`:
       ```python
       parser.add_argument(
           "--sink-streaming",
           action="store_true",
           default=False,
           help=(
               "Enable incremental mid-run event emission to the sink (opt-in). "
               "Only meaningful when --sink-enabled is also set. "
               "Default: batch mode emits all events once at finalization."
           ),
       )
       ```

    10. Add `sink_flush_mode: str = "batch"` to `run_crypto_pair_runner()` signature.

    11. In `main()`, before calling `run_crypto_pair_runner()`:
        ```python
        sink_flush_mode = "batch"
        if args.sink_streaming:
            if not args.sink_enabled:
                print("Warning: --sink-streaming has no effect without --sink-enabled.", file=sys.stderr)
            sink_flush_mode = "streaming"
        ```

    12. Pass `sink_flush_mode=sink_flush_mode` to `run_crypto_pair_runner()`, which passes it
        to `build_runner_settings()` as `config_payload={"sink_flush_mode": sink_flush_mode, ...}`.

    Use imports already present in paper_runner.py for event model classes
    (OpportunityObservedEvent etc. are in event_models.py, already imported via
    `from .event_models import SafetyStateTransitionEvent, build_events_from_paper_records`).
    Expand that import to include the individual event constructors needed.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m polytool crypto-pair-run --help && python -m pytest tests/test_crypto_pair_run.py -q --tb=short</automated>
  </verify>
  <done>
    --sink-streaming flag appears in --help output.
    CryptoPairRunnerSettings accepts sink_flush_mode="batch"|"streaming", rejects other values.
    Default paper run behavior is unchanged (existing test_crypto_pair_run.py tests pass).
    In streaming mode the runner calls sink.write_event() per event during _process_opportunity().
    Safety state transitions are not duplicated in streaming mode.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Write targeted tests and feature doc</name>
  <files>tests/test_crypto_pair_runner_events.py, docs/features/FEATURE-crypto-pair-runner-v2.md</files>
  <behavior>
    Test cases for tests/test_crypto_pair_runner_events.py:

    1. test_batch_mode_default_unchanged: run with sink but no streaming; sink.write_event() is never called;
       sink.write_events() is called exactly once at finalization; manifest has sink_write_result.

    2. test_streaming_mode_emits_incrementally: run with sink_flush_mode="streaming";
       verify sink.write_event() is called at least once during _process_opportunity()
       (opportunity, intent, fill, exposure events), NOT only at finalization.

    3. test_streaming_mode_sink_failure_soft_fails: sink.write_event() raises / returns error;
       run completes normally; artifacts directory exists with manifest; no exception propagated.

    4. test_streaming_mode_consecutive_fail_guard: CryptoPairClickHouseSink with max_consecutive_failures=2;
       inject failing client; after 2 failures write_event() returns skipped_reason="consecutive_fail_limit".

    5. test_streaming_mode_safety_transition_no_duplicate: inject two cycles where feed transitions
       from "connected_fresh" to "stale"; verify SafetyStateTransitionEvent is emitted via write_event()
       exactly once (not again in finalization batch).

    6. test_streaming_mode_run_summary_always_at_finalization: streaming run; verify that
       even though per-cycle events are streamed, a RunSummaryEvent is still passed to
       write_events() at finalization.

    7. test_write_event_disabled_sink_noop: DisabledCryptoPairClickHouseSink.write_event()
       returns enabled=False, written_rows=0, skipped_reason="disabled".

    8. test_write_event_enabled_sink_delegates: CryptoPairClickHouseSink.write_event() with
       mock client; delegates to write_events([event]); client.insert_rows called once.

    All tests are fully offline — no ClickHouse or Docker required. Use the existing
    mock patterns from test_crypto_pair_run.py (_make_gamma_client, _make_clob_client,
    _fresh_snapshot) and inject a stub sink using unittest.mock.MagicMock or a minimal
    spy class.

    For the feature doc docs/features/FEATURE-crypto-pair-runner-v2.md, document:
    - What changed vs v1 (streaming mode vs batch mode)
    - The --sink-streaming CLI flag
    - The consecutive_fail_limit guard
    - Artifact truth remains canonical
    - Which events are streamed in streaming mode
    - The finalization run_summary is always emitted
    - Dev log reference
  </behavior>
  <action>
    Create tests/test_crypto_pair_runner_events.py with the 8 test cases listed above.

    For test infrastructure, use a simple spy class instead of MagicMock for the sink
    so call counts and call arguments are inspectable:

    ```python
    class _SpySink:
        def __init__(self, fail_after: int = 0):
            self.write_event_calls: list = []
            self.write_events_calls: list = []
            self._fail_after = fail_after
            self._call_count = 0

        def write_event(self, event):
            self.write_event_calls.append(event)
            self._call_count += 1
            if self._fail_after and self._call_count > self._fail_after:
                return ClickHouseWriteResult(enabled=True, table_name="t", attempted_events=1, written_rows=0, error="injected")
            return ClickHouseWriteResult(enabled=True, table_name="t", attempted_events=1, written_rows=1)

        def write_events(self, events):
            events = list(events)
            self.write_events_calls.append(events)
            return ClickHouseWriteResult(enabled=True, table_name="t", attempted_events=len(events), written_rows=len(events))

        def contract(self):
            from packages.polymarket.crypto_pairs.clickhouse_sink import ClickHouseSinkContract
            return ClickHouseSinkContract()
    ```

    Use the same runner setup pattern as test_crypto_pair_run.py for tests 1-6:
    inject gamma_client, clob_client, reference_feed stub, and the spy sink, with
    cycle_limit=2 and a no-op sleep_fn.

    For tests 7-8, test the sink classes directly (unit tests, no runner needed).

    After writing tests, run the full suite to confirm no regressions:
    python -m pytest tests/test_crypto_pair_runner_events.py tests/test_crypto_pair_run.py tests/test_crypto_pair_clickhouse_sink.py -q --tb=short

    Create docs/features/FEATURE-crypto-pair-runner-v2.md with the feature summary.

    Create docs/dev_logs/2026-03-23_phase1a_incremental_sink_streaming_v0.md documenting
    the work done, test counts, and any design decisions (this is mandatory per CLAUDE.md).
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_crypto_pair_runner_events.py tests/test_crypto_pair_run.py tests/test_crypto_pair_clickhouse_sink.py -q --tb=short</automated>
  </verify>
  <done>
    All 8 new tests in test_crypto_pair_runner_events.py pass.
    Existing tests in test_crypto_pair_run.py and test_crypto_pair_clickhouse_sink.py pass unchanged.
    docs/features/FEATURE-crypto-pair-runner-v2.md exists with streaming mode documented.
    docs/dev_logs/2026-03-23_phase1a_incremental_sink_streaming_v0.md exists.
  </done>
</task>

</tasks>

<verification>
Final checks after all tasks:

1. python -m polytool crypto-pair-run --help  — shows --sink-streaming flag with clear description
2. python -m pytest tests/test_crypto_pair_runner_events.py tests/test_crypto_pair_run.py tests/test_crypto_pair_clickhouse_sink.py -q --tb=short  — all pass
3. python -m pytest tests/ -x -q --tb=short  — no regressions in full suite
4. Confirm docs/features/FEATURE-crypto-pair-runner-v2.md exists
5. Confirm docs/dev_logs/2026-03-23_phase1a_incremental_sink_streaming_v0.md exists
</verification>

<success_criteria>
- Default (batch) mode behavior is provably unchanged by the existing test suite
- Streaming mode emits events incrementally during _process_opportunity() (test 2 proves it)
- Sink failure in streaming mode does not abort the run (test 3 proves it)
- Consecutive failure guard prevents error storms (test 4 proves it)
- Safety state transitions are not duplicated in streaming mode (test 5 proves it)
- RunSummaryEvent is always emitted at finalization (test 6 proves it)
- No ClickHouse or Docker dependency in any test
- --sink-streaming CLI flag is visible in --help and passes through to the runner
- All scoped test files pass; no pre-existing tests broken
</success_criteria>

<output>
After completion, create `.planning/quick/21-add-incremental-mid-run-event-emission-f/21-SUMMARY.md`
</output>
