"""Vera — PolyTool operator Discord bot.

Phase A (current): connection + token + intents + Docker always-on path, with a
single ``/ping`` slash command. NO writes, NO gate access, NO approve/deny.

The webhook notification path (``packages.polymarket.notifications.discord``) is
a separate, decoupled transport and is unaffected by this bot.
"""

from packages.polymarket.discord_bot.bot import (
    MissingTokenError,
    VeraClient,
    build_client,
    register_commands,
    run,
)

__all__ = [
    "MissingTokenError",
    "VeraClient",
    "build_client",
    "register_commands",
    "run",
]
