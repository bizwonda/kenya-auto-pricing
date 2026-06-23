"""GitHub Actions training — loads scraped JSON data and trains the XGBoost model."""
import json, os, sys, glob
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

sys.path.insert(0, ".")

from src.pipeline.cleaner import DataCleaner
from src.model.train import VehiclePricingModel

# Load scraped JSON files
json_files = sorted(glob.glob("data/listings/scrape_*.json"))
if not json_files:
    print("No data files — skipping training")
    sys.exit(0)

# Only recent files (last 30 days)
cutoff = datetime.utcnow() - timedelta(days=30)
all_records = []
for f in json_files:
    try:
        ts_str = f.split("scrape_")[-1].replace(".json", "")
        ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        if ts < cutoff:
            continue
    except Exception:
        pass
    with open(f) as fh:
        all_records.extend(json.load(fh))

if not all_records:
    print("No recent data with prices — skipping")
    sys.exit(0)

df = pd.DataFrame(all_records)
print(f"Loaded {len(df)} records from {len(json_files)} files")

# Keep records with price
df = df[df["price_kes"].notna()].copy()
print(f"Records with price: {len(df)}")

if len(df) < 30:
    print(f"Need 30+ priced records (have {len(df)}) — skipping")
    sys.exit(0)

# Clean and train
df_clean = DataCleaner.clean_listings(df.to_dict("records"))
model = VehiclePricingModel(model_path="models/xgb_pricing_v1.json")
metrics = model.train(df_clean)

# Save metrics
os.makedirs("data", exist_ok=True)
with open("data/model_metrics.json", "w") as f:
    json.dump({k: float(v) if isinstance(v, (np.floating, np.integer)) else v
               for k, v in metrics.items()}, f, indent=2)

print(f"Done — MAE: KES {metrics['mae']:,.0f}, R²: {metrics['r2']:.3f}")
