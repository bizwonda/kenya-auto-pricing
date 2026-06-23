"""
Database storage for vehicle listings and predictions.
Uses SQLAlchemy with PostgreSQL (production) or SQLite (dev).
"""
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

import pandas as pd
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, DateTime, Boolean,
    Text, Index, UniqueConstraint, func, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB
from loguru import logger

from src.scrapers.base import VehicleListing

Base = declarative_base()


class VehicleRecord(Base):
    """Vehicle listing record in the database."""
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    source_id = Column(String(255), nullable=False)
    url = Column(Text)

    # Core attributes
    make = Column(String(100), nullable=False, index=True)
    model = Column(String(100), nullable=False, index=True)
    year = Column(Integer, index=True)
    month = Column(Integer)
    mileage_km = Column(Integer, index=True)
    engine_cc = Column(Integer)
    transmission = Column(String(50))
    fuel_type = Column(String(50))
    drive = Column(String(50))

    # Auction-specific
    grade = Column(String(20))
    auction_grade = Column(String(20))
    auction_score = Column(Float)
    has_accident = Column(Boolean)

    # Colors
    exterior_color = Column(String(50))
    interior_color = Column(String(50))

    # Pricing
    price_jpy = Column(Float, index=True)
    price_kes = Column(Float, index=True)
    price_usd = Column(Float, index=True)

    # Metadata
    location = Column(String(200))
    condition = Column(String(100))
    features = Column(JSON)

    # Tracking
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Raw data for debugging
    raw_data = Column(JSON)

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_source_listing"),
        Index("idx_make_model_year", "make", "model", "year"),
        Index("idx_price_kes", "price_kes"),
        Index("idx_scraped_at", "scraped_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "source_id": self.source_id,
            "url": self.url,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "mileage_km": self.mileage_km,
            "engine_cc": self.engine_cc,
            "transmission": self.transmission,
            "fuel_type": self.fuel_type,
            "price_kes": self.price_kes,
            "price_usd": self.price_usd,
            "price_jpy": self.price_jpy,
            "location": self.location,
            "auction_grade": self.auction_grade,
            "auction_score": self.auction_score,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }


class PricePrediction(Base):
    """Cached price predictions."""
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    make = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    mileage_km = Column(Integer)
    engine_cc = Column(Integer)
    transmission = Column(String(50))

    predicted_price_kes = Column(Float, nullable=False)
    price_range_low_kes = Column(Float)
    price_range_high_kes = Column(Float)
    confidence = Column(Float)

    # Market context
    similar_listings_count = Column(Integer)
    days_of_data = Column(Integer)

    # Computed market stats
    market_avg_kes = Column(Float)
    market_median_kes = Column(Float)
    market_std_kes = Column(Float)

    model_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_pred_lookup", "make", "model", "year", "mileage_km"),
    )


class Database:
    """Database manager for vehicle data."""

    def __init__(self, database_url: str):
        self.engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        self.SessionLocal = sessionmaker(bind=self.engine)

    def init_db(self):
        """Create all tables."""
        Base.metadata.create_all(self.engine)
        logger.info("Database initialized")

    @contextmanager
    def session(self) -> Session:
        """Get a database session."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def upsert_vehicles(self, listings: List[VehicleListing]) -> int:
        """Insert or update vehicle listings. Returns count of new records."""
        inserted = 0
        with self.session() as session:
            for listing in listings:
                existing = session.query(VehicleRecord).filter_by(
                    source=listing.source,
                    source_id=listing.source_id,
                ).first()

                if existing:
                    # Update
                    for key, value in listing.to_dict().items():
                        if hasattr(existing, key) and key not in ("id", "source", "source_id", "scraped_at"):
                            setattr(existing, key, value)
                    existing.updated_at = datetime.utcnow()
                else:
                    # Insert
                    record = VehicleRecord(
                        source=listing.source,
                        source_id=listing.source_id,
                        url=listing.url,
                        make=listing.make,
                        model=listing.model,
                        year=listing.year,
                        month=listing.month,
                        mileage_km=listing.mileage_km,
                        engine_cc=listing.engine_cc,
                        transmission=listing.transmission,
                        fuel_type=listing.fuel_type,
                        drive=listing.drive,
                        grade=listing.grade,
                        auction_grade=listing.auction_grade,
                        auction_score=listing.auction_score,
                        has_accident=listing.has_accident,
                        exterior_color=listing.exterior_color,
                        interior_color=listing.interior_color,
                        price_jpy=listing.price_jpy,
                        price_kes=listing.price_kes,
                        price_usd=listing.price_usd,
                        location=listing.location,
                        condition=listing.condition,
                        features=listing.features,
                        scraped_at=listing.scraped_at,
                        raw_data=listing.raw_data,
                    )
                    session.add(record)
                    inserted += 1

        logger.info(f"Upserted {len(listings)} listings ({inserted} new)")
        return inserted

    def get_vehicles_dataframe(
        self,
        make: str = None,
        model: str = None,
        year_from: int = None,
        year_to: int = None,
        days_back: int = 90,
    ) -> pd.DataFrame:
        """Get vehicle records as a DataFrame for model training."""
        with self.session() as session:
            query = session.query(VehicleRecord).filter(
                VehicleRecord.price_kes.isnot(None),
                VehicleRecord.scraped_at >= func.now() - func.make_interval(days=days_back),
            )

            if make:
                query = query.filter(VehicleRecord.make == make)
            if model:
                query = query.filter(VehicleRecord.model == model)
            if year_from:
                query = query.filter(VehicleRecord.year >= year_from)
            if year_to:
                query = query.filter(VehicleRecord.year <= year_to)

            records = query.all()
            return pd.DataFrame([r.to_dict() for r in records])

    def get_market_stats(
        self, make: str, model: str, year: int = None
    ) -> Dict[str, Any]:
        """Get market statistics for a specific vehicle."""
        with self.session() as session:
            query = session.query(
                func.count(VehicleRecord.id).label("count"),
                func.avg(VehicleRecord.price_kes).label("avg_price"),
                func.min(VehicleRecord.price_kes).label("min_price"),
                func.max(VehicleRecord.price_kes).label("max_price"),
                func.stddev(VehicleRecord.price_kes).label("std_price"),
                func.percentile_cont(0.5).within_group(
                    VehicleRecord.price_kes
                ).label("median_price"),
                func.avg(VehicleRecord.mileage_km).label("avg_mileage"),
                func.avg(VehicleRecord.year).label("avg_year"),
            ).filter(
                VehicleRecord.make == make,
                VehicleRecord.model == model,
                VehicleRecord.price_kes.isnot(None),
            )

            if year:
                query = query.filter(VehicleRecord.year == year)

            result = query.first()

            if not result or result.count == 0:
                return {"count": 0}

            return {
                "count": result.count,
                "avg_price_kes": round(result.avg_price) if result.avg_price else None,
                "median_price_kes": round(result.median_price) if result.median_price else None,
                "min_price_kes": round(result.min_price) if result.min_price else None,
                "max_price_kes": round(result.max_price) if result.max_price else None,
                "std_price_kes": round(result.std_price) if result.std_price else None,
                "avg_mileage_km": round(result.avg_mileage) if result.avg_mileage else None,
                "avg_year": round(result.avg_year, 1) if result.avg_year else None,
            }

    def get_popular_models(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most frequently listed models."""
        with self.session() as session:
            results = session.query(
                VehicleRecord.make,
                VehicleRecord.model,
                func.count(VehicleRecord.id).label("count"),
                func.avg(VehicleRecord.price_kes).label("avg_price"),
            ).filter(
                VehicleRecord.price_kes.isnot(None),
            ).group_by(
                VehicleRecord.make, VehicleRecord.model
            ).order_by(
                func.count(VehicleRecord.id).desc()
            ).limit(limit).all()

            return [
                {
                    "make": r.make,
                    "model": r.model,
                    "listing_count": r.count,
                    "avg_price_kes": round(r.avg_price) if r.avg_price else None,
                }
                for r in results
            ]
