# 2026-04-15 — Track 2 Paper Soak Reporting Hardening

## Summary

Hardened the Track 2 paper-soak reporting surfaces so that a completed 24h paper run
now produces three triage artifacts: (1) a standalone `paper_soak_verdict.json` file
containing just the promote/rerun/reject decision and minimum operator context, (2) an
enriched `paper_soak_summary.json` with an `operational_context` block (cycles completed,
symbols included, per-symbol market breakdown), and (3) an enriched `paper_soak_summary.md`
with those operational context rows visible at the top of the Key Metrics table. The
purpose is to let an operator `cat verdict.json` after a soak and immediately know
the outcome without parsing the full summary, and to see which symbols and how many
cycle iterations the run covered. Nine new deterministic tests cover all new logic
paths with no network or ClickHouse dependency.

## Files Changed

| File | Action | Why |
|------|--------|-----|
| `packages/polymarket/crypto_pairs/reporting.py` | Modified | Add verdict artifact, operational context, markdown enrichment |
| `tests/test_crypto_pair_report.py` | Modified | Add 9 new deterministic tests; extend fixture helper with symbol_cycle + runner_result params |
| `docs/dev_logs/2026-04-15_track2_paper_soak_hardening.md` | Created | Mandatory dev log |

## What Changed in reporting.py

### 1. New constant
```python
PAPER_SOAK_VERDICT_JSON = "paper_soak_verdict.json"
```

### 2. `CryptoPairReportResult` dataclass
Added `verdict_path: Path` field alongside existing `json_path` and `markdown_path`.

### 3. `generate_crypto_pair_paper_report`
After writing the summary JSON and markdown, now writes `paper_soak_verdict.json`
to the run directory containing:
```json
{
  "schema_version": "crypto_pair_verdict_v0",
  "run_id": "...",
  "generated_at": "...",
  "decision": "promote|rerun|reject",
  "verdict": "PROMOTE TO MICRO LIVE CANDIDATE",
  "rubric_pass": true,
  "safety_violation_count": 0,
  "decision_reasons": ["all rubric gates passed"],
  "net_pnl_usdc": 1.56,
  "soak_duration_hours": 24.0
}
```
Returns the updated `CryptoPairReportResult` with `verdict_path` populated.

### 4. `build_paper_soak_summary`
Added `operational_context` key to the returned report dict:
```json
{
  "cycles_completed": 48,
  "symbols_included": ["BTC", "ETH", "SOL"],
  "markets_observed_count": 30,
  "markets_by_symbol": {"BTC": 10, "ETH": 10, "SOL": 10}
}
```
- `cycles_completed`: read from `manifest["runner_result"]["cycles_completed"]` if present;
  falls back to counting `cycle_completed` runtime events; `null` if neither source available.
- `symbols_included`: sorted unique list from the `market_to_symbol` index (already built).
- `markets_by_symbol`: dict mapping symbol to count of unique market IDs for that symbol.

### 5. `render_paper_soak_summary_markdown`
Added three rows to the Key Metrics table after `soak_duration_hours`:
- `cycles_completed`
- `symbols_included` (comma-joined)
- `markets_by_symbol` (e.g. "BTC=10, ETH=10, SOL=10")

### 6. `build_report_artifact_paths`
Added `"verdict_json": str(result.verdict_path)` to the returned dict. The existing
`--auto-report` CLI integration already prints all keys from this function, so the
verdict path is now surfaced automatically without touching CLI files.

## Commands Run + Output

### CLI loads
```
python -m polytool --help
```
Result: CLI loads successfully, no import errors.

### Targeted test run
```
python -m pytest tests/test_crypto_pair_report.py -v --tb=short
```
Result: **13 passed, 0 failed** (4 original + 9 new).

```
tests/test_crypto_pair_report.py::test_generate_report_promote_and_write_artifacts PASSED
tests/test_crypto_pair_report.py::test_cli_report_reruns_when_evidence_floor_not_met PASSED
tests/test_crypto_pair_report.py::test_report_rejects_intent_created_during_frozen_feed_window PASSED
tests/test_crypto_pair_report.py::test_operator_interrupt_is_treated_as_graceful_stop PASSED
tests/test_crypto_pair_report.py::test_verdict_artifact_written_alongside_summary PASSED
tests/test_crypto_pair_report.py::test_verdict_artifact_reject_decision PASSED
tests/test_crypto_pair_report.py::test_verdict_artifact_rerun_decision PASSED
tests/test_crypto_pair_report.py::test_operational_context_symbols_included PASSED
tests/test_crypto_pair_report.py::test_operational_context_cycles_completed_from_manifest PASSED
tests/test_crypto_pair_report.py::test_reject_kill_switch_tripped PASSED
tests/test_crypto_pair_report.py::test_reject_daily_loss_cap_reached PASSED
tests/test_crypto_pair_report.py::test_markdown_contains_verdict_and_operational_context PASSED
tests/test_crypto_pair_report.py::test_report_result_includes_verdict_path PASSED
```

### Regression suite
```
python -m pytest tests/ -x -q --tb=short
```
Result: **2519 passed, 1 failed (pre-existing), 3 deselected, 19 warnings** in 69.59s.

The pre-existing failure is `tests/test_ris_phase2_cloud_provider_routing.py::test_gemini_provider_success`
with `AttributeError: module has no attribute '_post_json'` — confirmed pre-existing before
this work packet by running on the stashed baseline. Zero new failures introduced.

## What the Operator Can Now Decide After a Soak

After a 24h paper run completes with `--auto-report`, three artifacts are written to
`artifacts/tapes/crypto/paper_runs/<date>/<run_id>/`:

**Instant triage:**
```bash
cat artifacts/tapes/crypto/paper_runs/2026-04-15/<run_id>/paper_soak_verdict.json
```
Returns `{"decision": "promote", "verdict": "PROMOTE TO MICRO LIVE CANDIDATE", ...}`
with net_pnl_usdc, soak_duration_hours, safety_violation_count, and decision_reasons.

**Operational context in summary:**
`paper_soak_summary.md` now shows `cycles_completed`, `symbols_included`, and
per-symbol market counts (`markets_by_symbol`) in the Key Metrics table — visible
without scrolling past evidence floor and rubric band tables.

**All artifact paths:**
`--auto-report` now prints `verdict_json`, `summary_json`, and `summary_markdown`
paths automatically via `build_report_artifact_paths`.

## Remaining Gaps Before Live Use

1. **EU VPS evaluation** — deployment latency assumptions require EU-region hosting;
   not yet procured or benchmarked.
2. **Oracle mismatch validation** — Coinbase reference feed vs Chainlink on-chain
   settlement oracle discrepancy not yet quantified for SOL/ETH/BTC markets.
3. **Micro-live scaffold wiring** — promote decision from verdict.json needs a
   defined workflow for advancing to micro-live capital deployment (Stage 0).
4. **SOL adverse selection review** — SOL markets may have higher adverse selection
   than BTC/ETH; paper soak data needed to validate before promoting SOL legs.

## Codex Review Note

Skip per CLAUDE.md policy. This work packet touches only the reporting module
(`reporting.py`) and its test file. No execution layer, risk manager, kill switch,
rate limiter, pair engine, reference feed, order placement, or EIP-712 signing code
was modified. Recommended-tier files (strategy, SimTrader core, etc.) are also
untouched.
