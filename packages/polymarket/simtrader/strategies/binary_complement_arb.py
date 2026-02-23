"""Binary complement arb strategy for a single YES/NO binary market.

Theory of operation
-------------------
On a Polymarket binary market, YES and NO shares should sum to $1.00 at
settlement (one of them pays $1.00, the other pays $0.00; total is always
$1.00 per pair regardless of outcome).  If the combined best-ask is below
$1.00 by at least *buffer*, a theoretical risk-free arbitrage exists:

    profit_per_share ≈ 1.00 − ask_yes − ask_no − fees

This strategy detects such conditions and attempts two simultaneous BUY orders.

────────────────────────────────────────────────────────────────────────────
ASSUMPTION (merge_full_set) — clearly labeled in all output artifacts
────────────────────────────────────────────────────────────────────────────
The modeled "merge_full_set" operation treats 1 YES share + 1 NO share as
redeemable for exactly $1.00 USDC at settlement.  This is a SIMULATION
ASSUMPTION only.  Actual on-chain settlement timing, partial-resolution
scenarios, and edge cases are NOT modelled or validated here.

All opportunity log records containing modeled values carry the key
``"ASSUMPTION"`` with an explicit disclaimer string.
────────────────────────────────────────────────────────────────────────────

Legging policies
----------------
``wait_N_then_unwind`` (default)
    Wait *unwind_wait_ticks* tape events after submitting both legs.
    At the deadline, if both legs are not fully filled, cancel any unfilled
    leg and (if the other leg already got shares) submit a SELL at best_bid
    to unwind the filled position.

``immediate_unwind``
    As soon as ONE leg's fill is confirmed, start counting.  If the other
    leg does not fill within *unwind_wait_ticks* events, cancel it and sell
    any acquired shares of the filled leg.

Artifacts written by the runner
--------------------------------
``opportunities.jsonl``
    One JSON line per state-transition event per arb attempt.

``run_manifest.json`` field ``modeled_arb_summary``
    Aggregate counts and totals across all attempts.

Note on PortfolioLedger mark-to-market
---------------------------------------
The runner's ``timeline`` (used by PortfolioLedger for unrealized PnL) only
contains primary-asset (YES) prices.  NO positions will therefore be marked
at YES prices, which is incorrect.  This is a known limitation of the
current single-timeline ledger design and does not affect the opportunity-
level analysis in ``opportunities.jsonl``.

Usage (via runner)
------------------
::

    from packages.polymarket.simtrader.strategies.binary_complement_arb import (
        BinaryComplementArb,
    )
    from packages.polymarket.simtrader.strategy.runner import StrategyRunner

    strategy = BinaryComplementArb(
        yes_asset_id="<YES_TOKEN_ID>",
        no_asset_id="<NO_TOKEN_ID>",
        buffer=0.02,
        max_size=100,
        legging_policy="wait_N_then_unwind",
        unwind_wait_ticks=5,
        enable_merge_full_set=True,
    )
    runner = StrategyRunner(
        events_path=Path("events.jsonl"),
        run_dir=Path("runs/arb-001"),
        strategy=strategy,
        asset_id="<YES_TOKEN_ID>",
        extra_book_asset_ids=["<NO_TOKEN_ID>"],
        starting_cash=Decimal("2000"),
        fee_rate_bps=Decimal("200"),
    )
    summary = runner.run()
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN
from typing import Any, Optional

from ..orderbook.l2book import L2Book
from ..strategy.base import OrderIntent, Strategy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LEGGING_IMMEDIATE = "immediate_unwind"
LEGGING_WAIT_N = "wait_N_then_unwind"

_ONE = Decimal("1")
_ZERO = Decimal("0")

ASSUMPTION_MERGE_FULL_SET = (
    "MODELED ONLY — 1 YES share + 1 NO share redeemed for $1.00 USDC at "
    "settlement.  Actual settlement outcome, timing, and on-chain resolution "
    "are NOT validated in this simulation."
)


# ---------------------------------------------------------------------------
# Internal attempt state
# ---------------------------------------------------------------------------


@dataclass
class _ArbAttempt:
    """Tracks the lifecycle of one arb cycle."""

    attempt_id: str
    detected_seq: int
    detected_ts: float
    yes_ask: Decimal          # best_ask(YES) at detection time
    no_ask: Decimal           # best_ask(NO) at detection time
    size: Decimal             # shares per leg

    yes_order_id: Optional[str] = None
    no_order_id: Optional[str] = None

    # Filled info (accumulated via on_fill callbacks)
    yes_fill_price: Optional[Decimal] = None    # weighted-avg of all fills
    yes_filled_size: Decimal = field(default_factory=lambda: Decimal("0"))
    no_fill_price: Optional[Decimal] = None
    no_filled_size: Decimal = field(default_factory=lambda: Decimal("0"))

    # Status transitions
    status: str = "entering"  # entering|both_filled|merged|legged_out|cancelled|unwound
    ticks_since_enter: int = 0
    first_leg_fill_tick: Optional[int] = None  # for immediate_unwind policy

    # Unwind sell order (if legged out)
    unwind_order_id: Optional[str] = None

    @property
    def expected_profit_per_share(self) -> Decimal:
        return _ONE - self.yes_ask - self.no_ask

    @property
    def yes_order_resolved(self) -> bool:
        """YES order has been fully filled (based on on_fill calls)."""
        return self.yes_fill_price is not None and self.yes_filled_size >= self.size

    @property
    def no_order_resolved(self) -> bool:
        """NO order has been fully filled (based on on_fill calls)."""
        return self.no_fill_price is not None and self.no_filled_size >= self.size


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------


class BinaryComplementArb(Strategy):
    """Binary complement arb for a single YES/NO binary market.

    Args:
        yes_asset_id:          Token ID for the YES outcome share.
        no_asset_id:           Token ID for the NO outcome share.
        buffer:                Required gap below $1.00 to trigger entry.
                               E.g. buffer=0.02 → enter when sum_ask ≤ 0.98.
        max_size:              Maximum shares per leg (float; converted to Decimal).
        legging_policy:        ``"wait_N_then_unwind"`` (default) or
                               ``"immediate_unwind"``.  See module docstring.
        unwind_wait_ticks:     Tape events to wait before unwinding a legged position.
        enable_merge_full_set: If True, log a modeled $1.00 merge when both legs
                               fill.  Clearly labeled as an assumption.

    Exposed attributes (read by StrategyRunner after ``on_finish``):
        opportunities:       list[dict] — all opportunity log records.
        modeled_arb_summary: dict       — aggregate statistics across attempts.
    """

    def __init__(
        self,
        yes_asset_id: str,
        no_asset_id: str,
        buffer: float = 0.02,
        max_size: float = 100.0,
        legging_policy: str = LEGGING_WAIT_N,
        unwind_wait_ticks: int = 5,
        enable_merge_full_set: bool = True,
    ) -> None:
        if legging_policy not in (LEGGING_IMMEDIATE, LEGGING_WAIT_N):
            raise ValueError(
                f"legging_policy must be {LEGGING_IMMEDIATE!r} or "
                f"{LEGGING_WAIT_N!r}, got {legging_policy!r}."
            )
        self._yes_id = yes_asset_id
        self._no_id = no_asset_id
        self._buffer = Decimal(str(buffer))
        self._max_size = Decimal(str(max_size))
        self._legging_policy = legging_policy
        self._unwind_wait_ticks = unwind_wait_ticks
        self._enable_merge = enable_merge_full_set

        # Initialised in on_start
        self._no_book: L2Book
        self._active_attempt: Optional[_ArbAttempt] = None
        self._all_attempts: list[_ArbAttempt] = []
        self._attempt_counter: int = 0

        # Public output attributes read by StrategyRunner after on_finish
        self.opportunities: list[dict] = []
        self.modeled_arb_summary: dict = {}

    # ------------------------------------------------------------------
    # Strategy lifecycle
    # ------------------------------------------------------------------

    def on_start(self, asset_id: str, starting_cash: Decimal) -> None:
        self._no_book = L2Book(self._no_id, strict=False)
        self._active_attempt = None
        self._all_attempts = []
        self._attempt_counter = 0
        self.opportunities = []
        self.modeled_arb_summary = {}
        logger.info(
            "BinaryComplementArb started: yes=%s no=%s buffer=%s max_size=%s policy=%s",
            self._yes_id, self._no_id, self._buffer, self._max_size, self._legging_policy,
        )

    def on_event(
        self,
        event: dict,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        # Update our internal NO book from any NO events in the tape
        if event.get("asset_id") == self._no_id:
            self._no_book.apply(event)

        intents: list[OrderIntent] = []

        # Track whether we had an active attempt at the START of this tick
        # (to prevent immediate re-entry after completing an attempt)
        had_active = self._active_attempt is not None

        if had_active:
            self._active_attempt.ticks_since_enter += 1  # type: ignore[union-attr]
            intents.extend(
                self._manage_attempt(seq, ts_recv, best_bid, best_ask, open_orders)
            )

        # Only detect new arb if we were idle at the start of this tick
        if not had_active and self._active_attempt is None:
            yes_ask = best_ask  # primary book = YES
            no_ask = self._no_book.best_ask
            if yes_ask is not None and no_ask is not None:
                yes_ask_d = Decimal(str(yes_ask))
                no_ask_d = Decimal(str(no_ask))
                if yes_ask_d + no_ask_d < _ONE - self._buffer:
                    intents.extend(
                        self._enter_arb(seq, ts_recv, yes_ask_d, no_ask_d)
                    )

        return intents

    def on_fill(
        self,
        order_id: str,
        asset_id: str,
        side: str,
        fill_price: Decimal,
        fill_size: Decimal,
        fill_status: str,
        seq: int,
        ts_recv: float,
    ) -> None:
        attempt = self._active_attempt
        if attempt is None:
            return

        # Learn order IDs from same-tick fills (when the attempt was just created
        # and _resolve_order_ids hasn't had a chance to run yet).
        if attempt.yes_order_id is None and asset_id == self._yes_id and side == "BUY":
            attempt.yes_order_id = order_id
        if attempt.no_order_id is None and asset_id == self._no_id and side == "BUY":
            attempt.no_order_id = order_id

        if order_id == attempt.yes_order_id:
            if attempt.yes_fill_price is None:
                attempt.yes_fill_price = fill_price
            else:
                # Update weighted-average fill price across partial fills
                total = attempt.yes_filled_size + fill_size
                attempt.yes_fill_price = (
                    attempt.yes_fill_price * attempt.yes_filled_size
                    + fill_price * fill_size
                ) / total
            attempt.yes_filled_size += fill_size
            self._log(attempt, "leg_filled", seq, ts_recv, {
                "leg": "yes",
                "fill_price": str(fill_price),
                "fill_size": str(fill_size),
                "fill_status": fill_status,
            })
            if attempt.first_leg_fill_tick is None:
                attempt.first_leg_fill_tick = attempt.ticks_since_enter

        elif order_id == attempt.no_order_id:
            if attempt.no_fill_price is None:
                attempt.no_fill_price = fill_price
            else:
                total = attempt.no_filled_size + fill_size
                attempt.no_fill_price = (
                    attempt.no_fill_price * attempt.no_filled_size
                    + fill_price * fill_size
                ) / total
            attempt.no_filled_size += fill_size
            self._log(attempt, "leg_filled", seq, ts_recv, {
                "leg": "no",
                "fill_price": str(fill_price),
                "fill_size": str(fill_size),
                "fill_status": fill_status,
            })
            if attempt.first_leg_fill_tick is None:
                attempt.first_leg_fill_tick = attempt.ticks_since_enter

        elif order_id == attempt.unwind_order_id:
            self._log(attempt, "unwind_filled", seq, ts_recv, {
                "fill_price": str(fill_price),
                "fill_size": str(fill_size),
            })
            attempt.status = "unwound"
            self._complete_attempt()

    def on_finish(self) -> None:
        # Close any still-active attempt at tape end
        if self._active_attempt is not None:
            a = self._active_attempt
            self._log(a, "tape_ended_open", 0, 0.0, {
                "yes_filled_size": str(a.yes_filled_size),
                "no_filled_size": str(a.no_filled_size),
                "status": a.status,
            })
            self._complete_attempt()

        # Build modeled_arb_summary
        total = len(self._all_attempts)
        both_filled = sum(1 for a in self._all_attempts if a.status in ("both_filled", "merged"))
        merged = sum(1 for a in self._all_attempts if a.status == "merged")
        legged_out = sum(1 for a in self._all_attempts if a.status == "legged_out")
        cancelled = sum(1 for a in self._all_attempts if a.status == "cancelled")
        unwound = sum(1 for a in self._all_attempts if a.status == "unwound")

        modeled_profit = _ZERO
        modeled_cost = _ZERO
        for a in self._all_attempts:
            if a.status == "merged" and a.yes_fill_price and a.no_fill_price:
                size = min(a.yes_filled_size, a.no_filled_size)
                modeled_cost += (a.yes_fill_price + a.no_fill_price) * size
                modeled_profit += (_ONE - a.yes_fill_price - a.no_fill_price) * size

        self.modeled_arb_summary = {
            "total_attempts": total,
            "both_filled": both_filled,
            "merged_modeled": merged,
            "legged_out": legged_out,
            "cancelled": cancelled,
            "unwound": unwound,
            "modeled_total_cost": str(modeled_cost),
            "modeled_total_profit": str(modeled_profit),
            "ASSUMPTION": ASSUMPTION_MERGE_FULL_SET if merged > 0 else None,
        }
        logger.info(
            "BinaryComplementArb finished: %d attempts, %d both-filled, "
            "%d merged (modeled), %d legged-out, %d cancelled",
            total, both_filled, merged, legged_out, cancelled,
        )

    # ------------------------------------------------------------------
    # Entry logic
    # ------------------------------------------------------------------

    def _enter_arb(
        self,
        seq: int,
        ts_recv: float,
        yes_ask: Decimal,
        no_ask: Decimal,
    ) -> list[OrderIntent]:
        self._attempt_counter += 1
        attempt_id = f"arb-{self._attempt_counter:04d}"
        attempt = _ArbAttempt(
            attempt_id=attempt_id,
            detected_seq=seq,
            detected_ts=ts_recv,
            yes_ask=yes_ask,
            no_ask=no_ask,
            size=self._max_size,
        )
        self._active_attempt = attempt

        self._log(attempt, "detected", seq, ts_recv, {
            "yes_ask": str(yes_ask),
            "no_ask": str(no_ask),
            "sum_ask": str(yes_ask + no_ask),
            "buffer": str(self._buffer),
            "threshold": str(_ONE - self._buffer),
            "expected_profit_per_share": str(attempt.expected_profit_per_share),
            "size": str(self._max_size),
        })

        yes_intent = OrderIntent(
            action="submit",
            asset_id=self._yes_id,
            side="BUY",
            limit_price=yes_ask,
            size=self._max_size,
            reason=f"arb {attempt_id}: buy YES leg at ask={yes_ask}",
            meta={"attempt_id": attempt_id, "leg": "yes"},
        )
        no_intent = OrderIntent(
            action="submit",
            asset_id=self._no_id,
            side="BUY",
            limit_price=no_ask,
            size=self._max_size,
            reason=f"arb {attempt_id}: buy NO leg at ask={no_ask}",
            meta={"attempt_id": attempt_id, "leg": "no"},
        )
        # Capture order IDs via the runner's execute path.  We learn them
        # from subsequent open_orders dicts (the runner populates them from
        # broker events before the next on_event call).  We detect them by
        # checking open_orders for new entries with matching asset_id+side.
        # A cleaner hook: store a "pending assignment" flag and resolve
        # in the next on_event.
        self._pending_yes_intent = True
        self._pending_no_intent = True
        logger.info(
            "Arb %s: detected sum_ask=%s expected_profit=%s at seq=%d",
            attempt_id, yes_ask + no_ask, attempt.expected_profit_per_share, seq,
        )
        return [yes_intent, no_intent]

    # ------------------------------------------------------------------
    # Order-ID resolution from open_orders
    # ------------------------------------------------------------------

    def _resolve_order_ids(
        self, attempt: _ArbAttempt, open_orders: dict[str, Any]
    ) -> None:
        """Match newly submitted orders in open_orders to the active attempt."""
        if attempt.yes_order_id is None:
            for oid, od in open_orders.items():
                if (
                    od.get("asset_id") == self._yes_id
                    and od.get("side") == "BUY"
                    and Decimal(od["limit_price"]) == attempt.yes_ask
                    and oid != attempt.unwind_order_id
                ):
                    attempt.yes_order_id = oid
                    break
        if attempt.no_order_id is None:
            for oid, od in open_orders.items():
                if (
                    od.get("asset_id") == self._no_id
                    and od.get("side") == "BUY"
                    and Decimal(od["limit_price"]) == attempt.no_ask
                    and oid != attempt.unwind_order_id
                ):
                    attempt.no_order_id = oid
                    break

    # ------------------------------------------------------------------
    # Active-attempt management
    # ------------------------------------------------------------------

    def _manage_attempt(
        self,
        seq: int,
        ts_recv: float,
        best_bid: Optional[float],
        best_ask: Optional[float],
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        attempt = self._active_attempt
        assert attempt is not None

        # Resolve order IDs from open_orders on first opportunity
        self._resolve_order_ids(attempt, open_orders)

        intents: list[OrderIntent] = []

        yes_done = attempt.yes_order_resolved
        no_done = attempt.no_order_resolved

        # ── Both legs filled ──────────────────────────────────────────
        if yes_done and no_done:
            attempt.status = "both_filled"
            self._log_both_filled(attempt, seq, ts_recv)
            if self._enable_merge:
                self._log_merge(attempt, seq, ts_recv)
                attempt.status = "merged"
            self._complete_attempt()
            return intents

        # ── Determine unwind deadline ────────────────────────────────
        if self._legging_policy == LEGGING_IMMEDIATE:
            # Start countdown from when first leg filled
            ticks_for_deadline = self._unwind_wait_ticks
            elapsed = (
                attempt.ticks_since_enter - (attempt.first_leg_fill_tick or 0)
                if attempt.first_leg_fill_tick is not None
                else 0
            )
            deadline_reached = (
                attempt.first_leg_fill_tick is not None
                and elapsed >= ticks_for_deadline
            )
        else:  # wait_N_then_unwind
            deadline_reached = attempt.ticks_since_enter >= self._unwind_wait_ticks

        if not deadline_reached:
            return intents

        # ── Deadline reached — decide unwind action ──────────────────
        yes_has_shares = attempt.yes_filled_size > _ZERO
        no_has_shares = attempt.no_filled_size > _ZERO

        if yes_has_shares and not no_done:
            # YES filled (at least partially), NO did not → cancel NO, sell YES
            if attempt.no_order_id and attempt.no_order_id in open_orders:
                intents.append(OrderIntent(
                    action="cancel",
                    order_id=attempt.no_order_id,
                    reason=f"arb {attempt.attempt_id}: leg timeout, unwind YES",
                    meta={"attempt_id": attempt.attempt_id},
                ))
            unwind_intents = self._submit_unwind(
                attempt, seq, ts_recv, self._yes_id, attempt.yes_filled_size,
                best_bid, "YES", open_orders,
            )
            intents.extend(unwind_intents)
            attempt.status = "legged_out"
            self._log(attempt, "legged_out", seq, ts_recv, {
                "filled_leg": "yes",
                "filled_size": str(attempt.yes_filled_size),
                "filled_price": str(attempt.yes_fill_price),
                "cancelled_leg": "no",
                "ticks_waited": attempt.ticks_since_enter,
                "policy": self._legging_policy,
            })
            self._complete_attempt()

        elif no_has_shares and not yes_done:
            # NO filled, YES did not → cancel YES, sell NO
            if attempt.yes_order_id and attempt.yes_order_id in open_orders:
                intents.append(OrderIntent(
                    action="cancel",
                    order_id=attempt.yes_order_id,
                    reason=f"arb {attempt.attempt_id}: leg timeout, unwind NO",
                    meta={"attempt_id": attempt.attempt_id},
                ))
            no_bid = self._no_book.best_bid
            unwind_intents = self._submit_unwind(
                attempt, seq, ts_recv, self._no_id, attempt.no_filled_size,
                no_bid, "NO", open_orders,
            )
            intents.extend(unwind_intents)
            attempt.status = "legged_out"
            self._log(attempt, "legged_out", seq, ts_recv, {
                "filled_leg": "no",
                "filled_size": str(attempt.no_filled_size),
                "filled_price": str(attempt.no_fill_price),
                "cancelled_leg": "yes",
                "ticks_waited": attempt.ticks_since_enter,
                "policy": self._legging_policy,
            })
            self._complete_attempt()

        else:
            # Neither leg filled → cancel both
            for oid, label in [
                (attempt.yes_order_id, "yes"),
                (attempt.no_order_id, "no"),
            ]:
                if oid and oid in open_orders:
                    intents.append(OrderIntent(
                        action="cancel",
                        order_id=oid,
                        reason=f"arb {attempt.attempt_id}: timeout, no fills",
                        meta={"attempt_id": attempt.attempt_id, "leg": label},
                    ))
            attempt.status = "cancelled"
            self._log(attempt, "cancelled", seq, ts_recv, {
                "reason": "timeout_no_fills",
                "ticks_waited": attempt.ticks_since_enter,
            })
            self._complete_attempt()

        return intents

    def _submit_unwind(
        self,
        attempt: _ArbAttempt,
        seq: int,
        ts_recv: float,
        asset_id: str,
        size: Decimal,
        best_bid: Optional[float],
        leg_label: str,
        open_orders: dict[str, Any],
    ) -> list[OrderIntent]:
        if size <= _ZERO or best_bid is None:
            # Nothing to unwind or no book price available → just complete
            attempt.status = "unwound"
            self._complete_attempt()
            return []

        limit_price = Decimal(str(best_bid))
        intent = OrderIntent(
            action="submit",
            asset_id=asset_id,
            side="SELL",
            limit_price=limit_price,
            size=size,
            reason=f"arb {attempt.attempt_id}: unwind {leg_label} leg",
            meta={"attempt_id": attempt.attempt_id, "leg": leg_label.lower(), "unwind": True},
        )
        self._log(attempt, "unwind_sell_submitted", seq, ts_recv, {
            "leg": leg_label.lower(),
            "asset_id": asset_id,
            "size": str(size),
            "limit_price": str(limit_price),
        })
        # Mark this as the unwind order; resolved via on_fill
        # (we'll match the order ID when open_orders is next seen)
        self._pending_unwind = True
        return [intent]

    # ------------------------------------------------------------------
    # Completion helpers
    # ------------------------------------------------------------------

    def _complete_attempt(self) -> None:
        attempt = self._active_attempt
        if attempt is not None:
            self._all_attempts.append(attempt)
        self._active_attempt = None
        self._pending_yes_intent = False
        self._pending_no_intent = False
        self._pending_unwind = False

    # ------------------------------------------------------------------
    # Opportunity log helpers
    # ------------------------------------------------------------------

    def _log(
        self,
        attempt: _ArbAttempt,
        event_type: str,
        seq: int,
        ts_recv: float,
        extra: dict,
    ) -> None:
        record: dict[str, Any] = {
            "attempt_id": attempt.attempt_id,
            "type": event_type,
            "seq": seq,
            "ts_recv": ts_recv,
            "yes_asset_id": self._yes_id,
            "no_asset_id": self._no_id,
        }
        record.update(extra)
        self.opportunities.append(record)

    def _log_both_filled(
        self, attempt: _ArbAttempt, seq: int, ts_recv: float
    ) -> None:
        assert attempt.yes_fill_price is not None
        assert attempt.no_fill_price is not None
        size = min(attempt.yes_filled_size, attempt.no_filled_size)
        actual_cost_per_share = attempt.yes_fill_price + attempt.no_fill_price
        self._log(attempt, "both_filled", seq, ts_recv, {
            "yes_fill_price": str(attempt.yes_fill_price),
            "yes_filled_size": str(attempt.yes_filled_size),
            "no_fill_price": str(attempt.no_fill_price),
            "no_filled_size": str(attempt.no_filled_size),
            "pairs": str(size),
            "expected_profit_per_share": str(attempt.expected_profit_per_share),
            "actual_cost_per_share": str(actual_cost_per_share),
            "actual_profit_per_share_premerge": str(_ONE - actual_cost_per_share),
        })

    def _log_merge(
        self, attempt: _ArbAttempt, seq: int, ts_recv: float
    ) -> None:
        assert attempt.yes_fill_price is not None
        assert attempt.no_fill_price is not None
        size = min(attempt.yes_filled_size, attempt.no_filled_size)
        cost = (attempt.yes_fill_price + attempt.no_fill_price) * size
        proceeds = _ONE * size
        profit = proceeds - cost
        self._log(attempt, "merge_full_set", seq, ts_recv, {
            "pairs_merged": str(size),
            "modeled_proceeds": str(proceeds),
            "modeled_cost": str(cost),
            "modeled_profit": str(profit),
            "modeled_profit_per_share": str(_ONE - attempt.yes_fill_price - attempt.no_fill_price),
            "ASSUMPTION": ASSUMPTION_MERGE_FULL_SET,
        })
