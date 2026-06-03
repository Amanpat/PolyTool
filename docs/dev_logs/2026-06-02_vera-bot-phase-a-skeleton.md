# Dev Log — Vera bot Phase A: skeleton + /ping

**Date:** 2026-06-02
**Slug:** vera-bot-phase-a-skeleton
**Type:** Feature (new in-repo discord.py service; no writes, no gate access)
**Decision record:** `docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md`
**Predecessor:** `docs/dev_logs/2026-06-02_retire-hermes-vera-agent.md` (Hermes retired)

## Objective

Stand up the new discord.py bot ("Vera") that replaces Hermes. **Phase A only**
proves the connection, token, intents, and Docker always-on path work. No
approve/deny, no gate access, no auth guard yet — nothing sensitive is exposed.
The webhook notification path stays as-is.

## What was built

### Package — `packages/polymarket/discord_bot/`

- `bot.py` — `VeraClient` (subclass of `discord.Client`), `register_commands`,
  `build_client`, `run`, `MissingTokenError`.
  - **Intents:** `discord.Intents.none()` — least privilege. No message-content
    intent, no members intent. Slash commands / interactions are delivered
    without privileged intents.
  - **One command:** `/ping` → replies `pong`, **ephemeral**. Nothing else.
  - **Token:** read from `DISCORD_BOT_TOKEN`, fail-fast (`MissingTokenError`) if
    absent. The token is **never printed or logged** — only the resolved public
    bot user/id is logged at `on_ready`. The error message names the env key,
    never a value.
  - **Command sync:** optional `DISCORD_GUILD_ID` → instant per-guild
    registration; unset → global sync (can take ~1h to appear).
- `__main__.py` — `python -m packages.polymarket.discord_bot` runs the service
  (the command the Docker service invokes).
- `__init__.py` — re-exports the public surface.

### Dependency

- `pyproject.toml`: new optional extra `discord = ["discord.py>=2.3,<3.0"]`
  (installed 2.7.1 locally). Added `packages.polymarket.discord_bot` to the
  setuptools packages list. Not added to `[all]` (kept opt-in / lean).

### Docker (deployment standard)

- `Dockerfile.vera` — lean two-stage image, installs only `.[discord]` (no
  py-clob-client / RAG / studio / build tools in runtime). Runs as non-root
  `vera` user. `CMD python -m packages.polymarket.discord_bot`.
- `docker-compose.yml`: new `vera-bot` service, `profiles: [vera-bot]` (opt-in,
  not in the default stack), `restart: unless-stopped` (long-lived).
  - **Least privilege on env:** uses explicit `environment:` passthrough of
    ONLY `DISCORD_BOT_TOKEN` (fail-fast `:?`) and `DISCORD_GUILD_ID` — **not**
    `env_file: .env`. This deliberately keeps the wallet key (`PK`), CLOB
    secrets, and the ClickHouse password OUT of the bot container; the bot does
    no trading/DB work and must not hold those.
- `.env.example`: documented `DISCORD_BOT_TOKEN` / `DISCORD_GUILD_ID` (commented
  placeholders, "never commit a real token"; operator creates the app/token/invite).

### Tests — `tests/test_vera_discord_bot.py` (12, offline)

Gated by `pytest.importorskip("discord")` + `optional_dep` marker. Cover: token
fail-fast (missing/empty/whitespace) + trimmed value + no value leak in error;
guild-id parsing (unset/valid/invalid); intents are `none()` (message_content &
members False); exactly one command `/ping` with a description; `_ping` awaits
`interaction.response.send_message("pong", ephemeral=True)`.

## Verification

**Offline (done by me):**

- `pip install "discord.py>=2.3,<3.0"` → 2.7.1.
- `pytest tests/test_vera_discord_bot.py` → **12 passed**.
- Import/build smoke: `build_client()` builds; `intents.value == 0` (none);
  registered commands == `['ping']`; `run()` with no token raises
  `MissingTokenError` (fail-fast, no network reached, no token printed).
- `python -m polytool --help` → OK (CLI unaffected; discord_bot is not imported
  by the CLI).
- `pytest tests/ --collect-only` → 5493 collected, no import breakage.
- `docker compose --profile vera-bot config` → `vera-bot` resolves; env contains
  ONLY `DISCORD_BOT_TOKEN` + `DISCORD_GUILD_ID` (verified no PK/CLOB/CH secrets);
  `:?` fail-fast trips when the token is unset.

**Live (REQUIRES OPERATOR — blocked on the bot token):**

I cannot create the Discord application, mint the bot token, or invite the bot
to a server — those are operator-only (per the decision record, "Claude does not"
create the token) and no token exists in `.env`. So the final "bot appears online
+ /ping → pong in the server" check is a handoff. Runbook:

1. Discord Developer Portal → New Application → Bot → Reset/Copy **token**.
   Invite with `applications.commands` (+ `bot`) scope. No privileged intents
   needed — leave Message Content Intent OFF.
2. Add to `.env`: `DISCORD_BOT_TOKEN=<token>` and (recommended) `DISCORD_GUILD_ID=<your server id>`.
3. `docker compose --profile vera-bot up -d --build vera-bot`
4. `docker compose logs -f vera-bot` → expect `Vera is online as <name> (id=...)`
   and `Slash commands synced to guild <id> (instant).`
5. In the server, run `/ping` → expect an ephemeral `pong`.

(If you prefer, paste a token into `.env` and I can run steps 3–4 to confirm
login + command sync from the logs; step 5's `/ping` still needs a human in
Discord.)

## Guards honored

- No writes, no gate access, no approve/deny, no auth guard (Phase A exposes
  nothing sensitive).
- No denylist paths touched (kill_switch / execution / risk_manager / trading /
  secrets / config/).
- Token never logged. No secret committed.
- Webhook notification path untouched.

## Open items / next

- **Phase B** (separate packet): `/pending` + approve/deny buttons routed through
  the existing `discovery review` gate (`validate_transition`), author-ID guarded,
  Codex adversarial review MANDATORY. Not started here.
- Live verification handoff above is the one required step I could not perform.
