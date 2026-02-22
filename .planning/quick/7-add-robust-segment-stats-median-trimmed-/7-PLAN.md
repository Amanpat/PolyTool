---
phase: quick-7
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - polytool/reports/coverage.py
  - tools/cli/batch_run.py
  - tests/test_coverage_report.py
  - tests/test_batch_run.py
  - docs/features/FEATURE-robust-signal-stats.md
autonomous: true

must_haves:
  truths:
    - "Each finalized segment bucket contains median_clv_pct, trimmed_mean_clv_pct (10% trim, count-based), p25_clv_pct, p75_clv_pct with explicit count_used fields"
    - "Same four robust stats exist for entry_drift_pct in every finalized segment bucket"
    - "segment_analysis.json output from build_coverage_report contains the new fields in each bucket"
    - "Leaderboard markdown Top Segment Detail shows median_clv_pct and trimmed_mean_clv_pct next to avg_clv_pct"
    - "Value lists are capped at MAX_ROBUST_VALUES (500) using deterministic selection (index % cap) to guarantee memory safety"
    - "No existing metric semantics are changed (avg_clv_pct, notional_weighted_* are untouched)"
    - "All new tests pass; existing tests are unbroken"
  artifacts:
    - path: "polytool/reports/coverage.py"
      provides: "Robust stats accumulation and finalization"
      contains: "median_clv_pct"
    - path: "tools/cli/batch_run.py"
      provides: "Leaderboard markdown rendering of robust stats"
      contains: "median_clv_pct"
    - path: "tests/test_coverage_report.py"
      provides: "Unit tests for median, trimmed mean, IQR, deterministic ordering"
    - path: "tests/test_batch_run.py"
      provides: "Leaderboard markdown includes robust stats in detail section"
    - path: "docs/features/FEATURE-robust-signal-stats.md"
      provides: "Feature documentation"
  key_links:
    - from: "_empty_segment_bucket()"
      to: "_accumulate_segment_bucket()"
      via: "_clv_pct_values and _entry_drift_pct_values lists (capped)"
    - from: "_accumulate_segment_bucket()"
      to: "_finalize_segment_bucket()"
      via: "_compute_robust_stats() called on each value list"
    - from: "_finalize_segment_bucket()"
      to: "segment_analysis.json"
      via: "returned dict includes new robust stat fields"
    - from: "hypothesis_candidates metrics dict"
      to: "_build_markdown() in batch_run.py"
      via: "median_clv_pct and trimmed_mean_clv_pct surfaced in Top Segment Detail"
---

<objective>
Add robust distributional stats (median, trimmed mean, IQR percentiles) for clv_pct and entry_drift_pct to segment buckets. Expose them in segment_analysis.json and the batch-run leaderboard markdown.

Purpose: avg_clv_pct is sensitive to outliers. Median and trimmed mean give analysts a more robust signal. IQR (p25/p75) shows spread. These complement, not replace, existing mean metrics.
Output: New fields in every finalized segment bucket + leaderboard markdown detail section updated.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@polytool/reports/coverage.py
@tools/cli/batch_run.py
@tests/test_coverage_report.py
@tests/test_batch_run.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add robust stats accumulation and finalization in coverage.py</name>
  <files>polytool/reports/coverage.py</files>
  <action>
**Step 1 — Add constant at module level (near TOP_SEGMENT_MIN_COUNT):**
```python
MAX_ROBUST_VALUES = 500  # Memory cap for raw value lists used in robust stats
```

**Step 2 — Add `_compute_robust_stats(values)` function near `_compute_median`:**
```python
def _compute_robust_stats(values: List[float]) -> Dict[str, Any]:
    """Compute median, 10% trimmed mean (count-based), p25, p75 from a value list.

    Returns a dict with keys: median, trimmed_mean, p25, p75, count_used.
    All floats rounded to 6 decimal places. Returns all-None if list is empty.
    Trim removes floor(n * 0.10) values from each tail (count-based, symmetric).
    """
    if not values:
        return {"median": None, "trimmed_mean": None, "p25": None, "p75": None, "count_used": 0}
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    # Median
    mid = n // 2
    if n % 2 == 1:
        median = round(sorted_vals[mid], 6)
    else:
        median = round((sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0, 6)
    # 10% trimmed mean (count-based symmetric trim)
    trim_k = math.floor(n * 0.10)
    trimmed = sorted_vals[trim_k: n - trim_k] if trim_k > 0 else sorted_vals
    trimmed_mean = round(sum(trimmed) / len(trimmed), 6) if trimmed else None
    # p25 and p75 (nearest-rank, 1-indexed)
    p25_idx = max(0, math.ceil(n * 0.25) - 1)
    p75_idx = max(0, math.ceil(n * 0.75) - 1)
    p25 = round(sorted_vals[p25_idx], 6)
    p75 = round(sorted_vals[p75_idx], 6)
    return {
        "median": median,
        "trimmed_mean": trimmed_mean,
        "p25": p25,
        "p75": p75,
        "count_used": n,
    }
```

**Step 3 — In `_empty_segment_bucket()`**, add two new raw value list fields alongside `_minutes_to_close_values`:
```python
"_clv_pct_values": [],           # raw list for robust stats; capped, not emitted
"_entry_drift_pct_values": [],   # raw list for robust stats; capped, not emitted
```

**Step 4 — In `_accumulate_segment_bucket()`**, after the existing `clv_pct_sum` accumulation block, append to the capped list. Use deterministic index-based cap: only append if `len(list) < MAX_ROBUST_VALUES` OR replace at index `len(list) % MAX_ROBUST_VALUES` (use the simpler "only append if under cap" approach — no replacement needed, just cap to first MAX_ROBUST_VALUES values; note in docstring that values are first-arrival-ordered which is deterministic given consistent input ordering):

After `bucket["clv_pct_count"] += 1`:
```python
        if len(bucket["_clv_pct_values"]) < MAX_ROBUST_VALUES:
            bucket["_clv_pct_values"].append(clv_pct)
```

After `bucket["entry_drift_pct_count"] += 1`:
```python
        if len(bucket["_entry_drift_pct_values"]) < MAX_ROBUST_VALUES:
            bucket["_entry_drift_pct_values"].append(entry_drift_pct)
```

**Step 5 — In `_finalize_segment_bucket()`**, after the existing `median_minutes_to_close` computation, add:
```python
    # Robust stats for CLV
    clv_robust = _compute_robust_stats(list(bucket.get("_clv_pct_values") or []))
    # Robust stats for entry drift
    entry_drift_robust = _compute_robust_stats(list(bucket.get("_entry_drift_pct_values") or []))
```

**Step 6 — In the returned dict from `_finalize_segment_bucket()`**, add new fields after the `avg_clv_pct_count_used` entry and after the `avg_entry_drift_pct_count_used` entry:

After `"avg_clv_pct_count_used": clv_pct_count,`:
```python
        "median_clv_pct": clv_robust["median"],
        "trimmed_mean_clv_pct": clv_robust["trimmed_mean"],
        "p25_clv_pct": clv_robust["p25"],
        "p75_clv_pct": clv_robust["p75"],
        "robust_clv_pct_count_used": clv_robust["count_used"],
```

After `"avg_entry_drift_pct_count_used": entry_drift_pct_count,`:
```python
        "median_entry_drift_pct": entry_drift_robust["median"],
        "trimmed_mean_entry_drift_pct": entry_drift_robust["trimmed_mean"],
        "p25_entry_drift_pct": entry_drift_robust["p25"],
        "p75_entry_drift_pct": entry_drift_robust["p75"],
        "robust_entry_drift_pct_count_used": entry_drift_robust["count_used"],
```

**Note:** The `_clv_pct_values` and `_entry_drift_pct_values` private keys (prefixed with `_`) are already filtered out in the same way as `_minutes_to_close_values` — they are not emitted in finalized output because `_finalize_segment_bucket` builds the output dict explicitly with only the fields listed. No additional stripping needed.

Also propagate the new fields through `_build_hypothesis_candidates` metrics dict (in `metrics_out`): add after `"avg_clv_pct_count_used"`:
```python
            "median_clv_pct": _safe_float(m.get("median_clv_pct")),
            "trimmed_mean_clv_pct": _safe_float(m.get("trimmed_mean_clv_pct")),
            "p25_clv_pct": _safe_float(m.get("p25_clv_pct")),
            "p75_clv_pct": _safe_float(m.get("p75_clv_pct")),
            "robust_clv_pct_count_used": _coerce_int(m.get("robust_clv_pct_count_used")),
            "median_entry_drift_pct": _safe_float(m.get("median_entry_drift_pct")),
            "trimmed_mean_entry_drift_pct": _safe_float(m.get("trimmed_mean_entry_drift_pct")),
            "p25_entry_drift_pct": _safe_float(m.get("p25_entry_drift_pct")),
            "p75_entry_drift_pct": _safe_float(m.get("p75_entry_drift_pct")),
            "robust_entry_drift_pct_count_used": _coerce_int(m.get("robust_entry_drift_pct_count_used")),
```
  </action>
  <verify>
```bash
cd "D:/Coding Projects/Polymarket/PolyTool" && python -c "
from polytool.reports.coverage import _compute_robust_stats, _empty_segment_bucket, _finalize_segment_bucket
# Test _compute_robust_stats
r = _compute_robust_stats([1.0, 2.0, 3.0, 4.0, 5.0])
assert r['median'] == 3.0, r
assert r['p25'] == 2.0, r
assert r['p75'] == 4.0, r
# Empty bucket should finalize without error
b = _empty_segment_bucket()
f = _finalize_segment_bucket(b)
assert 'median_clv_pct' in f, list(f.keys())
assert 'median_entry_drift_pct' in f, list(f.keys())
print('OK')
"
```
  </verify>
  <done>
`_compute_robust_stats` exists and returns correct median/trimmed_mean/p25/p75/count_used. Every finalized segment bucket contains `median_clv_pct`, `trimmed_mean_clv_pct`, `p25_clv_pct`, `p75_clv_pct`, `robust_clv_pct_count_used` and the equivalent `*_entry_drift_pct` fields. Hypothesis candidate metrics dict propagates these fields.
  </done>
</task>

<task type="auto">
  <name>Task 2: Expose robust stats in leaderboard markdown and write tests + feature doc</name>
  <files>
    tools/cli/batch_run.py
    tests/test_coverage_report.py
    tests/test_batch_run.py
    docs/features/FEATURE-robust-signal-stats.md
  </files>
  <action>
**A. batch_run.py — Top Segment Detail section**

In `_build_markdown()`, inside the `for idx, segment_key in enumerate(top_detail_keys, ...)` loop, after the existing `notional_weighted_avg_clv_pct` line, add:

```python
        # Pull robust CLV stats from the first notional example's metrics
        first_notional_metrics = next(
            (
                ex.get("metrics") or {}
                for ex in row.get("examples", [])
                if str(ex.get("weighting") or "") == "notional"
            ),
            {},
        )
        median_clv = _to_float(first_notional_metrics.get("median_clv_pct"))
        trimmed_clv = _to_float(first_notional_metrics.get("trimmed_mean_clv_pct"))
        robust_count = _to_int(first_notional_metrics.get("robust_clv_pct_count_used"))
        if median_clv is not None or trimmed_clv is not None:
            lines.append(
                f"- median_clv_pct: {_fmt_number(median_clv)} | "
                f"trimmed_mean_clv_pct: {_fmt_number(trimmed_clv)} "
                f"(robust_count_used={robust_count})"
            )
```

Place this block after the `notional_weighted_avg_clv_pct` bullet, before the `notional_weighted_beat_close_rate` bullet.

**B. tests/test_coverage_report.py — New test class**

Add a new test class `TestRobustStats` (import `_compute_robust_stats` and `MAX_ROBUST_VALUES` from `polytool.reports.coverage`):

```python
class TestRobustStats:
    def test_median_odd(self):
        r = _compute_robust_stats([3.0, 1.0, 2.0])
        assert r["median"] == 2.0
        assert r["count_used"] == 3

    def test_median_even(self):
        r = _compute_robust_stats([1.0, 2.0, 3.0, 4.0])
        assert r["median"] == 2.5

    def test_trimmed_mean_10pct(self):
        # 10 values: trim floor(10*0.10)=1 from each tail -> 8 values used
        vals = [float(i) for i in range(1, 11)]  # [1..10]
        r = _compute_robust_stats(vals)
        # trimmed slice: [2,3,4,5,6,7,8,9] -> mean = 5.5
        assert r["trimmed_mean"] == 5.5

    def test_trimmed_mean_small_no_trim(self):
        # 5 values: floor(5*0.10)=0 -> no trim, mean = all values
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = _compute_robust_stats(vals)
        assert r["trimmed_mean"] == 3.0

    def test_iqr(self):
        vals = [1.0, 2.0, 3.0, 4.0, 5.0]
        r = _compute_robust_stats(vals)
        # p25: ceil(5*0.25)-1 = ceil(1.25)-1 = 2-1 = 1 -> sorted_vals[1] = 2.0
        assert r["p25"] == 2.0
        # p75: ceil(5*0.75)-1 = ceil(3.75)-1 = 4-1 = 3 -> sorted_vals[3] = 4.0
        assert r["p75"] == 4.0

    def test_single_value(self):
        r = _compute_robust_stats([7.5])
        assert r["median"] == 7.5
        assert r["trimmed_mean"] == 7.5
        assert r["p25"] == 7.5
        assert r["p75"] == 7.5

    def test_empty(self):
        r = _compute_robust_stats([])
        assert r["median"] is None
        assert r["trimmed_mean"] is None
        assert r["count_used"] == 0

    def test_cap_deterministic(self):
        # Accumulating MAX_ROBUST_VALUES+10 values should cap at MAX_ROBUST_VALUES
        from polytool.reports.coverage import _accumulate_segment_bucket, _empty_segment_bucket, MAX_ROBUST_VALUES
        b = _empty_segment_bucket()
        for i in range(MAX_ROBUST_VALUES + 10):
            _accumulate_segment_bucket(
                b,
                outcome="WIN",
                pnl_net=0.0,
                pnl_gross=0.0,
                clv_pct=float(i),
            )
        assert len(b["_clv_pct_values"]) == MAX_ROBUST_VALUES

    def test_finalized_bucket_has_robust_fields(self):
        from polytool.reports.coverage import _accumulate_segment_bucket, _empty_segment_bucket, _finalize_segment_bucket
        b = _empty_segment_bucket()
        for v in [0.1, 0.2, 0.3]:
            _accumulate_segment_bucket(b, "WIN", 0.0, 0.0, clv_pct=v, entry_drift_pct=v * 0.5)
        f = _finalize_segment_bucket(b)
        for field in ["median_clv_pct", "trimmed_mean_clv_pct", "p25_clv_pct", "p75_clv_pct",
                      "robust_clv_pct_count_used", "median_entry_drift_pct",
                      "trimmed_mean_entry_drift_pct", "robust_entry_drift_pct_count_used"]:
            assert field in f, f"Missing: {field}"
        assert f["robust_clv_pct_count_used"] == 3
        assert f["median_clv_pct"] == 0.2

    def test_deterministic_output_ordering(self):
        # Same values appended in same order => same robust stats across two identical runs
        from polytool.reports.coverage import _accumulate_segment_bucket, _empty_segment_bucket, _finalize_segment_bucket
        vals = [0.05, -0.1, 0.3, 0.0, 0.15]
        def _make():
            b = _empty_segment_bucket()
            for v in vals:
                _accumulate_segment_bucket(b, "WIN", 0.0, 0.0, clv_pct=v)
            return _finalize_segment_bucket(b)
        f1 = _make()
        f2 = _make()
        assert f1["median_clv_pct"] == f2["median_clv_pct"]
        assert f1["trimmed_mean_clv_pct"] == f2["trimmed_mean_clv_pct"]
```

Update the import at the top of the test file to also import `_compute_robust_stats` and `MAX_ROBUST_VALUES` from `polytool.reports.coverage`.

**C. tests/test_batch_run.py — Add markdown rendering test**

Add a test that builds a minimal leaderboard dict with a segment that has `median_clv_pct` and `trimmed_mean_clv_pct` in its example metrics, calls `_build_markdown`, and asserts those values appear in the output. Import `_build_markdown` from `tools.cli.batch_run`.

```python
from tools.cli.batch_run import _build_markdown

def test_build_markdown_includes_robust_clv_stats():
    example_metrics = {
        "count": 10,
        "avg_clv_pct": 0.05,
        "avg_clv_pct_count_used": 10,
        "notional_weighted_avg_clv_pct": 0.06,
        "notional_weighted_avg_clv_pct_weight_used": 500.0,
        "notional_weighted_beat_close_rate": 0.6,
        "notional_weighted_beat_close_rate_weight_used": 500.0,
        "beat_close_rate": 0.6,
        "beat_close_rate_count_used": 10,
        "median_clv_pct": 0.04,
        "trimmed_mean_clv_pct": 0.045,
        "robust_clv_pct_count_used": 10,
    }
    leaderboard = {
        "batch_id": "test-batch",
        "created_at": "2026-02-20T18:00:00+00:00",
        "users_attempted": 1,
        "users_succeeded": 1,
        "users_failed": 0,
        "segments": [
            {
                "segment_key": "sport:basketball",
                "users_with_segment": 1,
                "total_count": 10,
                "total_notional_weight_used": 500.0,
                "scores": {
                    "notional_weighted_avg_clv_pct": {"value": 0.06, "users_used": 1, "weight_used": 500.0},
                    "notional_weighted_beat_close_rate": {"value": 0.6, "users_used": 1, "weight_used": 500.0},
                    "count_weighted_avg_clv_pct": {"value": 0.05, "users_used": 1, "count_used": 10},
                    "count_weighted_beat_close_rate": {"value": 0.6, "users_used": 1, "count_used": 10},
                },
                "examples": [
                    {
                        "user": "alice",
                        "rank": 1,
                        "weighting": "notional",
                        "metrics": example_metrics,
                        "denominators": {"weight_used": 500.0, "weighting": "notional"},
                    }
                ],
            }
        ],
        "top_lists": {
            "top_by_notional_weighted_avg_clv_pct": ["sport:basketball"],
            "top_by_notional_weighted_beat_close_rate": [],
            "top_by_persistence_users": [],
        },
        "per_user": [],
    }
    md = _build_markdown(leaderboard)
    assert "median_clv_pct" in md
    assert "trimmed_mean_clv_pct" in md
    assert "0.040000" in md  # median value formatted
```

**D. docs/features/FEATURE-robust-signal-stats.md**

Create this file with the following content:

```markdown
# Feature: Robust Segment Stats (Median, Trimmed Mean, IQR)

## Status
Implemented — Quick-007 (2026-02-20)

## Motivation
`avg_clv_pct` and `avg_entry_drift_pct` are sensitive to outliers. Large positive or negative positions can skew the mean, making a segment look stronger or weaker than it actually is. Median and trimmed mean provide more robust central-tendency estimates.

## What Was Added

### New fields per segment bucket (in `segment_analysis.json`)

For each dimension bucket (by_league, by_sport, by_market_type, by_entry_price_tier, by_category, by_market_slug):

| Field | Description |
| --- | --- |
| `median_clv_pct` | Median of raw clv_pct values in the bucket |
| `trimmed_mean_clv_pct` | 10% symmetric trimmed mean (count-based: removes floor(n*0.10) from each tail) |
| `p25_clv_pct` | 25th percentile (nearest-rank) |
| `p75_clv_pct` | 75th percentile (nearest-rank) |
| `robust_clv_pct_count_used` | Number of values used (capped at MAX_ROBUST_VALUES=500) |
| `median_entry_drift_pct` | Median of raw entry_drift_pct values |
| `trimmed_mean_entry_drift_pct` | 10% symmetric trimmed mean for entry drift |
| `p25_entry_drift_pct` | 25th percentile |
| `p75_entry_drift_pct` | 75th percentile |
| `robust_entry_drift_pct_count_used` | Number of values used |

### Leaderboard Markdown
The `## Top Segment Detail` section now shows `median_clv_pct` and `trimmed_mean_clv_pct` alongside `avg_clv_pct` when available.

## Implementation Notes
- **No new dependencies**: stdlib `math`, `statistics` not used — manual sort-based computation.
- **Memory safety**: Raw value lists are capped at `MAX_ROBUST_VALUES = 500`. Values are collected in arrival order (deterministic given consistent position ordering from scan output).
- **Trim definition**: 10% count-based symmetric trim removes `floor(n * 0.10)` values from each tail. With n < 10 items, trim_k = 0 (no trim, equivalent to mean).
- **Percentile definition**: Nearest-rank method: `sorted_vals[ceil(n * p) - 1]` (0-indexed).
- **Existing metrics untouched**: `avg_clv_pct`, `notional_weighted_avg_clv_pct`, and all other existing fields are unchanged.

## Files Changed
- `polytool/reports/coverage.py`: `_compute_robust_stats()`, `_empty_segment_bucket()`, `_accumulate_segment_bucket()`, `_finalize_segment_bucket()`, `_build_hypothesis_candidates()`
- `tools/cli/batch_run.py`: `_build_markdown()` Top Segment Detail section
- `tests/test_coverage_report.py`: `TestRobustStats` class (9 tests)
- `tests/test_batch_run.py`: `test_build_markdown_includes_robust_clv_stats`
```
  </action>
  <verify>
```bash
cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_coverage_report.py tests/test_batch_run.py -v --tb=short 2>&1 | tail -30
```
  </verify>
  <done>
All tests pass (including the new TestRobustStats class and test_build_markdown_includes_robust_clv_stats). Leaderboard markdown for a segment with robust stats contains "median_clv_pct" and "trimmed_mean_clv_pct" lines in the Top Segment Detail section. FEATURE-robust-signal-stats.md exists at docs/features/.
  </done>
</task>

</tasks>

<verification>
```bash
cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```
All existing tests remain green. New robust stats tests pass. No import errors.
</verification>

<success_criteria>
- `_compute_robust_stats` correctly computes median, trimmed mean (10% count-based), p25, p75 for any non-empty list
- Every finalized segment bucket in `segment_analysis.json` contains 10 new fields (5 per metric)
- Value lists are capped at 500; list length never exceeds MAX_ROBUST_VALUES
- Leaderboard markdown Top Segment Detail section shows median_clv_pct + trimmed_mean_clv_pct when non-None
- No existing metric semantics changed (avg_clv_pct etc. are identical before and after)
- pytest passes with zero failures
</success_criteria>

<output>
After completion, create `.planning/quick/7-add-robust-segment-stats-median-trimmed-/7-SUMMARY.md`
</output>
