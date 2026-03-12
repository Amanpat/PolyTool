# Gate 3 — Shadow Mode Checklist

Shadow mode requires a live WebSocket connection to Polymarket and must be
run manually by an operator.  Automate it only after Stage 1 capital gates
are in force.

---

## Prerequisites

- [ ] Gates 1 (replay) and 2 (sweep) have **passed** (`gate_status.py` shows ✓ for both)
- [ ] A kill-switch file is **absent** or contains a falsy value
- [ ] No open positions from a prior run

---

## Steps

### 1. Pick a market

```bash
python -m polytool simtrader quickrun --dry-run --list-candidates 5
```

Note the market slug you intend to shadow.

### 2. Run shadow mode

```bash
python -m polytool simtrader shadow \
    --market <SLUG> \
    --duration 300 \
    --strategy market_maker_v0
```

Expected output (stderr lines emitted by the CLI):
- `[shadow] market   : <SLUG>` — confirms market resolved
- `[shadow] run dir  : artifacts/simtrader/shadow_runs/<id>` — run directory
- `[shadow] duration : 300s` — duration confirmed
- `run_manifest.json` under `artifacts/simtrader/shadow_runs/<id>/` has `"mode": "shadow"`
- `run_metrics.events_received > 0`
- No `RuntimeError` or kill-switch trip

Note: there is no `DRY-RUN` label in shadow mode output.  Shadow mode is
inherently dry (never submits real orders); the `--live` flag does not exist
for this subcommand.  The absence of real-order submission is verified by
checking `run_manifest["fills_count"] == 0` in step 3.

### 3. Review artifacts

Open the shadow run directory:

```
artifacts/simtrader/shadow_runs/<id>/
├── run_manifest.json   ← must contain "mode": "shadow", "exit_reason": null or "stall"
├── meta.json
├── raw_ws.jsonl        ← raw WS events (if tape_dir was set)
└── events.jsonl        ← parsed events
```

Verify:
- [ ] `run_manifest["mode"] == "shadow"`
- [ ] `run_manifest["run_metrics"]["events_received"] > 0`
- [ ] `run_manifest["fills_count"] == 0` (shadow never submits real orders)
- [ ] `run_manifest["exit_reason"]` is absent or `"stall"` (no crash/error)
- [ ] Strategy log shows WOULD PLACE lines (or no log output if market is quiet)

### 4. Write the gate artifact

Once satisfied, create the gate artifact manually:

```bash
mkdir -p artifacts/gates/shadow_gate
```

Create `artifacts/gates/shadow_gate/gate_passed.json`:

```json
{
  "gate": "shadow",
  "passed": true,
  "commit": "<git rev-parse --short HEAD>",
  "timestamp": "<ISO 8601 UTC timestamp>",
  "shadow_run_dir": "artifacts/simtrader/shadow_runs/<id>",
  "market_slug": "<SLUG>",
  "events_received": <N>,
  "duration_seconds": 300,
  "notes": "Manual sign-off by operator <name> on <date>"
}
```

### 5. Verify gate status

```bash
python tools/gates/gate_status.py
```

Gates 1, 2, 3 should all show ✓ PASSED.

---

## Abort Criteria

Stop and investigate if any of the following occur:

- Kill switch trips during the session
- `RuntimeError` or import error in stderr
- `events_received == 0` after 60 seconds (market may be stale)
- Any non-zero `fills_count` in `run_manifest.json` (should always be 0 in shadow mode)

---

## Notes

- Shadow mode never submits real orders.  There is no `--live` flag for this
  subcommand — real-order submission is structurally impossible.
- The WS stall timeout defaults to 30 s.  If the market is quiet, increase it:
  `--max-ws-stall-seconds 120`
- On WS disconnect or socket error, the runner calls `broker.cancel_all_immediate()`
  before reconnecting to prevent stale sim orders from filling against the
  reconnected book snapshot.  This is verified by `TestCancelAllOnDisconnect`
  in `tests/test_simtrader_shadow.py`.
- Gate 4 (dry-run live) may be run in parallel with or after Gate 3; it does
  not require a live WS connection.
- **Gate 2 must be PASSED before Gate 3 can be signed off.**  If Gate 2 is
  FAILED, investigate the sweep market or tape before proceeding.
