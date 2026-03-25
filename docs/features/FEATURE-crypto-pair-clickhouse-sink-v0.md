# Summary

Track 2 now has a concrete ClickHouse sink contract and Grafana-ready event
schema for the crypto-pair runner, but ClickHouse writes remain disabled by
default.

This packet is preparatory:

- paper/live runner artifacts stay JSONL-first
- no Docker dependency is introduced for default runs
- no runtime path fails just because ClickHouse is absent

# What Shipped

## Event Models

`packages/polymarket/crypto_pairs/event_models.py` defines explicit Track 2
event objects for:

- opportunity observed
- intent generated
- simulated fill recorded
- partial exposure updated
- pair settlement completed
- safety state transition
- run summary

The models can be built directly from the existing paper-ledger records with
`build_events_from_paper_records(...)`.

## Optional ClickHouse Sink

`packages/polymarket/crypto_pairs/clickhouse_sink.py` defines:

- `CryptoPairClickHouseSinkConfig`
- `ClickHouseSinkContract`
- `CryptoPairClickHouseSink`
- `DisabledCryptoPairClickHouseSink`
- `build_clickhouse_sink(...)`

Behavior:

- disabled by default
- lazy client creation only when writes are explicitly enabled
- no-op result when disabled
- soft-fail result when enabled but ClickHouse is unavailable

## ClickHouse Table Contract

`infra/clickhouse/initdb/26_crypto_pair_events.sql` adds a non-invasive DDL for:

- `polytool.crypto_pair_events`

The table is a single wide event stream with nullable metrics plus
`event_payload_json` for long-tail detail. It is meant for future Grafana use,
not for current runtime activation.

# Grafana Mapping

The schema is documented to support future panels for:

- active pairs
- pair cost distribution
- realized profit per settlement
- cumulative PnL
- daily trade count

No dashboard JSON or provisioning was added in this packet.

# Not Activated Yet

- no runner/store wiring calls `write_events(...)`
- no paper-mode or live-mode default writes to ClickHouse
- no dashboard provisioning
- no historical backfill from existing artifact bundles
