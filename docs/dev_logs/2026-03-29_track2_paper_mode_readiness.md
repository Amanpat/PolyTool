# Track 2 Paper Mode Readiness Audit

**Date:** 2026-03-29
**Quick task:** quick-047
**Author:** Claude Code

## Summary

This audit verifies that the Track 2 crypto pair bot is ready for a 24-48h paper
soak after the quick-046 strategy pivot (per-leg target-bid gate). It records the
definitive launch command, corrects stale documentation paths found during the
audit, and publishes success metrics the operator needs to reach a promote/rerun/reject
verdict. All answers are derived from actual source code, not prior session notes.

---

## Findings

### Q1 — Correct base command for paper mode

**Yes.** `python -m polytool crypto-pair-run` is the correct base command.

Paper mode is the default: no `--live` flag means paper. There is no `--paper`
flag. The `--live` flag (plus `--confirm CONFIRM`) is required to enter the live
scaffold.

Source: `tools/cli/crypto_pair_run.py`, `build_parser()` and `run_crypto_pair_runner()`.

### Q2 — Exact 24h launch command

See the **Definitive 24h Launch Command** section below.

Flags confirmed from `build_parser()`:
- `--duration-hours 24` — additive with `--duration-seconds`/`--duration-minutes`.
- `--cycle-interval-seconds 30` — matches the Docker `pair-bot-paper` service
  cycle interval.
- `--reference-feed-provider coinbase` — confirmed flag; choices come from
  `REFERENCE_FEED_PROVIDER_CHOICES` in `reference_feed.py`. Binance is geo-restricted
  per quick-022/023; Coinbase confirmed working per quick-023/026.
- `--heartbeat-minutes 30` — emits operator heartbeat every 30 minutes. Confirmed
  present in `build_parser()`.
- `--auto-report` — on graceful exit, auto-runs `crypto-pair-report` and prints
  artifact locations. Confirmed in `build_parser()`.
- `--sink-enabled` — enables ClickHouse batch write at finalization. Requires
  `CLICKHOUSE_PASSWORD` env var.

### Q3 — Required env vars for paper mode

- `CLICKHOUSE_PASSWORD` — **required only when `--sink-enabled` is used.** The CLI
  does a fail-fast check: if `--sink-enabled` and the var is empty, it exits 1 with
  an explicit error message.
- No Polymarket private key, CLOB credentials, or any other credentials are required
  in paper mode.
- `GAMMA_API_BASE` — has a default in the GammaClient; not required.

Source: `tools/cli/crypto_pair_run.py`, `main()`, lines 443-449.

### Q4 — Artifact output directory

Paper artifacts land under:

```
artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/
```

This is the post-quick-036 restructure canonical path. The constant in source is:

```python
DEFAULT_PAPER_ARTIFACTS_DIR = Path("artifacts/tapes/crypto/paper_runs")
```

Source: `packages/polymarket/crypto_pairs/paper_runner.py`, line 56.

**Note:** The runbook (`CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`) and feature doc
(`FEATURE-crypto-pair-runner-v0.md`) still reference the pre-restructure path
`artifacts/crypto_pairs/paper_runs/`. Both are corrected in Task 2.

### Q5 — Kill switch

Kill switch file:

```python
DEFAULT_KILL_SWITCH_PATH = Path("artifacts/crypto_pairs/kill_switch.txt")
```

Source: `packages/polymarket/crypto_pairs/paper_runner.py`, line 57.

Create the file to trip cleanly:

```bash
touch artifacts/crypto_pairs/kill_switch.txt
```

PowerShell:

```powershell
New-Item artifacts/crypto_pairs/kill_switch.txt -Force
```

The runner checks for this file every cycle. On detection it exits with
`stopped_reason=kill_switch`.

### Q6 — What quick-046 changes for the paper soak

**Old gate (always fired):** `YES_ask + NO_ask <= target_pair_cost_threshold` where
threshold was 0.99. This gate was too permissive: the sum of asks almost always
summed to near-1.0 before CLOB data was available, so the strategy accumulated into
positions that had no real edge.

**New gate (quick-046):** Each leg checked individually:
- `target_bid = 0.5 - edge_buffer_per_leg` (default: 0.04, so `target_bid = 0.46`).
- A leg meets the target when `ask_price <= target_bid`.
- At least one leg must meet the target; legs that do not are excluded.
- If no leg meets the target, SKIP.
- If one leg is already accumulated (partial pair), focus on the missing leg.

The gate is in `packages/polymarket/crypto_pairs/accumulation_engine.py`, documented
in the entry-rule hierarchy at the top of the module.

New config fields in `CryptoPairPaperModeConfig` (from `config_models.py`):
- `edge_buffer_per_leg: Decimal = Decimal("0.04")` — buffer subtracted from 0.5
- `max_pair_completion_pct: Decimal = Decimal("0.80")` — partial-pair completion cap
- `min_projected_profit: Decimal = Decimal("0.03")` — minimum projected profit gate

**Implication for paper soak:** The bot now looks for markets where YES or NO is
trading at or below 0.46 — reasonable for crypto 5m up/down markets near 50/50.
Near-launch markets may show asks near 0.50; once uncertainty resolves in one
direction an ask can drop below 0.46 and the strategy accumulates.

### Q7 — Duration flags for multi-hour soaks

Yes: `--duration-hours 24` or `--duration-hours 48`. Can be combined additively with
`--duration-seconds` and `--duration-minutes`. The parser resolves total duration with
`resolve_duration_seconds()`.

Source: `tools/cli/crypto_pair_run.py`, lines 66-78 and 202-215.

### Q8 — Grafana data source

`--sink-enabled` writes events to `polytool.crypto_pair_events` in ClickHouse.

Two flush modes:
- **batch (default):** All events are written at run finalization. Grafana data is
  visible only after the run ends.
- **streaming (--sink-streaming):** Per-event writes during the run loop. Grafana
  data is visible in near-real-time throughout the soak.

For a 24h soak with Grafana visibility during the run, `--sink-streaming` is worth
considering (see Open Items).

### Q9 — Files in the run directory

Per `run_manifest.json` artifact contract:
- `run_manifest.json` — metadata, stopped_reason, sink_write_result, artifact paths
- `run_summary.json` — metrics: intents, paired/partial/settled counts, PnL
- `runtime_events.jsonl` — per-cycle event stream for mid-run liveness
- `config_snapshot.json` — settings used for this run
- `observations.jsonl` — per-opportunity observation log
- `order_intents.jsonl` — per-intent log
- `fills.jsonl`, `exposures.jsonl`, `settlements.jsonl` — ledger records
- `market_rollups.jsonl` — per-market aggregate

### Q10 — Blockers as of 2026-03-29

- **Market availability:** BTC/ETH/SOL 5m markets confirmed active 2026-03-29 per
  quick-045 capture run.
- **Code blockers:** None. quick-046 strategy pivot ships cleanly with 2755 tests
  passing.
- **Stale docs:** Two files have the pre-restructure artifact path (corrected in
  Task 2). quick-046 strategy pivot not yet documented in `docs/`.

---

## Definitive 24h Launch Command

```bash
# Step 0: Ensure ClickHouse + Grafana are running (needed for --sink-enabled)
docker compose up -d
docker compose ps
curl "http://localhost:8123/?query=SELECT%201"

# Step 1: Set ClickHouse password for the sink
export CLICKHOUSE_PASSWORD="polytool_admin"   # replace with your actual value

# Step 2: Launch 24h paper soak
python -m polytool crypto-pair-run \
  --duration-hours 24 \
  --cycle-interval-seconds 30 \
  --reference-feed-provider coinbase \
  --heartbeat-minutes 30 \
  --auto-report \
  --sink-enabled

# Trip kill switch to stop early (graceful exit, triggers auto-report)
touch artifacts/crypto_pairs/kill_switch.txt
```

PowerShell equivalents:

```powershell
# Step 1
$env:CLICKHOUSE_PASSWORD = "polytool_admin"

# Step 2
python -m polytool crypto-pair-run `
  --duration-hours 24 `
  --cycle-interval-seconds 30 `
  --reference-feed-provider coinbase `
  --heartbeat-minutes 30 `
  --auto-report `
  --sink-enabled

# Kill switch
New-Item artifacts/crypto_pairs/kill_switch.txt -Force
```

48h rerun command:

```powershell
python -m polytool crypto-pair-run `
  --duration-hours 48 `
  --cycle-interval-seconds 30 `
  --reference-feed-provider coinbase `
  --heartbeat-minutes 30 `
  --auto-report `
  --sink-enabled
```

---

## Success Metrics (24-48h Verdict)

Source: `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`.

### PROMOTE — all of the following must be true

| Metric | Pass threshold |
|--------|---------------|
| `stopped_reason` | `completed` |
| Run length | >= 24h |
| `order_intents_generated` | >= 30 |
| `paired_exposure_count` | >= 20 |
| `settled_pair_count` | >= 20 |
| Pair completion rate | >= 0.90 |
| Avg completed pair cost | <= 0.965 |
| Estimated profit per completed pair | >= 0.035 |
| Maker fill rate | >= 0.95 |
| Partial-leg incidence | <= 0.10 |
| `net_pnl_usdc` | > 0 |
| Safety violations | 0 |

### RERUN (48h) — if any of the following

- Run is operationally clean but evidence floor is thin (intents/pairs below
  30/20/20 minimums).
- Any metric lands in the "rerun band" per rubric spec.
- Feed entered `stale` or `disconnected` but freeze/recovery behavior was correct.

### REJECT — if any of the following

- Any safety violation occurs.
- Any metric lands in the "reject band" per rubric spec.
- Positive economics but unstable operations (do not promote).

---

## Stale Docs Identified

1. **`docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`**
   - Stale path: `artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/`
   - Correct path: `artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/`
   - Missing flags: `--reference-feed-provider coinbase`, `--heartbeat-minutes`,
     `--auto-report`.
   - Missing section: quick-046 strategy gate documentation.
   - Missing section: kill switch procedure.

2. **`docs/features/FEATURE-crypto-pair-runner-v0.md`**
   - Stale path: `artifacts/crypto_pairs/paper_runs/<YYYY-MM-DD>/<run_id>/`
   - Correct path: `artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/`

3. **`docs/CURRENT_STATE.md` Track 2 section**
   - Still shows the old launch command without `--reference-feed-provider coinbase`.
   - Does not reflect quick-046 strategy pivot.
   - Does not explicitly state paper soak readiness status.

All three are corrected in Task 2.

---

## Open Items

1. **`--sink-streaming` for 24h+ soaks:** The default batch mode means Grafana shows
   no data until the soak completes. For a 24h soak, `--sink-streaming` provides
   live Grafana visibility every cycle. Operator should evaluate whether live
   dashboard feedback is worth the minor per-event write overhead. Recommendation:
   use `--sink-streaming` for soaks where mid-run Grafana review is wanted.

2. **Grafana dashboard panel updates for quick-046 metrics:** The provisioned
   dashboard (`polytool_crypto_pair_paper_soak.json`) was designed before
   quick-046. New metric names `edge_buffer_per_leg`, `max_pair_completion_pct`,
   and `min_projected_profit` may not have dedicated panels. Operator should review
   the Grafana dashboard after the first soak and add panels if needed.
