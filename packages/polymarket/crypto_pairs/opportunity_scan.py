"""Compute and rank pair opportunities for discovered crypto markets.

Strategy: if YES_ask + NO_ask < $1.00, buying both legs guarantees at least
one $1.00 settlement, yielding a gross positive edge equal to
$1.00 - paired_cost.

All computation is DRY-RUN — no orders are submitted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .market_discovery import CryptoPairMarket

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAIR_COST_THRESHOLD: float = 1.00  # Settlement value of the winning leg
MAKER_REBATE_BPS: int = 20         # 20 bps rebate assumption for crypto markets

# Qualitative assumption flags attached to every opportunity record so the
# operator always has context when reading the artifact bundle.
_STATIC_ASSUMPTIONS: list[str] = [
    "maker_rebate_20bps",       # Maker orders earn 20 bps rebate on crypto markets
    "no_slippage",              # Fills assumed at best ask; real fills may be worse
    "fills_not_guaranteed",     # Maker orders may not fill before market resolves
    "rapid_resolution",         # 5m/15m markets resolve quickly; edge window is narrow
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PairOpportunity:
    """Scored opportunity for one binary market (YES + NO legs)."""

    slug: str
    symbol: str
    duration_min: int
    question: str
    condition_id: str
    yes_token_id: str
    no_token_id: str

    # Live order-book snapshot
    yes_ask: Optional[float] = None
    no_ask: Optional[float] = None

    # Derived metrics
    paired_cost: Optional[float] = None
    gross_edge: Optional[float] = None   # positive → arbitrage edge present

    has_opportunity: bool = False
    book_status: str = "ok"   # ok | missing_yes | missing_no | fetch_error

    assumptions: list[str] = field(
        default_factory=lambda: list(_STATIC_ASSUMPTIONS)
    )


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_pair_opportunity(
    market: CryptoPairMarket,
    clob_client=None,
) -> PairOpportunity:
    """Fetch live best-ask prices for YES and NO, then compute pair metrics.

    Args:
        market: Discovered market with both token IDs.
        clob_client: ``ClobClient`` instance; creates a default one if None.

    Returns:
        :class:`PairOpportunity` with ``has_opportunity=True`` when
        ``YES_ask + NO_ask < 1.00``.
    """
    opp = PairOpportunity(
        slug=market.slug,
        symbol=market.symbol,
        duration_min=market.duration_min,
        question=market.question,
        condition_id=market.condition_id,
        yes_token_id=market.yes_token_id,
        no_token_id=market.no_token_id,
    )

    if clob_client is None:
        from packages.polymarket.clob import ClobClient
        clob_client = ClobClient()

    yes_top = clob_client.get_best_bid_ask(market.yes_token_id)
    no_top = clob_client.get_best_bid_ask(market.no_token_id)

    if yes_top is None or yes_top.best_ask is None:
        opp.book_status = "missing_yes"
        return opp

    if no_top is None or no_top.best_ask is None:
        opp.book_status = "missing_no"
        return opp

    opp.yes_ask = yes_top.best_ask
    opp.no_ask = no_top.best_ask
    opp.paired_cost = round(opp.yes_ask + opp.no_ask, 6)
    opp.gross_edge = round(PAIR_COST_THRESHOLD - opp.paired_cost, 6)
    opp.has_opportunity = opp.gross_edge > 0.0

    return opp


def scan_opportunities(
    pair_markets: list[CryptoPairMarket],
    clob_client=None,
) -> list[PairOpportunity]:
    """Compute pair opportunities for all discovered markets.

    Args:
        pair_markets: Markets to evaluate (from :func:`discover_crypto_pair_markets`).
        clob_client: Shared ``ClobClient`` instance (created once if None).

    Returns:
        One :class:`PairOpportunity` per input market, in input order.
    """
    if clob_client is None:
        from packages.polymarket.clob import ClobClient
        clob_client = ClobClient()

    return [
        compute_pair_opportunity(m, clob_client=clob_client)
        for m in pair_markets
    ]


def rank_opportunities(opportunities: list[PairOpportunity]) -> list[PairOpportunity]:
    """Rank opportunities deterministically.

    Sort order:
    1. Markets WITH a positive gross edge come first.
    2. Within each group, higher gross edge first.
    3. Slug as stable tie-breaker (alphabetical ascending).
    """
    return sorted(
        opportunities,
        key=lambda o: (
            0 if o.has_opportunity else 1,   # opportunities first
            -(o.gross_edge or 0.0),          # higher edge first
            o.slug,                          # stable tie-break
        ),
    )
