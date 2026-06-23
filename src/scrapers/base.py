"""
Base scraper with rate-limiting, proxy support, and retry logic.
"""
import time
import random
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential
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

    def __init__(self, proxy_url: Optional[str] = None, delay_seconds: float = 2.0):
        self.proxy_url = proxy_url
        self.delay_seconds = delay_seconds
        self.session = self._create_session()
        self._last_request = 0.0

    def _create_session(self) -> httpx.Client:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,ja;q=0.8,sw;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        transport = None
        if self.proxy_url:
            transport = httpx.HTTPTransport(proxy=self.proxy_url)
        return httpx.Client(headers=headers, transport=transport, timeout=30, follow_redirects=True)

    def _respect_rate_limit(self):
        elapsed = time.time() - self._last_request
        if elapsed < self.delay_seconds:
            sleep_time = self.delay_seconds - elapsed + random.uniform(0, 1)
            time.sleep(sleep_time)
        self._last_request = time.time()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def _get(self, url: str, params: dict = None) -> httpx.Response:
        self._respect_rate_limit()
        logger.debug(f"GET {url}")
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp

    def _soup(self, url: str, params: dict = None) -> BeautifulSoup:
        resp = self._get(url, params)
        return BeautifulSoup(resp.text, "lxml")

    @abstractmethod
    def search(self, **kwargs) -> List[VehicleListing]:
        """Search for vehicles matching criteria."""
        ...

    @abstractmethod
    def get_detail(self, listing_id: str) -> VehicleListing:
        """Get full details for a specific listing."""
        ...

    def close(self):
        self.session.close()
