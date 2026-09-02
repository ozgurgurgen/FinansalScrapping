"""
KAP HTTP Client — Anti-Bot, Rate-Limiting & Retry Logic
-------------------------------------------------------
All HTTP communication with kap.org.tr goes through this client.
Headers, cookies, delays, and retries are managed centrally.
"""

import logging
import random
import time
from typing import Any, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    AJAX_HEADERS,
    CONFIG,
    DEFAULT_HEADERS,
    KAP_BASE_URL,
)

logger = logging.getLogger(__name__)


class KAPClient:
    """
    Singleton-ish HTTP client for kap.org.tr.
    Handles session persistence, anti-bot headers, rate-limiting,
    and automatic retries with exponential backoff.
    """

    _instance: Optional["KAPClient"] = None

    def __new__(cls) -> "KAPClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.session = requests.Session()
        self._configure_session()
        self._last_request_time: float = 0.0

    # ── Session Configuration ──────────────────────────────────────────────
    def _configure_session(self) -> None:
        """Set up retry adapter and default headers."""
        retry_strategy = Retry(
            total=CONFIG.max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(DEFAULT_HEADERS)

        # Initial cookies from homepage (to get session cookies like JSESSIONID)
        try:
            self.session.get(KAP_BASE_URL, timeout=CONFIG.request_timeout)
            logger.info("Session initialized — cookies obtained from KAP homepage.")
        except requests.RequestException as e:
            logger.warning("Could not initialize session cookies: %s", e)

    # ── Rate Limiting ──────────────────────────────────────────────────────
    def _enforce_rate_limit(self, min_delay: float, max_delay: float) -> None:
        """Sleep a random amount between min_delay and max_delay seconds."""
        elapsed = time.time() - self._last_request_time
        delay = random.uniform(min_delay, max_delay)
        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug("Rate limit: sleeping %.2f seconds", sleep_time)
            time.sleep(sleep_time)

    # ── Core Requests ──────────────────────────────────────────────────────
    def get(
        self,
        url: str,
        params: Optional[dict] = None,
        rate_min: float = 2.0,
        rate_max: float = 4.5,
        timeout: Optional[int] = None,
        **kwargs,
    ) -> requests.Response:
        """
        Perform a GET request with rate limiting and anti-bot headers.
        Returns the Response object; caller is expected to handle errors.
        """
        self._enforce_rate_limit(rate_min, rate_max)
        if not url.startswith("http"):
            url = urljoin(KAP_BASE_URL, url)

        logger.debug("GET %s", url)
        resp = self.session.get(
            url,
            params=params,
            timeout=timeout or CONFIG.request_timeout,
            **kwargs,
        )
        self._last_request_time = time.time()
        resp.raise_for_status()
        return resp

    def post(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        rate_min: float = 1.5,
        rate_max: float = 3.0,
        timeout: Optional[int] = None,
        use_ajax_headers: bool = False,
        **kwargs,
    ) -> requests.Response:
        """
        Perform a POST request. If use_ajax_headers=True, switches
        to XHR-style headers (Accept: application/json).
        """
        self._enforce_rate_limit(rate_min, rate_max)
        if not url.startswith("http"):
            url = urljoin(KAP_BASE_URL, url)

        headers = AJAX_HEADERS if use_ajax_headers else None

        logger.debug("POST %s (ajax=%s)", url, use_ajax_headers)
        resp = self.session.post(
            url,
            data=data,
            json=json,
            headers=headers,
            timeout=timeout or CONFIG.request_timeout,
            **kwargs,
        )
        self._last_request_time = time.time()
        resp.raise_for_status()
        return resp

    def get_json(
        self,
        url: str,
        rate_min: float = 2.0,
        rate_max: float = 4.5,
        **kwargs,
    ) -> Any:
        """GET and return parsed JSON."""
        resp = self.get(url, rate_min=rate_min, rate_max=rate_max, **kwargs)
        return resp.json()

    def post_json(
        self,
        url: str,
        data: Optional[Any] = None,
        json: Optional[Any] = None,
        rate_min: float = 1.5,
        rate_max: float = 3.0,
        **kwargs,
    ) -> Any:
        """POST and return parsed JSON."""
        resp = self.post(
            url,
            data=data,
            json=json,
            rate_min=rate_min,
            rate_max=rate_max,
            use_ajax_headers=True,
            **kwargs,
        )
        return resp.json()

    def get_html(
        self,
        url: str,
        rate_min: float = 2.0,
        rate_max: float = 4.5,
        **kwargs,
    ) -> "requests.Response":
        """GET and return response (for BeautifulSoup parsing)."""
        return self.get(url, rate_min=rate_min, rate_max=rate_max, **kwargs)

    def download_attachment(
        self,
        attachment_url: str,
        save_path: str,
        rate_min: float = 3.0,
        rate_max: float = 6.0,
    ) -> str:
        """Download a file attachment (e.g. prospectus PDF) and save to disk."""
        self._enforce_rate_limit(rate_min, rate_max)
        resp = self.session.get(
            attachment_url, timeout=60, stream=True
        )
        resp.raise_for_status()
        self._last_request_time = time.time()

        with open(save_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        logger.info("Downloaded attachment → %s", save_path)
        return save_path

    def close(self) -> None:
        """Close the underlying session."""
        self.session.close()


# Convenience singleton accessor
def get_client() -> KAPClient:
    return KAPClient()
