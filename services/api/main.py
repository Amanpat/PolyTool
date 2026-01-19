"""PolyTool API service for username resolution and trade ingestion."""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import clickhouse_connect

# Add packages to path for local imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages"))

from polymarket.gamma import GammaClient
from polymarket.data_api import DataApiClient

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
    version="0.2.0",
)

# Initialize clients
gamma_client = GammaClient(base_url=GAMMA_API_BASE, timeout=HTTP_TIMEOUT_SECONDS)
data_api_client = DataApiClient(base_url=DATA_API_BASE, timeout=HTTP_TIMEOUT_SECONDS)


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
