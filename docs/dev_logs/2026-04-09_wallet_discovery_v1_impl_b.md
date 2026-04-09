# 2026-04-09 Wallet Discovery v1 — Scan-Side Implementation (Plan B)

## Objective

Implement the scan-side changes for Wallet Discovery v1 (quick task `260409-qez`):

1. Create the MVF (Multi-Variate Fingerprint) computation module.
2. Add a `--quick` flag to the `scan` CLI command with a hard no-LLM guarantee.
3. Wire MVF output into the dossier artifact when `--quick` is used.
4. Prove correctness with deterministic tests (AT-06, AT-07).

## What Was Built

### Task 1: MVF Computation Module

**File:** `packages/polymarket/discovery/mvf.py`

Implements `compute_mvf(positions, wallet_address) -> MvfResult` producing an 11-dimensional fingerprint:

| # | Dimension | Formula |
|---|-----------|---------|
| 1 | `win_rate` | (WIN+PROFIT_EXIT) / (WIN+PROFIT_EXIT+LOSS+LOSS_EXIT) — PENDING excluded |
| 2 | `avg_hold_duration_hours` | Mean of (last_ts - first_ts) / 3600 per position |
| 3 | `median_entry_price` | `statistics.median(entry_price)` for valid [0,1] prices |
| 4 | `market_concentration` | Herfindahl index: sum((slug_count/total)^2) over market_slugs |
| 5 | `category_entropy` | Shannon entropy (nats): -sum(p * math.log(p)) over categories |
| 6 | `avg_position_size_usdc` | Mean of position_notional_usd / total_cost / size*entry_price |
| 7 | `trade_frequency_per_day` | len(positions) / max(window_days, 1.0) |
| 8 | `late_entry_rate` | Fraction of positions entered in final 20% of market life (null if market timing absent — Gap E) |
| 9 | `dca_score` | Fraction of market_slugs with >1 position |
| 10 | `resolution_coverage_rate` | Fraction of positions with resolved outcome |
| 11 | `maker_taker_ratio` | Fraction of maker-side trades (null when field absent — never fabricated) |

Key design constraints honored:
- Pure Python stdlib only (`math`, `statistics`). No numpy, pandas, requests.
- All division operations guard against ZeroDivisionError.
- Deterministic: sorted iteration over dicts/sets where order matters.
- `maker_taker_ratio` is explicitly null (not fabricated) when no maker/taker field is present.

**File:** `packages/polymarket/discovery/__init__.py`

Updated with a `try/except ImportError` guard so the package loads cleanly before `models.py` (Loop A task) is implemented. This prevents import errors when only the MVF scan-side module is needed.

**Test file:** `tests/test_mvf.py` (37 tests, AT-07)

Coverage: output shape, determinism, win-rate correctness (25 WIN + 5 PROFIT_EXIT + 10 LOSS + 5 LOSS_EXIT + 5 PENDING = 30/45), empty input, metadata block, maker/taker explicit null, range validation.

### Task 2: --quick Flag on scan CLI

**File:** `tools/cli/scan.py`

Three changes:

1. `build_parser()` — added `--quick` argument with hard no-LLM guarantee docs.
2. `apply_scan_defaults()` — handles `--quick` BEFORE `--full` and `--lite` (takes precedence). Sets `LITE_PIPELINE_STAGE_SET` and disables non-lite stages.
3. `build_config()` — propagates `config["quick"]` from args.
4. `_emit_trust_artifacts()` — lazy-imports `compute_mvf` and appends MVF block to `dossier.json` when `quick=True`. Non-quick path is unaffected.

**Test file:** `tests/test_scan_quick_mode.py` (15 tests, AT-06)

Coverage:
- No-LLM guarantee: intercepts all `post_json` calls, asserts no LLM domains touched.
- MVF in dossier.json output with correct structure and trade count.
- `--quick` implies only lite stages (LITE_PIPELINE_STAGE_SET).
- `--quick` takes precedence over `--full` when both specified.
- Existing scan path unaffected (no MVF block without `--quick`).
- `build_config()` wires the flag correctly.

## Test Results

```
tests/test_mvf.py            37 passed
tests/test_scan_quick_mode.py 15 passed
tests/test_scan_trust_artifacts.py 26 passed (no regressions)
Full suite: 3896 passed, 0 new failures
```

Pre-existing failure: `test_ris_phase2_cloud_provider_routing.py` (8 tests) — `AttributeError: module has no attribute '_post_json'`. Confirmed pre-existing before this packet's changes.

## Commits

- `e2d0ac7` — `feat(quick-260409-qez-01): implement MVF computation module with AT-07 tests`
- `4282efc` — `feat(quick-260409-qez-02): add --quick flag to scan CLI with MVF output and AT-06 tests`

## Deviations

**Auto-fix [Rule 1]: `__init__.py` ImportError guard**

The discovery `__init__.py` had been modified by a parallel agent (quick-260409-qeu Loop A task) to import from `models.py`, which does not yet exist. This caused `ModuleNotFoundError` when loading `mvf.py`. Fixed by wrapping the models import in `try/except ImportError` so the package loads cleanly in either order. This is not a behavior change — the models imports work correctly once `models.py` is present.

## Open Items

- `late_entry_rate` requires `market_open_ts` and `close_timestamp` fields on positions (Gap E per spec). These fields are not present in the current dossier export schema. The dimension returns null with a data note. This is expected behavior per the spec.
- `test_ris_phase2_cloud_provider_routing.py` pre-existing failures should be investigated by whoever owns the RIS Phase 2 cloud provider routing feature.

## Codex Review

Scope: `tools/cli/scan.py`, `packages/polymarket/discovery/mvf.py` (no execution layer, no live-capital paths). Codex adversarial review not required (no files in mandatory tier). Recommended tier — skipped for offline pure-math module with no network access.
