---
phase: quick-260415-qpv
plan: "01"
subsystem: crypto-pairs/await-soak
tags: [track2, paper-soak, launcher, preflight, kill-switch, verdict]
dependency_graph:
  requires: []
  provides: [hardened-await-soak-launcher, soak-preflight-validation, verdict-extraction]
  affects: [tools/cli/crypto_pair_await_soak.py, packages/polymarket/crypto_pairs/await_soak.py]
tech_stack:
  added: []
  patterns: [preflight-validation, argv-builder, subprocess-output-extraction]
key_files:
  created:
    - docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md
  modified:
    - packages/polymarket/crypto_pairs/await_soak.py
    - tools/cli/crypto_pair_await_soak.py
    - tests/test_crypto_pair_await_soak.py
decisions:
  - DEFAULT_SOAK_DURATION_SECONDS=86400 and DEFAULT_SOAK_HEARTBEAT_SECONDS=1800 added as new named constants; old DEFAULT_DURATION_SECONDS=1800 and DEFAULT_HEARTBEAT_SECONDS=60 kept as backward-compat aliases
  - validate_soak_prerequisites() is a pure function returning a list of issues; injected via _validate_fn for offline testing
  - verdict_json_path derived as artifact_dir/paper_soak_verdict.json rather than extracted from child output (child does not emit the path directly)
metrics:
  duration: 12m
  completed: "2026-04-15"
  tasks_completed: 3
  files_changed: 4
---

# Phase quick-260415-qpv Plan 01: Track 2 Soak Launcher Watchdog Summary

## One-liner

Hardened `crypto-pair-await-soak` launcher with 24h/30min soak defaults, kill-switch preflight check, and post-run verdict extraction.

## What Was Built

The `await_soak` launcher previously produced a bare-bones paper-soak command
missing `--auto-report`, 24h duration, and 30-min heartbeat. An operator
running without extra flags would get a 30-minute smoke soak with no report.

This plan upgrades the launcher to:

1. Default to a full 24h paper soak (`DEFAULT_SOAK_DURATION_SECONDS=86400`)
   with 30-minute heartbeats (`DEFAULT_SOAK_HEARTBEAT_SECONDS=1800`) and
   `--auto-report` included in the spawned command.
2. Accept `--sink-enabled`, `--max-capital-window-usdc`, `--heartbeat-minutes`,
   and `--kill-switch` flags on the CLI.
3. Check the kill switch file before launching. If tripped, the launcher prints
   the blocking issue, writes it to the manifest, and returns exit_code=1
   without spawning the child process.
4. Extract `report_verdict` from the child process output and print both the
   verdict text and the `paper_soak_verdict.json` path at the end of the run.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Harden await_soak launch plan and add preflight validation | cac35ba |
| 2 | Add deterministic tests for hardened launcher behavior | cac35ba |
| 3 | Write dev log and run regression | a8af43b |

## Test Results

- `tests/test_crypto_pair_await_soak.py`: 17 passed (7 updated + 10 new)
- Crypto-pair regression slice (5 test files): 64 passed, 0 failed
- CLI smoke test: loads cleanly, all new flags visible

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Notes

- Tasks 1 and 2 were committed together since the test file changes are
  directly coupled to the source changes and testing was done as a single
  atomic verification step.
- The verdict_json_path is derived as `artifact_dir/paper_soak_verdict.json`
  rather than parsed from child output. The child's `report_verdict` output
  line contains the verdict text string, not the JSON path. The path is
  reliably constructable from the artifact dir.

## Known Stubs

None.

## Threat Flags

None. All changes confined to the launcher/watchdog layer. No new network
endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `packages/polymarket/crypto_pairs/await_soak.py` — FOUND
- `tools/cli/crypto_pair_await_soak.py` — FOUND
- `tests/test_crypto_pair_await_soak.py` — FOUND
- `docs/dev_logs/2026-04-15_track2_soak_launcher_watchdog.md` — FOUND
- Commit cac35ba — FOUND
- Commit a8af43b — FOUND
