# Runbook: Gate 2 Eligible Tape Acquisition

**Purpose**: Operator step-by-step guide for capturing a Gate 2 eligible tape
and verifying corpus coverage before attempting to close Gate 2.

**Spec**: `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md`
**Gate 2 script**: `tools/gates/close_sweep_gate.py`

---

## Prerequisites

- `python -m polytool market-scan` runs without errors (Gamma API reachable)
- `python tools/gates/gate_status.py` shows Gate 1 and Gate 4 PASSED
- Docker Compose services up (for ClickHouse, if needed): `docker compose up -d`
- No active `--live` sessions running

---

## Phase 1: Discover candidates

```bash
# Rank live binary markets by depth + complement edge
python -m polytool scan-gate2-candidates --all --top 20

# Same scan, plus an exact-slug watchlist file for copy-safe handoff
python -m polytool scan-gate2-candidates --all --top 20 \
  --watchlist-out artifacts/watchlists/gate2_top20.txt
```

Read the output table:
- **Exec > 0**: market currently has executable ticks — highest priority
- **Edge > 0, Depth = 0**: edge exists but not deep enough — candidate for watching
- **Depth > 0, Edge = 0**: deep but no edge — lower priority
- **MaxDepth YES/NO**: check both legs are close to 50+ shares

If a market slug is too long to copy safely from the table, use
`--watchlist-out` and copy from the generated file instead. It writes one exact
full slug per line for the shown ranked candidates.

> If no markets show any signal (Exec=0, Edge=0, Depth=0), the dislocation
> window has not opened yet. Retry during catalyst events (game start,
> vote close, breaking news).

---

## Phase 1.5: Create a session pack (recommended)

After reviewing the scan output, commit your ranked selection to a timestamped
session pack before starting the watch session. This records exact slugs,
planned watch config, per-slug regime/new-market context when available,
corpus state, and a post-session note template.

```bash
# Create session pack from the ranked export (keep the first 3 selected entries)
python -m polytool make-session-pack \
  --watchlist-file artifacts/watchlists/gate2_top20.txt \
  --top 3 \
  --regime sports \
  --source-manifest artifacts/gates/gate2_tape_manifest.json \
  --duration 600 \
  --poll-interval 30
```

The command prints a ready-to-paste `watch-arb-candidates` invocation that
uses `--watchlist-file` pointing to the generated `session_plan.json`.

### Targeting missing regimes

When the corpus shows missing regimes (e.g. `missing=['politics', 'new_market']`),
pass `--prefer-missing-regimes` to reorder candidates so those covering a
missing regime appear first — applied before `--top` so they are actually
selected:

```bash
python -m polytool make-session-pack \
  --watchlist-file artifacts/watchlists/gate2_top20.txt \
  --prefer-missing-regimes \
  --top 2 \
  --regime sports \
  --source-manifest artifacts/gates/gate2_tape_manifest.json
```

Or target a specific missing regime with `--target-regime`:

```bash
python -m polytool make-session-pack \
  --watchlist-file artifacts/watchlists/gate2_top20.txt \
  --target-regime politics \
  --top 3 \
  --regime politics \
  --source-manifest artifacts/gates/gate2_tape_manifest.json
```

Coverage guidance is **advisory only** — it does not change Gate 2 pass
criteria and exact slugs are never altered.  If `--target-regime` finds no
matching candidates (e.g. all scan results are UNKNOWN regime with no content
signal), all candidates are included with a warning and
`coverage_intent.advances_coverage` is set to `false`.  The session will not
falsely claim to advance missing-regime coverage in this case.  The
`session_plan.json` records the coverage intent and whether the selected
slugs actually advance missing-regime coverage (`coverage_intent.advances_coverage`).

Session pack artifacts are written to `artifacts/session_packs/<session_id>/`:
- `session_watchlist.txt` — exact slugs for `--watchlist-file`
- `session_plan.json` — full context including corpus state, watch config,
  per-slug context, and a watcher-compatible `watchlist` array

After each session, fill in the `post_session_template` in `session_plan.json`
to record what happened (trigger outcome, tape eligibility, next action).

### Optional: background helper

If you want the watcher to keep running while you continue development, use the
PowerShell helper. It runs the ranked scan, creates a session pack, starts the
watcher in the background, writes watcher logs into the newest session-pack
folder, and prints the follow-up `tape-manifest` / `gate2-preflight` commands.

```powershell
.\tools\ops\run_gate2_session.ps1 `
  -Regime politics `
  -TargetRegime politics `
  -SourceManifest artifacts/gates/gate2_tape_manifest.json `
  -PackTop 3 `
  -DurationSeconds 600
```

---

## Phase 2: Watch candidates and auto-record

Identify 3–5 top slugs from Phase 1. Choose a regime label:
- `politics` — elections, referenda, geopolitical outcomes
- `sports` — NBA, NFL, NHL, soccer
- `new_market` — markets < 48 hours old

```bash
# Example: two sports markets, 10-minute tapes
python -m polytool watch-arb-candidates \
  --markets will-the-oklahoma-city-thunder-win-t will-the-toronto-maple-leafs \
  --regime sports \
  --duration 600 \
  --poll-interval 30
```

`--markets` accepts either repeated slugs (`--markets slug1 slug2`) or a single
comma-separated argument (`--markets "slug1,slug2"`).

You can also hand the session plan directly to the watcher:

```bash
python -m polytool watch-arb-candidates \
  --watchlist-file artifacts/session_packs/<session_id>/session_plan.json \
  --regime sports \
  --duration 600 \
  --poll-interval 30 \
  --near-edge 1.0 \
  --min-depth 50
```

`--watchlist-file` accepts either:
- report-style JSON with a top-level `watchlist` array
- newline-delimited slug files from `scan-gate2-candidates --watchlist-out`

Blank lines in the watchlist file are ignored.

The session-plan JSON works because it preserves the same top-level
`watchlist` array contract as existing report-style watchlists while carrying
additional planning metadata.

The watcher prints one status line per market per poll cycle:
```
[watch-arb] 14:23:15Z  will-the-oklahoma-city-thunder...  sum=0.9820  YES=120 NO=95  near_edge=Y  depth_ok=Y  *** TRIGGER
[watch-arb] *** TRIGGER: will-the-oklahoma-city-thunder... -> recording 600s to artifacts/simtrader/tapes/...
```

When `*** TRIGGER` fires, tape recording starts automatically in a background
thread. The watcher continues polling other markets.

Current watch/prep artifacts also persist an additive `market_snapshot` block
when capture-time market metadata is available. `tape-manifest` prefers that
snapshot when deriving regime and new-market context later.

Press **Ctrl+C** to stop the watcher when done.

### Alternative: one-shot orchestrated run

```bash
# Scan top 3 candidates, record 5-minute tapes, check eligibility
python -m polytool prepare-gate2 \
  --top 3 --duration 300 --regime sports
```

This runs: scan → resolve → record → check eligibility → print verdict.

---

## Phase 3: Check tape corpus

```bash
# Scan all tapes, check eligibility, emit manifest
python -m polytool tape-manifest
```

Example output:
```
Market                                      | Regime       | Status      | ExecTicks | Detail
----------------------------------------------------------------------------------------------------
will-the-oklahoma-city-thunder...           | sports       | ELIGIBLE    |        12 | artifacts/simtrader/tapes/...
bitboy-convicted_64fd7c95                   | unknown      | INELIGIBLE  |         0 | insufficient depth: ...

Total: 14  |  Eligible: 1  |  Ineligible: 13

Corpus note: PARTIAL: 1 eligible tape(s) found, but mixed-regime corpus is incomplete.
Missing eligible tapes for: politics, new_market.
```

The manifest is written to `artifacts/gates/gate2_tape_manifest.json`.

### What to look for

| Corpus note prefix | Meaning |
|-------------------|---------|
| `BLOCKED:` | No eligible tapes — Gate 2 cannot be closed yet |
| `PARTIAL:` | Eligible tapes exist but mixed-regime coverage is incomplete |
| `OK:` | All three regimes have eligible tapes — ready for Gate 3 planning |

### Regime integrity fields

Starting with manifest schema v2, each tape entry includes regime provenance:

| Field | Meaning |
|-------|---------|
| `derived_regime` | Machine-classified regime from slug/metadata; `"other"` if weak signal |
| `operator_regime` | Raw `--regime` value you entered at capture time |
| `final_regime` | Authoritative regime used for coverage counting |
| `regime_source` | `"derived"` (classifier won) \| `"operator"` (classifier weak) \| `"fallback_unknown"` |
| `regime_mismatch` | `true` when machine and operator disagree — warrants review |

**If you see `regime_mismatch: true`**: check the tape slug and compare to the operator label.
Update `watch_meta.json` if the label is wrong, then re-run `tape-manifest`.

**If you see `regime_source: "fallback_unknown"`**: the slug alone did not signal a
clear regime and you did not supply `--regime`. Re-run `tape-manifest` after
adding the correct `regime` field to `watch_meta.json`.

---

## Phase 4: Close Gate 2

Before running the sweep, use the operator-safe preflight:

```bash
python -m polytool gate2-preflight
```

Expected preflight outcomes:
- `Result: READY` -> at least one eligible tape exists and mixed-regime coverage is complete
- `Result: BLOCKED` -> sweep should not be started yet; follow the printed `Next action`

The preflight also summarizes:
- eligible tape count
- which tapes are eligible
- covered regimes
- missing regimes
- the exact next action

Only run the sweep when preflight reports `READY`:

```bash
python tools/gates/close_sweep_gate.py
```

This runs 24 scenarios (4 fee rates × 3 cancel ticks × 2 mark methods)
across the eligible tape. Gate 2 passes when `profitable_fraction >= 0.70`.

```bash
# Check gate status after sweep
python tools/gates/gate_status.py
```

Gate 2 artifact written to:
```
artifacts/gates/sweep_gate/gate_passed.json   # if passed
artifacts/gates/sweep_gate/gate_failed.json   # if failed
```

---

## Phase 5: Grow the mixed-regime corpus (for Gate 3)

Gate 3 shadow validation requires at least one shadow run per regime
(politics, sports, new_market). While Gate 2 only needs one eligible tape,
the operator should continue collecting tapes in other regimes.

```bash
# Capture a politics tape
python -m polytool watch-arb-candidates \
  --markets <politics-slug-1,politics-slug-2> \
  --regime politics \
  --duration 600

# Capture a new-market tape (market < 48h old)
python -m polytool watch-arb-candidates \
  --markets <new-market-slug> \
  --regime new_market \
  --duration 600

# Refresh the manifest
python -m polytool tape-manifest
```

---

## Failure procedures

### All tapes fail on depth

Depth failure means `min_yes_ask_size` or `min_no_ask_size` is consistently
below 50 shares.

1. Check `scan-gate2-candidates` for markets with higher `MaxDepth` values
2. Increase `--min-depth` in the watcher if needed to filter shallow markets
3. Wait for higher-volume periods (market open, pre-event)
4. Do NOT reduce `max_size` below 50 — this would weaken Gate 2

### All tapes fail on edge

Edge failure means `min_sum_ask_seen` is consistently ≥ 0.99.

1. Complement edge is rare and event-driven
2. Target markets with upcoming resolution events (game within hours,
   election night)
3. Try `--near-edge 0.995` to tighten the watch trigger and capture
   near-miss events for diagnostic purposes
4. Do NOT change the strategy buffer (0.01) — this would weaken Gate 2

### Watch loop fires no trigger

- Increase `--poll-interval 15` for faster polling
- Try `--near-edge 1.005` to fire on deeper near-miss windows (diagnostic only)
- Check `scan-gate2-candidates` live to confirm candidates still have signal

### Tape recorded but no asset IDs

The eligibility check cannot run without YES/NO asset IDs. Fix by editing
`watch_meta.json` or `prep_meta.json` in the tape directory:

```json
{
  "market_slug": "the-market-slug",
  "yes_asset_id": "103456...",
  "no_asset_id": "203456...",
  "regime": "sports"
}
```

Do not invent missing `market_snapshot` values after the fact. Leave unknown
fields absent if they were not captured.

Then re-run `python -m polytool tape-manifest`.

---

## Hard stops

- Do NOT run `close_sweep_gate.py` blindly; run `python -m polytool gate2-preflight` first
- Do NOT weaken Gate 2 pass criteria (`profitable_fraction >= 0.70`)
- Do NOT label a tape eligible unless `executable_ticks > 0` is confirmed
- Do NOT proceed to Gate 3 until Gate 2 `gate_passed.json` exists
- Do NOT begin Stage 0 until all four gates have `gate_passed.json`

---

## Reference

- `docs/specs/SPEC-0014-gate2-eligible-tape-acquisition.md` — Full specification
- `docs/specs/SPEC-0012-phase1-tracka-live-bot-program.md` — Promotion ladder
- `docs/specs/SPEC-0013-phase1-tracka-gap-matrix.md` — Gap matrix + risk ranking
- `tools/gates/shadow_gate_checklist.md` — Gate 3 procedure (after Gate 2 passes)
