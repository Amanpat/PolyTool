# DEBUG: Windows PermissionError in pytest temp dirs

## What failed

`pytest -x -vv` initially failed with `PermissionError` before/early in test execution.

First observed signatures:

```text
PermissionError: [WinError 5] Access is denied: '...\\tests\\pytest_tmp'
```

and

```text
PermissionError: [Errno 13] Permission denied: '...\\cache\\tmp...\\manifest.json'
```

The second error came from tests using `tempfile.TemporaryDirectory(...)` and then trying to write inside that directory.

## Root cause

In this Windows environment, pytest/tmpdir and `tempfile.TemporaryDirectory` produced temp directories with ACL/permission behavior that was unstable across runs/processes. That caused:

1. test collection/setup to fail when pytest touched stale temp roots;
2. tests to fail when writing inside newly-created temp dirs;
3. teardown/cleanup failures for temp dirs.

## Fix applied

1. Added global test isolation in `tests/conftest.py`:
   - repo-local isolated workspace per test session;
   - env vars set for isolated outputs:
     - `POLYTOOL_KB_ROOT`
     - `POLYTOOL_ARTIFACTS_ROOT`
     - `POLYTOOL_CACHE_DIR`
     - `TMPDIR` / `TEMP` / `TMP`
   - `tempfile.tempdir` redirected to isolated cache dir.

2. Hardened pytest temp handling in `tests/conftest.py`:
   - set unique per-run `basetemp` under `.tmp/pytest-basetemp/<uuid>`;
   - patched `TempPathFactory` temp dir creation to avoid restrictive mode in this environment;
   - patched cleanup to tolerate `PermissionError` on shutdown-only temp cleanup edge cases.

3. Stopped pytest from recursing into stale temp roots:
   - `norecursedirs` updated in `pyproject.toml`.

4. Disabled pytest cacheprovider (to avoid `.pytest_cache` write-path flakiness in this environment):
   - `addopts = "-v --tb=short -p no:cacheprovider"` in `pyproject.toml`.

5. Removed direct repo-path write in one RAG test:
   - `tests/test_rag.py::RAGTests::test_query_returns_stable_structure` now uses isolated temp roots + patched repo-root resolution.

## FastAPI collection behavior

FastAPI-dependent tests are gated as optional dependency tests using `pytest.importorskip("fastapi")` + `pytest.mark.optional_dep`:

- `tests/test_export_schema_guard.py`
- `tests/test_opportunities.py`
- `tests/test_snapshot_books_metadata_refresh.py`

Marker documented in `pyproject.toml`:

```toml
markers = ["optional_dep: tests that require optional third-party dependencies"]
```

## Validation

Commands run after fixes:

1. `pytest -q --maxfail=1` -> pass (`255 passed, 4 skipped`)
2. `pytest -x -vv` -> pass (`255 passed, 4 skipped`)
3. `pytest -q` -> pass (`255 passed, 4 skipped`)
