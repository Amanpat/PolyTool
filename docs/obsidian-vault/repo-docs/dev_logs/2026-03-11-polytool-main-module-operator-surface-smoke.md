---
title: Polytool Main Module Operator Surface Smoke
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-03-11_polytool_main_module_operator_surface_smoke.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# Dev Log: PolyTool Main-Module Operator Surface Smoke

**Date:** 2026-03-11
**Branch:** codex/tracka-adverse-selection-default-wiring

## Summary

Extended the focused `python -m polytool` smoke coverage to the exact operator help
surfaces now relied on after the main-module entrypoint fix, and added one small
offline main-module invocation for `scan-gate2-candidates` using a synthetic local
`tapes-dir` fixture.

## What changed

### `tests/test_polytool_main_module_smoke.py`

- Kept the real subprocess `python -m polytool ...` smoke pattern.
- Added help coverage for:
  - `python -m polytool --help`
  - `python -m polytool simtrader run --help`
  - `python -m polytool scan-gate2-candidates --help`
  - `python -m polytool scan-gate2-candidates --regime politics --help`
- Added one offline invocation smoke test for:
  - `python -m polytool scan-gate2-candidates --tapes-dir <tmp> --regime politics --top 1`
- Used a tiny local tape fixture with two book snapshots, one batched `price_change`,
  and minimal `meta.json` regime metadata so the command stays fully offline.

## Scope notes

- No `polytool/__main__.py` routing changes were needed.
- No SimTrader behavior changed.
- No scanner behavior changed.
- No MarketMaker, adverse-selection, watcher, or session-pack work was touched.

## Tests run

```bash
pytest -q tests/test_polytool_main_module_smoke.py
python -m polytool --help
python -m polytool simtrader run --help
python -m polytool scan-gate2-candidates --help
python -m polytool scan-gate2-candidates --regime politics --help
```
