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
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from packages.polymarket.simtrader.strategy_presets import (
    STRATEGY_PRESET_CHOICES,
    build_binary_complement_strategy_config,
    normalize_strategy_preset,
)

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACTS_DIR = Path("artifacts/simtrader")
DEFAULT_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
DEFAULT_BATCH_NUM_MARKETS = 5
DEFAULT_BATCH_DURATION_SECONDS = 300.0
DEFAULT_BATCH_SMALL_NUM_MARKETS = 3
DEFAULT_BATCH_SMALL_DURATION_SECONDS = 300.0
_BROWSE_TYPE_DIRS: dict[str, str] = {
    "sweep": "sweeps",
    "batch": "batches",
    "run": "runs",
    "shadow": "shadow_runs",
}
_BROWSE_TS_RE = re.compile(r"(20\d{6}T\d{6}Z)")


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


def _as_nonempty_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text if text else None


def _infer_binary_arb_ids_from_tape_meta(events_path: Path) -> tuple[str, str]:
    meta_path = events_path.parent / "meta.json"
    guidance = (
        "Pass IDs via --strategy-config / --strategy-config-path, "
        "or use --yes-asset-id and --no-asset-id."
    )
    if not meta_path.exists():
        raise ValueError(
            "binary_complement_arb requires yes/no asset IDs. "
            f"Could not infer from tape meta because {meta_path} is missing. {guidance}"
        )

    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(
            "binary_complement_arb requires yes/no asset IDs. "
            f"Could not parse tape meta file {meta_path}: {exc}. {guidance}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "binary_complement_arb requires yes/no asset IDs. "
            f"Expected JSON object in {meta_path}. {guidance}"
        )

    for context_key in ("quickrun_context", "shadow_context"):
        context = payload.get(context_key)
        if not isinstance(context, dict):
            continue
        yes_token_id = _as_nonempty_str(context.get("yes_token_id"))
        no_token_id = _as_nonempty_str(context.get("no_token_id"))
        if yes_token_id and no_token_id:
            return yes_token_id, no_token_id

    raise ValueError(
        "binary_complement_arb requires yes/no asset IDs. "
        f"Could not infer from {meta_path}: expected quickrun_context or shadow_context "
        "with yes_token_id and no_token_id. "
        f"{guidance}"
    )


def _resolve_binary_arb_strategy_config(
    *,
    strategy_name: str,
    strategy_config: dict[str, Any],
    events_path: Path,
    yes_asset_id_override: Any = None,
    no_asset_id_override: Any = None,
) -> tuple[dict[str, Any], bool]:
    if strategy_name != "binary_complement_arb":
        return strategy_config, False

    resolved_config = dict(strategy_config)
    inferred_from_tape_meta = False

    yes_asset_id = _as_nonempty_str(yes_asset_id_override) or _as_nonempty_str(
        resolved_config.get("yes_asset_id")
    )
    no_asset_id = _as_nonempty_str(no_asset_id_override) or _as_nonempty_str(
        resolved_config.get("no_asset_id")
    )

    if yes_asset_id is None or no_asset_id is None:
        inferred_yes, inferred_no = _infer_binary_arb_ids_from_tape_meta(events_path)
        if yes_asset_id is None:
            yes_asset_id = inferred_yes
            inferred_from_tape_meta = True
        if no_asset_id is None:
            no_asset_id = inferred_no
            inferred_from_tape_meta = True

    resolved_config["yes_asset_id"] = yes_asset_id
    resolved_config["no_asset_id"] = no_asset_id
    return resolved_config, inferred_from_tape_meta


def _mark_run_manifest_inferred_ids(run_dir: Path) -> None:
    manifest_path = run_dir / "run_manifest.json"
    if not manifest_path.exists():
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return
    if not isinstance(payload, dict):
        return

    payload["inferred_ids_from_tape_meta"] = True
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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

    strategy_name: str = args.strategy
    inferred_ids_from_tape_meta = False
    try:
        strategy_config = _load_strategy_config_from_args(args)
        strategy_config, inferred_ids_from_tape_meta = _resolve_binary_arb_strategy_config(
            strategy_name=strategy_name,
            strategy_config=strategy_config,
            events_path=events_path,
            yes_asset_id_override=getattr(args, "yes_asset_id", None),
            no_asset_id_override=getattr(args, "no_asset_id", None),
        )
        starting_cash = _parse_starting_cash_arg(args.starting_cash)
        fee_rate_bps = _parse_fee_rate_bps_arg(args.fee_rate_bps)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

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

    if inferred_ids_from_tape_meta:
        _mark_run_manifest_inferred_ids(run_dir)
        print(
            "[simtrader run] yes/no asset IDs inferred from tape meta.json",
            file=sys.stderr,
        )

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
_QUICK_SMALL_SWEEP_FEE_RATES = [0, 200]
_QUICK_SMALL_SWEEP_CANCEL_TICKS = [0]
_QUICK_SMALL_SWEEP_MARK_METHODS = ["bid", "midpoint"]


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


def _build_quick_small_sweep_config() -> dict:
    """Return a compact sweep config for faster local development loops.

    Matrix: 2 fee_rates × 1 cancel_latency_ticks × 2 mark_methods = 4 scenarios.
    """
    import itertools

    scenarios = []
    for fee, cancel, mark in itertools.product(
        _QUICK_SMALL_SWEEP_FEE_RATES,
        _QUICK_SMALL_SWEEP_CANCEL_TICKS,
        _QUICK_SMALL_SWEEP_MARK_METHODS,
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
    "quick_small": _build_quick_small_sweep_config,
}

_LIQUIDITY_PRESETS: dict[str, dict[str, float | int]] = {
    "strict": {
        "min_depth_size": 200.0,
        "top_n_levels": 5,
    }
}


def _resolve_liquidity_settings(
    *,
    liquidity: str | None,
    min_depth_size: float,
    top_n_levels: int,
) -> tuple[float, int]:
    """Resolve effective depth filter settings, applying preset overrides."""
    if liquidity is None:
        return min_depth_size, top_n_levels

    preset_key = liquidity.removeprefix("preset:")
    preset = _LIQUIDITY_PRESETS.get(preset_key)
    if preset is None:
        known = ", ".join(f"'preset:{k}'" for k in sorted(_LIQUIDITY_PRESETS))
        raise ValueError(f"unknown --liquidity preset {liquidity!r}. Known: {known}")

    return float(preset["min_depth_size"]), int(preset["top_n_levels"])


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

    try:
        min_depth_size, top_n_levels = _resolve_liquidity_settings(
            liquidity=getattr(args, "liquidity", None),
            min_depth_size=float(getattr(args, "min_depth_size", 0.0) or 0.0),
            top_n_levels=int(getattr(args, "top_n_levels", 3) or 3),
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if min_depth_size < 0:
        print(
            f"Error: --min-depth-size must be non-negative (got {min_depth_size}).",
            file=sys.stderr,
        )
        return 1
    if top_n_levels < 1:
        print(
            f"Error: --top-n-levels must be >= 1 (got {top_n_levels}).",
            file=sys.stderr,
        )
        return 1

    # -- Resolve market --------------------------------------------------------
    picker = MarketPicker(GammaClient(), ClobClient())

    yes_val: Any = None  # BookValidation for quickrun_context
    no_val: Any = None

    exclude_slugs_set: set[str] = set(getattr(args, "exclude_markets", None) or [])
    list_candidates_n: int = getattr(args, "list_candidates", 0) or 0

    # -- List-candidates mode --------------------------------------------------
    # Only active when --list-candidates N > 0 and no explicit --market.
    if list_candidates_n > 0 and not args.market:
        try:
            candidates = picker.auto_pick_many(
                n=list_candidates_n,
                max_candidates=args.max_candidates,
                allow_empty_book=args.allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
                exclude_slugs=exclude_slugs_set if exclude_slugs_set else None,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}", file=sys.stderr)
            return 1

        if not candidates:
            print(
                f"No valid candidates found in first {args.max_candidates} examined.",
                file=sys.stderr,
            )
            return 1

        for i, cand in enumerate(candidates, start=1):
            # Validate both books to get depth stats for display.
            c_yes = picker.validate_book(
                cand.yes_token_id,
                allow_empty=args.allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
            )
            c_no = picker.validate_book(
                cand.no_token_id,
                allow_empty=args.allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
            )
            yes_depth = (
                f"{c_yes.depth_total:.1f}" if c_yes.depth_total is not None else "n/a"
            )
            no_depth = (
                f"{c_no.depth_total:.1f}" if c_no.depth_total is not None else "n/a"
            )
            yes_bid = f"{c_yes.best_bid}" if c_yes.best_bid is not None else "n/a"
            yes_ask = f"{c_yes.best_ask}" if c_yes.best_ask is not None else "n/a"
            no_bid = f"{c_no.best_bid}" if c_no.best_bid is not None else "n/a"
            no_ask = f"{c_no.best_ask}" if c_no.best_ask is not None else "n/a"
            print(f"[candidate {i}] slug     : {cand.slug}")
            print(f"[candidate {i}] question : {cand.question}")
            print(
                f"[candidate {i}] YES bid  : {yes_bid}  ask: {yes_ask}  depth: {yes_depth}"
            )
            print(
                f"[candidate {i}] NO  bid  : {no_bid}  ask: {no_ask}  depth: {no_depth}"
            )

        print(f"Listed {len(candidates)} candidates.")
        return 0

    if list_candidates_n > 0 and args.market:
        print(
            "Warning: --list-candidates is ignored when --market is explicit.",
            file=sys.stderr,
        )

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
                exclude_slugs=exclude_slugs_set if exclude_slugs_set else None,
            )
            # Re-validate selected books so quickrun_context captures concrete details.
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
                    f"Error: selected market {resolved.slug!r} failed re-validation on "
                    f"{bad_side} book: {bad_reason}",
                    file=sys.stderr,
                )
                return 1
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
        "excluded_slugs": list(exclude_slugs_set),
        "list_candidates": list_candidates_n,
    }

    # -- Load user strategy config overrides -----------------------------------
    cfg_path = getattr(args, "strategy_config_path", None)
    cfg_json = getattr(args, "strategy_config_json", None)
    strategy_preset_raw = getattr(args, "strategy_preset", "sane")
    try:
        user_overrides = load_strategy_config(
            config_path=cfg_path,
            config_json=cfg_json,
        )
        strategy_preset = normalize_strategy_preset(strategy_preset_raw)
    except ConfigLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # -- Build strategy config (default + preset + explicit overrides) --------
    strategy_config = build_binary_complement_strategy_config(
        yes_asset_id=yes_id,
        no_asset_id=no_id,
        strategy_preset=strategy_preset,
        user_overrides=user_overrides,
    )

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
        if strategy_preset != "sane":
            reproduce += f" --strategy-preset {strategy_preset}"
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
    if strategy_preset != "sane":
        reproduce += f" --strategy-preset {strategy_preset}"
    if cfg_path is not None:
        reproduce += f" --strategy-config-path {cfg_path}"
    print(reproduce)

    return 0


# ---------------------------------------------------------------------------
# Shadow sub-command
# ---------------------------------------------------------------------------


def _shadow(args: argparse.Namespace) -> int:
    """Run binary_complement_arb live against the Polymarket Market Channel WS feed."""
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
    from packages.polymarket.simtrader.shadow.runner import ShadowRunner
    from packages.polymarket.simtrader.strategy.facade import (
        StrategyRunConfigError,
        _build_strategy,
    )

    # -- Resolve market ---------------------------------------------------------
    picker = MarketPicker(GammaClient(), ClobClient())

    try:
        resolved = picker.resolve_slug(args.market)
        yes_val = picker.validate_book(resolved.yes_token_id, allow_empty=False)
        no_val = picker.validate_book(resolved.no_token_id, allow_empty=False)
    except MarketPickerError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    yes_id = resolved.yes_token_id
    no_id = resolved.no_token_id

    print(f"[shadow] market   : {resolved.slug}")
    print(f"[shadow] question : {resolved.question}")
    print(f"[shadow] YES      : {yes_id}  ({resolved.yes_label})")
    print(f"[shadow] NO       : {no_id}  ({resolved.no_label})")

    if not yes_val.valid or not no_val.valid:
        bad_side = "YES" if not yes_val.valid else "NO"
        bad_reason = (yes_val if not yes_val.valid else no_val).reason
        print(
            f"Error: {bad_side} orderbook not usable for {args.market!r}: {bad_reason}",
            file=sys.stderr,
        )
        return 1

    # -- Dry run ---------------------------------------------------------------
    if args.dry_run:
        print("dry_run=True : exiting.")
        return 0

    # -- Load strategy config --------------------------------------------------
    cfg_path = getattr(args, "strategy_config_path", None)
    cfg_json = getattr(args, "strategy_config_json", None)
    strategy_preset_raw = getattr(args, "strategy_preset", "sane")
    try:
        user_overrides = load_strategy_config(
            config_path=cfg_path,
            config_json=cfg_json,
        )
        strategy_preset = normalize_strategy_preset(strategy_preset_raw)
    except ConfigLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    strategy_name = getattr(args, "strategy", "binary_complement_arb")
    strategy_config = build_binary_complement_strategy_config(
        yes_asset_id=yes_id,
        no_asset_id=no_id,
        strategy_preset=strategy_preset,
        user_overrides=user_overrides,
    )

    try:
        strategy = _build_strategy(strategy_name, strategy_config)
    except StrategyRunConfigError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # -- Parse portfolio config ------------------------------------------------
    try:
        starting_cash = _parse_starting_cash_arg(args.starting_cash)
        fee_rate_bps = _parse_fee_rate_bps_arg(args.fee_rate_bps)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # -- Build run directory ---------------------------------------------------
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{ts}_shadow_{yes_id[:8]}"
    run_dir = DEFAULT_ARTIFACTS_DIR / "shadow_runs" / run_id

    # -- Optional tape directory -----------------------------------------------
    record_tape = not args.no_record_tape
    tape_dir: Optional[Path] = None
    if record_tape:
        tape_dir = DEFAULT_ARTIFACTS_DIR / "tapes" / f"{ts}_shadow_{yes_id[:8]}"

    print(f"[shadow] run dir  : {run_dir}", file=sys.stderr)
    print(f"[shadow] duration : {args.duration}s", file=sys.stderr)
    print(f"[shadow] record   : {record_tape}", file=sys.stderr)

    # -- Build shadow_context (for manifest) -----------------------------------
    shadow_context: dict[str, Any] = {
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "selected_slug": resolved.slug,
        "yes_token_id": yes_id,
        "no_token_id": no_id,
        "selection_mode": "explicit",
        "yes_no_mapping": {
            "yes_label": resolved.yes_label,
            "no_label": resolved.no_label,
            "mapping_tier": getattr(resolved, "mapping_tier", "explicit"),
        },
    }

    # -- Run -------------------------------------------------------------------
    from packages.polymarket.simtrader.broker.latency import LatencyConfig

    runner = ShadowRunner(
        run_dir=run_dir,
        asset_ids=[yes_id, no_id],
        strategy=strategy,
        primary_asset_id=yes_id,
        extra_book_asset_ids=[no_id],
        duration_seconds=args.duration,
        starting_cash=starting_cash,
        fee_rate_bps=fee_rate_bps,
        mark_method=args.mark_method,
        tape_dir=tape_dir,
        shadow_context=shadow_context,
        ws_url=getattr(args, "ws_url", DEFAULT_WS_URL),
        strict=False,
        latency=LatencyConfig(
            submit_ticks=0,
            cancel_ticks=getattr(args, "cancel_latency_ticks", 0),
        ),
        max_ws_stall_seconds=getattr(args, "max_ws_stall_seconds", 30.0),
    )

    try:
        pnl_summary = runner.run()
    except ImportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error during shadow run: {exc}", file=sys.stderr)
        return 1

    net_profit = pnl_summary.get("net_profit", "0")

    print()
    print("Shadow run complete")
    print(f"  Market     : {resolved.slug}")
    print(f"  YES token  : {yes_id}")
    print(f"  NO token   : {no_id}")
    print(f"  Net profit : {net_profit}")
    print(f"  Run dir    : artifacts/simtrader/shadow_runs/{run_id}/")
    if tape_dir is not None:
        print(f"  Tape dir   : artifacts/simtrader/tapes/{tape_dir.name}/")
    print()
    print("Reproduce:")
    reproduce = (
        f"  python -m polytool simtrader shadow "
        f"--market {resolved.slug} "
        f"--duration {args.duration}"
    )
    if args.starting_cash != 1000.0:
        reproduce += f" --starting-cash {args.starting_cash}"
    if args.fee_rate_bps is not None:
        reproduce += f" --fee-rate-bps {args.fee_rate_bps}"
    if args.mark_method != "bid":
        reproduce += f" --mark-method {args.mark_method}"
    if strategy_preset != "sane":
        reproduce += f" --strategy-preset {strategy_preset}"
    if not record_tape:
        reproduce += " --no-record-tape"
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
        "--yes-asset-id",
        default=None,
        metavar="ASSET_ID",
        dest="yes_asset_id",
        help=(
            "Manual YES token override for binary_complement_arb. "
            "Takes precedence over strategy config and tape meta inference."
        ),
    )
    run_p.add_argument(
        "--no-asset-id",
        default=None,
        metavar="ASSET_ID",
        dest="no_asset_id",
        help=(
            "Manual NO token override for binary_complement_arb. "
            "Takes precedence over strategy config and tape meta inference."
        ),
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
        "--strategy-preset",
        default="sane",
        choices=list(STRATEGY_PRESET_CHOICES),
        metavar="NAME",
        dest="strategy_preset",
        help=(
            "Named strategy preset. "
            "sane=conservative defaults; "
            "loose=min_top_size(1), min_edge(0.0005), max_notional(25)."
        ),
    )
    qr.add_argument(
        "--max-candidates",
        type=int,
        default=20,
        metavar="N",
        dest="max_candidates",
        help=(
            "Number of active markets to examine when auto-picking "
            "(default: 20, range: 1..100).  Ignored if --market is specified."
        ),
    )
    qr.add_argument(
        "--list-candidates",
        type=int,
        default=0,
        metavar="N",
        dest="list_candidates",
        help=(
            "Print the top N candidates that pass validation, then exit.  "
            "Best combined with --dry-run.  0 = disabled (default)."
        ),
    )
    qr.add_argument(
        "--exclude-market",
        action="append",
        default=[],
        metavar="SLUG",
        dest="exclude_markets",
        help=(
            "Skip this slug during auto-pick (repeatable).  "
            "e.g. --exclude-market will-x-happen --exclude-market will-y-happen"
        ),
    )
    qr.add_argument(
        "--min-depth-size",
        type=float,
        default=50.0,
        metavar="SIZE",
        dest="min_depth_size",
        help=(
            "Minimum total size (sum of top --top-n-levels bid + ask levels) "
            "required for a book to be considered liquid.  "
            "0 disables the depth filter (default: 50)."
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
        "--liquidity",
        default=None,
        metavar="PRESET",
        dest="liquidity",
        help=(
            "Liquidity preset for market selection depth filters. "
            "Use 'preset:strict' to force --min-depth-size 200 and "
            "--top-n-levels 5."
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

    # ------------------------------------------------------------------
    # batch
    # ------------------------------------------------------------------
    batch_p = sub.add_parser(
        "batch",
        help=(
            "Pick N live binary markets, run a quicksweep per market overnight, "
            "and produce a batch leaderboard.  "
            "Writes artifacts to artifacts/simtrader/batches/<batch_id>/."
        ),
    )
    batch_p.add_argument(
        "--preset",
        default="quick",
        metavar="NAME",
        help=(
            "Sweep preset to run per market.  "
            "Use 'quick' for the built-in 24-scenario evidence-run preset (default), "
            "or 'quick_small' for a faster local-development preset."
        ),
    )
    batch_p.add_argument(
        "--strategy-preset",
        default="sane",
        choices=list(STRATEGY_PRESET_CHOICES),
        metavar="NAME",
        dest="strategy_preset",
        help=(
            "Named strategy preset applied to each market run. "
            "sane=conservative defaults; "
            "loose=min_top_size(1), min_edge(0.0005), max_notional(25)."
        ),
    )
    batch_p.add_argument(
        "--num-markets",
        type=int,
        default=DEFAULT_BATCH_NUM_MARKETS,
        metavar="N",
        dest="num_markets",
        help=(
            "Number of markets to process "
            f"(default: {DEFAULT_BATCH_NUM_MARKETS}, max: 200)."
        ),
    )
    batch_p.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_BATCH_DURATION_SECONDS,
        metavar="SECONDS",
        help=(
            "Tape recording duration per market in seconds "
            f"(default: {DEFAULT_BATCH_DURATION_SECONDS:.0f})."
        ),
    )
    batch_p.add_argument(
        "--min-events",
        type=int,
        default=0,
        metavar="N",
        dest="min_events",
        help=(
            "Warn when a market tape has fewer than N parsed events. "
            "Use 0 to disable (default: 0)."
        ),
    )
    batch_p.add_argument(
        "--starting-cash",
        type=float,
        default=1000.0,
        metavar="USDC",
        dest="starting_cash",
        help="Starting USDC cash balance per run (default: 1000).",
    )
    batch_p.add_argument(
        "--fee-rate-bps",
        type=float,
        default=None,
        metavar="BPS",
        dest="fee_rate_bps",
        help="Base taker fee rate in bps (default: conservative 200 bps).",
    )
    batch_p.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default="bid",
        dest="mark_method",
        help="Base mark-price method (default: 'bid').",
    )
    batch_p.add_argument(
        "--max-candidates",
        type=int,
        default=100,
        metavar="N",
        dest="max_candidates",
        help=(
            "Candidate pool size for market picking (default: 100).  "
            "Range: 1..100. Must be >= --num-markets."
        ),
    )
    batch_p.add_argument(
        "--allow-empty-book",
        action="store_true",
        default=False,
        dest="allow_empty_book",
        help="Accept markets with empty orderbooks.",
    )
    batch_p.add_argument(
        "--min-depth-size",
        type=float,
        default=50.0,
        metavar="SIZE",
        dest="min_depth_size",
        help=(
            "Minimum total size across top --top-n-levels per side for a "
            "book to be considered liquid (default: 50, 0 = disabled)."
        ),
    )
    batch_p.add_argument(
        "--top-n-levels",
        type=int,
        default=3,
        metavar="N",
        dest="top_n_levels",
        help="Levels per side for depth sum (default: 3).",
    )
    batch_p.add_argument(
        "--liquidity",
        default=None,
        metavar="PRESET",
        dest="liquidity",
        help=(
            "Liquidity preset for auto-pick depth filters. "
            "Use 'preset:strict' to force --min-depth-size 200 and "
            "--top-n-levels 5."
        ),
    )
    batch_p.add_argument(
        "--batch-id",
        default=None,
        metavar="ID",
        dest="batch_id",
        help="Override the auto-generated batch ID.",
    )
    batch_p.add_argument(
        "--rerun",
        action="store_true",
        default=False,
        help="Re-run markets that already have results in this batch folder.",
    )
    batch_p.add_argument(
        "--time-budget-seconds",
        type=float,
        default=None,
        metavar="SECONDS",
        dest="time_budget_seconds",
        help=(
            "Optional wall-clock budget for the batch launcher. "
            "When exceeded, no new markets are launched and remaining markets are skipped."
        ),
    )

    # ------------------------------------------------------------------
    # shadow
    # ------------------------------------------------------------------
    shadow_p = sub.add_parser(
        "shadow",
        help=(
            "Run a strategy live against the Polymarket Market Channel WS feed "
            "(no real orders — BrokerSim only).  Resolves YES/NO tokens from --market SLUG, "
            "streams events inline, and writes the full run artifact set.  "
            "Use --no-record-tape to skip writing a tape."
        ),
    )
    shadow_p.add_argument(
        "--market",
        required=True,
        metavar="SLUG",
        help="Polymarket market slug to shadow-trade (e.g. 'will-x-happen-2026').",
    )
    shadow_p.add_argument(
        "--duration",
        type=float,
        default=300.0,
        metavar="SECONDS",
        help="How long to run in seconds (default: 300).  0 = run until Ctrl-C.",
    )
    shadow_p.add_argument(
        "--strategy",
        default="binary_complement_arb",
        metavar="NAME",
        help=(
            "Strategy name to use.  "
            f"Available: {', '.join(strategy_names)}.  "
            "Default: binary_complement_arb."
        ),
    )
    shadow_p.add_argument(
        "--strategy-config-path",
        default=None,
        metavar="PATH",
        dest="strategy_config_path",
        help="Path to a JSON file with strategy config overrides (accepts UTF-8 BOM).",
    )
    shadow_p.add_argument(
        "--strategy-config-json",
        default=None,
        metavar="JSON",
        dest="strategy_config_json",
        help="Inline JSON string with strategy config overrides.",
    )
    shadow_p.add_argument(
        "--strategy-preset",
        default="sane",
        choices=list(STRATEGY_PRESET_CHOICES),
        metavar="NAME",
        dest="strategy_preset",
        help=(
            "Named strategy preset. "
            "sane=conservative defaults; "
            "loose=min_top_size(1), min_edge(0.0005), max_notional(25)."
        ),
    )
    shadow_p.add_argument(
        "--starting-cash",
        type=float,
        default=1000.0,
        metavar="USDC",
        dest="starting_cash",
        help="Starting USDC cash balance (default: 1000).",
    )
    shadow_p.add_argument(
        "--fee-rate-bps",
        type=float,
        default=None,
        metavar="BPS",
        dest="fee_rate_bps",
        help="Taker fee rate in basis points (default: conservative 200 bps).",
    )
    shadow_p.add_argument(
        "--mark-method",
        choices=["bid", "midpoint"],
        default="bid",
        dest="mark_method",
        help="Mark-price method for unrealized PnL: 'bid' (default) or 'midpoint'.",
    )
    shadow_p.add_argument(
        "--cancel-latency-ticks",
        type=int,
        default=0,
        metavar="N",
        dest="cancel_latency_ticks",
        help="Cancel latency in tape ticks (default: 0).",
    )
    shadow_p.add_argument(
        "--no-record-tape",
        action="store_true",
        default=False,
        dest="no_record_tape",
        help=(
            "Disable concurrent tape recording.  "
            "By default the session is recorded to "
            "artifacts/simtrader/tapes/<ts>_shadow_<token_prefix>/ "
            "(raw_ws.jsonl + events.jsonl + meta.json)."
        ),
    )
    shadow_p.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        dest="dry_run",
        help="Resolve and validate the market, then exit without connecting.",
    )
    shadow_p.add_argument(
        "--ws-url",
        default=DEFAULT_WS_URL,
        dest="ws_url",
        help=f"WebSocket endpoint URL (default: {DEFAULT_WS_URL}).",
    )
    shadow_p.add_argument(
        "--max-ws-stalls-seconds",
        type=float,
        default=30.0,
        metavar="SECONDS",
        dest="max_ws_stall_seconds",
        help=(
            "Exit gracefully if no WS events arrive for this many seconds "
            "(default: 30).  All in-flight artifacts are written before exit.  "
            "Set 0 to disable."
        ),
    )

    # ------------------------------------------------------------------
    # browse
    # ------------------------------------------------------------------
    browse_p = sub.add_parser(
        "browse",
        help=(
            "List recent SimTrader artifacts and optionally generate "
            "report.html files."
        ),
    )
    browse_p.add_argument(
        "--limit",
        type=int,
        default=10,
        metavar="N",
        help="Maximum number of artifacts to list (default: 10).",
    )
    browse_p.add_argument(
        "--type",
        default="all",
        choices=["run", "sweep", "batch", "shadow", "all"],
        dest="artifact_type",
        help="Filter artifact type (default: all).",
    )
    browse_p.add_argument(
        "--open",
        action="store_true",
        default=False,
        dest="open_report",
        help=(
            "Generate report.html for the newest listed artifact and print "
            "browser open instructions."
        ),
    )
    browse_p.add_argument(
        "--report-all",
        action="store_true",
        default=False,
        dest="report_all",
        help="Generate report.html for all listed artifacts.",
    )

    # ------------------------------------------------------------------
    # report
    # ------------------------------------------------------------------
    report_p = sub.add_parser(
        "report",
        help=(
            "Generate a local self-contained HTML report for a SimTrader "
            "run/sweep/batch artifact folder."
        ),
    )
    report_p.add_argument(
        "--path",
        required=True,
        metavar="DIR",
        help=(
            "Path to an artifact directory. "
            "Auto-detects run/sweep/batch type from marker JSON files."
        ),
    )
    report_p.add_argument(
        "--open",
        action="store_true",
        default=False,
        dest="open_report",
        help="Print friendly instructions for opening the generated report.html.",
    )

    return parser


# ---------------------------------------------------------------------------
# Batch sub-command handler
# ---------------------------------------------------------------------------


def _batch(args: argparse.Namespace) -> int:
    """Pick N markets and run a quicksweep per market."""
    from packages.polymarket.clob import ClobClient
    from packages.polymarket.gamma import GammaClient
    from packages.polymarket.simtrader.batch.runner import (
        BatchRunError,
        BatchRunParams,
        run_batch,
    )

    # Validate
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
    if (
        args.time_budget_seconds is not None
        and float(args.time_budget_seconds) <= 0
    ):
        print(
            "Error: --time-budget-seconds must be > 0 when provided.",
            file=sys.stderr,
        )
        return 1
    try:
        min_depth_size, top_n_levels = _resolve_liquidity_settings(
            liquidity=getattr(args, "liquidity", None),
            min_depth_size=float(getattr(args, "min_depth_size", 0.0) or 0.0),
            top_n_levels=int(getattr(args, "top_n_levels", 3) or 3),
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if min_depth_size < 0:
        print(
            f"Error: --min-depth-size must be non-negative (got {min_depth_size}).",
            file=sys.stderr,
        )
        return 1
    if top_n_levels < 1:
        print(
            f"Error: --top-n-levels must be >= 1 (got {top_n_levels}).",
            file=sys.stderr,
        )
        return 1

    try:
        starting_cash = _parse_starting_cash_arg(args.starting_cash)
        fee_rate_bps = _parse_fee_rate_bps_arg(args.fee_rate_bps)
        strategy_preset = normalize_strategy_preset(
            getattr(args, "strategy_preset", "sane")
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Resolve preset
    preset_key = args.preset.removeprefix("preset:")
    if preset_key not in _SWEEP_PRESETS:
        known = ", ".join(f"'{k}'" for k in _SWEEP_PRESETS)
        print(
            f"Error: unknown --preset {args.preset!r}. Known: {known}",
            file=sys.stderr,
        )
        return 1

    effective_num_markets = int(args.num_markets)
    effective_duration = float(args.duration)
    if preset_key == "quick_small":
        if effective_num_markets == DEFAULT_BATCH_NUM_MARKETS:
            effective_num_markets = DEFAULT_BATCH_SMALL_NUM_MARKETS
        if effective_duration == DEFAULT_BATCH_DURATION_SECONDS:
            effective_duration = DEFAULT_BATCH_SMALL_DURATION_SECONDS

    if not (1 <= effective_num_markets <= 200):
        print(
            f"Error: --num-markets must be between 1 and 200 (got {effective_num_markets}).",
            file=sys.stderr,
        )
        return 1
    if args.max_candidates < effective_num_markets:
        print(
            f"Error: --max-candidates ({args.max_candidates}) must be >= "
            f"--num-markets ({effective_num_markets}).",
            file=sys.stderr,
        )
        return 1

    params = BatchRunParams(
        num_markets=effective_num_markets,
        preset=preset_key,
        duration=effective_duration,
        starting_cash=starting_cash,
        fee_rate_bps=fee_rate_bps,
        mark_method=args.mark_method,
        max_candidates=args.max_candidates,
        min_events=args.min_events,
        allow_empty_book=args.allow_empty_book,
        min_depth_size=min_depth_size,
        top_n_levels=top_n_levels,
        artifacts_root=DEFAULT_ARTIFACTS_DIR,
        batch_id=args.batch_id or None,
        rerun=args.rerun,
        time_budget_seconds=args.time_budget_seconds,
        strategy_preset=strategy_preset,
    )

    print(
        f"[batch] preset       : {preset_key}  "
        f"({len(_SWEEP_PRESETS[preset_key]()['scenarios'])} scenarios per market)",
        file=sys.stderr,
    )
    print(f"[batch] num_markets  : {effective_num_markets}", file=sys.stderr)
    print(f"[batch] duration     : {effective_duration}s per market", file=sys.stderr)
    print(f"[batch] starting_cash: {starting_cash}", file=sys.stderr)
    if args.time_budget_seconds is not None:
        print(
            f"[batch] time budget : {args.time_budget_seconds}s",
            file=sys.stderr,
        )

    try:
        result = run_batch(
            params=params,
            gamma_client=GammaClient(),
            clob_client=ClobClient(),
            sweep_config_factory=_SWEEP_PRESETS[preset_key],
        )
    except BatchRunError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error during batch run: {exc}", file=sys.stderr)
        return 1

    agg = result.summary.get("aggregate", {})
    markets = result.summary.get("markets", [])
    ok_count = agg.get("markets_ok", 0)
    skipped_count = agg.get("markets_skipped", 0)
    error_count = agg.get("markets_error", 0)
    total_orders = agg.get("total_orders", 0)
    total_decisions = agg.get("total_decisions", 0)
    total_fills = agg.get("total_fills", 0)
    tape_events_count = agg.get("tape_events_count", 0)
    tape_bbo_rows = agg.get("tape_bbo_rows", 0)

    print()
    print(f"Batch complete  (id: {result.batch_id})")
    print(f"  Batch dir    : {result.batch_dir}")
    print(
        f"  Markets      : {ok_count} ok  "
        f"{skipped_count} skipped  {error_count} error"
    )
    print(
        f"  Decisions/Orders/Fills : "
        f"{total_decisions}/{total_orders}/{total_fills}"
    )
    print(
        f"  Tape quality rows       : "
        f"events={tape_events_count}  bbo_rows={tape_bbo_rows}"
    )

    if ok_count > 0:
        print()
        print("  LEADERBOARD (best_net_profit per market):")
        leaderboard = sorted(
            [m for m in markets if m["status"] == "ok"],
            key=lambda m: (
                float(m.get("best_net_profit") or 0)
            ),
            reverse=True,
        )
        for rank, m in enumerate(leaderboard, start=1):
            print(
                f"  {rank:2d}. {m['slug']:<40s}  "
                f"best={m.get('best_net_profit') or 'n/a':>10s}  "
                f"fills={m.get('total_fills', 0)}"
            )

    print()
    print("Reproduce:")
    reproduce = (
        f"  python -m polytool simtrader batch "
        f"--preset {preset_key} "
        f"--num-markets {effective_num_markets} "
        f"--duration {effective_duration} "
        f"--batch-id {result.batch_id}"
    )
    if strategy_preset != "sane":
        reproduce += f" --strategy-preset {strategy_preset}"
    if args.time_budget_seconds is not None:
        reproduce += f" --time-budget-seconds {args.time_budget_seconds}"
    print(reproduce)

    return 0


# ---------------------------------------------------------------------------
# Browse sub-command helpers + handler
# ---------------------------------------------------------------------------


def _read_json_dict(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return payload if isinstance(payload, dict) else {}


def _text_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _parse_browse_datetime(value: Any) -> Optional[datetime]:
    text = _text_or_none(value)
    if text is None:
        return None

    # Allow timestamps embedded in IDs like "quickrun_20260224T220832Z_abcd1234".
    match = _BROWSE_TS_RE.search(text)
    if match is not None:
        text = match.group(1)

    if re.fullmatch(r"20\d{6}T\d{6}Z", text):
        try:
            return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    iso_text = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(iso_text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_browse_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _infer_browse_timestamp(
    artifact_dir: Path,
    *,
    candidates: list[Any],
) -> tuple[datetime, str]:
    folder_match = _BROWSE_TS_RE.search(artifact_dir.name)
    if folder_match is not None:
        parsed = _parse_browse_datetime(folder_match.group(1))
        if parsed is not None:
            return parsed, _format_browse_datetime(parsed)

    for raw in candidates:
        parsed = _parse_browse_datetime(raw)
        if parsed is not None:
            return parsed, _format_browse_datetime(parsed)

    try:
        fallback = datetime.fromtimestamp(
            artifact_dir.stat().st_mtime,
            tz=timezone.utc,
        )
    except OSError:
        fallback = datetime.fromtimestamp(0, tz=timezone.utc)
    return fallback, _format_browse_datetime(fallback)


def _extract_run_market_slug(run_manifest: dict[str, Any]) -> str:
    quickrun_context = run_manifest.get("quickrun_context")
    if isinstance(quickrun_context, dict):
        slug = _text_or_none(quickrun_context.get("selected_slug"))
        if slug is not None:
            return slug

    shadow_context = run_manifest.get("shadow_context")
    if isinstance(shadow_context, dict):
        for key in ("selected_slug", "market", "slug"):
            slug = _text_or_none(shadow_context.get(key))
            if slug is not None:
                return slug

    direct_slug = _text_or_none(run_manifest.get("market_slug"))
    return direct_slug or "-"


def _extract_batch_market_slug(
    batch_manifest: dict[str, Any],
    batch_summary: dict[str, Any],
) -> str:
    slugs: list[str] = []
    for container in (batch_summary, batch_manifest):
        markets = container.get("markets")
        if not isinstance(markets, list):
            continue
        for row in markets:
            if not isinstance(row, dict):
                continue
            slug = _text_or_none(row.get("slug"))
            if slug is not None:
                slugs.append(slug)
        if slugs:
            break

    deduped = sorted(set(slugs))
    if not deduped:
        return "-"
    if len(deduped) == 1:
        return deduped[0]
    return f"multiple({len(deduped)})"


def _is_browse_artifact_dir(artifact_type: str, artifact_dir: Path) -> bool:
    if artifact_type == "sweep":
        return (
            (artifact_dir / "sweep_summary.json").exists()
            or (artifact_dir / "sweep_manifest.json").exists()
        )
    if artifact_type == "batch":
        return (
            (artifact_dir / "batch_summary.json").exists()
            or (artifact_dir / "batch_manifest.json").exists()
        )
    # run + shadow both rely on run_manifest.json.
    return (artifact_dir / "run_manifest.json").exists()


def _collect_browse_entry(artifact_type: str, artifact_dir: Path) -> dict[str, Any]:
    artifact_id = artifact_dir.name
    market_slug = "-"
    timestamp_candidates: list[Any] = []

    if artifact_type == "sweep":
        sweep_manifest = _read_json_dict(artifact_dir / "sweep_manifest.json")
        sweep_summary = _read_json_dict(artifact_dir / "sweep_summary.json")
        artifact_id = (
            _text_or_none(sweep_summary.get("sweep_id"))
            or _text_or_none(sweep_manifest.get("sweep_id"))
            or artifact_dir.name
        )
        quickrun_context = sweep_manifest.get("quickrun_context")
        if isinstance(quickrun_context, dict):
            market_slug = _text_or_none(quickrun_context.get("selected_slug")) or "-"
            timestamp_candidates.append(quickrun_context.get("selected_at"))
        timestamp_candidates.append(sweep_manifest.get("created_at"))
        timestamp_candidates.append(sweep_summary.get("created_at"))

    elif artifact_type == "batch":
        batch_manifest = _read_json_dict(artifact_dir / "batch_manifest.json")
        batch_summary = _read_json_dict(artifact_dir / "batch_summary.json")
        artifact_id = (
            _text_or_none(batch_summary.get("batch_id"))
            or _text_or_none(batch_manifest.get("batch_id"))
            or artifact_dir.name
        )
        market_slug = _extract_batch_market_slug(batch_manifest, batch_summary)
        timestamp_candidates.append(batch_manifest.get("created_at"))
        timestamp_candidates.append(batch_summary.get("created_at"))

    else:
        run_manifest = _read_json_dict(artifact_dir / "run_manifest.json")
        artifact_id = _text_or_none(run_manifest.get("run_id")) or artifact_dir.name
        market_slug = _extract_run_market_slug(run_manifest)
        timestamp_candidates.append(run_manifest.get("created_at"))
        timestamp_candidates.append(run_manifest.get("started_at"))
        shadow_context = run_manifest.get("shadow_context")
        if isinstance(shadow_context, dict):
            timestamp_candidates.append(shadow_context.get("selected_at"))
        quickrun_context = run_manifest.get("quickrun_context")
        if isinstance(quickrun_context, dict):
            timestamp_candidates.append(quickrun_context.get("selected_at"))

    timestamp_dt, timestamp_text = _infer_browse_timestamp(
        artifact_dir,
        candidates=timestamp_candidates,
    )

    return {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "artifact_dir": artifact_dir,
        "timestamp_dt": timestamp_dt,
        "timestamp_text": timestamp_text,
        "market_slug": market_slug,
    }


def _collect_recent_artifacts(
    *,
    limit: int,
    artifact_type_filter: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact_type, subdir in _BROWSE_TYPE_DIRS.items():
        if artifact_type_filter != "all" and artifact_type_filter != artifact_type:
            continue
        root = DEFAULT_ARTIFACTS_DIR / subdir
        if not root.exists() or not root.is_dir():
            continue
        for artifact_dir in root.iterdir():
            if not artifact_dir.is_dir():
                continue
            if not _is_browse_artifact_dir(artifact_type, artifact_dir):
                continue
            rows.append(_collect_browse_entry(artifact_type, artifact_dir))

    rows.sort(
        key=lambda row: (
            row["timestamp_dt"],
            str(row["artifact_id"]).lower(),
            str(row["artifact_dir"]).lower(),
        ),
        reverse=True,
    )
    return rows[:limit]


def _print_open_report_instructions(report_path: Path) -> None:
    if sys.platform.startswith("win"):
        print(f'  PowerShell: ii "{report_path}"')
    elif sys.platform == "darwin":
        print(f'  macOS: open "{report_path}"')
    else:
        print(f'  Linux: xdg-open "{report_path}"')


def _browse(args: argparse.Namespace) -> int:
    """List recent SimTrader artifacts and optionally generate HTML reports."""
    from packages.polymarket.simtrader.report import (
        SimTraderReportError,
        generate_report,
    )

    if args.limit < 1:
        print(f"Error: --limit must be >= 1 (got {args.limit}).", file=sys.stderr)
        return 1

    artifacts = _collect_recent_artifacts(
        limit=args.limit,
        artifact_type_filter=args.artifact_type,
    )
    if not artifacts:
        print(
            f"No artifacts found under {DEFAULT_ARTIFACTS_DIR} "
            f"(type filter: {args.artifact_type})."
        )
        return 0

    print("Recent SimTrader artifacts:")
    for index, row in enumerate(artifacts, start=1):
        print(
            f"  {index}. type={row['artifact_type']:<6s} "
            f"id={row['artifact_id']} "
            f"ts={row['timestamp_text']} "
            f"market={row['market_slug']}"
        )

    report_targets: list[dict[str, Any]] = []
    if args.report_all:
        report_targets = artifacts
    elif args.open_report:
        report_targets = [artifacts[0]]

    generated_paths: dict[Path, Path] = {}
    errors = 0
    for row in report_targets:
        artifact_dir = row["artifact_dir"]
        try:
            result = generate_report(artifact_dir)
        except SimTraderReportError as exc:
            print(
                f"Error: could not generate report for {artifact_dir}: {exc}",
                file=sys.stderr,
            )
            errors += 1
            continue
        except Exception as exc:  # noqa: BLE001
            print(
                f"Error during report generation for {artifact_dir}: {exc}",
                file=sys.stderr,
            )
            errors += 1
            continue

        generated_paths[artifact_dir] = result.report_path
        print(f"Report written: {result.report_path}")

    if args.open_report:
        newest_dir = artifacts[0]["artifact_dir"]
        report_path = generated_paths.get(newest_dir)
        if report_path is not None:
            print()
            print("Open this report in a browser:")
            _print_open_report_instructions(report_path)
        elif report_targets:
            errors += 1

    return 1 if errors else 0


# ---------------------------------------------------------------------------
# Report sub-command handler
# ---------------------------------------------------------------------------


def _report(args: argparse.Namespace) -> int:
    """Generate an HTML report for an existing SimTrader artifact directory."""
    from packages.polymarket.simtrader.report import (
        SimTraderReportError,
        generate_report,
    )

    artifact_dir = Path(args.path)
    try:
        result = generate_report(artifact_dir)
    except SimTraderReportError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"Error during report generation: {exc}", file=sys.stderr)
        return 1

    print(f"Report written: {result.report_path}")
    print(f"  Artifact type: {result.artifact_type}")
    print(f"  Artifact id  : {result.artifact_id}")

    if args.open_report:
        print()
        print("Open this report in a browser:")
        _print_open_report_instructions(result.report_path)

    return 0


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
    if args.subcommand == "batch":
        return _batch(args)
    if args.subcommand == "shadow":
        return _shadow(args)
    if args.subcommand == "browse":
        return _browse(args)
    if args.subcommand == "report":
        return _report(args)

    parser.print_help()
    return 1
