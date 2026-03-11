# Gate 2 Tape Capture Playbook (2026-03-06)

## Scope

This is an operator workflow for capturing and pre-validating candidate tapes for
`binary_complement_arb` (`strategy_preset=sane`) before running Gate 2 sweeps.

It does **not** change strategy logic, sweep logic, thresholds, or gate criteria.

---

## SECTION 1 - Selecting a Market

Use the quickrun candidate scanner and take the first ranked candidate
(`candidate 1`) unless there is an obvious reason to skip it.

```powershell
python -m polytool simtrader quickrun --dry-run `
  --liquidity strict `
  --max-candidates 100 `
  --list-candidates 5 `
  --activeness-probe-seconds 10 `
  --min-probe-updates 3 `
  --require-active
```

Selection rule:
- Pick the slug printed under `[candidate 1] slug`.
- If candidate 1 is clearly stale/quiet, move to candidate 2, then 3.

Resolve YES/NO token IDs for the selected slug (needed for `record`):

```powershell
python -m polytool simtrader quickrun --dry-run --market <market_slug>
```

From stdout, capture:
- `[quickrun] YES : <yes_token_id>`
- `[quickrun] NO  : <no_token_id>`

---

## SECTION 2 - Recording a Tape

Current `record` CLI records by token IDs (not by slug). Use the YES/NO IDs
from Section 1.

```powershell
$TS = Get-Date -Format "yyyyMMddTHHmmssZ"
python -m polytool simtrader record `
  --asset-id <yes_token_id> `
  --asset-id <no_token_id> `
  --duration 600 `
  --output-dir "artifacts/simtrader/tapes/${TS}_tape_<market_slug>"
```

Expected files in `<tape_dir>`:
- `events.jsonl`
- `meta.json`
- `raw_ws.jsonl`

---

## SECTION 3 - Quick Tape Check

### 3.1 Inspect `meta.json` and `events.jsonl`

```powershell
$TAPE_DIR = "artifacts/simtrader/tapes/<tape_dir>"
Get-Content "$TAPE_DIR/meta.json"
python -m polytool simtrader tape-info --tape "$TAPE_DIR/events.jsonl"
```

Check:
- `meta.event_count` is non-trivial (not near-zero).
- `events.jsonl` parses cleanly (`parsed_events` > 0).

### 3.2 Generate and inspect `best_bid_ask.jsonl`

```powershell
$RUN_ID = "precheck_$(Get-Date -Format 'yyyyMMddTHHmmssZ')"
python -m polytool simtrader replay --tape "$TAPE_DIR/events.jsonl" --run-id $RUN_ID
$BBA = "artifacts/simtrader/runs/$RUN_ID/best_bid_ask.jsonl"

(Get-Content $BBA | Measure-Object -Line).Lines
Get-Content $BBA -TotalCount 3
Get-Content $BBA -Tail 3
```

Use this for quick continuity sanity (stream is not empty/truncated).

### 3.3 Confirm depth + complement edge (Gate 2 usability)

```powershell
$YES_ID = "<yes_token_id>"
$NO_ID  = "<no_token_id>"
$EVENTS = (Resolve-Path "$TAPE_DIR/events.jsonl").Path

@"
import json
from pathlib import Path
from packages.polymarket.simtrader.sweeps.eligibility import check_binary_arb_tape_eligibility

events_path = Path(r"$EVENTS")
cfg = {
    "yes_asset_id": "$YES_ID",
    "no_asset_id": "$NO_ID",
    "max_size": "50",
    "buffer": "0.01",
}
result = check_binary_arb_tape_eligibility(events_path, cfg)
stats = result.stats
print("eligible:", result.eligible)
print("reason:", result.reason or "ok")
print("depth_ticks:", stats["ticks_with_depth_ok"])
print("edge_ticks:", stats["ticks_with_edge_ok"])
print("executable_ticks:", stats["ticks_with_depth_and_edge"])
print(json.dumps(stats, indent=2))
"@ | python -
```

Interpretation:
- **YES/NO depth >= strategy size?** `depth_ticks > 0`
- **At least one complement-edge tick?** `edge_ticks > 0`
- **Gate-2 executable tick exists?** `executable_ticks > 0`

---

## SECTION 4 - Reject Criteria

Discard the tape immediately if any of these is true:
- `edge_ticks == 0` (zero edge ticks).
- `depth_ticks == 0` (depth never reaches strategy size).
- `executable_ticks == 0` (depth and edge never overlap on the same tick).
- Event stream is extremely short (practical rule: `meta.event_count < 50` or
  near-empty `best_bid_ask.jsonl`).

Do not run a full Gate 2 sweep on rejected tapes.

---

## SECTION 5 - Gate 2 Ready Criteria

A tape is Gate 2 ready only if all are true:
- `executable_ticks > 0`
- Orderbook depth supports strategy size (`depth_ticks > 0`, with `max_size=50`)
- Event continuity is sufficient (non-trivial event/BBO stream, not truncated)

If all pass, keep the tape and proceed to Gate 2 sweep execution. If not, drop
the tape and return to Section 1.
