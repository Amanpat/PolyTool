"""Backfill missing market metadata for user trades."""

import json
import logging
from datetime import datetime
from typing import Optional

from .gamma import GammaClient, Market

logger = logging.getLogger(__name__)


def get_missing_condition_ids_sql(proxy_wallet: str, limit: int = 500) -> str:
    """
    Generate SQL to find condition_ids in user_trades that are missing from market_tokens.

    Args:
        proxy_wallet: User's proxy wallet address
        limit: Maximum number of missing condition_ids to return

    Returns:
        SQL query string
    """
    return f"""
    SELECT DISTINCT t.condition_id
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t.condition_id = mt.condition_id
    WHERE t.proxy_wallet = '{proxy_wallet}'
      AND t.condition_id != ''
      AND length(mt.condition_id) = 0
    LIMIT {limit}
    """


def get_all_missing_condition_ids_sql(limit: int = 1000) -> str:
    """
    Generate SQL to find all condition_ids across all users that are missing from market_tokens.

    Args:
        limit: Maximum number of missing condition_ids to return

    Returns:
        SQL query string
    """
    return f"""
    SELECT DISTINCT t.condition_id
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t.condition_id = mt.condition_id
    WHERE t.condition_id != ''
      AND length(mt.condition_id) = 0
    LIMIT {limit}
    """


def backfill_missing_mappings(
    clickhouse_client,
    gamma_client: GammaClient,
    proxy_wallet: Optional[str] = None,
    max_missing: int = 500,
) -> dict:
    """
    Backfill missing market_tokens mappings for condition_ids in user_trades.

    Args:
        clickhouse_client: ClickHouse client instance
        gamma_client: GammaClient instance for fetching market data
        proxy_wallet: Optional - limit to a specific user's trades
        max_missing: Maximum number of condition_ids to backfill

    Returns:
        Dict with backfill stats: {
            "missing_found": int,
            "markets_fetched": int,
            "tokens_inserted": int,
            "markets_inserted": int,
        }
    """
    # Query for missing condition_ids
    if proxy_wallet:
        sql = get_missing_condition_ids_sql(proxy_wallet, max_missing)
    else:
        sql = get_all_missing_condition_ids_sql(max_missing)

    result = clickhouse_client.query(sql)
    missing_condition_ids = [row[0] for row in result.result_rows if row[0]]

    logger.info(f"Found {len(missing_condition_ids)} missing condition_ids to backfill")

    if not missing_condition_ids:
        return {
            "missing_found": 0,
            "markets_fetched": 0,
            "tokens_inserted": 0,
            "markets_inserted": 0,
        }

    # Fetch markets from Gamma
    markets = gamma_client.get_markets_by_condition_ids(missing_condition_ids)

    logger.info(f"Fetched {len(markets)} markets from Gamma API")

    if not markets:
        return {
            "missing_found": len(missing_condition_ids),
            "markets_fetched": 0,
            "tokens_inserted": 0,
            "markets_inserted": 0,
        }

    # Insert market_tokens
    token_rows = []
    for market in markets:
        for mt in market.to_market_tokens():
            token_rows.append([
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

    if token_rows:
        clickhouse_client.insert(
            "market_tokens",
            token_rows,
            column_names=[
                "token_id", "condition_id", "outcome_index", "outcome_name",
                "market_slug", "question", "category", "event_slug",
                "end_date_iso", "active", "raw_json", "ingested_at"
            ],
        )
        logger.info(f"Inserted {len(token_rows)} market_tokens rows")

    # Insert markets
    market_rows = []
    for m in markets:
        market_rows.append([
            m.condition_id,
            m.market_slug,
            m.question,
            m.description,
            m.category,
            m.event_slug,
            m.outcomes,
            m.clob_token_ids,
            m.end_date_iso,
            1 if m.active else 0,
            m.liquidity,
            m.volume,
            json.dumps(m.raw_json),
            datetime.utcnow(),
        ])

    if market_rows:
        clickhouse_client.insert(
            "markets",
            market_rows,
            column_names=[
                "condition_id", "market_slug", "question", "description",
                "category", "event_slug", "outcomes", "clob_token_ids",
                "end_date_iso", "active", "liquidity", "volume",
                "raw_json", "ingested_at"
            ],
        )
        logger.info(f"Inserted {len(market_rows)} markets rows")

    return {
        "missing_found": len(missing_condition_ids),
        "markets_fetched": len(markets),
        "tokens_inserted": len(token_rows),
        "markets_inserted": len(market_rows),
    }
