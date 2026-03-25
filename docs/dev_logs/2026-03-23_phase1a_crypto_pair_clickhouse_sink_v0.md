# Dev Log: Phase 1A Crypto Pair ClickHouse Sink v0

**Date:** 2026-03-23  
**Track:** Track 2  
**Status:** COMPLETE

---

## Objective

Add the Track 2 ClickHouse sink contract and Grafana-ready event schema without
activating ClickHouse writes by default.

---

## Files changed and why

- `packages/polymarket/crypto_pairs/event_models.py`
  - Added explicit Track 2 event models, stable ClickHouse column ordering, JSON serialization, and helpers to project existing paper-ledger records into event batches.
- `packages/polymarket/crypto_pairs/clickhouse_sink.py`
  - Added the opt-in ClickHouse sink config, contract metadata, no-op disabled sink, lazy real sink, and structured write results.
- `tests/test_crypto_pair_clickhouse_sink.py`
  - Added offline coverage for event serialization, disabled no-op behavior, soft-fail write behavior, and schema contract stability.
- `infra/clickhouse/initdb/26_crypto_pair_events.sql`
  - Added non-invasive DDL for the future `polytool.crypto_pair_events` table.
- `docs/specs/SPEC-crypto-pair-clickhouse-event-schema-v0.md`
  - Documented the event contract, table schema, activation model, and Grafana panel mapping.
- `docs/features/FEATURE-crypto-pair-clickhouse-sink-v0.md`
  - Added the feature-level summary for the inactive-by-default sink packet.
- `docs/dev_logs/2026-03-23_phase1a_crypto_pair_clickhouse_sink_v0.md`
  - Added this implementation log.

---

## Commands run + output

### 1. Initial targeted contract test

Command:

```bash
python -m pytest tests/test_crypto_pair_clickhouse_sink.py -q
```

Output:

```text
collected 4 items
...F
FAILED tests/test_crypto_pair_clickhouse_sink.py::test_clickhouse_schema_contract_is_stable
FileNotFoundError: ... infra\clickhouse\initdb\26_crypto_pair_events.sql
```

Fix applied:

- Corrected the test to resolve the repo-root DDL path from `__file__`.

### 2. Targeted contract test after fix

Command:

```bash
python -m pytest tests/test_crypto_pair_clickhouse_sink.py -q
```

Output:

```text
collected 4 items
4 passed in 0.24s
```

### 3. Requested broader crypto-pair slice

Command:

```bash
python -m pytest tests/test_crypto_pair_paper_ledger.py tests/test_crypto_pair_run.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_clickhouse_sink.py -q
```

Output:

```text
collected 18 items
18 passed in 2.55s
```

---

## Test results

- Initial targeted contract run: **3 passed / 1 failed**
  - Failure was the test-side DDL path lookup, not the event/sink implementation.
- Final targeted contract run: **4 passed / 0 failed**
- Requested broader crypto-pair slice: **18 passed / 0 failed**

No network access was used in tests.

---

## Event model decisions

1. One wide ClickHouse event table instead of one table per event type.
   - Reason: keeps Grafana queries simple and avoids premature schema fan-out.
2. Sparse first-class columns plus `event_payload_json`.
   - Reason: dashboards can query common metrics directly while long-tail detail stays available for debugging and future panels.
3. JSON serialization keeps Decimal-like values as strings.
   - Reason: matches the existing artifact-first style and avoids precision loss in offline records.
4. ClickHouse projection uses nullable numeric columns.
   - Reason: keeps the table query-friendly for histograms, time series, and aggregates.
5. Event construction is layered on top of existing `paper_ledger` records.
   - Reason: avoids duplicating Track 2 accounting logic and keeps the contract close to the current artifact model.
6. Safety transitions are modeled explicitly, starting with feed-state changes.
   - Reason: Phase 1A dashboards need visible disconnect/stale safety state changes, not just fills and settlements.

---

## What is intentionally NOT activated yet

- No paper-mode default writes to ClickHouse
- No live-mode default writes to ClickHouse
- No runner/store wiring that calls `write_events(...)`
- No Docker requirement for default Track 2 runs
- No Grafana dashboard provisioning or JSON export changes
- No migration/backfill from existing JSONL bundles into ClickHouse

---

## Open questions for next prompt

1. Should the future wiring happen at the position-store boundary or after run finalization from artifact files?
2. Should live-mode runtime events beyond feed-state changes also be normalized into `safety_state_transition` rows in the first wiring packet?
3. Is `Float64` sufficient for Grafana-facing PnL metrics, or does the next packet want ClickHouse `Decimal` types for tighter accounting precision?
4. Should a future backfill tool project historical JSONL bundles into this event table, or should persistence start only for new runs after activation?
