---
status: complete
completed: 2026-06-02
track: operator-tooling
scope: read-only
phase: A
---

# Feature: Vera Discord Bot — Phase A (skeleton + /ping)

The first phase of the purpose-built discord.py bot ("Vera") that replaces the
retired Hermes agent. Phase A proves the connection, token, intents, and Docker
always-on path. It exposes **one** slash command, `/ping`, and does **no** writes,
gate access, or approve/deny work. The webhook notification path is separate and
unaffected.

See the decision record:
`docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md`.

## What Was Built

| Item | Detail |
|---|---|
| Package | `packages/polymarket/discord_bot/` (`bot.py`, `__main__.py`, `__init__.py`) |
| Client | `VeraClient(discord.Client)` with `app_commands.CommandTree` |
| Intents | `discord.Intents.none()` — no message-content, no members (least privilege) |
| Command | `/ping` → ephemeral `pong` (the entire Phase A surface) |
| Token | `DISCORD_BOT_TOKEN` env var, fail-fast `MissingTokenError`; **never logged** |
| Guild sync | optional `DISCORD_GUILD_ID` → instant; unset → global (~1h) |
| Dependency | `pyproject.toml` extra `discord = ["discord.py>=2.3,<3.0"]` (opt-in) |
| Image | `Dockerfile.vera` — lean, `.[discord]` only, non-root `vera` user |
| Service | `docker-compose.yml` `vera-bot`, profile `vera-bot`, `restart: unless-stopped` |
| Env scope | explicit passthrough of ONLY the two Discord vars — NOT `env_file` (keeps `PK`/CLOB/CH secrets out of the bot container) |
| Tests | `tests/test_vera_discord_bot.py` — 12 offline (importorskip `discord`) |

## Security Boundaries (Phase A)

| Boundary | State |
|---|---|
| Writes | None — read-only; `/ping` only |
| Gate access / approve-deny | None — deferred to Phase B |
| Author-ID auth guard | Not present — nothing sensitive is exposed yet |
| Token handling | Read from env, fail-fast, never printed/logged |
| Gateway intents | `none()` — least privilege |
| Container secrets | Only `DISCORD_BOT_TOKEN` + `DISCORD_GUILD_ID`; no wallet/CLOB/DB secrets |
| Denylist paths | Untouched (kill_switch / execution / risk_manager / trading / secrets / config) |

## Run / Verify

```bash
# Operator: create the Discord app + bot token + invite (applications.commands scope).
# Add DISCORD_BOT_TOKEN (and recommended DISCORD_GUILD_ID) to .env.
docker compose --profile vera-bot up -d --build vera-bot
docker compose logs -f vera-bot          # expect: "Vera is online as <name> ..."
# In the server: run /ping  -> ephemeral "pong"
```

Offline verification (no token/network): `pytest tests/test_vera_discord_bot.py`
(12 passed). Full live "online + /ping → pong" check requires the operator's token.

## Next Phase

**Phase B** (separate packet, Codex adversarial review MANDATORY): `/pending`
list + approve/deny **buttons** routed through the existing enforced gate
(`validate_transition` via `discovery review`), author-ID guarded, idempotent,
defer-within-3s, disable-after-action. Scoped to approve/deny ONLY.

## Related Files

- `packages/polymarket/discord_bot/bot.py` — the bot
- `Dockerfile.vera`, `docker-compose.yml` (`vera-bot` service)
- `tests/test_vera_discord_bot.py`
- `docs/dev_logs/2026-06-02_vera-bot-phase-a-skeleton.md` — this session's dev log
