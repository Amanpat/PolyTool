# PolyTool Strategy Catalog

This document describes the trading strategy detectors available in PolyTool. Each detector analyzes a user's trading history and produces a classification label, a confidence score (0.0–1.0), and supporting evidence.

---

## Overview

| Internal Name | Display Name | What It Detects |
|---------------|--------------|-----------------|
| `HOLDING_STYLE` | Holding Style | How long the user holds positions before exiting |
| `DCA_LADDERING` | DCA / Laddering | Whether the user builds positions with consistent-size orders |
| `MARKET_SELECTION_BIAS` | Market Concentration | How diversified vs. concentrated the user's category exposure is |
| `COMPLETE_SET_ARBISH` | Complete-Set Arb | Whether the user buys both outcomes of a market and closes quickly |

---

## Holding Style

**Internal Name:** `HOLDING_STYLE`
**Display Name:** Holding Style

### What It Means
Classifies users by their typical holding duration. A **Scalper** flips positions within minutes to an hour, a **Swing Trader** holds for hours to days, and a **Long-Term Holder** maintains positions for a week or longer.

### Labels
| Label | Condition |
|-------|-----------|
| `SCALPER` | Median hold time < 60 minutes |
| `SWING` | Median hold time 60 minutes – 7 days |
| `HOLDER` | Median hold time >= 7 days |
| `UNKNOWN` | Insufficient matched trades to classify |

### Signals / Features
- **FIFO matching** of BUY → SELL for each token
- Median, P10, and P90 hold durations (minutes)
- Distribution buckets: `<1h`, `1h-24h`, `1d-7d`, `>7d`

### Evidence Fields (JSON)
```json
{
  "median_hold_minutes": 45.2,
  "p10_hold_minutes": 5.1,
  "p90_hold_minutes": 320.5,
  "matched_trades": 142,
  "unmatched_buys": 8,
  "hold_distribution": {
    "<1h": 85,
    "1h-24h": 42,
    "1d-7d": 12,
    ">7d": 3
  }
}
```

### Score Interpretation
- For **SCALPER**: Score decreases as median approaches 60 min (1.0 = instant flip, 0.0 = near threshold)
- For **SWING**: Score is normalized position within 60 min – 7 day range
- For **HOLDER**: Score increases with longer holds, capped at 1.0

### Common False Positives / Limitations
- **Unmatched buys** (open positions) are not included in hold time calculation
- Markets that resolve before a user can sell will appear as longer holds
- Transfers and redemptions are not currently tracked, which may affect accuracy

---

## DCA / Laddering

**Internal Name:** `DCA_LADDERING`
**Display Name:** DCA / Laddering

### What It Means
Detects dollar-cost averaging (DCA) or ladder entry patterns where a user builds a position through multiple similarly-sized orders rather than a single large order.

### Labels
| Label | Condition |
|-------|-----------|
| `DCA_LIKELY` | >30% of token/side groups show consistent sizing |
| `RANDOM` | Inconsistent sizing patterns |
| `INSUFFICIENT_DATA` | Fewer than 3 trades per token/side to analyze |

### Signals / Features
- Groups trades by `(token_id, side)`
- **Size consistency**: coefficient of variation (std/mean) < 0.3
- **Interval regularity**: time between trades analyzed for patterns
- Minimum 3 trades per group required

### Evidence Fields (JSON)
```json
{
  "tokens_with_dca_pattern": 5,
  "total_token_groups_analyzed": 12,
  "pattern_details": [
    {
      "token_id": "abc123...",
      "side": "BUY",
      "trade_count": 8,
      "size_cv": 0.15,
      "interval_cv": 0.42
    }
  ]
}
```

### Score Interpretation
- Score = (tokens with DCA pattern) / (total groups with 3+ trades)
- Higher score indicates more systematic position building
- 0.3 threshold for `DCA_LIKELY` label

### Common False Positives / Limitations
- Small accounts with few trades may show artificial consistency
- Price-based laddering (buying at specific prices) is not detected
- Time-interval consistency is computed but not currently used for labeling
- Does not distinguish intentional DCA from coincidental similar sizes

---

## Market Concentration

**Internal Name:** `MARKET_SELECTION_BIAS`
**Display Name:** Market Concentration

### What It Means
Measures how concentrated a user's trading is across market categories. A **Diversified** trader spreads volume across many categories (politics, sports, crypto, etc.), while a **Concentrated** trader focuses heavily on one or two.

### Labels
| Label | Condition |
|-------|-----------|
| `DIVERSIFIED` | HHI < 0.15 |
| `MODERATE` | HHI 0.15 – 0.25 |
| `CONCENTRATED` | HHI >= 0.25 |

### Signals / Features
- **Herfindahl-Hirschman Index (HHI)**: sum of squared market shares by category
- Volume aggregation by category from `market_tokens` mapping
- Top 5 categories with percentage breakdown

### Evidence Fields (JSON)
```json
{
  "hhi_score": 0.32,
  "top_categories": [
    {"category": "Politics", "volume": 5420.5, "pct": 54.2},
    {"category": "Crypto", "volume": 2810.0, "pct": 28.1},
    {"category": "Sports", "volume": 1769.5, "pct": 17.7}
  ],
  "unique_markets_traded": 45,
  "mapping_coverage_pct": 92.5
}
```

### Score Interpretation
- Score = HHI value (0.0 – 1.0)
- 0.0 = perfectly diversified across infinite categories
- 1.0 = all volume in a single category
- Typical diversified trader: 0.10 – 0.15

### Common False Positives / Limitations
- **Unmapped tokens** are grouped as "UNMAPPED" which inflates concentration
- Low `mapping_coverage_pct` (<80%) indicates unreliable results—run market ingestion first
- Category granularity depends on Polymarket's tagging; some events span multiple topics
- New markets may not have category metadata yet

---

## Complete-Set Arb

**Internal Name:** `COMPLETE_SET_ARBISH`
**Display Name:** Complete-Set Arb

### What It Means
Detects potential complete-set arbitrage behavior: buying both YES and NO outcomes of a binary market and closing the position quickly (within 24 hours). This is a common MEV/arb strategy when outcome prices sum to less than $1.

### Labels
| Label | Condition |
|-------|-----------|
| `ARB_LIKELY` | >30% of dual-outcome markets show quick close pattern |
| `NORMAL` | Standard trading behavior |
| `INSUFFICIENT_DATA` | No markets with both outcomes traded |

### Signals / Features
- Groups trades by `condition_id` (market)
- Checks if user bought both `outcome_index=0` and `outcome_index=1`
- Measures time between first buy of each outcome
- Threshold: both bought within 24 hours

### Evidence Fields (JSON)
```json
{
  "potential_arb_events": 3,
  "markets_with_both_outcomes": 8,
  "avg_close_time_hours": 2.5,
  "arb_details": [
    {
      "condition_id": "0xabc123...",
      "time_diff_hours": 0.5
    }
  ]
}
```

### Score Interpretation
- Score = (arb events) / (markets with both outcomes)
- Higher score indicates more arb-like behavior
- 0.3 threshold for `ARB_LIKELY` label

### Common False Positives / Limitations
- **Hedging** behavior looks identical to arb (buying both sides to reduce risk)
- Does not verify that prices summed to < $1 at time of purchase
- Sell/redeem timing is not analyzed—only time between initial buys
- Market resolution before position close is not distinguished from intentional arb

---

## Using Detectors in PolyTool

### API Endpoint
```bash
POST /api/run/detectors
{
  "user": "@username",
  "bucket": "day",
  "recompute_features": true,
  "backfill_mappings": true
}
```

### Response Fields
Each detector result includes:
- `detector`: Internal detector name
- `bucket_type`: Aggregation period (day/hour/week)
- `bucket_start`: Start of the time bucket
- `score`: Confidence score (0.0 – 1.0)
- `label`: Classification label
- `evidence`: JSON object with supporting metrics

### ClickHouse Table
Results are stored in `polyttool.detector_results`:
```sql
SELECT detector_name, label, score, evidence_json
FROM detector_results
WHERE proxy_wallet = '0x...'
ORDER BY computed_at DESC
```

### Grafana Dashboard
View results in **PolyTool - User Overview** dashboard:
1. Select user wallet from dropdown
2. Choose time bucket (day/hour/week)
3. See "Strategy Signals" table for latest classifications

---

## Future Detectors (Planned)

- **Momentum Chaser**: Detects buying into sharp price movements
- **Event Timer**: Identifies trading concentrated around event dates
- **Size Scaling**: Detects progressive position sizing (martingale-like)
- **Cross-Market Correlation**: Identifies related-market trading clusters
