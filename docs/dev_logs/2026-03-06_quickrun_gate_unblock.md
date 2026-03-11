# Quickrun Gate Unblock

## Root cause

`tools/cli/simtrader.py` `_quickrun()` built strategy config with:

```python
if strategy_name == "binary_complement_arb":
```

but never defined `strategy_name` in that scope. That produced a `NameError` during `quickrun`, which blocked both Gate 1 replay closure and Gate 2 sweep closure before either gate could complete its normal flow.

The minimal fix was to bind the same scoped identifier pattern already used by other `simtrader` subcommands:

```python
strategy_name = getattr(args, "strategy", "binary_complement_arb")
```

This preserves existing quickrun behavior because `quickrun` is still hard-wired to `binary_complement_arb` by default.

## Files changed

- `tools/cli/simtrader.py`
- `docs/dev_logs/2026-03-06_quickrun_gate_unblock.md`

## Commands run

1. `python tools/gates/close_replay_gate.py`
   - Result: failed in sandbox after timing out during `quickrun`.
   - Key output: `subprocess.TimeoutExpired ... timed out after 150 seconds`

2. `python -m polytool simtrader quickrun --sweep quick_small --duration 5`
   - Result: diagnostic run showed sandboxed network denial, not the original `strategy_name` crash.
   - Key output: `Failed to establish a new connection: [WinError 10013]`

3. `python tools/gates/close_replay_gate.py`
   - Rerun with network access.
   - Result: `quickrun` completed, tape recorded, Gate 1 then failed on replay result parsing.
   - Key output:
     - `Tape: artifacts\simtrader\tapes\20260306T003541Z_tape_bitboy-convicted_64fd7c95\events.jsonl`
     - `ERROR: could not locate run_dir for replay #1`

4. `python tools/gates/close_sweep_gate.py`
   - Run with network access.
   - Result: Gate 2 executed normally and reached its profitability check.
   - Key output:
     - `Scenario count: 24`
     - `Profitable   : 0/24  (0.0%)`
     - `Gate         : FAIL`

5. `python tools/gates/gate_status.py`
   - Result:
     - `Gate 1 - Replay Determinism           [FAILED] ... run_dir not found for replay #1`
     - `Gate 2 - Scenario Sweep ...           [FAILED]`

## Outputs and results

- `_quickrun` no longer crashes from undefined `strategy_name`.
- Gate 1 now gets past `quickrun`, records a tape, and fails later with a separate blocker.
- Gate 2 now runs its full sweep path instead of crashing in `_quickrun`.
- Gate 2 does not pass the gate criterion on this run: `0/24` profitable scenarios.

## Gate status

- Gate 1: not passed
- Gate 2: not passed

## Next blocker

The next real blocker after the `_quickrun` fix is in Gate 1 replay closure, not in `_quickrun`.

`tools/gates/close_replay_gate.py` tries to extract the replay run directory with:

```python
re.compile(r"Run dir\\s*:\\s*(.+?)/?$", re.MULTILINE)
```

but `simtrader run` emits:

```text
[simtrader run] run dir        : <path>
```

That output format mismatch prevents Gate 1 from locating `summary.json`, even though replay execution started successfully.

Gate 2's remaining failure is not a crash blocker; it is the gate's actual profitability criterion failing on the captured sweep.
