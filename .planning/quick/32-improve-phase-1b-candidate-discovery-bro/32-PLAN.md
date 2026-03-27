---
phase: quick-032
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/simtrader/candidate_discovery.py
  - packages/polymarket/simtrader/market_picker.py
  - tools/cli/simtrader.py
  - tests/test_simtrader_candidate_discovery.py
  - docs/dev_logs/2026-03-27_phase1b_candidate_discovery_upgrade.md
autonomous: true
requirements: [QUICK-032]

must_haves:
  truths:
    - "quickrun --list-candidates N returns markets from a larger pool (up to 200) not just the first Gamma page of 20"
    - "Each listed candidate shows inferred bucket (sports/politics/crypto/near_resolution/new_market/other)"
    - "Each listed candidate shows a rank_reason string explaining why it scored well"
    - "One-sided or obviously stale markets are rejected before appearing in the shortlist"
    - "Bucket shortage table is consulted to boost score for buckets with high shortage (sports=15, crypto=10)"
    - "Probe update counts appear in output when activeness probe was run"
  artifacts:
    - path: packages/polymarket/simtrader/candidate_discovery.py
      provides: "CandidateDiscovery class: bucket inference, shortage-aware scoring, ranked output"
      exports: [CandidateDiscovery, DiscoveryResult, infer_bucket, score_for_capture]
    - path: tests/test_simtrader_candidate_discovery.py
      provides: "Offline tests for bucket inference, scoring, ranking, shortage weighting"
    - path: docs/dev_logs/2026-03-27_phase1b_candidate_discovery_upgrade.md
      provides: "Dev log with old vs new behavior, commands run, test counts, example output"
  key_links:
    - from: tools/cli/simtrader.py
      to: packages/polymarket/simtrader/candidate_discovery.py
      via: "_list_candidates() calls CandidateDiscovery.rank()"
      pattern: "CandidateDiscovery"
    - from: packages/polymarket/simtrader/candidate_discovery.py
      to: packages/polymarket/simtrader/market_picker.py
      via: "auto_pick_many() to obtain validated ResolvedMarket list"
      pattern: "auto_pick_many"
    - from: packages/polymarket/simtrader/candidate_discovery.py
      to: packages/polymarket/market_selection/regime_policy.py
      via: "classify_market_regime() for bucket inference"
      pattern: "classify_market_regime"
---

<objective>
Improve the quality of `quickrun --list-candidates` for Phase 1B Gold capture by:
(1) expanding the candidate pool from one 20-market Gamma page to up to 200 active markets,
(2) adding bucket inference via the existing regime_policy classifier plus a near_resolution heuristic,
(3) adding shortage-aware score boosting so high-need buckets appear higher in the list,
(4) rejecting one-sided or stale markets before they surface,
(5) surfacing a transparent rank_reason per candidate.

Purpose: The operator's daily workflow (per CORPUS_GOLD_CAPTURE_RUNBOOK.md) starts with
`quickrun --list-candidates 10`. Today that command examines only 20 markets in unordered
Gamma API response order with no bucket awareness. The shortage is sports=15, crypto=10,
politics=9, new_market=5 — these markets are rarely first in the Gamma feed. This change
makes the command materially useful for target selection.

Output: CandidateDiscovery module, updated --list-candidates rendering in CLI, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@docs/specs/SPEC-phase1b-gold-capture-campaign.md
@docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: CandidateDiscovery module — bucket inference, shortage scoring, ranked output</name>
  <files>
    packages/polymarket/simtrader/candidate_discovery.py
    tests/test_simtrader_candidate_discovery.py
  </files>
  <behavior>
    - infer_bucket(raw_market: dict) -> str: uses classify_market_regime from regime_policy; maps regime
      "politics"→"politics", "sports"→"sports", "new_market"→"new_market", then applies near_resolution
      heuristic (end_date within 72h of now → "near_resolution"), crypto keyword heuristic
      (slug/question/category contains "btc|eth|sol|crypto|bitcoin|ethereum" → "crypto"), else "other".
      Pure function, no network. Tested with all 6 bucket outcomes + unknown fallback.
    - score_for_capture(resolved_market: ResolvedMarket, raw_meta: dict, shortage: dict[str,int],
      yes_val: BookValidation, no_val: BookValidation, probe_results: Optional[dict]) -> float:
      Combines: shortage_boost (shortage[bucket] / 15.0, clamped 0..1, weight=0.40),
      depth_score (min(depth_total, 200) / 200.0, weight=0.30), probe_score (1.0 if any active
      else 0.0 if probe ran else 0.5, weight=0.20), spread_score (clamp((ask-bid)/0.15, 0..1), weight=0.10).
      Returns float 0..1. Returns 0.0 when market is one-sided (one_sided_book or empty_book reason on
      either leg). Pure function tested with mocked inputs.
    - rank_reason(bucket: str, shortage: dict, score: float, depth_total: Optional[float],
      probe_active: Optional[bool]) -> str: Returns human-readable string like
      "bucket=sports shortage=15 score=0.87 depth=142 probe=active". Used in CLI display.
    - DiscoveryResult dataclass: slug, question, bucket, score, rank_reason, yes_depth, no_depth,
      probe_summary (str or None).
    - CandidateDiscovery class: __init__(picker: MarketPicker, shortage: dict[str,int]). rank(n,
      pool_size, probe_config, collect_skips, exclude_slugs) -> list[DiscoveryResult]:
      Fetches pool_size raw markets via picker._gamma.fetch_markets_page (with offset iteration to
      fetch multiple pages when pool_size > 100), resolves+validates via auto_pick_many with
      collect_skips, fetches raw Gamma metadata for each resolved market (from the raw_markets list,
      no extra network call), scores each, sorts descending, returns top n.
      pool_size defaults to 200, clamped to max 300. No new external dependencies.
    - Tests: infer_bucket for all 6 buckets, score_for_capture returns 0 for one-sided,
      shortage boost proportional, ranking orders by score descending, empty pool handled gracefully.
      Minimum 12 offline tests.
  </behavior>
  <action>
    Create packages/polymarket/simtrader/candidate_discovery.py.

    Imports needed: from packages.polymarket.simtrader.market_picker import (MarketPicker,
    ResolvedMarket, BookValidation, MarketPickerError); from packages.polymarket.market_selection.
    regime_policy import classify_market_regime; dataclasses, datetime, typing.

    STEP 1: Write tests (RED) in tests/test_simtrader_candidate_discovery.py.
    All imports mocked. Tests cover: infer_bucket each bucket, score_for_capture one-sided returns 0,
    shortage_boost proportional, probe_score 0.5 when no probe, rank orders correctly, empty list ok.
    Run: python -m pytest tests/test_simtrader_candidate_discovery.py -x -q -- expect failures.

    STEP 2: Implement module (GREEN).
    The near_resolution heuristic: parse end_date_iso field from raw_meta dict using
    datetime.fromisoformat; if <= 72 hours from now(UTC) and bucket not already politics/sports/
    crypto → override to "near_resolution".
    The crypto heuristic: check slug + question (lowercased) for keywords btc, eth, sol, crypto,
    bitcoin, ethereum, solana after regime classifier returns "other" or None.
    CandidateDiscovery.rank() implementation:
      1. Collect raw pages: loop fetch_markets_page(limit=100, offset=0), fetch_markets_page(
         limit=100, offset=100) etc. until pool_size reached. Store raw_market dicts indexed by slug.
      2. Call auto_pick_many(n=pool_size, max_candidates=pool_size, ...) to get validated+resolved list.
      3. For each resolved market: look up raw_meta from the slug index (use {} if not found),
         infer bucket, get book validation (re-use collect_skips data if available, else re-validate),
         compute score, build DiscoveryResult.
      4. Filter out score==0.0 (one-sided/empty/failed), sort descending, return top n.

    STEP 3: Run tests (GREEN). Fix until all pass.
    Run: python -m pytest tests/test_simtrader_candidate_discovery.py -x -q
  </action>
  <verify>
    <automated>python -m pytest tests/test_simtrader_candidate_discovery.py -x -q --tb=short</automated>
  </verify>
  <done>
    All tests in test_simtrader_candidate_discovery.py pass (minimum 12 tests).
    Module exists with exported: CandidateDiscovery, DiscoveryResult, infer_bucket, score_for_capture.
    No one-sided market scores above 0. Shortage=15 bucket scores higher than shortage=1 bucket at
    equal depth.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire CandidateDiscovery into quickrun --list-candidates output + regression + dev log</name>
  <files>
    tools/cli/simtrader.py
    docs/dev_logs/2026-03-27_phase1b_candidate_discovery_upgrade.md
  </files>
  <action>
    CHANGE IN tools/cli/simtrader.py (list-candidates block starting at line ~1610):

    1. Replace the existing `picker.auto_pick_many(...)` call block with a CandidateDiscovery.rank()
       call when list_candidates_n > 0 and not args.market.

       Import at top of the block (lazy): from packages.polymarket.simtrader.candidate_discovery
       import CandidateDiscovery.

       Hard-coded shortage dict (to avoid requiring live corpus_audit): read from
       tools/gates/capture_status.py if it can produce a shortage dict, otherwise use the last
       known values inline as a fallback constant. The safest approach: define
       _DEFAULT_SHORTAGE = {"sports": 15, "politics": 9, "crypto": 10, "new_market": 5,
       "near_resolution": 1} as a module-level constant, and use it unless
       --shortage-override is provided (do NOT add this flag yet, just hardcode the constant
       clearly labeled "Phase 1B campaign defaults — update after each capture batch").

       pool_size = min(getattr(args, "max_candidates", 20) * 10, 200). This gives operators
       who leave --max-candidates=20 a pool of 200 but caps at 200. No new CLI flag needed.

    2. Replace the existing print loop with the new DiscoveryResult fields:
       ```
       [candidate {i}] slug     : {result.slug}
       [candidate {i}] question : {result.question}
       [candidate {i}] bucket   : {result.bucket}
       [candidate {i}] score    : {result.score:.2f}
       [candidate {i}] why      : {result.rank_reason}
       [candidate {i}] depth    : YES={result.yes_depth:.1f}  NO={result.no_depth:.1f}
       ```
       If result.probe_summary is not None, add:
       ```
       [candidate {i}] probe    : {result.probe_summary}
       ```

    3. Backward compatibility: --activeness-probe-seconds, --min-probe-updates, --require-active
       flags still wire through to probe_config unchanged. --exclude-market still wires through.
       The "Listed N candidates." final line is preserved.

    4. Keep the existing code path for when list_candidates_n == 0 (normal quickrun flow).
       The only change is replacing what happens when list_candidates_n > 0.

    After editing simtrader.py, verify the CLI still parses:
      python -m polytool simtrader quickrun --help

    Then run full regression:
      python -m pytest tests/ -q --tb=short -x

    If any tests in test_gate2_candidate_ranking.py, test_simtrader_activeness_probe.py, or
    test_scan_gate2_candidates.py fail, fix the issue before proceeding.

    WRITE dev log to docs/dev_logs/2026-03-27_phase1b_candidate_discovery_upgrade.md covering:
    - Files changed and why
    - Old behavior: single fetch_markets_page(limit=20), first-pass results, no bucket
    - New behavior: pool_size=200, bucket inference, shortage boost, one-sided filter
    - Ranking factors and weights (shortage 0.40, depth 0.30, probe 0.20, spread 0.10)
    - Example shortlist output format (use the new print template, fill in sample values)
    - Commands run + test pass/fail counts
    - Shortage constants used (hardcoded Phase 1B defaults)
    - Open questions: auto-refresh shortage from corpus_audit output, tune weights after first
      capture session
  </action>
  <verify>
    <automated>python -m pytest tests/ -q --tb=short -x 2>&1 | tail -5</automated>
  </verify>
  <done>
    python -m polytool simtrader quickrun --help exits 0.
    Full test suite passes (all existing tests preserved, new tests added).
    quickrun --list-candidates output includes bucket, score, why fields.
    Dev log exists at docs/dev_logs/2026-03-27_phase1b_candidate_discovery_upgrade.md.
  </done>
</task>

</tasks>

<verification>
- python -m polytool --help exits 0 (no import errors)
- python -m pytest tests/ -q --tb=short -x passes (all prior tests + >= 12 new discovery tests)
- python -m polytool simtrader quickrun --help exits 0
- python -m pytest tests/test_simtrader_candidate_discovery.py -v shows >= 12 tests passing
- Dev log exists at docs/dev_logs/2026-03-27_phase1b_candidate_discovery_upgrade.md
</verification>

<success_criteria>
- `quickrun --list-candidates 10` draws from a pool of 200 markets not 20
- Output shows bucket, score, why for each candidate
- Sports and crypto buckets (shortage >= 10) appear near the top when present in the pool
- One-sided markets do not appear in the shortlist
- All existing tests continue to pass
- No new external dependencies
- Dev log written
</success_criteria>

<output>
After completion, create `.planning/quick/32-improve-phase-1b-candidate-discovery-bro/32-SUMMARY.md`
</output>
