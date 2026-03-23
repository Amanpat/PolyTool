"""Discover crypto pair markets (BTC/ETH/SOL 5m/15m) from Gamma API.

Each binary market has two CLOB tokens: YES and NO.  If you can buy both
for a combined cost below $1.00, one leg must resolve at $1.00 at settlement.
This module identifies the eligible markets and resolves both token IDs so
the opportunity scanner can fetch live order-book prices.

DRY-RUN ONLY — no orders are placed here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

# ---------------------------------------------------------------------------
# Keyword patterns for market classification
# ---------------------------------------------------------------------------

_SYMBOL_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bbtc\b|\bbitcoin\b", re.IGNORECASE), "BTC"),
    (re.compile(r"\beth\b|\bethereum\b|\bether\b", re.IGNORECASE), "ETH"),
    (re.compile(r"\bsol\b|\bsolana\b", re.IGNORECASE), "SOL"),
]

_DURATION_PATTERNS: list[tuple[re.Pattern, int]] = [
    (re.compile(r"\b5[\s\-]?min(ute)?s?\b|\b5m\b", re.IGNORECASE), 5),
    (re.compile(r"\b15[\s\-]?min(ute)?s?\b|\b15m\b", re.IGNORECASE), 15),
]

# Outcome name keywords used to identify the YES and NO legs of a binary market
_YES_OUTCOMES: frozenset[str] = frozenset({"yes", "y", "true", "up", "higher", "above"})
_NO_OUTCOMES: frozenset[str] = frozenset({"no", "n", "false", "down", "lower", "below"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CryptoPairMarket:
    """A discovered binary market with both YES and NO token IDs resolved."""

    slug: str
    condition_id: str
    question: str
    symbol: str           # BTC | ETH | SOL
    duration_min: int     # 5 | 15
    yes_token_id: str
    no_token_id: str
    end_date_iso: Optional[str] = None
    active: bool = True
    accepting_orders: Optional[bool] = None


# ---------------------------------------------------------------------------
# Detection helpers (public for unit testing)
# ---------------------------------------------------------------------------

def _detect_symbol(text: str) -> Optional[str]:
    """Return canonical symbol (BTC/ETH/SOL) if found in *text*, else None."""
    for pattern, symbol in _SYMBOL_PATTERNS:
        if pattern.search(text):
            return symbol
    return None


def _detect_duration(text: str) -> Optional[int]:
    """Return duration in minutes (5 or 15) if found in *text*, else None."""
    for pattern, minutes in _DURATION_PATTERNS:
        if pattern.search(text):
            return minutes
    return None


def _resolve_yes_no_tokens(
    clob_token_ids: list[str],
    outcomes: list[str],
) -> tuple[Optional[str], Optional[str]]:
    """Return (yes_token_id, no_token_id) for a binary market.

    Tries to match outcome names to known YES/NO keywords first; falls back
    to the Polymarket convention that index 0 is YES and index 1 is NO.

    Returns (None, None) when fewer than 2 token IDs are present.
    """
    if len(clob_token_ids) < 2:
        return None, None

    yes_idx: Optional[int] = None
    no_idx: Optional[int] = None

    for i, outcome in enumerate(outcomes):
        lower = outcome.strip().lower()
        if lower in _YES_OUTCOMES:
            yes_idx = i
        elif lower in _NO_OUTCOMES:
            no_idx = i

    if yes_idx is not None and no_idx is not None:
        yes_token = clob_token_ids[yes_idx] if yes_idx < len(clob_token_ids) else None
        no_token = clob_token_ids[no_idx] if no_idx < len(clob_token_ids) else None
        return yes_token, no_token

    # Fallback: index 0 = YES, index 1 = NO (Polymarket convention)
    return clob_token_ids[0], clob_token_ids[1]


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

def discover_crypto_pair_markets(
    gamma_client=None,
    max_pages: int = 5,
    page_size: int = 100,
) -> list[CryptoPairMarket]:
    """Discover active BTC/ETH/SOL 5m/15m binary markets from Gamma API.

    Args:
        gamma_client: ``GammaClient`` instance; creates a default one if None.
        max_pages: Maximum pagination pages to fetch (limits network usage).
        page_size: Markets per page.

    Returns:
        List of :class:`CryptoPairMarket` with YES/NO token IDs resolved,
        filtered to markets that are active, accepting orders, and have
        exactly two CLOB tokens.
    """
    if gamma_client is None:
        from packages.polymarket.gamma import GammaClient
        gamma_client = GammaClient()

    result = gamma_client.fetch_all_markets(
        max_pages=max_pages,
        page_size=page_size,
        active_only=True,
    )

    pairs: list[CryptoPairMarket] = []

    for market in result.markets:
        # Binary market: must have exactly two CLOB token IDs
        if len(market.clob_token_ids) != 2:
            continue

        # Must be active and not explicitly rejecting orders
        if not market.active:
            continue
        if market.accepting_orders is False:
            continue

        # Combine question and slug for keyword matching
        search_text = f"{market.question} {market.market_slug}"

        symbol = _detect_symbol(search_text)
        if symbol is None:
            continue

        duration = _detect_duration(search_text)
        if duration is None:
            continue

        yes_token_id, no_token_id = _resolve_yes_no_tokens(
            market.clob_token_ids, market.outcomes
        )
        if not yes_token_id or not no_token_id:
            continue

        end_date: Optional[str] = None
        if market.end_date_iso is not None:
            if isinstance(market.end_date_iso, datetime):
                end_date = market.end_date_iso.isoformat()
            else:
                end_date = str(market.end_date_iso)

        pairs.append(
            CryptoPairMarket(
                slug=market.market_slug,
                condition_id=market.condition_id,
                question=market.question,
                symbol=symbol,
                duration_min=duration,
                yes_token_id=yes_token_id,
                no_token_id=no_token_id,
                end_date_iso=end_date,
                active=market.active,
                accepting_orders=market.accepting_orders,
            )
        )

    return pairs
