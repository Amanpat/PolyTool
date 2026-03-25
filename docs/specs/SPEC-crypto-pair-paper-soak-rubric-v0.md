# SPEC: Crypto Pair Paper Soak Rubric v0

**Status**: Ready for operator use (2026-03-23)  
**Track**: Track 2 / Phase 1A  
**Related**: `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`, `docs/features/FEATURE-crypto-pair-paper-soak-v0.md`, `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md`, `docs/specs/SPEC-crypto-pair-clickhouse-event-schema-v0.md`

---

## 1. Purpose

Define the operator-facing 24-48 hour paper-soak rubric for the Phase 1A
crypto pair bot and bind that rubric to the current Track 2 artifact and
ClickHouse event contracts.

The operator should be able to answer one question without inventing extra
criteria:

`ready for micro live or not?`

---

## 2. Scope

This spec defines:

- the minimum evidence window for a paper soak
- the exact metrics the operator must review
- the pass / rerun / reject bands for those metrics
- the artifact audit required for safety sign-off
- the Grafana panel/query requirements for the ClickHouse event layer

This spec does not define:

- runtime code changes
- live deployment approval beyond the rubric
- Grafana dashboard JSON, panel UIDs, or provisioning

---

## 3. Source of Truth

Track 2 remains file-first.

Primary operator truth:

- `run_manifest.json`
- `run_summary.json`
- `runtime_events.jsonl`
- `observations.jsonl`
- `order_intents.jsonl`
- `fills.jsonl`
- `exposures.jsonl`
- `settlements.jsonl`

Secondary operator truth:

- ClickHouse table `polytool.crypto_pair_events`
- Grafana panels backed by that table

Important constraint:

- the current paper runner batch-emits Track 2 events to ClickHouse only at
  finalization, so Grafana review is post-run, not live during the 24h soak
- the current Track 2 event schema lifts feed-state transitions into
  `safety_state_transition`, but kill-switch events, drawdown cap blocks, and
  sink-write failures still live in runtime artifacts rather than first-class
  event rows

---

## 4. Evidence Floor

Minimum operator evidence before any promote decision:

- soak duration at least `24h`
- `order_intents_generated >= 30`
- `paired_exposure_count >= 20`
- `settled_pair_count >= 20`

If the run is operationally clean but misses the evidence floor, the verdict is
`RERUN`, not `PROMOTE`.

Mandatory `48h` run if any of the following happen in the first 24h:

- any metric lands in the rerun band
- any `safety_state_transition` reaches `stale` or `disconnected`
- the evidence floor is only barely met and the sample still looks thin

No promote decision is allowed before the 24h minimum.

---

## 5. Metric Definitions

| Metric | Definition | Source |
|-------|------------|--------|
| Pair completion rate | `paired_exposure_count / order_intents_generated` | `run_summary` event fields |
| Average completed pair cost | `avg(paired_cost_usdc)` where `event_type='partial_exposure_updated'` and `exposure_status='paired'` | Track 2 events |
| Estimated profit per completed pair | `avg(1 - paired_net_cash_outflow_usdc)` on fully paired exposure rows | Track 2 events |
| Maker fill rate floor | `count(simulated_fill_recorded) / (2 * count(intent_generated))` | Track 2 events |
| Partial-leg incidence | `partial_exposure_count / order_intents_generated` | `run_summary` event fields |
| Stale transition count | `countIf(to_state='stale')` where `event_type='safety_state_transition'` and `state_key='reference_feed'` | Track 2 events |
| Disconnect transition count | `countIf(to_state='disconnected')` on the same feed-state stream | Track 2 events |
| Aggregate paper net PnL sanity | `run_summary.net_pnl_usdc > 0` | `run_summary.json` and `run_summary` event |
| Safety violations | Count of artifact-level safety failures defined in Section 7 | Manifest + runtime artifacts |

Interpretation notes:

- pair completion rate is the v0 schema-backed proxy for "did an intent become a
  fully paired position," not a future multi-intent repair metric
- maker fill rate is a conservative floor because the current event schema does
  not expose selected-leg order counts as first-class columns
- estimated profit per completed pair must use `paired_net_cash_outflow_usdc`,
  not raw `paired_cost_usdc`, because the paper runner includes the configured
  maker rebate in net cash outflow

---

## 6. Pass / Rerun / Reject Bands

| Metric | Pass | Rerun | Reject |
|-------|------|--------|--------|
| Pair completion rate | `>= 0.90` | `>= 0.80` and `< 0.90` | `< 0.80` |
| Average completed pair cost | `<= 0.965` | `> 0.965` and `<= 0.970` | `> 0.970` |
| Estimated profit per completed pair | `>= 0.035` | `>= 0.030` and `< 0.035` | `< 0.030` |
| Maker fill rate floor | `>= 0.95` | `>= 0.90` and `< 0.95` | `< 0.90` |
| Partial-leg incidence | `<= 0.10` | `> 0.10` and `<= 0.20` | `> 0.20` |
| Feed-state transitions | `disconnect_count = 0`, `stale_count <= 2`, and the last recorded state is `connected_fresh` or no transition row exists | `disconnect_count = 1` or `stale_count in [3,5]`, but freeze/recovery is clean | `disconnect_count > 1`, `stale_count > 5`, last recorded state is not fresh after a degraded period, or freeze audit fails |
| Safety violations | `0` | none | `>= 1` |

Why these bands are conservative:

- the hard pair-cost ceiling in the current runner is `0.97`
- the minimum configured profit threshold is `0.03`
- the default maker rebate assumption is `20 bps`
- the rerun band allows the operator to gather more evidence without treating a
  marginal 24h run as a live-ready result

---

## 7. Safety Violation Definition

Any single safety violation is an automatic `REJECT` for the current soak.

Safety violation means any of the following:

- `run_manifest.json["stopped_reason"] != "completed"`
- `run_manifest.json["has_open_unpaired_exposure_final"] == true`
- `runtime_events.jsonl` contains `kill_switch_tripped`
- `runtime_events.jsonl` contains `order_intent_blocked` with
  `block_reason="daily_loss_cap_reached"`
- sink was enabled and `sink_write_result.error` is non-empty or
  `sink_write_result.skipped_reason == "write_failed"`
- any `order_intent_created` occurs while the feed is in a frozen window that
  began with a `safety_state_transition` to `stale` or `disconnected` and had
  not yet recovered to `connected_fresh`

Guardrail rule:

- positive economics do not override a safety failure

---

## 8. Decision Logic

### 8.1 Promote

Verdict is `PROMOTE TO MICRO LIVE CANDIDATE` only if all of the following are
true:

- evidence floor is met
- soak duration is at least `24h`
- every primary metric is in the pass band
- aggregate paper `net_pnl_usdc` is positive
- safety violations are zero

### 8.2 Rerun

Verdict is `RERUN PAPER SOAK` when:

- no safety violation occurred
- no reject-band metric fired
- but one or more metrics land in the rerun band, or the evidence floor is not
  yet met

The rerun path is:

- fix nothing if the issue is only thin sample
- fix infra if the issue is isolated feed quality or ClickHouse availability
- rerun for `48h`, not another short 24h pass

### 8.3 Reject

Verdict is `REJECT CURRENT CONFIG / DO NOT PROMOTE` when:

- any safety violation occurs
- any primary metric lands in the reject band
- the run shows positive per-pair economics but unstable operations

---

## 9. Required Review Surfaces

The operator sign-off must review both layers:

### Artifact layer

- `run_manifest.json`
- `run_summary.json`
- `runtime_events.jsonl`

### Grafana / ClickHouse layer

- paper soak scorecard
- completion / partial metrics
- pair cost distribution
- estimated profit per completed pair
- net profit per settlement
- cumulative net PnL
- daily or hourly trade count
- feed safety transition counts
- recent feed safety event table

The query pack for those panels is defined in
`docs/features/FEATURE-crypto-pair-grafana-panels-v0.md`.

---

## 10. Known Limitations

- exact maker-order denominator is not first-class in `polytool.crypto_pair_events`;
  the rubric therefore uses a conservative fill-rate floor
- feed-state transitions are first-class Track 2 events, but broader safety
  lifecycle evidence still requires `runtime_events.jsonl` and `run_manifest.json`
- because the paper runner emits the ClickHouse batch at finalization, Grafana
  is currently a post-run review surface rather than a live soak monitor
