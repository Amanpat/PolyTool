"""HTTP client with retries, exponential backoff, and jitter."""

import time
import random
import logging
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class HttpClient:
    """HTTP client wrapper with automatic retries and exponential backoff."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 20.0,
        max_retries: int = 5,
        backoff_factor: float = 1.0,
        retry_statuses: tuple = (429, 500, 502, 503, 504),
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Multiplier for exponential backoff
            retry_statuses: HTTP status codes that trigger a retry
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.retry_statuses = retry_statuses

        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()

        # Configure retry strategy (handles connection errors)
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=list(self.retry_statuses),
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        return session

    def _add_jitter(self, delay: float) -> float:
        """Add random jitter to delay (0-50% of delay)."""
        jitter = random.uniform(0, delay * 0.5)
        return delay + jitter

    def get(
        self,
        path: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> requests.Response:
        """
        Make a GET request with retry logic.

        Args:
            path: URL path (appended to base_url)
            params: Query parameters
            headers: Additional headers

        Returns:
            Response object

        Raises:
            requests.RequestException: If all retries fail
        """
        url = f"{self.base_url}/{path.lstrip('/')}"
        attempt = 0

        while attempt <= self.max_retries:
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                # Handle rate limiting with custom backoff
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 5))
                    delay = self._add_jitter(retry_after)
                    logger.warning(
                        f"Rate limited (429). Waiting {delay:.2f}s before retry. "
                        f"Attempt {attempt + 1}/{self.max_retries + 1}"
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue

                # Handle server errors with exponential backoff
                if response.status_code in self.retry_statuses:
                    delay = self._add_jitter(self.backoff_factor * (2**attempt))
                    logger.warning(
                        f"Server error ({response.status_code}). "
                        f"Waiting {delay:.2f}s before retry. "
                        f"Attempt {attempt + 1}/{self.max_retries + 1}"
                    )
                    time.sleep(delay)
                    attempt += 1
                    continue

                return response

            except requests.exceptions.Timeout:
                delay = self._add_jitter(self.backoff_factor * (2**attempt))
                logger.warning(
                    f"Request timeout. Waiting {delay:.2f}s before retry. "
                    f"Attempt {attempt + 1}/{self.max_retries + 1}"
                )
                time.sleep(delay)
                attempt += 1

            except requests.exceptions.ConnectionError as e:
                delay = self._add_jitter(self.backoff_factor * (2**attempt))
                logger.warning(
                    f"Connection error: {e}. Waiting {delay:.2f}s before retry. "
                    f"Attempt {attempt + 1}/{self.max_retries + 1}"
                )
                time.sleep(delay)
                attempt += 1

        raise requests.exceptions.RetryError(
            f"Max retries ({self.max_retries}) exceeded for {url}"
        )

    def get_json(
        self,
        path: str,
        params: Optional[dict] = None,
        headers: Optional[dict] = None,
    ) -> Any:
        """
        Make a GET request and return JSON response.

        Args:
            path: URL path
            params: Query parameters
            headers: Additional headers

        Returns:
            Parsed JSON response

        Raises:
            requests.RequestException: If request fails
            ValueError: If response is not valid JSON
        """
        response = self.get(path, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
