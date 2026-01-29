"""Smoke check for liquidity integrity queries.

Assumes ClickHouse is reachable.
"""

from __future__ import annotations

import os
import sys

import clickhouse_connect


def _env_int(key: str, default: str) -> int:
    value = os.getenv(key, default)
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{key} must be an integer, got: {value}") from exc


def _print_rows(rows: list[list], empty_message: str) -> None:
    if not rows:
        print(empty_message)
        return
    for row in rows:
        print("  " + ", ".join(str(item) for item in row))


def main() -> int:
    host = os.getenv("CLICKHOUSE_HOST", "clickhouse")
    port = _env_int("CLICKHOUSE_PORT", "8123")
    username = os.getenv("CLICKHOUSE_USER", "polyttool_admin")
    password = os.getenv("CLICKHOUSE_PASSWORD", "polyttool_admin")
    database = os.getenv("CLICKHOUSE_DATABASE", "polyttool")

    client = clickhouse_connect.get_client(
        host=host,
        port=port,
        username=username,
        password=password,
        database=database,
    )

    print("Duplicate token_id rows in market_tokens:")
    result = client.query(
        """
        SELECT token_id, count() c
        FROM polyttool.market_tokens
        GROUP BY token_id
        HAVING c > 1
        ORDER BY c DESC
        LIMIT 20
        """
    )
    _print_rows(result.result_rows, "  none")

    print("Duplicate snapshot_ts + token_id rows in orderbook_snapshots_enriched (last 30 days):")
    result = client.query(
        """
        SELECT snapshot_ts, token_id, count() c
        FROM polyttool.orderbook_snapshots_enriched
        WHERE snapshot_ts > now() - INTERVAL 30 DAY
        GROUP BY snapshot_ts, token_id
        HAVING c > 1
        ORDER BY c DESC
        LIMIT 20
        """
    )
    _print_rows(result.result_rows, "  none")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"Liquidity integrity smoke failed: {exc}")
        sys.exit(1)
