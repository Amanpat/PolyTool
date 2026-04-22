---
title: "Cross-Platform Price Divergence Empirics"
freshness_tier: CURRENT
confidence_tier: PRACTITIONER
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  SECONDARY SOURCE — HIGH PRIORITY CAUTION. The quantitative claims in this
  document (15-20% gap frequency, 5% threshold, convergence timelines) are derived
  from a secondary reference to an AhaSignals March 2026 tracker. The original
  tracker URL, archived snapshot, and full methodology have not been independently
  verified in this repo. Treat all specific figures as indicative pending primary
  source confirmation. This document was seeded by Director decision with this
  caution embedded — do not treat it as a validated empirical reference.
---

# Cross-Platform Price Divergence Empirics

## Purpose

This document summarizes observed cross-platform price gap patterns between
Polymarket and Kalshi on matched prediction markets. It is an empirics summary,
not a trading playbook. The figures below come from secondary references; see
the source-quality caution above.

## Key Empirical Claims (Secondary Source — UNTESTED)

The following observations derive from a reference to an AhaSignals March 2026
tracker, cited second-hand in PolyTool research notes:

- **Gap frequency**: Price gaps greater than 5% were observed approximately
  **15–20% of the time** across matched market pairs.
- **Convergence patterns**:
  - Some divergences converge within **minutes** when quickly arbitraged or when
    one venue reprices in response to the other.
  - Some gaps reportedly persist for **weeks or months**, driven by structural
    differences, liquidity conditions, or slow repricing.
- **Directional bias**: No stable directional bias was reported. Gaps do not
  systematically favor one venue over the other.

These figures should be treated as indicative until the original tracker source
is located, verified, and archived.

## Structural Factors That Produce Persistent Gaps

The following factors can produce genuine, non-exploitable price divergences:

1. **Resolution language differences**: Polymarket and Kalshi may resolve the same
   real-world event using different criteria, creating structurally different prices.
2. **Liquidity asymmetry**: A market that is highly liquid on one venue may have a
   wide bid/ask spread or low volume on the other, causing apparent price gaps.
3. **Settlement timing**: Different settlement windows mean positions converge at
   different real-world times.
4. **Counterparty mix**: Different participant bases and information sets on each
   venue can produce persistent disagreement.

## What Divergence Is and Is Not

Divergence statistics are most useful as an **inefficiency signal** or a **triage
input** for further investigation. They are not proof of risk-free arbitrage:

- Fee costs on both sides often consume the gross gap.
- Execution timing and fill uncertainty further erode expected value.
- Poor cross-platform matching can create **fake gaps** from mismatched events.
  See `cross_platform_market_matching.md` for matching failure modes.

## Normalization Requirements

Before comparing prices across venues, normalize:

- **Price units**: Polymarket uses shares on a 0–1 scale; Kalshi uses dollars (cents).
- **Contract framing**: Check whether both venues treat "YES" as the same outcome.
- **Resolution conditions**: Read the full resolution criteria on both sides.
  Keyword matches do not guarantee semantic equivalence.

## Retrieval Keywords

`cross-platform price divergence`, `Polymarket Kalshi 5% gap`,
`15-20% matched markets`, `convergence within minutes`, `no directional bias`,
`structural gaps persist`, `AhaSignals tracker`
