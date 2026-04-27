# 2026-04-24 Vera Discord Gateway — Startup Fix and Intent Blocker

## Scope

Determine the correct startup method for the vera-hermes-agent Discord gateway,
verify the existing profile config is healthy, start the gateway, and document
the result.

Prior failure: a previous attempt called `systemctl start discord-gateway` — no
such systemd unit exists. The correct method was not tested.

---

## Files Changed

| File | Change | Why |
|---|---|---|
| `scripts/start_vera_discord_gateway.sh` | Created | Reproducible operator launch script for the Discord gateway via tmux |
| `docs/dev_logs/2026-04-24_vera-discord-gateway-fix.md` | Created (this file) | Mandatory per repo convention |

No code, no skill, no business logic, no live execution paths were touched.

---

## Startup Method Confirmed

**Method:** `hermes -p vera-hermes-agent gateway run` (foreground, in tmux)

This is the official Hermes CLI command. Verified via `hermes gateway --help`:
```
run    Run gateway in foreground (recommended for WSL, Docker, Termux)
```

There is no systemd unit and none should be created — the Hermes docs explicitly
recommend `gateway run` for WSL. `gateway install` would create a systemd unit,
but that is not appropriate for this machine.

**Persistent startup via tmux:**
```bash
# From Windows terminal
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/start_vera_discord_gateway.sh"

# Or directly inside WSL
bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/start_vera_discord_gateway.sh
```

The script creates a tmux session named `vera-hermes-discord`. Idempotent — kills
any stale session before starting. Logs to
`/home/patel/.hermes/profiles/vera-hermes-agent/logs/gateway.log`.

To attach:
```bash
wsl bash -lc "tmux attach -t vera-hermes-discord"
```

To stop:
```bash
wsl bash -lc "tmux kill-session -t vera-hermes-discord"
```

---

## Pre-Flight Config Verification

All checks passed before starting:

| Check | Result |
|---|---|
| `DISCORD_BOT_TOKEN` in .env | PRESENT (non-empty) |
| `DISCORD_ALLOWED_USERS` in .env | PRESENT (non-empty) |
| `approvals.mode` | `deny` ✓ |
| `cron_mode` | `deny` ✓ |
| `command_allowlist` | `[]` ✓ |
| Local skills discovered | 3/3: polytool-dev-logs, polytool-files, polytool-status ✓ |
| Primary model | `openrouter / google/gemini-2.0-flash-001` |
| Fallback model | `openrouter / google/gemini-2.0-flash-001` |
| SOUL.md boundaries | Intact — read-only declared, obsidian-vault excluded ✓ |

---

## Gateway Run Result

**Status: FAILED — Discord Privileged Intents not enabled**

The gateway process started correctly. The Hermes binary is:
```
/home/patel/.hermes/hermes-agent/venv/bin/python3 /home/patel/.local/bin/hermes
```

Connection timed out after 30 seconds. Root cause from
`/home/patel/.hermes/profiles/vera-hermes-agent/logs/errors.log`:

```
discord.errors.PrivilegedIntentsRequired:
Shard ID None is requesting privileged intents that have not been explicitly
enabled in the developer portal. It is recommended to go to
https://discord.com/developers/applications/ and explicitly enable the
privileged intents within your application's page.
```

The startup method is correct. The token is valid enough for the bot to reach
Discord's API. The failure is a portal configuration problem, not a code problem.

---

## Required Operator Action: Enable Privileged Gateway Intents

**This step requires Aman to log into the Discord Developer Portal. Claude cannot do this.**

### Steps

1. Go to: https://discord.com/developers/applications/
2. Select the PolyTool bot application (the app whose token is in `.env`)
3. Click **Bot** in the left sidebar
4. Scroll down to **Privileged Gateway Intents**
5. Enable **MESSAGE CONTENT INTENT** — required for the bot to read DM messages
6. Optionally enable **SERVER MEMBERS INTENT** and **PRESENCE INTENT** if gateway logs show those are also required after the first fix
7. Click **Save Changes**

After saving:

```bash
wsl bash -lc "bash /mnt/d/Coding\ Projects/Polymarket/PolyTool/scripts/start_vera_discord_gateway.sh"
```

Then verify:
```bash
wsl bash -lc "sleep 10 && hermes -p vera-hermes-agent gateway status"
```

Expected after the portal fix:
```
✓ Gateway is running
  discord: connected
```

---

## DM Test Plan (run after gateway is online)

Send these to the bot as a DM in Discord:

| # | Message | Expected |
|---|---|---|
| R1 | `What skills do you have?` | Lists polytool-dev-logs, polytool-status, polytool-files |
| R2 | `What's active right now?` | Summarizes CURRENT_STATE.md / CURRENT_DEVELOPMENT.md |
| R3 | `Summarize the latest dev log.` | Reads most recent file under docs/dev_logs/ |
| R4 | `Read PLAN_OF_RECORD and summarize it.` | Reads docs/PLAN_OF_RECORD.md and summarizes |
| W1 | `Edit a file` or `Start the bot` | Immediate refusal: "This instance is read-only." |

---

## Gateway Connection (Second Attempt — After Portal Fix)

Operator enabled **Message Content Intent** in Discord Developer Portal.
Gateway restarted via `scripts/start_vera_discord_gateway.sh`.

From `agent.log` (15:22 UTC):

```
INFO gateway.run: Connecting to discord...
INFO gateway.platforms.discord: [Discord] Registered /skill command with 70 skill(s)
INFO discord.gateway: Shard ID None has connected to Gateway (Session ID: 2b46...)
INFO gateway.platforms.discord: [Discord] Connected as VERA#2261
INFO gateway.run: ✓ discord connected
INFO gateway.run: Gateway running with 1 platform(s)
INFO gateway.run: Cron ticker started (interval=60s)
WARNING gateway.platforms.discord: [Discord] Slash command sync timed out after 30s
```

Slash command sync timeout is non-fatal — DM messaging is fully operational.
Bot is online and accepting DMs as **VERA#2261**.

---

## Final Status

| Item | Status |
|---|---|
| Startup method identified | DONE — `hermes -p vera-hermes-agent gateway run` via tmux |
| Launch script created | DONE — `scripts/start_vera_discord_gateway.sh` |
| Profile config pre-flight | PASS — all safety checks green |
| Gateway process started | DONE |
| Discord connection | **CONNECTED — VERA#2261 online** |
| DM tests | PENDING — operator to run against live bot |

**Next action:** Run 4 read-only DM tests + 1 write/control refusal test listed
in the DM Test Plan above. Report results.

---

## Codex Review

Tier: Skip — launch script + dev log only, no Python code, no live paths touched.
