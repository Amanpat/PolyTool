---
phase: quick-002
plan: 01
subsystem: data-quality
tags: [resolution, polygon-rpc, the-graph, on-chain, ctf, subgraph]

# Dependency graph
requires:
  - phase: roadmap-2
    provides: Coverage reconciliation report revealing UNKNOWN_RESOLUTION as primary data gap
provides:
  - OnChainCTFProvider reading CTF payout state from Polygon RPC (no web3.py)
  - SubgraphResolutionProvider querying The Graph subgraph for CTF conditions
  - 4-stage CachedResolutionProvider chain (ClickHouse -> OnChainCTF -> Subgraph -> Gamma)
  - Resolution dataclass with explicit reason field for traceability
  - 13 unit tests for all resolution providers with mocked responses
affects: [scan-pipeline, coverage-reports, roadmap-3-completion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Raw JSON-RPC eth_call for on-chain data (no web3.py dependency)
    - GraphQL queries to The Graph subgraph
    - Cascading provider chain with graceful fallback
    - Explicit resolution_source and reason fields for debugging

key-files:
  created:
    - packages/polymarket/on_chain_ctf.py
    - packages/polymarket/subgraph.py
    - tests/test_resolution_providers.py
    - docs/adr/0003-roadmap-renumbering.md
  modified:
    - packages/polymarket/resolution.py
    - .env.example
    - docs/ROADMAP.md

key-decisions:
  - "Use raw JSON-RPC instead of web3.py for on-chain reads (no new dependency)"
  - "Chain order: ClickHouse (fastest cache) -> OnChainCTF (authoritative) -> Subgraph (fallback) -> Gamma (legacy)"
  - "Add reason field to Resolution for human-readable traceability"
  - "Insert Resolution Coverage as Roadmap 3, shift Hypothesis Validation to Roadmap 4"

patterns-established:
  - "Resolution providers return None on error/pending (graceful fallback)"
  - "All providers use timeout parameter (10s for RPC, 15s for subgraph)"
  - "Condition IDs normalized: lowercase hex without 0x prefix for subgraph queries"
  - "ABI encoding done manually for eth_call (selector + padded params)"

# Metrics
duration: 6min
completed: 2026-02-10
---

# Quick Task 002: Resolution Provider Chain Summary

**On-chain CTF resolution via Polygon RPC with subgraph fallback, reducing UNKNOWN_RESOLUTION for objectively resolved markets**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-10T21:34:53Z
- **Completed:** 2026-02-10T21:40:46Z
- **Tasks:** 3
- **Files modified:** 7
- **Tests:** 13 new tests, 217 total passing

## Accomplishments

- Implemented OnChainCTFProvider for reading CTF payout state from Polygon RPC using raw JSON-RPC eth_call
- Implemented SubgraphResolutionProvider for querying The Graph subgraph as fallback
- Updated CachedResolutionProvider to 4-stage chain: ClickHouse -> OnChainCTF -> Subgraph -> Gamma
- Added reason field to Resolution dataclass for traceability and debugging
- Comprehensive unit tests with mocked RPC/subgraph responses (no real network calls)
- Updated ROADMAP.md to insert Resolution Coverage as Roadmap 3, shifting all subsequent milestones by +1
- Created ADR-0003 documenting rationale for roadmap renumbering

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement OnChainCTFProvider and SubgraphResolutionProvider** - `aeba5be` (feat)
2. **Task 2: Unit tests for resolution provider chain** - `956c41e` (test)
3. **Task 3: Update ROADMAP.md and add ADR for roadmap renumbering** - `81f17d7` (docs)

## Files Created/Modified

**Created:**
- `packages/polymarket/on_chain_ctf.py` - OnChainCTFProvider using raw JSON-RPC eth_call to Polygon
- `packages/polymarket/subgraph.py` - SubgraphResolutionProvider querying The Graph
- `tests/test_resolution_providers.py` - 13 unit tests for OnChainCTF, Subgraph, and CachedResolutionProvider chain
- `docs/adr/0003-roadmap-renumbering.md` - ADR documenting roadmap renumbering rationale

**Modified:**
- `packages/polymarket/resolution.py` - Added reason field to Resolution, updated CachedResolutionProvider to 4-stage chain
- `.env.example` - Added POLYGON_RPC_URL and POLYMARKET_SUBGRAPH_URL with public defaults
- `docs/ROADMAP.md` - Inserted Roadmap 3 (Resolution Coverage), shifted Roadmap 3-8 to 4-9, updated kill conditions

## Decisions Made

**1. No web3.py dependency**
- Use raw JSON-RPC `requests.post` for eth_call instead of adding web3.py
- Rationale: Avoid heavy dependency, explicit control over ABI encoding, simpler error handling

**2. 4-stage provider chain order**
- ClickHouse (fastest, cached) -> OnChainCTF (authoritative, Polygon RPC) -> Subgraph (The Graph fallback) -> Gamma (legacy API)
- Rationale: Prioritize speed (cache first), then authoritative source (on-chain), then fallback (subgraph), then legacy (Gamma)

**3. Add reason field to Resolution dataclass**
- Stores human-readable explanation (e.g., "payoutDenominator=1000000, outcomeIndex=0 has payoutNumerator=1000000")
- Rationale: Debugging and traceability - know exactly where each resolution came from and why

**4. Roadmap renumbering**
- Insert Resolution Coverage as Roadmap 3, shift Hypothesis Validation to Roadmap 4
- Rationale: Data quality must precede analysis quality. UNKNOWN_RESOLUTION is the dominant gap revealed by Roadmap 2.

**5. Graceful fallback pattern**
- All providers return None on error/pending, chain continues to next provider
- Rationale: Network errors, timeouts, and unresolved markets shouldn't block the scan pipeline

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly with no blocking issues.

## User Setup Required

**Environment variables (optional):**

If users want to customize RPC endpoints or subgraph URLs, they can set:
- `POLYGON_RPC_URL` (defaults to https://polygon-rpc.com)
- `POLYMARKET_SUBGRAPH_URL` (defaults to https://api.thegraph.com/subgraphs/name/polymarket/polymarket-matic)

Both have sensible public defaults in `.env.example` and are optional for development.

**Verification commands:**
```bash
# Test imports
python -c "from packages.polymarket.on_chain_ctf import OnChainCTFProvider; print('OK')"
python -c "from packages.polymarket.subgraph import SubgraphResolutionProvider; print('OK')"

# Run unit tests
python -m pytest tests/test_resolution_providers.py -v --tb=short

# Run full test suite (verify no regressions)
python -m pytest tests/ -v --tb=short
```

## Next Phase Readiness

**Ready for Roadmap 3 completion:**
- Resolution provider infrastructure complete
- Unit tests passing with mocked providers
- ROADMAP.md updated to reflect current state

**Remaining for Roadmap 3:**
- Deploy providers in production scan pipeline (update scan command to instantiate new providers)
- Measure UNKNOWN_RESOLUTION rate reduction in real scans
- Mark Roadmap 3 as COMPLETE when UNKNOWN_RESOLUTION rate drops to < 5% for objectively resolved markets

**No blockers.**

---
*Phase: quick-002*
*Completed: 2026-02-10*
