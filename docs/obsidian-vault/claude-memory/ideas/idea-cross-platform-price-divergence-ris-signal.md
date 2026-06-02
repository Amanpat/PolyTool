---
title: "Idea — Cross-Platform Price Divergence as RIS Signal"
type: idea
status: active
source_zone: claude_memory
last_updated: 2026-05-23
lifecycle: reviewed
tags: [idea, RIS, signals]
---

# Idea — Cross-Platform Price Divergence as RIS Signal

## Concept

Use price disagreements between prediction market platforms as an intelligence signal, not a trading signal. Two applications:

### 1. RIS Precheck Enrichment

When the RIS evaluation gate scores a research document, enrich the evaluation with live market state:

- Document claims "Strategy X exploits inefficiency in market Y"
- Precheck queries market Y across Polymarket + Kalshi + Metaculus
- If all platforms agree within 1% → market is efficient → CAUTION flag on the document's claims
- If platforms diverge >5% → inefficiency may exist → supports the document → no flag

This grounds document evaluation in real-time market reality rather than evaluating claims in isolation.

### 2. Metaculus as Free Expert Consensus Baseline

Metaculus is a reputation-based forecasting platform — experts submit probability estimates, community consensus is public and free (no API key needed for reading via pmxt). When Metaculus community consensus differs from Polymarket price by >10%, that's a signal worth tracking in the `signals` RAG partition.

Example: Metaculus community says 70% probability on event X, Polymarket prices at 55%. The 15-point gap suggests either:
- Metaculus experts have information not priced in → potential directional signal
- Polymarket liquidity is thin and mispriced → potential market-making opportunity
- Different question framing → need to verify market matching carefully

## Implementation

Phase 3+ (requires pmxt or equivalent multi-platform API). Depends on [[claude-memory/ideas/idea-pmxt-sidecar-architecture-evaluation]].

## Source

Identified during [[legacy/Claude Desktop/08-Research/09-Hermes-PMXT-Deep-Dive]] analysis of hermes-pmxt arbitrage scan patterns.
