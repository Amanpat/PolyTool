# Phase 1B Residual Shortage Packet — Dev Log

**Date:** 2026-03-27
**Branch:** phase-1B
**Quick task:** 028 — finish-phase-1b-execution-path-gold-capt
**Author:** Claude Code

---

## Objective

Quick-027 established the corpus recovery tooling (`corpus_audit.py`, runbook, shortage_report.md)
and showed 9/50 qualifying tapes (all near_resolution Silver). Quick-028 picks up from there:
(a) exhaustively inventory all salvageable in-session options, (b) salvage the one qualifiable
tape found, (c) re-run corpus_audit and produce the definitive residual shortage packet that
proves exactly why Phase 1B cannot close in-session and gives the operator exact commands for
the remaining 40 tapes.

---

## Inventory Analysis Findings

Before writing the plan, a full inventory was conducted across all tape roots.

### 70-event politics shadow tape — SALVAGEABLE

`artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699` (slug: `will-trump-deport-less-than-250000`)
had 70 effective events. It was rejected by corpus_audit only because:
- `market_meta.json` was absent (no bucket label detectable)
- `watch_meta.json` was absent (tier detected as `unknown`)

Injecting these two metadata files qualified it as a Gold politics tape.

### Hockey shadow tapes — NOT salvageable

Three shadow tapes in `artifacts/simtrader/tapes/`:
- Toronto Maple Leafs: 40 effective events (below 50 threshold)
- Vancouver Canucks: 33 effective events (below 50 threshold)
- Calgary Flames: 15 effective events (below 50 threshold)

All three fall below the min_events=50 threshold. Cannot be salvaged without
re-recording new sessions.

### 118 Silver tapes — Silver reconstruction exhausted

All 118 Silver tapes across `artifacts/silver/` were scanned:
- 9 qualify (all near_resolution, >= 50 effective events) — already counted
- 34 fall in the 30–49 event range, all with only `price_2min_guide` event types
- 75 have < 30 effective events

The 34 tapes in the 30–49 range cannot be extended. Their effective event counts
reflect the density of historical price_2min data for those markets/windows (typically
~5-hour windows with ~30 data points). Re-running Silver reconstruction on these tapes
produces identical results — no additional Parquet or ClickHouse data sources exist
that would increase the event count.

### New-market archive tapes — NOT salvageable

`artifacts/tapes/new_market/` contains 7 crypto up/down tapes with 1–3 effective
events each. All far below threshold.

### Definitive conclusion

After the metadata salvage, corpus reaches 10/50 (1 politics Gold + 9 near_resolution Silver).
40 more tapes are needed via live Gold shadow captures. This cannot be resolved in an
agent session (requires live Polymarket WS connectivity).

---

## Files Changed and Why

| File | Action | Reason |
|------|--------|--------|
| `artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699/market_meta.json` | Created | Injects `benchmark_bucket: "politics"` so corpus_audit can detect bucket label |
| `artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699/watch_meta.json` | Created | Injects `bucket: "politics"` (Priority 1 in _detect_bucket()) and triggers Gold tier detection |
| `artifacts/corpus_audit/shortage_report.md` | Updated (by corpus_audit.py) | Reflects 10/50 accepted, politics=1/10 |
| `artifacts/corpus_audit/phase1b_residual_shortage_v1.md` | Created | Definitive operator guide: corpus state, why live capture is the only path, exact commands per bucket, resume instructions, Gate 2/3 reference |
| `docs/CURRENT_STATE.md` | Updated | Gate 2 section: 9/50 → 10/50, added phase1b_residual_shortage_v1.md reference |
| `.planning/STATE.md` | Updated | Added quick-028 row, updated blocker from 9/50 to 10/50 |

---

## Commands Run and Output

### Task 1 — Metadata salvage verification

```
python -c "from tools.gates.corpus_audit import _detect_tier, _detect_bucket ..."
```

**Output:**
```
tier=gold bucket=politics
PASS
```

### Task 2 — corpus_audit rerun

```
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

**Output:**
```
============================================================
Corpus Audit Summary
============================================================
Total scanned:   137
Total accepted:  10 / 50 needed
Total rejected:  127

Accepted by bucket:
  crypto               0 / 10  NEED 10 more
  near_resolution      9 / 10  NEED 1 more
  new_market           0 / 5  NEED 5 more
  politics             1 / 10  NEED 9 more
  sports               0 / 15  NEED 15 more

Verdict: SHORTAGE (exit 1)
============================================================
```

**Exit code:** 1 (shortage, as expected — corpus still insufficient)

### Task 3 — Full regression suite

```
python -m pytest tests/ -x -q --tb=short
```

**Result:** 2662 passed, 0 failed, 25 warnings

No regressions introduced. The metadata files added in Task 1 are pure JSON data
files; they touch no Python code paths.

---

## benchmark_v1 Preservation Confirmation

**benchmark_v1 lock/audit/manifest were NOT modified.**

The following files are confirmed unchanged:
- `config/benchmark_v1.tape_manifest`
- `config/benchmark_v1.lock.json`
- `config/benchmark_v1.audit.json`

`corpus_audit.py` only reads/writes `config/recovery_corpus_v1.tape_manifest` and
`artifacts/corpus_audit/`. It never touches benchmark_v1 files. This was verified
by code inspection in quick-027 and remains true in quick-028.

---

## Why Gate 2 Cannot Run In-Session

All paths to closing the corpus shortage in this agent session have been exhausted:

**(a) Silver reconstruction exhausted.** All 118 Silver tapes have been reconstructed
and scanned. The 34 tapes in the 30–49 event range cannot yield more events because
the underlying price_2min Parquet data is sparse for those markets/windows. No
additional data sources exist.

**(b) Existing shadow tapes too short.** The three hockey shadow tapes (40/33/15
effective events) fall below the 50-event minimum. They cannot be extended after the
fact.

**(c) Only 10/50 tapes qualify after salvage.** Even after the one salvageable tape
was rescued via metadata injection, 40 tapes remain needed across 4 buckets
(sports=15, politics=9, crypto=10, new_market=5, near_resolution=1).

**(d) Live WS shadow capture not possible from agent session.** Shadow recording
requires a live Polymarket WebSocket connection (`wss://ws-subscriptions-clob.polymarket.com/ws/market`).
This cannot be established from a non-interactive agent context without live market
connectivity, session tokens, and a running Polymarket WS infrastructure.

---

## Exact Next Operator Action

1. Capture live Gold shadow tapes using the commands in
   `artifacts/corpus_audit/phase1b_residual_shortage_v1.md` (Section 3).
   See `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` for full instructions.

2. After each batch, re-run corpus_audit:
   ```
   python tools/gates/corpus_audit.py \
       --tape-roots artifacts/simtrader/tapes \
       --tape-roots artifacts/silver \
       --tape-roots artifacts/tapes \
       --out-dir artifacts/corpus_audit \
       --manifest-out config/recovery_corpus_v1.tape_manifest
   ```

3. Stop when corpus_audit exits 0 (Verdict: QUALIFIED).

4. Run Gate 2:
   ```
   python tools/gates/close_mm_sweep_gate.py \
       --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
       --out artifacts/gates/mm_sweep_gate
   ```

5. Check result with `python tools/gates/gate_status.py`. If PASSED, proceed to Gate 3
   per `docs/runbooks/GATE3_SHADOW_RUNBOOK.md`.

Remaining shortage: sports=15, politics=9, crypto=10, new_market=5, near_resolution=1 (total 40 tapes).
