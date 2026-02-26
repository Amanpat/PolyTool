---
phase: quick-12
plan: "01"
subsystem: simtrader-studio
tags: [fastapi, web-ui, studio, simtrader, cli]
dependency_graph:
  requires:
    - packages/polymarket/simtrader/ (all existing subcommands)
    - tools/cli/simtrader.py (CLI wiring, _BROWSE_TYPE_DIRS, _BROWSE_TS_RE constants)
  provides:
    - packages/polymarket/simtrader/studio/ (FastAPI web UI package)
    - python -m polytool simtrader studio --open (new CLI subcommand)
    - GET /api/artifacts, /api/tapes, /api/run (REST API)
  affects:
    - tools/cli/simtrader.py (added _studio handler + studio subparser)
    - pyproject.toml (added studio optional dep group)
tech_stack:
  added:
    - fastapi>=0.100.0 (optional dep; already installed in environment)
    - uvicorn>=0.23.0 (optional dep)
  patterns:
    - FastAPI factory pattern (create_app(artifacts_dir) for testability)
    - Lazy import of uvicorn in CLI handler (graceful ImportError)
    - Subprocess-based command dispatch with explicit allowlist
    - Vanilla HTML+JS SPA (no framework, no CDN deps)
key_files:
  created:
    - packages/polymarket/simtrader/studio/__init__.py
    - packages/polymarket/simtrader/studio/app.py
    - packages/polymarket/simtrader/studio/static/index.html
    - tests/test_simtrader_studio.py
    - docs/features/FEATURE-simtrader-studio.md
  modified:
    - tools/cli/simtrader.py
    - pyproject.toml
    - docs/README_SIMTRADER.md
decisions:
  - FastAPI factory pattern (create_app) for test isolation via tmp_path injection
  - /api/run allowlist = 9 existing subcommands; HTTP 400 on any unknown command
  - Server binds 127.0.0.1 only; no auth needed for localhost-only deployment
  - Static files served from packages/polymarket/simtrader/studio/static/ via StaticFiles mount
  - Subprocess uses sys.executable (not hardcoded "python") for correct venv resolution
  - Dashboard auto-refreshes artifact list every 30s via setInterval
  - Tapes listed from /api/tapes (separate route) since tapes/ is not in _BROWSE_TYPE_DIRS
metrics:
  duration_minutes: 6
  completed_date: "2026-02-26"
  tasks_completed: 3
  tasks_total: 3
  files_created: 5
  files_modified: 3
  tests_added: 7
  tests_total: 908
---

# Phase quick-12 Plan 01: SimTrader Studio MVP Summary

**One-liner:** FastAPI local web UI for SimTrader with Dashboard/Sessions/Tapes/Reports tabs, subprocess command dispatch, and 7 unit tests.

## What Was Built

SimTrader Studio is a local-first browser control panel for SimTrader, implemented as a FastAPI application served by uvicorn. The `python -m polytool simtrader studio --open` command starts the server on `localhost:8765` and optionally opens the browser.

### Core module: `packages/polymarket/simtrader/studio/app.py`

- `create_app(artifacts_dir)` factory — returns a fully configured FastAPI app; `artifacts_dir` param enables test isolation
- `GET /` — serves `static/index.html` as HTMLResponse
- `GET /api/artifacts` — scans `_BROWSE_TYPE_DIRS` (sweep/batch/run/shadow) for dirs containing `run_manifest.json` or `meta.json`; returns sorted-by-timestamp list of up to 50 artifacts with `artifact_type`, `artifact_id`, `artifact_path`, `timestamp`, `has_report`
- `GET /api/tapes` — scans `artifacts/simtrader/tapes/` for dirs with `events.jsonl`
- `POST /api/run` — validates command against allowlist of 9 subcommands; launches `sys.executable -m polytool simtrader <cmd> <args>` via subprocess; returns `{output, returncode}`; returns HTTP 400 for non-allowlisted commands
- Module-level `app = create_app()` for uvicorn direct invocation

### UI: `packages/polymarket/simtrader/studio/static/index.html`

- Self-contained vanilla HTML+JS, no external CDN dependencies
- Dark theme (`#1a1a2e` background, `#e94560` accent)
- Four tabs (JS classList toggle, no page reload):
  - **Dashboard**: 4 quick action buttons + Last 10 Artifacts table (30s auto-refresh)
  - **Sessions**: run + shadow artifacts with report generation buttons
  - **Tapes**: tape list from `/api/tapes` with copy-path buttons
  - **Reports**: artifacts with `has_report=True` + manual path input for report generation
- Fixed status bar at bottom for last action result/error
- `apiFetch()` wrapper with error propagation to status bar

### CLI wiring: `tools/cli/simtrader.py`

- `_studio(args)` handler: lazy-imports uvicorn + studio app (prints install hint on ImportError), handles `--open` with a daemon thread + 1.2s delay, runs uvicorn
- `studio` subparser: `--port` (default 8765), `--open` flag
- Dispatch added in `main()` before `parser.print_help()`

### pyproject.toml

- `studio = ["fastapi>=0.100.0", "uvicorn>=0.23.0"]` optional dep group
- `all` group updated to `polytool[rag,mcp,simtrader,studio,dev]`
- `packages.polymarket.simtrader.studio` added to setuptools packages list

## Tests: `tests/test_simtrader_studio.py`

7 tests, all passing. Module-level `pytest.importorskip("fastapi")` skips gracefully if fastapi not installed.

| Test | What it covers |
|------|---------------|
| `test_root_returns_200` | GET / returns 200 + "SimTrader Studio" in body |
| `test_artifacts_endpoint_empty` | GET /api/artifacts returns `{"artifacts": []}` when dir doesn't exist |
| `test_artifacts_endpoint_with_run` | GET /api/artifacts returns 1 artifact for seeded run dir |
| `test_run_endpoint_rejects_unknown_command` | POST /api/run with "rm" returns HTTP 400 |
| `test_tapes_endpoint_empty` | GET /api/tapes returns `{"tapes": []}` when dir doesn't exist |
| `test_tapes_endpoint_with_tape` | GET /api/tapes returns 1 tape for seeded tape dir with events.jsonl |
| `test_artifacts_has_report_flag` | has_report=True when report.html present in artifact dir |

## Documentation

- `docs/features/FEATURE-simtrader-studio.md`: full feature doc with usage, install, architecture, API table, security notes, and tab descriptions
- `docs/README_SIMTRADER.md`: "Studio (local web UI)" section added after report/browse section

## Deviations from Plan

### Auto-added Issues

**1. [Rule 2 - Missing critical functionality] Added 3 extra tests beyond the 4 in plan**
- **Found during:** Task 3
- **Issue:** Plan specified 4 tests; added 3 more (tapes empty, tapes with tape, has_report flag) to cover the /api/tapes endpoint and has_report field which were implemented in Task 1
- **Fix:** Added test_tapes_endpoint_empty, test_tapes_endpoint_with_tape, test_artifacts_has_report_flag
- **Files modified:** tests/test_simtrader_studio.py
- **Commit:** c614630

**2. [Rule 2 - Missing critical functionality] Added `packages.polymarket.simtrader.studio` to pyproject.toml setuptools packages**
- **Found during:** Task 2
- **Issue:** Without this entry, the package would not be discoverable as an installed package
- **Fix:** Added `"packages.polymarket.simtrader.studio"` to `[tool.setuptools] packages` list
- **Files modified:** pyproject.toml
- **Commit:** 52a63fe

**3. [Rule 1 - Bug] Used `sys.executable` instead of hardcoded `"python"` in /api/run subprocess**
- **Found during:** Task 1
- **Issue:** Plan specified `["python", "-m", "polytool", ...]`; hardcoded "python" may resolve to wrong interpreter in virtual environments
- **Fix:** Used `sys.executable` for correct venv-aware resolution
- **Files modified:** packages/polymarket/simtrader/studio/app.py
- **Commit:** e061764

## Self-Check: PASSED

All 5 created files exist on disk. All 3 task commits (e061764, 52a63fe, c614630) found in git log. 908 tests pass with no regressions.
