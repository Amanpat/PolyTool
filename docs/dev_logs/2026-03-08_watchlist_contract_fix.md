# Dev Log: Watchlist Contract Fix

**Date:** 2026-03-08
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What changed

Patched `watch-arb-candidates --watchlist-file` so operators can pass the exact
newline-delimited slug export written by `scan-gate2-candidates --watchlist-out`
without any conversion step.

Accepted watchlist inputs now include:
- report-style JSON with a top-level `watchlist` array
- newline-delimited market slug files, one slug per non-blank line

Blank lines are ignored. Empty files, malformed JSON, and malformed slug lines
now fail with a clear CLI error.

---

## Files changed

| File | What changed |
|------|-------------|
| `tools/cli/watch_arb_candidates.py` | Added dual-format watchlist loading, blank-line skipping for slug files, and clearer format errors |
| `tests/test_watch_arb_candidates.py` | Added coverage for newline-delimited watchlists, blank-line handling, and malformed/empty file errors while preserving JSON watchlist coverage |
| `docs/runbooks/GATE2_ELIGIBLE_TAPE_ACQUISITION.md` | Documented direct handoff from `--watchlist-out` into `watch-arb-candidates --watchlist-file` |
| `docs/dev_logs/2026-03-08_watchlist_contract_fix.md` | This file |

---

## Test results

```bash
pytest -q tests/test_watch_arb_candidates.py
pytest -q tests/test_gate2_candidate_ranking.py -k watchlist
```

Result: 32 passed in `tests/test_watch_arb_candidates.py`; 3 passed / 22 deselected in `tests/test_gate2_candidate_ranking.py -k watchlist`.
