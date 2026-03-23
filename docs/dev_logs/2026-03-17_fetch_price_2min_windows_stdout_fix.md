# Dev Log: fetch-price-2min Windows stdout encoding fix

**Date:** 2026-03-17
**Branch:** `phase-1`
**Objective:** Fix the `UnicodeEncodeError` that caused `fetch-price-2min` to crash
on Windows cp1252 terminals before producing any ingest artifact, blocking
`benchmark_v1` closure.

---

## Root Cause Confirmed

The live operator attempt on 2026-03-17 produced the following traceback
(from `artifacts/benchmark_closure/2026-03-17/live_attempt_20260317_204109/13_fetch_price_2min.stderr.txt`):

```
UnicodeEncodeError: 'charmap' codec can't encode character '\u2192' in position 37:
character maps to <undefined>
```

Traceback path:
- `polytool/__main__.py` -> `tools/cli/fetch_price_2min.py`, line 157, in `main()`
- Python encoding layer: `encodings/cp1252.py`

The exact line (before fix):

```python
print(
    f"fetch-price-2min [{mode_label}]: {len(token_ids)} token(s) → polytool.price_2min",
    flush=True,
)
```

The Unicode RIGHT ARROW `→` (U+2192) is absent from the cp1252 code page, so
any Windows terminal configured as cp1252 (the Windows default) raises
`UnicodeEncodeError` immediately when this line executes — before the engine
runs, before any ingest, before the run artifact is written.

No other non-cp1252 characters were found in the direct output paths of
`fetch_price_2min.py`. The `close_benchmark_v1.py` bullet `•` (U+2022) is
encoded as cp1252 byte 0x95 and is safe.

---

## Files Changed

### `tools/cli/fetch_price_2min.py` — line 158

**Why:** The header print contained `→` (U+2192), which is not in cp1252.

**What was normalized:**
- `→` (Unicode RIGHT ARROW U+2192) replaced with `->` (two ASCII characters)

Before:
```python
f"fetch-price-2min [{mode_label}]: {len(token_ids)} token(s) → polytool.price_2min"
```

After:
```python
f"fetch-price-2min [{mode_label}]: {len(token_ids)} token(s) -> polytool.price_2min"
```

### `tests/test_fetch_price_2min.py` — new test `test_stdout_encodable_as_cp1252`

**Why:** Regression guard. Captures stdout from a dry-run CLI invocation and
asserts it can be encoded as cp1252 without raising. This catches any future
reintroduction of non-cp1252 characters in the CLI output path.

---

## Commands Run + Output

Regression tests run:

```
python -m pytest tests/test_fetch_price_2min.py -v --tb=short
```

Output:
```
31 passed in 0.30s
```

All 30 pre-existing tests pass; the new `test_stdout_encodable_as_cp1252` test
passes (confirming the fix eliminates the cp1252-hostile character).

---

## Exact Next Manual Command to Resume Benchmark Closure

With the fix in place, resume from step 3 of the runbook
(`docs/runbooks/BENCHMARK_CLOSURE_RUNBOOK.md`):

```powershell
# Step 3 — fetch price_2min for the 39 priority-1 tokens
python -m polytool fetch-price-2min `
    --token-file config/benchmark_v1_priority1_tokens.txt `
    --clickhouse-host localhost `
    --clickhouse-user polytool_admin `
    --clickhouse-password <from .env>
```

Prerequisites (already confirmed from the 2026-03-17 live attempt):
- Docker: `polytool-clickhouse` healthy on `localhost:8123`
- Token file: `config/benchmark_v1_priority1_tokens.txt` exists (39 tokens)
- Branch: `phase-1`

On success this produces `price_2min` rows for the 39 priority-1 tokens and
the run exits 0. Proceed to step 4 (`batch-reconstruct-silver`) from there.
