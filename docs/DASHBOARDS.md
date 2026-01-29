# PolyTool Grafana Dashboards

This guide explains each Grafana dashboard in PolyTool and how to use them.

## Quick Start

1. Open Grafana at [http://localhost:3000](http://localhost:3000)
2. Login with default credentials (admin/admin on first run)
3. Navigate to **Dashboards** > **Browse** > **PolyTool** folder
4. Start with **PolyTool - User Overview** for a comprehensive view

---

## Dashboard Overview

| Dashboard | Purpose | Key Use Case |
|-----------|---------|--------------|
| **User Overview** | Comprehensive user profile | First stop for analyzing any user |
| **Strategy Detectors** | Detailed strategy analysis | Deep-dive into trading patterns |
| **PnL** | Profit and loss tracking | Performance analysis |
| **Arb Feasibility** | Arbitrage cost analysis | Understanding arb opportunities |
| **Liquidity Snapshots** | Orderbook quality metrics | Market health assessment |
| **User Trades** | Raw trade data | Transaction-level debugging |
| **Infra Smoke** | System health | Monitoring infrastructure |

---

## User Dropdown (Centralized)

All dashboards with a User selector use the same centralized ClickHouse view for consistent labeling:

**View:** `polyttool.users_grafana_dropdown`

**Query:**
```sql
SELECT __value, __text FROM polyttool.users_grafana_dropdown ORDER BY __text
```

**Label format:**
- If username exists: `@username (0x1234…abcd)`
- If no username: `0x1234…abcd`

**Note:** Usernames appear only after a scan/resolve using a handle (e.g., `@alice`) at least once.

This ensures:
- Consistent labels across all dashboards
- No duplicate wallet display (e.g., no `0xabc…def (0xabc…def)`)
- Deduplication via `GROUP BY proxy_wallet` with `argMaxIf(username, last_updated)`
- Most recently updated users appear first

**Migration:** `infra/clickhouse/initdb/10_user_labels_view.sql`

---

## PolyTool - User Overview

**Location:** Dashboards > PolyTool - User Overview
**UID:** `polyttool-user-overview`

The primary dashboard for analyzing a Polymarket user. Combines key metrics from all other dashboards into a single view.

### Variables
- **User**: Dropdown showing username with wallet preview (e.g., "@alice (0x1234…5678)"). If no username, shows wallet address only. Never blank.
- **Time Bucket**: Aggregation period for metrics (day/hour/week)

### Panels

#### User Summary Row
| Panel | Description |
|-------|-------------|
| Total Trades | Lifetime trade count for the user |
| Total Volume | Sum of trade sizes × prices (USD notional) |
| Markets Traded | Unique markets (condition_ids) |
| Active Days | Days between first and last trade |
| Mapping Coverage | % of trades with market metadata |
| Latest Realized PnL | Most recent bucket's realized profit/loss |
| Snapshot Pricing % | % of tokens priced via stored orderbook snapshots (higher = more reliable MTM) |
| Pricing Confidence | Overall MTM reliability: HIGH (green), MED (yellow), LOW (red) |

See [QUALITY_CONFIDENCE.md](./QUALITY_CONFIDENCE.md) for detailed confidence interpretation.

#### PnL & Exposure Row
| Panel | Description |
|-------|-------------|
| PnL Over Time | Realized PnL (solid green) + MTM estimate (dashed blue) |
| Exposure Over Time | Open position notional value |

#### Plays (Recent Trades) Row
| Panel | Description |
|-------|-------------|
| Latest Trades (Plays) | Table of individual trades with timestamp, market, outcome, side (color-coded), price, size, notional, and tx hash (clickable link to PolygonScan). Sorted newest-first, limited to 100 rows. Respects dashboard time range. |
| Top Markets by Notional | Top 10 markets by total notional volume in selected time range |
| Top Outcomes by Notional | Top 10 outcome/market combinations by notional volume with trade counts |
| Top Categories by Volume | Top 10 categories by volume with percentage breakdown. Unknown category shown explicitly when market metadata is missing. |

See [PLAYS_VIEW.md](./PLAYS_VIEW.md) for detailed field definitions.

#### Strategy Signals Row
| Panel | Description |
|-------|-------------|
| Latest Strategy Signals | Table with detector name, score gauge, and color-coded label |
| Strategy Scores Over Time | Line chart of detector scores trending |

**Signal Color Coding:**
- 🟢 Green: Positive/neutral (Holder, Diversified, Normal)
- 🟡 Yellow: Moderate (Swing Trader, Moderate Focus)
- 🔴 Red: Aggressive/concentrated (Scalper, Concentrated)
- 🔵 Blue: Pattern detected (DCA Likely)
- 🟣 Purple: Arb behavior (Arb Likely)
- ⚫ Gray: Insufficient data

#### Market Mix Row
| Panel | Description |
|-------|-------------|
| Volume by Category | Pie chart of trading volume by market category |
| Top Categories | Table with category, volume, market count, percentage |
| Top Markets by Volume | Table of specific markets with highest volume |

#### Liquidity & Arb Row
| Panel | Description |
|-------|-------------|
| Orderbook Quality | Pie chart of snapshot statuses (OK/Empty/One-Sided/Error) |
| Orderbook OK Rate | Trend line of % of OK snapshots over time |
| Arb Events | Count of potential arb opportunities analyzed |
| Total Fees Est | Estimated total fees across all arb events |
| Total Slippage Est | Estimated total slippage across all arb events |
| Arb Usable Liquidity Rate | % of arb events with HIGH liquidity confidence (all legs have orderbooks) |
| $100 Depth Coverage | % of arb events where $100 trades can execute at estimated prices |
| Arb Confidence | Pie chart showing high/medium/low confidence distribution |
| Usable Liquidity Rate (User Tokens) | % of the user’s token snapshots that meet usable liquidity thresholds |
| Top Tradeable Markets (Low Cost) | Lowest median execution-cost markets among the user’s tokens |
| Opportunities (Low Cost) | Latest low-cost shortlist from the Opportunity Engine |

See [QUALITY_CONFIDENCE.md](./QUALITY_CONFIDENCE.md) for interpreting liquidity confidence and usability thresholds.  
See [PACKET_6_OPPORTUNITIES.md](./PACKET_6_OPPORTUNITIES.md) for Opportunity Engine details.

### Common Workflows

**Analyze a new user:**
1. Select user from dropdown
2. Review summary stats at top
3. Scroll to "Plays" section to see recent trades and top markets
4. Check strategy signals for trading style
5. Look at PnL trend for performance
6. Review market mix for concentration

**Compare time periods:**
1. Adjust Grafana time picker (top right)
2. Toggle between day/hour/week bucket types
3. Compare detector scores across periods

---

## PolyTool - Strategy Detectors

**Location:** Dashboards > PolyTool - Strategy Detectors
**UID:** `polyttool-strategy-detectors`

Detailed view of strategy detection results with evidence exploration.

### Variables
- **User Wallet**: Proxy wallet address
- **Bucket Type**: day/hour/week
- **Detector**: Filter to specific detector (or "All")

### Key Panels

| Panel | Description |
|-------|-------------|
| Detector Scores Over Time | Line chart of all detector scores |
| Latest Detector Results | Table with scores and labels |
| Mapping Coverage | Stat showing % of trades with market metadata |
| Total Markets Traded | Unique markets from features table |
| Trade Count by Bucket | Bar chart of trade activity |
| Notional Volume by Bucket | Bar chart of USD volume |
| Detector Evidence Details | Full evidence JSON for debugging |

### When to Use
- Deep-dive into why a detector produced a specific result
- Debug detector behavior by examining evidence JSON
- Track detector score changes over time
- Filter to a single detector for focused analysis

---

## PolyTool - PnL

**Location:** Dashboards > PolyTool - PnL
**UID:** `polyttool-pnl`

Focused view of profit/loss and exposure metrics.

### Panels

| Panel | Description |
|-------|-------------|
| Realized PnL Over Time | Profit from closed positions |
| MTM PnL Estimate Over Time | Mark-to-market estimate including open positions |
| Exposure Notional Over Time | Total open position size |

### Key Concepts

- **Realized PnL**: Actual profit/loss from completed trades
- **MTM Estimate**: Includes unrealized gains/losses on open positions (requires orderbook snapshots)
- **Exposure**: Total notional value of open positions

---

## PolyTool - Arb Feasibility

**Location:** Dashboards > PolyTool - Arb Feasibility
**UID:** `polyttool-arb-feasibility`

Analysis of arbitrage opportunities and their execution costs.

### Panels

| Panel | Description |
|-------|-------------|
| Total Arb Events | Count of potential arb opportunities |
| Total Fees Est | Estimated fees for all arb events |
| Total Slippage Est | Estimated slippage costs |
| Fees vs Slippage Over Time | Stacked bar chart comparing costs |
| Break-Even Notional | Average trade size needed to profit |
| Arb Feasibility Results | Table with per-market breakdown |

### Understanding Confidence Levels

| Confidence | Meaning |
|------------|---------|
| High | Complete fee + slippage data, reliable estimate |
| Medium | Some data missing, estimate may be off |
| Low | Significant data gaps, use with caution |

---

## PolyTool - Liquidity Snapshots

**Location:** Dashboards > PolyTool - Liquidity Snapshots
**UID:** `polyttool-liquidity-snapshots`

Global view of orderbook quality across all snapshots (not user-filtered).

### Panels

| Panel | Description |
|-------|-------------|
| Total Snapshots | Count of all snapshots in time range |
| OK/Empty/One-Sided/Error | Status breakdown stats |
| Usable Liquidity % (OK) | % of OK snapshots that pass usability thresholds |
| Median Exec Cost (bps) | Median execution cost across OK snapshots |
| Spread Over Time | Average/max/min spread in bps |
| Depth Over Time | Bid/ask depth at 50bps band |
| Slippage Over Time | Buy/sell slippage at $100/$500 sizes |
| Latest Snapshots | Table with enriched market info + usability flags |
| Status Distribution | Pie chart of snapshot statuses |
| Error Reasons | Table of error messages for debugging |
| Liquidity Grade Distribution | HIGH/MED/LOW breakdown of liquidity grades |

### Status Meanings

| Status | Color | Description |
|--------|-------|-------------|
| OK | 🟢 Green | Valid two-sided orderbook |
| Empty | 🟠 Orange | Orderbook exists but has no orders |
| One-Sided | 🟡 Yellow | Only bids or only asks present |
| No Orderbook | ⚫ Gray | Token doesn't have an orderbook |
| Error | 🔴 Red | Failed to fetch (API error, rate limit) |

---

## PolyTool - User Trades

**Location:** Dashboards > PolyTool - User Trades
**UID:** `polyttool-user-trades`

Raw trade data exploration.

### When to Use
- Verify trade ingestion worked correctly
- Debug specific transactions
- Export trade data for external analysis

---

## PolyTool - Infra Smoke

**Location:** Dashboards > PolyTool - Infra Smoke
**UID:** `polyttool-infra-smoke`

Infrastructure health monitoring.

### Panels
- ClickHouse connectivity
- Table row counts
- Recent activity indicators

### When to Use
- After `docker compose up` to verify services started
- Debugging "no data" issues
- Monitoring system health

---

## Tips & Tricks

### Navigating Between Dashboards
- Use the **Related Dashboards** dropdown in User Overview to jump to specialized views
- URL parameters (`?var-proxy_wallet=...`) are preserved when navigating

### Adjusting Time Range
1. Click the time picker in the top right
2. Select preset (Last 7 days, Last 30 days, etc.)
3. Or use custom range for specific analysis periods

### Exporting Data
1. Hover over any panel
2. Click the three-dot menu
3. Select **Inspect** > **Data**
4. Download as CSV or JSON

### Creating Alerts
1. Edit any panel
2. Go to **Alert** tab
3. Set conditions for notification (requires SMTP config in Grafana)

### Sharing
1. Click the share icon on any dashboard
2. Create snapshot link or export JSON
3. Snapshots include data; links require access

---

## Troubleshooting

### "No data" in panels
1. Check user is selected in dropdown
2. Verify data exists: run detectors/pnl/arb endpoints first
3. Check time range covers data period
4. Review Infra Smoke dashboard for connectivity

### Slow queries
1. Narrow time range
2. Use day bucket instead of hour
3. Check ClickHouse logs: `docker compose logs clickhouse`

### Missing market metadata
1. Run `/api/ingest/markets` endpoint
2. Enable `backfill_mappings` on detector runs
3. Check mapping coverage stat (uses `user_trades_resolved`, which resolves token aliases)
4. If Data API token ids differ from Gamma CLOB ids, ensure `token_aliases` is populated by re-running market ingestion or backfill

---

## Related Documentation

- [STRATEGY_CATALOG.md](./STRATEGY_CATALOG.md) - Detector algorithm details
- [CLAUDE.md](../CLAUDE.md) - Project overview and infrastructure commands
- [services/api/README.md](../services/api/README.md) - API endpoint documentation
