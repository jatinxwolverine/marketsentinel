"""Robust HTTP client with exponential backoff retries, timeout enforcement, and rate-limiting."""

from __future__ import annotations

import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from marketsentinel.core.exceptions import APIConnectionError
from marketsentinel.core.logging import get_logger

logger = get_logger("marketsentinel.api")


class BaseAPIClient:
    """Base HTTP client equipped with enterprise connection pooling and retry policies."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 15,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        # HTTP retry strategy for server errors only (not 429, to allow immediate fallback)
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": "MarketSentinel-Intelligence-Bot/1.0",
                "Accept": "application/json",
            }
        )

    def get(self, endpoint: str, params: dict | None = None) -> dict | list:
        """Executes a GET request against the API endpoint.

        Args:
            endpoint: URL path segment.
            params: Query string parameters.

        Returns:
            Parsed JSON dictionary or list.

        Raises:
            APIConnectionError: On HTTP errors, network timeouts, or malformed responses.
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        try:
            logger.debug(f"HTTP GET: {url} | Params: {params}")
            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 429:
                logger.warning(f"Rate limited by API at {url} (HTTP 429).")
                raise APIConnectionError("Rate limit exceeded (HTTP 429)", {"status_code": 429, "url": url})

            response.raise_for_status()
            return response.json()

        except (requests.exceptions.Timeout, TimeoutError) as e:
            logger.error(f"API Timeout connecting to {url}: {e}")
            raise APIConnectionError(f"Connection timed out after {self.timeout}s: {url}") from e
        except requests.exceptions.RequestException as e:
            logger.error(f"API Request failed for {url}: {e}")
            raise APIConnectionError(f"Failed HTTP request to {url}: {e}") from e
        except ValueError as e:
            logger.error(f"Failed to parse JSON response from {url}: {e}")
            raise APIConnectionError(f"Invalid JSON received from {url}") from e
        except Exception as e:
            if isinstance(e, APIConnectionError):
                raise
            logger.error(f"Unexpected connection error for {url}: {e}")
            raise APIConnectionError(f"Unexpected API error for {url}: {e}") from e

    def close(self) -> None:
        """Closes the underlying requests session."""
        self.session.close()
