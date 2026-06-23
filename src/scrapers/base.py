"""
Base scraper with rate-limiting, proxy support, and retry logic.
Handles anti-bot measures gracefully.
"""
import time
import random
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from loguru import logger


@dataclass
class VehicleListing:
    """Normalized vehicle listing across all sources."""
    source: str
    source_id: str
    url: str
    make: str
    model: str
    year: Optional[int] = None
    month: Optional[int] = None
    mileage_km: Optional[int] = None
    engine_cc: Optional[int] = None
    transmission: Optional[str] = None
    fuel_type: Optional[str] = None
    drive: Optional[str] = None
    grade: Optional[str] = None
    exterior_color: Optional[str] = None
    interior_color: Optional[str] = None
    auction_grade: Optional[str] = None
    auction_score: Optional[float] = None
    price_jpy: Optional[float] = None
    price_kes: Optional[float] = None
    price_usd: Optional[float] = None
    location: Optional[str] = None
    condition: Optional[str] = None
    has_accident: Optional[bool] = None
    features: List[str] = field(default_factory=list)
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
            else:
                d[k] = v
        return d


class BaseScraper(ABC):
    """Abstract base for all vehicle scrapers."""

    # Rotating User-Agents to avoid fingerprinting
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    ]

    def __init__(self, proxy_url: Optional[str] = None, delay_seconds: float = 2.0):
        self.proxy_url = proxy_url
        self.delay_seconds = delay_seconds
        self.session = self._create_session()
        self._last_request = 0.0

    def _random_ua(self) -> str:
        return random.choice(self.USER_AGENTS)

    def _create_session(self) -> httpx.Client:
        headers = {
            "User-Agent": self._random_ua(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,sw;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        transport = None
        if self.proxy_url:
            transport = httpx.HTTPTransport(proxy=self.proxy_url)
        return httpx.Client(
            headers=headers,
            transport=transport,
            timeout=30,
            follow_redirects=True,
            http2=True,
        )

    def _respect_rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.delay_seconds:
            sleep_time = self.delay_seconds - elapsed + random.uniform(0, 1)
            time.sleep(sleep_time)
        self._last_request = time.time()

    def _get(self, url: str, params: dict = None, retries: int = 2) -> Optional[httpx.Response]:
        """GET with retry, but skip retries on blocked responses."""
        last_error = None
        for attempt in range(retries + 1):
            self._respect_rate_limit()
            # Rotate UA each attempt
            self.session.headers["User-Agent"] = self._random_ua()
            try:
                logger.debug(f"GET {url} (attempt {attempt + 1})")
                resp = self.session.get(url, params=params)
                
                # Don't retry on blocking responses
                if resp.status_code in (403, 406, 429):
                    logger.warning(f"Blocked by {url}: HTTP {resp.status_code}")
                    return resp
                
                resp.raise_for_status()
                return resp
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code in (403, 406, 429):
                    logger.warning(f"Blocked: HTTP {e.response.status_code}")
                    break
                if attempt < retries:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.debug(f"Retrying in {wait:.1f}s...")
                    time.sleep(wait)
            except Exception as e:
                last_error = e
                if attempt < retries:
                    time.sleep(2)
        
        if last_error:
            logger.warning(f"Failed after {retries + 1} attempts: {url} — {last_error}")
        return None

    def _soup(self, url: str, params: dict = None) -> Optional[BeautifulSoup]:
        resp = self._get(url, params)
        if resp is None or resp.status_code >= 400:
            return None
        return BeautifulSoup(resp.text, "lxml")

    @abstractmethod
    def search(self, **kwargs) -> List[VehicleListing]:
        ...

    @abstractmethod
    def get_detail(self, listing_id: str) -> VehicleListing:
        ...

    def close(self):
        self.session.close()
