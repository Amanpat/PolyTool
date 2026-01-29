"""Gamma API client for Polymarket user resolution and market metadata."""

import json
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from .http_client import HttpClient
from .normalization import normalize_condition_id

logger = logging.getLogger(__name__)

# Default Gamma API base URL
DEFAULT_GAMMA_API_BASE = "https://gamma-api.polymarket.com"


@dataclass
class MarketToken:
    """Mapping of token_id to market/outcome metadata."""

    token_id: str
    condition_id: str
    outcome_index: int
    outcome_name: str
    market_slug: str
    question: str
    category: str
    event_slug: str
    end_date_iso: Optional[datetime]
    active: bool
    enable_order_book: Optional[bool]
    accepting_orders: Optional[bool]
    raw_json: dict


@dataclass
class TokenAlias:
    """Mapping of alias token ids to canonical clob token ids."""

    alias_token_id: str
    canonical_clob_token_id: str
    condition_id: str
    outcome_index: int
    outcome_name: str
    market_slug: str
    raw_json: dict


@dataclass
class Market:
    """Full market metadata from Gamma API."""

    condition_id: str
    market_slug: str
    question: str
    description: str
    category: str
    tags: list[str]
    event_slug: str
    event_title: str
    outcomes: list[str]
    clob_token_ids: list[str]
    alias_token_ids: list[str]
    enable_order_book: Optional[bool]
    accepting_orders: Optional[bool]
    start_date_iso: Optional[datetime]
    end_date_iso: Optional[datetime]
    close_date_iso: Optional[datetime]
    active: bool
    liquidity: float
    volume: float
    raw_json: dict

    def to_market_tokens(self) -> list[MarketToken]:
        """Extract MarketToken entries from this market."""
        tokens = []
        for idx, token_id in enumerate(self.clob_token_ids):
            outcome_name = self.outcomes[idx] if idx < len(self.outcomes) else f"Outcome {idx}"
            tokens.append(MarketToken(
                token_id=token_id,
                condition_id=self.condition_id,
                outcome_index=idx,
                outcome_name=outcome_name,
                market_slug=self.market_slug,
                question=self.question,
                category=self.category,
                event_slug=self.event_slug,
                end_date_iso=self.end_date_iso,
                active=self.active,
                enable_order_book=self.enable_order_book,
                accepting_orders=self.accepting_orders,
                raw_json=self.raw_json,
            ))
        return tokens

    def to_token_aliases(self) -> list[TokenAlias]:
        """Extract TokenAlias entries when alias ids are present."""
        aliases: list[TokenAlias] = []
        if not self.alias_token_ids:
            return aliases

        for idx, alias_id in enumerate(self.alias_token_ids):
            if not alias_id:
                continue
            canonical_id = self.clob_token_ids[idx] if idx < len(self.clob_token_ids) else ""
            if not canonical_id or alias_id == canonical_id:
                continue
            outcome_name = self.outcomes[idx] if idx < len(self.outcomes) else f"Outcome {idx}"
            aliases.append(TokenAlias(
                alias_token_id=str(alias_id),
                canonical_clob_token_id=str(canonical_id),
                condition_id=self.condition_id,
                outcome_index=idx,
                outcome_name=outcome_name,
                market_slug=self.market_slug,
                raw_json=self.raw_json,
            ))
        return aliases


@dataclass
class MarketsFetchResult:
    """Result of fetching markets from Gamma API."""

    markets: list[Market]
    market_tokens: list[MarketToken]
    token_aliases: list[TokenAlias]
    pages_fetched: int
    total_markets: int


@dataclass
class UserProfile:
    """Resolved Polymarket user profile."""

    proxy_wallet: str
    username: str
    raw_json: dict

    @property
    def display_name(self) -> str:
        """Get display name (username or truncated wallet)."""
        if self.username:
            return f"@{self.username}"
        return f"{self.proxy_wallet[:8]}..."


class GammaClient:
    """Client for Gamma API (Polymarket user data)."""

    def __init__(
        self,
        base_url: str = DEFAULT_GAMMA_API_BASE,
        timeout: float = 20.0,
    ):
        """
        Initialize Gamma API client.

        Args:
            base_url: Gamma API base URL
            timeout: Request timeout in seconds
        """
        self.client = HttpClient(base_url=base_url, timeout=timeout)

    def search_user(self, query: str) -> Optional[UserProfile]:
        """
        Search for a user by username.

        Uses GET /public-search?q=<query>&search_profiles=true

        Args:
            query: Username to search for (with or without @ prefix)

        Returns:
            UserProfile if found, None otherwise
        """
        # Strip @ prefix if present
        search_query = query.lstrip("@")

        logger.info(f"Searching for user: {search_query}")

        try:
            response = self.client.get_json(
                "/public-search",
                params={"q": search_query, "search_profiles": "true"},
            )
        except Exception as e:
            logger.error(f"Error searching for user '{search_query}': {e}")
            return None

        # Response structure: { "profiles": [...], ... }
        profiles = response.get("profiles", [])

        if not profiles:
            logger.warning(f"No profiles found for query: {search_query}")
            return None

        # Find exact match first, then fall back to first result
        best_match = None
        for profile in profiles:
            username = profile.get("username", "")
            if username.lower() == search_query.lower():
                best_match = profile
                break

        if best_match is None:
            best_match = profiles[0]
            logger.info(
                f"No exact match for '{search_query}', "
                f"using first result: {best_match.get('username', 'unknown')}"
            )

        # Extract proxy wallet - check multiple possible field names
        proxy_wallet = (
            best_match.get("proxyWallet")
            or best_match.get("proxy_wallet")
            or best_match.get("address")
            or ""
        )

        if not proxy_wallet:
            logger.error(f"No proxy wallet found in profile: {best_match}")
            return None

        return UserProfile(
            proxy_wallet=proxy_wallet,
            username=best_match.get("username", ""),
            raw_json=best_match,
        )

    def resolve(self, input_value: str) -> Optional[UserProfile]:
        """
        Resolve a username or wallet address to a UserProfile.

        Args:
            input_value: Username (with or without @) or wallet address (0x...)

        Returns:
            UserProfile if resolved, None otherwise
        """
        # If input looks like a wallet address, create minimal profile
        if input_value.startswith("0x") and len(input_value) >= 40:
            logger.info(f"Input appears to be wallet address: {input_value}")
            # Try to look up the profile anyway to get username
            # Search by wallet address
            try:
                response = self.client.get_json(
                    "/public-search",
                    params={"q": input_value, "search_profiles": "true"},
                )
                profiles = response.get("profiles", [])

                # Look for exact wallet match
                for profile in profiles:
                    wallet = (
                        profile.get("proxyWallet")
                        or profile.get("proxy_wallet")
                        or profile.get("address")
                        or ""
                    )
                    if wallet.lower() == input_value.lower():
                        return UserProfile(
                            proxy_wallet=wallet,
                            username=profile.get("username", ""),
                            raw_json=profile,
                        )

                # No profile found, return minimal profile with just wallet
                return UserProfile(
                    proxy_wallet=input_value,
                    username="",
                    raw_json={"proxyWallet": input_value},
                )
            except Exception as e:
                logger.warning(f"Could not lookup wallet {input_value}: {e}")
                return UserProfile(
                    proxy_wallet=input_value,
                    username="",
                    raw_json={"proxyWallet": input_value},
                )

        # Otherwise, search by username
        return self.search_user(input_value)

    def fetch_markets_page(
        self,
        limit: int = 100,
        offset: int = 0,
        active_only: bool = True,
    ) -> list[dict]:
        """
        Fetch a single page of markets.

        GET /markets?limit=N&offset=M&closed=false

        Args:
            limit: Number of markets per page (max 100)
            offset: Offset for pagination
            active_only: Only fetch non-closed markets

        Returns:
            List of raw market dictionaries
        """
        params = {"limit": limit, "offset": offset}
        if active_only:
            params["closed"] = "false"

        try:
            response = self.client.get_json("/markets", params=params)
        except Exception as e:
            logger.error(f"Error fetching markets page: {e}")
            return []

        # Response can be a list directly or wrapped in an object
        if isinstance(response, list):
            return response
        elif isinstance(response, dict):
            return response.get("data", response.get("markets", []))
        return []

    def fetch_markets_filtered(
        self,
        condition_ids: Optional[list[str]] = None,
        clob_token_ids: Optional[list[str]] = None,
        slugs: Optional[list[str]] = None,
        closed: Optional[bool] = None,
        limit: int = 100,
    ) -> list[Market]:
        """
        Fetch markets using filter parameters for targeted backfill.

        Supports condition_ids, clob_token_ids, slug, and closed filters.
        """
        params: dict[str, object] = {}
        if condition_ids:
            params["condition_ids"] = condition_ids
        if clob_token_ids:
            params["clob_token_ids"] = clob_token_ids
        if slugs:
            params["slug"] = slugs
        if closed is not None:
            params["closed"] = "true" if closed else "false"
        if limit:
            params["limit"] = min(limit, 100)

        try:
            response = self.client.get_json("/markets", params=params)
        except Exception as e:
            logger.error(f"Error fetching markets with filters {params}: {e}")
            return []

        if isinstance(response, list):
            raw_markets = response
        elif isinstance(response, dict):
            raw_markets = response.get("data", response.get("markets", []))
        else:
            return []

        markets: list[Market] = []
        for raw in raw_markets:
            market = self._parse_market(raw)
            if market:
                markets.append(market)
        return markets

    def fetch_all_markets(
        self,
        max_pages: int = 50,
        page_size: int = 100,
        active_only: bool = True,
    ) -> MarketsFetchResult:
        """
        Fetch all markets with pagination.

        Args:
            max_pages: Maximum pages to fetch
            page_size: Markets per page
            active_only: Only fetch non-closed markets

        Returns:
            MarketsFetchResult with markets and flattened market_tokens
        """
        result = MarketsFetchResult(
            markets=[],
            market_tokens=[],
            token_aliases=[],
            pages_fetched=0,
            total_markets=0,
        )
        offset = 0

        for page in range(max_pages):
            raw_markets = self.fetch_markets_page(
                limit=page_size, offset=offset, active_only=active_only
            )
            result.pages_fetched += 1

            if not raw_markets:
                break

            for raw in raw_markets:
                market = self._parse_market(raw)
                if market:
                    result.markets.append(market)
                    result.market_tokens.extend(market.to_market_tokens())
                    result.token_aliases.extend(market.to_token_aliases())
                    result.total_markets += 1

            logger.info(f"Fetched page {page + 1}: {len(raw_markets)} markets")

            if len(raw_markets) < page_size:
                break

            offset += page_size

        logger.info(
            f"Completed fetching markets: {result.total_markets} markets, "
            f"{len(result.market_tokens)} tokens in {result.pages_fetched} pages"
        )
        return result

    def _parse_market(self, raw: dict) -> Optional[Market]:
        """
        Parse raw market JSON into Market object.

        Handles JSON-encoded fields: outcomes, clobTokenIds, outcomePrices
        """
        def parse_bool(value: Optional[object]) -> Optional[bool]:
            if value is None:
                return None
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            if isinstance(value, str):
                cleaned = value.strip().lower()
                if cleaned in ("true", "1", "yes", "y"):
                    return True
                if cleaned in ("false", "0", "no", "n"):
                    return False
            return None

        def parse_datetime(value: Optional[object]) -> Optional[datetime]:
            if value is None:
                return None
            if isinstance(value, (int, float)):
                return datetime.utcfromtimestamp(value)
            if isinstance(value, str) and value:
                try:
                    cleaned = value.replace("Z", "+00:00")
                    if "T" in cleaned:
                        cleaned = cleaned.split("+")[0]
                        return datetime.fromisoformat(cleaned)
                    return datetime.strptime(cleaned[:19], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return None
            return None

        def parse_list_field(value: object) -> list:
            if value is None:
                return []
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    return []
            if isinstance(value, list):
                return [item for item in value if item not in ("", None)]
            return []

        def parse_token_list(value: object) -> list[str]:
            parsed = parse_list_field(value)
            tokens: list[str] = []
            for item in parsed:
                if isinstance(item, dict):
                    token_id = (
                        item.get("tokenId")
                        or item.get("token_id")
                        or item.get("asset")
                        or item.get("assetId")
                        or item.get("id")
                        or ""
                    )
                    if token_id:
                        tokens.append(str(token_id))
                elif isinstance(item, (str, int, float)):
                    tokens.append(str(item))
            return tokens

        def pick_alias_list(candidates: list[list[str]], target_len: int, fallback_len: int) -> list[str]:
            for candidate in candidates:
                if candidate and len(candidate) == target_len:
                    return candidate
            for candidate in candidates:
                if candidate and len(candidate) == fallback_len:
                    return candidate
            return []

        # Parse JSON-encoded lists (Gamma API returns these as strings)
        outcomes_raw = raw.get("outcomes", "[]")
        clob_tokens_raw = raw.get("clobTokenIds", "[]")

        outcomes = [str(item) for item in parse_list_field(outcomes_raw)]
        clob_token_ids = [str(item) for item in parse_list_field(clob_tokens_raw)]

        alias_candidates: list[list[str]] = []
        for key in ("tokenIds", "token_ids", "tokenID", "token_id", "tokenId"):
            alias_candidates.append(parse_token_list(raw.get(key)))
        alias_candidates.append(parse_token_list(raw.get("tokens")))

        alias_token_ids = pick_alias_list(
            [c for c in alias_candidates if c],
            len(clob_token_ids),
            len(outcomes),
        )

        # Skip markets without token IDs
        if not clob_token_ids:
            return None

        # Extract category from various possible locations
        category = raw.get("category", "")
        raw_tags = raw.get("tags", [])
        if isinstance(raw_tags, str):
            try:
                raw_tags = json.loads(raw_tags)
            except json.JSONDecodeError:
                raw_tags = []

        tags: list[str] = []
        if isinstance(raw_tags, list):
            for tag in raw_tags:
                if isinstance(tag, dict):
                    label = tag.get("label") or tag.get("name") or tag.get("slug") or ""
                    if label:
                        tags.append(label)
                elif isinstance(tag, str):
                    tags.append(tag)

        if not category and tags:
            category = tags[0]

        event_title = (
            raw.get("eventTitle")
            or raw.get("event_title")
            or raw.get("groupItemTitle")
            or raw.get("event", "")
        )
        event_slug = (
            raw.get("eventSlug")
            or raw.get("event_slug")
            or raw.get("groupItemSlug")
            or raw.get("groupItemTitle", "")
        )

        enable_order_book = parse_bool(
            raw.get("enableOrderBook")
            or raw.get("enable_order_book")
            or raw.get("enable_orderbook")
        )
        accepting_orders = parse_bool(
            raw.get("acceptingOrders")
            or raw.get("accepting_orders")
        )

        start_date = (
            parse_datetime(raw.get("startDate"))
            or parse_datetime(raw.get("start_date_iso"))
            or parse_datetime(raw.get("startTime"))
            or parse_datetime(raw.get("start_time"))
            or parse_datetime(raw.get("startDateIso"))
        )
        end_date = (
            parse_datetime(raw.get("endDate"))
            or parse_datetime(raw.get("end_date_iso"))
            or parse_datetime(raw.get("endTime"))
            or parse_datetime(raw.get("end_time"))
        )
        close_date = (
            parse_datetime(raw.get("closeTime"))
            or parse_datetime(raw.get("close_date"))
            or parse_datetime(raw.get("closeDate"))
            or parse_datetime(raw.get("closedTime"))
            or parse_datetime(raw.get("closedAt"))
        )

        condition_id = normalize_condition_id(
            raw.get("conditionId", "") or raw.get("condition_id", "")
        )

        return Market(
            condition_id=condition_id,
            market_slug=raw.get("slug", "") or raw.get("market_slug", ""),
            question=raw.get("question", ""),
            description=raw.get("description", ""),
            category=category,
            tags=tags,
            event_slug=event_slug,
            event_title=event_title or "",
            outcomes=outcomes,
            clob_token_ids=clob_token_ids,
            alias_token_ids=alias_token_ids,
            enable_order_book=enable_order_book,
            accepting_orders=accepting_orders,
            start_date_iso=start_date,
            end_date_iso=end_date,
            close_date_iso=close_date,
            active=raw.get("closed") != True and raw.get("closed") != "true",
            liquidity=float(raw.get("liquidityNum", 0) or raw.get("liquidity", 0) or 0),
            volume=float(raw.get("volumeNum", 0) or raw.get("volume", 0) or 0),
            raw_json=raw,
        )

    def get_market_by_condition_id(self, condition_id: str) -> Optional[Market]:
        """
        Fetch a single market by its condition_id.

        Uses GET /markets?condition_id=<id> to find the market.

        Args:
            condition_id: The market's condition ID (0x...)

        Returns:
            Market if found, None otherwise
        """
        if not condition_id:
            return None

        logger.debug(f"Fetching market by condition_id: {condition_id}")

        try:
            # Try fetching with condition_id filter
            response = self.client.get_json(
                "/markets",
                params={"condition_id": condition_id, "limit": 1},
            )

            markets = []
            if isinstance(response, list):
                markets = response
            elif isinstance(response, dict):
                markets = response.get("data", response.get("markets", []))

            if markets:
                return self._parse_market(markets[0])

            # Also try with conditionId (camelCase)
            response = self.client.get_json(
                "/markets",
                params={"conditionId": condition_id, "limit": 1},
            )

            if isinstance(response, list):
                markets = response
            elif isinstance(response, dict):
                markets = response.get("data", response.get("markets", []))

            if markets:
                return self._parse_market(markets[0])

            logger.debug(f"No market found for condition_id: {condition_id}")
            return None

        except Exception as e:
            logger.error(f"Error fetching market by condition_id {condition_id}: {e}")
            return None

    def get_markets_by_condition_ids(
        self,
        condition_ids: list[str],
        batch_size: int = 10,
    ) -> list[Market]:
        """
        Fetch multiple markets by their condition_ids.

        Args:
            condition_ids: List of condition IDs to fetch
            batch_size: Number of concurrent requests (rate limiting)

        Returns:
            List of found Market objects
        """
        normalized = [normalize_condition_id(cid) for cid in condition_ids if cid]
        normalized = [cid for cid in normalized if cid]
        if not normalized:
            return []

        markets: dict[str, Market] = {}
        for i in range(0, len(normalized), batch_size):
            batch = normalized[i:i + batch_size]
            fetched = self.fetch_markets_filtered(
                condition_ids=batch,
                closed=False,
            )
            for market in fetched:
                markets[market.condition_id] = market

            missing = [cid for cid in batch if cid not in markets]
            if missing:
                fetched_closed = self.fetch_markets_filtered(
                    condition_ids=missing,
                    closed=True,
                )
                for market in fetched_closed:
                    markets[market.condition_id] = market

            logger.info(
                f"Fetched batch {i // batch_size + 1}: "
                f"{len(markets)} markets so far"
            )

        logger.info(f"Fetched {len(markets)} markets out of {len(normalized)} condition_ids")
        return list(markets.values())

    def get_markets_by_clob_token_ids(
        self,
        clob_token_ids: list[str],
        batch_size: int = 20,
    ) -> list[Market]:
        """
        Fetch multiple markets by their clob token ids.
        """
        tokens = [str(token) for token in clob_token_ids if token]
        if not tokens:
            return []

        markets: dict[str, Market] = {}
        for i in range(0, len(tokens), batch_size):
            batch = tokens[i:i + batch_size]
            fetched = self.fetch_markets_filtered(
                clob_token_ids=batch,
                closed=False,
            )
            for market in fetched:
                markets[market.condition_id] = market

            if not fetched:
                fetched_closed = self.fetch_markets_filtered(
                    clob_token_ids=batch,
                    closed=True,
                )
                for market in fetched_closed:
                    markets[market.condition_id] = market

            logger.info(
                f"Fetched batch {i // batch_size + 1}: "
                f"{len(markets)} markets so far"
            )

        logger.info(f"Fetched {len(markets)} markets from {len(tokens)} clob token ids")
        return list(markets.values())

    def get_markets_by_slugs(
        self,
        slugs: list[str],
        batch_size: int = 20,
    ) -> list[Market]:
        """
        Fetch markets by slug list, with closed fallback.
        """
        cleaned = [slug.strip() for slug in slugs if slug and slug.strip()]
        if not cleaned:
            return []

        markets: dict[str, Market] = {}
        for i in range(0, len(cleaned), batch_size):
            batch = cleaned[i:i + batch_size]
            fetched = self.fetch_markets_filtered(
                slugs=batch,
                closed=False,
            )
            for market in fetched:
                markets[market.condition_id] = market

            if not fetched:
                fetched_closed = self.fetch_markets_filtered(
                    slugs=batch,
                    closed=True,
                )
                for market in fetched_closed:
                    markets[market.condition_id] = market

            logger.info(
                f"Fetched slug batch {i // batch_size + 1}: "
                f"{len(markets)} markets so far"
            )

        logger.info(f"Fetched {len(markets)} markets from {len(cleaned)} slugs")
        return list(markets.values())
