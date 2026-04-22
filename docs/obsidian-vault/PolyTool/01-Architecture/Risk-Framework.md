---
type: architecture
tags: [architecture, risk, status/done]
created: 2026-04-08
---

# Risk Framework

Source: roadmap "Risk Framework" + CLAUDE.md "Risk, Fees, and Live-Trading Guardrails" + roadmap "Capital Progression".

---

## Validation Ladder

Three levels of validation before live capital.

| Level | Name | What It Tests |
|-------|------|--------------|
| L1 | Multi-tape replay | Strategy must show positive net PnL across a broad tape set |
| L2 | Scenario sweep | Realistic latency / fill assumptions (150ms latency, 70% fill rate) |
| L3 / Gate 3 | Live shadow | Strategy decisions against real markets using simulated fills only |

---

## Gate Definitions

### Gate 1 — Replay Pass (PASSED)

- SimTrader L1 replay against at least one tape
- Status: **PASSED**

### Gate 2 — Parameter Sweep (FAILED as of 2026-03-29)

- MarketMaker strategy sweep across benchmark_v1 tape set (50 tapes)
- Gate threshold: **≥70% of tapes show positive net PnL after fees and realistic-retail assumptions**
- Status: **FAILED** — 7/50 positive (14%)
- Root cause: Silver tapes produce zero fills; politics/sports tapes negative PnL
- Crypto bucket positive: 7/10 (btc-updown 4/5, eth-updown 2/2, sol-updown 1/3)
- Gate artifact: `artifacts/gates/mm_sweep_gate/gate_failed.json`
- Run command: `python tools/gates/run_recovery_corpus_sweep.py --manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/mm_sweep_gate --threshold 0.70`

### Gate 3 — Shadow Run (BLOCKED)

- Live shadow run on 3-5 markets with simulated fills only
- Shadow PnL must stay within **25%** of Gate 2 replay prediction
- Status: **BLOCKED** — Gate 2 must PASS first

### Gate 4 — Dry-Run Pass (PASSED)

- Status: **PASSED**

---

## Capital Progression

Staged live deployment after Gate 3 passes.

| Stage | Capital | Description |
|-------|---------|-------------|
| Stage 0 | $0 | Paper live dry-run (72 hours, zero errors, positive PnL estimate) |
| Stage 1 | $500 | First live capital — 3-5 markets, 7 days |
| Stage 2+ | $500 → $5K → $25K | Scale if profitable; human approval required for each stage increase |

---

## Live-Trading Guardrails (CLAUDE.md rules)

- Fee realism matters — do not assume zero-friction profitability in replay or live code
- The repo's legacy research pipeline uses a 2% gross-profit fee model; Polymarket market-specific fees can differ — be explicit about which fee model a component uses
- Respect current platform rate limits and existing rate-limiter abstractions
- Always preserve the kill-switch model
- Inventory limits, daily loss caps, and max order/notional caps are not optional
- Do not weaken risk defaults just to make a backtest or paper run look better

---

## Execution Safety Modules

Located in `packages/polymarket/simtrader/execution/`:

| Module | Lines | Purpose |
|--------|-------|---------|
| `kill_switch.py` | 53 | Hardware kill switch — immediate halt on trigger (file-based) |
| `risk_manager.py` | 252 | Inventory limits, daily loss caps, max order caps |
| `rate_limiter.py` | 90 | API rate limiter (token bucket) |
| `live_executor.py` | 155 | Live order executor (wraps py_clob_client) |
| `live_runner.py` | 183 | Live strategy runner with session management |
| `order_manager.py` | 286 | Order lifecycle management and tracking |
| `adverse_selection.py` | 589 | Adverse selection detection and mitigation |

---

## Human-in-the-Loop Policy

### Fully Autonomous

- Candidate discovery and scoring
- Wallet scanning and dossier generation
- Alpha distillation and hypothesis creation
- SimTrader L1 and L2 validation runs
- SimTrader L3 shadow run initiation
- Research scraper ingestion (after quality gate)
- Market selection scoring
- Strategy parameter adjustments within pre-approved bounds
- Kill switch trigger on risk limit breach
- Crypto pair bot trade execution (within configured risk limits)

### Human Approval Required

- Promoting a strategy to live capital
- Capital stage increases (Stage 1 → 2 → 3)
- Any strategy flagged LOW_CONFIDENCE by LLM evaluation
- Strategy REVIEW state (perf_ratio 0.40–0.75)
- Autoresearch structural code changes (Phase 6)

### Human Only

- Wallet private key operations
- Moving capital or funding the hot wallet
- Infrastructure secrets
- Adding a strategy type never previously validated
- Disabling a live strategy

---

## Fee Realism

Polymarket market-making fee structure for crypto markets:
- Taker orders: small fee (dynamic, peaks near 50% odds)
- Maker orders: 20bps REBATE (paid to provide liquidity)
- Strategy uses maker orders exclusively → net positive fee impact

SimTrader fee model: `fee = fee_rate × notional × (1 - notional × fee_rate)` (quadratic curve)

Note: Two implementations exist — see [[Issue-Dual-Fee-Modules]] for the duplication risk.

---

## Cross-References

- [[Gates]] — Gate script inventory and details
- [[Track-1B-Market-Maker]] — Market maker strategy validation path
- [[System-Overview]] — System architecture overview
- [[Issue-Dual-Fee-Modules]] — Fee module duplication issue
