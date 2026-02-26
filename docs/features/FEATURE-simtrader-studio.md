# SimTrader Studio

SimTrader Studio is a local browser-based control panel for SimTrader. Running `python -m polytool simtrader studio --open` starts a lightweight FastAPI server on `localhost:8765` and opens a single-page web UI in your default browser. The UI provides four tabs — Dashboard (quick action buttons and last 10 artifacts), Sessions (completed runs and shadow sessions), Tapes (recorded WS tapes), and Reports (artifact report viewer) — replacing the need to manually compose CLI commands for common workflows. All commands trigger existing SimTrader CLI subcommands via subprocess; no new backend logic is introduced.

## Usage

```bash
# Start studio and open browser automatically
python -m polytool simtrader studio --open

# Start on a custom port
python -m polytool simtrader studio --port 9000
```

## Installation

Requires FastAPI and uvicorn:

```bash
pip install polytool[studio]
# or with all extras:
pip install polytool[all]
```

## Architecture

- `packages/polymarket/simtrader/studio/app.py` — FastAPI app with three API routes
- `packages/polymarket/simtrader/studio/static/index.html` — vanilla HTML+JS UI
- `tools/cli/simtrader.py` — `_studio()` handler and `studio` subparser

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Serves index.html |
| GET | /api/artifacts | Lists recent artifacts from artifacts/simtrader/ |
| GET | /api/tapes | Lists recorded tapes from artifacts/simtrader/tapes/ |
| POST | /api/run | Runs a SimTrader CLI subcommand (allowlist enforced) |

## Security

- Server binds to `127.0.0.1` only (no external access).
- `/api/run` enforces an explicit allowlist of permitted subcommands: `quickrun`, `shadow`, `run`, `sweep`, `batch`, `diff`, `clean`, `report`, `browse`. Requests with any other command string receive HTTP 400.
- No authentication is required since the server is localhost-only.

## Tabs

**Dashboard** — Quick action buttons (quickrun --dry-run, shadow --dry-run, browse, clean --yes) and a "Last 10 Artifacts" table that auto-refreshes every 30 seconds.

**Sessions** — Filters the artifact list to `run` and `shadow` types. Shows a table of completed runs and shadow sessions with per-row report generation buttons.

**Tapes** — Lists tape directories from `artifacts/simtrader/tapes/` that contain `events.jsonl`. Shows tape IDs, timestamps, and a copy-path button.

**Reports** — Shows all artifacts that have an existing `report.html`. Also provides a manual path input to generate or regenerate a report for any artifact directory.
