---
phase: quick-6
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/clv.py
  - polytool/reports/coverage.py
  - tools/cli/scan.py
  - tools/cli/audit_coverage.py
  - tests/test_clv.py
  - tests/test_coverage_report.py
  - tests/test_scan_trust_artifacts.py
  - docs/features/FEATURE-dual-clv-variants.md
autonomous: true

must_haves:
  truths:
    - "Each position dict gets 12 new fields: closing_price_settlement/closing_ts_settlement/clv_pct_settlement/beat_close_settlement/clv_source_settlement/clv_missing_reason_settlement and the same 6 for pre_event"
    - "clv_settlement uses only onchain_resolved_at as close_ts anchor (single-stage sub-ladder)"
    - "clv_pre_event uses gamma_closedTime -> gamma_endDate -> gamma_umaEndDate ladder (stages 1-3, never onchain_resolved_at)"
    - "Coverage report renders a CLV Settlement block and a CLV Pre-Event block"
    - "Hypothesis ranking prefers notional-weighted pre_event CLV when pre_event denom>0, falls back to settlement CLV"
    - "All existing tests still pass; new unit tests cover both variant paths and the fallback ranking logic"
  artifacts:
    - path: "packages/polymarket/clv.py"
      provides: "resolve_close_ts_settlement(), resolve_close_ts_pre_event(), enrich_position_with_dual_clv()"
    - path: "polytool/reports/coverage.py"
      provides: "_build_clv_coverage_dual() rendering both blocks; _build_hypothesis_candidates() updated ranking"
    - path: "docs/features/FEATURE-dual-clv-variants.md"
      provides: "Feature spec"
  key_links:
    - from: "packages/polymarket/clv.py"
      to: "polytool/reports/coverage.py"
      via: "enrich_position_with_dual_clv writes *_settlement/*_pre_event fields consumed by _build_clv_coverage_dual"
    - from: "polytool/reports/coverage.py"
      to: "tools/cli/scan.py"
      via: "_build_hypothesis_candidates reads pre_event notional_weighted_avg_clv_pct with settlement fallback"
---

<objective>
Add two named CLV variants per position: clv_settlement (anchor = onchain resolved_at only) and clv_pre_event (anchor = gamma closedTime/endDate/umaEndDate ladder). Coverage report renders both blocks. Hypothesis ranking prefers notional-weighted pre_event CLV, falls back to settlement.

Purpose: Separates market-close signal from resolution-settlement signal, enabling cleaner hypothesis segmentation and better pre-event edge measurement.
Output: Updated clv.py, coverage.py, scan.py, audit_coverage.py, tests, feature doc.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@packages/polymarket/clv.py
@polytool/reports/coverage.py
@tools/cli/scan.py
@tools/cli/audit_coverage.py
@tests/test_clv.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add dual CLV resolver functions and enrich_position_with_dual_clv to clv.py</name>
  <files>packages/polymarket/clv.py</files>
  <action>
Add two sub-ladder constants and two resolver functions to clv.py:

```python
# Settlement sub-ladder: ONLY onchain_resolved_at stage
_SETTLEMENT_TS_LADDER: Sequence[Tuple[str, Sequence[str]]] = (
    _CLOSE_TS_LADDER[0],  # ("onchain_resolved_at", ("resolved_at", "resolvedAt", "resolution_resolved_at"))
)

# Pre-event sub-ladder: closedTime/endDate/umaEndDate (skip resolution stage)
_PRE_EVENT_TS_LADDER: Sequence[Tuple[str, Sequence[str]]] = _CLOSE_TS_LADDER[1:]
```

Add `_resolve_close_ts_from_ladder(position, ladder)` private helper that accepts an explicit ladder sequence and returns `(ts, source, attempted, failure_reason)` using the same logic as the current `resolve_close_ts_with_diagnostics` (just parameterize the ladder).

Add public functions:
- `resolve_close_ts_settlement(position)` -> `(Optional[datetime], Optional[str])` — wraps `_resolve_close_ts_from_ladder` with `_SETTLEMENT_TS_LADDER`
- `resolve_close_ts_pre_event(position)` -> `(Optional[datetime], Optional[str])` — wraps `_resolve_close_ts_from_ladder` with `_PRE_EVENT_TS_LADDER`

Add `MISSING_REASON_NO_PRE_EVENT_CLOSE_TS = "NO_PRE_EVENT_CLOSE_TS"` and `MISSING_REASON_NO_SETTLEMENT_CLOSE_TS = "NO_SETTLEMENT_CLOSE_TS"` constants.

Add `_set_missing_clv_variant_fields(position, variant, reason)` that writes all 6 `*_{variant}` fields as None/reason.

Add `_apply_clv_variant(position, variant, close_ts, close_ts_source, entry_price, token_id, *, clickhouse_client, clob_client, allow_online, closing_window_seconds, interval, fidelity)` that calls `resolve_closing_price(token_id, close_ts, ...)` and writes the 6 per-variant fields:
- `closing_price_{variant}` (rounded float or None)
- `closing_ts_{variant}` (ISO string or None)
- `clv_pct_{variant}` (rounded float or None)
- `beat_close_{variant}` (bool or None)
- `clv_source_{variant}` (f"prices_history|{close_ts_source}" or None)
- `clv_missing_reason_{variant}` (reason string or None)

Add `enrich_position_with_dual_clv(position, ...)` that:
1. Calls existing `enrich_position_with_clv` (preserves all current fields including entry context, close_ts, etc.)
2. Calls `_apply_clv_variant(position, "settlement", ...)` using `resolve_close_ts_settlement`
3. Calls `_apply_clv_variant(position, "pre_event", ...)` using `resolve_close_ts_pre_event`
4. Returns the mutated position dict

Add `enrich_positions_with_dual_clv(positions, ...)` batch wrapper mirroring `enrich_positions_with_clv`, returning a summary dict that includes both variant present/missing counts.

Keep the existing `enrich_position_with_clv` and `enrich_positions_with_clv` unchanged (backward compat).

Add new symbols to module's implicit public surface (no `__all__` exists, just ensure they are importable).
  </action>
  <verify>
    python -c "from packages.polymarket.clv import resolve_close_ts_settlement, resolve_close_ts_pre_event, enrich_position_with_dual_clv, enrich_positions_with_dual_clv, MISSING_REASON_NO_PRE_EVENT_CLOSE_TS, MISSING_REASON_NO_SETTLEMENT_CLOSE_TS; print('imports ok')"
  </verify>
  <done>
    All six new imports succeed. Running `pytest tests/test_clv.py -v --tb=short` shows all pre-existing tests still pass (zero regressions). New functions are importable and callable with a minimal fake position dict without error.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire dual CLV into scan.py + audit_coverage.py and update coverage.py report rendering and hypothesis ranking</name>
  <files>
    polytool/reports/coverage.py
    tools/cli/scan.py
    tools/cli/audit_coverage.py
  </files>
  <action>
**coverage.py changes:**

1. Add `_build_clv_variant_coverage(positions, variant)` that mirrors `_build_clv_coverage` but reads `clv_pct_{variant}` and `clv_missing_reason_{variant}` and `clv_source_{variant}`. Returns a dict with `variant`, `eligible_positions`, `clv_present_count`, `clv_missing_count`, `coverage_rate`, `clv_source_counts`, `missing_reason_counts`.

2. Update `_build_clv_coverage` to return the existing flat dict plus embed two new keys: `"settlement": _build_clv_variant_coverage(positions, "settlement")` and `"pre_event": _build_clv_variant_coverage(positions, "pre_event")`.

3. Add `_render_clv_variant_block(coverage_dict, variant, label)` markdown renderer that prints: variant header, present/missing counts, coverage_rate, source breakdown, missing reason breakdown. Call it from `_render_clv_coverage` (or wherever CLV markdown is rendered) to emit two sub-blocks labeled "CLV Settlement" and "CLV Pre-Event".

4. Update `_build_hypothesis_candidates` ranking: in the sort key and weighting selection, prefer `notional_weighted_avg_clv_pct_pre_event` over `notional_weighted_avg_clv_pct_settlement` when the pre_event denominator weight > 0, else fall back to settlement. This requires the segment buckets to accumulate both variants. Update `_accumulate_segment_bucket` to also sum `clv_pct_settlement`, `beat_close_settlement`, `clv_pct_pre_event`, `beat_close_pre_event` (count and notional weighted), producing `avg_clv_pct_settlement`, `notional_weighted_avg_clv_pct_settlement`, `avg_clv_pct_pre_event`, `notional_weighted_avg_clv_pct_pre_event` in finalized bucket output. Update `_build_hypothesis_candidates` to pick the preferred variant's metric as `rank_clv` and record `clv_variant_used` ("pre_event" or "settlement") in the candidate dict output.

**scan.py changes:**

Update import block to also import `enrich_positions_with_dual_clv` from `packages.polymarket.clv`. In `_apply_clv_enrichment`, replace the call to `enrich_positions_with_clv` with `enrich_positions_with_dual_clv` so both variant fields land on each position in `dossier.json`. Update the summary dict keys written to the CLV enrichment artifact to include dual-variant counts.

**audit_coverage.py changes:**

Wherever CLV fields are read for display/stats in the audit report, also surface `clv_pct_settlement` and `clv_pct_pre_event` fields in sampled position rows (add them to the per-position field list without breaking existing layout).
  </action>
  <verify>
    pytest tests/test_coverage_report.py tests/test_scan_trust_artifacts.py -v --tb=short
  </verify>
  <done>
    All coverage and scan trust artifact tests pass. `_build_clv_coverage` output contains "settlement" and "pre_event" sub-dicts. `_build_hypothesis_candidates` output contains `clv_variant_used` key on each candidate. `enrich_positions_with_dual_clv` is called in `_apply_clv_enrichment`.
  </done>
</task>

<task type="auto">
  <name>Task 3: Unit tests + feature doc</name>
  <files>
    tests/test_clv.py
    tests/test_coverage_report.py
    tests/test_scan_trust_artifacts.py
    docs/features/FEATURE-dual-clv-variants.md
  </files>
  <action>
**tests/test_clv.py — add new test cases:**

Using the existing `_FakeClickHouse` and `_FakeClobClient` stubs already in the file, add:

- `test_resolve_close_ts_settlement_uses_only_onchain_resolved_at`: position has both `resolved_at` and `closedTime`; assert settlement returns resolved_at source, NOT closedTime.
- `test_resolve_close_ts_settlement_missing_when_no_onchain`: position has only `closedTime`; assert settlement returns None + failure reason.
- `test_resolve_close_ts_pre_event_skips_onchain_resolved_at`: position has `resolved_at` and `closedTime`; assert pre_event returns closedTime source.
- `test_resolve_close_ts_pre_event_ladder_fallback`: position has only `endDate`; assert pre_event resolves endDate.
- `test_enrich_position_with_dual_clv_both_variants_present`: fake position with resolved_at + closedTime + valid token + entry_price; fake CH cache returns prices for both anchors; assert all 12 variant fields are set and non-None.
- `test_enrich_position_with_dual_clv_settlement_missing_pre_event_present`: position has only closedTime (no resolved_at); assert settlement fields missing with `NO_SETTLEMENT_CLOSE_TS`, pre_event fields populated.
- `test_enrich_position_with_dual_clv_preserves_existing_clv_fields`: existing fields like `clv`, `clv_pct`, `beat_close`, `close_ts_source` are still present after dual enrichment.

**tests/test_coverage_report.py — add:**

- `test_build_clv_coverage_includes_settlement_and_pre_event_sub_dicts`: call `_build_clv_coverage` with positions that have both variant fields; assert output has "settlement" and "pre_event" keys each with `clv_present_count`.
- `test_build_hypothesis_candidates_prefers_pre_event_when_denom_positive`: craft segment_analysis where pre_event weight > 0 and is higher; assert candidate has `clv_variant_used == "pre_event"`.
- `test_build_hypothesis_candidates_falls_back_to_settlement`: segment_analysis where pre_event weight == 0 but settlement weight > 0; assert `clv_variant_used == "settlement"`.

**tests/test_scan_trust_artifacts.py — verify:**

Check that existing trust artifact tests still pass; if they mock `enrich_positions_with_clv`, update mocks to also patch `enrich_positions_with_dual_clv` (or patch at the scan module level) so the tests don't break.

**docs/features/FEATURE-dual-clv-variants.md:**

Write a concise feature doc covering:
- Motivation (separate market-close from settlement signal)
- Two variants: `clv_settlement` (anchor=onchain_resolved_at) and `clv_pre_event` (anchor=closedTime/endDate/umaEndDate)
- Per-position fields added (the 12 fields, both variants)
- Coverage report rendering (two blocks)
- Hypothesis ranking logic (pre_event preference with settlement fallback)
- Missing reason codes (NO_SETTLEMENT_CLOSE_TS, NO_PRE_EVENT_CLOSE_TS)
- Backward compatibility (existing `clv`/`clv_pct`/`beat_close` fields unchanged)
  </action>
  <verify>
    pytest tests/test_clv.py tests/test_coverage_report.py tests/test_scan_trust_artifacts.py -v --tb=short 2>&1 | tail -20
  </verify>
  <done>
    All new tests pass. No pre-existing tests regress. Feature doc exists at docs/features/FEATURE-dual-clv-variants.md with all six sections.
  </done>
</task>

</tasks>

<verification>
Run full test suite to confirm no regressions:

```
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Confirm dual variant fields appear on enriched positions:

```python
from packages.polymarket.clv import enrich_position_with_dual_clv
pos = {"resolved_at": "2025-01-01T00:00:00Z", "closedTime": "2024-12-31T23:00:00Z",
       "token_id": "tok1", "entry_price": 0.5}
result = enrich_position_with_dual_clv(pos, clickhouse_client=None, allow_online=False)
assert "clv_pct_settlement" in result
assert "clv_pct_pre_event" in result
assert "clv_missing_reason_settlement" in result
```
</verification>

<success_criteria>
- 12 new per-position variant fields (6 x settlement, 6 x pre_event) written by enrich_position_with_dual_clv
- Coverage report emits two named CLV blocks in markdown output
- Hypothesis candidates include clv_variant_used field; prefer pre_event when denom > 0
- All existing tests pass; at least 10 new targeted unit tests added
- FEATURE-dual-clv-variants.md committed
</success_criteria>

<output>
After completion, create `.planning/quick/6-add-dual-clv-variants-clv-settlement-anc/6-SUMMARY.md`
</output>
