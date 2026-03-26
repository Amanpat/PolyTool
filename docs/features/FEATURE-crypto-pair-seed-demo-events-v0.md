# Feature: Crypto Pair Seed Demo Events v0

**Status**: Shipped
**Track**: Track 2 / Phase 1A
**Date**: 2026-03-25
**Purpose**: Dev-only synthetic ClickHouse seed path for Grafana dashboard validation

---

## Summary

Track 2 now has a dedicated dev-only CLI that writes a small synthetic event
batch into `polytool.crypto_pair_events` so the Grafana paper-soak dashboard can
be validated when Polymarket has no active BTC/ETH/SOL 5m/15m markets.

This path is:

- explicit: it runs only via `python -m polytool crypto-pair-seed-demo-events`
- non-default: no production or paper runner default was changed
- schema-correct: it reuses the real Track 2 event models and ClickHouse writer
- clearly synthetic: seeded rows are labeled so they cannot be confused with
  real soak evidence

---

## Command

```bash
python -m polytool crypto-pair-seed-demo-events \
  --clickhouse-password "$CLICKHOUSE_PASSWORD"
```

Supported auth inputs:

- `--clickhouse-password`
- `CLICKHOUSE_PASSWORD` environment variable

If the password is missing or empty, the command fails fast before attempting
any ClickHouse write.

---

## What Gets Seeded

One synthetic paper-mode run is generated and inserted with these event types:

- `opportunity_observed`
- `intent_generated`
- `simulated_fill_recorded`
- `partial_exposure_updated`
- `pair_settlement_completed`
- `safety_state_transition`
- `run_summary`

The batch includes:

- one fully paired-and-settled synthetic BTC market
- one partially filled synthetic ETH market that remains open
- one synthetic reference-feed disconnect transition
- one run summary that rolls up the seeded activity

This is enough to exercise the main Grafana paper-soak panels, including active
pairs, pair cost distribution, settlement PnL, trade counts, safety events, and
run-summary scorecards.

---

## Synthetic Labeling

The seeded rows are intentionally obvious:

- `mode = 'paper'` so the existing dashboard queries include them
- `source = 'crypto_pair_demo_seed_dev_only_v0'`
- `run_id` starts with `synthetic-demo-track2-`
- synthetic market IDs, slugs, opportunities, intents, fills, settlements, and
  transitions are prefixed with `synthetic-demo-`
- opportunity assumptions include:
  - `synthetic_demo_event_not_real_market`
  - `dev_only_dashboard_validation_seed`
- the safety event reason is
  `synthetic_demo_disconnect_for_dashboard_validation`
- the run summary stopped reason is `synthetic_demo_seed_completed`

---

## Implementation Notes

The seed path reuses the real Track 2 contract instead of inventing a parallel
payload shape:

- `packages/polymarket/crypto_pairs/dev_seed.py` builds paper-ledger records,
  converts them with `build_events_from_paper_records(...)`, and appends a real
  `SafetyStateTransitionEvent`
- `tools/cli/crypto_pair_seed_demo_events.py` builds an enabled
  `CryptoPairClickHouseSinkConfig` with `soft_fail=False`
- writes go through `build_clickhouse_sink(...)` and `write_events(...)`

No live trading logic, strategy math, Gate 2 files, or production defaults were
changed.

---

## Cleanup

The command prints a cleanup statement after a successful write:

```sql
ALTER TABLE polytool.crypto_pair_events
DELETE WHERE run_id = '<synthetic-run-id>'
  AND source = 'crypto_pair_demo_seed_dev_only_v0'
```

Use the printed `run_id` from that specific seed run. This keeps cleanup scoped
to the demo rows only.

---

## Tests

Offline coverage lives in:

```text
tests/test_crypto_pair_seed_demo_events.py
```

Covered behaviors:

- synthetic batch contains the required dashboard event types
- seeded events are clearly labeled synthetic
- CLI builds an enabled ClickHouse sink with explicit credentials
- CLI fails fast when ClickHouse credentials are missing
