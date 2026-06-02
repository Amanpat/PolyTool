# Metrics Engine — 12-Dimension Minimal Viable Fingerprint (MVF)
**Status:** Researched, ready for implementation spec
**Last updated:** 2026-04-08
**Source:** GLM-5 Turbo research on strategy fingerprinting metrics

## The 12-Dimension MVF Vector

Each wallet gets this vector computed programmatically (no LLM needed).

| # | Metric | Category | Formula | Already Built? | Complexity |
|---|--------|----------|---------|----------------|------------|
| 1 | Maker/Taker Ratio | Execution | Vol_maker / Vol_total | Partial | Simple (needs maker/taker flags) |
| 2 | Cancel-to-Fill Ratio | Execution | Count_cancels / Count_fills | No | **Blocked** — cancelled orders are off-chain only |
| 3 | Trade Burstiness (CV) | Timing | StdDev(inter_trade_time) / Mean(inter_trade_time) | No | Simple |
| 4 | Lifecycle Entry % | Timing | Mean((first_trade - market_create) / (resolution - market_create)) | No | Simple |
| 5 | Resolution Exit % | Timing | Mean((last_trade - market_create) / (resolution - market_create)) | No | Simple |
| 6 | Sizing Convexity | Risk | Correlation(Trade_Size, Abs(Trade_Price - Market_Mid)) | No | Medium |
| 7 | Category Entropy | Selection | Shannon_Entropy(market_category_distribution) | Partial | Simple (scipy.stats.entropy) |
| 8 | Complement Rate | PM-Specific | Vol_both_YES_and_NO / Vol_total (same market) | Yes (COMPLETE_SET_ARBISH) | Simple |
| 9 | Win Rate | Profit | Count(winning_markets) / Count(total_markets) | Yes | Simple |
| 10 | Payoff Ratio | Profit | Avg_Profit_Per_Win / Abs(Avg_Loss_Per_Loss) | Partial | Simple |
| 11 | CLV | Skill | Mean((Exit_Price - Market_Mid_At_Exit) * Direction_Sign) | Yes | Medium |
| 12 | Longshot Bias | PM-Specific | ROI_on_trades_below_20c - ROI_on_trades_above_80c | No | Simple (pandas.groupby) |

## Strategy Classification Reference

The LLM receives the MVF vector + this reference to classify:

- **Market Maker:** MTR>.9, CFR>.8, Entry<.2, Exit>.95, WinRate>80%, Payoff<.2, Low CLV
- **Arbitrageur:** MTR~.5, Complement>.3, WinRate>95%, Zero/Negative CLV
- **Directional/Informed:** MTR<.2, CFR<.3, High CLV>0, Payoff>1.5, WinRate<55%, Late exit .90+
- **Momentum/Trend:** MTR<.3, Negative CLV (buys after moves), Moderate WinRate, High-volume markets
- **Contrarian:** MTR<.3, Positive CLV (buys into dips), Buys when market drops suddenly
- **Noise/Passive:** Low MTR, Low CFR, Late Entry>.7, CLV~0, High Category Entropy

## Cancel-to-Fill Workaround

CFR requires order-level data (cancellations are off-chain CLOB events, never hit the chain). Options:
1. **For Loop B watched wallets:** Compute CFR from live WebSocket orderbook monitoring (can see placements and cancellations in real-time)
2. **For historical scans:** Skip CFR, use 11-dimension vector. MTR + Burstiness + CLV are the three most discriminating anyway.
3. **Future:** If we get CLOB API access with user filtering, we could reconstruct CFR from historical order data.

**Decision:** Use 11-dim for discovery scans, 12-dim for actively watched wallets.

## Additional Metrics Beyond MVF (Phase 2+)

Research identified these as valuable but higher compute cost:
- **Brier Score Decomposition** — calibration measurement per price bucket
- **Trade-Price Cross Correlation (lagged)** — lead-lag detection, requires tick data
- **Mutual Information** — non-linear predictability, needs 500+ trades
- **HHI (Herfindahl)** — capital concentration across markets
- **Sortino Ratio** — better than Sharpe for binary markets (leptokurtic returns)

## Exemplar Selector Criteria

After computing MVF, select raw trades for LLM context:
1. Top 10 by absolute PnL (winners AND losers)
2. Top 5 by size
3. 5-10 trades around resolution or large price moves (>5% in <30 min)
4. Trades that DON'T fit the statistical fingerprint (anomalies)
5. Trades placed within first 5% of market lifecycle (early information signal)
6. Trades on opposite side of final resolution (contrarian or insider signal)

Each exemplar gets a one-line annotation: "This trade is unusual because X"

## Implementation Notes
- All metrics computable with numpy, scipy, pandas, statsmodels
- 1000 wallets in <1 hour on laptop is feasible for all 12 dimensions
- Minimum sample size for skill vs luck: ~600 trades at 50% baseline, ~800 at 90% pricing
- Lifecycle Entry/Exit require market creation timestamps from Gamma API
