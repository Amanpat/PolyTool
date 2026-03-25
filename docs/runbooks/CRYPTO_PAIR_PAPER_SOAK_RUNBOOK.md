# Runbook: Crypto Pair Paper Soak

**Purpose**: Run the Phase 1A crypto pair bot in paper mode for 24-48 hours and
apply a concrete promote / rerun / reject rubric without guessing.  
**Done condition**: the operator has one completed paper run, one completed
ClickHouse event batch, and a documented verdict using the rubric in
`docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`.

---

## Before You Start

This runbook assumes:

- Track 2 paper mode is used, not `--live`
- ClickHouse and Grafana are available locally
- the event sink is enabled so the post-run Grafana review can use
  `polytool.crypto_pair_events`

Important runtime note:

- the current paper runner writes Track 2 events to ClickHouse only when the run
  finishes
- during the soak itself, use the artifact directory and `runtime_events.jsonl`
  for liveness checks
- use Grafana only after the run finalizes

---

## Step 0 - Start Services

```powershell
docker compose up -d
docker compose ps
curl "http://localhost:8123/?query=SELECT%201"
```

Expected:

- Docker services are running
- ClickHouse returns `1`
- Grafana is reachable at `http://localhost:3000`

Set the ClickHouse password for the sink:

```powershell
$env:CLICKHOUSE_PASSWORD = "polytool_admin"
```

---

## Step 1 - Optional Preflight Backtest

If you already have a representative JSONL observation set, run the backtest
first. This is not the final paper-soak verdict, but it is a cheap preflight.

```powershell
python -m polytool crypto-pair-backtest --input <observations.jsonl>
```

Use the backtest only as a sanity check. The promote / rerun / reject decision
still comes from the live-market paper soak.

---

## Step 2 - Launch The 24h Paper Soak

Run the default paper shell across the full Track 2 market universe.

```powershell
python -m polytool crypto-pair-run `
  --duration-seconds 86400 `
  --sink-enabled
```

Do not add `--live`.

Do not narrow `--symbol` or `--market-duration` for sign-off unless you are
debugging a known issue.

Default operator caps and thresholds in the current runner:

- max capital per market: `10 USDC`
- max open pairs: `5`
- max open paired notional: `50 USDC`
- daily loss cap: `15 USDC`
- hard pair-cost ceiling: `0.97`
- minimum profit threshold: `0.03`
- maker rebate assumption: `20 bps`
- stale quote timeout: `15s`
- max unpaired exposure window: `120s`

Artifacts are written under:

- `artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/`

---

## Step 3 - Mid-Run Liveness Check

Use artifacts, not Grafana, while the 24h soak is still running.

Find the newest run directory:

```powershell
$runDir = Get-ChildItem artifacts/crypto_pairs/paper_runs -Recurse -Directory |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 -ExpandProperty FullName
$runDir
```

Tail runtime events if you want a liveness view:

```powershell
Get-Content "$runDir\runtime_events.jsonl" -Wait
```

Healthy mid-run signals:

- `cycle_started` and `cycle_completed` keep appearing
- `order_intent_created` appears occasionally
- no `kill_switch_tripped`
- no repeated `daily_loss_cap_reached`

Do not expect ClickHouse rows yet. The sink write happens only after finalization.

---

## Step 4 - Post-Run Artifact Audit

After the 24h process exits, inspect the run bundle first.

### 4.1 Manifest

Open:

- `run_manifest.json`

Confirm all of the following:

- `stopped_reason = "completed"`
- `has_open_unpaired_exposure_final = false`
- `sink_write_result.enabled = true`
- `sink_write_result.error` is empty
- `sink_write_result.skipped_reason` is not `write_failed`
- `sink_write_result.written_rows > 0`

### 4.2 Run Summary

Open:

- `run_summary.json`

Record these values:

- `order_intents_generated`
- `paired_exposure_count`
- `partial_exposure_count`
- `settled_pair_count`
- `gross_pnl_usdc`
- `net_pnl_usdc`

### 4.3 Runtime Event Audit

Open:

- `runtime_events.jsonl`

Explicit reject conditions:

- any `kill_switch_tripped`
- any `order_intent_blocked` with `block_reason = "daily_loss_cap_reached"`
- any sink write result with `skipped_reason = "write_failed"`

Feed-freeze audit:

1. Find every `paper_new_intents_frozen` event.
2. For each frozen window, confirm the next `order_intent_created` happens only
   after the feed has recovered to `connected_fresh` in the Track 2
   `safety_state_transition` stream.
3. If an intent is created before recovery, the soak is an automatic reject.

Useful PowerShell filter:

```powershell
Get-Content "$runDir\runtime_events.jsonl" |
  Select-String -Pattern "kill_switch_tripped|daily_loss_cap_reached|paper_new_intents_frozen|order_intent_created|sink_write_result"
```

---

## Step 5 - Post-Run Grafana Review

Only after the run finalizes, open Grafana and use the query pack in:

- `docs/features/FEATURE-crypto-pair-grafana-panels-v0.md`

Minimum required panels:

- `Paper Soak Scorecard`
- `Run Summary Funnel`
- `Maker Fill Rate Floor`
- `Partial-Leg Incidence`
- `Active Pairs`
- `Pair Cost Distribution`
- `Estimated Profit Per Completed Pair`
- `Net Profit Per Settlement`
- `Cumulative Net PnL`
- `Daily Trade Count`
- `Feed State Transition Counts`
- `Recent Feed Safety Events`

The operator should capture at least one screenshot or exported table for the
scorecard and the safety-event table before deciding.

---

## Step 6 - Apply The Rubric

Use `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md` as the authority.

### Promote

Promote to micro-live candidate only if all of the following are true:

- run length is at least `24h`
- evidence floor is met:
  - `order_intents_generated >= 30`
  - `paired_exposure_count >= 20`
  - `settled_pair_count >= 20`
- pair completion rate is `>= 0.90`
- average completed pair cost is `<= 0.965`
- estimated profit per completed pair is `>= 0.035`
- maker fill rate floor is `>= 0.95`
- partial-leg incidence is `<= 0.10`
- aggregate `net_pnl_usdc` is positive
- disconnect handling is clean
- safety violations are zero

### Rerun

Rerun for `48h` if:

- the run is operationally clean but misses the evidence floor
- any metric lands in the rerun band
- the feed enters `stale` or `disconnected`, but freeze / recovery behavior is
  still correct

48h rerun command:

```powershell
python -m polytool crypto-pair-run `
  --duration-seconds 172800 `
  --sink-enabled
```

### Reject

Reject the current paper-soak result immediately if:

- any safety violation occurs
- any metric lands in the reject band
- the run shows positive economics but unstable operations

Do not treat "profitable but unstable" as a promote candidate.

---

## Step 7 - Promote / Rerun / Reject Outcomes

### Promote

Record:

- run ID
- date range
- scorecard screenshot
- safety-event table screenshot
- short note: `PROMOTE TO MICRO LIVE CANDIDATE`

### Rerun

Record:

- run ID
- which metric missed the pass band
- whether the issue was thin sample, feed quality, or marginal economics
- planned 48h rerun window

### Reject

Record:

- run ID
- the exact reject trigger
- whether the fix is strategy, schema, or infra
- explicit note: `DO NOT PROMOTE`

---

## Operator Checklist

- services were up and ClickHouse was reachable
- paper run used `--sink-enabled`
- run finished with `stopped_reason = completed`
- sink wrote rows successfully
- evidence floor was met
- no open unpaired exposure remained at the end
- scorecard metrics were reviewed
- safety-event table was reviewed
- final verdict was written down
