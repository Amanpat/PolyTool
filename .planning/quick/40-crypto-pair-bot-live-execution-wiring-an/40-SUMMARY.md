---
phase: quick
plan: 40
subsystem: execution
tags: [py-clob-client, polymarket-clob, docker, live-trading, crypto-pair-bot, trade-logging]

# Dependency graph
requires:
  - phase: quick-037
    provides: crypto pair live runner with CryptoPairOrderClient Protocol and execution adapter

provides:
  - PolymarketClobOrderClient implementing CryptoPairOrderClient via py-clob-client 0.34.6
  - ClobOrderClientConfig with from_env() loading PK/CLOB_API_KEY/CLOB_API_SECRET/CLOB_API_PASSPHRASE
  - _log_trade_event() appending JSONL to trade_log.jsonl on every place/cancel
  - CLI env-var gate in run_crypto_pair_runner() auto-building live client when --live and no injected adapter
  - Dockerfile.bot (python:3.12-slim) with .[live,simtrader] + py-clob-client installed
  - docker-compose.yml pair-bot-paper (profile=pair-bot) and pair-bot-live (profile=pair-bot-live) services
  - docker_data/ directory structure with gitignored paper/ and live/ subdirs; KILL_SWITCH bind-mounts
  - 6 offline tests in test_clob_order_client.py (sys.modules patching; no py-clob-client install needed)

affects: [live-deployment, gate3-shadow, capital-staging, docker-operations]

# Tech tracking
tech-stack:
  added:
    - py-clob-client>=0.17 (optional dep group [live])
    - python:3.12-slim (Dockerfile.bot base image)
  patterns:
    - Deferred import: _build_client() defers from py_clob_client... to runtime; offline paths never load it
    - sys.modules patching in tests: stub py_clob_client before module import for offline isolation
    - Docker profile isolation: pair-bot services absent from default docker compose up
    - Kill switch via volume bind-mount: touching file from host trips switch inside container

key-files:
  created:
    - packages/polymarket/crypto_pairs/clob_order_client.py
    - tests/test_clob_order_client.py
    - Dockerfile.bot
    - docker_data/.gitkeep
    - docs/dev_logs/2026-03-28_crypto_pair_live_docker.md
  modified:
    - pyproject.toml
    - packages/polymarket/crypto_pairs/live_runner.py
    - tools/cli/crypto_pair_run.py
    - docker-compose.yml
    - .gitignore
    - tests/test_crypto_pair_live_safety.py

key-decisions:
  - "Used existing env var names (PK, CLOB_API_KEY, CLOB_API_SECRET, CLOB_API_PASSPHRASE) from .env.example lines 88-93 rather than POLYMARKET_PRIVATE_KEY alternatives in plan spec"
  - "Deferred import in _build_client() so paper mode, backtest, and offline tests never load py-clob-client"
  - "Created separate Dockerfile.bot (python:3.12-slim) rather than modifying existing SimTrader Studio Dockerfile"
  - "Docker profiles pair-bot / pair-bot-live isolate new services from existing ClickHouse/Grafana/API stack"
  - "KILL_SWITCH bind-mounted from ./docker_data/{paper,live}/ to container for host-controllable kill"
  - "Updated test_kill_switch_checked_before_live_cycle to inject explicit execution_adapter to avoid new env-var gate"

patterns-established:
  - "Deferred import pattern: guard live-only deps with from ... import inside method body, not at module top"
  - "sys.modules stub pattern: patch py_clob_client.* in sys.modules before importing the module under test"

requirements-completed: []

# Metrics
duration: ~90min
completed: 2026-03-28
---

# Quick Task 40: Crypto Pair Bot — Live Execution Wiring + Docker Summary

**py-clob-client 0.34.6 wired to crypto-pair live runner with per-trade JSONL logging and Docker pair-bot services for one-command paper/live deployment**

## Performance

- **Duration:** ~90 min
- **Started:** 2026-03-28T00:00:00Z
- **Completed:** 2026-03-28
- **Tasks:** 3
- **Files modified:** 10 (5 created, 5 modified)

## Accomplishments

- `PolymarketClobOrderClient` implementing the `CryptoPairOrderClient` Protocol via py-clob-client 0.34.6; deferred import ensures paper/test paths never load the library
- `_log_trade_event()` appends one JSONL line per place/cancel event to `trade_log.jsonl`; fields include action, at, cycle, market_id, leg, token_id, side, price, size, accepted, submitted, order_id, reason, raw_response, logged_at
- `Dockerfile.bot` (python:3.12-slim, non-root botuser) + two docker-compose services under profiles `pair-bot` / `pair-bot-live`; kill switch via bind-mounted `docker_data/{paper,live}/KILL_SWITCH` from host
- 6 offline tests in `test_clob_order_client.py` all pass via sys.modules patching; full regression suite at 2734 passed

## Task Commits

1. **Task 1: py-clob-client dep + ClobOrderClientConfig + PolymarketClobOrderClient** - `92182ec` (feat)
2. **Task 2: wire live runner + trade_log.jsonl + CLI env-var gate** - `9aa1c5b` (feat)
3. **Task 3: Docker pair-bot services + Dockerfile.bot + docker_data + dev log** - `d1ec36c` (feat)

## Files Created/Modified

- `packages/polymarket/crypto_pairs/clob_order_client.py` - ClobOrderClientConfig (from_env() + frozen dataclass) and PolymarketClobOrderClient (Protocol impl via deferred py-clob-client imports)
- `packages/polymarket/crypto_pairs/live_runner.py` - Added _log_trade_event() module-level helper; called after every place_order and cancel_order in live loop
- `tools/cli/crypto_pair_run.py` - Env-var gate: auto-builds PolymarketClobOrderClient from env when live=True and no injected execution_adapter
- `pyproject.toml` - Added [live] optional dep group (py-clob-client>=0.17); added live to [all]
- `Dockerfile.bot` - New: python:3.12-slim image, installs .[live,simtrader] + py-clob-client, non-root botuser, ENTRYPOINT crypto-pair-run
- `docker-compose.yml` - Added pair-bot-paper (profile=pair-bot) and pair-bot-live (profile=pair-bot-live) services
- `docker_data/.gitkeep` - Tracks directory in git; runtime subdirs gitignored
- `.gitignore` - Added /docker_data/paper/ and /docker_data/live/ exclusions
- `tests/test_clob_order_client.py` - 6 offline tests; sys.modules patching for py-clob-client isolation
- `tests/test_crypto_pair_live_safety.py` - Updated test_kill_switch_checked_before_live_cycle to inject explicit execution_adapter
- `docs/dev_logs/2026-03-28_crypto_pair_live_docker.md` - Dev log with full API shape, decisions, verification results, open items

## Decisions Made

1. **Env var names from .env.example** — Used `PK`, `CLOB_API_KEY`, `CLOB_API_SECRET`, `CLOB_API_PASSPHRASE` (already documented at .env.example lines 88-93) rather than `POLYMARKET_PRIVATE_KEY` / alternative naming suggested in plan spec Part A. Avoids duplicate naming.

2. **Deferred import pattern** — `_build_client()` defers `from py_clob_client...` to runtime so paper mode, backtest, and all offline tests never require py-clob-client installed. Tests mock via sys.modules patching.

3. **Separate Dockerfile.bot** — Existing `Dockerfile` is SimTrader Studio (python:3.11-slim, .[simtrader,studio], EXPOSE 8765). Created separate `Dockerfile.bot` for pair-bot to avoid coupling the images and to include `.[live,simtrader]` with py-clob-client.

4. **Docker profile isolation** — `profiles: [pair-bot]` and `profiles: [pair-bot-live]` ensure pair-bot services are entirely absent from default `docker compose up`. Existing ClickHouse, Grafana, API, SimTrader Studio services unmodified.

5. **Kill switch via bind-mount** — `./docker_data/paper/KILL_SWITCH` and `./docker_data/live/KILL_SWITCH` bind-mounted into container. `touch docker_data/paper/KILL_SWITCH` from host trips kill switch at next cycle check inside container.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated test_kill_switch_checked_before_live_cycle to inject explicit execution_adapter**
- **Found during:** Task 2 (wire live runner + CLI env-var gate)
- **Issue:** New env-var gate in run_crypto_pair_runner() raises ValueError when live=True and execution_adapter=None and env vars (PK, CLOB_*) not set. Pre-existing test called with live=True, no adapter, no env vars — caused ValueError before runner even started.
- **Fix:** Injected explicit `CryptoPairLiveExecutionAdapter(kill_switch=..., order_client=None, live_enabled=False)` in the test. Test only tests kill switch behavior, not order execution, so a no-op adapter is correct and preserves test intent.
- **Files modified:** tests/test_crypto_pair_live_safety.py
- **Verification:** Full test suite 2734 passed
- **Committed in:** 9aa1c5b (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Required fix to maintain pre-existing kill-switch test after new env-var gate added. No scope creep.

## Issues Encountered

- py-clob-client 0.34.6 API shape verified by inspecting installed source (OrderArgs fields, ClobClient constructor, ApiCreds struct). The `create_order(order_args)` + `post_order(signed, OrderType.GTC)` path confirmed against 0.34.6 source but not against live Polymarket endpoints.
- Market availability blocker remains: Polymarket has no active BTC/ETH/SOL 5m/15m binary pair markets as of 2026-03-25. Live runner will discover zero markets and complete cycles immediately. Use `crypto-pair-watch --watch` to poll for market availability.

## User Setup Required

To run live mode, ensure `.env` has:
```
PK=your_private_key_hex
CLOB_API_KEY=your_api_key
CLOB_API_SECRET=your_api_secret
CLOB_API_PASSPHRASE=your_passphrase
```

Paper mode does not require credentials.

Kill switch from host:
- Paper: `touch docker_data/paper/KILL_SWITCH`
- Live: `touch docker_data/live/KILL_SWITCH`

## Next Phase Readiness

- Live execution path is wired end-to-end; ready for staging deployment once active BTC/ETH/SOL pair markets are available on Polymarket
- py-clob-client API shape should be verified against Polymarket staging before deploying capital (see open item in dev log)
- Gate 2 (benchmark scenario sweep) is the parallel track: run `python tools/gates/close_sweep_gate.py` against `config/benchmark_v1.tape_manifest` once gold corpus meets 50-tape threshold

---
*Phase: quick*
*Completed: 2026-03-28*

## Self-Check: PASSED

All files verified present and all task commits confirmed in git history:
- `packages/polymarket/crypto_pairs/clob_order_client.py` - FOUND
- `tests/test_clob_order_client.py` - FOUND
- `Dockerfile.bot` - FOUND
- `docker_data/.gitkeep` - FOUND
- `docs/dev_logs/2026-03-28_crypto_pair_live_docker.md` - FOUND
- `.planning/quick/40-crypto-pair-bot-live-execution-wiring-an/40-SUMMARY.md` - FOUND
- Commit `92182ec` (Task 1) - FOUND
- Commit `9aa1c5b` (Task 2) - FOUND
- Commit `d1ec36c` (Task 3) - FOUND
