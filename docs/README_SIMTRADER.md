# SimTrader (PolyTool) — Operator Guide

SimTrader is a realism-first simulated trader for Polymarket.

It has two modes:
- **Replay-first (deterministic)**: record an immutable tape from the Market Channel WS, then replay it offline.
- **Shadow mode (live simulated)**: live WS feed → strategy → BrokerSim fills (no real orders), optionally recording a tape.

SimTrader results are **evidence, not truth**. If replay says "profitable" but shadow/live fails, replay is wrong.

---

## Fast dev loop (2–5 minutes)

1\) List viable markets (strict liquidity), exclude spam markets:

```powershell
python -m polytool simtrader quickrun --dry-run --liquidity strict --max-candidates 100 `
  --exclude-market will-trump-deport-less-than-250000 `
  --list-candidates 10
```

2\) Shadow run (live simulated) for 180s (sanity preset + higher stall threshold):

```powershell
python -m polytool simtrader shadow --market <SLUG> --duration 180 `
  --starting-cash 2000 --fee-rate-bps 200 --mark-method bid `
  --strategy-preset loose `
  --max-ws-stalls-seconds 180
```

3\) Replay run on the tape produced by shadow (no manual YES/NO IDs needed if tape meta has context):

```powershell
python -m polytool simtrader run --tape artifacts/simtrader/tapes/<tape_id>/events.jsonl `
  --strategy binary_complement_arb `
  --starting-cash 2000 --fee-rate-bps 200 --mark-method bid `
  --strategy-preset loose
```

4\) Open the newest HTML report:

```powershell
python -m polytool simtrader browse --open
```

---

## Core concepts

- **Tape is ground truth**: `raw_ws.jsonl` and `events.jsonl` are immutable evidence of the WS stream.
- **Replay determinism**: same tape + same config → same artifacts.
- **Conservative defaults**: marking, fees, and fills skew against you.
- **Explainability**: every no-trade run should still explain "why" via rejection counters and run manifests.

---

## Command overview

SimTrader CLI entry:

```
python -m polytool simtrader <subcommand> ...
```

Subcommands (current):

| Subcommand | Description |
|------------|-------------|
| `quickrun` | One-shot workflow (pick/validate → record → run or sweep) |
| `shadow` | Live simulated trading (WS → strategy → BrokerSim), optional tape recording |
| `run` | Run a strategy on an existing tape |
| `sweep` | Scenario grid runner for a tape |
| `batch` | Run many markets (optionally sweeps) and produce leaderboard summaries |
| `record`, `tape-info`, `replay` | Lower-level tape and replay utilities |
| `report` | Generate `report.html` for a run/sweep/batch/shadow artifact folder |
| `browse` | List recent artifacts; generate/open reports |
| `clean` | Delete artifact folders under artifacts/simtrader/ (dry-run by default) |
| `diff`  | Compare two run directories and write diff_summary.json |

---

## One-shot replay workflow: quickrun

Quickrun (single run):

```powershell
python -m polytool simtrader quickrun --duration 300 --starting-cash 2000 --fee-rate-bps 200 --mark-method bid
```

Quickrun (sweep preset):

```powershell
python -m polytool simtrader quickrun --duration 1800 --sweep quick --starting-cash 2000 --fee-rate-bps 200 --mark-method bid
```

Useful flags:

| Flag | Description |
|------|-------------|
| `--market <slug>` | Force a specific market (otherwise auto-pick) |
| `--dry-run` | Resolve and validate market then exit (no recording) |
| `--list-candidates N` | With `--dry-run` prints N candidates that pass validation (useful to avoid quiet markets) |
| `--exclude-market <slug>` | Repeatable; prevents overrepresented markets |
| `--liquidity strict` | Stricter depth thresholds (recommended) |
| `--min-events N` | Warn if tape has fewer than N parsed events |
| `--strategy-preset {sane,loose}` | `sane`=conservative, `loose`=activity sanity |
| `--strategy-config-json '{...}'` | Inline JSON overrides for `binary_complement_arb` |
| `--strategy-config-path file.json` | JSON file with overrides (UTF-8 BOM accepted) |
| `--sweep PRESET` | Run a scenario sweep (e.g. `quick`, `quick_small`) |
| `--activeness-probe-seconds N` | Subscribe to WS for N seconds and count live updates before recording. Off by default. |
| `--min-probe-updates N` | Updates threshold per token to be considered active (default: 1). |
| `--require-active` | Skip markets that don't reach `--min-probe-updates` within the probe window. |

**Activeness probe example** — list only actively-trading candidates (useful when many candidates are quiet):

```powershell
python -m polytool simtrader quickrun --dry-run --list-candidates 5 `
  --activeness-probe-seconds 10 --min-probe-updates 3 --require-active
```

Each candidate line will include probe stats, e.g.:
```
[candidate 1] YES probe : 7 updates in 10.0s — ACTIVE
[candidate 1] NO probe  : 4 updates in 10.0s — ACTIVE
```

### PowerShell note (JSON strings)

PowerShell does **not** support bash-style `\"` escaping. Prefer either:

- Single quotes around JSON: `--strategy-config-json '{"buffer":0.01,"max_size":25}'`
- Or generate JSON with `ConvertTo-Json` and pass the variable:

```powershell
$cfg = @{ buffer = 0.01; max_size = 25 } | ConvertTo-Json -Compress
python -m polytool simtrader quickrun ... --strategy-config-json $cfg
```

---

## Live simulated trading: shadow mode

Shadow runs strategies against the live WS feed (no real orders). It writes the same audited artifacts as replay, and can record a tape concurrently.

```powershell
python -m polytool simtrader shadow --market <slug> --duration 180 `
  --starting-cash 2000 --fee-rate-bps 200 --mark-method bid `
  --strategy-preset loose
```

Important flags:

| Flag | Description |
|------|-------------|
| `--no-record-tape` | Disable tape recording |
| `--max-ws-stalls-seconds N` | Exit gracefully if no events arrive for N seconds (increase for quiet markets) |

---

## Run a strategy on an existing tape: run

`run` supports:
- `--strategy-config-json`, `--strategy-config-path`, legacy `--strategy-config`
- `--strategy-preset {sane,loose}`
- Auto-inference of YES/NO IDs for `binary_complement_arb` from tape `meta.json` when present
- Manual overrides: `--yes-asset-id`, `--no-asset-id`

Typical:

```powershell
python -m polytool simtrader run --tape artifacts/simtrader/tapes/<tape_id>/events.jsonl `
  --strategy binary_complement_arb `
  --starting-cash 2000 --fee-rate-bps 200 --mark-method bid `
  --strategy-preset sane
```

If a tape lacks context, override:

```powershell
python -m polytool simtrader run --tape artifacts/simtrader/tapes/<tape_id>/events.jsonl `
  --strategy binary_complement_arb `
  --yes-asset-id <YES_TOKEN_ID> --no-asset-id <NO_TOKEN_ID> `
  --starting-cash 2000 --fee-rate-bps 200 --mark-method bid
```

---

## Sweeps and batch runs

Sweeps exist to produce distributions (robustness), not a single PnL number.

**Quick sweep presets:**

| Preset | Scenarios |
|--------|-----------|
| `quick` | 24 scenarios (fee × cancel latency × mark method) |
| `quick_small` | Compact sweep intended for iteration |

**Batch runs:**

```powershell
python -m polytool simtrader batch --preset quick_small --liquidity strict --time-budget-seconds 600
```

**Batch outputs:**

- `batch_manifest.json`
- `batch_summary.json` and `batch_summary.csv`

---

## Local UI: report and browse

Generate report for any artifact folder:

```powershell
python -m polytool simtrader report --path artifacts/simtrader/sweeps/<id> --open
```

Browse recent artifacts and open newest:

```powershell
python -m polytool simtrader browse --open
```

Use `--force` to regenerate `report.html`; otherwise existing reports are reused.

---

## Artifact cleanup: clean

`clean` removes artifact folders under `artifacts/simtrader/`. Defaults to dry-run; pass `--yes` to actually delete.

```powershell
# Preview what would be deleted (safe default)
python -m polytool simtrader clean

# Delete everything
python -m polytool simtrader clean --yes

# Delete only run artifacts
python -m polytool simtrader clean --runs --yes
```

Category flags (combinable): `--runs`, `--tapes`, `--sweeps`, `--batches`, `--shadow`.

Safety notes:
- Without `--yes`, the command only prints what would be deleted and the byte count — nothing is removed.
- `clean` refuses to operate if the artifacts root is not `artifacts/simtrader/` (guards against misconfigured paths).
- Tapes are immutable evidence. Delete tapes only after confirming they are no longer needed for replay or audit.

---

## Comparing runs: diff

`diff` compares two run directories (or shadow run directories) and writes a `diff_summary.json` to `artifacts/simtrader/diffs/<timestamp>_diff/` by default.

```powershell
python -m polytool simtrader diff `
  --a artifacts/simtrader/runs/<run_a_id> `
  --b artifacts/simtrader/runs/<run_b_id>
```

Output printed to stdout: strategy, config changed flag, counts (decisions/orders/fills A→B with delta), net PnL A→B, exit reason, dominant rejection counts.

Output written to disk: `artifacts/simtrader/diffs/<timestamp>_diff/diff_summary.json`

Optional: `--output-dir <path>` to write the diff to a custom directory.

Typical use: compare the same tape replayed with different strategy presets or fee rates to understand which parameter changed the outcome.

---

## Artifacts layout

All private outputs are under `artifacts/simtrader/` (gitignored). Typical structure:

```
tapes/<tape_id>/
    raw_ws.jsonl
    events.jsonl
    meta.json

runs/<run_id>/
    best_bid_ask.jsonl
    decisions.jsonl
    orders.jsonl
    fills.jsonl
    ledger.jsonl          (always has initial+final snapshots)
    equity_curve.jsonl
    summary.json
    run_manifest.json
    meta.json
    report.html           (optional)

shadow_runs/<run_id>/     (same file set as runs)

sweeps/<sweep_id>/
    sweep_manifest.json
    sweep_summary.json    (includes aggregates: total_orders/fills, scenarios_with_trades, dominant_rejection_counts)
    runs/<scenario_id>/...

batches/<batch_id>/
    batch_manifest.json
    batch_summary.json + .csv
    per-market folders
```

---

## Interpreting "no trades"

No orders/fills can be perfectly valid. Use:

- `sweep_summary.json.aggregate.dominant_rejection_counts`
- `run_manifest.json.strategy_debug.rejection_counts`

Common meanings:

| Key | Meaning |
|-----|---------|
| `insufficient_depth_yes/no` | Market is too thin at top-of-book |
| `fee_kills_edge` | Strategy refuses because fees erase expected edge |
| `edge_below_threshold` | Threshold too strict or market rarely crosses |
| `no_bbo` | Book missing BBO for one side |
| `legging_blocked` / `unwind_in_progress` | Execution policy gating |

---

## Golden Run v2 checklist (evidence-grade)

Recommended:

1. `quickrun --dry-run --list-candidates 10 --liquidity strict`
2. Pick a candidate that looks active
3. `quickrun --duration 1800 --sweep quick --liquidity strict --min-events 200`
4. Open report (`browse --open`)
5. Focus on distributions and rejection reasons, not best-case PnL

---

## Troubleshooting

- **PowerShell JSON**: use single quotes or `ConvertTo-Json`.
- **Shadow WS stall**: pick a more active market and/or increase `--max-ws-stalls-seconds`.
- Markets can be deep-but-static and one-sided; activeness matters.
- If a tape is "quiet," replay will still be deterministic; shadow will hit stalls sooner.

---

## Next engineering targets

- Improve report header: `created_at` from `started_at`; show `exit_reason` + `run_metrics`.
- Later: ClickHouse/Grafana export, evidence memo ingestion for RAG, shadow as gate before real trading.

---

## Further reading

| Resource | What's in it |
|----------|-------------|
| [`SPEC-0010`](specs/SPEC-0010-simtrader-vision-and-roadmap.md) | Full north-star vision, realism constraints, strategy classes, phased roadmap |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | PolyTool component overview and data flow |
| [`STRATEGY_PLAYBOOK.md`](STRATEGY_PLAYBOOK.md) | Outcome taxonomy, EV framework, falsification methodology |
| `artifacts/simtrader/` | All private tapes, runs, and sweeps (gitignored) |
