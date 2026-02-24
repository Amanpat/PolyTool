"""Market picker: resolve slugs to YES/NO token IDs and validate orderbooks.

Used by the ``quickrun`` CLI subcommand to auto-select a live binary market
or validate a user-supplied slug before recording + running.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Outcome name sets used to identify YES/NO legs of a binary market.
_YES_NAMES: frozenset[str] = frozenset({"yes", "y", "true", "1"})
_NO_NAMES: frozenset[str] = frozenset({"no", "n", "false", "0"})


class MarketPickerError(ValueError):
    """Raised when market resolution or validation fails."""


@dataclass
class ResolvedMarket:
    """A binary market with identified YES and NO token IDs."""

    slug: str
    yes_token_id: str
    no_token_id: str
    yes_label: str
    no_label: str
    question: str


@dataclass
class BookValidation:
    """Result of validating a token's orderbook."""

    token_id: str
    valid: bool
    # "ok" | "error_response" | "empty_book" | "fetch_failed"
    reason: str
    best_bid: Optional[float]
    best_ask: Optional[float]


class MarketPicker:
    """Resolve market slugs and validate orderbooks.

    Args:
        gamma_client: GammaClient instance for market metadata.
        clob_client:  ClobClient instance for orderbook queries.
    """

    def __init__(self, gamma_client, clob_client) -> None:
        self._gamma = gamma_client
        self._clob = clob_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def resolve_slug(self, slug: str) -> ResolvedMarket:
        """Resolve a market slug to a ResolvedMarket with YES/NO token IDs.

        Args:
            slug: Polymarket market slug (e.g. ``"will-x-happen-by-date"``).

        Returns:
            ResolvedMarket with identified token IDs.

        Raises:
            MarketPickerError: If the slug can't be fetched, the market is not
                binary, or YES/NO cannot be identified from the outcome names.
        """
        markets = self._gamma.fetch_markets_filtered(slugs=[slug])
        if not markets:
            raise MarketPickerError(f"no markets returned for slug: {slug!r}")

        market = markets[0]

        if len(market.clob_token_ids) != 2 or len(market.outcomes) != 2:
            raise MarketPickerError(
                f"market {slug!r} is not binary: "
                f"clob_token_ids={market.clob_token_ids}, "
                f"outcomes={market.outcomes}"
            )

        outcome_a, outcome_b = market.outcomes
        token_a, token_b = market.clob_token_ids

        yes_idx = self._identify_yes_index(
            [outcome_a, outcome_b], slug=slug
        )

        if yes_idx == 0:
            yes_token, no_token = token_a, token_b
            yes_label, no_label = outcome_a, outcome_b
        else:
            yes_token, no_token = token_b, token_a
            yes_label, no_label = outcome_b, outcome_a

        return ResolvedMarket(
            slug=market.market_slug,
            yes_token_id=yes_token,
            no_token_id=no_token,
            yes_label=yes_label,
            no_label=no_label,
            question=market.question,
        )

    def validate_book(
        self,
        token_id: str,
        allow_empty: bool = False,
    ) -> BookValidation:
        """Validate that a token has a live, non-empty orderbook.

        Args:
            token_id:    Token / asset ID to check.
            allow_empty: If True, accept an empty book (bids=[], asks=[]).

        Returns:
            BookValidation describing whether the book is usable.
        """
        try:
            book = self._clob.fetch_book(token_id)
        except Exception as exc:  # noqa: BLE001
            logger.debug("fetch_book(%s) raised: %s", token_id, exc)
            return BookValidation(
                token_id=token_id,
                valid=False,
                reason="fetch_failed",
                best_bid=None,
                best_ask=None,
            )

        if not isinstance(book, dict):
            return BookValidation(
                token_id=token_id,
                valid=False,
                reason="fetch_failed",
                best_bid=None,
                best_ask=None,
            )

        if "error" in book:
            return BookValidation(
                token_id=token_id,
                valid=False,
                reason="error_response",
                best_bid=None,
                best_ask=None,
            )

        bids = book.get("bids") or []
        asks = book.get("asks") or []

        if not bids and not asks and not allow_empty:
            return BookValidation(
                token_id=token_id,
                valid=False,
                reason="empty_book",
                best_bid=None,
                best_ask=None,
            )

        best_bid = self._best_bid_from_levels(bids)
        best_ask = self._best_ask_from_levels(asks)

        return BookValidation(
            token_id=token_id,
            valid=True,
            reason="ok",
            best_bid=best_bid,
            best_ask=best_ask,
        )

    def auto_pick(
        self,
        max_candidates: int = 20,
        allow_empty_book: bool = False,
    ) -> ResolvedMarket:
        """Auto-select the first valid binary market from active markets.

        Fetches up to ``max_candidates`` active markets, tries to resolve
        each as binary, and validates both orderbooks.

        Args:
            max_candidates:  Number of markets to examine before giving up.
            allow_empty_book: If True, accept markets with empty orderbooks.

        Returns:
            First ResolvedMarket that passes all checks.

        Raises:
            MarketPickerError: If no valid candidate is found.
        """
        raw_markets = self._gamma.fetch_markets_page(
            limit=max_candidates,
            active_only=True,
        )

        for raw in raw_markets:
            if not isinstance(raw, dict):
                continue

            # Quick structural check before a full fetch
            token_ids = raw.get("clobTokenIds") or raw.get("clob_token_ids") or []
            if isinstance(token_ids, str):
                import json as _json
                try:
                    token_ids = _json.loads(token_ids)
                except Exception:  # noqa: BLE001
                    token_ids = []
            outcomes = raw.get("outcomes") or []
            if isinstance(outcomes, str):
                import json as _json
                try:
                    outcomes = _json.loads(outcomes)
                except Exception:  # noqa: BLE001
                    outcomes = []

            if len(token_ids) != 2 or len(outcomes) != 2:
                continue

            slug = raw.get("slug") or raw.get("market_slug") or ""
            if not slug:
                continue

            # Full resolve (fetches from Gamma filtered by slug)
            try:
                resolved = self.resolve_slug(slug)
            except MarketPickerError as exc:
                logger.debug("resolve_slug(%r) failed: %s", slug, exc)
                continue

            # Validate both books
            yes_val = self.validate_book(
                resolved.yes_token_id,
                allow_empty=allow_empty_book,
            )
            if not yes_val.valid:
                logger.debug(
                    "YES book invalid for %r (%s): %s",
                    slug,
                    resolved.yes_token_id[:8],
                    yes_val.reason,
                )
                continue

            no_val = self.validate_book(
                resolved.no_token_id,
                allow_empty=allow_empty_book,
            )
            if not no_val.valid:
                logger.debug(
                    "NO book invalid for %r (%s): %s",
                    slug,
                    resolved.no_token_id[:8],
                    no_val.reason,
                )
                continue

            return resolved

        raise MarketPickerError(
            f"no valid binary market found in first {max_candidates} candidates"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_yes_index(outcomes: list[str], *, slug: str) -> int:
        """Return the index (0 or 1) of the YES outcome.

        Raises:
            MarketPickerError: If outcomes are ambiguous or unrecognised.
        """
        lower = [o.strip().lower() for o in outcomes]

        # Both known → assign definitively
        both_known = all(o in _YES_NAMES or o in _NO_NAMES for o in lower)
        if both_known:
            if lower[0] in _YES_NAMES:
                return 0
            if lower[1] in _YES_NAMES:
                return 1

        # Exactly one is known YES
        yes_hits = [i for i, o in enumerate(lower) if o in _YES_NAMES]
        if len(yes_hits) == 1:
            return yes_hits[0]

        raise MarketPickerError(
            f"cannot identify YES/NO from outcomes {outcomes!r} for market {slug!r}; "
            f"expected outcome names from {sorted(_YES_NAMES)} / {sorted(_NO_NAMES)}"
        )

    @staticmethod
    def _best_bid_from_levels(levels: list) -> Optional[float]:
        """Extract best (highest) bid price from a list of price levels."""
        prices: list[float] = []
        for lvl in levels:
            p = _extract_level_price(lvl)
            if p is not None:
                prices.append(p)
        return max(prices) if prices else None

    @staticmethod
    def _best_ask_from_levels(levels: list) -> Optional[float]:
        """Extract best (lowest) ask price from a list of price levels."""
        prices: list[float] = []
        for lvl in levels:
            p = _extract_level_price(lvl)
            if p is not None:
                prices.append(p)
        return min(prices) if prices else None


def _extract_level_price(level: object) -> Optional[float]:
    """Extract price from a CLOB book level (dict or list)."""
    if isinstance(level, dict):
        raw = level.get("price") or level.get("p")
    elif isinstance(level, (list, tuple)) and level:
        raw = level[0]
    else:
        return None

    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
