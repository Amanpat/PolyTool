# SPEC: Crypto Pair ClickHouse Event Schema v0

**Status**: Ready for wiring, inactive by default (2026-03-23)  
**Track**: Track 2 / Phase 1A  
**Related**: Roadmap Phase 1A, `FEATURE-crypto-pair-clickhouse-sink-v0.md`, `FEATURE-crypto-pair-runner-v0.md`

---

## 1. Purpose

Prepare the Track 2 crypto-pair runner for future ClickHouse persistence and
Grafana dashboards without changing the current JSONL-first runtime contract.

This packet ships:

- explicit Track 2 event models
- a default-disabled ClickHouse writer interface
- a Grafana-ready single-table event schema
- non-invasive ClickHouse DDL for future activation

This packet does **not** ship:

- active ClickHouse writes from paper or live runner defaults
- Docker as a runtime requirement
- Grafana dashboard provisioning

---

## 2. Design Rule

Track 2 remains file-first.

`artifacts/crypto_pairs/...` JSON and JSONL files stay authoritative in v0.
The ClickHouse sink is an optional projection target for a later packet.

The future write path is intentionally one-way:

1. existing runner artifacts are created first
2. Track 2 event models project those records into one explicit event contract
3. an opt-in sink may write those events to ClickHouse

No current runner path depends on ClickHouse availability.

---

## 3. Module Contract

## `packages/polymarket/crypto_pairs/event_models.py`

Exports:

- `OpportunityObservedEvent`
- `IntentGeneratedEvent`
- `SimulatedFillRecordedEvent`
- `PartialExposureUpdatedEvent`
- `PairSettlementCompletedEvent`
- `SafetyStateTransitionEvent`
- `RunSummaryEvent`
- `build_events_from_paper_records(...)`
- `CLICKHOUSE_EVENT_COLUMNS`

JSON serialization uses string-safe decimal fields for artifact fidelity.
ClickHouse projection uses nullable numeric columns for dashboard queries.

## `packages/polymarket/crypto_pairs/clickhouse_sink.py`

Exports:

- `CryptoPairClickHouseSinkConfig`
- `ClickHouseSinkContract`
- `ClickHouseWriteResult`
- `CryptoPairClickHouseSink`
- `DisabledCryptoPairClickHouseSink`
- `build_clickhouse_sink(...)`

Writer contract:

- `write_events(events)` accepts Track 2 event objects directly
- default config is `enabled=False`
- disabled mode is a no-op, not a startup blocker
- enabled mode lazily creates a ClickHouse client only when first used
- `soft_fail=True` converts write failures into structured results instead of exceptions

---

## 4. Event Types

The schema version is `crypto_pair_clickhouse_event_schema_v0`.

Supported event types:

1. `opportunity_observed`
2. `intent_generated`
3. `simulated_fill_recorded`
4. `partial_exposure_updated`
5. `pair_settlement_completed`
6. `safety_state_transition`
7. `run_summary`

### 4.1 `opportunity_observed`

Source: `PaperOpportunityObservation`

Key fields:

- `opportunity_id`
- `yes_token_id`
- `no_token_id`
- `yes_quote_price`
- `no_quote_price`
- `pair_quote_cost`
- `target_pair_cost_threshold`
- `threshold_edge_usdc`
- `threshold_passed`
- `quote_age_seconds`
- `assumptions`

### 4.2 `intent_generated`

Source: `PaperOrderIntent`

Key fields:

- `intent_id`
- `opportunity_id`
- `pair_size`
- `intended_yes_price`
- `intended_no_price`
- `intended_pair_cost`
- `intended_paired_notional_usdc`
- `target_pair_cost_threshold`
- fee and cap fields retained in payload JSON

### 4.3 `simulated_fill_recorded`

Source: `PaperLegFill`

Key fields:

- `fill_id`
- `intent_id`
- `leg`
- `token_id`
- `side`
- `fill_price`
- `fill_size`
- `fill_notional_usdc`
- `fee_adjustment_usdc`
- `net_cash_delta_usdc`

### 4.4 `partial_exposure_updated`

Source: `PaperExposureState`

Key fields:

- `intent_id`
- `exposure_status`
- `paired_size`
- `paired_cost_usdc`
- `paired_fee_adjustment_usdc`
- `paired_net_cash_outflow_usdc`
- `unpaired_size`
- `unpaired_notional_usdc`
- `unpaired_max_loss_usdc`
- `unpaired_max_gain_usdc`
- full `yes_position` and `no_position` snapshots retained in payload JSON

### 4.5 `pair_settlement_completed`

Source: `PaperPairSettlement`

Key fields:

- `settlement_id`
- `intent_id`
- `winning_leg`
- `paired_size`
- `settlement_value_usdc`
- `gross_pnl_usdc`
- `net_pnl_usdc`

### 4.6 `safety_state_transition`

Source: runtime/feed safety transitions, starting with feed state changes

Key fields:

- `transition_id`
- `state_key`
- `from_state`
- `to_state`
- `reason`
- optional cycle/details in payload JSON

### 4.7 `run_summary`

Source: `PaperRunSummary`

Key fields:

- `markets_seen`
- `opportunities_observed`
- `threshold_pass_count`
- `threshold_miss_count`
- `order_intents_generated`
- `paired_exposure_count`
- `partial_exposure_count`
- `settled_pair_count`
- `intended_paired_notional_usdc`
- `open_unpaired_notional_usdc`
- `gross_pnl_usdc`
- `net_pnl_usdc`

---

## 5. ClickHouse Table Contract

**Table**: `polytool.crypto_pair_events`  
**DDL**: `infra/clickhouse/initdb/26_crypto_pair_events.sql`  
**Engine**: `ReplacingMergeTree(recorded_at)`  
**ORDER BY**: `(run_id, event_type, event_ts, event_id)`

The schema is intentionally wide and sparse so Grafana can query one table
without event-type-specific joins.

### 5.1 Common identity columns

- `event_id`
- `event_type`
- `schema_version`
- `event_ts`
- `recorded_at`
- `run_id`
- `mode`
- `source`
- `market_id`
- `condition_id`
- `slug`
- `symbol`
- `duration_min`

### 5.2 Entity reference columns

- `opportunity_id`
- `intent_id`
- `fill_id`
- `settlement_id`
- `transition_id`
- `leg`
- `token_id`
- `side`
- `state_key`
- `from_state`
- `to_state`
- `reason`
- `exposure_status`
- `winning_leg`
- `yes_token_id`
- `no_token_id`

### 5.3 Numeric query columns

- `yes_quote_price`
- `no_quote_price`
- `pair_quote_cost`
- `target_pair_cost_threshold`
- `threshold_edge_usdc`
- `pair_size`
- `intended_yes_price`
- `intended_no_price`
- `intended_pair_cost`
- `intended_paired_notional_usdc`
- `fill_price`
- `fill_size`
- `fill_notional_usdc`
- `fee_adjustment_usdc`
- `net_cash_delta_usdc`
- `paired_size`
- `paired_cost_usdc`
- `paired_fee_adjustment_usdc`
- `paired_net_cash_outflow_usdc`
- `unpaired_size`
- `unpaired_notional_usdc`
- `unpaired_max_loss_usdc`
- `unpaired_max_gain_usdc`
- `settlement_value_usdc`
- `gross_pnl_usdc`
- `net_pnl_usdc`
- `markets_seen`
- `opportunities_observed`
- `threshold_pass_count`
- `threshold_miss_count`
- `order_intents_generated`
- `paired_exposure_count`
- `partial_exposure_count`
- `settled_pair_count`
- `open_unpaired_notional_usdc`
- `quote_age_seconds`
- `threshold_passed`

### 5.4 JSON carry-through columns

- `assumptions_json`
- `event_payload_json`

`event_payload_json` stores the full JSON serialization of the event so future
panels or debugging paths can recover fields not lifted into first-class
columns.

---

## 6. Grafana Panel Mapping

### 6.1 Active pairs

Recommended source: latest event per `intent_id` across
`partial_exposure_updated` and `pair_settlement_completed`.

Interpretation:

- latest event is `partial_exposure_updated` => pair is still active
- latest event is `pair_settlement_completed` => pair is closed

Useful fields:

- `symbol`
- `slug`
- `paired_size`
- `unpaired_size`
- `exposure_status`
- `event_ts`

### 6.2 Pair cost distribution

Recommended source: `intent_generated`

Primary metric:

- `intended_pair_cost`

Optional pre-intent diagnostic view:

- `opportunity_observed.pair_quote_cost`

### 6.3 Realized profit per settlement

Recommended source: `pair_settlement_completed`

Primary metrics:

- `net_pnl_usdc`
- `gross_pnl_usdc`
- `settlement_value_usdc`

### 6.4 Cumulative PnL

Recommended source: `pair_settlement_completed`

Primary metric:

- cumulative sum of `net_pnl_usdc` ordered by `event_ts`

### 6.5 Daily trade count

Recommended source: `simulated_fill_recorded`

Primary metric:

- count of rows grouped by `toDate(event_ts)`

If the future dashboard wants pair-level trade count instead of leg-level count,
use distinct `intent_id` per day instead.

---

## 7. Activation Behavior

Default behavior:

- `CryptoPairClickHouseSinkConfig.enabled = False`
- `build_clickhouse_sink()` returns `DisabledCryptoPairClickHouseSink`
- no runner/store module imports ClickHouse at startup
- no Docker dependency is introduced

Opt-in behavior for the next packet:

1. project paper/live artifacts into Track 2 event objects
2. construct `CryptoPairClickHouseSinkConfig(enabled=True, ...)`
3. call `sink.write_events(events)`

---

## 8. Out of Scope

- runner/store wiring to emit these events automatically
- live-run activation of ClickHouse persistence
- Grafana dashboard JSON provisioning
- migration/backfill from existing JSONL artifacts
- changing Gate 2 or unrelated repo infrastructure
