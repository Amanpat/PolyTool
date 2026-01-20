"""PnL computation for realized and conservative MTM estimates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Literal
from collections import defaultdict
import logging
import time

from .clob import ClobClient

logger = logging.getLogger(__name__)

BucketType = Literal["day", "hour", "week"]
PRICING_SOURCE = "clob_best_bid_ask"


@dataclass
class PnlBucketResult:
    """Computed PnL metrics for a user bucket."""

    proxy_wallet: str
    bucket_type: str
    bucket_start: datetime
    realized_pnl: float
    mtm_pnl_estimate: float
    exposure_notional_estimate: float
    open_position_tokens: int
    pricing_source: str

    def to_row(self) -> list:
        return [
            self.proxy_wallet,
            self.bucket_type,
            self.bucket_start,
            float(self.realized_pnl),
            float(self.mtm_pnl_estimate),
            float(self.exposure_notional_estimate),
            int(self.open_position_tokens),
            self.pricing_source,
            datetime.utcnow(),
        ]


@dataclass
class PnlComputeResult:
    """Aggregate PnL computation output."""

    buckets: list[PnlBucketResult]
    tokens_priced: int
    tokens_skipped_missing_orderbook: list[str]
    tokens_skipped_limit: list[str]
    pricing_source: str = PRICING_SOURCE


@dataclass
class InventoryLot:
    shares: float
    price: float


class FifoInventory:
    """FIFO inventory tracker supporting long and short positions."""

    def __init__(self) -> None:
        self._lots: dict[str, list[InventoryLot]] = defaultdict(list)

    def apply_trade(self, token_id: str, side: str, size: float, price: float) -> float:
        side = side.upper()
        if side == "BUY":
            return self._apply_buy(token_id, size, price)
        if side == "SELL":
            return self._apply_sell(token_id, size, price)
        return 0.0

    def snapshot_state(self) -> dict[str, dict[str, float]]:
        state: dict[str, dict[str, float]] = {}
        for token_id, lots in self._lots.items():
            if not lots:
                continue
            net_shares = sum(lot.shares for lot in lots)
            if abs(net_shares) < 1e-12:
                continue
            cost_basis = sum(lot.shares * lot.price for lot in lots)
            state[token_id] = {"net_shares": net_shares, "cost_basis": cost_basis}
        return state

    def _apply_buy(self, token_id: str, size: float, price: float) -> float:
        lots = self._lots[token_id]
        realized = 0.0
        remaining = size

        while remaining > 0 and lots and lots[0].shares < 0:
            lot = lots[0]
            match_size = min(remaining, abs(lot.shares))
            realized += (lot.price - price) * match_size
            lot.shares += match_size
            remaining -= match_size
            if abs(lot.shares) <= 1e-12:
                lots.pop(0)

        if remaining > 0:
            lots.append(InventoryLot(shares=remaining, price=price))
        return realized

    def _apply_sell(self, token_id: str, size: float, price: float) -> float:
        lots = self._lots[token_id]
        realized = 0.0
        remaining = size

        while remaining > 0 and lots and lots[0].shares > 0:
            lot = lots[0]
            match_size = min(remaining, lot.shares)
            realized += (price - lot.price) * match_size
            lot.shares -= match_size
            remaining -= match_size
            if lot.shares <= 1e-12:
                lots.pop(0)

        if remaining > 0:
            lots.append(InventoryLot(shares=-remaining, price=price))
        return realized


def _bucket_delta(bucket_type: BucketType) -> timedelta:
    if bucket_type == "hour":
        return timedelta(hours=1)
    if bucket_type == "week":
        return timedelta(days=7)
    return timedelta(days=1)


def get_bucket_start(ts: datetime, bucket_type: BucketType) -> datetime:
    if bucket_type == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    if bucket_type == "week":
        start = ts - timedelta(days=ts.weekday())
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def _build_bucket_range(
    start_ts: datetime,
    end_ts: datetime,
    bucket_type: BucketType,
) -> list[datetime]:
    bucket_start = get_bucket_start(start_ts, bucket_type)
    bucket_end = get_bucket_start(end_ts, bucket_type)
    step = _bucket_delta(bucket_type)

    buckets = []
    current = bucket_start
    while current <= bucket_end:
        buckets.append(current)
        current += step
    return buckets


def _group_snapshots_by_bucket(
    snapshots: list[dict],
    bucket_type: BucketType,
) -> dict[datetime, dict[datetime, list[dict]]]:
    grouped: dict[datetime, dict[datetime, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for snapshot in snapshots:
        ts = snapshot["snapshot_ts"]
        bucket_start = get_bucket_start(ts, bucket_type)
        grouped[bucket_start][ts].append(snapshot)
    return grouped


def _compute_token_weights(
    bucket_positions: dict[datetime, dict[str, float]]
) -> list[tuple[str, float]]:
    weights: dict[str, float] = {}
    for positions in bucket_positions.values():
        for token_id, shares in positions.items():
            if abs(shares) <= 1e-12:
                continue
            weights[token_id] = max(weights.get(token_id, 0.0), abs(shares))
    return sorted(weights.items(), key=lambda item: (-item[1], item[0]))


def compute_user_pnl_buckets(
    proxy_wallet: str,
    trades: list[dict],
    snapshots: list[dict],
    bucket_type: BucketType,
    clob_client: ClobClient,
    orderbook_cache_seconds: int = 30,
    max_tokens_per_run: int = 200,
    as_of: Optional[datetime] = None,
) -> PnlComputeResult:
    as_of = as_of or datetime.utcnow()

    if bucket_type not in ("day", "hour", "week"):
        raise ValueError(f"Unsupported bucket_type: {bucket_type}")

    if not trades and not snapshots:
        return PnlComputeResult(
            buckets=[],
            tokens_priced=0,
            tokens_skipped_missing_orderbook=[],
            tokens_skipped_limit=[],
        )

    timestamps = []
    if trades:
        timestamps.append(min(t["ts"] for t in trades))
        timestamps.append(max(t["ts"] for t in trades))
    if snapshots:
        timestamps.append(min(s["snapshot_ts"] for s in snapshots))
        timestamps.append(max(s["snapshot_ts"] for s in snapshots))
    timestamps.append(as_of)

    start_ts = min(timestamps)
    end_ts = max(timestamps)

    bucket_starts = _build_bucket_range(start_ts, end_ts, bucket_type)
    if not bucket_starts:
        return PnlComputeResult(
            buckets=[],
            tokens_priced=0,
            tokens_skipped_missing_orderbook=[],
            tokens_skipped_limit=[],
        )

    sorted_trades = sorted(trades, key=lambda t: t["ts"])
    snapshot_map = _group_snapshots_by_bucket(snapshots, bucket_type)

    inventory = FifoInventory()
    realized_by_bucket: dict[datetime, float] = defaultdict(float)
    inventory_state_by_bucket: dict[datetime, dict[str, dict[str, float]]] = {}

    trade_index = 0
    for bucket_start in bucket_starts:
        bucket_end = bucket_start + _bucket_delta(bucket_type)

        while trade_index < len(sorted_trades) and sorted_trades[trade_index]["ts"] < bucket_end:
            trade = sorted_trades[trade_index]
            size = float(trade.get("size", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            if size > 0 and price > 0:
                realized = inventory.apply_trade(
                    token_id=trade["token_id"],
                    side=trade.get("side", ""),
                    size=size,
                    price=price,
                )
                trade_bucket = get_bucket_start(trade["ts"], bucket_type)
                realized_by_bucket[trade_bucket] += realized
            trade_index += 1

        inventory_state_by_bucket[bucket_start] = inventory.snapshot_state()

    bucket_positions: dict[datetime, dict[str, float]] = {}
    bucket_cost_basis: dict[datetime, dict[str, float]] = {}

    for bucket_start in bucket_starts:
        snapshots_by_ts = snapshot_map.get(bucket_start)
        if snapshots_by_ts:
            latest_ts = max(snapshots_by_ts)
            rows = snapshots_by_ts[latest_ts]
            positions: dict[str, float] = {}
            cost_basis: dict[str, float] = {}
            fifo_state = inventory_state_by_bucket.get(bucket_start, {})

            for row in rows:
                token_id = row["token_id"]
                shares = float(row.get("shares", 0) or 0)
                positions[token_id] = shares
                avg_cost = row.get("avg_cost")
                if avg_cost is not None:
                    cost_basis[token_id] = shares * float(avg_cost)
                else:
                    fifo_basis = fifo_state.get(token_id, {}).get("cost_basis", 0.0)
                    cost_basis[token_id] = fifo_basis

            bucket_positions[bucket_start] = positions
            bucket_cost_basis[bucket_start] = cost_basis
        else:
            fifo_state = inventory_state_by_bucket.get(bucket_start, {})
            bucket_positions[bucket_start] = {
                token_id: values["net_shares"] for token_id, values in fifo_state.items()
            }
            bucket_cost_basis[bucket_start] = {
                token_id: values["cost_basis"] for token_id, values in fifo_state.items()
            }

    token_weights = _compute_token_weights(bucket_positions)
    tokens_all = [token for token, _ in token_weights]

    if max_tokens_per_run > 0:
        tokens_to_price = tokens_all[:max_tokens_per_run]
        tokens_skipped_limit = tokens_all[max_tokens_per_run:]
    else:
        tokens_to_price = tokens_all
        tokens_skipped_limit = []

    orderbook_cache: dict[str, dict[str, object]] = {}
    pricing: dict[str, tuple[float, float]] = {}
    tokens_missing_orderbook: list[str] = []

    for token_id in tokens_to_price:
        now_ts = time.time()
        cached = orderbook_cache.get(token_id)
        if cached and orderbook_cache_seconds > 0:
            if now_ts - float(cached["fetched_at"]) <= orderbook_cache_seconds:
                best_bid = cached["best_bid"]
                best_ask = cached["best_ask"]
            else:
                best_bid = None
                best_ask = None
        else:
            best_bid = None
            best_ask = None

        if best_bid is None or best_ask is None:
            book = clob_client.get_best_bid_ask(token_id)
            if book and book.best_bid is not None and book.best_ask is not None:
                best_bid = book.best_bid
                best_ask = book.best_ask
                orderbook_cache[token_id] = {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "fetched_at": now_ts,
                }
            else:
                tokens_missing_orderbook.append(token_id)
                continue

        pricing[token_id] = (float(best_bid), float(best_ask))

    results: list[PnlBucketResult] = []
    for bucket_start in bucket_starts:
        positions = bucket_positions.get(bucket_start, {})
        cost_basis = bucket_cost_basis.get(bucket_start, {})

        realized_pnl = realized_by_bucket.get(bucket_start, 0.0)
        mtm_pnl = 0.0
        exposure = 0.0

        open_tokens = 0
        for token_id, shares in positions.items():
            if abs(shares) <= 1e-12:
                continue
            open_tokens += 1

            price = pricing.get(token_id)
            if not price:
                continue

            best_bid, best_ask = price
            if shares > 0:
                mtm_value = shares * best_bid
            else:
                mtm_value = shares * best_ask

            mtm_pnl += mtm_value - cost_basis.get(token_id, 0.0)

            mid = (best_bid + best_ask) / 2.0
            exposure += abs(shares) * mid

        results.append(
            PnlBucketResult(
                proxy_wallet=proxy_wallet,
                bucket_type=bucket_type,
                bucket_start=bucket_start,
                realized_pnl=realized_pnl,
                mtm_pnl_estimate=mtm_pnl,
                exposure_notional_estimate=exposure,
                open_position_tokens=open_tokens,
                pricing_source=PRICING_SOURCE,
            )
        )

    return PnlComputeResult(
        buckets=results,
        tokens_priced=len(pricing),
        tokens_skipped_missing_orderbook=sorted(set(tokens_missing_orderbook)),
        tokens_skipped_limit=sorted(set(tokens_skipped_limit)),
        pricing_source=PRICING_SOURCE,
    )
