# Feature: Audit Default — All Positions

The audit coverage report now includes **all positions by default**, giving you a
complete picture of your scan run without needing any extra flags.

## What changed

Previously, running `audit-coverage` or adding `--audit-sample` to `scan` would
only show a small sample of 25 positions.  The report heading said
`## Samples (25)`.

Now:

- `python -m polytool audit-coverage --user "@you"` → includes every position,
  heading reads `## All Positions (N)`.
- `python -m polytool scan --user "@you" ...` → always emits an audit report with
  all positions; `audit_coverage_report_md` is always in the manifest.

## How to limit (if you need to)

Pass `--sample N` (audit-coverage) or `--audit-sample N` (scan) to cap at N
positions.  The report heading switches to `## Samples (N)` and the subset is
chosen deterministically using `--seed` / `--audit-seed` (default: 1337).

```bash
# All positions (default):
python -m polytool audit-coverage --user "@you"

# Limit to 25:
python -m polytool audit-coverage --user "@you" --sample 25 --seed 1337

# scan — all positions:
python -m polytool scan --user "@you"

# scan — limit to 25:
python -m polytool scan --user "@you" --audit-sample 25 --audit-seed 1337
```

## Why

A fixed 25-position sample silently excluded the tail of large portfolios.
Defaulting to ALL ensures no positions are invisibly omitted from the trust audit.
See [ADR-0011](../adr/0011-audit-default-all-positions.md) for the full decision
record.
