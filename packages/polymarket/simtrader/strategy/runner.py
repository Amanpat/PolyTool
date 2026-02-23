"""StrategyRunner: connects tape replay to a Strategy and PortfolioLedger.

Processing order for each tape event
-------------------------------------
1. ``book.apply(event)``
2. ``strategy.on_event(...)`` → list[OrderIntent]
3. For each OrderIntent: ``broker.submit_order`` / ``broker.cancel_order``
4. ``broker.step(event, book)``
5. Update open-order tracking from new broker events
6. Emit timeline row on book-affecting events

After the loop
--------------
- ``strategy.on_finish()``
- ``PortfolioLedger.process(broker.order_events, timeline)``
- Write all artifacts to ``run_dir``

Artifacts written
-----------------
  best_bid_ask.jsonl, orders.jsonl, fills.jsonl, ledger.jsonl,
  equity_curve.jsonl, summary.json, decisions.jsonl,
  run_manifest.json, meta.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..broker.latency import ZERO_LATENCY, LatencyConfig
from ..broker.sim_broker import SimBroker
from ..orderbook.l2book import L2Book
from ..portfolio.ledger import PortfolioLedger
from ..portfolio.mark import MARK_BID
from ..tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE
from .base import OrderIntent, Strategy

logger = logging.getLogger(__name__)

_BOOK_AFFECTING = frozenset({EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE})


class StrategyRunner:
    """Orchestrates tape replay for a single Strategy instance.

    Determinism guarantee: given the same tape, strategy, and config, two
    calls to ``run()`` produce byte-identical artifacts (including
    ``decisions.jsonl``).
    """

    def __init__(
        self,
        events_path: Path,
        run_dir: Path,
        strategy: Strategy,
        asset_id: Optional[str] = None,
        latency: LatencyConfig = ZERO_LATENCY,
        starting_cash: Decimal = Decimal("1000"),
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = MARK_BID,
        strict: bool = False,
    ) -> None:
        """
        Args:
            events_path:   Path to events.jsonl tape file.
            run_dir:       Directory for all output artifacts (created if absent).
            strategy:      Strategy instance to drive.
            asset_id:      Asset to focus on.  Auto-detected if tape has one asset.
            latency:       Submit / cancel latency model (default: zero ticks).
            starting_cash: Initial USDC cash for the portfolio ledger.
            fee_rate_bps:  Taker fee rate in bps (default: 200 bps conservative).
            mark_method:   "bid" (conservative) or "midpoint".
            strict:        If True, raise on L2BookError or malformed events.
        """
        self.events_path = events_path
        self.run_dir = run_dir
        self.strategy = strategy
        self.asset_id = asset_id
        self.latency = latency
        self.starting_cash = starting_cash
        self.fee_rate_bps = fee_rate_bps
        self.mark_method = mark_method
        self.strict = strict

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute strategy replay and write artifacts.

        Returns:
            The PnL summary dict (same schema as ``summary.json``).

        Raises:
            ValueError: If the tape is empty or asset_id cannot be resolved.
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)

        events, warnings = self._load_events()
        if not events:
            raise ValueError(f"No events found in {self.events_path}")

        asset_id = self._resolve_asset_id(events)
        book = L2Book(asset_id, strict=self.strict)
        broker = SimBroker(latency=self.latency)

        # Open-order tracking: keyed by order_id, plain dict values
        open_orders: dict[str, dict] = {}
        _last_order_event_idx = 0

        timeline: list[dict] = []
        decisions: list[dict] = []

        self.strategy.on_start(asset_id, self.starting_cash)

        for event in events:
            seq: int = event.get("seq", 0)
            ts_recv: float = event.get("ts_recv", 0.0)
            evt_asset: str = event.get("asset_id", "")
            event_type: str = event.get("event_type", "")

            # 1. Update book
            if evt_asset == asset_id:
                book.apply(event)

            # 2. Ask strategy for intents (pass a snapshot of open_orders)
            intents = self.strategy.on_event(
                event,
                seq,
                ts_recv,
                book.best_bid,
                book.best_ask,
                dict(open_orders),
            )

            # 3. Execute intents
            for intent in intents:
                self._execute_intent(
                    intent, seq, ts_recv, asset_id, book,
                    broker, open_orders, decisions,
                )

            # 4. Step broker (must be after book.apply)
            if evt_asset == asset_id:
                broker.step(event, book)

                # Update open_orders from broker events emitted in this step
                new_events = broker.order_events[_last_order_event_idx:]
                _last_order_event_idx = len(broker.order_events)
                for bev in new_events:
                    _update_open_orders(open_orders, bev)

            # 5. Emit timeline row on book-affecting events
            if evt_asset == asset_id and event_type in _BOOK_AFFECTING:
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

        self.strategy.on_finish()

        # Portfolio ledger
        ledger = PortfolioLedger(
            starting_cash=self.starting_cash,
            fee_rate_bps=self.fee_rate_bps,
            mark_method=self.mark_method,
        )
        ledger_events, equity_curve = ledger.process(broker.order_events, timeline)
        final_best_bid: Optional[float] = timeline[-1].get("best_bid") if timeline else None
        final_best_ask: Optional[float] = timeline[-1].get("best_ask") if timeline else None

        run_id = self.run_dir.name
        pnl_summary = ledger.summary(run_id, final_best_bid, final_best_ask)

        self._write_artifacts(
            broker=broker,
            timeline=timeline,
            ledger_events=ledger_events,
            equity_curve=equity_curve,
            pnl_summary=pnl_summary,
            decisions=decisions,
            warnings=warnings,
            asset_id=asset_id,
            total_events=len(events),
        )

        return pnl_summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_events(self) -> tuple[list[dict], list[str]]:
        events: list[dict] = []
        warnings: list[str] = []
        with open(self.events_path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    warnings.append(f"Skipping malformed line {lineno}: {exc}")
        events.sort(key=lambda e: e.get("seq", 0))
        return events, warnings

    def _resolve_asset_id(self, events: list[dict]) -> str:
        if self.asset_id:
            return self.asset_id
        ids = {e.get("asset_id", "") for e in events if e.get("asset_id")}
        if len(ids) == 1:
            return next(iter(ids))
        if len(ids) > 1:
            raise ValueError(
                f"Tape has multiple asset_ids {sorted(ids)}. "
                "Pass asset_id to StrategyRunner."
            )
        raise ValueError("Tape has no asset_id fields.")

    def _execute_intent(
        self,
        intent: OrderIntent,
        seq: int,
        ts_recv: float,
        asset_id: str,
        book: L2Book,
        broker: SimBroker,
        open_orders: dict[str, dict],
        decisions: list[dict],
    ) -> None:
        if intent.action == "submit":
            effective_asset = intent.asset_id or asset_id
            if intent.limit_price is None or intent.size is None or intent.side is None:
                logger.warning(
                    "OrderIntent(submit) missing required fields at seq=%d; skipping.", seq
                )
                return
            oid = broker.submit_order(
                asset_id=effective_asset,
                side=intent.side,
                limit_price=intent.limit_price,
                size=intent.size,
                submit_seq=seq,
                submit_ts=ts_recv,
            )
            open_orders[oid] = {
                "order_id": oid,
                "side": intent.side,
                "asset_id": effective_asset,
                "limit_price": str(intent.limit_price),
                "size": str(intent.size),
                "status": "PENDING",
                "filled_size": "0",
            }
            decisions.append(
                {
                    "seq": seq,
                    "ts_recv": ts_recv,
                    "action": "submit",
                    "order_id": oid,
                    "asset_id": effective_asset,
                    "side": intent.side,
                    "limit_price": str(intent.limit_price),
                    "size": str(intent.size),
                    "best_bid": book.best_bid,
                    "best_ask": book.best_ask,
                    "reason": intent.reason,
                    "meta": intent.meta,
                }
            )
            logger.debug(
                "Strategy submitted order: id=%s side=%s seq=%d", oid, intent.side, seq
            )

        elif intent.action == "cancel":
            if intent.order_id is None:
                logger.warning(
                    "OrderIntent(cancel) missing order_id at seq=%d; skipping.", seq
                )
                return
            try:
                broker.cancel_order(intent.order_id, cancel_seq=seq, cancel_ts=ts_recv)
                decisions.append(
                    {
                        "seq": seq,
                        "ts_recv": ts_recv,
                        "action": "cancel",
                        "order_id": intent.order_id,
                        "reason": intent.reason,
                        "meta": intent.meta,
                    }
                )
                logger.debug(
                    "Strategy cancelled order: id=%s seq=%d", intent.order_id, seq
                )
            except (KeyError, ValueError) as exc:
                logger.warning("Cancel failed at seq=%d: %s", seq, exc)

        else:
            logger.warning(
                "Unknown OrderIntent action %r at seq=%d; skipping.", intent.action, seq
            )

    def _write_artifacts(
        self,
        *,
        broker: SimBroker,
        timeline: list[dict],
        ledger_events: list[dict],
        equity_curve: list[dict],
        pnl_summary: dict,
        decisions: list[dict],
        warnings: list[str],
        asset_id: str,
        total_events: int,
    ) -> None:
        run_dir = self.run_dir

        def _jsonl(path: Path, rows: list) -> None:
            with open(path, "w", encoding="utf-8") as fh:
                for row in rows:
                    fh.write(json.dumps(row) + "\n")

        _jsonl(run_dir / "best_bid_ask.jsonl", timeline)
        _jsonl(run_dir / "orders.jsonl", broker.order_events)
        _jsonl(run_dir / "fills.jsonl", [f.to_dict() for f in broker.fills])
        _jsonl(run_dir / "ledger.jsonl", ledger_events)
        _jsonl(run_dir / "equity_curve.jsonl", equity_curve)
        _jsonl(run_dir / "decisions.jsonl", decisions)

        (run_dir / "summary.json").write_text(
            json.dumps(pnl_summary, indent=2) + "\n", encoding="utf-8"
        )

        run_id = run_dir.name
        manifest: dict[str, Any] = {
            "run_id": run_id,
            "command": "simtrader run",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tape_path": str(self.events_path),
            "asset_id": asset_id,
            "latency_config": {
                "submit_ticks": self.latency.submit_ticks,
                "cancel_ticks": self.latency.cancel_ticks,
            },
            "portfolio_config": {
                "starting_cash": str(self.starting_cash),
                "fee_rate_bps": (
                    str(self.fee_rate_bps)
                    if self.fee_rate_bps is not None
                    else "default(200)"
                ),
                "mark_method": self.mark_method,
            },
            "fills_count": len(broker.fills),
            "decisions_count": len(decisions),
            "timeline_rows": len(timeline),
            "net_profit": pnl_summary["net_profit"],
            "run_quality": "ok" if not warnings else "warnings",
            "warnings": warnings[:50],
        }
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        meta: dict[str, Any] = {
            "run_quality": manifest["run_quality"],
            "events_path": str(self.events_path),
            "total_events": total_events,
            "timeline_rows": len(timeline),
            "warnings": warnings[:50],
        }
        (run_dir / "meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )


# ------------------------------------------------------------------
# Open-order tracker helper (module-level for clarity)
# ------------------------------------------------------------------


def _update_open_orders(open_orders: dict[str, dict], bev: dict) -> None:
    """Update the open-order tracking dict from a single broker event."""
    oid = bev.get("order_id", "")
    evt = bev.get("event", "")

    if evt == "activated":
        if oid in open_orders:
            open_orders[oid]["status"] = "ACTIVE"

    elif evt == "fill":
        if oid in open_orders:
            remaining = bev.get("remaining", "0")
            size = open_orders[oid]["size"]
            filled = str(Decimal(size) - Decimal(str(remaining)))
            open_orders[oid]["filled_size"] = filled
            if bev.get("fill_status") == "full":
                del open_orders[oid]
            else:
                open_orders[oid]["status"] = "PARTIAL"

    elif evt == "cancelled":
        open_orders.pop(oid, None)
