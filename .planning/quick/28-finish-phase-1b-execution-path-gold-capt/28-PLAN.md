# Quick Task 028 — Finish Phase 1B Execution Path

**Slug:** finish-phase-1b-execution-path-gold-capt
**Branch:** phase-1B
**Created:** 2026-03-27

---

## Situation

Quick-027 established:
- Recovery corpus has 9/50 qualifying tapes (all `near_resolution` Silver, eff 56-60)
- `corpus_audit.py` exits 1 (SHORTAGE)
- Gate 2 cannot run; Gate 3 blocked
- Runbook for live Gold shadow capture is written

**New findings from pre-plan inventory analysis (2026-03-27):**

| Finding | Impact |
|---------|--------|
| `20260226T181825Z_shadow_10167699` tape (slug: `will-trump-deport-less-than-250000`) has 70 effective events but is rejected as `no_bucket_label` + `unknown` tier because it lacks `market_meta.json` and `watch_meta.json` | Salvageable — adding metadata files qualifies it as a `politics` bucket Gold tape |
| 3 hockey shadow tapes (Toronto/Vancouver/Calgary) have 40/33/15 effective events | Below threshold, cannot be salvaged |
| All 118 Silver tapes with `benchmark_bucket` labels have <= 30 `price_2min_guide` events in non-near_resolution buckets | Silver reconstruction cannot be re-run to produce more events — the underlying price_2min data was sparse for those markets/windows |
| `artifacts/tapes/new_market/` contains 7 crypto updown tapes with 1-3 events each | Not salvageable |

**Definitive conclusion:** After the metadata salvage below, the corpus reaches 10/50
(1 politics + 9 near_resolution). The remaining shortage of 40 tapes requires **live**
Gold shadow captures and cannot be resolved within this agent session.

**This task's job:** Salvage the one qualifiable tape, re-run corpus_audit, and produce
the definitive residual shortage packet proving exactly why Phase 1B cannot close in-session.

---

## Constraints

- `benchmark_v1` lock/audit/manifest are immutable — do not touch
- Gate 2 threshold >= 0.70 is never weakened
- `min_events=50` is never softened
- No live capital; no live WS connections from this agent
- No strategy tuning, no gate threshold changes, no Phase 2 work

---

## Tasks

### Task 1 — Salvage the 70-event politics shadow tape via metadata injection

**Objective:** The `20260226T181825Z_shadow_10167699` tape has 70 effective events
from the `will-trump-deport-less-than-250000` market (politics bucket). It is
rejected by `corpus_audit.py` only because it lacks `market_meta.json` (no bucket
label) and has no `watch_meta.json` (tier detected as `unknown`). Injecting these
two metadata files makes it qualify as a Gold politics tape.

**Files to create:**
- `artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699/market_meta.json`
- `artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699/watch_meta.json`

**Implementation:**

Create `market_meta.json` using the `silver_market_meta_v1` schema (same format
as all other Silver tapes that have bucket labels):

```json
{
  "schema_version": "silver_market_meta_v1",
  "slug": "will-trump-deport-less-than-250000",
  "category": "politics",
  "market_id": "",
  "platform": "polymarket",
  "token_id": "101676997363687199724245607342877036148401850938023978421879460310389391082353",
  "benchmark_bucket": "politics"
}
```

`token_id` comes from `meta.json["shadow_context"]["yes_token_id"]`. `market_id`
is left empty (not required for corpus qualification; only bucket label matters).

Create `watch_meta.json` to establish Gold tier detection. The minimum required
fields are `bucket` (used by `_detect_bucket()` Priority 1) and `bucket` enables
Gold tier detection when `watch_meta.json` is present:

```json
{
  "bucket": "politics",
  "slug": "will-trump-deport-less-than-250000",
  "recorded_at": "2026-02-26T18:18:25Z",
  "source": "shadow"
}
```

**Verification:**

```bash
python -c "
from tools.gates.corpus_audit import _detect_tier, _detect_bucket
from pathlib import Path
import json

tape_dir = Path('artifacts/simtrader/tapes/20260226T181825Z_shadow_10167699')
tier = _detect_tier(tape_dir)
meta = json.loads((tape_dir / 'meta.json').read_text())
watch_meta = json.loads((tape_dir / 'watch_meta.json').read_text()) if (tape_dir / 'watch_meta.json').exists() else {}
market_meta = json.loads((tape_dir / 'market_meta.json').read_text()) if (tape_dir / 'market_meta.json').exists() else {}
bucket = _detect_bucket(tape_dir, meta=meta, watch_meta=watch_meta, market_meta=market_meta, silver_meta={})
print(f'tier={tier} bucket={bucket}')
assert tier == 'gold', f'Expected gold, got {tier}'
assert bucket == 'politics', f'Expected politics, got {bucket}'
print('PASS')
"
```

**Done:** Both files exist; the inline verification prints `tier=gold bucket=politics PASS`.

---

### Task 2 — Re-run corpus_audit and produce definitive residual shortage packet

**Objective:** Re-run `corpus_audit.py` with the now-salvaged tape. Confirm the
updated count (10/50, 1 politics + 9 near_resolution). Produce the updated
`artifacts/corpus_audit/shortage_report.md`. Then write the definitive residual
shortage packet as a structured Markdown doc at
`artifacts/corpus_audit/phase1b_residual_shortage_v1.md` that the operator can
use as the authoritative execution guide for live Gold capture.

**Files to create/modify:**
- `artifacts/corpus_audit/shortage_report.md` (updated by tool)
- `artifacts/corpus_audit/phase1b_residual_shortage_v1.md` (new — definitive packet)

**Step 1 — Re-run corpus_audit:**

```bash
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest
```

Expected: exit 1, total accepted = 10 (was 9), politics = 1 (was 0), near_resolution = 9.
If exit 0 (unexpected surplus discovered), skip the shortage packet and proceed to Gate 2 rerun
per the command in CORPUS_GOLD_CAPTURE_RUNBOOK.md §8.

**Step 2 — Write `artifacts/corpus_audit/phase1b_residual_shortage_v1.md`:**

This file is the definitive "here is exactly what the operator must do to unblock Gate 2"
document. It must contain:

1. **Preamble** — date, quick task number, branch, status (SHORTAGE, gate blocked)
2. **Current corpus state table** — per bucket: quota, have, shortage, tier of existing tapes
3. **Why live capture is the only path** — explain: Silver reconstruction is exhausted
   (all 118 Silver tapes reconstructed; those with valid bucket labels have max 30 events
   from sparse price_2min data; cannot exceed 50 without real market activity); existing
   shadow tapes are too short; no additional tape roots were found
4. **Exact capture commands per bucket** — ordered by priority (sports=15 hardest, do first):
   - Sports (need 15): example slugs (NHL/NBA/soccer), 600s minimum
   - Politics (need 9): example slug pattern (US elections, international policy), 600s
   - Crypto (need 10): note crypto markets rotate daily; use `crypto-pair-watch --watch`
     to detect when BTC/ETH/SOL 5m markets appear; target up/down markets, 600s minimum
   - Near_resolution (need 1): any market resolving within 48h, 300s may suffice
   - New_market (need 5): browse Polymarket front page for newly listed markets
5. **How to resume** — run `corpus_audit.py` after each batch; stop when exit 0;
   then run Gate 2 sweep per CORPUS_GOLD_CAPTURE_RUNBOOK.md §8
6. **Gate 2 and Gate 3 command reference** (copy from shortage_report.md §Next Steps)

**Verification:**

```bash
python -c "
from pathlib import Path
sr = Path('artifacts/corpus_audit/shortage_report.md')
rp = Path('artifacts/corpus_audit/phase1b_residual_shortage_v1.md')
assert sr.exists(), 'shortage_report.md missing'
assert rp.exists(), 'phase1b_residual_shortage_v1.md missing'
# Verify the updated shortage shows politics = 1/10 (not 0/10)
content = sr.read_text()
# Check that total accepted is now 10
import subprocess, re
result = subprocess.run(['python', 'tools/gates/corpus_audit.py', '--out-dir', 'artifacts/corpus_audit', '--manifest-out', 'config/recovery_corpus_v1.tape_manifest'], capture_output=True, text=True)
print('corpus_audit exit:', result.returncode)
lines = (result.stdout + result.stderr)
print(lines)
"
```

**Done:** `shortage_report.md` shows 10/50 accepted, `phase1b_residual_shortage_v1.md`
exists with all five sections. Corpus_audit exits 1 (shortage, not 0). The shortage
counts match: politics=9 remaining, near_resolution=1 remaining, others unchanged.

---

### Task 3 — Run full regression suite and write dev log + update state docs

**Objective:** Confirm no regressions from the metadata file additions, write the
mandatory dev log, and update `docs/CURRENT_STATE.md` and `.planning/STATE.md`.

**Files to create/modify:**
- `docs/dev_logs/2026-03-27_phase1b_residual_shortage.md` (new dev log)
- `docs/CURRENT_STATE.md` (update corpus status, reference new artifacts)
- `.planning/STATE.md` (add quick-028 row, update blockers)

**Step 1 — Regression suite:**

```bash
python -m pytest tests/ -x -q --tb=short
```

Report exact counts. The metadata files added in Task 1 are JSON data files, not
Python code — no test regressions are expected. If any test fails, diagnose and
fix before continuing.

**Step 2 — Dev log `docs/dev_logs/2026-03-27_phase1b_residual_shortage.md`:**

Required sections:
- **Objective** — why quick-028 was run
- **Inventory analysis findings** — what was inspected, what was found (the 70-event
  politics tape, the 118 Silver tapes breakdown, the failed shadow tapes)
- **Files changed and why** — market_meta.json and watch_meta.json for the salvaged
  tape; phase1b_residual_shortage_v1.md; updated state docs
- **Commands run and output** — corpus_audit before (9/50) and after (10/50) salvage
- **Tests run and pass/fail counts** — exact numbers from Step 1
- **benchmark_v1 preservation confirmation** — explicitly state benchmark_v1 files
  were not touched
- **Why Gate 2 cannot run in-session** — list all paths exhausted:
  (a) Silver reconstruction exhausted, (b) existing shadow tapes too short,
  (c) only 10/50 tapes qualify after salvage, (d) live WS capture not possible
  from agent session
- **Exact next operator action** — run live Gold shadow captures per
  `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`; consult
  `artifacts/corpus_audit/phase1b_residual_shortage_v1.md` for per-bucket commands

**Step 3 — `docs/CURRENT_STATE.md` update (Gate 2 section):**

Update the Gate 2 corpus status line from "9/50 tapes qualify" to "10/50 tapes qualify"
and add a reference to the new `artifacts/corpus_audit/phase1b_residual_shortage_v1.md`
artifact. Do not change any other sections. Read the file first; make a targeted update.

**Step 4 — `.planning/STATE.md` update:**

- Add quick-028 row to the completed table:
  `028 | Phase 1B residual shortage packet | 2026-03-27 | <commit> | 28-finish-phase-1b-execution-path-gold-capt`
- Update Blockers/Concerns: change "9/50 qualifying tapes" to "10/50 qualifying tapes"
  and add reference to `artifacts/corpus_audit/phase1b_residual_shortage_v1.md`

**Verification:**

```bash
python -m polytool --help
```

CLI loads with no import errors. This confirms the metadata-only file additions did not
break any imports.

**Done:** Dev log written, CURRENT_STATE.md and STATE.md updated to reflect 10/50
tapes and the definitive shortage packet location. Full test suite passes.

---

## Dependency Order

```
Task 1 (metadata salvage) --> Task 2 (corpus_audit rerun + shortage packet) --> Task 3 (regression + docs)
```

All three tasks must run sequentially. Task 2 depends on Task 1's metadata files being
present. Task 3 depends on Task 2's audit output for the dev log.

---

## Constraints Checklist

- [ ] `benchmark_v1` lock/audit/manifest not modified
- [ ] Gate 2 threshold >= 0.70 not weakened
- [ ] `min_events=50` not softened anywhere
- [ ] No live WS or live capital
- [ ] No Gate 3 attempted
- [ ] Full regression suite passes
- [ ] Dev log written at `docs/dev_logs/2026-03-27_phase1b_residual_shortage.md`
- [ ] `docs/CURRENT_STATE.md` updated
- [ ] `.planning/STATE.md` updated

---

## Expected Outcomes

**After Task 1:** corpus has one salvageable Gold politics tape with bucket metadata.

**After Task 2:** corpus_audit shows 10/50 (1 politics + 9 near_resolution). Gate 2
still blocked (corpus insufficient). `phase1b_residual_shortage_v1.md` exists as the
operator's executable guide.

**After Task 3:** No regressions. Authority docs updated. The operator has a complete,
actionable packet: run live shadow captures per the runbook, 40 tapes needed across
4 buckets (sports=15, politics=9, crypto=10, new_market=5, near_resolution=1).

---

## What This Task Does NOT Do

- Does not attempt live Gold shadow captures (requires Polymarket WS connectivity)
- Does not rerun Gate 2 (corpus still insufficient after salvage)
- Does not attempt Gate 3 (Gate 2 blocked)
- Does not tune strategy parameters
- Does not modify `benchmark_v1` artifacts
- Does not soften the `min_events=50` threshold
- Does not re-run Silver reconstruction (exhausted — no additional data sources)
