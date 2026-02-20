from __future__ import annotations

from datetime import datetime

from polymarket.gamma import MarketToken
from services.api import main as api_main


def test_ingest_markets_insert_columns_include_category_and_subcategory_when_available():
    available_columns = {
        "token_id",
        "condition_id",
        "outcome_index",
        "outcome_name",
        "market_slug",
        "question",
        "category",
        "subcategory",
        "category_source",
        "subcategory_source",
        "event_slug",
        "end_date_iso",
        "active",
        "enable_order_book",
        "accepting_orders",
        "raw_json",
        "ingested_at",
    }
    columns = api_main._market_tokens_insert_columns(available_columns)
    assert "category" in columns
    assert "subcategory" in columns
    assert "category_source" in columns
    assert "subcategory_source" in columns


def test_ingest_markets_rows_fill_empty_taxonomy_without_overwrite():
    token = MarketToken(
        token_id="tok-1",
        condition_id="0xcond",
        outcome_index=0,
        outcome_name="Yes",
        market_slug="market-slug",
        question="Question?",
        category="",
        subcategory="",
        category_source="none",
        subcategory_source="none",
        event_slug="event-slug",
        end_date_iso=datetime(2026, 2, 19, 0, 0, 0),
        active=True,
        enable_order_book=True,
        accepting_orders=True,
        raw_json={"token_id": "tok-1"},
    )
    columns = api_main._market_tokens_insert_columns(
        {
            "token_id",
            "condition_id",
            "outcome_index",
            "outcome_name",
            "market_slug",
            "question",
            "category",
            "subcategory",
            "category_source",
            "subcategory_source",
            "event_slug",
            "end_date_iso",
            "active",
            "enable_order_book",
            "accepting_orders",
            "raw_json",
            "ingested_at",
        }
    )
    rows = api_main._build_market_token_insert_rows(
        [token],
        {
            "tok-1": {
                "category": "Politics",
                "subcategory": "Elections",
                "category_source": "event",
                "subcategory_source": "event",
            }
        },
        columns,
    )
    row = rows[0]
    assert row[columns.index("category")] == "Politics"
    assert row[columns.index("subcategory")] == "Elections"
    assert row[columns.index("category_source")] == "event"
    assert row[columns.index("subcategory_source")] == "event"
