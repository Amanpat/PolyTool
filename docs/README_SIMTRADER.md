# SimTrader (PolyTool) — Plan, Roadmap, Procedure, and Current Status

This document is the single “how we run SimTrader” reference. It explains the full end-to-end plan, our phased roadmap, the hardened operating procedure (with copy/paste commands), and what we have already implemented.

Realism is the top rule: if SimTrader says a strategy is profitable but it fails live, SimTrader is wrong and we treat that as a blocker.

## 1) The full plan (end-to-end)

We are building a replay-first “simulated trader” for Polymarket. It’s meant to behave like a real exchange + trader loop so we can test strategies honestly under frictions:

- L2 orderbook (book snapshots + deltas)
- spread/slippage and limited size at price levels
- partial fills, cancels, cancel latency
- latency knobs (submit/cancel timing)
- run quality gates (invalid/degraded/ok)
- deterministic replay (same tape/config → same outputs)

The system is designed to support:

- Replay mode first (deterministic, scalable)
- Shadow mode later (live data, fake orders) as a realism gate before real trading
- Strategies as plugins (copy-wallet and binary complement arb first)
- Scenario sweeps (distributions, not a single PnL number)
- Batch runs later (20+ strategies × 200+ markets overnight)
- Evidence → RAG flow later (store results as evidence, not truth)

## 2) Roadmap (from start to “complete”)

This is the SimTrader roadmap we’re building toward (we keep it phased so we don’t explode scope):

Phase 0 — Replay Core (DONE)

- Record Market Channel WS tape (raw_ws.jsonl + events.jsonl)
- Deterministic replay
- L2 book reconstruction
- best_bid_ask timeline output

Phase 1 — BrokerSim (DONE)

- Marketable limit fills (walk-the-book)
- Cancel support + cancel latency
- Deterministic fills with “because” logic

Phase 2 — Portfolio & PnL (DONE)

- Portfolio ledger (reservations, FIFO cost basis)
- Conservative marking (bid-side default; midpoint optional)
- Fee model (conservative default)
- equity_curve + summary.json

Phase 3 — Strategy Runner + CopyWalletReplay (DONE)

- Strategy interface (on_start/on_event/on_finish)
- StrategyRunner with full audit artifacts
- CopyWalletReplay strategy using a JSONL trade fixture + signal delay

Phase 4 — BinaryComplementArb strategy (DONE)

- Two-leg arb attempt logic
- Legging policy + unwind behavior
- Correctness fixes for same-tick fills and repeated unwind issues

Phase 5 — Scenario Sweeps (DONE)

- Run the same tape+strategy across scenario overrides
- Produce sweep_manifest.json + sweep_summary.json (best/median/worst)

Phase 6 — Tape correctness for multi-asset arb (DONE)

- Record multiple asset IDs into one tape dir
- tape-info command
- Coverage validation for arb (fail-fast invalid, optional allow-degraded)

Phase 7 — Batch Orchestrator (NEXT)

- Run many jobs overnight (strategy × market/tape) with optional sweeps
- Produce leaderboard/batch_summary.json and pointers to artifacts

Phase 8 — Visual stage (NEXT)

- Export run + sweep summaries into ClickHouse or generate HTML reports
- Grafana dashboard / minimal UI for browsing results

Phase 9 — Evidence → RAG integration (FUTURE)

- Store every run as evidence with metadata + artifacts
- Promote distilled learnings into the research RAG

Phase 10 — Shadow mode (FUTURE)

- Live market feed + simulated broker (no real orders)
- Same strategy interface, same artifacts

## 3) What we have built so far (current status)

We currently have a usable SimTrader stack:

- Record (WS Market Channel) to tape with keepalive pings + reconnect/resubscribe.
- Correct Market Channel subscribe payload (assets_ids, type=market, initial_dump=true).
- Replay runner and L2 book reconstructor.
- BrokerSim (fills/cancels/partial behavior) with determinism.
- PortfolioLedger + PnL outputs (summary + equity curve).
- Strategy interface + StrategyRunner that emits audited artifacts:
  - decisions.jsonl
  - orders.jsonl
  - fills.jsonl
  - ledger.jsonl
  - equity_curve.jsonl
  - summary.json
  - best_bid_ask.jsonl
  - run_manifest.json
  - meta.json
- Strategies:
  - copy_wallet_replay
  - binary_complement_arb
- Scenario sweeps:
  - simtrader sweep produces sweep_summary.json and per-scenario run folders
- Tape correctness:
  - multi-asset record supported
  - tape-info command
  - arb coverage validation (invalid/degraded)

In short: we can already record a market, replay it, run arb/copy strategies, and get net profit + audit trails.

## 4) The hardened procedure (how to run SimTrader correctly)

### 4.1) Rule #1: Only record markets with real CLOB orderbooks

A market can exist in Gamma but have no live orderbook. If /book returns:
"No orderbook exists for the requested token id"
then Market Channel WS will stream nothing.

So the workflow is:

1. get token IDs (asset_ids) for the two outcomes
2. confirm both have a live /book
3. record YES+NO into one tape
4. tape-info must show book snapshots for both assets

### 4.2) Get outcome token IDs (asset_ids) from a Polymarket event URL

Example URL:
https://polymarket.com/event/<SLUG>

The slug is the part after /event/.

PowerShell:

```powershell
$slug = "PUT_SLUG_HERE"
$m = Invoke-RestMethod "https://gamma-api.polymarket.com/markets/slug/$slug"

$tokenIds = $m.clobTokenIds
if ($tokenIds -is [string]) { $tokenIds = $tokenIds | ConvertFrom-Json }

$outcomes = $m.outcomes
if ($outcomes -is [string]) { $outcomes = $outcomes | ConvertFrom-Json }

"Outcomes:"; $outcomes
"clobTokenIds:"; $tokenIds

The token IDs are what SimTrader calls --asset-id (one per outcome).

4.3) Confirm both tokens have a live orderbook
$YES = "YES_TOKEN_ID"
$NO  = "NO_TOKEN_ID"

Invoke-RestMethod "https://clob.polymarket.com/book?token_id=$YES" | Out-Null
Invoke-RestMethod "https://clob.polymarket.com/book?token_id=$NO"  | Out-Null
"Both books exist."

If either call errors with “No orderbook exists…”, pick a different market.

4.4) Record a tape (YES + NO) into one directory
python -m polytool simtrader record `
  --asset-id $YES `
  --asset-id $NO `
  --duration 600

This creates:
artifacts/simtrader/tapes/<tape-id>/{raw_ws.jsonl, events.jsonl, meta.json}

4.5) Inspect tape coverage (required before arb)
python -m polytool simtrader tape-info `
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl

You want:

both asset_ids present

snapshot_by_asset shows true for both

event_type_counts includes book and price_change

warnings empty

4.6) Run CopyWalletReplay (fixture-based)

Create a trades fixture (seq is the tape seq you want to act on):

@'
{"seq": 10, "side": "BUY",  "limit_price": "0.45", "size": "200", "trade_id": "t1"}
{"seq": 40, "side": "SELL", "limit_price": "0.55", "size": "200", "trade_id": "t2"}
'@ | Out-File trades.jsonl

Run:

python -m polytool simtrader run `
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl `
  --strategy copy_wallet_replay `
  --strategy-config (Get-Content trades.jsonl -Raw | ForEach-Object { '{"trades_path":"trades.jsonl","signal_delay_ticks":2}' }) `
  --starting-cash 1000 `
  --fee-rate-bps 200 `
  --mark-method bid

(If you prefer: put strategy config in a JSON file and use --strategy-config-path.)

4.7) Run BinaryComplementArb (file-based config is safest on Windows)

IMPORTANT: Windows PowerShell 5.1 often writes UTF-8 with BOM. JSON readers may reject BOM.
Use the .NET WriteAllText trick to avoid BOM.

Create arb_strategy.json without BOM:

$cfg = @'
{
  "yes_asset_id": "YES_TOKEN_ID",
  "no_asset_id":  "NO_TOKEN_ID",
  "buffer": 0.02,
  "max_size": 25,
  "legging_policy": "wait_N_then_unwind",
  "unwind_wait_ticks": 5
}
'@
[System.IO.File]::WriteAllText(".\arb_strategy.json", $cfg, (New-Object System.Text.UTF8Encoding($false)))

Run:

python -m polytool simtrader run `
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl `
  --strategy binary_complement_arb `
  --strategy-config-path .\arb_strategy.json `
  --asset-id YES_TOKEN_ID `
  --starting-cash 2000 `
  --fee-rate-bps 200 `
  --mark-method bid

Artifacts appear in:
artifacts/simtrader/runs/<run-id>/

4.8) Scenario sweeps (robustness distribution)

Create sweep config:

$sc = @'
{
  "scenarios": [
    {"name":"base","overrides":{}},
    {"name":"fees_high","overrides":{"fee_rate_bps":300}},
    {"name":"midmark","overrides":{"mark_method":"midpoint"}},
    {"name":"cancel_slow","overrides":{"cancel_latency_ticks":5}}
  ]
}
'@
[System.IO.File]::WriteAllText(".\sweep.json", $sc, (New-Object System.Text.UTF8Encoding($false)))

Run sweep:

python -m polytool simtrader sweep `
  --tape artifacts/simtrader/tapes/<tape-id>/events.jsonl `
  --strategy binary_complement_arb `
  --strategy-config-path .\arb_strategy.json `
  --starting-cash 2000 `
  --sweep-config (Get-Content .\sweep.json -Raw)

Sweep outputs:
artifacts/simtrader/sweeps/<sweep-id>/
sweep_summary.json
sweep_manifest.json
runs/<scenario>/... (normal run artifacts)

4.9) Interpreting outputs (what to look at first)

summary.json → headline net_profit and key totals

decisions.jsonl → why the strategy acted (or didn’t)

fills.jsonl → what actually filled (audit)

ledger.jsonl + equity_curve.jsonl → accounting and curve

meta.json / run_manifest.json → run_quality and assumptions

5) Hardening checklist (before scaling to batch)

Before we run big overnight batches, we enforce these gates:

Tape gate:

tape-info must show both assets and snapshots for arb

no malformed lines

Run quality gate:

invalid runs excluded from leaderboards by default

degraded runs only included if explicitly allowed

Determinism gate:

rerunning same tape/config produces identical artifacts

Conservatism gate:

default fees and marking are conservative

scenario sweeps are required for any “promoted” strategy claim

Evidence gate:

store artifacts as evidence, never as truth

6) Known gotchas (and how to avoid them)

Gamma tokens but no orderbook

Gamma can list markets that don’t have a live CLOB book.

Always check /book on BOTH outcome tokens before recording.

Market Channel WS returns nothing

Usually means no live orderbook OR bad subscription payload.

SimTrader recorder now uses correct payload and has keepalive/reconnect.

If /book fails, WS will not stream.

Windows PowerShell BOM in JSON files

Out-File -Encoding utf8 writes BOM in PS 5.1.

Use [System.IO.File]::WriteAllText with UTF8Encoding(false) to write BOM-free JSON.

Alternatively, the CLI should be hardened to read config files using utf-8-sig.

Short tapes may show net_profit=0

A short tape may contain no arb windows.

Record longer tapes (10–30 minutes) for meaningful experiments.

7) Where to read deeper details

docs/specs/SPEC-0010-simtrader-vision-and-roadmap.md (full north-star vision)

docs/ARCHITECTURE.md and docs/STRATEGY_PLAYBOOK.md (overall PolyTool approach)

artifacts/simtrader/* (all private tapes/runs/sweeps)
```
