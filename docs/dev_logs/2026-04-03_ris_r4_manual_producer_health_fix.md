# Dev Log: 2026-04-03 RIS R4 Manual Producer Health Fix

## Objective

Wire research-ingest and research-acquire CLI commands into append_run() so manual
operator runs create real RunRecords visible to research-health. Fix health check
messaging to honestly label deferred/stubbed checks.

Quick task: 260403-it1

## Problem

The RIS health surface showed "no_data" after manual operator runs because
research-ingest and research-acquire did not call append_run(). This made
research-health useless for the most common operator workflow (running
research-ingest by hand, then checking research-health).

Additionally, model_unavailable and rejection_audit_disagreement checks displayed
GREEN with messages that didn't explain WHY they were green — creating false
confidence. An operator seeing all-GREEN had no way to know two checks were
silently stubbed out.

## Files Changed

**Modified:**
- `tools/cli/research_ingest.py` — added `--run-log` arg, timing capture, and
  append_run() call in both success and error paths (non-fatal try/except)
- `tools/cli/research_acquire.py` — added `--run-log` arg, timing capture, and
  append_run() call in URL path (success and error); skipped on `--dry-run`
- `packages/research/monitoring/health_checks.py` — `[DEFERRED]` prefix and
  `check_type='stub'` in data dict for model_unavailable and
  rejection_audit_disagreement (when audit_disagreement_rate=None)
- `tools/cli/research_health.py` — deferred-checks footer in table output;
  `deferred_checks` list in JSON output
- `tests/test_ris_monitoring.py` — 14 new tests in 3 new classes
- `docs/features/FEATURE-ris-monitoring-health-v1.md` — updated wiring docs,
  deferred items, test count
- `docs/CURRENT_STATE.md` — updated RIS monitoring section

## What Now Writes Run Logs

| Command | Pipeline Name | When |
|---------|--------------|------|
| `research-ingest` | `research_ingest` | After every ingest (success, rejection, or error) |
| `research-acquire` | `research_acquire` | After every acquire (skipped on `--dry-run`) |
| `research-scheduler run-job` | `{job_id}` | After every scheduled job (existing, from quick-260403-2ow) |

## Health Checks Still Stubbed

| Check | Status | Why |
|-------|--------|-----|
| `model_unavailable` | GREEN [DEFERRED] | Requires provider error event data from scheduler |
| `rejection_audit_disagreement` | GREEN [DEFERRED] | Requires audit runner computing disagreement rate |

Both checks now clearly label themselves as `[DEFERRED]` in their messages and
include `check_type='stub'` in their data dict. The health table footer also
notes: "GREEN = no data, not verified healthy."

## Implementation Pattern

Followed the same non-fatal append_run() pattern as the APScheduler run_job():
- Capture `_t0 = time.monotonic()` and `_started_at` at top of execution
- Wrap append_run() call in `try/except Exception: pass`
- Write error record inside the `except Exception` block before `return 2`
- Write success record before `return 0`
- Both records include pipeline name, timing, accepted/rejected counts, exit_status

## Commands Run

```
python -m pytest tests/test_ris_monitoring.py -x -q --tb=short
# 54 passed in 0.77s

python -m pytest tests/ -x -q --tb=short
# [full regression -- see below]
```

## Codex Review Tier

Skip -- no execution/kill-switch/order-placement code.
This is CLI wiring and health observability only.
