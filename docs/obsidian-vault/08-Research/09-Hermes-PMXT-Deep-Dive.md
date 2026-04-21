---
tags: [research, open-source, pmxt, arbitrage, RIS]
date: 2026-04-10
status: complete
topics: [hermes-agent, pmxt-sdk, cross-platform-arb, RIS-signals, agent-skills]
---

# Deep Dive: 0xharryriddle/hermes-pmxt

## What It Is

A Python toolset + Hermes agent skill that wraps pmxt SDK calls into agent-callable functions. 10 tools: `pmxt_search`, `pmxt_quote`, `pmxt_order_book`, `pmxt_ohlcv`, `pmxt_trades`, `pmxt_events`, `pmxt_balance`, `pmxt_positions`, `pmxt_order`, `pmxt_arbitrage_scan`.

2 commits, 2 stars. Tiny repo. BUT the author (0xharryriddle) is a **pmxt core contributor** — he built the Metaculus exchange integration (PR #71 on pmxt-dev/pmxt). This means the patterns here are authoritative for pmxt usage.

## LEARNINGS.md: Real-World pmxt Gotchas (HIGH VALUE)

This file documents pitfalls discovered during implementation. If we ever use pmxt, this saves significant debugging time:

1. **`server.status()` returns dict, not object** — use `.get()` not attribute access
2. **`fetch_market(market_id="...")` singular method doesn't work** — throws `PmxtError: Unknown error`. Use `fetch_markets(query=keyword)` instead
3. **Slug-based lookup is slow or returns empty** — `fetch_markets(slug="will-bitcoin-reach-...")` times out or returns 0 results. Use keyword query search.
4. **`create_order()` needs both `market_id` and `outcome_id`** — outcome_id must be resolved from a prior `fetch_markets` call. outcome_ids are 70+ character strings for Polymarket.
5. **Cross-exchange arb matching uses Jaccard word similarity at 40% threshold** — title word overlap matching, not exact slug comparison
6. **"True arbitrage is rare — most combined prices are near 1.00"** — empirical finding from actually running the arb scanner
7. **Prices normalized to 0-1 across all platforms** — Kalshi internally uses 0-100 but pmxt normalizes
8. **Sidecar auto-starts on first SDK call (~1-2 seconds)** — shared across Python processes (singleton), logs at `~/.pmxt/server.log`

**RIS seed candidate:** This LEARNINGS.md should be seeded into `external_knowledge` as `PRACTITIONER` confidence — it's empirical findings from a pmxt core contributor.

## Arbitrage Scan: Jaccard Matching (Phase 3 Relevant)

The `pmxt_arbitrage_scan` tool does cross-exchange price comparison:

1. Search for matching markets on multiple exchanges by keyword
2. Match outcomes across platforms using **Jaccard word similarity** (40% threshold on title words)
3. Compare YES+NO prices across platforms
4. Flag spreads above threshold as arb opportunities

This is directly relevant to:
- **Our Phase 3 cross-platform arb detector** — the Jaccard matching approach is simpler and possibly more robust than the realfishsam `matcher.js` fuzzy matching already in our roadmap
- **Our RIS synthesis engine precheck** — multi-platform price divergence as a GO/CAUTION/STOP signal

Key empirical finding from LEARNINGS.md: **"True arbitrage is rare."** This validates our roadmap's Phase 5 positioning of cross-platform arb (not Phase 1). The opportunity isn't in the arb itself but in using price divergence as an INFORMATION signal.

## RIS Integration Angle: Multi-Platform Price Divergence as Signal

This is the "think outside the box" finding. Instead of using `pmxt_arbitrage_scan` for trading, use it for **intelligence**:

**Scenario:** RIS evaluates a research document claiming "Strategy X works in market Y." The precheck could:
1. `pmxt_search` for market Y across Polymarket, Kalshi, Metaculus
2. Compare prices across platforms
3. If prices diverge >5% → the market is inefficient → strategy might have room
4. If prices converge within 1% → market is efficient → strategy claims are suspect

This turns price divergence into a **document credibility signal** for the RIS evaluation gate. A paper claiming inefficiency in a market where all platforms agree within 1% gets a CAUTION flag.

**Also useful for:** The `signals` RAG partition (Phase 3). Cross-platform price disagreement events are themselves signals worth tracking — when Polymarket and Kalshi disagree by >5% on the same event, that's information.

### Platforms Available via pmxt (More Than We Planned)

| Platform | Type | In Our Roadmap? |
|----------|------|----------------|
| Polymarket | Crypto-native CLOB | Yes (primary) |
| Kalshi | CFTC-regulated | Yes (Phase 3) |
| Limitless | Crypto CLOB | No |
| Metaculus | Reputation-based forecasting | No |
| Myriad | Social predictions | No |
| Opinion | Community predictions | No |
| Smarkets | UK exchange | No |
| Polymarket US | CFTC-regulated (upcoming) | Yes (Phase 8) |

**New idea:** Metaculus is a reputation-based forecasting platform where experts submit probability estimates. Their community predictions could serve as a FREE "expert consensus" signal for our RIS — no API key needed for reading. When Metaculus community consensus differs from Polymarket price by >10%, that's a signal.

## What To Pull vs Skip

### PULL (reimplement, don't copy):
1. **Jaccard word similarity matching** for cross-platform market matching — simpler than realfishsam's fuzzy matcher, may be sufficient for Phase 3
2. **LEARNINGS.md gotchas** → seed into RIS `external_knowledge` as PRACTITIONER
3. **Multi-platform price divergence as RIS precheck signal** — architectural pattern, not code

### SKIP:
- The Hermes agent framework integration (we don't use Hermes)
- The SKILL.md agent prompt (interesting but our RIS has its own evaluation gate design)
- The tool wrapper functions themselves (trivial pmxt SDK calls)

### DEFER (evaluate with pmxt sidecar decision):
- Using `pmxt_arbitrage_scan` directly as a Phase 3 arb detector
- Using Metaculus as a signal source for RIS

## Connection to Other Research

- **[[Idea - pmxt Sidecar Architecture Evaluation]]** — All hermes-pmxt value is contingent on the pmxt sidecar decision. If we skip pmxt, we'd reimplement the Jaccard matching ourselves.
- **[[07-Backtesting-Repo-Deep-Dive]]** — Backtesting repo also uses pmxt for data but through NautilusTrader adapter layer
- **[[Work-Packet - Fee Model Maker-Taker + Kalshi]]** — Kalshi fee model is needed regardless of whether we use pmxt or build our own adapter

## New Ideas Generated

1. **Metaculus as free expert consensus signal** — no API key needed, community predictions = crowd wisdom baseline. When Metaculus and Polymarket diverge, something interesting is happening.
2. **Cross-platform divergence as RIS precheck** — enrich document evaluation with live market state. "Does the claimed inefficiency actually exist right now?"
3. **Jaccard word similarity > fuzzy matching** — simpler, already validated at 40% threshold for cross-platform market matching

## Cross-References

- [[08-Copy-Trader-Deep-Dive]] — Same pmxt SDK, different application
- [[07-Backtesting-Repo-Deep-Dive]] — Same pmxt ecosystem
- [[01-Wallet-Discovery-Pipeline]] — Loop D uses CLOB WebSocket, not pmxt
- [[Idea - pmxt Sidecar Architecture Evaluation]] — Gating question for all pmxt-dependent work
