# Master Construction Manual — Component Mapping Note

**Status:** Reference / Future-direction mapping (not a scope change)
**Created:** 2026-03-04
**Author:** PolyTool Contributors

---

## Disclaimer

This document is a **future-direction mapping note only**. It does not change the scope of
this repository. PolyTool today is a **research-only toolchain**: it ingests public Polymarket
data, simulates strategies against recorded tapes, and supports offline LLM-assisted
hypothesis examination. There is no exchange-integrated live trading system in this repo right
now. Track A Stage-0 execution primitives exist, but they are gated and dry-run-first by
default and do not change the current roadmap scope.

The "Construction Manual" referenced here is a conceptual framework describing what a
complete Polymarket automated-trading system would require. Mapping its components against
this repo's modules clarifies which building blocks already exist as research tools, which are
partially present, and which are entirely out of scope. This mapping is provided so that
future contributors can reason about the gap clearly — not as a commitment to build anything.

See `docs/PLAN_OF_RECORD.md` Section 1 for the durable mission and constraints, including:
- **No trading signals** — PolyTool does not provide trading recommendations or claim alpha.
- **Local-first** — all data and artifacts stay on the operator's machine.
- **Backtesting deferred** — Section 11 of PLAN_OF_RECORD describes kill conditions for
  any future backtesting work.

---

## Component Mapping Table

The Construction Manual describes a system with the following conceptual layers. Each row
maps one manual concept to its current status in this repo.

| Manual Concept | Current Repo Status | Where It Lives (or Would Live) | Notes |
|---|---|---|---|
| **Market data feed (WS)** | Exists | `packages/polymarket/simtrader/tape/recorder.py` | Records Polymarket Market Channel WS to immutable tapes (`raw_ws.jsonl`, `events.jsonl`) |
| **L2 order book reconstruction** | Exists | `packages/polymarket/simtrader/orderbook/l2book.py` | Pure state machine; handles `book` snapshots and `price_change` deltas; batched schema supported |
| **Replay engine** | Exists | `packages/polymarket/simtrader/replay/runner.py` | Deterministic replay of recorded tapes; drives L2 book, emits best_bid_ask timeline |
| **Fill simulation (broker)** | Exists | `packages/polymarket/simtrader/broker/` | Conservative fill model (back-of-queue, actual size, tick-aligned prices); no exchange connectivity |
| **Portfolio / PnL accounting** | Exists | `packages/polymarket/simtrader/portfolio/` | FIFO cost basis, realized + unrealized PnL, fee deduction; Decimal-safe |
| **Strategy framework** | Exists | `packages/polymarket/simtrader/strategy/base.py` + `strategies/` | Pluggable `Strategy` ABC; shipped strategies: `binary_complement_arb`, `copy_wallet_replay` |
| **Scenario sweeps / parameter grid** | Exists | `tools/cli/simtrader.py` (`--sweep`, `batch`) | Quick sweep presets (24 scenarios); batch leaderboard with `batch_manifest.json` |
| **Shadow / paper-trading mode** | Exists | `packages/polymarket/simtrader/shadow/runner.py` | Live WS → strategy → simulated fills; no real orders placed; tape recording optional |
| **Activeness probe** | Exists | `packages/polymarket/simtrader/activeness_probe.py` | Measures WS update rate before committing to a market; CLI: `--activeness-probe-seconds` |
| **Market selection / auto-pick** | Exists | `packages/polymarket/simtrader/market_picker.py` | Resolves slugs, validates CLOB book, auto-selects candidates; `--list-candidates` |
| **Artifact management** | Exists | `tools/cli/simtrader.py` (`clean`, `diff`, `report`, `browse`) | Safe dry-run deletion; run comparison; self-contained HTML reports |
| **Resolution / outcome data** | Exists (partial) | `packages/polymarket/resolution.py` | 4-stage cascade: ClickHouse → OnChainCTF → Subgraph → Gamma; gaps documented in PLAN_OF_RECORD §3 |
| **Historical trade ingestion** | Exists | `polytool/` CLI commands (`scan`, `export-dossier`) | Pulls public trade/position data into ClickHouse; FIFO PnL approximation |
| **Hypothesis / evidence pipeline** | Exists | `scan` → `export-dossier` → `llm-bundle` → manual LLM → `llm-save` | Research workflow, not trading workflow; see `docs/RUNBOOK_MANUAL_EXAMINE.md` |
| **Local RAG / evidence retrieval** | Exists | `packages/polymarket/rag/`; CLI: `rag-index`, `rag-query` | Chroma + SentenceTransformers; hybrid vector + FTS5; private-local only |
| **Signals store (news/social)** | Not started | Would live at `packages/polymarket/simtrader/signals/` | Described in SPEC-0010 §8 as "Optional / Future"; gated behind SimTrader-5 + evidence of timing edge |
| **Live order submission** | Partial / gated Stage 0 | `packages/polymarket/simtrader/execution/live_executor.py`, `live_runner.py`; `tools/cli/simtrader.py` (`live`) | Dry-run default; no exchange-integrated client is wired in the default path, so real submission remains blocked |
| **Risk management / position limits** | Exists (gated Stage 0) | `packages/polymarket/simtrader/execution/risk_manager.py` | Conservative pre-trade order, position, inventory, and daily-loss caps; used with kill-switch + rate-limiter primitives |
| **Execution algorithm (TWAP, etc.)** | Out of scope | N/A | No exchange connectivity; not planned for any current milestone |
| **Multi-account / portfolio aggregation** | Out of scope | N/A | Deferred to Roadmap 8 per PLAN_OF_RECORD §1 |
| **Cloud deployment** | Out of scope | N/A | Architecture does not preclude it; not required; AWS deferred per PLAN_OF_RECORD §1 |

---

## Progression Gates (Research → Live)

The Construction Manual envisions a progression from research to execution. The gates below
describe the conceptual sequence. **Stages beyond "Shadow" remain gated and are not approved
for live capital in this repo.**

```
Gate 1 — Tape / Replay [DONE]
  Record WS → deterministic replay → L2 book reconstruction verified.
  Required before any fill simulation.

Gate 2 — Broker Simulation [DONE]
  Conservative fill model on replay tapes → portfolio PnL → strategy testing.
  Required before shadow mode.

Gate 3 — Shadow Mode [DONE]
  Live WS feed → strategy → simulated fills, no real orders placed.
  Required before any hypothetical live execution could be considered.

Gate 4 — Hypothesis Validation Loop [PARTIAL / ROADMAP 4+]
  llm-save schema enforcement, hypothesis diff, falsification harness.
  Required before backtesting is meaningful (see PLAN_OF_RECORD §11).

Gate 5 — Backtesting [NOT STARTED / DEFERRED]
  Replay historical tapes to validate hypotheses with out-of-sample data.
  Blocked by: hypothesis validation loop, historical orderbook data, 3+ complete runs.
  Kill conditions documented in PLAN_OF_RECORD §11.

Gate 6 — Live Execution [PARTIAL / GATED STAGE 0]
  Dry-run-first execution primitives now exist: kill switch, rate limiter,
  risk manager, LiveExecutor, LiveRunner, and `simtrader live`.
  No exchange-integrated client is wired in the default path, and no capital
  stage is approved in the active roadmap.
```

---

## What This Is Not

- This document is **not** a roadmap change. Roadmap changes go in `docs/ROADMAP.md` via the
  standard planning process.
- This document is **not** a commitment to build live execution. The mapping explicitly labels
  Stages 5–6 as deferred or gated future work.
- This document is **not** an alpha claim. Any simulated PnL produced by SimTrader is
  evidence for further research, not a trading signal. See SPEC-0010 §7.3.

---

## Cross-References

- [Plan of Record](../PLAN_OF_RECORD.md) — Mission, constraints, backtesting kill conditions
- [SPEC-0010: SimTrader Vision](../specs/SPEC-0010-simtrader-vision-and-roadmap.md) — Full SimTrader architecture and phased roadmap
- [Current State](../CURRENT_STATE.md) — What is built and working today
- [Roadmap](../ROADMAP.md) — Active milestone checklist
- [Strategy Playbook](../STRATEGY_PLAYBOOK.md) — Hypothesis falsification methodology
