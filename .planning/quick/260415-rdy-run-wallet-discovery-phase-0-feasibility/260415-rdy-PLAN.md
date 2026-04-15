---
phase: quick-260415-rdy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/discovery/loop_d_probe.py
  - tests/test_loop_d_probe.py
  - docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md
autonomous: true
requirements: [LOOP-D-FEASIBILITY]

must_haves:
  truths:
    - "Feasibility verdict (READY / READY WITH CONSTRAINTS / BLOCKED) is documented with evidence"
    - "Gamma API bootstrap yields a concrete token-ID count for current platform state"
    - "ClobStreamClient gaps for Loop D are cataloged with specific code references"
    - "Anomaly-detector data sufficiency is assessed against last_trade_price event schema"
    - "Reconnection and backfill constraints are documented with specific protocol requirements"
  artifacts:
    - path: "packages/polymarket/discovery/loop_d_probe.py"
      provides: "Minimal probe helpers: Gamma bootstrap token counter, WS event fixture parser, ClobStreamClient gap audit"
    - path: "tests/test_loop_d_probe.py"
      provides: "Deterministic offline tests for probe helpers"
    - path: "docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md"
      provides: "Feasibility dev log with verdict, constraints matrix, evidence, next blockers"
  key_links:
    - from: "packages/polymarket/discovery/loop_d_probe.py"
      to: "packages/polymarket/gamma.py"
      via: "imports GammaClient.fetch_all_markets for bootstrap scale measurement"
      pattern: "from.*gamma.*import"
    - from: "tests/test_loop_d_probe.py"
      to: "packages/polymarket/discovery/loop_d_probe.py"
      via: "imports probe functions and validates with fixtures"
      pattern: "from.*loop_d_probe.*import"
---

<objective>
Determine whether the PolyTool repo can support the managed CLOB subscription and
anomaly-detection substrate that the roadmap assumes for Loop D of wallet discovery.

Purpose: Loop D requires platform-wide WebSocket streaming of all active markets and
real-time anomaly detection on the trade stream. Before building it, we need evidence-based
answers to three questions: (1) Can we bootstrap and maintain subscriptions to all active
markets? (2) Does the trade-event schema provide enough data for anomaly detectors?
(3) What reconnection/backfill/scaling constraints exist?

Output: A feasibility dev log with a READY / READY WITH CONSTRAINTS / BLOCKED verdict,
plus minimal probe code with deterministic tests that produce the evidence supporting
that verdict.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@docs/PLAN_OF_RECORD.md
@docs/CURRENT_STATE.md
@docs/ARCHITECTURE.md

Key existing code the executor needs to understand:

<interfaces>
<!-- ClobStreamClient — the existing WS client that Loop D would extend/adapt -->
From packages/polymarket/crypto_pairs/clob_stream.py:
```python
WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_STALE_THRESHOLD_S = 5.0
DEFAULT_RECV_TIMEOUT_S = 5.0
DEFAULT_RECONNECT_SLEEP_S = 1.0

class ClobStreamClient:
    # Designed for small token sets (crypto pair bot: 4-8 tokens)
    # Key gaps for Loop D:
    #   - No PING keepalive (WS requires PING every 10s)
    #   - No dynamic subscribe/unsubscribe at runtime
    #   - No new_market / market_resolved event handling
    #   - No platform-wide subscription management
    # Has: _event_source injection for offline testing, _time_fn for clock injection
    # Subscribe message format:
    #   {"assets_ids": [...], "type": "market",
    #    "custom_feature_enabled": True, "initial_dump": True}
```

<!-- Gamma API client — bootstrap source for all active market token IDs -->
From packages/polymarket/gamma.py:
```python
@dataclass
class Market:
    condition_id: str
    market_slug: str
    question: str
    clob_token_ids: list[str]
    active: bool
    accepting_orders: Optional[bool]
    # ... other fields

    def to_market_tokens(self) -> list[MarketToken]:
        """Extract MarketToken entries from this market."""

@dataclass
class MarketsFetchResult:
    markets: list[Market]
    market_tokens: list[MarketToken]
    token_aliases: list[TokenAlias]

class GammaClient:
    def fetch_all_markets(
        self,
        max_pages: int = 50,
        page_size: int = 100,
        active_only: bool = True,
    ) -> MarketsFetchResult:
        """Fetch all markets with pagination."""
```

<!-- Wallet Discovery v1 — DO NOT modify, but neighbor new probe code here -->
From packages/polymarket/discovery/__init__.py:
```python
# 11 exports: 8 Loop A models + 3 MVF
# Loop D probe code goes in same package as a new file
# but MUST NOT import from or modify any v1 modules
```

<!-- CLOB WS trade event schema (from research docs) -->
```json
{
  "event_type": "last_trade_price",
  "asset_id": "0x...",
  "price": "0.55",
  "size": "100",
  "side": "BUY",
  "timestamp": "1712345678",
  "fee_rate_bps": "200",
  "market": "slug-name"
}
// NOTE: No wallet address in trade events.
// Wallet attribution requires separate Alchemy eth_getLogs feed.
```

<!-- WS protocol requirements (from research docs) -->
- PING every 10 seconds required
- Subscribe per-asset_id (no wildcard "all markets" mode)
- Dynamic subscribe/unsubscribe without reconnecting IS supported
- new_market / market_resolved events for lifecycle management
- No replay on disconnect; backfill via REST GET /trades
- No documented subscription limit per connection
</interfaces>

Key research documents (executor should read for evidence):
@docs/obsidian-vault/09-Decisions/Decision - Loop D Managed CLOB Subscription.md
@docs/obsidian-vault/08-Research/01-Wallet-Discovery-Pipeline.md
@docs/obsidian-vault/11-Prompt-Archive/2026-04-09 GLM5 - CLOB WebSocket and Alchemy CU.md
@docs/specs/SPEC-wallet-discovery-v1.md (Loop D blockers section)
@docs/features/wallet-discovery-v1.md
</context>

<constraints>
HARD CONSTRAINTS — violation = plan failure:
- DO NOT touch Loop B/C production code
- DO NOT modify any Wallet Discovery v1 behavior (models.py, mvf.py, loop_a.py, etc.)
- DO NOT touch Track 2 files (crypto_pairs/, pair_engine.py, reference_feed.py)
- DO NOT touch n8n or Grafana configuration
- DO NOT implement full Loop D — this is feasibility assessment only
- Build minimal probe code ONLY for reproducible verdicts
- Add deterministic tests for any new helpers
- Run existing tests after to prove zero regressions
</constraints>

<tasks>

<task type="auto">
  <name>Task 1: Build Loop D feasibility probe helpers and tests</name>
  <files>packages/polymarket/discovery/loop_d_probe.py, tests/test_loop_d_probe.py</files>
  <action>
Create `packages/polymarket/discovery/loop_d_probe.py` with these minimal probe helpers:

1. **`count_subscribable_tokens(markets: list) -> dict`**
   Accept a list of Market-like dicts (or Market dataclasses) and return:
   - `total_markets`: count of markets
   - `total_tokens`: count of all clob_token_ids across markets
   - `accepting_orders_tokens`: count of tokens where market.accepting_orders is True
   - `category_breakdown`: dict of category -> token count
   This function does NOT call the network. It is a pure data summarizer for Gamma API results.
   Include a convenience wrapper `bootstrap_token_inventory(gamma_client)` that calls
   `gamma_client.fetch_all_markets(active_only=True)` and passes the result to
   `count_subscribable_tokens`. This wrapper is for live use only (not tested offline).

2. **`audit_clob_stream_gaps() -> list[dict]`**
   Return a static list of identified gaps in ClobStreamClient for Loop D use. Each entry:
   `{"gap_id": str, "description": str, "severity": "blocker"|"constraint"|"enhancement",
     "code_ref": str, "remediation": str}`.
   Gaps to catalog (read clob_stream.py to confirm each):
   - No PING keepalive (blocker — WS will disconnect after ~30s without PING)
   - No dynamic subscribe/unsubscribe (blocker — cannot add new markets at runtime)
   - No new_market/market_resolved event parsing (constraint — must be added for lifecycle)
   - Fixed token set at construction (constraint — constructor takes asset_ids, no add/remove)
   - No reconnect backfill (enhancement — REST /trades backfill on reconnect)

3. **`assess_trade_event_sufficiency(sample_events: list[dict]) -> dict`**
   Accept a list of last_trade_price event dicts (fixtures) and return:
   - `fields_present`: set of field names found across all events
   - `fields_needed_for_detectors`: dict mapping detector name to required fields:
     * "volume_spike": ["asset_id", "size", "timestamp"]
     * "price_anomaly": ["asset_id", "price", "timestamp"]
     * "trade_burst": ["asset_id", "timestamp", "side"]
     * "spread_divergence": ["asset_id", "price", "side", "timestamp"]
     * "wallet_attribution": ["maker_address", "taker_address"] (these are NOT in CLOB events)
   - `detector_readiness`: dict mapping detector name to {"ready": bool, "missing_fields": list}
   - `wallet_attribution_note`: string explaining that CLOB events lack wallet addresses and
     Alchemy eth_getLogs is required as the second feed

4. **`format_feasibility_verdict(token_inventory: dict, gaps: list, sufficiency: dict) -> dict`**
   Combine all three assessments into a structured verdict:
   - `verdict`: "READY" | "READY_WITH_CONSTRAINTS" | "BLOCKED"
   - Logic: BLOCKED if any gap has severity "blocker" AND no remediation path;
     READY_WITH_CONSTRAINTS if blockers exist but all have clear remediation;
     READY if no blockers.
   - `constraints`: list of constraint strings
   - `blockers`: list of blocker strings (empty if not BLOCKED)
   - `scale_assessment`: summary of token counts and throughput estimate
   - `next_steps`: list of recommended actions

Do NOT modify `packages/polymarket/discovery/__init__.py` — the probe module is standalone.
Do NOT import from any v1 module (models, mvf, loop_a, etc.).
The only import from the broader codebase is `GammaClient` / `Market` types (for type hints
in the convenience wrapper only).

Then create `tests/test_loop_d_probe.py` with deterministic offline tests:

- **TestCountSubscribableTokens** (4-5 tests):
  - Empty market list returns zeros
  - Single market with 2 tokens counted correctly
  - Multiple markets across categories produce correct category_breakdown
  - Markets with accepting_orders=False are counted in total but not in accepting_orders_tokens
  - Large fixture (simulate 500 markets, 1000 tokens) runs without error and returns correct totals

- **TestAuditClobStreamGaps** (2-3 tests):
  - Returns non-empty list
  - All entries have required keys (gap_id, description, severity, code_ref, remediation)
  - At least 2 entries have severity "blocker"

- **TestAssessTradeEventSufficiency** (3-4 tests):
  - Fixture with full last_trade_price fields: volume_spike, price_anomaly, trade_burst,
    spread_divergence all show ready=True; wallet_attribution shows ready=False
  - Fixture with missing "size" field: volume_spike shows ready=False, others still correct
  - Empty event list: all detectors show ready=False (no fields present)
  - wallet_attribution_note is always non-empty

- **TestFormatFeasibilityVerdict** (3 tests):
  - With blocker gaps that have remediation: verdict is READY_WITH_CONSTRAINTS
  - With no blocker gaps: verdict is READY
  - Verify constraints and next_steps are non-empty lists

After writing the probe and tests, run:
```
python -m pytest tests/test_loop_d_probe.py -v --tb=short -x
```
All tests must pass.

Then run the existing discovery area tests to prove zero regressions:
```
python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short
```
All 118 tests must still pass.

Then run a broader regression check:
```
python -m pytest tests/ -q --tb=no --deselect tests/test_ris_phase2_cloud_provider_routing.py -x
```
  </action>
  <verify>
    <automated>python -m pytest tests/test_loop_d_probe.py -v --tb=short -x</automated>
  </verify>
  <done>
    - loop_d_probe.py exists with 4 functions: count_subscribable_tokens, audit_clob_stream_gaps, assess_trade_event_sufficiency, format_feasibility_verdict
    - test_loop_d_probe.py exists with 12+ deterministic offline tests, all passing
    - Existing 118 discovery-area tests still pass (zero regressions)
    - Full project test suite shows no regressions from probe code addition
  </done>
</task>

<task type="auto">
  <name>Task 2: Write feasibility dev log with evidence-backed verdict</name>
  <files>docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md</files>
  <action>
Create `docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md` — the comprehensive
feasibility assessment for Loop D managed CLOB subscription.

Structure the dev log as follows:

**Header:**
```
# 2026-04-15 — Wallet Discovery Loop D: Phase 0 Feasibility Assessment
```

**## Objective**
One paragraph: determine if PolyTool can support the managed CLOB subscription and
anomaly-detection substrate Loop D requires. Reference SPEC-wallet-discovery-v1.md
which explicitly lists the three Loop D blockers this assessment addresses.

**## Verdict**

Run the probe functions from Task 1 to produce the actual verdict. Use the output of
`format_feasibility_verdict()` as the authoritative source. Present the verdict prominently:

```
VERDICT: [READY / READY_WITH_CONSTRAINTS / BLOCKED]
```

Expected verdict based on analysis: **READY WITH CONSTRAINTS** because:
- The managed subscription pattern is viable (Gamma API bootstrap exists, WS protocol supports it)
- But ClobStreamClient needs non-trivial adaptation (PING, dynamic sub/unsub, lifecycle events)
- And anomaly detection works for pattern detection but NOT wallet attribution without Alchemy

**## Evidence: Subscription Scale**

Run `bootstrap_token_inventory()` against the live Gamma API (or document the expected
scale from research: typically 400-800 active markets, 800-1600+ token IDs).
If live Gamma is available, include actual numbers. If not, use the fixture-based
`count_subscribable_tokens()` with a realistic synthetic fixture and note "synthetic estimate."

Include:
- Total active markets and tokens
- Category breakdown
- accepting_orders count
- Throughput estimate: 150k-300k trades/day = 2-3/sec average, 50/sec peaks
- Single Python process capacity: 10k+ msg/sec (from research doc)
- Conclusion: throughput is NOT a bottleneck

**## Evidence: ClobStreamClient Gap Audit**

Include the full output of `audit_clob_stream_gaps()` as a table:

| Gap ID | Severity | Description | Code Reference | Remediation |
|--------|----------|-------------|----------------|-------------|
| ... | ... | ... | ... | ... |

For each blocker-severity gap, explain why it is remediable (all involve adding
well-understood WS functionality, no unknown protocol constraints).

**## Evidence: Anomaly Detector Data Sufficiency**

Include the full output of `assess_trade_event_sufficiency()` as a table:

| Detector | Required Fields | Available | Ready | Missing |
|----------|----------------|-----------|-------|---------|
| volume_spike | asset_id, size, timestamp | Yes | Yes | - |
| price_anomaly | asset_id, price, timestamp | Yes | Yes | - |
| trade_burst | asset_id, timestamp, side | Yes | Yes | - |
| spread_divergence | asset_id, price, side, timestamp | Yes | Yes | - |
| wallet_attribution | maker_address, taker_address | No | No | Both fields |

Document the two-feed architecture constraint: CLOB detects WHAT is anomalous (which
market, when). Alchemy eth_getLogs tells WHO did it (wallet addresses). This is by design
per the accepted decision doc, not a bug.

**## Reconnection and Backfill Constraints**

Document from research:
- No WS replay: disconnect loses events. Backfill via REST `GET /trades` endpoint.
- PING required every 10s (not in current ClobStreamClient).
- Re-bootstrap on reconnect: re-fetch active markets from Gamma, re-subscribe all tokens.
- No documented subscription limit per connection (but untested at scale).
- Recommendation: implement with a reconnect counter and exponential backoff.

**## Constraints Matrix**

| Constraint | Category | Severity | Remediation Complexity | Notes |
|------------|----------|----------|------------------------|-------|
| No PING in ClobStreamClient | Protocol | Blocker | Low | Add threading.Timer or select-based ping |
| No dynamic sub/unsub | Architecture | Blocker | Medium | Refactor ClobStreamClient or build new ManagedSubscriptionClient |
| No lifecycle event handling | Protocol | Constraint | Low | Parse new_market/market_resolved JSON |
| No wallet address in CLOB events | Data | Constraint | N/A (by design) | Requires Alchemy second feed |
| No backfill on reconnect | Reliability | Enhancement | Medium | REST /trades paginated fetch |
| Subscription limit unknown | Scale | Risk | Unknown | Needs live probe (not done in feasibility) |

**## ClobStreamClient Adaptation Requirements**

Enumerate what must change in ClobStreamClient (or a new class) to support Loop D:
1. Add PING keepalive timer (10s interval)
2. Add `subscribe(asset_ids)` / `unsubscribe(asset_ids)` runtime methods
3. Add `new_market` / `market_resolved` event parsing and callbacks
4. Remove constructor-time-only token-set assumption
5. Add reconnect backfill hook (call REST /trades on reconnect for missed window)
6. Add platform-wide subscription manager (bootstrap from Gamma, maintain via lifecycle events)

Note: These are implementation requirements for the future Loop D build phase, NOT
for this feasibility assessment.

**## Next Blockers (for Loop D implementation)**

1. Build or extend ClobStreamClient with PING + dynamic subscription
2. Live probe: subscribe to all active tokens on a single connection, measure stability over 1h
3. Alchemy eth_getLogs cost estimate for wallet attribution feed
4. Choose anomaly detector algorithms (binomial win-rate first per research doc)
5. ClickHouse schema design for anomaly events

**## Test Commands Run**

Include exact commands and results:
```
python -m pytest tests/test_loop_d_probe.py -v --tb=short -x
# Result: NN passed in X.XXs

python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short
# Result: 118 passed in X.XXs

python -m pytest tests/ -q --tb=no --deselect tests/test_ris_phase2_cloud_provider_routing.py
# Result: NNNN passed, NN deselected, NN warnings
```

**## Commits**

| Hash | Message |
|---|---|
| (filled after commit) | ... |

**## Codex Review**

Tier: Skip (probe-only + feasibility doc — no execution, strategy, or CH write paths modified).
  </action>
  <verify>
    <automated>python -c "import pathlib; p=pathlib.Path('docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md'); assert p.exists(); text=p.read_text(); assert 'VERDICT' in text; assert 'READY' in text; assert 'Constraints Matrix' in text; assert 'Test Commands Run' in text; print('Dev log structure verified')"</automated>
  </verify>
  <done>
    - Dev log exists at docs/dev_logs/2026-04-15_wallet_discovery_loop_d_pof.md
    - Contains VERDICT with one of: READY / READY_WITH_CONSTRAINTS / BLOCKED
    - Contains Evidence sections for subscription scale, gap audit, and data sufficiency
    - Contains Constraints Matrix table
    - Contains ClobStreamClient Adaptation Requirements
    - Contains Next Blockers for Loop D implementation
    - Contains Test Commands Run with actual pass/fail counts
    - Codex Review tier documented
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Gamma API (read-only) | Fetching active market list — public API, no auth required |
| CLOB WS (not connected) | Feasibility assessment only — no live WS connection in this plan |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-rdy-01 | I (Info Disclosure) | loop_d_probe.py | accept | Probe code is read-only analysis; no secrets, no PII, no live connections |
| T-rdy-02 | T (Tampering) | Gamma API response | accept | Feasibility only — no decisions made on untrusted data without human review |
</threat_model>

<verification>
1. `python -m pytest tests/test_loop_d_probe.py -v --tb=short -x` — all probe tests pass
2. `python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short` — 118 discovery tests pass (zero regressions)
3. `python -m pytest tests/ -q --tb=no --deselect tests/test_ris_phase2_cloud_provider_routing.py -x` — full suite passes
4. `python -m polytool --help` — CLI loads without import errors
5. Dev log contains VERDICT, Constraints Matrix, and all evidence sections
</verification>

<success_criteria>
- Feasibility verdict is documented with evidence (not opinion)
- Probe code is minimal, deterministic, fully tested offline
- Zero regressions in existing test suite
- Dev log is the single artifact an operator reads to decide whether to greenlight Loop D planning
</success_criteria>

<output>
After completion, the executor writes a SUMMARY to:
`.planning/quick/260415-rdy-run-wallet-discovery-phase-0-feasibility/260415-rdy-SUMMARY.md`
</output>
