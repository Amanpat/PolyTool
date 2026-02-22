---
phase: quick
plan: 4
type: execute
wave: 1
depends_on: []
files_modified:
  - polytool/reports/coverage.py
  - tools/cli/scan.py
  - tests/test_coverage_report.py
  - tests/test_scan_trust_artifacts.py
  - docs/features/FEATURE-hypothesis-candidates.md
autonomous: true

must_haves:
  truths:
    - "hypothesis_candidates.json appears in run root after scan"
    - "run_manifest output_paths contains hypothesis_candidates_json key"
    - "Each candidate entry includes segment_key, metrics snapshot, denominators, and falsification plan"
    - "Ranking is deterministic: notional_weighted_avg_clv_pct desc then notional_weighted_beat_close_rate desc, min count=5"
    - "coverage_reconciliation_report.md contains a Hypothesis Candidates section with top 2-5 entries"
    - "pytest -q passes with no new failures"
  artifacts:
    - path: "polytool/reports/coverage.py"
      provides: "_build_hypothesis_candidates(), write_hypothesis_candidates(), _render_hypothesis_candidates() added"
      exports: ["_build_hypothesis_candidates", "write_hypothesis_candidates"]
    - path: "tools/cli/scan.py"
      provides: "hypothesis_candidates.json written to output_dir, path registered in output_paths"
    - path: "tests/test_coverage_report.py"
      provides: "Unit tests for _build_hypothesis_candidates"
    - path: "tests/test_scan_trust_artifacts.py"
      provides: "Integration assertion that hypothesis_candidates_json appears in emitted paths"
  key_links:
    - from: "polytool/reports/coverage.py (_build_hypothesis_candidates)"
      to: "segment_analysis (already in coverage_report)"
      via: "reads segment_analysis dict produced by _build_segment_analysis"
      pattern: "segment_analysis"
    - from: "tools/cli/scan.py"
      to: "write_hypothesis_candidates"
      via: "import from polytool.reports.coverage, called after write_coverage_report"
      pattern: "write_hypothesis_candidates"
    - from: "scan.py output_paths dict"
      to: "hypothesis_candidates_json key"
      via: "assigned immediately after write_hypothesis_candidates returns"
      pattern: "hypothesis_candidates_json"
---

<objective>
Build hypothesis_candidates.json artifact and Hypothesis Candidates markdown section from existing segment_analysis outputs.

Purpose: Surface the top 2-5 segments as actionable hypothesis starters with falsification plans, denominator transparency, and deterministic ranking.
Output: hypothesis_candidates.json in run root, Hypothesis Candidates section in coverage markdown, manifest registration.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@polytool/reports/coverage.py
@tools/cli/scan.py
@tests/test_coverage_report.py
@tests/test_scan_trust_artifacts.py
@docs/features/FEATURE-hypothesis-ready-aggregations.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add _build_hypothesis_candidates, write_hypothesis_candidates, and markdown renderer to coverage.py</name>
  <files>polytool/reports/coverage.py</files>
  <action>
Add three functions to coverage.py after `_collect_top_segments_by_metric`:

**`_build_hypothesis_candidates(segment_analysis, top_n=5) -> List[Dict[str, Any]]`**

Candidate selection logic:
- Call `_collect_top_segments_by_metric(segment_analysis, "notional_weighted_avg_clv_pct", top_n=top_n)` to get primary ranked list (already enforces count >= TOP_SEGMENT_MIN_COUNT and metric not None).
- For each row returned, look up the full bucket from segment_analysis by parsing the segment string (format: "dimension_label:bucket_name", e.g. "entry_price_tier:coinflip") — map dimension_label back to field key using the same dimensions tuple as `_collect_top_segments_by_metric`:
  ```python
  _DIMENSION_FIELD_MAP = {
      "entry_price_tier": "by_entry_price_tier",
      "market_type": "by_market_type",
      "league": "by_league",
      "sport": "by_sport",
      "category": "by_category",
  }
  ```
  Split on the first colon to get (dimension_label, bucket_name). Look up segment_analysis[field][bucket_name] for full metrics dict.
- If notional_weighted_avg_clv_pct is None for a candidate (should not happen given filtering, but guard), fall back to count-weighted avg_clv_pct; set denominators["weighting"] = "count".
- For each candidate, emit:
  ```python
  {
      "segment_key": "entry_price_tier:coinflip",
      "rank": 1,                          # 1-based position in sorted list
      "metrics": {
          "notional_weighted_avg_clv_pct": <float or null>,
          "notional_weighted_avg_clv_pct_weight_used": <float>,
          "notional_weighted_beat_close_rate": <float or null>,
          "notional_weighted_beat_close_rate_weight_used": <float>,
          "avg_clv_pct": <float or null>,
          "avg_clv_pct_count_used": <int>,
          "beat_close_rate": <float or null>,
          "beat_close_rate_count_used": <int>,
          "avg_entry_drift_pct": <float or null>,
          "avg_entry_drift_pct_count_used": <int>,
          "avg_minutes_to_close": <float or null>,
          "median_minutes_to_close": <float or null>,
          "minutes_to_close_count_used": <int>,
          "win_rate": <float>,
          "count": <int>,
      },
      "denominators": {
          "count_used": <int>,           # same as metrics["count"]
          "weight_used": <float>,        # notional_weighted_avg_clv_pct_weight_used
          "weighting": "notional",       # or "count" if weight_used == 0
      },
      "falsification_plan": {
          "min_sample_size": max(30, count * 2),
          "min_coverage_rate": 0.80,
          "stop_conditions": [
              "notional_weighted_avg_clv_pct < 0 for 2 consecutive future periods",
              "count drops below TOP_SEGMENT_MIN_COUNT in a future run",
          ],
      },
  }
  ```
- Sort order for the full list before slicing: primary = notional_weighted_avg_clv_pct desc (None sorts last via key trick: `(0 if v is None else -v)`), secondary = notional_weighted_beat_close_rate desc (same), tertiary = segment_key asc.
- Return list of up to top_n dicts.

**`write_hypothesis_candidates(candidates, output_dir, generated_at, run_id, user_slug, wallet) -> str`**

- `output_dir` is a `Path` object.
- Wraps candidates list in envelope: `{"generated_at": ..., "run_id": ..., "user_slug": ..., "wallet": ..., "candidates": candidates}`
- Writes to `output_dir / "hypothesis_candidates.json"` with `json.dumps(..., indent=2, sort_keys=True, allow_nan=False)`, encoding="utf-8".
- Returns the file path as a POSIX string (`path.as_posix()`).

**`_render_hypothesis_candidates(report) -> List[str]`**

- Returns lines for markdown section `## Hypothesis Candidates` (to be called after `_render_hypothesis_signals` in `_render_markdown`).
- If `report.get("hypothesis_candidates")` is falsy (empty list or missing), emit one line "- None (no segments meet the minimum count threshold or lack notional-weighted CLV data)." plus blank line and return.
- Otherwise render a markdown table: Rank | Segment | Count | Notional-Wt CLV% | Notional-Wt Beat-Close | Weighting | Min Sample.
- After the table, for each candidate add a sub-section: `### Candidate N: {segment_key}` with falsification plan bullets (min_sample_size, min_coverage_rate, stop_conditions).
- Use `f"{v:.4f}"` for float metrics, string "N/A" for None values.

**Wire into existing functions:**
- In `build_coverage_report`, after `segment_analysis = _build_segment_analysis(...)`, add:
  `hypothesis_candidates = _build_hypothesis_candidates(segment_analysis)`
  Then in the `report` dict, add key `"hypothesis_candidates": hypothesis_candidates`.
- In `_render_markdown`, after `lines.extend(_render_hypothesis_signals(report))`, add:
  `lines.extend(_render_hypothesis_candidates(report))`
  </action>
  <verify>
    python -c "from polytool.reports.coverage import _build_hypothesis_candidates, write_hypothesis_candidates; print('imports ok')"
  </verify>
  <done>
    `_build_hypothesis_candidates({})` returns [].
    `_build_hypothesis_candidates` with qualifying segments returns list with segment_key, rank, metrics, denominators, falsification_plan.
    `write_hypothesis_candidates` writes hypothesis_candidates.json with candidates key in envelope.
    `build_coverage_report` result dict contains "hypothesis_candidates" key.
    `_render_markdown` output contains "## Hypothesis Candidates" section.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire hypothesis_candidates into scan.py, add tests, write feature doc</name>
  <files>
    tools/cli/scan.py
    tests/test_coverage_report.py
    tests/test_scan_trust_artifacts.py
    docs/features/FEATURE-hypothesis-candidates.md
  </files>
  <action>
**scan.py changes:**

1. Add `write_hypothesis_candidates` to the existing `from polytool.reports.coverage import (...)` block at the top of the file.

2. In `run_scan`, immediately after `coverage_paths = write_coverage_report(coverage_report, output_dir, write_markdown=True)`:
   ```python
   hypothesis_candidates_path = write_hypothesis_candidates(
       candidates=coverage_report.get("hypothesis_candidates", []),
       output_dir=output_dir,
       generated_at=coverage_report.get("generated_at", ""),
       run_id=run_id,
       user_slug=username_slug,
       wallet=proxy_wallet,
   )
   ```

3. Add to the `output_paths` dict (alongside the existing entries):
   ```python
   output_paths["hypothesis_candidates_json"] = hypothesis_candidates_path
   ```

4. Add to the `emitted` dict (alongside the existing entries):
   ```python
   emitted["hypothesis_candidates_json"] = hypothesis_candidates_path
   ```

**tests/test_coverage_report.py changes:**

Add to the import block at the top:
```python
from polytool.reports.coverage import (
    ...existing imports...,
    _build_hypothesis_candidates,
    write_hypothesis_candidates,
)
```

Add a new class `TestBuildHypothesisCandidates` with these tests:

- `test_empty_segment_analysis_returns_empty_list`: call `_build_hypothesis_candidates({})`, assert result is `[]`.

- `test_candidates_below_min_count_excluded`: build a minimal segment_analysis dict with `by_entry_price_tier` containing one bucket with `count=2` and `notional_weighted_avg_clv_pct=0.5`. Call `_build_hypothesis_candidates(seg)`. Assert result is `[]` (count 2 < TOP_SEGMENT_MIN_COUNT=5).

- `test_candidates_ranked_by_notional_clv_desc`: build segment_analysis with `by_entry_price_tier` having two buckets: `coinflip` with count=10, notional_weighted_avg_clv_pct=0.15, notional_weighted_avg_clv_pct_weight_used=100.0 and `favorite` with count=10, notional_weighted_avg_clv_pct=0.05, notional_weighted_avg_clv_pct_weight_used=80.0. Assert first candidate segment_key == "entry_price_tier:coinflip", second == "entry_price_tier:favorite".

- `test_candidate_has_required_fields`: using the candidates from the test above, take `candidates[0]`. Assert it has keys: segment_key, rank, metrics, denominators, falsification_plan. Assert `candidates[0]["rank"] == 1`. Assert `denominators["weighting"] == "notional"` (weight_used > 0). Assert `falsification_plan["min_sample_size"] >= 30`. Assert `len(falsification_plan["stop_conditions"]) >= 1`.

- `test_write_hypothesis_candidates_produces_valid_json` (uses `tmp_path` fixture): call `write_hypothesis_candidates(candidates=[{"segment_key": "x"}], output_dir=tmp_path, generated_at="2026-02-20T00:00:00+00:00", run_id="r1", user_slug="testuser", wallet="0xabc")`. Assert returned path exists. Assert `json.loads(Path(returned_path).read_text())["candidates"] == [{"segment_key": "x"}]`. Assert envelope keys: generated_at, run_id, user_slug, wallet, candidates all present.

- `test_build_coverage_report_includes_hypothesis_candidates_key`: call `build_coverage_report` with a list of 10 minimal positions (use `_make_positions()` repeated twice from the existing helper, or inline 10 dicts). Assert `"hypothesis_candidates"` in result. Assert isinstance(result["hypothesis_candidates"], list).

**tests/test_scan_trust_artifacts.py changes:**

In `test_run_scan_emits_trust_artifacts_from_canonical_scan_path`, after the line `assert manifest["output_paths"]["segment_analysis_json"] == emitted["segment_analysis_json"]`, add:
```python
assert "hypothesis_candidates_json" in manifest["output_paths"]
assert "hypothesis_candidates_json" in emitted
assert Path(emitted["hypothesis_candidates_json"]).exists()
```

**docs/features/FEATURE-hypothesis-candidates.md** — create new file with this content:

```
# Feature: Hypothesis Candidates Artifact (Roadmap 5.4)

## Summary

Produces `hypothesis_candidates.json` in the scan run root and a **Hypothesis Candidates**
section in `coverage_reconciliation_report.md`. Each entry is a top segment with a metrics
snapshot, explicit denominators, and a falsification plan.

## Candidate Selection Rules

- Only segments with `count >= TOP_SEGMENT_MIN_COUNT` (currently 5) are eligible.
- Ranked by `notional_weighted_avg_clv_pct` descending (primary), then
  `notional_weighted_beat_close_rate` descending (secondary), then segment_key ascending (tie-break).
- When `notional_weighted_avg_clv_pct_weight_used == 0`, uses count-weighted `avg_clv_pct` as
  primary rank signal; `denominators.weighting` is set to `"count"`.
- Top 2-5 candidates emitted (default top_n=5).

## Artifact Schema

See `docs/features/FEATURE-hypothesis-ready-aggregations.md` for segment metric definitions.

Envelope:
- generated_at, run_id, user_slug, wallet, candidates[]

Each candidate:
- segment_key (e.g. "entry_price_tier:coinflip")
- rank (1-based)
- metrics (notional_weighted_avg_clv_pct, notional_weighted_beat_close_rate, avg_clv_pct,
  beat_close_rate, avg_entry_drift_pct, avg_minutes_to_close, median_minutes_to_close, win_rate, count,
  plus weight_used and count_used denominators for each)
- denominators (count_used, weight_used, weighting)
- falsification_plan (min_sample_size, min_coverage_rate, stop_conditions)

## Manifest Registration

`run_manifest.output_paths["hypothesis_candidates_json"]` contains the POSIX path.

## Files Changed

- `polytool/reports/coverage.py`: _build_hypothesis_candidates, write_hypothesis_candidates, _render_hypothesis_candidates
- `tools/cli/scan.py`: writes artifact, registers in output_paths and emitted
- `tests/test_coverage_report.py`: TestBuildHypothesisCandidates (6 tests)
- `tests/test_scan_trust_artifacts.py`: manifest path assertions

## Guardrails

- Offline only: no network calls, no backtesting engine, no unverifiable claims.
- All metrics come from already-computed segment_analysis; no new data access.
- Falsification plan values are static defaults, not model predictions.

## How to Verify

pytest -q
# All tests pass

# After a real scan:
# hypothesis_candidates.json appears in the run root directory
```
  </action>
  <verify>pytest -q --tb=short 2>&1 | tail -20</verify>
  <done>
    pytest -q passes with no new failures.
    hypothesis_candidates.json exists in the run root (verified by test_scan_trust_artifacts).
    manifest["output_paths"]["hypothesis_candidates_json"] is set (verified by test).
    emitted["hypothesis_candidates_json"] is set (verified by test).
    6 new tests in TestBuildHypothesisCandidates all pass.
  </done>
</task>

</tasks>

<verification>
pytest -q --tb=short
python -c "from polytool.reports.coverage import _build_hypothesis_candidates, write_hypothesis_candidates; print('ok')"
</verification>

<success_criteria>
- pytest -q passes with no failures
- hypothesis_candidates_json key present in run_manifest output_paths (verified by test)
- hypothesis_candidates.json file written to output_dir (verified by test)
- Each candidate dict contains segment_key, rank, metrics, denominators, falsification_plan
- Ranking is deterministic: notional_weighted_avg_clv_pct desc, then beat_close_rate desc, then segment_key asc
- coverage_reconciliation_report.md contains Hypothesis Candidates section
</success_criteria>

<output>
After completion, create `.planning/quick/4-build-hypothesis-candidates-json-artifac/4-SUMMARY.md`
</output>
