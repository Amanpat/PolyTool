---
title: Background Gate2 Session Helper
type: session_note
status: active
source_zone: repo
mirror_of: docs/dev_logs/2026-03-10_background_gate2_session_helper.md
last_synced: '2026-05-25T22:03:09Z'
lifecycle: reviewed
generator: repo-sync
---

# 2026-03-10: Background Gate 2 session helper

## Summary

Added a small PowerShell operator helper at `tools/ops/run_gate2_session.ps1`.
It wraps the existing Track A CLI flow without changing Python logic:

1. run `scan-gate2-candidates` with ranked JSON output
2. run `make-session-pack` with regime plus optional `--target-regime`
3. locate the newest session pack
4. launch `watch-arb-candidates` in the background with bounded duration
5. redirect watcher stdout/stderr into the session pack directory
6. print the watcher PID and exact follow-up commands for `tape-manifest` and `gate2-preflight`

## Notes

- Uses `.\.venv\Scripts\python.exe` from the repo root.
- Keeps the workflow aligned with the existing `session_plan.json` watchlist contract.
- Defaults remain operator-oriented and small: ranked scan -> pack -> detached watcher.

## Verification

- PowerShell syntax parse of `tools/ops/run_gate2_session.ps1`
- No Python files or Gate 2 logic were changed
