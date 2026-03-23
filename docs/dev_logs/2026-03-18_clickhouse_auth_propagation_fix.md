# Dev Log: ClickHouse Auth Propagation Fix

**Date:** 2026-03-18
**Branch:** `phase-1`
**Objective:** Fix the silent `"polytool_admin"` credential fallback that caused
every `fetch-price-2min` invocation inside `close-benchmark-v1` to fail with
ClickHouse error code 516 `AUTHENTICATION_FAILED`, leaving Silver inventory at 0
and the benchmark closure path blocked.

---

## Outcome

Fix applied. All 76 affected tests pass. No source logic or benchmark contract
changed.

---

## Root Cause

`close_benchmark_v1.main()` and `batch_reconstruct_silver.main()` both resolved
the ClickHouse password as:

```python
ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")
```

Python does **not** auto-load `.env` files. When the operator runs from a host
shell without `export CLICKHOUSE_PASSWORD=<real_password>`, the env var is
absent and Python silently substituted `"polytool_admin"`. ClickHouse rejected
every request with code 516.

The same string `"polytool_admin"` also appeared as a default in four function
signatures:

- `run_silver_gap_fill_stage(clickhouse_password: str = "polytool_admin")`
- `run_closure(clickhouse_password: str = "polytool_admin")`
- `run_batch(clickhouse_password: str = "polytool_admin")`
- `run_batch_from_targets(clickhouse_password: str = "polytool_admin")`

---

## Fix

### `tools/cli/close_benchmark_v1.py`

1. `run_silver_gap_fill_stage` default: `"polytool_admin"` → `""`
2. `run_closure` default: `"polytool_admin"` → `""`
3. `main()` credential resolution (before fix):
   ```python
   ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")
   ```
   After fix:
   ```python
   ch_password = args.clickhouse_password
   if ch_password is None:
       ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
   if ch_password is None:
       print(
           "Error: ClickHouse password not set.\n"
           "  Pass --clickhouse-password PASSWORD, or export CLICKHOUSE_PASSWORD=<password>.",
           file=sys.stderr,
       )
       return 1
   ```

### `tools/cli/batch_reconstruct_silver.py`

1. `run_batch` default: `"polytool_admin"` → `""`
2. `run_batch_from_targets` default: `"polytool_admin"` → `""`
3. `main()` credential resolution: same pattern as above.

---

## Files Changed And Why

- `tools/cli/close_benchmark_v1.py`
  Removed silent fallback; fail-fast with clear error when no password supplied.
- `tools/cli/batch_reconstruct_silver.py`
  Same fix; keeps the two CLIs consistent.
- `tests/test_close_benchmark_v1.py`
  Added `import os`. Added `"--clickhouse-password", "testpass"` to two
  existing `TestCLISmoke` tests that previously succeeded only because the
  silent fallback existed. Added `TestCLISmoke.test_missing_password_returns_1`,
  `test_password_via_env_var_proceeds`, `test_password_flag_takes_precedence_over_env`.
- `tests/test_batch_silver.py`
  Added `"--clickhouse-password", "testpass"` to six existing `TestBatchCLI`
  tests. Added `test_missing_password_returns_1`, `test_password_via_env_var_proceeds`,
  `test_password_flag_takes_precedence_over_env`.
- `docs/CURRENT_STATE.md`
  Added ClickHouse auth propagation fix bullet; updated next-step guidance to
  include the password export requirement.
- `docs/dev_logs/2026-03-18_clickhouse_auth_propagation_fix.md`
  This file.

---

## Tests

```
python -m pytest tests/test_close_benchmark_v1.py tests/test_batch_silver.py -v --tb=short
```

Result: **76 passed** in 4.82 s.

---

## Credential Resolution After Fix

Priority order for the ClickHouse password (both CLIs):

1. `--clickhouse-password PASSWORD` CLI flag
2. `CLICKHOUSE_PASSWORD` environment variable
3. → fail-fast with rc=1 and actionable error message (no silent fallback)

Credential forwarding path (unchanged, now correctly populated):

```
close_benchmark_v1.main()
  └─ run_closure(clickhouse_password=<resolved>)
       └─ run_silver_gap_fill_stage(clickhouse_password=<resolved>)
            ├─ fetch_price_2min.main(["--clickhouse-password", <resolved>, ...])
            └─ run_batch_from_targets(clickhouse_password=<resolved>)
                 └─ ReconstructConfig(clickhouse_password=<resolved>)
                      └─ SilverReconstructor(config).reconstruct(...)
```

---

## Operator Command After Fix

Before running `close-benchmark-v1`, export the real password:

```bash
export CLICKHOUSE_PASSWORD=<your_real_password>
docker compose up -d
python -m polytool close-benchmark-v1 --skip-new-market \
    --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" \
    --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
```

Or pass the flag directly:

```bash
python -m polytool close-benchmark-v1 --skip-new-market \
    --clickhouse-password <your_real_password> \
    --pmxt-root "D:\Coding Projects\Polymarket\PolyToolData\raw\pmxt_archive" \
    --jon-root "D:\Coding Projects\Polymarket\PolyToolData\raw\jon_becker"
```

---

## Final Result

- Root cause identified and fixed: **Yes**
- Tests pass: **76 / 76**
- `AUTHENTICATION_FAILED` path eliminated: **Yes** (fail-fast replaces silent bad-default)
- Credential forwarding path verified end-to-end: **Yes** (unchanged; only resolution source fixed)
- `benchmark_v1` closure unblocked at the auth layer: **Yes**
- Remaining blocker: Docker must be healthy and `CLICKHOUSE_PASSWORD` must be
  exported before the next live run attempt.
