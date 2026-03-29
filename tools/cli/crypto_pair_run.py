"""CLI entrypoint for the crypto-pair runtime shell."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

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
from packages.polymarket.crypto_pairs.reference_feed import (
    REFERENCE_FEED_PROVIDER_CHOICES,
    normalize_reference_feed_provider,
)
from packages.polymarket.crypto_pairs.reporting import (
    CryptoPairReportError,
    build_report_artifact_paths,
    generate_crypto_pair_paper_report,
    is_graceful_paper_stop_reason,
)
from packages.polymarket.simtrader.config_loader import ConfigLoadError, load_json_from_path


LIVE_CONFIRMATION_TEXT = "CONFIRM"
_CLI_PREFIX = "[crypto-pair-run]"


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
        default=None,
        help=(
            "Run duration seconds. Combines with --duration-minutes/--duration-hours. "
            "If all duration flags are omitted, default is 30 seconds. Values <= 0 still execute one cycle."
        ),
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=None,
        help="Additional run duration in minutes for paper-soak launches.",
    )
    parser.add_argument(
        "--duration-hours",
        type=int,
        default=None,
        help="Additional run duration in hours for paper-soak launches.",
    )
    parser.add_argument(
        "--cycle-interval-seconds",
        type=float,
        default=None,
        help="Override cycle interval seconds (default from config or 0.5).",
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
            "artifacts/tapes/crypto/paper_runs in paper mode, "
            "artifacts/crypto_pairs/live_runs in live mode."
        ),
    )
    parser.add_argument(
        "--kill-switch",
        default=str(DEFAULT_KILL_SWITCH_PATH),
        help="Kill-switch file checked every cycle.",
    )
    parser.add_argument(
        "--reference-feed-provider",
        choices=REFERENCE_FEED_PROVIDER_CHOICES,
        default=None,
        help=(
            "Reference price feed provider for paper mode. "
            "Default: binance. Use coinbase when Binance is unavailable or "
            "geo-restricted. auto opens both and prefers Binance when both are healthy."
        ),
    )
    parser.add_argument(
        "--heartbeat-seconds",
        type=int,
        default=None,
        help=(
            "Emit operator heartbeat/status output every N seconds. "
            "Combine with --heartbeat-minutes. Default: disabled."
        ),
    )
    parser.add_argument(
        "--heartbeat-minutes",
        type=int,
        default=None,
        help="Emit operator heartbeat/status output every N minutes. Default: disabled.",
    )
    parser.add_argument(
        "--auto-report",
        action="store_true",
        default=False,
        help=(
            "Paper mode only. On graceful exit, auto-run crypto-pair-report and print "
            "where paper_soak_summary artifacts landed."
        ),
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
    parser.add_argument(
        "--sink-streaming",
        action="store_true",
        default=False,
        help=(
            "Enable incremental per-event sink writes during the run loop instead of "
            "batching all events at finalization. Requires --sink-enabled. "
            "Allows Grafana visibility during long runs."
        ),
    )
    return parser


def load_config_payload(config_path: Optional[str]) -> dict[str, Any]:
    if config_path is None:
        return {}
    return load_json_from_path(config_path)


def resolve_duration_seconds(
    *,
    duration_seconds: Optional[int],
    duration_minutes: Optional[int],
    duration_hours: Optional[int],
) -> int:
    parts = [
        duration_seconds or 0,
        (duration_minutes or 0) * 60,
        (duration_hours or 0) * 3600,
    ]
    if duration_seconds is None and duration_minutes is None and duration_hours is None:
        return 30
    return sum(parts)


def resolve_heartbeat_interval_seconds(
    *,
    heartbeat_seconds: Optional[int],
    heartbeat_minutes: Optional[int],
) -> int:
    return (heartbeat_seconds or 0) + ((heartbeat_minutes or 0) * 60)


def format_heartbeat_status(payload: dict[str, Any]) -> str:
    latest_feed_states = payload.get("latest_feed_states") or {}
    if isinstance(latest_feed_states, dict) and latest_feed_states:
        feed_state_text = ",".join(
            f"{symbol}={state}"
            for symbol, state in sorted(latest_feed_states.items())
        )
    else:
        feed_state_text = "unseen"

    stale_symbols = payload.get("stale_symbols") or []
    if isinstance(stale_symbols, list) and stale_symbols:
        stale_text = ",".join(str(symbol) for symbol in stale_symbols)
    else:
        stale_text = "none"

    return (
        f"{_CLI_PREFIX} heartbeat     : "
        f"elapsed={payload.get('elapsed_runtime', '00:00:00')} "
        f"cycle={payload.get('cycle', 0)} "
        f"opportunities={payload.get('opportunities_observed', 0)} "
        f"intents={payload.get('intents_generated', 0)} "
        f"completed_pairs={payload.get('completed_pairs', 0)} "
        f"partial_exposure={payload.get('partial_exposure_count', 0)} "
        f"feed={feed_state_text} "
        f"stale={stale_text}"
    )


def persist_manifest_update(manifest: dict[str, Any]) -> None:
    manifest_path = Path(
        manifest.get("artifacts", {}).get("manifest_path")
        or Path(str(manifest["artifact_dir"])) / "run_manifest.json"
    )
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def run_crypto_pair_runner(
    *,
    live: bool = False,
    confirm: Optional[str] = None,
    config_path: Optional[str] = None,
    config_payload: Optional[dict[str, Any]] = None,
    duration_seconds: int = 30,
    cycle_interval_seconds: Optional[float] = None,
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
    heartbeat_interval_seconds: int = 0,
    heartbeat_callback: Optional[Callable[[dict[str, Any]], None]] = None,
    sink_enabled: bool = False,
    clickhouse_host: str = "localhost",
    clickhouse_port: int = 8123,
    clickhouse_user: str = "polytool_admin",
    clickhouse_password: str = "",
    sink_flush_mode: str = "batch",
    reference_feed_provider: Optional[str] = None,
    auto_report: bool = False,
    report_generator=generate_crypto_pair_paper_report,
) -> dict[str, Any]:
    if live and confirm != LIVE_CONFIRMATION_TEXT:
        raise ValueError(
            f'Live mode requires --confirm {LIVE_CONFIRMATION_TEXT} before startup.'
        )

    payload = dict(config_payload or {})
    if config_path is not None:
        payload.update(load_config_payload(config_path))

    # CLI-level sink_flush_mode overrides anything in the config file
    if sink_flush_mode != "batch":
        payload["sink_flush_mode"] = sink_flush_mode
    if reference_feed_provider is not None:
        payload["reference_feed_provider"] = reference_feed_provider

    selected_reference_feed_provider = normalize_reference_feed_provider(
        payload.get("reference_feed_provider", "binance")
    )
    payload["reference_feed_provider"] = selected_reference_feed_provider
    if live and selected_reference_feed_provider != "binance":
        raise ValueError(
            "reference_feed_provider only applies to paper mode in v1; "
            "live mode remains binance-only."
        )

    default_output = DEFAULT_LIVE_ARTIFACTS_DIR if live else DEFAULT_PAPER_ARTIFACTS_DIR
    settings = build_runner_settings(
        config_payload=payload,
        artifact_base_dir=output_base or default_output,
        kill_switch_path=kill_switch_path or Path(payload.get("kill_switch_path", DEFAULT_KILL_SWITCH_PATH)),
        duration_seconds=duration_seconds,
        symbol_filters=symbol_filters,
        duration_filters=duration_filters,
        cycle_limit=cycle_limit,
        heartbeat_interval_seconds=heartbeat_interval_seconds,
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
                "heartbeat_interval_seconds": settings.heartbeat_interval_seconds,
            },
            artifact_base_dir=settings.artifact_base_dir,
            kill_switch_path=settings.kill_switch_path,
            duration_seconds=settings.duration_seconds,
            symbol_filters=settings.symbol_filters,
            duration_filters=settings.duration_filters,
            cycle_limit=settings.cycle_limit,
            heartbeat_interval_seconds=settings.heartbeat_interval_seconds,
        )

    sink_config = CryptoPairClickHouseSinkConfig(
        enabled=sink_enabled,
        clickhouse_host=clickhouse_host,
        clickhouse_port=clickhouse_port,
        clickhouse_user=clickhouse_user,
        clickhouse_password=clickhouse_password,
    )
    sink = build_clickhouse_sink(sink_config)

    if live and execution_adapter is None:
        from packages.polymarket.crypto_pairs.clob_order_client import (
            ClobOrderClientConfig,
            ClobOrderClientConfigError,
            PolymarketClobOrderClient,
        )
        from packages.polymarket.crypto_pairs.live_execution import CryptoPairLiveExecutionAdapter
        from packages.polymarket.simtrader.execution.kill_switch import FileBasedKillSwitch

        try:
            clob_cfg = ClobOrderClientConfig.from_env()
            real_client = PolymarketClobOrderClient(clob_cfg)
        except ClobOrderClientConfigError as exc:
            raise ValueError(str(exc)) from exc
        execution_adapter = CryptoPairLiveExecutionAdapter(
            kill_switch=FileBasedKillSwitch(
                kill_switch_path or Path(payload.get("kill_switch_path", DEFAULT_KILL_SWITCH_PATH))
            ),
            order_client=real_client,
            live_enabled=True,
        )

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
            heartbeat_callback=heartbeat_callback,
        )
    manifest = runner.run()

    if auto_report and not live:
        auto_report_payload = {
            "enabled": True,
            "executed": False,
            "stopped_reason": manifest.get("stopped_reason"),
        }
        if is_graceful_paper_stop_reason(manifest.get("stopped_reason")):
            report_result = report_generator(Path(str(manifest["artifact_dir"])))
            auto_report_payload.update(
                {
                    "executed": True,
                    "decision": report_result.report.get("rubric", {}).get("decision"),
                    "verdict": report_result.report.get("rubric", {}).get("verdict"),
                    **build_report_artifact_paths(report_result),
                }
            )
        else:
            auto_report_payload["skipped_reason"] = "non_graceful_stop"
        manifest["auto_report"] = auto_report_payload
        persist_manifest_update(manifest)

    return manifest


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    duration_seconds = resolve_duration_seconds(
        duration_seconds=args.duration_seconds,
        duration_minutes=args.duration_minutes,
        duration_hours=args.duration_hours,
    )
    heartbeat_interval_seconds = resolve_heartbeat_interval_seconds(
        heartbeat_seconds=args.heartbeat_seconds,
        heartbeat_minutes=args.heartbeat_minutes,
    )

    ch_password = ""
    if args.sink_enabled:
        ch_password = os.environ.get("CLICKHOUSE_PASSWORD", "")
        if not ch_password:
            print(
                "Error: --sink-enabled requires the CLICKHOUSE_PASSWORD environment variable to be set.",
                file=sys.stderr,
            )
            return 1

    if args.sink_streaming and not args.sink_enabled:
        print(
            "Warning: --sink-streaming has no effect without --sink-enabled.",
            file=sys.stderr,
        )

    duration_parts = (
        ("--duration-seconds", args.duration_seconds),
        ("--duration-minutes", args.duration_minutes),
        ("--duration-hours", args.duration_hours),
    )
    for flag, value in duration_parts:
        if value is not None and value < 0:
            print(f"Error: {flag} must be >= 0.", file=sys.stderr)
            return 1
    heartbeat_parts = (
        ("--heartbeat-seconds", args.heartbeat_seconds),
        ("--heartbeat-minutes", args.heartbeat_minutes),
    )
    for flag, value in heartbeat_parts:
        if value is not None and value < 0:
            print(f"Error: {flag} must be >= 0.", file=sys.stderr)
            return 1

    if duration_seconds < 0:
        print("Error: total duration must be >= 0.", file=sys.stderr)
        return 1
    if heartbeat_interval_seconds < 0:
        print("Error: heartbeat interval must be >= 0.", file=sys.stderr)
        return 1
    if args.live and heartbeat_interval_seconds > 0:
        print(
            "Warning: paper heartbeat output is ignored in live mode.",
            file=sys.stderr,
        )
    if args.live and args.auto_report:
        print(
            "Warning: --auto-report is ignored in live mode.",
            file=sys.stderr,
        )

    heartbeat_callback = None if args.live else lambda payload: print(
        format_heartbeat_status(payload)
    )

    try:
        manifest = run_crypto_pair_runner(
            live=args.live,
            confirm=args.confirm,
            config_path=args.config,
            duration_seconds=duration_seconds,
            cycle_interval_seconds=args.cycle_interval_seconds,
            symbol_filters=tuple(args.symbol or ()),
            duration_filters=tuple(args.market_duration or ()),
            output_base=Path(args.output) if args.output else None,
            kill_switch_path=Path(args.kill_switch),
            heartbeat_interval_seconds=heartbeat_interval_seconds,
            heartbeat_callback=heartbeat_callback,
            sink_enabled=args.sink_enabled,
            clickhouse_host=args.clickhouse_host,
            clickhouse_port=args.clickhouse_port,
            clickhouse_user=args.clickhouse_user,
            clickhouse_password=ch_password,
            sink_flush_mode="streaming" if args.sink_streaming else "batch",
            reference_feed_provider=args.reference_feed_provider,
            auto_report=args.auto_report and not args.live,
        )
    except ConfigLoadError as exc:
        print(f"crypto-pair-run rejected startup: {exc}", file=sys.stderr)
        return 1
    except CryptoPairReportError as exc:
        print(
            f"crypto-pair-run completed but auto-report failed: {exc}",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"crypto-pair-run rejected startup: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(
            f"crypto-pair-run failed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    mode_label = "live" if args.live else "paper"
    print(f"{_CLI_PREFIX} mode          : {mode_label}")
    print(f"{_CLI_PREFIX} run_id        : {manifest['run_id']}")
    print(f"{_CLI_PREFIX} stopped_reason: {manifest['stopped_reason']}")
    print(f"{_CLI_PREFIX} artifact_dir  : {manifest['artifact_dir']}")
    print(
        f"{_CLI_PREFIX} manifest_path : "
        f"{manifest.get('artifacts', {}).get('manifest_path', 'unknown')}"
    )
    print(
        f"{_CLI_PREFIX} run_summary   : "
        f"{manifest.get('artifacts', {}).get('run_summary_path', 'unknown')}"
    )
    auto_report = manifest.get("auto_report")
    if isinstance(auto_report, dict) and auto_report.get("enabled"):
        if auto_report.get("executed"):
            print(f"{_CLI_PREFIX} report_json   : {auto_report.get('summary_json')}")
            print(
                f"{_CLI_PREFIX} report_md     : "
                f"{auto_report.get('summary_markdown')}"
            )
            print(
                f"{_CLI_PREFIX} report_verdict: "
                f"{auto_report.get('verdict', 'unknown')}"
            )
        else:
            print(
                f"{_CLI_PREFIX} auto_report   : skipped "
                f"({auto_report.get('skipped_reason', 'unknown')})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
