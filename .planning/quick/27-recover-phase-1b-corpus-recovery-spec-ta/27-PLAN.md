# Quick Task 027 — Phase 1B Corpus Recovery

**Slug:** recover-phase-1b-corpus-recovery-spec-ta
**Branch:** phase-1B
**Created:** 2026-03-26

---

## Situation

Gate 2 is correctly NOT_RUN (exit 0). Root cause established by quick-026:
- 41/50 benchmark_v1 tapes are SKIPPED_TOO_SHORT (effective_events < 50)
- 9/50 qualifying tapes: all near_resolution Silver, all RAN_ZERO_PROFIT/no_touch
- strategy behavior is correct; corpus quality is the blocker

benchmark_v1 is finalized and must not be mutated. A recovery corpus must be
built separately, qualified, and only then used to rerun Gate 2.

---

## Tasks

### Task 1 — Write the recovery corpus spec

**Objective:** Create an authoritative spec defining corpus recovery rules so
every subsequent task is building against an explicit written contract.

**Files to create:**
- `docs/specs/SPEC-phase1b-corpus-recovery-v1.md`

**Spec must cover:**
1. benchmark_v1 preservation rule — immutable reference corpus, never overwritten
2. Recovery corpus admission rules:
   - Minimum effective_events per tape: >= 50 (same as Gate 2 threshold; never soften)
   - Accepted tiers: Gold (preferred) or Silver-with-fills (price_2min-only Silver does
     not qualify unless effective_events >= 50 and fills exist in the tape)
   - Bucket quotas matching benchmark_v1: politics=10, sports=15, crypto=10,
     near_resolution=10, new_market=5 (total 50)
3. Manifest versioning policy:
   - New manifest name: `config/recovery_corpus_v1.tape_manifest`
   - benchmark_v1 lock/audit/manifest remain untouched
   - Recovery manifest follows the same JSON array format (list of events.jsonl paths)
4. Gate 2 rerun preconditions:
   - recovery manifest must contain >= 50 tapes
   - each tape must pass mm_sweep's min_events=50 check at runtime
   - all five buckets must be represented (>= 1 tape per bucket minimum;
     >= 70% bucket fill recommended before declaring corpus ready)
   - rerun command: `python tools/gates/close_mm_sweep_gate.py --benchmark-manifest
     config/recovery_corpus_v1.tape_manifest --out artifacts/gates/mm_sweep_gate`
5. Success/failure artifact contract:
   - On qualified manifest built: emit `artifacts/corpus_audit/recovery_corpus_audit.md`
     and `config/recovery_corpus_v1.tape_manifest`
   - On shortage: emit `artifacts/corpus_audit/shortage_report.md` with exact counts
     needed per bucket/tier
   - Gate 2 rerun produces `artifacts/gates/mm_sweep_gate/gate_passed.json` or
     `gate_failed.json` per existing SPEC-phase1b-gate2-shadow-packet.md §2.3
6. Gold tape capture flow requirements (pointer to Task 4)

**Tests to add:** None — this is a documentation task.

**Commit message:** `docs(quick-027): add SPEC-phase1b-corpus-recovery-v1 recovery corpus contract`

---

### Task 2 — Implement corpus audit tool

**Objective:** Build `tools/gates/corpus_audit.py` — a read-only tool that
scans all tape inventory, applies admission rules from Task 1's spec, and
either writes a qualified recovery manifest or an exact shortage report.

**Files to create:**
- `tools/gates/corpus_audit.py`
- `tests/test_corpus_audit.py`

**Implementation details:**

`corpus_audit.py` must:
- Accept `--tape-roots` (repeatable, default: `artifacts/simtrader/tapes`,
  `artifacts/silver`, `artifacts/tapes`) to discover candidate tape dirs
- Accept `--out-dir` (default: `artifacts/corpus_audit`)
- Accept `--min-events` (default: 50, never weaken)
- Accept `--manifest-out` (default: `config/recovery_corpus_v1.tape_manifest`)
- For each tape dir found, call the existing `discover_mm_sweep_tapes`-style
  logic (reuse `TapeCandidate` and effective_events counting from `mm_sweep.py`)
  to get: events_path, effective_events, bucket, tier
- Apply admission rules:
  - effective_events >= min_events
  - bucket must be one of the five valid buckets (politics/sports/crypto/
    near_resolution/new_market); tapes with no bucket label are rejected
    with reason "no_bucket_label"
  - tier "gold" always accepted if events pass; tier "silver" accepted only
    if effective_events >= min_events (same rule — do not add tier-specific
    weakening)
  - Reject duplicate tape dirs (same canonical path = same tape)
- Group qualified tapes by bucket, applying quota caps:
  politics=10, sports=15, crypto=10, near_resolution=10, new_market=5
  (select up to quota per bucket; prefer Gold over Silver when oversubscribed;
  within same tier, prefer higher effective_events)
- If total qualified >= 50 AND all buckets have >= 1 tape:
  - Write `config/recovery_corpus_v1.tape_manifest` (JSON array of events_path strings)
  - Write `artifacts/corpus_audit/recovery_corpus_audit.md` with:
    - per-tape table: tape_dir, bucket, tier, effective_events, status (ACCEPTED/REJECTED)
    - reject reason for each rejected tape
    - summary: total scanned, accepted, rejected by reason, count by bucket/tier
    - "Qualified manifest written to: ..." line
- If total qualified < 50 OR any bucket is empty:
  - Write `artifacts/corpus_audit/shortage_report.md` with:
    - current qualified count per bucket and tier
    - exact shortage: how many more tapes needed per bucket
    - recommended action per bucket (e.g. "record 8 Gold shadow tapes in sports bucket")
  - Exit 1 (shortage is a signal to the operator, not a crash)
- Print summary table to stdout regardless of outcome
- Do NOT write `recovery_corpus_v1.tape_manifest` when shortage exists (partial
  manifest would be invalid for Gate 2)

`test_corpus_audit.py` must cover (TDD — write tests first):
1. `test_qualified_tape_accepted`: a tape dir with effective_events >= 50 and valid
   bucket/tier is accepted
2. `test_too_short_tape_rejected`: effective_events < 50 → REJECTED reason "too_short"
3. `test_no_bucket_label_rejected`: tape with no bucket metadata → REJECTED reason
   "no_bucket_label"
4. `test_quota_cap_per_bucket`: if 12 sports tapes qualify, only 15 are selected
   (or whichever are available up to quota); excess tapes appear as REJECTED with
   reason "over_quota"
5. `test_shortage_when_below_50`: corpus with only 5 qualified tapes → exits 1,
   shortage_report.md written, recovery_corpus_v1.tape_manifest NOT written
6. `test_qualified_manifest_written_when_sufficient`: mock 50+ tapes across all
   5 buckets meeting min_events → manifest JSON written, audit report written,
   exits 0

**Commit message:** `feat(quick-027): add corpus_audit tool for recovery manifest builder (TDD)`

---

### Task 3 — Execute corpus audit and produce recovery artifact

**Objective:** Run the corpus audit against current inventory and produce either
a qualified recovery manifest (which enables Gate 2 rerun) or an exact shortage
report (which tells the operator exactly what tapes to capture).

**Files to create/modify:**
- `artifacts/corpus_audit/recovery_corpus_audit.md` (created by tool)
- `config/recovery_corpus_v1.tape_manifest` (created by tool if corpus qualifies)
- OR `artifacts/corpus_audit/shortage_report.md` (created by tool if corpus insufficient)
- `docs/dev_logs/2026-03-26_phase1b_corpus_recovery.md` (mandatory dev log)

**Execution steps:**

1. Run corpus audit against all known tape roots:
   ```
   python tools/gates/corpus_audit.py \
       --tape-roots artifacts/simtrader/tapes \
       --tape-roots artifacts/silver \
       --tape-roots artifacts/tapes \
       --out-dir artifacts/corpus_audit \
       --manifest-out config/recovery_corpus_v1.tape_manifest
   ```

2. Inspect output. Two branches:

   **Branch A — shortage report produced (most likely given diagnostic findings):**
   - `artifacts/corpus_audit/shortage_report.md` shows exact tape counts needed
   - Do NOT attempt Gate 2 rerun
   - Record shortage report path, counts, and recommended next action in dev log

   **Branch B — qualified manifest produced:**
   - `config/recovery_corpus_v1.tape_manifest` exists with >= 50 qualified tapes
   - Rerun Gate 2:
     ```
     python tools/gates/close_mm_sweep_gate.py \
         --benchmark-manifest config/recovery_corpus_v1.tape_manifest \
         --out artifacts/gates/mm_sweep_gate
     ```
   - Run gate_status to capture current state:
     ```
     python tools/gates/gate_status.py
     ```
   - Record Gate 2 verdict in dev log

3. Write `docs/dev_logs/2026-03-26_phase1b_corpus_recovery.md` with required sections
   (see task description in the task header). Must include:
   - Files changed and why
   - Commands run and their output
   - Tests run and pass/fail counts
   - benchmark_v1 preservation decision (document explicitly: "benchmark_v1 lock/audit/
     manifest were not modified")
   - Recovery manifest path OR shortage report path
   - Qualified tape counts by bucket and tier
   - Whether Gate 2 was rerun, and if so the verdict
   - Exact blocker for next phase if still blocked

4. Run full regression suite to confirm no regressions:
   ```
   python -m pytest tests/ -x -q --tb=short
   ```
   Report exact counts.

**Tests to add:** None in this task — existing tests cover corpus_audit (Task 2).
The regression run here is the verification.

**Commit message:** `feat(quick-027): execute corpus audit, emit recovery manifest or shortage report`

---

### Task 4 — Document Gold tape capture runbook

**Objective:** Write an operator runbook for capturing Gold shadow tapes that
qualify for the recovery corpus. This is the primary path to unblocking Gate 2
when a shortage exists.

**Files to create:**
- `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`

**Runbook must cover:**
1. Overview: why Gold tapes are preferred (live shadow recording, Gold tier,
   high effective_events, real market microstructure)
2. Prerequisites: Docker running, ClickHouse up, `CLICKHOUSE_PASSWORD` set,
   `python -m polytool --help` loads without error
3. Determine which buckets still need tapes:
   ```
   python tools/gates/corpus_audit.py --tape-roots ... (see Task 3 command)
   ```
   Read `artifacts/corpus_audit/shortage_report.md` for exact counts needed
   per bucket.
4. Capture flow (one tape at a time):
   ```
   # Replace SLUG and BUCKET with actual values
   python -m polytool simtrader shadow \
       --market <SLUG> \
       --strategy market_maker_v1 \
       --duration 600 \
       --record-tape \
       --tape-dir artifacts/simtrader/tapes/<BUCKET>_<SLUG>_<YYYYMMDDTHHMMSSZ>
   ```
   Minimum recommended duration: 600 seconds (10 minutes) to accumulate >= 50
   effective_events on active markets. Crypto up/down markets typically reach
   50+ events in under 5 minutes.
5. Validate each new tape immediately after capture:
   ```
   python tools/gates/mm_sweep_diagnostic.py \
       --benchmark-manifest config/benchmark_v1.tape_manifest
   ```
   The new tape won't appear in benchmark_v1 but you can run corpus_audit
   to check the new tape's effective_events count.
6. Resumability: corpus_audit always scans all roots and recomputes from
   scratch — run it after each new tape to see updated counts. Each shadow
   session writes a new tape dir (timestamped), so re-running never
   overwrites existing tapes.
7. Bucket targeting: map Polymarket market categories to corpus buckets:
   - crypto markets (BTC/ETH/SOL up/down) → `crypto` bucket
   - NHL/NBA/NFL/soccer → `sports` bucket
   - US elections / political → `politics` bucket
   - markets within 48h of resolution → `near_resolution` bucket
   - newly listed markets (< 7 days old) → `new_market` bucket
8. Stopping condition: run corpus_audit until it reports exit 0 and
   `config/recovery_corpus_v1.tape_manifest` is written, then proceed to
   Gate 2 rerun (Task 3, Branch B).
9. No live capital: shadow mode never submits real orders; all capture
   sessions are safe to run.

**Tests to add:** None — this is a documentation task.

**Commit message:** `docs(quick-027): add corpus Gold capture runbook for Gate 2 recovery path`

---

### Task 5 — Update CURRENT_STATE.md and STATE.md

**Objective:** Bring authority docs up to date so the next session starts from
accurate context.

**Files to modify:**
- `docs/CURRENT_STATE.md` — update Gate 2 status section and corpus recovery state
- `.planning/STATE.md` — record quick-027 completion and updated blocker

**CURRENT_STATE.md updates:**
- Update Gate 2 block description to reference the recovery corpus spec and tooling
- Add: "Recovery corpus tooling: `tools/gates/corpus_audit.py` — scans tape inventory,
  applies admission rules, writes `config/recovery_corpus_v1.tape_manifest` or
  `artifacts/corpus_audit/shortage_report.md`."
- Add: "Gold tape capture runbook: `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`"
- Update corpus status based on what Task 3 produced (manifest built or shortage reported)
- If Gate 2 was rerun in Task 3: record verdict

**STATE.md updates:**
- Add quick-027 row to the completed table with date, commit, directory
- Update "Blockers/Concerns" section:
  - If shortage: "Track 1 Gate 2 corpus: recovery corpus tooling is in place
    (`corpus_audit.py`). Shortage report at `artifacts/corpus_audit/shortage_report.md`
    shows exact tape counts needed. Next step: capture Gold shadow tapes per
    `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`."
  - If Gate 2 PASSED: remove the corpus blocker note, add Gate 3 as next item
  - If Gate 2 FAILED (strategy result): note the strategy failure with pass rate

**Tests to add:** None — documentation update.

**Commit message:** `docs(quick-027): update CURRENT_STATE.md and STATE.md with corpus recovery status`

---

## Dependency Order

```
Task 1 (spec) --> Task 2 (tool, TDD) --> Task 3 (execution + dev log)
                                              |
                  Task 4 (runbook) -----------> (no dependency, can run after Task 1)
                                              |
                  Task 5 (state update) <---- Task 3 (needs results)
```

Recommended execution order: 1 → 2 → 3 → 4 → 5

---

## Constraints Checklist

- [ ] benchmark_v1 lock/audit/manifest are not modified
- [ ] Gate 2 threshold >= 0.70 is not weakened anywhere
- [ ] min_events=50 is not softened in corpus_audit.py
- [ ] No live capital (shadow mode only for Gold capture)
- [ ] No Gate 3 until Gate 2 truly passes
- [ ] All new code has tests (corpus_audit.py has 6 tests in test_corpus_audit.py)
- [ ] Full regression suite passes before final commit
- [ ] Dev log written at docs/dev_logs/2026-03-26_phase1b_corpus_recovery.md

---

## Expected Outcomes

**Most likely outcome (current inventory insufficient):**
- `artifacts/corpus_audit/shortage_report.md` written
- Exact shortage per bucket documented (all buckets short except near_resolution
  which has 9 tapes but all sub-50-events)
- `config/recovery_corpus_v1.tape_manifest` NOT written
- Gate 2 NOT rerun
- Operator directed to `docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md`

**If current inventory surprisingly qualifies:**
- `config/recovery_corpus_v1.tape_manifest` written with >= 50 tapes
- Gate 2 rerun against recovery manifest
- Verdict recorded (PASS or FAIL based on actual strategy performance)
