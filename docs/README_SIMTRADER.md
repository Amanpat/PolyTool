# SimTrader â€” User Guide

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

Outcome mapping is deterministic:
- Explicit `Yes`/`No` labels are preferred.
- `True`/`False` and `Up`/`Down` are supported as aliases.
- Ambiguous labels fail fast with a clear error that includes the raw outcomes and slug.

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

**Auditability notes:**
- `ledger.jsonl` always contains at least two rows â€” an **initial** snapshot (starting cash, no positions) and a **final** snapshot â€” even when zero orders are placed. This guarantees the file is never empty and is safe to ingest into downstream RAG / evidence pipelines.
- When `binary_complement_arb` produces zero decisions, `run_manifest.json` and `summary.json` include a `strategy_debug.rejection_counts` dict explaining why (e.g. `no_bbo`, `edge_below_threshold`, `waiting_on_attempt`).

---

## 1a. Shadow mode (live simulated)

Shadow mode processes live Polymarket WS events *inline* â€” no tape file needed before the strategy runs. It streams YES + NO token data, drives `binary_complement_arb` through `BrokerSim` (no real orders ever placed), and writes the full artifact set at the end.

```bash
# Shadow-trade a specific market for 5 minutes
python -m polytool simtrader shadow --market will-x-happen-2026 --duration 300

# Skip tape recording (no raw_ws.jsonl / events.jsonl written)
python -m polytool simtrader shadow --market will-x-happen-2026 --duration 300 --no-record-tape
```

**How it differs from `quickrun`:**

| | `quickrun` | `shadow` |
|---|---|---|
| Phases | Record â†’ replay (sequential) | Process live (inline) |
| Tape required up-front | Yes | No |
| Concurrent tape writing | No | Yes (default ON) |
| Artifacts | Same set | Same set + `mode: "shadow"` |

**Output layout:**

```
artifacts/simtrader/shadow_runs/<ts>_shadow_<token_prefix>/
    best_bid_ask.jsonl   decisions.jsonl   fills.jsonl
    orders.jsonl         ledger.jsonl      equity_curve.jsonl
    summary.json         run_manifest.json meta.json

artifacts/simtrader/tapes/<ts>_shadow_<token_prefix>/   (if recording)
    raw_ws.jsonl   events.jsonl   meta.json
```

`run_manifest.json` includes `"mode": "shadow"` and a `shadow_context` block (slug, token IDs, selection metadata) for full auditability.  The tape written alongside is identical to `TapeRecorder` output and can be replayed with `simtrader replay` or `simtrader run`.

**Prerequisites:** `pip install 'websocket-client>=1.6'`

---

## 1b. Evidence sweep (multi-scenario)

Run a bounded matrix of parameter variants in one command:

```bash
python -m polytool simtrader quickrun --duration 900 --sweep quick
```

The **`quick` preset** expands to 24 scenarios:

| Axis | Values |
|------|--------|
| `fee_rate_bps` | 0, 50, 100, 200 |
| `cancel_latency_ticks` | 0, 2, 5 |
| `mark_method` | bid, midpoint |

Output: `artifacts/simtrader/sweeps/quickrun_<ts>_<token_prefix>/`
Files: `sweep_manifest.json`, `sweep_summary.json`, one run sub-folder per scenario.

**Expected output (abridged):**

```
QuickSweep complete  (preset: quick, 24 scenarios)
  Market    : will-candidate-win-2026
  Sweep dir : artifacts/simtrader/sweeps/quickrun_.../

  LEADERBOARD (net_profit):
    Best   : 1.43  (fee0_cancel0_bid)
    Median : 0.12  (fee100_cancel2_midpoint)
    Worst  : -0.05  (fee200_cancel5_midpoint)

Reproduce:
  python -m polytool simtrader quickrun --market will-candidate-win-2026 --duration 900 --sweep quick
```

---

## 1c. Overnight batch leaderboard

Run many one-shot quick sweeps and aggregate them in one leaderboard:

```bash
python -m polytool simtrader batch --preset quick --num-markets 20 --duration 1800
```

For faster local development loops:

```bash
python -m polytool simtrader batch --preset quick_small
```

`quick_small` is a compact preset (3 markets by default and a smaller 4-scenario sweep matrix per market).

Optional runtime cap:

```bash
python -m polytool simtrader batch --preset quick_small --time-budget-seconds 900
```

When the time budget is exceeded, batch stops launching new markets and marks the remaining markets as skipped.

Output root: `artifacts/simtrader/batches/<batch_id>/`

- `batch_manifest.json` (params + deterministic seed + selected markets)
- `batch_summary.json` (per-market best/median/worst net profit, decisions/orders/fills, dominant rejection counts, tape quality stats)
- `batch_summary.csv` (same data, spreadsheet-friendly)
- `markets/<slug>/...` (per-market sweep artifacts and copied tape metadata)

Idempotency: if a market already has `markets/<slug>/sweep_summary.json`, batch skips it unless you pass `--rerun`.

---

## 1d. Viewing results (`report.html`)

You can generate a local self-contained HTML report for any SimTrader artifact folder:

```bash
python -m polytool simtrader report --path artifacts/simtrader/sweeps/<sweep-id>
python -m polytool simtrader report --path artifacts/simtrader/batches/<batch-id>
python -m polytool simtrader report --path artifacts/simtrader/runs/<run-id>
```

This writes `report.html` directly inside the folder you passed.

Optional:

```bash
python -m polytool simtrader report --path <artifact_dir> --open
```

`--open` prints a friendly command you can run to open the file in your browser.

---

## 1e. Browse recent results

Use `browse` to list the newest artifacts across runs, sweeps, batches, and shadow runs:

```bash
python -m polytool simtrader browse
python -m polytool simtrader browse --limit 20 --type sweep
python -m polytool simtrader browse --open
python -m polytool simtrader browse --report-all
```

- `--limit N` controls how many entries are listed (default: 10).
- `--type run|sweep|batch|shadow|all` filters artifact type (default: all).
- `--open` generates `report.html` for the newest listed artifact and prints browser-open instructions.
- `--report-all` generates `report.html` for every listed artifact.

---

## 1f. Golden Run v2 checklist (strict)

Use this exact operator workflow for copy/paste repeatability and consistent evidence artifacts.

1. Pick and validate a market candidate:

```bash
python -m polytool simtrader quickrun --dry-run
```

2. Run the 30-minute evidence sweep on the chosen slug:

```bash
python -m polytool simtrader quickrun --market <slug> --duration 1800 --sweep quick --min-events 200
```

3. Read the sweep artifact bundle:

- `sweep_summary.json` lives at `artifacts/simtrader/sweeps/quickrun_<timestamp>_<token_prefix>/sweep_summary.json`
- `aggregate` is the leaderboard (best/median/worst).
- `aggregate.total_decisions`, `aggregate.total_orders`, `aggregate.total_fills` are summed across all scenarios.
- `aggregate.scenarios_with_trades` counts scenarios where `fills_count > 0`.
- `aggregate.dominant_rejection_counts` lists the top 5 aggregated rejection counters as `[{ "key": ..., "count": ... }]`.
- `scenarios[].artifact_path` points to each scenario run directory.

4. Interpret `strategy_debug.rejection_counts` per scenario:

- Open `<artifact_path>/run_manifest.json` or `<artifact_path>/summary.json`.
- Look at `strategy_debug.rejection_counts`.
- High `no_bbo` means missing tradable quote context.
- High `edge_below_threshold` means edge did not clear fees+buffer.
- High `waiting_on_attempt` means the strategy spent time in wait/unwind cadence.

Minimum tape quality gate (recommended):

- `snapshot_by_asset` is `true` for both YES and NO assets.
- `event_type_counts.price_change > 200`.
- `best_bid_ask` lines > 200 (or `run_manifest.json` has `timeline_rows > 200`).

If any gate fails, rerun with longer `--duration` or pick a more active market.

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
`https://polymarket.com/event/<slug>` â€” the slug is everything after `/event/`.

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

You can also use named presets:

| Preset | Intent | Equivalent strategy overrides |
|------|------|------|
| `sane` | Conservative baseline | (none; current defaults) |
| `loose` | More permissive entries | `{"max_size": 1, "buffer": 0.0005, "max_notional_usdc": 25}` |

```bash
python -m polytool simtrader quickrun --market some-slug --strategy-preset loose
```

```bash
# Inline JSON (bash)
python -m polytool simtrader quickrun \
  --market some-slug \
  --strategy-config-json '{"buffer": 0.02, "max_size": 25}'
```

**PowerShell note (`--strategy-config-json`)**

PowerShell does **NOT** support bash-style `\"` escaping.
Use single quotes around the full JSON and double quotes inside.

```powershell
python -m polytool simtrader quickrun `
  --market some-slug `
  --strategy-config-json '{"buffer": 0.02, "max_size": 25}'
```

For complex JSON, use a here-string:

```powershell
$cfg = @'
{"buffer": 0.02, "max_size": 25, "legging_policy": "wait_N_then_unwind", "unwind_wait_ticks": 5}
'@
python -m polytool simtrader quickrun `
  --market some-slug `
  --strategy-config-json $cfg
```

Alternative: JSON file (PowerShell; UTF-8 BOM is handled automatically):

```powershell
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
| `--duration N` | 30 | Recording duration in seconds (use 600â€“1800 for meaningful results) |
| `--min-events N` | 0 | Warn if recorded `parsed_events` is below N (no auto-extend, run still proceeds) |
| `--starting-cash X` | 1000 | Starting USDC balance |
| `--fee-rate-bps N` | 200 | Taker fee in basis points (conservative default) |
| `--mark-method` | bid | `bid` (conservative) or `midpoint` for unrealized PnL |
| `--cancel-latency-ticks N` | 0 | Cancel latency knob |
| `--allow-empty-book` | false | Accept markets whose books are currently empty |
| `--dry-run` | false | Resolve + validate without recording |
| `--strategy-preset NAME` | sane | Named strategy profile (`sane` or `loose`) |
| `--strategy-config-json STR` | â€” | Inline JSON overrides for `binary_complement_arb` |
| `--strategy-config-path PATH` | â€” | JSON file with overrides (UTF-8 BOM accepted) |
| `--max-candidates N` | 20 | Markets to scan when auto-picking |
| `--list-candidates N` | 0 | Print top N passing candidates and exit (combine with `--dry-run`). 0 = disabled |
| `--exclude-market SLUG` | – | Skip this slug during auto-pick; repeatable |

### Browsing candidates and excluding over-represented markets

If `quickrun --dry-run` always picks the same market (because it dominates the liquidity ranking),
use `--list-candidates N` to see the top N passing candidates, then exclude the unwanted one:

```bash
# See the top 5 passing candidates without committing to any
python -m polytool simtrader quickrun --dry-run --list-candidates 5

# Skip a specific market on the next run
python -m polytool simtrader quickrun --exclude-market will-always-selected-2026 --dry-run

# Exclude multiple slugs and list what remains
python -m polytool simtrader quickrun \
  --dry-run \
  --list-candidates 3 \
  --exclude-market will-always-selected-2026 \
  --exclude-market will-second-most-popular-2026
```

`--exclude-market` is also persisted to `quickrun_context` in the run manifest for auditability.

---

## 3. Advanced: manual workflow

Use the manual steps when you want to **reuse a recorded tape**, run different strategies, or produce a **scenario sweep** for robustness analysis.

### 3.1 Record a tape

```bash
# bash â€” record YES and NO tokens for 10 minutes
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

Always check coverage before running arb â€” a tape with no book snapshot for an asset will produce zero decisions:

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

`simtrader run` now auto-infers `yes_asset_id` / `no_asset_id` from
`<tape-dir>/meta.json` when available (checks `quickrun_context` first, then
`shadow_context`).  You can still pass IDs explicitly via strategy config, or
override with `--yes-asset-id` and `--no-asset-id`.

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
# PowerShell â€” use a config file to avoid quoting hell
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
# PowerShell â€” create sweep config
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
| `raw_ws.jsonl` | Raw WS frames (archive â€” not used by replay) |
| `meta.json` | Recorder metadata (reconnect count, warnings) |

### Start here when reading results

1. `summary.json` â†’ `net_profit` and fee totals
2. `decisions.jsonl` â†’ did the strategy see arb windows?
3. `fills.jsonl` â†’ what actually executed
4. `run_manifest.json` â†’ `run_quality` and `warnings`

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

