# Dev Log: Gate2 Preflight Main-Module Fix

**Date:** 2026-03-11
**Branch:** phase-1

## Summary

Restored the `python -m polytool gate2-preflight` operator path on `phase-1`.
The main-module dispatcher now routes `gate2-preflight` again, and the branch
has a standalone Gate 2 preflight CLI implementation so the entrypoint does not
rely on later operator-path modules that are not present on this branch.

## What changed

- Registered `gate2-preflight` in `polytool/__main__.py` and added it to top-level help.
- Added `tools/cli/gate2_preflight.py` with the historical Gate 2 readiness checks:
  - tape eligibility still requires simultaneous depth and edge
  - READY still requires at least one eligible tape plus politics, sports, and new_market coverage
  - exit codes remain 0 for READY, 2 for BLOCKED, 1 for CLI errors
- Added focused subprocess smoke coverage for:
  - `python -m polytool --help`
  - `python -m polytool gate2-preflight --help`
  - `python -m polytool gate2-preflight --tapes-dir <tmp>` with an offline READY corpus

## Scope notes

- No MarketMaker code changed.
- No watcher/session-pack logic changed.
- No scanner logic changed.
- No adverse-selection logic changed.
