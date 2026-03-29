---
phase: quick-048
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - artifacts/dossiers/users/gabagool22/
  - artifacts/research/wallet_scan/
  - artifacts/debug/gabagool22_crypto_gap_report.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "gabagool22's wallet address is resolved and confirmed"
    - "scan output artifact exists with category/entry_price segment breakdown"
    - "a gap report documents which crypto-specific dimensions the pipeline cannot answer and why"
  artifacts:
    - path: "artifacts/dossiers/users/gabagool22/"
      provides: "scan run outputs (coverage report, segment_analysis.json, hypothesis_candidates.json)"
    - path: "artifacts/debug/gabagool22_crypto_gap_report.md"
      provides: "structured gap report documenting pipeline limits vs. required crypto dimensions"
  key_links:
    - from: "scan --user @gabagool22"
      to: "/api/resolve -> /api/ingest/trades -> segment_analysis.json"
      via: "PolyTool API"
      pattern: "python -m polytool scan --user @gabagool22"
---

<objective>
Run the existing wallet-scan and alpha-distill pipeline against gabagool22 and produce a structured
gap report documenting exactly which crypto-pair-specific analytical dimensions the pipeline can
answer versus which it cannot.

Purpose: Determine whether gabagool22 is a useful signal source for Track 2 crypto pair bot
strategy, and identify what pipeline modifications would be needed for a complete crypto-pair
analysis.

Output:
- scan artifact bundle under artifacts/dossiers/users/gabagool22/
- gap report at artifacts/debug/gabagool22_crypto_gap_report.md
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Resolve gabagool22 wallet and run scan pipeline</name>
  <files>artifacts/dossiers/users/gabagool22/ (created by scan), artifacts/research/wallet_scan/ (created by wallet-scan)</files>
  <action>
    Run the full scan + wallet-scan + alpha-distill pipeline against gabagool22.

    Step 1 — Verify CLI loads:
    ```
    python -m polytool --help
    ```

    Step 2 — Run scan (resolves username to wallet internally via /api/resolve):
    ```
    python -m polytool scan --user @gabagool22 --lite --ingest-positions --compute-pnl --enrich-resolutions --compute-clv
    ```
    Note: scan accepts @handle directly and calls /api/resolve internally. If @gabagool22 fails
    (user not found), try without @ prefix: `--user gabagool22`. If the scan returns
    positions_total=0, record this as a gap finding (no position data available) and proceed
    to Task 2 with only the diagnostic information.

    Step 3 — Run wallet-scan with gabagool22 as the sole input. Create a single-entry input file:
    ```
    echo "@gabagool22" > /tmp/gabagool22_input.txt
    python -m polytool wallet-scan --input /tmp/gabagool22_input.txt --profile lite
    ```

    Step 4 — Run alpha-distill against the wallet-scan output. The wallet-scan run produces a
    dated directory under artifacts/research/wallet_scan/. Pass the most recent run directory:
    ```
    python -m polytool alpha-distill --wallet-scan-run $(ls -td artifacts/research/wallet_scan/*/ | head -1)
    ```

    Capture all stdout/stderr to console. Note any errors but do not abort — partial results
    are useful for the gap report.
  </action>
  <verify>
    <automated>ls artifacts/dossiers/users/gabagool22/ 2>/dev/null || echo "NO_SCAN_OUTPUT — proceed to gap report"</automated>
  </verify>
  <done>Scan pipeline attempted for gabagool22. Either artifact bundle exists under
  artifacts/dossiers/users/gabagool22/, or a clear failure reason (user not found,
  positions=0, API error) is recorded for inclusion in the gap report.</done>
</task>

<task type="auto">
  <name>Task 2: Inspect scan output and write crypto gap report</name>
  <files>artifacts/debug/gabagool22_crypto_gap_report.md</files>
  <action>
    Inspect the scan artifacts (if they exist) and write a structured gap report that answers
    the focus questions as far as possible and documents what the pipeline cannot answer.

    Step 1 — Locate segment_analysis.json (if scan produced output):
    ```
    ls artifacts/dossiers/users/gabagool22/
    cat artifacts/dossiers/users/gabagool22/*/segment_analysis.json 2>/dev/null | python -m json.tool | head -200
    ```

    Step 2 — Check hypothesis_candidates.json for any crypto-category signal:
    ```
    cat artifacts/dossiers/users/gabagool22/*/hypothesis_candidates.json 2>/dev/null
    ```

    Step 3 — Check the alpha_candidates.json from alpha-distill (if produced):
    ```
    ls artifacts/research/wallet_scan/*/alpha_candidates.json 2>/dev/null
    cat artifacts/research/wallet_scan/*/alpha_candidates.json 2>/dev/null | python -m json.tool | head -100
    ```

    Step 4 — Write the gap report to artifacts/debug/gabagool22_crypto_gap_report.md.
    The report must be structured with two main sections:

    ## What The Pipeline CAN Answer (from scan output)
    For each of the following focus dimensions, state what is available in segment_analysis.json
    or hypothesis_candidates.json. If scan returned positions=0 or failed, state that explicitly:
    - Category breakdown: does gabagool22 have crypto positions? What % of positions?
    - Entry price tier breakdown: what tiers does gabagool22 trade in (sub-35c = tier 0.0-0.35)?
    - CLV summary: positive/negative edge overall and in crypto category?
    - Position count and total notional in crypto markets

    ## What The Pipeline CANNOT Answer (pipeline gaps)
    For each of the following focus dimensions, state exactly why the pipeline cannot answer it
    and what modification would be required:

    1. **Pair cost (YES + NO combined cost)**: The scan pipeline treats YES and NO tokens as
       independent positions. It has no concept of pairing YES and NO entries on the same
       bracket. To answer this, a custom analysis step would need to: (a) filter positions to
       crypto bracket markets by slug pattern (btc-up/btc-down etc.), (b) group positions by
       event_slug + bracket_window, (c) compute sum(entry_price * size) for YES+NO legs per
       bracket window, (d) divide by total size to get avg pair cost. This does NOT exist in
       any current CLI command.

    2. **Maker vs taker split**: The /api/export/user_dossier response includes trade records
       but the scan pipeline's coverage.py does NOT extract or segment by order_type/maker_taker
       field. The raw dossier export may include this field — check run artifacts for raw
       dossier.json. If not present, this requires adding a new segment dimension to coverage.py.

    3. **Bracket entry timing (minutes into bracket)**: No current pipeline component captures
       the relationship between a trade's timestamp and the bracket's open time. Would require:
       (a) fetching bracket market open/close times from Gamma API, (b) computing
       trade_ts - bracket_open_ts for each crypto position, (c) binning into entry windows
       (0-5m, 5-15m, etc.). No CLI command implements this.

    4. **Second leg fill timing (leg1_ts to leg2_ts delta)**: Requires pairing YES and NO trades
       per bracket window (same as pair cost), then computing time(leg2) - time(leg1). Not
       implemented anywhere.

    5. **Position sizing patterns**: Partially answerable via segment_analysis.json
       avg_size_per_segment — document what the scan shows. Full distribution histogram
       not available without custom analysis.

    6. **Which symbols (BTC/ETH/SOL) and durations (5m/15m)**: The scan pipeline's
       category field would show "Crypto" but does NOT break down by underlying symbol or
       bracket duration. Would require filtering positions by slug pattern and grouping.

    End each gap item with a concrete one-line modification spec: what file would change and
    what new field/segment axis would be added.

    Write the report to artifacts/debug/gabagool22_crypto_gap_report.md.
  </action>
  <verify>
    <automated>test -f artifacts/debug/gabagool22_crypto_gap_report.md && echo "REPORT_EXISTS" || echo "MISSING"</automated>
  </verify>
  <done>artifacts/debug/gabagool22_crypto_gap_report.md exists with both sections populated.
  The report clearly states what the pipeline answered from scan output (or why it could not,
  e.g. user not found / positions=0) and lists all six gap dimensions with modification specs.
  No scan pipeline code was modified.</done>
</task>

</tasks>

<verification>
1. Scan ran without crashing (even if positions=0 is the result)
2. artifacts/debug/gabagool22_crypto_gap_report.md exists and has both sections
3. No scan pipeline code was modified (constraint from task description)
4. All six focus dimensions are addressed in the report — either answered from scan output
   or documented as gaps with modification specs
</verification>

<success_criteria>
- gabagool22's Polymarket identity resolved (wallet address known or "user not found" confirmed)
- entry_price tier and category breakdown extracted from scan output (or 0-position result documented)
- Six crypto-pair-specific focus dimensions assessed: which are answerable vs. which require pipeline modifications
- Gap report written to artifacts/debug/gabagool22_crypto_gap_report.md
- Zero scan pipeline code changes made
</success_criteria>

<output>
After completion, create `.planning/quick/48-analyze-gabagool22-crypto-trading-patter/48-SUMMARY.md`
with: wallet resolved (yes/no), position count found, which focus dimensions answered, gap count,
and the path to the gap report.
</output>
