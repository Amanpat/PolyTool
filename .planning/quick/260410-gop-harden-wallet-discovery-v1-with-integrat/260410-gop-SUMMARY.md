---
phase: 260410-gop
plan: 01
subsystem: wallet-discovery
tags: [testing, acceptance, discovery, mvf, loop-a, lifecycle]
dependency_graph:
  requires: []
  provides: [integrated-acceptance-tests-wallet-discovery-v1]
  affects: [tests/test_wallet_discovery_integrated.py, docs/features/wallet-discovery-v1.md]
tech_stack:
  added: []
  patterns: [in-memory-stub, mock-http-client, monkeypatch, tmp_path, injected-fixtures]
key_files:
  created:
    - tests/test_wallet_discovery_integrated.py
    - docs/dev_logs/2026-04-10_wallet_discovery_v1_acceptance_hardening.md
  modified:
    - docs/features/wallet-discovery-v1.md
decisions:
  - "All 12 integrated tests written against existing contracts with zero production code changes — v1 contract was already correct"
  - "Pre-existing test_ris_phase2_cloud_provider_routing.py failures (8 tests) documented as out-of-scope; not fixed"
metrics:
  duration: "~12 minutes"
  completed_date: "2026-04-10"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
---

# Phase 260410-gop Plan 01: Wallet Discovery v1 Acceptance Hardening Summary

**One-liner:** 12 deterministic integrated acceptance tests for full v1 path (leaderboard fetch -> snapshot -> churn -> queue -> scan --quick -> MVF) on injected fixtures with zero production code changes.

---

## Tasks Completed

| Task | Name | Commit | Files |
|---|---|---|---|
| 1 | Create integrated acceptance test suite | `c6d0982` | `tests/test_wallet_discovery_integrated.py` (613 lines) |
| 2 | Verify existing tests + update feature doc | `a3d23c4` | `docs/features/wallet-discovery-v1.md` |

---

## What Was Built

### Task 1: `tests/test_wallet_discovery_integrated.py`

613-line integrated acceptance test file covering the full frozen v1 contract. All 12 tests are deterministic (no network, no ClickHouse, no real clock). All pass in 1.24s.

**Test structure:**

| Class | Count | Coverage |
|---|---|---|
| `TestIntegratedLoopAPath` | 4 | Full Loop A: 150-entry fetch->churn->queue; T vs T-1 churn (5 new / 5 dropped / 145 persisting); queue idempotency (10 wallets x2 = 10 items); snapshot idempotency |
| `TestIntegratedScanQuickMvf` | 4 | MVF shape (11 dims, all spec keys, input_trade_count, wallet_address); null maker_taker_ratio + data_note; no-LLM request interception; no-quick yields no mvf block |
| `TestIntegratedLifecycleGate` | 3 | Happy path (discovered->queued->scanned->reviewed->promoted); scanned->promoted blocked; reviewed->promoted-without-approval blocked |
| `TestIntegratedLoopAOrchestrator` | 1 | run_loop_a dry_run: 100 fetched, 100 new_wallets, 0 enqueued |

### Task 2: Feature doc update

`docs/features/wallet-discovery-v1.md` updated with "Hardening pass" entry. Test count corrected from 106 to 118. All other doc assertions verified accurate vs shipped behavior. No scope added.

---

## Test Counts

| Command | Result |
|---|---|
| `pytest tests/test_wallet_discovery_integrated.py -v --tb=short -x` | **12 passed in 1.24s** |
| `pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short` | **118 passed in 2.31s** |
| `python -m polytool --help` | CLI loads, no import errors |
| `pytest tests/ -q --tb=no --deselect tests/test_ris_phase2_cloud_provider_routing.py` | **3908 passed, 0 new failures** |

---

## Deviations from Plan

None — plan executed exactly as written. All 12 tests passed on first run without any production code changes.

---

## Pre-existing Issues (Out of Scope)

`tests/test_ris_phase2_cloud_provider_routing.py` has 8 pre-existing test failures
(AttributeError: `providers` module has no attribute `_post_json`). These failures exist
on `main` before this packet. Logged as out-of-scope per deviation scope boundary rule.

---

## Known Stubs

None — all test assertions verify real behavior against real modules.

---

## Threat Flags

None — changes are test-only and doc-only. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

---

## Self-Check

**Created files exist:**
- `tests/test_wallet_discovery_integrated.py` — FOUND (613 lines)
- `docs/dev_logs/2026-04-10_wallet_discovery_v1_acceptance_hardening.md` — FOUND
- `.planning/quick/260410-gop-harden-wallet-discovery-v1-with-integrat/260410-gop-SUMMARY.md` — this file

**Commits exist:**
- `c6d0982` — test(260410-gop-01): add integrated acceptance tests for wallet discovery v1
- `a3d23c4` — docs(260410-gop-02): update wallet-discovery-v1 feature doc with hardening pass

## Self-Check: PASSED
