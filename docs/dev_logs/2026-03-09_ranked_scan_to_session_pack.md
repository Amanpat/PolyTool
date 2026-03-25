# Dev Log: Ranked Scan → Session Pack Pipeline

**Date:** 2026-03-09
**Branch:** simtrader

---

## Problem

Between `scan-gate2-candidates` output and `make-session-pack` invocation,
the operator had to manually select slugs and the advisory context produced
by scoring (gate2_status, rank_score, explanation lines) was silently discarded.

---

## Solution

**`scan-gate2-candidates --ranked-json-out PATH`**

Emits a `gate2_ranked_scan_v1` JSON artifact alongside the human table.
Each entry carries the full `Gate2RankScore` fields: slug, gate2_status,
rank_score, executable/edge/depth ticks, best_edge, depth_yes/no, regime,
regime_source, is_new_market, age_hours, reward_apr_est, volume_24h,
competition_score, explanation lines, source.

**`make-session-pack --ranked-json PATH`**

Reads the ranked JSON artifact. Slugs are extracted in rank order.
Advisory context is preserved under `rank_advisory` in each watchlist row
of the resulting `session_plan.json`. Regime/age metadata from the scan
is surfaced so `derive_tape_regime` produces correct provenance.

Can be combined with `--slugs`/`--watchlist-file`; ranked-json entries
appear first. Deduplication by slug is applied.

---

## Operator workflow (new integrated path)

```bash
# Step 1: scan and emit ranked JSON
python -m polytool scan-gate2-candidates --all --top 20 --explain \
  --ranked-json-out artifacts/watchlists/gate2_top20_ranked.json

# Step 2: create session pack from ranked JSON (advisory context preserved)
python -m polytool make-session-pack \
  --ranked-json artifacts/watchlists/gate2_top20_ranked.json \
  --top 3 \
  --regime sports \
  --source-manifest artifacts/gates/gate2_tape_manifest.json \
  --duration 600

# Step 3: copy the printed watch command and run it
```

---

## Files changed

| File | Change |
|------|--------|
| `tools/cli/scan_gate2_candidates.py` | Added `RANKED_JSON_SCHEMA_VERSION`, `write_ranked_json()`, `--ranked-json-out` arg |
| `tools/cli/make_session_pack.py` | Added `_RANKED_JSON_SCHEMA`, `_load_ranked_json()`, `--ranked-json` arg; updated `main()` merge flow |
| `tests/test_gate2_candidate_ranking.py` | +6 tests for `write_ranked_json` and `--ranked-json-out` |
| `tests/test_gate2_session_pack.py` | +9 tests for `_load_ranked_json` and `--ranked-json` |
| `docs/specs/SPEC-0017-...` | CLI surface section updated; acceptance criterion 12 added |
| `docs/specs/SPEC-0018-...` | CLI contract updated; `--ranked-json` arg documented; operator workflow updated |
| `docs/features/FEATURE-gate2-capture-session-pack.md` | Checklist updated; deferred item removed (now implemented) |
| `docs/INDEX.md` | Dev log row added |

---

## Invariants preserved

- Default `scan-gate2-candidates` behavior unchanged (no `--ranked-json-out` = no file written)
- Default `make-session-pack` behavior unchanged (`--slugs`/`--watchlist-file` still work)
- Gate 2 pass criteria, sweep economics, eligibility rules: unchanged
- `chosen_slugs` and `session_watchlist.txt` remain exact, untruncated
- `rank_advisory` is advisory only; it does not influence Gate 2 pass/fail

---

## Deferred

- `--ranked-json` input from tape-scan mode (live-only for now; tape scan
  also writes `Gate2RankScore` objects so the same function works, but no
  runbook integration yet)
