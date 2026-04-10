# 2026-04-10 — Wallet Discovery v1 Acceptance Hardening

## Objective

Add integrated acceptance tests that validate the frozen v1 contract end-to-end on
deterministic fixtures. No new product scope. Purpose: prove the full v1 path works
as a cohesive system, not just at the unit level.

## Work Done

### Task 1: Created `tests/test_wallet_discovery_integrated.py`

613 lines. 12 integrated acceptance tests covering the full v1 path:

```
leaderboard fetch -> snapshot rows -> churn detection -> queue insert -> scan --quick -> MVF output
```

Test classes:

| Class | Tests | What it proves |
|---|---|---|
| `TestIntegratedLoopAPath` | 4 | fetch->churn->queue flow; idempotency of queue and snapshot |
| `TestIntegratedScanQuickMvf` | 4 | MVF shape; null maker_taker; no-LLM request interception; no-quick no-MVF |
| `TestIntegratedLifecycleGate` | 3 | happy path; scanned->promoted blocked; reviewed->promoted without approval blocked |
| `TestIntegratedLoopAOrchestrator` | 1 | run_loop_a() dry_run black-box: 100 fetched, 100 new, 0 enqueued |

All tests use injected timestamps, UUIDs, in-memory ScanQueueManager, and mocked
HTTP clients. No network, no ClickHouse, no real clock dependency.

### Task 2: Feature doc update

`docs/features/wallet-discovery-v1.md` updated with a "Hardening pass" entry noting
the 12 new integrated tests and updating the total discovery-area test count from 106 to 118.
No scope was added; all other doc assertions verified accurate vs shipped behavior.

## Test Commands Run

### Integrated test suite only

```
python -m pytest tests/test_wallet_discovery_integrated.py -v --tb=short -x
```

Result: **12 passed in 1.24s**

### Full discovery area

```
python -m pytest tests/test_wallet_discovery.py tests/test_mvf.py tests/test_scan_quick_mode.py tests/test_wallet_discovery_integrated.py -v --tb=short
```

Result: **118 passed in 2.31s**

### CLI smoke test

```
python -m polytool --help
```

Result: CLI loads, all commands listed, no import errors.

### Full project suite

```
python -m pytest tests/ -q --tb=no --deselect tests/test_ris_phase2_cloud_provider_routing.py
```

Result: **3908 passed, 11 deselected, 25 warnings** — zero regressions introduced.

Note: `tests/test_ris_phase2_cloud_provider_routing.py` has 8 pre-existing failures
(AttributeError: providers module missing `_post_json` attribute). These failures exist
on main before this packet and are out of scope.

## Deviations from Plan

None. Plan executed exactly as written. All 12 tests passed on the first run without
any production code changes — the v1 contract was already correct.

## Commits

| Hash | Message |
|---|---|
| `c6d0982` | test(260410-gop-01): add integrated acceptance tests for wallet discovery v1 |
| `a3d23c4` | docs(260410-gop-02): update wallet-discovery-v1 feature doc with hardening pass |

## Codex Review

Tier: Skip (test-only changes + doc update — no execution, strategy, or CH write paths modified).
