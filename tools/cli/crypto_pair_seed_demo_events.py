"""CLI: dev-only synthetic Track 2 event seeder for dashboard validation."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from packages.polymarket.crypto_pairs.clickhouse_sink import (
    CryptoPairClickHouseSinkConfig,
    build_clickhouse_sink,
)
from packages.polymarket.crypto_pairs.dev_seed import (
    DEMO_SEED_SOURCE,
    seed_demo_events,
)


_CLI_PREFIX = "[crypto-pair-seed-demo-events]"
_DEV_ONLY_NOTE = "synthetic demo rows only; not real soak evidence"
WriterFactory = Callable[[CryptoPairClickHouseSinkConfig], Any]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "DEV-ONLY: seed a small synthetic Track 2 crypto-pair event batch into "
            "ClickHouse so the Grafana paper-soak dashboard can be validated when "
            "real BTC/ETH/SOL 5m/15m markets are absent."
        )
    )
    parser.add_argument(
        "--clickhouse-host",
        default="localhost",
        help="ClickHouse host for demo-event writes (default: localhost).",
    )
    parser.add_argument(
        "--clickhouse-port",
        type=int,
        default=8123,
        help="ClickHouse HTTP port for demo-event writes (default: 8123).",
    )
    parser.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        help="ClickHouse user for demo-event writes (default: polytool_admin).",
    )
    parser.add_argument(
        "--clickhouse-password",
        default=None,
        help="ClickHouse password (falls back to CLICKHOUSE_PASSWORD env var).",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="Optional explicit synthetic run_id for repeatable cleanup.",
    )
    return parser


def resolve_clickhouse_password(
    *,
    explicit_password: Optional[str],
    environ: Mapping[str, str],
) -> str:
    if explicit_password is not None:
        return explicit_password.strip()
    return str(environ.get("CLICKHOUSE_PASSWORD", "")).strip()


def run_crypto_pair_seed_demo_events(
    *,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str,
    run_id: Optional[str] = None,
    started_at: Optional[datetime] = None,
    writer_factory: WriterFactory = build_clickhouse_sink,
) -> dict[str, Any]:
    if clickhouse_port <= 0:
        raise ValueError("clickhouse_port must be > 0")
    if not clickhouse_password:
        raise ValueError(
            "ClickHouse password is required. Pass --clickhouse-password PASSWORD, "
            "or export CLICKHOUSE_PASSWORD=<password>."
        )

    writer = writer_factory(
        CryptoPairClickHouseSinkConfig(
            enabled=True,
            clickhouse_host=clickhouse_host,
            clickhouse_port=clickhouse_port,
            clickhouse_user=clickhouse_user,
            clickhouse_password=clickhouse_password,
            soft_fail=False,
        )
    )
    seed_result = seed_demo_events(
        writer=writer,
        run_id=run_id,
        started_at=started_at,
    )
    return seed_result.to_dict()


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ch_password = resolve_clickhouse_password(
        explicit_password=args.clickhouse_password,
        environ=os.environ,
    )

    try:
        result = run_crypto_pair_seed_demo_events(
            clickhouse_host=args.clickhouse_host,
            clickhouse_port=args.clickhouse_port,
            clickhouse_user=args.clickhouse_user,
            clickhouse_password=ch_password,
            run_id=args.run_id,
        )
    except ValueError as exc:
        print(f"crypto-pair-seed-demo-events rejected startup: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"crypto-pair-seed-demo-events failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    write_result = result["write_result"]
    event_types = ",".join(str(item) for item in result["event_types"])
    print(f"{_CLI_PREFIX} dev_only      : true")
    print(f"{_CLI_PREFIX} note          : {_DEV_ONLY_NOTE}")
    print(f"{_CLI_PREFIX} source        : {DEMO_SEED_SOURCE}")
    print(f"{_CLI_PREFIX} run_id        : {result['run_id']}")
    print(f"{_CLI_PREFIX} event_count   : {result['event_count']}")
    print(f"{_CLI_PREFIX} event_types   : {event_types}")
    print(f"{_CLI_PREFIX} written_rows  : {write_result['written_rows']}")
    print(f"{_CLI_PREFIX} cleanup_sql   : {result['cleanup_sql']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
