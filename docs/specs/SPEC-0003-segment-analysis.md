# SPEC-0003: Segment Analysis for Scan Trust Artifacts

**Status**: Accepted  
**Created**: 2026-02-16

## Overview

`polytool scan` now produces deterministic position-segmentation outputs so users can
see where performance comes from (entry price tiers, market type, league, sport)
without dropping uncertain rows.

## Entry Price Tier Configuration

Source: local `polytool.yaml` (`segment_config.entry_price_tiers`).

Expected shape:

```yaml
segment_config:
  entry_price_tiers:
    - name: "deep_underdog"
      max: 0.30
    - name: "underdog"
      min: 0.30
      max: 0.45
    - name: "coinflip"
      min: 0.45
      max: 0.55
    - name: "favorite"
      min: 0.55
```

If config is missing or invalid, defaults are used:

- `deep_underdog`: `< 0.30`
- `underdog`: `0.30 <= price < 0.45`
- `coinflip`: `0.45 <= price < 0.55`
- `favorite`: `>= 0.55`

Rows with missing/non-numeric `entry_price` map to `unknown`.

## Position-Derived Classification Rules

### League

Priority:

1. Split `market_slug` on `-`, take the first token.
2. If token is a known league code, use it.
3. Else `unknown`.

### Sport

Derived only from league mapping:

- `nba`, `wnba`, `ncaamb` -> `basketball`
- `nfl`, `ncaafb` -> `american_football`
- `mlb` -> `baseball`
- `nhl` -> `hockey`
- `epl`, `lal`, `elc`, `ucl`, `mls` -> `soccer`
- `atp`, `wta` -> `tennis`
- `ufc` -> `mma`
- `pga` -> `golf`
- `nascar`, `f1` -> `motorsport`
- `unknown` -> `unknown`

### Market Type

Allowed values: `moneyline`, `spread`, `unknown`.

Rules:

1. If `question` or `market_slug` contains `spread` or `handicap` -> `spread`.
2. Else if `question` matches `Will .* win` (case-insensitive) -> `moneyline`.
3. Else `unknown`.

No row is dropped; unknowns are explicit buckets.

## Segment Metrics Schema

`coverage_reconciliation_report.json` adds top-level `segment_analysis`:

- `by_entry_price_tier`
- `by_market_type`
- `by_league`
- `by_sport`

Each segment entry includes:

- `count`
- `wins`
- `losses`
- `profit_exits`
- `loss_exits`
- `win_rate`
- `total_pnl_net`

Win-rate formula (playbook-aligned):

```
win_rate = (WIN + PROFIT_EXIT) / (WIN + LOSS + PROFIT_EXIT + LOSS_EXIT)
```

`PENDING` and `UNKNOWN_RESOLUTION` are excluded from denominator.

## Schema Versioning

Because `coverage_reconciliation_report.json` gained a new top-level field
(`segment_analysis`), report schema version is bumped:

- from `report_version = "1.0.0"`
- to `report_version = "1.1.0"`

## Artifact Emission

Each scan run now emits:

- `coverage_reconciliation_report.json` (extended with `segment_analysis`)
- `coverage_reconciliation_report.md` (adds Segment Highlights)
- `segment_analysis.json`
- `run_manifest.json` with `output_paths.segment_analysis_json`

All manifest output paths are forward-slash normalized (`Path.as_posix()`).
