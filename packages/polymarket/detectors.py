"""Strategy detectors for identifying trading patterns."""

import json
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class DetectorResult:
    """Result from a strategy detector."""

    proxy_wallet: str
    detector_name: str
    bucket_type: str
    bucket_start: date
    score: float
    label: str
    evidence: dict

    def to_row(self) -> list:
        """Convert to ClickHouse row format."""
        return [
            self.proxy_wallet,
            self.detector_name,
            self.bucket_type,
            self.bucket_start,
            self.score,
            self.label,
            json.dumps(self.evidence),
            datetime.utcnow(),
        ]


class BaseDetector:
    """Base class for all detectors."""

    NAME: str = "BASE"
    DISPLAY_NAME: str = "Base Detector"

    def detect(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "all",
        bucket_start: Optional[date] = None,
        market_tokens_map: Optional[dict] = None,
    ) -> DetectorResult:
        """Run detection on trades. Override in subclasses."""
        raise NotImplementedError


class HoldingStyleDetector(BaseDetector):
    """
    Classifies holding time distribution using FIFO matching.

    Algorithm:
    1. Group trades by token_id
    2. For each token, match BUYs to SELLs using FIFO
    3. Compute hold_minutes for each matched pair
    4. Compute statistics: median, p10, p90
    5. Classify: SCALPER (<1hr median), SWING (1hr-7d), HOLDER (>7d)

    Evidence:
    - median_hold_minutes
    - p10_hold_minutes, p90_hold_minutes
    - matched_trades, unmatched_trades
    - hold_time_distribution (buckets)
    """

    NAME = "HOLDING_STYLE"
    DISPLAY_NAME = "Holding Style"

    # Classification thresholds (in minutes)
    SCALPER_MAX_MINUTES = 60  # < 1 hour
    SWING_MAX_MINUTES = 60 * 24 * 7  # < 7 days

    def detect(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "all",
        bucket_start: Optional[date] = None,
        market_tokens_map: Optional[dict] = None,
    ) -> DetectorResult:
        # Group trades by token_id
        trades_by_token = defaultdict(list)
        for t in trades:
            trades_by_token[t["token_id"]].append(t)

        hold_times_minutes = []
        matched_count = 0
        unmatched_count = 0

        for token_id, token_trades in trades_by_token.items():
            # Sort by timestamp
            sorted_trades = sorted(token_trades, key=lambda x: x["ts"])

            # FIFO matching: maintain queue of buys
            buy_queue = []  # [[ts, remaining_size], ...]

            for trade in sorted_trades:
                side = trade["side"].upper()
                ts = trade["ts"]
                size = trade["size"]

                if side == "BUY":
                    buy_queue.append([ts, size])
                elif side == "SELL" and buy_queue:
                    remaining = size
                    while remaining > 0 and buy_queue:
                        buy_ts, buy_remaining = buy_queue[0]

                        match_size = min(remaining, buy_remaining)

                        # Compute hold time
                        if isinstance(ts, datetime) and isinstance(buy_ts, datetime):
                            delta = ts - buy_ts
                            hold_minutes = delta.total_seconds() / 60
                            hold_times_minutes.append(hold_minutes)
                            matched_count += 1

                        buy_queue[0][1] -= match_size
                        remaining -= match_size

                        if buy_queue[0][1] <= 0:
                            buy_queue.pop(0)

            # Count unmatched buys
            unmatched_count += len(buy_queue)

        # Compute statistics
        if hold_times_minutes:
            median_hold = statistics.median(hold_times_minutes)
            sorted_holds = sorted(hold_times_minutes)
            p10_idx = max(0, int(len(sorted_holds) * 0.1))
            p90_idx = min(len(sorted_holds) - 1, int(len(sorted_holds) * 0.9))
            p10_hold = sorted_holds[p10_idx]
            p90_hold = sorted_holds[p90_idx]
        else:
            median_hold = 0
            p10_hold = 0
            p90_hold = 0

        # Distribution buckets
        buckets = {"<1h": 0, "1h-24h": 0, "1d-7d": 0, ">7d": 0}
        for hm in hold_times_minutes:
            if hm < 60:
                buckets["<1h"] += 1
            elif hm < 60 * 24:
                buckets["1h-24h"] += 1
            elif hm < 60 * 24 * 7:
                buckets["1d-7d"] += 1
            else:
                buckets[">7d"] += 1

        # Classification
        if not hold_times_minutes:
            label = "UNKNOWN"
            score = 0.0
        elif median_hold < self.SCALPER_MAX_MINUTES:
            label = "SCALPER"
            # Score: higher = more scalper-like
            score = 1.0 - (median_hold / self.SCALPER_MAX_MINUTES)
        elif median_hold < self.SWING_MAX_MINUTES:
            label = "SWING"
            # Score: normalized within swing range
            score = (median_hold - self.SCALPER_MAX_MINUTES) / (
                self.SWING_MAX_MINUTES - self.SCALPER_MAX_MINUTES
            )
        else:
            label = "HOLDER"
            # Score: capped at 1.0
            score = min(1.0, median_hold / (self.SWING_MAX_MINUTES * 2))

        evidence = {
            "median_hold_minutes": round(median_hold, 2),
            "p10_hold_minutes": round(p10_hold, 2),
            "p90_hold_minutes": round(p90_hold, 2),
            "matched_trades": matched_count,
            "unmatched_buys": unmatched_count,
            "hold_distribution": buckets,
        }

        return DetectorResult(
            proxy_wallet=proxy_wallet,
            detector_name=self.NAME,
            bucket_type=bucket_type,
            bucket_start=bucket_start or date.today(),
            score=round(score, 4),
            label=label,
            evidence=evidence,
        )


class DCALadderingDetector(BaseDetector):
    """
    Detects dollar-cost averaging or ladder patterns.

    Algorithm:
    1. Group trades by token_id + side
    2. For each group, analyze:
       - Consistency of trade sizes (low std/mean ratio)
       - Regularity of intervals (coefficient of variation)
       - Number of sequential trades in same direction
    3. Score based on pattern strength

    Evidence:
    - tokens_with_dca_pattern
    - avg_trades_per_ladder
    - size_consistency (std/mean)
    - interval_consistency
    """

    NAME = "DCA_LADDERING"
    DISPLAY_NAME = "DCA / Laddering"

    MIN_TRADES_FOR_PATTERN = 3
    SIZE_CONSISTENCY_THRESHOLD = 0.3  # std/mean < 0.3 = consistent

    def detect(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "all",
        bucket_start: Optional[date] = None,
        market_tokens_map: Optional[dict] = None,
    ) -> DetectorResult:
        # Group by token_id + side
        groups = defaultdict(list)
        for t in trades:
            key = (t["token_id"], t["side"].upper())
            groups[key].append(t)

        dca_patterns_found = 0
        pattern_details = []

        for (token_id, side), group_trades in groups.items():
            if len(group_trades) < self.MIN_TRADES_FOR_PATTERN:
                continue

            # Sort by time
            sorted_trades = sorted(group_trades, key=lambda x: x["ts"])

            # Analyze size consistency
            sizes = [t["size"] for t in sorted_trades]
            if sizes:
                mean_size = statistics.mean(sizes)
                if mean_size > 0 and len(sizes) > 1:
                    std_size = statistics.stdev(sizes)
                    size_cv = std_size / mean_size
                else:
                    size_cv = 0
            else:
                size_cv = float("inf")

            # Analyze time intervals
            interval_cv = float("inf")
            if len(sorted_trades) >= 2:
                intervals = []
                for i in range(1, len(sorted_trades)):
                    if isinstance(sorted_trades[i]["ts"], datetime) and isinstance(
                        sorted_trades[i - 1]["ts"], datetime
                    ):
                        delta = (
                            sorted_trades[i]["ts"] - sorted_trades[i - 1]["ts"]
                        ).total_seconds() / 3600
                        intervals.append(delta)

                if intervals and len(intervals) > 1:
                    mean_interval = statistics.mean(intervals)
                    if mean_interval > 0:
                        std_interval = statistics.stdev(intervals)
                        interval_cv = std_interval / mean_interval

            # Check if this is a DCA pattern
            if size_cv < self.SIZE_CONSISTENCY_THRESHOLD:
                dca_patterns_found += 1
                pattern_details.append(
                    {
                        "token_id": token_id[:20] + "..." if len(token_id) > 20 else token_id,
                        "side": side,
                        "trade_count": len(sorted_trades),
                        "size_cv": round(size_cv, 4),
                        "interval_cv": round(interval_cv, 4)
                        if interval_cv != float("inf")
                        else None,
                    }
                )

        # Score: ratio of tokens showing DCA patterns
        total_groups = len(
            [g for g in groups.values() if len(g) >= self.MIN_TRADES_FOR_PATTERN]
        )
        if total_groups > 0:
            score = dca_patterns_found / total_groups
            label = "DCA_LIKELY" if score > 0.3 else "RANDOM"
        else:
            score = 0.0
            label = "INSUFFICIENT_DATA"

        evidence = {
            "tokens_with_dca_pattern": dca_patterns_found,
            "total_token_groups_analyzed": total_groups,
            "pattern_details": pattern_details[:10],  # Top 10
        }

        return DetectorResult(
            proxy_wallet=proxy_wallet,
            detector_name=self.NAME,
            bucket_type=bucket_type,
            bucket_start=bucket_start or date.today(),
            score=round(score, 4),
            label=label,
            evidence=evidence,
        )


class MarketSelectionBiasDetector(BaseDetector):
    """
    Detects concentration in specific categories/markets.

    Algorithm:
    1. Join trades with market_tokens to get category
    2. Compute volume/trades by category
    3. Calculate Herfindahl-Hirschman Index (HHI) for concentration
    4. Classify: DIVERSIFIED (HHI < 0.15), MODERATE (0.15-0.25), CONCENTRATED (> 0.25)

    Evidence:
    - hhi_score
    - top_categories with percentages
    - unique_markets_traded
    - mapping_coverage (% of trades with category)
    """

    NAME = "MARKET_SELECTION_BIAS"
    DISPLAY_NAME = "Market Concentration"

    def detect(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "all",
        bucket_start: Optional[date] = None,
        market_tokens_map: Optional[dict] = None,
    ) -> DetectorResult:
        """
        Requires market_tokens_map: {token_id: {"category": ..., "condition_id": ...}}
        """
        market_tokens_map = market_tokens_map or {}

        # Aggregate by category
        category_volume = defaultdict(float)
        category_trades = defaultdict(int)
        mapped_count = 0
        unique_markets = set()

        for t in trades:
            token_id = t["token_id"]
            size = t["size"]

            if token_id in market_tokens_map:
                mapped_count += 1
                info = market_tokens_map[token_id]
                category = info.get("category", "UNKNOWN") or "UNKNOWN"
                category_volume[category] += size
                category_trades[category] += 1
                unique_markets.add(info.get("condition_id", token_id))
            else:
                category_volume["UNMAPPED"] += size
                category_trades["UNMAPPED"] += 1

        # Calculate HHI
        total_volume = sum(category_volume.values())
        if total_volume > 0:
            shares = [(cat, vol / total_volume) for cat, vol in category_volume.items()]
            hhi = sum(share**2 for _, share in shares)
        else:
            hhi = 0

        # Top categories
        sorted_cats = sorted(category_volume.items(), key=lambda x: -x[1])[:5]
        top_categories = [
            {
                "category": cat,
                "volume": round(vol, 2),
                "pct": round(vol * 100 / total_volume, 2) if total_volume > 0 else 0,
            }
            for cat, vol in sorted_cats
        ]

        # Classification
        if hhi < 0.15:
            label = "DIVERSIFIED"
        elif hhi < 0.25:
            label = "MODERATE"
        else:
            label = "CONCENTRATED"

        mapping_coverage = (mapped_count / len(trades) * 100) if trades else 0

        evidence = {
            "hhi_score": round(hhi, 4),
            "top_categories": top_categories,
            "unique_markets_traded": len(unique_markets),
            "mapping_coverage_pct": round(mapping_coverage, 2),
        }

        return DetectorResult(
            proxy_wallet=proxy_wallet,
            detector_name=self.NAME,
            bucket_type=bucket_type,
            bucket_start=bucket_start or date.today(),
            score=round(hhi, 4),
            label=label,
            evidence=evidence,
        )


class CompleteSetArbDetector(BaseDetector):
    """
    Detects complete set arbitrage: buying both outcomes and closing quickly.

    Algorithm:
    1. Join trades with market_tokens to get condition_id and outcome_index
    2. For each market (condition_id), check if user bought both outcomes
    3. Check if positions were closed within threshold (e.g., 24 hours)
    4. Score based on frequency of arb-like behavior

    Evidence:
    - potential_arb_events
    - avg_close_time_hours
    - markets_with_both_outcomes
    """

    NAME = "COMPLETE_SET_ARBISH"
    DISPLAY_NAME = "Complete-Set Arb"

    CLOSE_THRESHOLD_HOURS = 24  # Arb if closed within this window

    def detect(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "all",
        bucket_start: Optional[date] = None,
        market_tokens_map: Optional[dict] = None,
    ) -> DetectorResult:
        """
        Requires market_tokens_map with condition_id mapping.
        """
        market_tokens_map = market_tokens_map or {}

        # Group trades by condition_id
        trades_by_market = defaultdict(list)

        for t in trades:
            token_id = t["token_id"]
            if token_id in market_tokens_map:
                info = market_tokens_map[token_id]
                condition_id = info.get("condition_id", "")
                if condition_id:
                    trades_by_market[condition_id].append(
                        {
                            **t,
                            "outcome_index": info.get("outcome_index", 0),
                            "outcome_name": info.get("outcome_name", ""),
                        }
                    )

        arb_events = []
        markets_with_both = 0

        for condition_id, market_trades in trades_by_market.items():
            # Check if both outcomes were traded
            outcomes_traded = set(t["outcome_index"] for t in market_trades)

            if len(outcomes_traded) >= 2:
                markets_with_both += 1

                # Sort by time and check for quick close pattern
                sorted_trades = sorted(market_trades, key=lambda x: x["ts"])

                # Find first buy of each outcome
                first_buys = {}
                for t in sorted_trades:
                    if (
                        t["side"].upper() == "BUY"
                        and t["outcome_index"] not in first_buys
                    ):
                        first_buys[t["outcome_index"]] = t["ts"]

                # Check if both bought within threshold
                if len(first_buys) >= 2:
                    buy_times = list(first_buys.values())
                    if all(isinstance(bt, datetime) for bt in buy_times):
                        time_diff = (
                            abs((buy_times[0] - buy_times[1]).total_seconds()) / 3600
                        )

                        if time_diff < self.CLOSE_THRESHOLD_HOURS:
                            arb_events.append(
                                {
                                    "condition_id": condition_id[:20] + "..."
                                    if len(condition_id) > 20
                                    else condition_id,
                                    "time_diff_hours": round(time_diff, 2),
                                }
                            )

        # Score
        if markets_with_both > 0:
            score = len(arb_events) / markets_with_both
            label = "ARB_LIKELY" if score > 0.3 else "NORMAL"
        else:
            score = 0.0
            label = "INSUFFICIENT_DATA"

        avg_close_time = 0
        if arb_events:
            avg_close_time = statistics.mean([e["time_diff_hours"] for e in arb_events])

        evidence = {
            "potential_arb_events": len(arb_events),
            "markets_with_both_outcomes": markets_with_both,
            "avg_close_time_hours": round(avg_close_time, 2),
            "arb_details": arb_events[:10],  # Top 10
        }

        return DetectorResult(
            proxy_wallet=proxy_wallet,
            detector_name=self.NAME,
            bucket_type=bucket_type,
            bucket_start=bucket_start or date.today(),
            score=round(score, 4),
            label=label,
            evidence=evidence,
        )


def _get_bucket_start(ts: datetime, bucket_type: str) -> datetime:
    """Get the start of the bucket period for a given timestamp."""
    if bucket_type == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    elif bucket_type == "week":
        # Start of week (Monday)
        days_since_monday = ts.weekday()
        start = ts - timedelta(days=days_since_monday)
        return start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # day
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)


def _group_trades_by_bucket(trades: list[dict], bucket_type: str) -> dict[datetime, list[dict]]:
    """Group trades by their bucket start time."""
    grouped = defaultdict(list)
    for trade in trades:
        ts = trade.get("ts")
        if isinstance(ts, datetime):
            bucket_start = _get_bucket_start(ts, bucket_type)
            grouped[bucket_start].append(trade)
    return dict(grouped)


class DetectorRunner:
    """Runs all detectors and aggregates results."""

    DETECTORS = [
        HoldingStyleDetector(),
        DCALadderingDetector(),
        MarketSelectionBiasDetector(),
        CompleteSetArbDetector(),
    ]

    def run_all(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "all",
        bucket_start: Optional[date] = None,
        market_tokens_map: Optional[dict] = None,
    ) -> list[DetectorResult]:
        """Run all detectors on all trades and return results."""
        results = []

        for detector in self.DETECTORS:
            try:
                result = detector.detect(
                    trades=trades,
                    proxy_wallet=proxy_wallet,
                    bucket_type=bucket_type,
                    bucket_start=bucket_start,
                    market_tokens_map=market_tokens_map,
                )
                results.append(result)
                logger.info(
                    f"Detector {detector.NAME}: score={result.score}, label={result.label}"
                )
            except Exception as e:
                logger.error(f"Detector {detector.NAME} failed: {e}")
                results.append(
                    DetectorResult(
                        proxy_wallet=proxy_wallet,
                        detector_name=detector.NAME,
                        bucket_type=bucket_type,
                        bucket_start=bucket_start or date.today(),
                        score=0.0,
                        label="ERROR",
                        evidence={"error": str(e)},
                    )
                )

        return results

    def run_all_by_bucket(
        self,
        trades: list[dict],
        proxy_wallet: str,
        bucket_type: str = "day",
        market_tokens_map: Optional[dict] = None,
    ) -> list[DetectorResult]:
        """
        Run all detectors for each time bucket.

        Groups trades by bucket_type (day/hour/week) and runs detectors
        on each bucket's trades separately.

        Args:
            trades: List of trade dicts with 'ts' datetime field
            proxy_wallet: User's proxy wallet address
            bucket_type: Bucket granularity: 'day', 'hour', 'week'
            market_tokens_map: Token ID to market info mapping

        Returns:
            List of DetectorResults for all buckets
        """
        if bucket_type == "all":
            # No bucketing - run on all trades at once
            return self.run_all(
                trades=trades,
                proxy_wallet=proxy_wallet,
                bucket_type="all",
                bucket_start=date.today(),
                market_tokens_map=market_tokens_map,
            )

        # Group trades by bucket
        grouped_trades = _group_trades_by_bucket(trades, bucket_type)

        logger.info(f"Running detectors for {len(grouped_trades)} {bucket_type} buckets")

        all_results = []
        for bucket_start_dt, bucket_trades in sorted(grouped_trades.items()):
            bucket_start = bucket_start_dt.date() if isinstance(bucket_start_dt, datetime) else bucket_start_dt

            results = self.run_all(
                trades=bucket_trades,
                proxy_wallet=proxy_wallet,
                bucket_type=bucket_type,
                bucket_start=bucket_start,
                market_tokens_map=market_tokens_map,
            )
            all_results.extend(results)

        logger.info(f"Generated {len(all_results)} detector results across {len(grouped_trades)} buckets")
        return all_results


def get_insert_columns() -> list[str]:
    """Get column names for inserting detector results."""
    return [
        "proxy_wallet",
        "detector_name",
        "bucket_type",
        "bucket_start",
        "score",
        "label",
        "evidence_json",
        "computed_at",
    ]


# Human-friendly display name mappings
DETECTOR_DISPLAY_NAMES: dict[str, str] = {
    "HOLDING_STYLE": "Holding Style",
    "DCA_LADDERING": "DCA / Laddering",
    "MARKET_SELECTION_BIAS": "Market Concentration",
    "COMPLETE_SET_ARBISH": "Complete-Set Arb",
}

LABEL_DISPLAY_NAMES: dict[str, str] = {
    # Holding Style labels
    "SCALPER": "Scalper",
    "SWING": "Swing Trader",
    "HOLDER": "Long-Term Holder",
    # DCA labels
    "DCA_LIKELY": "DCA Likely",
    "RANDOM": "Random Sizing",
    # Market Concentration labels
    "DIVERSIFIED": "Diversified",
    "MODERATE": "Moderate Focus",
    "CONCENTRATED": "Concentrated",
    # Arb labels
    "ARB_LIKELY": "Arb Likely",
    "NORMAL": "Normal",
    # Common labels
    "INSUFFICIENT_DATA": "Insufficient Data",
    "UNKNOWN": "Unknown",
    "ERROR": "Error",
}


def get_detector_display_name(detector_name: str) -> str:
    """Get human-friendly display name for a detector."""
    return DETECTOR_DISPLAY_NAMES.get(detector_name, detector_name)


def get_label_display_name(label: str) -> str:
    """Get human-friendly display name for a label."""
    return LABEL_DISPLAY_NAMES.get(label, label)
