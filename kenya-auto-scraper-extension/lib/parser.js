// Kenya Auto Parser — extracts vehicle listings from car marketplace pages

const PARSERS = {
  cheki: {
    name: "Cheki Kenya",
    listingSelector: [
      ".listing-item", ".car-listing", ".vehicle-card", "[class*='listing-card']",
      ".search-result-item", ".car-item", "article.listing", ".col-listing",
      "[class*='CarListItem']", ".listing-box", ".classified-listing"
    ],
    fields: {
      title: [".listing-title", ".car-title", "h2", "h3", ".title", "[class*='title']", ".name"],
      price: [".listing-price", ".price", "[class*='price']", ".amount", ".car-price"],
      year: [".listing-year", ".year", "[class*='year']", ".model-year"],
      mileage: [".listing-mileage", ".mileage", "[class*='mileage']", "[class*='km']"],
      engine: [".listing-engine", ".engine", "[class*='engine']", "[class*='cc']"],
      transmission: [".listing-transmission", ".transmission", "[class*='transmission']"],
      location: [".listing-location", ".location", "[class*='location']"],
      url: ["a[href]", "a.listing-link", ".listing-url a"]
    }
  },

  jiji: {
    name: "Jiji Kenya",
    listingSelector: [
      ".b-list-advert__item", ".b-advert-list-item", "[data-ad-id]",
      ".qa-advert-list-item", ".masonry-item", ".b-list-advert__gallery__item",
      "[class*='advert-list'] > div", ".b-advert-listing"
    ],
    fields: {
      title: [".b-advert-title-inner", ".qa-advert-title", "h3", "[class*='title']", ".b-list-advert__item-title"],
      price: [".b-list-advert__item-price", ".qa-advert-price", "[class*='price']", ".b-advert-price"],
      year: [".b-list-advert__item-attr", "[class*='year']"],
      mileage: [".b-list-advert__item-attr", "[class*='mileage']"],
      engine: [".b-list-advert__item-attr", "[class*='engine']"],
      transmission: [".b-list-advert__item-attr"],
      location: [".b-list-advert__item-location", "[class*='location']"],
      url: ["a.b-list-advert__item-image-link", "a[href*='/ad/']", ".qa-advert-title a"]
    }
  },

  pigiame: {
    name: "PigiaMe",
    listingSelector: [
      ".listing-card", ".item-card", "[class*='listing-card']",
      "[class*='product-card']", ".search-item", ".ad-item",
      ".listing-item", ".classified"
    ],
    fields: {
      title: [".listing-title", "h2", "h3", ".title", "[class*='title']"],
      price: [".listing-price", ".price", "[class*='price']"],
      year: [".listing-year", ".year", "[class*='year']"],
      mileage: [".listing-mileage", "[class*='mileage']"],
      engine: [".listing-engine", "[class*='engine']"],
      transmission: [".listing-transmission"],
      location: [".listing-location", "[class*='location']"],
      url: ["a[href*='/item/']", "a[href*='/ad/']", ".listing-title a"]
    }
  },

  sbt: {
    name: "SBT Japan",
    listingSelector: [
      ".car-list-item", ".vehicle-card", "[class*='car-item']",
      "[class*='vehicle-list'] > div", ".stock-list-item",
      ".car-box", ".vehicle-box", "tr[class*='car']"
    ],
    fields: {
      title: ["h2", "h3", ".car-name", ".vehicle-name", "[class*='title']", "[class*='name']"],
      price: [".price", "[class*='price']", ".fob-price", ".car-price", "[class*='amount']"],
      year: [".year", "[class*='year']", ".mfgyear", ".model-year"],
      mileage: [".mileage", "[class*='mileage']", "[class*='odo']", "[class*='km']"],
      engine: [".engine", "[class*='engine']", "[class*='cc']"],
      transmission: [".transmission", "[class*='transmission']"],
      location: [".location", "[class*='location']", ".port"],
      url: ["a[href*='/car/']", "a[href*='/stock/']", "a[href*='/vehicle/']", "a[href*='/detail/']"]
    }
  },

  tradecarview: {
    name: "TradeCarView",
    listingSelector: [
      ".car-list-item", ".vehicle-item", "[class*='list-item']",
      ".stock-item", ".car-card", "[class*='car-box']"
    ],
    fields: {
      title: ["h3", ".car-name", "[class*='title']", "[class*='name']"],
      price: [".price", "[class*='price']", ".fob", "[class*='amount']"],
      year: [".year", "[class*='year']"],
      mileage: [".mileage", "[class*='mileage']"],
      engine: [".engine", "[class*='engine']"],
      transmission: [".transmission"],
      location: [".location", ".port"],
      url: ["a[href*='/car/']", "a[href]"]
    }
  }
};

// Known car brands for make/model extraction
const CAR_MAKES = [
  "Toyota", "Nissan", "Honda", "Mitsubishi", "Mazda", "Subaru",
  "Suzuki", "Daihatsu", "Isuzu", "Lexus", "Infiniti", "Acura",
  "Volkswagen", "BMW", "Mercedes-Benz", "Audi", "Land Rover",
  "Peugeot", "Renault", "Ford", "Hyundai", "Kia", "Proton",
  "Mahindra", "Volvo", "Jaguar", "Porsche", "Mini",
];

function detectSource(url) {
  if (url.includes("cheki.co.ke")) return "cheki";
  if (url.includes("jiji.co.ke")) return "jiji";
  if (url.includes("pigiame.co.ke")) return "pigiame";
  if (url.includes("sbtjapan.com")) return "sbt";
  if (url.includes("tradecarview.com")) return "tradecarview";
  return null;
}

function extractText(el, selectors) {
  for (const sel of selectors) {
    const found = el.querySelector(sel);
    if (found) {
      const text = found.textContent.trim();
      if (text && text.length < 200) return text;
    }
  }
  return null;
}

function extractUrl(el, selectors, baseUrl) {
  for (const sel of selectors) {
    const found = el.querySelector(sel);
    if (found && found.href) {
      const href = found.href;
      if (href.startsWith("http")) return href;
      return new URL(href, baseUrl).href;
    }
  }
  return null;
}

function parsePrice(text) {
  if (!text) return { price_kes: null, price_usd: null };
  const cleaned = text.replace(/,/g, "");

  // KES patterns
  let match = cleaned.match(/KES?\s*([\d,]+)/i);
  if (!match) match = cleaned.match(/KSh\s*([\d,]+)/i);
  if (!match) match = cleaned.match(/KES?\s*([\d,]+)/i);
  if (match) return { price_kes: parseFloat(match[1]), price_usd: null };

  // USD patterns
  match = cleaned.match(/\$\s*([\d,]+)/);
  if (!match) match = cleaned.match(/USD\s*([\d,]+)/i);
  if (match) return { price_kes: null, price_usd: parseFloat(match[1]) };

  // Plain number — assume KES if > 100k, USD if < 100k
  match = cleaned.match(/([\d,]+)/);
  if (match) {
    const val = parseFloat(match[1]);
    if (val > 500000) return { price_kes: val, price_usd: null };
    if (val < 100000) return { price_kes: null, price_usd: val };
    return { price_kes: val, price_usd: null };
  }
  return { price_kes: null, price_usd: null };
}

function parseYear(text) {
  if (!text) return null;
  const match = text.match(/(20\d{2})/);
  return match ? parseInt(match[1]) : null;
}

function parseMileage(text) {
  if (!text) return null;
  const match = text.replace(/,/g, "").match(/([\d]+)\s*km/i);
  return match ? parseInt(match[1]) : null;
}

function parseEngine(text) {
  if (!text) return null;
  const match = text.replace(/,/g, "").match(/([\d]+)\s*cc/i);
  return match ? parseInt(match[1]) : null;
}

function parseTransmission(text) {
  if (!text) return null;
  const t = text.toLowerCase();
  if (t.includes("automatic") || t.includes("auto") || t.includes("cvt")) return "automatic";
  if (t.includes("manual") || t.includes("mt")) return "manual";
  return null;
}

function extractMakeModel(title) {
  if (!title) return { make: null, model: null };

  for (const make of CAR_MAKES) {
    const regex = new RegExp(`\\b${make}\\b`, "i");
    if (regex.test(title)) {
      const rest = title.replace(regex, "").trim();
      const parts = rest.split(/[\s,]+/);
      // Find first non-year, non-numeric word as model
      for (const part of parts) {
        if (!/^\d+$/.test(part) && !/^20\d{2}$/.test(part) && part.length > 1) {
          return { make, model: part };
        }
      }
      return { make, model: rest.substring(0, 30).trim() || "Unknown" };
    }
  }
  return { make: null, model: null };
}

function parseListing(el, sourceKey, baseUrl) {
  const parser = PARSERS[sourceKey];
  if (!parser) return null;

  const title = extractText(el, parser.fields.title);
  if (!title || title.length < 3) return null;

  const { make, model } = extractMakeModel(title);
  const priceText = extractText(el, parser.fields.price);
  const { price_kes, price_usd } = parsePrice(priceText);
  
  const yearText = extractText(el, parser.fields.year);
  const year = parseYear(yearText || title);

  const mileageText = extractText(el, parser.fields.mileage);
  const mileage_km = parseMileage(mileageText || el.textContent);

  const engineText = extractText(el, parser.fields.engine);
  const engine_cc = parseEngine(engineText || el.textContent);

  const transText = extractText(el, parser.fields.transmission);
  const transmission = parseTransmission(transText || el.textContent);

  const location = extractText(el, parser.fields.location);
  const url = extractUrl(el, parser.fields.url, baseUrl);

  return {
    source: parser.name,
    source_key: sourceKey,
    url: url || baseUrl,
    make: make || "Unknown",
    model: model || "Unknown",
    year,
    mileage_km,
    engine_cc,
    transmission,
    price_kes,
    price_usd,
    location,
    title: title.substring(0, 100),
    scraped_at: new Date().toISOString(),
  };
}

function parsePage(sourceKey) {
  const parser = PARSERS[sourceKey];
  if (!parser) return [];

  const listings = [];
  const baseUrl = window.location.href;

  for (const selector of parser.listingSelector) {
    const elements = document.querySelectorAll(selector);
    if (elements.length > 0) {
      console.log(`[AutoScraper] Found ${elements.length} listings with "${selector}"`);
      for (const el of elements) {
        const listing = parseListing(el, sourceKey, baseUrl);
        if (listing && listing.make !== "Unknown") {
          // Deduplicate by URL
          if (!listings.find(l => l.url === listing.url)) {
            listings.push(listing);
          }
        }
      }
      if (listings.length > 0) break; // Use first matching selector
    }
  }

  return listings;
}

// Export for content script
if (typeof window !== "undefined") {
  window.AutoScraper = { PARSERS, detectSource, parsePage, CAR_MAKES };
}
