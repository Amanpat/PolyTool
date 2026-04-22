---
title: "Cross-Platform Market Matching"
freshness_tier: CURRENT
confidence_tier: COMMUNITY
validation_status: UNTESTED
source_family: external_knowledge
source_quality_caution: >
  Algorithm descriptions derive from secondary notes about matcher.js in the
  hermes-pmxt repo. No published benchmark, precision/recall study, or accuracy
  metric set was found. Keep confidence at COMMUNITY and treat the stated
  thresholds as starting-point heuristics, not validated defaults.
---

# Cross-Platform Market Matching

## Overview

Cross-platform market matching is a heuristic normalization problem. Polymarket
and Kalshi each expose thousands of markets with their own internal slugs, titles,
and outcome naming. There is no shared identifier across venues, so matching must
be inferred from text similarity and structural cues. The recommended approach is
a Jaccard Levenshtein market matching pipeline: a Jaccard word-overlap filter
followed by Levenshtein character-distance re-ranking to reduce false positives.

---

## Baseline Algorithm: Jaccard Word Similarity

The simplest workable baseline is Jaccard similarity on bag-of-words representations
of market titles:

```
jaccard(A, B) = |A ∩ B| / |A ∪ B|
```

**Threshold**: A 40% Jaccard score was used as the match threshold in the
hermes-pmxt notes. Below this threshold, pairs are treated as unmatched.

**Why 40%**: Prediction market titles tend to be short and semantically dense.
Lower thresholds increase recall but admit too many false positives from
shared common words.

---

## Improved Algorithm: Hybrid Jaccard + Levenshtein

The Jaccard Levenshtein market matching approach is the recommended direction
for more robust cross-platform alignment:

1. **Jaccard pass**: Filter candidate pairs using Jaccard word overlap.
2. **Levenshtein refinement**: Re-rank or filter candidates using character-level
   edit distance to catch paraphrases with high overlap but different wording.

This two-stage approach reduces false positives from the Jaccard step while
preserving recall for semantically equivalent but lexically variant titles.

---

## Known Failure Modes

### Shared-Keyword Collisions

The primary failure mode for pure Jaccard matching: two unrelated markets that
share high-frequency domain words (e.g., "Bitcoin", "election", "price", "above")
score above the threshold despite being entirely different events.

Example failure: "Will Bitcoin close above $50K by March?" on Polymarket might
match "Will Bitcoin ETF be approved by March?" on Kalshi due to shared terms,
even though they have different resolution conditions.

### Wording and Outcome Name Differences

Venue-specific phrasing produces false non-matches:
- Polymarket: "Will [Team A] beat [Team B]?"
- Kalshi: "[Team A] to win vs [Team B]?"

Both describe the same event but score below threshold.

### Resolution Condition Mismatch

A keyword-based match does not guarantee semantic equivalence. Two markets can
share a title and resolve on different criteria, at different times, or against
different reference prices.

---

## Downstream Impact of Matching Errors

Poor matching quality directly contaminates:
- **Divergence statistics**: False matches create phantom gaps; false non-matches
  undercount real divergences. See `cross_platform_price_divergence_empirics.md`.
- **Arbitrage scans**: A false positive match can generate a spurious arb signal.
- **PnL attribution**: Attributing fills from different markets to the same event
  produces incorrect P&L accounting.

---

## What Has Not Been Measured

No published accuracy metrics, benchmark set, or precision/recall study exist
for the described matcher approach in the PolyTool or hermes-pmxt context. The
40% Jaccard threshold and the Jaccard + Levenshtein direction are candidate
heuristics, not validated defaults.

Before deploying a matcher in production, create a labeled test set of known
matches and non-matches across venues and measure precision, recall, and F1.

---

## Retrieval Keywords

`Jaccard Levenshtein market matching`, `40% threshold`, `matcher.js`,
`shared keyword false matches`, `cross-platform arbitrage matching`,
`Polymarket Kalshi event matching`, `market title similarity`
