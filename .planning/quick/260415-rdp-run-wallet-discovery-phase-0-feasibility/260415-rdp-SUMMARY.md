---
phase: quick-260415-rdp
plan: 01
subsystem: wallet-discovery
tags: [loop-b, feasibility, on-chain, alchemy, websocket, abi-decoding]
dependency_graph:
  requires: [SPEC-wallet-discovery-v1.md, packages/polymarket/on_chain_ctf.py]
  provides: [loop_b_probe.py, Loop B feasibility verdict]
  affects: [packages/polymarket/discovery/, docs/dev_logs/]
tech_stack:
  added: [pycryptodome keccak256 (already installed, now explicitly used)]
  patterns: [raw JSON-RPC ABI decoding (no web3.py), Ethereum log topic extraction]
key_files:
  created:
    - packages/polymarket/discovery/loop_b_probe.py
    - tests/test_loop_b_probe.py
    - docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md
  modified: []
decisions:
  - "Hardcode ORDER_FILLED_TOPIC0 constant (verified via pycryptodome at authoring time) rather than computing at import time — avoids runtime dependency, follows on_chain_ctf.py selector convention"
  - "VERDICT: READY_WITH_CONSTRAINTS — Loop B technically viable with 4 named constraints"
  - "No backfill possible: maker/taker data not present in user_trades or jb_trades warehouse tables"
  - "Two subscriptions required for maker-OR-taker filtering (Ethereum OR-within-topic limitation)"
  - "A/B subscription swap pattern recommended to avoid event gaps during watchlist updates"
metrics:
  duration: "~25 minutes"
  completed: "2026-04-15"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 0
  tests_added: 36
  tests_regression: 118
---

# Phase quick-260415-rdp Plan 01: Loop B Phase 0 Feasibility Summary

**One-liner:** OrderFilled ABI decoder + wallet topic filter helpers proving Loop B READY_WITH_CONSTRAINTS (4 named blockers, none architectural dead-ends).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Build OrderFilled decoding + wallet filter probe module | 04e5d4d | packages/polymarket/discovery/loop_b_probe.py, tests/test_loop_b_probe.py |
| 2 | Write feasibility verdict dev log | 0ea2b57 | docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md |

## Verification Results

- `python -m pytest tests/test_loop_b_probe.py -v --tb=short -x` — **36 passed, 0 failed**
- `python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py` — **118 passed, 0 failed** (no regressions)
- `python -m polytool --help` — exit 0, no import errors
- Dev log size: 10,474 bytes (> 2,000 byte threshold)

## Feasibility Verdict

**READY_WITH_CONSTRAINTS**

Loop B (Alchemy-based watched-wallet monitoring) is technically viable. All core mechanics proven:

| Question | Verdict |
|----------|---------|
| OrderFilled decoding (maker/taker/asset IDs) | YES — 36 deterministic tests passing |
| Maker/taker data in warehouse | NOT AVAILABLE — on-chain events only, no backfill |
| Dynamic subscription update without data loss | YES WITH CONSTRAINTS — A/B swap pattern required |
| CU budget within 30M free tier | YES — 50 wallets = 1.38M CU/month (4.6%) |
| Topic-based wallet filtering viable | YES — maker=topic2, taker=topic3, OR-within-position confirmed |

## Remaining Blockers (4 items, none architectural dead-ends)

1. **BLOCKER-1 (human-action):** Alchemy account creation + `ALCHEMY_API_KEY` in `.env` (~5-10 min).
2. **BLOCKER-2 (implementation):** Async WebSocket manager with A/B subscription swap (~200-300 LOC). Pattern references: `clob_stream.py`, `shadow/runner.py`.
3. **BLOCKER-3 (implementation):** New ClickHouse table `loop_b_fills` for decoded on-chain fills (new DDL, ~20 lines, ReplacingMergeTree on (tx_hash, log_index)).
4. **BLOCKER-4 (design decision):** What action on watched-wallet trade? Options: Discord alert, copy-trade signal, or log-only. Operator decision required before alert pipeline is built.

## Key Design Decisions

- **No web3.py.** Pure Python keccak256 (pycryptodome) + manual hex chunking — follows `on_chain_ctf.py` convention throughout.
- **Hardcoded topic0 constant** (`0xd0a08e8c493f9c94f29311604c9de1b4e8c8d4c06bd0c789af57f2d65bfec0f6`) verified via pycryptodome at authoring time; `_compute_order_filled_topic0()` provides runtime verification in tests.
- **Two-subscription approach** for maker-OR-taker coverage (`build_wallet_filter_topics_either()`); or single unfiltered subscription + Python post-filter as simpler alternative.
- **A/B swap pattern** for zero-gap watchlist updates; dedup by (tx_hash, log_index) during overlap window.

## Deviations from Plan

None — plan executed exactly as written. The ORDER_FILLED_TOPIC0 value in the initial file write was corrected before tests ran (incorrect placeholder replaced with proper keccak256 via immediate pycryptodome verification — this was an authoring-time self-correction, not a deviation from the plan's intent).

## Known Stubs

None. All functions return real computed values. No placeholder data flows to any UI.

## Threat Flags

None. The probe module is offline-only (no network calls, no external API access, no user input processing). Threat model: T-rdp-01 (info disclosure, accepted — only public contract addresses) and T-rdp-02 (spoofing, accepted — authenticity guaranteed by Alchemy RPC in production Loop B).

## Self-Check: PASSED

- `packages/polymarket/discovery/loop_b_probe.py` — EXISTS (verified)
- `tests/test_loop_b_probe.py` — EXISTS (verified)
- `docs/dev_logs/2026-04-15_wallet_discovery_loop_b_pof.md` — EXISTS (verified)
- Commit `04e5d4d` — EXISTS (verified via git log)
- Commit `0ea2b57` — EXISTS (verified via git log)
- 36 probe tests: PASSED
- 118 regression tests: PASSED
