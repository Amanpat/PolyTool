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

import dataclasses
import logging
import os
from typing import Optional

import discord
from discord import app_commands

from packages.polymarket.discord_bot.config import BotConfig, load_config

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


async def _ping(interaction: discord.Interaction) -> None:
    """``/ping`` → ephemeral ``pong``.  The Phase A health-check command."""
    await interaction.response.send_message("pong", ephemeral=True)


def register_commands(tree: app_commands.CommandTree, config: BotConfig) -> None:
    """Register Vera's slash commands onto ``tree``.

    Phase A: ``/ping``. Phase B: ``/pending`` (operator-only list of pending
    wallets with approve/deny buttons — the write surface lives in
    :mod:`packages.polymarket.discord_bot.approvals`).
    """
    tree.command(name="ping", description="Health check — Vera replies pong")(_ping)

    @tree.command(
        name="pending",
        description="List wallets pending review with approve/deny (operator only)",
    )
    async def _pending(interaction: discord.Interaction) -> None:
        # Lazy import so /ping-only use never imports discord_bot.approvals or
        # the discovery read deps.
        from packages.polymarket.discord_bot.approvals import pending_command

        await pending_command(interaction, config=config)

    @tree.command(
        name="status",
        description="Read-only scan-status window (operator only)",
    )
    async def _status(interaction: discord.Interaction) -> None:
        # Lazy import so /ping-only use never pulls the status read deps.
        from packages.polymarket.discord_bot.status_command import status_command

        await status_command(interaction, config=config)


class VeraClient(discord.Client):
    """Minimal gateway client: no privileged intents, one command tree."""

    def __init__(self, config: BotConfig) -> None:
        # Least privilege: only the non-privileged `guilds` intent. Privileged
        # intents (message_content, members) stay OFF.
        intents = discord.Intents.none()
        intents.guilds = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.config = config
        self._guild_id = config.guild_id
        register_commands(self.tree, config)

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


def build_client(
    config: Optional[BotConfig] = None, *, guild_id: Optional[int] = None
) -> VeraClient:
    """Construct a :class:`VeraClient` with ``/ping`` + ``/pending`` registered.

    No network I/O. ``config`` defaults to :func:`load_config` (read from the
    environment). ``guild_id`` is an explicit override (used by tests) applied on
    top of the resolved config.
    """
    if config is None:
        config = load_config()
    if guild_id is not None:
        config = dataclasses.replace(config, guild_id=guild_id)
    return VeraClient(config)


def run() -> None:
    """Entry point: load the token, build the client, and run until stopped."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = _get_token()  # raises MissingTokenError if absent — never logs it
    client = build_client(load_config())
    # discord.py reads the token internally; log_handler=None keeps our root
    # logging config (and avoids the library re-configuring handlers).
    client.run(token, log_handler=None)
