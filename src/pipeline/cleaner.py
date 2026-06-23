"""
Data pipeline: clean raw scraped listings, engineer features, store in DB.
Handles the full ETL flow from scrapers → clean data → model-ready features.
"""
import re
from typing import List, Optional, Dict, Any
from datetime import datetime

import pandas as pd
import numpy as np
from loguru import logger

from src.scrapers.base import VehicleListing


class DataCleaner:
    """
    Cleans and normalizes raw vehicle listings from all sources.
    Standardizes makes, models, handles missing values, removes outliers.
    """

    # Known model names by make (expand over time)
    MAKE_MODEL_MAP = {
        "Toyota": [
            "Vitz", "Yaris", "Corolla", "Axio", "Fielder", "Premio", "Allion",
            "Camry", "Mark", "Crown", "Harrier", "RAV4", "Vanguard", "Land",
            "Prado", "Landcruiser", "Hilux", "Fortuner", "Alphard", "Vellfire",
            "Noah", "Voxy", "Wish", "Sienta", "Passo", "Belta", "Probox",
            "Succeed", "Hiace", "Avanza", "Rush", "C-HR", "Aqua", "Prius",
            "FJ", "Ractis", "Isis", "Ipsum", "Auris", "Porte", "Spade",
            "Estima", "Kluger", "GT86", "Celsior", "Century",
        ],
        "Nissan": [
            "Note", "March", "Tiida", "Latio", "Sylphy", "Bluebird", "Teana",
            "X-Trail", "Dualis", "Juke", "Murano", "Patrol", "Navara",
            "Wingroad", "AD", "NV", "Serena", "Elgrand", "Cube", "Leaf",
        ],
        "Honda": [
            "Fit", "Vezel", "Freed", "CR-V", "Accord", "Civic", "Insight",
            "Grace", "Shuttle", "Jade", "Stepwgn", "Odyssey", "Stream",
        ],
        "Subaru": [
            "Forester", "Impreza", "Legacy", "Outback", "XV", "WRX",
        ],
        "Mitsubishi": [
            "Pajero", "Outlander", "RVR", "Delica", "Lancer", "Galant", "Colt",
        ],
        "Mazda": [
            "Demio", "Axela", "Atenza", "CX-5", "CX-3", "Premacy", "Verisa",
            "BT-50",
        ],
    }

    # Model name aliases (kanji/Japanese → English)
    MODEL_ALIASES = {
        "vitz": "Vitz", "yaris": "Yaris", "corolla": "Corolla",
        "fielder": "Fielder", "premio": "Premio", "allion": "Allion",
        "camry": "Camry", "harrier": "Harrier", "rav4": "RAV4",
        "prado": "Prado", "hilux": "Hilux", "fortuner": "Fortuner",
        "alphard": "Alphard", "vellfire": "Vellfire", "noah": "Noah",
        "voxy": "Voxy", "sienta": "Sienta", "passo": "Passo",
        "probox": "Probox", "hiace": "Hiace", "aqua": "Aqua",
        "prius": "Prius", "c-hr": "C-HR", "chr": "C-HR",
        "note": "Note", "march": "March", "tiida": "Tiida",
        "x-trail": "X-Trail", "xtrail": "X-Trail", "juke": "Juke",
        "fit": "Fit", "vezel": "Vezel", "freed": "Freed",
        "cr-v": "CR-V", "crv": "CR-V", "forester": "Forester",
        "impreza": "Impreza", "demio": "Demio", "axela": "Axela",
        "pajero": "Pajero", "outlander": "Outlander",
        "land cruiser": "Land Cruiser", "landcruiser": "Land Cruiser",
    }

    @classmethod
    def clean_listings(cls, listings: List[VehicleListing]) -> pd.DataFrame:
        """Convert listing objects to a clean DataFrame."""
        records = [l.to_dict() for l in listings]
        df = pd.DataFrame(records)

        if df.empty:
            logger.warning("No listings to clean")
            return df

        # Normalize makes
        df["make"] = df["make"].apply(cls._normalize_make)

        # Normalize models
        df["model"] = df.apply(
            lambda row: cls._normalize_model(row["make"], row["model"]), axis=1
        )

        # Handle missing values
        df = cls._handle_missing(df)

        # Remove outliers
        df = cls._remove_outliers(df)

        # Calculate age
        current_year = datetime.now().year
        df["vehicle_age"] = df["year"].apply(
            lambda y: current_year - y if pd.notna(y) else None
        )

        # Standardize mileage (km)
        df["mileage_km"] = df["mileage_km"].apply(
            lambda m: m if pd.notna(m) and 0 < m < 500000 else None
        )

        # Remove defensive: known bad/placeholder prices
        df = cls._filter_bad_prices(df)

        logger.info(f"Cleaned {len(df)} listings ({len(listings) - len(df)} removed)")
        return df

    @classmethod
    def _normalize_make(cls, make: str) -> str:
        """Normalize manufacturer name."""
        if not make or not isinstance(make, str):
            return "Unknown"

        make = make.strip()
        # Handle common misspellings
        corrections = {
            "toyot": "Toyota", "toyta": "Toyota",
            "nissin": "Nissan", "nissian": "Nissan",
            "hoda": "Honda", "hundai": "Hyundai", "hyundia": "Hyundai",
            "mazada": "Mazda", "mazada": "Mazda",
            "subaro": "Subaru",
            "mitsibishi": "Mitsubishi", "mitshubishi": "Mitsubishi",
            "isuz": "Isuzu",
            "mercedez": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz",
            "landrover": "Land Rover", "land rover": "Land Rover",
            "range rover": "Land Rover", "rangerover": "Land Rover",
            "vw": "Volkswagen",
        }
        make_lower = make.lower()
        for wrong, right in corrections.items():
            if wrong in make_lower:
                return right
        return make.title()

    @classmethod
    def _normalize_model(cls, make: str, model: str) -> str:
        """Normalize model name to canonical form."""
        if not model or not isinstance(model, str):
            return "Unknown"

        model = model.strip()
        model_lower = model.lower()

        # Direct alias lookup
        for alias, canonical in cls.MODEL_ALIASES.items():
            if alias == model_lower or model_lower.startswith(alias):
                return canonical

        return model

    @staticmethod
    def _handle_missing(df: pd.DataFrame) -> pd.DataFrame:
        """Intelligent missing value handling."""
        # Drop rows with no make or model
        df = df.dropna(subset=["make", "model"])
        df = df[df["make"] != "Unknown"]
        df = df[df["model"] != "Unknown"]

        # Estimate year from model + market knowledge if missing
        # (basic: none for now, requires more data)

        return df

    @staticmethod
    def _remove_outliers(df: pd.DataFrame) -> pd.DataFrame:
        """Remove clearly erroneous data points."""
        # Year must be between 1995 and current year + 1
        current_year = datetime.now().year
        if "year" in df.columns:
            df = df[
                (df["year"].isna()) | ((df["year"] >= 1995) & (df["year"] <= current_year + 1))
            ]

        # Mileage must be positive and under 500k km
        if "mileage_km" in df.columns:
            df = df[
                (df["mileage_km"].isna()) | ((df["mileage_km"] > 0) & (df["mileage_km"] < 500000))
            ]

        # Price (KES) must be reasonable
        if "price_kes" in df.columns:
            df = df[
                (df["price_kes"].isna()) | ((df["price_kes"] > 100000) & (df["price_kes"] < 50000000))
            ]

        return df

    @staticmethod
    def _filter_bad_prices(df: pd.DataFrame) -> pd.DataFrame:
        """Remove listings with placeholder/stale prices."""
        # Remove exact duplicates of known stale prices
        common_placeholder_prices = [1234567, 1000000, 999999, 888888]
        for price in common_placeholder_prices:
            if "price_kes" in df.columns:
                df = df[df["price_kes"] != price]
        return df


class FeatureEngineer:
    """
    Engineers features from cleaned vehicle data for ML model training.
    Creates depreciation curves, categorical features, and derived metrics.
    """

    @staticmethod
    def build_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Build ML-ready features from cleaned vehicle data.

        Key features:
        - vehicle_age: Current year - manufacturing year
        - mileage_per_year: km / age (wear rate)
        - is_premium: whether it's a luxury brand
        - is_4x4: SUV/off-road capability premium
        - engine_size_bin: engine capacity buckets
        - make_model_combo: combined make+model categorical
        - condition_from_source: inferred condition
        """
        df = df.copy()

        current_year = datetime.now().year

        # Age features
        if "year" in df.columns:
            df["vehicle_age"] = current_year - df["year"]
            df["vehicle_age_squared"] = df["vehicle_age"] ** 2

        # Mileage features
        if "mileage_km" in df.columns and "vehicle_age" in df.columns:
            df["km_per_year"] = df["mileage_km"] / df["vehicle_age"].clip(lower=1)
            df["log_mileage"] = np.log1p(df["mileage_km"].clip(lower=0))
        elif "mileage_km" in df.columns:
            df["log_mileage"] = np.log1p(df["mileage_km"].clip(lower=0))

        # Brand categories
        df["is_premium"] = df["make"].isin(
            ["Lexus", "Infiniti", "Acura", "BMW", "Mercedes-Benz", "Audi", "Land Rover"]
        ).astype(int)

        df["is_luxury_jdm"] = df["make"].isin(
            ["Lexus", "Infiniti", "Acura"]
        ).astype(int)

        df["is_european"] = df["make"].isin(
            ["BMW", "Mercedes-Benz", "Audi", "Volkswagen", "Land Rover",
             "Peugeot", "Renault", "Volvo"]
        ).astype(int)

        # Vehicle type classification
        df["is_4x4"] = df["model"].isin([
            "Land Cruiser", "Prado", "RAV4", "Hilux", "Fortuner", "Pajero",
            "X-Trail", "Outlander", "Patrol", "CR-V", "Forester", "Outback",
            "RVR", "Rush", "FJ", "Vanguard", "Harrier", "Murano",
        ]).astype(int)

        df["is_sedan"] = df["model"].isin([
            "Corolla", "Axio", "Fielder", "Premio", "Allion", "Camry", "Crown",
            "Teana", "Accord", "Civic", "Atenza", "Axela", "Legacy",
        ]).astype(int)

        df["is_van"] = df["model"].isin([
            "Probox", "Succeed", "AD", "Wingroad", "Hiace", "Noah", "Voxy",
            "Serena", "Elgrand", "Alphard", "Vellfire", "Stepwgn", "Odyssey",
        ]).astype(int)

        df["is_compact"] = df["model"].isin([
            "Vitz", "Yaris", "March", "Note", "Fit", "Demio", "Passo",
            "Aqua", "Sienta", "Cube", "Porte", "Spade", "Belta",
        ]).astype(int)

        # Engine size bins
        if "engine_cc" in df.columns:
            df["engine_bin"] = pd.cut(
                df["engine_cc"].fillna(1500),
                bins=[0, 1000, 1500, 2000, 2500, 3000, 4000, 10000],
                labels=["sub_1L", "1L-1.5L", "1.5L-2L", "2L-2.5L", "2.5L-3L", "3L-4L", "4L+"],
            )

        # Transmission
        if "transmission" in df.columns:
            df["is_automatic"] = df["transmission"].fillna("").str.contains(
                "auto|cvt", case=False, na=False
            ).astype(int)

        # Age bracket
        if "vehicle_age" in df.columns:
            df["age_bracket"] = pd.cut(
                df["vehicle_age"],
                bins=[-1, 3, 7, 12, 20, 100],
                labels=["0-3", "4-7", "8-12", "13-20", "20+"],
            )

        # Combined categorical
        df["make_model"] = df["make"] + "_" + df["model"]

        # Count-based features (how many of this model on the market)
        if "model" in df.columns:
            model_counts = df["model"].value_counts().to_dict()
            df["model_market_share"] = df["model"].map(model_counts) / len(df)

        return df

    @staticmethod
    def get_target_columns() -> list:
        """Return target column names for prediction."""
        return ["price_kes", "price_usd", "price_jpy"]

    @staticmethod
    def get_feature_columns() -> List[str]:
        """Return feature columns used for training."""
        return [
            "vehicle_age",
            "vehicle_age_squared",
            "mileage_km",
            "km_per_year",
            "engine_cc",
            "is_premium",
            "is_luxury_jdm",
            "is_european",
            "is_4x4",
            "is_sedan",
            "is_van",
            "is_compact",
            "is_automatic",
        ]
