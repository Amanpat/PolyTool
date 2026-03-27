# Quick Task 029 — Convert Phase 1B to Clean Operator Capture Campaign

## Objective

Convert Phase 1B from an ambiguous blocker into a clean, low-friction operator capture
campaign. After this task:

- One authoritative capture campaign spec exists (`SPEC-phase1b-gold-capture-campaign.md`)
- The runbook (`CORPUS_GOLD_CAPTURE_RUNBOOK.md`) is the single "do this next" document with
  exact commands — no scattered guidance
- A minimal `capture_status.py` helper prints the current shortage table with one command
- `docs/CURRENT_STATE.md` says Phase 1B is waiting on live capture, not gate-core changes
- A dev log records the transition

Starting state: 10/50 tapes, 40 needed (sports=15, politics=9, crypto=10, new_market=5,
near_resolution=1). No gate-core or strategy changes are required.

---

## Task 1 — Campaign Spec + Runbook Tightening

**Commit:** `docs(quick-029): add gold capture campaign spec and tighten runbook`

**Files:**
- `docs/specs/SPEC-phase1b-gold-capture-campaign.md` (create)
- `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` (update)

**Action:**

Create `docs/specs/SPEC-phase1b-gold-capture-campaign.md` as the single phase-level
authority for the Gold capture campaign. It must contain:

1. **Campaign context** — why we are here: `benchmark_v1` is immutable; 10/50 tapes
   qualify; Silver reconstruction exhausted; 40 tapes needed via live Gold shadow capture.

2. **Starting shortage table** (verbatim from shortage_report.md):

   | Bucket          | Quota | Have | Need |
   |-----------------|------:|-----:|-----:|
   | sports          |    15 |    0 |   15 |
   | politics        |    10 |    1 |    9 |
   | crypto          |    10 |    0 |   10 |
   | new_market      |     5 |    0 |    5 |
   | near_resolution |    10 |    9 |    1 |
   | **Total**       |**50** |**10**|**40**|

3. **Bucket quotas and completion rules** — point to `SPEC-phase1b-corpus-recovery-v1.md`
   for the formal contract; this spec summarises: min_events=50 never weakened,
   `effective_events >= 50` required, all 5 buckets must be represented, `corpus_audit.py`
   is the authoritative counter.

4. **Campaign loop** (one paragraph + numbered list):
   1. Run `capture_status.py` to see current shortage.
   2. Shadow-record one or more tapes for the highest-shortage bucket.
   3. Re-run `corpus_audit.py` to validate.
   4. Repeat until `corpus_audit.py` exits 0.
   5. Then run Gate 2 sweep.

5. **Resumability rules** — each shadow session writes to a new timestamped dir;
   `corpus_audit.py` always scans from scratch; safe to restart at any step.

6. **Success artifacts** — `corpus_audit.py` exits 0, `config/recovery_corpus_v1.tape_manifest`
   written. Then Gate 2 command unblocked.

7. **Failure artifacts** — `artifacts/corpus_audit/shortage_report.md` written by
   `corpus_audit.py` on exit 1.

8. **Constraints section** — no live capital, min_events=50 immutable, Gate 2 threshold
   >= 70% immutable, benchmark_v1 immutable.

9. **Tool reference table**:

   | Tool | Purpose |
   |------|---------|
   | `tools/gates/capture_status.py` | Quick shortage status (one command) |
   | `tools/gates/corpus_audit.py` | Full scan + manifest writer |
   | `python -m polytool simtrader shadow ...` | Live Gold tape capture |
   | `tools/gates/close_mm_sweep_gate.py` | Gate 2 sweep (after corpus qualifies) |

Update `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`:
- Add a "Section 0: Quick Status Check" at the top showing the one-liner:
  `python tools/gates/capture_status.py`
- Replace the hard-coded shortage numbers in Section 7 ("Recommended capture priorities")
  with a note to run `capture_status.py` for current counts (the hard-coded numbers are
  from 2026-03-26 and will drift as tapes are added)
- Update the reference block at the bottom to include:
  `- Campaign spec: docs/specs/SPEC-phase1b-gold-capture-campaign.md`
  `- Quick status: tools/gates/capture_status.py`
- Do NOT add a second overlapping runbook. One runbook is the operational document.
- Do NOT change any capture commands, min_events, or gate thresholds.

**Verify:** Both files exist. `grep -q "capture_status.py" docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` passes. `grep -q "Starting shortage" docs/specs/SPEC-phase1b-gold-capture-campaign.md` passes.

**Done:** One authoritative campaign spec exists. Runbook references `capture_status.py` and has no stale hard-coded shortage counts in the priority section.

---

## Task 2 — capture_status.py Helper + Tests

**Commit:** `feat(quick-029): add capture_status.py quota-status helper with tests`

**Files:**
- `tools/gates/capture_status.py` (create)
- `tests/test_capture_status.py` (create)

**Action:**

Create `tools/gates/capture_status.py` — a read-only quota-status helper.

**Interface:**
```
Usage: python tools/gates/capture_status.py [OPTIONS]

Options:
  --tape-roots PATH    (repeatable) Same defaults as corpus_audit.py:
                       artifacts/simtrader/tapes, artifacts/silver, artifacts/tapes
  --json               Emit machine-readable JSON instead of table

Exit codes:
  0 — corpus complete (manifest exists OR corpus_audit would exit 0)
  1 — shortage exists
```

**Implementation rules:**
- Import and reuse `audit_tape_candidates`, `_discover_tape_dirs`, `_BUCKET_QUOTAS`,
  `_TOTAL_QUOTA`, `DEFAULT_TAPE_ROOTS`, `DEFAULT_MIN_EVENTS` from `tools/gates/corpus_audit`
  (same repo-root sys.path setup pattern as corpus_audit.py).
- Never call `run_corpus_audit()` (that writes files). Call the read-only functions only:
  `_discover_tape_dirs` + `audit_tape_candidates`.
- Build a per-bucket summary dict:
  ```python
  {bucket: {"quota": Q, "have": H, "need": max(0, Q-H), "gold": G, "silver": S}}
  ```
  where H = count of ACCEPTED tapes in that bucket, G/S = gold/silver breakdown.
- Also compute: `total_have`, `total_need`, `total_quota` (50).
- **Table output (default):** Print a compact table to stdout:
  ```
  Corpus status: 10 / 50 tapes qualified (40 needed)

  Bucket           Quota  Have  Need  Gold  Silver
  ---------------  -----  ----  ----  ----  ------
  sports              15     0    15     0       0
  politics            10     1     9     1       0
  crypto              10     0    10     0       0
  new_market           5     0     5     0       0
  near_resolution     10     9     1     0       9
  ---------------  -----  ----  ----  ----  ------
  Total               50    10    40     1       9

  Next: run corpus_audit.py after capturing tapes. Gate 2 unblocks at exit 0.
  ```
  When complete (need=0 for all buckets):
  ```
  Corpus status: 50 / 50 tapes qualified — COMPLETE
  Run: python tools/gates/close_mm_sweep_gate.py --benchmark-manifest config/recovery_corpus_v1.tape_manifest --out artifacts/gates/mm_sweep_gate
  ```
- **JSON output (`--json`):** Print a single JSON object to stdout:
  ```json
  {
    "total_have": 10,
    "total_quota": 50,
    "total_need": 40,
    "complete": false,
    "buckets": {
      "sports": {"quota": 15, "have": 0, "need": 15, "gold": 0, "silver": 0},
      ...
    }
  }
  ```
- Exit 0 when `total_need == 0`, exit 1 otherwise.
- Never writes any file. Never mutates any state.

Create `tests/test_capture_status.py` with at least 4 tests using `tmp_path` and the
injectable tape-roots pattern (pass `--tape-roots` pointing at synthetic tape dirs):

1. **test_shortage_table** — Create 1 fake Gold politics tape dir with a `watch_meta.json`
   (bucket=politics) and a 60-line `events.jsonl` (each line a JSON dict with
   `type="price_change"`). Run `capture_status.main(["--tape-roots", str(tmp_path)])`.
   Assert exit code 1, stdout contains "politics" and "Need" header.

2. **test_complete_state** — Create 50 fake tape dirs spread across all 5 buckets
   (10 politics, 15 sports, 10 crypto, 10 near_resolution, 5 new_market), each with
   60 `price_change` events and a `watch_meta.json` with the correct `bucket` field.
   Assert exit code 0, stdout contains "COMPLETE".

3. **test_json_mode** — Same 1-tape setup as test_shortage_table. Run with `--json`.
   Parse stdout as JSON. Assert `complete=false`, `total_need=49`,
   `buckets["politics"]["have"]==1`.

4. **test_empty_roots** — Pass `--tape-roots` pointing at an empty directory.
   Assert exit code 1, `total_have=0` in JSON output.

For the fake tape dirs: each tape dir must contain an `events.jsonl` file with >= 50
lines where each line is `{"type": "price_change", "asset_id": "x", "price": 0.5}`.
Gold tapes need `watch_meta.json` with `{"bucket": "<bucket_name>"}`.

Use `main(argv)` entry point pattern — `capture_status.py` should expose a `main(argv=None)`
function that accepts a list of CLI args and returns an int exit code (same pattern as
other tools in this repo). Tests call `main(["--tape-roots", str(tmp_path)])` directly
without subprocess.

**Verify:**
```bash
python -m pytest tests/test_capture_status.py -v --tb=short
```
All tests pass. Then smoke test:
```bash
python tools/gates/capture_status.py --tape-roots artifacts/simtrader/tapes --tape-roots artifacts/silver --tape-roots artifacts/tapes
```
Prints the shortage table (exit code 1 since corpus is not yet complete).

**Done:** `capture_status.py` is importable and returns correct exit codes. All 4 tests pass. The smoke test prints a readable shortage table.

---

## Task 3 — CURRENT_STATE.md Update + Dev Log

**Commit:** `docs(quick-029): update CURRENT_STATE.md and write dev log for campaign packet`

**Files:**
- `docs/CURRENT_STATE.md` (update)
- `docs/dev_logs/2026-03-27_phase1b_gold_capture_campaign_packet.md` (create)

**Action:**

Update `docs/CURRENT_STATE.md` — find the "## Status as of" section and the "Blockers/Concerns" section. Make the following targeted changes:

1. Update the status header to:
   ```
   ## Status as of 2026-03-27 (Phase 1B — Gate 2 NOT_RUN, awaiting live Gold capture)
   ```

2. In the Gate 2 bullet, update the text to reflect:
   - Gate 2: **NOT_RUN** — 10/50 tapes qualify; 40 more needed via live Gold shadow capture.
   - No gate-core changes required. No strategy tuning required.
   - Capture campaign packet complete as of 2026-03-27.
   - Quick tools: `python tools/gates/capture_status.py` (current shortage), `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` (capture commands).
   - Authoritative spec: `docs/specs/SPEC-phase1b-gold-capture-campaign.md`.

3. In the "Blockers/Concerns" section, update the Track 1 Gate 2 corpus bullet to:
   ```
   - Track 1 Gate 2 corpus: recovery corpus has 10/50 qualifying tapes. Silver reconstruction
     exhausted. No gate-core or strategy changes needed. Next action: live Gold shadow capture
     per campaign packet. Run `python tools/gates/capture_status.py` to see current shortage.
     Capture per `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`. Gate 2 rerun unblocked when
     corpus_audit.py exits 0. Shortage by bucket: sports=15, politics=9, crypto=10,
     new_market=5, near_resolution=1 (as of 2026-03-27).
   ```

4. Do NOT change any other section. Do NOT touch benchmark_v1, Gate 3, Stage 0/1, Track 2,
   or any infrastructure details.

Create `docs/dev_logs/2026-03-27_phase1b_gold_capture_campaign_packet.md`:

```markdown
# Dev Log — Phase 1B Gold Capture Campaign Packet

**Date:** 2026-03-27
**Quick task:** 029 — convert-phase-1b-to-clean-operator-captu
**Branch:** phase-1B

## What Was Done

Converted Phase 1B from ambiguous blocker state into a clean, documented operator
capture campaign. No code changes to gate logic, strategy, or benchmark_v1.

### Deliverables

1. `docs/specs/SPEC-phase1b-gold-capture-campaign.md` — authoritative campaign spec
   with starting shortage state, bucket quotas, campaign loop, resumability rules,
   and success/failure artifact contracts.

2. `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md` — updated to add Section 0 quick
   status check, remove stale hard-coded counts from Section 7, and add campaign spec
   to reference block.

3. `tools/gates/capture_status.py` — read-only quota-status helper. Prints compact
   shortage table (or JSON). Exit 0 when complete, exit 1 when shortage. One command
   to check progress without running the full audit.

4. `tests/test_capture_status.py` — 4 offline deterministic tests.

5. `docs/CURRENT_STATE.md` — updated to reflect no-gate-core-changes-needed status
   and link to campaign packet tools.

### Starting State (as of this task)

- 10/50 tapes qualify for Gate 2
- sports=15 shortage, politics=9, crypto=10, new_market=5, near_resolution=1
- All Silver reconstruction routes exhausted
- Next: operator live Gold shadow capture per CORPUS_GOLD_CAPTURE_RUNBOOK.md

### What Was NOT Changed

- Gate 2 threshold (>= 70%) — unchanged
- min_events=50 — unchanged
- benchmark_v1 artifacts — immutable, untouched
- Strategy (market_maker_v1) — no changes
- Gate 3, Stage 0, Stage 1, Track 2 — not touched

## Tests

- `tests/test_capture_status.py`: 4 tests, all passing
- Full suite regression: run `python -m pytest tests/ -x -q --tb=short` before merging

## Next Operator Action

```bash
# Check current shortage
python tools/gates/capture_status.py

# Capture a sports tape (replace SLUG and timestamp)
python -m polytool simtrader shadow \
    --market <SLUG> \
    --strategy market_maker_v1 \
    --duration 600 \
    --record-tape \
    --tape-dir "artifacts/simtrader/tapes/sports_<SLUG>_<YYYYMMDDTHHMMSSZ>"

# After each batch, re-audit
python tools/gates/corpus_audit.py \
    --tape-roots artifacts/simtrader/tapes \
    --tape-roots artifacts/silver \
    --tape-roots artifacts/tapes \
    --out-dir artifacts/corpus_audit \
    --manifest-out config/recovery_corpus_v1.tape_manifest

# When corpus_audit exits 0, run Gate 2
python tools/gates/close_mm_sweep_gate.py \
    --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
    --out artifacts/gates/mm_sweep_gate
```
```

Also update `.planning/STATE.md`: append to the "Quick Tasks Completed" table:
```
| 029 | Phase 1B gold capture campaign packet: campaign spec, runbook tightened, capture_status.py helper (exit 0/1), 4 tests, CURRENT_STATE.md updated | 2026-03-27 | <commit> | [29-convert-phase-1b-to-clean-operator-captu](./quick/29-convert-phase-1b-to-clean-operator-captu/) |
```
And update "Last activity" in STATE.md to:
```
Last activity: 2026-03-27 - Completed quick-029: Phase 1B gold capture campaign packet. Campaign spec, tightened runbook, capture_status.py helper (shortage table, exit 0/1), 4 tests, CURRENT_STATE.md updated to reflect no-gate-core-changes-needed status.
```

**Verify:**
```bash
python -m pytest tests/ -x -q --tb=short
```
No regressions. Exact count reported.

**Done:** CURRENT_STATE.md correctly says "awaiting live Gold capture, no gate-core changes needed." Dev log exists. STATE.md updated. All existing tests pass.

---

## Execution Order

Tasks 1 and 2 are independent — they touch non-overlapping files and can be done in
either order. Task 3 (docs/CURRENT_STATE.md + dev log) should be done last so the
dev log can accurately report what was completed.

Recommended sequence: Task 2 first (code + tests, verify passing), then Task 1
(docs only), then Task 3 (final state update).

## Constraints (Non-Negotiable)

- Do NOT weaken `min_events=50` or the `>= 70%` Gate 2 threshold anywhere
- Do NOT modify any `benchmark_v1.*` file
- Do NOT add strategy tuning or gate-core changes
- Do NOT use "Phase 1B complete" or "Gate 2 ready" language — the corpus is NOT qualified
- Do NOT attempt live capture
- `capture_status.py` is READ-ONLY — it must never write any file
- All existing tests must pass after Task 3 regression run
