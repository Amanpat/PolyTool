# Dev Log: Track 2 Post-Soak Review Helper

**Date:** 2026-04-15
**Task:** quick-260415-qqa
**Author:** Claude Code (Sonnet 4.6)

## Summary

Built `crypto-pair-review`, a one-command operator tool that reads completed Track 2 paper soak artifacts and prints a concise single-screen summary. The goal is to close the workflow gap between "paper soak finished, artifacts written" and "operator understands the outcome."

Before this work, `crypto-pair-report` wrote `paper_soak_summary.json`, `paper_soak_summary.md`, and `paper_soak_verdict.json` but only printed 6 lines of terminal output. An operator wanting to understand the verdict, risk control triggers, and promote-band fit had to manually open JSON files.

After this work: `python -m polytool crypto-pair-review --run <path>` prints a full one-screen ASCII review covering all decision-critical information.

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `packages/polymarket/crypto_pairs/reporting.py` | Modified | Added `format_post_soak_review()` and `load_or_generate_report()` |
| `tools/cli/crypto_pair_review.py` | Created | New CLI entrypoint for the review command |
| `polytool/__main__.py` | Modified | Registered `crypto-pair-review` in command table and help text |
| `tests/test_crypto_pair_review.py` | Created | 8 deterministic offline tests |
| `docs/dev_logs/2026-04-15_track2_post_soak_review_helper.md` | Created | This file |

## What Changed in reporting.py

### `load_or_generate_report(run_path: Path) -> dict[str, Any]`

Convenience loader that:
1. Checks if `paper_soak_summary.json` already exists in the run directory. If yes, reads and returns it (avoids re-computation — idempotent for operators re-running the review command).
2. If not present, calls `generate_crypto_pair_paper_report()` to generate all artifacts and returns `result.report`.

This makes `crypto-pair-review` work on runs that have already been reported AND on fresh runs that have not yet been processed by `crypto-pair-report`.

### `format_post_soak_review(report: Mapping[str, Any]) -> str`

Takes a report dict (same shape as `build_paper_soak_summary`) and returns a plain-ASCII, terminal-friendly formatted string. Output is structured in 7 sections:

1. **Header block** — run ID, duration, generated timestamp
2. **Verdict block** — full verdict string, decision (promote/rerun/reject), decision reasons
3. **Key Metrics block** — Net PnL, opportunities, intents, completed pairs, settled pairs, symbols, cycles
4. **Promote-Band Fit table** — all 8 rubric metrics with their banded classification (pass/rerun/reject/insufficient_data)
5. **Risk Controls block** — lists triggered safety violations with counts and first detail; "No risk controls triggered." if clean
6. **Evidence Floor block** — overall MET/NOT MET status; lists FAIL lines for any failing checks
7. **Notes block** — only printed if notes list is non-empty

All formatting uses plain ASCII only (no Unicode box-drawing characters) per CLAUDE.md Windows gotcha guidance.

## New CLI Command

```
python -m polytool crypto-pair-review --run <path>
```

Arguments:
- `--run PATH` (required) — path to a completed paper-run directory or run_manifest.json inside it
- `--json` (optional) — print `paper_soak_summary.json` content as formatted JSON instead of the human review (useful for scripting/piping)

Example output structure:

```
=== TRACK 2 POST-SOAK REVIEW ===
Run: my-run-id  |  Duration: 24.00h  |  Generated: 2026-04-15T12:00:00+00:00

VERDICT: PROMOTE TO MICRO LIVE CANDIDATE
Decision: promote
Reasons:
  - all rubric gates passed

--- Key Metrics ---
Net PnL:            1.5600 USDC
Opportunities:      30
Intents generated:  30
Completed pairs:    30
Settled pairs:      30
Symbols:            BTC  (BTC=30)
Cycles completed:   N/A

--- Promote-Band Fit ---
  pair_completion_rate                              1.0000  [pass]
  average_completed_pair_cost                       0.9500  [pass]
  estimated_profit_per_completed_pair               0.0520  [pass]
  maker_fill_rate_floor                             1.0000  [pass]
  partial_leg_incidence                             0.0000  [pass]
  feed_state_transitions              stale=0, disconnect=0  [pass]
  safety_violations                                      0  [pass]
  net_pnl_positive                                  1.5600  [pass]

--- Risk Controls ---
  No risk controls triggered.

--- Evidence Floor ---
Overall: MET
  All checks passed.
```

## Test Results

```
tests/test_crypto_pair_report.py   13 passed
tests/test_crypto_pair_review.py    8 passed
Full suite (tests/):            2546 passed, 1 pre-existing failure (test_gemini_provider_success)
```

New tests cover:
- `test_review_promote_contains_all_sections` — all 6 section headers present, PROMOTE verdict
- `test_review_reject_shows_triggered_controls` — REJECT verdict with `stopped_reason_not_completed` code
- `test_review_rerun_shows_failed_evidence_floor` — RERUN verdict, NOT MET, FAIL lines
- `test_review_multi_symbol_display` — BTC=10, ETH=10, SOL=10 in output
- `test_load_or_generate_reads_existing_summary` — sentinel field confirms pre-existing JSON is used
- `test_load_or_generate_generates_when_missing` — full report generated when no JSON present
- `test_cli_review_prints_formatted_output` — TRACK 2 POST-SOAK REVIEW and Promote-Band Fit in stdout
- `test_cli_review_json_flag_prints_valid_json` — valid JSON with rubric and metrics keys

## Codex Review Note

Skipped per CLAUDE.md policy. This work touches `reporting.py` (display/formatting only), a new CLI wrapper, and tests. None of the mandatory review categories apply: no execution/, no kill_switch.py, no risk_manager.py, no rate_limiter.py, no pair_engine.py, no reference_feed.py, no py_clob_client order placement, no EIP-712 signing, no BBO price extraction.
