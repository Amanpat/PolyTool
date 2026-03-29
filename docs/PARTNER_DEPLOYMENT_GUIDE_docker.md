# Crypto Pair Bot — Docker Deployment Guide

## Overview

This guide covers deploying the crypto pair bot to any Linux host with Docker and
Docker Compose. The bot runs as a non-root container (`botuser`) and writes all
output to the repo's `artifacts/` directory via a bind mount.

Two services are defined:

| Service | Profile | Default | Purpose |
|---|---|---|---|
| `pair-bot-live` | _(none — default)_ | yes | Live trading. Started by `docker compose up`. |
| `pair-bot-paper` | `pair-bot` | no | Paper test. Started manually with `docker compose run`. |

Infrastructure services (ClickHouse, Grafana, API, Migrate, SimTrader Studio) are
unrelated to the bot and are not covered here.

---

## Prerequisites

- Docker Engine >= 24 and Docker Compose v2 (`docker compose` not `docker-compose`)
- A funded Polymarket wallet and its private key
- An `.env` file with at minimum `POLYMARKET_PRIVATE_KEY` set

---

## One-time Setup

```bash
# Clone and enter the repo
git clone <repo-url>
cd PolyTool

# Create your .env from the template
cp .env.example .env
# Edit .env and set POLYMARKET_PRIVATE_KEY=0x<your_hot_wallet_key>

# artifacts/ is gitignored but must exist for the volume mount
mkdir -p artifacts
```

---

## Output Paths

The bot uses its built-in default paths, all under `artifacts/`. The Docker volume
mount `./artifacts:/app/artifacts` makes these visible on the host at the same paths.

| Mode | Host path |
|---|---|
| Paper runs | `artifacts/tapes/crypto/paper_runs/<run-id>/` |
| Live runs | `artifacts/crypto_pairs/live_runs/<run-id>/` |
| Kill switch | `artifacts/crypto_pairs/kill_switch.txt` |

---

## Paper Test (run first, always)

Verify the bot starts, connects to price feeds, and runs its paper cycle without
errors before any live capital is committed.

```bash
# Run paper mode for 2 minutes, then exit
docker compose run --rm pair-bot-paper --duration-minutes 2

# Check output
ls -la artifacts/tapes/crypto/paper_runs/
```

Expected: a timestamped run directory with `run_manifest.json`, `cycle_log.jsonl`,
and no error stack traces.

---

## Live Run

```bash
# Build image and start live bot in the background
docker compose up -d --build

# Tail logs
docker compose logs -f pair-bot-live

# Check run output
ls -la artifacts/crypto_pairs/live_runs/

# Stop (graceful shutdown)
docker compose down
```

The bot self-terminates after `--duration-hours 8` (default). Docker will restart
it automatically (`restart: unless-stopped`) after each 8-hour cycle — each restart
creates a fresh run directory with its own artifacts.

---

## Kill Switch

To immediately halt the bot without stopping the container:

```bash
touch artifacts/crypto_pairs/kill_switch.txt
```

The bot's kill-switch checker fires within the next cycle interval (default 30s)
and exits cleanly. The container will then restart (per `unless-stopped`) unless
you also stop it:

```bash
touch artifacts/crypto_pairs/kill_switch.txt
docker compose stop pair-bot-live
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `POLYMARKET_PRIVATE_KEY` | **Yes** | Hot wallet private key (0x...) |
| `POLYMARKET_API_KEY` | No | Pre-derived CLOB API key |
| `POLYMARKET_API_SECRET` | No | Pre-derived CLOB API secret |
| `POLYMARKET_PASSPHRASE` | No | Pre-derived CLOB API passphrase |
| `POLYMARKET_FUNDER` | No | Funder address if using proxy wallet |
| `POLYMARKET_CHAIN_ID` | No | Polygon chain ID (default: 137) |
| `POLYMARKET_CLOB_URL` | No | CLOB endpoint (default: https://clob.polymarket.com) |

If `POLYMARKET_API_KEY` / `API_SECRET` / `PASSPHRASE` are absent, the bot derives
or creates API credentials automatically on startup.

---

## Output Layout

```
artifacts/
  tapes/crypto/paper_runs/
    <run-id>/
      run_manifest.json
      cycle_log.jsonl
  crypto_pairs/
    kill_switch.txt          ← touch this to halt the bot
    live_runs/
      <run-id>/
        run_manifest.json
        cycle_log.jsonl
        trade_log.jsonl      ← every place/cancel event with timestamps
        open_positions.json
```

---

## Useful Commands

```bash
# Rebuild image after code changes
docker compose build pair-bot-live

# Tail logs
docker compose logs -f pair-bot-live

# View last 100 log lines
docker compose logs --tail=100 pair-bot-live

# Inspect container resource usage
docker stats polytool-pair-bot-live

# Remove stopped containers and dangling images
docker compose down --remove-orphans
docker image prune -f
```

---

## Security Notes

- Never commit `.env` to git. It is listed in `.gitignore`.
- The container runs as non-root `botuser` — no sudo or host-level access.
- The private key is passed via env var only, never written to disk inside the container.
- `artifacts/` should be mode `700` on the host.
- Rotate the hot wallet key after any suspected compromise; it holds only trading capital, never main wallet funds.
