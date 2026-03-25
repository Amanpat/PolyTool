# 2026-03-08 Dev Log: Regime Policy Utility

## What changed

Added a small pure helper at `packages/polymarket/market_selection/regime_policy.py`
for Track A mixed-regime policy checks.

## API

- `classify_market_regime(market, *, reference_time=None, new_market_max_age_hours=48.0) -> str`
- `check_mixed_regime_coverage(markets, *, reference_time=None, new_market_max_age_hours=48.0) -> dict`

## Policy behavior

- Primary classification is a single label: `politics`, `sports`, `new_market`, or `other`.
- Politics and sports are inferred from slug/question/category/tag-style text.
- `new_market` is inferred from explicit "new market" text or deterministic age data.
- Age checks are pure:
  - `age_hours` / `ageHours` can be supplied directly.
  - Otherwise the helper compares `created_at`-style fields to an explicit
    `reference_time`.
- The 48-hour rule is strict: a market is "new" only when age is `< 48.0` hours.

## Coverage behavior

- `check_mixed_regime_coverage` reports:
  - `satisfies_policy`
  - `covered_regimes`
  - `missing_regimes`
  - `regime_counts`
- Coverage treats `new_market` as orthogonal to the primary regime so a recent
  sports or politics market can satisfy both its base category and the
  `new_market` requirement.
- Politics vs sports stays single-label to avoid double-counting ambiguous text
  across both base categories.

## Non-goals

- No integration with scan/watch/tape capture, gates, Discord, or runtime market
  selection.
- No network, filesystem, env, or CLI access.
