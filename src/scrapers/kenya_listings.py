"""
Kenya local market scrapers — Cheki, Jiji, PigiaMe.
These are the "ground truth" prices after import, duty, and dealer markup.
"""
import re
from typing import List, Optional
from datetime import datetime

from loguru import logger

from .base import BaseScraper, VehicleListing


class KenyaMarketScraper(BaseScraper):
    """
    Scrapes Kenyan car marketplace listings.

    Sources (by traffic):
    1. Cheki (cheki.co.ke) — largest, most professional
    2. Jiji (jiji.co.ke/cars) — classifieds, good volume
    3. PigiaMe (pigiame.co.ke) — classifieds

    These give us the actual street price in KES for imported vehicles.
    Combined with JDM auction data, we can calculate:
    - Full landed cost (auction + shipping + duty + dealer margin)
    - Dealer profit margins
    - Fair market value
    """

    CHEKI_URL = "https://cheki.co.ke"
    CHEKI_SEARCH = "https://cheki.co.ke/search"
    JIJI_URL = "https://jiji.co.ke"
    JIJI_CARS = "https://jiji.co.ke/cars"
    PIGIAME_URL = "https://www.pigiame.co.ke"
    PIGIAME_CARS = "https://www.pigiame.co.ke/vehicles"
    PIGIAME_SEARCH = "https://www.pigiame.co.ke/vehicles/search"

    # Kenya-specific makes (adds to JDM list)
    KENYA_MAKES = {
        **{
            "toyota": "Toyota", "nissan": "Nissan", "honda": "Honda",
            "mitsubishi": "Mitsubishi", "mazda": "Mazda", "subaru": "Subaru",
            "suzuki": "Suzuki", "daihatsu": "Daihatsu", "isuzu": "Isuzu",
            "lexus": "Lexus", "volkswagen": "Volkswagen", "vw": "Volkswagen",
            "bmw": "BMW", "mercedes": "Mercedes-Benz", "benz": "Mercedes-Benz",
            "audi": "Audi", "land rover": "Land Rover", "landrover": "Land Rover",
            "range rover": "Land Rover", "peugeot": "Peugeot", "renault": "Renault",
            "ford": "Ford", "hyundai": "Hyundai", "kia": "Kia",
            "proton": "Proton", "mahindra": "Mahindra",
        }
    }

    def __init__(self, proxy_url: str = None, delay_seconds: float = 2.0):
        super().__init__(proxy_url=proxy_url, delay_seconds=delay_seconds)

    def search_cheki(
        self,
        make: str = None,
        model: str = None,
        year_from: int = None,
        year_to: int = None,
        price_min: int = None,
        price_max: int = None,
        page: int = 1,
    ) -> List[VehicleListing]:
        """Search Cheki Kenya."""
        params = {
            "make": make or "",
            "model": model or "",
            "year_from": year_from or "",
            "year_to": year_to or "",
            "price_from": price_min or "",
            "price_to": price_max or "",
            "page": page,
        }
        params = {k: v for k, v in params.items() if v}

        listings = []
        try:
            soup = self._soup(self.CHEKI_SEARCH, params)
            if soup is None:
                logger.warning("Cheki blocked or unreachable")
                return []
            cars = soup.select(
                ".listing-item, .car-card, .vehicle-listing, "
                "[class*='listing'], [class*='car-card'], article"
            )

            for car in cars:
                listing = self._parse_kenya_listing(car, source="cheki")
                if listing:
                    listings.append(listing)

            logger.info(f"Cheki returned {len(listings)} results (page {page})")
        except Exception as e:
            logger.error(f"Cheki search failed: {e}")

        return listings

    def search_jiji(
        self,
        make: str = None,
        model: str = None,
        year_from: int = None,
        year_to: int = None,
        price_min: int = None,
        price_max: int = None,
    ) -> List[VehicleListing]:
        """Search Jiji Kenya."""
        # Jiji uses URL-based filters
        url = self.JIJI_CARS
        if make:
            url = f"{self.JIJI_URL}/cars/{make.lower().replace(' ', '-')}"

        params = {}
        if price_min:
            params["price_min"] = price_min
        if price_max:
            params["price_max"] = price_max

        listings = []
        try:
            soup = self._soup(url, params if params else None)
            if soup is None:
                logger.warning("Jiji blocked or unreachable")
                return []
            cars = soup.select(
                ".b-list-advert__item, .b-advert-list-item, "
                "[class*='advert'], [data-ad-id], .qa-advert-list-item"
            )

            for car in cars:
                listing = self._parse_kenya_listing(car, source="jiji")
                if listing:
                    listings.append(listing)

            logger.info(f"Jiji returned {len(listings)} results")
        except Exception as e:
            logger.error(f"Jiji search failed: {e}")

        return listings

    def search_pigiame(
        self,
        make: str = None,
        model: str = None,
        page: int = 1,
    ) -> List[VehicleListing]:
        """Search PigiaMe Kenya."""
        params = {"page": page}
        if make:
            params["make"] = make
        if model:
            params["model"] = model

        listings = []
        try:
            soup = self._soup(self.PIGIAME_SEARCH, params)
            if soup is None:
                logger.warning("PigiaMe blocked or unreachable")
                return []
            cars = soup.select(
                ".listing-card, .item-card, [class*='listing-card'], "
                "[class*='product-card'], .ad-item"
            )

            for car in cars:
                listing = self._parse_kenya_listing(car, source="pigiame")
                if listing:
                    listings.append(listing)

            logger.info(f"PigiaMe returned {len(listings)} results (page {page})")
        except Exception as e:
            logger.error(f"PigiaMe search failed: {e}")

        return listings

    def search_all(
        self,
        make: str = None,
        model: str = None,
        year_from: int = None,
        year_to: int = None,
    ) -> List[VehicleListing]:
        """Scrape all Kenyan sources for a vehicle query."""
        all_listings = []

        # Cheki
        try:
            all_listings.extend(self.search_cheki(make, model, year_from, year_to))
        except Exception as e:
            logger.error(f"Cheki all failed: {e}")

        # Jiji
        try:
            all_listings.extend(
                self.search_jiji(make, model, year_from, year_to)
            )
        except Exception as e:
            logger.error(f"Jiji all failed: {e}")

        # PigiaMe
        try:
            all_listings.extend(self.search_pigiame(make, model))
        except Exception as e:
            logger.error(f"PigiaMe all failed: {e}")

        return self._deduplicate_listings(all_listings)

    def _parse_kenya_listing(self, element, source: str) -> Optional[VehicleListing]:
        """Parse a listing from any Kenyan marketplace."""
        try:
            # Title
            title_el = element.select_one(
                "h2, h3, .title, .name, [class*='title'], [class*='name'], a"
            )
            if not title_el:
                return None
            title = title_el.get_text(strip=True)

            # Make/Model
            make = "Unknown"
            model = "Unknown"
            for alias, canonical in self.KENYA_MAKES.items():
                if alias in title.lower():
                    make = canonical
                    rest = title.lower().replace(alias, "").strip()
                    parts = rest.split()
                    if parts:
                        model = parts[0].title()
                    break

            # Price (KES)
            price_el = element.select_one(
                ".price, [class*='price'], .amount, [class*='amount'], "
                ".listing-price, [data-price]"
            )
            price_kes = None
            if price_el:
                price_text = price_el.get_text(strip=True)
                price_match = re.search(r"KES?\s*([\d,]+)", price_text, re.IGNORECASE)
                if not price_match:
                    price_match = re.search(r"KSh\s*([\d,]+)", price_text, re.IGNORECASE)
                if not price_match:
                    price_match = re.search(r"([\d,]+)", price_text)
                if price_match:
                    price_kes = float(price_match.group(1).replace(",", ""))

            # Year
            year = None
            year_el = element.select_one(".year, [class*='year'], .mfgyear")
            if year_el:
                year_match = re.search(r"(20\d{2})", year_el.get_text(strip=True))
                if year_match:
                    year = int(year_match.group(1))
            if not year:
                year_match = re.search(r"(20\d{2})", title)
                if year_match:
                    year = int(year_match.group(1))

            # Mileage
            mileage_km = None
            mile_el = element.select_one(".mileage, [class*='mileage'], [class*='km']")
            if mile_el:
                mile_text = mile_el.get_text(strip=True)
                mile_match = re.search(r"([\d,]+)\s*km", mile_text, re.IGNORECASE)
                if mile_match:
                    mileage_km = int(mile_match.group(1).replace(",", ""))

            # Location
            location_el = element.select_one(".location, [class*='location'], .area")
            location = None
            if location_el:
                location = location_el.get_text(strip=True)

            # URL
            link_el = element.select_one("a[href]")
            url = ""
            source_id = str(hash(title + str(price_kes)))
            if link_el:
                href = link_el.get("href", "")
                if source == "cheki":
                    url = href if href.startswith("http") else f"{self.CHEKI_URL}{href}"
                elif source == "jiji":
                    url = href if href.startswith("http") else f"{self.JIJI_URL}{href}"
                else:
                    url = href if href.startswith("http") else href
                source_id = url.split("/")[-1].split("?")[0] if url else source_id

            # Transmission
            transmission = None
            trans_text = element.get_text().lower()
            if "automatic" in trans_text or "auto" in trans_text:
                transmission = "automatic"
            elif "manual" in trans_text:
                transmission = "manual"

            # Engine
            engine_cc = None
            eng_match = re.search(r"([\d,]+)\s*cc", element.get_text(), re.IGNORECASE)
            if eng_match:
                engine_cc = int(eng_match.group(1).replace(",", ""))

            return VehicleListing(
                source=source,
                source_id=source_id,
                url=url,
                make=make,
                model=model,
                year=year,
                mileage_km=mileage_km,
                engine_cc=engine_cc,
                transmission=transmission,
                price_kes=price_kes,
                location=location or "Kenya",
            )
        except Exception as e:
            logger.warning(f"Failed to parse {source} listing: {e}")
            return None

    def _deduplicate_listings(self, listings: List[VehicleListing]) -> List[VehicleListing]:
        """Remove duplicates across sources by make/model/year/price proximity."""
        seen = set()
        unique = []
        for l in listings:
            key = (l.make, l.model, l.year, l.transmission)
            if key not in seen:
                seen.add(key)
                unique.append(l)
        return unique

    def search(self, **kwargs) -> List[VehicleListing]:
        return self.search_all(**kwargs)

    def get_detail(self, listing_id: str) -> VehicleListing:
        return VehicleListing(
            source="kenya", source_id=listing_id, url="", make="Unknown", model="Unknown"
        )
