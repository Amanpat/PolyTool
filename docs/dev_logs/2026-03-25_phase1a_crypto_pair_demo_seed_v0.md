# Dev Log: Phase 1A Crypto Pair Demo Seed v0

**Date**: 2026-03-25
**Scope**: Track 2 / Phase 1A
**Objective**: Add a dev-only synthetic Track 2 ClickHouse seeder so Grafana
can be validated even when Polymarket has no active target crypto-pair markets

---

## Files Changed And Why

- `packages/polymarket/crypto_pairs/dev_seed.py`
  - added the synthetic event-batch builder and write helper
  - reused real paper-ledger primitives plus Track 2 event models
  - stamped every seeded run with synthetic/dev-only labels
- `tools/cli/crypto_pair_seed_demo_events.py`
  - added the dev-only CLI entrypoint
  - enforced explicit ClickHouse credential checks before any write
  - printed cleanup SQL after a successful seed
- `polytool/__main__.py`
  - registered `crypto-pair-seed-demo-events`
  - exposed the command in CLI usage text
- `tests/test_crypto_pair_seed_demo_events.py`
  - added offline coverage for synthetic event generation
  - added offline coverage for sink construction and fail-fast auth behavior
- `docs/features/FEATURE-crypto-pair-seed-demo-events-v0.md`
  - documented command usage, synthetic labeling, and cleanup flow
- `docs/dev_logs/2026-03-25_phase1a_crypto_pair_demo_seed_v0.md`
  - recorded implementation details, verification commands, and cleanup notes

---

## Commands Run + Output

### 1. Help Command

```bash
python -m polytool crypto-pair-seed-demo-events --help
```

Output:

```text
usage: __main__.py [-h] [--clickhouse-host CLICKHOUSE_HOST]
                   [--clickhouse-port CLICKHOUSE_PORT]
                   [--clickhouse-user CLICKHOUSE_USER]
                   [--clickhouse-password CLICKHOUSE_PASSWORD]
                   [--run-id RUN_ID]

DEV-ONLY: seed a small synthetic Track 2 crypto-pair event batch into
ClickHouse so the Grafana paper-soak dashboard can be validated when real
BTC/ETH/SOL 5m/15m markets are absent.
```

### 2. Offline Test Run

```bash
pytest tests\test_crypto_pair_seed_demo_events.py -q
```

Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 3 items

tests\test_crypto_pair_seed_demo_events.py ...                           [100%]

============================== 3 passed in 0.24s ==============================
```

### 3. Live Seed Execution

Not run during implementation. The task-required verification only called for
`--help` plus the offline pytest file, and writing synthetic rows would mutate
the local ClickHouse table.

---

## Test Results

- `python -m polytool crypto-pair-seed-demo-events --help`: passed
- `pytest tests\test_crypto_pair_seed_demo_events.py -q`: passed
- offline assertions confirm the batch includes:
  - opportunity observed
  - intent generated
  - simulated fill
  - partial exposure update
  - completed settlement
  - safety/disconnect event
  - run summary

---

## Safety Labeling Of Synthetic Data

- `mode` is kept as `paper` so the existing Grafana queries can see the rows
- `source` is always `crypto_pair_demo_seed_dev_only_v0`
- `run_id` starts with `synthetic-demo-track2-`
- synthetic market IDs, slugs, opportunity IDs, intent IDs, fill IDs,
  settlement IDs, and transition IDs use the `synthetic-demo-` prefix
- opportunity assumptions include:
  - `synthetic_demo_event_not_real_market`
  - `dev_only_dashboard_validation_seed`
- safety transition reason:
  `synthetic_demo_disconnect_for_dashboard_validation`
- run summary stopped reason:
  `synthetic_demo_seed_completed`

These labels make the rows obviously synthetic while still matching the real
Track 2 schema and dashboard filters.

---

## How To Clear / Remove Seeded Demo Rows

After a successful seed, the CLI prints a scoped cleanup statement using the
synthetic run ID:

```sql
ALTER TABLE polytool.crypto_pair_events
DELETE WHERE run_id = '<synthetic-run-id>'
  AND source = 'crypto_pair_demo_seed_dev_only_v0'
```

Recommended flow:

1. Run the seed command and copy the printed `run_id`.
2. Execute the matching `ALTER TABLE ... DELETE ...` statement in ClickHouse.
3. Wait for ClickHouse background merges to finalize the delete before
   re-checking Grafana.

This keeps deletion restricted to the demo batch and avoids touching real
Track 2 rows.
