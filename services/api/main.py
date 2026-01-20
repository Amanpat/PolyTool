"""PolyTool API service for username resolution and trade ingestion."""

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import clickhouse_connect

# Add packages to path for local imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.gamma import GammaClient
from polymarket.data_api import DataApiClient
from polymarket.clob import ClobClient
from polymarket.features import (
    compute_daily_features_sql,
    compute_features_sql,
    get_insert_columns as get_features_columns,
    get_bucket_insert_columns,
)
from polymarket.detectors import DetectorRunner, get_insert_columns as get_detector_columns
from polymarket.backfill import backfill_missing_mappings
from polymarket.pnl import compute_user_pnl_buckets
from polymarket.arb import compute_arb_feasibility_buckets, get_insert_columns as get_arb_columns

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Configuration from environment
GAMMA_API_BASE = os.getenv("GAMMA_API_BASE", "https://gamma-api.polymarket.com")
DATA_API_BASE = os.getenv("DATA_API_BASE", "https://data-api.polymarket.com")
INGEST_MAX_PAGES_DEFAULT = int(os.getenv("INGEST_MAX_PAGES_DEFAULT", "50"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
CLOB_API_BASE = os.getenv("CLOB_API_BASE", "https://clob.polymarket.com")
PNL_BUCKET_DEFAULT = os.getenv("PNL_BUCKET_DEFAULT", "day")
PNL_ORDERBOOK_CACHE_SECONDS = int(os.getenv("PNL_ORDERBOOK_CACHE_SECONDS", "30"))
PNL_MAX_TOKENS_PER_RUN = int(os.getenv("PNL_MAX_TOKENS_PER_RUN", "200"))
PNL_HTTP_TIMEOUT_SECONDS = float(os.getenv("PNL_HTTP_TIMEOUT_SECONDS", "20"))
ARB_CACHE_SECONDS = int(os.getenv("ARB_CACHE_SECONDS", "30"))
ARB_MAX_TOKENS_PER_RUN = int(os.getenv("ARB_MAX_TOKENS_PER_RUN", "200"))

# ClickHouse configuration
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "polyttool_admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "polyttool_admin")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "polyttool")

# Initialize FastAPI
app = FastAPI(
    title="PolyTool API",
    description="API for Polymarket data ingestion and analysis",
    version="0.5.0",
)

# Initialize clients
gamma_client = GammaClient(base_url=GAMMA_API_BASE, timeout=HTTP_TIMEOUT_SECONDS)
data_api_client = DataApiClient(base_url=DATA_API_BASE, timeout=HTTP_TIMEOUT_SECONDS)
clob_client = ClobClient(base_url=CLOB_API_BASE, timeout=PNL_HTTP_TIMEOUT_SECONDS)


def get_clickhouse_client():
    """Create ClickHouse client connection."""
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


# Request/Response models
class ResolveRequest(BaseModel):
    """Request body for /api/resolve endpoint."""

    input: str = Field(..., description="Username (with or without @) or wallet address (0x...)")


class ResolveResponse(BaseModel):
    """Response body for /api/resolve endpoint."""

    proxy_wallet: str
    username: str
    profile: dict


class IngestTradesRequest(BaseModel):
    """Request body for /api/ingest/trades endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    max_pages: int = Field(default=50, ge=1, le=100, description="Maximum pages to fetch")


class IngestTradesResponse(BaseModel):
    """Response body for /api/ingest/trades endpoint."""

    proxy_wallet: str
    pages_fetched: int
    rows_fetched_total: int
    rows_written: int
    distinct_trade_uids_total: int


class IngestActivityRequest(BaseModel):
    """Request body for /api/ingest/activity endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    max_pages: int = Field(default=50, ge=1, le=100, description="Maximum pages to fetch")


class IngestActivityResponse(BaseModel):
    """Response body for /api/ingest/activity endpoint."""

    proxy_wallet: str
    pages_fetched: int
    rows_fetched_total: int
    rows_written: int
    distinct_activity_uids_total: int


class IngestPositionsRequest(BaseModel):
    """Request body for /api/ingest/positions endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")


class IngestPositionsResponse(BaseModel):
    """Response body for /api/ingest/positions endpoint."""

    proxy_wallet: str
    snapshot_ts: datetime
    rows_written: int


# Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "polyttool-api"}


@app.post("/api/resolve", response_model=ResolveResponse)
async def resolve_user(request: ResolveRequest):
    """
    Resolve a username or wallet address to a Polymarket profile.

    - If input starts with '@', strips it for search
    - If input is a wallet address (0x...), attempts lookup
    - Returns proxy wallet, username, and full profile
    """
    logger.info(f"Resolving user: {request.input}")

    profile = gamma_client.resolve(request.input)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve user: {request.input}",
        )

    # Store/update profile in ClickHouse
    try:
        client = get_clickhouse_client()
        now = datetime.utcnow()

        # Check if user exists
        existing = client.query(
            "SELECT first_seen FROM users WHERE proxy_wallet = {wallet:String}",
            parameters={"wallet": profile.proxy_wallet},
        )

        first_seen = now
        if existing.result_rows:
            first_seen = existing.result_rows[0][0]

        # Upsert user profile
        client.insert(
            "users",
            [[
                profile.proxy_wallet,
                profile.username,
                json.dumps(profile.raw_json),
                first_seen,
                now,
            ]],
            column_names=["proxy_wallet", "username", "raw_profile_json", "first_seen", "last_updated"],
        )

        logger.info(f"Stored profile for {profile.proxy_wallet}")
    except Exception as e:
        logger.error(f"Failed to store profile in ClickHouse: {e}")
        # Don't fail the request, just log the error

    return ResolveResponse(
        proxy_wallet=profile.proxy_wallet,
        username=profile.username,
        profile=profile.raw_json,
    )


@app.post("/api/ingest/trades", response_model=IngestTradesResponse)
async def ingest_trades(request: IngestTradesRequest):
    """
    Ingest trades for a user into ClickHouse.

    - Resolves username to proxy wallet if needed
    - Fetches trades from Data API (up to max_pages)
    - Inserts into ClickHouse with idempotent deduplication
    - Returns ingestion metrics
    """
    logger.info(f"Ingesting trades for: {request.user}, max_pages={request.max_pages}")

    # First resolve the user to get proxy wallet
    profile = gamma_client.resolve(request.user)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve user: {request.user}",
        )

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    # Fetch trades from Data API
    result = data_api_client.fetch_all_trades(
        proxy_wallet=proxy_wallet,
        max_pages=request.max_pages,
    )

    logger.info(
        f"Fetched {result.total_rows} trades in {result.pages_fetched} pages"
    )

    # Insert trades into ClickHouse
    rows_written = 0
    try:
        client = get_clickhouse_client()

        if result.trades:
            # Prepare batch for insertion
            rows = []
            for trade in result.trades:
                rows.append([
                    trade.proxy_wallet,
                    trade.trade_uid,
                    trade.ts,
                    trade.token_id,
                    trade.condition_id,
                    trade.outcome,
                    trade.side,
                    trade.size,
                    trade.price,
                    trade.transaction_hash,
                    json.dumps(trade.raw_json),
                    datetime.utcnow(),
                ])

            # Insert all rows
            client.insert(
                "user_trades",
                rows,
                column_names=[
                    "proxy_wallet",
                    "trade_uid",
                    "ts",
                    "token_id",
                    "condition_id",
                    "outcome",
                    "side",
                    "size",
                    "price",
                    "transaction_hash",
                    "raw_json",
                    "ingested_at",
                ],
            )
            rows_written = len(rows)
            logger.info(f"Inserted {rows_written} rows into ClickHouse")

        # Also update user profile
        now = datetime.utcnow()
        existing = client.query(
            "SELECT first_seen FROM users WHERE proxy_wallet = {wallet:String}",
            parameters={"wallet": proxy_wallet},
        )

        first_seen = now
        if existing.result_rows:
            first_seen = existing.result_rows[0][0]

        client.insert(
            "users",
            [[
                profile.proxy_wallet,
                profile.username,
                json.dumps(profile.raw_json),
                first_seen,
                now,
            ]],
            column_names=["proxy_wallet", "username", "raw_profile_json", "first_seen", "last_updated"],
        )

        # Get distinct trade count for this user (after merge)
        # Force merge to get accurate count
        client.command("OPTIMIZE TABLE user_trades FINAL")

        count_result = client.query(
            "SELECT count(DISTINCT trade_uid) FROM user_trades WHERE proxy_wallet = {wallet:String}",
            parameters={"wallet": proxy_wallet},
        )
        distinct_count = count_result.result_rows[0][0] if count_result.result_rows else 0

    except Exception as e:
        logger.error(f"Failed to insert trades into ClickHouse: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}",
        )

    return IngestTradesResponse(
        proxy_wallet=proxy_wallet,
        pages_fetched=result.pages_fetched,
        rows_fetched_total=result.total_rows,
        rows_written=rows_written,
        distinct_trade_uids_total=distinct_count,
    )


@app.post("/api/ingest/activity", response_model=IngestActivityResponse)
async def ingest_activity(request: IngestActivityRequest):
    """
    Ingest activity for a user into ClickHouse.

    - Resolves username to proxy wallet if needed
    - Fetches activity from Data API (up to max_pages)
    - Inserts into ClickHouse with idempotent deduplication
    - Returns ingestion metrics
    """
    logger.info(f"Ingesting activity for: {request.user}, max_pages={request.max_pages}")

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    result = data_api_client.fetch_all_activity(
        proxy_wallet=proxy_wallet,
        max_pages=request.max_pages,
    )

    logger.info(
        f"Fetched {result.total_rows} activity rows in {result.pages_fetched} pages"
    )

    rows_written = 0
    try:
        client = get_clickhouse_client()

        if result.activities:
            rows = []
            for activity in result.activities:
                rows.append([
                    activity.proxy_wallet,
                    activity.activity_uid,
                    activity.ts,
                    activity.activity_type,
                    activity.token_id,
                    activity.condition_id,
                    activity.size,
                    activity.price,
                    activity.tx_hash,
                    json.dumps(activity.raw_json),
                    datetime.utcnow(),
                ])

            client.insert(
                "user_activity",
                rows,
                column_names=[
                    "proxy_wallet",
                    "activity_uid",
                    "ts",
                    "activity_type",
                    "token_id",
                    "condition_id",
                    "size",
                    "price",
                    "tx_hash",
                    "raw_json",
                    "ingested_at",
                ],
            )
            rows_written = len(rows)
            logger.info(f"Inserted {rows_written} activity rows into ClickHouse")

        now = datetime.utcnow()
        existing = client.query(
            "SELECT first_seen FROM users WHERE proxy_wallet = {wallet:String}",
            parameters={"wallet": proxy_wallet},
        )

        first_seen = now
        if existing.result_rows:
            first_seen = existing.result_rows[0][0]

        client.insert(
            "users",
            [[
                profile.proxy_wallet,
                profile.username,
                json.dumps(profile.raw_json),
                first_seen,
                now,
            ]],
            column_names=["proxy_wallet", "username", "raw_profile_json", "first_seen", "last_updated"],
        )

        client.command("OPTIMIZE TABLE user_activity FINAL")

        count_result = client.query(
            "SELECT count(DISTINCT activity_uid) FROM user_activity WHERE proxy_wallet = {wallet:String}",
            parameters={"wallet": proxy_wallet},
        )
        distinct_count = count_result.result_rows[0][0] if count_result.result_rows else 0

    except Exception as e:
        logger.error(f"Failed to insert activity into ClickHouse: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return IngestActivityResponse(
        proxy_wallet=proxy_wallet,
        pages_fetched=result.pages_fetched,
        rows_fetched_total=result.total_rows,
        rows_written=rows_written,
        distinct_activity_uids_total=distinct_count,
    )


@app.post("/api/ingest/positions", response_model=IngestPositionsResponse)
async def ingest_positions(request: IngestPositionsRequest):
    """
    Ingest current positions snapshot for a user into ClickHouse.

    - Resolves username to proxy wallet if needed
    - Fetches current positions from Data API
    - Writes a snapshot each call
    """
    logger.info(f"Ingesting positions for: {request.user}")

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    result = data_api_client.fetch_positions(proxy_wallet=proxy_wallet)
    snapshot_ts = datetime.utcnow()

    rows_written = 0
    try:
        client = get_clickhouse_client()

        if result.positions:
            rows = []
            for position in result.positions:
                rows.append([
                    position.proxy_wallet,
                    snapshot_ts,
                    position.token_id,
                    position.condition_id,
                    position.outcome,
                    position.shares,
                    position.avg_cost,
                    json.dumps(position.raw_json),
                    datetime.utcnow(),
                ])

            client.insert(
                "user_positions_snapshots",
                rows,
                column_names=[
                    "proxy_wallet",
                    "snapshot_ts",
                    "token_id",
                    "condition_id",
                    "outcome",
                    "shares",
                    "avg_cost",
                    "raw_json",
                    "ingested_at",
                ],
            )
            rows_written = len(rows)
            logger.info(f"Inserted {rows_written} position snapshots into ClickHouse")

        now = datetime.utcnow()
        existing = client.query(
            "SELECT first_seen FROM users WHERE proxy_wallet = {wallet:String}",
            parameters={"wallet": proxy_wallet},
        )

        first_seen = now
        if existing.result_rows:
            first_seen = existing.result_rows[0][0]

        client.insert(
            "users",
            [[
                profile.proxy_wallet,
                profile.username,
                json.dumps(profile.raw_json),
                first_seen,
                now,
            ]],
            column_names=["proxy_wallet", "username", "raw_profile_json", "first_seen", "last_updated"],
        )

    except Exception as e:
        logger.error(f"Failed to insert positions into ClickHouse: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return IngestPositionsResponse(
        proxy_wallet=proxy_wallet,
        snapshot_ts=snapshot_ts,
        rows_written=rows_written,
    )


@app.get("/api/users")
async def list_users():
    """List all ingested users."""
    try:
        client = get_clickhouse_client()
        result = client.query(
            """
            SELECT
                proxy_wallet,
                username,
                first_seen,
                last_updated
            FROM users
            ORDER BY last_updated DESC
            """
        )

        users = []
        for row in result.result_rows:
            users.append({
                "proxy_wallet": row[0],
                "username": row[1],
                "first_seen": row[2].isoformat() if row[2] else None,
                "last_updated": row[3].isoformat() if row[3] else None,
            })

        return {"users": users, "count": len(users)}
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/{proxy_wallet}/trades/stats")
async def get_user_trade_stats(proxy_wallet: str):
    """Get trade statistics for a user."""
    try:
        client = get_clickhouse_client()

        # Force merge for accurate count
        client.command("OPTIMIZE TABLE user_trades FINAL")

        result = client.query(
            """
            SELECT
                count() as total_trades,
                countIf(side = 'BUY') as buys,
                countIf(side = 'SELL') as sells,
                min(ts) as first_trade,
                max(ts) as last_trade,
                sum(size * price) as total_volume
            FROM user_trades
            WHERE proxy_wallet = {wallet:String}
            """,
            parameters={"wallet": proxy_wallet},
        )

        if not result.result_rows or result.result_rows[0][0] == 0:
            raise HTTPException(status_code=404, detail="No trades found for user")

        row = result.result_rows[0]
        return {
            "proxy_wallet": proxy_wallet,
            "total_trades": row[0],
            "buys": row[1],
            "sells": row[2],
            "first_trade": row[3].isoformat() if row[3] else None,
            "last_trade": row[4].isoformat() if row[4] else None,
            "total_volume": float(row[5]) if row[5] else 0.0,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trade stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class IngestMarketsRequest(BaseModel):
    """Request body for /api/ingest/markets endpoint."""

    active_only: bool = Field(default=True, description="Only fetch active/non-closed markets")
    max_pages: int = Field(default=50, ge=1, le=200, description="Maximum pages to fetch")


class IngestMarketsResponse(BaseModel):
    """Response body for /api/ingest/markets endpoint."""

    pages_fetched: int
    markets_total: int
    market_tokens_written: int


class RunDetectorsRequest(BaseModel):
    """Request body for /api/run/detectors endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    bucket: str = Field(default="day", description="Bucket type: day, hour, week")
    recompute_features: bool = Field(default=True, description="Recompute features first")
    backfill_mappings: bool = Field(default=True, description="Backfill missing market token mappings")


class RunDetectorsResponse(BaseModel):
    """Response body for /api/run/detectors endpoint."""

    proxy_wallet: str
    detectors_run: int
    results: list[dict]
    features_computed: bool
    backfill_stats: Optional[dict] = None


class ComputePnlRequest(BaseModel):
    """Request body for /api/compute/pnl endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    bucket: str = Field(
        default=PNL_BUCKET_DEFAULT,
        description="Bucket type: day, hour, week",
    )
    max_days: Optional[int] = Field(
        default=None,
        ge=1,
        le=3650,
        description="Limit to most recent N days",
    )


class PnlBucketSummary(BaseModel):
    """Summary of latest PnL bucket."""

    bucket_start: datetime
    realized_pnl: float
    mtm_pnl_estimate: float
    exposure_notional_estimate: float
    open_position_tokens: int


class ComputePnlResponse(BaseModel):
    """Response body for /api/compute/pnl endpoint."""

    proxy_wallet: str
    bucket_type: str
    buckets_written: int
    tokens_priced: int
    tokens_skipped_missing_orderbook: list[str]
    tokens_skipped_limit: list[str]
    latest_bucket: Optional[PnlBucketSummary] = None


class ComputeArbFeasibilityRequest(BaseModel):
    """Request body for /api/compute/arb_feasibility endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    bucket: str = Field(default="day", description="Bucket type: day, hour, week")
    max_tokens: int = Field(
        default=ARB_MAX_TOKENS_PER_RUN,
        ge=1,
        le=1000,
        description="Max tokens to process per run",
    )


class ArbBucketSummary(BaseModel):
    """Summary of an arb feasibility bucket."""

    bucket_start: datetime
    condition_id: str
    total_fees_est_usdc: float
    total_slippage_est_usdc: float
    break_even_notional_usd: Optional[float]
    confidence: str


class ComputeArbFeasibilityResponse(BaseModel):
    """Response body for /api/compute/arb_feasibility endpoint."""

    proxy_wallet: str
    bucket_type: str
    buckets_computed: int
    fee_rates_fetched: int
    slippage_estimates: int
    markets_analyzed: int
    tokens_skipped_limit: list[str]
    tokens_skipped_missing_book: list[str]
    latest_buckets: list[ArbBucketSummary]


@app.post("/api/ingest/markets", response_model=IngestMarketsResponse)
async def ingest_markets(request: IngestMarketsRequest):
    """
    Fetch and ingest market metadata from Gamma API.

    - Fetches markets with optional active_only filter
    - Extracts market_tokens mapping (token_id -> outcome)
    - Stores in market_tokens and markets tables
    """
    logger.info(f"Ingesting markets: active_only={request.active_only}, max_pages={request.max_pages}")

    result = gamma_client.fetch_all_markets(
        max_pages=request.max_pages,
        active_only=request.active_only,
    )

    logger.info(f"Fetched {result.total_markets} markets, {len(result.market_tokens)} tokens")

    # Insert into ClickHouse
    tokens_written = 0
    try:
        client = get_clickhouse_client()

        if result.market_tokens:
            rows = []
            for mt in result.market_tokens:
                rows.append([
                    mt.token_id,
                    mt.condition_id,
                    mt.outcome_index,
                    mt.outcome_name,
                    mt.market_slug,
                    mt.question,
                    mt.category,
                    mt.event_slug,
                    mt.end_date_iso,
                    1 if mt.active else 0,
                    json.dumps(mt.raw_json),
                    datetime.utcnow(),
                ])

            client.insert(
                "market_tokens",
                rows,
                column_names=[
                    "token_id", "condition_id", "outcome_index", "outcome_name",
                    "market_slug", "question", "category", "event_slug",
                    "end_date_iso", "active", "raw_json", "ingested_at"
                ],
            )
            tokens_written = len(rows)
            logger.info(f"Inserted {tokens_written} market tokens")

        # Also insert full markets
        if result.markets:
            market_rows = []
            for m in result.markets:
                market_rows.append([
                    m.condition_id,
                    m.market_slug,
                    m.question,
                    m.description,
                    m.category,
                    m.tags,
                    m.event_slug,
                    m.event_title,
                    m.outcomes,
                    m.clob_token_ids,
                    m.start_date_iso,
                    m.end_date_iso,
                    m.close_date_iso,
                    1 if m.active else 0,
                    m.liquidity,
                    m.volume,
                    json.dumps(m.raw_json),
                    datetime.utcnow(),
                ])

            client.insert(
                "markets",
                market_rows,
                column_names=[
                    "condition_id", "market_slug", "question", "description",
                    "category", "tags", "event_slug", "event_title",
                    "outcomes", "clob_token_ids", "start_date_iso",
                    "end_date_iso", "close_date_iso", "active",
                    "liquidity", "volume",
                    "raw_json", "ingested_at"
                ],
            )
            logger.info(f"Inserted {len(market_rows)} markets")

    except Exception as e:
        logger.error(f"Failed to insert markets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return IngestMarketsResponse(
        pages_fetched=result.pages_fetched,
        markets_total=result.total_markets,
        market_tokens_written=tokens_written,
    )


@app.post("/api/run/detectors", response_model=RunDetectorsResponse)
async def run_detectors(request: RunDetectorsRequest):
    """
    Run strategy detectors for a user.

    - Resolves username to wallet
    - Optionally backfills missing market token mappings
    - Fetches trades from ClickHouse
    - Optionally recomputes bucket features
    - Runs all 4 detectors for each bucket
    - Stores results in detector_results table
    """
    logger.info(f"Running detectors for: {request.user}, bucket={request.bucket}")

    # Resolve user
    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    try:
        client = get_clickhouse_client()

        # Optionally backfill missing market token mappings
        backfill_stats = None
        if request.backfill_mappings:
            logger.info(f"Running backfill for missing market mappings...")
            backfill_stats = backfill_missing_mappings(
                clickhouse_client=client,
                gamma_client=gamma_client,
                proxy_wallet=proxy_wallet,
                max_missing=500,
            )
            logger.info(f"Backfill complete: {backfill_stats}")

        # Fetch trades
        trades_result = client.query(
            """
            SELECT proxy_wallet, trade_uid, ts, token_id, condition_id,
                   outcome, side, size, price, transaction_hash
            FROM user_trades
            WHERE proxy_wallet = {wallet:String}
            ORDER BY ts
            """,
            parameters={"wallet": proxy_wallet},
        )

        trades = []
        for row in trades_result.result_rows:
            trades.append({
                "proxy_wallet": row[0],
                "trade_uid": row[1],
                "ts": row[2],
                "token_id": row[3],
                "condition_id": row[4],
                "outcome": row[5],
                "side": row[6],
                "size": float(row[7]),
                "price": float(row[8]),
                "transaction_hash": row[9],
            })

        if not trades:
            raise HTTPException(status_code=404, detail="No trades found for user")

        logger.info(f"Fetched {len(trades)} trades for {proxy_wallet}")

        # Fetch market_tokens map (after potential backfill)
        tokens_result = client.query(
            "SELECT token_id, condition_id, outcome_index, outcome_name, category FROM market_tokens"
        )
        market_tokens_map = {}
        for row in tokens_result.result_rows:
            market_tokens_map[row[0]] = {
                "condition_id": row[1],
                "outcome_index": row[2],
                "outcome_name": row[3],
                "category": row[4],
            }

        logger.info(f"Loaded {len(market_tokens_map)} market tokens for mapping")

        # Optionally recompute bucket features
        features_computed = False
        if request.recompute_features:
            features_sql = compute_features_sql(proxy_wallet, bucket_type=request.bucket)
            features_result = client.query(features_sql)

            if features_result.result_rows:
                feature_rows = []
                for row in features_result.result_rows:
                    feature_rows.append([
                        row[0],  # proxy_wallet
                        row[1],  # bucket_type
                        row[2],  # bucket_start
                        int(row[3]),  # trades_count
                        int(row[4]),  # buys_count
                        int(row[5]),  # sells_count
                        float(row[6]),  # volume
                        float(row[7]),  # notional
                        int(row[8]),  # unique_tokens
                        int(row[9]),  # unique_markets
                        float(row[10]),  # avg_trade_size
                        float(row[11]),  # pct_buys
                        float(row[12]),  # pct_sells
                        float(row[13]),  # mapping_coverage
                        datetime.utcnow(),
                    ])

                client.insert(
                    "user_bucket_features",
                    feature_rows,
                    column_names=get_bucket_insert_columns(),
                )
                features_computed = True
                logger.info(f"Computed and stored {len(feature_rows)} bucket feature rows")

        # Run detectors for each bucket
        runner = DetectorRunner()
        all_results = runner.run_all_by_bucket(
            trades=trades,
            proxy_wallet=proxy_wallet,
            bucket_type=request.bucket,
            market_tokens_map=market_tokens_map,
        )

        # Store results
        detector_rows = [r.to_row() for r in all_results]
        if detector_rows:
            client.insert(
                "detector_results",
                detector_rows,
                column_names=get_detector_columns(),
            )
            logger.info(f"Stored {len(detector_rows)} detector results")

        # Return results
        return RunDetectorsResponse(
            proxy_wallet=proxy_wallet,
            detectors_run=len(all_results),
            results=[
                {
                    "detector": r.detector_name,
                    "bucket_type": r.bucket_type,
                    "bucket_start": r.bucket_start.isoformat() if r.bucket_start else None,
                    "score": r.score,
                    "label": r.label,
                    "evidence": r.evidence,
                }
                for r in all_results
            ],
            features_computed=features_computed,
            backfill_stats=backfill_stats,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run detectors: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compute/pnl", response_model=ComputePnlResponse)
async def compute_pnl(request: ComputePnlRequest):
    """
    Compute realized + conservative MTM PnL and exposure series for a user.
    """
    logger.info(f"Computing PnL for: {request.user}, bucket={request.bucket}")

    bucket = request.bucket.lower()
    if bucket not in ("day", "hour", "week"):
        raise HTTPException(status_code=400, detail="bucket must be one of: day, hour, week")

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    start_ts = None
    if request.max_days:
        start_ts = datetime.utcnow() - timedelta(days=request.max_days)

    try:
        client = get_clickhouse_client()

        trade_filters = ["proxy_wallet = {wallet:String}"]
        params: dict = {"wallet": proxy_wallet}
        if start_ts:
            trade_filters.append("ts >= {start_ts:DateTime}")
            params["start_ts"] = start_ts

        trades_query = f"""
        SELECT ts, token_id, side, size, price
        FROM user_trades
        WHERE {' AND '.join(trade_filters)}
        ORDER BY ts
        """
        trades_result = client.query(trades_query, parameters=params)

        trades = []
        for row in trades_result.result_rows:
            trades.append({
                "ts": row[0],
                "token_id": row[1],
                "side": row[2],
                "size": float(row[3]) if row[3] is not None else 0.0,
                "price": float(row[4]) if row[4] is not None else 0.0,
            })

        snapshot_filters = ["proxy_wallet = {wallet:String}"]
        if start_ts:
            snapshot_filters.append("snapshot_ts >= {start_ts:DateTime}")

        snapshots_query = f"""
        SELECT snapshot_ts, token_id, shares, avg_cost
        FROM user_positions_snapshots
        WHERE {' AND '.join(snapshot_filters)}
        ORDER BY snapshot_ts
        """
        snapshots_result = client.query(snapshots_query, parameters=params)

        snapshots = []
        for row in snapshots_result.result_rows:
            snapshots.append({
                "snapshot_ts": row[0],
                "token_id": row[1],
                "shares": float(row[2]) if row[2] is not None else 0.0,
                "avg_cost": float(row[3]) if row[3] is not None else None,
            })

        if not trades and not snapshots:
            raise HTTPException(status_code=404, detail="No trades or positions found for user")

        pnl_result = compute_user_pnl_buckets(
            proxy_wallet=proxy_wallet,
            trades=trades,
            snapshots=snapshots,
            bucket_type=bucket,
            clob_client=clob_client,
            orderbook_cache_seconds=PNL_ORDERBOOK_CACHE_SECONDS,
            max_tokens_per_run=PNL_MAX_TOKENS_PER_RUN,
            as_of=datetime.utcnow(),
        )

        if not pnl_result.buckets:
            raise HTTPException(status_code=404, detail="No PnL buckets computed")

        pnl_rows = [b.to_row() for b in pnl_result.buckets]
        client.insert(
            "user_pnl_bucket",
            pnl_rows,
            column_names=[
                "proxy_wallet",
                "bucket_type",
                "bucket_start",
                "realized_pnl",
                "mtm_pnl_estimate",
                "exposure_notional_estimate",
                "open_position_tokens",
                "pricing_source",
                "computed_at",
            ],
        )

        latest_bucket = max(pnl_result.buckets, key=lambda b: b.bucket_start)
        latest_summary = PnlBucketSummary(
            bucket_start=latest_bucket.bucket_start,
            realized_pnl=latest_bucket.realized_pnl,
            mtm_pnl_estimate=latest_bucket.mtm_pnl_estimate,
            exposure_notional_estimate=latest_bucket.exposure_notional_estimate,
            open_position_tokens=latest_bucket.open_position_tokens,
        )

        return ComputePnlResponse(
            proxy_wallet=proxy_wallet,
            bucket_type=bucket,
            buckets_written=len(pnl_rows),
            tokens_priced=pnl_result.tokens_priced,
            tokens_skipped_missing_orderbook=pnl_result.tokens_skipped_missing_orderbook,
            tokens_skipped_limit=pnl_result.tokens_skipped_limit,
            latest_bucket=latest_summary,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute PnL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compute/arb_feasibility", response_model=ComputeArbFeasibilityResponse)
async def compute_arb_feasibility(request: ComputeArbFeasibilityRequest):
    """
    Compute arb feasibility with dynamic fees and slippage estimates.

    - Identifies arb-like events (buying both outcomes, closing within 24h)
    - Fetches fee rates from CLOB API for each token
    - Estimates slippage by simulating execution through orderbook
    - Computes total costs and break-even notional
    - Stores results in arb_feasibility_bucket table
    """
    logger.info(
        f"Computing arb feasibility for: {request.user}, "
        f"bucket={request.bucket}, max_tokens={request.max_tokens}"
    )

    bucket = request.bucket.lower()
    if bucket not in ("day", "hour", "week"):
        raise HTTPException(status_code=400, detail="bucket must be one of: day, hour, week")

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    try:
        client = get_clickhouse_client()

        # Fetch trades
        trades_result = client.query(
            """
            SELECT proxy_wallet, trade_uid, ts, token_id, condition_id,
                   outcome, side, size, price, transaction_hash
            FROM user_trades
            WHERE proxy_wallet = {wallet:String}
            ORDER BY ts
            """,
            parameters={"wallet": proxy_wallet},
        )

        trades = []
        for row in trades_result.result_rows:
            trades.append({
                "proxy_wallet": row[0],
                "trade_uid": row[1],
                "ts": row[2],
                "token_id": row[3],
                "condition_id": row[4],
                "outcome": row[5],
                "side": row[6],
                "size": float(row[7]) if row[7] is not None else 0.0,
                "price": float(row[8]) if row[8] is not None else 0.0,
                "transaction_hash": row[9],
            })

        if not trades:
            raise HTTPException(status_code=404, detail="No trades found for user")

        logger.info(f"Fetched {len(trades)} trades for {proxy_wallet}")

        # Fetch market_tokens map
        tokens_result = client.query(
            "SELECT token_id, condition_id, outcome_index, outcome_name, category FROM market_tokens"
        )
        market_tokens_map = {}
        for row in tokens_result.result_rows:
            market_tokens_map[row[0]] = {
                "condition_id": row[1],
                "outcome_index": row[2],
                "outcome_name": row[3],
                "category": row[4],
            }

        logger.info(f"Loaded {len(market_tokens_map)} market tokens for mapping")

        # Compute arb feasibility
        arb_result = compute_arb_feasibility_buckets(
            proxy_wallet=proxy_wallet,
            trades=trades,
            market_tokens_map=market_tokens_map,
            bucket_type=bucket,
            clob_client=clob_client,
            cache_ttl_seconds=ARB_CACHE_SECONDS,
            max_tokens_per_run=request.max_tokens,
        )

        if not arb_result.buckets:
            return ComputeArbFeasibilityResponse(
                proxy_wallet=proxy_wallet,
                bucket_type=bucket,
                buckets_computed=0,
                fee_rates_fetched=arb_result.fee_rates_fetched,
                slippage_estimates=arb_result.slippage_estimates,
                markets_analyzed=arb_result.markets_analyzed,
                tokens_skipped_limit=arb_result.tokens_skipped_limit,
                tokens_skipped_missing_book=arb_result.tokens_skipped_missing_book,
                latest_buckets=[],
            )

        # Insert into ClickHouse
        arb_rows = [b.to_row() for b in arb_result.buckets]
        client.insert(
            "arb_feasibility_bucket",
            arb_rows,
            column_names=get_arb_columns(),
        )
        logger.info(f"Stored {len(arb_rows)} arb feasibility buckets")

        # Build latest buckets summary
        latest_buckets = [
            ArbBucketSummary(
                bucket_start=b.bucket_start,
                condition_id=b.condition_id,
                total_fees_est_usdc=b.total_fees_est_usdc,
                total_slippage_est_usdc=b.total_slippage_est_usdc,
                break_even_notional_usd=b.break_even_notional_usd,
                confidence=b.confidence,
            )
            for b in arb_result.buckets
        ]

        return ComputeArbFeasibilityResponse(
            proxy_wallet=proxy_wallet,
            bucket_type=bucket,
            buckets_computed=len(arb_result.buckets),
            fee_rates_fetched=arb_result.fee_rates_fetched,
            slippage_estimates=arb_result.slippage_estimates,
            markets_analyzed=arb_result.markets_analyzed,
            tokens_skipped_limit=arb_result.tokens_skipped_limit,
            tokens_skipped_missing_book=arb_result.tokens_skipped_missing_book,
            latest_buckets=latest_buckets,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute arb feasibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
