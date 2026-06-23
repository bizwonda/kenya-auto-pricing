"""
FastAPI application — Kenya Used Vehicle Pricing API.

Endpoints:
- POST /predict — price a single vehicle
- POST /predict/batch — price multiple vehicles
- GET /market-stats/{make}/{model} — market overview
- GET /depreciation/{make}/{model} — depreciation curve
- GET /popular — trending vehicles
- GET /health — service health check
"""
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from loguru import logger

from src.model.train import VehiclePricingModel
from src.pipeline.storage import Database

# --- Configuration ---
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/kenya_auto.db")
MODEL_PATH = os.getenv("MODEL_PATH", "./models/xgb_pricing_v1.json")
API_KEY = os.getenv("API_KEY", "demo-key")

# --- Initialize ---
app = FastAPI(
    title="Kenya Used Vehicle Pricing API",
    description="""
    ## Accurate pricing for used vehicles in Kenya
    
    Combines JDM auction data, Kenyan marketplace listings, and machine learning
    to provide fair market value estimates for any vehicle.
    
    ### Features:
    - **Price prediction** — Fair market value in KES with confidence intervals
    - **Market stats** — Real-time listing data, trends, and comparables
    - **Depreciation curves** — See how a model holds value over time
    - **Batch pricing** — Price entire inventories at once
    
    ### Use cases:
    - Car dealers verifying purchase prices
    - Buyers checking if they're overpaying
    - Banks assessing collateral value
    - Insurance companies setting premiums
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global state ---
model = VehiclePricingModel(model_path=MODEL_PATH if os.path.exists(MODEL_PATH) else None)
db = Database(DATABASE_URL)


# --- Auth dependency ---
def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key


# --- Request/Response schemas ---
class VehicleRequest(BaseModel):
    make: str = Field(..., example="Toyota", description="Manufacturer")
    model: str = Field(..., example="Vitz", description="Model name")
    year: int = Field(..., ge=1995, le=datetime.now().year, example=2019, description="Manufacturing year")
    mileage_km: Optional[int] = Field(None, ge=0, example=45000, description="Odometer in km")
    engine_cc: Optional[int] = Field(None, ge=500, le=10000, example=1000, description="Engine capacity in cc")
    transmission: Optional[str] = Field("automatic", example="automatic", description="Transmission type")
    fuel_type: Optional[str] = Field("petrol", example="petrol")


class BatchRequest(BaseModel):
    vehicles: List[VehicleRequest] = Field(..., min_items=1, max_items=100)


class PriceResponse(BaseModel):
    make: str
    model: str
    year: int
    mileage_km: Optional[int]
    engine_cc: Optional[int]
    transmission: Optional[str]
    predicted_price_kes: float
    price_range: Dict[str, float]
    predicted_price_usd: float
    confidence: float
    market_context: Optional[Dict[str, Any]] = None
    model_version: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class BatchPriceResponse(BaseModel):
    predictions: List[PriceResponse]
    total: int
    average_confidence: float


class MarketStatsResponse(BaseModel):
    make: str
    model: str
    stats: Dict[str, Any]
    similar_listings: Optional[List[Dict[str, Any]]] = None


class DepreciationPoint(BaseModel):
    year: int
    age: int
    estimated_mileage_km: int
    price_kes: float
    price_usd: float


class DepreciationResponse(BaseModel):
    make: str
    model: str
    curve: List[DepreciationPoint]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_version: str
    training_metrics: Optional[Dict[str, float]]
    database: str
    uptime: str


# --- Routes ---
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health and model status."""
    return {
        "status": "healthy",
        "model_loaded": model.model is not None,
        "model_version": model.model_version,
        "training_metrics": model.training_metrics if model.training_metrics else None,
        "database": DATABASE_URL.split("://")[0],
        "uptime": "running",
    }


@app.post("/predict", response_model=PriceResponse)
async def predict_price(
    vehicle: VehicleRequest,
    x_api_key: str = Depends(verify_api_key),
):
    """
    Predict the fair market price of a used vehicle in Kenya.
    
    Returns KES price, USD estimate, confidence score, and price range.
    """
    try:
        prediction = model.predict(
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
            mileage_km=vehicle.mileage_km,
            engine_cc=vehicle.engine_cc,
            transmission=vehicle.transmission,
            fuel_type=vehicle.fuel_type,
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=503,
            detail="Model not trained yet. Train the model with sufficient data first, "
                   "or use /market-stats for data-driven estimates."
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction error: {str(e)}")

    # Add market context
    market_context = None
    try:
        db.init_db()
        market_context = db.get_market_stats(
            make=vehicle.make,
            model=vehicle.model,
            year=vehicle.year,
        )
    except Exception:
        pass

    return PriceResponse(
        **prediction,
        market_context=market_context,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post("/predict/batch", response_model=BatchPriceResponse)
async def predict_batch(
    batch: BatchRequest,
    x_api_key: str = Depends(verify_api_key),
):
    """
    Price up to 100 vehicles at once. Ideal for dealer inventory valuation.
    """
    if model.model is None:
        raise HTTPException(status_code=503, detail="Model not trained yet")

    predictions = []
    for v in batch.vehicles:
        pred = model.predict(
            make=v.make, model=v.model, year=v.year,
            mileage_km=v.mileage_km, engine_cc=v.engine_cc,
            transmission=v.transmission, fuel_type=v.fuel_type,
        )
        predictions.append(PriceResponse(
            **pred,
            timestamp=datetime.utcnow().isoformat(),
        ))

    avg_conf = sum(p.confidence for p in predictions) / len(predictions) if predictions else 0

    return BatchPriceResponse(
        predictions=predictions,
        total=len(predictions),
        average_confidence=round(avg_conf, 1),
    )


@app.get("/market-stats/{make}/{model}", response_model=MarketStatsResponse)
async def get_market_stats(
    make: str,
    model: str,
    year: Optional[int] = Query(None, ge=1995),
    x_api_key: str = Depends(verify_api_key),
):
    """
    Get real market statistics for a vehicle make/model.
    
    Includes: average price, price range, listing count, average mileage.
    Uses live data from Kenyan marketplaces.
    """
    try:
        db.init_db()
        stats = db.get_market_stats(make=make, model=model, year=year)
    except Exception as e:
        logger.error(f"Market stats error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if stats.get("count", 0) == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No market data found for {make} {model}"
            + (f" ({year})" if year else "")
        )

    return MarketStatsResponse(
        make=make,
        model=model,
        stats=stats,
        similar_listings=None,
    )


@app.get("/depreciation/{make}/{model}", response_model=DepreciationResponse)
async def get_depreciation_curve(
    make: str,
    model: str,
    start_year: int = Query(2005, ge=1995),
    end_year: Optional[int] = Query(None),
    x_api_key: str = Depends(verify_api_key),
):
    """
    Get the depreciation curve for a vehicle model.
    
    See how the vehicle loses value over time — useful for:
    - Deciding optimal age to buy/sell
    - Estimating residual value
    - Comparing models for long-term cost
    """
    if model.model is None:
        raise HTTPException(status_code=503, detail="Model not trained yet")

    curve = model.get_depreciation_curve(
        make=make, model=model,
        start_year=start_year, end_year=end_year,
    )

    return DepreciationResponse(
        make=make,
        model=model,
        curve=[DepreciationPoint(**p) for p in curve],
    )


@app.get("/popular")
async def get_popular_models(
    limit: int = Query(20, ge=1, le=50),
    x_api_key: str = Depends(verify_api_key),
):
    """Get the most frequently listed vehicles in Kenya."""
    try:
        db.init_db()
        popular = db.get_popular_models(limit=limit)
    except Exception as e:
        logger.error(f"Popular models error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    return {
        "models": popular,
        "total": len(popular),
        "category": "most_listed",
    }


@app.on_event("startup")
async def startup():
    """Initialize DB and load model on startup."""
    try:
        db.init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")

    if os.path.exists(MODEL_PATH):
        try:
            model.load(MODEL_PATH)
            logger.info(f"Model loaded: {model.model_version}")
        except Exception as e:
            logger.warning(f"Model not loaded (train with data first): {e}")
    else:
        logger.info("No model found — train with /admin/train after data collection")


@app.on_event("shutdown")
async def shutdown():
    logger.info("API shutting down")
