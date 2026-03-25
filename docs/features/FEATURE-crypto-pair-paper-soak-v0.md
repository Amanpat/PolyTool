# Summary

Track 2 / Phase 1A now has an operator-facing paper-soak packet for the crypto
pair bot.

The packet is meant to answer one question after a 24-48 hour paper run:

- promote to micro live candidate
- rerun paper mode
- reject the current config

It does that without changing runtime code.

# What Shipped

## Paper Soak Rubric

`docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md` defines:

- the minimum evidence floor for a soak
- the exact formulas for the required metrics
- pass / rerun / reject bands
- automatic no-go rules for safety failures

## Operator Runbook

`docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md` defines:

- how to start the 24h soak
- when to escalate to 48h
- which artifacts to inspect first
- which Grafana panels to review after finalization
- what constitutes promote / rerun / reject

## Grafana Query Layer

`docs/features/FEATURE-crypto-pair-grafana-panels-v0.md` defines a panel pack
for the existing Track 2 event table:

- paper soak scorecard
- active pairs
- pair cost distribution
- estimated profit per completed pair
- profit per settlement
- cumulative net PnL
- trade count
- feed safety transitions

# Key Guardrails

- any safety violation is an automatic no-go
- positive paper economics do not override unstable operations
- 24h is the minimum evidence window
- 48h is required when the first 24h run is marginal or sees feed degradation

# Important Limitations

- the paper runner currently writes its ClickHouse event batch only at
  finalization, so Grafana is a post-run review surface rather than a live soak
  monitor
- the current Track 2 event schema does not expose selected-leg order counts as
  first-class columns, so maker fill is documented as a conservative floor
- some safety evidence still lives in `runtime_events.jsonl` and
  `run_manifest.json`, not only in `polytool.crypto_pair_events`
