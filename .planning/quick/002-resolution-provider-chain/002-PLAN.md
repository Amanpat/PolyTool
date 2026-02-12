---
phase: quick-002
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/resolution.py
  - packages/polymarket/on_chain_ctf.py
  - packages/polymarket/subgraph.py
  - tests/test_resolution_providers.py
  - .env.example
  - docs/ROADMAP.md
  - docs/adr/0003-roadmap-renumbering.md
autonomous: true

must_haves:
  truths:
    - "OnChainCTFProvider resolves WIN/LOSS for a known resolved conditionId via Polygon RPC"
    - "OnChainCTFProvider returns PENDING for unresolved conditionId (payoutDenominator == 0)"
    - "SubgraphResolutionProvider resolves WIN/LOSS from The Graph subgraph query"
    - "CachedResolutionProvider cascades: ClickHouse -> OnChainCTF -> Subgraph -> Gamma -> None"
    - "Every resolution carries explicit resolution_source and reason fields"
    - "Unit tests pass with mocked RPC and subgraph responses"
  artifacts:
    - path: "packages/polymarket/on_chain_ctf.py"
      provides: "OnChainCTFProvider using raw JSON-RPC eth_call"
      exports: ["OnChainCTFProvider"]
    - path: "packages/polymarket/subgraph.py"
      provides: "SubgraphResolutionProvider querying The Graph"
      exports: ["SubgraphResolutionProvider"]
    - path: "packages/polymarket/resolution.py"
      provides: "Updated Resolution dataclass (reason field) and CachedResolutionProvider (4-stage chain)"
      contains: "on_chain_ctf_provider"
    - path: "tests/test_resolution_providers.py"
      provides: "Unit tests for OnChainCTF, Subgraph, and updated CachedResolutionProvider"
    - path: "docs/adr/0003-roadmap-renumbering.md"
      provides: "ADR for roadmap renumbering"
  key_links:
    - from: "packages/polymarket/on_chain_ctf.py"
      to: "Polygon RPC (POLYGON_RPC_URL)"
      via: "requests.post with JSON-RPC eth_call"
      pattern: "eth_call.*payoutDenominator"
    - from: "packages/polymarket/subgraph.py"
      to: "The Graph (POLYMARKET_SUBGRAPH_URL)"
      via: "requests.post with GraphQL query"
      pattern: "conditions.*payoutNumerators"
    - from: "packages/polymarket/resolution.py"
      to: "on_chain_ctf.py and subgraph.py"
      via: "CachedResolutionProvider constructor params"
      pattern: "on_chain_ctf_provider.*subgraph_provider"
---

<objective>
Reduce UNKNOWN_RESOLUTION materially by implementing a resolution provider chain
that reads on-chain CTF payout state from Polygon, with subgraph fallback.
Also update docs/ROADMAP.md to reflect the Roadmap 0-8 plan and add an ADR for
roadmap renumbering.

Purpose: UNKNOWN_RESOLUTION is the primary data-quality gap in the scan pipeline.
On-chain CTF payouts are the authoritative source of truth and never lag behind
the Gamma API. Adding this provider closes the gap for any market that has been
resolved on-chain but not yet reflected in Gamma.

Output:
- `packages/polymarket/on_chain_ctf.py` -- OnChainCTFProvider
- `packages/polymarket/subgraph.py` -- SubgraphResolutionProvider
- Updated `packages/polymarket/resolution.py` -- 4-stage CachedResolutionProvider + reason field
- `tests/test_resolution_providers.py` -- unit tests
- Updated `.env.example` with POLYGON_RPC_URL and POLYMARKET_SUBGRAPH_URL
- Updated `docs/ROADMAP.md` -- Roadmap 3 = Resolution Coverage
- `docs/adr/0003-roadmap-renumbering.md`
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@packages/polymarket/resolution.py
@packages/polymarket/gamma.py
@packages/polymarket/http_client.py
@packages/polymarket/normalization.py
@pyproject.toml
@.env.example
@docs/ROADMAP.md
@docs/adr/0001-template.md
@infra/clickhouse/initdb/17_resolutions.sql
@tests/test_token_resolution.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement OnChainCTFProvider and SubgraphResolutionProvider</name>
  <files>
    packages/polymarket/on_chain_ctf.py
    packages/polymarket/subgraph.py
    packages/polymarket/resolution.py
    .env.example
  </files>
  <action>
**1a. Add `reason` field to `Resolution` dataclass in `resolution.py`:**

Update the `Resolution` dataclass to include an optional `reason: str = ""` field.
This provides human-readable context for how the resolution was determined (e.g.,
"payoutDenominator=1000000, outcomeIndex=0 has payoutNumerator=1000000" or
"subgraph condition resolved=true, payouts=[1,0]").

**1b. Create `packages/polymarket/on_chain_ctf.py`:**

Implement `OnChainCTFProvider` that resolves market outcomes by reading the
ConditionalTokens (CTF) contract on Polygon via raw JSON-RPC `eth_call`.

Key implementation details:

- CTF contract address: `0x4D97DCd97eC945f40cF65F87097ACe5EA0476045`
- Polygon RPC URL from `os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")`
- Use `requests.post` for JSON-RPC calls (no web3.py dependency)
- Timeout: 10 seconds per RPC call

Two contract view functions to call:

1. `payoutDenominator(bytes32 conditionId)` -- selector: `0xda35a26f`
   - ABI-encode: `0xda35a26f` + conditionId zero-padded to 32 bytes
   - If result == 0: market is PENDING (not yet resolved on-chain). Return None.
   - If result > 0: market is resolved, proceed to step 2.

2. `payoutNumerators(bytes32 conditionId, uint256 outcomeIndex)` -- selector: `0x20135e58`
   - ABI-encode: `0x20135e58` + conditionId (32 bytes) + outcomeIndex (32 bytes uint256)
   - Call for outcomeIndex 0 and 1 (binary markets)
   - The winning outcome has payoutNumerator == payoutDenominator
   - The losing outcome has payoutNumerator == 0

The provider needs `condition_id` and `outcome_index` to determine settlement.
Since the existing `ResolutionProvider` protocol takes `(condition_id, outcome_token_id)`,
add an optional `outcome_index: Optional[int] = None` parameter to `get_resolution()`.
When outcome_index is None, query both indices (0 and 1) and return the result for
the token that matches. The caller should pass outcome_index when known.

Provider class structure:
```python
class OnChainCTFProvider:
    CTF_ADDRESS = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
    PAYOUT_DENOMINATOR_SELECTOR = "0xda35a26f"
    PAYOUT_NUMERATORS_SELECTOR = "0x20135e58"

    def __init__(self, rpc_url: str | None = None, timeout: float = 10.0):
        self.rpc_url = rpc_url or os.environ.get("POLYGON_RPC_URL", "https://polygon-rpc.com")
        self.timeout = timeout

    def _eth_call(self, data: str) -> str | None:
        """Execute eth_call against CTF contract. Returns hex result or None on error."""
        # JSON-RPC payload: {"jsonrpc":"2.0","method":"eth_call","params":[{"to":CTF_ADDRESS,"data":data},"latest"],"id":1}
        # Parse response["result"], return None on error/timeout

    def _encode_condition_id(self, condition_id: str) -> str:
        """Ensure condition_id is 32-byte hex (strip 0x, left-pad to 64 chars)."""

    def get_payout_denominator(self, condition_id: str) -> int | None:
        """Call payoutDenominator(conditionId). Returns int or None on failure."""

    def get_payout_numerator(self, condition_id: str, outcome_index: int) -> int | None:
        """Call payoutNumerators(conditionId, outcomeIndex). Returns int or None."""

    def get_resolution(self, condition_id: str, outcome_token_id: str, outcome_index: int | None = None) -> Resolution | None:
        """Resolve using on-chain CTF payout data.
        If outcome_index is None, check both 0 and 1.
        Returns Resolution with resolution_source="on_chain_ctf" and descriptive reason.
        """
```

Handle errors gracefully: log warnings and return None (let chain fall through to next provider).

**1c. Create `packages/polymarket/subgraph.py`:**

Implement `SubgraphResolutionProvider` that queries The Graph for CTF condition data.

- Subgraph URL from `os.environ.get("POLYMARKET_SUBGRAPH_URL", "https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic")`
- Use `requests.post` with a GraphQL query
- Timeout: 15 seconds

GraphQL query:
```graphql
{
  condition(id: "<conditionId_lowercase_no_0x>") {
    id
    resolved
    payoutNumerators
    payoutDenominator
    resolutionTimestamp
  }
}
```

Note: The Graph indexes conditionId as lowercase hex WITHOUT the 0x prefix.
Strip 0x and lowercase before querying.

Provider class structure:
```python
class SubgraphResolutionProvider:
    def __init__(self, subgraph_url: str | None = None, timeout: float = 15.0):
        self.subgraph_url = subgraph_url or os.environ.get("POLYMARKET_SUBGRAPH_URL", ...)
        self.timeout = timeout

    def get_resolution(self, condition_id: str, outcome_token_id: str, outcome_index: int | None = None) -> Resolution | None:
        """Query subgraph for condition resolution.
        Returns Resolution with resolution_source="subgraph" and descriptive reason.
        """
```

If `resolved` is false or payoutNumerators is empty, return None.
If resolved, determine winner from payoutNumerators array (winner has nonzero value).

**1d. Update `CachedResolutionProvider` in `resolution.py`:**

- Add `on_chain_ctf_provider` and `subgraph_provider` constructor params (both Optional)
- Update `get_resolution()` chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma -> None
- Update `get_resolutions_batch()` similarly: after ClickHouse batch, iterate remaining
  through on_chain_ctf, then subgraph, then gamma
- When all providers return None, do NOT create a Resolution with UNKNOWN_RESOLUTION.
  Return None as before -- the caller (`determine_resolution_outcome`) already handles None
  by returning PENDING or UNKNOWN_RESOLUTION based on context.

**1e. Update `.env.example`:**

Add these lines after the existing Polymarket API Configuration section:
```
# Polygon RPC for on-chain CTF resolution
POLYGON_RPC_URL=https://polygon-rpc.com

# The Graph subgraph for Polymarket CTF conditions (fallback)
POLYMARKET_SUBGRAPH_URL=https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic
```

**Important anti-patterns to AVOID:**
- Do NOT add web3.py as a dependency. Use raw `requests.post` for JSON-RPC.
- Do NOT silently swallow errors. Always `logger.warning()` on failures.
- Do NOT hardcode RPC URLs. Always read from env with sensible defaults.
- Do NOT modify the `ResolutionProvider` Protocol signature (it uses structural typing;
  the new providers just need to match the duck-typed interface).
  Actually -- the Protocol has `get_resolution(condition_id, outcome_token_id)` without
  outcome_index. The new providers accept outcome_index as an OPTIONAL keyword arg,
  which is compatible with the Protocol (callers without it still work).
  </action>
  <verify>
- `python -c "from packages.polymarket.on_chain_ctf import OnChainCTFProvider; print('OK')"` succeeds
- `python -c "from packages.polymarket.subgraph import SubgraphResolutionProvider; print('OK')"` succeeds
- `python -c "from packages.polymarket.resolution import CachedResolutionProvider, Resolution; r = Resolution('cid','tid',1.0,None,'test','reason'); print(r.reason)"` prints "reason"
- Grep `.env.example` for POLYGON_RPC_URL and POLYMARKET_SUBGRAPH_URL
  </verify>
  <done>
- `on_chain_ctf.py` exists with OnChainCTFProvider class using raw JSON-RPC eth_call
- `subgraph.py` exists with SubgraphResolutionProvider class using GraphQL query
- `Resolution` dataclass has `reason` field (str, default "")
- `CachedResolutionProvider` accepts 4 providers and cascades in order
- `.env.example` includes POLYGON_RPC_URL and POLYMARKET_SUBGRAPH_URL
  </done>
</task>

<task type="auto">
  <name>Task 2: Unit tests for resolution provider chain</name>
  <files>
    tests/test_resolution_providers.py
  </files>
  <action>
Create `tests/test_resolution_providers.py` with unit tests using `unittest` and
`unittest.mock`. Follow the project pattern: `sys.path.insert(0, ...)` at top.

**Test cases for OnChainCTFProvider:**

1. `test_onchain_resolved_win` -- Mock `requests.post` to return:
   - payoutDenominator call: result = hex(1000000) (nonzero => resolved)
   - payoutNumerators(conditionId, 0): result = hex(1000000) (winner)
   - payoutNumerators(conditionId, 1): result = hex(0) (loser)
   - Call `get_resolution(condition_id="0xabc123...", outcome_token_id="token1", outcome_index=0)`
   - Assert: resolution.settlement_price == 1.0, resolution.resolution_source == "on_chain_ctf"
   - Assert: resolution.reason contains "payoutDenominator" and "payoutNumerator"

2. `test_onchain_resolved_loss` -- Same mock but call with outcome_index=1
   - Assert: resolution.settlement_price == 0.0

3. `test_onchain_pending` -- Mock payoutDenominator returning hex(0)
   - Assert: get_resolution returns None (PENDING means "not resolved yet", chain falls through)

4. `test_onchain_rpc_error` -- Mock requests.post raising `requests.exceptions.Timeout`
   - Assert: get_resolution returns None (graceful fallback)

5. `test_onchain_no_outcome_index` -- Mock same as test 1 but call WITHOUT outcome_index
   - Provider should query both indices, return result for whichever matches
   - For outcome_token_id context, it should return resolutions for both indices 0 and 1

**Test cases for SubgraphResolutionProvider:**

6. `test_subgraph_resolved` -- Mock requests.post returning JSON:
   ```json
   {"data":{"condition":{"id":"abc123","resolved":true,"payoutNumerators":["1000000","0"],"payoutDenominator":"1000000","resolutionTimestamp":"1700000000"}}}
   ```
   - Call with outcome_index=0
   - Assert: resolution.settlement_price == 1.0, resolution_source == "subgraph"

7. `test_subgraph_not_resolved` -- Mock with `resolved: false`
   - Assert: get_resolution returns None

8. `test_subgraph_error` -- Mock requests.post raising ConnectionError
   - Assert: returns None

**Test cases for CachedResolutionProvider chain:**

9. `test_chain_clickhouse_hit` -- ClickHouse returns resolution
   - Assert: result comes from ClickHouse, OnChainCTF/Subgraph/Gamma never called

10. `test_chain_falls_through_to_onchain` -- ClickHouse returns None, OnChainCTF returns resolution
    - Assert: result.resolution_source == "on_chain_ctf"

11. `test_chain_falls_through_to_subgraph` -- ClickHouse and OnChainCTF return None, Subgraph returns resolution
    - Assert: result.resolution_source == "subgraph"

12. `test_chain_falls_through_to_gamma` -- ClickHouse, OnChainCTF, Subgraph all None, Gamma returns resolution
    - Assert: result.resolution_source == "gamma"

13. `test_chain_all_none` -- All providers return None
    - Assert: result is None

Use `unittest.mock.patch("requests.post")` for RPC/subgraph mocks.
Use `unittest.mock.MagicMock()` for ClickHouse and Gamma provider mocks
(they are injected as constructor args, easy to mock).

Helper function to build a mock JSON-RPC response:
```python
def mock_rpc_response(result_hex: str):
    resp = MagicMock()
    resp.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": result_hex}
    resp.raise_for_status = MagicMock()
    return resp
```
  </action>
  <verify>
Run: `python -m pytest tests/test_resolution_providers.py -v --tb=short`
All tests pass. No imports fail.
  </verify>
  <done>
- 13 test cases covering OnChainCTF, Subgraph, and CachedResolutionProvider chain
- All tests use mocked HTTP responses (no real network calls)
- Tests verify resolution_source, settlement_price, reason fields
- Tests verify graceful error handling (timeouts, connection errors)
- Full test suite still passes: `python -m pytest tests/ -v --tb=short`
  </done>
</task>

<task type="auto">
  <name>Task 3: Update ROADMAP.md and add ADR for roadmap renumbering</name>
  <files>
    docs/ROADMAP.md
    docs/adr/0003-roadmap-renumbering.md
  </files>
  <action>
**3a. Update `docs/ROADMAP.md`:**

Change Roadmap 3 from "Hypothesis Validation Loop" to "Resolution Coverage".
Move the current Roadmap 3 content to Roadmap 4, and shift all subsequent roadmaps
by +1. The new structure:

- Roadmap 0 - Foundation [COMPLETE] (unchanged)
- Roadmap 1 - Examination Pipeline [COMPLETE] (unchanged)
- Roadmap 2 - Trust Artifacts & Scan Canonicalization [COMPLETE] (unchanged)
- **Roadmap 3 - Resolution Coverage [IN PROGRESS]** (NEW)
  - [ ] OnChainCTFProvider reading CTF payout state from Polygon RPC
  - [ ] SubgraphResolutionProvider as fallback via The Graph
  - [ ] 4-stage CachedResolutionProvider chain (ClickHouse -> OnChainCTF -> Subgraph -> Gamma)
  - [ ] Resolution dataclass with explicit `reason` field for traceability
  - [ ] Unit tests for all resolution providers with mocked RPC/subgraph
  - [ ] Reduce `UNKNOWN_RESOLUTION` rate for resolved markets to near-zero
  - **Acceptance**: `UNKNOWN_RESOLUTION` rate for markets that are objectively resolved
    on-chain drops to < 5%. All resolution sources carry explicit `resolution_source`
    and `reason` fields. Unit tests pass with mocked providers.
  - **Kill condition**: If Gamma API coverage is already sufficient (>95% resolved
    markets covered), defer on-chain provider to a future milestone.
- **Roadmap 4 - Hypothesis Validation Loop [NOT STARTED]** (was Roadmap 3)
  - Keep all existing items from old Roadmap 3
  - Update acceptance and kill condition text to reference "Roadmap 4"
  - Update the global kill condition: "No backtesting until Roadmap 4 hypothesis validation is done."
- Roadmap 5 - Source Caching & Crawl (was Roadmap 4)
- Roadmap 6 - MCP Hardening (was Roadmap 5)
- Roadmap 7 - Multi-User & Comparison (was Roadmap 6)
- Roadmap 8 - CLI & Dashboard Polish (was Roadmap 7)
- Roadmap 9 - CI & Testing (was Roadmap 8)

Update the "Kill / Stop Conditions (Global)" section:
- Change "No backtesting until Roadmap 3" to "No backtesting until Roadmap 4"

**3b. Create `docs/adr/0003-roadmap-renumbering.md`:**

Follow the ADR template format (Context, Decision, Consequences):

```
# ADR 0003: Roadmap Renumbering -- Resolution Coverage as Roadmap 3

Date: 2026-02-10
Status: Accepted

## Context

Roadmap 2 (Trust Artifacts) revealed that UNKNOWN_RESOLUTION is the dominant
data-quality gap. The existing provider chain (ClickHouse cache -> Gamma API)
cannot resolve markets where Gamma's `winningOutcome` field is absent or delayed.
On-chain CTF payout data is the authoritative source of truth for market resolution
and is available immediately after settlement.

The original Roadmap 3 (Hypothesis Validation Loop) depends on accurate resolution
data. Shipping hypothesis validation on top of unreliable resolution coverage
would produce unreliable hypotheses.

## Decision

Insert "Resolution Coverage" as Roadmap 3 and shift all subsequent milestones
by +1. This prioritizes data quality before analysis quality.

Scope of new Roadmap 3:
- OnChainCTFProvider (raw JSON-RPC to Polygon, no web3.py)
- SubgraphResolutionProvider (The Graph fallback)
- 4-stage CachedResolutionProvider chain
- Explicit resolution_source and reason traceability

## Consequences

- Roadmap numbers 3-8 shift to 4-9. External references to old numbers are
  limited to internal docs (no public consumers).
- Hypothesis Validation Loop (now Roadmap 4) is deferred but not dropped.
- The "no backtesting" kill condition now gates on Roadmap 4 instead of 3.
- Two new env vars are introduced: POLYGON_RPC_URL, POLYMARKET_SUBGRAPH_URL.
  Both have sensible public defaults and are optional for development.
```
  </action>
  <verify>
- `docs/ROADMAP.md` contains "Roadmap 3 - Resolution Coverage"
- `docs/ROADMAP.md` contains "Roadmap 4 - Hypothesis Validation Loop"
- `docs/ROADMAP.md` global kill conditions reference "Roadmap 4" for backtesting
- `docs/adr/0003-roadmap-renumbering.md` exists with Context, Decision, Consequences
- No references to old "Roadmap 3 - Hypothesis Validation Loop" remain (it should say Roadmap 4)
  </verify>
  <done>
- ROADMAP.md reflects Roadmap 0-9 with Resolution Coverage as Roadmap 3
- All subsequent milestones renumbered correctly
- Global kill conditions updated
- ADR-0003 documents the rationale for renumbering
  </done>
</task>

</tasks>

<verification>
1. All new imports work:
   - `python -c "from packages.polymarket.on_chain_ctf import OnChainCTFProvider"`
   - `python -c "from packages.polymarket.subgraph import SubgraphResolutionProvider"`
2. Unit tests pass: `python -m pytest tests/test_resolution_providers.py -v --tb=short`
3. Full test suite has no regressions: `python -m pytest tests/ -v --tb=short`
4. `.env.example` includes POLYGON_RPC_URL and POLYMARKET_SUBGRAPH_URL
5. `docs/ROADMAP.md` has 10 milestones (0-9) with correct ordering
6. `docs/adr/0003-roadmap-renumbering.md` exists
7. `Resolution` dataclass has `reason` field
8. `CachedResolutionProvider.__init__` accepts 4 provider params
</verification>

<success_criteria>
- OnChainCTFProvider can resolve WIN/LOSS from Polygon RPC (verified by mocked unit tests)
- SubgraphResolutionProvider can resolve from The Graph (verified by mocked unit tests)
- CachedResolutionProvider cascades 4 providers in order (verified by chain tests)
- Resolution dataclass carries reason field for traceability
- No new dependencies added to pyproject.toml (uses existing `requests`)
- ROADMAP.md and ADR reflect renumbering decision
- All existing tests continue to pass
</success_criteria>

<output>
After completion, create `.planning/quick/002-resolution-provider-chain/002-SUMMARY.md`
</output>
