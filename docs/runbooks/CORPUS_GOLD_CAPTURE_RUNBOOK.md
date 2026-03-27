# Corpus Gold Tape Capture Runbook

**Version:** v1.1
**Created:** 2026-03-26
**Updated:** 2026-03-27
**Status:** Active — use this when corpus_audit.py exits 1 (shortage)

---

## 0. Quick Status Check

Before anything else, check the current shortage with one command:

```
python tools/gates/capture_status.py
```

This prints a compact table showing how many tapes each bucket still needs.
Exit 0 means the corpus is already complete; exit 1 means capture is needed.

For the authoritative campaign spec and campaign loop see:
`docs/specs/SPEC-phase1b-gold-capture-campaign.md`

---

## 1. Overview

Gate 2 (market-maker scenario sweep) requires a recovery corpus of at least 50
tapes, each with >= 50 effective events, covering all five market buckets.
The `benchmark_v1` corpus is finalized and immutable; new tapes must be captured
into a separate recovery corpus.

Gold tapes are preferred over Silver because:
- They are recorded by the live shadow tape recorder (`watch_meta.json` present).
- They contain real market microstructure at tick-level fidelity.
- They have higher effective_events counts on active markets (crypto markets
  typically reach 50+ events in under 5 minutes of shadow recording).
- They are assigned a reliable bucket label at capture time.
- Silver tapes reconstruct from historical archives that may lack fill data,
  producing zero-profit price-only records that fail Gate 2 strategies.

---

## 2. Prerequisites

Before capturing any Gold shadow tapes, confirm:

1. **Docker running:**
   ```
   docker compose ps
   ```
   All services should be healthy (ClickHouse, etc.).

2. **ClickHouse accessible:**
   ```
   curl "http://localhost:8123/?query=SELECT%201"
   ```
   Should return `1`.

3. **CLICKHOUSE_PASSWORD set:**
   ```
   echo $CLICKHOUSE_PASSWORD
   ```
   Must be non-empty. Set it from your `.env` file if needed:
   ```
   export CLICKHOUSE_PASSWORD=$(grep CLICKHOUSE_PASSWORD .env | cut -d= -f2)
   ```

4. **CLI loads without error:**
   ```
   python -m polytool --help
   ```
   Should print the help text with no import errors.

5. **Know your target market slug:**
   Use `python -m polytool simtrader quickrun --list-candidates 10` or browse
   Polymarket to find active markets in the shortage buckets.

---

## 3. Determine Which Buckets Need Tapes

Run corpus_audit to get the current shortage per bucket:

```
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

Read `artifacts/corpus_audit/shortage_report.md` for exact counts needed per
bucket. The "Need" column tells you how many tapes to capture per bucket.

---

## 4. Shadow Capture Command

Capture one tape at a time. Replace `<SLUG>`, `<BUCKET>`, and the timestamp:

```
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir artifacts/simtrader/tapes/<BUCKET>_<SLUG>_<YYYYMMDDTHHMMSSZ>
```

**Required arguments:**
- `--market <SLUG>`: Polymarket market slug (e.g., `will-btc-hit-100k-by-eoy`)
- `--strategy market_maker_v1`: Use the canonical Phase 1 market maker
- `--duration 600`: 10 minutes. Minimum recommended duration to accumulate
  >= 50 effective events on any active market. **Important:** most Polymarket
  markets record YES and NO token events in the same stream (2 asset IDs).
  `effective_events = raw_events // n_asset_ids`, so binary markets need
  **>= 100 raw events** to clear the 50 effective threshold. Crypto up/down
  markets typically reach 100+ raw events in 5–10 minutes; extend to 900s
  for low-activity markets. Check the `effective_events` column in the audit
  output after capture to confirm.
- `--record-tape`: Enables tape recording (writes `events.jsonl`, `meta.json`,
  `watch_meta.json` to the tape dir)
- `--tape-dir ...`: Timestamped dir under `artifacts/simtrader/tapes/`

**Example (crypto bucket):**
```
python -m polytool simtrader shadow \
    --market will-btc-be-above-100k-on-march-28 \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir "artifacts/simtrader/tapes/crypto_will-btc-be-above-100k_20260326T210000Z"
```

**Important:** Shadow mode never submits real orders. All sessions are safe to run.

---

## 5. Post-Capture Validation

After each capture session, validate the new tape immediately:

```
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

The summary table will show the updated count for each bucket. If the new tape
is accepted, its bucket count increments. If it appears under "rejected", check
the `shortage_report.md` for the reject reason.

Common reasons a new Gold tape may still be rejected:
- `too_short`: Tape has fewer than 50 effective events. For binary markets
  (YES+NO token pair), `effective = raw_events // 2`, so you need **>= 100
  raw events**. Recapture with longer `--duration` (900s+ for slow markets).
  Run `python -c "from tools.gates.mm_sweep import _count_effective_events;
  import pathlib; print(_count_effective_events(pathlib.Path('TAPE_DIR/events.jsonl')))"`
  to check a tape's raw/asset/effective breakdown before auditing.
- `no_bucket_label`: `watch_meta.json` is missing the `bucket` field. This should
  not happen for tapes captured with `--tape-dir` that encodes the bucket prefix,
  but you can add it manually to `watch_meta.json` if needed.

---

## 6. Resumability

Corpus audit always scans all roots and recomputes from scratch — it is safe to
run after every new tape session. Each shadow session writes to a new timestamped
tape dir, so re-running never overwrites existing tapes.

Workflow for iterative capture:
1. Run corpus_audit → read shortage_report.md.
2. Capture one or more tapes for the highest-shortage bucket.
3. Run corpus_audit again → see updated counts.
4. Repeat until corpus_audit exits 0.

---

## 7. Bucket Targeting Guide

Map Polymarket market categories to the five corpus buckets:

| Corpus Bucket    | Polymarket Market Types | Examples |
|------------------|-------------------------|---------|
| `crypto`         | BTC/ETH/SOL/XRP up/down binary markets (5m, 15m, 1h) | `will-btc-be-above-X-on-Y`, `will-eth-hit-X-by-Y` |
| `sports`         | NHL, NBA, NFL, soccer match markets | `will-team-A-beat-team-B`, `nhl-stanley-cup-winner` |
| `politics`       | US elections, international elections, policy outcomes | `will-X-win-the-presidential-election`, `will-Y-pass` |
| `near_resolution`| Any market within 48h of its resolution date | Markets expiring within the next 2 days |
| `new_market`     | Recently listed markets (< 7 days old) | Newly appeared markets on Polymarket front page |

**Recommended capture priorities:** Run `python tools/gates/capture_status.py`
to see current counts — hard-coded numbers from any prior date will drift as
tapes are captured. The tool shows exactly how many are needed per bucket.

General priority guidance (capture the highest "Need" bucket first):
1. `sports`: Best captured during evening/weekend when NHL, NBA, or soccer
   matches are live (highest event activity).
2. `politics`: US political markets or international elections.
3. `crypto`: BTC/ETH/SOL 5m up/down pairs. Note: these markets rotate daily
   on Polymarket. Use `crypto-pair-watch --watch` to detect when they appear.
4. `new_market`: Browse Polymarket for newly listed markets.
5. `near_resolution`: Any market within 48h of resolution.

---

## 8. Stopping Condition

Run `corpus_audit.py` after each batch of new tapes. Continue until the tool
reports:

```
Verdict: QUALIFIED (exit 0)
```

At that point, `config/recovery_corpus_v1.tape_manifest` will have been written.
Proceed to Gate 2 rerun:

```
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```

Then check the result:
```
python tools/gates/gate_status.py
```

If `mm_sweep_gate` shows PASSED: Gate 2 is cleared; proceed to Gate 3 shadow
validation per `docs/runbooks/GATE3_SHADOW_RUNBOOK.md`.

If `mm_sweep_gate` shows FAILED: The strategy did not achieve >= 70% positive
net PnL. Review `artifacts/gates/mm_sweep_gate/gate_summary.md` for per-tape
breakdown, then investigate strategy parameters or market selection.

---

## 9. No Live Capital

Shadow mode (`--strategy market_maker_v1` with `--record-tape`) **never submits
real orders**. All shadow sessions are safe to run at any time. No funds are at
risk during corpus capture.

Live capital is only involved in Stage 0 and Stage 1, which require Gate 2 and
Gate 3 to be PASSED first. Do not attempt live trading before these gates clear.

---

## Reference

- Campaign spec: `docs/specs/SPEC-phase1b-gold-capture-campaign.md`
- Quick status: `tools/gates/capture_status.py`
- Corpus contract spec: `docs/specs/SPEC-phase1b-corpus-recovery-v1.md`
- Audit tool: `tools/gates/corpus_audit.py`
- Shortage report: `artifacts/corpus_audit/shortage_report.md`
- Gate 2 rerun: `tools/gates/close_mm_sweep_gate.py`
- Gate 3 runbook: `docs/runbooks/GATE3_SHADOW_RUNBOOK.md`
