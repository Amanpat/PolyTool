---
phase: quick-40
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - packages/polymarket/crypto_pairs/clob_order_client.py
  - packages/polymarket/crypto_pairs/live_runner.py
  - Dockerfile
  - docker-compose.yml
  - .env.example
  - docker_data/.gitkeep
  - .gitignore
  - tests/test_clob_order_client.py
  - docs/dev_logs/2026-03-28_crypto_pair_live_docker.md
autonomous: true
requirements: []

must_haves:
  truths:
    - "Running with --live flag uses py-clob-client to submit orders when POLYMARKET env vars are set"
    - "Running with --live flag but missing env vars fails fast with a clear error before any network call"
    - "Every place/cancel attempt writes a line to trade_log.jsonl in the artifact dir"
    - "docker compose up pair-bot-paper starts the paper runner in a container with --output /data/paper"
    - "docker compose up pair-bot-live starts the live runner in a container with --output /data/live"
    - "All 6 clob_order_client tests pass with no real API calls"
  artifacts:
    - path: "packages/polymarket/crypto_pairs/clob_order_client.py"
      provides: "ClobOrderClientConfig + PolymarketClobOrderClient implementing CryptoPairOrderClient Protocol"
      exports: ["ClobOrderClientConfig", "PolymarketClobOrderClient"]
    - path: "tests/test_clob_order_client.py"
      provides: "6 offline tests covering config, place, cancel, missing-key, runner rejection, trade log"
    - path: "docs/dev_logs/2026-03-28_crypto_pair_live_docker.md"
      provides: "Dev log for this work unit"
  key_links:
    - from: "tools/cli/crypto_pair_run.py"
      to: "packages/polymarket/crypto_pairs/clob_order_client.py"
      via: "run_crypto_pair_runner() builds PolymarketClobOrderClient when --live and env vars present"
    - from: "packages/polymarket/crypto_pairs/live_runner.py"
      to: "trade_log.jsonl"
      via: "_log_trade_event() called after every place/cancel in _process_opportunity"
---

<objective>
Wire the crypto-pair bot to real Polymarket CLOB order placement via py-clob-client, add per-trade logging, and containerize for one-command partner deployment.

Purpose: Phase 1A Track 2 must be able to submit real limit orders. The live runner currently returns "live_client_unconfigured" for every order. This plan closes that gap and adds Docker services so a partner machine can run both paper and live modes with a single command.

Output: clob_order_client.py (CLOB Protocol impl), live_runner trade_log.jsonl, pair-bot-paper and pair-bot-live Docker services, 6 offline tests, dev log.
</objective>

<execution_context>
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/workflows/execute-plan.md
@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@D:/Coding Projects/Polymarket/PolyTool/CLAUDE.md
@D:/Coding Projects/Polymarket/PolyTool/.planning/STATE.md

<!-- Executor needs these interfaces before writing clob_order_client.py -->
<interfaces>
<!-- From packages/polymarket/crypto_pairs/live_execution.py -->
```python
LIMIT_ORDER_TYPE = "limit"

@dataclass(frozen=True)
class LiveOrderRequest:
    market_id: str
    token_id: str
    side: str          # "BUY"
    price: Decimal
    size: Decimal
    order_type: str = "limit"
    post_only: bool = True
    meta: dict[str, Any]

class CryptoPairOrderClient(Protocol):
    def place_limit_order(self, request: LiveOrderRequest) -> dict[str, Any]: ...
    def cancel_order(self, order_id: str) -> dict[str, Any]: ...
```

<!-- From tools/cli/crypto_pair_run.py (lines 266-405 — live branch) -->
```python
def run_crypto_pair_runner(
    *,
    live: bool = False,
    execution_adapter: Any = None,   # currently None in live mode
    ...
) -> dict[str, Any]:
    ...
    if live:
        runner = CryptoPairLiveRunner(
            settings,
            execution_adapter=execution_adapter,   # <-- inject real adapter here
            gamma_client=gamma_client,
            clob_client=clob_client,
            ...
        )
```

<!-- .env.example already has these keys (lines 88-93) -->
```
PK=replace_with_wallet_private_key_hex_no_0x
CLOB_API_KEY=replace_with_clob_api_key
CLOB_API_SECRET=replace_with_clob_api_secret
CLOB_API_PASSPHRASE=replace_with_clob_api_passphrase
```

<!-- Existing Dockerfile and docker-compose.yml already exist — they must be extended, not replaced -->
<!-- Dockerfile builds the simtrader studio image on python:3.11-slim, installs .[simtrader,studio] -->
<!-- docker-compose.yml has clickhouse, grafana, api, migrate, polytool services -->
<!-- Scope guard: do NOT add ClickHouse/Grafana to the new pair-bot services -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: py-clob-client dep + ClobOrderClientConfig + PolymarketClobOrderClient</name>
  <files>
    pyproject.toml
    packages/polymarket/crypto_pairs/clob_order_client.py
  </files>
  <behavior>
    - Test 1: config_from_env_missing_key — os.environ missing PK → raises ValueError with message listing the missing key
    - Test 2: config_from_env_success — all four env vars present → ClobOrderClientConfig fields match env values
    - Test 3: place_limit_order_returns_dict — mock ClobClient.create_order returns {"id": "ord-1"} → method returns that dict
    - Test 4: cancel_order_returns_dict — mock ClobClient.cancel returns {"cancelled": True} → method returns that dict
    - Test 5: live_runner_refuses_without_key — run_crypto_pair_runner(live=True, confirm="CONFIRM") with no PK env var → raises ValueError before starting the runner loop
    - Test 6: trade_event_logging — after one successful place_order call, artifact dir contains trade_log.jsonl with one line; after one cancel_order call, a second line is appended
  </behavior>
  <action>
1. In pyproject.toml add a new optional-dependency group `live` containing `py-clob-client>=0.17` (check latest on PyPI; use `>=0.17` as minimum unless Context7 says otherwise). Add `live` to the `all` extras list.

2. Create `packages/polymarket/crypto_pairs/clob_order_client.py`:

```python
"""Real Polymarket CLOB order client implementing CryptoPairOrderClient Protocol."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .live_execution import LiveOrderRequest


_REQUIRED_ENV_VARS = ("PK", "CLOB_API_KEY", "CLOB_API_SECRET", "CLOB_API_PASSPHRASE")


class ClobOrderClientConfigError(ValueError):
    """Raised when required env vars are missing."""


@dataclass(frozen=True)
class ClobOrderClientConfig:
    private_key: str
    api_key: str
    api_secret: str
    api_passphrase: str
    clob_api_base: str = "https://clob.polymarket.com"

    @classmethod
    def from_env(cls) -> "ClobOrderClientConfig":
        missing = [k for k in _REQUIRED_ENV_VARS if not os.environ.get(k)]
        if missing:
            raise ClobOrderClientConfigError(
                f"Live CLOB client requires env vars: {', '.join(missing)}"
            )
        return cls(
            private_key=os.environ["PK"],
            api_key=os.environ["CLOB_API_KEY"],
            api_secret=os.environ["CLOB_API_SECRET"],
            api_passphrase=os.environ["CLOB_API_PASSPHRASE"],
            clob_api_base=os.environ.get("CLOB_API_BASE", "https://clob.polymarket.com"),
        )


class PolymarketClobOrderClient:
    """CryptoPairOrderClient backed by py-clob-client.

    Import is deferred so the rest of the package does not hard-depend on py-clob-client.
    """

    def __init__(self, config: ClobOrderClientConfig) -> None:
        self._config = config
        self._client = self._build_client(config)

    @staticmethod
    def _build_client(config: ClobOrderClientConfig) -> Any:
        from py_clob_client.client import ClobClient  # deferred import
        from py_clob_client.clob_types import ApiCreds

        creds = ApiCreds(
            api_key=config.api_key,
            api_secret=config.api_secret,
            api_passphrase=config.api_passphrase,
        )
        return ClobClient(
            host=config.clob_api_base,
            key=config.private_key,
            chain_id=137,  # Polygon mainnet
            creds=creds,
        )

    def place_limit_order(self, request: LiveOrderRequest) -> dict[str, Any]:
        from py_clob_client.clob_types import OrderArgs, OrderType

        order_args = OrderArgs(
            token_id=request.token_id,
            price=float(request.price),
            size=float(request.size),
            side=request.side,
        )
        signed_order = self._client.create_order(order_args)
        resp = self._client.post_order(signed_order, OrderType.GTC)
        return dict(resp) if not isinstance(resp, dict) else resp

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        resp = self._client.cancel(order_id)
        return dict(resp) if not isinstance(resp, dict) else resp
```

Deferred import pattern means tests can mock `py_clob_client.client.ClobClient` without having the package installed (use `unittest.mock.patch`).

3. In `tests/test_clob_order_client.py` write the 6 tests described in the behavior block. Use `unittest.mock.patch` to mock `py_clob_client.client.ClobClient` and `py_clob_client.clob_types`. Do NOT make real network calls. Mark tests that import py-clob-client with `@pytest.mark.optional_dep` (consistent with existing test conventions).
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_clob_order_client.py -v --tb=short 2>&1 | tail -20</automated>
  </verify>
  <done>All 6 tests pass. pyproject.toml has `live` extra. clob_order_client.py exists with ClobOrderClientConfig and PolymarketClobOrderClient.</done>
</task>

<task type="auto">
  <name>Task 2: Wire live runner + trade_log.jsonl + CLI env-var gate</name>
  <files>
    packages/polymarket/crypto_pairs/live_runner.py
    tools/cli/crypto_pair_run.py
  </files>
  <action>
1. Add `_log_trade_event()` to `CryptoPairLiveRunner` in `live_runner.py`:

```python
def _log_trade_event(
    self,
    *,
    action: str,          # "place" | "cancel"
    at: str,
    cycle: int,
    market_id: str,
    leg: str | None,
    order_id: str | None,
    accepted: bool,
    submitted: bool,
    reason: str,
    raw_response: dict | None = None,
) -> None:
    import json as _json
    log_path = self.store.run_dir / "trade_log.jsonl"
    entry = {
        "action": action,
        "at": at,
        "cycle": cycle,
        "market_id": market_id,
        "leg": leg,
        "order_id": order_id,
        "accepted": accepted,
        "submitted": submitted,
        "reason": reason,
    }
    if raw_response is not None:
        entry["raw_response"] = raw_response
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(_json.dumps(entry) + "\n")
```

Call `_log_trade_event()` in two places inside `_process_opportunity()`:
- After `self.execution_adapter.place_order(...)` returns `result` — pass `action="place"`, `leg=leg`, and all result fields.
- After each `self.execution_adapter.cancel_order(...)` call in `_handle_disconnect_state()` — pass `action="cancel"`, `leg=None`.

2. In `tools/cli/crypto_pair_run.py`, add env-var-based client construction at the top of `run_crypto_pair_runner()`, inside the `if live:` branch, BEFORE building `CryptoPairLiveRunner`. This is the only place that constructs a live runner. Existing `execution_adapter` injection must still work (tests pass a mock adapter):

```python
if live and execution_adapter is None:
    from packages.polymarket.crypto_pairs.clob_order_client import (
        ClobOrderClientConfig,
        ClobOrderClientConfigError,
        PolymarketClobOrderClient,
    )
    try:
        clob_cfg = ClobOrderClientConfig.from_env()
        real_client = PolymarketClobOrderClient(clob_cfg)
    except ClobOrderClientConfigError as exc:
        raise ValueError(str(exc)) from exc
    from packages.polymarket.crypto_pairs.live_execution import CryptoPairLiveExecutionAdapter
    from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch
    execution_adapter = CryptoPairLiveExecutionAdapter(
        kill_switch=FileBasedKillSwitch(
            kill_switch_path or Path(payload.get("kill_switch_path", DEFAULT_KILL_SWITCH_PATH))
        ),
        order_client=real_client,
        live_enabled=True,
    )
```

The deferred import of `PolymarketClobOrderClient` (which itself has a deferred py-clob-client import) means paper mode and tests that don't pass `--live` never import py-clob-client. Scope guards: do NOT modify `paper_runner.py`. Do NOT remove the `execution_adapter` parameter from `run_crypto_pair_runner`.
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_clob_order_client.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_run.py -v --tb=short 2>&1 | tail -30</automated>
  </verify>
  <done>
    - live_runner.py has _log_trade_event() called after every place and cancel
    - crypto_pair_run.py builds PolymarketClobOrderClient from env when --live + no injected adapter
    - Missing env var raises ValueError before runner starts
    - All three test files pass with no regressions
  </done>
</task>

<task type="auto">
  <name>Task 3: Docker pair-bot services + docker_data + dev log</name>
  <files>
    docker-compose.yml
    docker_data/.gitkeep
    .gitignore
    docs/dev_logs/2026-03-28_crypto_pair_live_docker.md
  </files>
  <action>
1. Append two new services to the existing `docker-compose.yml` (do NOT remove or modify existing services: clickhouse, grafana, api, migrate, polytool). Add them before the closing `volumes:` block:

```yaml
  pair-bot-paper:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: polytool-pair-bot-paper
    env_file:
      - .env
    command: [
      "python", "-m", "polytool", "crypto-pair-run",
      "--duration-hours", "24",
      "--cycle-interval-seconds", "30",
      "--output", "/data/paper",
      "--kill-switch", "/data/paper/KILL_SWITCH",
      "--reference-feed-provider", "coinbase"
    ]
    volumes:
      - ./docker_data/paper:/data/paper
    profiles:
      - pair-bot
    restart: "no"

  pair-bot-live:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: polytool-pair-bot-live
    env_file:
      - .env
    command: [
      "python", "-m", "polytool", "crypto-pair-run",
      "--live",
      "--confirm", "CONFIRM",
      "--duration-hours", "24",
      "--cycle-interval-seconds", "30",
      "--output", "/data/live",
      "--kill-switch", "/data/live/KILL_SWITCH"
    ]
    volumes:
      - ./docker_data/live:/data/live
    profiles:
      - pair-bot-live
    restart: "no"
```

Use Docker profiles so `docker compose up` (without `--profile`) does NOT start the pair-bot services and does NOT break existing ClickHouse/Grafana usage. Partner launches with:
- Paper: `docker compose --profile pair-bot up pair-bot-paper`
- Live: `docker compose --profile pair-bot-live up pair-bot-live`

Kill switch: touching `docker_data/paper/KILL_SWITCH` or `docker_data/live/KILL_SWITCH` from the host trips the kill switch inside the container (shared volume bind mount).

2. Create `docker_data/.gitkeep` (empty file) so the directory is tracked by git but its contents (runtime artifact subdirs) are not.

3. Add to `.gitignore` (append after the existing `artifacts/**` block):
```
# Crypto pair bot Docker runtime data
/docker_data/paper/
/docker_data/live/
```
Do NOT ignore the `docker_data/` directory itself (we need `.gitkeep` tracked).

4. Write the dev log at `docs/dev_logs/2026-03-28_crypto_pair_live_docker.md`. Include:
   - Summary: what was built (live execution wiring, trade_log.jsonl, Docker services)
   - Files changed
   - Test results: list exact test counts from the verification run
   - How to use (paper launch, live launch, kill switch)
   - Open items: market availability blocker still active; py-clob-client API shape may need adjustment once real auth is tested against Polymarket staging
  </action>
  <verify>
    <automated>cd "D:/Coding Projects/Polymarket/PolyTool" && python -m pytest tests/test_clob_order_client.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_run.py -v --tb=short 2>&1 | tail -10</automated>
  </verify>
  <done>
    - docker-compose.yml has pair-bot-paper and pair-bot-live services with profiles
    - docker_data/.gitkeep exists
    - .gitignore excludes docker_data/paper/ and docker_data/live/ contents
    - Dev log written at docs/dev_logs/2026-03-28_crypto_pair_live_docker.md
    - Full test suite passes with no regressions (report exact count)
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. `python -m polytool --help` — CLI loads without import errors
2. `python -m pytest tests/test_clob_order_client.py tests/test_crypto_pair_live_safety.py tests/test_crypto_pair_run.py -v --tb=short` — all pass
3. `python -m pytest tests/ -x -q --tb=short` — no regressions vs baseline (2717+ passing)
4. `docker compose config` — YAML validates (no syntax errors in docker-compose.yml)
5. Confirm `docker_data/.gitkeep` is tracked: `git status docker_data/`
6. Confirm `packages/polymarket/crypto_pairs/clob_order_client.py` exists with both exports
</verification>

<success_criteria>
- py-clob-client in pyproject.toml [live] extra
- ClobOrderClientConfig.from_env() raises ValueError listing missing keys when any of PK/CLOB_API_KEY/CLOB_API_SECRET/CLOB_API_PASSPHRASE absent
- PolymarketClobOrderClient implements CryptoPairOrderClient Protocol via deferred py-clob-client import
- CryptoPairLiveRunner._log_trade_event() appends one JSONL line per place/cancel attempt
- run_crypto_pair_runner(live=True) auto-builds PolymarketClobOrderClient from env; fails fast if keys missing
- docker compose --profile pair-bot up pair-bot-paper and --profile pair-bot-live up pair-bot-live launch successfully
- 6 new offline tests pass; no regressions in existing suite
- Dev log written
</success_criteria>

<output>
After completion, create `.planning/quick/40-crypto-pair-bot-live-execution-wiring-an/40-SUMMARY.md` using the summary template at `@D:/Coding Projects/Polymarket/PolyTool/.claude/get-shit-done/templates/summary.md`.
</output>
