# SPEC: Phase 1B — Gate 2 Benchmark Sweep and Gate 3 Shadow Packet

**Status:** Active
**Phase:** 1B
**Date:** 2026-03-26
**Owner:** Operator

---

## 1. Purpose

Phase 1B closes the two remaining validation gates that must pass before
Track A (MarketMakerV1) can proceed to Stage 0 paper-live deployment:

- **Gate 2** — benchmark sweep: `market_maker_v1` must show positive net PnL on
  at least 70% of the benchmark_v1 tape set (50 tapes across 5 buckets).
- **Gate 3** — shadow run: the strategy must successfully consume a live
  WebSocket session with no structural errors, no real orders submitted, and
  operator sign-off.

Gate 4 (dry-run live) is already closed. The promotion path after Phase 1B
completes is: Gate 2 PASS → Gate 3 sign-off → Stage 0 → Stage 1.

---

## 2. Gate 2 — Benchmark Sweep

### 2.1 Input

- `config/benchmark_v1.tape_manifest` — closed 2026-03-21, 50 tapes:
  - `politics` = 10 tapes (Silver, reconstructed)
  - `sports` = 15 tapes (Gold, live-recorded)
  - `crypto` = 10 tapes (Silver, reconstructed)
  - `near_resolution` = 10 tapes (Silver, reconstructed)
  - `new_market` = 5 tapes (Gold, live-captured)
- Strategy: `market_maker_v1` (Logit Avellaneda-Stoikov)
- Sweep: 5 spread multipliers: 0.50x, 1.00x, 1.50x, 2.00x, 3.00x
- Fee model: 200 bps (default), mark method: `bid` (conservative)
- Min events per tape: 50 effective events

### 2.2 Acceptance Criteria

Gate 2 PASSES when:

```
tapes_positive / tapes_total >= 0.70
```

where:
- `tapes_positive` = number of tapes where at least one spread-multiplier
  scenario yields `net_profit > 0` after fees (best-of-5 per tape)
- `tapes_total` = number of tapes with `effective_events >= 50`
- Threshold is `>= 0.70` (not `> 0.70`). Never weaken this.

Tapes with `effective_events < 50` are counted as SKIPPED, not failed.
If fewer than 50 tapes meet the event threshold, Gate 2 is NOT_RUN (not
auto-failed).

### 2.3 Artifact Contract

On Gate 2 completion, these files are written to `artifacts/gates/mm_sweep_gate/`:

| File | Content |
|------|---------|
| `gate_passed.json` | Full JSON payload (present on PASS, absent on FAIL) |
| `gate_failed.json` | Full JSON payload (present on FAIL, absent on PASS) |
| `gate_summary.md` | Human-readable Markdown summary with per-bucket breakdown |

The JSON payload schema:

```json
{
  "gate": "mm_sweep",
  "passed": true,
  "tapes_total": 50,
  "tapes_positive": 37,
  "pass_rate": 0.74,
  "bucket_breakdown": {
    "politics": {"total": 10, "positive": 7, "pass_rate": 0.7},
    "sports": {"total": 15, "positive": 12, "pass_rate": 0.8},
    "crypto": {"total": 10, "positive": 8, "pass_rate": 0.8},
    "near_resolution": {"total": 10, "positive": 6, "pass_rate": 0.6},
    "new_market": {"total": 5, "positive": 4, "pass_rate": 0.8}
  },
  "best_scenarios": [...],
  "generated_at": "2026-03-26T00:00:00Z"
}
```

The `bucket_breakdown` field is present when tape metadata includes bucket
labels (all benchmark_v1 tapes carry this via `watch_meta.json` or
`market_meta.json`).

### 2.4 Run Command

```bash
# Primary path: via close_mm_sweep_gate.py
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate

# Alternative: via simtrader CLI
python -m polytool simtrader sweep-mm \
    --benchmark-manifest config/benchmark_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```

### 2.5 Verify Gate Status

```bash
python tools/gates/gate_status.py
```

Gate 2 in the status reporter is labeled `mm_sweep_gate (Gate 2b optional)`.
It reads from `artifacts/gates/mm_sweep_gate/gate_passed.json` or
`gate_failed.json`.

### 2.6 Tape Metadata Fallback Chain

`_build_tape_candidate` reads YES token ID from these sources in priority order:

1. `prep_meta.json` → `yes_asset_id` or `yes_token_id`
2. `meta.json` → extracted from context dicts (`quickrun_context`, `shadow_context`)
3. `watch_meta.json` → `yes_asset_id` (Gold new_market tapes from `capture_new_market_tapes.py`)
4. `market_meta.json` → `token_id` (Silver tapes from `batch_reconstruct_silver.py`)
5. `silver_meta.json` → `token_id` (Silver tape metadata)

If no YES token is found and the tape is from a benchmark manifest,
`ValueError` is raised (not silently skipped).

---

## 3. Gate 3 — Shadow Run

### 3.1 Purpose

Gate 3 verifies that `market_maker_v1` can operate against a live Polymarket
WebSocket feed for a sustained session without errors, and that no real orders
are submitted. This is the final pre-Stage 0 gate.

### 3.2 Prerequisites

- Gate 2 benchmark sweep MUST be PASSED before Gate 3 sign-off.
- `python tools/gates/gate_status.py` must show PASSED for `mm_sweep_gate`.
- No open positions from a prior run.
- Kill-switch file must be absent or falsy.

### 3.3 Acceptance Criteria

Gate 3 PASSES when all of the following hold:

1. Shadow run completes without `RuntimeError` or import errors.
2. `run_manifest["run_metrics"]["events_received"] > 0` (market was live).
3. `run_manifest["fills_count"] == 0` (shadow mode never submits real orders).
4. `run_manifest["exit_reason"]` is `null` or `"stall"` (not an error).
5. Strategy log shows `WOULD PLACE` lines, or market was quiet (no log is acceptable).
6. Operator manual sign-off with `gate_passed.json` written to `artifacts/gates/shadow_gate/`.

### 3.4 Artifact Contract

The gate artifact is written manually by the operator:

```json
{
  "gate": "shadow",
  "passed": true,
  "commit": "<git rev-parse --short HEAD>",
  "timestamp": "<ISO 8601 UTC>",
  "shadow_run_dir": "artifacts/simtrader/shadow_runs/<id>",
  "market_slug": "<SLUG>",
  "events_received": 142,
  "duration_seconds": 300,
  "notes": "Manual sign-off by operator <name> on <date>"
}
```

### 3.5 Run Command

```bash
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 300
```

See `docs/runbooks/GATE3_SHADOW_RUNBOOK.md` for the full operator procedure.

---

## 4. Promotion Path

```
Gate 1 (replay)  PASSED [done]
Gate 2 (mm_sweep benchmark) -> PASS required
Gate 3 (shadow, manual sign-off) -> PASS required
Gate 4 (dry-run live) PASSED [done]
     |
     v
Stage 0: Paper live dry-run
     |
     v
Stage 1: Live capital (operator decision)
```

Gate 2 and Gate 3 can be run in either order, but Gate 3 sign-off requires
Gate 2 to have PASSED first. Stage 0 requires all four gates.

---

## 5. Blockers

| Blocker | Status | Notes |
|---------|--------|-------|
| Gate 2 verdict | NOT YET RUN | Run `close_mm_sweep_gate.py --benchmark-manifest config/benchmark_v1.tape_manifest` |
| Gate 3 shadow run | NOT YET RUN | Requires live WS connection; run after Gate 2 passes |
| Track 2 (crypto pair) market availability | BLOCKED | No active BTC/ETH/SOL 5m/15m markets as of 2026-03-25 |

---

## 6. Security and Risk Constraints

- Gate threshold `>= 0.70` must never be weakened.
- Shadow mode structurally cannot submit real orders (no `--live` flag exists).
- Kill-switch behavior is preserved through `LiveRunner` in shadow mode.
- `cancel_all_immediate()` fires on WS disconnect in shadow mode (verified by
  `TestCancelAllOnDisconnect` in `tests/test_simtrader_shadow.py`).
- ClickHouse is not accessed during Gate 2 sweep (pure offline replay).
