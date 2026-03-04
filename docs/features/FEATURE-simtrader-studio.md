# SimTrader Studio

SimTrader Studio is a local browser-based control panel for SimTrader. Running `python -m polytool simtrader studio --open` starts a lightweight FastAPI server on `localhost:8765` and opens a single-page web UI in your default browser. The UI provides a workspace-based layout — each workspace is a panel that can be attached to a live session, an OnDemand replay, or a static artifact — replacing the need to manually compose CLI commands for common workflows. All commands trigger existing SimTrader CLI subcommands via subprocess; no new backend logic is introduced.

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

- `packages/polymarket/simtrader/studio/app.py` — FastAPI app with API routes
- `packages/polymarket/simtrader/studio/static/index.html` — vanilla HTML+JS UI
- `packages/polymarket/simtrader/studio/ondemand.py` — OnDemand replay session manager
- `packages/polymarket/simtrader/studio_sessions.py` — live session registry
- `tools/cli/simtrader.py` — `_studio()` handler and `studio` subparser

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | / | Serves index.html |
| GET | /api/artifacts | Lists recent artifacts from artifacts/simtrader/ |
| GET | /api/tapes | Lists recorded tapes from artifacts/simtrader/tapes/ |
| GET | /api/sessions | Lists active and completed sessions |
| GET | /api/sessions/{id}/monitor | Lightweight monitor snapshot (equity, fills, rejection counts) |
| POST | /api/run | Runs a SimTrader CLI subcommand (allowlist enforced) |

## Security

- Server binds to `127.0.0.1` only (no external access).
- `/api/run` enforces an explicit allowlist of permitted subcommands: `quickrun`, `shadow`, `run`, `sweep`, `batch`, `diff`, `clean`, `report`, `browse`. Requests with any other command string receive HTTP 400.
- No authentication is required since the server is localhost-only.

## Workspace Layout

Studio uses a grid of workspaces instead of fixed tabs. Each workspace card can be independently attached to a data source:

- **Session** — a running or completed shadow/replay session; shows equity curve, orders, fills, and rejection reasons from the monitor endpoint
- **OnDemand** — a replay scrubber attached to a recorded tape; lets you seek to any point in the tape and paper-trade with a chosen strategy config
- **Artifact** — a static artifact folder (run, sweep, batch); shows the existing report or summary

Workspaces are persisted in `localStorage` (key `simtrader_studio_state`, schema v1) across browser sessions. Persisted fields include workspace definitions, the active workspace ID, and the grid layout. Ephemeral state (live log text, in-flight loading flags) is not persisted. On schema mismatch the load silently no-ops, resetting to defaults.

The Settings panel provides **Export Layout JSON**, **Import Layout JSON**, and **Clear Saved Workspaces** for portability and recovery.

## OnDemand Scrubbing

The OnDemand workspace type attaches to a recorded tape and streams events through a strategy in a controlled replay session. You can:

- Seek forward through the tape at 1×, 2×, 4×, or max speed
- Swap the strategy config and re-run from the current position
- Paper-trade and observe fills, equity curve, and rejection counters

OnDemand sessions are the primary tool for iterating on a strategy after a live shadow run produces a tape.

## Monitor Cards

Each session workspace polls `GET /api/sessions/{id}/monitor` on a short interval (configurable, default 5 s) to show a lightweight snapshot:

- Current equity and unrealized PnL
- Total orders, fills, and open positions
- Per-reason rejection counter breakdown

Monitor data is cached on the frontend so the card remains readable even if a polling interval is missed.

## Planned: Live / Rewind Buttons

Two planned buttons will complete the Live practice + Rewind workflow:

- **▶ Live** — launches a shadow run directly inside the current workspace without leaving the UI; the workspace transitions from idle → live session automatically.
- **⏪ Rewind** — when a shadow run finishes and a tape is available, one click opens the tape in a new OnDemand workspace pre-attached to the same market context.

These buttons are not yet implemented; the underlying primitives (monitor endpoint, OnDemand sessions, workspace persistence) are in place.
