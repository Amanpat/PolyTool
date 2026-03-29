---
phase: quick-050
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - tools/gates/tape_integrity_audit.py
  - artifacts/debug/tape_integrity_audit_report.md
  - docs/dev_logs/2026-03-29_tape_integrity_audit.md
  - docs/CURRENT_STATE.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Every tape root is scanned (gold, silver, shadow, crypto/new_market, crypto/paper_runs)"
    - "YES/NO token ID distinctness is verified for all binary-leg tapes"
    - "Structural issues (missing files, unparseable JSONL, truncation) are counted per root"
    - "Timestamp monotonicity is checked and violations are flagged"
    - "Cadence summary (inter-event gap median/p95) is produced for shadow tapes"
    - "Report artifact exists at artifacts/debug/tape_integrity_audit_report.md with binary verdict"
    - "Dev log exists at docs/dev_logs/2026-03-29_tape_integrity_audit.md"
  artifacts:
    - path: "tools/gates/tape_integrity_audit.py"
      provides: "Audit script covering all 5 check dimensions"
      exports: ["main", "audit_tape_roots"]
    - path: "artifacts/debug/tape_integrity_audit_report.md"
      provides: "Audit report with verdict SAFE_TO_USE or CORPUS_REPAIR_NEEDED"
      contains: "## Verdict"
    - path: "docs/dev_logs/2026-03-29_tape_integrity_audit.md"
      provides: "Dev log with findings, commands, verdict, next work packet"
  key_links:
    - from: "tools/gates/tape_integrity_audit.py"
      to: "artifacts/debug/tape_integrity_audit_report.md"
      via: "script writes report on completion"
    - from: "report verdict"
      to: "docs/CURRENT_STATE.md"
      via: "one-line integrity status note added to CURRENT_STATE.md"
---

<objective>
Audit all collected tape corpus roots for structural, semantic, and cadence integrity before further Gate 2 or Track 2 decisions. The primary concern is the Phase 1A observation where YES and NO values appeared identical in some crypto 5m markets — this audit must determine if that was a real mapping bug in captured tapes or just symmetric market state.

Purpose: Produce hard evidence that the corpus is trustworthy (or identify which tapes are not) before committing to any strategy-improvement or deployment work that depends on corpus data.
Output: Audit report at artifacts/debug/tape_integrity_audit_report.md with binary verdict, dev log, CURRENT_STATE.md integrity note.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md

<!-- Key interfaces the executor needs -->
<interfaces>
<!-- Tape roots (canonical post quick-036 restructure) -->
- artifacts/tapes/gold/         -- 8 subdirs, structure: events.jsonl + meta.json (+ raw_ws.jsonl for some)
- artifacts/tapes/silver/       -- 131 subdirs, nested: {market_id}/{timestamp}/silver_events.jsonl + silver_meta.json + market_meta.json
- artifacts/tapes/shadow/       -- 181 subdirs, structure: events.jsonl + meta.json + market_meta.json + watch_meta.json + raw_ws.jsonl
- artifacts/tapes/crypto/new_market/ -- 5 subdirs (bnb/btc/doge/eth/hype updown 5m), structure: events.jsonl + raw_ws.jsonl + watch_meta.json
- artifacts/tapes/crypto/paper_runs/ -- date-bucketed dirs (2026-03-25/26/28/29), each with session_id dirs containing run_manifest.json, runtime_events.jsonl (NOT events.jsonl — different schema)

<!-- YES/NO token identity in shadow tape meta.json -->
{
  "shadow_context": {
    "yes_token_id": "6014005...",
    "no_token_id": "3631616...",
    "asset_ids": ["6014005...", "3631616..."]
  }
}

<!-- watch_meta.json structure (gold and some shadow tapes) -->
{
  "yes_asset_id": "112743...",
  "no_asset_id": "29663...",
  "bucket": "new_market",
  "regime": "new_market"
}

<!-- events.jsonl line shapes (two schemas both present in corpus) -->
-- Legacy (gold/silver): {"seq": 0, "ts_recv": 1774136519.42, "asset_id": "112743...", "event_type": "book", "bids": [...], "asks": [...]}
-- Modern (shadow): {"seq": 2, "ts_recv": 1774136806.18, "price_changes": [{"asset_id": "112743...", "best_bid": "0.5", "best_ask": "0.51"}, ...], "event_type": "price_change"}

<!-- Binary identity check: in the btc new_market tape sampled, YES and NO asset_ids are distinct:
     YES: 112743211105732682824065853522599256301175382192545822114934232230980207992039
     NO:  29663479610622343352156301036037666097886386790898410612123158446043075288392
     These are DIFFERENT — this is the correct / healthy state.
     The bug reported was: "same values in both YES and NO" — that would manifest as
     both asset_ids being equal, or both best_bid/best_ask streams being bit-for-bit identical. -->

<!-- paper_runs use a different artifact schema — no events.jsonl, use runtime_events.jsonl -->
-- run_manifest.json has "artifacts.runtime_events_path"
-- paper_runs are NOT replay tapes; they record strategy decisions, not raw WS events
-- Do NOT apply structural tape checks to paper_runs; report them separately as "paper run artifacts"

<!-- existing corpus_audit.py in tools/gates/ covers admission rules but NOT:
     - YES/NO token distinctness
     - Timestamp monotonicity
     - Quote equality / duplication detection
     - Cadence / inter-event gap statistics
     Those are the 4 gaps this audit fills. -->
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write tape_integrity_audit.py and run it across all tape roots</name>
  <files>tools/gates/tape_integrity_audit.py</files>
  <action>
Create `tools/gates/tape_integrity_audit.py`. The script performs 5 audit dimensions and writes a markdown report to `artifacts/debug/tape_integrity_audit_report.md`.

**Script structure:**

```
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TAPE_ROOTS = {
    "gold":         _REPO_ROOT / "artifacts/tapes/gold",
    "silver":       _REPO_ROOT / "artifacts/tapes/silver",
    "shadow":       _REPO_ROOT / "artifacts/tapes/shadow",
    "crypto_new":   _REPO_ROOT / "artifacts/tapes/crypto/new_market",
    # paper_runs excluded from structural tape checks — different artifact schema
}
```

**Dimension 1 — Structural check** (per tape dir):
- Required files present: at minimum `events.jsonl` (or `silver_events.jsonl` for silver). Flag tapes missing both.
- Parse every line of events.jsonl — catch json.JSONDecodeError, mark tape `JSONL_BROKEN`.
- Count lines; if count == 0, mark `EMPTY_TAPE`.
- Detect truncated last line: try `json.loads(last_line)` — if it fails AND file does not end with `\n`, mark `TRUNCATED`.

**Dimension 2 — Timestamp monotonicity** (per tape dir):
- Extract `ts_recv` from each event line (float, Unix seconds).
- Check `ts_recv[i] >= ts_recv[i-1]` for all consecutive events.
- Count violations. Mark tape `TIMESTAMP_VIOLATION` if any violations found.
- Record the first violation ts for report detail.

**Dimension 3 — YES/NO token distinctness** (binary tapes only):
Binary tapes = tapes from shadow/gold roots that have watch_meta.json OR meta.json with `shadow_context`.

For each binary tape:
1. Extract yes_token_id and no_token_id from `watch_meta.json` (fields: `yes_asset_id`/`no_asset_id`) or from `meta.json` (fields: `shadow_context.yes_token_id` / `shadow_context.no_token_id`).
2. If both IDs present and are equal: flag `YES_NO_SAME_TOKEN_ID` (definitive bug).
3. If only one ID found: flag `YES_NO_INCOMPLETE_MAPPING`.
4. If both distinct: proceed to quote-stream check.

**Quote-stream equality check** (only for tapes with distinct YES/NO IDs):
This checks the original concern — "same values for YES and NO across the entire run."
- For modern-schema tapes (price_changes[] events), collect (best_bid, best_ask) per asset_id over all events.
- For each asset, build a list of (ts_recv, best_bid, best_ask) tuples.
- Compare YES and NO streams: if the number of events is equal AND more than 90% of (best_bid, best_ask) pairs are identical at matching sequence positions, flag `QUOTE_STREAM_DUPLICATE` (likely mapping bug — same token fed to both legs).
- If YES/NO streams differ meaningfully (>10% divergence or different lengths), mark `QUOTE_STREAM_OK`.
- For book-only tapes (legacy schema, no price_changes): collect (best_bid=max(bids), best_ask=min(asks)) per asset_id from book events. Apply same 90% equality threshold.

**Dimension 4 — Replay fidelity indicators**:
- Missing initial book snapshot: if the first event is NOT `event_type == "book"` for legacy tapes, note `NO_INITIAL_SNAPSHOT` (warning, not error).
- Duplicate seq values: if any seq value appears more than once, flag `DUPLICATE_SEQ`.
- Record total unique asset_ids seen in tape.

**Dimension 5 — Cadence summary** (shadow tapes only, sample-based):
- For up to 20 shadow tapes selected uniformly across the shadow root:
  - Compute inter-event gaps: `gap[i] = ts_recv[i] - ts_recv[i-1]` for all i.
  - Compute median and p95 of gaps (use sorted list, pick index).
  - Aggregate across sampled tapes: report overall median and p95.
- Also read `packages/polymarket/crypto_pairs/paper_runner.py` DEFAULT_SCAN_INTERVAL or config to determine runner scan cadence (search for `scan_interval` or `sleep` calls with a constant). Document: "runner scan cadence: Xs, tape event cadence: median Ys, p95 Zs".

**Report format** (`artifacts/debug/tape_integrity_audit_report.md`):
```markdown
# Tape Corpus Integrity Audit Report
**Date:** 2026-03-29
**Roots scanned:** gold, silver, shadow, crypto_new_market

## Summary Table
| Root | Tapes | Clean | Suspicious | Bad |
...

## YES/NO Token Distinctness
(table: tape_dir, yes_id_prefix, no_id_prefix, result)

## Structural Issues
(table: tape_dir, root, issue)

## Timestamp Violations
(table: tape_dir, violation_count, first_violation_ts)

## Quote Stream Equality Check
(table: tape_dir, yes_events, no_events, pct_identical, verdict)

## Cadence Summary (Shadow Sample)
- Median inter-event gap: Xs
- p95 inter-event gap: Xs
- Runner scan cadence: Xs (from paper_runner.py)

## Paper Runs (separate)
- Roots: artifacts/tapes/crypto/paper_runs/
- Sessions found: N
- Schema: runtime_events.jsonl (not replay tapes)
- Structural tape checks do not apply; these are strategy decision logs

## Verdict
**SAFE_TO_USE** | **CORPUS_REPAIR_NEEDED**

Rationale: (1-3 sentences)

## Next Work Packet
(one sentence)
```

**Verdict logic:**
- `CORPUS_REPAIR_NEEDED` if: any `YES_NO_SAME_TOKEN_ID` flag OR any `QUOTE_STREAM_DUPLICATE` flag OR more than 10% of tapes in any root are `JSONL_BROKEN` or `EMPTY_TAPE`.
- `SAFE_TO_USE` otherwise (warnings like `NO_INITIAL_SNAPSHOT` do not block).

**CLI entry point:**
```python
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Tape corpus integrity audit")
    parser.add_argument("--out", default="artifacts/debug/tape_integrity_audit_report.md")
    parser.add_argument("--cadence-sample-n", type=int, default=20)
    args = parser.parse_args(argv)
    return run_audit(out_path=Path(args.out), cadence_sample_n=args.cadence_sample_n)

if __name__ == "__main__":
    raise SystemExit(main())
```

Run it after writing:
```
cd "D:/Coding Projects/Polymarket/PolyTool" && python tools/gates/tape_integrity_audit.py
```

Capture stdout and the report for use in Task 2.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python tools/gates/tape_integrity_audit.py && python -m pytest tests/ -x -q --tb=short -k "not test_wallet_only" 2>&1 | tail -5</automated>
  </verify>
  <done>
    Script runs without unhandled exceptions; artifacts/debug/tape_integrity_audit_report.md exists and contains "## Verdict" with either SAFE_TO_USE or CORPUS_REPAIR_NEEDED; all existing tests still pass.
  </done>
</task>

<task type="auto">
  <name>Task 2: Write dev log and update CURRENT_STATE.md</name>
  <files>docs/dev_logs/2026-03-29_tape_integrity_audit.md, docs/CURRENT_STATE.md</files>
  <action>
**Dev log** (`docs/dev_logs/2026-03-29_tape_integrity_audit.md`):

Write a dev log with these sections:
1. **Why this audit was run** — Phase 1A observation of identical YES/NO values in crypto 5m markets; needed to validate corpus before Gate 2 re-analysis or Track 2 deployment.
2. **Tape roots scanned** — list all five roots with tape counts.
3. **Commands run** — exact command(s) used.
4. **Findings summary** — counts of clean / suspicious / bad per root; specific YES/NO duplication findings (quote the token IDs if any same-ID bugs found, or confirm none found); timestamp violation counts; cadence findings (median/p95 inter-event gap vs runner scan cadence).
5. **Verdict** — SAFE_TO_USE or CORPUS_REPAIR_NEEDED with rationale.
6. **Next work packet** — one sentence.

**CURRENT_STATE.md update:**

Add a one-line integrity note in the "Status as of 2026-03-29" section, after the Gate 2 paragraph. Example format:
```
- **Tape integrity audit** (quick-050, 2026-03-29): All {N} tape roots scanned.
  Verdict: {SAFE_TO_USE | CORPUS_REPAIR_NEEDED}. Details:
  `artifacts/debug/tape_integrity_audit_report.md`.
```

Do NOT modify benchmark manifests, gate artifacts, roadmap prose, or any tape contents.
  </action>
  <verify>
    <automated>test -f "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-29_tape_integrity_audit.md" && grep -l "SAFE_TO_USE\|CORPUS_REPAIR_NEEDED" "D:/Coding Projects/Polymarket/PolyTool/docs/dev_logs/2026-03-29_tape_integrity_audit.md" && grep -l "tape integrity audit" "D:/Coding Projects/Polymarket/PolyTool/docs/CURRENT_STATE.md"</automated>
  </verify>
  <done>
    Dev log exists with all 6 required sections and a clear binary verdict; CURRENT_STATE.md contains the one-line integrity status note linking to the report artifact.
  </done>
</task>

</tasks>

<verification>
1. `python tools/gates/tape_integrity_audit.py` exits cleanly (exit 0 or 1 based on verdict, not due to script errors)
2. `artifacts/debug/tape_integrity_audit_report.md` exists and contains "## Verdict" with SAFE_TO_USE or CORPUS_REPAIR_NEEDED
3. Every tape root (gold/silver/shadow/crypto_new_market) appears in the report summary table
4. YES/NO token distinctness check results are present for all shadow/gold binary tapes
5. Quote-stream equality check results are present
6. Cadence section shows median + p95 inter-event gap for shadow sample
7. Paper runs section clarifies these are NOT subject to structural tape checks
8. Dev log has all 6 sections and matches report verdict
9. CURRENT_STATE.md has integrity note
10. Existing test suite passes: `python -m pytest tests/ -x -q --tb=short`
</verification>

<success_criteria>
- Audit script covers all 5 dimensions (structural, YES/NO token ID, quote stream equality, fidelity indicators, cadence)
- Binary verdict in report: SAFE_TO_USE or CORPUS_REPAIR_NEEDED
- No benchmark manifests modified
- No tape contents mutated
- No existing tests broken
- Dev log and CURRENT_STATE.md updated
</success_criteria>

<output>
After completion, create `.planning/quick/50-tape-corpus-integrity-audit-structural-s/50-SUMMARY.md`
</output>
