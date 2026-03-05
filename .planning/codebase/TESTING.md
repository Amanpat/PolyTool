# Testing Patterns

**Analysis Date:** 2026-03-05

## Test Framework

**Runner:**
- pytest 7.0+ (declared in `pyproject.toml` `[project.optional-dependencies].dev`)
- Config: `pyproject.toml` `[tool.pytest.ini_options]`

**Assertion Library:**
- pytest built-in `assert` (pytest-style tests)
- `unittest.TestCase` assertions (`assertEqual`, `assertIsNone`, etc.) in older tests

**Run Commands:**
```bash
pytest -v --tb=short              # Run all tests (default flags from pyproject.toml)
pytest tests/test_simtrader_arb.py  # Run a single test file
pytest -k "test_onchain"          # Run tests matching a pattern
pytest --cov                      # Coverage (pytest-cov installed)
```

**Default flags (from `pyproject.toml`):**
```toml
addopts = "-v --tb=short -p no:cacheprovider"
testpaths = ["tests"]
norecursedirs = ["tests/pytest_tmp", "tests/.pytest_tmp", ".tmp", "pytest_tmp", ".pytest_tmp"]
```

## Test File Organization

**Location:**
- All tests co-located in a flat `tests/` directory at project root
- No test files inside `packages/` or `tools/`

**Naming:**
- `test_<subject>.py` — e.g., `test_simtrader_arb.py`, `test_resolution_providers.py`
- For simtrader subsystems: `test_simtrader_<subsystem>.py` pattern — e.g., `test_simtrader_broker.py`, `test_simtrader_portfolio.py`, `test_simtrader_replay.py`

**Structure:**
```
tests/
├── __init__.py
├── _safe_cleanup.py          # Shared Windows-safe rmtree helper
├── conftest.py               # Global session setup: env isolation, tmpdir config
├── test_<subject>.py         # One file per major subject area
└── ...                       # 56 test files total, ~987 test functions
```

## Test Structure

**Module-level docstring pattern:**
Every test file opens with a docstring that lists the test plan in numbered categories:
```python
"""Tests for SimTrader tape replay and L2 book reconstruction.

Test plan
---------
1. L2Book snapshot:       applying a 'book' event initializes bids/asks correctly.
2. L2Book price_change:   delta events update levels; size-0 removes a level.
...
"""
```

**Suite Organization (pytest-style — dominant pattern):**
```python
class TestResolveSlug:
    def _picker(self, markets):
        """Private helper to construct the object under test."""
        ...

    def test_resolve_slug_binary_yes_no(self):
        """Standard binary market: outcomes ["Yes", "No"] → correct token mapping."""
        ...

    def test_resolve_slug_reversed_order(self):
        ...
```

**Suite Organization (unittest-style — used in older tests):**
```python
class TestOnChainCTFProvider(unittest.TestCase):
    def test_onchain_resolved_win(self):
        """Test on-chain resolution for winning outcome."""
        ...

if __name__ == "__main__":
    unittest.main()
```

Files using unittest style: `tests/test_resolution_providers.py`, `tests/test_rag.py`, `tests/test_user_context.py`
Files using pytest class style: `tests/test_simtrader_quickrun.py`, `tests/test_simtrader_replay.py`, `tests/test_simtrader_arb.py`
Standalone `def test_*` functions: also common alongside class-based tests in the same file.

**Visual section separators:**
```python
# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------
```
Used to separate constants, helper functions, and test classes within a file.

**Patterns:**
- Setup: inline construction (no `setUp`/`teardown` in pytest-style tests)
- Teardown: handled by `conftest.py` global workspace cleanup; test-specific temp dirs via `tmp_path` fixture or `tempfile.TemporaryDirectory`
- Assertion pattern: `assert result.field == expected` (pytest) or `self.assertEqual(result, expected)` (unittest)

## Mocking

**Framework:** `unittest.mock` — `MagicMock`, `patch`

**Patterns:**
```python
# Context manager patch (most common)
with patch("requests.post") as mock_post:
    mock_post.return_value = mock_rpc_response("0x...")
    result = provider.get_resolution(...)

# side_effect for sequential responses
mock_post.side_effect = [
    mock_rpc_response(hex(1000000)),  # denominator
    mock_rpc_response(hex(1000000)),  # numerator[0]
    mock_rpc_response(hex(0)),        # numerator[1]
]

# MagicMock as spec-constrained test double
mock_ch = MagicMock(spec=ClickHouseResolutionProvider)
mock_ch.get_resolution.return_value = None

# Verify call assertions
mock_ch.get_resolution.assert_called_once()
mock_onchain.get_resolution.assert_not_called()
```

**Test doubles via `_event_source` hook:**
Many SimTrader components accept `_event_source: Iterable[dict]` to bypass real WS connections:
```python
runner = ShadowRunner(
    slug=SLUG,
    strategy=strategy,
    _event_source=_make_fake_events(),  # Offline event injection
)
runner.run()
```
This pattern appears in: `ShadowRunner`, `ActivenessProbe`, `TapeRecorder`.

**What to Mock:**
- Network calls (`requests.post`, `requests.get`, WebSocket connections)
- External API clients (`GammaClient`, `ClobClient`) replaced with `MagicMock()`
- File I/O when testing business logic in isolation
- `TapeRecorder` and `run_strategy` when testing CLI argument parsing

**What NOT to Mock:**
- `Decimal` arithmetic — always use real `Decimal` values in financial tests
- `L2Book`, `SimBroker`, `PortfolioLedger` — test these with real synthetic tape events
- File artifacts — write to `tmp_path` / `tempfile.TemporaryDirectory` and assert on actual file contents

## Fixtures and Factories

**Test Data — module-level helper functions (no pytest fixtures):**
```python
# Event factories — return minimal but valid event dicts
def _book_event(seq=0, ts=1000.0, asset_id="tok1", bids=None, asks=None) -> dict:
    return {
        "parser_version": PARSER_VERSION,
        "seq": seq,
        "ts_recv": ts,
        "event_type": "book",
        "asset_id": asset_id,
        "bids": bids if bids is not None else [{"price": "0.55", "size": "100"}],
        "asks": asks if asks is not None else [{"price": "0.57", "size": "200"}],
    }

def _price_change(seq, ts=1001.0, asset_id="tok1", changes=None) -> dict: ...

# Order event factories for portfolio tests
def _submitted(order_id, seq, side="BUY", asset_id="tok1", ...) -> dict: ...
def _fill(order_id, seq, fill_price, fill_size, remaining, ...) -> dict: ...

# Market mock factory
def _make_market(slug=SLUG, outcomes=None, clob_token_ids=None) -> MagicMock:
    m = MagicMock()
    m.market_slug = slug
    ...
    return m
```

**Constants at module top:**
```python
YES_ID = "yes-001"
NO_ID = "no-001"
YES_TOKEN = "aaa" * 20 + "1"
NO_TOKEN = "bbb" * 20 + "2"
SLUG = "will-it-rain-2026"
```

**Location:**
- All fixtures are module-local helper functions; no shared fixture files beyond `conftest.py`
- `conftest.py` handles only session-scoped environment isolation (not test data)

## Coverage

**Requirements:** No minimum enforced in CI (no `--cov-fail-under` in config)

**View Coverage:**
```bash
pytest --cov=packages --cov=tools --cov=polytool --cov-report=html
```

**Approximate count:** ~987 test functions across 56 test files (as of 2026-03-05)

## Test Types

**Unit Tests:**
- Scope: single class or function with all collaborators mocked
- All SimTrader unit tests are fully offline — stated explicitly in module docstrings: "All tests are fully offline — no network calls are made"
- Example: `tests/test_simtrader_broker.py` — tests `SimBroker` with synthetic tape; no WS calls

**Integration Tests:**
- Scope: multiple real collaborators (e.g., `StrategyRunner` + `SimBroker` + `L2Book` + `PortfolioLedger`)
- Use real synthetic tape data injected via `_event_source` or written to `tmp_path` as JSONL files
- Assert on artifact files (JSON, JSONL) written to a temp directory
- Example: `tests/test_simtrader_arb.py` — runs full `BinaryComplementArb` strategy through `StrategyRunner`

**E2E / CLI Tests:**
- Test CLI `main(argv)` entry points end-to-end by calling them directly
- Assert on process exit code and file artifacts written to `tmp_path`
- Example in `tests/test_simtrader_broker.py`: "CLI trade subcommand end-to-end artifact writing"

**Optional-dep Tests:**
- Tests requiring optional packages (RAG, ClickHouse) marked with `pytestmark = pytest.mark.optional_dep`
- Files: `tests/test_opportunities.py`, `tests/test_export_schema_guard.py`, `tests/test_snapshot_books_metadata_refresh.py`

## Common Patterns

**Determinism Testing:**
Tests frequently assert deterministic output for identical inputs — a dedicated invariant category in nearly every simtrader test module:
```python
def test_determinism(self, tmp_path):
    """Same tape + config -> byte-identical output files."""
    # Run once
    run_dir_a = tmp_path / "run_a"
    _run_strategy(events_path, run_dir_a, strategy_config)

    # Run again
    run_dir_b = tmp_path / "run_b"
    _run_strategy(events_path, run_dir_b, strategy_config)

    # Compare artifacts
    assert (run_dir_a / "fills.jsonl").read_text() == (run_dir_b / "fills.jsonl").read_text()
```

**Artifact assertion pattern:**
```python
manifest = json.loads((run_dir / "run_manifest.json").read_text())
assert manifest["strategy"] == "binary_complement_arb"
assert manifest["modeled_arb_summary"]["total_attempts"] >= 1
```

**Error testing:**
```python
with pytest.raises(ConfigLoadError, match="not found"):
    load_json_from_path("/nonexistent/path.json")

with pytest.raises(MarketPickerError, match="not binary"):
    picker.resolve_slug("some-slug")
```

**Async Testing:**
- Not applicable — codebase is synchronous Python; no async test patterns used

**Windows-safe temp cleanup:**
`conftest.py` overrides `tempfile.TemporaryDirectory` and pytest's tmpdir factory globally to handle Windows ACL restrictions. All temp paths are rooted under `.tmp/` in the project root. Tests should use `tmp_path` (pytest fixture) or `tempfile.TemporaryDirectory()` — both are safe under this override.

**`optional_dep` marker skip pattern:**
Tests for optional dependencies use `pytestmark` at module level. If the import fails, the test is expected to be skipped or xfailed:
```python
pytestmark = pytest.mark.optional_dep
```

---

*Testing analysis: 2026-03-05*
