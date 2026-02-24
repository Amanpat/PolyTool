# SimTrader — User Guide

**Realism is the top rule.** If SimTrader says a strategy is profitable but it fails live, SimTrader is wrong and that is a blocker, not an asterisk.

---

## 1. One command

```bash
python -m polytool simtrader quickrun --duration 900
```

That's it. `quickrun` does everything automatically:

1. Fetches active Polymarket markets from Gamma
2. Finds the first live binary market with valid orderbooks on both legs
3. Records a 15-minute tape of the YES and NO tokens over WebSocket
4. Runs `binary_complement_arb` with conservative defaults (200 bps fees, bid-side marking)
5. Prints a summary and the exact reproduce command

**Expected output (abridged):**

```
[quickrun] market   : will-candidate-win-2026
[quickrun] YES      : abc123...  (Yes)
[quickrun] NO       : def456...  (No)
[quickrun] tape dir : artifacts/simtrader/tapes/...

QuickRun complete
  Market     : will-candidate-win-2026
  YES token  : abc123...
  NO token   : def456...
  Tape stats : 4820 parsed events  (YES snapshot=True  NO snapshot=True)
  Decisions  : 12   Orders: 24   Fills: 18
  Net profit : 1.43
  Run quality: ok
  Tape dir   : artifacts/simtrader/tapes/<tape-id>/
  Run dir    : artifacts/simtrader/runs/<run-id>/

Both `tapes/<tape-id>/meta.json` and `runs/<run-id>/run_manifest.json` include a
`quickrun_context` field with the selected slug, token IDs, selection mode, and
book-validation results for auditability.

Reproduce:
  python -m polytool simtrader quickrun --market will-candidate-win-2026 --duration 900
```

**Prerequisites:** `pip install 'websocket-client>=1.6'`

---

## 2. Common flags

### Target a specific market

```bash
# bash
python -m polytool simtrader quickrun \
  --market will-trump-win-2026 \
  --duration 900

# PowerShell
python -m polytool simtrader quickrun `
  --market will-trump-win-2026 `
  --duration 900
```

Find the slug from the Polymarket URL:
`https://polymarket.com/event/<slug>` — the slug is everything after `/event/`.

### Validate before recording (dry-run)

Check that a market has valid orderbooks without writing any tape:

```bash
python -m polytool simtrader quickrun --market some-slug --dry-run
```

Exits with code 0 if both books are live, non-zero otherwise. Safe to run anytime.

### Adjust portfolio parameters

```bash
python -m polytool simtrader quickrun \
  --market some-slug \
  --duration 900 \
  --starting-cash 2000 \
  --fee-rate-bps 250 \
  --mark-method midpoint
```

### Override strategy parameters

Pass overrides as a JSON string or a file. The defaults are merged first; your overrides win.

```bash
# Inline JSON (bash — single quotes safe)
python -m polytool simtrader quickrun \
  --market some-slug \
  --strategy-config-json '{"buffer": 0.02, "max_size": 25}'

# JSON file (PowerShell — BOM is handled automatically)
python -m polytool simtrader quickrun `
  --market some-slug `
  --strategy-config-path .\arb_overrides.json
```

`arb_overrides.json` example:

```json
{
  "buffer": 0.02,
  "max_size": 25,
  "unwind_wait_ticks": 10
}
```

### All quickrun flags

| Flag | Default | Description |
|------|---------|-------------|
| `--market SLUG` | auto | Polymarket slug; omit to auto-pick the first valid binary market |
| `--duration N` | 30 | Recording duration in seconds (use 600–1800 for meaningful results) |
| `--starting-cash X` | 1000 | Starting USDC balance |
| `--fee-rate-bps N` | 200 | Taker fee in basis points (conservative default) |
| `--mark-method` | bid | `bid` (conservative) or `midpoint` for unrealized PnL |
| `--cancel-latency-ticks N` | 0 | Cancel latency knob |
| `--allow-empty-book` | false | Accept markets whose books are currently empty |
| `--dry-run` | false | Resolve + validate without recording |
| `--strategy-config-json STR` | — | Inline JSON overrides for `binary_complement_arb` |
| `--strategy-config-path PATH` | — | JSON file with overrides (UTF-8 BOM accepted) |
| `--max-candidates N` | 20 | Markets to scan when auto-picking |

---

## 3. Advanced: manual workflow

Use the manual steps when you want to **reuse a recorded tape**, run different strategies, or produce a **scenario sweep** for robustness analysis.

### 3.1 Record a tape

```bash
# bash — record YES and NO tokens for 10 minutes
python -m polytool simtrader record \
  --asset-id <YES_TOKEN_ID> \
  --asset-id <NO_TOKEN_ID> \
  --duration 600

# PowerShell
python -m polytool simtrader record `
  --asset-id $YES `
  --asset-id $NO `
  --duration 600
```

Output: `artifacts/simtrader/tapes/<timestamp>_<prefix>/`
Files: `raw_ws.jsonl`, `events.jsonl`, `meta.json`

**How to find token IDs** (PowerShell):

```powershell
$slug = "your-market-slug"
$m = Invoke-RestMethod "https://gamma-api.polymarket.com/markets?slug=$slug"
$ids = $m[0].clobTokenIds | ConvertFrom-Json
$outs = $m[0].outcomes | ConvertFrom-Json
"YES: $($ids[0])  ($($outs[0]))"
"NO:  $($ids[1])  ($($outs[1]))"
```

### 3.2 Inspect tape coverage

Always check coverage before running arb — a tape with no book snapshot for an asset will produce zero decisions:

```bash
python -m polytool simtrader tape-info \
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl
```

Look for:

- Both asset IDs present under `asset_ids`
- `snapshot_by_asset` showing `true` for both tokens
- `event_type_counts` includes `book` and `price_change`
- `warnings` is empty (or only cosmetic)

### 3.3 Run binary_complement_arb against a tape

```bash
# bash
python -m polytool simtrader run \
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl \
  --strategy binary_complement_arb \
  --strategy-config '{"yes_asset_id":"<YES>","no_asset_id":"<NO>","buffer":0.01,"max_size":50}' \
  --asset-id <YES_TOKEN_ID> \
  --starting-cash 1000 \
  --fee-rate-bps 200 \
  --mark-method bid
```

```powershell
# PowerShell — use a config file to avoid quoting hell
python -m polytool simtrader run `
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl `
  --strategy binary_complement_arb `
  --strategy-config-path .\arb_strategy.json `
  --asset-id $YES `
  --starting-cash 1000 `
  --fee-rate-bps 200 `
  --mark-method bid
```

`arb_strategy.json`:

```json
{
  "yes_asset_id": "<YES_TOKEN_ID>",
  "no_asset_id":  "<NO_TOKEN_ID>",
  "buffer": 0.01,
  "max_size": 50,
  "legging_policy": "wait_N_then_unwind",
  "unwind_wait_ticks": 5,
  "enable_merge_full_set": true
}
```

### 3.4 Scenario sweep (robustness distribution)

Sweeps run the same tape+strategy across multiple parameter overrides and produce best/median/worst statistics. Use sweeps before promoting any strategy claim.

```powershell
# PowerShell — create sweep config
$sc = @'
{
  "scenarios": [
    {"name": "base",        "overrides": {}},
    {"name": "fees_high",   "overrides": {"fee_rate_bps": 300}},
    {"name": "midmark",     "overrides": {"mark_method": "midpoint"}},
    {"name": "cancel_slow", "overrides": {"cancel_latency_ticks": 5}}
  ]
}
'@
$sc | Out-File -Encoding utf8 sweep.json

python -m polytool simtrader sweep `
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl `
  --strategy binary_complement_arb `
  --strategy-config-path .\arb_strategy.json `
  --starting-cash 1000 `
  --sweep-config (Get-Content .\sweep.json -Raw)
```

```bash
# bash
python -m polytool simtrader sweep \
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl \
  --strategy binary_complement_arb \
  --strategy-config-path ./arb_strategy.json \
  --starting-cash 1000 \
  --sweep-config "$(cat sweep.json)"
```

Sweep output: `artifacts/simtrader/sweeps/<sweep-id>/`

---

## 4. Artifact reference

### Per-run artifacts (`artifacts/simtrader/runs/<run-id>/`)

| File | What it contains |
|------|-----------------|
| `summary.json` | Headline metrics: `net_profit`, `realized_pnl`, `unrealized_pnl`, `total_fees` |
| `decisions.jsonl` | One record per strategy decision (why it acted or didn't) |
| `orders.jsonl` | Order lifecycle events (submitted, activated, filled, cancelled) |
| `fills.jsonl` | Fill records with price, size, side, asset |
| `ledger.jsonl` | Portfolio snapshots after each fill event |
| `equity_curve.jsonl` | Equity over time (one row per book-affecting event) |
| `best_bid_ask.jsonl` | Best bid/ask timeline for the primary asset |
| `run_manifest.json` | Full run config, warnings, run quality, fill/decision counts |
| `meta.json` | Run quality summary (ok / warnings / invalid / degraded) |

### Per-tape artifacts (`artifacts/simtrader/tapes/<tape-id>/`)

| File | What it contains |
|------|-----------------|
| `events.jsonl` | Normalized events (one JSON object per line, `seq` envelope) |
| `raw_ws.jsonl` | Raw WS frames (archive — not used by replay) |
| `meta.json` | Recorder metadata (reconnect count, warnings) |

### Start here when reading results

1. `summary.json` → `net_profit` and fee totals
2. `decisions.jsonl` → did the strategy see arb windows?
3. `fills.jsonl` → what actually executed
4. `run_manifest.json` → `run_quality` and `warnings`

---

## 5. Troubleshooting

### Empty tape / `parsed_events: 0`

The WebSocket received nothing. Almost always means the market has no live CLOB orderbook.

**Fix:** Use `--dry-run` first. If `quickrun` passes dry-run but the tape is empty, try a different market or a longer `--duration`.

### "No orderbook exists for the requested token id"

The Gamma API listed this market but the CLOB has no order book for one of the tokens.

**Fix:** `quickrun` detects this automatically and skips the market. If you're running `record` manually, check both tokens first:

```bash
curl "https://clob.polymarket.com/book?token_id=<YES_TOKEN>"
curl "https://clob.polymarket.com/book?token_id=<NO_TOKEN>"
```

Both must return an object with `bids`/`asks` keys (not an `error` key).

### No decisions / `net_profit: 0`

The strategy ran but found no arb windows. Common causes:

- **Tape too short.** 30 seconds rarely contains an arb opportunity. Use `--duration 900` or longer.
- **Buffer too wide.** Default `buffer=0.01` means `sum_ask < 0.99` to trigger. Try `--strategy-config-json '{"buffer":0.005}'` to widen the detection window.
- **Quiet market.** Some markets barely trade. Try a different market with higher volume.

### `run_quality: degraded`

One asset in the tape has no book snapshot (`snapshot_by_asset` shows `false`). The arb strategy can still run but results are unreliable.

**Fix:** Record a longer tape (initial snapshot arrives within the first few seconds of connection). Check `tape-info` output.

### `run_quality: invalid`

The tape failed the coverage check and the run was aborted. Re-record with a longer duration, or add `--allow-degraded` to `simtrader run` if you're aware of the limitation.

### Windows PowerShell BOM in config files

**This is now handled automatically.** `--strategy-config-path` reads config files with `utf-8-sig` encoding, so files written by PowerShell's `Out-File -Encoding utf8` (which adds a BOM) load correctly.

You no longer need the `[System.IO.File]::WriteAllText(...)` workaround. Standard `Out-File` is fine.

---

## 6. Further reading

| Resource | What's in it |
|----------|-------------|
| [`SPEC-0010`](specs/SPEC-0010-simtrader-vision-and-roadmap.md) | Full north-star vision, realism constraints, strategy classes, phased roadmap |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | PolyTool component overview and data flow |
| [`STRATEGY_PLAYBOOK.md`](STRATEGY_PLAYBOOK.md) | Outcome taxonomy, EV framework, falsification methodology |
| `artifacts/simtrader/` | All private tapes, runs, and sweeps (gitignored) |
