"""PortfolioLedger: deterministic cash/position/PnL tracker for SimTrader.

Design invariants
-----------------
1. **All monetary values use Decimal** — never float.  Conversion from broker
   event strings happens at the boundary; everything else stays Decimal.
2. **FIFO cost basis** — lots are consumed oldest-first when closing a long.
3. **Conservative reservation model** — when a BUY order is submitted, the
   maximum possible cost (``limit_price × size``) is reserved from cash.  If
   the actual fill price is lower, the difference is immediately returned.
4. **Reserve-then-release** — reserved cash/shares are released only when a
   fill or cancel *becomes effective* (i.e. when the broker emits the event).
5. **Fees are Decimal** — computed via :func:`.fees.compute_fill_fee` so the
   ledger totals are byte-reproducible across runs.
6. **Gross realized PnL is pre-fee** — fees are tracked separately in
   ``total_fees``; ``net_profit = realized_pnl + unrealized_pnl − total_fees``.

Usage
-----
Post-process a completed broker replay::

    from packages.polymarket.simtrader.portfolio.ledger import PortfolioLedger

    ledger = PortfolioLedger(starting_cash=Decimal("1000"))
    ledger_events, equity_curve = ledger.process(
        broker.order_events,   # list[dict] from SimBroker
        timeline,              # [{seq, ts_recv, best_bid, best_ask}, ...]
    )
    summary = ledger.summary(run_id, final_best_bid, final_best_ask)

All three outputs are serialisable with ``json.dumps``.

Artifact schemas
----------------
**ledger.jsonl** (one row per order lifecycle event)::

    {
      "seq": 42, "ts_recv": 1708620001.3,
      "event": "fill", "order_id": "abc123",
      "cash_usdc": "958.999",
      "reserved_cash_usdc": "21.000",
      "reserved_shares": {},
      "positions": {
        "<asset_id>": {"total_size": "50", "avg_cost": "0.42",
                       "lots": [{"size": "50", "cost": "0.42"}]}
      },
      "realized_pnl": "0",
      "total_fees": "0.001"
    }

**equity_curve.jsonl** (one row per book-affecting event)::

    {
      "seq": 42, "ts_recv": 1708620001.3,
      "cash_usdc": "958.999",
      "reserved_cash_usdc": "21.000",
      "position_mark_value": "21.000",
      "unrealized_pnl": "0",
      "realized_pnl": "0",
      "total_fees": "0.001",
      "equity": "1000.999",
      "mark_method": "bid",
      "best_bid": "0.42", "best_ask": "0.43"
    }

**summary.json**::

    {
      "run_id": "...", "starting_cash": "1000",
      "final_cash": "1003", "final_equity": "1003",
      "realized_pnl": "3", "unrealized_pnl": "0",
      "total_fees": "0.002", "net_profit": "2.998",
      "mark_method": "bid", "fee_rate_bps": "200"
    }
"""

from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional

from .fees import DEFAULT_FEE_RATE_BPS, compute_fill_fee
from .mark import MARK_BID, mark_price

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")

# Broker event type constants (must match sim_broker._append_event calls)
_EVT_SUBMITTED = "submitted"
_EVT_ACTIVATED = "activated"
_EVT_FILL = "fill"
_EVT_CANCEL_SUBMITTED = "cancel_submitted"
_EVT_CANCELLED = "cancelled"

_SIDE_BUY = "BUY"
_SIDE_SELL = "SELL"


class PortfolioLedger:
    """Deterministic portfolio ledger for a SimTrader replay run.

    Instantiate with a starting cash balance, then call :meth:`process` with
    the broker's accumulated order events and the book-state timeline.

    Thread-safety: not thread-safe; designed for single-threaded post-processing.
    """

    def __init__(
        self,
        starting_cash: Decimal,
        fee_rate_bps: Optional[Decimal] = None,
        mark_method: str = MARK_BID,
    ) -> None:
        """
        Args:
            starting_cash: Initial USDC balance.
            fee_rate_bps:  Taker fee rate in basis points.  Pass ``None`` to
                           apply the conservative default (200 bps).
            mark_method:   Mark-price method: ``"bid"`` (default, conservative)
                           or ``"midpoint"``.
        """
        if starting_cash < _ZERO:
            raise ValueError(f"starting_cash must be non-negative; got {starting_cash}")

        self._starting_cash: Decimal = starting_cash
        self._cash: Decimal = starting_cash  # available (unreserved) USDC
        self._fee_rate_bps: Optional[Decimal] = fee_rate_bps
        self._mark_method: str = mark_method

        # FIFO lots per asset: asset_id → [(size, cost_per_share), ...]
        # Cost basis = fill_price at time of purchase (fees tracked separately).
        self._lots: dict[str, list[tuple[Decimal, Decimal]]] = defaultdict(list)

        # Reservations for open orders
        # order_id → USDC reserved (for BUY orders)
        self._reserved_cash: dict[str, Decimal] = {}
        # order_id → (asset_id, qty) reserved (for SELL orders)
        self._reserved_shares: dict[str, tuple[str, Decimal]] = {}

        # Order metadata needed for future events
        # order_id → (side, asset_id, limit_price, size)
        self._order_meta: dict[str, tuple[str, str, Decimal, Decimal]] = {}

        # Running totals
        self._realized_pnl: Decimal = _ZERO
        self._total_fees: Decimal = _ZERO

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        order_events: list[dict],
        timeline: list[dict],
    ) -> tuple[list[dict], list[dict]]:
        """Process broker order events and book timeline to build artifacts.

        Events at the same ``seq`` are processed in this order:
          1. Broker order events (fills update state before equity is sampled).
          2. Book timeline entry (equity curve row emitted with updated state).

        Args:
            order_events: ``broker.order_events`` from :class:`SimBroker`.
                          Each dict must have ``event``, ``order_id``, ``seq``,
                          ``ts_recv`` plus event-specific fields.
            timeline:     Book-state rows, each with ``seq``, ``ts_recv``,
                          ``best_bid``, and ``best_ask``.

        Returns:
            ``(ledger_snapshots, equity_curve)`` — both are lists of
            JSON-serialisable dicts suitable for writing as ``.jsonl``.
        """
        # Group order events by seq (preserve original order within same seq)
        oe_by_seq: dict[int, list[dict]] = defaultdict(list)
        for evt in order_events:
            oe_by_seq[int(evt["seq"])].append(evt)

        # Timeline is keyed by seq; last entry wins if duplicates exist
        tl_by_seq: dict[int, dict] = {}
        for row in timeline:
            tl_by_seq[int(row["seq"])] = row

        all_seqs = sorted(set(list(oe_by_seq.keys()) + list(tl_by_seq.keys())))

        ledger_snapshots: list[dict] = []
        equity_curve: list[dict] = []

        for seq in all_seqs:
            # 1. Process all broker order events at this seq
            for evt in oe_by_seq.get(seq, []):
                snapshot = self._process_order_event(evt)
                if snapshot is not None:
                    ledger_snapshots.append(snapshot)

            # 2. Emit equity curve row if we have book data at this seq
            if seq in tl_by_seq:
                tl_row = tl_by_seq[seq]
                equity_curve.append(
                    self._equity_snapshot(
                        seq,
                        tl_row["ts_recv"],
                        tl_row.get("best_bid"),
                        tl_row.get("best_ask"),
                    )
                )

        return ledger_snapshots, equity_curve

    def summary(
        self,
        run_id: str,
        final_best_bid: Optional[float],
        final_best_ask: Optional[float],
    ) -> dict[str, Any]:
        """Compute the end-of-run summary dict.

        ``net_profit = realized_pnl + unrealized_pnl − total_fees``

        Open positions are marked at the final book state using the configured
        :attr:`mark_method`.  If book data is unavailable, unrealized PnL is
        reported as ``"0"`` and open positions are listed without a mark price.
        """
        reserved_cash_total = sum(self._reserved_cash.values())

        position_mark_value = _ZERO
        unrealized_pnl = _ZERO
        open_positions: dict[str, dict] = {}

        for asset_id, lots in self._lots.items():
            if not lots:
                continue
            total_size = sum(s for s, _ in lots)
            if total_size <= _ZERO:
                continue
            avg_cost = sum(s * c for s, c in lots) / total_size

            mp = mark_price(_SIDE_BUY, final_best_bid, final_best_ask, self._mark_method)
            if mp is not None:
                position_mark_value += total_size * mp
                unrealized_pnl += total_size * (mp - avg_cost)

            open_positions[asset_id] = {
                "total_size": str(total_size),
                "avg_cost": str(avg_cost),
                "mark_price": str(mp) if mp is not None else None,
            }

        final_equity = self._cash + reserved_cash_total + position_mark_value
        net_profit = self._realized_pnl + unrealized_pnl - self._total_fees
        effective_fee_rate = (
            self._fee_rate_bps
            if self._fee_rate_bps is not None
            else DEFAULT_FEE_RATE_BPS
        )

        return {
            "run_id": run_id,
            "starting_cash": str(self._starting_cash),
            "final_cash": str(self._cash),
            "reserved_cash": str(reserved_cash_total),
            "position_mark_value": str(position_mark_value),
            "final_equity": str(final_equity),
            "realized_pnl": str(self._realized_pnl),
            "unrealized_pnl": str(unrealized_pnl),
            "total_fees": str(self._total_fees),
            "net_profit": str(net_profit),
            "open_positions": open_positions,
            "mark_method": self._mark_method,
            "fee_rate_bps": str(effective_fee_rate),
        }

    # ------------------------------------------------------------------
    # Internal: order event processing
    # ------------------------------------------------------------------

    def _process_order_event(self, evt: dict) -> Optional[dict]:
        """Dispatch one broker order event and return a ledger snapshot or None."""
        event_type = evt.get("event")
        order_id: str = evt["order_id"]
        seq: int = int(evt["seq"])
        ts_recv: float = evt["ts_recv"]

        if event_type == _EVT_SUBMITTED:
            return self._on_submitted(order_id, seq, ts_recv, evt)

        if event_type == _EVT_ACTIVATED:
            # No cash/position effect; skip snapshot to keep ledger.jsonl compact
            return None

        if event_type == _EVT_FILL:
            return self._on_fill(order_id, seq, ts_recv, evt)

        if event_type == _EVT_CANCELLED:
            return self._on_cancelled(order_id, seq, ts_recv, evt)

        if event_type == _EVT_CANCEL_SUBMITTED:
            # Cancel latency: reservation release happens at "cancelled" event
            return None

        logger.debug("Unknown broker event type %r — skipping", event_type)
        return None

    def _on_submitted(
        self, order_id: str, seq: int, ts_recv: float, evt: dict
    ) -> dict:
        side: str = evt["side"]
        asset_id: str = evt["asset_id"]
        limit_price = Decimal(evt["limit_price"])
        size = Decimal(evt["size"])

        self._order_meta[order_id] = (side, asset_id, limit_price, size)

        if side == _SIDE_BUY:
            reserve = limit_price * size
            if reserve > self._cash:
                logger.warning(
                    "Insufficient cash to fully reserve BUY order %s: "
                    "need %s, have %s — reserving available cash",
                    order_id, reserve, self._cash,
                )
                reserve = self._cash
            self._cash -= reserve
            self._reserved_cash[order_id] = reserve

        elif side == _SIDE_SELL:
            pos_size = self._position_size(asset_id)
            if size > pos_size:
                logger.warning(
                    "Insufficient position to reserve SELL order %s: "
                    "need %s shares, have %s — reserving available",
                    order_id, size, pos_size,
                )
                reserve = pos_size
            else:
                reserve = size
            self._reserved_shares[order_id] = (asset_id, reserve)

        return self._ledger_snapshot(seq, ts_recv, "order_submitted", order_id)

    def _on_fill(
        self, order_id: str, seq: int, ts_recv: float, evt: dict
    ) -> Optional[dict]:
        meta = self._order_meta.get(order_id)
        if meta is None:
            logger.error("Fill received for unknown order %s — skipping", order_id)
            return None

        side, asset_id, limit_price, _ = meta
        fill_price = Decimal(evt["fill_price"])
        fill_size = Decimal(evt["fill_size"])
        remaining = Decimal(evt["remaining"])

        fee = compute_fill_fee(fill_size, fill_price, self._fee_rate_bps)
        self._total_fees += fee

        if side == _SIDE_BUY:
            # Release the slice of the reservation that covers this fill
            reserved_for_fill = limit_price * fill_size
            current_reserved = self._reserved_cash.get(order_id, _ZERO)
            actual_release = min(reserved_for_fill, current_reserved)
            self._reserved_cash[order_id] = current_reserved - actual_release

            # Spend actual cost; return any excess from the reservation
            actual_cost = fill_price * fill_size + fee
            excess = actual_release - actual_cost
            if excess > _ZERO:
                self._cash += excess
            elif excess < _ZERO:
                # Fill price + fee exceeded the reserved slice (shouldn't happen
                # if fill_price <= limit_price and fee is small)
                self._cash += excess  # cash goes negative; log a warning
                logger.warning(
                    "BUY fill cost exceeded reservation for order %s "
                    "(excess=%s) — cash may be negative",
                    order_id, excess,
                )

            # Add FIFO lot; cost basis = fill_price (fees tracked separately)
            self._lots[asset_id].append((fill_size, fill_price))

            if remaining <= _ZERO:
                self._reserved_cash.pop(order_id, None)

        elif side == _SIDE_SELL:
            # Release the corresponding reserved shares
            reserved_entry = self._reserved_shares.get(order_id)
            if reserved_entry is not None:
                res_asset, res_qty = reserved_entry
                new_qty = res_qty - fill_size
                if new_qty <= _ZERO:
                    self._reserved_shares.pop(order_id, None)
                else:
                    self._reserved_shares[order_id] = (res_asset, new_qty)

            # Receive proceeds (fee deducted from proceeds, not added to cost)
            proceeds = fill_price * fill_size - fee
            self._cash += proceeds

            # FIFO: consume lots and accumulate gross realized PnL
            gross_pnl = self._consume_lots(asset_id, fill_size, fill_price)
            self._realized_pnl += gross_pnl

            if remaining <= _ZERO:
                self._reserved_shares.pop(order_id, None)

        return self._ledger_snapshot(seq, ts_recv, "fill", order_id)

    def _on_cancelled(
        self, order_id: str, seq: int, ts_recv: float, evt: dict
    ) -> Optional[dict]:
        meta = self._order_meta.get(order_id)
        if meta is None:
            logger.error("Cancel received for unknown order %s — skipping", order_id)
            return None

        side, asset_id, limit_price, _ = meta

        if side == _SIDE_BUY:
            # Return any remaining reservation to available cash
            remaining_reserved = self._reserved_cash.pop(order_id, _ZERO)
            self._cash += remaining_reserved

        elif side == _SIDE_SELL:
            # Shares return to freely tradeable position
            self._reserved_shares.pop(order_id, None)

        return self._ledger_snapshot(seq, ts_recv, "cancelled", order_id)

    # ------------------------------------------------------------------
    # Internal: helpers
    # ------------------------------------------------------------------

    def _position_size(self, asset_id: str) -> Decimal:
        """Total shares in FIFO lots for *asset_id* (includes reserved shares)."""
        return sum(size for size, _ in self._lots.get(asset_id, []))

    def _consume_lots(
        self,
        asset_id: str,
        sell_size: Decimal,
        sell_price: Decimal,
    ) -> Decimal:
        """Consume FIFO lots for a SELL and return gross realized PnL (pre-fee).

        Gross PnL = sum over consumed lots of (sell_price − lot_cost) × qty.
        """
        lots = self._lots[asset_id]
        remaining = sell_size
        realized = _ZERO

        while remaining > _ZERO and lots:
            lot_size, lot_cost = lots[0]
            consume = min(lot_size, remaining)
            realized += consume * (sell_price - lot_cost)
            remaining -= consume
            if consume < lot_size:
                lots[0] = (lot_size - consume, lot_cost)
            else:
                lots.pop(0)

        if remaining > _ZERO:
            logger.warning(
                "SELL of %s %s exceeded position (%s over) — PnL may be incorrect",
                sell_size, asset_id, remaining,
            )

        return realized

    # ------------------------------------------------------------------
    # Internal: snapshot builders
    # ------------------------------------------------------------------

    def _ledger_snapshot(
        self, seq: int, ts_recv: float, event: str, order_id: str
    ) -> dict:
        """Build a ledger balance snapshot dict."""
        reserved_cash_total = sum(self._reserved_cash.values())

        positions: dict[str, dict] = {}
        for asset_id, lots in self._lots.items():
            if not lots:
                continue
            total_size = sum(s for s, _ in lots)
            if total_size <= _ZERO:
                continue
            avg_cost = sum(s * c for s, c in lots) / total_size
            positions[asset_id] = {
                "total_size": str(total_size),
                "avg_cost": str(avg_cost),
                "lots": [{"size": str(s), "cost": str(c)} for s, c in lots],
            }

        reserved_shares_info = {
            oid: {"asset_id": v[0], "qty": str(v[1])}
            for oid, v in self._reserved_shares.items()
        }

        return {
            "seq": seq,
            "ts_recv": ts_recv,
            "event": event,
            "order_id": order_id,
            "cash_usdc": str(self._cash),
            "reserved_cash_usdc": str(reserved_cash_total),
            "reserved_shares": reserved_shares_info,
            "positions": positions,
            "realized_pnl": str(self._realized_pnl),
            "total_fees": str(self._total_fees),
        }

    def _equity_snapshot(
        self,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
    ) -> dict:
        """Build an equity curve row using current ledger state + book prices.

        Note: in a single-asset trade the same ``best_bid``/``best_ask`` applies
        to all positions.  Multi-asset support would require per-asset book state.
        """
        reserved_cash_total = sum(self._reserved_cash.values())

        position_mark_value = _ZERO
        unrealized_pnl = _ZERO

        for asset_id, lots in self._lots.items():
            if not lots:
                continue
            total_size = sum(s for s, _ in lots)
            if total_size <= _ZERO:
                continue
            avg_cost = sum(s * c for s, c in lots) / total_size

            mp = mark_price(_SIDE_BUY, best_bid, best_ask, self._mark_method)
            if mp is None:
                continue
            position_mark_value += total_size * mp
            unrealized_pnl += total_size * (mp - avg_cost)

        equity = self._cash + reserved_cash_total + position_mark_value

        return {
            "seq": seq,
            "ts_recv": ts_recv,
            "cash_usdc": str(self._cash),
            "reserved_cash_usdc": str(reserved_cash_total),
            "position_mark_value": str(position_mark_value),
            "unrealized_pnl": str(unrealized_pnl),
            "realized_pnl": str(self._realized_pnl),
            "total_fees": str(self._total_fees),
            "equity": str(equity),
            "mark_method": self._mark_method,
            "best_bid": str(best_bid) if best_bid is not None else None,
            "best_ask": str(best_ask) if best_ask is not None else None,
        }
