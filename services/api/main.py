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
from polymarket.orderbook_snapshots import (
    OrderbookSnapshot,
    snapshot_from_book,
    get_insert_columns as get_snapshot_columns,
)
from polymarket.opportunities import get_opportunity_bucket_start, normalize_bucket_type
from polymarket.normalization import normalize_condition_id
from polymarket.token_resolution import resolve_token_id
from polymarket.llm_research_packets import export_user_dossier
from polymarket.resolution_enrichment import (
    DEFAULT_BATCH_SIZE as DEFAULT_RESOLUTION_BATCH_SIZE,
    DEFAULT_MAX_CANDIDATES as DEFAULT_RESOLUTION_MAX_CANDIDATES,
    DEFAULT_MAX_CONCURRENCY as DEFAULT_RESOLUTION_MAX_CONCURRENCY,
    build_provider_chain as build_resolution_provider_chain,
    enrich_market_resolutions,
    select_resolution_candidates,
)

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
RESOLUTION_RPC_TIMEOUT_SECONDS = float(os.getenv("RESOLUTION_RPC_TIMEOUT_SECONDS", "10"))
RESOLUTION_SUBGRAPH_TIMEOUT_SECONDS = float(os.getenv("RESOLUTION_SUBGRAPH_TIMEOUT_SECONDS", "15"))

# Orderbook snapshot configuration
BOOK_SNAPSHOT_DEPTH_BAND_BPS = float(os.getenv("BOOK_SNAPSHOT_DEPTH_BAND_BPS", "50"))
BOOK_SNAPSHOT_NOTIONALS = [float(x) for x in os.getenv("BOOK_SNAPSHOT_NOTIONALS", "100,500").split(",")]
BOOK_SNAPSHOT_MAX_TOKENS = int(os.getenv("BOOK_SNAPSHOT_MAX_TOKENS", "200"))
BOOK_SNAPSHOT_MIN_OK_TARGET = int(os.getenv("BOOK_SNAPSHOT_MIN_OK_TARGET", "5"))
BOOK_SNAPSHOT_404_TTL_HOURS = int(os.getenv("BOOK_SNAPSHOT_404_TTL_HOURS", "24"))
BOOK_SNAPSHOT_MAX_PREFLIGHT = int(os.getenv("BOOK_SNAPSHOT_MAX_PREFLIGHT", "200"))
ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS = int(os.getenv("ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS", "3600"))
OPPORTUNITY_TRADE_LOOKBACK_DAYS = int(os.getenv("OPPORTUNITY_TRADE_LOOKBACK_DAYS", "90"))
OPPORTUNITY_SNAPSHOT_MAX_AGE_SECONDS = int(
    os.getenv("OPPORTUNITY_SNAPSHOT_MAX_AGE_SECONDS", str(ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS))
)

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


DOSSIER_REQUIRED_SCHEMA_OBJECTS = (
    "user_trade_lifecycle",
    "user_trade_lifecycle_enriched",
)
DOSSIER_SCHEMA_REMEDIATION = "docker compose down -v && docker compose up -d --build clickhouse api"


def get_clickhouse_client():
    """Create ClickHouse client connection."""
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


class MissingClickHouseSchemaError(RuntimeError):
    """Raised when required ClickHouse schema objects are missing."""


def _assert_dossier_export_schema(client) -> None:
    required = list(DOSSIER_REQUIRED_SCHEMA_OBJECTS)
    try:
        result = client.query(
            """
            SELECT name
            FROM system.tables
            WHERE database = {database:String}
              AND name IN {names:Array(String)}
            """,
            parameters={"database": CLICKHOUSE_DATABASE, "names": required},
        )
    except Exception as exc:
        raise MissingClickHouseSchemaError(
            "Failed to validate ClickHouse schema for dossier export. "
            f"Check ClickHouse availability and init scripts. Remediation: {DOSSIER_SCHEMA_REMEDIATION}"
        ) from exc

    found = {str(row[0]) for row in result.result_rows if row and row[0]}
    missing = [name for name in required if name not in found]
    if missing:
        raise MissingClickHouseSchemaError(
            "Missing ClickHouse schema objects required for dossier export: "
            f"{', '.join(missing)}. Remediation: {DOSSIER_SCHEMA_REMEDIATION}"
        )


def _extract_error_message_from_response(response) -> Optional[str]:
    try:
        payload = response.json()
    except ValueError:
        text = response.text.strip()
        return text or None

    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if value:
                return str(value)
    if isinstance(payload, str):
        return payload
    return None


def _is_wallet_address(value: str) -> bool:
    value = value.strip()
    return value.startswith("0x") and len(value) >= 40


def _normalize_username_input(input_value: str) -> Optional[str]:
    cleaned = input_value.strip()
    if not cleaned or cleaned == "@":
        return None
    if _is_wallet_address(cleaned):
        return None
    if cleaned.startswith("@"):
        return cleaned
    return f"@{cleaned}"


def _get_existing_user_metadata(client, proxy_wallet: str) -> tuple[Optional[datetime], str]:
    result = client.query(
        """
        SELECT
            min(first_seen) AS first_seen,
            argMaxIf(trimBoth(username), last_updated, trimBoth(username) != '') AS best_username
        FROM users
        WHERE proxy_wallet = {wallet:String}
        """,
        parameters={"wallet": proxy_wallet},
    )

    if result.result_rows:
        first_seen = result.result_rows[0][0]
        best_username = result.result_rows[0][1] or ""
        return first_seen, best_username

    return None, ""


def _sanitize_datetime_for_insert(value: Optional[datetime], fallback: datetime) -> datetime:
    """Guard against out-of-range timestamps on Windows hosts."""
    if value is None:
        return fallback
    try:
        _ = value.timestamp()
        return value
    except (OSError, OverflowError, ValueError):
        return fallback


def _upsert_user_profile(client, profile, input_value: str) -> None:
    now = datetime.utcnow()
    existing_first_seen, existing_username = _get_existing_user_metadata(
        client,
        profile.proxy_wallet,
    )
    first_seen = _sanitize_datetime_for_insert(existing_first_seen, now)
    input_username = _normalize_username_input(input_value)
    username_to_store = input_username or existing_username or ""

    client.insert(
        "users",
        [[
            profile.proxy_wallet,
            username_to_store,
            json.dumps(profile.raw_json),
            first_seen,
            now,
        ]],
        column_names=["proxy_wallet", "username", "raw_profile_json", "first_seen", "last_updated"],
    )


def _build_basic_snapshot(
    token_id: str,
    snapshot_ts: datetime,
    status: str,
    reason: Optional[str],
) -> OrderbookSnapshot:
    return OrderbookSnapshot(
        token_id=token_id,
        snapshot_ts=snapshot_ts,
        best_bid=None,
        best_ask=None,
        mid_price=None,
        spread_bps=None,
        depth_bid_usd_50bps=None,
        depth_ask_usd_50bps=None,
        slippage_buy_bps_100=None,
        slippage_sell_bps_100=None,
        slippage_buy_bps_500=None,
        slippage_sell_bps_500=None,
        levels_captured=0,
        book_timestamp=None,
        status=status,
        reason=reason,
    )


def _resolve_candidate_tokens(client, candidates: list[dict]) -> tuple[list[str], dict[str, str]]:
    if not candidates:
        return [], {}

    token_ids = [c.get("token_id") for c in candidates if c.get("token_id")]
    token_ids = [token_id for token_id in token_ids if token_id]
    if not token_ids:
        return [], {}

    unique_tokens = list(dict.fromkeys(token_ids))

    direct_tokens = set()
    try:
        direct_result = client.query(
            "SELECT token_id FROM market_tokens WHERE token_id IN {tokens:Array(String)}",
            parameters={"tokens": unique_tokens},
        )
        direct_tokens = {row[0] for row in direct_result.result_rows if row and row[0]}
    except Exception as exc:
        logger.warning(f"Failed to fetch direct token mappings: {exc}")

    alias_map: dict[str, str] = {}
    try:
        alias_result = client.query(
            """
            SELECT alias_token_id, canonical_clob_token_id
            FROM token_aliases
            WHERE alias_token_id IN {tokens:Array(String)}
            """,
            parameters={"tokens": unique_tokens},
        )
        alias_map = {
            row[0]: row[1] for row in alias_result.result_rows if row and row[0] and row[1]
        }
    except Exception as exc:
        logger.warning(f"Failed to fetch token aliases: {exc}")

    condition_ids = [
        normalize_condition_id(c.get("condition_id"))
        for c in candidates
        if c.get("condition_id")
    ]
    condition_ids = [cid for cid in condition_ids if cid]

    markets_map: dict[str, dict[str, list[str]]] = {}
    if condition_ids:
        unique_conditions = list(dict.fromkeys(condition_ids))
        try:
            markets_result = client.query(
                """
                SELECT condition_id, outcomes, clob_token_ids
                FROM markets
                WHERE if(
                    startsWith(lowerUTF8(trimBoth(condition_id)), '0x'),
                    concat('0x', substring(lowerUTF8(trimBoth(condition_id)), 3)),
                    concat('0x', lowerUTF8(trimBoth(condition_id)))
                ) IN {conditions:Array(String)}
                """,
                parameters={"conditions": unique_conditions},
            )
            for row in markets_result.result_rows:
                if not row:
                    continue
                condition_id = normalize_condition_id(row[0])
                outcomes = row[1] or []
                clob_token_ids = row[2] or []
                if condition_id:
                    markets_map[condition_id] = {
                        "outcomes": [str(o) for o in outcomes],
                        "clob_token_ids": [str(t) for t in clob_token_ids],
                    }
        except Exception as exc:
            logger.warning(f"Failed to fetch markets for condition mapping: {exc}")

    resolved_tokens: list[str] = []
    resolution_map: dict[str, str] = {}
    for candidate in candidates:
        token_id = candidate.get("token_id") or ""
        if not token_id:
            continue
        resolved = resolve_token_id(
            token_id=token_id,
            condition_id=candidate.get("condition_id"),
            outcome=candidate.get("outcome"),
            direct_token_ids=direct_tokens,
            alias_map=alias_map,
            markets_map=markets_map,
        )
        if resolved:
            resolution_map[token_id] = resolved
            if resolved not in resolved_tokens:
                resolved_tokens.append(resolved)

    return resolved_tokens, resolution_map


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


class EnrichResolutionsRequest(BaseModel):
    """Request body for /api/enrich/resolutions endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    max_candidates: int = Field(
        default=DEFAULT_RESOLUTION_MAX_CANDIDATES,
        ge=1,
        le=1000,
        description="Hard cap on token candidates to enrich",
    )
    batch_size: int = Field(
        default=DEFAULT_RESOLUTION_BATCH_SIZE,
        ge=1,
        le=200,
        description="Batch size per enrichment wave",
    )
    max_concurrency: int = Field(
        default=DEFAULT_RESOLUTION_MAX_CONCURRENCY,
        ge=1,
        le=16,
        description="Max concurrent provider calls per batch",
    )


class EnrichResolutionsResponse(BaseModel):
    """Response body for /api/enrich/resolutions endpoint."""

    proxy_wallet: str
    max_candidates: int
    batch_size: int
    max_concurrency: int
    candidates_total: int
    candidates_selected: int
    truncated: bool
    candidates_processed: int
    cached_hits: int
    resolved_written: int
    unresolved_network: int
    skipped_missing_identifiers: int
    skipped_unsupported: int
    errors: int
    skipped_reasons: dict[str, int]
    lifecycle_token_universe_size_used_for_selection: int
    warnings: list[str]


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
        _upsert_user_profile(client, profile, request.input)

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
        _upsert_user_profile(client, profile, request.user)

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

        _upsert_user_profile(client, profile, request.user)

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

        _upsert_user_profile(client, profile, request.user)

    except Exception as e:
        logger.error(f"Failed to insert positions into ClickHouse: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    return IngestPositionsResponse(
        proxy_wallet=proxy_wallet,
        snapshot_ts=snapshot_ts,
        rows_written=rows_written,
    )


@app.post("/api/enrich/resolutions", response_model=EnrichResolutionsResponse)
async def enrich_resolutions(request: EnrichResolutionsRequest):
    """
    Enrich market resolutions for a user and cache results into market_resolutions.

    Chain: ClickHouse cache -> OnChain CTF -> Subgraph -> Gamma.
    """
    logger.info(
        "Enriching resolutions for user=%s max_candidates=%s batch_size=%s max_concurrency=%s",
        request.user,
        request.max_candidates,
        request.batch_size,
        request.max_concurrency,
    )

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not resolve user: {request.user}",
        )

    proxy_wallet = profile.proxy_wallet
    try:
        client = get_clickhouse_client()
        provider, provider_warnings = build_resolution_provider_chain(
            clickhouse_client=client,
            gamma_client=gamma_client,
            rpc_timeout_seconds=RESOLUTION_RPC_TIMEOUT_SECONDS,
            subgraph_timeout_seconds=RESOLUTION_SUBGRAPH_TIMEOUT_SECONDS,
        )
        selection = select_resolution_candidates(
            clickhouse_client=client,
            proxy_wallet=proxy_wallet,
            max_candidates=request.max_candidates,
        )
        summary = enrich_market_resolutions(
            clickhouse_client=client,
            proxy_wallet=proxy_wallet,
            provider=provider,
            max_candidates=request.max_candidates,
            batch_size=request.batch_size,
            max_concurrency=request.max_concurrency,
            candidates=selection.candidates,
            candidates_total=selection.candidates_total,
            truncated=selection.truncated,
            selection_warnings=selection.warnings,
        )
        if provider_warnings:
            summary.warnings.extend(provider_warnings)

        logger.info(
            "Resolution enrichment complete for wallet=%s candidates=%s selected=%s truncated=%s cached=%s written=%s unresolved=%s skipped_missing=%s errors=%s",
            proxy_wallet,
            summary.candidates_total,
            summary.candidates_selected,
            summary.truncated,
            summary.cached_hits,
            summary.resolved_written,
            summary.unresolved_network,
            summary.skipped_missing_identifiers,
            summary.errors,
        )
        response_payload = summary.as_dict()
        response_payload["lifecycle_token_universe_size_used_for_selection"] = (
            selection.lifecycle_token_universe_size_used_for_selection
        )
        return EnrichResolutionsResponse(**response_payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Failed to enrich resolutions: {exc}")
        raise HTTPException(status_code=500, detail=f"Resolution enrichment failed: {exc}")


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
    # Quality/confidence metrics
    tokens_priced_snapshot: int = 0
    tokens_priced_live: int = 0
    tokens_unpriced: int = 0
    pricing_snapshot_ratio: float = 0.0
    pricing_confidence: str = "LOW"


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
    # Liquidity confidence fields
    liquidity_confidence: str = "low"
    priced_legs: int = 0
    missing_legs: int = 0
    depth_100_ok: bool = False
    depth_500_ok: bool = False


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
    # Liquidity quality metrics
    events_with_full_liquidity: int = 0
    events_with_partial_liquidity: int = 0
    events_with_no_liquidity: int = 0
    overall_liquidity_rate: float = 0.0


class ComputeOpportunitiesRequest(BaseModel):
    """Request body for /api/compute/opportunities endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    bucket: str = Field(default="day", description="Bucket type: day, hour, week")
    limit: int = Field(
        default=25,
        ge=1,
        le=200,
        description="Max opportunities to return",
    )


class ComputeOpportunitiesResponse(BaseModel):
    """Response body for /api/compute/opportunities endpoint."""

    proxy_wallet: str
    bucket_type: str
    bucket_start: datetime
    buckets_written: int
    candidates_considered: int
    returned_count: int


class SnapshotBooksRequest(BaseModel):
    """Request body for /api/snapshot/books endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    max_tokens: int = Field(
        default=200,
        ge=1,
        le=1000,
        description="Max tokens to snapshot",
    )
    lookback_days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Days to look back for recent trades",
    )
    require_active_market: bool = Field(
        default=True,
        description="Only snapshot tokens from active markets (not closed/ended)",
    )
    include_inactive: bool = Field(
        default=False,
        description="Fall back to inactive/historical tokens if no active tokens found",
    )


class SnapshotBooksResponse(BaseModel):
    """Response body for /api/snapshot/books endpoint."""

    proxy_wallet: str
    # Backfill diagnostics
    backfill_missing_found: int = 0
    backfill_markets_fetched: int = 0
    backfill_tokens_inserted: int = 0
    # Token selection diagnostics
    tokens_candidates_before_filter: int
    tokens_from_trades_recent: int
    tokens_from_trades_fallback: int
    tokens_from_positions: int
    tokens_with_market_metadata: int
    tokens_after_active_filter: int
    tokens_selected_total: int
    # Execution results
    tokens_attempted: int
    tokens_ok: int
    tokens_empty: int
    tokens_one_sided: int
    tokens_no_orderbook: int
    tokens_error: int
    tokens_http_429: int
    tokens_http_5xx: int
    tokens_skipped_no_orderbook_ttl: int
    tokens_skipped_limit: list[str]
    snapshot_ts: datetime
    # Diagnostic reason if no OK snapshots
    no_ok_reason: Optional[str] = None


class ExportUserDossierRequest(BaseModel):
    """Request body for /api/export/user_dossier endpoint."""

    user: str = Field(..., description="Username (with or without @) or wallet address (0x...)")
    days: int = Field(default=30, ge=1, le=3650, description="Lookback window in days")
    max_trades: int = Field(
        default=200,
        ge=1,
        le=5000,
        description="Max anchor trades to include across all lists",
    )


class ExportUserDossierResponse(BaseModel):
    """Response body for /api/export/user_dossier endpoint."""

    export_id: str
    proxy_wallet: str
    username: Optional[str] = None
    username_slug: str
    artifact_path: str
    generated_at: datetime
    path_json: str
    path_md: str
    stats: dict


class ExportUserDossierHistoryRow(BaseModel):
    """History row for /api/export/user_dossier/history endpoint."""

    export_id: str
    proxy_wallet: str
    username: Optional[str] = None
    username_slug: str
    artifact_path: str
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    window_days: int
    max_trades: int
    trades_count: int
    activity_count: int
    positions_count: int
    mapping_coverage: float
    liquidity_ok_count: int
    liquidity_total_count: int
    usable_liquidity_rate: float
    pricing_snapshot_ratio: float
    pricing_confidence: str
    anchor_trade_uids: list[str] = []
    detectors_json: Optional[str] = None
    dossier_json: Optional[str] = None
    memo_md: Optional[str] = None


class ExportUserDossierHistoryResponse(BaseModel):
    """Response body for /api/export/user_dossier/history endpoint."""

    proxy_wallet: str
    rows: list[ExportUserDossierHistoryRow]


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
                    1 if mt.enable_order_book else 0 if mt.enable_order_book is not None else None,
                    1 if mt.accepting_orders else 0 if mt.accepting_orders is not None else None,
                    json.dumps(mt.raw_json),
                    datetime.utcnow(),
                ])

            client.insert(
                "market_tokens",
                rows,
                column_names=[
                    "token_id", "condition_id", "outcome_index", "outcome_name",
                    "market_slug", "question", "category", "event_slug",
                    "end_date_iso", "active", "enable_order_book", "accepting_orders",
                    "raw_json", "ingested_at"
                ],
            )
            tokens_written = len(rows)
            logger.info(f"Inserted {tokens_written} market tokens")

        if result.token_aliases:
            alias_rows = []
            for alias in result.token_aliases:
                alias_rows.append([
                    alias.alias_token_id,
                    alias.canonical_clob_token_id,
                    alias.condition_id,
                    alias.outcome_index,
                    alias.outcome_name,
                    alias.market_slug,
                    json.dumps(alias.raw_json),
                    datetime.utcnow(),
                ])

            client.insert(
                "token_aliases",
                alias_rows,
                column_names=[
                    "alias_token_id",
                    "canonical_clob_token_id",
                    "condition_id",
                    "outcome_index",
                    "outcome_name",
                    "market_slug",
                    "raw_json",
                    "ingested_at",
                ],
            )
            logger.info(f"Inserted {len(alias_rows)} token alias rows")

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
            SELECT proxy_wallet, trade_uid, ts, resolved_token_id, resolved_condition_id,
                   resolved_outcome_name, side, size, price, transaction_hash
            FROM user_trades_resolved
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
        SELECT ts, resolved_token_id AS token_id, side, size, price
        FROM user_trades_resolved
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
        SELECT snapshot_ts, resolved_token_id AS token_id, shares, avg_cost
        FROM user_positions_resolved
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
            clickhouse_client=client,
            snapshot_max_age_seconds=ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS,
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
                "pricing_snapshot_ratio",
                "pricing_confidence",
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
            tokens_priced_snapshot=pnl_result.tokens_priced_snapshot,
            tokens_priced_live=pnl_result.tokens_priced_live,
            tokens_unpriced=pnl_result.tokens_unpriced,
            pricing_snapshot_ratio=pnl_result.pricing_snapshot_ratio,
            pricing_confidence=pnl_result.pricing_confidence,
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
            SELECT proxy_wallet, trade_uid, ts, resolved_token_id, resolved_condition_id,
                   resolved_outcome_name, side, size, price, transaction_hash
            FROM user_trades_resolved
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
            clickhouse_client=client,
            snapshot_max_age_seconds=ORDERBOOK_SNAPSHOT_MAX_AGE_SECONDS,
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
                liquidity_confidence=b.liquidity_confidence,
                priced_legs=b.priced_legs,
                missing_legs=b.missing_legs,
                depth_100_ok=b.depth_100_ok,
                depth_500_ok=b.depth_500_ok,
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
            events_with_full_liquidity=arb_result.events_with_full_liquidity,
            events_with_partial_liquidity=arb_result.events_with_partial_liquidity,
            events_with_no_liquidity=arb_result.events_with_no_liquidity,
            overall_liquidity_rate=arb_result.overall_liquidity_rate,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute arb feasibility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/compute/opportunities", response_model=ComputeOpportunitiesResponse)
async def compute_opportunities(request: ComputeOpportunitiesRequest):
    """
    Compute low-cost, tradeable opportunity candidates for a user.
    """
    logger.info(
        f"Computing opportunities for: {request.user}, "
        f"bucket={request.bucket}, limit={request.limit}"
    )

    try:
        bucket = normalize_bucket_type(request.bucket)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    now = datetime.utcnow()
    bucket_start = get_opportunity_bucket_start(now, bucket)
    trade_cutoff = now - timedelta(days=OPPORTUNITY_TRADE_LOOKBACK_DAYS)
    snapshot_cutoff = now - timedelta(seconds=OPPORTUNITY_SNAPSHOT_MAX_AGE_SECONDS)

    try:
        client = get_clickhouse_client()

        tokens_result = client.query(
            """
            SELECT DISTINCT token_id
            FROM (
                SELECT resolved_token_id AS token_id
                FROM user_trades_resolved
                WHERE proxy_wallet = {wallet:String}
                  AND ts >= {trade_cutoff:DateTime}
                  AND resolved_token_id != ''
                UNION ALL
                SELECT resolved_token_id AS token_id
                FROM user_positions_resolved
                WHERE proxy_wallet = {wallet:String}
                  AND snapshot_ts = (
                      SELECT max(snapshot_ts)
                      FROM user_positions_resolved
                      WHERE proxy_wallet = {wallet:String}
                  )
                  AND resolved_token_id != ''
            )
            """,
            parameters={"wallet": proxy_wallet, "trade_cutoff": trade_cutoff},
        )
        tokens = [row[0] for row in tokens_result.result_rows if row and row[0]]
        tokens = list(dict.fromkeys(tokens))
        candidates_considered = len(tokens)

        if not tokens:
            return ComputeOpportunitiesResponse(
                proxy_wallet=proxy_wallet,
                bucket_type=bucket,
                bucket_start=bucket_start,
                buckets_written=0,
                candidates_considered=0,
                returned_count=0,
            )

        opportunities_query = """
        WITH latest AS (
            SELECT
                resolved_token_id AS token_id,
                argMax(market_slug, snapshot_ts) AS market_slug,
                argMax(question, snapshot_ts) AS question,
                argMax(outcome_name, snapshot_ts) AS outcome_name,
                argMax(execution_cost_bps_100, snapshot_ts) AS execution_cost_bps_100,
                argMax(depth_bid_usd_50bps, snapshot_ts) AS depth_bid_usd_50bps,
                argMax(depth_ask_usd_50bps, snapshot_ts) AS depth_ask_usd_50bps,
                argMax(liquidity_grade, snapshot_ts) AS liquidity_grade,
                argMax(status, snapshot_ts) AS status
            FROM orderbook_snapshots_enriched
            WHERE resolved_token_id IN {tokens:Array(String)}
              AND snapshot_ts >= {snapshot_cutoff:DateTime}
            GROUP BY resolved_token_id
        )
        SELECT
            token_id,
            market_slug,
            question,
            outcome_name,
            execution_cost_bps_100,
            depth_bid_usd_50bps,
            depth_ask_usd_50bps,
            liquidity_grade,
            status
        FROM latest
        WHERE status = 'ok'
          AND liquidity_grade IN ('HIGH', 'MED')
        ORDER BY execution_cost_bps_100 ASC,
                 (depth_bid_usd_50bps + depth_ask_usd_50bps) DESC
        LIMIT {limit:UInt16}
        """

        opp_result = client.query(
            opportunities_query,
            parameters={
                "tokens": tokens,
                "snapshot_cutoff": snapshot_cutoff,
                "limit": request.limit,
            },
        )

        computed_at = datetime.utcnow()
        rows = []
        for row in opp_result.result_rows:
            if not row:
                continue
            rows.append([
                proxy_wallet,
                bucket_start,
                bucket,
                row[0],
                row[1] or "",
                row[2] or "",
                row[3] or "",
                float(row[4]) if row[4] is not None else 0.0,
                float(row[5]) if row[5] is not None else 0.0,
                float(row[6]) if row[6] is not None else 0.0,
                row[7] or "",
                row[8] or "",
                computed_at,
            ])

        if rows:
            client.insert(
                "user_opportunities_bucket",
                rows,
                column_names=[
                    "proxy_wallet",
                    "bucket_start",
                    "bucket_type",
                    "token_id",
                    "market_slug",
                    "question",
                    "outcome_name",
                    "execution_cost_bps_100",
                    "depth_bid_usd_50bps",
                    "depth_ask_usd_50bps",
                    "liquidity_grade",
                    "status",
                    "computed_at",
                ],
            )

        return ComputeOpportunitiesResponse(
            proxy_wallet=proxy_wallet,
            bucket_type=bucket,
            bucket_start=bucket_start,
            buckets_written=1 if rows else 0,
            candidates_considered=candidates_considered,
            returned_count=len(rows),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compute opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/snapshot/books", response_model=SnapshotBooksResponse)
async def snapshot_books(request: SnapshotBooksRequest):
    """
    Snapshot orderbook metrics for tokens the user has traded.

    - Resolves user -> proxy_wallet
    - Gets candidate token_ids from user_trades + user_positions_snapshots (within lookback_days)
    - Filters to active markets only (if require_active_market=True)
    - Snapshots each token's orderbook (best bid/ask, spread, depth, slippage)
    - Writes to token_orderbook_snapshots table
    - Returns snapshot statistics with diagnostics
    """
    logger.info(
        f"Snapshotting books for: {request.user}, max_tokens={request.max_tokens}, "
        f"lookback_days={request.lookback_days}, require_active={request.require_active_market}, "
        f"include_inactive={request.include_inactive}"
    )

    # Resolve user
    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    logger.info(f"Resolved to proxy wallet: {proxy_wallet}")

    try:
        client = get_clickhouse_client()

        # Token selection with fallbacks
        tokens_from_trades_recent: list[str] = []
        tokens_from_trades_fallback: list[str] = []
        tokens_from_positions: list[str] = []

        candidate_contexts: list[dict] = []
        candidates_seen: set[str] = set()

        positions_seen: set[str] = set()
        latest_positions = client.query(
            """
            SELECT
                token_id,
                argMax(condition_id, ingested_at) AS condition_id,
                argMax(outcome, ingested_at) AS outcome
            FROM user_positions_snapshots
            WHERE proxy_wallet = {wallet:String}
              AND shares > 0
              AND token_id IS NOT NULL
              AND snapshot_ts = (
                  SELECT max(snapshot_ts)
                  FROM user_positions_snapshots
                  WHERE proxy_wallet = {wallet:String}
              )
            GROUP BY token_id
            """,
            parameters={"wallet": proxy_wallet},
        )
        for row in latest_positions.result_rows:
            token_id = row[0]
            condition_id = row[1] if len(row) > 1 else ""
            outcome = row[2] if len(row) > 2 else ""
            if token_id and token_id not in positions_seen:
                positions_seen.add(token_id)
                tokens_from_positions.append(token_id)
                if token_id not in candidates_seen:
                    candidates_seen.add(token_id)
                    candidate_contexts.append({
                        "token_id": token_id,
                        "condition_id": condition_id or "",
                        "outcome": outcome or "",
                    })

        lookback_start = datetime.utcnow() - timedelta(days=request.lookback_days)
        recent_trades = client.query(
            """
            SELECT
                token_id,
                argMax(condition_id, ts) AS condition_id,
                argMax(outcome, ts) AS outcome,
                max(ts) AS latest_ts
            FROM user_trades
            WHERE proxy_wallet = {wallet:String}
              AND ts >= {start:DateTime}
              AND token_id IS NOT NULL
            GROUP BY token_id
            ORDER BY latest_ts DESC
            """,
            parameters={"wallet": proxy_wallet, "start": lookback_start},
        )
        trades_seen: set[str] = set()
        for row in recent_trades.result_rows:
            token_id = row[0]
            condition_id = row[1] if len(row) > 1 else ""
            outcome = row[2] if len(row) > 2 else ""
            if token_id and token_id not in trades_seen:
                trades_seen.add(token_id)
                tokens_from_trades_recent.append(token_id)
                if token_id not in candidates_seen:
                    candidates_seen.add(token_id)
                    candidate_contexts.append({
                        "token_id": token_id,
                        "condition_id": condition_id or "",
                        "outcome": outcome or "",
                    })

        candidates_ordered, _ = _resolve_candidate_tokens(client, candidate_contexts)
        all_candidates = candidates_ordered
        tokens_candidates_before_filter = len(all_candidates)

        logger.info(
            f"Candidates before filter: {tokens_candidates_before_filter} "
            f"(positions={len(tokens_from_positions)}, recent_trades={len(tokens_from_trades_recent)})"
        )

        # 2.5. Backfill missing market_tokens mappings for candidate tokens
        # Run the metadata join before backfill, then re-run after backfill completes.
        backfill_stats = {"missing_found": 0, "markets_fetched": 0, "tokens_inserted": 0}
        missing_token_ids: list[str] = []

        def _query_market_metadata(tokens: list[str]) -> tuple[set[str], dict[str, bool]]:
            if not tokens:
                return set(), {}

            active_check = client.query(
                """
                SELECT DISTINCT mt.token_id,
                       mt.active AS mt_active,
                       mt.enable_order_book AS enable_order_book,
                       mt.accepting_orders AS accepting_orders,
                       me.active AS me_active,
                       me.close_date_iso
                FROM market_tokens mt
                LEFT JOIN markets_enriched me ON if(
                    startsWith(lowerUTF8(trimBoth(mt.condition_id)), '0x'),
                    concat('0x', substring(lowerUTF8(trimBoth(mt.condition_id)), 3)),
                    concat('0x', lowerUTF8(trimBoth(mt.condition_id)))
                ) = if(
                    startsWith(lowerUTF8(trimBoth(me.condition_id)), '0x'),
                    concat('0x', substring(lowerUTF8(trimBoth(me.condition_id)), 3)),
                    concat('0x', lowerUTF8(trimBoth(me.condition_id)))
                )
                WHERE mt.token_id IN {tokens:Array(String)}
                """,
                parameters={"tokens": list(tokens)},
            )

            tokens_with_metadata: set[str] = set()
            active_map: dict[str, bool] = {}
            for row in active_check.result_rows:
                token_id = row[0]
                mt_active = row[1]
                enable_order_book = row[2]
                accepting_orders = row[3]
                me_active = row[4]
                close_date = row[5]
                tokens_with_metadata.add(token_id)

                tradeable_flag = None
                if enable_order_book is not None:
                    tradeable_flag = enable_order_book == 1
                if accepting_orders is not None:
                    tradeable_flag = (tradeable_flag if tradeable_flag is not None else True) and accepting_orders == 1

                is_active = mt_active == 1
                if close_date is not None:
                    is_active = is_active and close_date > datetime.utcnow()
                if me_active is not None:
                    is_active = is_active and me_active == 1

                if tradeable_flag is not None:
                    is_active = is_active and tradeable_flag

                active_map[token_id] = is_active

            return tokens_with_metadata, active_map

        # 3. Apply active market filter if requested (post-backfill metadata)
        tokens_with_metadata: set[str] = set()
        tokens_after_active_filter: list[str] = []
        no_ok_reason = None

        if request.require_active_market and all_candidates:
            tokens_with_metadata, active_map = _query_market_metadata(all_candidates)
            missing_token_ids = [
                token_id for token_id in all_candidates if token_id not in tokens_with_metadata
            ]

            if missing_token_ids:
                logger.info(
                    f"Running backfill for {len(missing_token_ids)} missing market token mappings..."
                )
                candidate_condition_ids = [
                    c.get("condition_id") or "" for c in candidate_contexts if c.get("condition_id")
                ]
                candidate_token_ids = [
                    c.get("token_id") or "" for c in candidate_contexts if c.get("token_id")
                ]
                backfill_stats = backfill_missing_mappings(
                    clickhouse_client=client,
                    gamma_client=gamma_client,
                    proxy_wallet=proxy_wallet,
                    max_missing=min(200, len(missing_token_ids)),  # Bounded by safety cap
                    candidate_condition_ids=candidate_condition_ids,
                    candidate_token_ids=candidate_token_ids,
                )
                logger.info(f"Backfill complete: {backfill_stats}")

                # Re-resolve candidate tokens after backfill (aliases/markets may now be present)
                all_candidates, _ = _resolve_candidate_tokens(client, candidate_contexts)

                # Refresh metadata after backfill completes
                tokens_with_metadata, active_map = _query_market_metadata(all_candidates)

            tokens_after_active_filter = [
                token_id for token_id in all_candidates if active_map.get(token_id)
            ]

            logger.info(
                f"Active filter: {len(tokens_with_metadata)} have metadata, "
                f"{len(tokens_after_active_filter)} are active"
            )

            # If no active tokens but we have candidates, set diagnostic reason
            if not tokens_after_active_filter:
                if tokens_with_metadata:
                    no_ok_reason = (
                        f"All {len(tokens_with_metadata)} tokens with market metadata are from closed/inactive markets"
                    )
                else:
                    if backfill_stats.get("tokens_inserted", 0) > 0:
                        no_ok_reason = (
                            "Backfill inserted tokens but metadata join still returned 0 - "
                            "investigate market_tokens coverage/schema"
                        )
                    else:
                        market_tokens_total = client.query(
                            "SELECT count() FROM market_tokens"
                        ).result_rows[0][0]
                        if market_tokens_total == 0:
                            no_ok_reason = (
                                f"No market metadata found for {len(all_candidates)} candidate tokens "
                                "(markets not ingested; run /api/ingest/markets)"
                            )
                        elif backfill_stats.get("missing_found", 0) > 0 and backfill_stats.get("tokens_inserted", 0) == 0:
                            no_ok_reason = (
                                f"No market metadata found for {len(all_candidates)} candidate tokens "
                                "(token id mismatch unresolved)"
                            )
                        else:
                            no_ok_reason = (
                                f"No market metadata found for {len(all_candidates)} candidate tokens "
                                "(run /api/ingest/markets first)"
                            )

                # Fall back to historical if requested
                if request.include_inactive:
                    logger.info("include_inactive=True, falling back to historical tokens")
                    # Get last 50 distinct tokens from all trades
                    fallback_trades = client.query(
                        """
                        SELECT
                            token_id,
                            argMax(condition_id, ts) AS condition_id,
                            argMax(outcome, ts) AS outcome,
                            max(ts) AS latest_ts
                        FROM user_trades
                        WHERE proxy_wallet = {wallet:String}
                          AND token_id IS NOT NULL
                        GROUP BY token_id
                        ORDER BY latest_ts DESC
                        LIMIT 50
                        """,
                        parameters={"wallet": proxy_wallet},
                    )
                    fallback_seen: set[str] = set()
                    fallback_candidates: list[dict] = []
                    for row in fallback_trades.result_rows:
                        token_id = row[0]
                        condition_id = row[1] if len(row) > 1 else ""
                        outcome = row[2] if len(row) > 2 else ""
                        if token_id and token_id not in fallback_seen:
                            fallback_seen.add(token_id)
                            tokens_from_trades_fallback.append(token_id)
                            fallback_candidates.append({
                                "token_id": token_id,
                                "condition_id": condition_id or "",
                                "outcome": outcome or "",
                            })
                    resolved_fallback_tokens, _ = _resolve_candidate_tokens(
                        client, fallback_candidates
                    )
                    tokens_from_trades_fallback = resolved_fallback_tokens
                    no_ok_reason = no_ok_reason + " (using historical fallback)"
        else:
            # Not filtering by active market - use all candidates
            tokens_after_active_filter = list(all_candidates)
            tokens_with_metadata = set()  # Not checked

        # Final token set to snapshot
        final_tokens: list[str] = list(tokens_after_active_filter)
        final_seen = set(final_tokens)
        for token_id in tokens_from_trades_fallback:
            if token_id not in final_seen:
                final_seen.add(token_id)
                final_tokens.append(token_id)
        tokens_selected_total = len(final_tokens)

        logger.info(
            f"Final token selection: {tokens_selected_total} tokens "
            f"(active_filtered={len(tokens_after_active_filter)}, fallback={len(tokens_from_trades_fallback)})"
        )

        if not final_tokens:
            return SnapshotBooksResponse(
                proxy_wallet=proxy_wallet,
                backfill_missing_found=backfill_stats.get("missing_found", 0),
                backfill_markets_fetched=backfill_stats.get("markets_fetched", 0),
                backfill_tokens_inserted=backfill_stats.get("tokens_inserted", 0),
                tokens_candidates_before_filter=tokens_candidates_before_filter,
                tokens_from_trades_recent=len(tokens_from_trades_recent),
                tokens_from_trades_fallback=len(tokens_from_trades_fallback),
                tokens_from_positions=len(tokens_from_positions),
                tokens_with_market_metadata=len(tokens_with_metadata),
                tokens_after_active_filter=len(tokens_after_active_filter),
                tokens_selected_total=0,
                tokens_attempted=0,
                tokens_ok=0,
                tokens_empty=0,
                tokens_one_sided=0,
                tokens_no_orderbook=0,
                tokens_error=0,
                tokens_http_429=0,
                tokens_http_5xx=0,
                tokens_skipped_no_orderbook_ttl=0,
                tokens_skipped_limit=[],
                snapshot_ts=datetime.utcnow(),
                no_ok_reason=no_ok_reason or "No tokens found for user",
            )

        snapshot_ts = datetime.utcnow()
        max_tokens_attempted = min(request.max_tokens, BOOK_SNAPSHOT_MAX_PREFLIGHT)

        tokens_skipped_no_orderbook_ttl = 0
        skip_no_orderbook: set[str] = set()
        if BOOK_SNAPSHOT_404_TTL_HOURS > 0 and final_tokens:
            ttl_cutoff = snapshot_ts - timedelta(hours=BOOK_SNAPSHOT_404_TTL_HOURS)
            try:
                ttl_result = client.query(
                    """
                    SELECT token_id
                    FROM (
                        SELECT token_id, argMax(status, snapshot_ts) AS latest_status
                        FROM token_orderbook_snapshots
                        WHERE snapshot_ts >= {cutoff:DateTime}
                          AND token_id IN {tokens:Array(String)}
                        GROUP BY token_id
                    )
                    WHERE latest_status = 'no_orderbook'
                    """,
                    parameters={"cutoff": ttl_cutoff, "tokens": list(final_tokens)},
                )
                skip_no_orderbook = {row[0] for row in ttl_result.result_rows if row and row[0]}
            except Exception as exc:
                logger.warning(f"Failed to load no_orderbook TTL cache: {exc}")

        snapshots: list[OrderbookSnapshot] = []
        tokens_attempted = 0
        tokens_ok = 0
        tokens_empty = 0
        tokens_one_sided = 0
        tokens_no_orderbook = 0
        tokens_error = 0
        tokens_http_429 = 0
        tokens_http_5xx = 0
        tokens_skipped_limit: list[str] = []

        remaining_start = None
        for idx, token_id in enumerate(final_tokens):
            if token_id in skip_no_orderbook:
                tokens_skipped_no_orderbook_ttl += 1
                continue
            if tokens_attempted >= max_tokens_attempted or tokens_ok >= BOOK_SNAPSHOT_MIN_OK_TARGET:
                remaining_start = idx
                break

            tokens_attempted += 1
            try:
                response = clob_client.fetch_book_response(token_id)
            except Exception as exc:
                snapshots.append(
                    _build_basic_snapshot(
                        token_id=token_id,
                        snapshot_ts=snapshot_ts,
                        status="error",
                        reason=str(exc),
                    )
                )
                tokens_error += 1
                continue

            status_code = response.status_code
            if status_code == 200:
                try:
                    book = response.json()
                except ValueError:
                    snapshots.append(
                        _build_basic_snapshot(
                            token_id=token_id,
                            snapshot_ts=snapshot_ts,
                            status="error",
                            reason="Invalid JSON response",
                        )
                    )
                    tokens_error += 1
                    continue

                snapshot = snapshot_from_book(
                    token_id=token_id,
                    book=book,
                    snapshot_ts=snapshot_ts,
                    depth_band_bps=BOOK_SNAPSHOT_DEPTH_BAND_BPS,
                    notional_sizes=BOOK_SNAPSHOT_NOTIONALS,
                )
                snapshots.append(snapshot)
                if snapshot.status == "ok":
                    tokens_ok += 1
                elif snapshot.status == "empty":
                    tokens_empty += 1
                elif snapshot.status == "one_sided":
                    tokens_one_sided += 1
                else:
                    tokens_error += 1
                continue

            error_message = _extract_error_message_from_response(response)
            if status_code == 404 and error_message and "No orderbook exists" in error_message:
                snapshots.append(
                    _build_basic_snapshot(
                        token_id=token_id,
                        snapshot_ts=snapshot_ts,
                        status="no_orderbook",
                        reason=error_message,
                    )
                )
                tokens_no_orderbook += 1
                continue

            if status_code == 429:
                tokens_http_429 += 1
            elif 500 <= status_code <= 599:
                tokens_http_5xx += 1

            snapshots.append(
                _build_basic_snapshot(
                    token_id=token_id,
                    snapshot_ts=snapshot_ts,
                    status="error",
                    reason=error_message or f"HTTP {status_code}",
                )
            )
            tokens_error += 1

        if remaining_start is not None:
            tokens_skipped_limit = [
                token_id for token_id in final_tokens[remaining_start:]
                if token_id not in skip_no_orderbook
            ]

        # Write to ClickHouse
        if snapshots:
            rows = [s.to_row() for s in snapshots]
            client.insert(
                "token_orderbook_snapshots",
                rows,
                column_names=get_snapshot_columns(),
            )
            logger.info(f"Inserted {len(rows)} orderbook snapshots into ClickHouse")

        # Build diagnostic reason if no OK snapshots
        if tokens_ok == 0:
            if tokens_no_orderbook > 0:
                if tokens_attempted > 0 and tokens_no_orderbook >= (tokens_attempted / 2):
                    no_ok_reason = (
                        f"Most tokens returned no_orderbook ({tokens_no_orderbook} of {tokens_attempted})"
                    )
                else:
                    no_ok_reason = f"{tokens_no_orderbook} tokens returned no_orderbook"
            elif tokens_empty > 0:
                no_ok_reason = f"All {tokens_empty} tokens have empty orderbooks"
            elif tokens_one_sided > 0:
                no_ok_reason = f"All {tokens_one_sided} tokens have one-sided orderbooks"
            elif tokens_error > 0:
                no_ok_reason = f"All {tokens_error} tokens had errors fetching orderbook"

        return SnapshotBooksResponse(
            proxy_wallet=proxy_wallet,
            backfill_missing_found=backfill_stats.get("missing_found", 0),
            backfill_markets_fetched=backfill_stats.get("markets_fetched", 0),
            backfill_tokens_inserted=backfill_stats.get("tokens_inserted", 0),
            tokens_candidates_before_filter=tokens_candidates_before_filter,
            tokens_from_trades_recent=len(tokens_from_trades_recent),
            tokens_from_trades_fallback=len(tokens_from_trades_fallback),
            tokens_from_positions=len(tokens_from_positions),
            tokens_with_market_metadata=len(tokens_with_metadata),
            tokens_after_active_filter=len(tokens_after_active_filter),
            tokens_selected_total=tokens_selected_total,
            tokens_attempted=tokens_attempted,
            tokens_ok=tokens_ok,
            tokens_empty=tokens_empty,
            tokens_one_sided=tokens_one_sided,
            tokens_no_orderbook=tokens_no_orderbook,
            tokens_error=tokens_error,
            tokens_http_429=tokens_http_429,
            tokens_http_5xx=tokens_http_5xx,
            tokens_skipped_no_orderbook_ttl=tokens_skipped_no_orderbook_ttl,
            tokens_skipped_limit=tokens_skipped_limit,
            snapshot_ts=snapshot_ts,
            no_ok_reason=no_ok_reason,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to snapshot books: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/user_dossier", response_model=ExportUserDossierResponse)
async def export_user_dossier_api(request: ExportUserDossierRequest):
    """
    Export a deterministic user dossier + research memo for later LLM review.

    - Resolves user to proxy wallet
    - Builds dossier JSON and memo template
    - Writes artifacts and stores export in ClickHouse
    """
    logger.info(
        f"Exporting user dossier for: {request.user}, days={request.days}, max_trades={request.max_trades}"
    )

    profile = gamma_client.resolve(request.user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {request.user}")

    proxy_wallet = profile.proxy_wallet
    try:
        client = get_clickhouse_client()
        _assert_dossier_export_schema(client)
        _, stored_username = _get_existing_user_metadata(client, proxy_wallet)
        input_username = _normalize_username_input(request.user)
        resolved_profile_username = f"@{profile.username}" if profile.username else ""
        if input_username:
            resolved_username = resolved_profile_username or input_username
        else:
            resolved_username = stored_username or resolved_profile_username
        resolved_username = resolved_username or None

        _upsert_user_profile(client, profile, request.user)

        export_result = export_user_dossier(
            clickhouse_client=client,
            proxy_wallet=proxy_wallet,
            user_input=request.user,
            username=resolved_username,
            window_days=request.days,
            max_trades=request.max_trades,
        )
    except HTTPException:
        raise
    except MissingClickHouseSchemaError as e:
        logger.error(f"Dossier export schema check failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to export user dossier: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return ExportUserDossierResponse(
        export_id=export_result.export_id,
        proxy_wallet=proxy_wallet,
        username=export_result.username,
        username_slug=export_result.username_slug,
        artifact_path=export_result.artifact_path,
        generated_at=export_result.generated_at,
        path_json=export_result.path_json,
        path_md=export_result.path_md,
        stats=export_result.stats,
    )


@app.get("/api/export/user_dossier/history", response_model=ExportUserDossierHistoryResponse)
async def export_user_dossier_history(
    user: str,
    limit: int = 20,
    include_body: bool = False,
):
    """
    Fetch export history rows for a user.

    - Returns summary rows by default
    - include_body=true returns full JSON/memo fields
    """
    if limit <= 0:
        raise HTTPException(status_code=400, detail="limit must be positive")
    if limit > 200:
        raise HTTPException(status_code=400, detail="limit must be <= 200")

    profile = gamma_client.resolve(user)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Could not resolve user: {user}")

    proxy_wallet = profile.proxy_wallet
    select_fields = [
        "export_id",
        "proxy_wallet",
        "username",
        "username_slug",
        "artifact_path",
        "generated_at",
        "window_start",
        "window_end",
        "window_days",
        "max_trades",
        "trades_count",
        "activity_count",
        "positions_count",
        "mapping_coverage",
        "liquidity_ok_count",
        "liquidity_total_count",
        "usable_liquidity_rate",
        "pricing_snapshot_ratio",
        "pricing_confidence",
        "anchor_trade_uids",
    ]
    if include_body:
        select_fields.extend(["detectors_json", "dossier_json", "memo_md"])

    query = f"""
        SELECT {", ".join(select_fields)}
        FROM user_dossier_exports
        WHERE proxy_wallet = {{wallet:String}}
        ORDER BY generated_at DESC
        LIMIT {{limit:Int32}}
    """

    try:
        client = get_clickhouse_client()
        result = client.query(
            query,
            parameters={"wallet": proxy_wallet, "limit": limit},
        )
    except Exception as e:
        logger.error(f"Failed to load dossier export history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    rows: list[ExportUserDossierHistoryRow] = []
    for row in result.result_rows:
        base = {
            "export_id": row[0],
            "proxy_wallet": row[1],
            "username": row[2] or None,
            "username_slug": row[3] or "unknown",
            "artifact_path": row[4] or "",
            "generated_at": row[5],
            "window_start": row[6],
            "window_end": row[7],
            "window_days": row[8],
            "max_trades": row[9],
            "trades_count": row[10],
            "activity_count": row[11],
            "positions_count": row[12],
            "mapping_coverage": row[13],
            "liquidity_ok_count": row[14],
            "liquidity_total_count": row[15],
            "usable_liquidity_rate": row[16],
            "pricing_snapshot_ratio": row[17],
            "pricing_confidence": row[18],
            "anchor_trade_uids": row[19] or [],
        }
        if include_body:
            base["detectors_json"] = row[20]
            base["dossier_json"] = row[21]
            base["memo_md"] = row[22]
        rows.append(ExportUserDossierHistoryRow(**base))

    return ExportUserDossierHistoryResponse(proxy_wallet=proxy_wallet, rows=rows)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
