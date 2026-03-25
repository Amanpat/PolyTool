# Phase 1 Track A Offline Verification

- Log file requested: `docs/dev_logs/2026-03-09_phase1_tracka_offline_verification.md`
- Actual verification run date: `2026-03-10`
- Scope: offline verification only; no live market activity, no live tape capture, no real Discord delivery

## Concise summary

Offline verification passed.

- Targeted test suites passed: `5/5`
- Targeted test cases passed: `188/188`
- CLI smoke/help checks passed: `5/5`
- Failed commands: `0`

This offline sweep verifies the recent Track A contract surface across:

- scan candidate ranking and watchlist export contract
- watcher trigger logic, dry-run behavior, watchlist ingest, and regime propagation
- session-pack generation and watcher-compatible plan/watchlist contract
- tape manifest eligibility invariant and regime coverage accounting
- gate2 preflight readiness/blocker reporting
- Discord notification code paths in offline unit tests

## Commands run

```text
pytest -q tests/test_gate2_candidate_ranking.py
pytest -q tests/test_watch_arb_candidates.py
pytest -q tests/test_gate2_session_pack.py
pytest -q tests/test_gate2_eligible_tape_acquisition.py
pytest -q tests/test_discord_notifications.py
python -m polytool scan-gate2-candidates --help
python -m polytool make-session-pack --help
python -m polytool watch-arb-candidates --help
python -m polytool tape-manifest --help
python -m polytool gate2-preflight --help
```

## Passing checks

### Targeted tests

`pytest -q tests/test_gate2_candidate_ranking.py`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 25 items

tests\test_gate2_candidate_ranking.py .........................          [100%]

============================= 25 passed in 0.33s ==============================
```

`pytest -q tests/test_watch_arb_candidates.py`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 33 items

tests\test_watch_arb_candidates.py .................................     [100%]

============================= 33 passed in 0.61s ==============================
```

`pytest -q tests/test_gate2_session_pack.py`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 38 items

tests\test_gate2_session_pack.py ......................................  [100%]

============================= 38 passed in 1.91s ==============================
```

`pytest -q tests/test_gate2_eligible_tape_acquisition.py`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: C:\Users\CodexSandboxOffline\.codex\.sandbox\cwd\9a7e3ce232144e7e
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 59 items

tests\test_gate2_eligible_tape_acquisition.py .......................... [ 44%]
.................................                                        [100%]

============================= 59 passed in 1.96s ==============================
```

`pytest -q tests/test_discord_notifications.py`

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.0.2, pluggy-1.6.0
rootdir: D:\Coding Projects\Polymarket\PolyTool
configfile: pyproject.toml
plugins: anyio-4.12.0
collected 33 items

tests\test_discord_notifications.py .................................    [100%]

============================= 33 passed in 0.44s ==============================
```

Aggregate targeted test result:

```text
5 suites passed
188 tests passed
0 test failures
```

### Safe CLI smoke/help checks

`python -m polytool scan-gate2-candidates --help`

```text
usage: scan-gate2-candidates [-h] [--tapes-dir DIR] [--max-size N]
                             [--buffer F] [--candidates N] [--top N] [--all]
                             [-v] [--explain] [--enrich]
                             [--watchlist-out PATH]

...
  --enrich              Fetch live market metadata/reward context to reduce
                        UNKNOWN ranking fields (live mode only). (default:
                        False)
  --watchlist-out PATH  Write exact untruncated slugs for the shown ranked
                        candidates (one slug per line). (default: None)
```

`python -m polytool make-session-pack --help`

```text
usage: make-session-pack [-h] [--slugs SLUG [SLUG ...]]
                         [--watchlist-file PATH] [--top N] --regime REGIME
                         [--source-manifest PATH] [--out-dir DIR]
                         [--duration SECS] [--poll-interval SECS]
                         [--near-edge F] [--min-depth N] [-v]

...
  --watchlist-file PATH
                        Existing watchlist input in the same format accepted
                        by watch-arb-candidates: report-style JSON with a top-
                        level 'watchlist' array or newline-delimited slugs.
```

`python -m polytool watch-arb-candidates --help`

```text
usage: watch-arb-candidates [-h] [--markets SLUG [SLUG ...]]
                            [--watchlist-file PATH] [--near-edge F]
                            [--min-depth N] [--poll-interval SECS]
                            [--duration SECS] [--tapes-base-dir DIR]
                            [--ws-url URL] [--max-concurrent N] [--dry-run]
                            [--regime REGIME] [-v]

...
  --dry-run             Evaluate triggers and print status but do not start
                        any recordings.
  --regime REGIME       Market regime label written to tape metadata. Used by
                        'tape-manifest' for mixed-regime corpus tracking.
```

`python -m polytool tape-manifest --help`

```text
usage: tape-manifest [-h] [--tapes-dir DIR] [--out PATH] [--max-size N]
                     [--buffer F] [-v]

Gate 2 tape acquisition manifest generator.

Eligibility invariant: a tape is ONLY marked eligible when
executable_ticks > 0 (depth_ok AND edge_ok simultaneously).
Non-executable tapes are NEVER labeled eligible.
```

`python -m polytool gate2-preflight --help`

```text
usage: gate2-preflight [-h] [--tapes-dir DIR] [--max-size N] [--buffer F] [-v]

Check whether Gate 2 sweep is ready using existing tape eligibility and mixed-
regime coverage rules.
```

## Failed checks

None.

```text
0 failed commands
0 failed test suites
0 failed test cases
```

## Warnings

- This was an offline-only sweep. No live Gamma/CLOB scan, no real market resolution, no live websocket tape recording, and no real Discord webhook delivery were attempted.
- The strongest contract coverage came from targeted offline tests, not from a single persisted end-to-end CLI run through real artifacts.
- One test command reported a sandbox rootdir path while still passing:

```text
rootdir: C:\Users\CodexSandboxOffline\.codex\.sandbox\cwd\9a7e3ce232144e7e
```

That did not produce a failure, but it means that one pytest invocation ran from the sandbox mirror rather than displaying the workspace path in its header.

## Live-only unverified items

- `scan-gate2-candidates` against live Polymarket markets, including live enrichment behavior and actual ranked output quality during a catalyst window
- `watch-arb-candidates` real slug resolution, live polling cadence, actual trigger firing, background tape recording, and writeout under real market conditions
- `make-session-pack` generated from a real ranked watchlist chosen from a same-day live scan
- `tape-manifest` over newly recorded real tapes from a catalyst-window session
- `gate2-preflight` against the actual current tape corpus rather than synthetic/offline test fixtures
- Whether any current tape corpus is actually Gate 2 ready right now on `2026-03-10`
- Real Discord webhook delivery and operator visibility of notifications

## Recommended next action

Run one supervised live operator session during a real catalyst window, then verify the resulting real artifacts with:

```text
python -m polytool scan-gate2-candidates --all --top 20 --watchlist-out artifacts/watchlists/gate2_top20.txt
python -m polytool make-session-pack --watchlist-file artifacts/watchlists/gate2_top20.txt --top 3 --regime <regime> --source-manifest artifacts/gates/gate2_tape_manifest.json
python -m polytool watch-arb-candidates --watchlist-file artifacts/session_packs/<session_id>/session_plan.json --regime <regime> --duration 600 --poll-interval 30
python -m polytool tape-manifest
python -m polytool gate2-preflight
```

Until that live session exists, the offline result is:

```text
PASS for offline verification
NOT SUFFICIENT to conclude live Gate 2 readiness
```
