"""OnDemand tape-replay engine for SimTrader Studio.

Provides deterministic tape-playback with manual order submission:

- ``OnDemandSession`` — loads a recorded tape, advances cursor event-by-event,
  accepts user order submissions, and exposes a live portfolio snapshot.
- ``OnDemandSessionManager`` — in-memory registry for concurrent sessions.

Design notes
------------
- All Decimal conversions from string happen at the API boundary (app.py).
  This module receives Decimal values directly.
- PortfolioLedger is re-instantiated on every get_state() call for portfolio
  snapshot (O(events) but acceptable for manual/interactive sessions).
- SimBroker uses ZERO_LATENCY so orders submitted at the current cursor seq
  are immediately eligible for fills on the next step.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..broker.latency import ZERO_LATENCY
from ..broker.rules import OrderStatus
from ..broker.sim_broker import SimBroker
from ..orderbook.l2book import L2Book
from ..portfolio.ledger import PortfolioLedger
from ..tape.schema import (
    EVENT_TYPE_BOOK,
    EVENT_TYPE_LAST_TRADE_PRICE,
    EVENT_TYPE_PRICE_CHANGE,
)

_BOOK_AFFECTING = frozenset({EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OnDemandSession:
    """Deterministic tape-playback session with manual order submission.

    Usage::

        session = OnDemandSession(tape_path="/path/to/tape", starting_cash=Decimal("1000"))
        state = session.step(10)          # advance 10 events
        oid, state = session.submit_order("tok1", "BUY", Decimal("0.45"), Decimal("100"))
        state = session.step(5)           # advance 5 more; fills may occur
        session.save_artifacts(Path("output/session_123"))
    """

    def __init__(
        self,
        tape_path: str,
        starting_cash: Decimal,
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = "bid",
    ) -> None:
        self._session_id: str = uuid.uuid4().hex[:12]
        self._started_at: str = _now_iso()
        self._tape_path: str = tape_path

        # --- Load events ---
        events_file = Path(tape_path) / "events.jsonl"
        raw_events: list[dict] = []
        with open(events_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    raw_events.append(json.loads(line))
        # Sort by seq ascending
        self._events: list[dict] = sorted(raw_events, key=lambda e: e.get("seq", 0))

        # --- Detect asset_ids ---
        asset_id_set: list[str] = []
        seen: set[str] = set()
        for evt in self._events:
            aid = evt.get("asset_id")
            if aid and aid not in seen:
                asset_id_set.append(aid)
                seen.add(aid)
            for entry in evt.get("price_changes", []):
                a = entry.get("asset_id")
                if a and a not in seen:
                    asset_id_set.append(a)
                    seen.add(a)
        self._asset_ids: list[str] = asset_id_set

        # --- L2Books (one per asset) ---
        self._books: dict[str, L2Book] = {
            aid: L2Book(aid, strict=False) for aid in self._asset_ids
        }

        # --- Broker (zero latency for interactive use) ---
        self._broker: SimBroker = SimBroker(latency=ZERO_LATENCY)

        # --- Portfolio config ---
        self._starting_cash: Decimal = starting_cash
        self._fee_rate_bps: Optional[Decimal] = fee_rate_bps
        self._mark_method: str = mark_method

        # --- Cursor / state ---
        self._cursor: int = 0
        self._last_trade_price: Optional[float] = None
        # Timeline for PortfolioLedger: book-affecting events (primary asset)
        self._timeline: list[dict] = []
        # Wall-clock log of user actions
        self._user_actions: list[dict] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    def step(self, n: int = 1) -> dict:
        """Advance the tape cursor by *n* events (or until end of tape).

        For each event:
        1. Apply to relevant L2Book(s).
        2. Call broker.step() so pending orders can activate/fill/cancel.
        3. Track last_trade_price.
        4. Append timeline entry for book-affecting events.

        Returns the updated state dict.
        """
        end = min(self._cursor + n, len(self._events))
        primary_book = self._primary_book()

        for i in range(self._cursor, end):
            evt = self._events[i]
            event_type = evt.get("event_type", "")

            # Apply book updates
            if event_type == EVENT_TYPE_BOOK or event_type == EVENT_TYPE_PRICE_CHANGE:
                aid = evt.get("asset_id")
                if aid and aid in self._books:
                    self._books[aid].apply(evt)

            # Modern batched price_changes[] format
            for entry in evt.get("price_changes", []):
                aid = entry.get("asset_id")
                if aid and aid in self._books:
                    self._books[aid].apply_single_delta(entry)

            # Broker step (primary book for fill decisions)
            self._broker.step(evt, primary_book)

            # Track last trade price
            if event_type == EVENT_TYPE_LAST_TRADE_PRICE:
                ltp = evt.get("price")
                if ltp is not None:
                    try:
                        self._last_trade_price = float(ltp)
                    except (TypeError, ValueError):
                        pass

            # Timeline row for book-affecting events
            if event_type in _BOOK_AFFECTING:
                seq = evt.get("seq", 0)
                ts_recv = evt.get("ts_recv", 0.0)
                self._timeline.append(
                    {
                        "seq": seq,
                        "ts_recv": ts_recv,
                        "best_bid": primary_book.best_bid if primary_book is not None else None,
                        "best_ask": primary_book.best_ask if primary_book is not None else None,
                    }
                )

        self._cursor = end
        return self.get_state()

    def submit_order(
        self,
        asset_id: str,
        side: str,
        limit_price: Decimal,
        size: Decimal,
    ) -> tuple[str, dict]:
        """Submit a limit order at the current tape position.

        The order is submitted at the most recently processed seq (or seq=0
        if the cursor has not advanced yet).  With ZERO_LATENCY the order is
        immediately eligible for fills on the next step().

        Returns:
            (order_id, state_dict)
        """
        current_seq, current_ts = self._current_seq_ts()
        order_id = self._broker.submit_order(
            asset_id=asset_id,
            side=side,
            limit_price=limit_price,
            size=size,
            submit_seq=current_seq,
            submit_ts=current_ts,
        )
        self._user_actions.append(
            {
                "ts_wall": _now_iso(),
                "action": "submit_order",
                "params": {
                    "asset_id": asset_id,
                    "side": side,
                    "limit_price": str(limit_price),
                    "size": str(size),
                    "order_id": order_id,
                },
            }
        )
        return order_id, self.get_state()

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an open order.

        Raises:
            KeyError:   order_id not found.
            ValueError: order is already terminal.
        """
        current_seq, current_ts = self._current_seq_ts()
        self._broker.cancel_order(
            order_id=order_id,
            cancel_seq=current_seq,
            cancel_ts=current_ts,
        )
        self._user_actions.append(
            {
                "ts_wall": _now_iso(),
                "action": "cancel_order",
                "params": {"order_id": order_id},
            }
        )
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        """Return a complete snapshot of the current session state."""
        # Current event (last processed, index cursor-1)
        current_evt: Optional[dict] = None
        if self._cursor > 0:
            current_evt = self._events[self._cursor - 1]

        # BBO and depth per asset
        bbo: dict[str, dict] = {}
        depth: dict[str, dict] = {}
        for aid, book in self._books.items():
            bbo[aid] = {"best_bid": book.best_bid, "best_ask": book.best_ask}
            depth[aid] = {"bids": book.top_bids(5), "asks": book.top_asks(5)}

        # Open orders
        open_orders = [
            {
                "order_id": o.order_id,
                "asset_id": o.asset_id,
                "side": o.side,
                "limit_price": str(o.limit_price),
                "size": str(o.size),
                "filled_size": str(o.filled_size),
                "status": o.status,
            }
            for o in self._broker._orders.values()
            if not OrderStatus.is_terminal(o.status)
        ]

        return {
            "session_id": self._session_id,
            "cursor": self._cursor,
            "total_events": len(self._events),
            "done": self._cursor >= len(self._events),
            "seq": current_evt["seq"] if current_evt is not None else None,
            "ts_recv": current_evt["ts_recv"] if current_evt is not None else None,
            "bbo": bbo,
            "depth": depth,
            "last_trade_price": self._last_trade_price,
            "open_orders": open_orders,
            "portfolio_snapshot": self._portfolio_snapshot(),
        }

    def save_artifacts(self, session_dir: Path) -> None:
        """Write 6 artifact files to *session_dir*.

        Files written:
        1. user_actions.jsonl
        2. orders.jsonl
        3. fills.jsonl
        4. ledger.jsonl
        5. equity_curve.jsonl
        6. run_manifest.json
        """
        session_dir.mkdir(parents=True, exist_ok=True)
        ended_at = _now_iso()

        # 1. user_actions.jsonl
        with open(session_dir / "user_actions.jsonl", "w", encoding="utf-8") as fh:
            for action in self._user_actions:
                fh.write(json.dumps(action) + "\n")

        # 2. orders.jsonl
        with open(session_dir / "orders.jsonl", "w", encoding="utf-8") as fh:
            for evt in self._broker.order_events:
                fh.write(json.dumps(evt) + "\n")

        # 3. fills.jsonl
        with open(session_dir / "fills.jsonl", "w", encoding="utf-8") as fh:
            for fill in self._broker.fills:
                fh.write(json.dumps(fill.to_dict()) + "\n")

        # 4 & 5. ledger.jsonl + equity_curve.jsonl (via PortfolioLedger)
        ledger = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        ledger_rows, equity_curve = ledger.process(
            self._broker.order_events, self._timeline
        )

        with open(session_dir / "ledger.jsonl", "w", encoding="utf-8") as fh:
            for row in ledger_rows:
                fh.write(json.dumps(row) + "\n")

        with open(session_dir / "equity_curve.jsonl", "w", encoding="utf-8") as fh:
            for row in equity_curve:
                fh.write(json.dumps(row) + "\n")

        # Summary for manifest
        primary_book = self._primary_book()
        final_best_bid = primary_book.best_bid if primary_book is not None else None
        final_best_ask = primary_book.best_ask if primary_book is not None else None
        summary = ledger.summary(self._session_id, final_best_bid, final_best_ask)

        # 6. run_manifest.json
        manifest = {
            "session_id": self._session_id,
            "tape_path": self._tape_path,
            "started_at": self._started_at,
            "ended_at": ended_at,
            "total_events": len(self._events),
            "cursor": self._cursor,
            "summary": summary,
        }
        with open(session_dir / "run_manifest.json", "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _primary_book(self) -> Optional[L2Book]:
        """Return the L2Book for the first (primary) asset, or None."""
        if not self._asset_ids:
            return None
        return self._books[self._asset_ids[0]]

    def _current_seq_ts(self) -> tuple[int, float]:
        """Return (seq, ts_recv) of the most recently processed event."""
        if self._cursor > 0:
            evt = self._events[self._cursor - 1]
            return int(evt.get("seq", 0)), float(evt.get("ts_recv", 0.0))
        return 0, 0.0

    def _portfolio_snapshot(self) -> dict[str, Any]:
        """Compute a live portfolio snapshot via a fresh PortfolioLedger."""
        primary_book = self._primary_book()
        final_best_bid = primary_book.best_bid if primary_book is not None else None
        final_best_ask = primary_book.best_ask if primary_book is not None else None

        ledger = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        ledger.process(self._broker.order_events, self._timeline)
        return ledger.summary("live", final_best_bid, final_best_ask)


class OnDemandSessionManager:
    """Thread-safe (single-threaded asyncio) in-memory session registry.

    Sessions are identified by a 12-character hex ID generated at creation.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, OnDemandSession] = {}

    def create(
        self,
        tape_path: str,
        starting_cash: Decimal,
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = "bid",
    ) -> OnDemandSession:
        """Create a new session and register it."""
        session = OnDemandSession(
            tape_path=tape_path,
            starting_cash=starting_cash,
            fee_rate_bps=fee_rate_bps,
            mark_method=mark_method,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> OnDemandSession:
        """Return the session for *session_id*.

        Raises:
            KeyError: session not found.
        """
        return self._sessions[session_id]

    def delete(self, session_id: str) -> None:
        """Remove a session (no error if not found)."""
        self._sessions.pop(session_id, None)
