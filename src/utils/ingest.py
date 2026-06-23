"""
Scheduled data ingestion runner.
Runs scrapers on a schedule, cleans data, stores in DB, and optionally retrains model.
"""
import os
import sys
import time
import signal
from datetime import datetime
from typing import List

import schedule
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

from src.scrapers import JDMAuctionScraper, KenyaMarketScraper
from src.pipeline.cleaner import DataCleaner
from src.pipeline.storage import Database
from src.model.train import VehiclePricingModel

# Config
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/kenya_auto.db")
MODEL_PATH = os.getenv("MODEL_PATH", "./models/xgb_pricing_v1.json")
PROXY_URL = os.getenv("PROXY_URL", None)
SCRAPE_INTERVAL_HOURS = int(os.getenv("SCRAPE_INTERVAL_HOURS", "6"))
RETRAIN_INTERVAL_DAYS = int(os.getenv("RETRAIN_INTERVAL_DAYS", "7"))
SEARCH_QUERIES = os.getenv("SEARCH_QUERIES", "")

# Popular Kenya models to always scrape (high-demand vehicles)
POPULAR_MODELS = [
    ("Toyota", "Vitz"), ("Toyota", "Corolla"), ("Toyota", "Probox"),
    ("Toyota", "Premio"), ("Toyota", "Axio"), ("Toyota", "Fielder"),
    ("Toyota", "Harrier"), ("Toyota", "Prado"), ("Toyota", "Land Cruiser"),
    ("Toyota", "RAV4"), ("Toyota", "Vanguard"), ("Toyota", "Sienta"),
    ("Toyota", "Aqua"), ("Toyota", "Prius"), ("Toyota", "Passo"),
    ("Nissan", "Note"), ("Nissan", "X-Trail"), ("Nissan", "March"),
    ("Honda", "Fit"), ("Honda", "Vezel"), ("Honda", "Freed"),
    ("Subaru", "Forester"), ("Subaru", "Impreza"), ("Subaru", "Legacy"),
    ("Mazda", "Demio"), ("Mazda", "Axela"), ("Mazda", "CX-5"),
    ("Mitsubishi", "Pajero"), ("Mitsubishi", "Outlander"),
    ("Suzuki", "Swift"), ("Suzuki", "Escudo"),
]

# If user specified custom queries, use those
CUSTOM_QUERIES = []
if SEARCH_QUERIES:
    for q in SEARCH_QUERIES.split(";"):
        parts = q.strip().split(",")
        if len(parts) >= 2:
            CUSTOM_QUERIES.append((parts[0].strip(), parts[1].strip()))


class DataPipeline:
    """Orchestrates scraping → cleaning → storage → model training."""

    def __init__(self):
        self.db = Database(DATABASE_URL)
        self.jdm = JDMAuctionScraper(proxy_url=PROXY_URL, delay_seconds=3.0)
        self.kenya = KenyaMarketScraper(proxy_url=PROXY_URL, delay_seconds=2.0)
        self.model = VehiclePricingModel(model_path=MODEL_PATH)
        self.last_train = None

    def ingest_single_vehicle(self, make: str, model: str, year_from: int = 2010):
        """Scrape data for a single vehicle make/model combination from all sources."""
        logger.info(f"Scraping: {make} {model}")

        all_listings = []

        # JDM sources (export/FOB prices)
        jdm_listings = self.jdm.search_sbt(
            make=make, model=model, year_from=year_from
        )
        all_listings.extend(jdm_listings)
        logger.info(f"  JDM: {len(jdm_listings)} listings")

        # Kenya sources (street prices)
        kenya_listings = self.kenya.search_all(
            make=make, model=model, year_from=year_from
        )
        all_listings.extend(kenya_listings)
        logger.info(f"  Kenya: {len(kenya_listings)} listings")

        if all_listings:
            self.db.init_db()
            cleaned = DataCleaner.clean_listings(all_listings)
            if not cleaned.empty:
                inserted = self.db.upsert_vehicles(all_listings)
                logger.info(f"  Stored: {inserted} new records")
                return inserted
        return 0

    def run_full_ingestion(self, queries: List[tuple] = None):
        """Run a complete ingestion cycle for all tracked vehicles."""
        start = datetime.now()
        queries = queries or POPULAR_MODELS

        total = 0
        for make, model in queries:
            try:
                total += self.ingest_single_vehicle(make, model)
            except Exception as e:
                logger.error(f"Failed {make} {model}: {e}")
                continue

        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"Ingestion complete: {total} records in {elapsed:.0f}s")

        return total

    def retrain_if_needed(self):
        """Retrain model if enough time has passed and data exists."""
        if self.last_train:
            days_since = (datetime.now() - self.last_train).days
            if days_since < RETRAIN_INTERVAL_DAYS:
                logger.info(f"Skipping retrain ({days_since}d since last)")
                return

        try:
            df = self.db.get_vehicles_dataframe(days_back=180)
            if len(df) < 100:
                logger.warning(f"Not enough data to train ({len(df)} samples)")
                return

            logger.info(f"Training model on {len(df)} samples")
            self.model.train(df, target_col="price_kes")
            self.last_train = datetime.now()
        except Exception as e:
            logger.error(f"Training failed: {e}")

    def run_scheduled(self):
        """Run ingestion on a schedule indefinitely."""
        logger.info(f"Starting scheduled ingestion (every {SCRAPE_INTERVAL_HOURS}h)")

        # Immediate first run
        self.run_full_ingestion(CUSTOM_QUERIES if CUSTOM_QUERIES else POPULAR_MODELS)
        self.retrain_if_needed()

        # Schedule recurring
        schedule.every(SCRAPE_INTERVAL_HOURS).hours.do(
            lambda: self.run_full_ingestion(
                CUSTOM_QUERIES if CUSTOM_QUERIES else POPULAR_MODELS
            )
        )
        schedule.every(24).hours.do(self.retrain_if_needed)

        # Handle signals gracefully
        running = True

        def shutdown(sig, frame):
            nonlocal running
            running = False
            logger.info("Shutting down...")

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        while running:
            schedule.run_pending()
            time.sleep(60)

    def shutdown(self):
        self.jdm.close()
        self.kenya.close()


def main():
    """Entry point for the data pipeline."""
    logger.info("Kenya Auto Pricing — Data Pipeline")

    pipeline = DataPipeline()
    try:
        pipeline.run_scheduled()
    finally:
        pipeline.shutdown()


if __name__ == "__main__":
    main()
