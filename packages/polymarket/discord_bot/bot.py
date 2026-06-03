"""Vera operator Discord bot — Phase A skeleton (connection + ``/ping``).

Phase A scope (intentionally tiny):
- Prove the bot connects to the Discord gateway with a token from the
  environment, registers exactly one slash command, and runs as a long-lived
  service (Docker ``restart: unless-stopped``).
- NO writes, NO gate access, NO approve/deny buttons, NO author-ID auth guard.
  Nothing sensitive is exposed, so no auth surface exists to protect yet.  Those
  arrive in Phase B (``/pending`` + approve/deny routed through the existing
  ``discovery review`` gate — see the decision record below).

Security contract:
- The bot token is read from ``DISCORD_BOT_TOKEN`` and is **never** printed or
  logged.  Only the resolved bot user/id (public) is logged at startup.
- Least-privilege gateway intents: only the non-privileged ``guilds`` intent
  (discord.py's recommended baseline for a slash-command bot; avoids the
  "Guilds intent seems to be disabled" state warning).  The privileged
  ``message_content`` and ``members`` intents are explicitly OFF.

Decision record:
    docs/obsidian-vault/claude-memory/decisions/decision-retire-hermes-build-vera-bot.md
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import discord
from discord import app_commands

_TOKEN_ENV = "DISCORD_BOT_TOKEN"
_GUILD_ENV = "DISCORD_GUILD_ID"

logger = logging.getLogger("vera.bot")


class MissingTokenError(RuntimeError):
    """Raised when ``DISCORD_BOT_TOKEN`` is absent or empty.

    The message deliberately never includes the (missing) value.
    """


def _get_token() -> str:
    """Return the bot token from the environment, fail-fast if unset.

    The token value is never logged or included in the raised error.
    """
    token = os.environ.get(_TOKEN_ENV, "").strip()
    if not token:
        raise MissingTokenError(
            f"{_TOKEN_ENV} is not set. Add it to .env (never commit it). "
            "Vera cannot start without a bot token."
        )
    return token


def _get_guild_id() -> Optional[int]:
    """Optional guild ID for instant slash-command registration.

    When set, commands sync to that single guild and appear immediately.  When
    unset, commands sync globally (Discord may take up to ~1h to surface them).
    """
    raw = os.environ.get(_GUILD_ENV, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "%s is set but is not an integer; ignoring and syncing globally.",
            _GUILD_ENV,
        )
        return None


async def _ping(interaction: discord.Interaction) -> None:
    """``/ping`` → ephemeral ``pong``.  The entire Phase A command surface."""
    await interaction.response.send_message("pong", ephemeral=True)


def register_commands(tree: app_commands.CommandTree) -> None:
    """Register Phase A slash commands onto ``tree``. Exactly one: ``/ping``."""
    tree.command(name="ping", description="Health check — Vera replies pong")(_ping)


class VeraClient(discord.Client):
    """Minimal gateway client: no privileged intents, one command tree."""

    def __init__(self, guild_id: Optional[int] = None) -> None:
        # Least privilege: only the non-privileged `guilds` intent. Privileged
        # intents (message_content, members) stay OFF.
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._guild_id = guild_id
        register_commands(self.tree)

    async def setup_hook(self) -> None:
        """Sync the command tree before the gateway connection is established."""
        if self._guild_id is not None:
            guild = discord.Object(id=self._guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("Slash commands synced to guild %s (instant).", self._guild_id)
        else:
            await self.tree.sync()
            logger.info(
                "Slash commands synced globally (may take up to ~1h to appear). "
                "Set %s for instant per-guild registration.",
                _GUILD_ENV,
            )

    async def on_ready(self) -> None:
        # Public identity only — never the token.
        logger.info(
            "Vera is online as %s (id=%s).",
            self.user,
            getattr(self.user, "id", "?"),
        )


def build_client(guild_id: Optional[int] = None) -> VeraClient:
    """Construct a :class:`VeraClient` with ``/ping`` registered. No network I/O."""
    return VeraClient(guild_id=guild_id)


def run() -> None:
    """Entry point: load the token, build the client, and run until stopped."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = _get_token()  # raises MissingTokenError if absent — never logs it
    client = build_client(guild_id=_get_guild_id())
    # discord.py reads the token internally; log_handler=None keeps our root
    # logging config (and avoids the library re-configuring handlers).
    client.run(token, log_handler=None)
