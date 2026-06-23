"""GitHub Actions scraper — pulls data from Kenyan marketplaces + JDM auctions."""
import json, os, sys
from datetime import datetime

sys.path.insert(0, ".")

from src.scrapers.kenya_listings import KenyaMarketScraper
from src.scrapers.jdm_auctions import JDMAuctionScraper

proxy = os.getenv("PROXY_URL") or None

POPULAR = [
    ("Toyota", "Vitz"), ("Toyota", "Corolla"), ("Toyota", "Probox"),
    ("Toyota", "Premio"), ("Toyota", "Fielder"), ("Toyota", "Harrier"),
    ("Toyota", "Prado"), ("Toyota", "Land Cruiser"), ("Toyota", "RAV4"),
    ("Nissan", "Note"), ("Nissan", "X-Trail"), ("Nissan", "March"),
    ("Honda", "Fit"), ("Honda", "Vezel"), ("Honda", "Freed"),
    ("Subaru", "Forester"), ("Subaru", "Impreza"), ("Subaru", "Legacy"),
    ("Mazda", "Demio"), ("Mazda", "Axela"), ("Mazda", "CX-5"),
    ("Mitsubishi", "Pajero"), ("Mitsubishi", "Outlander"),
    ("Toyota", "Axio"), ("Toyota", "Aqua"), ("Toyota", "Sienta"),
    ("Toyota", "Passo"), ("Toyota", "Prius"), ("Toyota", "Vanguard"),
    ("Suzuki", "Swift"), ("Suzuki", "Escudo"),
]

# Top models worth JDM lookup (auction sites are slower)
JDM_MODELS = {"Vitz", "Corolla", "Premio", "Fielder", "Prado", "Harrier",
              "Forester", "Fit", "Demio", "Note", "Aqua", "RAV4"}

# Allow custom input from workflow_dispatch
custom = os.getenv("SEARCH_QUERIES", "")
if custom:
    models = [tuple(m.strip().split(":")) for m in custom.split(",") if ":" in m]
else:
    models = POPULAR

kenya = KenyaMarketScraper(proxy_url=proxy, delay_seconds=2.0)
jdm = JDMAuctionScraper(proxy_url=proxy, delay_seconds=3.0)

all_data = []
for make, model in models:
    j_listings = []
    try:
        k_listings = kenya.search_all(make=make, model=model, year_from=2010)
        for l in k_listings:
            all_data.append(l.to_dict())
    except Exception as e:
        print(f"FAILED {make} {model} (KE): {e}")
        k_listings = []

    if model in JDM_MODELS:
        try:
            j_listings = jdm.search_sbt(make=make, model=model, year_from=2010)
            for l in j_listings:
                all_data.append(l.to_dict())
        except Exception as e:
            print(f"FAILED {make} {model} (JDM): {e}")

    print(f"{make} {model}: {len(k_listings)} KE + {len(j_listings)} JDM")

kenya.close()
jdm.close()

os.makedirs("data/listings", exist_ok=True)
ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
path = f"data/listings/scrape_{ts}.json"
with open(path, "w") as f:
    json.dump(all_data, f, default=str)

print(f"Done: {len(all_data)} listings → {path}")
