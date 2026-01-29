"""Opportunity engine helpers for bucketing and validation."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from .pnl import BucketType, get_bucket_start


def normalize_bucket_type(bucket_type: str) -> BucketType:
    """Normalize and validate the bucket type for opportunities."""
    bucket = bucket_type.strip().lower()
    if bucket not in ("day", "hour", "week"):
        raise ValueError("bucket must be one of: day, hour, week")
    return cast(BucketType, bucket)


def get_opportunity_bucket_start(ts: datetime, bucket_type: str) -> datetime:
    """Return the bucket start timestamp for the given bucket type."""
    bucket = normalize_bucket_type(bucket_type)
    return get_bucket_start(ts, bucket)
