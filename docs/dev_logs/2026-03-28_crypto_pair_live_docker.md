# Dev Log: Crypto Pair Bot — Live Execution Wiring + Docker

**Date:** 2026-03-28
**Quick task:** quick-040
**Branch:** phase-1B

## Summary

This work unit closes the last gap between the crypto-pair paper runner and a real live
order-submission path. Three things were shipped:

1. **Live execution wiring** — `packages/polymarket/crypto_pairs/clob_order_client.py`
   implements the `CryptoPairOrderClient` Protocol using py-clob-client (v0.34.6). The
   deferred-import pattern means paper mode, backtest, and all offline tests never need
   py-clob-client installed.

2. **Trade event logging** — `_log_trade_event()` added to `live_runner.py`. Called after
   every `place_order` and every `cancel_order` in the live loop. Appends one JSON line
   per event to `trade_log.jsonl` in the artifact dir. Contains: action, at, cycle,
   market_id, leg, token_id, side, price, size, accepted, submitted, order_id, reason,
   raw_response, logged_at.

3. **Docker services** — Two new services in `docker-compose.yml` under profiles
   `pair-bot` and `pair-bot-live`. Services are isolated from existing ClickHouse/Grafana
   stack and do not start on plain `docker compose up`.

## Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | Added `[live]` optional-dependency group: `py-clob-client>=0.17` |
| `packages/polymarket/crypto_pairs/clob_order_client.py` | New: ClobOrderClientConfig + PolymarketClobOrderClient |
| `packages/polymarket/crypto_pairs/live_runner.py` | _log_trade_event() helper; called in _process_opportunity and _handle_disconnect_state |
| `tools/cli/crypto_pair_run.py` | Auto-build PolymarketClobOrderClient from env when --live and no injected adapter |
| `Dockerfile.bot` | New: python:3.12-slim image for pair-bot; installs .[live,simtrader] + py-clob-client |
| `docker-compose.yml` | Added pair-bot-paper and pair-bot-live services (using Dockerfile.bot) with profiles |
| `docker_data/.gitkeep` | New directory tracked by git; runtime subdirs gitignored |
| `.gitignore` | Added docker_data/paper/ and docker_data/live/ exclusions |
| `tests/test_clob_order_client.py` | New: 6 offline tests; all sys.modules-mocked |
| `tests/test_crypto_pair_live_safety.py` | Updated test_kill_switch_checked_before_live_cycle to inject execution_adapter explicitly |

## py-clob-client Version

Installed: **0.34.6** (latest as of 2026-03-28).

Key API shape verified:
- `ClobClient(host, key, chain_id, creds)` — constructor
- `ApiCreds(api_key, api_secret, api_passphrase)` — credential struct
- `OrderArgs(token_id, price, size, side, ...)` — order params
- `OrderType.GTC` — time-in-force constant
- `ClobClient.create_order(order_args)` → signed order
- `ClobClient.post_order(signed, OrderType.GTC)` → response dict
- `ClobClient.cancel(order_id)` → response dict

## Key Decisions

### Deferred import pattern
`PolymarketClobOrderClient._build_client()` defers the `from py_clob_client...` imports
to runtime. This ensures paper/test paths never load py-clob-client. Tests mock via
`sys.modules` patching before any import.

### Env var names
Used the existing `.env.example` credentials (`PK`, `CLOB_API_KEY`, `CLOB_API_SECRET`,
`CLOB_API_PASSPHRASE`) rather than the alternative `POLYMARKET_PRIVATE_KEY` names
suggested in the plan's part A spec. The `.env.example` already had these vars with
comments at lines 88-93, so using them avoids duplicate naming.

### Docker profiles
`profiles: [pair-bot]` and `profiles: [pair-bot-live]` ensure pair-bot services are
entirely absent from the default `docker compose up`. The existing ClickHouse, Grafana,
API, and SimTrader Studio services are not modified.

### Kill switch via volume mount
`./docker_data/paper/KILL_SWITCH` and `./docker_data/live/KILL_SWITCH` are bind-mounted
into the container. Touching either file from the host trips the kill switch inside the
container at the next cycle check.

### Test update for kill_switch_checked test
`test_kill_switch_checked_before_live_cycle` was updated to pass an explicit
`execution_adapter` because the new env-var gate raises ValueError if PK is not set when
live=True and no adapter is injected. The test only tests kill switch behavior, so
injecting a no-op adapter is correct.

## Verification

### Smoke tests run

```
python -c "from py_clob_client.client import ClobClient; print('py-clob-client OK')"
py-clob-client OK

python -c "from packages.polymarket.crypto_pairs.clob_order_client import PolymarketClobOrderClient; print('import OK')"
import OK

docker compose config --quiet
YAML valid
```

### Test results

```
pytest tests/test_clob_order_client.py -v --tb=short
6 passed in 0.34s

pytest tests/test_clob_order_client.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_run.py -v --tb=short
19 passed in 2.67s

pytest tests/ -x -q --tb=short
2734 passed, 25 warnings in 79.10s
```

## How to Use

### Paper mode (Docker)
```bash
docker compose --profile pair-bot up pair-bot-paper
```
Artifacts land in `./docker_data/paper/`. Kill: `touch docker_data/paper/KILL_SWITCH`.

### Live mode (Docker)
```bash
# Ensure .env has PK, CLOB_API_KEY, CLOB_API_SECRET, CLOB_API_PASSPHRASE set
docker compose --profile pair-bot-live up pair-bot-live
```
Artifacts land in `./docker_data/live/`. Kill: `touch docker_data/live/KILL_SWITCH`.

### Live mode (CLI)
```bash
export PK=your_private_key_hex
export CLOB_API_KEY=your_api_key
export CLOB_API_SECRET=your_api_secret
export CLOB_API_PASSPHRASE=your_passphrase
python -m polytool crypto-pair-run --live --confirm CONFIRM --duration-hours 8 --symbol BTC
```

## Open Items

1. **Market availability blocker still active** — Polymarket has no active BTC/ETH/SOL
   5m/15m binary pair markets as of 2026-03-25. The live runner will discover zero markets
   and complete all cycles immediately. Use `crypto-pair-watch --watch` to poll for market
   availability.

2. **py-clob-client API shape unverified against live Polymarket** — The `OrderArgs` field
   names (`token_id`, `price`, `size`, `side`) match the 0.34.6 dataclass definition, but
   the actual POST payload and response format should be verified against Polymarket staging
   before deploying capital.

3. **ApiCreds derivation** — The implementation uses pre-generated API credentials. The
   alternative `derive_api_key()` / `create_api_key()` path was not wired because the
   existing `.env.example` already exposes `CLOB_API_KEY/SECRET/PASSPHRASE` as the primary
   pattern.

4. **py-clob-client API shape unverified against live Polymarket** — The `OrderArgs` field
   names and response format should be verified against Polymarket staging before deploying
   capital. The `ClobClient.create_order` + `post_order` path was confirmed by inspecting
   the 0.34.6 source but not against live endpoints.
