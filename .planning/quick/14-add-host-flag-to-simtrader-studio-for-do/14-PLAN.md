---
phase: quick-14
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/cli/simtrader.py
  - tests/test_simtrader_studio.py
  - docs/README_SIMTRADER.md
autonomous: true

must_haves:
  truths:
    - "`simtrader studio` accepts `--host` with default 127.0.0.1"
    - "Uvicorn binds to the provided `--host` value"
    - "Existing behavior (no flags) is identical to before"
    - "Docs describe `--host 0.0.0.0` for Docker and warn against `--open` in containers"
  artifacts:
    - path: "tools/cli/simtrader.py"
      provides: "--host argument in studio subparser + args.host wired into uvicorn.run"
    - path: "tests/test_simtrader_studio.py"
      provides: "Parser tests for --host default and explicit value"
    - path: "docs/README_SIMTRADER.md"
      provides: "Docker binding note in Studio section"
  key_links:
    - from: "studio_p.add_argument('--host')"
      to: "_studio() host = args.host"
      via: "args.host attribute"
      pattern: "args\\.host"
    - from: "_studio() host"
      to: "uvicorn.run(app, host=host, port=port)"
      via: "local variable"
      pattern: "uvicorn\\.run\\(app, host=host"
---

<objective>
Add `--host` flag to the `simtrader studio` subcommand so the server can bind to `0.0.0.0` for Docker deployments.

Purpose: The host is currently hardcoded to `127.0.0.1`, making it impossible to expose the studio in Docker without modifying source. A flag keeps the safe default for local use while enabling container deployments.
Output: Updated CLI with `--host` flag, 2 new parser tests, and a Docker note in docs.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add --host flag to CLI and wire it into uvicorn</name>
  <files>tools/cli/simtrader.py</files>
  <action>
    Two edits in tools/cli/simtrader.py:

    **Edit 1 — subparser (around line 3888, after the --open argument block):**
    Insert a new `studio_p.add_argument` call for `--host` immediately after the existing `--open` block and before `return parser`:

    ```python
    studio_p.add_argument(
        "--host",
        default="127.0.0.1",
        help=(
            "Host/IP to bind the studio server (default: 127.0.0.1). "
            "Use 0.0.0.0 to bind all interfaces (e.g. inside Docker). "
            "Note: --open is not useful inside Docker containers."
        ),
    )
    ```

    **Edit 2 — _studio() handler (around line 4492):**
    Replace the hardcoded line:
    ```python
    host = "127.0.0.1"
    ```
    with:
    ```python
    host = args.host
    ```

    No other changes. The `url` construction and `uvicorn.run` call already use the `host` local variable, so they pick up the new value automatically.
  </action>
  <verify>
    python -m pytest tests/test_simtrader_studio.py -v --tb=short -q
    python -c "from tools.cli.simtrader import _build_parser; p = _build_parser(); a = p.parse_args(['studio']); assert a.host == '127.0.0.1', a.host; a2 = p.parse_args(['studio', '--host', '0.0.0.0']); assert a2.host == '0.0.0.0', a2.host; print('OK')"
  </verify>
  <done>
    `python -m polytool simtrader studio --help` shows `--host HOST` with default 127.0.0.1.
    Parser roundtrip: default resolves to 127.0.0.1, `--host 0.0.0.0` resolves to 0.0.0.0.
    Existing studio tests still pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Add parser tests and update docs</name>
  <files>tests/test_simtrader_studio.py, docs/README_SIMTRADER.md</files>
  <action>
    **tests/test_simtrader_studio.py** — append two new tests at the end of the file (no import changes needed; uses `_build_parser` from tools.cli.simtrader, no fastapi required):

    ```python
    # ---------------------------------------------------------------------------
    # Test N: studio subparser --host flag
    # ---------------------------------------------------------------------------


    def test_studio_parser_host_default():
        """--host defaults to 127.0.0.1."""
        from tools.cli.simtrader import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["studio"])
        assert args.host == "127.0.0.1"


    def test_studio_parser_host_explicit():
        """--host 0.0.0.0 is accepted and stored on args."""
        from tools.cli.simtrader import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["studio", "--host", "0.0.0.0"])
        assert args.host == "0.0.0.0"
    ```

    **docs/README_SIMTRADER.md** — find the Studio section (around line 231) and replace:

    ```
    Starts a FastAPI server at `http://127.0.0.1:8765` and opens your browser. Use the tabs to trigger quickrun, shadow, browse, clean, and report actions without memorizing CLI flags.

    Install deps first: `pip install polytool[studio]`
    ```

    with:

    ```
    Starts a FastAPI server at `http://127.0.0.1:8765` and opens your browser. Use the tabs to trigger quickrun, shadow, browse, clean, and report actions without memorizing CLI flags.

    **Docker / remote binding:** pass `--host 0.0.0.0` to bind all interfaces:

    ```bash
    python -m polytool simtrader studio --host 0.0.0.0 --port 8765
    ```

    Note: `--open` launches a local browser and has no effect inside a Docker container — omit it when running in a container.

    Install deps first: `pip install polytool[studio]`
    ```
  </action>
  <verify>
    python -m pytest tests/test_simtrader_studio.py -v --tb=short -q
    grep -n "0.0.0.0" docs/README_SIMTRADER.md
  </verify>
  <done>
    Two new tests (`test_studio_parser_host_default`, `test_studio_parser_host_explicit`) pass.
    docs/README_SIMTRADER.md contains a Docker binding note with `--host 0.0.0.0` example and the `--open` warning.
    All existing studio tests still pass.
  </done>
</task>

</tasks>

<verification>
Run the full studio test suite:

```bash
python -m pytest tests/test_simtrader_studio.py tests/test_simtrader_studio_sessions.py -v --tb=short
```

Smoke-check the parser:

```bash
python -c "
from tools.cli.simtrader import _build_parser
p = _build_parser()
a = p.parse_args(['studio'])
assert a.host == '127.0.0.1'
assert a.port == 8765
a2 = p.parse_args(['studio', '--host', '0.0.0.0', '--port', '9000'])
assert a2.host == '0.0.0.0'
assert a2.port == 9000
print('parser OK')
"
```
</verification>

<success_criteria>
- `studio_p` has a `--host` argument with default `"127.0.0.1"` and a help string mentioning Docker and the `--open` caveat.
- `_studio()` uses `host = args.host` instead of the hardcoded string.
- `uvicorn.run(app, host=host, port=port, ...)` is unchanged in structure.
- Two new tests pass: default host and explicit `0.0.0.0`.
- All pre-existing studio tests continue to pass.
- `docs/README_SIMTRADER.md` Studio section includes a Docker binding example and `--open` warning.
</success_criteria>

<output>
After completion, create `.planning/quick/14-add-host-flag-to-simtrader-studio-for-do/14-SUMMARY.md`
</output>
