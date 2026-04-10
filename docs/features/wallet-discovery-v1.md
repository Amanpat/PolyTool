# Wallet Discovery v1

## Status

**Implemented** (2026-04-09). **Integrated** (2026-04-10).

This is NOT the full four-loop discovery system. See the spec for non-goals and blockers.

---

## Implementation

Delivered across two parallel packets integrated on 2026-04-10:

- **Packet A** (commit `83832e1`): ClickHouse DDL (3 tables), models with lifecycle state machine,
  leaderboard fetcher, churn detector, scan queue manager, Loop A orchestrator, `discovery` CLI — 54 tests.
- **Packet B** (commit `724a23c`): MVF computation module (`mvf.py`), `--quick` flag on `scan` CLI,
  MVF block wired into dossier artifact — 52 tests (37 MVF + 15 scan-quick).
- **Integration pass** (2026-04-10): Unified `packages/polymarket/discovery/__init__.py` exports
  covering all 11 symbols (8 Loop A models + 3 MVF). Removed dead ImportError guard.
  Combined 106 touched-area tests green.

---

## Spec

`docs/specs/SPEC-wallet-discovery-v1.md`

---

## What v1 Covers

Wallet Discovery v1 is a narrowly scoped discovery loop covering four capabilities:

1. **Loop A leaderboard discovery** — 24h fetch from the Polymarket leaderboard API,
   churn detection (new wallets, rising wallets, DAY vs ALL comparison), and scan
   queue population.

2. **ClickHouse table contracts** — Three new tables:
   - `watchlist` — one row per wallet, `lifecycle_state` and `review_status` fields,
     no auto-promotion.
   - `leaderboard_snapshots` — append-only raw fetch facts.
   - `scan_queue` — deduplicating work queue with lease/expiry semantics.

3. **Unified `python -m polytool scan <address>` with `--quick`** — The existing
   `scan` surface extended with a `--quick` flag. `--quick` is a hard no-LLM-call
   guarantee: it produces MVF vector, existing detectors, and PnL data without any
   cloud LLM endpoint call under any condition.

4. **MVF (Multi-Variate Fingerprint) computation** — An 11-dimensional fingerprint
   vector computed from a wallet's trade history using Python math only, no cloud LLM
   calls. Dimensions include win rate, hold duration, entry price, market concentration,
   category entropy, position size, trade frequency, late-entry rate, DCA score,
   resolution coverage, and maker/taker ratio.

---

## CLI Surface

Extended:
```
python -m polytool scan <address> [--quick]
```

New:
```
python -m polytool discovery run-loop-a
```

---

## Human Review Gate

A human review gate is **required** before any wallet reaches the `promoted` or
`watched` lifecycle state. No code path in v1 bypasses this gate. The wallet lifecycle
state machine enforces that `scanned -> promoted` is an invalid transition; the
correct path is `scanned -> reviewed -> promoted` where the `reviewed -> promoted`
transition requires `review_status = 'approved'` set by a human operator.

---

## What v1 Does NOT Cover

- Loop B (live wallet monitoring via Alchemy WebSocket)
- Loop C (deep analysis + cloud LLM hypothesis generation)
- Loop D (platform-wide anomaly detection via CLOB WebSocket)
- Insider scoring (binomial test, pre-event trading score)
- Exemplar selection (trade annotation for LLM context)
- Cloud LLM calls for wallet analysis (policy not yet authorized beyond RIS)
- Auto-promotion to watchlist
- n8n workflow integration for discovery
- Docker service definitions for Loop B / Loop D
- Copy-trading system

See `docs/specs/SPEC-wallet-discovery-v1.md` section "Blockers for Phases Beyond v1"
for the named prerequisite for each deferred capability.

---

## Predecessor

`docs/features/wallet-scan-v0.md` — Wallet-Scan v0 is the existing batch scan
implementation. Wallet Discovery v1 extends the `scan` CLI surface (adds `--quick`)
and adds discovery-specific infrastructure (Loop A, ClickHouse tables, MVF).
