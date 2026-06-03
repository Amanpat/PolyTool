"""Configuration for the Vera bot, loaded from the environment.

All values come from environment variables (injected by Docker compose from
.env). Secrets — the bot token and the ClickHouse password — are read at the
point of use and are **never** stored on a long-lived object that might be
logged. Only non-secret config (operator id, guild id, ClickHouse host/port/user)
lives on :class:`BotConfig`.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("vera.config")

_OPERATOR_ENV = "DISCORD_OPERATOR_USER_ID"
_GUILD_ENV = "DISCORD_GUILD_ID"


@dataclass(frozen=True)
class ClickHouseConfig:
    """Non-secret ClickHouse connection parameters.

    The password is intentionally NOT held here — it is read from
    ``CLICKHOUSE_PASSWORD`` at the call site (in-process reads) or inherited by
    the review subprocess via the environment, so it never lands on a config
    object, an argv list, or a log line.
    """

    host: str = "localhost"
    port: int = 8123
    user: str = "polytool_admin"


@dataclass(frozen=True)
class BotConfig:
    """Runtime configuration (no secrets)."""

    operator_user_id: Optional[int]
    guild_id: Optional[int]
    clickhouse: ClickHouseConfig


def _int_env(name: str) -> Optional[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        logger.warning("%s is set but is not an integer; treating as unset.", name)
        return None


def load_clickhouse_config() -> ClickHouseConfig:
    """ClickHouse connection params from the environment (no password)."""
    host = os.environ.get("CLICKHOUSE_HOST", "").strip() or "localhost"
    user = os.environ.get("CLICKHOUSE_USER", "").strip() or "polytool_admin"
    port_raw = os.environ.get("CLICKHOUSE_PORT", "").strip()
    try:
        port = int(port_raw) if port_raw else 8123
    except ValueError:
        logger.warning("CLICKHOUSE_PORT is not an integer; defaulting to 8123.")
        port = 8123
    return ClickHouseConfig(host=host, port=port, user=user)


def load_config() -> BotConfig:
    """Build :class:`BotConfig` from the environment.

    ``DISCORD_OPERATOR_USER_ID`` is required for the Phase B write surface
    (/pending + approve/deny). When it is unset the bot still starts and /ping
    works, but every approve/deny path treats *no one* as authorized (and says
    so) — fail-closed, never fail-open.
    """
    operator_user_id = _int_env(_OPERATOR_ENV)
    if operator_user_id is None:
        logger.warning(
            "%s is not set - /pending and approve/deny will reject EVERYONE "
            "until it is configured (fail-closed).",
            _OPERATOR_ENV,
        )
    return BotConfig(
        operator_user_id=operator_user_id,
        guild_id=_int_env(_GUILD_ENV),
        clickhouse=load_clickhouse_config(),
    )
