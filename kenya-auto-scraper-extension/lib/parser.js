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
    // SBT uses dynamic rendering — cards appear after JS loads
    listingSelector: [
      // Common SBT card patterns
      ".car-list-item", ".vehicle-card", ".stock-list-item",
      "[class*='car-item']", "[class*='vehicle-item']", "[class*='stock-item']",
      "[class*='car-card']", "[class*='vehicle-card']", "[class*='stock-card']",
      "[class*='car-box']", "[class*='vehicle-box']", "[class*='stock-box']",
      // Grid/list children
      ".car-list > div", ".vehicle-list > div", ".stock-list > div",
      ".search-result-list > div", ".search-results > div",
      // Generic card patterns SBT might use
      "[class*='product-card']", "[class*='product-item']",
      "[class*='inventory-card']", "[class*='inventory-item']",
      // Table rows
      "tr[class*='car']", "tr[class*='stock']", "tr[class*='vehicle']",
      // SBT-specific: items with car detail links
      "a[href*='/used-cars/stock/']", "a[href*='/car-detail/']",
      "a[href*='/stock/']",
      // Very generic: divs containing car makes (fallback)
      "div[class*='item']", "div[class*='card']"
    ],
    fields: {
      // SBT typically shows title as uppercase MAKE MODEL YEAR
      title: [
        "h2", "h3", "h4", "h5",
        ".car-name", ".vehicle-name", ".stock-name",
        ".car-title", ".vehicle-title", ".stock-title",
        "[class*='car-name']", "[class*='vehicle-name']", "[class*='stock-name']",
        "[class*='title']", "[class*='name']",
        ".listing-title", ".item-title",
        // SBT may use strong/b tags for car names
        "strong", "b",
        // Link text itself often contains the car name
        "a[href*='/used-cars/stock/']", "a[href*='/stock/']", "a[href*='/car-detail/']"
      ],
      price: [
        ".price", "[class*='price']", ".fob-price", ".car-price",
        "[class*='amount']", "[class*='fob']",
        ".vehicle-price", ".stock-price", ".listing-price",
        "[class*='vehicle-price']", "[class*='stock-price']",
        // SBT often shows price in a highlighted span
        "span[class*='price']", "div[class*='price']",
        ".currency", "[class*='currency']",
        // Price near "FOB" or "USD" text
        ".fob", "[class*='fob']"
      ],
      year: [
        ".year", "[class*='year']", ".mfgyear", ".model-year",
        "[class*='mfg']", "[class*='model-year']",
        ".vehicle-year", ".stock-year",
        // SBT specs often in a list/dl
        ".specs .year", "dl dt:contains('Year') + dd",
        "li:contains('Year')", "td:contains('Year') + td"
      ],
      mileage: [
        ".mileage", "[class*='mileage']", "[class*='odo']", "[class*='km']",
        ".vehicle-mileage", ".stock-mileage",
        "li:contains('Mileage')", "li:contains('km')",
        "td:contains('Mileage') + td", "td:contains('km') + td",
        "dl dt:contains('Mileage') + dd", "dl dt:contains('Odometer') + dd"
      ],
      engine: [
        ".engine", "[class*='engine']", "[class*='cc']",
        ".engine-size", ".engine-capacity",
        "li:contains('Engine')", "td:contains('Engine') + td",
        "dl dt:contains('Engine') + dd", "dl dt:contains('cc') + dd",
        "li:contains('cc')", "td:contains('cc') + td"
      ],
      transmission: [
        ".transmission", "[class*='transmission']", "[class*='trans']",
        "li:contains('Transmission')", "td:contains('Transmission') + td",
        "dl dt:contains('Transmission') + dd"
      ],
      location: [
        ".location", "[class*='location']", ".port",
        ".yard", "[class*='yard']", "[class*='port']",
        "li:contains('Location')", "td:contains('Location') + td"
      ],
      url: [
        "a[href*='/used-cars/stock/']", "a[href*='/stock/']",
        "a[href*='/car-detail/']", "a[href*='/vehicle/']",
        "a[href*='/car/']", "a[href*='/detail/']",
        // If the card itself is a link
        "a[href*='sbtjapan.com']"
      ]
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
    // Handle :contains() pseudo-selector (not native CSS)
    if (sel.includes(":contains(")) {
      const text = extractByContains(el, sel);
      if (text) return text;
      continue;
    }
    try {
      const found = el.querySelector(sel);
      if (found) {
        const text = found.textContent.trim();
        if (text && text.length < 200) return text;
      }
    } catch (e) {
      // Invalid selector, skip
    }
  }
  return null;
}

// Extract text using label:value pattern (e.g., "Year: 2019" in li/td/dt+dd)
function extractByContains(el, selector) {
  // Parse: "li:contains('Year')" or "td:contains('Year') + td" or "dl dt:contains('Year') + dd"
  const match = selector.match(/^([a-z]+)(?:\.([\w-]+))?:contains\(['"](.+?)['"]\)(?:\s*\+\s*([a-z]+))?$/);
  if (!match) return null;
  
  const [, tag, className, searchText, siblingTag] = match;
  const searchLower = searchText.toLowerCase();
  
  // Find elements matching tag that contain the search text
  const els = el.querySelectorAll(tag);
  for (const e of els) {
    if (e.textContent.toLowerCase().includes(searchLower)) {
      // If looking for sibling (e.g., td:contains('Year') + td)
      if (siblingTag) {
        let sib = e.nextElementSibling;
        while (sib) {
          if (sib.tagName.toLowerCase() === siblingTag) {
            return sib.textContent.trim();
          }
          sib = sib.nextElementSibling;
        }
      } else {
        // Extract value after the label text
        const text = e.textContent.trim();
        // "Year: 2019" → "2019", "Year 2019" → "2019"
        const after = text.substring(text.toLowerCase().indexOf(searchLower) + searchLower.length);
        return after.replace(/^[\s:：]+/, "").trim();
      }
    }
  }
  return null;
}

// SBT-specific: extract specs from the full text content
function extractSpecsFromText(el) {
  const text = el.textContent || "";
  const specs = {};
  
  // Year: look for 4-digit year starting with 19 or 20
  const yearMatch = text.match(/\b(19\d{2}|20\d{2})\b/);
  if (yearMatch) specs.year = parseInt(yearMatch[1]);
  
  // Mileage: number followed by km
  const mileMatch = text.match(/([\d,]+)\s*km/i);
  if (mileMatch) specs.mileage_km = parseInt(mileMatch[1].replace(/,/g, ""));
  
  // Engine: number followed by cc
  const engMatch = text.match(/([\d,]+)\s*cc/i);
  if (engMatch) specs.engine_cc = parseInt(engMatch[1].replace(/,/g, ""));
  
  // Transmission
  if (/automatic|\bauto\b|cvt/i.test(text)) specs.transmission = "automatic";
  else if (/manual|\bmt\b/i.test(text)) specs.transmission = "manual";
  
  // Price: USD or KES
  const usdMatch = text.match(/\$\s*([\d,]+)/);
  if (usdMatch) specs.price_usd = parseFloat(usdMatch[1].replace(/,/g, ""));
  
  const kesMatch = text.match(/KES?\s*([\d,]+)/i);
  if (kesMatch) specs.price_kes = parseFloat(kesMatch[1].replace(/,/g, ""));
  
  const jpyMatch = text.match(/[¥￥]\s*([\d,]+)/);
  if (jpyMatch) specs.price_jpy = parseFloat(jpyMatch[1].replace(/,/g, ""));
  
  // FOB price
  const fobMatch = text.match(/FOB\s*[:]?\s*\$?\s*([\d,]+)/i);
  if (fobMatch && !specs.price_usd) specs.price_usd = parseFloat(fobMatch[1].replace(/,/g, ""));
  
  return specs;
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
  if (!make) return null; // Skip if no recognized car make

  const priceText = extractText(el, parser.fields.price);
  const { price_kes, price_usd } = parsePrice(priceText);
  
  const yearText = extractText(el, parser.fields.year);
  const mileageText = extractText(el, parser.fields.mileage);
  const engineText = extractText(el, parser.fields.engine);
  const transText = extractText(el, parser.fields.transmission);
  const location = extractText(el, parser.fields.location);
  const url = extractUrl(el, parser.fields.url, baseUrl);

  // Fallback: extract specs from full element text
  const textSpecs = extractSpecsFromText(el);

  return {
    source: parser.name,
    source_key: sourceKey,
    url: url || baseUrl,
    make: make,
    model: model || "Unknown",
    year: parseYear(yearText || title) || textSpecs.year,
    mileage_km: parseMileage(mileageText) || textSpecs.mileage_km,
    engine_cc: parseEngine(engineText) || textSpecs.engine_cc,
    transmission: parseTransmission(transText) || textSpecs.transmission,
    price_kes: price_kes || textSpecs.price_kes,
    price_usd: price_usd || textSpecs.price_usd,
    price_jpy: textSpecs.price_jpy,
    location: location,
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
