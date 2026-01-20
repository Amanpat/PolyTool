"""Polymarket API client package."""

from .http_client import HttpClient
from .gamma import GammaClient, Market, MarketToken, MarketsFetchResult
from .data_api import DataApiClient
from .clob import ClobClient, OrderBookTop
from .features import (
    DailyFeatures,
    BucketFeatures,
    compute_daily_features_sql,
    compute_features_sql,
    get_bucket_insert_columns,
)
from .detectors import DetectorRunner, DetectorResult
from .backfill import backfill_missing_mappings
from .pnl import PnlBucketResult, PnlComputeResult, compute_user_pnl_buckets

__all__ = [
    "HttpClient",
    "GammaClient",
    "DataApiClient",
    "ClobClient",
    "OrderBookTop",
    "Market",
    "MarketToken",
    "MarketsFetchResult",
    "DailyFeatures",
    "BucketFeatures",
    "compute_daily_features_sql",
    "compute_features_sql",
    "get_bucket_insert_columns",
    "DetectorRunner",
    "DetectorResult",
    "backfill_missing_mappings",
    "PnlBucketResult",
    "PnlComputeResult",
    "compute_user_pnl_buckets",
]
