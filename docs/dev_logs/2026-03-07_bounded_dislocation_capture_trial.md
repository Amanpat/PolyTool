# Bounded Dislocation Capture Trial (2026-03-07)

## Purpose

Run a short, bounded live capture loop for `binary_complement_arb` without
changing any strategy logic, thresholds, or sizing. The goal is to determine
whether catalyst-driven dislocations produce an eligible Gate 2 tape.

## Choose 3-5 markets

- Pick 3-5 binary markets tied to one clear catalyst window: breaking news,
  a live sports event, an election update, or another fast repricing event.
- Prefer markets with active books and obvious complementary YES/NO structure.
- Prefer markets you can explain in one sentence. If the catalyst is vague, the
  watch window will usually be badly timed.
- If you already have a report-derived watchlist, use
  `artifacts/watchlists/report_watchlist.json`.
- Keep the list small. The point is a focused capture trial, not broad market
  coverage.

## When to start the watcher

- Start 30-60 minutes before the expected catalyst if the event time is known.
- If the catalyst is unplanned breaking news, start the watcher immediately and
  keep it running through the first repricing window.
- Let the watcher run through the highest-volatility period, not just the first
  minute.

## Commands to run

Optional prescan:

```bash
python -m polytool scan-gate2-candidates --candidates 100 --top 30
```

Watch a report-derived watchlist:

```bash
python -m polytool watch-arb-candidates \
  --watchlist-file artifacts/watchlists/report_watchlist.json \
  --poll-interval 30 \
  --duration 300
```

Or watch explicit slugs:

```bash
python -m polytool watch-arb-candidates \
  --markets slug1,slug2,slug3 \
  --poll-interval 30 \
  --duration 300
```

Use `--dry-run` first if you want to confirm market resolution and observe live
`sum_ask` values without recording.

## Scan tapes afterward

After the watch window ends, score the tape set:

```bash
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --all
python -m polytool prepare-gate2 --tapes-dir artifacts/simtrader/tapes
```

If `prepare-gate2 --tapes-dir` finds an eligible tape, the next command is:

```bash
python tools/gates/close_sweep_gate.py
```

Do not move to Gate 3 unless Gate 2 passes cleanly.

## What counts as success

- A new tape is recorded during a real catalyst window and shows actual
  dislocation evidence (`Edge > 0` or `Exec > 0`).
- Best case: `prepare-gate2 --tapes-dir` marks a tape `ELIGIBLE`, which means
  Gate 2 can be rerun immediately.
- Even a non-eligible tape is useful if it captures a real near-edge window and
  sharpens the diagnosis.

## What counts as evidence to deprioritize the strategy

- Repeated bounded trials around obvious catalysts still produce no trigger and
  no new tapes.
- New tapes keep showing depth but zero edge ticks and zero executable ticks.
- Best observed edge stays materially below threshold across multiple catalyst
  windows, which points to an efficient market rather than a tooling problem.
- If several focused trials end the same way, treat that as evidence that the
  current `binary_complement_arb` opportunity is too scarce to prioritize right
  now.

## Scope guard

- No strategy logic changes
- No watcher logic changes
- No threshold changes
- No sizing changes
