"""Vera — PolyTool operator Discord bot.

Phase A: connection + token + intents + Docker always-on path, ``/ping``.
Phase B: ``/pending`` + one-tap approve/deny buttons — the first Discord-triggered
write surface, implemented as a THIN TRIGGER over the verified ``discovery review``
CLI (see :mod:`packages.polymarket.discord_bot.approvals`).

The webhook notification path (``packages.polymarket.notifications.discord`` /
``packages.polymarket.discovery.pending_notify``) is a separate, decoupled
transport and is unaffected by this bot.
"""

from packages.polymarket.discord_bot.bot import (
    MissingTokenError,
    VeraClient,
    build_client,
    register_commands,
    run,
)
from packages.polymarket.discord_bot.config import BotConfig, ClickHouseConfig, load_config

__all__ = [
    "MissingTokenError",
    "VeraClient",
    "build_client",
    "register_commands",
    "run",
    "BotConfig",
    "ClickHouseConfig",
    "load_config",
]
