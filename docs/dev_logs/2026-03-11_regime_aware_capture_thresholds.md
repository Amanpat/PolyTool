# Dev Log: Regime-Aware Capture Thresholds + Observational Evidence Label

**Date:** 2026-03-11
**Branch:** codex/tracka-adverse-selection-default-wiring
**Track:** Track A — Phase 1

---

## Summary

Three scoped fixes to make capture smarter by regime, while Gate 2 eligibility
and pass criteria remain strictly unchanged.

**PART A** — Per-regime near-edge capture thresholds (new)
**PART B** — Dedicated new-market discovery (was already done, see 2026-03-10 log)
**PART C** — Additive politics inventory augmentation (was already done, see 2026-03-10 log)
**Optional** — Observational/non-eligible label for runs with decisions but no fills

---

## What Changed

### 1. `packages/polymarket/market_selection/regime_policy.py`

**Fixed inversion bug** and switched to explicit threshold semantics:

**`REGIME_CAPTURE_NEAR_EDGE_DEFAULTS`** — dict mapping each required regime to its
near-edge capture *threshold* (not buffer).  Capture is eligible when
`yes_ask + no_ask < threshold`:
- `sports: 0.99` — current default, unchanged (consistent with Gate 2 entry level)
- `politics: 1.03` — looser; politics edges appear and vanish quickly; fires before arb exists
- `new_market: 1.015` — slightly looser; wider net for shallow-book new markets

Thresholds > 1.0 enable near-miss detection: capture fires before the arb is
fully profitable.  The previous buffer values (0.01 / 0.03 / 0.02) used the
formula `threshold = 1.0 - buffer`, which produced **tighter** thresholds for
politics (0.97) and new_market (0.98) than sports (0.99) — the opposite of
intent.  That inversion is now fixed.

**`_DEFAULT_CAPTURE_THRESHOLD = 0.99`** — renamed from `_DEFAULT_CAPTURE_BUFFER`
(value equivalent for sports; semantics clarified as threshold, not buffer).

**`get_regime_capture_threshold(regime)`** — renamed from `get_regime_capture_buffer`.
Returns the threshold directly; no caller needs to subtract from 1.0.
Falls back to `_DEFAULT_CAPTURE_THRESHOLD` for unrecognised values.

These affect **capture/session planning behavior only**.
Gate 2 eligibility and pass criteria are NOT altered.

### 2. `tools/cli/scan_gate2_candidates.py`

**`resolve_effective_buffer` renamed → `resolve_effective_threshold`** — now
returns `(threshold, source)` where threshold is the direct near-edge value:
- `"user-set"`: `--buffer` was explicitly provided; threshold = `1.0 - buffer`
- `"regime-default"`: `--regime` set, no explicit `--buffer`; threshold from
  `get_regime_capture_threshold`
- `"global-default"`: neither set; threshold = `_DEFAULT_CAPTURE_THRESHOLD`

**`main()` now separates Gate 2 scoring buffer from capture threshold:**
- `gate2_buffer`: always uses `args.buffer` (default 0.01) — Gate 2 scoring
  is never modified by `--regime`.  This was the key correctness fix: the
  previous code incorrectly passed the regime buffer to `scan_tapes` /
  `scan_live_markets`, making `--regime politics` silently use a tighter
  Gate 2 threshold (0.97) than the standard (0.99).
- `capture_threshold`: from `resolve_effective_threshold`; used for provenance
  printing only.

Provenance line format updated:
`regime_used=politics  near_edge_threshold_used=1.0300  gate2_buffer_used=0.0100  threshold_source=regime-default`

Scan header updated to show both values unambiguously.

### 3. `packages/polymarket/simtrader/strategy/runner.py` (optional)

Added observational evidence label: when a run has decisions (strategy submitted
orders) but zero fills, `"observational_evidence": true` is written to both
`summary.json` and `run_manifest.json`.  This is **informational only** — it does
not change any gate eligibility check or sweep pass behavior.

### 4. `packages/polymarket/simtrader/shadow/runner.py` (optional)

Same observational label added to shadow run artifacts (`summary.json` and
`run_manifest.json`).

---

## Gate 2 Eligibility — Explicit Statement

**Gate 2 eligibility was NOT changed.**

- `close_sweep_gate.py` was not touched.
- `close_replay_gate.py` was not touched.
- Tape-manifest executable eligibility logic was not touched.
- `observational_evidence` is a read-only informational field; no gate logic
  reads it, and it does not grant or revoke eligibility.
- Regime-aware buffers apply only to scan/capture behavior; they have no effect
  on what counts as an executable tick in a tape manifest.

---

## Tests Added

### `tests/test_regime_inventory_discovery.py` — 16 tests (`TestRegimeCaptureThresholds`)

| Test | What it proves |
|------|----------------|
| `test_sports_threshold_unchanged` | Sports threshold == 0.99 (unchanged) |
| `test_politics_threshold_looser_than_sports` | Politics threshold > sports threshold |
| `test_new_market_threshold_looser_than_sports` | new_market threshold > sports threshold |
| `test_new_market_threshold_does_not_exceed_politics` | new_market ≤ politics |
| `test_unknown_regime_returns_default` | "unknown"/"other" → 0.99 fallback |
| `test_all_required_regimes_have_entries` | All REQUIRED_REGIMES in defaults dict |
| `test_all_thresholds_in_valid_range` | All thresholds in (0, 2) |
| `test_politics_threshold_above_one` | Politics > 1.0 (near-miss detection) |
| `test_new_market_threshold_above_sports` | new_market threshold > sports threshold |
| `test_resolve_no_args_uses_global_default` | No regime, no explicit → global-default (0.99) |
| `test_resolve_regime_sports_uses_regime_default` | Sports → regime-default (0.99) |
| `test_resolve_regime_politics_uses_politics_threshold` | Politics → 1.03, looser than default |
| `test_resolve_regime_new_market_uses_new_market_threshold` | new_market → 1.015 |
| `test_resolve_explicit_buffer_overrides_regime` | `--buffer 0.05 --regime politics` → threshold=0.95 |
| `test_resolve_explicit_buffer_overrides_global` | `--buffer 0.02` (no regime) → threshold=0.98 |
| `test_unknown_off_target_never_promoted` | Bad regimes → default threshold, not widened |

### `tests/test_simtrader_strategy.py` — 3 new observational tests

| Test | What it proves |
|------|----------------|
| `test_observational_evidence_absent_when_no_decisions` | No key when no decisions |
| `test_observational_evidence_present_when_decisions_but_no_fills` | Key present; no gate fields added |
| `test_observational_evidence_informational_only` | Run with fills → key absent |

---

## Tests Run

```bash
pytest -q tests/test_regime_inventory_discovery.py tests/test_simtrader_strategy.py \
  tests/test_adverse_selection.py tests/test_simtrader_quickrun.py \
  tests/test_simtrader_shadow.py tests/test_market_maker_v1.py \
  tests/test_polytool_main_module_smoke.py
# 305 passed
```

---

## Manual Verification Commands

```bash
# Politics scan — capture_threshold=1.0300, Gate 2 buffer=0.01 (unchanged)
python -m polytool scan-gate2-candidates --regime politics --top 20

# new_market scan — capture_threshold=1.0150, Gate 2 buffer=0.01 (unchanged)
python -m polytool scan-gate2-candidates --regime new_market --top 20

# Sports scan — capture_threshold=0.9900, Gate 2 buffer=0.01 (unchanged)
python -m polytool scan-gate2-candidates --regime sports --top 20

# Explicit override — user-set buffer=0.05 → threshold=0.95, Gate 2 also uses 0.05
python -m polytool scan-gate2-candidates --regime politics --buffer 0.05 --top 10

# Unit tests only
python -m pytest tests/test_regime_inventory_discovery.py::TestRegimeCaptureThresholds -v

# Sanity check thresholds directly
python -c "
from packages.polymarket.market_selection.regime_policy import get_regime_capture_threshold
for r in ('sports', 'politics', 'new_market', 'other', 'unknown'):
    print(f'{r:12s}: {get_regime_capture_threshold(r)}')
"
```

---

## Scope Constraints

Touched:
- `packages/polymarket/market_selection/regime_policy.py` — capture threshold defaults
- `tools/cli/scan_gate2_candidates.py` — buffer resolution + provenance output
- `packages/polymarket/simtrader/strategy/runner.py` — optional observational label
- `packages/polymarket/simtrader/shadow/runner.py` — optional observational label
- `tests/test_regime_inventory_discovery.py` — PART A tests
- `tests/test_simtrader_strategy.py` — observational label tests

Did NOT touch:
- Gate 2 pass criteria
- `close_sweep_gate.py` / `close_replay_gate.py`
- Tape-manifest executable eligibility definition
- MarketMakerV1 quote math
- Adverse-selection math
- Any API, UI, or unrelated scanner work

---

## PART D — Session Pack + Watcher Capture Wiring (2026-03-11, follow-up)

The thresholds were correct in provenance output but **not yet wired** into real
capture behavior.  This section records the wiring work.

### Problem

`scan-gate2-candidates` printed the regime-aware capture threshold in its provenance
line but `watch-arb-candidates` still used the hardcoded `1.00` default unconditionally.
`make-session-pack` did not exist.  The threshold was provenance-only; actual capture
behavior was unchanged for politics / new_market.

### New file: `tools/cli/make_session_pack.py`

Generates a session pack JSON that a watcher session can be seeded from:
- `watch_config.near_edge_threshold` — from `get_regime_capture_threshold(regime)` unless
  `--near-edge` override is supplied.
- `watch_config.threshold_source` — `"regime-default"` | `"operator-override"` | `"global-default"`.
- `session.{regime, near_edge_threshold_used, threshold_source}` — artifact provenance block.
- `watchlist` — merged from `--markets` and/or `--watchlist-file`.

Threshold priority: `--near-edge` (operator override) > `--regime` default > global default.

### Updated: `tools/cli/watch_arb_candidates.py`

- `--session-plan PATH`: loads a session pack; extracts `watch_config.near_edge_threshold`,
  `threshold_source`, and session `regime`.  Watchlist entries from the plan are merged.
- `--near-edge` now defaults to `None`; if absent + session plan present → threshold from plan.
  If both absent → falls back to `1.00` (cli-default).
- `ArbWatcher` gains `threshold_source` and `regime` fields.
- `_record_tape_for_market` writes `near_edge_threshold_used`, `threshold_source`, and
  optionally `regime` to `watch_meta.json`.

### New tests: `tests/test_gate2_session_pack.py` — 26 tests

All 6 required behaviors verified (see test file for full coverage).
Existing `tests/test_watch_arb_candidates.py`: one `fake_record` signature updated to
accept new kwargs; all 25 pre-existing tests still pass.
