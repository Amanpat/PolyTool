# Dislocation Watch + Auto-Record (2026-03-07)

## Summary

Built a minimal event-driven dislocation watch and auto-record workflow for
`binary_complement_arb` candidates. The tool polls a user-specified market
watchlist, evaluates a configurable near-edge trigger, and automatically starts
tape recording when the trigger fires.

This is intentionally smaller than an Opportunity Radar. It is diagnostic
capture infrastructure, not a trading signal platform.

---

## Context

After 12 recorded tapes (including 3 fresh 5-minute tapes on 2026-03-07):
- 0 executable ticks across all tapes
- 0 edge ticks across all tapes
- Binding constraint: `yes_ask + no_ask < 0.99` never occurred
- Minimum observed sum_ask: 1.001 (1.1 cents above the 0.99 threshold)

The standard `prepare-gate2` workflow records tapes reactively after a manual
scan. Because dislocations are transient (minutes-long windows around news
events), the operator needs to be watching the right markets *before* the
dislocation appears, not scanning after the fact.

---

## Files Changed

### New files

| File | Purpose |
|---|---|
| `tools/cli/watch_arb_candidates.py` | Main watch + auto-record CLI tool |
| `tests/test_watch_arb_candidates.py` | 21 focused unit tests |
| `docs/dev_logs/2026-03-07_dislocation_watch_recorder.md` | This document |

### Modified files

| File | Change |
|---|---|
| `polytool/__main__.py` | Import + route `watch-arb-candidates` command |

---

## CLI / Command Added

```
python -m polytool watch-arb-candidates --markets <slug1,slug2,...> [options]
```

### Key options

| Option | Default | Purpose |
|---|---|---|
| `--markets` | (required) | Comma-separated market slugs to watch |
| `--near-edge` | `1.00` | Trigger when `sum_ask < this` (looser than strategy entry 0.99) |
| `--min-depth` | `50` | Required best-ask size per leg in shares |
| `--poll-interval` | `30` | Seconds between CLOB polls per market |
| `--duration` | `300` | Recording duration per triggered market (seconds) |
| `--max-concurrent` | `2` | Max simultaneously recording markets |
| `--tapes-base-dir` | `artifacts/simtrader/tapes` | Where to write tapes |
| `--dry-run` | off | Evaluate triggers + print status without recording |

### Sample operator usage

```bash
# Watch two NHL playoff markets, trigger if sum_ask drops below 1.00:
python -m polytool watch-arb-candidates \
  --markets will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup,will-the-vancouver-canucks-win-the-2026-nhl-stanley-cup

# Tighter trigger (only capture if very close to the strategy entry threshold):
python -m polytool watch-arb-candidates \
  --markets will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup \
  --near-edge 0.995

# Dry-run to verify market resolution and observe live sum_ask values:
python -m polytool watch-arb-candidates \
  --markets will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup \
  --dry-run

# Watch 5 markets, poll every 15 seconds, record for 10 minutes on trigger:
python -m polytool watch-arb-candidates \
  --markets slug1,slug2,slug3,slug4,slug5 \
  --poll-interval 15 --duration 600
```

### Sample output

```
[watch-arb] Watching 2 market(s)  near_edge_threshold=1.0000  min_depth=50 shares  poll_interval=30s  record_duration=300s
[watch-arb] Strategy entry threshold: sum_ask < 0.9900  (near-edge trigger is LOOSER — captures near-miss conditions)
[watch-arb] Press Ctrl+C to stop.

  will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup
    YES: 32761305560497515...
    NO:  30580289066077385...

[watch-arb] 20:15:00Z  will-the-toronto-maple-leafs-win...  sum=1.0010  YES=130961 NO=11924  near_edge=N  depth_ok=Y
[watch-arb] 20:15:30Z  will-the-toronto-maple-leafs-win...  sum=0.9950  YES=45000  NO=12000  near_edge=Y  depth_ok=Y  *** TRIGGER
[watch-arb] *** TRIGGER: will-the-toronto-maple-leafs-win...  -> recording 300s to artifacts/simtrader/tapes/20260307T201530Z_watch_will-the-toronto-map
```

---

## Trigger Logic

The near-edge trigger fires when **both** conditions hold simultaneously:

1. **Near-edge**: `yes_ask + no_ask < near_edge_threshold`
   - Default threshold: `1.00`
   - Strategy entry threshold (unchanged): `0.99`
   - The watch trigger is intentionally looser to capture near-miss conditions
     before they either reach the strategy entry threshold or dissipate

2. **Sufficient depth**: `yes_ask_size >= min_depth AND no_ask_size >= min_depth`
   - Default: `50` shares per leg (matches the `sane` preset `max_size`)

When the trigger fires, a background recording thread starts for that market.
The poll loop continues monitoring other markets during recording.

**Nothing about the trigger changes strategy logic.** The `0.99` strategy entry
threshold, `max_size=50` preset sizing, and gate criteria are untouched.

### Why the trigger is looser than the strategy threshold

The strategy requires `sum_ask < 0.99`. The current market environment shows
`sum_ask >= 1.001` at all observed ticks. If the watch trigger were set to `0.99`
(identical to the strategy), it would never fire except at the exact moment the
strategy would enter — too late to have a useful tape.

Setting the trigger at `1.00` captures the lead-up to a dislocation: the tape
records from before the arb window opens, through the window, and after it
closes. This is the data we need to verify the strategy works in a real event.

---

## Architecture

```
watch_arb_candidates.py
├── evaluate_trigger()         Pure function: WatchSnapshot from ask levels
├── ResolvedWatch              Dataclass: slug + YES/NO token IDs
├── WatchSnapshot              Dataclass: snapshot evaluation result
├── _resolve_market()          Reuses MarketPicker.resolve_slug()
├── _fetch_books()             Reuses ClobClient.fetch_book()
├── _record_tape_for_market()  Reuses TapeRecorder (same as prepare_gate2)
└── ArbWatcher                 Poll loop + threading + trigger dispatch
    ├── run()                  Main blocking loop (Ctrl+C to exit)
    ├── _poll_round()          One pass over all watched markets
    └── _start_recording()     Launch background thread, track in-flight set
```

All production components are reused:
- Market resolution: `packages.polymarket.simtrader.market_picker.MarketPicker`
- Book fetching: `packages.polymarket.clob.ClobClient`
- Trigger scoring: `tools.cli.scan_gate2_candidates._best_ask_price_and_size`
- Recording: `packages.polymarket.simtrader.tape.recorder.TapeRecorder`

The tape format written by `watch-arb-candidates` is identical to tapes written
by `prepare-gate2`. Both can be scored with `scan-gate2-candidates --tapes-dir`
and checked with `prepare-gate2 --tapes-dir`.

### watch_meta.json

Each triggered tape directory contains a `watch_meta.json` (analogous to
`prep_meta.json` from `prepare_gate2`):

```json
{
  "market_slug": "will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup",
  "yes_asset_id": "327613055604975152...",
  "no_asset_id": "305802890660773857...",
  "triggered_by": "watch-arb-candidates"
}
```

This allows `prepare-gate2 --tapes-dir` to find YES/NO asset IDs without
re-resolving the market.

---

## Tests Run

```
tests/test_watch_arb_candidates.py  21/21 PASSED
```

### Test coverage

| Test | What it verifies |
|---|---|
| `test_fires_on_near_edge_and_sufficient_depth` | Trigger fires: near_edge + depth_ok |
| `test_fires_at_sum_just_below_threshold` | sum=0.999 < 1.00 fires |
| `test_does_not_fire_on_non_edge_market` | sum=1.01: depth_ok but no trigger |
| `test_does_not_fire_on_near_edge_but_insufficient_depth` | sum=0.99 but YES size=10 |
| `test_does_not_fire_when_no_bbo` | Empty YES book: no trigger |
| `test_does_not_fire_when_both_books_empty` | Both books empty |
| `test_at_exact_threshold_does_not_fire` | sum=1.00 exactly (strict less-than) |
| `test_strategy_threshold_is_not_changed` | sum=0.995 fires watch (>0.99 strategy) |
| `test_near_edge_threshold_configurable` | sum=0.999 does not fire at threshold=0.995 |
| `test_recorder_called_with_correct_resolved_market` | Recorder gets correct slug + token IDs |
| `test_recorder_not_called_when_no_trigger` | Non-edge market: no recording |
| `test_recorder_not_called_on_insufficient_depth` | Shallow book: no recording |
| `test_recorder_not_called_in_dry_run` | Dry-run suppresses recording |
| `test_recorder_not_called_when_max_concurrent_reached` | Concurrency cap enforced |
| `test_already_recording_market_skips_poll` | In-flight market not polled |
| `test_recorder_releases_lock_after_completion` | Slug removed from in-flight set after record |
| `test_rejects_invalid_near_edge` | CLI validation: near_edge=0 rejected |
| `test_rejects_invalid_min_depth` | CLI validation: min_depth=-1 rejected |
| `test_rejects_empty_markets` | CLI validation: --markets=,,, rejected |
| `test_resolve_failure_skips_market_and_returns_error_when_all_fail` | All-fail → exit code 1 |
| `test_dry_run_succeeds_with_resolved_markets` | Trigger printed, no recording in dry-run |

---

## Why This Is Smaller Than Opportunity Radar

The ROADMAP defers the Opportunity Radar to after the first clean Gate 2 → Gate 3
progression. This tool does not implement:

- Automatic market discovery (the operator supplies the watchlist)
- Relevance scoring or ranking of watched markets
- Integration with dossiers, bundles, or LLM reports
- Notifications (Slack, email, desktop alerts)
- A persistent background daemon or service
- Historical scan-and-rank across the full Polymarket universe

What it does instead:

- Takes an explicit operator-provided watchlist
- Watches selected markets around a known catalyst event
- Triggers on operator-configured conditions
- Writes a tape in the standard format for downstream scoring

The operator workflow is:
1. Identify a catalyst (sports event, election result, news)
2. Build a watchlist of binary markets likely to be affected
3. Run `watch-arb-candidates --markets ...` 30-60 minutes before the event
4. Tapes are automatically recorded if a near-edge condition appears
5. Score tapes with `scan-gate2-candidates --tapes-dir` after collection

---

## No Strategy Logic Changes

- Strategy entry threshold (`0.99`) unchanged
- Preset sizing (`max_size=50`, `buffer=0.01`) unchanged
- Gate rules unchanged
- `binary_complement_arb` strategy code unchanged
- `eligibility.py` unchanged
- `prepare_gate2.py` unchanged
