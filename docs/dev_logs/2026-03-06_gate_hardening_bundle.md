# Dev Log: Gate Hardening Bundle — Gate 1 and Gate 3

**Date:** 2026-03-06
**Branch:** simtrader
**Author:** Claude (automated)

---

## Summary

Two gate validation gaps were closed:

1. **Gate 1 (Replay Determinism)** — Fixed two distinct defects in `close_replay_gate.py` that prevented the gate from running at all or from passing once it ran.
2. **Gate 3 (Shadow Mode / Cancel-All-on-Disconnect)** — Proven and implemented: `cancel_all_immediate` added to `SimBroker`; shadow runner calls it on every WS disconnect before reconnecting. Tests added at both unit and integration level.

---

## Gate 1 — Replay Determinism

### Root Causes

**Defect A — Case-sensitive regex mismatched actual CLI output.**

| Location | Pattern | Actual CLI output |
|---|---|---|
| `close_replay_gate.py:36` | `Tape dir\s*:\s*` | `[quickrun] tape dir : ...` (stderr, lowercase) |
| `close_replay_gate.py:37` | `Run dir\s*:\s*` | `[simtrader run] run dir        : ...` (stderr, lowercase) |

The CLI prefixes lines with `[simtrader run]` and uses lowercase `run dir` / `tape dir`. The gate's regexes required exact case and no prefix, so they matched only the stdout summary lines (which exist for single-run quickrun but not always for sweep mode). For `simtrader run` the stderr line never matched, causing `"run_dir not found for replay #1"`.

**Defect B — `run_id` included in determinism comparison.**

`summary.json` contains a `run_id` field that is the timestamped directory name of the run. Since two replay runs always run at different wall-clock times, `run_id` always differs. `_diff_summaries` compared every field including `run_id`, producing a false-positive failure even when all financial fields were identical.

### Files Changed

- `tools/gates/close_replay_gate.py`

### Changes

```python
# Before
_TAPE_LINE_RE = re.compile(r"Tape dir\s*:\s*(.+?)/?$", re.MULTILINE)
_RUN_DIR_LINE_RE = re.compile(r"Run dir\s*:\s*(.+?)/?$", re.MULTILINE)

# After — case-insensitive, tolerates any prefix (including [simtrader run])
_TAPE_LINE_RE = re.compile(r"tape\s+dir\s*:\s*(.+?)/?$", re.MULTILINE | re.IGNORECASE)
_RUN_DIR_LINE_RE = re.compile(r"run\s+dir\s*:\s*(.+?)/?$", re.MULTILINE | re.IGNORECASE)
```

```python
# Added exclusion set
_DIFF_EXCLUDE = frozenset({"run_id"})

# _diff_summaries now skips _DIFF_EXCLUDE fields
all_keys = (set(a) | set(b)) - _DIFF_EXCLUDE
```

### Commands Executed

```
python tools/gates/close_replay_gate.py --duration 20
```

### Output

```
[1/4] Recording tape with quickrun --sweep quick_small ...
  Tape: artifacts\simtrader\tapes\20260306T044438Z_tape_bitboy-convicted_64fd7c95\events.jsonl

[2/4] Replay run #1 ...
  Run dir: artifacts\simtrader\runs\20260306T044459Z_run_bitboy-convicted_binary_complement_arb_sane

[3/4] Replay run #2 ...
  Run dir: artifacts\simtrader\runs\20260306T044500Z_run_bitboy-convicted_binary_complement_arb_sane

[4/4] Comparing summary.json ...
  PASS — both replays produced identical summary.json

Passed: artifacts/gates/replay_gate/gate_passed.json
```

**Gate 1: PASSED**

---

## Gate 3 — Shadow Mode Cancel-All-on-Disconnect

### Analysis

Gate 3 is a manual gate: an operator runs shadow mode live, verifies artifacts, and signs off by writing `artifacts/gates/shadow_gate/gate_passed.json`. The gate was **MISSING** (no artifact at all, no live shadow run completed).

The pre-condition for Gate 3 is that the shadow runner must implement **cancel-all-on-disconnect** before attempting reconnect. This prevents stale sim orders from filling against a reconnected book snapshot.

**Finding:** `SimBroker` had no `cancel_all_immediate` method. `ShadowRunner._ws_loop` had no cancel step in its disconnect handlers (`closed_exc` and `OSError`). The feature was absent, not hidden under another name.

### Files Changed

1. `packages/polymarket/simtrader/broker/sim_broker.py` — added `cancel_all_immediate`
2. `packages/polymarket/simtrader/shadow/runner.py` — called `cancel_all_immediate` in both disconnect handlers
3. `tests/test_simtrader_broker.py` — 5 unit tests for `SimBrokerCancelAllImmediate`
4. `tests/test_simtrader_shadow.py` — 3 integration tests for `TestCancelAllOnDisconnect`

### Implementation

**`SimBroker.cancel_all_immediate(seq, ts_recv)`** (new method):
- Iterates all orders; skips those in terminal states (FILLED, CANCELLED, REJECTED)
- Directly sets status to `CANCELLED` (bypasses latency queue — intentional: on disconnect, no future tape events will process delayed cancels)
- Appends `"cancelled"` broker event with `reason="disconnect"` for full auditability
- Returns count of orders cancelled

**`ShadowRunner._ws_loop` disconnect handlers** (two paths patched):

```python
# closed_exc path (WebSocketConnectionClosedException)
_n = broker.cancel_all_immediate(seq=event_seq, ts_recv=time.time())
if _n:
    logger.info("Disconnect cancel-all: %d sim order(s) cancelled before reconnect.", _n)
ws = _connect(reconnect=True)

# OSError path (socket error)
_n = broker.cancel_all_immediate(seq=event_seq, ts_recv=time.time())
if _n:
    logger.info("Socket-error cancel-all: %d sim order(s) cancelled before reconnect.", _n)
ws = _connect(reconnect=True)
```

Conservative behavior: cancel before reconnect fires in both disconnect paths. Does not affect the stall-exit path (stall = orderly shutdown, not a disconnect).

### Tests

**`TestSimBrokerCancelAllImmediate`** (5 unit tests in `test_simtrader_broker.py`):
- `test_cancels_all_pending_orders` — verifies both PENDING orders become CANCELLED
- `test_does_not_cancel_terminal_orders` — terminal orders are unchanged
- `test_emits_cancelled_events_with_disconnect_reason` — broker event has `reason="disconnect"`
- `test_returns_zero_when_no_open_orders` — safe to call on empty book
- `test_mixed_terminal_and_active_orders` — only non-terminal orders are touched

**`TestCancelAllOnDisconnect`** (3 integration tests in `test_simtrader_shadow.py`):

All use a mock `websocket` module injected via `patch.dict(sys.modules, {"websocket": mock})` with `time.time` patched to control the deadline, so no network connection is required.

- `test_cancel_all_called_on_closed_exc` — `WebSocketConnectionClosedException` triggers cancel_all_immediate
- `test_cancel_all_called_on_oserror` — `OSError` (socket error) triggers cancel_all_immediate
- `test_artifacts_written_after_disconnect` — all run artifacts still written even after disconnect

### Commands Executed

```
python -m pytest tests/test_simtrader_broker.py::TestSimBrokerCancelAllImmediate -v --tb=short
python -m pytest tests/test_simtrader_shadow.py::TestCancelAllOnDisconnect -v --tb=short
python -m pytest tests/test_simtrader_broker.py tests/test_simtrader_shadow.py tests/test_simtrader_replay.py tests/test_simtrader_sweep.py -v --tb=short
```

### Results

```
5 passed  (TestSimBrokerCancelAllImmediate)
3 passed  (TestCancelAllOnDisconnect)
127 passed  (full affected suite — no regressions)
```

**Gate 3 (MISSING → implementation complete; manual sign-off still required).**

Gate 3 requires a live shadow run and operator sign-off per `tools/gates/shadow_gate_checklist.md`. The code-level gap (cancel-all-on-disconnect) is now closed. Gate 3 remains MISSING until an operator completes the checklist and writes the artifact.

---

## Final Gate Matrix

```
Gate Status Report  [2026-03-06 04:45 UTC]
Gate 1 - Replay Determinism           [PASSED]    2026-03-06 04:44:35
Gate 2 - Scenario Sweep (>=70%)       [FAILED]    2026-03-06 00:36:25   (0/24 profitable)
Gate 3 - Shadow Mode (manual)         [MISSING]   -                     code ready; no live run
Gate 4 - Dry-Run Live                 [PASSED]    2026-03-05 21:50:10
```

---

## Stage 0 Readiness

**Stage 0 is still blocked.**

Blockers:
1. **Gate 2 FAILED** — BinaryComplementArb achieves 0/24 profitable scenarios in the sweep. This is a strategy alpha gap, out of scope for this bundle.
2. **Gate 3 MISSING** — No live shadow run has been executed and signed off. The code is ready; an operator must run the shadow mode checklist.

Gates 1 and 4 now both pass.
