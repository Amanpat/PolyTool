"""Backfill missing market metadata for user trades."""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Optional

from .gamma import GammaClient, Market
from .normalization import normalize_condition_id

logger = logging.getLogger(__name__)

_BACKFILL_CACHE: dict[str, datetime] = {}
_BACKFILL_CACHE_TTL = timedelta(hours=6)


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
    WITH
        if(
            startsWith(lowerUTF8(trimBoth(t.condition_id)), '0x'),
            concat('0x', substring(lowerUTF8(trimBoth(t.condition_id)), 3)),
            concat('0x', lowerUTF8(trimBoth(t.condition_id)))
        ) AS t_condition_norm,
        if(
            startsWith(lowerUTF8(trimBoth(mt.condition_id)), '0x'),
            concat('0x', substring(lowerUTF8(trimBoth(mt.condition_id)), 3)),
            concat('0x', lowerUTF8(trimBoth(mt.condition_id)))
        ) AS mt_condition_norm
    SELECT DISTINCT t_condition_norm
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t_condition_norm = mt_condition_norm
    WHERE t.proxy_wallet = '{proxy_wallet}'
      AND t_condition_norm != ''
      AND (mt_condition_norm = '' OR mt_condition_norm IS NULL)
    LIMIT {limit}
    """


def get_missing_token_ids_sql(proxy_wallet: str, limit: int = 500) -> str:
    """
    Generate SQL to find token_ids in user_trades missing from market_tokens and token_aliases.
    """
    return f"""
    SELECT DISTINCT t.token_id
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t.token_id = mt.token_id
    LEFT JOIN polyttool.token_aliases AS ta ON t.token_id = ta.alias_token_id
    WHERE t.proxy_wallet = '{proxy_wallet}'
      AND t.token_id != ''
      AND (mt.token_id = '' OR mt.token_id IS NULL)
      AND (ta.alias_token_id = '' OR ta.alias_token_id IS NULL)
    LIMIT {limit}
    """


def get_missing_slugs_sql(proxy_wallet: str, limit: int = 200) -> str:
    """
    Generate SQL to find slugs embedded in raw_json that are missing from markets.
    """
    return f"""
    SELECT DISTINCT slug
    FROM (
        SELECT
            coalesce(
                JSONExtractString(raw_json, 'slug'),
                JSONExtractString(raw_json, 'marketSlug'),
                JSONExtractString(raw_json, 'market_slug')
            ) AS slug
        FROM polyttool.user_trades
        WHERE proxy_wallet = '{proxy_wallet}'
    )
    WHERE slug != ''
      AND slug NOT IN (SELECT market_slug FROM polyttool.markets)
    LIMIT {limit}
    """


def _filter_recent(identifiers: list[str]) -> list[str]:
    now = datetime.utcnow()
    filtered: list[str] = []
    for ident in identifiers:
        last = _BACKFILL_CACHE.get(ident)
        if last is None or now - last > _BACKFILL_CACHE_TTL:
            filtered.append(ident)
            _BACKFILL_CACHE[ident] = now
    return filtered


def _filter_missing_condition_ids(clickhouse_client, condition_ids: list[str]) -> list[str]:
    if not condition_ids:
        return []
    unique = list(dict.fromkeys([normalize_condition_id(cid) for cid in condition_ids if cid]))
    if not unique:
        return []
    result = clickhouse_client.query(
        """
        WITH
            if(
                startsWith(lowerUTF8(trimBoth(condition_id)), '0x'),
                concat('0x', substring(lowerUTF8(trimBoth(condition_id)), 3)),
                concat('0x', lowerUTF8(trimBoth(condition_id)))
            ) AS condition_id_norm
        SELECT DISTINCT condition_id_norm
        FROM polyttool.market_tokens
        WHERE condition_id_norm IN {conditions:Array(String)}
        """,
        parameters={"conditions": unique},
    )
    existing = {row[0] for row in result.result_rows if row and row[0]}
    return [cid for cid in unique if cid not in existing]


def _filter_missing_token_ids(clickhouse_client, token_ids: list[str]) -> list[str]:
    if not token_ids:
        return []
    unique = list(dict.fromkeys([str(token) for token in token_ids if token]))
    if not unique:
        return []
    mt_result = clickhouse_client.query(
        "SELECT token_id FROM polyttool.market_tokens WHERE token_id IN {tokens:Array(String)}",
        parameters={"tokens": unique},
    )
    ta_result = clickhouse_client.query(
        "SELECT alias_token_id FROM polyttool.token_aliases WHERE alias_token_id IN {tokens:Array(String)}",
        parameters={"tokens": unique},
    )
    mapped = {row[0] for row in mt_result.result_rows if row and row[0]}
    mapped.update({row[0] for row in ta_result.result_rows if row and row[0]})
    return [token for token in unique if token not in mapped]


def _filter_missing_slugs(clickhouse_client, slugs: list[str]) -> list[str]:
    if not slugs:
        return []
    unique = list(dict.fromkeys([slug.strip() for slug in slugs if slug and slug.strip()]))
    if not unique:
        return []
    result = clickhouse_client.query(
        "SELECT market_slug FROM polyttool.markets WHERE market_slug IN {slugs:Array(String)}",
        parameters={"slugs": unique},
    )
    existing = {row[0] for row in result.result_rows if row and row[0]}
    return [slug for slug in unique if slug not in existing]


def _load_existing_taxonomy_by_token(clickhouse_client, token_ids: list[str]) -> dict[str, dict[str, str]]:
    """Load latest taxonomy fields so backfill never overwrites non-empty values."""
    if not token_ids:
        return {}
    unique = list(dict.fromkeys(str(token_id) for token_id in token_ids if token_id))
    if not unique:
        return {}

    try:
        result = clickhouse_client.query(
            """
            SELECT
                token_id,
                argMax(category, ingested_at) AS category,
                argMax(subcategory, ingested_at) AS subcategory,
                argMax(category_source, ingested_at) AS category_source,
                argMax(subcategory_source, ingested_at) AS subcategory_source
            FROM polyttool.market_tokens
            WHERE token_id IN {tokens:Array(String)}
            GROUP BY token_id
            """,
            parameters={"tokens": unique},
        )
        rows = result.result_rows
        has_subcategory = True
        has_category_source = True
        has_subcategory_source = True
    except Exception:
        # Backward-compatible query when source marker columns are not yet available.
        try:
            result = clickhouse_client.query(
                """
                SELECT
                    token_id,
                    argMax(category, ingested_at) AS category,
                    argMax(subcategory, ingested_at) AS subcategory
                FROM polyttool.market_tokens
                WHERE token_id IN {tokens:Array(String)}
                GROUP BY token_id
                """,
                parameters={"tokens": unique},
            )
            rows = result.result_rows
            has_subcategory = True
            has_category_source = False
            has_subcategory_source = False
        except Exception:
            # Backward-compatible query when only category exists.
            try:
                result = clickhouse_client.query(
                    """
                    SELECT
                        token_id,
                        argMax(category, ingested_at) AS category
                    FROM polyttool.market_tokens
                    WHERE token_id IN {tokens:Array(String)}
                    GROUP BY token_id
                    """,
                    parameters={"tokens": unique},
                )
                rows = result.result_rows
                has_subcategory = False
                has_category_source = False
                has_subcategory_source = False
            except Exception:
                return {}

    taxonomy_by_token: dict[str, dict[str, str]] = {}
    for row in rows:
        if not row:
            continue
        token_id = str(row[0] or "").strip()
        if not token_id:
            continue
        category = str(row[1] or "").strip() if len(row) > 1 else ""
        subcategory = str(row[2] or "").strip() if has_subcategory and len(row) > 2 else ""
        category_source = (
            str(row[3] or "").strip()
            if has_category_source and len(row) > 3
            else "none"
        )
        subcategory_source = (
            str(row[4] or "").strip()
            if has_subcategory_source and len(row) > 4
            else "none"
        )
        if not category:
            category_source = "none"
        elif category_source not in {"market", "event"}:
            category_source = "none"
        if not subcategory:
            subcategory_source = "none"
        elif subcategory_source != "event":
            subcategory_source = "none"
        taxonomy_by_token[token_id] = {
            "category": category,
            "subcategory": subcategory,
            "category_source": category_source,
            "subcategory_source": subcategory_source,
        }
    return taxonomy_by_token


def get_all_missing_condition_ids_sql(limit: int = 1000) -> str:
    """
    Generate SQL to find all condition_ids across all users that are missing from market_tokens.

    Args:
        limit: Maximum number of missing condition_ids to return

    Returns:
        SQL query string
    """
    return f"""
    WITH
        if(
            startsWith(lowerUTF8(trimBoth(t.condition_id)), '0x'),
            concat('0x', substring(lowerUTF8(trimBoth(t.condition_id)), 3)),
            concat('0x', lowerUTF8(trimBoth(t.condition_id)))
        ) AS t_condition_norm,
        if(
            startsWith(lowerUTF8(trimBoth(mt.condition_id)), '0x'),
            concat('0x', substring(lowerUTF8(trimBoth(mt.condition_id)), 3)),
            concat('0x', lowerUTF8(trimBoth(mt.condition_id)))
        ) AS mt_condition_norm
    SELECT DISTINCT t_condition_norm
    FROM polyttool.user_trades AS t
    LEFT JOIN polyttool.market_tokens AS mt ON t_condition_norm = mt_condition_norm
    WHERE t_condition_norm != ''
      AND (mt_condition_norm = '' OR mt_condition_norm IS NULL)
    LIMIT {limit}
    """


def backfill_missing_mappings(
    clickhouse_client,
    gamma_client: GammaClient,
    proxy_wallet: Optional[str] = None,
    max_missing: int = 500,
    candidate_condition_ids: Optional[list[str]] = None,
    candidate_token_ids: Optional[list[str]] = None,
    candidate_slugs: Optional[list[str]] = None,
    request_delay_seconds: float = 0.1,
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
    missing_condition_ids: list[str] = []
    missing_token_ids: list[str] = []
    missing_slugs: list[str] = []

    if candidate_condition_ids:
        missing_condition_ids = _filter_missing_condition_ids(
            clickhouse_client,
            candidate_condition_ids,
        )
    elif proxy_wallet:
        sql = get_missing_condition_ids_sql(proxy_wallet, max_missing)
        result = clickhouse_client.query(sql)
        missing_condition_ids = [
            normalize_condition_id(row[0]) for row in result.result_rows if row[0]
        ]
    else:
        sql = get_all_missing_condition_ids_sql(max_missing)
        result = clickhouse_client.query(sql)
        missing_condition_ids = [
            normalize_condition_id(row[0]) for row in result.result_rows if row[0]
        ]

    if candidate_token_ids:
        missing_token_ids = _filter_missing_token_ids(
            clickhouse_client,
            candidate_token_ids,
        )
    elif proxy_wallet:
        token_sql = get_missing_token_ids_sql(proxy_wallet, max_missing)
        token_result = clickhouse_client.query(token_sql)
        missing_token_ids = [row[0] for row in token_result.result_rows if row[0]]

    if candidate_slugs:
        missing_slugs = _filter_missing_slugs(clickhouse_client, candidate_slugs)
    elif proxy_wallet:
        slug_sql = get_missing_slugs_sql(proxy_wallet, max_missing)
        slug_result = clickhouse_client.query(slug_sql)
        missing_slugs = [row[0] for row in slug_result.result_rows if row[0]]

    missing_condition_ids = _filter_recent(missing_condition_ids)
    missing_token_ids = _filter_recent(missing_token_ids)
    missing_slugs = _filter_recent(missing_slugs)

    if max_missing:
        missing_condition_ids = missing_condition_ids[:max_missing]
        missing_token_ids = missing_token_ids[:max_missing]
        missing_slugs = missing_slugs[:max_missing]

    missing_total = len(missing_condition_ids) + len(missing_token_ids) + len(missing_slugs)
    logger.info(
        "Found missing identifiers for backfill: "
        f"conditions={len(missing_condition_ids)}, "
        f"tokens={len(missing_token_ids)}, "
        f"slugs={len(missing_slugs)}"
    )

    if missing_total == 0:
        return {
            "missing_found": 0,
            "missing_conditions": 0,
            "missing_tokens": 0,
            "missing_slugs": 0,
            "markets_fetched": 0,
            "tokens_inserted": 0,
            "markets_inserted": 0,
            "aliases_inserted": 0,
        }

    markets_by_condition: dict[str, Market] = {}
    markets: list[Market] = []

    if missing_condition_ids:
        markets.extend(gamma_client.get_markets_by_condition_ids(missing_condition_ids))
        if request_delay_seconds:
            time.sleep(request_delay_seconds)

    if missing_token_ids:
        markets.extend(gamma_client.get_markets_by_clob_token_ids(missing_token_ids))
        if request_delay_seconds:
            time.sleep(request_delay_seconds)

    if missing_slugs:
        markets.extend(gamma_client.get_markets_by_slugs(missing_slugs))
        if request_delay_seconds:
            time.sleep(request_delay_seconds)

    for market in markets:
        markets_by_condition[market.condition_id] = market

    markets = list(markets_by_condition.values())

    logger.info(f"Fetched {len(markets)} markets from Gamma API")

    if not markets:
        return {
            "missing_found": missing_total,
            "missing_conditions": len(missing_condition_ids),
            "missing_tokens": len(missing_token_ids),
            "missing_slugs": len(missing_slugs),
            "markets_fetched": 0,
            "tokens_inserted": 0,
            "markets_inserted": 0,
            "aliases_inserted": 0,
        }

    # Insert market_tokens
    market_tokens = []
    for market in markets:
        market_tokens.extend(market.to_market_tokens())

    existing_taxonomy_by_token = _load_existing_taxonomy_by_token(
        clickhouse_client,
        [mt.token_id for mt in market_tokens],
    )

    token_rows = []
    for mt in market_tokens:
        existing_taxonomy = existing_taxonomy_by_token.get(str(mt.token_id), {})

        category = str(mt.category or "").strip()
        existing_category = str(existing_taxonomy.get("category") or "").strip()
        if existing_category:
            category = existing_category

        subcategory = str(mt.subcategory or "").strip()
        existing_subcategory = str(existing_taxonomy.get("subcategory") or "").strip()
        if existing_subcategory:
            subcategory = existing_subcategory

        category_source = str(mt.category_source or "none").strip() or "none"
        existing_category_source = str(existing_taxonomy.get("category_source") or "").strip()
        if existing_category_source in {"market", "event"}:
            category_source = existing_category_source
        if not category:
            category_source = "none"
        elif category_source not in {"market", "event"}:
            category_source = "none"

        subcategory_source = str(mt.subcategory_source or "none").strip() or "none"
        existing_subcategory_source = str(existing_taxonomy.get("subcategory_source") or "").strip()
        if existing_subcategory_source == "event":
            subcategory_source = existing_subcategory_source
        if not subcategory:
            subcategory_source = "none"
        elif subcategory_source != "event":
            subcategory_source = "none"

        token_rows.append([
            mt.token_id,
            mt.condition_id,
            mt.outcome_index,
            mt.outcome_name,
            mt.market_slug,
            mt.question,
            category,
            subcategory,
            category_source,
            subcategory_source,
            mt.event_slug,
            mt.end_date_iso,
            1 if mt.active else 0,
            1 if mt.enable_order_book else 0 if mt.enable_order_book is not None else None,
            1 if mt.accepting_orders else 0 if mt.accepting_orders is not None else None,
            json.dumps(mt.raw_json),
            datetime.utcnow(),
        ])

    if token_rows:
        clickhouse_client.insert(
            "market_tokens",
            token_rows,
            column_names=[
                "token_id", "condition_id", "outcome_index", "outcome_name",
                "market_slug", "question", "category", "subcategory",
                "category_source", "subcategory_source", "event_slug",
                "end_date_iso", "active", "enable_order_book", "accepting_orders",
                "raw_json", "ingested_at"
            ],
        )
        logger.info(f"Inserted {len(token_rows)} market_tokens rows")

    # Insert token_aliases mappings
    alias_rows = []
    for market in markets:
        for alias in market.to_token_aliases():
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

    if alias_rows:
        clickhouse_client.insert(
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
        logger.info(f"Inserted {len(alias_rows)} token_aliases rows")

    # Insert markets
    market_rows = []
    for m in markets:
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

    if market_rows:
        clickhouse_client.insert(
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
        logger.info(f"Inserted {len(market_rows)} markets rows")

    return {
        "missing_found": missing_total,
        "missing_conditions": len(missing_condition_ids),
        "missing_tokens": len(missing_token_ids),
        "missing_slugs": len(missing_slugs),
        "markets_fetched": len(markets),
        "tokens_inserted": len(token_rows),
        "markets_inserted": len(market_rows),
        "aliases_inserted": len(alias_rows),
    }
