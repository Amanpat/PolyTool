# Dev Log: Watch Arb Duration Fix

**Date:** 2026-03-09
**Branch:** simtrader
**Author:** PolyTool Contributors

---

## What changed

`watch-arb-candidates` now enforces `--duration` as a hard monotonic deadline for
the watch session instead of running indefinitely until manual interruption.

The loop now:
- computes a deadline with `time.monotonic()`
- stops cleanly once remaining time is `<= 0`
- caps inter-round sleeps by the remaining time
- stops polling additional markets mid-round if the deadline has already elapsed

Existing trigger evaluation, dry-run behavior, background recording dispatch,
and concurrency limits are unchanged.

---

## Root cause

`ArbWatcher.run()` validated `--duration` and printed it, but never used that
value to bound the watch loop. The loop only checked the stop event and
`KeyboardInterrupt`, so `--duration` affected tape recording length but did not
stop the watcher itself.

---

## Files changed

| File | What changed |
|------|-------------|
| `tools/cli/watch_arb_candidates.py` | Added monotonic deadline enforcement, remaining-time sleep capping, and a clean duration-expired exit path |
| `tests/test_watch_arb_candidates.py` | Added a regression test with an injected fake clock proving a short duration exits automatically without major overshoot |
| `docs/dev_logs/2026-03-09_watch_arb_duration_fix.md` | This file |

---

## Test results

```bash
pytest -q tests/test_watch_arb_candidates.py
```

Result: 33 passed.
