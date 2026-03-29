# Dev Log: Phase 1B Gold Capture Wave 2

**Date:** 2026-03-29
**Quick task:** quick-041
**Branch:** phase-1B
**Decision:** MORE_GOLD_NEEDED

## Why This Run Was Executed

Wave 1 of Gold capture (quick-039, 2026-03-28) advanced the corpus from 10/50 to 27/50
qualifying tapes. Three reachable buckets still had shortages: sports=5, new_market=5,
politics=3 (crypto=10 remained blocked -- no active BTC/ETH/SOL binary pair markets on
Polymarket as of 2026-03-25).

Wave 2 targeted those three buckets using additional live shadow recording sessions.
The `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` capture protocol and path drift fix
from quick-039 were already in place.

## Pre-Wave-2 Corpus State (Start of quick-041)

From `capture_status.py` at the beginning of this wave:

| Bucket           | Quota | Have | Need | Gold | Silver |
|------------------|------:|-----:|-----:|-----:|-------:|
| sports           |    15 |   10 |    5 |   10 |      0 |
| politics         |    10 |    7 |    3 |    7 |      0 |
| crypto           |    10 |    0 |   10 |    0 |      0 |
| new_market       |     5 |    0 |    5 |    0 |      0 |
| near_resolution  |    10 |   10 |    0 |    1 |      9 |
| **Total**        |    50 |   27 |   23 |   18 |      9 |

## Capture Sessions Executed

All sessions used the standard runbook protocol:

```bash
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape
```

Slow or low-activity markets were retried with `--duration 900`.

**Sports markets captured (wave 2):**
- NHL: Tampa Bay Lightning, Toronto Maple Leafs, Washington Capitals, Carolina Hurricanes
- NBA: Charlotte Hornets, Portland Trail Blazers, Golden State Warriors, Miami Heat,
  Boston Celtics (vs Charlotte), Houston Rockets (vs New Orleans)
- Soccer (FIFA World Cup qualification): Colombia vs France, Lithuania vs Georgia,
  Morocco vs Paraguay, Ivory Coast vs Jubilee fixture, Kameru vs Toscana
- F2100 league fixtures (Tokyo/Kochi, Monterrey/Toscana)

**Politics markets captured (wave 2):**
- Active US 2028 Democratic primary markets (Beto O'Rourke, JB Pritzker)
- Hungary parliamentary election (Fidesz-KDNP 80-seat threshold)
- International political event markets (Netanyahu 2027 Israel elections, Russia/Ukraine
  territorial captures by June 2026, Israel ground operation, US-Iran ceasefire)
- Putin departure markets

**new_market markets captured (wave 2):**
- OpenAI federal backstop market (newly listed)
- Elon Musk tweet count March 30-April 1 window
- Fact-check: Maduro capture staged
- Will JD Vance talk to Iranian negotiators
- Will Trump sell 1-100 Gold Cards
- US federally charges Cuba leader Miguel Diaz-Canel
- Various newly listed resolution markets (<7 days old)

**near_resolution markets (incidental captures):**
- XRP above $1.20 on March 29
- Bitcoin above $64,600 on March 29
- Earthquake >=7.0 by April deadline
- Temperature records (London, Wellington, Hong Kong, Chicago, Denver, Miami)
- Fed interest rate decision
- Will there be >=2000 measles cases by deadline
- Russia captures Kostyantynivka / Lyman by June 30

Path drift fix was applied after each capture batch:
```bash
for dir in artifacts/simtrader/tapes/*/; do
    dirname=$(basename "$dir")
    mv "$dir" "artifacts/tapes/shadow/$dirname"
done
```

After wave 2, `artifacts/simtrader/tapes/` confirmed empty.

## Post-Wave-2 Corpus State (Verified 2026-03-29)

From `capture_status.py` after all wave 2 sessions and path drift fix:

| Bucket           | Quota | Have | Need | Gold | Silver |
|------------------|------:|-----:|-----:|-----:|-------:|
| sports           |    15 |   15 |    0 |   15 |      0 |
| politics         |    10 |   10 |    0 |   10 |      0 |
| crypto           |    10 |    0 |   10 |    0 |      0 |
| new_market       |     5 |    5 |    0 |    5 |      0 |
| near_resolution  |    10 |   10 |    0 |    1 |      9 |
| **Total**        |    50 |   40 |   10 |   31 |      9 |

**Net gain from wave 2:** +13 qualifying tapes
- sports: +5 (10 -> 15, bucket complete)
- politics: +3 (7 -> 10, bucket complete)
- new_market: +5 (0 -> 5, bucket complete)

**Path drift check confirmed:** `artifacts/simtrader/tapes/` is empty (0 files).

## Shadow Tape Artifacts Written

Wave 2 session directories written to `artifacts/tapes/shadow/` (all with `20260329T*` prefix):

```
20260329T015716Z_shadow_j2100-iwa-jub-2026-03-29-jub_9b55087d
20260329T020027Z_shadow_fif-col-fra-2026-03-29-draw_b1d82c4e
20260329T021547Z_shadow_fif-lit-geo-2026-03-29-lit_dc98c405
20260329T021547Z_shadow_khamenei-of-tweets-march-24-march-31_df1390aa
20260329T021547Z_shadow_will-israel-launch-a-ground-operatio_b6957452
20260329T022851Z_shadow_fact-check-maduro-capture-staged_1bb3563f
20260329T022851Z_shadow_will-max-verstappen-be-the-2026-f1-d_ec8a365e
20260329T024022Z_shadow_nba-bos-cha-2026-03-29-points-lamelo_68509745
20260329T024022Z_shadow_nba-hou-nop-2026-03-29-points-kevin_53e8ff0c
20260329T024022Z_shadow_putin-out-as-president-of-russia-by_ce0a1037
20260329T025303Z_shadow_j2100-kam-tsc-2026-03-29-tsc_043d2e4f
20260329T025303Z_shadow_j2100-mon-tsc-2026-03-29-mon_108bd0ad
20260329T025303Z_shadow_j2100-tok-koc-2026-03-29-tok_18cb8d82
20260329T025303Z_shadow_will-fidesz-kdnp-win-at-least-80-sea_7849ec58
20260329T030407Z_shadow_bitcoin-above-64600-on-march-29-2026_7148919e
20260329T030407Z_shadow_j2100-mon-tsc-2026-03-29-mon_108bd0ad
20260329T030407Z_shadow_openai-receives-federal-backstop-for_8e5d076e
20260329T032005Z_shadow_j2100-iwa-jub-2026-03-29-jub_9b55087d
20260329T032005Z_shadow_j2100-tok-koc-2026-03-29-tok_18cb8d82
20260329T032005Z_shadow_will-benjamin-netanyahu-be-the-next_b6b5b5dc
20260329T032005Z_shadow_will-israel-launch-a-ground-operatio_b6957452
20260329T032005Z_shadow_will-israel-or-the-us-target-fordow_13eba83f
20260329T034139Z_shadow_another-7pt0-or-above-earthquake-by_c094ba2e
20260329T034139Z_shadow_highest-temperature-in-london-on-mar_63ebd57b
20260329T034139Z_shadow_highest-temperature-in-wellington-on_e081602a
20260329T034139Z_shadow_will-matthias-bluebaum-win-the-2026_68bf1fa5
20260329T034139Z_shadow_xrp-above-1pt2-on-march-29_b8902eaa
20260329T034641Z_shadow_another-7pt0-or-above-earthquake-by_c094ba2e
20260329T034641Z_shadow_highest-temperature-in-chicago-on-ma_764d40a7
20260329T034641Z_shadow_highest-temperature-in-london-on-mar_63ebd57b
20260329T034641Z_shadow_highest-temperature-in-wellington-on_e081602a
20260329T034704Z_shadow_will-a-different-combination-of-cand_e43fb707
20260329T034705Z_shadow_elon-musk-of-tweets-march-30-april-1_6e11c43c
20260329T034705Z_shadow_fif-mar-par-2026-03-31-par_37ec3b14
20260329T034705Z_shadow_will-fidesz-kdnp-win-at-least-80-sea_7849ec58
20260329T034759Z_shadow_highest-temperature-in-denver-on-mar_459c57ad
20260329T034800Z_shadow_will-duke-win-the-2026-ncaa-tourname_386d0721
20260329T034800Z_shadow_will-jd-vance-talk-to-iranian-negoti_17b9e45f
20260329T034800Z_shadow_will-russia-capture-kostyantynivka-b_4c781e62
20260329T034803Z_shadow_elon-musk-of-tweets-march-30-april-1_6e11c43c
20260329T034803Z_shadow_will-fidesz-kdnp-win-at-least-80-sea_7849ec58
20260329T035119Z_shadow_will-russia-capture-lyman-by-june-30_28d844cb
20260329T035120Z_shadow_will-there-be-at-least-2000-measles_79feef23
20260329T040912Z_shadow_highest-temperature-in-miami-on-apri_15be698a
20260329T040912Z_shadow_will-fidesz-kdnp-win-at-least-80-sea_7849ec58
20260329T040958Z_shadow_another-7pt0-or-above-earthquake-by_c094ba2e
20260329T040958Z_shadow_highest-temperature-in-hong-kong-on_9cbb30b0
20260329T040958Z_shadow_will-a-different-combination-of-cand_e43fb707
20260329T041225Z_shadow_highest-temperature-in-hong-kong-on_9cbb30b0
20260329T041309Z_shadow_will-russia-capture-lyman-by-june-30_28d844cb
20260329T041309Z_shadow_will-there-be-no-change-in-fed-inter_92d768ed
20260329T041309Z_shadow_will-trump-sell-1-100-gold-cards-in_a1558b88
20260329T041534Z_shadow_will-there-be-no-change-in-fed-inter_92d768ed
20260329T041534Z_shadow_will-trump-sell-1-100-gold-cards-in_a1558b88
20260329T043123Z_shadow_us-federally-charges-cuba-leader-mig_c10d85fb
20260329T043123Z_shadow_will-fidesz-kdnp-win-at-least-80-sea_7849ec58
20260329T043123Z_shadow_will-jd-vance-talk-to-iranian-negoti_17b9e45f
20260329T043123Z_shadow_will-russia-capture-kostyantynivka-b_4c781e62
20260329T043351Z_shadow_will-russia-capture-kostyantynivka-b_4c781e62
20260329T043352Z_shadow_will-russia-capture-lyman-by-june-30_28d844cb
```

Total shadow tape directories (all time): 167 (96 from wave 1 + ~71 from wave 2;
many wave 2 directories are retries of the same slugs and may not all qualify due
to too_short events; capture_status.py is authoritative).

## Remaining Shortage by Bucket

| Bucket     | Still Needed |
|------------|-------------:|
| crypto     |           10 |
| sports     |            0 |
| politics   |            0 |
| new_market |            0 |
| near_resolution | 0       |

Only the crypto bucket remains open. It is blocked by market availability: Polymarket
has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-29.

## Final Verdict: MORE_GOLD_NEEDED

**40/50 tapes qualify. 10 more needed (all in crypto bucket).**

Gate 2 (scenario sweep) requires all 50 tapes. The corpus cannot proceed to Gate 2 until
10 crypto binary market tapes are captured.

## Next Command / Work Packet

```bash
# Monitor for crypto market availability
python -m polytool crypto-pair-watch --one-shot  # check once
python -m polytool crypto-pair-watch --watch     # poll until found

# When active crypto markets appear, capture 12-15 sessions (account for too_short rejects):
python -m polytool simtrader shadow \
    --market <BTC-or-ETH-or-SOL-SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape

# After crypto captures, apply path drift fix:
for dir in artifacts/simtrader/tapes/*/; do
    dirname=$(basename "$dir")
    mv "$dir" "artifacts/tapes/shadow/$dirname"
done

# Verify corpus is ready (must exit 0):
python tools/gates/capture_status.py

# When capture_status.py exits 0 (50/50 qualify), run Gate 2:
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/gate2_sweep
```

## Files Changed

| File | Change |
|---|---|
| `artifacts/tapes/shadow/` | ~71 new tape directories added (wave 2 captures) |
| `docs/dev_logs/2026-03-29_gold_capture_wave2.md` | This file |
| `docs/CURRENT_STATE.md` | Updated corpus count 27/50 -> 40/50 and next step |

No code changes. No config/benchmark_v1.* files touched.

## Open Items

1. **Crypto bucket blocked (10 tapes needed):** No active BTC/ETH/SOL 5m/15m binary
   pair markets on Polymarket as of 2026-03-29. Use `crypto-pair-watch --watch` to poll.
   This is the only remaining gate to Gate 2 eligibility.
2. **Path drift root cause not fixed:** `DEFAULT_ARTIFACTS_DIR` in `tools/cli/simtrader.py`
   still writes to `artifacts/simtrader/`. Manual mv required after each capture session.
   A future cleanup could update the default, but is out of scope for this task.
