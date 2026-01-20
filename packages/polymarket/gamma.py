"""Gamma API client for Polymarket user resolution and market metadata."""

import json
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from .http_client import HttpClient

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
                raw_json=self.raw_json,
            ))
        return tokens


@dataclass
class MarketsFetchResult:
    """Result of fetching markets from Gamma API."""

    markets: list[Market]
    market_tokens: list[MarketToken]
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

        # Parse JSON-encoded lists (Gamma API returns these as strings)
        outcomes_raw = raw.get("outcomes", "[]")
        clob_tokens_raw = raw.get("clobTokenIds", "[]")

        if isinstance(outcomes_raw, str):
            try:
                outcomes = json.loads(outcomes_raw)
            except json.JSONDecodeError:
                outcomes = []
        else:
            outcomes = outcomes_raw or []

        if isinstance(clob_tokens_raw, str):
            try:
                clob_token_ids = json.loads(clob_tokens_raw)
            except json.JSONDecodeError:
                clob_token_ids = []
        else:
            clob_token_ids = clob_tokens_raw or []

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

        return Market(
            condition_id=raw.get("conditionId", "") or raw.get("condition_id", ""),
            market_slug=raw.get("slug", "") or raw.get("market_slug", ""),
            question=raw.get("question", ""),
            description=raw.get("description", ""),
            category=category,
            tags=tags,
            event_slug=event_slug,
            event_title=event_title or "",
            outcomes=outcomes,
            clob_token_ids=clob_token_ids,
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
        markets = []
        for i, condition_id in enumerate(condition_ids):
            market = self.get_market_by_condition_id(condition_id)
            if market:
                markets.append(market)

            # Log progress every 10 markets
            if (i + 1) % 10 == 0:
                logger.info(f"Fetched {i + 1}/{len(condition_ids)} markets by condition_id")

        logger.info(f"Fetched {len(markets)} markets out of {len(condition_ids)} condition_ids")
        return markets
