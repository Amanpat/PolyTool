# Feature: Scan Exact Slug Export

## Problem

`scan-gate2-candidates` truncates long market slugs in the terminal table to keep
the layout readable. That is fine for ranking review, but unsafe for operators
who need to copy an exact slug into `watch-arb-candidates`.

## Change

Add `--watchlist-out PATH` to `python -m polytool scan-gate2-candidates`.

When provided, the command writes the exact full slugs for the shown ranked
candidates to `PATH`, one slug per line, in the same order as the printed table.

## Usage

```bash
python -m polytool scan-gate2-candidates --top 10 --watchlist-out artifacts/watchlists/gate2_top10.txt
```

## Guarantees

- Default output stays unchanged when `--watchlist-out` is not used
- Ranking logic stays unchanged
- Exported slugs are exact and untruncated
