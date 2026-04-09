# Dev Log: Wallet Discovery v1 Contract Freeze

**Date**: 2026-04-09
**Quick task**: 260409-l77
**Type**: Docs-only — no code, migrations, tests, or workflow JSON changed.

---

## What Was Done

Froze the Wallet Discovery v1 contract as a docs-only packet. Created one canonical
spec, one feature stub, and updated four governing docs to establish truth-sync.

---

## Naming Choice

**Naming used**: `SPEC-wallet-discovery-v1.md`

**Rationale**: The project uses two spec naming conventions:

1. Numbered specs (`SPEC-0001` through `SPEC-0019`) for gate/SimTrader/infrastructure
   specs that have a well-defined ordering relationship (e.g., SPEC-0011 live execution,
   SPEC-0014 tape acquisition).

2. Descriptive slugs for feature specs that are self-contained and do not need a
   sequence number (e.g., `SPEC-wallet-scan-v0.md`, `SPEC-alpha-distill-v0.md`,
   `SPEC-benchmark-closure-operator-readiness-v0.md`).

Wallet Discovery v1 is a self-contained feature spec that does not need a global
sequence number. The `SPEC-wallet-discovery-v1.md` pattern follows `SPEC-wallet-scan-v0.md`
and `SPEC-alpha-distill-v0.md` exactly. This naming choice was made deliberately and
is recorded here so future agents do not re-litigate it.

---

## What Was Frozen

### V1 Scope

The spec defines exactly four capabilities as v1 scope:

1. **Loop A leaderboard discovery** — 24h fetch, churn detection (DAY vs ALL
   comparison), scan queue population.
2. **ClickHouse table contracts** — `watchlist`, `leaderboard_snapshots`, `scan_queue`
   with exact DDL (column names, types, engines, ORDER BY keys).
3. **Unified `polytool scan <address> --quick`** — hard no-LLM-call guarantee on
   the `--quick` flag; MVF + detectors + PnL output.
4. **MVF computation** — 11-dimensional fingerprint, Python math only, no cloud LLM.

### Table Contracts

Exact ClickHouse DDL is in the spec for all three tables. Engine choices:
- `watchlist` and `scan_queue`: `ReplacingMergeTree(updated_at)` — mutable state,
  one current row per key.
- `leaderboard_snapshots`: `MergeTree()` — append-only raw facts.

### Lifecycle State Machine

Documented with valid transitions, invalid transitions, and their triggers. Key
invariant: `scanned -> promoted` is explicitly invalid. The mandatory path is
`scanned -> reviewed -> promoted` where `reviewed -> promoted` requires
`review_status = 'approved'` set by a human operator.

### Deterministic Acceptance Tests

7 acceptance tests defined as specifications (not code):
- AT-01: Leaderboard pagination fixture (150 entries, 3 pages, no duplicates)
- AT-02: Churn detection (new wallet flagging, dropped wallet detection)
- AT-03: Snapshot idempotency (same key, same snapshot_ts — no duplicate rows)
- AT-04: Queue dedup and lease behavior (single open item per dedup_key, expiry)
- AT-05: Invalid lifecycle transition rejection (application-level, not ClickHouse)
- AT-06: `--quick` no-LLM guarantee (verified by request-intercepting fixture)
- AT-07: MVF output shape (all 11 dims, float ranges, metadata block, determinism)

---

## Research and Decision Context

The v1 scope was narrowed based on:

- **Obsidian vault research** (session notes, research pipeline docs):
  The full four-loop discovery architecture (A/B/C/D) and 7-phase roadmap were
  reviewed. Loop A was identified as the minimal viable starting point that provides
  real signal without requiring Alchemy WebSocket accounts, CLOB WebSocket
  connectivity, or cloud LLM policy changes.

- **Architect review (2026-04-09)**:
  - Insider scoring using a single averaged-p0 binomial test is mathematically
    incorrect. The test treats all events as if they have the same base probability,
    which is wrong for a multi-category prediction market. Per-bucket calibration is
    required before insider scoring can be implemented.
  - Cloud LLM wallet analysis (Loop C) requires an explicit PLAN_OF_RECORD update
    to extend the Tier 1 policy beyond RIS evaluation. This is a human decision.

- **Director decision** (Obsidian vault: "Decision - Roadmap Narrowed to V1"):
  Full four-loop system is future intent. V1 is the correct implementation target.

---

## Explicitly Deferred Capabilities (and why)

| Capability | Deferral reason |
|------------|-----------------|
| Loop B (Alchemy WebSocket) | Alchemy account not created; dynamic topic filter feasibility unproven; CU cost model unknown |
| Loop C (cloud LLM wallet analysis) | PLAN_OF_RECORD Section 0 update required; current policy authorizes Tier 1 cloud APIs for RIS evaluation only |
| Loop D (CLOB anomaly detection) | CLOB WebSocket connectivity unproven; anomaly threshold calibration data not available |
| Insider scoring | Single averaged-p0 binomial test is mathematically incorrect (architect review); per-bucket calibration test design required first |
| Auto-promotion | Evidence-quality threshold not defined; human gate removal not justified |
| n8n discovery integration | Phase 3 target; RIS n8n pilot (ADR 0013) does not extend to discovery workflows |
| Copy-trading system | Not in any v1 milestone; separate track |

---

## Files Changed

### New files (docs only)
- `docs/specs/SPEC-wallet-discovery-v1.md` — canonical v1 contract
- `docs/features/wallet-discovery-v1.md` — feature stub
- `docs/dev_logs/2026-04-09_wallet_discovery_v1_contract_freeze.md` — this file

### Updated files (docs only, surgical additions)
- `docs/ROADMAP.md` — Wallet Discovery v1 milestone section added
- `docs/CURRENT_STATE.md` — Wallet Discovery v1 status section added
- `docs/ARCHITECTURE.md` — discovery tables row added to database table
- `docs/INDEX.md` — spec and feature entries added

### Not changed
- No files under `packages/`, `tools/`, `infra/`, `tests/`, `services/`, `config/`
- No Docker files, workflow JSON, or migration scripts

---

## Existing Tests

No code was touched. Existing test suite remains unchanged and passable.
Smoke test: `python -m polytool --help` exits 0, CLI loads without errors.

---

## Codex Review

- **Tier**: Skip (docs-only change; no execution, risk, or strategy code)
- **Issues found**: N/A
- **Issues addressed**: N/A
