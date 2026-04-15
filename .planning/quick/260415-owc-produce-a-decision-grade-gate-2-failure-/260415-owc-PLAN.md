---
phase: quick-260415-owc
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/gates/gate2_failure_anatomy.py
  - docs/dev_logs/2026-04-15_gate2_failure_anatomy.md
  - tests/test_gate2_failure_anatomy.py
autonomous: true
requirements: [GATE2-ANATOMY]

must_haves:
  truths:
    - "Every tape in the 50-tape corpus is classified into exactly one of three partitions: structural-zero-fill, executable-negative-or-flat, executable-positive"
    - "Per-tape fill counts, order counts, and per-scenario PnL are extracted from sweep_summary.json files"
    - "A recommendation matrix ranks the three documented path-forward options with evidence-backed scoring"
    - "Dev log exists at docs/dev_logs/2026-04-15_gate2_failure_anatomy.md with partition table and recommendation matrix"
  artifacts:
    - path: "tools/gates/gate2_failure_anatomy.py"
      provides: "Partition classifier and report generator"
      exports: ["main", "classify_tape", "load_sweep_results", "build_recommendation_matrix"]
    - path: "docs/dev_logs/2026-04-15_gate2_failure_anatomy.md"
      provides: "Decision-grade analysis document"
      contains: "Partition Table"
    - path: "tests/test_gate2_failure_anatomy.py"
      provides: "Unit tests for partition classifier"
  key_links:
    - from: "tools/gates/gate2_failure_anatomy.py"
      to: "artifacts/gates/gate2_sweep/gate_failed.json"
      via: "JSON read of per-tape results"
      pattern: "gate_failed\\.json"
    - from: "tools/gates/gate2_failure_anatomy.py"
      to: "artifacts/gates/gate2_sweep/sweeps/*/sweep_summary.json"
      via: "Per-tape sweep summary glob"
      pattern: "sweep_summary\\.json"
---

<objective>
Produce a decision-grade Gate 2 failure anatomy analysis that partitions all 50 tapes
in the recovery corpus into three categories — structural zero-fill, executable-but-
negative/flat, and executable-positive — using per-tape sweep_summary.json data
(fill counts, order counts, per-scenario PnL). Then rank the three documented
path-forward options (crypto-only subset, low-frequency strategy improvement,
Track 2 focus) in a recommendation matrix scored against evidence.

Purpose: The operator needs a clear, evidence-backed decision document to choose
the next path for Gate 2 / Track 1 progress. The current "7/50 = 14% FAIL" headline
obscures the structural reality that most failures are not strategy failures — they
are data-tier or market-type incompatibilities.

Output: An analysis script, a dev log with partition table and recommendation matrix,
and tests for the classifier.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-14_gate2_full_corpus_resweep.md
@D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md
@D:/Coding Projects/Polymarket/PolyTool/artifacts/gates/gate2_sweep/gate_failed.json

<interfaces>
<!-- Key data structures the executor needs. Extracted from existing sweep artifacts. -->

gate_failed.json structure (top-level):
```json
{
  "gate": "mm_sweep_gate",
  "verdict": "FAIL",
  "threshold": 0.7,
  "positive_count": 7,
  "total_count": 50,
  "pass_rate": 0.14,
  "tapes": [
    {
      "tape_id": "...",
      "tape_path": "...",
      "bucket": "crypto|politics|sports|near_resolution|new_market",
      "best_scenario_id": "spread-x050|spread-x100|...|spread-x300",
      "best_net_profit": "35.535...",
      "positive": true|false,
      "sweep_dir": "..."
    }
  ]
}
```

Per-tape sweep_summary.json structure (in sweeps/*/sweep_summary.json):
```json
{
  "sweep_id": "...",
  "tape_path": "...",
  "strategy": "market_maker_v1",
  "scenarios": [
    {
      "scenario_id": "spread-x050",
      "net_profit": "0",
      "realized_pnl": "0",
      "unrealized_pnl": "0",
      "total_fees": "0",
      "warnings_count": 1
    }
  ],
  "aggregate": {
    "best_net_profit": "0",
    "worst_net_profit": "0",
    "total_decisions": 0,
    "total_orders": 0,
    "total_fills": 0,
    "scenarios_with_trades": 0,
    "dominant_rejection_counts": []
  }
}
```

Classification rules (derived from evidence gathering):
- STRUCTURAL ZERO-FILL: total_fills == 0 AND total_orders == 0
  (Silver tapes: no L2 book data, L2Book never initializes, fill engine rejects all)
- EXECUTABLE-NEGATIVE/FLAT: total_fills > 0 AND best_net_profit <= 0
  (Shadow non-crypto: has fills but strategy cannot generate positive PnL at any spread)
- EXECUTABLE-POSITIVE: total_fills > 0 AND best_net_profit > 0
  (Crypto shadow tapes: 7/10 positive)

IMPORTANT CORRECTION from evidence gathering:
Many Shadow tapes showing "$0 best_net_profit" in gate_failed.json are NOT zero-fill.
Example: politics tape "will-a-different-combination" has total_fills=209 but best
scenario is $0. Sports tape "fif-col-fra-2026-03-29-draw" has total_fills=1271 but
best scenario is $0. The "$0" means break-even-at-best, NOT no-fills. Only Silver
tapes (total_fills=0, total_orders=0, total_decisions=0) are truly structurally
non-executable. The partition MUST use per-tape sweep_summary.json aggregate data,
not just best_net_profit from gate_failed.json.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build partition classifier and report generator</name>
  <files>tools/gates/gate2_failure_anatomy.py, tests/test_gate2_failure_anatomy.py</files>
  <action>
Create `tools/gates/gate2_failure_anatomy.py` with the following functions:

1. `load_sweep_results(gate_json_path, sweeps_dir)` -> list[dict]:
   - Read `gate_failed.json` for the 50-tape roster with bucket, best_net_profit, positive flag.
   - For each tape, locate and read its `sweep_summary.json` from `sweeps_dir/{sweep_id}/sweep_summary.json`.
     The sweep_id is derived from the tape's `sweep_dir` field in gate_failed.json (basename of sweep_dir).
   - Merge per-tape aggregate data: total_fills, total_orders, total_decisions, scenarios_with_trades,
     dominant_rejection_counts, worst_net_profit, median_net_profit.
   - Return enriched tape list.

2. `classify_tape(tape: dict)` -> str:
   - "structural-zero-fill" if total_fills == 0 AND total_orders == 0
   - "executable-positive" if total_fills > 0 AND float(best_net_profit) > 0
   - "executable-negative-or-flat" otherwise (total_fills > 0, best <= 0)
   - Edge case: if total_fills > 0 but total_orders == 0, flag as anomaly (should not happen).

3. `build_partition_table(tapes: list[dict])` -> dict:
   - Group by partition class.
   - For each group: count, list of tape_ids, bucket breakdown, aggregate fill stats.
   - Return structured dict.

4. `build_recommendation_matrix(partition: dict)` -> list[dict]:
   - Score three options against four criteria:
     a. Time-to-first-dollar (how fast can this unblock revenue?)
     b. Gate-2 closure feasibility (can this path pass the 70% threshold?)
     c. Data dependency (what new data/tapes are needed?)
     d. Strategy risk (does this require untested strategy changes?)
   - Option 1 "Crypto-only corpus subset": fast closure (7/10=70%), requires spec change (operator authorization), no strategy changes needed, no new data needed. Score: HIGH feasibility, LOW risk, FAST time.
   - Option 2 "Low-frequency strategy improvement": unknown timeline, needs new strategy research for politics/sports, needs re-sweep after changes, HIGH risk. Score: LOW feasibility, HIGH risk, SLOW time.
   - Option 3 "Track 2 focus (standalone)": does NOT close Gate 2 but generates revenue independently, 12 active markets available now, needs paper soak + VPS. Score: N/A for Gate 2 closure, MEDIUM risk, MEDIUM time.
   - Return list of option dicts with scores and rationale.

5. `render_markdown(partition, matrix, output_path)`:
   - Write a complete markdown report with:
     - Executive summary (one paragraph)
     - Partition table (3 rows: structural, negative/flat, positive)
     - Per-partition detail sections with per-tape tables
     - Recommendation matrix table
     - Ranked recommendation with rationale
   - The markdown will be incorporated into the dev log (Task 2).

6. `main(argv=None)`:
   - argparse with --gate-json (default: artifacts/gates/gate2_sweep/gate_failed.json),
     --sweeps-dir (default: artifacts/gates/gate2_sweep/sweeps),
     --output-json (default: artifacts/gates/gate2_sweep/failure_anatomy.json),
     --output-md (default: artifacts/gates/gate2_sweep/failure_anatomy.md).
   - Run the full pipeline: load -> classify -> partition -> matrix -> render.
   - Write JSON report and markdown report.
   - Print summary to stdout.
   - Return 0 on success.

Also create `tests/test_gate2_failure_anatomy.py` with tests:
- `test_classify_structural_zero_fill`: tape with total_fills=0, total_orders=0 -> "structural-zero-fill"
- `test_classify_executable_positive`: tape with total_fills=100, best_net_profit="5.0" -> "executable-positive"
- `test_classify_executable_negative`: tape with total_fills=50, best_net_profit="0" -> "executable-negative-or-flat"
- `test_classify_negative_pnl`: tape with total_fills=50, best_net_profit="-2.0" -> "executable-negative-or-flat"
- `test_partition_table_groups_correctly`: 3 mock tapes (one per class), verify grouping
- `test_recommendation_matrix_has_three_options`: verify all three options present with all four criteria scored

Use Decimal or string comparison for PnL values (they come as strings from JSON). Do NOT convert to float for equality checks -- use `Decimal(str) > 0` for comparisons.

The script must work standalone: `python tools/gates/gate2_failure_anatomy.py` with no extra dependencies beyond stdlib + json + pathlib + argparse + decimal.
  </action>
  <verify>
    <automated>python -m pytest tests/test_gate2_failure_anatomy.py -v --tb=short</automated>
  </verify>
  <done>
    - classify_tape correctly assigns all three partition classes based on fill counts and PnL
    - load_sweep_results merges gate_failed.json with per-tape sweep_summary.json aggregate data
    - build_partition_table produces a structured grouping with bucket breakdowns
    - build_recommendation_matrix produces three options scored on four criteria
    - All tests pass
  </done>
</task>

<task type="auto">
  <name>Task 2: Run anatomy analysis and write dev log</name>
  <files>docs/dev_logs/2026-04-15_gate2_failure_anatomy.md</files>
  <action>
Run the analysis script from Task 1 against the real sweep artifacts:

```bash
python tools/gates/gate2_failure_anatomy.py \
  --gate-json artifacts/gates/gate2_sweep/gate_failed.json \
  --sweeps-dir artifacts/gates/gate2_sweep/sweeps \
  --output-json artifacts/gates/gate2_sweep/failure_anatomy.json \
  --output-md artifacts/gates/gate2_sweep/failure_anatomy.md
```

Then write `docs/dev_logs/2026-04-15_gate2_failure_anatomy.md` using the generated
markdown report as the core content. The dev log must follow the project's dev log
format and contain:

**Header:**
- Title: "Gate 2 Failure Anatomy -- Decision-Grade Analysis"
- Date: 2026-04-15
- Task reference: quick-260415-owc

**Summary:** One paragraph stating: 50-tape corpus partitioned into three classes;
structural zero-fill (Silver tapes, no L2 data), executable-negative-or-flat
(Shadow non-crypto with fills but no profit), executable-positive (crypto Shadow).
State the exact counts for each partition.

**Partition Table:** A three-row table:
| Partition | Count | Buckets | Fills (total across all scenarios) | Best PnL Range |
with one row per class.

**Partition Detail Sections:**
For each partition, a per-tape table showing: tape_id (shortened), bucket,
total_fills, total_orders, scenarios_with_trades, best_net_profit, worst_net_profit.
Add a brief narrative explaining why this partition behaves the way it does.

For structural-zero-fill: explain L2 book initialization failure chain
(Silver tapes have price_2min_guide events only, L2Book.apply() ignores them,
book stays uninitialized, fill engine rejects with book_not_initialized).

For executable-negative-or-flat: explain that these tapes DID generate fills but
the market-maker spread capture is insufficient on low-frequency, extreme-probability
markets. Note which tapes had fills but $0 best PnL (break-even-at-best) vs which
had negative best PnL (losing even at optimal spread).

For executable-positive: note the 7/10 crypto success, cite spread scenarios
and PnL range, note the 3 negative crypto tapes and their characteristics.

**Recommendation Matrix:**
A table scoring the three path-forward options:
| Option | Time-to-First-Dollar | Gate-2 Closure | Data Dependency | Strategy Risk | Rank |

**Ranked Recommendation:**
Number the options 1-3 by overall desirability with a one-sentence rationale each.
Do NOT advocate for any option -- present evidence and let the operator decide.
But DO clearly state which option has the highest Gate-2-closure feasibility
(Option 1: crypto-only subset at 7/10=70%) and which has the fastest standalone
revenue path (Option 3: Track 2).

**Artifacts Written:** List all files produced (JSON report, MD report, dev log).

**Smoke Test:** Include the commands run and their output summary.
  </action>
  <verify>
    <automated>python -c "import json; d=json.load(open('artifacts/gates/gate2_sweep/failure_anatomy.json')); assert len(d['partitions']) == 3; assert sum(p['count'] for p in d['partitions'].values()) == 50; print('PASS: 50 tapes across 3 partitions')"</automated>
  </verify>
  <done>
    - failure_anatomy.json exists with 50 tapes partitioned into exactly 3 classes
    - failure_anatomy.md exists with partition table and recommendation matrix
    - Dev log at docs/dev_logs/2026-04-15_gate2_failure_anatomy.md follows project format
    - Dev log contains partition table, per-partition detail, and recommendation matrix
    - No strategy changes, no gate threshold changes, no benchmark manifest modifications
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Sweep artifacts -> classifier | Reading cached JSON from local filesystem; no external input |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Tampering | gate_failed.json | accept | Read-only analysis of gitignored artifacts; no code changes to strategy or gates |
| T-quick-02 | Information Disclosure | failure_anatomy.json | accept | Contains only aggregated PnL data already in gate_failed.json; no secrets |
</threat_model>

<verification>
1. `python -m pytest tests/test_gate2_failure_anatomy.py -v --tb=short` -- all tests pass
2. `python tools/gates/gate2_failure_anatomy.py` -- runs without error, produces JSON + MD
3. `python -c "import json; d=json.load(open('artifacts/gates/gate2_sweep/failure_anatomy.json')); assert len(d['partitions']) == 3; assert sum(p['count'] for p in d['partitions'].values()) == 50"` -- 50 tapes, 3 partitions
4. `test -f docs/dev_logs/2026-04-15_gate2_failure_anatomy.md` -- dev log exists
</verification>

<success_criteria>
- All 50 tapes classified into exactly one of three partitions
- Per-tape evidence includes fill counts from sweep_summary.json (not just PnL)
- Recommendation matrix scores all three path-forward options on four criteria
- Dev log is complete, follows project format, contains no strategy changes or gate modifications
- Analysis is reproducible: running the script again produces identical output
</success_criteria>

<output>
After completion, create `.planning/quick/260415-owc-produce-a-decision-grade-gate-2-failure-/260415-owc-SUMMARY.md`
</output>
