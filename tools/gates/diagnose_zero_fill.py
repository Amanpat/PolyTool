"""Tick-level diagnostic for Gate 2 zero-fill failures.

Runs a single tape through the SimTrader pipeline with manual instrumentation
to answer four diagnostic questions at every tick:

  Q1 — Book initialization: Is L2Book._initialized True? How many levels?
  Q2 — Quote marketability: Do strategy quotes cross the book BBO?
  Q3 — Reservation/inventory blocking: Does SELL get blocked by inventory?
  Q4 — Fill rejection reasons: What reject_reason does FillRecord carry?

Produces a structured JSON verdict:

  BOOK_NEVER_INITIALIZED  — tape has no book snapshot; fill engine never engaged
  NO_COMPETITIVE_LEVELS   — book initialized but strategy quotes don't cross BBO
  RESERVATION_BLOCKED     — SELL orders blocked by inventory reservation check
  QUOTES_TOO_WIDE         — quotes never cross BBO (spreads too wide for market)
  FILLS_OK                — fills occurred; no zero-fill problem
  UNKNOWN                 — unable to determine from available evidence

Usage::

    python tools/gates/diagnose_zero_fill.py \\
        --tape-dir artifacts/tapes/silver/TOKEN_ID/DATE \\
        --asset-id TOKEN_ID \\
        [--out artifacts/debug/diag_result.json] \\
        [--verbose]

For Silver tapes the events file is expected at ``silver_events.jsonl``.
For Gold tapes it is expected at ``events.jsonl``.
The script tries both automatically.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Ensure repo root on sys.path so package imports work from any cwd.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from packages.polymarket.simtrader.broker.fill_engine import try_fill
from packages.polymarket.simtrader.broker.latency import ZERO_LATENCY
from packages.polymarket.simtrader.broker.rules import FillRecord, Order, OrderStatus, Side
from packages.polymarket.simtrader.broker.sim_broker import SimBroker
from packages.polymarket.simtrader.orderbook.l2book import L2Book
from packages.polymarket.simtrader.strategies.market_maker_v1 import MarketMakerV1
from packages.polymarket.simtrader.tape.schema import EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE

# Import Gate 2 defaults so diagnostic uses same config as the real sweep.
from tools.gates.mm_sweep import (
    DEFAULT_MM_SWEEP_BASE_CONFIG,
    DEFAULT_MM_SWEEP_FEE_RATE_BPS,
    DEFAULT_MM_SWEEP_STARTING_CASH,
)

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_BOOK_AFFECTING = frozenset({EVENT_TYPE_BOOK, EVENT_TYPE_PRICE_CHANGE})
_MAX_QUOTE_SAMPLES = 10  # keep first 5 + last 5


def _load_events(tape_dir: Path) -> tuple[list[dict], str]:
    """Load events from tape_dir.

    Tries silver_events.jsonl first (Silver tapes), then events.jsonl (Gold).
    Returns (events, filename_used).
    """
    for candidate in ("silver_events.jsonl", "events.jsonl"):
        p = tape_dir / candidate
        if p.exists():
            events: list[dict] = []
            with open(p, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            events.sort(key=lambda e: e.get("seq", 0))
            return events, candidate
    raise FileNotFoundError(
        f"No events file found in {tape_dir}. "
        "Expected silver_events.jsonl or events.jsonl."
    )


def _detect_tape_tier(tape_dir: Path) -> str:
    """Guess tape tier from directory structure and event file name."""
    path_str = str(tape_dir)
    if "silver" in path_str.lower():
        return "silver"
    if "gold" in path_str.lower():
        return "gold"
    if "shadow" in path_str.lower():
        return "shadow"
    if "crypto" in path_str.lower():
        return "crypto"
    return "unknown"


def _build_strategy() -> MarketMakerV1:
    """Build a MarketMakerV1 instance using the same defaults as Gate 2 sweeps."""
    cfg = dict(DEFAULT_MM_SWEEP_BASE_CONFIG)
    return MarketMakerV1(
        tick_size="0.01",
        order_size="10",
        min_spread=cfg.get("min_spread", 0.020),
        max_spread=cfg.get("max_spread", 0.120),
        spread_multiplier=cfg.get("spread_multiplier", 1.0),
    )


def _open_orders_dict(broker: SimBroker) -> dict:
    """Build open_orders dict compatible with Strategy.on_event signature."""
    result: dict[str, dict] = {}
    for order_ev in broker.order_events:
        oid = order_ev.get("order_id", "")
        evt = order_ev.get("event", "")
        if not oid:
            continue
        if evt == "submitted":
            result[oid] = {
                "order_id": oid,
                "side": order_ev.get("side", ""),
                "asset_id": order_ev.get("asset_id", ""),
                "limit_price": order_ev.get("limit_price", "0"),
                "size": order_ev.get("size", "0"),
                "status": OrderStatus.PENDING,
                "filled_size": "0",
            }
        elif evt in ("filled", "cancelled"):
            result.pop(oid, None)
        elif evt == "activated":
            if oid in result:
                result[oid]["status"] = OrderStatus.ACTIVE
    return result


def run_diagnostic(
    tape_dir: Path,
    asset_id: str,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run tick-level diagnostic on *tape_dir* for *asset_id*.

    Returns a structured JSON-serializable diagnostic report dict.
    """
    events, events_file = _load_events(tape_dir)
    tape_tier = _detect_tape_tier(tape_dir)

    # --- Counters and accumulators ---
    event_type_counts: dict[str, int] = defaultdict(int)
    fill_rejection_counts: dict[str, int] = defaultdict(int)
    reservation_blocks = {"sell_insufficient_position": 0}
    order_intents_by_side: dict[str, int] = {"BUY": 0, "SELL": 0}

    book_ever_initialized = False
    first_book_init_seq: Optional[int] = None
    book_affecting_events = 0
    quote_ticks = 0
    fill_attempts = 0
    fill_successes = 0

    quote_samples: list[dict] = []  # first 5 captured, last 5 from a buffer
    _quote_last_5: list[dict] = []

    # --- Infrastructure ---
    book = L2Book(asset_id, strict=False)
    broker = SimBroker(latency=ZERO_LATENCY)
    strategy = _build_strategy()
    strategy.on_start(asset_id, DEFAULT_MM_SWEEP_STARTING_CASH)

    _last_fill_idx = 0
    _last_order_event_idx = 0
    open_orders: dict[str, dict] = {}

    for event in events:
        seq: int = event.get("seq", 0)
        ts_recv: float = event.get("ts_recv", 0.0)
        event_type: str = str(event.get("event_type") or "")
        evt_asset: str = str(event.get("asset_id") or "")

        event_type_counts[event_type] += 1

        # --- Q1 pre-apply state ---
        was_initialized = book._initialized

        # --- Apply event to book ---
        applied = False
        if event_type == EVENT_TYPE_PRICE_CHANGE and "price_changes" in event:
            for entry in event.get("price_changes", []):
                if str(entry.get("asset_id") or "") == asset_id:
                    book.apply_single_delta(entry)
                    applied = True
        elif evt_asset == asset_id:
            applied = book.apply(event)

        # --- Q1 post-apply state ---
        if book._initialized and not was_initialized:
            book_ever_initialized = True
            if first_book_init_seq is None:
                first_book_init_seq = seq
            if verbose:
                print(
                    f"[seq={seq}] BOOK INITIALIZED: n_bids={len(book._bids)} "
                    f"n_asks={len(book._asks)} best_bid={book.best_bid} "
                    f"best_ask={book.best_ask}",
                    file=sys.stderr,
                )

        if applied and event_type in _BOOK_AFFECTING:
            book_affecting_events += 1

        if verbose and applied:
            print(
                f"[seq={seq}] {event_type}: initialized={book._initialized} "
                f"n_bids={len(book._bids)} n_asks={len(book._asks)} "
                f"best_bid={book.best_bid} best_ask={book.best_ask}",
                file=sys.stderr,
            )

        # --- Q2 strategy quoting ---
        # Build event context similar to StrategyRunner
        event_ctx = dict(event)
        event_ctx["_best_by_asset"] = {
            asset_id: {"best_bid": book.best_bid, "best_ask": book.best_ask}
        }
        intents = strategy.on_event(
            event_ctx,
            seq,
            ts_recv,
            book.best_bid,
            book.best_ask,
            dict(open_orders),
        )

        if intents:
            quote_ticks += 1

            # Record quote samples (first 5 + rolling last 5)
            for intent in intents:
                side = intent.side or "UNKNOWN"
                order_intents_by_side[side] = order_intents_by_side.get(side, 0) + 1

            bid_intent = next((i for i in intents if i.side == "BUY"), None)
            ask_intent = next((i for i in intents if i.side == "SELL"), None)

            strat_bid = float(bid_intent.limit_price) if bid_intent and bid_intent.limit_price else None
            strat_ask = float(ask_intent.limit_price) if ask_intent and ask_intent.limit_price else None
            bbo_bid = book.best_bid
            bbo_ask = book.best_ask

            # Q2: does strat bid cross BBO ask? does strat ask cross BBO bid?
            bid_crosses = (
                strat_bid is not None and bbo_ask is not None and strat_bid >= bbo_ask
            )
            ask_crosses = (
                strat_ask is not None and bbo_bid is not None and strat_ask <= bbo_bid
            )

            sample = {
                "seq": seq,
                "strat_bid": strat_bid,
                "strat_ask": strat_ask,
                "book_best_bid": bbo_bid,
                "book_best_ask": bbo_ask,
                "bid_crosses_ask": bid_crosses,
                "ask_crosses_bid": ask_crosses,
                "book_initialized": book._initialized,
            }

            if len(quote_samples) < 5:
                quote_samples.append(sample)

            _quote_last_5.append(sample)
            if len(_quote_last_5) > 5:
                _quote_last_5.pop(0)

        # --- Q3 submit to broker ---
        for intent in intents:
            if intent.action != "submit" or intent.side is None or intent.limit_price is None:
                continue

            # Check for inventory blocking BEFORE submitting
            # The StrategyRunner submits orders; SimBroker tracks reservations via the
            # portfolio ledger (in the full runner). The "Insufficient position to
            # reserve SELL order" warning comes from PortfolioLedger, not SimBroker.
            # In this diagnostic we bypass the ledger and just track SELL intents vs.
            # book state. A SELL order from MarketMakerV1 implies the strategy thinks
            # it can provide ask-side liquidity. We count SELL intents blocked at
            # submission time by checking the strategy's inventory tracking:
            # MarketMakerV0._inventory tracks YES position; a SELL when inventory==0
            # would hit the "insufficient position" path in the full ledger.
            if intent.side == Side.SELL:
                strat_inventory = getattr(strategy, "_inventory", None)
                if strat_inventory is not None and strat_inventory <= _ZERO:
                    reservation_blocks["sell_insufficient_position"] += 1
                    if verbose:
                        print(
                            f"[seq={seq}] SELL blocked: inventory={strat_inventory}",
                            file=sys.stderr,
                        )

            broker.submit_order(
                asset_id=intent.asset_id or asset_id,
                side=intent.side,
                limit_price=intent.limit_price,
                size=intent.size or Decimal("10"),
                submit_seq=seq,
                submit_ts=ts_recv,
            )

        # --- Q4 fill rejections via broker.step ---
        if event_type in _BOOK_AFFECTING:
            new_fills = broker.step(event, book, fill_asset_id=asset_id)

            # Collect all fill records including rejections via direct engine call
            # SimBroker.step only tracks successful fills; we need to capture rejections.
            # We replicate the evaluation by inspecting active orders.
            for order in list(broker._orders.values()):
                if order.is_active and order.asset_id == asset_id:
                    fill_attempts += 1
                    if not book._initialized:
                        fill_rejection_counts["book_not_initialized"] += 1
                    elif not _has_competitive_levels(book, order):
                        fill_rejection_counts["no_competitive_levels"] += 1

            for fill in new_fills:
                if fill.fill_size > _ZERO:
                    fill_successes += 1

        # --- Update open_orders from broker events ---
        new_broker_events = broker.order_events[_last_order_event_idx:]
        _last_order_event_idx = len(broker.order_events)
        for bev in new_broker_events:
            oid = bev.get("order_id", "")
            evt = bev.get("event", "")
            if not oid:
                continue
            if evt == "submitted":
                open_orders[oid] = {
                    "order_id": oid,
                    "side": bev.get("side", ""),
                    "asset_id": bev.get("asset_id", asset_id),
                    "limit_price": bev.get("limit_price", "0"),
                    "size": bev.get("size", "0"),
                    "status": OrderStatus.PENDING,
                    "filled_size": "0",
                }
            elif evt in ("filled", "cancelled"):
                open_orders.pop(oid, None)
            elif evt == "activated":
                if oid in open_orders:
                    open_orders[oid]["status"] = OrderStatus.ACTIVE

        # notify strategy of fills
        new_fills_all = broker.fills[_last_fill_idx:]
        _last_fill_idx = len(broker.fills)
        for fill in new_fills_all:
            if fill.fill_size > _ZERO:
                strategy.on_fill(
                    order_id=fill.order_id,
                    asset_id=fill.asset_id,
                    side=fill.side,
                    fill_price=fill.fill_price,
                    fill_size=fill.fill_size,
                    fill_status=fill.fill_status,
                    seq=fill.seq,
                    ts_recv=fill.ts_recv,
                )

    strategy.on_finish()

    # Combine first-5 + last-5 quote samples (dedup by seq)
    seen_seqs: set[int] = set()
    combined_samples: list[dict] = []
    for s in quote_samples + _quote_last_5:
        if s["seq"] not in seen_seqs:
            combined_samples.append(s)
            seen_seqs.add(s["seq"])

    # --- Verdict logic (deterministic) ---
    verdict, verdict_evidence = _compute_verdict(
        book_ever_initialized=book_ever_initialized,
        fill_rejection_counts=dict(fill_rejection_counts),
        reservation_blocks=reservation_blocks,
        order_intents_by_side=order_intents_by_side,
        quote_samples=combined_samples,
        fill_successes=fill_successes,
    )

    report: dict[str, Any] = {
        "tape_dir": str(tape_dir),
        "events_file": events_file,
        "tape_tier": tape_tier,
        "asset_id": asset_id,
        "total_events": len(events),
        "book_affecting_events": book_affecting_events,
        "book_ever_initialized": book_ever_initialized,
        "first_book_init_seq": first_book_init_seq,
        "event_type_counts": dict(event_type_counts),
        "quote_ticks": quote_ticks,
        "quote_samples": combined_samples,
        "fill_attempts": fill_attempts,
        "fill_successes": fill_successes,
        "fill_rejection_counts": dict(fill_rejection_counts),
        "reservation_blocks": reservation_blocks,
        "order_intents_by_side": order_intents_by_side,
        "verdict": verdict,
        "verdict_evidence": verdict_evidence,
    }
    return report


def _has_competitive_levels(book: L2Book, order: "Order") -> bool:
    """Return True if the book has levels that would satisfy *order* at its limit price."""
    from packages.polymarket.simtrader.broker.fill_engine import (
        _sorted_ask_levels,
        _sorted_bid_levels,
    )
    if order.side == Side.BUY:
        return bool(_sorted_ask_levels(book, order.limit_price))
    return bool(_sorted_bid_levels(book, order.limit_price))


def _compute_verdict(
    *,
    book_ever_initialized: bool,
    fill_rejection_counts: dict[str, int],
    reservation_blocks: dict[str, int],
    order_intents_by_side: dict[str, int],
    quote_samples: list[dict],
    fill_successes: int,
) -> tuple[str, str]:
    """Deterministic verdict logic. Returns (verdict_code, human_explanation)."""

    if not book_ever_initialized:
        return (
            "BOOK_NEVER_INITIALIZED",
            "The L2Book._initialized flag never became True during replay. "
            "This means no EVENT_TYPE_BOOK (book snapshot) event was present in the tape. "
            "The fill engine rejects every fill attempt with 'book_not_initialized' because "
            "it requires at least one book snapshot before it can walk order levels. "
            "This is a tape quality limitation: price_2min-only Silver tapes contain only "
            "price guide events, not real L2 book snapshots.",
        )

    total_rejections = sum(fill_rejection_counts.values())
    no_competitive = fill_rejection_counts.get("no_competitive_levels", 0)
    book_not_init = fill_rejection_counts.get("book_not_initialized", 0)

    if fill_successes > 0:
        return (
            "FILLS_OK",
            f"Book initialized and {fill_successes} fill(s) succeeded. No zero-fill problem.",
        )

    sell_blocks = reservation_blocks.get("sell_insufficient_position", 0)
    sell_intents = order_intents_by_side.get("SELL", 0)
    sell_block_fraction = sell_blocks / max(sell_intents, 1)

    if sell_blocks > 0 and sell_block_fraction > 0.50:
        return (
            "RESERVATION_BLOCKED",
            f"SELL orders blocked by zero inventory in {sell_blocks}/{sell_intents} cases "
            f"({sell_block_fraction:.0%} of SELL intents). "
            "MarketMakerV1 generates SELL (ask-side) quotes but the portfolio ledger "
            "requires holding the asset before a SELL can be reserved. "
            "With no prior BUY fills, inventory stays at zero.",
        )

    if total_rejections > 0 and no_competitive >= 0.8 * total_rejections:
        return (
            "NO_COMPETITIVE_LEVELS",
            f"Book initialized but {no_competitive}/{total_rejections} fill rejections "
            "were 'no_competitive_levels'. Strategy quotes do not cross the BBO: "
            "the strategy's bid price is below the book's best ask (no BUY fill), "
            "and the strategy's ask is above the book's best bid (no SELL fill). "
            "Possible causes: book spread wider than strategy spread, or strategy "
            "spread_multiplier too conservative.",
        )

    # Check if quotes ever crossed the BBO
    any_cross = any(
        s.get("bid_crosses_ask") or s.get("ask_crosses_bid")
        for s in quote_samples
    )
    if quote_samples and not any_cross:
        return (
            "QUOTES_TOO_WIDE",
            "Book initialized, strategy generated quotes, but no quote ever crossed "
            "the book BBO. Strategy bid never reached book best_ask and strategy ask "
            "never reached book best_bid. The strategy's spread is wider than the "
            "market spread — no fills are possible at these parameters.",
        )

    return (
        "UNKNOWN",
        "Book initialized, quotes generated, but fills did not occur and the "
        "rejection pattern does not match a clear single cause. "
        "Inspect quote_samples and fill_rejection_counts in the full report.",
    )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Tick-level Gate 2 zero-fill diagnostic for a single tape."
    )
    parser.add_argument(
        "--tape-dir",
        required=True,
        help="Path to a tape directory containing events.jsonl or silver_events.jsonl.",
    )
    parser.add_argument(
        "--asset-id",
        required=True,
        help="YES token asset ID to replay against.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write the JSON diagnostic report.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-tick book state to stderr.",
    )
    args = parser.parse_args(argv)

    tape_dir = Path(args.tape_dir)
    if not tape_dir.exists():
        print(f"ERROR: tape_dir not found: {tape_dir}", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        report = run_diagnostic(
            tape_dir,
            args.asset_id,
            verbose=args.verbose,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR during diagnostic: {exc}", file=sys.stderr)
        logger.exception("Diagnostic failed")
        return 1

    output = json.dumps(report, indent=2, default=str)
    print(output)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"\nReport written to: {out_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
