"""Shadow mode runner: live WS market feed → simulated strategy execution.

Unlike ``quickrun`` (record → replay in two phases), shadow mode processes
live WS events *inline* — no tape file is required before the strategy runs:

  1. Open WS subscriptions for YES + NO tokens.
  2. Normalize each WS frame exactly as ``TapeRecorder`` does.
  3. Feed each normalized event immediately into L2Books, Strategy, and SimBroker.
  4. Optionally write ``raw_ws.jsonl`` + ``events.jsonl`` concurrently so the
     session is fully auditable and replayable.
  5. At end: call ``strategy.on_finish()``, run ``PortfolioLedger``, and write
     the full artifact set (same files as ``StrategyRunner``).

``run_manifest.json`` includes::

    "mode": "shadow"
    "shadow_context": { ... }   # slug, token IDs, selection metadata
    "run_metrics": { ... }      # ws_reconnects, ws_timeouts, events_received, …
    "exit_reason": "…"          # present only on stall/abnormal exit

Stall kill-switch
-----------------
``max_ws_stall_seconds`` (default 30): if no WS frames arrive for that many
seconds the runner exits gracefully and records ``exit_reason`` in both
``run_manifest.json`` and ``meta.json``.  All in-flight artifacts are still
written.  Set to 0 to disable.

Resilience: the WS loop reconnects and resubscribes on disconnect/timeout,
matching the behaviour of ``TapeRecorder``.

Offline testing: pass ``_event_source`` (an iterable of already-normalised
event dicts) to bypass the WS layer entirely.  ``raw_ws.jsonl`` is not written
in this mode (no raw frames exist); ``events.jsonl`` is written normally.
Use ``_stall_after_n_events`` to trigger a simulated stall exit without
waiting for real time to pass.
"""

from __future__ import annotations

import json
import logging
import signal
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Generator, Iterable, Optional

from ..broker.latency import ZERO_LATENCY, LatencyConfig
from ..broker.sim_broker import SimBroker
from ..orderbook.l2book import L2Book, L2BookError
from ..portfolio.ledger import PortfolioLedger
from ..portfolio.mark import MARK_BID
from ..strategy.base import OrderIntent, Strategy
from ..strategy.runner import (
    _ZERO,
    _no_trade_ledger_snapshot,
    _update_open_orders,
)
from ..tape.recorder import (
    DEFAULT_RECONNECT_SLEEP_SECONDS,
    DEFAULT_RECV_TIMEOUT_SECONDS,
    WS_MARKET_URL,
)
from ..tape.schema import (
    EVENT_TYPE_BOOK,
    EVENT_TYPE_PRICE_CHANGE,
    KNOWN_EVENT_TYPES,
    PARSER_VERSION,
)

logger = logging.getLogger(__name__)

_BOOK_AFFECTING = frozenset({EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE})
_RUN_QUALITY_OK = "ok"
_RUN_QUALITY_WARNINGS = "warnings"

# Sentinel labels for tape meta source field.
_SOURCE_WS = "websocket"
_SOURCE_INJECTED = "injected"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@dataclass
class _RunMetrics:
    """Counters accumulated during a shadow run.

    Attributes exposed in ``run_manifest.json["run_metrics"]``:
      ws_reconnects          Number of WS reconnections (0 in injected mode).
      ws_timeouts            Number of recv-timeout events (0 in injected mode).
      events_received        Total normalized events processed.
      batched_price_changes  Modern price_changes[] frames (one frame may carry
                             updates for multiple assets).
      per_asset_update_counts  Mapping of asset_id → book-update events applied.

    Internal (used by tape meta / reconnect logic, not in run_metrics dict):
      _ws_reconnect_warnings  Warning strings from reconnect events.
      _ws_frame_count         Raw WS frames received (including non-event frames).
    """

    ws_reconnects: int = 0
    ws_timeouts: int = 0
    events_received: int = 0
    batched_price_changes: int = 0
    per_asset_update_counts: dict[str, int] = field(default_factory=dict)

    # Internal: not surfaced in run_metrics dict.
    _ws_reconnect_warnings: list[str] = field(default_factory=list)
    _ws_frame_count: int = 0

    def increment_asset(self, asset_id: str) -> None:
        """Increment the per-asset update counter for *asset_id*."""
        self.per_asset_update_counts[asset_id] = (
            self.per_asset_update_counts.get(asset_id, 0) + 1
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the public metrics as a plain dict (for run_manifest.json)."""
        return {
            "ws_reconnects": self.ws_reconnects,
            "ws_timeouts": self.ws_timeouts,
            "events_received": self.events_received,
            "batched_price_changes": self.batched_price_changes,
            "per_asset_update_counts": dict(self.per_asset_update_counts),
        }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class ShadowRunner:
    """Run a strategy live against the Polymarket Market Channel (no real orders).

    The runner connects to the WS market feed, drives ``L2Book`` state machines
    for both the YES and NO tokens, and calls the strategy on each tick — exactly
    like ``StrategyRunner`` does during replay, but with live data.

    Args:
        run_dir:               Directory for all output artifacts (created if absent).
        asset_ids:             Token IDs to subscribe to on the WS Market Channel.
        strategy:              Strategy instance to drive.
        primary_asset_id:      The primary asset for the portfolio ledger (YES token).
        extra_book_asset_ids:  Additional assets to track (NO token).
        duration_seconds:      Stop after this many seconds.  ``None`` = run until signal.
        starting_cash:         Initial USDC cash balance.
        fee_rate_bps:          Taker fee rate in basis points (default 200 bps).
        mark_method:           "bid" or "midpoint".
        tape_dir:              If set, write ``raw_ws.jsonl``, ``events.jsonl``, and
                               ``meta.json`` here (same layout as ``TapeRecorder``).
        shadow_context:        Metadata dict embedded in ``run_manifest.json`` under
                               the ``shadow_context`` key.
        ws_url:                WebSocket endpoint URL.
        strict:                If True, raise on unexpected WS shapes / L2BookError.
        latency:               Submit / cancel latency model for SimBroker.
        max_ws_stall_seconds:  Exit gracefully if no WS events arrive for this many
                               seconds.  0 disables the stall check.  Default: 30.
        _event_source:         **For offline tests only.** Iterate this instead of WS.
                               ``raw_ws.jsonl`` is not written.
        _stall_after_n_events: **For offline tests only.** Simulate a stall exit after
                               this many events from ``_event_source``.  Requires
                               ``_event_source`` to be set.
    """

    def __init__(
        self,
        run_dir: Path,
        asset_ids: list[str],
        strategy: Strategy,
        primary_asset_id: str,
        extra_book_asset_ids: Optional[list[str]] = None,
        duration_seconds: Optional[float] = None,
        starting_cash: Decimal = Decimal("1000"),
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = MARK_BID,
        tape_dir: Optional[Path] = None,
        shadow_context: Optional[dict] = None,
        ws_url: str = WS_MARKET_URL,
        strict: bool = False,
        latency: LatencyConfig = ZERO_LATENCY,
        max_ws_stall_seconds: float = 30.0,
        _event_source: Optional[Iterable[dict]] = None,
        _stall_after_n_events: Optional[int] = None,
    ) -> None:
        self.run_dir = run_dir
        self.asset_ids = [str(a) for a in asset_ids if str(a)]
        self.strategy = strategy
        self.primary_asset_id = primary_asset_id
        self.extra_book_asset_ids = list(extra_book_asset_ids or [])
        self.duration_seconds = duration_seconds
        self.starting_cash = starting_cash
        self.fee_rate_bps = fee_rate_bps
        self.mark_method = mark_method
        self.tape_dir = tape_dir
        self.shadow_context = shadow_context or {}
        self.ws_url = ws_url
        self.strict = strict
        self.latency = latency
        self.max_ws_stall_seconds = max(0.0, float(max_ws_stall_seconds))
        self._event_source = _event_source
        self._stall_after_n_events = _stall_after_n_events

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> dict:
        """Execute shadow mode and return the PnL summary dict.

        Returns:
            Same schema as ``summary.json`` (net_profit, realized_pnl, …).
        """
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.tape_dir is not None:
            self.tape_dir.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc).isoformat()

        # Initialise L2Books for all tracked assets.
        all_books: dict[str, L2Book] = {
            self.primary_asset_id: L2Book(self.primary_asset_id, strict=self.strict)
        }
        for aid in self.extra_book_asset_ids:
            if aid not in all_books:
                all_books[aid] = L2Book(aid, strict=self.strict)

        broker = SimBroker(latency=self.latency)
        open_orders: dict[str, dict] = {}
        process_state = {"last_fill_idx": 0, "last_order_event_idx": 0}

        timeline: list[dict] = []
        decisions: list[dict] = []
        all_events: list[dict] = []
        warnings: list[str] = []

        metrics = _RunMetrics()
        stall_exit_reason: Optional[str] = None
        event_source_label = _SOURCE_INJECTED if self._event_source is not None else _SOURCE_WS

        self.strategy.on_start(self.primary_asset_id, self.starting_cash)

        # Open tape file handles if recording.
        with self._open_tape_writers() as (raw_fh, events_fh):
            if self._event_source is not None:
                # ---- Offline / test path ----------------------------------------
                stall_exit_reason = self._consume_source(
                    source=self._event_source,
                    all_books=all_books,
                    broker=broker,
                    open_orders=open_orders,
                    process_state=process_state,
                    timeline=timeline,
                    decisions=decisions,
                    all_events=all_events,
                    warnings=warnings,
                    metrics=metrics,
                    events_fh=events_fh,
                )
            else:
                # ---- Live WS path -----------------------------------------------
                stall_exit_reason = self._ws_loop(
                    all_books=all_books,
                    broker=broker,
                    open_orders=open_orders,
                    process_state=process_state,
                    timeline=timeline,
                    decisions=decisions,
                    all_events=all_events,
                    warnings=warnings,
                    metrics=metrics,
                    raw_fh=raw_fh,
                    events_fh=events_fh,
                )

        ended_at = datetime.now(timezone.utc).isoformat()

        self.strategy.on_finish()

        # Portfolio ledger.
        ledger = PortfolioLedger(
            starting_cash=self.starting_cash,
            fee_rate_bps=self.fee_rate_bps,
            mark_method=self.mark_method,
        )
        ledger_events, equity_curve = ledger.process(broker.order_events, timeline)
        final_best_bid: Optional[float] = timeline[-1].get("best_bid") if timeline else None
        final_best_ask: Optional[float] = timeline[-1].get("best_ask") if timeline else None

        # Guarantee at least initial + final ledger rows even for no-trade runs.
        if not ledger_events and all_events:
            ledger_events = [
                _no_trade_ledger_snapshot("initial", all_events[0], self.starting_cash),
                _no_trade_ledger_snapshot("final", all_events[-1], self.starting_cash),
            ]

        run_id = self.run_dir.name
        pnl_summary = ledger.summary(run_id, final_best_bid, final_best_ask)

        run_quality = _RUN_QUALITY_OK if not warnings else _RUN_QUALITY_WARNINGS

        self._write_artifacts(
            broker=broker,
            timeline=timeline,
            ledger_events=ledger_events,
            equity_curve=equity_curve,
            pnl_summary=pnl_summary,
            decisions=decisions,
            warnings=warnings,
            total_events=len(all_events),
            run_quality=run_quality,
            started_at=started_at,
            ended_at=ended_at,
            metrics=metrics,
            stall_exit_reason=stall_exit_reason,
        )

        # Write tape meta.json if recording.
        if self.tape_dir is not None:
            self._write_tape_meta(
                event_count=len(all_events),
                frame_count=metrics._ws_frame_count,
                reconnect_count=metrics.ws_reconnects,
                reconnect_warnings=metrics._ws_reconnect_warnings,
                source=event_source_label,
                started_at=started_at,
                ended_at=ended_at,
            )

        return pnl_summary

    # ------------------------------------------------------------------
    # Event consumption — injected source path
    # ------------------------------------------------------------------

    def _consume_source(
        self,
        *,
        source: Iterable[dict],
        all_books: dict[str, L2Book],
        broker: SimBroker,
        open_orders: dict[str, dict],
        process_state: dict,
        timeline: list[dict],
        decisions: list[dict],
        all_events: list[dict],
        warnings: list[str],
        metrics: _RunMetrics,
        events_fh: Any,
    ) -> Optional[str]:
        """Consume events from an injected iterable (offline / test path).

        Returns:
            Stall-exit reason string if ``_stall_after_n_events`` was reached,
            otherwise ``None``.
        """
        for i, event in enumerate(source):
            # Simulated stall: stop early and return a stall reason.
            if self._stall_after_n_events is not None and i >= self._stall_after_n_events:
                reason = (
                    f"ws_stall: no events received for "
                    f"{self.max_ws_stall_seconds:.0f}s "
                    f"(simulated after {i} events)"
                )
                logger.info(
                    "Shadow mode (injected): simulated stall triggered at event %d.", i
                )
                return reason

            if events_fh is not None:
                events_fh.write(json.dumps(event) + "\n")
                events_fh.flush()

            all_events.append(event)
            self._update_metrics_from_event(event, metrics)

            _warn = self._process_one_event(
                event, all_books, broker, open_orders,
                timeline, decisions, process_state,
            )
            if _warn:
                warnings.append(_warn)

        return None

    # ------------------------------------------------------------------
    # WS loop (live path)
    # ------------------------------------------------------------------

    def _ws_loop(
        self,
        *,
        all_books: dict[str, L2Book],
        broker: SimBroker,
        open_orders: dict[str, dict],
        process_state: dict,
        timeline: list,
        decisions: list,
        all_events: list,
        warnings: list,
        metrics: _RunMetrics,
        raw_fh: Any,
        events_fh: Any,
    ) -> Optional[str]:
        """Connect to the WS Market Channel and drive the event loop.

        Returns:
            Stall-exit reason string if the stall kill-switch fired, else ``None``.
        """
        try:
            import websocket  # type: ignore
        except ImportError as exc:
            raise ImportError(
                "websocket-client is required for shadow mode. "
                "Run: pip install 'websocket-client>=1.6'"
            ) from exc

        timeout_exc = getattr(websocket, "WebSocketTimeoutException", TimeoutError)
        closed_exc = getattr(websocket, "WebSocketConnectionClosedException", OSError)

        event_seq = 0
        deadline = (time.time() + self.duration_seconds) if self.duration_seconds else None
        stop = [False]
        stall_exit_reason: Optional[str] = None
        ws: object | None = None

        # Wall-clock time of the last successfully received frame.
        # Used for stall detection in the recv-timeout handler.
        last_frame_wall_time = time.time()

        def _on_signal(sig, frame):  # noqa: ARG001
            logger.info("Shadow mode: received signal %d — stopping.", sig)
            stop[0] = True

        signal.signal(signal.SIGINT, _on_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _on_signal)

        subscribe_msg = json.dumps(
            {
                "assets_ids": self.asset_ids,
                "type": "market",
                "custom_feature_enabled": True,
                "initial_dump": True,
            }
        )

        def _connect(*, reconnect: bool) -> object | None:
            while not stop[0]:
                if deadline and time.time() >= deadline:
                    return None
                try:
                    ws_conn = websocket.WebSocket()
                    ws_conn.connect(self.ws_url)
                    ws_conn.settimeout(DEFAULT_RECV_TIMEOUT_SECONDS)
                    ws_conn.send(subscribe_msg)
                    if reconnect:
                        metrics.ws_reconnects += 1
                        msg = (
                            f"Shadow WS reconnect #{metrics.ws_reconnects}: "
                            "connected and resubscribed."
                        )
                        metrics._ws_reconnect_warnings.append(msg)
                        logger.warning(msg)
                    else:
                        logger.info("Shadow mode connected to %s", self.ws_url)
                    return ws_conn
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Shadow WS connect failed: %s", exc)
                    if self.strict:
                        raise
                    time.sleep(DEFAULT_RECONNECT_SLEEP_SECONDS)
            return None

        def _ping(ws_conn: object) -> bool:
            try:
                ping = getattr(ws_conn, "ping", None)
                if callable(ping):
                    ping("shadow-keepalive")
                return True
            except Exception as exc:  # noqa: BLE001
                logger.warning("Shadow keepalive ping failed: %s", exc)
                if self.strict:
                    raise
                return False

        try:
            ws = _connect(reconnect=False)
            while not stop[0]:
                if deadline and time.time() >= deadline:
                    logger.info("Shadow mode: duration expired — stopping.")
                    break
                if ws is None:
                    ws = _connect(reconnect=True)
                    if ws is None:
                        break

                try:
                    raw_msg = ws.recv()
                except timeout_exc:
                    metrics.ws_timeouts += 1

                    # Stall kill-switch: exit if no frames for too long.
                    if self.max_ws_stall_seconds > 0:
                        elapsed = time.time() - last_frame_wall_time
                        if elapsed >= self.max_ws_stall_seconds:
                            stall_exit_reason = (
                                f"ws_stall: no events received for {elapsed:.1f}s "
                                f"(threshold={self.max_ws_stall_seconds}s)"
                            )
                            logger.warning(
                                "Shadow mode: %s — exiting gracefully.",
                                stall_exit_reason,
                            )
                            break

                    if ws is not None and not _ping(ws):
                        ws = _connect(reconnect=True)
                        if ws is None:
                            break
                    continue

                except closed_exc as exc:
                    msg = f"Shadow WS disconnected: {exc}"
                    logger.warning("%s", msg)
                    metrics._ws_reconnect_warnings.append(msg)
                    if ws is not None:
                        try:
                            ws.close()
                        except Exception:  # noqa: BLE001
                            pass
                    ws = _connect(reconnect=True)
                    if ws is None:
                        break
                    continue

                except OSError as exc:
                    msg = f"Shadow WS socket error: {exc}"
                    logger.warning("%s", msg)
                    metrics._ws_reconnect_warnings.append(msg)
                    if ws is not None:
                        try:
                            ws.close()
                        except Exception:  # noqa: BLE001
                            pass
                    ws = _connect(reconnect=True)
                    if ws is None:
                        break
                    continue

                ts_recv = time.time()
                last_frame_wall_time = ts_recv  # reset stall clock on each frame

                # Write raw frame if recording.
                if raw_fh is not None:
                    raw_line = {
                        "frame_seq": metrics._ws_frame_count,
                        "ts_recv": ts_recv,
                        "raw": raw_msg,
                    }
                    raw_fh.write(json.dumps(raw_line) + "\n")
                    raw_fh.flush()

                # Parse + normalize + process.
                try:
                    parsed = json.loads(raw_msg)
                    if not isinstance(parsed, list):
                        parsed = [parsed]
                    for evt in parsed:
                        normalized = self._normalize(evt, event_seq, ts_recv)
                        if normalized is None:
                            continue
                        if events_fh is not None:
                            events_fh.write(json.dumps(normalized) + "\n")
                            events_fh.flush()
                        all_events.append(normalized)
                        self._update_metrics_from_event(normalized, metrics)
                        _warn = self._process_one_event(
                            normalized, all_books, broker, open_orders,
                            timeline, decisions, process_state,
                        )
                        if _warn:
                            warnings.append(_warn)
                        event_seq += 1
                except Exception as exc:  # noqa: BLE001
                    msg = f"Shadow: failed to parse frame #{metrics._ws_frame_count}: {exc}"
                    logger.warning("%s", msg)
                    warnings.append(msg)
                    if self.strict:
                        raise

                metrics._ws_frame_count += 1

        finally:
            if ws is not None:
                try:
                    ws.close()
                except Exception:  # noqa: BLE001
                    pass

        return stall_exit_reason

    # ------------------------------------------------------------------
    # Metrics helper
    # ------------------------------------------------------------------

    @staticmethod
    def _update_metrics_from_event(event: dict, metrics: _RunMetrics) -> None:
        """Update counters from one normalized event (called by both paths)."""
        metrics.events_received += 1
        event_type = event.get("event_type", "")

        if event_type == EVENT_TYPE_PRICE_CHANGE and "price_changes" in event:
            metrics.batched_price_changes += 1
            for entry in event.get("price_changes", []):
                asset_id = str(entry.get("asset_id") or "")
                if asset_id:
                    metrics.increment_asset(asset_id)
        else:
            asset_id = event.get("asset_id", "")
            if asset_id:
                metrics.increment_asset(str(asset_id))

    # ------------------------------------------------------------------
    # Event processing (single event)
    # ------------------------------------------------------------------

    def _process_one_event(
        self,
        event: dict,
        all_books: dict[str, L2Book],
        broker: SimBroker,
        open_orders: dict[str, dict],
        timeline: list[dict],
        decisions: list[dict],
        state: dict,
    ) -> Optional[str]:
        """Apply one normalized event through books, strategy, and broker.

        Args:
            state:  Mutable dict with keys ``last_fill_idx`` and
                    ``last_order_event_idx`` (updated in-place).

        Returns:
            Warning string if a book error occurred (non-strict mode), else None.
        """
        seq: int = event.get("seq", 0)
        ts_recv: float = event.get("ts_recv", 0.0)
        evt_asset: str = event.get("asset_id", "")
        event_type: str = event.get("event_type", "")

        primary_book = all_books[self.primary_asset_id]
        _active_assets: set[str] = set()

        # 1. Update books.
        if event_type == EVENT_TYPE_PRICE_CHANGE and "price_changes" in event:
            for entry in event.get("price_changes", []):
                entry_asset = str(entry.get("asset_id") or "")
                if entry_asset and entry_asset in all_books:
                    try:
                        all_books[entry_asset].apply_single_delta(entry)
                        _active_assets.add(entry_asset)
                    except L2BookError as exc:
                        msg = f"seq={seq} asset={entry_asset} L2BookError: {exc}"
                        if self.strict:
                            raise
                        logger.warning("%s", msg)
                        return msg
        elif evt_asset in all_books:
            try:
                all_books[evt_asset].apply(event)
                _active_assets.add(evt_asset)
            except L2BookError as exc:
                msg = f"seq={seq} L2BookError: {exc}"
                if self.strict:
                    raise
                logger.warning("%s", msg)
                return msg

        # 2. Build event context (mirrors StrategyRunner).
        event_ctx = dict(event)
        event_ctx["_best_by_asset"] = {
            aid: {"best_bid": bk.best_bid, "best_ask": bk.best_ask}
            for aid, bk in all_books.items()
        }

        # 3. Ask strategy for intents.
        intents = self.strategy.on_event(
            event_ctx,
            seq,
            ts_recv,
            primary_book.best_bid,
            primary_book.best_ask,
            dict(open_orders),
        )

        # 4. Execute intents.
        for intent in intents:
            self._execute_intent(
                intent, seq, ts_recv, all_books, broker, open_orders, decisions,
            )

        # 5. Step broker for each active asset.
        for step_asset in _active_assets:
            broker.step(event, all_books[step_asset], fill_asset_id=step_asset)

        # 6. Dispatch on_fill for new fills.
        new_fills = broker.fills[state["last_fill_idx"]:]
        state["last_fill_idx"] = len(broker.fills)
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

        # 7. Update open-order tracking.
        new_broker_events = broker.order_events[state["last_order_event_idx"]:]
        state["last_order_event_idx"] = len(broker.order_events)
        for bev in new_broker_events:
            _update_open_orders(open_orders, bev)

        # 8. Emit timeline row for primary-asset book-affecting events.
        if self.primary_asset_id in _active_assets and event_type in _BOOK_AFFECTING:
            timeline.append(
                {
                    "seq": seq,
                    "ts_recv": ts_recv,
                    "asset_id": self.primary_asset_id,
                    "event_type": event_type,
                    "best_bid": primary_book.best_bid,
                    "best_ask": primary_book.best_ask,
                }
            )

        return None

    def _execute_intent(
        self,
        intent: OrderIntent,
        seq: int,
        ts_recv: float,
        all_books: dict[str, L2Book],
        broker: SimBroker,
        open_orders: dict[str, dict],
        decisions: list[dict],
    ) -> None:
        if intent.action == "submit":
            effective_asset = intent.asset_id or self.primary_asset_id
            if intent.limit_price is None or intent.size is None or intent.side is None:
                logger.warning(
                    "Shadow: OrderIntent(submit) missing fields at seq=%d; skipping.", seq
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
            log_book = all_books.get(effective_asset, all_books[self.primary_asset_id])
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

        elif intent.action == "cancel":
            if intent.order_id is None:
                logger.warning(
                    "Shadow: OrderIntent(cancel) missing order_id at seq=%d; skipping.", seq
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
            except (KeyError, ValueError) as exc:
                logger.warning("Shadow: cancel failed at seq=%d: %s", seq, exc)
        else:
            logger.warning(
                "Shadow: unknown OrderIntent action %r at seq=%d; skipping.",
                intent.action, seq,
            )

    # ------------------------------------------------------------------
    # Artifact writing
    # ------------------------------------------------------------------

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
        total_events: int,
        run_quality: str,
        started_at: str,
        ended_at: str,
        metrics: _RunMetrics,
        stall_exit_reason: Optional[str],
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

        opportunities: list[dict] = getattr(self.strategy, "opportunities", [])
        modeled_arb_summary: dict = getattr(self.strategy, "modeled_arb_summary", {})
        rejection_counts: Optional[dict] = getattr(self.strategy, "rejection_counts", None)

        opportunities_count = 0
        if opportunities:
            _jsonl(run_dir / "opportunities.jsonl", opportunities)
            opportunities_count = len(opportunities)

        summary_payload = dict(pnl_summary)
        if run_quality != _RUN_QUALITY_OK or warnings:
            summary_payload["run_quality"] = run_quality
            summary_payload["warnings"] = warnings[:50]
        if rejection_counts is not None:
            summary_payload["strategy_debug"] = {"rejection_counts": rejection_counts}
        (run_dir / "summary.json").write_text(
            json.dumps(summary_payload, indent=2) + "\n", encoding="utf-8"
        )

        run_id = run_dir.name
        manifest: dict[str, Any] = {
            "run_id": run_id,
            "mode": "shadow",
            "command": "simtrader shadow",
            "started_at": started_at,
            "ended_at": ended_at,
            "asset_id": self.primary_asset_id,
            "extra_book_asset_ids": self.extra_book_asset_ids,
            "ws_url": self.ws_url,
            "duration_seconds": self.duration_seconds,
            "max_ws_stall_seconds": self.max_ws_stall_seconds,
            "latency_config": {
                "submit_ticks": self.latency.submit_ticks,
                "cancel_ticks": self.latency.cancel_ticks,
            },
            "portfolio_config": {
                "starting_cash": str(self.starting_cash),
                "fee_rate_bps": (
                    str(self.fee_rate_bps) if self.fee_rate_bps is not None else "default(200)"
                ),
                "mark_method": self.mark_method,
            },
            "fills_count": len(broker.fills),
            "decisions_count": len(decisions),
            "opportunities_count": opportunities_count,
            "timeline_rows": len(timeline),
            "total_events": total_events,
            "net_profit": pnl_summary.get("net_profit"),
            "run_quality": run_quality,
            "warnings": warnings[:50],
            "tape_dir": str(self.tape_dir) if self.tape_dir is not None else None,
            "shadow_context": self.shadow_context,
            "run_metrics": metrics.to_dict(),
        }
        if stall_exit_reason is not None:
            manifest["exit_reason"] = stall_exit_reason
        if modeled_arb_summary:
            manifest["modeled_arb_summary"] = modeled_arb_summary
        if rejection_counts is not None:
            manifest["strategy_debug"] = {"rejection_counts": rejection_counts}

        (run_dir / "run_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

        meta: dict[str, Any] = {
            "run_quality": run_quality,
            "mode": "shadow",
            "total_events": total_events,
            "timeline_rows": len(timeline),
            "warnings": warnings[:50],
            "run_metrics": metrics.to_dict(),
        }
        if stall_exit_reason is not None:
            meta["exit_reason"] = stall_exit_reason
        (run_dir / "meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )

    def _write_tape_meta(
        self,
        *,
        event_count: int,
        frame_count: int,
        reconnect_count: int,
        reconnect_warnings: list[str],
        source: str,
        started_at: str,
        ended_at: str,
    ) -> None:
        """Write tape/meta.json (same schema as TapeRecorder output)."""
        assert self.tape_dir is not None
        meta = {
            "ws_url": self.ws_url,
            "asset_ids": self.asset_ids,
            "source": source,
            "started_at": started_at,
            "ended_at": ended_at,
            "recv_timeout_seconds": DEFAULT_RECV_TIMEOUT_SECONDS,
            "reconnect_count": reconnect_count,
            "frame_count": frame_count,
            "event_count": event_count,
            "warnings": reconnect_warnings[:200],
        }
        if isinstance(self.shadow_context, dict):
            meta["shadow_context"] = dict(self.shadow_context)
        (self.tape_dir / "meta.json").write_text(
            json.dumps(meta, indent=2) + "\n", encoding="utf-8"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @contextmanager
    def _open_tape_writers(self) -> Generator[tuple[Any, Any], None, None]:
        """Context manager that opens raw_ws.jsonl + events.jsonl if tape_dir is set."""
        if self.tape_dir is None:
            yield None, None
            return

        raw_path = self.tape_dir / "raw_ws.jsonl"
        events_path = self.tape_dir / "events.jsonl"
        with (
            open(raw_path, "w", encoding="utf-8") as raw_fh,
            open(events_path, "w", encoding="utf-8") as events_fh,
        ):
            yield raw_fh, events_fh

    @staticmethod
    def _normalize(evt: object, seq: int, ts_recv: float) -> Optional[dict]:
        """Normalize a parsed WS event into a tape-compatible event dict.

        Mirrors ``TapeRecorder._normalize`` exactly (stateless, no instance state).
        Returns ``None`` for unknown event types (or if evt is not a dict).
        """
        if not isinstance(evt, dict):
            logger.warning("Shadow: expected dict event, got %r — skipping.", type(evt))
            return None
        event_type = evt.get("event_type") or evt.get("type")
        if event_type not in KNOWN_EVENT_TYPES:
            logger.debug("Shadow: skipping unknown event_type: %r", event_type)
            return None
        return {
            "parser_version": PARSER_VERSION,
            "seq": seq,
            "ts_recv": ts_recv,
            **evt,
        }
