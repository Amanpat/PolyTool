# Coding Conventions

**Analysis Date:** 2026-03-05

## Naming Patterns

**Files:**
- `snake_case.py` throughout — e.g., `config_loader.py`, `binary_complement_arb.py`, `market_picker.py`
- Test files prefix with `test_` — e.g., `test_simtrader_arb.py`, `test_resolution_providers.py`
- Private helpers prefix with `_` — e.g., `_safe_cleanup.py`, `_BROWSE_TYPE_DIRS`, `_YES_NAMES`

**Functions:**
- `snake_case` for all functions and methods
- Private/internal helpers prefix with `_` — e.g., `_record()`, `_quickrun()`, `_build_quick_sweep_config()`
- CLI handlers named `_<subcommand>(args)` — e.g., `_record(args)`, `_quickrun(args)`
- All tool CLI modules expose `main(argv: list[str]) -> int`

**Variables:**
- `snake_case` for all variables
- Constants use `UPPER_SNAKE_CASE` — e.g., `DEFAULT_FEE_RATE_BPS`, `PARSER_VERSION`, `DEFAULT_WS_URL`
- Module-level logger always: `logger = logging.getLogger(__name__)`
- Common shorthand: `_D = Decimal` in test/financial modules

**Types:**
- `PascalCase` for classes and dataclasses — e.g., `MarketPickerError`, `ResolvedMarket`, `OrderIntent`
- `PascalCase` for Protocols and Enums — e.g., `ResolutionProvider`, `ResolutionOutcome`
- String-constant class pattern used for enums without inheritance: `class OrderStatus` with `PENDING = "pending"`, `_TERMINAL = frozenset({...})`

## Code Style

**Formatting:**
- No formatter config detected (no `.prettierrc`, `.editorconfig`, `pyproject.toml[tool.black]`, or `.flake8`)
- 4-space indentation consistent throughout
- Line length: informal ~100 chars; docstrings wrap at ~80
- f-strings used for logging messages in `logger.warning(f"...")` — inconsistent with `%s` style used in `logger.warning("... %s", value)` in fee modules

**Linting:**
- No pylint/flake8/ruff config detected
- Type annotations used consistently in function signatures throughout `packages/`

## Import Organization

**Order:**
1. `from __future__ import annotations` — first line in nearly all `packages/` and `tests/` files
2. Standard library imports
3. Third-party imports (e.g., `requests`, `pytest`)
4. Internal package imports (relative or absolute from project root)

**Path Aliases:**
- No path aliases; project root is always on `sys.path`
- Some older test files manually: `sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))` — see `tests/test_resolution_providers.py`, `tests/test_rag.py`
- Newer tests import directly: `from packages.polymarket.simtrader... import ...`

**Relative vs absolute imports in packages:**
- Within `packages/polymarket/simtrader/` subpackages: relative imports used — e.g., `from ..tape.schema import EVENT_TYPE_BOOK`
- Cross-package: absolute from project root — e.g., `from packages.polymarket.simtrader.config_loader import ConfigLoadError`

## Error Handling

**Strategy:** Domain-specific exception subclasses raised; callers use `except DomainError`

**Patterns:**
- Custom exceptions subclass built-in types — e.g., `ConfigLoadError(ValueError)`, `MarketPickerError(ValueError)`, `L2BookError(Exception)`
- Chain exceptions with `raise NewError(...) from original_exc`
- Network/IO errors caught and logged, returning `None` rather than propagating — e.g., `OnChainCTFProvider.get_resolution()` returns `None` on `requests.exceptions.Timeout`
- CLI `main()` functions return int exit codes: `0` = success, `1` = failure; print errors to `sys.stderr`
- Optional-dependency `ImportError` caught at CLI dispatch time; user shown install hint

**Error messages:**
- Include enough context to diagnose — e.g., `ConfigLoadError(f"config file not found: {p}")`
- `match=` patterns used in `pytest.raises()` for error message assertions

## Logging

**Framework:** `logging` stdlib; `logger = logging.getLogger(__name__)` in every module that logs

**Patterns:**
- `logger.warning(...)` for recoverable issues (rate limits, missing data, conservative defaults applied)
- `logger.warning("message %s", value)` in performance-sensitive paths (lazy formatting)
- `logger.warning(f"message {value}")` in less frequent paths (f-string)
- No `print()` in library code; `print()` reserved for CLI user-facing output
- CLI modules use `print(..., file=sys.stderr)` for errors

## Comments

**When to Comment:**
- Module-level docstrings: always present; describe purpose, key terminology, lifecycle, usage example
- Class docstrings: always present; describe invariants and usage
- Function/method docstrings: always present in public APIs; Args/Returns/Raises sections used for non-trivial functions
- Inline section separators: `# ---------------------------------------------------------------------------` delimiter pattern used extensively in both source and test files to visually group logical sections
- Assumption disclaimers: `# ASSUMPTION` prefix in `binary_complement_arb.py` for modeled values

**Docstring style:**
- Google-style Args/Returns/Raises with indented descriptions — e.g., `packages/polymarket/simtrader/config_loader.py`
- Module-level docstrings include "Theory of operation", "Lifecycle", or numbered steps for complex modules

## Function Design

**Size:** CLI handlers (`_record`, `_quickrun`, etc.) can be large (50-200 lines). Library functions are typically 10-40 lines.

**Parameters:**
- Keyword-only parameters enforced with `*` for multi-arg factory functions — e.g., `load_strategy_config(*, config_path=None, config_json=None)`
- `Optional[X]` used for nullable params; default `None` when not required
- Dataclasses used for rich parameter objects instead of long argument lists

**Return Values:**
- Library functions return domain objects (`Resolution`, `ResolvedMarket`) or `None` for "not found"
- CLI `main()` always returns `int`
- Predicate helpers return `bool`

## Module Design

**Exports:**
- No barrel `__init__.py` files with explicit `__all__`; `__init__.py` files are empty or minimal
- Consumers import directly from the implementing module path

**Constants module pattern:**
- Schema constants isolated in `tape/schema.py`: `PARSER_VERSION`, `EVENT_TYPE_*`, `KNOWN_EVENT_TYPES`
- Fee constants in `portfolio/fees.py`: `DEFAULT_FEE_RATE_BPS`, private `_ZERO`, `_ONE`, `_TEN_THOUSAND`

**Decimal arithmetic:**
- All monetary values use `Decimal` (never `float`) in broker, portfolio, and strategy code
- Private `_ZERO = Decimal("0")`, `_ONE = Decimal("1")` module-level constants for Decimal comparisons
- Common shorthand `_D = Decimal` in test files for compact test fixtures

---

*Convention analysis: 2026-03-05*
