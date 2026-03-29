# Crypto Pair Bot — Docker Deployment Guide

## Overview

This guide covers deploying the crypto pair bot to any Linux host with Docker and
Docker Compose. The bot runs as a non-root container (`botuser`) and writes all
output to bind-mounted host directories under `docker_data/`.

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

# Create output directories (git only tracks .gitkeep)
mkdir -p docker_data/paper docker_data/live docker_data/kill_switch
```

---

## Paper Test (run first, always)

Verify the bot starts, connects to price feeds, and runs its paper cycle without
errors before any live capital is committed.

```bash
# Run paper mode for 2 minutes, then exit
docker compose run --rm pair-bot-paper --duration-minutes 2

# Check output
ls -la docker_data/paper/
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
ls -la docker_data/live/

# Stop (graceful shutdown)
docker compose down
```

The bot self-terminates after `--duration-hours 8` (default). Docker will restart
it automatically (`restart: unless-stopped`) after each 8-hour cycle. To run
continuously, this is intentional — each restart creates a fresh run directory
with its own artifacts.

---

## Kill Switch

To immediately halt the bot without stopping the container:

```bash
touch docker_data/live/KILL_SWITCH
```

The bot's kill-switch checker fires within the next cycle interval (default 30s)
and exits cleanly. The container will then restart (per `unless-stopped`) unless
you also run `docker compose down` or `docker compose stop pair-bot-live`.

To halt permanently:
```bash
touch docker_data/live/KILL_SWITCH
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
docker_data/
  live/
    KILL_SWITCH          ← touch this to halt the bot
    <run-id>/
      run_manifest.json
      cycle_log.jsonl
      trade_log.jsonl    ← every place/cancel event with timestamps
      open_positions.json
  paper/
    <run-id>/
      run_manifest.json
      cycle_log.jsonl
```

---

## Useful Commands

```bash
# Rebuild image after code changes
docker compose build pair-bot-live

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
- `docker_data/live/` should be mode `700` on the host.
- Rotate the hot wallet key after any suspected compromise; it holds only trading capital, never main wallet funds.
