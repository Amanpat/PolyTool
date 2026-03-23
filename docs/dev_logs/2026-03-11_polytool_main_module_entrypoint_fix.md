# Dev Log: PolyTool Main-Module Entrypoint Fix

**Date:** 2026-03-11
**Branch:** codex/tracka-adverse-selection-default-wiring

## Summary

Fixed the `python -m polytool` entrypoint break by stopping `polytool/__main__.py`
from eagerly importing every CLI module at import time. The entrypoint now lazy-loads
command modules only when the selected command is invoked, so unrelated missing CLI
modules no longer block top-level help or other operator verification paths.

## What changed

### `polytool/__main__.py`

- Replaced eager top-level CLI imports with small lazy wrapper entrypoints.
- Kept existing command names and routing behavior intact.
- Preserved the module-level `*_main` handler seam so existing monkeypatch-based
  routing tests still work.
- Left command implementations untouched; only import timing changed.

### `tests/test_polytool_main_module_smoke.py`

- Added focused subprocess smoke coverage for the real main-module path:
  - `python -m polytool --help`
  - `python -m polytool simtrader run --help`
  - `python -m polytool scan-gate2-candidates --help`

## Scope notes

- No SimTrader math changed.
- No scanner logic changed.
- No watcher or session-pack implementation logic changed.
- Missing optional CLI modules now fail only when explicitly invoked.

## Tests run

```bash
pytest -q tests/test_polytool_main_module_smoke.py tests/test_hypotheses_cli.py tests/test_market_selection.py
python -m polytool --help
python -m polytool simtrader run --help
python -m polytool scan-gate2-candidates --help
```
