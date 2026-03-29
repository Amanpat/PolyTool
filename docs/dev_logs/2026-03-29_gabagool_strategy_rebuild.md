# Dev Log: 2026-03-29 — Gabagool22 Strategy Rebuild (Quick Task 49)

**Objective:** Replace the old snapshot pair-cost checker in the crypto pair bot with a
directional momentum strategy modeled on gabagool22's observed trading pattern
(fast scalps, momentum-triggered entries, asymmetric leg sizing).

---

## Summary

Three sub-tasks completed:

1. **TDD momentum engine** (prior session, commit `9289b15`)
2. **Wire directional engine into paper runner + extend observation logging** (this session)
3. **10-minute paper soak + test fixes** (this session)

All 34 crypto pair tests pass. Full regression suite: **2767 passed, 0 failed**.

---

## Task 1: TDD Momentum Engine (prior session)

### Files added / modified
- `packages/polymarket/crypto_pairs/config_models.py` — added `MomentumConfig` frozen
  dataclass and `momentum` field on `CryptoPairPaperModeConfig`
- `packages/polymarket/crypto_pairs/accumulation_engine.py` — added `MomentumSignal`,
  `compute_momentum_signal()`, `evaluate_directional_entry()`, and extended `PairMarketState`
  with `price_history` and `cooldown_brackets`
- `packages/polymarket/crypto_pairs/paper_ledger.py` — added 6 new optional fields to
  `PaperOpportunityObservation`: `reference_price`, `price_change_pct`, `signal_direction`,
  `favorite_side`, `hedge_side`, `entry_timing_seconds`
- `tests/test_crypto_pair_momentum.py` (new) — 12 offline TDD tests covering config defaults,
  backward compat, signal computation, and all 6 gate paths in `evaluate_directional_entry()`

### Strategy logic

`evaluate_directional_entry()` runs 6 gates in order:

1. **Feed gate**: if snapshot is not connected+fresh → FREEZE (propagate to all open logic)
2. **Quote gate**: if both YES and NO asks are missing → SKIP
3. **Momentum gate**: compute signal from price history deque; if NONE → SKIP
4. **Cooldown gate**: if market_id is in `_entered_brackets` → SKIP
5. **Favorite price gate**: if favorite ask > `max_favorite_entry` → SKIP
6. **Entry gate**: ACCUMULATE with favorite + hedge leg

Signal direction:
- UP → favorite=YES, hedge=NO
- DOWN → favorite=NO, hedge=YES

`compute_momentum_signal()` uses first element as baseline, last as current:
- `price_change_pct = (current - baseline) / baseline`
- `>= threshold` → UP, `<= -threshold` → DOWN, otherwise NONE

### MomentumConfig defaults

| Field | Value |
|-------|-------|
| `momentum_window_seconds` | 30 |
| `momentum_threshold` | 0.003 (0.3%) |
| `max_favorite_entry` | 0.75 |
| `max_hedge_price` | 0.20 |
| `favorite_leg_size_usdc` | 8.0 |
| `hedge_leg_size_usdc` | 2.0 |

---

## Task 2: Wire Directional Engine into Paper Runner

### Files modified
- `packages/polymarket/crypto_pairs/paper_runner.py`
  - Added `DirectionalPaperExecutionAdapter` class: favorite fills at ask, hedge fills ONLY
    if ask <= `max_hedge_price`
  - Added `_price_history: dict[str, deque[float]]` (per-symbol, maxlen=momentum_window_s)
  - Added `_entered_brackets: set[str]` for one-entry-per-bracket cooldown
  - Replaced `evaluate_accumulation()` with `evaluate_directional_entry()` in the main loop
  - Enriches frozen observation via `dataclasses.replace()` after accumulation result known
- `tests/test_crypto_pair_run.py`
  - Added `MomentumFeed` test helper
  - Updated `test_paper_default_path_creates_jsonl_bundle`: `cycle_limit=3`, `MomentumFeed`,
    `yes_ask=0.72`, `no_ask=0.18`
  - Updated `test_runner_emits_heartbeat_event_and_callback`: `cycle_limit=3`, `MomentumFeed`;
    fixed heartbeat assertions (heartbeat fires after cycle 1 with frozen clock — before
    momentum signal fires on cycle 3, so `intents_generated=0`)

### Key design decisions

**Why 3 cycles are needed for the momentum signal to fire:**

- Cycle 1: price_history=[60000] → 1 point, pct=N/A → NONE
- Cycle 2: price_history=[60000, 60000] → pct=0.0% < 0.3% → NONE
- Cycle 3: price_history=[60000, 60000, 60600] → pct=1.0% > 0.3% → UP

**Why yes_ask=0.72, no_ask=0.18:**

- Signal=UP → favorite=YES, hedge=NO
- Gate 5: YES ask 0.72 < max_favorite_entry 0.75 → passes
- Adapter: fills YES at 0.72; checks NO: 0.18 <= max_hedge_price 0.20 → fills both
- Result: `exposure_status="paired"`, 2 fills, 1 exposure

**Heartbeat timing with frozen clock:**

- `now_fn=lambda: started_at + 2min` means elapsed is always 120s
- First heartbeat check after cycle 1: 120 >= 60 → fires
- Next threshold: 180. Elapsed stays 120 < 180, no more heartbeats
- Heartbeat fires with cycle 1 data only (1 obs, 0 intents, 0 pairs)

---

## Task 3: Paper Soak + Test Fixes

### Test fixes

`test_streaming_mode_emits_incrementally` in `test_crypto_pair_runner_events.py` was using
`StaticFeed` + `cycle_limit=1`. With the directional strategy, a single cycle with no price
history produces 0 intents, so only 1 observation event was emitted — failing `>= 5`.

Fix: same `MomentumFeed` + `cycle_limit=3` pattern. 3 obs + 1 intent + 2 fills + 1 exposure
= 7 incremental `write_event` calls, satisfying `>= 5`.

### 10-minute paper soak results

**Run ID:** `ddb89f4ef6c0`
**Artifact dir:** `artifacts/tapes/crypto/paper_runs/2026-03-29/ddb89f4ef6c0/`
**Duration:** 21.5 minutes actual (10-minute window + reconnect overhead)
**Markets scanned:** 18
**Opportunities observed:** 949
**Intents generated:** 0
**Reference feed:** Coinbase (live BTC price ~$66,366)
**Feed state:** connected_fresh throughout, 0 stale, 0 disconnects

**Why 0 intents:** No active BTC/ETH/SOL 5m/15m pair markets exist on Polymarket as of
2026-03-29. The markets scanned were returning static prices (not oscillating enough to
clear the 0.3% momentum threshold). All 949 observations have `signal_direction=NONE`.

**New observation fields confirmed present:**
- `reference_price`: 66366.22 (live Coinbase BTC price)
- `price_change_pct`: 0.0 (insufficient price movement)
- `signal_direction`: "NONE"
- `favorite_side`: null
- `hedge_side`: null
- `entry_timing_seconds`: null

**Verdict:** RERUN PAPER SOAK (expected — no eligible markets available)

---

## Commits

| Hash | Message |
|------|---------|
| `9289b15` | `test(quick-049): add failing TDD tests for momentum engine` |
| (prior session, multiple) | Momentum engine implementation + paper runner wiring |
| `49d6e71` | `test(quick-049): fix streaming mode test to use MomentumFeed + 3 cycles` |

---

## Open Items

- No active BTC/ETH/SOL 5m/15m markets on Polymarket as of 2026-03-29. Use
  `python -m polytool crypto-pair-watch --one-shot` to check availability.
- When markets appear, re-run `crypto-pair-await-soak` to get real momentum signal data
  and evaluate whether the 0.3% threshold needs tuning.
- `_entered_brackets` cooldown is in-memory only; if the runner restarts mid-bracket,
  the cooldown resets. This is acceptable for paper mode but should be reviewed before
  live deployment.
