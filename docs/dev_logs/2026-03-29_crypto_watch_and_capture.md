# Dev Log: Crypto Watch, Shadow Capture, and Gate 2 Run

**Date:** 2026-03-29
**Plan:** quick-045 Task 3 Branch B (proceed-capture)
**Status:** COMPLETE — Gate 2 FAILED (7/50 positive, 14%; threshold 70%)

---

## Summary

Waited for crypto markets to reappear (they did, in the morning of 2026-03-29),
captured 14 shadow sessions, fixed a path drift issue, built recovery corpus
manifest at 50/50, created a new recovery corpus sweep driver to bypass manifest
format incompatibility, and ran Gate 2 against the full 50-tape corpus.

Gate 2 result: **FAILED** — 7/50 tapes positive (14%), well below the 70% threshold.
The market maker strategy requires further calibration or parameter work before Gate 2
can pass. Gate 3 remains blocked.

---

## Step-by-Step Record

### B1: Crypto markets confirmed active

Command run (from prior session):
```
python -m polytool crypto-pair-watch --one-shot
```
Result: BTC, ETH, SOL 5m markets detected. Proceeded to capture.

### B2: Shadow capture sessions

14 shadow sessions captured throughout 2026-03-29 morning:
- 5x BTC 5m updown markets (btc-updown-5m-*)
- 5x ETH 5m updown markets (eth-updown-5m-*)
- 4x SOL 5m updown markets (sol-updown-5m-*)

Shadow sessions landed in `artifacts/simtrader/tapes/` due to path drift (see B3).

### B3: Path drift fix

`DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")` in simtrader CLI caused shadow
tapes to land in `artifacts/simtrader/tapes/` instead of canonical `artifacts/tapes/shadow/`.

Fix: moved all 14 dirs using Python `shutil.move`:
```python
import shutil, os
src = "artifacts/simtrader/tapes"
dst = "artifacts/tapes/shadow"
for d in os.listdir(src):
    shutil.move(os.path.join(src, d), os.path.join(dst, d))
```

After move: 14 crypto tape dirs now in `artifacts/tapes/shadow/20260329T*`.
Each dir contains: `events.jsonl`, `meta.json`, `raw_ws.jsonl`.

### B4: Bucket label injection

`corpus_audit.py` requires a bucket label to classify each tape. Shadow crypto tapes
had no `watch_meta.json` file to provide it. Injected `{"bucket": "crypto"}` into
`watch_meta.json` for all 14 crypto tape dirs:

```
artifacts/tapes/shadow/20260329T072654Z_shadow_btc-updown-5m-1774769100_5dc97865/watch_meta.json
artifacts/tapes/shadow/20260329T075706Z_shadow_btc-updown-5m-1774770900_c6d6239f/watch_meta.json
artifacts/tapes/shadow/20260329T074302Z_shadow_btc-updown-5m-1774770000_58cfc565/watch_meta.json
artifacts/tapes/shadow/20260329T071135Z_shadow_btc-updown-5m-1774768200_978c735c/watch_meta.json
artifacts/tapes/shadow/20260329T081159Z_shadow_btc-updown-5m-1774771800_47588a18/watch_meta.json
artifacts/tapes/shadow/20260329T073214Z_shadow_eth-updown-5m-1774769400_f115dd6f/watch_meta.json
artifacts/tapes/shadow/20260329T080222Z_shadow_eth-updown-5m-1774771200_d475af7e/watch_meta.json
artifacts/tapes/shadow/20260329T072148Z_shadow_sol-updown-5m-1774768800_a86c6cd9/watch_meta.json
artifacts/tapes/shadow/20260329T080713Z_shadow_sol-updown-5m-1774771500_ad2e61a7/watch_meta.json
artifacts/tapes/shadow/20260329T073734Z_shadow_sol-updown-5m-1774769700_885e7214/watch_meta.json
```
(4 additional crypto dirs for remaining BTC/ETH/SOL sessions)

### B4: corpus_audit run

```
python tools/gates/corpus_audit.py \
  --manifest config/recovery_corpus_v1.tape_manifest \
  --require-50 \
  --out-manifest config/recovery_corpus_v1.tape_manifest
```

Second run result (after watch_meta.json injection):
```
QUALIFIED: 50/50 tapes
  politics:        10/10
  sports:          15/15
  crypto:          10/10
  near_resolution: 10/10
  new_market:       5/5
Exit code: 0
```

Manifest written to: `config/recovery_corpus_v1.tape_manifest` (JSON list, 50 entries).

### B5: Gate 2 sweep — manifest format mismatch

Initial attempt: `python tools/gates/close_mm_sweep_gate.py --manifest config/recovery_corpus_v1.tape_manifest`
Result: NOT_RUN — `close_mm_sweep_gate.py --manifest` expects dict-format `gate2_tape_manifest.json`,
not the corpus_audit list format. `_load_gate2_manifest_index` returned `{}` for list input,
causing the sweep to walk only `artifacts/tapes/gold/` (3 old NHL tapes, all too short).

Second attempt: `--benchmark-manifest` flag.
Result: FAILED — `validate_benchmark_manifest` rejects recovery corpus because tapes lack
proper `market_meta["benchmark_bucket"]` and `select_manifest` fails quota checks.

Resolution: Created `tools/gates/run_recovery_corpus_sweep.py` — a recovery-specific sweep
driver that:
1. Reads the corpus_audit list manifest directly
2. Calls `_build_tape_candidate(..., require_selected=False)` for each tape
3. Replicates the mm_sweep inner loop with [XX/50] progress output
4. Writes gate result to `artifacts/gates/mm_sweep_gate/`

### B5: Gate 2 sweep execution

```
python tools/gates/run_recovery_corpus_sweep.py \
  --manifest config/recovery_corpus_v1.tape_manifest \
  --out artifacts/gates/mm_sweep_gate \
  --threshold 0.70
```

Runtime: approximately 3 hours (crypto tapes 41-50 each have 20k-24k events).

Full sweep output (condensed — per-tape BUY/SELL reservation warnings omitted):

```
Recovery corpus sweep
  manifest : D:\Coding Projects\Polymarket\PolyTool\config\recovery_corpus_v1.tape_manifest
  threshold: 70%
  min-events: 50
  Recovery corpus: 50 tapes loaded, 0 skipped

  [01/50] 20260328T212103Z_shadow_elon-musk-of-tweets-march-28-ma ... RAN net=-1.99 positive=False
  [02/50] 2026-03-15T10-00-01Z ... RAN net=n/a positive=False
  [03/50] 2026-03-15T10-00-28Z ... RAN net=n/a positive=False
  [04/50] 2026-03-15T10-00-28Z ... RAN net=n/a positive=False
  [05/50] 2026-03-15T10-00-04Z ... RAN net=n/a positive=False
  [06/50] 2026-03-15T10-00-24Z ... RAN net=n/a positive=False
  [07/50] 2026-03-15T10-00-02Z ... RAN net=n/a positive=False
  [08/50] 2026-03-15T10-00-07Z ... RAN net=n/a positive=False
  [09/50] 2026-03-15T10-00-56Z ... RAN net=n/a positive=False
  [10/50] 2026-03-15T10-00-02Z ... RAN net=n/a positive=False
  [11/50] 20260329T040958Z_shadow_will-a-different-combination-of ... RAN net=n/a positive=False
  [12/50] 20260329T034800Z_shadow_will-jd-vance-talk-to-iranian-n ... RAN net=n/a positive=False
  [13/50] 20260328T223857Z_shadow_will-daniel-mercuri-win-the-cal ... RAN net=-2.92 positive=False
  [14/50] 20260328T212124Z_shadow_will-jon-stewart-win-the-2028-d ... RAN net=n/a positive=False
  [15/50] 20260328T210509Z_shadow_will-jb-pritzker-win-the-2028-u ... RAN net=n/a positive=False
  [16/50] 20260327T181917Z_shadow_will-harvey-weinstein-be-senten ... RAN net=n/a positive=False
  [17/50] 20260328T210513Z_shadow_will-jb-pritzker-win-the-2028-u ... RAN net=n/a positive=False
  [18/50] 20260329T043351Z_shadow_will-russia-capture-kostyantyni ... RAN net=n/a positive=False
  [19/50] 20260226T181825Z_shadow_10167699 ... RAN net=n/a positive=False
  [20/50] 20260329T043352Z_shadow_will-russia-capture-lyman-by-ju ... RAN net=n/a positive=False
  [21/50] 20260329T020027Z_shadow_fif-col-fra-2026-03-29-draw_b1d ... RAN net=n/a positive=False
  [22/50] 20260329T034800Z_shadow_will-duke-win-the-2026-ncaa-tou ... RAN net=n/a positive=False
  [23/50] 20260328T212034Z_shadow_will-iowa-win-the-2026-ncaa-tou ... RAN net=n/a positive=False
  [24/50] 20260329T021547Z_shadow_fif-lit-geo-2026-03-29-lit_dc98 ... RAN net=n/a positive=False
  [25/50] 20260328T210450Z_shadow_will-the-tampa-bay-lightning-wi ... RAN net=n/a positive=False
  [26/50] 20260328T210502Z_shadow_will-england-win-the-2026-fifa- ... RAN net=n/a positive=False
  [27/50] 20260329T030407Z_shadow_j2100-mon-tsc-2026-03-29-mon_10 ... RAN net=n/a positive=False
  [28/50] 20260328T212038Z_shadow_will-duke-win-the-2026-ncaa-tou ... RAN net=n/a positive=False
  [29/50] 20260328T212009Z_shadow_will-manchester-city-win-the-20 ... RAN net=n/a positive=False
  [30/50] 20260328T223857Z_shadow_nba-2025-26-rpg-leader-kel-el-w ... RAN net=-6.21 positive=False
  [31/50] 20260328T220004Z_shadow_nba-2025-26-most-improved-playe ... RAN net=n/a positive=False
  [32/50] 20260328T213449Z_shadow_will-the-miami-heat-make-the-nb ... RAN net=n/a positive=False
  [33/50] 20260328T220003Z_shadow_nba-2025-26-apg-leader-trae-you ... RAN net=-5.18 positive=False
  [34/50] 20260328T213449Z_shadow_will-max-verstappen-be-the-2026 ... RAN net=n/a positive=False
  [35/50] 20260329T032005Z_shadow_j2100-tok-koc-2026-03-29-tok_18 ... RAN net=n/a positive=False
  [36/50] 20260329T034641Z_shadow_highest-temperature-in-wellingt ... RAN net=-7.04 positive=False
  [37/50] 20260329T040912Z_shadow_highest-temperature-in-miami-on ... RAN net=-2.42 positive=False
  [38/50] 20260329T041225Z_shadow_highest-temperature-in-hong-kon ... RAN net=n/a positive=False
  [39/50] 20260329T040958Z_shadow_highest-temperature-in-hong-kon ... RAN net=n/a positive=False
  [40/50] 20260329T034641Z_shadow_highest-temperature-in-chicago- ... RAN net=-17.60 positive=False
  [41/50] 20260329T072654Z_shadow_btc-updown-5m-1774769100_5dc978 ... RAN net=+35.54 positive=True
  [42/50] 20260329T075706Z_shadow_btc-updown-5m-1774770900_c6d623 ... RAN net=+8.79 positive=True
  [43/50] 20260329T074302Z_shadow_btc-updown-5m-1774770000_58cfc5 ... RAN net=+5.93 positive=True
  [44/50] 20260329T071135Z_shadow_btc-updown-5m-1774768200_978c73 ... RAN net=+4.67 positive=True
  [45/50] 20260329T081159Z_shadow_btc-updown-5m-1774771800_47588a ... RAN net=-19.90 positive=False
  [46/50] 20260329T073214Z_shadow_eth-updown-5m-1774769400_f115dd ... RAN net=+297.25 positive=True
  [47/50] 20260329T080222Z_shadow_eth-updown-5m-1774771200_d475af ... RAN net=+99.81 positive=True
  [48/50] 20260329T072148Z_shadow_sol-updown-5m-1774768800_a86c6c ... RAN net=-492.34 positive=False
  [49/50] 20260329T080713Z_shadow_sol-updown-5m-1774771500_ad2e61 ... RAN net=-34.59 positive=False
  [50/50] 20260329T073734Z_shadow_sol-updown-5m-1774769700_885e72 ... RAN net=+183.48 positive=True

MM Sweep Summary
========================================================================================
Positive tapes: 7/50  pass_rate=14.0%  threshold=70%  gate=FAIL
Artifact: artifacts\gates\mm_sweep_gate\gate_failed.json
```

### B6: gate_status.py output

```
Gate Status Report  [2026-03-29 12:44 UTC]
======================================================================================================================
Gate                                          Status    Timestamp                   Notes
----------------------------------------------------------------------------------------------------------------------
Gate 1 - Replay Determinism                   [PASSED]    2026-03-06 04:44:35         commit 4f5f8c2
Gate 2 - Scenario Sweep (>=70% profitable)    [FAILED]    2026-03-06 00:36:25
Gate 3 - Shadow Mode (manual)                 [MISSING]   -                           No artifact found
Gate 4 - Dry-Run Live                         [PASSED]    2026-03-05 21:50:10         submitted=0, dry_run=true
mm_sweep_gate (Gate 2b optional)              [FAILED]    2026-03-29 12:32:30         7/50 positive tapes (14%)
----------------------------------------------------------------------------------------------------------------------

Extra gate dirs (not in registry): ['gate2_sweep', 'gate3_shadow', 'manifests']

Result: ONE OR MORE REQUIRED GATES NOT PASSED - do not promote to Stage 1 capital.
```

---

## Gate 2 Result Analysis

**Outcome: FAILED** — 7/50 positive (14%), need 70% (35/50).

**Positive tapes (7):**
- btc-updown-5m-1774769100: +35.54
- btc-updown-5m-1774770900: +8.79
- btc-updown-5m-1774770000: +5.93
- btc-updown-5m-1774768200: +4.67
- eth-updown-5m-1774769400: +297.25
- eth-updown-5m-1774771200: +99.81
- sol-updown-5m-1774769700: +183.48

All 7 positives are crypto 5m tapes. All 9 silver tapes returned net=n/a (zero fills — expected,
as silver tapes are reconstructed and lack the tick density for MM fills). All 31 shadow
non-crypto tapes returned negative or n/a.

**Root cause observations:**
1. Silver tapes (tapes 2-10): zero fills → net=n/a. Silver reconstruction lacks the order book
   depth/ticks needed to trigger MM fills. These tapes are structurally unsuitable for the
   `market_maker_v1` sweep.
2. Shadow non-crypto tapes (tapes 11-40): mostly negative or zero. Low tick rates on
   politics/sports/near_resolution markets mean the MM spreads are not being crossed frequently
   enough to generate positive PnL over a 5-minute session.
3. Crypto tapes (tapes 41-50): 7/10 positive (70%). The crypto 5m markets have the tick density
   and spread crossing frequency the MM strategy needs. The 3 negatives (btc-1774771800,
   sol-1774768800, sol-1774771500) reflect adverse sessions.

**Implication:** The `market_maker_v1` strategy works on high-frequency crypto markets but not
on lower-frequency politics/sports/binary markets. The 50-tape corpus includes 40 non-crypto
tapes that the strategy cannot profit from, dragging the pass rate to 14%.

**Path forward:**
- Option A: Run Gate 2 against crypto-only subset (10 tapes, 7/10 = 70% pass). This would
  mean redefining the gate corpus to crypto markets only, which is a scoping decision for
  the operator.
- Option B: Improve strategy calibration to capture PnL on lower-frequency markets.
- Option C: Accept FAIL and focus on Phase 1A crypto pair bot path (Track 2) which does not
  depend on Gate 2.

---

## Files Created / Modified

- `config/recovery_corpus_v1.tape_manifest` — new, 50-entry JSON list manifest
- `tools/gates/run_recovery_corpus_sweep.py` — new, recovery corpus sweep driver
- `artifacts/tapes/shadow/20260329T*/watch_meta.json` — injected bucket labels (gitignored)
- `artifacts/gates/mm_sweep_gate/gate_failed.json` — gate result artifact (gitignored)

---

## Open Questions / Blockers

1. Gate 2 pass on crypto-only vs. full mixed corpus — operator decision needed.
2. Silver tapes produce zero fills in MM sweep — investigate if silver tape format is
   compatible with `market_maker_v1`, or exclude them from future corpus definitions.
3. SOL tapes showed large negative PnL (-492, -35) — adverse selection is high for SOL
   5m markets. Strategy may need tighter adverse selection thresholds for SOL.
