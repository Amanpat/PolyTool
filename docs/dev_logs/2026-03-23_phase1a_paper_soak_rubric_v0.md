# Dev Log: Phase 1A Paper Soak Rubric v0

**Date:** 2026-03-23  
**Track:** Track 2 / Phase 1A

## Files Changed And Why

| File | Why |
|------|-----|
| `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md` | Added the operator procedure for starting a 24h paper soak, reviewing artifacts, reviewing Grafana, and issuing a promote / rerun / reject verdict. |
| `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md` | Added the formal rubric: evidence floor, formulas, pass bands, safety violation definition, and decision logic. |
| `docs/features/FEATURE-crypto-pair-paper-soak-v0.md` | Added the feature-level summary for the paper-soak packet. |
| `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md` | Added the Grafana-ready panel and SQL template layer mapped to `polytool.crypto_pair_events`. |
| `docs/OPERATOR_QUICKSTART.md` | Added a short reference-doc cross-link to the new Track 2 paper-soak docs. |
| `docs/dev_logs/2026-03-23_phase1a_paper_soak_rubric_v0.md` | Recorded the source docs, rubric choices, panel/query list, and open questions. |

## Source Docs Used

- `docs/reference/POLYTOOL_MASTER_ROADMAP_v5.md`
- `docs/specs/SPEC-crypto-pair-clickhouse-event-schema-v0.md`
- `docs/features/FEATURE-crypto-pair-clickhouse-sink-v0.md`
- `docs/features/FEATURE-crypto-pair-runner-v0.md`
- `docs/features/FEATURE-crypto-pair-runner-v1.md`
- `docs/features/FEATURE-crypto-pair-backtest-v0.md`
- `docs/dev_logs/2026-03-23_phase1a_crypto_pair_backtest_v0.md`
- `docs/dev_logs/2026-03-23_phase1a_paper_runner_sink_wiring_v0.md`
- `infra/clickhouse/initdb/26_crypto_pair_events.sql`
- `packages/polymarket/crypto_pairs/paper_runner.py`
- `packages/polymarket/crypto_pairs/paper_ledger.py`
- `packages/polymarket/crypto_pairs/event_models.py`
- `packages/polymarket/crypto_pairs/position_store.py`

## Rubric Decisions

- Set the minimum soak window to `24h`, with a mandatory `48h` rerun whenever
  the first 24h run is marginal or sees feed degradation.
- Added an evidence floor so a thin run cannot be promoted:
  - `order_intents_generated >= 30`
  - `paired_exposure_count >= 20`
  - `settled_pair_count >= 20`
- Defined pair completion using the current v0 schema contract:
  `paired_exposure_count / order_intents_generated`.
- Defined average completed pair cost from `partial_exposure_updated` paired
  rows rather than raw intent rows, so the metric reflects actual paired fills.
- Defined estimated profit per completed pair as
  `1 - paired_net_cash_outflow_usdc`, not `1 - paired_cost_usdc`, so the maker
  rebate is included.
- Defined maker fill rate as a conservative floor:
  `count(simulated_fill_recorded) / (2 * count(intent_generated))`.
- Treated any safety violation as automatic reject, including kill switch,
  daily loss cap, sink write failure with sink enabled, unpaired exposure at end
  of run, or intent creation inside a frozen feed window.
- Documented explicitly that Grafana review is post-run because the current paper
  runner writes the event batch only at finalization.

## Panel / Query List

- Recent run selector
- Paper soak scorecard
- Run summary funnel
- Active pairs
- Pair cost distribution
- Estimated profit per completed pair
- Net profit per settlement
- Cumulative net PnL
- Daily trade count
- Feed state transition counts
- Recent feed safety events
- Maker fill rate floor
- Partial-leg incidence

## Open Questions For Next Prompt

1. Should `selected_legs` or an explicit intended-leg count be lifted into
   `polytool.crypto_pair_events` so maker fill rate can be exact rather than a
   conservative floor?
2. Should runtime safety events such as kill-switch trips, drawdown-cap blocks,
   and sink write failures become first-class Track 2 event rows so the full
   go / no-go verdict can live inside Grafana?
3. Should the paper runner emit events incrementally during the soak instead of
   only at finalization, so Grafana can be used as a live monitor rather than a
   post-run review surface?
