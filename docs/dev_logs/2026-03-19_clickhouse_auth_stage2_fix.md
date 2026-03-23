# Dev Log: ClickHouse Auth Stage 2 Fix (2026-03-19)

## Problem

After the 2026-03-18 auth propagation patch, a live run of
`python -m polytool close-benchmark-v1 --skip-new-market ...` still produced:

```
fetch-price-2min [LIVE]: 38 token(s) -> polytool.price_2min
  [ERROR] <token>: ClickHouse code 516 AUTHENTICATION_FAILED for user 'polytool_admin'
  ...
Total: N rows fetched, 0 inserted, 0 skipped
```

All 38 tokens failed with HTTP 516. The 2026-03-18 patch had added fail-fast
guards to `close_benchmark_v1.main()` and `batch_reconstruct_silver.main()`,
but missed `fetch_price_2min.main()`.

## Root Cause (multi-part)

### 1. Remaining `"polytool_admin"` fallback in `fetch_price_2min.py`

`tools/cli/fetch_price_2min.py` line 144 (before fix):

```python
ch_password = args.clickhouse_password
if ch_password is None:
    ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")
```

When `close_benchmark_v1` calls `_fetch_price_2min_main(argv)` in Stage 2,
it does pass `--clickhouse-password <password>` in `argv`. However, if the
password resolved in `close_benchmark_v1.main()` happened to be an empty
string (e.g., because `CLICKHOUSE_PASSWORD=""` was exported), `argv` contains
`["--clickhouse-password", ""]`, `args.clickhouse_password = ""`, the
`is None` check is False, and `ch_password = ""` propagates to ClickHouse
causing a 516.

More directly: if the operator forgot to export `CLICKHOUSE_PASSWORD` and
also did not pass `--clickhouse-password`, `close_benchmark_v1.main()`'s own
fail-fast would have caught it. But the `"polytool_admin"` fallback made
`fetch_price_2min` its own failure point — it would silently use
`"polytool_admin"` as the password even when called standalone.

### 2. Empty-string password bypass in all three `main()` guards

The 2026-03-18 guards in `close_benchmark_v1.main()` and
`batch_reconstruct_silver.main()` both checked `if ch_password is None` but
not `if not ch_password`. This means `CLICKHOUSE_PASSWORD=""` passed silently
through the guard with an empty string, then propagated to ClickHouse → 516.

## Fix

### `tools/cli/fetch_price_2min.py`

Replaced the silent `"polytool_admin"` fallback with a fail-fast guard:

```python
# BEFORE:
ch_password = args.clickhouse_password
if ch_password is None:
    ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "polytool_admin")

# AFTER:
ch_password = args.clickhouse_password
if ch_password is None:
    ch_password = os.environ.get("CLICKHOUSE_PASSWORD")
if not ch_password:
    print(
        "Error: ClickHouse password not set.\n"
        "  Pass --clickhouse-password PASSWORD, or export CLICKHOUSE_PASSWORD=<password>.",
        file=sys.stderr,
    )
    return 1
```

### `tools/cli/close_benchmark_v1.py` and `tools/cli/batch_reconstruct_silver.py`

Strengthened the existing `None`-only guard to also catch empty string:

```python
# BEFORE:
if ch_password is None:
    print("Error: ClickHouse password not set...", file=sys.stderr)
    return 1

# AFTER:
if not ch_password:
    print("Error: ClickHouse password not set...", file=sys.stderr)
    return 1
```

## Tests Added

### `tests/test_fetch_price_2min.py` — `TestFetchPrice2MinAuthFailFast` (4 tests)

- `test_no_password_arg_no_env_returns_1` — no `--clickhouse-password` and
  no env → rc=1 with "password" in stderr
- `test_empty_env_password_returns_1` — `CLICKHOUSE_PASSWORD=""` → rc=1
- `test_explicit_password_arg_accepted` — `--clickhouse-password secret` →
  engine called, rc=0
- `test_env_password_accepted` — `CLICKHOUSE_PASSWORD=secret` → rc=0

### `tests/test_close_benchmark_v1.py` — `TestCLISmoke` (1 test)

- `test_empty_string_password_returns_1` — `CLICKHOUSE_PASSWORD=""` → rc=1

### `tests/test_batch_silver.py` — `TestBatchCLI` (1 test)

- `test_empty_string_password_returns_1` — `CLICKHOUSE_PASSWORD=""` → rc=1

### Existing tests updated (5 in `TestFetchPrice2MinCLI`)

The old `TestFetchPrice2MinCLI` tests called `main()` without a password
(previously they got a free pass via the `"polytool_admin"` fallback). All
five were updated to pass `--clickhouse-password testpass` so they test the
intended engine behavior, not the auth check.

## Test Results

```
113 passed in 5.00s
```

All 113 tests across the three affected files pass with no regressions.

## Next Step

From a real-user shell with Docker running:

```bash
export CLICKHOUSE_PASSWORD=<real_password>
docker compose up -d
python -m polytool close-benchmark-v1 \
  --skip-new-market \
  --pmxt-root /path/to/pmxt_archive \
  --jon-root  /path/to/jon_becker \
  --clickhouse-password "$CLICKHOUSE_PASSWORD" \
  --out artifacts/benchmark_closure/$(date +%Y-%m-%d)/run.json
```

`fetch-price-2min` will no longer silently use `polytool_admin` as the
password. Any auth error will now surface as a clear exit-code-1 message
before any ClickHouse writes are attempted.
