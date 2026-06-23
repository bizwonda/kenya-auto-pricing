# 🇰🇪 Kenya Used Vehicle Pricing API

**Know the real price of any car in Kenya. Backed by JDM auction data + local market ML.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![License: BUSL-1.1](https://img.shields.io/badge/license-BUSL--1.1-yellow.svg)](LICENSE)

## The Problem

Car dealers in Kenya lose **KES 200K-500K per vehicle** because pricing is pure guesswork.

- No Kelley Blue Book for Kenya
- JDM auction prices are invisible to most buyers
- Dealers don't know what the same car sells for across town
- Customers don't know if they're getting ripped off

## The Solution

A data pipeline + ML API that tells you the real price of any vehicle in Kenya, instantly.

**Data sources:**
- 🇯🇵 JDM auctions (SBT Japan, USS, TradeCarView) — FOB/freight prices
- 🇰🇪 Kenya marketplaces (Cheki, Jiji, PigiaMe) — street prices
- 📊 ML model combining both for fair market value

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/predict` | Price a single vehicle |
| `POST` | `/predict/batch` | Price up to 100 vehicles at once |
| `GET` | `/market-stats/{make}/{model}` | Real market data (avg price, range, listings) |
| `GET` | `/depreciation/{make}/{model}` | Full depreciation curve for a model |
| `GET` | `/popular` | Most listed vehicles in Kenya |
| `GET` | `/health` | API health + model status |

### Full API docs

Once running: `http://localhost:8000/docs` (interactive Swagger UI)

## Quick Start

### 1. Install dependencies

```bash
cd kenya-auto-pricing
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set your API_KEY at minimum
```

### 3. Start with Docker (recommended)

```bash
docker-compose up -d
```

This starts:
- **API** on port `8000`
- **Scraper** (ingests data every 6 hours)
- **PostgreSQL** (vehicle database)
- **Redis** (caching)

### 4. Or run locally

```bash
# Start the API
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# In another terminal: start data ingestion
python -m src.utils.ingest
```

### 5. Test it

```bash
curl -X POST http://localhost:8000/predict \
  -H "X-API-Key: your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "make": "Toyota",
    "model": "Vitz",
    "year": 2019,
    "mileage_km": 45000,
    "engine_cc": 1000,
    "transmission": "automatic"
  }'
```

Response:
```json
{
  "make": "Toyota",
  "model": "Vitz",
  "year": 2019,
  "predicted_price_kes": 1350000,
  "price_range": {
    "low_kes": 1150000,
    "high_kes": 1550000
  },
  "predicted_price_usd": 9300,
  "confidence": 85,
  "market_context": {
    "count": 47,
    "avg_price_kes": 1420000,
    "median_price_kes": 1380000
  }
}
```

## How It Works

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  JDM Sources │     │ Kenya Market │     │  Reference   │
│  SBT, USS,   │     │ Cheki, Jiji, │     │  Global MSRP │
│  TradeCarView│     │ PigiaMe      │     │  (optional)  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┼────────────────────┘
                            ▼
                   ┌────────────────┐
                   │  Data Pipeline │
                   │  Clean → Feat  │
                   │  → Store (PG)  │
                   └───────┬────────┘
                           │
                           ▼
                   ┌────────────────┐
                   │  XGBoost Model │
                   │  Train / Retrain│
                   │  (every 7 days) │
                   └───────┬────────┘
                           │
                           ▼
                   ┌────────────────┐
                   │   FastAPI      │
                   │   /predict     │
                   │   /stats       │
                   └────────────────┘
```

### Model Features

The ML model uses:
- Vehicle age + age² (captures depreciation acceleration)
- Mileage (km) + log mileage + km/year
- Engine capacity (affects import duty brackets)
- Brand premium flags (Lexus, European brands)
- Vehicle type (4x4, sedan, compact, van — each has different demand)
- Market rarity (how many of this model are currently listed)
- Transmission (automatic commands premium in Kenya)

### Training

Model retrains automatically every 7 days using the latest market data.

Manual retrain:
```bash
python -c "
from src.pipeline.storage import Database
from src.model.train import VehiclePricingModel

db = Database('sqlite:///data/kenya_auto.db')
df = db.get_vehicles_dataframe(days_back=180)
model = VehiclePricingModel(model_path='models/xgb_pricing_v1.json')
metrics = model.train(df)
print(metrics)
"
```

## Pricing & Monetization

### Sell access to car dealers

| Tier | Price | Features |
|------|-------|----------|
| **Basic** | KES 2,500/mo | 50 lookups/month |
| **Dealer** | KES 7,500/mo | 500 lookups/month + batch |
| **Enterprise** | KES 25,000/mo | Unlimited + API access + white-label |

**Reach**: ~500 active car dealers in Nairobi alone. Close rate of 20% = 100 dealers × KES 7,500 = **KES 750,000/month** from Nairobi dealers.

Secondary markets:
- **Banks** — vehicle collateral valuation
- **Insurance** — accurate replacement values
- **SACCOs** — loan collateral assessment
- **Importers** — JDM purchase decisions

### Going national: ~3,000+ dealers across Kenya. Revenue ceiling: KES 5-10M/month.

## Deployment

### On a VPS (Hetzner, DigitalOcean, etc.)

```bash
# Clone and deploy
git clone <repo> kenya-auto-pricing && cd kenya-auto-pricing
docker-compose up -d

# Set up nginx reverse proxy
sudo cp deploy/nginx/kenya-pricing.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/kenya-pricing.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL with certbot
sudo certbot --nginx -d api.yourdomain.com
```

### Railway / Render / Fly.io

Single-click deploy — just point at the Dockerfile and set env vars.

## Cold Outreach Playbook

### Who to target first
- Car dealers on Mombasa Road, Ngong Road, Kiambu Road
- JDM importers (SBT Japan customers in Kenya)
- Car bazaars — Jamhuri, Kenya Motor Sports Club meets

### The opening (print this, walk in)
1. Walk into a dealership. Don't pitch.
2. Ask about 3 cars on their lot — what they paid, what they're asking
3. Pull out your phone/printout. Show them what the same car costs:
   - At Japanese auction (FOB price)
   - After shipping + duty (landed cost)
   - Average street price from 50+ current listings
4. Point out which cars they overpaid on
5. They'll ask: "How do you know this?"
6. **That's your sale.** "KES 7,500/month. First month free."

### Objection handling

| They say | You say |
|----------|---------|
| "I know the market" | "Then you know the Vitz you paid 1.2M for is selling for 950K on Mombasa Road right now." |
| "Too expensive" | "How much did you lose on your last bad buy? This pays for itself on one car." |
| "I don't use tech" | "It's WhatsApp. Send me a car, I send you the price. That's it." |

### WhatsApp integration (Phase 2)
Build a WhatsApp bot: dealer sends `price Toyota Vitz 2019 45000km` → instant response with fair value, range, and market count. No app, no login. This is the growth hack.

## Project Structure

```
kenya-auto-pricing/
├── src/
│   ├── scrapers/          # Data ingestion
│   │   ├── base.py        #   Base scraper class
│   │   ├── jdm_auctions.py #   SBT Japan, USS, etc.
│   │   └── kenya_listings.py # Cheki, Jiji, PigiaMe
│   ├── pipeline/          # ETL + storage
│   │   ├── cleaner.py     #   Data cleaning + feature engineering
│   │   └── storage.py     #   PostgreSQL/SQLite database layer
│   ├── model/             # ML
│   │   └── train.py       #   XGBoost model training + prediction
│   ├── api/               # Web service
│   │   └── main.py        #   FastAPI application
│   └── utils/
│       └── ingest.py      #   Scheduled data pipeline runner
├── tests/                 # Tests (add as you go)
├── notebooks/             # Jupyter for exploratory analysis
├── deploy/                # Deployment configs
├── docker-compose.yml     # Full stack orchestration
├── Dockerfile             # Container build
├── requirements.txt       # Python dependencies
└── .env.example           # Environment config template
```

## Requirements

- Python 3.11+
- PostgreSQL 16+ (or SQLite for dev)
- Redis (caching, optional for basic use)
- 2GB+ RAM for model training

## License

BUSL-1.1 — Free for non-production use, paid license for commercial deployment.

## Roadmap

- [ ] WhatsApp bot for dealer queries
- [ ] Real-time price alerts (price drops on tracked models)
- [ ] Import cost calculator (JDM auction → landed Kenya)
- [ ] Dealer panel dashboard (track your inventory value)
- [ ] Mobile app for buyers
- [ ] Regional expansion (UG, TZ, RW)
