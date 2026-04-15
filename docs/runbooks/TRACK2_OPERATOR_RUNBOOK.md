# Track 2 Operator Runbook: Crypto Pair Bot

**Track**: Track 2 / Phase 1A (STANDALONE)
**Status**: Active revenue path as of 2026-04-15 (Gate 2 decision, Option 3 approved)
**Covers**: Preflight, market availability, scan, 24h paper soak, safety audit, stop conditions

---

## 1. What Track 2 Is (and Is Not)

**Track 2 is the crypto pair bot.** Phase 1A. STANDALONE per `CLAUDE.md`.

- Strategy: directional momentum entries on BTC/ETH/SOL 5m up/down binary markets on Polymarket.
- Per-leg entry gate: ask <= 0.46 per leg (target_bid = 0.5 - 0.04 buffer). Both legs meeting
  the target enables accumulation. This is the quick-046 pivot -- not sum-cost accumulation.
- Paper mode is the default. No `--live` flag used until a paper soak promotes.

**Track 2 was approved as the active revenue path per Gate 2 decision (2026-04-15, Option 3).**

What this does NOT mean:

- It does NOT close Gate 2. Gate 2 remains FAILED (7/50 = 14%, threshold 70%).
- Gate 2 is deprioritized, not abandoned. No gate thresholds, benchmark manifests, or policy
  documents were changed by this decision.
- Track 1 (market maker) and Track 3 (sports directional) continue at background priority.
- Track 2 promotion to live capital requires its own paper soak verdict -- Gate 2 status is
  irrelevant to that decision.

Reference: `docs/dev_logs/2026-04-15_gate2_decision_packet.md`

---

## 2. Prerequisites / Environment Checks

Run this preflight before any Track 2 session.

### 2.1 CLI loads

```bash
python -m polytool --help
```

Expected: no import errors, subcommand list includes `crypto-pair-watch`, `crypto-pair-scan`,
`crypto-pair-run`.

### 2.2 Docker services

```bash
docker compose ps
```

Expected: all services healthy. ClickHouse and Grafana should be listed as running.

```bash
curl "http://localhost:8123/?query=SELECT%201"
```

Expected: response `1`. If this fails, run `docker compose up -d` first.

### 2.3 ClickHouse password

The runner requires `CLICKHOUSE_PASSWORD` when `--sink-enabled` is used. Set it before launch.

Bash:
```bash
export CLICKHOUSE_PASSWORD="your-password-from-.env"
```

PowerShell:
```powershell
$env:CLICKHOUSE_PASSWORD = "your-password-from-.env"
```

Never hardcode the password. Never leave it unset and proceed with `--sink-enabled`. Fail-fast
rule: the runner will exit if the variable is missing.

### 2.4 Credentials NOT needed for paper mode

- No Polymarket private keys
- No CLOB credentials
- No Binance API keys

Reference price feed (Coinbase) requires outbound HTTPS only.

### 2.5 Reference feed note

Use `--reference-feed-provider coinbase`. Binance is geo-restricted from many locations
(confirmed quick-022/023). Coinbase is the reliable fallback.

---

## 3. Step 1: Check Market Availability

```bash
python -m polytool crypto-pair-watch
```

This is a one-shot check. It queries Gamma for active BTC/ETH/SOL 5m/15m binary markets and
prints eligible markets. No orders are submitted. No credentials required.

As of 2026-04-14: 12 active 5m markets confirmed (BTC=4, ETH=4, SOL=4).

**Flag notes (v0 behavior):**
- `--symbol` and `--duration` are accepted but do not filter the Gamma query yet (wired in v1).
  All eligible symbols and durations are always returned.
- Artifact written to `artifacts/crypto_pairs/watch/` by default.

**If no markets found:** Crypto 5m markets rotate daily. Use watch mode:

```bash
python -m polytool crypto-pair-watch --watch --timeout 7200
```

Poll interval defaults to 60 seconds. Exit 0 when markets appear; exit 1 on timeout.

---

## 4. Step 2: Dry-Run Scan

```bash
python -m polytool crypto-pair-scan
```

Reads the current market universe, computes edge estimates, and prints a summary table.
No orders submitted. No credentials required.

Review output: look for markets where the ask price is at or below 0.46 on both legs.
Zero rows with favorable asks means the engine will generate zero intents. If this happens,
wait for market rotation and re-run the check before launching a paper soak.

Optional filters:
```bash
python -m polytool crypto-pair-scan --symbol BTC --duration 5
```

Artifact written to `artifacts/crypto_pairs/scan/` by default.

---

## 5. Step 3: Paper Soak (24h)

### 5.1 Launch command

Bash:
```bash
python -m polytool crypto-pair-run \
  --duration-hours 24 \
  --cycle-interval-seconds 30 \
  --reference-feed-provider coinbase \
  --heartbeat-minutes 30 \
  --auto-report \
  --sink-enabled
```

PowerShell:
```powershell
python -m polytool crypto-pair-run `
  --duration-hours 24 `
  --cycle-interval-seconds 30 `
  --reference-feed-provider coinbase `
  --heartbeat-minutes 30 `
  --auto-report `
  --sink-enabled
```

**Do not add `--live`.** Paper mode is the default. Live scaffold is behind `--live --confirm CONFIRM`.

### 5.2 Flag explanations

| Flag | Meaning |
|------|---------|
| `--duration-hours 24` | Run for 24 hours. Additive with `--duration-minutes` and `--duration-seconds`. |
| `--cycle-interval-seconds 30` | Pause 30 seconds between strategy cycles. |
| `--reference-feed-provider coinbase` | Use Coinbase price feed. Binance is geo-restricted. |
| `--heartbeat-minutes 30` | Print operator status summary every 30 minutes. |
| `--auto-report` | On clean exit, auto-run `crypto-pair-report` and print artifact locations. |
| `--sink-enabled` | Write events to ClickHouse at run end. Requires `CLICKHOUSE_PASSWORD`. |
| `--sink-streaming` | Optional: write events incrementally for live Grafana visibility during the soak. Add if you want Grafana panels live during the run. |

### 5.3 Artifact location

```
artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/
```

Key files:
- `run_manifest.json` -- top-level status: stopped_reason, sink result, exposure flags
- `run_summary.json` -- counts: intents, pairs, settled, PnL
- `runtime_events.jsonl` -- full event stream with cycle and safety events
- `order_intents.jsonl` -- per-intent records
- `observations.jsonl` -- raw market observations

### 5.4 Mid-run monitoring

Find the run directory (bash):
```bash
ls -td artifacts/tapes/crypto/paper_runs/*/* | head -1
```

Tail live events:
```bash
tail -f artifacts/tapes/crypto/paper_runs/<YYYY-MM-DD>/<run_id>/runtime_events.jsonl
```

Healthy signals: `cycle_started` and `cycle_completed` appearing continuously,
`order_intent_created` occasionally, no `kill_switch_tripped`, no `daily_loss_cap_reached`.

For Grafana during soak: add `--sink-streaming` to the launch command.

For detailed verdict rubric after run: `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`

---

## 6. Safety Checklist (operator must verify after every run)

Check each item after the run exits. All must pass for a clean result.

- [ ] `run_manifest.json: stopped_reason = "completed"` -- not crash, not kill_switch
- [ ] `run_manifest.json: has_open_unpaired_exposure_final = false` -- no legs left open
- [ ] `run_manifest.json: sink_write_result.written_rows > 0` -- events written to ClickHouse
- [ ] `run_manifest.json: sink_write_result.error` is empty or absent
- [ ] `runtime_events.jsonl`: no `kill_switch_tripped` events
- [ ] `runtime_events.jsonl`: no `order_intent_blocked` with `block_reason = daily_loss_cap_reached`
- [ ] Feed freeze audit: for every `paper_new_intents_frozen` event, confirm the next
      `order_intent_created` occurs only after `safety_state_transition` shows `connected_fresh`.
      If an intent fires during a freeze window, this is an automatic REJECT.
- [ ] `run_summary.json: net_pnl_usdc > 0` -- net PnL is positive
- [ ] Evidence floor: `order_intents_generated >= 30`, `paired_exposure_count >= 20`,
      `settled_pair_count >= 20`

Use this PowerShell filter to check safety events:
```powershell
Get-Content "artifacts\tapes\crypto\paper_runs\<date>\<run_id>\runtime_events.jsonl" |
  Select-String "kill_switch_tripped|daily_loss_cap_reached|paper_new_intents_frozen|order_intent_created|sink_write_result"
```

---

## 7. Stop Conditions / Kill Switch

### When to stop early

- Any safety checklist violation is detected mid-run
- Daily loss cap (`daily_loss_cap_reached`) fires repeatedly
- Reference feed is permanently disconnected (not a transient blip)
- System error makes artifact writes unreliable

### How to stop cleanly

Write a truthy value to the kill switch file. The runner checks the file every cycle
and exits with `stopped_reason = kill_switch`.

Bash:
```bash
printf '1\n' > artifacts/crypto_pairs/kill_switch.txt
```

PowerShell:
```powershell
Set-Content -Path artifacts/crypto_pairs/kill_switch.txt -Value 1
```

**Accepted truthy values:** `1`, `true`, `yes`, `on`. An empty file alone does NOT trip
the kill switch.

Ctrl+C also works but `--auto-report` may not fire, so artifact finalization may be incomplete.

### Resetting the kill switch before the next run

Delete the file or overwrite it with a falsy value:
```bash
rm artifacts/crypto_pairs/kill_switch.txt
```

---

## 8. What Success Looks Like

A successful 24h paper soak must pass all safety checklist items and meet the promote band:

| Metric | Pass Band |
|--------|-----------|
| Run length | >= 24h |
| `order_intents_generated` | >= 30 |
| `paired_exposure_count` | >= 20 |
| `settled_pair_count` | >= 20 |
| Pair completion rate | >= 0.90 |
| Average completed pair cost | <= 0.965 |
| Estimated profit per completed pair | >= 0.035 |
| Maker fill rate floor | >= 0.95 |
| Partial-leg incidence | <= 0.10 |
| `net_pnl_usdc` | > 0 |
| Safety violations | 0 |

**Next step on pass:** promote to micro-live candidate. Full rubric with rerun and reject
bands: `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`

**What a passing paper soak does NOT authorize:**
- Live capital deployment (requires separate live-scaffold validation)
- EU VPS decision (oracle mismatch concern unresolved)
- SOL market inclusion (3 of 10 crypto tapes showed heavy adverse selection -- pending review)

---

## 9. Troubleshooting

**"No eligible markets found"**
Crypto 5m markets rotate daily. Run: `python -m polytool crypto-pair-watch --watch --timeout 7200`
Markets typically appear at the top of each UTC hour.

**"ClickHouse connection refused"**
Run: `docker compose up -d` then verify: `curl "http://localhost:8123/?query=SELECT%201"`

**"CLICKHOUSE_PASSWORD not set or empty"**
Export from `.env` before launching. Never hardcode. The runner will exit with an error.

**"Binance feed error" or feed connection failures**
Use `--reference-feed-provider coinbase`. Binance is geo-restricted from many regions.

**"Zero intents generated"**
Markets exist but asks are above 0.46 target. Wait for market rotation and re-check with
`crypto-pair-scan`. Do not lower the target-bid gate.

**"Feed freeze events in runtime log"**
Check whether intents were created during the freeze window. If yes: REJECT (automatic).
If no: review the freeze duration -- short freezes with clean recovery are acceptable.

**"Run stopped early (stopped_reason != completed)"**
Check: (1) kill switch file contents, (2) `daily_loss_cap_reached` in runtime log,
(3) any `feed_timeout` or connection error events.

**"sink_write_result: written_rows = 0 or skipped_reason = write_failed"**
Verify ClickHouse is running, password is set, and the `polytool.crypto_pair_events`
table exists. Run: `curl "http://localhost:8123/?query=SHOW%20TABLES%20FROM%20polytool"`

---

## 10. Reference Links

| Document | Purpose |
|----------|---------|
| `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md` | Full step-by-step paper soak walkthrough with Grafana review steps |
| `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md` | Authoritative promote / rerun / reject rubric with metric bands |
| `docs/dev_logs/2026-04-15_gate2_decision_packet.md` | Gate 2 decision packet -- three options, Option 3 rationale |
| `docs/dev_logs/2026-03-29_track2_paper_mode_readiness.md` | quick-046 strategy pivot (target-bid per leg, not sum-cost) |
| `docs/dev_logs/2026-04-14_gate2_fill_diagnosis.md` | Gate 2 failure anatomy and root cause analysis |
| `docs/features/FEATURE-crypto-pair-*.md` | Feature implementation docs (pair engine, feed, sink, Grafana panels) |
| `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` | Gold tape capture runbook (for Track 1 Gate 2 re-entry path) |

---

*This runbook covers the paper soak path only. Live deployment steps (EU VPS,
oracle mismatch validation, micro-live scaffold) are deferred pending a successful
paper soak promote verdict.*
