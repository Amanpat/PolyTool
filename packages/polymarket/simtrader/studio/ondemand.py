"""OnDemand tape-replay engine for SimTrader Studio.

Provides deterministic tape playback with manual order submission:

- ``OnDemandSession`` keeps a file-backed cursor over ``events.jsonl`` and
  rebuilds state from sparse checkpoints when the user seeks in time.
- ``OnDemandSessionManager`` is the in-memory registry used by Studio routes.

Design notes
------------
- Tape events are indexed once, then read on demand by file offset. The full
  tape payload is never loaded into RAM.
- User actions are replayable. Seeking backward preserves past actions; taking
  a new action after seeking truncates the old future and starts a new branch.
- Checkpoints are in-memory snapshots. They stay small by storing only runtime
  state needed to continue replay, not duplicated tape history.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from ..broker.latency import ZERO_LATENCY
from ..broker.rules import OrderStatus
from ..broker.sim_broker import SimBroker
from ..display_name import build_display_name
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


@dataclass(frozen=True)
class TapeIndex:
    """Sparse tape metadata for indexed event reads."""

    events_path: Path
    offsets: tuple[int, ...]
    timestamps: tuple[float, ...]
    seqs: tuple[int, ...]
    asset_ids: tuple[str, ...]

    @classmethod
    def build(cls, events_path: Path) -> "TapeIndex":
        rows: list[tuple[int, int, int, float]] = []
        asset_ids: list[str] = []
        seen_assets: set[str] = set()

        with open(events_path, "rb") as fh:
            ordinal = 0
            while True:
                offset = fh.tell()
                raw_line = fh.readline()
                if not raw_line:
                    break
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                event = json.loads(raw_line.decode("utf-8"))
                seq = int(event.get("seq", ordinal))
                ts_recv = float(event.get("ts_recv", 0.0))
                rows.append((seq, ordinal, offset, ts_recv))
                cls._collect_asset_ids(event, asset_ids, seen_assets)
                ordinal += 1

        rows.sort(key=lambda row: (row[0], row[1]))

        return cls(
            events_path=events_path,
            offsets=tuple(row[2] for row in rows),
            timestamps=tuple(row[3] for row in rows),
            seqs=tuple(row[0] for row in rows),
            asset_ids=tuple(asset_ids),
        )

    @staticmethod
    def _collect_asset_ids(event: dict, ordered: list[str], seen: set[str]) -> None:
        asset_id = event.get("asset_id")
        if asset_id and asset_id not in seen:
            ordered.append(str(asset_id))
            seen.add(str(asset_id))

        for entry in event.get("price_changes", []):
            entry_asset_id = entry.get("asset_id")
            if entry_asset_id and entry_asset_id not in seen:
                ordered.append(str(entry_asset_id))
                seen.add(str(entry_asset_id))

    def __len__(self) -> int:
        return len(self.offsets)

    @property
    def start_ts(self) -> Optional[float]:
        if not self.timestamps:
            return None
        return self.timestamps[0]

    @property
    def end_ts(self) -> Optional[float]:
        if not self.timestamps:
            return None
        return self.timestamps[-1]

    def cursor_for_timestamp(self, timestamp: float) -> int:
        """Return the replay cursor after applying all events at or before *timestamp*."""
        if not self.timestamps:
            return 0
        return bisect_right(self.timestamps, float(timestamp))


@dataclass
class _Checkpoint:
    """Sparse runtime snapshot for fast seek."""

    cursor: int
    order: int
    seq: Optional[int]
    ts_recv: Optional[float]
    last_trade_price: Optional[float]
    books: dict[str, dict[str, Any]]
    broker: dict[str, Any]
    portfolio: dict[str, Any]


class OnDemandSession:
    """Deterministic tape-playback session with manual order submission."""

    _DEFAULT_CHECKPOINT_EVERY_EVENTS = 250
    _DEFAULT_CHECKPOINT_EVERY_SECONDS = 30.0
    _DEFAULT_MAX_CHECKPOINTS = 0

    def __init__(
        self,
        tape_path: str,
        starting_cash: Decimal,
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = "bid",
        checkpoint_every_events: int = _DEFAULT_CHECKPOINT_EVERY_EVENTS,
        checkpoint_every_seconds: float = _DEFAULT_CHECKPOINT_EVERY_SECONDS,
        max_checkpoints: int = _DEFAULT_MAX_CHECKPOINTS,
    ) -> None:
        self._session_id: str = uuid.uuid4().hex[:12]
        self._started_at: str = _now_iso()
        self._tape_path: str = tape_path

        checkpoint_every_events = int(checkpoint_every_events)
        checkpoint_every_seconds = float(checkpoint_every_seconds)
        max_checkpoints = int(max_checkpoints)
        if checkpoint_every_events < 1:
            raise ValueError("checkpoint_every_events must be >= 1")
        if checkpoint_every_seconds < 0:
            raise ValueError("checkpoint_every_seconds must be >= 0")
        if max_checkpoints < 0:
            raise ValueError("max_checkpoints must be >= 0")

        events_file = Path(tape_path) / "events.jsonl"
        self._tape_index = TapeIndex.build(events_file)
        self._events_fh = open(events_file, "rb")

        self._asset_ids: list[str] = list(self._tape_index.asset_ids)

        self._starting_cash: Decimal = starting_cash
        self._fee_rate_bps: Optional[Decimal] = fee_rate_bps
        self._mark_method: str = mark_method
        self._checkpoint_every_events = checkpoint_every_events
        self._checkpoint_every_seconds = checkpoint_every_seconds
        self._max_checkpoints = max_checkpoints

        self._user_actions: list[dict[str, Any]] = []
        self._actions_by_cursor: dict[int, list[dict[str, Any]]] = {}
        self._next_action_index = 0
        self._checkpoints: list[_Checkpoint] = []
        self._next_checkpoint_order = 0
        self._activity_feed: list[dict[str, Any]] = []

        self._reset_runtime_state()
        self._capture_checkpoint(force=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def tape_path(self) -> str:
        return self._tape_path

    def close(self) -> None:
        """Release the underlying tape file handle."""
        if not self._events_fh.closed:
            self._events_fh.close()

    def step(self, n: int = 1) -> dict[str, Any]:
        """Advance the tape cursor by *n* events (or until end of tape)."""
        target_cursor = min(self._cursor + n, len(self._tape_index))
        self._drive_to_cursor(target_cursor)
        return self.get_state()

    def seek_to(self, timestamp: float) -> dict[str, Any]:
        """Jump to the replay state at *timestamp* using the nearest checkpoint."""
        target_cursor = self._tape_index.cursor_for_timestamp(timestamp)
        checkpoint = self._checkpoint_at_or_before(target_cursor)
        self._restore_checkpoint(checkpoint)
        self._drive_to_cursor(target_cursor, record_activity=False)
        self._rebuild_activity_feed()
        return self.get_state()

    def submit_order(
        self,
        asset_id: str,
        side: str,
        limit_price: Decimal,
        size: Decimal,
    ) -> tuple[str, dict[str, Any]]:
        """Submit a limit order at the current tape position."""
        current_seq, current_ts = self._current_seq_ts()
        order_id = uuid.uuid4().hex[:8]
        action = {
            "ts_wall": _now_iso(),
            "cursor": self._cursor,
            "action_index": self._next_action_index,
            "action": "submit_order",
            "params": {
                "asset_id": asset_id,
                "side": side,
                "limit_price": str(limit_price),
                "size": str(size),
                "order_id": order_id,
                "submit_seq": current_seq,
                "submit_ts": current_ts,
            },
        }
        self._next_action_index += 1
        self._record_user_action(action)
        return order_id, self.get_state()

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order."""
        current_seq, current_ts = self._current_seq_ts()
        action = {
            "ts_wall": _now_iso(),
            "cursor": self._cursor,
            "action_index": self._next_action_index,
            "action": "cancel_order",
            "params": {
                "order_id": order_id,
                "cancel_seq": current_seq,
                "cancel_ts": current_ts,
            },
        }
        self._next_action_index += 1
        self._record_user_action(action)
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        """Return a complete snapshot of the current session state."""
        bbo: dict[str, dict[str, Optional[float]]] = {}
        depth: dict[str, dict[str, list[dict[str, float]]]] = {}
        for asset_id, book in self._books.items():
            bbo[asset_id] = {"best_bid": book.best_bid, "best_ask": book.best_ask}
            depth[asset_id] = {"bids": book.top_bids(5), "asks": book.top_asks(5)}

        open_orders = [
            {
                "order_id": order.order_id,
                "asset_id": order.asset_id,
                "side": order.side,
                "limit_price": str(order.limit_price),
                "size": str(order.size),
                "filled_size": str(order.filled_size),
                "status": order.status,
            }
            for order in self._broker._orders.values()
            if not OrderStatus.is_terminal(order.status)
        ]

        recent_activity = list(self._activity_feed[-200:])

        return {
            "session_id": self._session_id,
            "cursor": self._cursor,
            "total_events": len(self._tape_index),
            "done": self._cursor >= len(self._tape_index),
            "seq": self._current_seq,
            "ts_recv": self._current_ts_recv,
            "current_time": self._current_ts_recv,
            "tape_start_ts": self._tape_index.start_ts,
            "tape_end_ts": self._tape_index.end_ts,
            "asset_ids": list(self._asset_ids),
            "bbo": bbo,
            "depth": depth,
            "last_trade_price": self._last_trade_price,
            "open_orders": open_orders,
            "activity": recent_activity,
            "activity_total": len(self._activity_feed),
            "portfolio_snapshot": self._portfolio_snapshot(),
        }

    def save_artifacts(self, session_dir: Path) -> None:
        """Write the current OnDemand session artifacts to *session_dir*."""
        session_dir.mkdir(parents=True, exist_ok=True)
        ended_at = _now_iso()

        with open(session_dir / "user_actions.jsonl", "w", encoding="utf-8") as fh:
            for action in self._user_actions:
                fh.write(json.dumps(action) + "\n")

        broker, timeline, final_best_bid, final_best_ask = self._replay_for_artifacts(
            self._cursor
        )

        with open(session_dir / "orders.jsonl", "w", encoding="utf-8") as fh:
            for event in broker.order_events:
                fh.write(json.dumps(event) + "\n")

        with open(session_dir / "fills.jsonl", "w", encoding="utf-8") as fh:
            for fill in broker.fills:
                fh.write(json.dumps(fill.to_dict()) + "\n")

        ledger = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        ledger_rows, equity_curve = ledger.process(broker.order_events, timeline)

        with open(session_dir / "ledger.jsonl", "w", encoding="utf-8") as fh:
            for row in ledger_rows:
                fh.write(json.dumps(row) + "\n")

        with open(session_dir / "equity_curve.jsonl", "w", encoding="utf-8") as fh:
            for row in equity_curve:
                fh.write(json.dumps(row) + "\n")

        summary = ledger.summary(self._session_id, final_best_bid, final_best_ask)
        manifest = {
            "session_id": self._session_id,
            "kind": "ondemand",
            "tape_path": self._tape_path,
            "started_at": self._started_at,
            "ended_at": ended_at,
            "total_events": len(self._tape_index),
            "cursor": self._cursor,
            "summary": summary,
        }
        manifest["display_name"] = build_display_name(
            kind="ondemand",
            timestamp=self._started_at,
            fallback_id=self._session_id,
        )
        with open(session_dir / "run_manifest.json", "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _reset_runtime_state(self) -> None:
        self._books: dict[str, L2Book] = {
            asset_id: L2Book(asset_id, strict=False) for asset_id in self._asset_ids
        }
        self._broker = SimBroker(latency=ZERO_LATENCY)
        self._portfolio = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        self._cursor = 0
        self._current_seq: Optional[int] = None
        self._current_ts_recv: Optional[float] = None
        self._last_trade_price: Optional[float] = None

    def _record_user_action(self, action: dict[str, Any]) -> None:
        start_index = self._broker.order_event_count
        self._apply_action_to_state(action, self._broker, self._portfolio)
        self._truncate_future_history()
        self._user_actions.append(action)
        self._actions_by_cursor.setdefault(self._cursor, []).append(action)
        self._activity_feed.append(self._user_action_activity(action))
        self._append_broker_activity(
            self._activity_feed,
            self._broker,
            start_index,
            self._cursor,
        )
        self._capture_checkpoint(force=True)

    def _truncate_future_history(self) -> None:
        self._user_actions = [
            action for action in self._user_actions if int(action["cursor"]) <= self._cursor
        ]
        rebuilt: dict[int, list[dict[str, Any]]] = {}
        for action in self._user_actions:
            rebuilt.setdefault(int(action["cursor"]), []).append(action)
        self._actions_by_cursor = rebuilt
        self._activity_feed = [
            item for item in self._activity_feed if int(item.get("cursor", 0)) <= self._cursor
        ]
        self._checkpoints = [
            checkpoint
            for checkpoint in self._checkpoints
            if checkpoint.cursor <= self._cursor
        ]
        if not self._checkpoints:
            self._capture_checkpoint(force=True)

    def _drive_to_cursor(self, target_cursor: int, record_activity: bool = True) -> None:
        target_cursor = max(0, min(target_cursor, len(self._tape_index)))
        while self._cursor < target_cursor:
            start_index = self._broker.order_event_count
            event = self._read_event(self._cursor)
            (
                self._current_seq,
                self._current_ts_recv,
                self._last_trade_price,
            ) = self._apply_event_to_state(
                event=event,
                books=self._books,
                broker=self._broker,
                portfolio=self._portfolio,
                last_trade_price=self._last_trade_price,
            )
            self._cursor += 1
            if record_activity:
                self._append_broker_activity(
                    self._activity_feed,
                    self._broker,
                    start_index,
                    self._cursor,
                )
            self._apply_actions_for_cursor(
                self._cursor,
                self._broker,
                self._portfolio,
                activity_feed=self._activity_feed if record_activity else None,
            )
            self._capture_checkpoint(force=False)

    def _apply_actions_for_cursor(
        self,
        cursor: int,
        broker: SimBroker,
        portfolio: PortfolioLedger,
        activity_feed: Optional[list[dict[str, Any]]] = None,
    ) -> None:
        for action in self._actions_by_cursor.get(cursor, []):
            start_index = broker.order_event_count
            self._apply_action_to_state(action, broker, portfolio)
            if activity_feed is not None:
                activity_feed.append(self._user_action_activity(action))
                self._append_broker_activity(activity_feed, broker, start_index, cursor)

    def _user_action_activity(self, action: dict[str, Any]) -> dict[str, Any]:
        params = dict(action.get("params", {}))
        action_type = str(action.get("action") or "")
        cursor = int(action.get("cursor", 0))
        if action_type == "submit_order":
            return {
                "kind": "user_action",
                "action": action_type,
                "cursor": cursor,
                "seq": int(params.get("submit_seq", 0)),
                "ts_recv": float(params.get("submit_ts", 0.0)),
                "order_id": str(params.get("order_id", "")),
                "asset_id": str(params.get("asset_id", "")),
                "side": str(params.get("side", "")),
                "limit_price": str(params.get("limit_price", "")),
                "size": str(params.get("size", "")),
            }
        if action_type == "cancel_order":
            return {
                "kind": "user_action",
                "action": action_type,
                "cursor": cursor,
                "seq": int(params.get("cancel_seq", 0)),
                "ts_recv": float(params.get("cancel_ts", 0.0)),
                "order_id": str(params.get("order_id", "")),
            }
        return {
            "kind": "user_action",
            "action": action_type,
            "cursor": cursor,
            "seq": 0,
            "ts_recv": 0.0,
        }

    def _broker_event_activity(
        self,
        event: dict[str, Any],
        broker: SimBroker,
        cursor: int,
    ) -> dict[str, Any]:
        order_id = str(event.get("order_id", ""))
        order = broker._orders.get(order_id)
        item: dict[str, Any] = {
            "kind": "fill" if event.get("event") == "fill" else "broker_event",
            "action": str(event.get("event", "")),
            "cursor": cursor,
            "seq": int(event.get("seq", 0)),
            "ts_recv": float(event.get("ts_recv", 0.0)),
            "order_id": order_id,
        }
        if order is not None:
            item["asset_id"] = order.asset_id
            item["side"] = order.side
            item["limit_price"] = str(order.limit_price)
            item["size"] = str(order.size)
        for key in (
            "fill_price",
            "fill_size",
            "remaining",
            "fill_status",
            "effective_seq",
            "cancel_effective_seq",
        ):
            if key in event:
                item[key] = event[key]
        because = event.get("because")
        if because:
            item["because"] = dict(because)
        reason = event.get("reject_reason")
        if reason:
            item["reason"] = reason
        return item

    def _append_broker_activity(
        self,
        activity_feed: list[dict[str, Any]],
        broker: SimBroker,
        start_index: int,
        cursor: int,
    ) -> None:
        for event in broker.order_events_since(start_index):
            activity_feed.append(self._broker_event_activity(event, broker, cursor))

    def _rebuild_activity_feed(self) -> None:
        target_cursor = max(0, min(self._cursor, len(self._tape_index)))
        books = {
            asset_id: L2Book(asset_id, strict=False) for asset_id in self._asset_ids
        }
        broker = SimBroker(latency=ZERO_LATENCY)
        portfolio = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        feed: list[dict[str, Any]] = []
        last_trade_price: Optional[float] = None

        self._apply_actions_for_cursor(0, broker, portfolio, activity_feed=feed)

        for index in range(target_cursor):
            start_index = broker.order_event_count
            event = self._read_event(index)
            _, _, last_trade_price = self._apply_event_to_state(
                event=event,
                books=books,
                broker=broker,
                portfolio=portfolio,
                last_trade_price=last_trade_price,
            )
            cursor = index + 1
            self._append_broker_activity(feed, broker, start_index, cursor)
            self._apply_actions_for_cursor(cursor, broker, portfolio, activity_feed=feed)

        self._activity_feed = feed

    def _apply_action_to_state(
        self,
        action: dict[str, Any],
        broker: SimBroker,
        portfolio: PortfolioLedger,
    ) -> None:
        params = dict(action.get("params", {}))
        start_index = broker.order_event_count
        action_type = action.get("action")

        if action_type == "submit_order":
            broker.submit_order(
                asset_id=str(params["asset_id"]),
                side=str(params["side"]),
                limit_price=Decimal(str(params["limit_price"])),
                size=Decimal(str(params["size"])),
                submit_seq=int(params.get("submit_seq", 0)),
                submit_ts=float(params.get("submit_ts", 0.0)),
                order_id=str(params["order_id"]),
            )
        elif action_type == "cancel_order":
            broker.cancel_order(
                order_id=str(params["order_id"]),
                cancel_seq=int(params.get("cancel_seq", 0)),
                cancel_ts=float(params.get("cancel_ts", 0.0)),
            )
        else:
            raise ValueError(f"unknown user action: {action_type!r}")

        self._apply_new_order_events(broker, portfolio, start_index)

    def _apply_event_to_state(
        self,
        event: dict[str, Any],
        books: dict[str, L2Book],
        broker: SimBroker,
        portfolio: PortfolioLedger,
        last_trade_price: Optional[float],
        timeline: Optional[list[dict[str, Any]]] = None,
    ) -> tuple[Optional[int], Optional[float], Optional[float]]:
        event_type = event.get("event_type", "")

        if event_type in _BOOK_AFFECTING:
            asset_id = event.get("asset_id")
            if asset_id and asset_id in books:
                books[str(asset_id)].apply(event)

        for entry in event.get("price_changes", []):
            asset_id = entry.get("asset_id")
            if asset_id and asset_id in books:
                books[str(asset_id)].apply_single_delta(entry)

        primary_book = self._primary_book_for(books)
        start_index = broker.order_event_count
        if primary_book is not None:
            broker.step(event, primary_book)
        self._apply_new_order_events(broker, portfolio, start_index)

        if event_type == EVENT_TYPE_LAST_TRADE_PRICE:
            price = event.get("price")
            if price is not None:
                try:
                    last_trade_price = float(price)
                except (TypeError, ValueError):
                    pass

        seq: Optional[int] = None
        if event.get("seq") is not None:
            seq = int(event["seq"])

        ts_recv: Optional[float] = None
        if event.get("ts_recv") is not None:
            ts_recv = float(event["ts_recv"])

        if timeline is not None and event_type in _BOOK_AFFECTING:
            timeline.append(
                {
                    "seq": seq if seq is not None else 0,
                    "ts_recv": ts_recv if ts_recv is not None else 0.0,
                    "best_bid": (
                        primary_book.best_bid if primary_book is not None else None
                    ),
                    "best_ask": (
                        primary_book.best_ask if primary_book is not None else None
                    ),
                }
            )

        return seq, ts_recv, last_trade_price

    @staticmethod
    def _apply_new_order_events(
        broker: SimBroker,
        portfolio: PortfolioLedger,
        start_index: int,
    ) -> None:
        for event in broker.order_events_since(start_index):
            portfolio.apply_order_event(event)

    def _replay_for_artifacts(
        self,
        target_cursor: int,
    ) -> tuple[SimBroker, list[dict[str, Any]], Optional[float], Optional[float]]:
        books = {
            asset_id: L2Book(asset_id, strict=False) for asset_id in self._asset_ids
        }
        broker = SimBroker(latency=ZERO_LATENCY)
        portfolio = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        timeline: list[dict[str, Any]] = []
        current_seq: Optional[int] = None
        current_ts: Optional[float] = None
        last_trade_price: Optional[float] = None

        self._apply_actions_for_cursor(0, broker, portfolio)

        for index in range(max(0, min(target_cursor, len(self._tape_index)))):
            event = self._read_event(index)
            current_seq, current_ts, last_trade_price = self._apply_event_to_state(
                event=event,
                books=books,
                broker=broker,
                portfolio=portfolio,
                last_trade_price=last_trade_price,
                timeline=timeline,
            )
            self._apply_actions_for_cursor(index + 1, broker, portfolio)

        primary_book = self._primary_book_for(books)
        final_best_bid = primary_book.best_bid if primary_book is not None else None
        final_best_ask = primary_book.best_ask if primary_book is not None else None

        return broker, timeline, final_best_bid, final_best_ask

    def _capture_checkpoint(self, force: bool) -> None:
        latest = self._checkpoint_at_or_before(self._cursor, required=False)
        if not force and latest is not None:
            if latest.cursor == self._cursor:
                return
            if self._cursor - latest.cursor < self._checkpoint_every_events:
                if (
                    latest.ts_recv is None
                    or self._current_ts_recv is None
                    or self._current_ts_recv - latest.ts_recv < self._checkpoint_every_seconds
                ):
                    return

        snapshot = _Checkpoint(
            cursor=self._cursor,
            order=self._next_checkpoint_order,
            seq=self._current_seq,
            ts_recv=self._current_ts_recv,
            last_trade_price=self._last_trade_price,
            books={
                asset_id: book.snapshot_state()
                for asset_id, book in self._books.items()
            },
            broker=self._broker.snapshot_state(include_history=False),
            portfolio=self._portfolio.snapshot_state(),
        )

        for idx, existing in enumerate(self._checkpoints):
            if existing.cursor == snapshot.cursor:
                snapshot.order = existing.order
                self._checkpoints[idx] = snapshot
                self._trim_checkpoints()
                return
            if existing.cursor > snapshot.cursor:
                self._checkpoints.insert(idx, snapshot)
                self._next_checkpoint_order += 1
                self._trim_checkpoints()
                return
        self._checkpoints.append(snapshot)
        self._next_checkpoint_order += 1
        self._trim_checkpoints()

    def _trim_checkpoints(self) -> None:
        if self._max_checkpoints == 0:
            return
        while len(self._checkpoints) > self._max_checkpoints:
            if len(self._checkpoints) <= 1:
                break
            oldest_idx = min(
                range(1, len(self._checkpoints)),
                key=lambda idx: self._checkpoints[idx].order,
            )
            self._checkpoints.pop(oldest_idx)

    def _checkpoint_at_or_before(
        self,
        cursor: int,
        required: bool = True,
    ) -> Optional[_Checkpoint]:
        candidate: Optional[_Checkpoint] = None
        for checkpoint in self._checkpoints:
            if checkpoint.cursor > cursor:
                break
            candidate = checkpoint
        if candidate is None and required:
            raise RuntimeError("no checkpoint available for replay")
        return candidate

    def _restore_checkpoint(self, checkpoint: _Checkpoint) -> None:
        self._books = {
            asset_id: L2Book(asset_id, strict=False) for asset_id in self._asset_ids
        }
        for asset_id, state in checkpoint.books.items():
            if asset_id in self._books:
                self._books[asset_id].restore_state(state)

        self._broker = SimBroker(latency=ZERO_LATENCY)
        self._broker.restore_state(checkpoint.broker)

        self._portfolio = PortfolioLedger(
            starting_cash=self._starting_cash,
            fee_rate_bps=self._fee_rate_bps,
            mark_method=self._mark_method,
        )
        self._portfolio.restore_state(checkpoint.portfolio)

        self._cursor = checkpoint.cursor
        self._current_seq = checkpoint.seq
        self._current_ts_recv = checkpoint.ts_recv
        self._last_trade_price = checkpoint.last_trade_price

    def _read_event(self, index: int) -> dict[str, Any]:
        offset = self._tape_index.offsets[index]
        self._events_fh.seek(offset)
        raw_line = self._events_fh.readline()
        if not raw_line:
            raise IndexError(f"tape event missing at index {index}")
        raw_line = raw_line.strip()
        if not raw_line:
            raise ValueError(f"blank tape line at index {index}")
        return json.loads(raw_line.decode("utf-8"))

    def _primary_book(self) -> Optional[L2Book]:
        return self._primary_book_for(self._books)

    def _primary_book_for(self, books: dict[str, L2Book]) -> Optional[L2Book]:
        if not self._asset_ids:
            return None
        return books.get(self._asset_ids[0])

    def _current_seq_ts(self) -> tuple[int, float]:
        if self._current_seq is None or self._current_ts_recv is None:
            return 0, 0.0
        return self._current_seq, self._current_ts_recv

    def _portfolio_snapshot(self) -> dict[str, Any]:
        primary_book = self._primary_book()
        final_best_bid = primary_book.best_bid if primary_book is not None else None
        final_best_ask = primary_book.best_ask if primary_book is not None else None
        return self._portfolio.summary("live", final_best_bid, final_best_ask)


class OnDemandSessionManager:
    """Thread-safe (single-threaded asyncio) in-memory session registry."""

    def __init__(self) -> None:
        self._sessions: dict[str, OnDemandSession] = {}

    def create(
        self,
        tape_path: str,
        starting_cash: Decimal,
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = "bid",
        checkpoint_every_events: int = OnDemandSession._DEFAULT_CHECKPOINT_EVERY_EVENTS,
        checkpoint_every_seconds: float = OnDemandSession._DEFAULT_CHECKPOINT_EVERY_SECONDS,
        max_checkpoints: int = OnDemandSession._DEFAULT_MAX_CHECKPOINTS,
    ) -> OnDemandSession:
        session = OnDemandSession(
            tape_path=tape_path,
            starting_cash=starting_cash,
            fee_rate_bps=fee_rate_bps,
            mark_method=mark_method,
            checkpoint_every_events=checkpoint_every_events,
            checkpoint_every_seconds=checkpoint_every_seconds,
            max_checkpoints=max_checkpoints,
        )
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> OnDemandSession:
        return self._sessions[session_id]

    def list(self) -> list[OnDemandSession]:
        return list(self._sessions.values())

    def delete(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session is not None:
            session.close()

