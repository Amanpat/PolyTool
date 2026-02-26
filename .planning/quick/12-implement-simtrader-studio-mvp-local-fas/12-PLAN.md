---
phase: quick-12
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - packages/polymarket/simtrader/studio/__init__.py
  - packages/polymarket/simtrader/studio/app.py
  - packages/polymarket/simtrader/studio/static/index.html
  - tools/cli/simtrader.py
  - pyproject.toml
  - tests/test_simtrader_studio.py
  - docs/features/FEATURE-simtrader-studio.md
  - docs/README_SIMTRADER.md
autonomous: true

must_haves:
  truths:
    - "`python -m polytool simtrader studio` starts a FastAPI server on localhost:8765 without error"
    - "GET / returns 200 with HTML containing the Studio UI (tabs: Dashboard, Sessions, Tapes, Reports)"
    - "GET /api/artifacts returns JSON list of recent artifacts from artifacts/simtrader/"
    - "GET /api/artifacts returns empty list (not error) when no artifacts exist"
    - "Two unit tests pass: server boots and returns 200, artifact list endpoint returns list"
  artifacts:
    - path: "packages/polymarket/simtrader/studio/__init__.py"
      provides: "package marker"
    - path: "packages/polymarket/simtrader/studio/app.py"
      provides: "FastAPI app with / and /api/artifacts routes"
      exports: ["app", "create_app"]
    - path: "packages/polymarket/simtrader/studio/static/index.html"
      provides: "single-page UI with Dashboard/Sessions/Tapes/Reports tabs"
    - path: "tests/test_simtrader_studio.py"
      provides: "unit tests for studio server"
      contains: "test_root_returns_200, test_artifacts_endpoint"
    - path: "docs/features/FEATURE-simtrader-studio.md"
      provides: "feature documentation"
  key_links:
    - from: "tools/cli/simtrader.py"
      to: "packages/polymarket/simtrader/studio/app.py"
      via: "_studio() handler imports and runs uvicorn"
      pattern: "from packages.polymarket.simtrader.studio"
    - from: "packages/polymarket/simtrader/studio/app.py"
      to: "tools/cli/simtrader.py _collect_recent_artifacts logic"
      via: "/api/artifacts endpoint reuses artifact-scanning logic"
      pattern: "DEFAULT_ARTIFACTS_DIR"
---

<objective>
Implement SimTrader Studio: a local FastAPI web UI launched via `python -m polytool simtrader studio --open` that consolidates common CLI actions into a single browser page.

Purpose: Replace the need to memorize and type multiple CLI invocations by providing a browser-based control panel for all SimTrader operations.
Output: FastAPI studio module, vanilla HTML+JS single-page UI, CLI subcommand wiring, two unit tests, and updated docs.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@tools/cli/simtrader.py
@packages/polymarket/simtrader/report.py
@docs/README_SIMTRADER.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create studio FastAPI module and static UI</name>
  <files>
    packages/polymarket/simtrader/studio/__init__.py
    packages/polymarket/simtrader/studio/app.py
    packages/polymarket/simtrader/studio/static/index.html
  </files>
  <action>
Create `packages/polymarket/simtrader/studio/` package.

`__init__.py`: empty (package marker).

`app.py`:
- Import `fastapi`, `fastapi.staticfiles`, `fastapi.responses.HTMLResponse`, `pathlib.Path`, `json`, `re`, `datetime`.
- Define `DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")`.
- Define `_BROWSE_TYPE_DIRS = {"sweep": "sweeps", "batch": "batches", "run": "runs", "shadow": "shadow_runs"}` matching the CLI constants.
- Define `_BROWSE_TS_RE = re.compile(r"(20\d{6}T\d{6}Z)")` for timestamp extraction.
- `create_app(artifacts_dir: Path = DEFAULT_ARTIFACTS_DIR) -> FastAPI`: factory so tests can pass a temp dir.
  - Mount `static/` directory (relative to `app.py`) as StaticFiles at `/static`.
  - Route `GET /`: serve `static/index.html` as HTMLResponse.
  - Route `GET /api/artifacts`: scan each subdir in `_BROWSE_TYPE_DIRS`, collect artifact dirs that contain `run_manifest.json` or `meta.json`, extract `artifact_type`, `artifact_id` (dirname), `timestamp` (from TS regex match on dirname or file mtime isoformat), `has_report` (bool: `report.html` exists). Return sorted by timestamp desc, limit 50. Return `{"artifacts": [...]}`. On any OS error for a single dir, skip it (do not crash). If `artifacts_dir` does not exist, return `{"artifacts": []}`.
  - Route `POST /api/run`: accept JSON body `{"command": str, "args": list[str]}`. Validate `command` is one of `["quickrun","shadow","run","sweep","batch","diff","clean","report","browse"]`. Launch `subprocess.Popen(["python", "-m", "polytool", "simtrader", command, *args], stdout=PIPE, stderr=STDOUT, text=True)`. Stream output lines. Return `{"output": "...combined stdout/stderr...", "returncode": int}` after process completes (wait up to 300s). If command not in allowlist, return 400 `{"error": "command not allowed"}`.
- `app = create_app()` at module bottom.

`static/index.html`: Self-contained vanilla HTML+JS, no external CDN deps.
- Title: "SimTrader Studio".
- Minimal CSS: dark-ish background (#1a1a2e), card style for panels, tab nav bar, monospace font for output.
- Four tabs: Dashboard, Sessions, Tapes, Reports. Tab switching via JS classList toggle (no page reload).
- **Dashboard tab**: Shows "Quick Actions" buttons: [quickrun --dry-run], [shadow --dry-run], [browse], [clean --yes]. Each button POSTs to `/api/run` with the corresponding command+args, displays output in a `<pre>` below. Also shows "Last 10 Artifacts" list fetched from `GET /api/artifacts` on page load and refreshed on a 30s interval via `setInterval`. Each artifact row shows: type, id, timestamp, and a "Report" link (if has_report) opening `/static/...` -- actually just the artifact dir path shown as text (we can't serve arbitrary paths; just show the path as copyable text).
- **Sessions tab**: Fetches `/api/artifacts` and filters to type=run and type=shadow. Displays in a table: type, id, timestamp, has_report. Static label "Completed runs and shadow sessions".
- **Tapes tab**: Fetches `/api/artifacts` but artifacts/simtrader/tapes/ is NOT in _BROWSE_TYPE_DIRS (tapes are raw recordings, not structured artifacts). For this tab, separately call `GET /api/tapes` endpoint. Add a `GET /api/tapes` route in app.py that scans `artifacts/simtrader/tapes/`, lists dirs containing `events.jsonl`, returns `{"tapes": [{"tape_id": str, "timestamp": str, "has_events": true}]}`. JS shows tapes in a list with a "Run Report" button that POSTs to `/api/run` with `{"command": "report", "args": ["--path", tape_path]}` -- no, report needs a run dir not tape. Instead, show "Open" button that triggers `browse` command (just shows path). Keep it simple: show tape_id and timestamp, button to copy path.
- **Reports tab**: Fetches `/api/artifacts`, shows all artifacts with has_report=true. Each row has a "View" button: since the server can't serve arbitrary file paths outside /static, clicking "View" POSTs `{"command": "report", "args": ["--path", artifact_dir_path]}` to generate/regenerate, then shows the output. Add a text input to manually paste an artifact dir path and generate report for it.
- JS fetch wrapper: async function `apiFetch(url, opts)` with try/catch showing errors in a status bar div at bottom.
- Status bar: fixed bottom strip showing last action result or error.

Note: Do NOT use any Python web framework other than FastAPI. Do NOT use Jinja2 templates (inline HTML string in the route is fine, but since we have a static file that is cleaner). The static/index.html approach avoids template deps.
  </action>
  <verify>
```bash
cd "/d/Coding Projects/Polymarket/PolyTool" && python -c "
from packages.polymarket.simtrader.studio.app import create_app
app = create_app()
routes = [r.path for r in app.routes]
assert '/' in routes, f'Missing / route, got: {routes}'
print('Studio app imports OK, routes:', routes)
"
```
  </verify>
  <done>
`create_app()` imports without error, returns a FastAPI app with `/`, `/api/artifacts`, `/api/tapes`, `/api/run` routes, and `static/index.html` exists with the four-tab UI structure.
  </done>
</task>

<task type="auto">
  <name>Task 2: Wire studio subcommand into CLI and add optional dep</name>
  <files>
    tools/cli/simtrader.py
    pyproject.toml
  </files>
  <action>
In `tools/cli/simtrader.py`:

1. Add `_studio()` handler function (near end of handlers, before `main()`):

```python
def _studio(args: argparse.Namespace) -> int:
    """Launch SimTrader Studio local web UI."""
    try:
        import uvicorn
        from packages.polymarket.simtrader.studio.app import create_app
    except ImportError as exc:
        print(
            f"Error: SimTrader Studio requires 'fastapi' and 'uvicorn'. "
            f"Install with: pip install polytool[studio]\n  Detail: {exc}",
            file=sys.stderr,
        )
        return 1

    host = "127.0.0.1"
    port = args.port
    url = f"http://{host}:{port}"
    print(f"[simtrader studio] Starting SimTrader Studio at {url}")
    print(f"[simtrader studio] Press Ctrl-C to stop.")

    if args.open:
        import threading, webbrowser
        def _open_browser():
            import time; time.sleep(1.2)
            webbrowser.open(url)
        threading.Thread(target=_open_browser, daemon=True).start()

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")
    return 0
```

2. In `_build_parser()`, after the `clean_p` block and before the closing `return parser`, add:

```python
studio_p = sub.add_parser(
    "studio",
    help="Launch SimTrader Studio local web UI (FastAPI + browser UI).",
)
studio_p.add_argument(
    "--port",
    type=int,
    default=8765,
    help="Port to bind the studio server (default: 8765).",
)
studio_p.add_argument(
    "--open",
    action="store_true",
    default=False,
    help="Open browser automatically after server starts.",
)
```

3. In `main()`, add dispatch before `parser.print_help()`:

```python
if args.subcommand == "studio":
    return _studio(args)
```

In `pyproject.toml`, add `studio` optional dep group under `[project.optional-dependencies]`:

```toml
studio = [
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
]
```

Also add `"polytool[studio]"` to the `all` group so it reads:
`"polytool[rag,mcp,simtrader,studio,dev]"`.
  </action>
  <verify>
```bash
cd "/d/Coding Projects/Polymarket/PolyTool" && python -m polytool simtrader studio --help
```
Output should show `--port` and `--open` arguments without error.
  </verify>
  <done>
`python -m polytool simtrader studio --help` exits 0 and shows the studio subcommand help. `pyproject.toml` has `studio = ["fastapi>=0.100.0", "uvicorn>=0.23.0"]` under optional-dependencies.
  </done>
</task>

<task type="auto">
  <name>Task 3: Unit tests and documentation</name>
  <files>
    tests/test_simtrader_studio.py
    docs/features/FEATURE-simtrader-studio.md
    docs/README_SIMTRADER.md
  </files>
  <action>
**`tests/test_simtrader_studio.py`:**

Use `httpx` + `fastapi.testclient.TestClient` (both ship with FastAPI test extras; TestClient only needs `httpx` as a dep). Skip the whole module if fastapi is not installed:

```python
pytest.importorskip("fastapi", reason="fastapi not installed; skip studio tests")
```

Test 1 — `test_root_returns_200`:
```python
def test_root_returns_200(tmp_path):
    from packages.polymarket.simtrader.studio.app import create_app
    from fastapi.testclient import TestClient
    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "SimTrader Studio" in resp.text
```

Test 2 — `test_artifacts_endpoint_empty`:
```python
def test_artifacts_endpoint_empty(tmp_path):
    from packages.polymarket.simtrader.studio.app import create_app
    from fastapi.testclient import TestClient
    app = create_app(artifacts_dir=tmp_path / "nonexistent")
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert "artifacts" in data
    assert data["artifacts"] == []
```

Test 3 — `test_artifacts_endpoint_with_run`:
```python
def test_artifacts_endpoint_with_run(tmp_path):
    from packages.polymarket.simtrader.studio.app import create_app
    from fastapi.testclient import TestClient
    import json
    # Create a fake run artifact
    run_dir = tmp_path / "runs" / "20260226T120000Z_testmarket"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text(json.dumps({"artifact_type": "run"}))
    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.get("/api/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["artifact_type"] == "run"
```

Test 4 — `test_run_endpoint_rejects_unknown_command`:
```python
def test_run_endpoint_rejects_unknown_command(tmp_path):
    from packages.polymarket.simtrader.studio.app import create_app
    from fastapi.testclient import TestClient
    app = create_app(artifacts_dir=tmp_path)
    client = TestClient(app)
    resp = client.post("/api/run", json={"command": "rm", "args": ["-rf", "/"]})
    assert resp.status_code == 400
```

**`docs/features/FEATURE-simtrader-studio.md`:**

Write a feature doc with a short plain-English paragraph at the top, then sections:

```markdown
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
| GET | /api/tapes | Lists recorded tapes |
| POST | /api/run | Runs a SimTrader CLI subcommand (allowlist enforced) |
```

**`docs/README_SIMTRADER.md`:**

Find the existing table of contents or section list near the top and add "Studio" section. Insert after the "Fast dev loop" section (or wherever browse/report are referenced) a new section:

```markdown
## Studio (local web UI)

SimTrader Studio provides a browser UI for common workflows:

```bash
python -m polytool simtrader studio --open
```

Starts a FastAPI server at `http://127.0.0.1:8765` and opens your browser. Use the tabs to trigger quickrun, shadow, browse, clean, and report actions without memorizing CLI flags.

Install deps first: `pip install polytool[studio]`
```
  </action>
  <verify>
```bash
cd "/d/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_simtrader_studio.py -v --tb=short 2>&1 | tail -20
```
All four tests should pass (or skip if fastapi not installed, which is acceptable — document as optional).
  </verify>
  <done>
`tests/test_simtrader_studio.py` exists with 4 tests, all pass when fastapi+httpx are installed (skip gracefully otherwise). `docs/features/FEATURE-simtrader-studio.md` exists with plain-English opening paragraph. `docs/README_SIMTRADER.md` has a "Studio" section.
  </done>
</task>

</tasks>

<verification>
1. `python -m polytool simtrader studio --help` exits 0 and shows --port, --open flags
2. `python -c "from packages.polymarket.simtrader.studio.app import create_app, app"` imports without error
3. `python -m pytest tests/test_simtrader_studio.py -v --tb=short` — all tests pass or skip cleanly
4. `static/index.html` contains the four tab names: Dashboard, Sessions, Tapes, Reports
5. `FEATURE-simtrader-studio.md` exists and is non-empty
6. `docs/README_SIMTRADER.md` contains "Studio" section
</verification>

<success_criteria>
- `simtrader studio` subcommand is registered and dispatches correctly
- FastAPI app serves `/` (HTML) and `/api/artifacts` (JSON) correctly
- `/api/run` allowlist rejects arbitrary commands (returns 400)
- Unit tests cover server boot (200), empty artifacts, populated artifacts, command rejection
- Feature doc and README section are in place
- All existing tests continue to pass (no regressions to the 883 passing tests)
</success_criteria>

<output>
After completion, create `.planning/quick/12-implement-simtrader-studio-mvp-local-fas/12-SUMMARY.md`
</output>
