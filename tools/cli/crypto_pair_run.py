"""CLI entrypoint for the crypto-pair runtime shell."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Optional

from packages.polymarket.crypto_pairs.clickhouse_sink import (
    CryptoPairClickHouseSinkConfig,
    build_clickhouse_sink,
)
from packages.polymarket.crypto_pairs.live_runner import (
    DEFAULT_LIVE_ARTIFACTS_DIR,
    CryptoPairLiveRunner,
)
from packages.polymarket.crypto_pairs.paper_runner import (
    DEFAULT_KILL_SWITCH_PATH,
    DEFAULT_PAPER_ARTIFACTS_DIR,
    CryptoPairPaperRunner,
    build_runner_settings,
)
from packages.polymarket.simtrader.config_loader import ConfigLoadError, load_json_from_path


LIVE_CONFIRMATION_TEXT = "CONFIRM"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the crypto-pair runtime shell. Paper mode is the default. "
            "Use --live and --confirm CONFIRM to enter the live scaffold. "
            "Live scaffold safety: kill switch checked every cycle, "
            "post-only/limit-only only, disconnect cancels working orders, "
            "and no production client wiring is required in v0."
        )
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to a JSON config file for runner settings and paper_config.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=int,
        default=30,
        help="How long to run the shell. Values <= 0 still execute one cycle.",
    )
    parser.add_argument(
        "--cycle-interval-seconds",
        type=int,
        default=None,
        help="Override cycle interval seconds (default from config or 5).",
    )
    parser.add_argument(
        "--symbol",
        action="append",
        default=None,
        choices=["BTC", "ETH", "SOL"],
        help="Restrict runtime consideration to one symbol. Repeat to allow multiple.",
    )
    parser.add_argument(
        "--market-duration",
        action="append",
        default=None,
        type=int,
        choices=[5, 15],
        help="Restrict runtime consideration to one market duration in minutes.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Base artifact directory. Default: "
            "artifacts/crypto_pairs/paper_runs in paper mode, "
            "artifacts/crypto_pairs/live_runs in live mode."
        ),
    )
    parser.add_argument(
        "--kill-switch",
        default=str(DEFAULT_KILL_SWITCH_PATH),
        help="Kill-switch file checked every cycle.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help=(
            "Enter the live scaffold. This does not activate a production "
            "client by itself, but it does enforce live safety gates."
        ),
    )
    parser.add_argument(
        "--confirm",
        default=None,
        help='Required with --live. Must be the exact string "CONFIRM".',
    )
    parser.add_argument(
        "--sink-enabled",
        action="store_true",
        default=False,
        help="Enable the ClickHouse Track 2 event sink (opt-in). Requires CLICKHOUSE_PASSWORD env var.",
    )
    parser.add_argument(
        "--clickhouse-host",
        default="localhost",
        help="ClickHouse host for the event sink (default: localhost).",
    )
    parser.add_argument(
        "--clickhouse-port",
        type=int,
        default=8123,
        help="ClickHouse HTTP port for the event sink (default: 8123).",
    )
    parser.add_argument(
        "--clickhouse-user",
        default="polytool_admin",
        help="ClickHouse user for the event sink (default: polytool_admin).",
    )
    return parser


def load_config_payload(config_path: Optional[str]) -> dict[str, Any]:
    if config_path is None:
        return {}
    return load_json_from_path(config_path)


def run_crypto_pair_runner(
    *,
    live: bool = False,
    confirm: Optional[str] = None,
    config_path: Optional[str] = None,
    config_payload: Optional[dict[str, Any]] = None,
    duration_seconds: int = 30,
    cycle_interval_seconds: Optional[int] = None,
    symbol_filters: Optional[tuple[str, ...]] = None,
    duration_filters: Optional[tuple[int, ...]] = None,
    output_base: Optional[Path] = None,
    kill_switch_path: Optional[Path] = None,
    gamma_client: Any = None,
    clob_client: Any = None,
    reference_feed: Any = None,
    execution_adapter: Any = None,
    store: Any = None,
    cycle_limit: Optional[int] = None,
    sink_enabled: bool = False,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "",
) -> dict[str, Any]:
    if live and confirm != LIVE_CONFIRMATION_TEXT:
        raise ValueError(
            f'Live mode requires --confirm {LIVE_CONFIRMATION_TEXT} before startup.'
        )

    payload = dict(config_payload or {})
    if config_path is not None:
        payload.update(load_config_payload(config_path))

    default_output = DEFAULT_LIVE_ARTIFACTS_DIR if live else DEFAULT_PAPER_ARTIFACTS_DIR
    settings = build_runner_settings(
        config_payload=payload,
        artifact_base_dir=output_base or default_output,
        kill_switch_path=kill_switch_path or Path(payload.get("kill_switch_path", DEFAULT_KILL_SWITCH_PATH)),
        duration_seconds=duration_seconds,
        symbol_filters=symbol_filters,
        duration_filters=duration_filters,
        cycle_limit=cycle_limit,
    )
    if cycle_interval_seconds is not None:
        settings = build_runner_settings(
            config_payload={
                **payload,
                "paper_config": settings.paper_config.to_dict(),
                "cycle_interval_seconds": cycle_interval_seconds,
                "max_open_pairs": settings.max_open_pairs,
                "daily_loss_cap_usdc": str(settings.daily_loss_cap_usdc),
                "min_profit_threshold_usdc": str(settings.min_profit_threshold_usdc),
            },
            artifact_base_dir=settings.artifact_base_dir,
            kill_switch_path=settings.kill_switch_path,
            duration_seconds=settings.duration_seconds,
            symbol_filters=settings.symbol_filters,
            duration_filters=settings.duration_filters,
            cycle_limit=settings.cycle_limit,
        )

    sink_config = CryptoPairClickHouseSinkConfig(
        enabled=sink_enabled,
        clickhouse_host=clickhouse_host,
        clickhouse_port=clickhouse_port,
        clickhouse_user=clickhouse_user,
        clickhouse_password=clickhouse_password,
    )
    sink = build_clickhouse_sink(sink_config)

    if live:
        runner = CryptoPairLiveRunner(
            settings,
            execution_adapter=execution_adapter,
            gamma_client=gamma_client,
            clob_client=clob_client,
            reference_feed=reference_feed,
            store=store,
        )
    else:
        runner = CryptoPairPaperRunner(
            settings,
            gamma_client=gamma_client,
            clob_client=clob_client,
            reference_feed=reference_feed,
            store=store,
            execution_adapter=execution_adapter,
            sink=sink,
        )
    return runner.run()


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    ch_password = ""
    if args.sink_enabled:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "")
        if not ch_password:
            print(
                "Error: --sink-enabled requires the CLICKHOUSE_PASSWORD environment variable to be set.",
                file=sys.stderr,
            )
            return 1

    if args.duration_seconds < 0:
        print("Error: --duration-seconds must be >= 0.", file=sys.stderr)
        return 1

    try:
        manifest = run_crypto_pair_runner(
            live=args.live,
            confirm=args.confirm,
            config_path=args.config,
            duration_seconds=args.duration_seconds,
            cycle_interval_seconds=args.cycle_interval_seconds,
            symbol_filters=tuple(args.symbol or ()),
            duration_filters=tuple(args.market_duration or ()),
            output_base=Path(args.output) if args.output else None,
            kill_switch_path=Path(args.kill_switch),
            sink_enabled=args.sink_enabled,
            clickhouse_host=args.clickhouse_host,
            clickhouse_port=args.clickhouse_port,
            clickhouse_user=args.clickhouse_user,
            clickhouse_password=ch_password,
        )
    except (ConfigLoadError, ValueError) as exc:
        print(f"crypto-pair-run rejected startup: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"crypto-pair-run failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    mode_label = "live" if args.live else "paper"
    print(f"[crypto-pair-run] mode          : {mode_label}")
    print(f"[crypto-pair-run] run_id        : {manifest['run_id']}")
    print(f"[crypto-pair-run] stopped_reason: {manifest['stopped_reason']}")
    print(f"[crypto-pair-run] artifact_dir  : {manifest['artifact_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
