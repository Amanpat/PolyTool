"""Gamma API client for Polymarket user resolution."""

import logging
from typing import Optional
from dataclasses import dataclass

from .http_client import HttpClient

logger = logging.getLogger(__name__)

# Default Gamma API base URL
DEFAULT_GAMMA_API_BASE = "https://gamma-api.polymarket.com"


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
