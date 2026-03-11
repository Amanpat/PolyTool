## Summary

Track A Week 1 shipped the Stage-0 execution primitives behind
`python -m polytool simtrader live`.

This is a safety-first execution shell, not a promotion to live capital.
Dry-run is the default, the Track A gates remain in force, and the default CLI
path uses a no-op strategy.

## What shipped

- `FileBasedKillSwitch` + `KillSwitch`
- `TokenBucketRateLimiter`
- `RiskManager` with conservative Stage-0 caps
- `LiveExecutor` with kill-switch-first order/cancel flow
- `LiveRunner` orchestration
- `simtrader live` CLI wiring

## Safety properties

- Dry-run default: `simtrader live` does not submit orders unless `--live` is passed.
- Kill-switch first: the kill switch is checked before strategy execution and before every place/cancel action.
- Rate-limited live path: live calls consume token-bucket capacity; dry-run never touches the client.
- Conservative defaults: order, position, daily-loss, and inventory caps start small.
- Gated usage: `replay -> scenario sweeps -> shadow -> dry-run live` remains the hard order.

## How to run it

```bash
python -m polytool simtrader live

python -m polytool simtrader live \
  --kill-switch artifacts/kill_switch.txt \
  --rate-limit 30 \
  --max-order-usd 25 \
  --max-position-usd 100 \
  --daily-loss-cap-usd 15 \
  --inventory-skew-limit-usd 100
```

`--live` exists, but it is still a gated operator-only path and not the
normal shipped workflow.

## Current boundary

- The shipped CLI path runs a single Stage-0 tick and prints a JSON summary.
- The default path is dry-run-first and safe even when no strategy returns any orders.
- Exchange-integrated order submission is not wired into the default path.

## References

- `docs/specs/SPEC-0011-live-execution-layer.md`
- `docs/dev_logs/2026-03-05_trackA_week1_execution_primitives.md`
