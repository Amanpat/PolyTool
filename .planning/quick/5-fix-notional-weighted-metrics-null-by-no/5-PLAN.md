---
phase: quick-5
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/scan.py
  - tests/test_coverage_report.py
  - docs/features/FEATURE-hypothesis-ready-aggregations.md
autonomous: true

must_haves:
  truths:
    - "notional_weight_total_global > 0 for positions carrying total_cost"
    - "Top Segments populate in coverage_reconciliation_report.md"
    - "notional_weight_debug.json exists in run root and is in run_manifest output_paths"
  artifacts:
    - path: "tools/cli/scan.py"
      provides: "_normalize_position_notional / _build_notional_weight_debug helpers + invocation before build_coverage_report"
    - path: "tests/test_coverage_report.py"
      provides: "Two new tests: total_cost path and string coercion path"
    - path: "docs/features/FEATURE-hypothesis-ready-aggregations.md"
      provides: "Notional parity guarantee note"
  key_links:
    - from: "tools/cli/scan.py (_run_scan_pipeline)"
      to: "polytool/reports/coverage.py (build_coverage_report)"
      via: "positions list with position_notional_usd injected"
      pattern: "_normalize_position_notional.*position"
---

<objective>
Fix notional-weighted metrics being all-null (notional_weight_total_global=0, Top Segments None) by
injecting a canonical position_notional_usd onto each position dict before build_coverage_report is
called. Add notional_weight_debug.json to make the weight extraction transparent and auditable.

Purpose: coverage.py's extract_position_notional_usd already has the full fallback chain
(position_notional_usd -> total_cost -> size*entry_price), but the result is computed inside the
report loop and never written back. Positions from real dossiers carry total_cost, not
position_notional_usd — so the field is missing when a live scan reads them. Normalizing the field
onto each dict before the call ensures the value is present and the debug artifact can be written
from the same pass.

Output: modified scan.py with normalization + debug artifact, two new tests, one doc note.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@tools/cli/scan.py
@polytool/reports/coverage.py
@tests/test_coverage_report.py
@docs/features/FEATURE-hypothesis-ready-aggregations.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Inject position_notional_usd + emit notional_weight_debug.json in scan.py</name>
  <files>tools/cli/scan.py</files>
  <action>
Add two private helpers near the other parity-debug helpers (around the `_build_parity_debug` area,
roughly line 1452):

```python
def _normalize_position_notional(positions: list[dict[str, Any]]) -> None:
    """Inject canonical position_notional_usd onto every position dict in-place.

    Uses the same priority chain as coverage.extract_position_notional_usd:
      1. existing position_notional_usd (if positive finite float)
      2. total_cost (if positive finite float)
      3. size * entry_price (if both present and entry_price > 0)

    Positions that yield None from all three sources are left unchanged
    (position_notional_usd absent); the debug artifact records why.
    """
    from polytool.reports.coverage import extract_position_notional_usd
    for pos in positions:
        existing = pos.get("position_notional_usd")
        # Avoid overwriting a valid value already present
        try:
            ev = float(existing) if existing is not None else None
        except (TypeError, ValueError):
            ev = None
        if ev is not None and ev > 0:
            continue
        extracted = extract_position_notional_usd(pos)
        if extracted is not None:
            pos["position_notional_usd"] = extracted


def _build_notional_weight_debug(positions: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the notional_weight_debug.json payload from already-normalized positions."""
    import math

    WEIGHT_FIELDS = ("position_notional_usd", "total_cost", "size", "entry_price")
    total = len(positions)
    extracted_total = 0.0
    count_missing = 0
    missing_reasons: dict[str, int] = {}
    samples = []

    for pos in positions:
        pnu = pos.get("position_notional_usd")
        try:
            v = float(pnu) if pnu is not None else None
        except (TypeError, ValueError):
            v = None

        if v is not None and v > 0 and math.isfinite(v):
            extracted_total += v
        else:
            count_missing += 1
            # Classify reason
            has_tc = pos.get("total_cost") is not None
            has_size = pos.get("size") is not None
            has_ep = pos.get("entry_price") is not None
            if not has_tc and not has_size:
                reason = "NO_FIELDS"
            elif pnu is not None and v is None:
                reason = "NON_NUMERIC"
            elif v is not None and v <= 0:
                reason = "ZERO_OR_NEGATIVE"
            else:
                reason = "FALLBACK_FAILED"
            missing_reasons[reason] = missing_reasons.get(reason, 0) + 1

        if len(samples) < 10:
            sample_fields = {k: pos.get(k) for k in WEIGHT_FIELDS if pos.get(k) is not None}
            samples.append({
                "token_id": pos.get("token_id") or pos.get("resolved_token_id"),
                "market_slug": pos.get("market_slug"),
                "fields_present": list(sample_fields.keys()),
                "extracted_position_notional_usd": v if (v is not None and v > 0) else None,
            })

    top_missing = sorted(missing_reasons.items(), key=lambda x: -x[1])
    return {
        "total_positions": total,
        "extracted_weight_total": round(extracted_total, 6),
        "count_missing_weight": count_missing,
        "top_missing_reasons": [{"reason": r, "count": c} for r, c in top_missing],
        "samples": samples,
    }
```

Then in `_run_scan_pipeline` (the function that calls `build_coverage_report` around line 1296),
BEFORE the `build_coverage_report(...)` call, add:

```python
    # Normalize position_notional_usd so weighted metrics are non-null.
    _normalize_position_notional(positions)
    notional_debug = _build_notional_weight_debug(positions)
```

After `parity_debug_path.write_text(...)` (around line 1459), add:

```python
    notional_debug_path = output_dir / "notional_weight_debug.json"
    notional_debug_path.write_text(
        json.dumps(notional_debug, indent=2, sort_keys=True), encoding="utf-8"
    )
```

Then add `"notional_weight_debug_json": notional_debug_path.as_posix()` to both the
`output_paths` dict (around line 1483) and the `emitted` dict (around line 1527).

Do NOT modify polytool/reports/coverage.py — extract_position_notional_usd already has the correct
fallback chain. The fix is purely in scan.py so that the field is present before build_coverage_report
reads it.
  </action>
  <verify>
Run: `python -m pytest tests/test_scan_trust_artifacts.py -v --tb=short`
Check no import errors: `python -c "from tools.cli.scan import _normalize_position_notional, _build_notional_weight_debug"`
  </verify>
  <done>
_normalize_position_notional and _build_notional_weight_debug exist in scan.py, the normalization
call appears before build_coverage_report, notional_weight_debug.json path appears in output_paths
and emitted dicts.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add unit tests for notional normalization + string coercion</name>
  <files>tests/test_coverage_report.py</files>
  <action>
Add two test functions to the existing test file. Import `extract_position_notional_usd` is already
present. Add a new class or append to the end of the file:

```python
class TestExtractPositionNotionalUsd:
    """Unit tests for extract_position_notional_usd fallback chain."""

    def test_total_cost_used_when_no_explicit_notional(self):
        """Positions with total_cost but no position_notional_usd should yield a positive weight."""
        pos = {
            "token_id": "tok_tc_001",
            "total_cost": 47.50,
            "resolution_outcome": "WIN",
            "clv_pct": 0.12,
            "beat_close": True,
        }
        result = extract_position_notional_usd(pos)
        assert result == pytest.approx(47.50), (
            "Expected total_cost to be returned when position_notional_usd absent"
        )

    def test_string_total_cost_coerces_to_float(self):
        """total_cost stored as a numeric string should coerce cleanly; non-numeric should return None."""
        pos_numeric_str = {"total_cost": "25.00"}
        assert extract_position_notional_usd(pos_numeric_str) == pytest.approx(25.0)

        pos_bad_str = {"total_cost": "N/A"}
        assert extract_position_notional_usd(pos_bad_str) is None, (
            "Non-numeric string total_cost should return None, not raise"
        )


class TestNotionalWeightInCoverageReport:
    """Integration: build_coverage_report produces non-null notional metrics when total_cost present."""

    def _make_positions_with_total_cost(self):
        """Positions that have total_cost but NOT position_notional_usd."""
        base = [
            {
                "resolved_token_id": f"tok_{i:03d}",
                "resolution_outcome": "WIN",
                "realized_pnl_net": 5.0,
                "total_cost": 20.0 + i,
                "clv_pct": 0.10 + i * 0.01,
                "beat_close": True,
                "fees_actual": 0.0,
                "fees_estimated": 0.0,
                "fees_source": "unknown",
                "position_remaining": 0.0,
            }
            for i in range(6)  # 6 positions > TOP_SEGMENT_MIN_COUNT=5
        ]
        return base

    def test_notional_weight_total_global_nonzero_with_total_cost(self):
        """After injecting position_notional_usd from total_cost, hypothesis_meta weight > 0."""
        from tools.cli.scan import _normalize_position_notional

        positions = self._make_positions_with_total_cost()
        # Simulate scan.py normalization step
        _normalize_position_notional(positions)

        # All positions should now have position_notional_usd set
        for pos in positions:
            assert "position_notional_usd" in pos and pos["position_notional_usd"] > 0

        report = build_coverage_report(positions=positions, run_id="test-run", user_slug="testuser")
        hyp_meta = report.get("hypothesis_meta", {})
        weight = hyp_meta.get("notional_weight_total_global", 0.0)
        assert weight > 0, (
            f"Expected notional_weight_total_global > 0, got {weight}. "
            "Likely total_cost normalization did not propagate."
        )

    def test_notional_weighted_metrics_non_null_after_normalization(self):
        """Segment metrics include non-null notional-weighted fields after normalization."""
        from tools.cli.scan import _normalize_position_notional

        positions = self._make_positions_with_total_cost()
        _normalize_position_notional(positions)

        report = build_coverage_report(positions=positions, run_id="test-run2", user_slug="testuser2")
        segment_analysis = report.get("segment_analysis", {})
        # At least one segment bucket should have a non-null notional_weighted_avg_clv_pct
        any_weighted = any(
            v.get("notional_weighted_avg_clv_pct") is not None
            for bucket_group in segment_analysis.values()
            if isinstance(bucket_group, dict)
            for v in bucket_group.values()
            if isinstance(v, dict)
        )
        assert any_weighted, (
            "Expected at least one segment bucket to have non-null notional_weighted_avg_clv_pct "
            "after total_cost normalization."
        )
```

Note: `build_coverage_report` is already imported at the top of the test file. `_normalize_position_notional` is imported from `tools.cli.scan` inside the test methods (to avoid circular-import issues at module load time).
  </action>
  <verify>
`python -m pytest tests/test_coverage_report.py::TestExtractPositionNotionalUsd tests/test_coverage_report.py::TestNotionalWeightInCoverageReport -v --tb=short`
All 4 new tests must pass. Existing tests must not regress.
  </verify>
  <done>
4 new tests pass. Full test suite `pytest -v --tb=short` shows no regressions.
  </done>
</task>

<task type="auto">
  <name>Task 3: Add Notional parity guarantee note to feature doc</name>
  <files>docs/features/FEATURE-hypothesis-ready-aggregations.md</files>
  <action>
Append a new section after the existing content (after the last `---` or at end of file):

```markdown
---

## Notional Parity Guarantee

Before segment analysis runs, `scan.py` normalizes `position_notional_usd` onto every position dict
using the following priority chain (implemented in `extract_position_notional_usd` in
`polytool/reports/coverage.py`):

1. `position_notional_usd` — explicit field if present and positive
2. `total_cost` — cost basis from dossier positions (most common real-world source)
3. `size * entry_price` — computed from raw position fields

Non-numeric values are silently skipped. Positions that yield `None` from all three sources
contribute 0 to the notional denominator and are excluded from notional-weighted metrics (they
still count in count-weighted metrics).

This normalization runs in `_normalize_position_notional()` in `tools/cli/scan.py` and is applied
to the `positions` list *before* `build_coverage_report` is called, ensuring `coverage.py` always
sees a populated `position_notional_usd` when any source field is available.

### Debug Artifact

Every scan run emits `notional_weight_debug.json` in the run root with:

| Field | Description |
|---|---|
| `total_positions` | Count of all positions |
| `extracted_weight_total` | Sum of all extracted `position_notional_usd` values |
| `count_missing_weight` | Positions where no source field yielded a positive value |
| `top_missing_reasons` | Reason breakdown: `NO_FIELDS`, `NON_NUMERIC`, `ZERO_OR_NEGATIVE`, `FALLBACK_FAILED` |
| `samples` | First 10 positions with their field presence and extracted value |

The path is recorded as `notional_weight_debug_json` in `run_manifest.output_paths`.
```
  </action>
  <verify>
Read docs/features/FEATURE-hypothesis-ready-aggregations.md and confirm the "Notional Parity Guarantee" section appears at the end with the debug artifact table.
  </verify>
  <done>
The doc contains the Notional Parity Guarantee section explaining the normalization chain and the notional_weight_debug.json artifact schema.
  </done>
</task>

</tasks>

<verification>
1. `python -m pytest tests/test_coverage_report.py -v --tb=short` — all tests pass including 4 new ones
2. `python -m pytest tests/test_scan_trust_artifacts.py -v --tb=short` — no regressions
3. `python -m pytest -v --tb=short` — full suite green (217+ tests)
4. `grep "notional_weight_debug_json" tools/cli/scan.py` — appears in output_paths and emitted dicts
5. `grep "_normalize_position_notional" tools/cli/scan.py` — called before build_coverage_report
</verification>

<success_criteria>
- pytest full suite passes with no regressions
- notional_weight_debug.json is written to run root on every scan and listed in run_manifest output_paths
- Positions carrying total_cost (but not position_notional_usd) yield notional_weight_total_global > 0 and non-null segment weighted metrics in coverage report
- Feature doc records the normalization guarantee and debug artifact schema
</success_criteria>

<output>
After completion, create `.planning/quick/5-fix-notional-weighted-metrics-null-by-no/5-SUMMARY.md`
</output>
