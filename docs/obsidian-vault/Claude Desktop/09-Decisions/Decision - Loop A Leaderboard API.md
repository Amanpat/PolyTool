---
tags: [decision]
date: 2026-04-09
status: accepted
---
# Decision — Loop A Leaderboard Discovery via Data API

## Context
Aman was manually copy-pasting usernames from the Polymarket leaderboard website. Research found an official public API endpoint.

## Decision
Use `GET https://data-api.polymarket.com/v1/leaderboard` for automated discovery:
- Fetch top 500 by PNL + top 500 by VOL across all categories every 24h
- Compare with previous snapshot to detect leaderboard churn (new/rising wallets)
- DAY leaderboard specifically catches fast-rising new wallets
- New wallets get priority queued for Loop C deep analysis
- Known wallets rescanned every 7-14 days if profile changed

## Why Not On-Chain Only
On-chain aggregation gives more complete data but is compute-heavy. The leaderboard API is free, instant, and curated by Polymarket. We use it as the primary discovery source, supplemented by on-chain analysis in Loop D for wallets not on the leaderboard.

See [[11-Prompt-Archive/2026-04-09 GLM5 - Polymarket Leaderboard API]], [[08-Research/01-Wallet-Discovery-Pipeline]]
