# Live Deployment Stage 1

## Prerequisites

- All four Track A gates must be closed with `gate_passed.json` artifacts:
  `replay_gate`, `sweep_gate`, `shadow_gate`, `dry_run_gate`.
- The 72 hour Stage 0 paper-live run must be complete and clean on the same release commit.
- VPS is provisioned, reachable, and has the repo checked out on the intended release commit.
- Environment is loaded with `PK` and, if already derived, `CLOB_API_KEY`, `CLOB_API_SECRET`, and `CLOB_API_PASSPHRASE`.
- The trading wallet holds enough USDC for the configured Stage 1 limits.
- Grafana dashboards and Telegram alerts are active before the session starts.

## Validation Pipeline (Canonical)

The canonical operator validation pipeline is:

1. Replay Validation -> Gate 1
2. Sweep Validation -> Gate 2
3. Shadow Validation -> Gate 3
4. Dry Run -> Gate 4
5. Stage 0 -> 72 hour paper-live run
6. Stage 1 -> live trading with capital

Historical note: older planning language may refer to a "30-day shadow
validation." That wording is superseded. Gate 3 shadow validation plus Gate 4
dry-run live plus the separate 72 hour Stage 0 paper-live run are now the
required prerequisites for this Stage 1 runbook.

## Run

```bash
python -m polytool simtrader live --live --strategy market_maker_v0 \
  --best-bid 0.45 --best-ask 0.55 --asset-id <TOKEN_ID> \
  --max-position-usd 500 \
  --daily-loss-cap-usd 100 \
  --max-order-usd 200 \
  --inventory-skew-limit-usd 400
```

- The CLI will refuse to start if any gate artifact is missing.
- This runbook still assumes Stage 0 operator sign-off; the CLI enforces gate artifacts, not the Stage 0 completion record.
- The CLI will print a live-trading warning banner and require `CONFIRM`.
- `Ctrl+C` stops the current process. The file kill switch blocks new orders on the next check.

## Monitor

- Watch Grafana panels for order attempts, submitted orders, rejections, and kill-switch state.
- Watch Telegram alerts for runtime errors, kill-switch trips, and loss-cap breaches.
- Confirm the stderr banner shows `mode          : LIVE` before treating the session as armed.

## Emergency Stop

- Arm the file kill switch immediately:

```bash
python -m polytool simtrader kill
```

- Manual fallback:

```bash
touch artifacts/kill_switch.txt
```

- After the kill switch is armed, verify no new orders are being submitted and investigate before restart.

## Daily Review Checklist

- Confirm gate artifacts still match the release commit used for the session.
- Review fills, cancels, rejects, and realized PnL for the day.
- Check that daily loss cap and inventory skew stayed within limits.
- Verify Grafana and Telegram coverage matched the actual session timeline.
- Archive the session notes, commit hash, and any incidents before the next live run.
