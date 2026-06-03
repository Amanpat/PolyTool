"""Offline unit tests for the Vera Discord bot (Phase A skeleton).

Fully offline: no token, no gateway connection, no network. The Discord client is
constructed but never ``.run()``/``.login()``-ed, so nothing touches Discord.

These tests require the optional ``discord`` extra (``pip install polytool[discord]``);
the module is skipped entirely when discord.py is not installed.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("discord", reason="requires the [discord] optional dependency")

import discord  # noqa: E402

from packages.polymarket.discord_bot import bot as vera_bot  # noqa: E402
from packages.polymarket.discord_bot import config as vera_config  # noqa: E402
from packages.polymarket.discord_bot.bot import (  # noqa: E402
    MissingTokenError,
    VeraClient,
    build_client,
)

pytestmark = pytest.mark.optional_dep


# ---------------------------------------------------------------------------
# Token loading — fail-fast, never echoes the value
# ---------------------------------------------------------------------------


def test_get_token_missing_raises(monkeypatch):
    monkeypatch.delenv("DISCORD_BOT_TOKEN", raising=False)
    with pytest.raises(MissingTokenError):
        vera_bot._get_token()


def test_get_token_empty_raises(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "   ")
    with pytest.raises(MissingTokenError):
        vera_bot._get_token()


def test_get_token_returns_trimmed_value(monkeypatch):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "  abc.def.ghi  ")
    assert vera_bot._get_token() == "abc.def.ghi"


def test_missing_token_error_message_does_not_leak_value(monkeypatch):
    # Even when a value is somehow present-but-blank, the error names the env
    # key, never a token value.
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "")
    with pytest.raises(MissingTokenError) as excinfo:
        vera_bot._get_token()
    assert "DISCORD_BOT_TOKEN" in str(excinfo.value)


# ---------------------------------------------------------------------------
# Env int parsing (guild id, operator id)
# ---------------------------------------------------------------------------


def test_int_env_unset_returns_none(monkeypatch):
    monkeypatch.delenv("DISCORD_GUILD_ID", raising=False)
    assert vera_config._int_env("DISCORD_GUILD_ID") is None


def test_int_env_valid_int(monkeypatch):
    monkeypatch.setenv("DISCORD_GUILD_ID", "123456789012345678")
    assert vera_config._int_env("DISCORD_GUILD_ID") == 123456789012345678


def test_int_env_invalid_returns_none(monkeypatch):
    monkeypatch.setenv("DISCORD_GUILD_ID", "not-an-int")
    assert vera_config._int_env("DISCORD_GUILD_ID") is None


# ---------------------------------------------------------------------------
# Client construction — least privilege + exactly one command
# ---------------------------------------------------------------------------


def test_build_client_uses_no_privileged_intents():
    client = build_client()
    # Only the non-privileged `guilds` intent is enabled (discord.py baseline).
    assert client.intents.guilds is True
    # The privileged intents must NOT be requested.
    assert client.intents.message_content is False
    assert client.intents.members is False


def test_build_client_registers_ping_and_pending():
    client = build_client()
    commands = client.tree.get_commands()
    names = sorted(c.name for c in commands)
    assert names == ["pending", "ping"]


def test_build_client_is_vera_client():
    client = build_client(guild_id=42)
    assert isinstance(client, VeraClient)
    assert client._guild_id == 42


def test_ping_command_has_description():
    client = build_client()
    ping = next(c for c in client.tree.get_commands() if c.name == "ping")
    assert ping.description  # non-empty help text


# ---------------------------------------------------------------------------
# /ping behaviour — ephemeral pong
# ---------------------------------------------------------------------------


def test_ping_replies_pong_ephemeral():
    interaction = MagicMock()
    interaction.response.send_message = AsyncMock()

    asyncio.run(vera_bot._ping(interaction))

    interaction.response.send_message.assert_awaited_once_with("pong", ephemeral=True)
