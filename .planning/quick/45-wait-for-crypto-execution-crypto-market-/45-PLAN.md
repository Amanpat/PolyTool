---
phase: quick-045
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docs/CURRENT_STATE.md
  - docs/dev_logs/2026-03-29_crypto_watch_and_capture.md
  - artifacts/tapes/shadow/  # only if Branch B
  - config/recovery_corpus_v1.tape_manifest  # only if corpus_audit exits 0
  - artifacts/gates/mm_sweep_gate/  # only if Gate 2 runs
autonomous: false
requirements: []
must_haves:
  truths:
    - "Operator knows whether BTC/ETH/SOL 5m/15m pair markets exist right now"
    - "If markets absent: dev log records watcher output and status=WAITING_FOR_CRYPTO_MARKETS, no manifests changed"
    - "If markets present: 10 qualifying crypto Gold tapes added to corpus, corpus_audit exits 0 (50/50), Gate 2 sweep runs, gate_status reports outcome"
  artifacts:
    - path: "docs/dev_logs/2026-03-29_crypto_watch_and_capture.md"
      provides: "Mandatory dev log regardless of branch taken"
    - path: "docs/CURRENT_STATE.md"
      provides: "Updated checkpoint reflecting outcome"
  key_links:
    - from: "corpus_audit.py exit code"
      to: "close_mm_sweep_gate.py"
      via: "only invoked when exit code is 0"
      pattern: "exit 0 -> proceed; exit 1 -> stop at checkpoint"
---

<objective>
Execute the WAIT_FOR_CRYPTO policy for the remaining crypto corpus gap.

Purpose: Determine whether BTC/ETH/SOL 5m/15m pair markets have returned to Polymarket. If yes, capture 10+ qualifying Gold tapes, run corpus_audit to reach 50/50, and immediately run Gate 2. If no, record exact evidence and stop without changing any manifest.

Output:
- Branch A (absent): dev log with watcher output, CURRENT_STATE.md checkpoint note, no manifest changes.
- Branch B (present): 10+ crypto Gold tapes under artifacts/tapes/shadow/, corpus_audit at 50/50, config/recovery_corpus_v1.tape_manifest updated, Gate 2 sweep result under artifacts/gates/mm_sweep_gate/.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/docs/runbooks/CORPUS_GOLD_CAPTURE_RUNBOOK.md
@D:/Coding Projects/Polymarket/PolyTool/docs/specs/ADR-benchmark-versioning-and-crypto-unavailability.md

<!-- Key constraints (inline for executor speed) -->
<!-- 1. benchmark_v1 is LOCKED — do NOT touch config/benchmark_v1.* -->
<!-- 2. Gate 2 manifest path: config/recovery_corpus_v1.tape_manifest -->
<!-- 3. Path drift fix after shadow capture: move artifacts/simtrader/tapes/*/ to artifacts/tapes/shadow/ -->
<!-- 4. Binary markets need >= 100 raw events (effective = raw // 2 per 2 asset IDs); use --duration 900 -->
<!-- 5. crypto-pair-watch has no --one-shot flag; use --timeout 30 --watch to get a single-poll exit -->
</context>

<tasks>

<task type="auto">
  <name>Task 1: Preflight + one-shot availability check</name>
  <files>(read-only: no files written by this task)</files>
  <action>
    Run the following two commands and capture their full output for the checkpoint decision.

    1. Confirm corpus shortage is crypto-only:
       ```
       python tools/gates/capture_status.py
       ```
       Expected: exit 1, crypto=10 shortage only, all other buckets at 0 shortage.
       If any other bucket shows a shortage, STOP and surface the discrepancy before proceeding.

    2. Run a single-poll availability check (--timeout 30 exits quickly if no markets):
       ```
       python -m polytool crypto-pair-watch --watch --timeout 30 --poll-interval 15
       ```
       This polls twice (at 0s and 15s) then exits after 30s. Record:
       - Exit code (0 = markets found, 1 = timeout/none found)
       - Printed market list (if any)
       - Number of eligible markets found

    Preserve both outputs verbatim — they are the primary evidence for the checkpoint decision.
  </action>
  <verify>
    Both commands complete without Python import errors. capture_status.py exits with a numeric code (0 or 1). crypto-pair-watch exits within 45 seconds.
  </verify>
  <done>
    Operator has exact corpus shortage table and watcher exit code + output. No files have been modified.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 2: Branch decision — markets present or absent?</name>
  <action>Pause for operator to review Task 1 outputs and decide which branch to execute.</action>
  <verify>Operator replies with "proceed-capture" or "stop-waiting".</verify>
  <done>Branch selected. Executor knows which path Task 3 will take.</done>
  <what-built>
    Task 1 ran capture_status.py (shortage table) and crypto-pair-watch --watch --timeout 30 (single availability poll). Both outputs are printed above.
  </what-built>
  <how-to-verify>
    Review the two command outputs from Task 1:

    1. Does capture_status.py confirm crypto=10 is the ONLY shortage?
       - If other buckets also show shortage: investigation needed before proceeding.

    2. Did crypto-pair-watch exit 0 (markets found) or exit 1 (timeout / none found)?
       - Exit 0: Branch B — proceed with capture (reply "proceed-capture")
       - Exit 1: Branch A — stop cleanly (reply "stop-waiting")
       - Markets found but you want to defer: reply "stop-waiting"

    Reply with exactly one of:
      "proceed-capture" — markets are available, continue to Task 3 (capture + Gate 2)
      "stop-waiting"    — markets are absent, continue to Task 3 (dev log only)
  </how-to-verify>
  <resume-signal>Reply "proceed-capture" or "stop-waiting"</resume-signal>
</task>

<task type="auto">
  <name>Task 3: Branch A (stop-waiting) dev log only — OR — Branch B (proceed-capture) capture + audit + Gate 2</name>
  <files>
    docs/dev_logs/2026-03-29_crypto_watch_and_capture.md
    docs/CURRENT_STATE.md
    artifacts/tapes/shadow/  [Branch B only]
    config/recovery_corpus_v1.tape_manifest  [Branch B only, only if corpus_audit exits 0]
    artifacts/gates/mm_sweep_gate/  [Branch B only, only if Gate 2 runs]
  </files>
  <action>
    === BRANCH A (stop-waiting): markets absent ===

    1. Write dev log at docs/dev_logs/2026-03-29_crypto_watch_and_capture.md:

       # 2026-03-29 Crypto Watch — WAITING_FOR_CRYPTO_MARKETS

       ## Summary
       Ran WAIT_FOR_CRYPTO execution check per quick-045 plan.

       ## Status
       status: WAITING_FOR_CRYPTO_MARKETS

       ## Capture Status Output
       [paste capture_status.py output verbatim]

       ## Watcher Output
       [paste crypto-pair-watch output verbatim]

       ## Conclusion
       No eligible BTC/ETH/SOL 5m/15m pair markets found on Polymarket as of 2026-03-29.
       No manifests changed. benchmark_v1 untouched. recovery_corpus_v1 not updated.
       Corpus remains at 40/50 (crypto=0/10 blocked).

       ## Next Step
       Recheck with: python -m polytool crypto-pair-watch --watch --timeout 30
       When markets appear, run quick-045 again.

    2. Update docs/CURRENT_STATE.md — find the crypto bullet point inside the Gate 2 status
       section and append:
       "**2026-03-29 quick-045 check:** crypto-pair-watch returned no eligible markets.
       Corpus still at 40/50. WAIT_FOR_CRYPTO policy unchanged. Recheck next session."
       Do NOT remove or overwrite any existing content.

    3. Do NOT modify config/benchmark_v1.*, config/recovery_corpus_v1.tape_manifest,
       or any artifacts/gates/ path.

    STOP here for Branch A. Branch A is complete.

    ---

    === BRANCH B (proceed-capture): markets present ===

    Step B1 — Identify target market slugs

    Run again to get slugs:
    ```
    python -m polytool crypto-pair-watch --watch --timeout 30
    ```
    Extract market slugs from output. Target: BTC/ETH/SOL, durations 5m or 15m.
    Need 10 qualifying tapes minimum; capture 12-14 for buffer (some may reject).

    Step B2 — Capture shadow sessions (main loop)

    For each target market slug (repeat 12-14 times, varying across markets):
    ```
    python -m polytool simtrader shadow \
        --market <SLUG> \
        --strategy market_maker_v1 \
        --duration 900 \
        --record-tape \
        --tape-dir "artifacts/simtrader/tapes/crypto_<SLUG_SHORT>_$(date -u +%Y%m%dT%H%M%SZ)"
    ```
    Use --duration 900 (15 min) to ensure >= 100 raw events for binary markets.
    Vary markets across BTC/ETH/SOL and both 5m/15m if multiple are available.
    Shadow mode never submits real orders — all sessions are safe.

    Step B3 — Path drift fix

    After all captures, move tapes to canonical path:
    ```
    for dir in artifacts/simtrader/tapes/*/; do
        mv "$dir" "artifacts/tapes/shadow/$(basename "$dir")"
    done
    ```
    Verify: ls artifacts/tapes/shadow/ shows the new crypto_* directories.

    Step B4 — corpus_audit

    ```
    python tools/gates/corpus_audit.py \
        --out-dir artifacts/corpus_audit \
        --manifest-out config/recovery_corpus_v1.tape_manifest
    ```
    (No --tape-roots needed; defaults pick up artifacts/tapes/gold, artifacts/tapes/silver,
    and artifacts/tapes.)

    Check output:
    - Exit 0: corpus is 50/50. Proceed to Step B5.
    - Exit 1: crypto bucket still short. Capture more tapes (return to Step B2).
      Do NOT invoke Gate 2 if corpus_audit exits 1.

    Step B5 — Gate 2 sweep (only if corpus_audit exited 0)

    ```
    python tools/gates/close_mm_sweep_gate.py \
        --manifest config/recovery_corpus_v1.tape_manifest \
        --out artifacts/gates/mm_sweep_gate \
        --threshold 0.70
    ```

    Step B6 — Gate status

    ```
    python tools/gates/gate_status.py
    ```
    Record the output verbatim.

    Step B7 — Dev log

    Write docs/dev_logs/2026-03-29_crypto_watch_and_capture.md:

    # 2026-03-29 Crypto Watch and Capture — Gate 2 Execution

    ## Summary
    Markets found. Captured N crypto Gold tapes. corpus_audit exit: X.
    [If Gate 2 ran:] Gate 2 result: PASS/FAIL/NOT_RUN.

    ## Tapes Captured
    [list tape dirs and their effective_events from corpus_audit output]

    ## corpus_audit Output
    [verbatim]

    ## Gate 2 Output
    [verbatim, or N/A if corpus_audit exited 1]

    ## gate_status Output
    [verbatim]

    ## Outcome
    [PASSED / FAILED / NOT_RUN with reason]

    Step B8 — Update CURRENT_STATE.md

    Update the Gate 2 / crypto bullet point to reflect:
    - New corpus count (50/50)
    - Gate 2 outcome (PASSED / FAILED / NOT_RUN)
    Do NOT touch benchmark_v1 bullets or other phase sections.
  </action>
  <verify>
    Branch A: docs/dev_logs/2026-03-29_crypto_watch_and_capture.md exists with
    status=WAITING_FOR_CRYPTO_MARKETS; CURRENT_STATE.md has the checkpoint note appended;
    git diff shows no changes to config/benchmark_v1.* or config/recovery_corpus_v1.tape_manifest.

    Branch B: dev log exists with corpus_audit and Gate 2 outputs; corpus_audit exited 0 before
    Gate 2 was invoked; config/recovery_corpus_v1.tape_manifest updated; Gate 2 artifacts
    present in artifacts/gates/mm_sweep_gate/; CURRENT_STATE.md updated.
  </verify>
  <done>
    Branch A: Evidence recorded, policy unchanged, operator knows to recheck next session.
    Branch B: Gate 2 has run and produced a definitive PASS or FAIL result against the
    50-tape recovery corpus. CURRENT_STATE.md reflects the final outcome.
  </done>
</task>

</tasks>

<verification>
1. docs/dev_logs/2026-03-29_crypto_watch_and_capture.md exists and contains watcher output verbatim.
2. docs/CURRENT_STATE.md has been updated (checkpoint note or Gate 2 result).
3. config/benchmark_v1.* files are unchanged — verify with: git diff config/benchmark_v1.*
4. Branch A only: config/recovery_corpus_v1.tape_manifest is not modified.
5. Branch B only: corpus_audit exited 0 before Gate 2 was invoked. Gate 2 artifacts exist.
</verification>

<success_criteria>
- Watcher output captured with exact exit code and market list (or empty list).
- Dev log written with status clearly labeled (WAITING_FOR_CRYPTO_MARKETS or Gate 2 outcome).
- CURRENT_STATE.md updated with checkpoint note or Gate 2 result.
- benchmark_v1 untouched (zero diff on config/benchmark_v1.*).
- If markets present and corpus reaches 50/50: Gate 2 has run and result is recorded.
</success_criteria>

<output>
After completion, create `.planning/quick/45-wait-for-crypto-execution-crypto-market-/45-SUMMARY.md`
</output>
