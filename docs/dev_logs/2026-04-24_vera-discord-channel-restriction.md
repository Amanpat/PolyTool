# 2026-04-24 Vera Discord — Private Server Channel Restriction

## Scope

Restrict the vera-hermes-agent Discord gateway to a single private operator
channel on the PolyTool Discord server. Keep DM support. Keep all read-only
SOUL.md boundaries and approvals.mode: deny intact.

---

## Files Changed

| File | Change | Why |
|---|---|---|
| `/home/patel/.hermes/profiles/vera-hermes-agent/.env` | Appended `DISCORD_ALLOWED_CHANNELS` and `DISCORD_AUTO_THREAD` | Channel whitelist and thread suppression are read from env vars by the gateway source |
| `/home/patel/.hermes/profiles/vera-hermes-agent/config.yaml` | `discord.require_mention: false → true`; `discord.allowed_channels: '' → '<ID>'` | Require @VERA mention in channel; keep config.yaml in sync with env var |
| `docs/dev_logs/2026-04-24_vera-discord-channel-restriction.md` | Created (this file) | Mandatory per repo convention |

No business logic, no Python code, no live execution paths, no new skills
were touched.

---

## Config Fields Used

### Source of truth for channel restriction

The Hermes gateway reads these from **env vars** (not config.yaml) at message
dispatch time. Setting them in `.env` is the correct and only reliable path:

| Env var | Value | Effect |
|---|---|---|
| `DISCORD_ALLOWED_CHANNELS` | `<channel_id>` | Whitelist — bot silently ignores all other server channels |
| `DISCORD_AUTO_THREAD` | `false` | Disable auto-thread creation; replies are inline |
| `DISCORD_ALLOWED_USERS` | `<user_id>` (pre-existing) | Only this Discord user can interact |

### Read from config.yaml (via `config.extra`)

| Field | Value | Effect |
|---|---|---|
| `discord.require_mention` | `true` | Bot only responds in the allowed channel when @VERA is in the message |
| `discord.allowed_channels` | `<channel_id>` | Kept in sync with env var for documentation consistency |
| `discord.auto_thread` | `false` | Kept in sync with env var |

### IDs (redacted form)

- Server (guild) ID: `14117…551` (PolyTool operator server)
- Operator channel ID: `14809…891`

The channel ID alone is sufficient for server restriction — Discord channel IDs
are globally unique, so the channel whitelist implicitly restricts to the correct
server.

---

## DM Behaviour

DMs are routed through a separate code path (`discord.DMChannel`) that bypasses
the `DISCORD_ALLOWED_CHANNELS` check entirely. DM support is preserved.
`DISCORD_ALLOWED_USERS` still gates DMs — only the allowlisted user ID can
initiate them.

---

## Routing Logic (verified in source)

From `gateway/platforms/discord.py` `_handle_message()`:

```python
if not isinstance(message.channel, discord.DMChannel):
    # Check allowed channels - whitelist
    allowed_channels_raw = os.getenv("DISCORD_ALLOWED_CHANNELS", "")
    if allowed_channels_raw:
        allowed_channels = {ch.strip() for ch in allowed_channels_raw.split(",") ...}
        if "*" not in allowed_channels and not (channel_ids & allowed_channels):
            return  # silently ignored

    # require_mention check
    if require_mention and not is_free_channel and not in_bot_thread:
        if self._client.user not in message.mentions ...:
            return
```

Messages in any channel other than `1480993371429408891` are silently dropped
before any processing. @VERA mention required in the allowed channel.

---

## Post-Restart Gateway Connection

Restarted via `scripts/start_vera_discord_gateway.sh` at 15:36 UTC.

From `agent.log`:
```
INFO gateway.platforms.discord: [Discord] Connected as VERA#2261
INFO gateway.run: ✓ discord connected
INFO gateway.run: Gateway running with 1 platform(s)
INFO gateway.run: Channel directory built: 1 target(s)
```

Slash command sync returned 503 (Discord-side upstream error) — non-fatal,
message routing unaffected.

---

## Safety Posture — Confirmed

| Check | Result |
|---|---|
| `approvals.mode` | `deny` ✓ |
| `cron_mode` | `deny` ✓ |
| `command_allowlist` | `[]` ✓ |
| Local skills | 3/3 discovered ✓ |
| SOUL.md read-only boundaries | Intact ✓ |
| Channel restriction | `DISCORD_ALLOWED_CHANNELS` set ✓ |
| User allowlist | `DISCORD_ALLOWED_USERS` set ✓ |
| @mention required in channel | `require_mention: true` ✓ |

---

## Live Test Results

| # | Query | Channel / DM | Result |
|---|---|---|---|
| C1 | `@VERA What skills do you have?` | Operator channel | PENDING |
| C2 | `@VERA What's active right now?` | Operator channel | PENDING |
| C3 | `@VERA Summarize the latest dev log.` | Operator channel | PENDING |
| C4 | `@VERA Edit a file.` | Operator channel | PENDING — expect refusal |

---

## Final Status

| Item | Status |
|---|---|
| Channel whitelist configured | DONE — `DISCORD_ALLOWED_CHANNELS` in .env |
| @mention required | DONE — `require_mention: true` in config.yaml |
| Auto-thread disabled | DONE — `DISCORD_AUTO_THREAD=false` in .env |
| DM support | PRESERVED |
| Gateway restarted and connected | DONE — VERA#2261 online |
| Live tests | PENDING — operator running now |

**Next action:** Operator runs C1–C4 in the private channel and reports results.

---

## Codex Review

Tier: Skip — .env and config.yaml changes only, no Python code touched.
