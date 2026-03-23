# Dev Log: Parallel SimTrader Pool Design Pack

**Date:** 2026-03-20
**Task:** Produce a design pack for Parallel SimTrader execution using `multiprocessing.Pool`.
**OBJECTIVE:** Docs-only preparation for the next roadmap item after `benchmark_v1` closure.

## Files Created
- `docs/specs/SPEC-parallel-simtrader-pool-execution-v1.md`: Detailed specification for the parallel execution engine.

## Context and Constraints
- **Authority Order Followed:** Master Roadmap v4.2 -> PLAN_OF_RECORD.md -> ARCHITECTURE.md.
- **Current State:** Verified that `benchmark_v1` is still open (missing `config/benchmark_v1.tape_manifest`).
- **Implementation Status:** Design only. No source code was modified.
- **Prerequisite:** Implementation must wait until `benchmark_v1` is successfully closed.

## Key Design Decisions
1. **Tool Choice:** `multiprocessing.Pool` chosen over threads due to Python's GIL; SimTrader is CPU-bound during L2 book reconstruction.
2. **Worker Isolation:** Each worker receives a full set of parameters and manages its own internal state to ensure total determinism.
3. **CLI UX:** A new `--workers` flag will allow operators to tune performance based on their local hardware.
4. **Safety:** Added a "Risk Checklist" to the spec to address pickle compatibility and signal handling before implementation begins.

## Next Steps
1. Monitor `benchmark_v1` closure progress.
2. Once `config/benchmark_v1.tape_manifest` exists:
   - Implement `ParallelReplayRunner` in `packages/polymarket/simtrader/replay/runner.py`.
   - Update `tools/cli/simtrader.py` to support `--workers` and `--benchmark`.
   - Verify performance targets (50 tapes in ~5s).
