---
phase: quick-8
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/batch_run.py
  - tests/test_batch_run.py
  - docs/features/FEATURE-batch-run-hypothesis-leaderboard.md
autonomous: true

must_haves:
  truths:
    - "--aggregate-only --run-roots <path> skips all scanning and produces leaderboard from existing run root dirs"
    - "--workers N parallelizes per-user scans and output ordering is identical to serial execution"
    - "continue-on-error is respected under --workers (failures logged, remaining users processed)"
    - "No network calls occur in tests"
  artifacts:
    - path: "tools/cli/batch_run.py"
      provides: "aggregate_only_from_roots(), updated BatchRunner.run_batch() with workers support"
      contains: "ThreadPoolExecutor"
    - path: "tests/test_batch_run.py"
      provides: "tests for aggregate-only mode and workers determinism"
      exports: ["test_aggregate_only_from_run_roots", "test_workers_ordering_matches_serial"]
  key_links:
    - from: "build_parser()"
      to: "main()"
      via: "--aggregate-only / --run-roots / --workers args"
      pattern: "aggregate_only|run_roots|workers"
    - from: "BatchRunner.run_batch()"
      to: "ThreadPoolExecutor"
      via: "workers parameter"
      pattern: "ThreadPoolExecutor|concurrent.futures"
---

<objective>
Add two features to batch-run: (1) --aggregate-only --run-roots <dir_or_file> to re-aggregate existing run roots without re-scanning; (2) --workers N to parallelize per-user scans with deterministic output ordering.

Purpose: --aggregate-only makes leaderboard re-generation instant when scans already exist. --workers cuts wall time for large user lists.
Output: Updated batch_run.py, new tests, updated feature doc.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@tools/cli/batch_run.py
@tests/test_batch_run.py
@docs/features/FEATURE-batch-run-hypothesis-leaderboard.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add --aggregate-only + --run-roots and --workers to BatchRunner</name>
  <files>tools/cli/batch_run.py</files>
  <action>
**aggregate-only mode:**

Add a module-level function `aggregate_from_roots(run_roots: list[Path]) -> tuple[list[dict], dict[str, list[dict]]]` that iterates over the provided paths and calls `_success_user_result` for each (using the directory name as the user slug if the run root does not contain a resolvable user identifier; prefer reading `user_slug` from `hypothesis_candidates.json` if present). Return `(per_user_results, segment_contributions)` using the same shape that `run_batch` already builds.

Update `BatchRunner.run_batch()` signature to accept an optional `run_roots_override: list[Path] | None = None`. When `run_roots_override` is provided, skip the scan loop entirely and call `aggregate_from_roots(run_roots_override)` instead. The rest of the method (segment aggregation, file writing) is unchanged.

Add a standalone entry-point function `aggregate_only(*, run_roots: list[Path], output_root: Path, batch_id: str, now_provider=None) -> dict[str, str]` that constructs a `BatchRunner` and calls `run_batch` with `run_roots_override`. This keeps `main()` readable.

**--run-roots resolution:**

`--run-roots` accepts a single path that is either:
- A directory: all immediate subdirectories are treated as individual run roots (non-recursive; skip files).
- A file: each non-blank, non-comment line is a path to a run root directory.

Add a helper `_resolve_run_roots(path: Path) -> list[Path]` that applies this logic and raises `FileNotFoundError` if any resolved run root does not exist as a directory.

**--workers N (parallel scans):**

Add `workers: int = 1` parameter to `BatchRunner.run_batch()`. When `workers > 1` and `run_roots_override` is None, use `concurrent.futures.ThreadPoolExecutor(max_workers=workers)` to submit one future per user. Collect results in original user-list order (iterate futures in the same order as `users`, not completion order) to guarantee determinism. Honor `continue_on_error`: if a future raises and `continue_on_error=False`, cancel remaining futures and re-raise; if `continue_on_error=True`, append a failure result and continue. When `workers == 1` keep the current sequential loop (no executor).

**Parser changes in `build_parser()`:**

```python
parser.add_argument(
    "--aggregate-only",
    action="store_true",
    default=False,
    help="Skip scanning; aggregate existing run roots into a leaderboard.",
)
parser.add_argument(
    "--run-roots",
    help=(
        "Path to a directory of run roots OR a file listing run root paths, "
        "one per line. Required when --aggregate-only is set."
    ),
)
parser.add_argument(
    "--workers",
    type=int,
    default=1,
    help="Number of parallel scan workers (default: 1, sequential).",
)
```

**`main()` changes:**

- If `args.aggregate_only` is True and `args.run_roots` is None: print error and return 1.
- If `args.aggregate_only` is True: call `aggregate_only(run_roots=_resolve_run_roots(Path(args.run_roots)), ...)` and skip the regular `run_batch` path.
- Pass `workers=args.workers` to `runner.run_batch(...)`.
- --users remains required in the parser but `main()` should make it optional when `--aggregate-only` is set. Simplest approach: change `--users` to `required=False` in `build_parser()` and add a guard in `main()`: if not aggregate_only and not args.users, print error and return 1.

**Imports to add at top of file:**
```python
import concurrent.futures
```
  </action>
  <verify>pytest tests/test_batch_run.py -q --tb=short</verify>
  <done>All existing tests pass. New tests added in Task 2 also pass.</done>
</task>

<task type="auto">
  <name>Task 2: Tests for aggregate-only and workers determinism + update feature doc</name>
  <files>tests/test_batch_run.py, docs/features/FEATURE-batch-run-hypothesis-leaderboard.md</files>
  <action>
**Add to `tests/test_batch_run.py`:**

`test_aggregate_only_from_run_roots(tmp_path)`:
- Create two run roots using `_make_run_root()` for users `@u1` and `@u2` with different segment keys (`sport:tennis` for u1, `sport:cricket` for u2).
- Call `aggregate_only(run_roots=[run_root_u1, run_root_u2], output_root=tmp_path / "out", batch_id="batch-agg", now_provider=lambda: FIXED_NOW)` (import `aggregate_only` from `tools.cli.batch_run`).
- Assert `hypothesis_leaderboard.json` and `batch_manifest.json` exist.
- Assert `leaderboard["users_attempted"] == 2` and `leaderboard["users_succeeded"] == 2`.
- Assert both segment keys appear in `leaderboard["segments"]`.

`test_aggregate_only_directory_input(tmp_path)`:
- Create two run roots as subdirectories of `tmp_path / "roots"`.
- Call `_resolve_run_roots(tmp_path / "roots")` and assert it returns a list of length 2.
- This is a unit test of the helper, no BatchRunner needed.

`test_workers_ordering_matches_serial(tmp_path)`:
- Create three run roots for `@u1`, `@u2`, `@u3` with distinct single-candidate segments.
- Define `fake_scan` that returns the corresponding run root (no network).
- Run `runner.run_batch(..., workers=1)` -> capture `per_user` order and top_lists.
- Run `runner.run_batch(..., workers=3, batch_id="batch-par")` with the same inputs.
- Assert `per_user` list order (by `user` field) is identical between serial and parallel runs.
- Assert `top_lists` are identical between both runs.

`test_workers_continue_on_error_parallel(tmp_path)`:
- Create run roots for `@ok1`, `@bad`, `@ok2`.
- `fake_scan` raises for `@bad`.
- Run with `workers=2, continue_on_error=True`.
- Assert `users_attempted == 3`, `users_succeeded == 2`, `users_failed == 1`.
- Assert `@bad` row has `status == "failure"`.
- Assert per_user list preserves original user order.

Import `_resolve_run_roots` and `aggregate_only` from `tools.cli.batch_run` at top of test file.

**Update `docs/features/FEATURE-batch-run-hypothesis-leaderboard.md`:**

Add a new section `## Aggregate-Only Mode` after `## CLI Usage`:

```markdown
## Aggregate-Only Mode

Re-aggregate an existing set of scan run roots without re-running scans:

```bash
# Point at a directory of run roots
python -m polytool batch-run \
  --aggregate-only \
  --run-roots artifacts/research/batch_runs/2026-02-20/<batch_id>/

# Or point at a file listing run root paths (one per line)
python -m polytool batch-run \
  --aggregate-only \
  --run-roots my_run_roots.txt
```

`--run-roots` accepts:
- A directory: all immediate subdirectories are treated as run roots.
- A file: each non-blank, non-comment line is a path to a run root.

`--users` is not required in aggregate-only mode.
```

Add a `## Parallel Scan Workers` section after that:

```markdown
## Parallel Scan Workers

```bash
python -m polytool batch-run \
  --users users.txt \
  --workers 4 \
  --compute-clv
```

`--workers N` runs per-user scans in N parallel threads. Output ordering is always deterministic (matches the order users appear in `--users`). `--continue-on-error` is respected under parallel execution.
```

Update the `Batch options` bullet list to include:
- `--aggregate-only`: skip scanning, re-aggregate from existing run roots
- `--run-roots <path>`: directory of run roots or file listing them (required with --aggregate-only)
- `--workers <N>`: parallel scan threads (default 1)

Update the `## Tests` section to mention the new test functions.
  </action>
  <verify>pytest tests/test_batch_run.py -q --tb=short</verify>
  <done>
- `test_aggregate_only_from_run_roots` passes without any network calls.
- `test_aggregate_only_directory_input` passes.
- `test_workers_ordering_matches_serial` passes and demonstrates per_user order is stable.
- `test_workers_continue_on_error_parallel` passes.
- All pre-existing tests still pass (zero regressions).
- Feature doc includes both new sections with usage examples.
  </done>
</task>

</tasks>

<verification>
pytest tests/test_batch_run.py -v --tb=short

All 8+ tests pass. No imports of network libraries or scan module occur in the test file directly. `aggregate_only` and `_resolve_run_roots` are importable from `tools.cli.batch_run`.
</verification>

<success_criteria>
- `--aggregate-only --run-roots <dir>` produces a valid `hypothesis_leaderboard.json` in seconds using pre-existing run roots, with no scan invocation.
- `--workers N` reduces wall time for large user lists while segment rows and per_user order are byte-identical to serial execution.
- `continue_on_error=True` is honoured under parallel execution (failed users are recorded, not silently dropped).
- All tests pass with `pytest tests/test_batch_run.py -q`.
</success_criteria>

<output>
After completion, create `.planning/quick/8-batch-run-aggregate-only-and-workers-n-f/8-SUMMARY.md`
</output>
