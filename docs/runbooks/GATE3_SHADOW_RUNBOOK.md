# Gate 3 Shadow Runbook

**Gate:** Gate 3 — Shadow Mode
**Strategy:** market_maker_v1
**Status required before Stage 0:** PASSED

---

## Overview

Gate 3 verifies that `market_maker_v1` can operate against the live Polymarket
WebSocket feed without structural errors and without submitting real orders. It
is a manual operator-signed gate: the operator runs the shadow session, reviews
the artifacts, and writes `gate_passed.json` if criteria are met.

Shadow mode is structurally incapable of placing real orders. There is no
`--live` flag for `simtrader shadow`. This is verified by
`TestCancelAllOnDisconnect` and the shadow mode test suite.

---

## Prerequisites

Before starting Gate 3:

- [ ] Gate 2 benchmark sweep has **PASSED**
  ```bash
  python tools/gates/gate_status.py
  # Must show PASSED for mm_sweep_gate (Gate 2b)
  ```
- [ ] Gate 1 replay has PASSED (already done in Phase 1A)
- [ ] Gate 4 dry-run live has PASSED (already done in Phase 1A)
- [ ] Kill-switch file is absent or falsy
- [ ] No open positions from a prior run
- [ ] `python -m polytool --help` shows all commands load cleanly

**Gate 2 must PASS before Gate 3 sign-off.** If Gate 2 is FAILED, investigate
the sweep market or tape before running Gate 3.

---

## Safety Invariants

These safety properties are built into the shadow runner and must not be
bypassed:

| Invariant | Implementation | Verified by |
|-----------|---------------|-------------|
| No real orders submitted | Shadow mode has no order-submission path | `run_manifest["fills_count"] == 0` |
| Cancel-all on WS disconnect | `broker.cancel_all_immediate()` fires before reconnect | `TestCancelAllOnDisconnect` in `test_simtrader_shadow.py` |
| Kill-switch trips halt strategy | `LiveRunner` checks kill-switch file before each tick | `test_discord_notifications.py` |
| WS stall auto-exits | `max_ws_stall_seconds` (default 30s) triggers clean exit | `TestShadowStall` in `test_simtrader_shadow.py` |
| No hardcoded credentials | All ClickHouse credentials from env vars | CLAUDE.md ClickHouse auth rule |

---

## Step 1: Pick a Market

Find an active, liquid market. The market should have at least one recent
price-change event in the last 10 minutes.

```bash
python -m polytool simtrader quickrun \
    --dry-run \
    --list-candidates 10 \
    --activeness-probe-seconds 30
```

Note the `market_slug` of a candidate showing active price-change events.
Prefer crypto or near-resolution markets for maximum event density.

---

## Step 2: Run the Shadow Session

```bash
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 300
```

Optional flags:
- `--max-ws-stall-seconds 120` — increase stall timeout for quieter markets
- `--no-record-tape` — skip tape recording (not recommended for gate run)

**Expected stderr output:**
```
[shadow] market   : <SLUG>
[shadow] strategy : market_maker_v1
[shadow] run dir  : artifacts/simtrader/shadow_runs/<id>
[shadow] duration : 300s
```

The command exits when duration elapses or WS stalls. Exit code 0 is normal.

---

## Step 3: Review Artifacts

The shadow run directory is at:
```
artifacts/simtrader/shadow_runs/<id>/
```

Files produced:
```
run_manifest.json   <- primary verification artifact
meta.json           <- market resolution metadata
raw_ws.jsonl        <- raw WS frames (if tape recording enabled)
events.jsonl        <- parsed events (if tape recording enabled)
```

### run_manifest.json checks

Open `run_manifest.json` and verify:

- [ ] `"mode": "shadow"` — confirms shadow (not replay) run
- [ ] `"run_metrics.events_received" > 0` — market was live and events received
- [ ] `"fills_count": 0` — zero fills, shadow never submits real orders
- [ ] `"exit_reason"` is `null` or `"stall"` — no crash or error
- [ ] No `RuntimeError` or import errors in stderr

**Minimum viable evidence checklist:**

```bash
python -c "
import json, sys
path = 'artifacts/simtrader/shadow_runs/<id>/run_manifest.json'
m = json.loads(open(path).read())
assert m['mode'] == 'shadow', 'mode must be shadow'
assert m['run_metrics']['events_received'] > 0, 'must receive at least 1 event'
assert m['fills_count'] == 0, 'fills_count must be 0'
assert m.get('exit_reason') in (None, 'stall'), f'unexpected exit_reason: {m.get(\"exit_reason\")}'
print('All checks passed')
"
```

### Strategy log check

Inspect stderr or any log output for `WOULD PLACE` lines (the strategy
reporting it would submit a quote if this were live). If the market was quiet,
no log lines is acceptable; silence is not a failure.

---

## Step 4: Write the Gate Artifact

Once all checks pass, create the gate artifact manually:

```bash
mkdir -p artifacts/gates/shadow_gate
```

Create `artifacts/gates/shadow_gate/gate_passed.json` with:

```json
{
  "gate": "shadow",
  "passed": true,
  "commit": "<output of: git rev-parse --short HEAD>",
  "timestamp": "<ISO 8601 UTC, e.g. 2026-03-26T20:00:00Z>",
  "shadow_run_dir": "artifacts/simtrader/shadow_runs/<id>",
  "market_slug": "<SLUG used for shadow run>",
  "events_received": <value from run_manifest.run_metrics.events_received>,
  "duration_seconds": 300,
  "notes": "Manual sign-off by operator <name> on <date>"
}
```

Get the commit hash:
```bash
git rev-parse --short HEAD
```

---

## Step 5: Verify Gate Status

```bash
python tools/gates/gate_status.py
```

Gates 1, 2, 3, and 4 should all show PASSED. The output should end with:

```
Result: ALL REQUIRED GATES PASSED - Track A promotion criteria met.
```

---

## Abort Criteria

Stop the shadow run and investigate before writing `gate_passed.json` if:

- Kill switch trips during the session (reported in stderr)
- `RuntimeError` or import error in stderr
- `events_received == 0` after the full duration (market may be stale or WS broken)
- Any `fills_count > 0` in `run_manifest.json` (should structurally be impossible)
- `exit_reason` is not `null` or `"stall"` (indicates unexpected error path)

---

## Artifact Schema Reference

```
run_manifest.json:
  mode: "shadow"
  started_at: ISO 8601 UTC
  ended_at: ISO 8601 UTC
  exit_reason: null | "stall" | <error string>
  fills_count: 0
  run_metrics:
    ws_reconnects: int
    ws_timeouts: int
    events_received: int
    batched_price_changes: int
    per_asset_update_counts: {asset_id: int}
  shadow_context:
    market_slug: str
    yes_asset_id: str
    no_asset_id: str
    strategy: str
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `events_received == 0` | Market is inactive or WS URL changed | Pick a different market or check `--max-ws-stall-seconds` |
| WS connect error | Network issue or Polymarket outage | Wait and retry |
| `ModuleNotFoundError` | Missing dependency | `pip install -e .[all]` |
| Kill switch trips immediately | Stale kill-switch file | Remove `artifacts/kill_switch` or reset its value |
| `fills_count > 0` | Shadow mode structural failure (should not happen) | File a bug immediately; do not sign off |

---

## Notes

- Shadow mode never submits real orders. The absence of a `--live` flag is
  structural, not configurable.
- Gate 4 (dry-run live) may be run in parallel with Gate 3. It does not
  require a live WS connection and is already PASSED.
- After Gate 3 sign-off, verify that `python tools/gates/gate_status.py`
  shows all four gates PASSED before proceeding to Stage 0.
- Stage 0 (paper live dry-run) is a human-only promotion decision. Capital
  deployment requires operator authorization.
