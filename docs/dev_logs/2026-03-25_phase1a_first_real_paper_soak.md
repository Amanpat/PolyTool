# 2026-03-25 Phase 1A First Real Paper Soak — Execution Blocked by Binance 451

**Work unit**: Phase 1A / Track 2 smoke-soak run, post-run artifact review, report generation, blocker documentation.
**Author**: operator + Claude Code
**Status**: CLOSED — blocker recorded, full soak intentionally not run

---

## Summary

The first real Track 2 crypto pair paper run completed cleanly as a smoke soak on
2026-03-25. The run executed 240 cycles over approximately 24.4 minutes and
stopped with `stopped_reason = completed`. However, Binance returned HTTP 451
(Unavailable For Legal Reasons / geo-restriction) on every WebSocket connection
attempt. The reference feed never delivered data, so the runner observed
zero markets, generated zero intents, and produced no meaningful economic activity.

The rubric verdict produced by `crypto-pair-report` is:

```
verdict: RERUN PAPER SOAK
rubric_pass: no
safety_count: 0
```

The 24-hour soak was intentionally not run. It would have produced an
informationally identical outcome: the geo-restriction blocks the only configured
reference feed (Binance), so no opportunity evaluation can occur regardless of
duration. Running 24h of zero-data cycles adds no evidence and wastes 24 hours.

---

## Smoke Soak Command

The smoke soak was launched with a 1200-second (20-minute) duration to confirm
end-to-end flow before committing to a full 24h soak:

```powershell
python -m polytool crypto-pair-run --duration-seconds 1200
```

The sink was not enabled for the smoke soak (`--sink-enabled` was omitted).

---

## Artifact Path

```
artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/
```

Files produced:

| File | Notes |
|------|-------|
| `config_snapshot.json` | Runner config at launch time |
| `run_manifest.json` | Full run metadata, counts, sink result |
| `run_summary.json` | Economic summary (all zeros) |
| `runtime_events.jsonl` | 728 structured events |
| `paper_soak_summary.json` | Report output from `crypto-pair-report` |
| `paper_soak_summary.md` | Human-readable report output |

Missing artifact files (expected when no activity occurs):

- `observations.jsonl` — no markets observed
- `order_intents.jsonl` — no intents generated
- `fills.jsonl` — no fills
- `exposures.jsonl` — no exposures
- `settlements.jsonl` — no settlements
- `market_rollups.jsonl` — no rollups

---

## Blocker Details

### Root Cause

Binance blocks WebSocket connections from certain geographic regions (or
cloud/VPN egress IPs) with HTTP 451 — "Unavailable For Legal Reasons." This
is a hard geo-restriction, not a transient network error, not a rate limit,
and not a credentials problem.

### How It Manifests

The `BinanceFeed._ws_loop()` background thread connects to:

```
wss://stream.binance.com:9443/stream?streams=btcusdt@aggTrade/ethusdt@aggTrade/solusdt@aggTrade
```

When Binance returns 451, the `_on_error` handler fires and sets the connection
state to `DISCONNECTED`. The reconnect loop immediately retries with a 2-second
sleep, receives 451 again, and the cycle repeats. Because `_on_error` is a
background thread callback, the 451 rejection is emitted as a Python logging
error (`_log.error(...)`) — it does not produce a structured `runtime_event` in
`runtime_events.jsonl`. This means the artifact file alone does not show the 451;
the evidence of the block lives in the runner's stderr log output.

### Artifact Confirmation

From `run_manifest.json`:

```json
"counts": {
  "exposures": 0,
  "fills": 0,
  "market_rollups": 0,
  "observations": 0,
  "order_intents": 0,
  "runtime_events": 728,
  "settlements": 0
},
"run_summary": {
  "markets_seen": 0,
  "opportunities_observed": 0,
  "order_intents_generated": 0,
  "paired_exposure_count": 0,
  "partial_exposure_count": 0,
  "settled_pair_count": 0
}
```

Runtime event distribution (728 total, all structural / lifecycle):

| Event type | Count |
|---|---|
| `kill_switch_checked` | 240 |
| `cycle_started` | 240 |
| `cycle_completed` | 240 |
| `runner_heartbeat` | 4 |
| `runner_started` | 1 |
| `reference_feed_connect_called` | 1 |
| `reference_feed_disconnect_called` | 1 |
| `sink_write_result` | 1 |

No `safety_state_transition` events appear because the feed's safety state
machine never received a message to transition on. The runner itself operated
correctly — kill switch checked every cycle, no daily loss cap hit, no open
unpaired exposure at end — the feed simply never fed data.

---

## Report Command and Verdict

```bash
python -m polytool crypto-pair-report --run artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/
```

Output:

```
[crypto-pair-report] run_id        : 603e0ef17ff2
[crypto-pair-report] verdict       : RERUN PAPER SOAK
[crypto-pair-report] rubric_pass   : no
[crypto-pair-report] safety_count  : 0
[crypto-pair-report] summary_json  : artifacts\crypto_pairs\paper_runs\2026-03-25\603e0ef17ff2\paper_soak_summary.json
[crypto-pair-report] summary_md    : artifacts\crypto_pairs\paper_runs\2026-03-25\603e0ef17ff2\paper_soak_summary.md
```

The rubric verdict of RERUN is accurate under the spec — the evidence floor was
not met (`order_intents_generated=0`, `paired_exposure_count=0`,
`settled_pair_count=0`, duration=0.41h vs 24h minimum). No safety violations
occurred. No metric landed in the reject band because no metric had data.

However, the correct operator interpretation of this specific RERUN verdict is:

> **RERUN is blocked by geo-restriction, not by thin sample or marginal
> economics. The issue is feed access, not strategy performance or
> run duration. A standard 48h rerun will produce identical zero-data output
> until the feed access problem is resolved.**

---

## Why the 24h Soak Was Not Run

A 24-hour soak under current conditions would have produced:

- 240 cycles/hour × 24 hours = 5,760 cycles of zero activity
- identical `markets_seen=0`, `opportunities_observed=0` outcome
- no additional evidence about strategy economics, pair cost, fill rate, or PnL
- no Grafana signal (ClickHouse sink was disabled; even with sink enabled,
  zero events would be emitted)

Running it would waste 24 hours and produce an artifact that is
informationally identical to the smoke soak, just with a higher cycle count.
This is not a "thin sample" problem that more time fixes; it is a hard
external dependency blocking all data inflow.

The decision to stop here is consistent with the "simple path first" and
"first dollar before perfect system" principles in CLAUDE.md. Spending 24h
re-confirming a known blocker is not simple and does not advance the first
dollar.

---

## Recommended Next Step: Resolve Feed Access

The Binance reference feed is the only configured price feed. Until feed access
is restored, Phase 1A paper soak cannot produce meaningful results.

Three options (in rough order of operator preference):

### Option A — Coinbase Advanced Trade WebSocket (preferred)

Add a Coinbase fallback feed to `packages/polymarket/crypto_pairs/reference_feed.py`.
Coinbase Advanced Trade has no geographic restriction comparable to Binance's
451 behavior and provides BTC-USD, ETH-USD, SOL-USD tick data. The
`reference_feed.py` architecture already reserves the `feed_source` field on
`ReferencePriceSnapshot` for a future `"coinbase"` value.

Scope: implement `CoinbaseFeed` as a `_ws_loop` variant using the Coinbase
Advanced Trade WebSocket (`wss://advanced-trade-ws.coinbase.com/`),
add a fallback chain in the runner config so Coinbase is used when
Binance is unavailable, update the config snapshot to record which feed
sourced data.

This is the cleanest long-term fix and avoids infrastructure dependency on
any specific machine's geography.

### Option B — Run from a Canadian or US-accessible machine

If a machine with unrestricted Binance access is available (e.g., a VPS in
a Binance-unrestricted jurisdiction), the current code works as-is. The runner
does not need code changes; it just needs a network path where Binance does not
return 451.

This is the fastest option if such a machine is on hand.

### Option C — VPN or egress routing

Route the runner's traffic through a VPN endpoint that Binance does not
geo-restrict. This is operationally fragile for a 24h soak (VPN disconnects,
split tunneling issues) and is not recommended as the primary path.

---

## Run Configuration Reference

From `config_snapshot.json`:

- mode: `paper`
- duration_seconds: `1200` (smoke soak)
- cycle_interval_seconds: `5`
- symbols: `BTC`, `ETH`, `SOL`
- duration_filters: `5`, `15` (minutes)
- max_capital_per_market_usdc: `10`
- max_open_pairs: `5`
- max_open_paired_notional_usdc: `50`
- daily_loss_cap_usdc: `15`
- target_pair_cost_threshold: `0.97`
- min_profit_threshold_usdc: `0.03`
- maker_rebate_bps: `20`
- stale_quote_timeout_seconds: `15`
- max_unpaired_exposure_seconds: `120`
- kill_switch_path: `artifacts/crypto_pairs/kill_switch.txt`
- sink: disabled (smoke soak only)

---

## Open Questions / Deferred

- Should `crypto-pair-run` emit a structured `reference_feed_error` runtime
  event when the feed enters the `DISCONNECTED` state due to a non-transient
  error (e.g., 451)? Currently the error is only in Python logging, not in
  `runtime_events.jsonl`. This would help future automation diagnose the
  blocker without needing log capture. Deferred — no code changes in scope here.
- Should the runner emit a `cycle_skipped_no_feed_data` event after N
  consecutive zero-observation cycles to make the dead-feed pattern visible in
  the artifact? Deferred.
- Coinbase fallback feed implementation is the priority follow-on task for
  this track.

---

## Files Reviewed

- `artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/run_manifest.json`
- `artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/run_summary.json`
- `artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/runtime_events.jsonl`
- `artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/config_snapshot.json`
- `artifacts/crypto_pairs/paper_runs/2026-03-25/603e0ef17ff2/paper_soak_summary.json` (generated this session)
- `packages/polymarket/crypto_pairs/reference_feed.py` (architecture review)
- `docs/runbooks/CRYPTO_PAIR_PAPER_SOAK_RUNBOOK.md`
- `docs/specs/SPEC-crypto-pair-paper-soak-rubric-v0.md`
- `tools/cli/crypto_pair_report.py`
