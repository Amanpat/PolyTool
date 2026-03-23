# Dev Log: Main-Module Track A Help Surface Repair

**Date:** 2026-03-11
**Branch:** phase-1

## Summary

Repaired the `python -m polytool` main-module dispatcher on `phase-1` so the
expected Track A operator commands are visible again in top-level help and their
`--help` paths succeed, while preserving the standalone working
`gate2-preflight` implementation added earlier on this branch.

## What changed

- Restored the missing Track A command names in `polytool/__main__.py` top-level help:
  - `scan-gate2-candidates`
  - `watch-arb-candidates`
  - `tape-manifest`
  - `make-session-pack`
  - `gate2-preflight`
- Added help-safe dispatcher fallbacks in `polytool/__main__.py` for Track A
  commands whose later-branch modules are not present on `phase-1`.
- Kept `gate2-preflight` routed to the local standalone CLI implementation.
- Expanded focused subprocess smoke coverage for:
  - `python -m polytool --help`
  - `python -m polytool tape-manifest --help`
  - `python -m polytool scan-gate2-candidates --help`
  - `python -m polytool make-session-pack --help`
  - `python -m polytool watch-arb-candidates --help`
  - `python -m polytool gate2-preflight --help`
  - `python -m polytool gate2-preflight --tapes-dir <tmp>`

## Scope notes

- No MarketMaker code changed.
- No watcher/session-pack implementation logic changed.
- No scanner logic changed.
- No adverse-selection logic changed.
- No gate logic changed beyond preserving the existing `gate2-preflight` path.
