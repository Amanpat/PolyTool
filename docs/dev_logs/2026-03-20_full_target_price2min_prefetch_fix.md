# Full-Target price_2min Prefetch Fix

## Files changed and why

- `tools/cli/close_benchmark_v1.py`
  - Added `_all_unique_token_ids()` helper (order-preserving dedup via `dict.fromkeys`).
  - Changed `run_silver_gap_fill_stage()` to use `all_token_ids` (all 120 targets) instead
    of `priority1_ids` (39 targets) when building the `fetch-price-2min` argv.
  - Added `priority1_count` field to `fetch_outcome` artifact for traceability alongside
    the expanded `token_count`.
  - Added operator print: `[fetch-price-2min] prefetching price_2min for N unique token
    IDs (M targets)`.
- `tests/test_close_benchmark_v1.py`
  - Added `_all_unique_token_ids` to import block.
  - Updated 2 existing test assertions that previously checked `0xCCC333` (priority-2
    fixture token) was NOT in the fetch argv / planned_tokens — flipped to assert it IS
    included.
  - Added 5 new helper tests in `TestHelpers`:
    `test_all_unique_token_ids_includes_all_priorities`,
    `test_all_unique_token_ids_deduplicates`,
    `test_all_unique_token_ids_empty_list`,
    `test_all_unique_token_ids_skips_malformed`,
    `test_all_unique_token_ids_returns_more_than_priority1`.
  - Added 5 new regression tests in `TestFullTargetPricePrefetch`:
    `test_fetch_argv_includes_overflow_token`,
    `test_fetch_outcome_token_count_reflects_all_targets`,
    `test_dry_run_planned_tokens_includes_overflow`,
    `test_deduplication_when_token_appears_in_multiple_buckets`,
    `test_old_priority1_only_behavior_no_longer_present`.
- `docs/CURRENT_STATE.md`
  - Updated benchmark closure orchestrator section to note the prefetch scope fix.
  - Updated operator focus section to reflect all-target fetch.
- `docs/dev_logs/2026-03-20_full_target_price2min_prefetch_fix.md`
  - This log.

## Context

- Branch: `phase-1`
- Root cause identified from the 2026-03-20 full-manifest direct run
  (`artifacts/silver/manual_gap_fill_full_20260319_213841/`):
  `price_2min_missing=80` across 120 targets; only 40 targets had `confidence=low`
  (price_2min_only) while 80 were `confidence=none` (empty tape).
- The prior `--export-tokens` / live fetch on 2026-03-17 only populated ClickHouse for
  the priority-1 subset (38 unique token IDs from the 39-line export file). The 81
  overflow targets (priority≥2) never had `price_2min` rows inserted, so the Silver
  reconstructor found no rows and produced empty tapes.

## Root cause

`run_silver_gap_fill_stage()` in `close_benchmark_v1.py` called:

```python
priority1_ids = _priority1_token_ids(targets)
# ... built fetch-price-2min argv from priority1_ids only
```

`_priority1_token_ids()` returns only entries where `priority == 1`. With 120 targets
total (9+11+10+9 priority-1 = 39, the rest priority-2 overflow), only 39 tokens were
passed to `fetch-price-2min`. The Silver reconstructor queries ClickHouse inline at
reconstruction time for each token; if no rows exist, it logs `price_2min_missing` and
the tape degrades to `confidence=none`.

## Fix

Added `_all_unique_token_ids()`:

```python
def _all_unique_token_ids(targets: List[dict]) -> List[str]:
    """Return deduplicated token IDs from ALL targets (all priorities).

    Preserves first-seen order via dict.fromkeys.  Used so that
    fetch-price-2min covers every gap-fill target, not just priority-1.
    """
    return list(dict.fromkeys(
        t["token_id"]
        for t in targets
        if isinstance(t, dict) and t.get("token_id")
    ))
```

Changed `run_silver_gap_fill_stage()` to call `_all_unique_token_ids(targets)` for the
`fetch-price-2min` argv. `priority1_ids` is still computed (and stored in
`fetch_outcome["priority1_count"]`) for artifact traceability.

Note on deduplication: two slugs in the full manifest appear in more than one bucket
(`claudia-sheinbaum-out-as-president-of-mexico-by-june-30-791` in politics + sports;
`brian-armstrong-out-as-coinbase-ceo-before-2027` in sports + crypto). `dict.fromkeys`
ensures each token_id appears in the argv exactly once.

## Test results

Targeted test files:

```
python -m pytest tests/test_close_benchmark_v1.py tests/test_batch_silver.py tests/test_fetch_price_2min.py -v --tb=short -q
```

- `test_close_benchmark_v1.py`: 40 passed, 0 failed
- `test_benchmark_closure_operator.py`: 17 passed, 0 failed (57 total across both closure files)
- `test_batch_silver.py`: all pass (no regressions)
- `test_fetch_price_2min.py`: all pass (no regressions)

Full suite (excluding pre-existing failures in unrelated test files):

- 2262+ tests pass, 0 new failures introduced

Pre-existing failures (not caused by this change, confirmed by stash-and-retest):
- `tests/test_batch_silver_gap_fill.py` — import errors from unrelated fixture gap
- `tests/test_gate2_eligible_tape_acquisition.py` — pre-existing
- `tests/test_new_market_capture.py` — pre-existing

## Expected impact on next live run

When `close-benchmark-v1` runs the Silver gap-fill stage next, `fetch-price-2min` will
be invoked with all unique token IDs from the full 120-target manifest (≈118 unique
after dedup). ClickHouse will be populated for all targets before reconstruction runs,
so overflow targets should no longer degrade to `confidence=none` due to missing
`price_2min` data. The real reconstruction confidence ceiling remains `low` (since pmxt
anchor and Jon-Becker fills are still absent in-window), but the `price_2min_missing=80`
problem is eliminated.
