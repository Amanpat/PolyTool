"""DR-3: the ``/status`` slash-command handler (Discord layer, READ-ONLY).

Thin handler over :mod:`packages.polymarket.discord_bot.status_window` (the pure,
testable assembler). This file owns ONLY the Discord I/O and the author-guard;
all data assembly + embed building lives in ``status_window`` so it tests with no
Discord and no ClickHouse.

READ-ONLY CONTRACT:
- ``/status`` reads counts and one ranked query and posts a card. There is NO
  write path reachable from here: no subprocess, no writer import, no lifecycle
  mutation. The only DB touch is ``status_window.read_status_snapshot`` (HTTP GET
  SELECTs). Unlike ``/pending`` there are NO action buttons.

AUTHOR-GUARD (reuses the shipped ``approvals.is_operator`` pattern, commit
c66f375 "make /pending cards public, keep author-guard"):
- Only the configured operator may summon ``/status``; any other member gets an
  ephemeral "Not authorized" and NOTHING is read or posted. Fail-closed: an unset
  operator id authorizes NO ONE. The resulting card is PUBLIC (visible in the
  private channel), matching the /pending visibility decision.
"""

from __future__ import annotations

import logging
from typing import Optional

import discord

from packages.polymarket.discord_bot.approvals import is_operator
from packages.polymarket.discord_bot.config import BotConfig
from packages.polymarket.discord_bot.status_window import (
    StatusSnapshot,
    build_status_embed,
    read_status_snapshot,
)

logger = logging.getLogger("vera.status_command")

# The reader is injectable (default :func:`_default_reader`) so tests never touch
# ClickHouse. It maps a :class:`BotConfig` -> :class:`StatusSnapshot` or None
# (None = could not read, e.g. CLICKHOUSE_PASSWORD unset).


def _default_reader(config: BotConfig) -> Optional[StatusSnapshot]:
    ch = config.clickhouse
    return read_status_snapshot(host=ch.host, port=ch.port, user=ch.user)


async def status_command(
    interaction: discord.Interaction,
    *,
    config: BotConfig,
    reader=_default_reader,
) -> None:
    """Handle ``/status``. Author-guarded, read-only, never raises.

    Only the operator may summon it (author-guard); the resulting card is public
    in the channel. ``reader`` is injectable for offline tests.
    """
    try:
        # Author-guard FIRST — a non-operator gets an ephemeral denial and we
        # NEVER read the DB or post a public card for them.
        if not is_operator(interaction, config):
            uid = getattr(getattr(interaction, "user", None), "id", None)
            logger.warning("Unauthorized /status by user id=%s — rejected.", uid)
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return

        # Public deferral — the card below is visible to the whole channel.
        await interaction.response.defer(thinking=True)

        snap = reader(config)
        if snap is None:
            await interaction.edit_original_response(
                content="Could not read scan status right now (is ClickHouse "
                "reachable and CLICKHOUSE_PASSWORD set?)."
            )
            return

        embed = discord.Embed.from_dict(build_status_embed(snap))
        await interaction.edit_original_response(embed=embed)
    except Exception:  # never raise out of a command callback
        logger.exception("Unexpected error in /status (read-only path).")
        try:
            await interaction.followup.send(
                "Something went wrong building the status card.", ephemeral=True
            )
        except Exception:  # pragma: no cover - last-resort guard
            pass
