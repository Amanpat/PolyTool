# Dev Log — 2026-04-15 — Track 2 Execution Lane A: --dry-run preflight mode

**Quick task:** 260415-pq9  
**Area:** `tools/cli/crypto_pair_run.py`  
**Status:** Complete

---

## Objective

Add a `--dry-run` preflight mode to the `crypto-pair-run` CLI so operators can
validate their config, discover eligible BTC/ETH/SOL markets, and preview a
targeting summary — without starting any run cycles, connecting reference feeds,
writing artifacts, or requiring a ClickHouse password.

This addresses the operator workflow gap identified in the approved Track 2
execution plan: there was no safe "preview before committing" path.

---

## Changes Made

### `tools/cli/crypto_pair_run.py`

1. **Parser** — added `--dry-run` flag (boolean, default `False`) with a help
   string explaining exactly what it does and does not do.

2. **`format_preflight_summary(preflight: dict)`** — new public function that
   renders an operator-readable targeting summary showing:
   - Mode (always `paper` in preflight)
   - Symbol and duration filters active
   - Reference feed provider
   - Run duration and cycle interval
   - Operator safety caps (sourced from `paper_runner` module-level constants)
   - Each eligible market (slug, symbol, duration, active status, order status)
   - A `WARNING: no eligible markets found` line when the list is empty

3. **`run_crypto_pair_runner(dry_run=False, ...)`** — added `dry_run` parameter.
   When `True`, the function:
   - Still calls `build_runner_settings()` so invalid config raises `ValueError`
     before discovery (config validation is not skipped)
   - Calls `discover_crypto_pair_markets()` with the caller-supplied
     `gamma_client` (or default if None)
   - Applies symbol and duration filters (same logic as the paper runner)
   - Returns `{"dry_run": True, "preflight": {...}}` immediately — no sinks,
     no feeds, no loops, no artifacts

4. **`main()`** — added a dry-run branch that fires before the ClickHouse
   password check and the sink construction. On `--dry-run`:
   - Calls `run_crypto_pair_runner(dry_run=True, live=False, ...)`
   - Catches `ConfigLoadError` / `ValueError` and exits 1 with a readable error
   - Prints the formatted preflight summary to stdout
   - Returns 0

The dry-run path is entirely contained in the CLI layer — no changes to
`paper_runner.py`, `market_discovery.py`, or any other package module.

---

## Tests Added

**File:** `tests/test_crypto_pair_run.py`  
**New tests:** 6 (total in file: 23, all passing)

| Test | What it covers |
|---|---|
| `test_dry_run_flag_parsed` | Parser wires `--dry-run` → `args.dry_run=True`; default is `False` |
| `test_dry_run_returns_preflight_without_running_cycles` | Returns `{"dry_run": True, "preflight": {...}}`; `clob.get_best_bid_ask` call count is 0 |
| `test_dry_run_applies_symbol_filter` | BTC symbol filter causes ETH markets to be excluded from preflight |
| `test_dry_run_shows_zero_markets_warning` | Empty gamma response → `format_preflight_summary` output contains "no eligible markets found" |
| `test_dry_run_does_not_create_artifacts` | `output_base` dir remains empty after dry-run call |
| `test_dry_run_validates_config_errors` | `duration_seconds=-1` raises `ValueError` before discovery runs |

A `_make_gamma_client_with_targeted()` helper was added because
`discover_crypto_pair_markets()` calls both `gamma_client.fetch_all_markets()`
(returns a result object with `.markets`) and `gamma_client.fetch_markets_filtered()`
(returns a list directly for the targeted 5m slug lookup). The existing
`_make_gamma_client()` helper only covered the first path.

---

## Test Results

```
tests/test_crypto_pair_run.py: 23 passed in 1.57s
```

No regressions in any existing test.

---

## Commits

- `50abcb1` — `feat(quick-260415-pq9): add --dry-run preflight mode to crypto-pair-run CLI`
- `e899171` — `test(quick-260415-pq9): add 6 dry-run preflight tests`

---

## Operator Usage

```bash
# Preview what markets are available without starting anything
python -m polytool crypto-pair-run --dry-run

# Filter to BTC 5m only
python -m polytool crypto-pair-run --dry-run --symbol BTC --duration 5

# Test a custom config file without committing
python -m polytool crypto-pair-run --dry-run --strategy-config-path config/my_settings.json
```

The command requires no ClickHouse password and writes nothing to disk.
Exit code 0 = config valid and discovery succeeded. Exit code 1 = bad config.

---

## Codex Review Note

Not required per CLAUDE.md Codex policy: this is a CLI formatting function
and test additions. No execution-layer, risk-manager, or order-placement code
was modified.

---

## Open Questions / Next Steps

- Active BTC/ETH/SOL 5m markets returned 2026-04-14. Operators can now use
  `--dry-run` to confirm live market availability before starting a paper soak.
- Full paper soak (oracle mismatch concern, EU VPS latency) remains a separate
  gate before live capital deployment.
