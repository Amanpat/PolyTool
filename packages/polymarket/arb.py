"""Arb feasibility computation with dynamic fees and slippage.

Identifies arb-like activity (buying both outcomes of a market and closing quickly)
and estimates profitability by computing actual fees and slippage.
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional, Literal
from collections import defaultdict

from .clob import ClobClient
from .fees import compute_taker_fee_usdc
from .slippage import estimate_slippage_bps

logger = logging.getLogger(__name__)

BucketType = Literal["day", "hour", "week"]
Confidence = Literal["high", "medium", "low"]

# Arb detection threshold: both outcomes bought within this window
CLOSE_THRESHOLD_HOURS = 24


@dataclass
class ArbFeasibilityBucket:
    """Computed arb feasibility metrics for a market/bucket."""

    proxy_wallet: str
    bucket_type: str
    bucket_start: datetime
    condition_id: str
    gross_edge_est_bps: Optional[float]  # Estimated gross edge, None if unknown
    total_fees_est_usdc: float
    total_slippage_est_usdc: float
    net_edge_est_bps: Optional[float]  # gross - costs, None if gross unknown
    break_even_notional_usd: Optional[float]  # Notional needed to cover costs
    confidence: Confidence
    evidence: dict

    def to_row(self) -> list:
        """Convert to ClickHouse row format."""
        return [
            self.proxy_wallet,
            self.bucket_type,
            self.bucket_start,
            self.condition_id,
            self.gross_edge_est_bps,
            float(self.total_fees_est_usdc),
            float(self.total_slippage_est_usdc),
            self.net_edge_est_bps,
            self.break_even_notional_usd,
            self.confidence,
            json.dumps(self.evidence),
            datetime.utcnow(),
        ]


@dataclass
class ArbFeasibilityResult:
    """Aggregate result from arb feasibility computation."""

    buckets: list[ArbFeasibilityBucket]
    fee_rates_fetched: int
    slippage_estimates: int
    tokens_skipped_limit: list[str]
    tokens_skipped_missing_book: list[str]
    markets_analyzed: int


def _get_bucket_start(ts: datetime, bucket_type: BucketType) -> datetime:
    """Get the start of the bucket period for a given timestamp."""
    if bucket_type == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    elif bucket_type == "week":
        days_since_monday = ts.weekday()
        start = ts - timedelta(days=days_since_monday)
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # day
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def _identify_arb_events(
    trades: list[dict],
    market_tokens_map: dict,
) -> list[dict]:
    """
    Identify potential arb events from trades.

    An arb event is when both outcomes of a market are bought within the threshold window.

    Returns list of arb event dicts with:
        - condition_id
        - tokens: list of token_ids involved
        - trades: list of trades
        - time_span_hours: time between first and last trade
        - bucket_start: bucket start time
    """
    # Group trades by condition_id
    # Use condition_id from trade if available, otherwise from market_tokens_map
    trades_by_market: dict[str, list[dict]] = defaultdict(list)

    for trade in trades:
        token_id = trade.get("token_id", "")

        # Try to get condition_id from the trade itself first
        condition_id = trade.get("condition_id", "")

        # Get outcome info from market_tokens_map if available
        if token_id in market_tokens_map:
            info = market_tokens_map[token_id]
            if not condition_id:
                condition_id = info.get("condition_id", "")
            outcome_index = info.get("outcome_index", None)
            outcome_name = info.get("outcome_name", "")
        else:
            # No mapping - use token_id as pseudo outcome_index for grouping
            outcome_index = None
            outcome_name = ""

        if condition_id:
            trades_by_market[condition_id].append({
                **trade,
                "outcome_index": outcome_index,
                "outcome_name": outcome_name,
            })

    arb_events = []

    for condition_id, market_trades in trades_by_market.items():
        # Check if multiple outcomes (tokens) were bought
        # Use outcome_index if available, otherwise fall back to token_id
        outcomes_traded = set()
        for t in market_trades:
            if t.get("side", "").upper() == "BUY":
                # Use outcome_index if available, otherwise use token_id
                outcome_key = t.get("outcome_index")
                if outcome_key is None:
                    outcome_key = t.get("token_id", "")
                outcomes_traded.add(outcome_key)

        if len(outcomes_traded) >= 2:
            # Sort by time
            sorted_trades = sorted(market_trades, key=lambda x: x["ts"])

            # Find first buy of each outcome
            first_buys: dict = {}
            for t in sorted_trades:
                if t.get("side", "").upper() == "BUY":
                    outcome_key = t.get("outcome_index")
                    if outcome_key is None:
                        outcome_key = t.get("token_id", "")
                    if outcome_key not in first_buys:
                        first_buys[outcome_key] = t["ts"]

            # Check if bought within threshold
            if len(first_buys) >= 2:
                buy_times = list(first_buys.values())
                if all(isinstance(bt, datetime) for bt in buy_times):
                    min_time = min(buy_times)
                    max_time = max(buy_times)
                    time_span_hours = (max_time - min_time).total_seconds() / 3600

                    if time_span_hours <= CLOSE_THRESHOLD_HOURS:
                        tokens_involved = list(set(t["token_id"] for t in market_trades))
                        arb_events.append({
                            "condition_id": condition_id,
                            "tokens": tokens_involved,
                            "trades": market_trades,
                            "time_span_hours": time_span_hours,
                            "first_trade_ts": min_time,
                        })

    return arb_events


def _estimate_arb_costs(
    arb_event: dict,
    clob_client: ClobClient,
    fee_cache: dict,
    book_cache: dict,
    cache_ttl_seconds: int = 30,
) -> dict:
    """
    Estimate costs for an arb event.

    Returns dict with:
        - total_fees_usdc
        - total_slippage_usdc
        - fee_details: {token_id: fee_rate_bps}
        - slippage_details: {token_id_side: slippage_bps}
        - confidence
        - reasons: list of confidence reasons
    """
    now_ts = time.time()
    trades = arb_event["trades"]
    tokens = arb_event["tokens"]

    total_fees_usdc = 0.0
    total_slippage_usdc = 0.0
    fee_details = {}
    slippage_details = {}
    book_timestamps = {}
    reasons = []
    overall_confidence: Confidence = "high"

    for token_id in tokens:
        # Fetch fee rate (with caching)
        cached_fee = fee_cache.get(token_id)
        if cached_fee and now_ts - cached_fee["fetched_at"] <= cache_ttl_seconds:
            fee_rate_bps = cached_fee["fee_rate_bps"]
        else:
            fee_info = clob_client.get_fee_rate(token_id)
            if fee_info:
                fee_rate_bps = fee_info.fee_rate_bps
                fee_cache[token_id] = {
                    "fee_rate_bps": fee_rate_bps,
                    "fetched_at": now_ts,
                }
            else:
                fee_rate_bps = 0.0
                reasons.append(f"Failed to fetch fee rate for {token_id[:20]}...")

        fee_details[token_id] = fee_rate_bps

        # Fetch orderbook (with caching)
        cached_book = book_cache.get(token_id)
        if cached_book and now_ts - cached_book["fetched_at"] <= cache_ttl_seconds:
            book = cached_book["book"]
            book_ts = cached_book["book_ts"]
        else:
            try:
                book = clob_client.fetch_book(token_id)
                book_ts = datetime.utcnow().isoformat()
                book_cache[token_id] = {
                    "book": book,
                    "book_ts": book_ts,
                    "fetched_at": now_ts,
                }
            except Exception as e:
                logger.warning(f"Failed to fetch book for {token_id}: {e}")
                book = {}
                book_ts = None
                overall_confidence = "low"
                reasons.append(f"Failed to fetch orderbook for {token_id[:20]}...")

        book_timestamps[token_id] = book_ts

        # Compute fees and slippage for each trade on this token
        token_trades = [t for t in trades if t["token_id"] == token_id]

        for trade in token_trades:
            size = float(trade.get("size", 0) or 0)
            price = float(trade.get("price", 0) or 0)
            side = trade.get("side", "").upper()

            if size <= 0 or price <= 0:
                continue

            # Compute fee
            fee_usdc = compute_taker_fee_usdc(size, price, fee_rate_bps)
            total_fees_usdc += fee_usdc

            # Estimate slippage
            if book:
                slip_result = estimate_slippage_bps(book, side, size)
                slippage_key = f"{token_id[:20]}_{side}"
                slippage_details[slippage_key] = slip_result.slippage_bps

                if slip_result.slippage_bps is not None and slip_result.mid is not None:
                    # Convert slippage bps to USDC: size * mid * (slippage_bps / 10000)
                    slippage_usdc = size * slip_result.mid * (slip_result.slippage_bps / 10000)
                    total_slippage_usdc += slippage_usdc

                # Adjust confidence
                if slip_result.confidence == "low":
                    if overall_confidence == "high":
                        overall_confidence = "medium"
                    reasons.append(slip_result.reason)
                elif slip_result.confidence == "medium" and overall_confidence == "high":
                    overall_confidence = "medium"

    return {
        "total_fees_usdc": total_fees_usdc,
        "total_slippage_usdc": total_slippage_usdc,
        "fee_details": fee_details,
        "slippage_details": slippage_details,
        "book_timestamps": book_timestamps,
        "confidence": overall_confidence,
        "reasons": reasons,
    }


def compute_arb_feasibility_buckets(
    proxy_wallet: str,
    trades: list[dict],
    market_tokens_map: dict,
    bucket_type: BucketType,
    clob_client: ClobClient,
    cache_ttl_seconds: int = 30,
    max_tokens_per_run: int = 200,
    clickhouse_client: Optional[object] = None,
    snapshot_max_age_seconds: Optional[int] = None,
) -> ArbFeasibilityResult:
    """
    Compute arb feasibility for a user's trades.

    Identifies arb-like events and estimates costs (fees + slippage).

    Args:
        proxy_wallet: User's proxy wallet address
        trades: List of trade dicts with ts, token_id, side, size, price
        market_tokens_map: {token_id: {condition_id, outcome_index, outcome_name}}
        bucket_type: Bucket granularity ('day', 'hour', 'week')
        clob_client: ClobClient for API calls
        cache_ttl_seconds: Cache TTL for fee/book data
        max_tokens_per_run: Max tokens to process per run
        clickhouse_client: Optional ClickHouse client for snapshot pricing (unused)
        snapshot_max_age_seconds: Optional max age for snapshots (unused)

    Returns:
        ArbFeasibilityResult with computed buckets and diagnostics
    """
    if bucket_type not in ("day", "hour", "week"):
        raise ValueError(f"Unsupported bucket_type: {bucket_type}")

    if not trades or not market_tokens_map:
        return ArbFeasibilityResult(
            buckets=[],
            fee_rates_fetched=0,
            slippage_estimates=0,
            tokens_skipped_limit=[],
            tokens_skipped_missing_book=[],
            markets_analyzed=0,
        )

    # Identify arb events
    arb_events = _identify_arb_events(trades, market_tokens_map)
    logger.info(f"Found {len(arb_events)} potential arb events")

    if not arb_events:
        return ArbFeasibilityResult(
            buckets=[],
            fee_rates_fetched=0,
            slippage_estimates=0,
            tokens_skipped_limit=[],
            tokens_skipped_missing_book=[],
            markets_analyzed=0,
        )

    # Collect all tokens involved
    all_tokens = set()
    for event in arb_events:
        all_tokens.update(event["tokens"])

    # Limit tokens if needed
    all_tokens_list = sorted(all_tokens)
    if max_tokens_per_run > 0 and len(all_tokens_list) > max_tokens_per_run:
        tokens_to_process = set(all_tokens_list[:max_tokens_per_run])
        tokens_skipped_limit = all_tokens_list[max_tokens_per_run:]
        logger.warning(
            f"Limiting to {max_tokens_per_run} tokens, skipping {len(tokens_skipped_limit)}"
        )
    else:
        tokens_to_process = all_tokens
        tokens_skipped_limit = []

    # Filter events to only those with processable tokens
    filtered_events = []
    for event in arb_events:
        event_tokens = set(event["tokens"])
        if event_tokens.issubset(tokens_to_process):
            filtered_events.append(event)
        else:
            # Log but continue
            missing = event_tokens - tokens_to_process
            logger.debug(f"Skipping event for {event['condition_id']}: tokens {missing} over limit")

    # Caches
    fee_cache: dict = {}
    book_cache: dict = {}
    tokens_missing_book: list[str] = []

    # Process each event
    buckets: list[ArbFeasibilityBucket] = []

    for event in filtered_events:
        condition_id = event["condition_id"]
        first_trade_ts = event["first_trade_ts"]
        bucket_start = _get_bucket_start(first_trade_ts, bucket_type)

        # Estimate costs
        cost_result = _estimate_arb_costs(
            event,
            clob_client,
            fee_cache,
            book_cache,
            cache_ttl_seconds,
        )

        # Compute notional for the arb event
        event_trades = event["trades"]
        total_notional = sum(
            float(t.get("size", 0) or 0) * float(t.get("price", 0) or 0)
            for t in event_trades
        )

        # Compute total costs
        total_fees = cost_result["total_fees_usdc"]
        total_slippage = cost_result["total_slippage_usdc"]
        total_costs = total_fees + total_slippage

        # Estimate gross edge - for complete set arb, the edge is typically
        # the deviation from parity (sum of outcome prices != 1.0)
        # We don't have enough info to compute this precisely, so leave as None
        gross_edge_est_bps = None
        net_edge_est_bps = None

        # Break-even notional: how much notional to cover costs
        # If we knew the edge rate, we could compute: costs / edge_rate
        # Without that, we can estimate based on typical edges (1-5%)
        # Using a conservative 1% edge assumption for break-even
        assumed_edge_rate = 0.01  # 1%
        if total_costs > 0:
            break_even_notional = total_costs / assumed_edge_rate
        else:
            break_even_notional = None

        # Build evidence
        event_counts = defaultdict(int)
        example_tx_hashes = []
        for t in event_trades:
            side = t.get("side", "UNKNOWN").upper()
            event_counts[side] += 1
            tx_hash = t.get("transaction_hash", "")
            if tx_hash and tx_hash not in example_tx_hashes:
                example_tx_hashes.append(tx_hash)
                if len(example_tx_hashes) >= 5:
                    break

        evidence = {
            "event_counts": dict(event_counts),
            "example_tx_hashes": example_tx_hashes[:5],
            "tokens_involved": event["tokens"],
            "markets_involved": [condition_id],
            "fee_rate_bps_values": cost_result["fee_details"],
            "slippage_bps_values": cost_result["slippage_details"],
            "book_timestamps": cost_result["book_timestamps"],
            "time_span_hours": round(event["time_span_hours"], 2),
            "total_notional_usd": round(total_notional, 2),
            "assumed_edge_rate_for_break_even": assumed_edge_rate,
            "reasons": cost_result["reasons"][:5],
        }

        buckets.append(
            ArbFeasibilityBucket(
                proxy_wallet=proxy_wallet,
                bucket_type=bucket_type,
                bucket_start=bucket_start,
                condition_id=condition_id,
                gross_edge_est_bps=gross_edge_est_bps,
                total_fees_est_usdc=total_fees,
                total_slippage_est_usdc=total_slippage,
                net_edge_est_bps=net_edge_est_bps,
                break_even_notional_usd=break_even_notional,
                confidence=cost_result["confidence"],
                evidence=evidence,
            )
        )

    # Collect tokens with missing books
    for token_id, cache_entry in book_cache.items():
        if not cache_entry.get("book"):
            tokens_missing_book.append(token_id)

    return ArbFeasibilityResult(
        buckets=buckets,
        fee_rates_fetched=len(fee_cache),
        slippage_estimates=sum(
            len(b.evidence.get("slippage_bps_values", {})) for b in buckets
        ),
        tokens_skipped_limit=tokens_skipped_limit,
        tokens_skipped_missing_book=sorted(set(tokens_missing_book)),
        markets_analyzed=len(arb_events),
    )


def get_insert_columns() -> list[str]:
    """Get column names for inserting arb feasibility results."""
    return [
        "proxy_wallet",
        "bucket_type",
        "bucket_start",
        "condition_id",
        "gross_edge_est_bps",
        "total_fees_est_usdc",
        "total_slippage_est_usdc",
        "net_edge_est_bps",
        "break_even_notional_usd",
        "confidence",
        "evidence_json",
        "computed_at",
    ]
