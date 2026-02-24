#!/usr/bin/env python3
"""SimTrader CLI: record Market Channel WS tapes, replay them, and run scripted trades.

Commands
--------
  python -m polytool simtrader record --asset-id <TOKEN_ID> [--asset-id <TOKEN_ID>] [--duration 60]
  python -m polytool simtrader replay --tape <PATH/events.jsonl> [--format csv]
  python -m polytool simtrader tape-info --tape <PATH/events.jsonl>
  python -m polytool simtrader trade  --tape <PATH/events.jsonl> --buy --limit 0.42 --size 100 --at-seq 5
  python -m polytool simtrader run    --tape <PATH/events.jsonl> --strategy copy_wallet_replay \\
                                       --strategy-config '{"trades_path":"trades.jsonl"}'
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")
DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------


def _record(args: argparse.Namespace) -> int:
    try:
        from packages.polymarket.simtrader.tape.recorder import TapeRecorder
    except ImportError as exc:
        print(f"Error: could not import SimTrader recorder: {exc}", file=sys.stderr)
        return 1

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    first_id_prefix = args.asset_ids[0][:8] if args.asset_ids else "unknown"

    if args.output_dir:
        tape_dir = Path(args.output_dir)
    else:
        tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / f"{ts}_{first_id_prefix}"

    print(f"[simtrader record] tape dir : {tape_dir}", file=sys.stderr)
    print(f"[simtrader record] asset IDs: {args.asset_ids}", file=sys.stderr)
    if args.duration:
        print(f"[simtrader record] duration : {args.duration}s", file=sys.stderr)
    else:
        print("[simtrader record] duration : until Ctrl-C", file=sys.stderr)

    recorder = TapeRecorder(
        tape_dir=tape_dir,
        asset_ids=args.asset_ids,
        strict=args.strict,
    )

    try:
        recorder.record(
            duration_seconds=args.duration,
            ws_url=args.ws_url,
        )
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    raw_path = tape_dir / "raw_ws.jsonl"
    events_path = tape_dir / "events.jsonl"
    print("\nTape written:")
    print(f"  raw WS frames  : {raw_path}")
    print(f"  normalized     : {events_path}")
    return 0


def _summarize_tape(events_path: Path) -> dict[str, Any]:
    """Return a compact JSON-serializable summary for one events.jsonl tape."""
    asset_ids_seen: set[str] = set()
    snapshot_by_asset: dict[str, bool] = {}
    event_type_counts: dict[str, int] = defaultdict(int)
    warnings: list[str] = []
    first_seq: int | None = None
    last_seq: int | None = None
    total_lines = 0
    parsed_events = 0
    malformed_lines = 0

    with open(events_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            total_lines += 1
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                malformed_lines += 1
                warnings.append(f"malformed line {lineno}: {exc}")
                continue

            if not isinstance(event, dict):
                malformed_lines += 1
                warnings.append(
                    f"line {lineno}: expected JSON object, got {type(event).__name__}"
                )
                continue

            parsed_events += 1

            seq = event.get("seq")
            if isinstance(seq, int):
                first_seq = seq if first_seq is None else min(first_seq, seq)
                last_seq = seq if last_seq is None else max(last_seq, seq)

            asset_id = event.get("asset_id")
            if isinstance(asset_id, str) and asset_id:
                asset_ids_seen.add(asset_id)
                snapshot_by_asset.setdefault(asset_id, False)

            event_type = event.get("event_type")
            if not isinstance(event_type, str) or not event_type:
                event_type = "<missing>"
            event_type_counts[event_type] += 1

            if (
                event_type == "book"
                and isinstance(asset_id, str)
                and asset_id
            ):
                snapshot_by_asset[asset_id] = True

    asset_ids = sorted(asset_ids_seen)
    snapshot_map = {
        asset_id: bool(snapshot_by_asset.get(asset_id, False))
        for asset_id in asset_ids
    }
    counts = {
        event_type: event_type_counts[event_type]
        for event_type in sorted(event_type_counts)
    }

    return {
        "tape_path": str(events_path),
        "total_lines": total_lines,
        "parsed_events": parsed_events,
        "malformed_lines": malformed_lines,
        "asset_ids": asset_ids,
        "event_type_counts": counts,
        "first_seq": first_seq,
        "last_seq": last_seq,
        "snapshot_by_asset": snapshot_map,
        "warnings": warnings[:50],
    }


def _tape_info(args: argparse.Namespace) -> int:
    events_path = Path(args.tape)
    if not events_path.exists():
        print(f"Error: tape file not found: {events_path}", file=sys.stderr)
        return 1

    summary = _summarize_tape(events_path)
    payload = json.dumps(summary, indent=2) + "\n"

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(payload, encoding="utf-8")
        print(f"Tape summary written: {out_path}")
        return 0

    print(payload, end="")
    return 0


def _replay(args: argparse.Namespace) -> int:
    try:
        from packages.polymarket.simtrader.replay.runner import ReplayRunner
    except ImportError as exc:
        print(f"Error: could not import SimTrader runner: {exc}", file=sys.stderr)
        return 1

    events_path = Path(args.tape)
    if not events_path.exists():
        print(f"Error: tape file not found: {events_path}", file=sys.stderr)
        return 1

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DEFAULT_ARTIFACTS_DIR / "runs" / run_id

    print(f"[simtrader replay] tape    : {events_path}", file=sys.stderr)
    print(f"[simtrader replay] run dir : {run_dir}", file=sys.stderr)
    print(f"[simtrader replay] format  : {args.format}", file=sys.stderr)
    print(f"[simtrader replay] strict  : {args.strict}", file=sys.stderr)

    runner = ReplayRunner(
        events_path=events_path,
        run_dir=run_dir,
        strict=args.strict,
        output_format=args.format,
    )

    try:
        out_path = runner.run()
    except Exception as exc:  # noqa: BLE001
        print(f"Error during replay: {exc}", file=sys.stderr)
        return 1

    print(f"Replay complete: {out_path}")
    return 0


def _trade(args: argparse.Namespace) -> int:
    """Run a single scripted order against a tape and emit broker artifacts."""
    from packages.polymarket.simtrader.broker.latency import LatencyConfig
    from packages.polymarket.simtrader.broker.rules import Side
    from packages.polymarket.simtrader.broker.sim_broker import SimBroker
    from packages.polymarket.simtrader.orderbook.l2book import L2Book
    from packages.polymarket.simtrader.portfolio.ledger import PortfolioLedger
    from packages.polymarket.simtrader.portfolio.mark import MARK_BID

    # -- Validate inputs -------------------------------------------------------
    events_path = Path(args.tape)
    if not events_path.exists():
        print(f"Error: tape file not found: {events_path}", file=sys.stderr)
        return 1

    try:
        limit_price = Decimal(str(args.limit))
        size = Decimal(str(args.size))
    except InvalidOperation as exc:
        print(f"Error: invalid limit or size: {exc}", file=sys.stderr)
        return 1

    if limit_price <= 0 or size <= 0:
        print("Error: --limit and --size must be positive.", file=sys.stderr)
        return 1

    try:
        starting_cash = Decimal(str(args.starting_cash))
    except InvalidOperation as exc:
        print(f"Error: invalid --starting-cash: {exc}", file=sys.stderr)
        return 1
    if starting_cash < 0:
        print("Error: --starting-cash must be non-negative.", file=sys.stderr)
        return 1

    fee_rate_bps: Decimal | None = None
    if args.fee_rate_bps is not None:
        try:
            fee_rate_bps = Decimal(str(args.fee_rate_bps))
        except InvalidOperation as exc:
            print(f"Error: invalid --fee-rate-bps: {exc}", file=sys.stderr)
            return 1

    mark_method: str = args.mark_method

    side = Side.BUY if args.buy else Side.SELL
    at_seq: int = args.at_seq
    cancel_at_seq: int | None = args.cancel_at_seq

    latency = LatencyConfig(
        submit_ticks=args.latency_ticks,
        cancel_ticks=args.cancel_latency_ticks,
    )

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DEFAULT_ARTIFACTS_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"[simtrader trade] tape          : {events_path}", file=sys.stderr)
    print(f"[simtrader trade] run dir       : {run_dir}", file=sys.stderr)
    print(f"[simtrader trade] side          : {side}", file=sys.stderr)
    print(f"[simtrader trade] limit         : {limit_price}", file=sys.stderr)
    print(f"[simtrader trade] size          : {size}", file=sys.stderr)
    print(f"[simtrader trade] at-seq        : {at_seq}", file=sys.stderr)
    if cancel_at_seq is not None:
        print(f"[simtrader trade] cancel        : {cancel_at_seq}", file=sys.stderr)
    print(
        f"[simtrader trade] latency       : submit={latency.submit_ticks} cancel={latency.cancel_ticks}",
        file=sys.stderr,
    )
    print(f"[simtrader trade] starting-cash : {starting_cash}", file=sys.stderr)
    print(
        f"[simtrader trade] fee-rate-bps  : {fee_rate_bps if fee_rate_bps is not None else 'default (200)'}",
        file=sys.stderr,
    )
    print(f"[simtrader trade] mark-method   : {mark_method}", file=sys.stderr)

    # -- Load and sort events --------------------------------------------------
    events: list[dict] = []
    warnings: list[str] = []
    with open(events_path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                warnings.append(f"Skipping malformed line {lineno}: {exc}")
    events.sort(key=lambda e: e.get("seq", 0))

    if not events:
        print("Error: tape contains no events.", file=sys.stderr)
        return 1

    # Detect asset_id ---------------------------------------------------------
    asset_id = args.asset_id
    if asset_id is None:
        ids = {e.get("asset_id", "") for e in events if e.get("asset_id")}
        if len(ids) == 1:
            asset_id = next(iter(ids))
        elif len(ids) > 1:
            print(
                f"Error: tape has multiple asset_ids {sorted(ids)}. "
                "Specify one with --asset-id.",
                file=sys.stderr,
            )
            return 1
        else:
            print("Error: tape has no asset_id fields.", file=sys.stderr)
            return 1

    # -- Set up book + broker --------------------------------------------------
    book = L2Book(asset_id, strict=False)
    broker = SimBroker(latency=latency)
    order_id: str | None = None
    cancel_submitted = False

    # -- Replay loop -----------------------------------------------------------
    timeline: list[dict] = []
    from packages.polymarket.simtrader.tape.schema import (
        EVENT_TYPE_BOOK,
        EVENT_TYPE_PRICE_CHANGE,
    )

    for event in events:
        seq: int = event.get("seq", 0)
        ts_recv: float = event.get("ts_recv", 0.0)
        evt_asset = event.get("asset_id", "")

        # Apply to book (per-asset)
        if evt_asset == asset_id:
            book.apply(event)

        # Submit order once we reach at_seq
        if order_id is None and seq >= at_seq:
            order_id = broker.submit_order(
                asset_id=asset_id,
                side=side,
                limit_price=limit_price,
                size=size,
                submit_seq=seq,
                submit_ts=ts_recv,
            )
            print(
                f"[simtrader trade] order submitted: id={order_id} seq={seq}",
                file=sys.stderr,
            )

        # Submit cancel once we reach cancel_at_seq (after order is known)
        if (
            order_id is not None
            and not cancel_submitted
            and cancel_at_seq is not None
            and seq >= cancel_at_seq
        ):
            broker.cancel_order(order_id, cancel_seq=seq, cancel_ts=ts_recv)
            cancel_submitted = True
            print(
                f"[simtrader trade] cancel submitted: id={order_id} seq={seq}",
                file=sys.stderr,
            )

        # Step broker (after book update, after any submit/cancel above)
        if evt_asset == asset_id:
            broker.step(event, book)

        # Emit best_bid_ask row on book-affecting events
        event_type = event.get("event_type", "")
        if evt_asset == asset_id and event_type in (
            EVENT_TYPE_BOOK,
            EVENT_TYPE_PRICE_CHANGE,
        ):
            timeline.append(
                {
                    "seq": seq,
                    "ts_recv": ts_recv,
                    "asset_id": asset_id,
                    "event_type": event_type,
                    "best_bid": book.best_bid,
                    "best_ask": book.best_ask,
                }
            )

    # -- Portfolio ledger ------------------------------------------------------
    ledger = PortfolioLedger(
        starting_cash=starting_cash,
        fee_rate_bps=fee_rate_bps,
        mark_method=mark_method,
    )
    ledger_events, equity_curve = ledger.process(broker.order_events, timeline)

    # Final book state for summary mark price
    final_best_bid: float | None = timeline[-1].get("best_bid") if timeline else None
    final_best_ask: float | None = timeline[-1].get("best_ask") if timeline else None
    pnl_summary = ledger.summary(run_id, final_best_bid, final_best_ask)

    # -- Write artifacts -------------------------------------------------------
    # best_bid_ask.jsonl
    bba_path = run_dir / "best_bid_ask.jsonl"
    with open(bba_path, "w", encoding="utf-8") as fh:
        for row in timeline:
            fh.write(json.dumps(row) + "\n")

    # orders.jsonl
    orders_path = run_dir / "orders.jsonl"
    with open(orders_path, "w", encoding="utf-8") as fh:
        for evt in broker.order_events:
            fh.write(json.dumps(evt) + "\n")

    # fills.jsonl
    fills_path = run_dir / "fills.jsonl"
    with open(fills_path, "w", encoding="utf-8") as fh:
        for fill in broker.fills:
            fh.write(json.dumps(fill.to_dict()) + "\n")

    # ledger.jsonl (new)
    ledger_path = run_dir / "ledger.jsonl"
    with open(ledger_path, "w", encoding="utf-8") as fh:
        for evt in ledger_events:
            fh.write(json.dumps(evt) + "\n")

    # equity_curve.jsonl (new)
    equity_curve_path = run_dir / "equity_curve.jsonl"
    with open(equity_curve_path, "w", encoding="utf-8") as fh:
        for row in equity_curve:
            fh.write(json.dumps(row) + "\n")

    # summary.json (new)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps(pnl_summary, indent=2) + "\n", encoding="utf-8")

    # run_manifest.json
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "command": "simtrader trade",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tape_path": str(events_path),
        "latency_config": {
            "submit_ticks": latency.submit_ticks,
            "cancel_ticks": latency.cancel_ticks,
        },
        "orders_spec": [
            {
                "order_id": order_id,
                "asset_id": asset_id,
                "side": side,
                "limit_price": str(limit_price),
                "size": str(size),
                "at_seq": at_seq,
                "cancel_at_seq": cancel_at_seq,
            }
        ],
        "portfolio_config": {
            "starting_cash": str(starting_cash),
            "fee_rate_bps": str(fee_rate_bps) if fee_rate_bps is not None else "default(200)",
            "mark_method": mark_method,
        },
        "fills_count": len(broker.fills),
        "timeline_rows": len(timeline),
        "net_profit": pnl_summary["net_profit"],
        "run_quality": "ok" if not warnings else "warnings",
        "warnings": warnings[:50],
    }
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # meta.json (consistent with replay runner format)
    meta: dict[str, Any] = {
        "run_quality": manifest["run_quality"],
        "events_path": str(events_path),
        "total_events": len(events),
        "timeline_rows": len(timeline),
        "warnings": warnings[:50],
    }
    meta_path = run_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # -- Summary ---------------------------------------------------------------
    total_filled = sum(Decimal(f.to_dict()["fill_size"]) for f in broker.fills)
    print(f"\nTrade run complete: {run_dir}")
    print(f"  orders       : {orders_path.name}  ({len(broker.order_events)} events)")
    print(f"  fills        : {fills_path.name}  ({len(broker.fills)} fills, total size {total_filled})")
    print(f"  ledger       : {ledger_path.name}  ({len(ledger_events)} snapshots)")
    print(f"  equity_curve : {equity_curve_path.name}  ({len(equity_curve)} rows)")
    print(f"  summary      : {summary_path.name}  (net_profit={pnl_summary['net_profit']})")
    print(f"  manifest     : {manifest_path.name}")
    if warnings:
        print(f"  warnings     : {len(warnings)}", file=sys.stderr)

    return 0


# ---------------------------------------------------------------------------
# Strategy runner sub-command
# ---------------------------------------------------------------------------


def _parse_json_object_arg(raw: Any, *, flag_name: str) -> dict[str, Any]:
    """Parse one JSON-object argument without double-parsing."""
    if isinstance(raw, dict):
        return raw

    if isinstance(raw, str):
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{flag_name} is not valid JSON: {exc}") from exc
    else:
        payload = raw

    if not isinstance(payload, dict):
        raise ValueError(f"{flag_name} must be a JSON object")
    return payload


def _load_strategy_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    from packages.polymarket.simtrader.config_loader import (
        ConfigLoadError,
        load_json_from_path,
        load_json_from_string,
    )

    raw_config = getattr(args, "strategy_config", None)
    raw_path = getattr(args, "strategy_config_path", None)

    if raw_config is not None and raw_path is not None:
        raise ValueError(
            "Provide only one of --strategy-config or --strategy-config-path."
        )

    if raw_path is not None:
        cfg_path = Path(str(raw_path))
        if not cfg_path.exists():
            raise ValueError(f"--strategy-config-path file not found: {cfg_path}")
        try:
            return load_json_from_path(cfg_path)
        except ConfigLoadError as exc:
            raise ValueError(str(exc)) from exc

    if raw_config is None:
        return {}

    try:
        return load_json_from_string(raw_config)
    except ConfigLoadError as exc:
        raise ValueError(str(exc)) from exc


def _parse_starting_cash_arg(raw: Any) -> Decimal:
    try:
        starting_cash = Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"invalid --starting-cash: {exc}") from exc
    if starting_cash < 0:
        raise ValueError("--starting-cash must be non-negative.")
    return starting_cash


def _parse_fee_rate_bps_arg(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    try:
        fee_rate_bps = Decimal(str(raw))
    except InvalidOperation as exc:
        raise ValueError(f"invalid --fee-rate-bps: {exc}") from exc
    if fee_rate_bps < 0:
        raise ValueError("--fee-rate-bps must be non-negative.")
    return fee_rate_bps


def _run(args: argparse.Namespace) -> int:
    """Run a strategy against a tape and emit all artifacts."""
    from packages.polymarket.simtrader.strategy.facade import (
        StrategyRunConfigError,
        StrategyRunParams,
        run_strategy,
    )

    events_path = Path(args.tape)
    if not events_path.exists():
        print(f"Error: tape file not found: {events_path}", file=sys.stderr)
        return 1

    try:
        strategy_config = _load_strategy_config_from_args(args)
        starting_cash = _parse_starting_cash_arg(args.starting_cash)
        fee_rate_bps = _parse_fee_rate_bps_arg(args.fee_rate_bps)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    strategy_name: str = args.strategy
    mark_method: str = args.mark_method

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DEFAULT_ARTIFACTS_DIR / "runs" / run_id

    print(f"[simtrader run] tape           : {events_path}", file=sys.stderr)
    print(f"[simtrader run] run dir        : {run_dir}", file=sys.stderr)
    print(f"[simtrader run] strategy       : {strategy_name}", file=sys.stderr)
    print(f"[simtrader run] strategy-config: {strategy_config}", file=sys.stderr)
    print(f"[simtrader run] starting-cash  : {starting_cash}", file=sys.stderr)
    print(
        f"[simtrader run] fee-rate-bps   : "
        f"{fee_rate_bps if fee_rate_bps is not None else 'default (200)'}",
        file=sys.stderr,
    )
    print(f"[simtrader run] mark-method    : {mark_method}", file=sys.stderr)
    print(
        f"[simtrader run] latency-ticks  : "
        f"submit={args.latency_ticks} cancel={args.cancel_latency_ticks}",
        file=sys.stderr,
    )
    print(f"[simtrader run] allow-degraded : {args.allow_degraded}", file=sys.stderr)

    try:
        run_result = run_strategy(
            StrategyRunParams(
                events_path=events_path,
                run_dir=run_dir,
                strategy_name=strategy_name,
                strategy_config=strategy_config,
                asset_id=args.asset_id or None,
                starting_cash=starting_cash,
                fee_rate_bps=fee_rate_bps,
                mark_method=mark_method,
                latency_submit_ticks=args.latency_ticks,
                latency_cancel_ticks=args.cancel_latency_ticks,
                strict=args.strict,
                allow_degraded=args.allow_degraded,
            )
        )
    except StrategyRunConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error during strategy run: {exc}", file=sys.stderr)
        return 1

    print(f"\nStrategy run complete: {run_dir}")
    print(f"  decisions    : decisions.jsonl")
    print(
        f"  summary      : summary.json  "
        f"(net_profit={run_result.metrics['net_profit']})"
    )
    print(f"  manifest     : run_manifest.json")
    return 0


def _sweep(args: argparse.Namespace) -> int:
    """Run one strategy sweep with scenario-level parameter overrides."""
    from packages.polymarket.simtrader.sweeps.runner import (
        SweepConfigError,
        SweepRunParams,
        parse_sweep_config_json,
        run_sweep,
    )

    events_path = Path(args.tape)
    if not events_path.exists():
        print(f"Error: tape file not found: {events_path}", file=sys.stderr)
        return 1

    try:
        strategy_config = _parse_json_object_arg(
            args.strategy_config, flag_name="--strategy-config"
        )
        sweep_config = parse_sweep_config_json(args.sweep_config)
        starting_cash = _parse_starting_cash_arg(args.starting_cash)
        fee_rate_bps = _parse_fee_rate_bps_arg(args.fee_rate_bps)
    except (ValueError, SweepConfigError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"[simtrader sweep] tape           : {events_path}", file=sys.stderr)
    print(f"[simtrader sweep] strategy       : {args.strategy}", file=sys.stderr)
    print(f"[simtrader sweep] strategy-config: {strategy_config}", file=sys.stderr)
    print(f"[simtrader sweep] sweep-config   : {sweep_config}", file=sys.stderr)
    print(f"[simtrader sweep] starting-cash  : {starting_cash}", file=sys.stderr)
    print(
        f"[simtrader sweep] fee-rate-bps   : "
        f"{fee_rate_bps if fee_rate_bps is not None else 'default (200)'}",
        file=sys.stderr,
    )
    print(f"[simtrader sweep] mark-method    : {args.mark_method}", file=sys.stderr)
    print(
        f"[simtrader sweep] latency-ticks  : "
        f"submit={args.latency_ticks} cancel={args.cancel_latency_ticks}",
        file=sys.stderr,
    )

    try:
        sweep_result = run_sweep(
            SweepRunParams(
                events_path=events_path,
                strategy_name=args.strategy,
                strategy_config=strategy_config,
                asset_id=args.asset_id or None,
                starting_cash=starting_cash,
                fee_rate_bps=fee_rate_bps,
                mark_method=args.mark_method,
                latency_submit_ticks=args.latency_ticks,
                latency_cancel_ticks=args.cancel_latency_ticks,
                strict=args.strict,
                sweep_id=args.sweep_id or None,
                artifacts_root=DEFAULT_ARTIFACTS_DIR,
            ),
            sweep_config=sweep_config,
        )
    except SweepConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error during sweep run: {exc}", file=sys.stderr)
        return 1

    summary = sweep_result.summary
    aggregate = summary.get("aggregate", {})

    print(f"\nSweep complete: {sweep_result.sweep_dir}")
    print(f"  manifest     : sweep_manifest.json")
    print(f"  summary      : sweep_summary.json")
    print(f"  scenarios    : {len(summary.get('scenarios', []))}")
    print(
        f"  best/median/worst net_profit: "
        f"{aggregate.get('best_net_profit')} / "
        f"{aggregate.get('median_net_profit')} / "
        f"{aggregate.get('worst_net_profit')}"
    )
    return 0


# ---------------------------------------------------------------------------
# Quick sweep preset
# ---------------------------------------------------------------------------

#: Named parameter presets for quickrun --sweep.
_QUICK_SWEEP_FEE_RATES = [0, 50, 100, 200]
_QUICK_SWEEP_CANCEL_TICKS = [0, 2, 5]
_QUICK_SWEEP_MARK_METHODS = ["bid", "midpoint"]


def _build_quick_sweep_config() -> dict:
    """Return a sweep config dict for the 'quick' evidence-run preset.

    Matrix: 4 fee_rates × 3 cancel_latency_ticks × 2 mark_methods = 24 scenarios.
    Each scenario overrides fee_rate_bps, cancel_latency_ticks, and mark_method.
    """
    import itertools

    scenarios = []
    for fee, cancel, mark in itertools.product(
        _QUICK_SWEEP_FEE_RATES,
        _QUICK_SWEEP_CANCEL_TICKS,
        _QUICK_SWEEP_MARK_METHODS,
    ):
        scenarios.append(
            {
                "name": f"fee{fee}_cancel{cancel}_{mark}",
                "overrides": {
                    "fee_rate_bps": fee,
                    "cancel_latency_ticks": cancel,
                    "mark_method": mark,
                },
            }
        )
    return {"scenarios": scenarios}


_SWEEP_PRESETS: dict[str, Any] = {
    "quick": _build_quick_sweep_config,
}


# ---------------------------------------------------------------------------
# QuickRun sub-command
# ---------------------------------------------------------------------------


def _quickrun(args: argparse.Namespace) -> int:
    """Record a binary market tape and immediately run binary_complement_arb."""
    from packages.polymarket.clob import ClobClient
    from packages.polymarket.gamma import GammaClient
    from packages.polymarket.simtrader.config_loader import (
        ConfigLoadError,
        load_strategy_config,
    )
    from packages.polymarket.simtrader.market_picker import (
        MarketPicker,
        MarketPickerError,
    )
    from packages.polymarket.simtrader.strategy.facade import (
        StrategyRunConfigError,
        StrategyRunParams,
        run_strategy,
    )
    from packages.polymarket.simtrader.tape.recorder import TapeRecorder

    # Validate --max-candidates bounds
    if not (1 <= args.max_candidates <= 100):
        print(
            f"Error: --max-candidates must be between 1 and 100 "
            f"(got {args.max_candidates}).",
            file=sys.stderr,
        )
        return 1
    if args.min_events < 0:
        print(
            f"Error: --min-events must be non-negative (got {args.min_events}).",
            file=sys.stderr,
        )
        return 1

    min_depth_size: float = getattr(args, "min_depth_size", 0.0) or 0.0
    top_n_levels: int = getattr(args, "top_n_levels", 3) or 3

    # -- Resolve market --------------------------------------------------------
    picker = MarketPicker(GammaClient(), ClobClient())

    yes_val: Any = None  # BookValidation for quickrun_context
    no_val: Any = None

    try:
        if args.market:
            resolved = picker.resolve_slug(args.market)
            yes_val = picker.validate_book(
                resolved.yes_token_id,
                allow_empty=args.allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
            )
            no_val = picker.validate_book(
                resolved.no_token_id,
                allow_empty=args.allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
            )
            if not yes_val.valid or not no_val.valid:
                bad_side = "YES" if not yes_val.valid else "NO"
                bad_reason = (yes_val if not yes_val.valid else no_val).reason
                print(
                    f"Error: {bad_side} orderbook not usable for {args.market!r}: "
                    f"{bad_reason}",
                    file=sys.stderr,
                )
                return 1
        else:
            skip_log: list[dict] = []
            resolved = picker.auto_pick(
                max_candidates=args.max_candidates,
                allow_empty_book=args.allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
                collect_skips=skip_log if args.dry_run else None,
            )
            if args.dry_run and skip_log:
                print("Skipped candidates:", file=sys.stderr)
                for entry in skip_log:
                    side_info = f" ({entry['side']})" if entry.get("side") else ""
                    depth_info = (
                        f" depth={entry['depth_total']:.1f}"
                        if entry.get("depth_total") is not None
                        else ""
                    )
                    print(
                        f"  {entry['slug']}{side_info}: {entry['reason']}{depth_info}",
                        file=sys.stderr,
                    )
    except MarketPickerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    yes_id = resolved.yes_token_id
    no_id = resolved.no_token_id

    print(f"[quickrun] market   : {resolved.slug}")
    print(f"[quickrun] question : {resolved.question}")
    print(f"[quickrun] YES      : {yes_id}  ({resolved.yes_label})")
    print(f"[quickrun] NO       : {no_id}  ({resolved.no_label})")

    # -- Dry run early exit ----------------------------------------------------
    if args.dry_run:
        print("dry_run=True : exiting.")
        return 0

    # -- Build auditability context (persisted to tape meta + run manifest) ----
    quickrun_context: dict[str, Any] = {
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "selected_slug": resolved.slug,
        "yes_token_id": yes_id,
        "no_token_id": no_id,
        "selection_mode": "explicit" if args.market else "auto_pick",
        "max_candidates": args.max_candidates,
        "allow_empty_book": args.allow_empty_book,
        "yes_book_validation": (
            {"reason": yes_val.reason, "valid": yes_val.valid}
            if yes_val is not None
            else {"reason": "ok", "valid": True}
        ),
        "no_book_validation": (
            {"reason": no_val.reason, "valid": no_val.valid}
            if no_val is not None
            else {"reason": "ok", "valid": True}
        ),
        "yes_no_mapping": {
            "yes_label": resolved.yes_label,
            "no_label": resolved.no_label,
            "mapping_tier": getattr(resolved, "mapping_tier", "explicit"),
        },
    }

    # -- Load user strategy config overrides -----------------------------------
    cfg_path = getattr(args, "strategy_config_path", None)
    cfg_json = getattr(args, "strategy_config_json", None)
    try:
        user_overrides = load_strategy_config(
            config_path=cfg_path,
            config_json=cfg_json,
        )
    except ConfigLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # -- Build default strategy config, merge user overrides ------------------
    strategy_config: dict[str, Any] = {
        "yes_asset_id": yes_id,
        "no_asset_id": no_id,
        "buffer": 0.01,
        "max_size": 50,
        "legging_policy": "wait_N_then_unwind",
        "unwind_wait_ticks": 5,
        "enable_merge_full_set": True,
    }
    strategy_config.update(user_overrides)

    # -- Build tape directory --------------------------------------------------
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / f"{ts}_quickrun_{yes_id[:8]}"
    tape_id = tape_dir.name

    print(f"[quickrun] tape dir : {tape_dir}", file=sys.stderr)
    print(f"[quickrun] duration : {args.duration}s", file=sys.stderr)

    # -- Record ----------------------------------------------------------------
    recorder = TapeRecorder(
        tape_dir=tape_dir,
        asset_ids=[yes_id, no_id],
        strict=False,
    )
    try:
        recorder.record(duration_seconds=args.duration)
    except ImportError as exc:
        print(f"Error recording tape: {exc}", file=sys.stderr)
        return 1

    events_path = tape_dir / "events.jsonl"
    if not events_path.exists():
        print(f"Error: events.jsonl not written to {tape_dir}", file=sys.stderr)
        return 1

    # -- Annotate tape meta with quickrun context ------------------------------
    tape_meta_path = tape_dir / "meta.json"
    if tape_meta_path.exists():
        try:
            tape_meta = json.loads(tape_meta_path.read_text(encoding="utf-8"))
            tape_meta["quickrun_context"] = quickrun_context
            tape_meta_path.write_text(
                json.dumps(tape_meta, indent=2) + "\n", encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    # -- Tape stats ------------------------------------------------------------
    tape_summary = _summarize_tape(events_path)
    parsed_events = tape_summary["parsed_events"]
    snapshot_map = tape_summary.get("snapshot_by_asset", {})
    yes_snapshot = snapshot_map.get(yes_id, False)
    no_snapshot = snapshot_map.get(no_id, False)
    if args.min_events > 0 and parsed_events < args.min_events:
        print(
            f"[quickrun] warning: tape has {parsed_events} parsed events "
            f"(< --min-events {args.min_events}).",
            file=sys.stderr,
        )
        print(
            "[quickrun] warning: rerun with a longer --duration for better tape quality.",
            file=sys.stderr,
        )

    # -- Parse run params ------------------------------------------------------
    try:
        starting_cash = _parse_starting_cash_arg(args.starting_cash)
        fee_rate_bps = _parse_fee_rate_bps_arg(args.fee_rate_bps)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    sweep_preset: str | None = getattr(args, "sweep", None)

    # ------------------------------------------------------------------
    # Sweep mode: --sweep quick (or preset:<name>)
    # ------------------------------------------------------------------
    if sweep_preset is not None:
        from packages.polymarket.simtrader.sweeps.runner import (
            SweepConfigError,
            SweepRunParams,
            run_sweep,
        )

        # Resolve preset name (support both "quick" and "preset:quick")
        preset_key = sweep_preset.removeprefix("preset:")
        if preset_key not in _SWEEP_PRESETS:
            known = ", ".join(f"'{k}'" for k in _SWEEP_PRESETS)
            print(
                f"Error: unknown --sweep preset {sweep_preset!r}. Known: {known}",
                file=sys.stderr,
            )
            return 1

        sweep_config = _SWEEP_PRESETS[preset_key]()  # call the factory
        sweep_id = f"quickrun_{ts}_{yes_id[:8]}"
        sweep_dir = DEFAULT_ARTIFACTS_DIR / "sweeps" / sweep_id

        print(f"[quickrun sweep] preset  : {preset_key}", file=sys.stderr)
        print(
            f"[quickrun sweep] scenarios: {len(sweep_config['scenarios'])}",
            file=sys.stderr,
        )
        print(f"[quickrun sweep] sweep dir: {sweep_dir}", file=sys.stderr)

        try:
            sweep_result = run_sweep(
                SweepRunParams(
                    events_path=events_path,
                    strategy_name="binary_complement_arb",
                    strategy_config=strategy_config,
                    asset_id=yes_id,
                    starting_cash=starting_cash,
                    # fee_rate_bps and mark_method are overridden per scenario
                    fee_rate_bps=None,
                    mark_method="bid",
                    latency_submit_ticks=0,
                    latency_cancel_ticks=0,
                    strict=False,
                    sweep_id=sweep_id,
                    artifacts_root=DEFAULT_ARTIFACTS_DIR,
                ),
                sweep_config=sweep_config,
            )
        except SweepConfigError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"Error during sweep: {exc}", file=sys.stderr)
            return 1

        # Annotate sweep manifest with quickrun context
        sweep_manifest_path = sweep_result.sweep_dir / "sweep_manifest.json"
        if sweep_manifest_path.exists():
            try:
                sm = json.loads(sweep_manifest_path.read_text(encoding="utf-8"))
                sm["quickrun_context"] = quickrun_context
                sweep_manifest_path.write_text(
                    json.dumps(sm, indent=2) + "\n", encoding="utf-8"
                )
            except Exception:  # noqa: BLE001
                pass

        aggregate = sweep_result.summary.get("aggregate", {})
        scenario_count = len(sweep_result.summary.get("scenarios", []))

        print()
        print(f"QuickSweep complete  (preset: {preset_key}, {scenario_count} scenarios)")
        print(f"  Market    : {resolved.slug}")
        print(
            f"  Tape stats: {parsed_events} parsed events  "
            f"(YES snapshot={yes_snapshot}  NO snapshot={no_snapshot})"
        )
        print(f"  Sweep dir : artifacts/simtrader/sweeps/{sweep_id}/")
        print(f"  Tape dir  : artifacts/simtrader/tapes/{tape_id}/")
        print()
        print("  LEADERBOARD (net_profit):")
        print(
            f"    Best   : {aggregate.get('best_net_profit')}  "
            f"({aggregate.get('best_scenario')})"
        )
        print(
            f"    Median : {aggregate.get('median_net_profit')}  "
            f"({aggregate.get('median_scenario')})"
        )
        print(
            f"    Worst  : {aggregate.get('worst_net_profit')}  "
            f"({aggregate.get('worst_scenario')})"
        )
        print()
        print("Reproduce:")
        reproduce = (
            f"  python -m polytool simtrader quickrun "
            f"--market {resolved.slug} "
            f"--duration {args.duration} "
            f"--sweep {sweep_preset}"
        )
        if args.starting_cash != 1000.0:
            reproduce += f" --starting-cash {args.starting_cash}"
        if args.allow_empty_book:
            reproduce += " --allow-empty-book"
        if cfg_path is not None:
            reproduce += f" --strategy-config-path {cfg_path}"
        print(reproduce)
        return 0

    # ------------------------------------------------------------------
    # Single-run mode (original behaviour)
    # ------------------------------------------------------------------
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DEFAULT_ARTIFACTS_DIR / "runs" / run_id

    # -- Run strategy ----------------------------------------------------------
    try:
        run_result = run_strategy(
            StrategyRunParams(
                events_path=events_path,
                run_dir=run_dir,
                strategy_name="binary_complement_arb",
                strategy_config=strategy_config,
                asset_id=yes_id,
                starting_cash=starting_cash,
                fee_rate_bps=fee_rate_bps,
                mark_method=args.mark_method,
                latency_submit_ticks=0,
                latency_cancel_ticks=args.cancel_latency_ticks,
                strict=False,
                allow_degraded=False,
            )
        )
    except StrategyRunConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error during strategy run: {exc}", file=sys.stderr)
        return 1

    # -- Summary ---------------------------------------------------------------
    manifest_path = run_dir / "run_manifest.json"
    decisions_count = 0
    orders_count = 0
    fills_count = 0
    run_quality = "ok"
    if manifest_path.exists():
        try:
            mf = json.loads(manifest_path.read_text(encoding="utf-8"))
            decisions_count = mf.get("decisions_count", 0)
            fills_count = mf.get("fills_count", 0)
            run_quality = mf.get("run_quality", "ok")
        except Exception:  # noqa: BLE001
            pass

    # Count orders from orders.jsonl (run_manifest has no orders_count key)
    orders_jsonl_path = run_dir / "orders.jsonl"
    if orders_jsonl_path.exists():
        try:
            orders_count = sum(
                1
                for line in orders_jsonl_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        except Exception:  # noqa: BLE001
            pass

    # Annotate run manifest with quickrun context
    if manifest_path.exists():
        try:
            run_manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            run_manifest_data["quickrun_context"] = quickrun_context
            manifest_path.write_text(
                json.dumps(run_manifest_data, indent=2) + "\n", encoding="utf-8"
            )
        except Exception:  # noqa: BLE001
            pass

    net_profit = run_result.metrics.get("net_profit", "0")

    print()
    print("QuickRun complete")
    print(f"  Market     : {resolved.slug}")
    print(f"  YES token  : {yes_id}")
    print(f"  NO token   : {no_id}")
    print(
        f"  Tape stats : {parsed_events} parsed events  "
        f"(YES snapshot={yes_snapshot}  NO snapshot={no_snapshot})"
    )
    print(
        f"  Decisions  : {decisions_count}   "
        f"Orders: {orders_count}   "
        f"Fills: {fills_count}"
    )
    print(f"  Net profit : {net_profit}")
    print(f"  Run quality: {run_quality}")
    print(f"  Tape dir   : artifacts/simtrader/tapes/{tape_id}/")
    print(f"  Run dir    : artifacts/simtrader/runs/{run_id}/")
    print()
    print("Reproduce:")
    reproduce = (
        f"  python -m polytool simtrader quickrun "
        f"--market {resolved.slug} "
        f"--duration {args.duration}"
    )
    if args.starting_cash != 1000.0:
        reproduce += f" --starting-cash {args.starting_cash}"
    if args.fee_rate_bps is not None:
        reproduce += f" --fee-rate-bps {args.fee_rate_bps}"
    if args.mark_method != "bid":
        reproduce += f" --mark-method {args.mark_method}"
    if args.cancel_latency_ticks != 0:
        reproduce += f" --cancel-latency-ticks {args.cancel_latency_ticks}"
    if args.allow_empty_book:
        reproduce += " --allow-empty-book"
    if cfg_path is not None:
        reproduce += f" --strategy-config-path {cfg_path}"
    print(reproduce)

    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    from packages.polymarket.simtrader.strategy.facade import known_strategies

    strategy_names = known_strategies()

    parser = argparse.ArgumentParser(
        prog="polytool simtrader",
        description=(
            "SimTrader: record Polymarket Market Channel WS tapes, "
            "replay them deterministically, and run scripted broker trades."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: WARNING).",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # ------------------------------------------------------------------
    # record
    # ------------------------------------------------------------------
    rec = sub.add_parser(
        "record",
        help="Connect to the Polymarket Market Channel and record a tape.",
    )
    rec.add_argument(
        "--asset-id",
        dest="asset_ids",
        metavar="ASSET_ID",
        action="append",
        required=True,
        help=(
            "Token / asset ID to subscribe to.  "
            "Repeat the flag to record multiple assets in one session."
        ),
    )
    rec.add_argument(
        "--duration",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Stop after this many seconds (default: run until Ctrl-C).",
    )
    rec.add_argument(
        "--output-dir",
        default=None,
        metavar="PATH",
        help=(
            "Override tape output directory "
            "(default: artifacts/simtrader/tapes/<timestamp>_<asset_prefix>/)."
        ),
    )
    rec.add_argument(
        "--ws-url",
        default=DEFAULT_WS_URL,
        help=f"WebSocket endpoint URL (default: {DEFAULT_WS_URL}).",
    )
    rec.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail on unexpected message shapes instead of warning and skipping.",
    )

    # ------------------------------------------------------------------
    # tape-info
    # ------------------------------------------------------------------
    tape_info = sub.add_parser(
        "tape-info",
        help="Inspect a tape and print JSON summary (assets, event counts, seq range).",
    )
    tape_info.add_argument(
        "--tape",
        required=True,
        metavar="PATH",
        help="Path to the events.jsonl tape file.",
    )
    tape_info.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Optional path to write the JSON summary (prints to stdout if omitted).",
    )

    # ------------------------------------------------------------------
    # replay
    # ------------------------------------------------------------------
    rep = sub.add_parser(
        "replay",
        help="Replay a tape's events.jsonl and produce a best_bid_ask timeline.",
    )
    rep.add_argument(
        "--tape",
        required=True,
        metavar="PATH",
        help="Path to the events.jsonl tape file.",
    )
    rep.add_argument(
        "--run-id",
        default=None,
        metavar="ID",
        help=(
            "Run identifier used for the output directory name "
            "(default: UTC timestamp)."
        ),
    )
    rep.add_argument(
        "--format",
        choices=["jsonl", "csv"],
        default="jsonl",
        help="Output format for the best_bid_ask timeline (default: jsonl).",
    )
    rep.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail on missing book snapshot or invalid events.",
    )

    # ------------------------------------------------------------------
    # trade
    # ------------------------------------------------------------------
    trd = sub.add_parser(
        "trade",
        help=(
            "Run a scripted order against a tape and emit "
            "orders.jsonl + fills.jsonl + run_manifest.json."
        ),
    )
    trd.add_argument(
        "--tape",
        required=True,
        metavar="PATH",
        help="Path to the events.jsonl tape file.",
    )
    side_group = trd.add_mutually_exclusive_group(required=True)
    side_group.add_argument(
        "--buy",
        action="store_true",
        help="Submit a BUY (taker) order.",
    )
    side_group.add_argument(
        "--sell",
        action="store_true",
        help="Submit a SELL (taker) order.",
    )
    trd.add_argument(
        "--limit",
        type=float,
        required=True,
        metavar="PRICE",
        help=(
            "Limit price.  For --buy: fill at any ask <= PRICE.  "
            "For --sell: fill at any bid >= PRICE."
        ),
    )
    trd.add_argument(
        "--size",
        type=float,
        required=True,
        metavar="SIZE",
        help="Order size (shares / contracts).",
    )
    trd.add_argument(
        "--at-seq",
        type=int,
        required=True,
        metavar="SEQ",
        dest="at_seq",
        help="Tape seq at which to submit the order (or first seq >= SEQ).",
    )
    trd.add_argument(
        "--cancel-at-seq",
        type=int,
        default=None,
        metavar="SEQ",
        dest="cancel_at_seq",
        help="Tape seq at which to submit a cancel (optional).",
    )
    trd.add_argument(
        "--latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="latency_ticks",
        help=(
            "Events that must elapse after order submission before it becomes "
            "active (default: 0 = instant)."
        ),
    )
    trd.add_argument(
        "--cancel-latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="cancel_latency_ticks",
        help=(
            "Events that must elapse after cancel request before it takes "
            "effect (default: 0 = instant)."
        ),
    )
    trd.add_argument(
        "--asset-id",
        default=None,
        metavar="ASSET_ID",
        help="Asset / token ID (auto-detected if tape has exactly one asset).",
    )
    trd.add_argument(
        "--run-id",
        default=None,
        metavar="ID",
        help="Run identifier for the output directory (default: UTC timestamp).",
    )
    trd.add_argument(
        "--starting-cash",
        type=float,
        default=1000.0,
        metavar="USDC",
        dest="starting_cash",
        help=(
            "Starting USDC cash balance for the portfolio ledger "
            "(default: 1000).  Must be non-negative."
        ),
    )
    trd.add_argument(
        "--fee-rate-bps",
        type=float,
        default=None,
        metavar="BPS",
        dest="fee_rate_bps",
        help=(
            "Taker fee rate in basis points applied to each fill "
            "(default: conservative 200 bps).  "
            "Pass 0 to disable fees."
        ),
    )
    trd.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default="bid",
        dest="mark_method",
        help=(
            "Mark-price method for unrealized PnL computation: "
            "'bid' (default, conservative — marks longs at best_bid) or "
            "'midpoint' (marks at (best_bid + best_ask) / 2).  "
            "Recorded in summary.json and run_manifest.json."
        ),
    )

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------
    run_p = sub.add_parser(
        "run",
        help=(
            "Run a strategy against a tape and emit all artifacts "
            "(best_bid_ask, orders, fills, ledger, equity_curve, summary, decisions)."
        ),
    )
    run_p.add_argument(
        "--tape",
        required=True,
        metavar="PATH",
        help="Path to the events.jsonl tape file.",
    )
    run_p.add_argument(
        "--strategy",
        required=True,
        metavar="NAME",
        help=(
            "Strategy name to use.  "
            f"Available: {', '.join(strategy_names)}."
        ),
    )
    run_p.add_argument(
        "--strategy-config",
        default=None,
        type=str,
        metavar="JSON",
        dest="strategy_config",
        help=(
            "JSON object passed as keyword arguments to the strategy constructor.  "
            "Example: '{\"trades_path\": \"trades.jsonl\", \"signal_delay_ticks\": 2}'."
        ),
    )
    run_p.add_argument(
        "--strategy-config-path",
        default=None,
        metavar="PATH",
        dest="strategy_config_path",
        help="Path to a JSON file containing the strategy config object.",
    )
    run_p.add_argument(
        "--asset-id",
        default=None,
        metavar="ASSET_ID",
        dest="asset_id",
        help="Asset / token ID (auto-detected if tape has exactly one asset).",
    )
    run_p.add_argument(
        "--run-id",
        default=None,
        metavar="ID",
        dest="run_id",
        help="Run identifier for the output directory (default: UTC timestamp).",
    )
    run_p.add_argument(
        "--starting-cash",
        type=float,
        default=1000.0,
        metavar="USDC",
        dest="starting_cash",
        help="Starting USDC cash balance (default: 1000).",
    )
    run_p.add_argument(
        "--fee-rate-bps",
        type=float,
        default=None,
        metavar="BPS",
        dest="fee_rate_bps",
        help="Taker fee rate in basis points (default: conservative 200 bps).",
    )
    run_p.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default="bid",
        dest="mark_method",
        help="Mark-price method for unrealized PnL: 'bid' (default) or 'midpoint'.",
    )
    run_p.add_argument(
        "--latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="latency_ticks",
        help="Events that elapse after order submission before it becomes active (default: 0).",
    )
    run_p.add_argument(
        "--cancel-latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="cancel_latency_ticks",
        help=(
            "Events that elapse after cancel submission before cancellation takes "
            "effect (default: 0)."
        ),
    )
    run_p.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail on L2BookError or malformed events instead of warning and skipping.",
    )
    run_p.add_argument(
        "--allow-degraded",
        action="store_true",
        default=False,
        dest="allow_degraded",
        help=(
            "Allow runs to continue when strategy-specific tape coverage checks fail. "
            "The run is marked degraded instead of invalid."
        ),
    )

    # ------------------------------------------------------------------
    # sweep
    # ------------------------------------------------------------------
    sweep_p = sub.add_parser(
        "sweep",
        help=(
            "Run multiple strategy scenarios over the same tape and emit "
            "sweep-level robustness summary artifacts."
        ),
    )
    sweep_p.add_argument(
        "--tape",
        required=True,
        metavar="PATH",
        help="Path to the events.jsonl tape file.",
    )
    sweep_p.add_argument(
        "--strategy",
        required=True,
        metavar="NAME",
        help=(
            "Strategy name to use.  "
            f"Available: {', '.join(strategy_names)}."
        ),
    )
    sweep_p.add_argument(
        "--strategy-config",
        default="{}",
        metavar="JSON",
        dest="strategy_config",
        help=(
            "Base strategy config JSON object used by all scenarios "
            "(scenario overrides are patch-merged onto this)."
        ),
    )
    sweep_p.add_argument(
        "--sweep-config",
        required=True,
        metavar="JSON",
        dest="sweep_config",
        help=(
            "Sweep scenario JSON object with a non-empty 'scenarios' list. "
            "Each scenario may set overrides for fee_rate_bps, mark_method, "
            "latency knobs, and strategy_config."
        ),
    )
    sweep_p.add_argument(
        "--asset-id",
        default=None,
        metavar="ASSET_ID",
        dest="asset_id",
        help="Primary asset / token ID (auto-detected if tape has exactly one asset).",
    )
    sweep_p.add_argument(
        "--sweep-id",
        default=None,
        metavar="ID",
        dest="sweep_id",
        help=(
            "Optional explicit sweep ID. If omitted, a deterministic ID is "
            "derived from tape + base args + sweep config."
        ),
    )
    sweep_p.add_argument(
        "--starting-cash",
        type=float,
        default=1000.0,
        metavar="USDC",
        dest="starting_cash",
        help="Starting USDC cash balance (default: 1000).",
    )
    sweep_p.add_argument(
        "--fee-rate-bps",
        type=float,
        default=None,
        metavar="BPS",
        dest="fee_rate_bps",
        help="Base taker fee rate in basis points (default: conservative 200 bps).",
    )
    sweep_p.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default="bid",
        dest="mark_method",
        help="Base mark-price method for unrealized PnL: 'bid' or 'midpoint'.",
    )
    sweep_p.add_argument(
        "--latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="latency_ticks",
        help="Base submit latency in tape ticks (default: 0).",
    )
    sweep_p.add_argument(
        "--cancel-latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="cancel_latency_ticks",
        help="Base cancel latency in tape ticks (default: 0).",
    )
    sweep_p.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Fail on L2BookError or malformed events instead of warning and skipping.",
    )

    # ------------------------------------------------------------------
    # quickrun
    # ------------------------------------------------------------------
    qr = sub.add_parser(
        "quickrun",
        help=(
            "Auto-pick a live binary market (or resolve --market SLUG), "
            "record a tape, and immediately run binary_complement_arb. "
            "Use --dry-run to check market selection without recording."
        ),
    )
    qr.add_argument(
        "--market",
        default=None,
        metavar="SLUG",
        help=(
            "Polymarket market slug to use.  "
            "If omitted, auto-selects the first valid live binary market."
        ),
    )
    qr.add_argument(
        "--duration",
        type=float,
        default=30.0,
        metavar="SECONDS",
        help="Recording duration in seconds (default: 30).",
    )
    qr.add_argument(
        "--min-events",
        type=int,
        default=0,
        metavar="N",
        dest="min_events",
        help=(
            "Warn when the recorded tape has fewer than N parsed events. "
            "Use 0 to disable (default: 0)."
        ),
    )
    qr.add_argument(
        "--starting-cash",
        type=float,
        default=1000.0,
        metavar="USDC",
        dest="starting_cash",
        help="Starting USDC cash balance (default: 1000).",
    )
    qr.add_argument(
        "--fee-rate-bps",
        type=float,
        default=None,
        metavar="BPS",
        dest="fee_rate_bps",
        help="Taker fee rate in basis points (default: conservative 200 bps).",
    )
    qr.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default="bid",
        dest="mark_method",
        help="Mark-price method for unrealized PnL: 'bid' (default) or 'midpoint'.",
    )
    qr.add_argument(
        "--cancel-latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="cancel_latency_ticks",
        help="Cancel latency in tape ticks (default: 0).",
    )
    qr.add_argument(
        "--allow-empty-book",
        action="store_true",
        default=False,
        dest="allow_empty_book",
        help="Accept markets whose orderbooks are empty (bids=[], asks=[]).",
    )
    qr.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Resolve and validate the market, then exit without recording.",
    )
    qr.add_argument(
        "--strategy-config-path",
        default=None,
        metavar="PATH",
        dest="strategy_config_path",
        help="Path to a JSON file with strategy config overrides (accepts UTF-8 BOM).",
    )
    qr.add_argument(
        "--strategy-config-json",
        default=None,
        metavar="JSON",
        dest="strategy_config_json",
        help="Inline JSON string with strategy config overrides.",
    )
    qr.add_argument(
        "--max-candidates",
        type=int,
        default=20,
        metavar="N",
        dest="max_candidates",
        help=(
            "Number of active markets to examine when auto-picking "
            "(default: 20).  Ignored if --market is specified."
        ),
    )
    qr.add_argument(
        "--min-depth-size",
        type=float,
        default=0.0,
        metavar="SIZE",
        dest="min_depth_size",
        help=(
            "Minimum total size (sum of top --top-n-levels bid + ask levels) "
            "required for a book to be considered liquid.  "
            "0 disables the depth filter (default: 0)."
        ),
    )
    qr.add_argument(
        "--top-n-levels",
        type=int,
        default=3,
        metavar="N",
        dest="top_n_levels",
        help=(
            "Number of price levels per side to include in the depth sum "
            "used by --min-depth-size (default: 3)."
        ),
    )
    qr.add_argument(
        "--sweep",
        default=None,
        metavar="PRESET",
        dest="sweep",
        help=(
            "Run a parameter sweep instead of a single strategy run.  "
            "Use 'quick' for the built-in evidence-run preset "
            "(4 fee_rates × 3 cancel_ticks × 2 mark_methods = 24 scenarios).  "
            "Also accepts 'preset:quick' for future-proof usage."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str]) -> int:
    """CLI entry point.  Returns exit code (0 = success)."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.subcommand == "record":
        return _record(args)
    if args.subcommand == "tape-info":
        return _tape_info(args)
    if args.subcommand == "replay":
        return _replay(args)
    if args.subcommand == "trade":
        return _trade(args)
    if args.subcommand == "run":
        return _run(args)
    if args.subcommand == "sweep":
        return _sweep(args)
    if args.subcommand == "quickrun":
        return _quickrun(args)

    parser.print_help()
    return 1
