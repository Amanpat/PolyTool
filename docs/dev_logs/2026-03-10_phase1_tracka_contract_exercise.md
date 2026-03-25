# 2026-03-10 Phase 1 Track A contract exercise

## Summary

- Overall result: PARTIAL PASS.
- The offline `ranked-json -> make-session-pack -> session_watchlist.txt/session_plan.json -> watch_arb_candidates watchlist loader` contract worked with real commands and temp artifacts.
- The current local tape corpus is not Gate 2 ready. `gate2-preflight` reported `Result: BLOCKED`, `Eligible tapes: 0`, `Missing regimes: politics, new_market`, and the real process exit code was `2`.
- One real setup failure occurred during the exercise: the first temp ranked fixture was written with a UTF-8 BOM and `make-session-pack` rejected it. Rewriting the same JSON without BOM fixed the run.
- No code was changed.

## Current local baseline

Observed before running the CLIs:

```text
tapes_dir_exists=True
tape_dir_count=12
manifest_exists=True
schema_version=gate2_tape_manifest_v2
generated_at=2026-03-10T18:10:42.164479+00:00
eligible_count=0
ineligible_count=12
corpus_note=BLOCKED: No eligible tapes. Gate 2 requires at least one tape with executable_ticks > 0 (simultaneous depth_ok AND edge_ok). Run 'prepare-gate2' or 'watch-arb-candidates' targeting markets with sufficient depth and complement edge.
covered_regimes=sports
missing_regimes=politics, new_market
```

Temp artifact root used for this exercise:

```text
D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014
```

Temp ranked fixture written for contract testing:

```text
schema_version=gate2_ranked_scan_v1
generated_at=2026-03-10T19:20:14.0551540Z
scan_mode=fixture
rank=1 slug=will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup gate2_status=NEAR rank_score=0.456
rank=2 slug=will-the-vancouver-canucks-win-the-2026-nhl-stanley-cup gate2_status=EDGE_ONLY rank_score=0.311
rank=3 slug=will-the-calgary-flames-win-the-2026-nhl-stanley-cup gate2_status=NO_SIGNAL rank_score=0.102
```

## Commands run

```text
pytest -q tests/test_gate2_candidate_ranking.py tests/test_gate2_session_pack.py tests/test_watch_arb_candidates.py tests/test_gate2_eligible_tape_acquisition.py
python -m polytool scan-gate2-candidates --help
python -m polytool make-session-pack --help
python -m polytool watch-arb-candidates --help
python -m polytool tape-manifest --help
python -m polytool gate2-preflight --help
python -m polytool scan-gate2-candidates --tapes-dir artifacts/simtrader/tapes --all --top 3 --explain --watchlist-out D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\scan_watchlist.txt --ranked-json-out D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\scan_ranked.json
python -m polytool make-session-pack --ranked-json D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\ranked_fixture.json --regime sports --source-manifest artifacts/gates/gate2_tape_manifest.json --out-dir D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\session_packs --duration 600 --poll-interval 15 --near-edge 0.995 --min-depth 50
python -c "from pathlib import Path; from tools.cli.watch_arb_candidates import _load_watchlist_file; ..."
python -m polytool tape-manifest --tapes-dir artifacts/simtrader/tapes --out D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\fresh_gate2_tape_manifest.json
python -m polytool gate2-preflight --tapes-dir artifacts/simtrader/tapes
```

## Passing checks

1. Targeted offline tests passed.

```text
collected 171 items
171 passed in 2.22s
```

2. Safe CLI help checks passed for all five commands.

```text
scan-gate2-candidates --help -> exit 0
make-session-pack --help -> exit 0
watch-arb-candidates --help -> exit 0
tape-manifest --help -> exit 0
gate2-preflight --help -> exit 0
```

3. Real offline `scan-gate2-candidates` tape-mode smoke passed and wrote both exports.

```text
Showed 3/12 candidates. Mode: tape. Executable: 0. Threshold: sum_ask < 0.9900, depth >= 50 shares.
[scan-gate2] Wrote 3 exact slug(s) to: D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\scan_watchlist.txt
[scan-gate2] Wrote 3 ranked candidate(s) to: D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\scan_ranked.json
```

Top 3 real corpus results from that smoke:

```text
will-the-toronto-maple-leafs-win-the-2026-nh | DEPTH | 0.398 | Exec 0 | BestEdge -0.0110
will-the-vancouver-canucks-win-the-2026-nhl- | DEPTH | 0.398 | Exec 0 | BestEdge -0.0110
will-the-calgary-flames-win-the-2026-nhl-sta | DEPTH | 0.398 | Exec 0 | BestEdge -0.0110
```

4. `make-session-pack` passed after the fixture was rewritten without BOM.

```text
Session pack created: 20260310T192029Z
Regime : sports
Slugs  : 3
Watchlist : D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\session_packs\20260310T192029Z\session_watchlist.txt
Plan      : D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\session_packs\20260310T192029Z\session_plan.json
Corpus    : eligible=0  covered=['sports']  missing=['politics', 'new_market']
```

5. Generated `session_watchlist.txt` preserved exact slug order.

```text
watchlist[1]=will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup
watchlist[2]=will-the-vancouver-canucks-win-the-2026-nhl-stanley-cup
watchlist[3]=will-the-calgary-flames-win-the-2026-nhl-stanley-cup
watchlist_count=3
```

6. Generated `session_plan.json` preserved the fixture advisory payload and current manifest context.

```text
schema_version=gate2_session_pack_v1
session_id=20260310T192029Z
regime=sports
slug_count=3
corpus_eligible_count=0
corpus_covered=sports
corpus_missing=politics, new_market
watch_duration=600.0
watch_poll=15.0
watch_near_edge=0.995
watch_min_depth=50.0
row1_selection_source=ranked-json:ranked_fixture.json
row1_final_regime=sports
row1_derived_regime=sports
row1_rank=1
row1_gate2=NEAR
row2_rank=2
row2_gate2=EDGE_ONLY
row3_rank=3
row3_gate2=NO_SIGNAL
```

7. The generated `session_plan.json` was readable by the watcher JSON loader.

```text
watch_loader_count=3
watch_loader_slugs=will-the-toronto-maple-leafs-win-the-2026-nhl-stanley-cup | will-the-vancouver-canucks-win-the-2026-nhl-stanley-cup | will-the-calgary-flames-win-the-2026-nhl-stanley-cup
watch_loader_first_priority=1
watch_loader_first_final_regime=sports
watch_loader_first_rank=1
```

8. Real offline `tape-manifest` passed on the current local corpus and the fresh manifest summary matched the current manifest summary.

```text
Total: 12  |  Eligible: 0  |  Ineligible: 12
Corpus note: BLOCKED: No eligible tapes. Gate 2 requires at least one tape with executable_ticks > 0 (simultaneous depth_ok AND edge_ok). Run 'prepare-gate2' or 'watch-arb-candidates' targeting markets with sufficient depth and complement edge.
[tape-manifest] Manifest written: D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\fresh_gate2_tape_manifest.json
eligible_match=True
ineligible_match=True
covered_match=True
missing_match=True
corpus_note_match=True
```

## Failed checks

1. First `make-session-pack` attempt failed because the temp fixture had a BOM.

```text
Error: Cannot read ranked JSON from 'D:\Coding Projects\Polymarket\PolyTool\artifacts\_tmp_phase1_tracka_contract_exercise_20260310T152014\ranked_fixture.json': Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)
```

This was a fixture-writing issue in the exercise, not a source-code change request. Rewriting the exact same JSON without BOM fixed it immediately.

2. `gate2-preflight` failed on the current local tape corpus.

```text
Gate 2 Preflight
================
Result: BLOCKED
Eligible tapes: 0
Eligible tape list: none
Mixed-regime coverage: BLOCKED
Covered regimes: sports
Missing regimes: politics, new_market
Blocker: No eligible tapes. Gate 2 sweep still lacks a tape with executable_ticks > 0.
Next action: python -m polytool scan-gate2-candidates --all --top 20 --explain
process_exit=2
```

## Warnings

- The fixture advisory values were intentional contract-test data. They only verified carry-through into `session_plan.json`. They do not prove those three markets are currently executable.
- The current real corpus signal is weak. The offline tape-mode scan found depth on the three sports futures, but `Exec=0` and `BestEdge=-0.0110` for all three. That is not tradeable.
- The current corpus remains single-regime from the manifest's point of view: `covered_regimes=sports`, `missing_regimes=politics, new_market`.

## Live-only unverified items

- Whether `watch-arb-candidates` can resolve these or any future session-plan slugs against live Polymarket and actually trigger recording.
- Whether a real catalyst-window watch session can produce `executable_ticks > 0`.
- Whether fresh politics and new-market captures will close the mixed-regime gap after at least one eligible tape exists.
- Whether the current sports futures ever move from `DEPTH_ONLY` to an executable edge during a live window.

## Recommended next action

- Do not treat this offline pass as operational readiness.
- The contract is good enough to use, but the corpus is not.
- Next real step: run a live catalyst-window session using a real ranked export from `scan-gate2-candidates`, feed that into `make-session-pack`, watch with `watch-arb-candidates`, then rerun `tape-manifest` and `gate2-preflight`.
- Since the corpus already only covers `sports` and still has `eligible_count=0`, priority should be capturing at least one real eligible tape and then expanding into `politics` or `new_market`. Do not run `close_sweep_gate.py` yet.
