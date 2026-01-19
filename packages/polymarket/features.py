"""Feature computation for user trade analysis with bucket granularity support."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)

# Supported bucket types
BucketType = Literal["day", "hour", "week"]

# ClickHouse functions for bucket rounding
BUCKET_FUNCTIONS = {
    "day": "toStartOfDay",
    "hour": "toStartOfHour",
    "week": "toStartOfWeek",
}


@dataclass
class BucketFeatures:
    """Computed aggregates for a user per time bucket."""

    proxy_wallet: str
    bucket_type: str  # 'day', 'hour', 'week'
    bucket_start: datetime
    trades_count: int
    buys_count: int
    sells_count: int
    volume: float
    notional: float
    unique_tokens: int
    unique_markets: int
    avg_trade_size: float
    pct_buys: float
    pct_sells: float
    mapping_coverage: float

    def to_row(self) -> list:
        """Convert to ClickHouse row format."""
        return [
            self.proxy_wallet,
            self.bucket_type,
            self.bucket_start,
            self.trades_count,
            self.buys_count,
            self.sells_count,
            self.volume,
            self.notional,
            self.unique_tokens,
            self.unique_markets,
            self.avg_trade_size,
            self.pct_buys,
            self.pct_sells,
            self.mapping_coverage,
            datetime.utcnow(),
        ]


# Keep DailyFeatures for backward compatibility
@dataclass
class DailyFeatures:
    """Computed daily aggregates for a user (backward compatible)."""

    proxy_wallet: str
    bucket_day: date
    trades_count: int
    buys_count: int
    sells_count: int
    volume: float
    notional: float
    unique_tokens: int
    unique_markets: int
    avg_trade_size: float
    pct_buys: float
    pct_sells: float
    mapping_coverage: float

    def to_row(self) -> list:
        """Convert to ClickHouse row format."""
        return [
            self.proxy_wallet,
            self.bucket_day,
            self.trades_count,
            self.buys_count,
            self.sells_count,
            self.volume,
            self.notional,
            self.unique_tokens,
            self.unique_markets,
            self.avg_trade_size,
            self.pct_buys,
            self.pct_sells,
            self.mapping_coverage,
            datetime.utcnow(),
        ]


def compute_features_sql(
    proxy_wallet: str,
    bucket_type: BucketType = "day",
    start_date: Optional[date] = None,
) -> str:
    """
    Generate SQL to compute features for a user with specified bucket granularity.

    Uses LEFT JOIN to market_tokens for mapping coverage and unique_markets.

    Args:
        proxy_wallet: User's proxy wallet address
        bucket_type: Bucket granularity: 'day', 'hour', or 'week'
        start_date: Optional start date filter

    Returns:
        SQL query string
    """
    bucket_func = BUCKET_FUNCTIONS.get(bucket_type, "toStartOfDay")

    where_clause = f"WHERE t.proxy_wallet = '{proxy_wallet}'"
    if start_date:
        where_clause += f" AND toDate(t.ts) >= '{start_date.isoformat()}'"

    return f"""
    SELECT
        t.proxy_wallet,
        '{bucket_type}' AS bucket_type,
        {bucket_func}(t.ts) AS bucket_start,
        count() AS trades_count,
        countIf(upper(t.side) = 'BUY') AS buys_count,
        countIf(upper(t.side) = 'SELL') AS sells_count,
        sum(t.size) AS volume,
        sum(t.size * t.price) AS notional,
        count(DISTINCT t.token_id) AS unique_tokens,
        count(DISTINCT if(length(mt.condition_id) > 0, mt.condition_id, NULL)) AS unique_markets,
        if(count() > 0, sum(t.size) / count(), 0) AS avg_trade_size,
        if(count() > 0, countIf(upper(t.side) = 'BUY') * 100.0 / count(), 0) AS pct_buys,
        if(count() > 0, countIf(upper(t.side) = 'SELL') * 100.0 / count(), 0) AS pct_sells,
        if(count() > 0, countIf(length(mt.token_id) > 0) * 100.0 / count(), 0) AS mapping_coverage
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t.token_id = mt.token_id
    {where_clause}
    GROUP BY t.proxy_wallet, bucket_start
    ORDER BY bucket_start
    """


# Backward compatible function
def compute_daily_features_sql(proxy_wallet: str, start_date: Optional[date] = None) -> str:
    """
    Generate SQL to compute daily features for a user.

    Backward compatible wrapper around compute_features_sql.

    Args:
        proxy_wallet: User's proxy wallet address
        start_date: Optional start date filter

    Returns:
        SQL query string
    """
    where_clause = f"WHERE t.proxy_wallet = '{proxy_wallet}'"
    if start_date:
        where_clause += f" AND toDate(t.ts) >= '{start_date.isoformat()}'"

    return f"""
    SELECT
        t.proxy_wallet,
        toDate(t.ts) AS bucket_day,
        count() AS trades_count,
        countIf(upper(t.side) = 'BUY') AS buys_count,
        countIf(upper(t.side) = 'SELL') AS sells_count,
        sum(t.size) AS volume,
        sum(t.size * t.price) AS notional,
        count(DISTINCT t.token_id) AS unique_tokens,
        count(DISTINCT if(length(mt.condition_id) > 0, mt.condition_id, NULL)) AS unique_markets,
        if(count() > 0, sum(t.size) / count(), 0) AS avg_trade_size,
        if(count() > 0, countIf(upper(t.side) = 'BUY') * 100.0 / count(), 0) AS pct_buys,
        if(count() > 0, countIf(upper(t.side) = 'SELL') * 100.0 / count(), 0) AS pct_sells,
        if(count() > 0, countIf(length(mt.token_id) > 0) * 100.0 / count(), 0) AS mapping_coverage
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t.token_id = mt.token_id
    {where_clause}
    GROUP BY t.proxy_wallet, bucket_day
    ORDER BY bucket_day
    """


def get_insert_columns() -> list[str]:
    """Get column names for inserting daily features (backward compatible)."""
    return [
        "proxy_wallet",
        "bucket_day",
        "trades_count",
        "buys_count",
        "sells_count",
        "volume",
        "notional",
        "unique_tokens",
        "unique_markets",
        "avg_trade_size",
        "pct_buys",
        "pct_sells",
        "mapping_coverage",
        "computed_at",
    ]


def get_bucket_insert_columns() -> list[str]:
    """Get column names for inserting bucket features."""
    return [
        "proxy_wallet",
        "bucket_type",
        "bucket_start",
        "trades_count",
        "buys_count",
        "sells_count",
        "volume",
        "notional",
        "unique_tokens",
        "unique_markets",
        "avg_trade_size",
        "pct_buys",
        "pct_sells",
        "mapping_coverage",
        "computed_at",
    ]
