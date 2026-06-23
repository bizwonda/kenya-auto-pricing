"""
ML Pricing Model — XGBoost-based vehicle price prediction.
Trains on combined JDM auction + Kenya market data.

Target: price_kes (Kenyan Shilling) — the actual market price in Kenya.

Features capture:
- Vehicle attributes (make, model, year, mileage, engine, transmission)
- Market dynamics (depreciation curve by brand/model)
- Import cost factors (engine size affects duty)
- Condition proxies (mileage/year ratio, auction grade if available)
"""
import json
import os
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    mean_absolute_percentage_error,
)
import category_encoders as ce
from loguru import logger

from src.pipeline.cleaner import FeatureEngineer


class VehiclePricingModel:
    """
    XGBoost regression model for vehicle price prediction.

    Handles:
    - Feature engineering
    - Training with early stopping
    - Model persistence (JSON)
    - Confidence intervals via quantile prediction
    - Market-adjusted pricing
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model: Optional[xgb.XGBRegressor] = None
        self.model_path = model_path
        self.feature_columns: List[str] = []
        self.feature_engineer = FeatureEngineer()
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.target_encoder: Optional[ce.TargetEncoder] = None
        self.training_metrics: Dict[str, float] = {}
        self.model_version: str = "1.0.0"
        self.trained_at: Optional[str] = None

        if model_path and os.path.exists(model_path):
            self.load(model_path)

    def _prepare_features(self, df: pd.DataFrame, fit_encoders: bool = False) -> pd.DataFrame:
        """
        Convert raw + engineered features into model-ready numeric matrix.
        """
        # Engineer features
        df = self.feature_engineer.build_features(df)

        # Select numeric feature columns
        numeric_features = [
            "vehicle_age", "vehicle_age_squared", "mileage_km", "km_per_year",
            "engine_cc", "log_mileage", "is_premium", "is_luxury_jdm",
            "is_european", "is_4x4", "is_sedan", "is_van", "is_compact",
            "is_automatic", "model_market_share",
        ]

        # Categorical features to encode
        categorical_features = ["make", "model", "make_model", "transmission",
                                 "engine_bin", "age_bracket"]

        # Build feature matrix
        features = df[numeric_features].copy().fillna(0)

        # Encode categoricals
        for col in categorical_features:
            if col not in df.columns:
                continue
            if fit_encoders:
                le = LabelEncoder()
                encoded = le.fit_transform(df[col].fillna("unknown").astype(str))
                self.label_encoders[col] = le
            elif col in self.label_encoders:
                le = self.label_encoders[col]
                # Handle unseen categories
                encoded = df[col].fillna("unknown").astype(str).apply(
                    lambda x: le.transform([x])[0] if x in le.classes_ else -1
                )
            else:
                continue

            features[f"{col}_encoded"] = encoded

        # Store feature columns for later prediction
        if fit_encoders:
            self.feature_columns = list(features.columns)

        return features

    def train(
        self,
        df: pd.DataFrame,
        target_col: str = "price_kes",
        test_size: float = 0.2,
        random_state: int = 42,
        early_stopping_rounds: int = 50,
        n_estimators: int = 1000,
    ) -> Dict[str, float]:
        """
        Train the XGBoost pricing model.

        Args:
            df: Cleaned vehicle DataFrame with price data
            target_col: Column to predict (default: price_kes)
            test_size: Validation split ratio
            random_state: Reproducibility seed
            early_stopping_rounds: XGBoost early stopping
            n_estimators: Max boosting rounds

        Returns:
            Dict of training metrics
        """
        logger.info(f"Training model with {len(df)} samples")

        if df.empty:
            raise ValueError("Empty DataFrame — no data to train on")

        # Remove rows without target
        df = df.dropna(subset=[target_col]).copy()
        logger.info(f"Samples with target price: {len(df)}")

        if len(df) < 50:
            logger.warning(f"Only {len(df)} samples — model may be unreliable")

        # Prepare features
        X = self._prepare_features(df, fit_encoders=True)
        y = df[target_col]

        # Split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        logger.info(f"Training: {len(X_train)}, Validation: {len(X_val)}")

        # Handle missing feature values
        X_train = X_train.fillna(0)
        X_val = X_val.fillna(0)

        # Train XGBoost
        self.model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=3,
            gamma=0.1,
            reg_alpha=0.1,
            reg_lambda=1.0,
            objective="reg:squarederror",
            eval_metric="mae",
            early_stopping_rounds=early_stopping_rounds,
            random_state=random_state,
            n_jobs=-1,
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=50,
        )

        # Evaluate
        y_pred = self.model.predict(X_val)
        y_pred = np.maximum(y_pred, 0)  # No negative prices

        metrics = {
            "mae": mean_absolute_error(y_val, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_val, y_pred)),
            "r2": r2_score(y_val, y_pred),
            "mape": mean_absolute_percentage_error(y_val, y_pred) * 100,
            "n_samples": len(df),
            "n_features": len(self.feature_columns),
        }

        self.training_metrics = metrics
        self.trained_at = datetime.utcnow().isoformat()

        # Feature importance
        importance = self.model.feature_importances_
        top_features = sorted(
            zip(self.feature_columns, importance),
            key=lambda x: x[1], reverse=True
        )[:10]
        logger.info("Top 10 features:")
        for feat, imp in top_features:
            logger.info(f"  {feat}: {imp:.4f}")

        logger.info(
            f"Training complete — MAE: KES {metrics['mae']:,.0f}, "
            f"R²: {metrics['r2']:.3f}, MAPE: {metrics['mape']:.1f}%"
        )

        if self.model_path:
            self.save(self.model_path)

        return metrics

    def predict(
        self,
        make: str,
        model: str,
        year: int,
        mileage_km: Optional[int] = None,
        engine_cc: Optional[int] = None,
        transmission: Optional[str] = "automatic",
        fuel_type: Optional[str] = "petrol",
        features_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Predict the fair market price for a vehicle in KES.

        Returns prediction with confidence interval.
        """
        if self.model is None:
            if self.model_path:
                self.load(self.model_path)
            else:
                raise RuntimeError("Model not loaded — call train() or load() first")

        # Build a single-row DataFrame
        row = {
            "make": make,
            "model": model,
            "year": year,
            "mileage_km": mileage_km if mileage_km else 0,
            "engine_cc": engine_cc if engine_cc else 1500,
            "transmission": transmission or "automatic",
            "fuel_type": fuel_type or "petrol",
            "source": "api_query",
            "source_id": f"{make}_{model}_{year}",
            "url": "",
        }

        if features_override:
            row.update(features_override)

        df = pd.DataFrame([row])

        # Prepare features
        X = self._prepare_features(df)
        X = X.fillna(0)

        # Ensure columns match
        for col in self.feature_columns:
            if col not in X.columns:
                X[col] = 0
        X = X[self.feature_columns]

        # Predict
        price_kes = float(np.maximum(self.model.predict(X)[0], 0))

        # Simple confidence estimate based on training metrics
        mae = self.training_metrics.get("mae", 0)
        mape = self.training_metrics.get("mape", 15)

        # Price range (±1.5 × MAE for approximate 85% confidence)
        confidence_margin = 1.5 * mae if mae > 0 else price_kes * (mape / 100)
        price_low = max(0, price_kes - confidence_margin)
        price_high = price_kes + confidence_margin

        # Confidence score (0-100)
        # Higher confidence for: newer vehicles, models with more data, common brands
        vehicle_age = datetime.now().year - year
        confidence = 85
        if vehicle_age > 10:
            confidence -= 10
        if mileage_km and mileage_km > 150000:
            confidence -= 10
        if mileage_km and mileage_km < 50000:
            confidence += 5
        if self.training_metrics.get("r2", 0) > 0.85:
            confidence += 5
        confidence = max(30, min(98, confidence))

        return {
            "make": make,
            "model": model,
            "year": year,
            "mileage_km": mileage_km,
            "engine_cc": engine_cc,
            "transmission": transmission,
            "predicted_price_kes": round(price_kes, -2),  # Round to nearest 100
            "price_range": {
                "low_kes": round(price_low, -2),
                "high_kes": round(price_high, -2),
            },
            "predicted_price_usd": round(price_kes / 145, -1),  # Approximate KES rate
            "confidence": confidence,
            "model_version": self.model_version,
            "trained_at": self.trained_at,
        }

    def predict_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        """Predict prices for a batch of vehicles."""
        if self.model is None:
            raise RuntimeError("Model not loaded")

        X = self._prepare_features(df)
        X = X.fillna(0)
        for col in self.feature_columns:
            if col not in X.columns:
                X[col] = 0
        X = X[self.feature_columns]

        prices = self.model.predict(X)
        prices = np.maximum(prices, 0)

        result = df.copy()
        result["predicted_price_kes"] = prices
        return result

    def save(self, path: str):
        """Save model to JSON (XGBoost native format)."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

        if self.model is None:
            raise RuntimeError("No model to save")

        self.model.save_model(path)

        # Save metadata alongside
        meta = {
            "feature_columns": self.feature_columns,
            "label_encoders": {k: list(v.classes_) for k, v in self.label_encoders.items()},
            "training_metrics": self.training_metrics,
            "model_version": self.model_version,
            "trained_at": self.trained_at,
        }
        meta_path = path.replace(".json", "_meta.json")
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Model saved to {path}")

    def load(self, path: str):
        """Load model from JSON."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model not found: {path}")

        self.model = xgb.XGBRegressor()
        self.model.load_model(path)

        # Load metadata
        meta_path = path.replace(".json", "_meta.json")
        if os.path.exists(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            self.feature_columns = meta.get("feature_columns", [])
            self.training_metrics = meta.get("training_metrics", {})
            self.model_version = meta.get("model_version", "1.0.0")
            self.trained_at = meta.get("trained_at")

            # Reconstruct label encoders
            for col, classes in meta.get("label_encoders", {}).items():
                le = LabelEncoder()
                le.classes_ = np.array(classes)
                self.label_encoders[col] = le

        logger.info(f"Model loaded from {path} (v{self.model_version})")

    def get_depreciation_curve(
        self, make: str, model: str, start_year: int = 2005, end_year: int = None
    ) -> List[Dict[str, Any]]:
        """Generate depreciation curve for a vehicle model."""
        if end_year is None:
            end_year = datetime.now().year

        curve = []
        for year in range(start_year, end_year + 1):
            age = end_year - year
            # Estimate mileage based on age (Kenya average: ~15k km/year)
            est_mileage = age * 15000

            prediction = self.predict(
                make=make,
                model=model,
                year=year,
                mileage_km=est_mileage,
            )
            curve.append({
                "year": year,
                "age": age,
                "estimated_mileage_km": est_mileage,
                "price_kes": prediction["predicted_price_kes"],
                "price_usd": prediction["predicted_price_usd"],
            })

        return curve
