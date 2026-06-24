// Content script — injected into car marketplace pages
// Handles both static HTML and dynamic JS-rendered SPAs

(function () {
  "use strict";

  const sourceKey = detectSource(window.location.href);
  if (!sourceKey) return;

  const parserName = PARSERS[sourceKey]?.name || sourceKey;
  console.log(`[Kenya Auto Scraper] Active on ${parserName}`);

  let scrapedUrls = new Set();
  let scrapeTimer = null;
  let domChangeCount = 0;

  // Load previously scraped URLs
  chrome.storage.local.get({ listings: [] }, (data) => {
    (data.listings || []).forEach((l) => l.url && scrapedUrls.add(l.url));
  });

  function isListingContainer(el) {
    // Check if element or its children look like car listings
    const text = (el.textContent || "").toLowerCase();
    const signals = ["toyota", "nissan", "honda", "mitsubishi", "subaru", "mileage", "engine", "transmission", "kes", "ksh", "fob", "year"];
    let hits = 0;
    signals.forEach((s) => { if (text.includes(s)) hits++; });
    return hits >= 2;
  }

  function findAllListings() {
    const results = [];

    // Strategy 1: Known selectors (fast path)
    for (const selector of PARSERS[sourceKey].listingSelector) {
      const els = document.querySelectorAll(selector);
      if (els.length >= 2) {
        console.log(`[AutoScraper] Found ${els.length} listings via "${selector}"`);
        els.forEach((el) => {
          const listing = parseListing(el, sourceKey, window.location.href);
          if (listing && listing.make !== "Unknown" && !scrapedUrls.has(listing.url)) {
            results.push(listing);
            scrapedUrls.add(listing.url);
          }
        });
        if (results.length > 0) break;
      }
    }

    // Strategy 2: Generic container scan (for unknown page structures)
    if (results.length === 0) {
      // Find repeating card-like elements
      const candidates = document.querySelectorAll(
        "div[class*='card'], div[class*='item'], div[class*='list'], " +
        "li[class*='item'], article, div[class*='box'], div[class*='result'], " +
        "tr[class*='row'], tr[class*='item'], div[class*='col-'], " +
        "div[class*='grid'] > div, div[class*='masonry'] > div"
      );

      // Group by tag + class pattern to find repeating structures
      const patterns = {};
      candidates.forEach((el) => {
        const key = el.tagName + "|" + (el.className || "").split(" ").slice(0, 2).join(".");
        if (!patterns[key]) patterns[key] = [];
        patterns[key].push(el);
      });

      // Use the most common pattern that looks like listings
      for (const [, els] of Object.entries(patterns).sort((a, b) => b[1].length - a[1].length)) {
        if (els.length < 3) continue;
        if (els.length > 200) continue; // Too generic

        const listingEls = els.filter(isListingContainer);
        if (listingEls.length < 2) continue;

        console.log(`[AutoScraper] Generic scan: ${listingEls.length} possible listings`);
        listingEls.forEach((el) => {
          const listing = parseListing(el, sourceKey, window.location.href);
          if (listing && listing.make !== "Unknown" && !scrapedUrls.has(listing.url)) {
            results.push(listing);
            scrapedUrls.add(listing.url);
          }
        });
        if (results.length > 0) break;
      }
    }

    // Strategy 3: SPA table/row scan
    if (results.length === 0) {
      const rows = document.querySelectorAll("tr:not(:first-child)");
      const carRows = Array.from(rows).filter(isListingContainer);
      if (carRows.length >= 3) {
        console.log(`[AutoScraper] Table scan: ${carRows.length} rows`);
        carRows.forEach((el) => {
          const listing = parseListing(el, sourceKey, window.location.href);
          if (listing && listing.make !== "Unknown" && !scrapedUrls.has(listing.url)) {
            results.push(listing);
            scrapedUrls.add(listing.url);
          }
        });
      }
    }

    // Strategy 4: Deep text search for car makes + prices
    if (results.length === 0 && domChangeCount > 3) {
      console.log("[AutoScraper] Deep scan — searching text patterns");
      const allDivs = document.querySelectorAll("div, li, article, section");
      const potentialListings = [];
      
      allDivs.forEach((el) => {
        // Skip tiny or huge elements
        const textLen = (el.textContent || "").length;
        if (textLen < 50 || textLen > 2000) return;
        if (el.children.length > 10) return; // Too many children = container, not a listing
        if (el.querySelectorAll("div, li, article").length > 5) return;
        
        if (isListingContainer(el)) {
          potentialListings.push(el);
        }
      });

      // Deduplicate nested elements (keep the most specific)
      const deduped = [];
      potentialListings.forEach((el) => {
        if (!deduped.some((d) => d.contains(el))) {
          deduped.push(el);
        }
      });

      console.log(`[AutoScraper] Deep scan: ${deduped.length} candidate elements`);
      deduped.forEach((el) => {
        const listing = parseListing(el, sourceKey, window.location.href);
        if (listing && listing.make !== "Unknown" && !scrapedUrls.has(listing.url)) {
          results.push(listing);
          scrapedUrls.add(listing.url);
        }
      });
    }

    return results;
  }

  function saveAndNotify(listings) {
    if (listings.length === 0) return;

    chrome.storage.local.get({ listings: [] }, (data) => {
      const existing = data.listings || [];
      const updated = [...existing, ...listings];
      chrome.storage.local.set({ listings: updated }, () => {
        console.log(`[AutoScraper] +${listings.length} new (total: ${updated.length})`);
        chrome.runtime.sendMessage({
          action: "updateBadge",
          count: updated.length,
          source: sourceKey,
          newCount: listings.length,
        });
        showToast(listings.length, updated.length);
      });
    });
  }

  function scrapeCurrentPage() {
    const listings = findAllListings();
    if (listings.length > 0) {
      saveAndNotify(listings);
    } else if (domChangeCount === 0) {
      console.log("[AutoScraper] No listings yet — waiting for page to load...");
    }
  }

  function showToast(newCount, total) {
    // Remove existing toast
    const old = document.getElementById("kenya-auto-scraper-toast");
    if (old) old.remove();

    const toast = document.createElement("div");
    toast.id = "kenya-auto-scraper-toast";
    toast.style.cssText = `
      position: fixed; bottom: 20px; right: 20px; z-index: 999999;
      background: #1a1a2e; color: #e0e0e0; padding: 14px 20px;
      border-radius: 10px; font-family: system-ui, sans-serif;
      font-size: 14px; box-shadow: 0 4px 24px rgba(0,0,0,0.4);
      border-left: 4px solid #00c853; max-width: 320px;
      animation: kasSlideIn 0.3s ease; pointer-events: none;
    `;
    toast.innerHTML = `
      <div style="font-weight:700;color:#00c853;margin-bottom:4px">🚗 +${newCount} listings saved</div>
      <div style="font-size:12px;color:#999">Total: <b style="color:#fff">${total}</b> • ${parserName}</div>
    `;
    document.body.appendChild(toast);

    if (!document.getElementById("kas-anim-style")) {
      const style = document.createElement("style");
      style.id = "kas-anim-style";
      style.textContent = "@keyframes kasSlideIn { from { transform: translateY(100px); opacity:0; } to { transform: translateY(0); opacity:1; } }";
      document.head.appendChild(style);
    }

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // --- Progressive scraping for dynamic pages ---
  function scheduleScrape(delay = 1500) {
    if (scrapeTimer) clearTimeout(scrapeTimer);
    scrapeTimer = setTimeout(() => {
      scrapeCurrentPage();
      // Schedule follow-ups for late-loading content
      if (domChangeCount < 5) {
        scheduleScrape(4000); // Check again in 4s
      }
    }, delay);
  }

  // Initial scrape
  scheduleScrape(2000);

  // Re-scrape on popup request
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "scrapeNow") {
      scrapeCurrentPage();
      sendResponse({ ok: true });
    }
    return true;
  });

  // Watch for DOM changes (catches JS-rendered content)
  const observer = new MutationObserver((mutations) => {
    domChangeCount++;

    // Look for significant changes that might mean listings loaded
    let significantChange = false;
    for (const m of mutations) {
      if (m.addedNodes.length > 0) {
        for (const node of m.addedNodes) {
          if (node.nodeType === 1) {
            const textLen = (node.textContent || "").length;
            if (textLen > 200) {
              significantChange = true;
              break;
            }
          }
        }
      }
      if (significantChange) break;
    }

    if (significantChange) {
      // Debounce — wait for DOM to settle, then scrape
      scheduleScrape(2000);
    }
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: false,
  });

  // Watch for XHR/fetch completion
  const originalFetch = window.fetch;
  window.fetch = function (...args) {
    return originalFetch.apply(this, args).then((response) => {
      const url = typeof args[0] === "string" ? args[0] : args[0]?.url || "";
      if (url.includes("search") || url.includes("list") || url.includes("stock") || url.includes("car")) {
        console.log("[AutoScraper] Detected API call:", url.substring(0, 80));
        scheduleScrape(2500); // Wait for DOM update after data fetch
      }
      return response;
    });
  };

  // Watch for XHR
  const originalXHROpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    this._kasUrl = url;
    return originalXHROpen.apply(this, arguments);
  };
  const originalXHRSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    this.addEventListener("load", function () {
      const url = this._kasUrl || "";
      if (url.includes("search") || url.includes("list") || url.includes("stock") || url.includes("car")) {
        scheduleScrape(2500);
      }
    });
    return originalXHRSend.apply(this, arguments);
  };

  console.log("[Kenya Auto Scraper] Ready — watching for listings...");
})();
