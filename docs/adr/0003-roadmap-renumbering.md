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
