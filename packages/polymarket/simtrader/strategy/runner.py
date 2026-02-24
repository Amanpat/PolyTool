"""StrategyRunner: connects tape replay to a Strategy and PortfolioLedger.

Processing order for each tape event
-------------------------------------
1. ``book.apply(event)`` for all tracked assets
2. ``strategy.on_event(...)`` → list[OrderIntent]
3. For each OrderIntent: ``broker.submit_order`` / ``broker.cancel_order``
4. ``broker.step(event, book, fill_asset_id=evt_asset)`` for all tracked assets
5. ``strategy.on_fill(...)`` for each new fill (fill_size > 0)
6. Update open-order tracking from new broker events
7. Emit timeline row on primary-asset book-affecting events

Multi-asset support
-------------------
Pass ``extra_book_asset_ids`` to track additional assets (e.g. the NO token
of a binary market).  The runner maintains one ``L2Book`` per tracked asset,
applies events to the right book, and calls ``broker.step`` with the matching
book and an asset-level fill filter so YES orders only fill against the YES
book and NO orders only fill against the NO book.

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
  opportunities.jsonl  (only if strategy exposes a non-empty ``.opportunities``)
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
_ZERO_STR = "0"


def _no_trade_ledger_snapshot(label: str, event: dict, starting_cash: Decimal) -> dict:
    """Build a synthetic ledger snapshot for a no-trade run (initial or final)."""
    return {
        "seq": event.get("seq", 0),
        "ts_recv": event.get("ts_recv", 0.0),
        "event": label,
        "order_id": "",
        "cash_usdc": str(starting_cash),
        "reserved_cash_usdc": _ZERO_STR,
        "reserved_shares": {},
        "positions": {},
        "realized_pnl": _ZERO_STR,
        "total_fees": _ZERO_STR,
    }
_ZERO = Decimal("0")
_RUN_QUALITY_OK = "ok"
_RUN_QUALITY_WARNINGS = "warnings"
_RUN_QUALITY_DEGRADED = "degraded"
_RUN_QUALITY_INVALID = "invalid"


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
        extra_book_asset_ids: Optional[list[str]] = None,
        latency: LatencyConfig = ZERO_LATENCY,
        starting_cash: Decimal = Decimal("1000"),
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = MARK_BID,
        strict: bool = False,
        allow_degraded: bool = False,
    ) -> None:
        """
        Args:
            events_path:           Path to events.jsonl tape file.
            run_dir:               Directory for all output artifacts (created if absent).
            strategy:              Strategy instance to drive.
            asset_id:              Primary asset.  Auto-detected if tape has one asset.
            extra_book_asset_ids:  Additional asset IDs to track with their own L2Books.
                                   Used for multi-leg strategies (e.g. binary arb).
                                   Orders for each asset fill against that asset's book.
            latency:               Submit / cancel latency model (default: zero ticks).
            starting_cash:         Initial USDC cash for the portfolio ledger.
            fee_rate_bps:          Taker fee rate in bps (default: 200 bps conservative).
            mark_method:           "bid" (conservative) or "midpoint".
            strict:                If True, raise on L2BookError or malformed events.
            allow_degraded:        If True, continue multi-asset runs even when
                                   required tape coverage is incomplete.
        """
        self.events_path = events_path
        self.run_dir = run_dir
        self.strategy = strategy
        self.asset_id = asset_id
        self.extra_book_asset_ids: list[str] = list(extra_book_asset_ids or [])
        self.latency = latency
        self.starting_cash = starting_cash
        self.fee_rate_bps = fee_rate_bps
        self.mark_method = mark_method
        self.strict = strict
        self.allow_degraded = allow_degraded

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
        coverage = self._validate_tape_coverage(events)
        run_quality = _RUN_QUALITY_OK

        if coverage is not None and coverage["warnings"]:
            warnings.extend(coverage["warnings"])
            run_quality = coverage["run_quality"]

        if run_quality == _RUN_QUALITY_INVALID:
            error_message = str(coverage.get("error")) if coverage else "Invalid run"
            self._write_failure_artifacts(
                warnings=warnings,
                asset_id=asset_id,
                total_events=len(events),
                error=error_message,
                tape_coverage=(coverage or {}).get("details"),
            )
            raise ValueError(error_message)

        # Build L2Books for all tracked assets
        all_books: dict[str, L2Book] = {asset_id: L2Book(asset_id, strict=self.strict)}
        for extra_id in self.extra_book_asset_ids:
            if extra_id not in all_books:
                all_books[extra_id] = L2Book(extra_id, strict=self.strict)

        broker = SimBroker(latency=self.latency)

        # Open-order tracking: keyed by order_id, plain dict values
        open_orders: dict[str, dict] = {}
        _last_order_event_idx = 0
        _last_fill_idx = 0

        timeline: list[dict] = []
        decisions: list[dict] = []

        self.strategy.on_start(asset_id, self.starting_cash)

        for event in events:
            seq: int = event.get("seq", 0)
            ts_recv: float = event.get("ts_recv", 0.0)
            evt_asset: str = event.get("asset_id", "")
            event_type: str = event.get("event_type", "")

            primary_book = all_books[asset_id]

            # 1. Update book(s).  Track which assets had book state changed.
            #
            # Schema A — legacy / single-asset:
            #   event has top-level asset_id + changes[] (or bids/asks for snapshots)
            #
            # Schema B — modern / batched (Polymarket Market Channel):
            #   event has price_changes[]; each entry carries its own asset_id and
            #   direct side/price/size fields.  There may be no top-level asset_id.
            _active_assets: set[str] = set()
            if event_type == EVENT_TYPE_PRICE_CHANGE and "price_changes" in event:
                # Modern batched format — apply each entry to the matching book.
                for entry in event.get("price_changes", []):
                    entry_asset = str(entry.get("asset_id") or "")
                    if entry_asset and entry_asset in all_books:
                        all_books[entry_asset].apply_single_delta(entry)
                        _active_assets.add(entry_asset)
            elif evt_asset in all_books:
                all_books[evt_asset].apply(event)
                _active_assets.add(evt_asset)

            event_ctx = dict(event)
            event_ctx["_best_by_asset"] = {
                aid: {"best_bid": book.best_bid, "best_ask": book.best_ask}
                for aid, book in all_books.items()
            }

            # 2. Ask strategy for intents (pass snapshot; best_bid/best_ask = primary)
            intents = self.strategy.on_event(
                event_ctx,
                seq,
                ts_recv,
                primary_book.best_bid,
                primary_book.best_ask,
                dict(open_orders),
            )

            # 3. Execute intents
            for intent in intents:
                self._execute_intent(
                    intent, seq, ts_recv, asset_id, all_books,
                    broker, open_orders, decisions,
                )

            # 4. Step broker for each active asset, with per-asset fill filter so
            #    orders only fill against their own asset's book.
            #    Activate / cancel steps inside broker.step are unfiltered and
            #    idempotent across multiple calls at the same seq.
            for step_asset in _active_assets:
                broker.step(event, all_books[step_asset], fill_asset_id=step_asset)

            # 5. Dispatch on_fill for each new fill (non-zero size only)
            new_fills = broker.fills[_last_fill_idx:]
            _last_fill_idx = len(broker.fills)
            for fill in new_fills:
                if fill.fill_size > _ZERO:
                    self.strategy.on_fill(
                        order_id=fill.order_id,
                        asset_id=fill.asset_id,
                        side=fill.side,
                        fill_price=fill.fill_price,
                        fill_size=fill.fill_size,
                        fill_status=fill.fill_status,
                        seq=fill.seq,
                        ts_recv=fill.ts_recv,
                    )

            # 6. Update open-order tracking from new broker events
            new_events = broker.order_events[_last_order_event_idx:]
            _last_order_event_idx = len(broker.order_events)
            for bev in new_events:
                _update_open_orders(open_orders, bev)

            # 7. Emit timeline row when the primary asset's book changed this tick.
            #    For modern batched events, event_type is still "price_change" which
            #    is in _BOOK_AFFECTING, so the check is symmetric with legacy format.
            if asset_id in _active_assets and event_type in _BOOK_AFFECTING:
                timeline.append(
                    {
                        "seq": seq,
                        "ts_recv": ts_recv,
                        "asset_id": asset_id,
                        "event_type": event_type,
                        "best_bid": primary_book.best_bid,
                        "best_ask": primary_book.best_ask,
                    }
                )

        self.strategy.on_finish()

        # Portfolio ledger (primary asset timeline for mark-to-market)
        ledger = PortfolioLedger(
            starting_cash=self.starting_cash,
            fee_rate_bps=self.fee_rate_bps,
            mark_method=self.mark_method,
        )
        ledger_events, equity_curve = ledger.process(broker.order_events, timeline)
        final_best_bid: Optional[float] = timeline[-1].get("best_bid") if timeline else None
        final_best_ask: Optional[float] = timeline[-1].get("best_ask") if timeline else None

        # Guarantee at least initial + final snapshots even for no-trade runs.
        # Both snapshots reflect starting state (cash=starting_cash, no positions).
        if not ledger_events:
            ledger_events = [
                _no_trade_ledger_snapshot("initial", events[0], self.starting_cash),
                _no_trade_ledger_snapshot("final", events[-1], self.starting_cash),
            ]

        run_id = self.run_dir.name
        pnl_summary = ledger.summary(run_id, final_best_bid, final_best_ask)

        # Warn when a large tape produced almost no timeline rows — this often
        # means the tape uses the modern batched price_changes[] schema that was
        # not previously supported, or it is missing a book snapshot.
        if len(events) > 5 and len(timeline) <= 1:
            warnings.append(
                f"timeline_rows={len(timeline)} despite total_events={len(events)}; "
                "check for modern price_changes[] batching, missing book snapshot, "
                "or mismatched asset_id."
            )

        if run_quality == _RUN_QUALITY_OK and warnings:
            run_quality = _RUN_QUALITY_WARNINGS

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
            run_quality=run_quality,
            tape_coverage=(coverage or {}).get("details"),
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
        ids: set[str] = set()
        for e in events:
            if e.get("asset_id"):
                ids.add(str(e["asset_id"]))
            # Modern batched format: collect asset_ids from price_changes[] entries.
            for entry in e.get("price_changes", []):
                if entry.get("asset_id"):
                    ids.add(str(entry["asset_id"]))
        # Prefer to return the primary even from a multi-asset tape when the
        # caller gave us extra_book_asset_ids — we need a primary.
        if len(ids) == 1:
            return next(iter(ids))
        if len(ids) > 1:
            raise ValueError(
                f"Tape has multiple asset_ids {sorted(ids)}. "
                "Pass asset_id to StrategyRunner."
            )
        raise ValueError("Tape has no asset_id fields.")

    def _validate_tape_coverage(self, events: list[dict]) -> Optional[dict[str, Any]]:
        required_asset_ids = self._required_strategy_asset_ids()
        if not required_asset_ids:
            return None

        seen_set: set[str] = {str(e["asset_id"]) for e in events if e.get("asset_id")}
        for e in events:
            for entry in e.get("price_changes", []):
                if entry.get("asset_id"):
                    seen_set.add(str(entry["asset_id"]))
        seen_asset_ids = sorted(seen_set)
        missing_asset_ids = [
            asset_id for asset_id in required_asset_ids if asset_id not in seen_asset_ids
        ]
        details: dict[str, Any] = {
            "strategy": "binary_complement_arb",
            "required_asset_ids": required_asset_ids,
            "seen_asset_ids": seen_asset_ids,
            "missing_asset_ids": missing_asset_ids,
            "allow_degraded": self.allow_degraded,
        }

        if not missing_asset_ids:
            details["status"] = _RUN_QUALITY_OK
            return {"run_quality": _RUN_QUALITY_OK, "warnings": [], "details": details}

        message = (
            "Tape coverage check failed for binary_complement_arb: "
            f"missing events for required asset_ids {missing_asset_ids}. "
            f"required={required_asset_ids} seen={seen_asset_ids}."
        )

        if self.allow_degraded:
            details["status"] = _RUN_QUALITY_DEGRADED
            return {
                "run_quality": _RUN_QUALITY_DEGRADED,
                "warnings": [
                    f"{message} Continuing because allow_degraded=True."
                ],
                "details": details,
            }

        details["status"] = _RUN_QUALITY_INVALID
        return {
            "run_quality": _RUN_QUALITY_INVALID,
            "warnings": [
                f"{message} Failing fast. Re-run with --allow-degraded to continue."
            ],
            "details": details,
            "error": (
                f"{message} Failing fast. Re-run with --allow-degraded to continue."
            ),
        }

    def _required_strategy_asset_ids(self) -> Optional[list[str]]:
        strategy_name = self.strategy.__class__.__name__
        if strategy_name != "BinaryComplementArb":
            return None

        yes_asset_id = getattr(self.strategy, "_yes_id", None)
        no_asset_id = getattr(self.strategy, "_no_id", None)
        if (
            not isinstance(yes_asset_id, str)
            or not yes_asset_id
            or not isinstance(no_asset_id, str)
            or not no_asset_id
        ):
            return None

        if yes_asset_id == no_asset_id:
            return [yes_asset_id]
        return [yes_asset_id, no_asset_id]

    def _execute_intent(
        self,
        intent: OrderIntent,
        seq: int,
        ts_recv: float,
        asset_id: str,
        all_books: dict[str, L2Book],
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
            # Use the book for this order's asset for the decision log bid/ask
            log_book = all_books.get(effective_asset, all_books[asset_id])
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
                    "best_bid": log_book.best_bid,
                    "best_ask": log_book.best_ask,
                    "reason": intent.reason,
                    "meta": intent.meta,
                }
            )
            logger.debug(
                "Strategy submitted order: id=%s asset=%s side=%s seq=%d",
                oid, effective_asset, intent.side, seq,
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
        run_quality: str,
        tape_coverage: Optional[dict[str, Any]],
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

        # Duck-typed strategy outputs resolved early so they're available for both
        # summary.json and run_manifest.json below.
        opportunities: list[dict] = getattr(self.strategy, "opportunities", [])
        modeled_arb_summary: dict = getattr(self.strategy, "modeled_arb_summary", {})
        rejection_counts: Optional[dict] = getattr(self.strategy, "rejection_counts", None)

        summary_payload = dict(pnl_summary)
        if run_quality != _RUN_QUALITY_OK or warnings:
            summary_payload["run_quality"] = run_quality
            summary_payload["warnings"] = warnings[:50]
        if (
            tape_coverage is not None
            and tape_coverage.get("status") in (_RUN_QUALITY_DEGRADED, _RUN_QUALITY_INVALID)
        ):
            summary_payload["tape_coverage"] = tape_coverage
        if rejection_counts is not None:
            summary_payload["strategy_debug"] = {"rejection_counts": rejection_counts}
        (run_dir / "summary.json").write_text(
            json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8"
        )

        # Strategy-specific artifacts: write opportunities.jsonl if the strategy
        # exposes a non-empty `.opportunities` list (duck-typed extension point).
        opportunities_count = 0
        if opportunities:
            _jsonl(run_dir / "opportunities.jsonl", opportunities)
            opportunities_count = len(opportunities)

        run_id = run_dir.name
        manifest: dict[str, Any] = {
            "run_id": run_id,
            "command": "simtrader run",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tape_path": str(self.events_path),
            "asset_id": asset_id,
            "extra_book_asset_ids": self.extra_book_asset_ids,
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
            "opportunities_count": opportunities_count,
            "timeline_rows": len(timeline),
            "net_profit": pnl_summary["net_profit"],
            "run_quality": run_quality,
            "warnings": warnings[:50],
        }
        if tape_coverage is not None:
            manifest["tape_coverage"] = tape_coverage
        if modeled_arb_summary:
            manifest["modeled_arb_summary"] = modeled_arb_summary
        if rejection_counts is not None:
            manifest["strategy_debug"] = {"rejection_counts": rejection_counts}
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
        if tape_coverage is not None:
            meta["tape_coverage"] = tape_coverage
        (run_dir / "meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )

    def _write_failure_artifacts(
        self,
        *,
        warnings: list[str],
        asset_id: str,
        total_events: int,
        error: str,
        tape_coverage: Optional[dict[str, Any]],
    ) -> None:
        run_dir = self.run_dir
        run_id = run_dir.name
        manifest: dict[str, Any] = {
            "run_id": run_id,
            "command": "simtrader run",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tape_path": str(self.events_path),
            "asset_id": asset_id,
            "extra_book_asset_ids": self.extra_book_asset_ids,
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
            "fills_count": 0,
            "decisions_count": 0,
            "opportunities_count": 0,
            "timeline_rows": 0,
            "net_profit": None,
            "run_quality": _RUN_QUALITY_INVALID,
            "warnings": warnings[:50],
            "error": error,
            "failed_fast": True,
        }
        if tape_coverage is not None:
            manifest["tape_coverage"] = tape_coverage
        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        meta: dict[str, Any] = {
            "run_quality": _RUN_QUALITY_INVALID,
            "events_path": str(self.events_path),
            "total_events": total_events,
            "timeline_rows": 0,
            "warnings": warnings[:50],
            "error": error,
            "failed_fast": True,
        }
        if tape_coverage is not None:
            meta["tape_coverage"] = tape_coverage
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
