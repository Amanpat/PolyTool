"""Target resolver for simtrader shadow: accepts any Polymarket URL or slug.

Handles four input forms:
  1. Direct market slug:  ``will-btc-hit-100k``
  2. Market URL:          ``https://polymarket.com/market/will-btc-hit-100k``
  3. Event slug:          ``btc-price-december-2025``
  4. Event URL:           ``https://polymarket.com/event/btc-price-december-2025``

Resolution logic:
  - Forms 1 and 2 resolve directly via MarketPicker.resolve_slug().
  - If a bare slug (form 1) fails with "no markets returned", it is retried as
    an event slug (falling through to form 3/4 logic).
  - Form 3/4: fetches child markets whose event_slug matches, ranks by liquidity
    then volume, and either auto-resolves (single usable child) or raises
    ChildMarketChoice (multiple usable children) for operator selection.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from packages.polymarket.simtrader.market_picker import (
    MarketPicker,
    MarketPickerError,
    ResolvedMarket,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TargetResolverError(ValueError):
    """Raised when target resolution fails completely.

    The message is operator-facing: it names the input form, states what was
    tried, and explains why it failed.
    """


class ChildMarketChoice(Exception):
    """Raised when an event URL yields multiple usable binary child markets.

    The operator must rerun with one of the listed ``--market`` slugs.

    Attributes:
        candidates: Ranked list of usable markets.  Each entry has keys:
            ``rank`` (int, 1-based), ``slug``, ``question``,
            ``liquidity`` (float), ``volume`` (float).
        skipped: List of child markets that were excluded.  Each entry has
            keys: ``slug``, ``question``, ``reason``.
    """

    def __init__(
        self,
        candidates: list[dict],
        skipped: list[dict],
        message: str = "",
    ) -> None:
        super().__init__(message or f"{len(candidates)} candidate markets found")
        self.candidates = candidates
        self.skipped = skipped


# ---------------------------------------------------------------------------
# URL / slug parsing
# ---------------------------------------------------------------------------


def _parse_target(raw: str) -> tuple[str, str]:
    """Parse *raw* into ``(slug, hint)``.

    hint is one of:
      - ``"market"``  — stripped from a ``/market/…`` URL path
      - ``"event"``   — stripped from an ``/event/…`` URL path
      - ``"unknown"`` — bare slug with no URL prefix

    Raises:
        TargetResolverError: For URLs that are not valid Polymarket market/event
            paths, or for non-polymarket.com domains.
    """
    stripped = raw.strip()
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        # Bare slug
        return stripped, "unknown"

    parsed = urlparse(stripped)
    host = parsed.netloc.lower().lstrip("www.")
    if "polymarket.com" not in host:
        raise TargetResolverError(
            f"Unrecognised URL domain {parsed.netloc!r}. "
            "Only polymarket.com URLs are supported. "
            "Pass a bare slug instead, e.g. 'will-x-happen-2026'."
        )

    path = parsed.path.rstrip("/")

    if path.startswith("/market/"):
        slug = path[len("/market/"):]
        if not slug:
            raise TargetResolverError(
                "URL has /market/ path but no slug after it: provide the full market URL."
            )
        return slug, "market"

    if path.startswith("/event/"):
        slug = path[len("/event/"):]
        if not slug:
            raise TargetResolverError(
                "URL has /event/ path but no slug after it: provide the full event URL."
            )
        return slug, "event"

    raise TargetResolverError(
        f"Unsupported polymarket.com path {path!r}. "
        "Only /market/ and /event/ paths are supported. "
        "Example: 'https://polymarket.com/market/will-x-happen-2026' "
        "or 'https://polymarket.com/event/some-event-name'."
    )


# ---------------------------------------------------------------------------
# Event child market helpers
# ---------------------------------------------------------------------------


def _fetch_event_child_markets(gamma_client, event_slug: str) -> list:
    """Fetch Market-like objects whose event_slug matches *event_slug*.

    GammaClient.fetch_markets_filtered does NOT accept an ``event_slug``
    kwarg (checked against actual source signature).  We therefore use the
    page-scan approach: call ``fetch_markets_page`` and filter by
    ``market.event_slug == event_slug or event_slug in market.event_slugs``.

    The raw dicts returned by fetch_markets_page are converted to lightweight
    _ChildMarket objects for downstream processing.
    """
    raw_pages = gamma_client.fetch_markets_page(limit=100, active_only=False)
    results = []
    for raw in raw_pages:
        if not isinstance(raw, dict):
            continue
        m_event_slug = (
            raw.get("eventSlug")
            or raw.get("event_slug")
            or ""
        )
        m_event_slugs_raw = raw.get("eventSlugs") or raw.get("event_slugs") or []
        if isinstance(m_event_slugs_raw, str):
            import json
            try:
                m_event_slugs_raw = json.loads(m_event_slugs_raw)
            except Exception:
                m_event_slugs_raw = []
        if not isinstance(m_event_slugs_raw, list):
            m_event_slugs_raw = []

        if m_event_slug == event_slug or event_slug in m_event_slugs_raw:
            results.append(_ChildMarket.from_raw(raw))
    return results


def _coalesce(d: dict, *keys: str):
    """Return the value of the first key present in *d* (even if the value is falsy).

    Unlike ``d.get(k1) or d.get(k2)``, this correctly returns ``False`` and
    ``0`` when the first matching key maps to those values.
    """
    sentinel = object()
    for key in keys:
        val = d.get(key, sentinel)
        if val is not sentinel:
            return val
    return None


class _ChildMarket:
    """Lightweight market-like object parsed from a raw Gamma dict."""

    __slots__ = (
        "market_slug",
        "question",
        "outcomes",
        "clob_token_ids",
        "active",
        "enable_order_book",
        "accepting_orders",
        "event_slug",
        "event_slugs",
        "liquidity",
        "volume",
    )

    def __init__(
        self,
        market_slug: str,
        question: str,
        outcomes: list,
        clob_token_ids: list,
        active: bool,
        enable_order_book,
        accepting_orders,
        event_slug: str,
        event_slugs: list,
        liquidity: float,
        volume: float,
    ) -> None:
        self.market_slug = market_slug
        self.question = question
        self.outcomes = outcomes
        self.clob_token_ids = clob_token_ids
        self.active = active
        self.enable_order_book = enable_order_book
        self.accepting_orders = accepting_orders
        self.event_slug = event_slug
        self.event_slugs = event_slugs
        self.liquidity = liquidity
        self.volume = volume

    @classmethod
    def from_raw(cls, raw: dict) -> "_ChildMarket":
        import json as _json

        def _parse_list(v):
            if v is None:
                return []
            if isinstance(v, str):
                try:
                    v = _json.loads(v)
                except Exception:
                    return []
            if isinstance(v, list):
                return [x for x in v if x not in ("", None)]
            return []

        def _parse_bool(v):
            if v is None:
                return None
            if isinstance(v, bool):
                return v
            if isinstance(v, (int, float)):
                return bool(v)
            if isinstance(v, str):
                if v.lower() in ("true", "1", "yes"):
                    return True
                if v.lower() in ("false", "0", "no"):
                    return False
            return None

        return cls(
            market_slug=str(raw.get("slug") or raw.get("market_slug") or ""),
            question=str(raw.get("question") or ""),
            outcomes=_parse_list(raw.get("outcomes")),
            clob_token_ids=_parse_list(
                raw.get("clobTokenIds") or raw.get("clob_token_ids")
            ),
            active=bool(raw.get("active", True)),
            enable_order_book=_parse_bool(
                _coalesce(raw, "enableOrderBook", "enable_order_book")
            ),
            accepting_orders=_parse_bool(
                _coalesce(raw, "acceptingOrders", "accepting_orders")
            ),
            event_slug=str(raw.get("eventSlug") or raw.get("event_slug") or ""),
            event_slugs=_parse_list(
                raw.get("eventSlugs") or raw.get("event_slugs")
            ),
            liquidity=float(raw.get("liquidity") or 0.0),
            volume=float(raw.get("volume") or 0.0),
        )


# ---------------------------------------------------------------------------
# Child market ranking
# ---------------------------------------------------------------------------


def _rank_children(markets: list) -> tuple[list, list[dict]]:
    """Partition markets into (usable, skipped).

    Usable criteria (checked in order; first failing check wins):
      - active == True          -> "closed"
      - accepting_orders != False -> "not_accepting_orders"
      - enable_order_book != False -> "orderbook_disabled"
      - exactly 2 outcomes and 2 clob_token_ids -> "not_binary (N outcomes)"
      - at least 1 clob_token_id -> "no_token_ids"

    Usable markets are sorted by liquidity desc, volume desc.

    Returns:
        (usable_markets, skipped_list) where skipped_list entries have keys
        ``slug``, ``question``, ``reason``.
    """
    usable = []
    skipped: list[dict] = []

    for m in markets:
        slug = getattr(m, "market_slug", "") or ""
        question = getattr(m, "question", "") or ""
        active = getattr(m, "active", True)
        accepting_orders = getattr(m, "accepting_orders", None)
        enable_order_book = getattr(m, "enable_order_book", None)
        outcomes = getattr(m, "outcomes", []) or []
        token_ids = getattr(m, "clob_token_ids", []) or []

        if not active:
            skipped.append({"slug": slug, "question": question, "reason": "closed"})
            continue
        if accepting_orders is False:
            skipped.append(
                {"slug": slug, "question": question, "reason": "not_accepting_orders"}
            )
            continue
        if enable_order_book is False:
            skipped.append(
                {"slug": slug, "question": question, "reason": "orderbook_disabled"}
            )
            continue
        if not token_ids:
            skipped.append(
                {"slug": slug, "question": question, "reason": "no_token_ids"}
            )
            continue
        if len(outcomes) != 2 or len(token_ids) != 2:
            n = len(outcomes)
            skipped.append(
                {
                    "slug": slug,
                    "question": question,
                    "reason": f"not_binary ({n} outcomes)",
                }
            )
            continue

        usable.append(m)

    usable.sort(
        key=lambda m: (getattr(m, "liquidity", 0.0), getattr(m, "volume", 0.0)),
        reverse=True,
    )

    return usable, skipped


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------


class TargetResolver:
    """Resolve any Polymarket slug or URL to a ResolvedMarket.

    Accepted input forms:
      1. Bare market slug:  ``will-btc-hit-100k``
      2. Market URL:        ``https://polymarket.com/market/will-btc-hit-100k``
      3. Event slug:        ``btc-price-december-2025``
      4. Event URL:         ``https://polymarket.com/event/btc-price-december-2025``
    """

    def __init__(self, gamma_client, clob_client) -> None:
        self._gamma = gamma_client
        self._clob = clob_client
        self._picker = MarketPicker(gamma_client, clob_client)

    def resolve_target(self, raw: str) -> ResolvedMarket:
        """Resolve *raw* to a ResolvedMarket.

        Raises:
            ChildMarketChoice: When an event has multiple usable binary children.
            TargetResolverError: When resolution fails completely.
        """
        slug, hint = _parse_target(raw)
        logger.debug("resolve_target: slug=%r hint=%r", slug, hint)

        # ------------------------------------------------------------------
        # Step 1 — try direct market lookup for market/unknown hints
        # ------------------------------------------------------------------
        if hint in ("market", "unknown"):
            try:
                resolved = self._picker.resolve_slug(slug)
                logger.debug("Resolved %r directly -> %r", slug, resolved.slug)
                return resolved
            except MarketPickerError as exc:
                msg = str(exc)
                if "no markets returned" in msg and hint == "unknown":
                    # Bare slug not found as a direct market; try as event slug
                    logger.debug(
                        "Direct market lookup failed for %r; retrying as event slug", slug
                    )
                    # fall through to step 2 below
                else:
                    # Not found (and was an explicit market URL) or other error
                    raise TargetResolverError(
                        f"Could not resolve market slug {slug!r} "
                        f"(input: {raw!r}): {exc}"
                    ) from exc

        # ------------------------------------------------------------------
        # Step 2 — event slug lookup (used for hint=="event" and unknown fallback)
        # ------------------------------------------------------------------
        children = _fetch_event_child_markets(self._gamma, slug)
        if not children:
            if hint == "unknown":
                raise TargetResolverError(
                    f"{raw!r} was not found as a direct market slug and also returned "
                    f"no child markets when looked up as an event slug. "
                    f"Check that the slug is correct and the market/event is active. "
                    f"Try: python -m polytool simtrader shadow --market <exact-slug>"
                )
            else:
                raise TargetResolverError(
                    f"Event slug {slug!r} returned no child markets. "
                    f"Check the slug is correct and the event is active."
                )

        usable, skipped = _rank_children(children)

        if not usable:
            skip_lines = "; ".join(
                f"{s['slug']}: {s['reason']}" for s in skipped
            )
            raise TargetResolverError(
                f"Event {slug!r} has child markets but none are usable for shadow trading. "
                f"Skipped: {skip_lines}"
            )

        if len(usable) == 1:
            child_slug = usable[0].market_slug
            logger.debug(
                "Event %r has single usable child %r; auto-resolving", slug, child_slug
            )
            try:
                return self._picker.resolve_slug(child_slug)
            except MarketPickerError as exc:
                raise TargetResolverError(
                    f"Event {slug!r} has one usable child market {child_slug!r} "
                    f"but it could not be fully resolved: {exc}"
                ) from exc

        # Multiple usable children — build ranked shortlist
        candidates = [
            {
                "rank": idx + 1,
                "slug": m.market_slug,
                "question": m.question,
                "liquidity": getattr(m, "liquidity", 0.0),
                "volume": getattr(m, "volume", 0.0),
            }
            for idx, m in enumerate(usable)
        ]

        raise ChildMarketChoice(candidates=candidates, skipped=skipped)
