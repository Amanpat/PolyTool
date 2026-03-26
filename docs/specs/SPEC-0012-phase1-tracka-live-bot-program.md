# SPEC-0012: Phase 1 Track A Live Bot Program

**Status:** Accepted
**Created:** 2026-03-08
**Authors:** PolyTool Contributors

---

## 1. Purpose and scope

Define the canonical Phase 1 Track A live bot program: the strategy, validation
path, market selection policy, operator controls, and evidence artifacts required
before any live capital is deployed.

This spec is the single authoritative reference for the Track A story. Where it
conflicts with older planning language, this spec governs.

**In scope:**
- Canonical Phase 1 strategy identity
- Promotion ladder from Gate 1 through Stage 1
- Validation corpus requirements (mixed-regime)
- Market selection policy for live deployment
- Alerting, telemetry, and operator controls
- FastAPI/n8n sequencing rule
- Stage 0 and Stage 1 promotion requirements
- Kill and stop conditions
- Required evidence artifacts

**Out of scope:**
- Strategy discovery and alpha generation (Track B, research-only)
- Backtesting (explicitly deferred; see `PLAN_OF_RECORD.md` §11)
- Multi-strategy live operation (Phase 2+)
- Cloud deployment (local-first only until explicitly scoped)

---

## 2. Canonical strategy and non-goals

### Canonical Phase 1 strategy: `market_maker_v1`

The Phase 1 mainline live strategy is **`market_maker_v1`** — a Logit
Avellaneda-Stoikov market maker that operates in logit-probability space
for binary prediction markets.

> **Upgrade note:** `market_maker_v1` (Logit Avellaneda-Stoikov) replaced
> `market_maker_v0` as the Phase 1 default on 2026-03-10. `market_maker_v0`
> remains in the strategy registry but is no longer the Phase 1 mainline.
> SPEC-0012 was not updated at that time; this section corrects the record.
> See dev log `docs/dev_logs/2026-03-10_tracka_marketmaker_v1_default_wiring.md`
> and `docs/dev_logs/2026-03-26_phase1b_recovery_root_cause.md`.

Key properties:
- Logit-space quoting with logit Avellaneda-Stoikov spread formula
- Realized variance estimate on logit-mid price differences
- Trade-arrival proxy for kappa calibration
- Resolution guard (no quoting near market close)
- Bounded spreads and quote clamps for binary markets
- Registered as `"market_maker_v1"` in `STRATEGY_REGISTRY` (`strategy/facade.py`)
- Compatible with `simtrader run`, `simtrader quickrun`, `simtrader shadow`,
  and `simtrader live`

### Role of `binary_complement_arb`

`binary_complement_arb` is a **secondary scouting and detection strategy**. It
is used as the Gate 2 scouting vehicle: it identifies complement-arb
dislocations in live tapes to produce eligible Gate 2 evidence.

`binary_complement_arb` is **not** the Phase 1 live strategy. It must not be
described as the Track A mainline in any doc, runbook, or operator guide.

### Non-goals

- No market orders — limit orders only.
- No alpha logic or strategy generation within the execution layer.
- No live execution by default — dry-run is always the default.
- No automated capital allocation — operator controls all stage transitions.
- No "trade everything" — market selection filters apply at every stage.

---

## 3. Promotion ladder and hard gates

The canonical promotion ladder is:

```
Gate 1 (Replay Determinism)
  -> Gate 2 (Scenario Sweep ≥70%)
    -> Gate 3 (Shadow Mode, manual)
      -> Gate 4 (Dry-Run Live)
        -> Stage 0 (72h paper-live, zero capital)
          -> Stage 1 (live capital, operator opt-in)
```

**Hard rule**: no live capital before all four gates have `gate_passed.json`
artifacts and Stage 0 completes cleanly.

**Hard order**: gates must be completed in sequence. Gate 3 cannot start before
Gate 2 passes. Stage 0 cannot start before Gate 4 passes.

### Gate descriptions

| Gate | Script | What it validates |
|------|--------|-------------------|
| Gate 1 — Replay Determinism | `tools/gates/close_replay_gate.py` | Tape replay produces identical output across two runs |
| Gate 2 — Scenario Sweep ≥70% | `tools/gates/close_sweep_gate.py` | Strategy survives friction and latency stress; requires eligible tape with `executable_ticks > 0` |
| Gate 3 — Shadow Mode (manual) | `tools/gates/shadow_gate_checklist.md` | Live WS feed + simulated fills runs cleanly, including disconnect/reconnect |
| Gate 4 — Dry-Run Live | `tools/gates/run_dry_run_gate.py` | Full runner path is stable with zero order submission |

Gate artifacts are written to `artifacts/gates/<gate_name>/gate_passed.json`
(or `gate_failed.json`) with commit hash, timestamp, and operator sign-off.

Check current status:
```bash
python tools/gates/gate_status.py
```

Returns exit 0 only when all four gates have passing artifacts.

### Status as of 2026-03-08

- Gate 1: **PASSED**
- Gate 2: NOT PASSED (tooling ready; blocked on eligible tape)
- Gate 3: BLOCKED behind Gate 2
- Gate 4: **PASSED**
- Stage 0: BLOCKED until all four gates pass
- Stage 1: BLOCKED until Stage 0 completes cleanly

---

## 4. Validation corpus requirements

### Mixed-regime requirement

Gate 2+ validation must cover **at least three market regimes**:

| Regime | Examples |
|--------|---------|
| **Politics** | Elections, policy referenda, geopolitical outcomes |
| **Sports** | NFL, NBA, soccer, other event-resolution markets |
| **New markets** | Markets < 48 hours old (spread dynamics differ from mature markets) |

**Rationale**: A strategy validated only on sports markets may fail on politics
or new markets due to different liquidity profiles, event cadence, and spread
behavior. The mixed-regime corpus guards against regime overfitting.

**Minimum corpus for Gate 3 shadow validation**: at least one shadow run per
regime listed above. The operator documents which markets were used and their
regime labels in the Gate 3 artifact.

**Minimum corpus for Stage 0**: the 72-hour paper-live soak must include
observations across at least two regimes. If only one regime is active, the
operator documents this in the Stage 0 sign-off artifact.

---

## 5. Market selection policy for live deployment

Live deployment uses **filtered market selection**, not "trade everything."

### Pre-trade filters (`packages/polymarket/market_selection/filters.py`)

Markets must pass all filters before any strategy is allowed to quote:

| Filter | Policy |
|--------|--------|
| Mid-price range | 0.25 ≤ mid ≤ 0.75 (not near resolution) |
| Spread threshold | Spread after fees must exceed minimum viable edge |
| Age gate | Market must be active and not approaching close |
| Liquidity floor | Minimum orderbook depth on both sides |
| Category allowlist | Operator-configured; default allows all but can be restricted |

### Market scoring (`packages/polymarket/market_selection/scorer.py`)

`python -m polytool market-scan --top N` ranks eligible markets by a composite
score. The operator reviews top candidates and selects `--asset-id` explicitly.
The strategy never self-selects markets without operator review.

### One-market-at-a-time policy (Stage 1)

Stage 1 runs on a **single asset per session** (`--asset-id <TOKEN_ID>`).
Multi-market concurrent quoting is deferred to Phase 2+.

---

## 6. Alerting, telemetry, and operator controls

### Canonical alerting system: Discord

Discord is the canonical Track A alerting channel. Telegram references in any
doc are outdated and must be replaced with Discord.

Alert categories:
- **Runtime errors**: strategy exceptions, WS reconnect failures, executor errors
- **Kill-switch trips**: automatic and manual kill-switch activations
- **Risk cap breaches**: daily loss cap, inventory skew cap, per-order cap
- **Session lifecycle**: start, clean stop, abnormal exit

### Telemetry

All sessions write structured artifacts for audit and reconciliation:
- `run_manifest.json` — session metadata, risk config, strategy params
- `ledger.jsonl` — per-tick position and cash snapshots
- `equity_curve.jsonl` — equity over time
- `summary.json` — final PnL, fill counts, rejection counts

Grafana panels surface: order attempts, submitted orders, rejections,
kill-switch state, daily loss progression, inventory skew.

### Operator controls

| Control | Command |
|---------|---------|
| Emergency stop (immediate) | `python -m polytool simtrader kill` |
| Manual kill switch arm | `touch artifacts/kill_switch.txt` |
| Gate status check | `python tools/gates/gate_status.py` |
| Session dry-run (default) | `python -m polytool simtrader live --strategy market_maker_v1 ...` |
| Session live (explicit opt-in) | Add `--live` flag; requires `CONFIRM` |

The kill switch is checked before every place/cancel action, even in dry-run
mode. The strategy cannot bypass the kill switch.

---

## 7. FastAPI/n8n sequencing rule

FastAPI (`services/api/`) and any n8n automation workflows are **thin
automation layers only**. They do not own strategy logic, gate decisions, or
risk policy.

**Rule**: FastAPI and n8n invoke the CLI and respect CLI-enforced gate checks.
They must not re-implement gate logic, bypass the `CONFIRM` prompt, or hold
strategy state.

Specifically:
- Strategy configuration lives in `--strategy-config` JSON passed to the CLI.
- Gate artifacts are checked by the CLI at startup; automation layers may not
  pre-validate or skip them.
- Risk caps are enforced by `RiskManager` inside the CLI process; automation
  layers may not relax caps.
- Kill switch state is owned by `FileBasedKillSwitch`; automation layers check
  it by calling `simtrader kill` or reading the kill file, not by bypassing it.

If a FastAPI endpoint or n8n workflow triggers a simtrader session, it does so
by invoking the subprocess CLI, not by importing strategy classes directly.

---

## 8. Stage 0 and Stage 1 promotion requirements

### Stage 0 — 72-hour paper-live (zero capital)

**Prerequisites:**
- All four gate artifacts present and passing (`python tools/gates/gate_status.py` exits 0)
- Mixed-regime validation corpus complete (see §4)
- VPS provisioned with repo at intended release commit
- Discord alerts wired and confirmed active

**Run:**
```bash
python -m polytool simtrader live --strategy market_maker_v1 --asset-id <TOKEN_ID>
```
(Dry-run is the default; no `--live` flag for Stage 0.)

**Sign-off criteria:**
- 72 continuous hours without unhandled exceptions
- Kill switch never tripped by bug (operator trips are acceptable tests)
- Simulated PnL trajectory does not show consistent losses (net negative over >50% of ticks)
- No unrecoverable WS stalls within the 30-second stall timeout
- Operator reviews ledger.jsonl and equity_curve.jsonl; documents findings

**Stage 0 artifact**: operator writes `artifacts/gates/stage0/stage0_passed.json`
with commit hash, start time, end time, markets observed, regimes covered, and
sign-off note.

### Stage 1 — live capital (operator opt-in)

**Prerequisites:**
- Stage 0 artifact present and signed off
- Trading wallet funded with at least the configured `--max-position-usd`
- Environment loaded with `PK`, `CLOB_API_KEY`, `CLOB_API_SECRET`, `CLOB_API_PASSPHRASE`
- Polygon RPC configured
- Discord alerts confirmed active before session starts

**Initial Stage 1 risk caps:**
```bash
python -m polytool simtrader live --live \
  --strategy market_maker_v1 --asset-id <TOKEN_ID> \
  --max-position-usd 500 \
  --daily-loss-cap-usd 100 \
  --max-order-usd 200 \
  --inventory-skew-limit-usd 400
```

The CLI refuses to start if any gate artifact is missing. The operator must
enter `CONFIRM` at the live-trading warning banner.

**Stage 1 → Stage 2 promotion**: only after completing a clean Stage 1 review
cycle covering daily PnL, fill quality, and inventory behavior. Cap increases
require explicit operator documentation. This spec does not define Stage 2+.

---

## 9. Kill/stop conditions

### Automatic stop conditions (CLI-enforced)

- Kill switch file present (`artifacts/kill_switch.txt`): no new orders submitted.
- Daily loss cap breached: `RiskManager` rejects all new orders for the session.
- Inventory skew cap breached: `RiskManager` rejects directional orders until inventory normalizes.
- Per-order notional cap: orders above `--max-order-usd` are rejected.

### Operator stop conditions (manual)

- Any unhandled exception not recovered by the WS reconnect loop.
- Kill switch tripped more than once in a single session without a clear cause.
- Simulated or real PnL trending consistently negative with no sign of mean-reversion.
- Market regime changes (e.g., election outcome imminent) that invalidate the market selection basis.
- Discord alerts fire with no operator acknowledgment available.

### Emergency stop procedure

```bash
# Immediate: arm file kill switch
python -m polytool simtrader kill

# Manual fallback
touch artifacts/kill_switch.txt

# Verify: no new orders being submitted
# Then: investigate before restart
```

After any emergency stop, write a session incident note to `artifacts/gates/stage1/`
documenting the trigger, timeline, and disposition before restarting.

### Global kill conditions (Track A pause)

Track A live execution must pause entirely if:
- Gate artifact integrity cannot be verified against the running commit.
- RiskManager or KillSwitch code has been modified without a full gate re-run.
- A reproducible loss pattern appears that was not present in Stage 0.
- The operator cannot monitor Discord alerts for the duration of a session.

---

## 10. Required evidence artifacts

All of the following must be present and verifiable before Stage 1:

| Artifact | Path | Description |
|----------|------|-------------|
| Gate 1 artifact | `artifacts/gates/replay_gate/gate_passed.json` | Replay determinism confirmation |
| Gate 2 artifact | `artifacts/gates/sweep_gate/gate_passed.json` | Scenario sweep ≥70% pass with eligible tape |
| Gate 3 artifact | `artifacts/gates/shadow_gate/gate_passed.json` | Shadow mode manual operator sign-off |
| Gate 4 artifact | `artifacts/gates/dry_run_gate/gate_passed.json` | Dry-run live stability confirmation |
| Stage 0 artifact | `artifacts/gates/stage0/stage0_passed.json` | 72h paper-live sign-off |
| Mixed-regime log | Gate 3 + Stage 0 artifacts | Documents markets, regimes, and durations covered |
| Discord alert confirmation | Session notes | Evidence alerts fired and were acknowledged during Stage 0 |
| Market selection audit | `market-scan` run log | Shows filtered candidates reviewed before `--asset-id` was chosen |

Each artifact includes: commit hash, operator timestamp, and a human-readable
sign-off field. Artifacts are not generated by the strategy; they are written by
gate closure scripts or operator, and are read-only once passed.

---

## References

- `docs/PLAN_OF_RECORD.md` — mission constraints, fees policy, data gaps
- `docs/ARCHITECTURE.md` — component layout, execution loop diagram
- `docs/ROADMAP.md` — milestone checklist, gate evidence, kill conditions
- `docs/CURRENT_STATE.md` — current gate status, operator focus
- `docs/OPERATOR_QUICKSTART.md` — end-to-end operator guide
- `docs/runbooks/LIVE_DEPLOYMENT_STAGE1.md` — Stage 1 deployment runbook
- `docs/specs/SPEC-0011-live-execution-layer.md` — execution layer interfaces and gate model
- `packages/polymarket/simtrader/strategies/market_maker_v1.py` — canonical strategy (Phase 1 mainline)
- `packages/polymarket/simtrader/strategies/market_maker_v0.py` — legacy strategy (no longer mainline)
- `tools/gates/` — gate closure scripts and shadow checklist
