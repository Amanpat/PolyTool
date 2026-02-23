#!/usr/bin/env python3
"""SimTrader CLI: record Market Channel WS tapes, replay them, and run scripted trades.

Commands
--------
  python -m polytool simtrader record --asset-id <TOKEN_ID> [--duration 60]
  python -m polytool simtrader replay --tape <PATH/events.jsonl> [--format csv]
  python -m polytool simtrader trade  --tape <PATH/events.jsonl> --buy --limit 0.42 --size 100 --at-seq 5
  python -m polytool simtrader run    --tape <PATH/events.jsonl> --strategy copy_wallet_replay \\
                                       --strategy-config '{"trades_path":"trades.jsonl"}'
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
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

_STRATEGY_REGISTRY: dict[str, str] = {
    "copy_wallet_replay": (
        "packages.polymarket.simtrader.strategies.copy_wallet_replay.CopyWalletReplay"
    ),
    "binary_complement_arb": (
        "packages.polymarket.simtrader.strategies.binary_complement_arb.BinaryComplementArb"
    ),
}


def _run(args: argparse.Namespace) -> int:
    """Run a strategy against a tape and emit all artifacts."""
    from packages.polymarket.simtrader.broker.latency import LatencyConfig
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner
    from packages.polymarket.simtrader.portfolio.mark import MARK_BID

    # -- Validate tape ---------------------------------------------------------
    events_path = Path(args.tape)
    if not events_path.exists():
        print(f"Error: tape file not found: {events_path}", file=sys.stderr)
        return 1

    # -- Strategy config -------------------------------------------------------
    strategy_config: dict[str, Any] = {}
    if args.strategy_config:
        try:
            strategy_config = json.loads(args.strategy_config)
        except json.JSONDecodeError as exc:
            print(f"Error: --strategy-config is not valid JSON: {exc}", file=sys.stderr)
            return 1

    # -- Instantiate strategy --------------------------------------------------
    strategy_name: str = args.strategy
    if strategy_name not in _STRATEGY_REGISTRY:
        known = ", ".join(sorted(_STRATEGY_REGISTRY))
        print(
            f"Error: unknown strategy {strategy_name!r}.  Known: {known}",
            file=sys.stderr,
        )
        return 1

    module_path, class_name = _STRATEGY_REGISTRY[strategy_name].rsplit(".", 1)
    try:
        import importlib
        mod = importlib.import_module(module_path)
        strategy_cls = getattr(mod, class_name)
    except (ImportError, AttributeError) as exc:
        print(f"Error: could not load strategy {strategy_name!r}: {exc}", file=sys.stderr)
        return 1

    try:
        strategy = strategy_cls(**strategy_config)
    except TypeError as exc:
        print(
            f"Error: invalid strategy config for {strategy_name!r}: {exc}", file=sys.stderr
        )
        return 1

    # -- Portfolio config ------------------------------------------------------
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

    latency = LatencyConfig(submit_ticks=args.latency_ticks)

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
        f"[simtrader run] latency-ticks  : {latency.submit_ticks}",
        file=sys.stderr,
    )

    # Some strategies (e.g. binary_complement_arb) declare extra asset books
    # via a special key in their strategy_config.  Extract it here so the
    # runner can maintain per-asset L2Books and fill filters.
    extra_book_asset_ids: list[str] = []
    if isinstance(strategy_config.get("extra_book_asset_ids"), list):
        extra_book_asset_ids = [str(x) for x in strategy_config["extra_book_asset_ids"]]
    elif hasattr(strategy, "_no_id"):
        # BinaryComplementArb: automatically include the NO asset
        extra_book_asset_ids = [strategy._no_id]  # type: ignore[union-attr]

    runner = StrategyRunner(
        events_path=events_path,
        run_dir=run_dir,
        strategy=strategy,
        asset_id=args.asset_id or None,
        extra_book_asset_ids=extra_book_asset_ids or None,
        latency=latency,
        starting_cash=starting_cash,
        fee_rate_bps=fee_rate_bps,
        mark_method=mark_method,
        strict=args.strict,
    )

    try:
        pnl_summary = runner.run()
    except Exception as exc:  # noqa: BLE001
        print(f"Error during strategy run: {exc}", file=sys.stderr)
        return 1

    print(f"\nStrategy run complete: {run_dir}")
    print(f"  decisions    : decisions.jsonl")
    print(f"  summary      : summary.json  (net_profit={pnl_summary['net_profit']})")
    print(f"  manifest     : run_manifest.json")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
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
            f"Available: {', '.join(sorted(_STRATEGY_REGISTRY))}."
        ),
    )
    run_p.add_argument(
        "--strategy-config",
        default="{}",
        metavar="JSON",
        dest="strategy_config",
        help=(
            "JSON object passed as keyword arguments to the strategy constructor.  "
            "Example: '{\"trades_path\": \"trades.jsonl\", \"signal_delay_ticks\": 2}'"
        ),
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
        "--strict",
        action="store_true",
        default=False,
        help="Fail on L2BookError or malformed events instead of warning and skipping.",
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
    if args.subcommand == "replay":
        return _replay(args)
    if args.subcommand == "trade":
        return _trade(args)
    if args.subcommand == "run":
        return _run(args)

    parser.print_help()
    return 1
