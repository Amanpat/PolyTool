# SPEC: Parallel SimTrader Pool Execution (v1)

**Status:** Draft (Implementation Ready)
**Created:** 2026-03-20
**Authors:** Gemini CLI (as PolyTool Contributor)
**Package:** `packages/polymarket/simtrader/`
**Prerequisite:** `benchmark_v1` closure (`config/benchmark_v1.tape_manifest`)

---

## 1. Purpose and Motivation

SimTrader replays are currently executed sequentially. While a single tape replay is fast, running a full benchmark suite (50 tapes) or a large parameter sweep (hundreds or thousands of combinations) is a significant bottleneck.

Tape replays are "embarrassingly parallel" — each run is independent, has no shared state, and does not require communication between workers. This specification describes a `multiprocessing.Pool` based implementation to parallelize these executions, targeting a 10x speedup on typical developer machines.

## 2. Goals and Non-Goals

### Goals
- Parallelize SimTrader replays using `multiprocessing.Pool`.
- Support parallel execution in both `simtrader run` (multiple tapes) and `simtrader sweep` (parameter grids).
- Maintain 100% determinism: parallel execution must produce byte-identical results to sequential execution.
- Provide a clean CLI interface via a `--workers` flag.
- Gracefully handle worker failures without crashing the entire batch.

### Non-Goals
- Parallelizing a *single* tape replay (replays are inherently sequential by event sequence).
- Distributed execution across multiple machines (local-only scope).
- Shared memory or IPC between workers (isolation is a requirement).

## 3. Implementation Design

### 3.1 Process Model
The implementation will use `multiprocessing.Pool` to manage a pool of worker processes.

```python
import os
from multiprocessing import Pool

# Default to N-2 cores to keep the system responsive
DEFAULT_WORKERS = max(1, os.cpu_count() - 2)
```

### 3.2 Worker Function
A top-level (pickleable) worker function will be defined to encapsulate a single replay run.

```python
def simtrader_worker(run_args):
    """
    Executes a single SimTrader replay.
    run_args: tuple (tape_path, strategy_config, output_dir, ...)
    Returns: (run_id, success, metrics, error_message)
    """
    # Initialize L2Book, Broker, Portfolio locally within the process
    # Run the replay
    # Write artifacts to output_dir
    # Return summary
```

### 3.3 Orchestration
The main process will:
1. Prepare the list of tasks (tape/config combinations).
2. Initialize the `Pool` with the requested number of workers.
3. Use `pool.imap_unordered` or `pool.map` to distribute tasks.
4. Collect results and update a progress bar (e.g., using `tqdm`).
5. Generate a final summary/leaderboard after all workers complete.

### 3.4 Worker Isolation
Each worker must:
- Have its own instance of `L2Book`, `BrokerFillSim`, and `Portfolio`.
- Write to a unique directory in `artifacts/simtrader/runs/<run_id>/`.
- Avoid any global state mutation (e.g., in `STRATEGY_REGISTRY`).

## 4. CLI Interface

The following flags will be added/updated in `tools/cli/simtrader.py`:

- `--workers N`: Number of parallel workers (default: `cpu_count - 2`). Set to 1 for sequential execution.
- `--benchmark`: Shortcut to run against `config/benchmark_v1.tape_manifest`.

Example usage:
```bash
# Run the full benchmark suite in parallel
python -m polytool simtrader run --benchmark --workers 10

# Run a parameter sweep in parallel
python -m polytool simtrader sweep --config sweep.yaml --workers 8
```

## 5. Artifacts and Outputs

- **Per-run artifacts**: No change to existing layout under `artifacts/simtrader/runs/<run_id>/`.
- **Batch summary**: `batch_summary.json` will be updated to include worker metadata (e.g., which worker process handled which run).
- **Logs**: Workers will log to per-run log files instead of a shared stdout to prevent interleaved output.

## 6. Failure Handling

- If a worker process crashes or raises an unhandled exception, the orchestrator must catch the failure.
- The failed task will be marked as `FAILED` in the final summary with the associated error message.
- The remaining tasks in the pool should continue to execute.

## 7. Performance Target

- **Hardware**: i7-8700K (6 cores, 12 threads)
- **Task**: Replay 50 tapes (approx. 1 hour of live data each)
- **Target**: < 5 seconds total wall-clock time with `--workers 10`.

## 8. Acceptance Criteria

1. **Determinism**: Running the same benchmark twice (sequential vs parallel) produces identical PnL results in `pnl_summary.json`.
2. **Speed**: Parallel execution shows a near-linear speedup (accounting for pool overhead) up to `os.cpu_count()`.
3. **Robustness**: A single corrupt tape file does not halt the entire batch; the summary correctly identifies the failed run.
4. **Clean Exit**: Ctrl-C during a parallel run terminates all worker processes immediately and safely.

## 9. Implementation Plan (Future)

**WAIT: DO NOT IMPLEMENT UNTIL `benchmark_v1` IS CLOSED.**

### File Touch Plan
- `packages/polymarket/simtrader/replay/runner.py`: Add `ParallelReplayRunner` class.
- `tools/cli/simtrader.py`: Add `--workers` and `--benchmark` flags; wire up the `Pool`.
- `tests/test_simtrader_parallel.py`: New test suite for parallel execution and determinism.

---

## 10. Risk Checklist

- [ ] **Race Conditions**: Verify no shared file-system writes (e.g., log files) between workers.
- [ ] **Pickle Compatibility**: Ensure all strategy configs and runner arguments are pickleable for `multiprocessing`.
- [ ] **Memory Usage**: Monitor total RAM usage when running with high worker counts (50+).
- [ ] **Signal Handling**: Ensure workers terminate on parent process exit (SIGINT/SIGTERM).

---

## 11. Operator Checklist: Post-Benchmark Kickoff

Once `benchmark_v1` is closed, follow these steps to verify the parallel implementation:

1. **Verify Manifest**:
   ```bash
   python -m polytool benchmark-manifest --validate
   ```
2. **First Parallel Run**:
   Run the full benchmark suite with default workers:
   ```bash
   python -m polytool simtrader run --benchmark
   ```
3. **Compare with Sequential**:
   Run a subset (e.g., 5 tapes) sequentially and in parallel, then diff the `pnl_summary.json` files:
   ```bash
   # Parallel
   python -m polytool simtrader run --tapes tape1,tape2... --workers 4 --output-dir artifacts/simtrader/runs/parallel_test
   # Sequential
   python -m polytool simtrader run --tapes tape1,tape2... --workers 1 --output-dir artifacts/simtrader/runs/sequential_test
   
   diff artifacts/simtrader/runs/parallel_test/batch_summary.json artifacts/simtrader/runs/sequential_test/batch_summary.json
   ```
4. **Stress Test**:
   Run a large sweep (e.g., 100+ combinations) and monitor system resource usage in Task Manager/`top`.
