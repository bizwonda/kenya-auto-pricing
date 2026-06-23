"""
JDM auction scraper — pulls data from Japanese auto auction platforms.
Sources: USS, Aucnet, JAA, TAA — primarily via their search/list pages.

Key JDM auction fields:
- Auction grade (3-6, R, RA) — heavily determines price
- Auction score (interior/exterior ratings)
- Mileage (km) — verified vs. unknown
- Auction house + date sold
"""
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

from loguru import logger

from .base import BaseScraper, VehicleListing

# Japanese manufacturer mapping (alias → canonical)
JDM_MAKES = {
    "toyota": "Toyota", "nissan": "Nissan", "honda": "Honda",
    "mitsubishi": "Mitsubishi", "mazda": "Mazda", "subaru": "Subaru",
    "suzuki": "Suzuki", "daihatsu": "Daihatsu", "isuzu": "Isuzu",
    "lexus": "Lexus", "infiniti": "Infiniti", "acura": "Acura",
}

# Transmission codes
TRANSMISSION_MAP = {
    "AT": "automatic", "MT": "manual", "CVT": "cvt",
    "FAT": "automatic", "5F": "automatic", "6MT": "manual",
}


class JDMAuctionScraper(BaseScraper):
    """
    Scrapes Japanese auto auction data.

    Primary sources (in order of reliability):
    1. USS Auction (www.ussauction.co.jp) — largest, most data
    2. Aucnet (www.aucnet.co.jp) — good API-like interface
    3. JAA (www.jaa.or.jp) — dealer-focused
    4. TAA (www.taa.or.jp) — regional auctions

    Many of these require membership. For initial MVP, we can scrape:
    - USS public search results
    - GooNet Exchange listings (wholesale pricing with auction grades)
    - TradeCarView (export-oriented, shows FOB prices)
    - SBT Japan (Kenya's biggest JDM exporter — already shows KES prices)
    """

    # SBT Japan — direct source for Kenya-bound JDM vehicles
    SBT_URL = "https://sbtjapan.com"
    SBT_SEARCH = "https://sbtjapan.com/search"

    # TradeCarView — shows FOB Japan prices
    TCV_URL = "https://www.tradecarview.com"

    # GooNet Exchange — auction reference prices
    GOONET_URL = "https://www.goo-net-exchange.com"

    def __init__(self, proxy_url: str = None, delay_seconds: float = 3.0):
        super().__init__(proxy_url=proxy_url, delay_seconds=delay_seconds)

    def search_sbt(
        self,
        make: str = None,
        model: str = None,
        year_from: int = None,
        year_to: int = None,
        price_min_usd: int = None,
        price_max_usd: int = None,
        page: int = 1,
    ) -> List[VehicleListing]:
        """
        Search SBT Japan — the primary JDM exporter to East Africa.
        Their prices are already in KES/USD FOB.
        """
        params = {
            "page": page,
            "maker": make or "",
            "model": model or "",
            "yf": year_from or "",
            "yt": year_to or "",
            "pf": price_min_usd or "",
            "pt": price_max_usd or "",
        }
        params = {k: v for k, v in params.items() if v}

        listings = []
        try:
            soup = self._soup(self.SBT_SEARCH, params)
            if soup is None:
                logger.warning(f"SBT blocked or unreachable")
                return []
            cars = soup.select(".car-list-item, .vehicle-card, [class*='car-item']")

            for car in cars:
                listing = self._parse_sbt_car(car)
                if listing:
                    listings.append(listing)

            logger.info(f"SBT search returned {len(listings)} results (page {page})")
        except Exception as e:
            logger.error(f"SBT search failed: {e}")

        return listings

    def _parse_sbt_car(self, car_element) -> Optional[VehicleListing]:
        """Parse an SBT Japan car listing element."""
        try:
            # Try multiple selectors (sites change)
            title_el = car_element.select_one("h2, .title, [class*='name'], .car-name")
            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            make, model = self._parse_make_model(title)

            # Price
            price_el = car_element.select_one(
                ".price, [class*='price'], .amount, [class*='fob']"
            )
            price_usd = None
            price_kes = None
            if price_el:
                price_text = price_el.get_text(strip=True)
                price_usd = self._extract_price(price_text, "USD")
                price_kes = self._extract_price(price_text, "KES")

            # Year
            year_el = car_element.select_one(".year, [class*='year'], .mfgyear")
            year = None
            if year_el:
                year_match = re.search(r"(20\d{2})", year_el.get_text(strip=True))
                if year_match:
                    year = int(year_match.group(1))

            # Mileage
            mile_el = car_element.select_one(".mileage, [class*='mileage'], [class*='odo']")
            mileage_km = None
            if mile_el:
                mile_text = mile_el.get_text(strip=True)
                mile_match = re.search(r"([\d,]+)\s*km", mile_text, re.IGNORECASE)
                if mile_match:
                    mileage_km = int(mile_match.group(1).replace(",", ""))

            # Engine
            engine_el = car_element.select_one(".engine, [class*='engine'], [class*='cc']")
            engine_cc = None
            if engine_el:
                eng_match = re.search(r"([\d,]+)\s*cc", engine_el.get_text(strip=True), re.IGNORECASE)
                if eng_match:
                    engine_cc = int(eng_match.group(1).replace(",", ""))

            # Transmission
            trans_el = car_element.select_one(".transmission, [class*='trans'], [class*='transmission']")
            transmission = None
            if trans_el:
                trans_text = trans_el.get_text(strip=True).upper()
                for code, name in TRANSMISSION_MAP.items():
                    if code in trans_text:
                        transmission = name
                        break
                if not transmission and "auto" in trans_text.lower():
                    transmission = "automatic"
                elif not transmission and "manual" in trans_text.lower():
                    transmission = "manual"

            # Link
            link_el = car_element.select_one("a[href]")
            url = ""
            if link_el:
                href = link_el.get("href", "")
                url = href if href.startswith("http") else f"{self.SBT_URL}{href}"

            # ID
            source_id = url.split("/")[-1] if url else title

            return VehicleListing(
                source="sbt_japan",
                source_id=source_id,
                url=url,
                make=make,
                model=model,
                year=year,
                mileage_km=mileage_km,
                engine_cc=engine_cc,
                transmission=transmission,
                price_usd=price_usd,
                price_kes=price_kes,
                fuel_type="petrol",  # default for JDM — can refine
                location="Japan",
            )
        except Exception as e:
            logger.warning(f"Failed to parse SBT car: {e}")
            return None

    def _parse_make_model(self, title: str) -> tuple:
        """Extract make and model from a title like 'Toyota Vitz 2019'."""
        for alias, canonical in JDM_MAKES.items():
            if alias in title.lower():
                make = canonical
                rest = re.sub(alias, "", title, flags=re.IGNORECASE).strip()
                # Try to extract model (first word after make, unless it's a number)
                parts = rest.split()
                if parts and not parts[0].isdigit():
                    model = parts[0]
                else:
                    model = rest[:30] if rest else "Unknown"
                return make, model
        return "Unknown", title[:30] if title else "Unknown"

    @staticmethod
    def _extract_price(text: str, currency: str) -> Optional[float]:
        """Extract price in specific currency from text."""
        patterns = {
            "USD": [r"\$\s*([\d,]+)", r"USD\s*([\d,]+)", r"([\d,]+)\s*USD"],
            "KES": [r"KES\s*([\d,]+)", r"KSh\s*([\d,]+)", r"([\d,]+)\s*KES"],
            "JPY": [r"¥\s*([\d,]+)", r"JPY\s*([\d,]+)", r"([\d,]+)\s*JPY"],
        }
        for pattern in patterns.get(currency, []):
            match = re.search(pattern, text.replace(",", ""), re.IGNORECASE)
            if match:
                return float(match.group(1))
        return None

    def search(self, **kwargs) -> List[VehicleListing]:
        return self.search_sbt(**kwargs)

    def get_detail(self, listing_id: str) -> VehicleListing:
        soup = self._soup(f"{self.SBT_URL}/car/{listing_id}")
        if soup is None:
            return VehicleListing(
                source="sbt_japan", source_id=listing_id, url="", make="Unknown", model="Unknown"
            )
        # Detail page parsing — often richer than listing page
        # Reuse _parse_sbt_car on the detail page
        fake_element = soup.find("body")
        return self._parse_sbt_car(fake_element) if fake_element else VehicleListing(
            source="sbt_japan", source_id=listing_id, url="", make="Unknown", model="Unknown"
        )
