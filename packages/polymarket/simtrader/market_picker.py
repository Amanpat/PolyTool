"""Market picker: resolve slugs to YES/NO token IDs and validate orderbooks.

Used by the ``quickrun`` and ``batch`` CLI subcommands to auto-select live
binary markets or validate user-supplied slugs before recording + running.

YES/NO mapping strategy (in priority order):
  1. Prefer outcomes whose lowercase form is in ``_YES_EXPLICIT`` / ``_NO_EXPLICIT``
     (e.g. "Yes", "Y", "No", "N").  One explicit YES match → return that index.
  2. Fall back to any recognised alias in ``_YES_NAMES`` / ``_NO_NAMES``
     (e.g. "True"/"False", "Up"/"Down", "1"/"0", "Long"/"Short", "Higher"/"Lower").
  3. If neither tier identifies exactly one YES, raise ``MarketPickerError`` with the
     raw outcome names and market slug so the caller can diagnose the problem.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YES / NO name sets (case-insensitive after .strip().lower())
# ---------------------------------------------------------------------------

# Tier-1 (explicit): preferred when present; wins over tier-2 aliases.
_YES_EXPLICIT: frozenset[str] = frozenset({"yes", "y"})
_NO_EXPLICIT: frozenset[str] = frozenset({"no", "n"})

# Tier-2 (aliases): accepted when no tier-1 match exists.
# Supported variants: True/False, Up/Down, 1/0, Long/Short, Higher/Lower.
_YES_ALIASES: frozenset[str] = frozenset({"true", "1", "up", "long", "higher"})
_NO_ALIASES: frozenset[str] = frozenset({"false", "0", "down", "short", "lower"})

# Combined sets used for validation and error messages.
_YES_NAMES: frozenset[str] = _YES_EXPLICIT | _YES_ALIASES
_NO_NAMES: frozenset[str] = _NO_EXPLICIT | _NO_ALIASES


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
    #: "explicit" if a tier-1 name was used; "alias" if a tier-2 name was used.
    mapping_tier: str = "explicit"


@dataclass
class BookValidation:
    """Result of validating a token's orderbook."""

    token_id: str
    valid: bool
    # "ok" | "error_response" | "empty_book" | "fetch_failed" | "shallow_book"
    reason: str
    best_bid: Optional[float]
    best_ask: Optional[float]
    #: Total size summed from the top ``top_n`` bid + ask levels (None if not computed).
    depth_total: Optional[float] = None


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

        yes_idx, mapping_tier = self._identify_yes_index(
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
            mapping_tier=mapping_tier,
        )

    def validate_book(
        self,
        token_id: str,
        allow_empty: bool = False,
        min_depth_size: float = 0.0,
        top_n_levels: int = 3,
    ) -> BookValidation:
        """Validate that a token has a live, non-empty orderbook.

        Args:
            token_id:       Token / asset ID to check.
            allow_empty:    If True, accept an empty book (bids=[], asks=[]).
            min_depth_size: Minimum total size required across the top
                            ``top_n_levels`` bid + ask levels.  0 disables the
                            check (default).
            top_n_levels:   Number of levels per side to sum for the depth check
                            (default: 3).

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

        # Depth filter (only when min_depth_size > 0 and book is non-empty)
        depth_total: Optional[float] = None
        if min_depth_size > 0 and (bids or asks):
            depth_total = self._compute_depth_total(bids, asks, top_n=top_n_levels)
            if depth_total < min_depth_size:
                return BookValidation(
                    token_id=token_id,
                    valid=False,
                    reason="shallow_book",
                    best_bid=best_bid,
                    best_ask=best_ask,
                    depth_total=depth_total,
                )

        return BookValidation(
            token_id=token_id,
            valid=True,
            reason="ok",
            best_bid=best_bid,
            best_ask=best_ask,
            depth_total=depth_total,
        )

    def auto_pick(
        self,
        max_candidates: int = 20,
        allow_empty_book: bool = False,
        min_depth_size: float = 0.0,
        top_n_levels: int = 3,
        collect_skips: Optional[list] = None,
    ) -> ResolvedMarket:
        """Auto-select the first valid binary market from active markets.

        Fetches up to ``max_candidates`` active markets, tries to resolve
        each as binary, and validates both orderbooks.

        Args:
            max_candidates:  Number of markets to examine before giving up.
            allow_empty_book: If True, accept markets with empty orderbooks.
            min_depth_size:  Minimum total size in top ``top_n_levels`` levels.
            top_n_levels:    Levels per side for depth check (default: 3).
            collect_skips:   If not None, append skip-reason dicts here so the
                             caller can report them (useful for ``--dry-run``).

        Returns:
            First ResolvedMarket that passes all checks.

        Raises:
            MarketPickerError: If no valid candidate is found.
        """
        results = self.auto_pick_many(
            n=1,
            max_candidates=max_candidates,
            allow_empty_book=allow_empty_book,
            min_depth_size=min_depth_size,
            top_n_levels=top_n_levels,
            collect_skips=collect_skips,
        )
        if not results:
            raise MarketPickerError(
                f"no valid binary market found in first {max_candidates} candidates"
            )
        return results[0]

    def auto_pick_many(
        self,
        n: int,
        max_candidates: int = 100,
        allow_empty_book: bool = False,
        min_depth_size: float = 0.0,
        top_n_levels: int = 3,
        collect_skips: Optional[list] = None,
        exclude_slugs: Optional[set] = None,
    ) -> list[ResolvedMarket]:
        """Pick up to ``n`` distinct valid binary markets.

        Args:
            n:               Maximum number of markets to return.
            max_candidates:  Candidate pool size to fetch from Gamma.
            allow_empty_book: Accept markets with empty orderbooks.
            min_depth_size:  Minimum total depth across top levels.
            top_n_levels:    Levels per side for depth check.
            collect_skips:   If not None, append skip-reason dicts here.
            exclude_slugs:   Slugs to skip (for idempotency in batch runs).

        Returns:
            List of up to ``n`` ResolvedMarket instances (may be fewer if not
            enough valid markets exist in the candidate pool).
        """
        raw_markets = self._gamma.fetch_markets_page(
            limit=max_candidates,
            active_only=True,
        )

        results: list[ResolvedMarket] = []
        seen_slugs: set[str] = set(exclude_slugs or [])

        for raw in raw_markets:
            if len(results) >= n:
                break

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

            if slug in seen_slugs:
                continue

            # Full resolve (fetches from Gamma filtered by slug)
            try:
                resolved = self.resolve_slug(slug)
            except MarketPickerError as exc:
                logger.debug("resolve_slug(%r) failed: %s", slug, exc)
                if collect_skips is not None:
                    collect_skips.append(
                        {"slug": slug, "reason": "resolve_failed", "detail": str(exc)}
                    )
                continue

            # Validate both books
            yes_val = self.validate_book(
                resolved.yes_token_id,
                allow_empty=allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
            )
            if not yes_val.valid:
                logger.debug(
                    "YES book invalid for %r (%s): %s",
                    slug,
                    resolved.yes_token_id[:8],
                    yes_val.reason,
                )
                if collect_skips is not None:
                    collect_skips.append(
                        {
                            "slug": slug,
                            "reason": yes_val.reason,
                            "side": "YES",
                            "token_id": resolved.yes_token_id[:8],
                            "depth_total": yes_val.depth_total,
                        }
                    )
                continue

            no_val = self.validate_book(
                resolved.no_token_id,
                allow_empty=allow_empty_book,
                min_depth_size=min_depth_size,
                top_n_levels=top_n_levels,
            )
            if not no_val.valid:
                logger.debug(
                    "NO book invalid for %r (%s): %s",
                    slug,
                    resolved.no_token_id[:8],
                    no_val.reason,
                )
                if collect_skips is not None:
                    collect_skips.append(
                        {
                            "slug": slug,
                            "reason": no_val.reason,
                            "side": "NO",
                            "token_id": resolved.no_token_id[:8],
                            "depth_total": no_val.depth_total,
                        }
                    )
                continue

            seen_slugs.add(slug)
            results.append(resolved)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _identify_yes_index(outcomes: list[str], *, slug: str) -> tuple[int, str]:
        """Return ``(index, mapping_tier)`` for the YES outcome.

        mapping_tier is ``"explicit"`` when a tier-1 name matched, ``"alias"``
        otherwise.

        Raises:
            MarketPickerError: If outcomes are ambiguous or unrecognised.
        """
        lower = [o.strip().lower() for o in outcomes]

        # Tier 1: explicit "yes"/"y" names (highest priority)
        yes_explicit = [i for i, o in enumerate(lower) if o in _YES_EXPLICIT]
        if len(yes_explicit) == 1:
            return yes_explicit[0], "explicit"

        # Tier 2: any recognised YES alias (true, 1, up, long, higher, …)
        yes_any = [i for i, o in enumerate(lower) if o in _YES_NAMES]
        if len(yes_any) == 1:
            return yes_any[0], "alias"

        raise MarketPickerError(
            f"cannot identify YES/NO from outcomes {outcomes!r} for market {slug!r}; "
            f"expected outcome names like "
            f"{sorted(_YES_EXPLICIT)} / {sorted(_NO_EXPLICIT)} "
            f"or aliases {sorted(_YES_ALIASES)} / {sorted(_NO_ALIASES)}"
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

    @staticmethod
    def _compute_depth_total(bids: list, asks: list, top_n: int) -> float:
        """Sum sizes from the top ``top_n`` bid levels and top ``top_n`` ask levels.

        Bids are sorted descending by price (best bid first); asks ascending
        (best ask first).  The ``top_n`` deepest levels per side are summed.
        """

        def _price(lvl: object) -> float:
            if isinstance(lvl, dict):
                raw = lvl.get("price") or lvl.get("p") or 0
            elif isinstance(lvl, (list, tuple)) and lvl:
                raw = lvl[0]
            else:
                return 0.0
            try:
                return float(raw)
            except (TypeError, ValueError):
                return 0.0

        def _size(lvl: object) -> float:
            if isinstance(lvl, dict):
                raw = lvl.get("size") or lvl.get("s") or 0
            elif isinstance(lvl, (list, tuple)) and len(lvl) >= 2:
                raw = lvl[1]
            else:
                return 0.0
            try:
                return float(raw)
            except (TypeError, ValueError):
                return 0.0

        top_bids = sorted(bids, key=_price, reverse=True)[:top_n]
        top_asks = sorted(asks, key=_price)[:top_n]
        return sum(_size(lvl) for lvl in top_bids + top_asks)


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
