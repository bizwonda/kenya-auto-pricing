// Content script — injected into car marketplace pages
// Auto-detects listings and saves them

(function () {
  "use strict";

  const sourceKey = detectSource(window.location.href);
  if (!sourceKey) return;

  const parserName = PARSERS[sourceKey]?.name || sourceKey;
  console.log(`[Kenya Auto Scraper] Active on ${parserName} (${sourceKey})`);

  // Parse current page
  function scrapeCurrentPage() {
    const listings = parsePage(sourceKey);
    if (listings.length === 0) {
      console.log(`[Kenya Auto Scraper] No listings detected on this page`);
      return;
    }

    // Save to extension storage
    chrome.storage.local.get({ listings: [] }, (data) => {
      const existing = data.listings || [];

      // Merge — skip duplicates by URL
      const existingUrls = new Set(existing.map((l) => l.url));
      const newListings = listings.filter((l) => !existingUrls.has(l.url));

      if (newListings.length === 0) {
        console.log(`[Kenya Auto Scraper] All ${listings.length} listings already saved`);
        return;
      }

      const updated = [...existing, ...newListings];
      chrome.storage.local.set({ listings: updated }, () => {
        const total = updated.length;
        console.log(
          `[Kenya Auto Scraper] Saved ${newListings.length} new listings (total: ${total})`
        );

        // Update badge
        chrome.runtime.sendMessage({
          action: "updateBadge",
          count: total,
          source: sourceKey,
          newCount: newListings.length,
        });

        // Visual feedback on page
        showToast(newListings.length, total);
      });
    });
  }

  // Toast notification on the page
  function showToast(newCount, total) {
    const toast = document.createElement("div");
    toast.id = "kenya-auto-scraper-toast";
    toast.style.cssText = `
      position: fixed; bottom: 20px; right: 20px; z-index: 999999;
      background: #1a1a2e; color: #e0e0e0; padding: 14px 20px;
      border-radius: 10px; font-family: system-ui, sans-serif;
      font-size: 14px; box-shadow: 0 4px 24px rgba(0,0,0,0.4);
      border-left: 4px solid #00c853; max-width: 320px;
      animation: kasSlideIn 0.3s ease;
    `;
    toast.innerHTML = `
      <div style="font-weight:700;color:#00c853;margin-bottom:4px">🚗 +${newCount} listings saved</div>
      <div style="font-size:12px;color:#999">Total collected: <b style="color:#fff">${total}</b> • ${PARSERS[sourceKey]?.name}</div>
    `;
    document.body.appendChild(toast);

    // Add animation style
    const style = document.createElement("style");
    style.textContent =
      "@keyframes kasSlideIn { from { transform: translateY(100px); opacity:0; } to { transform: translateY(0); opacity:1; } }";
    document.head.appendChild(style);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s";
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // Run on page load
  setTimeout(scrapeCurrentPage, 1500);

  // Listen for re-scrape requests from popup
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === "scrapeNow") {
      scrapeCurrentPage();
      sendResponse({ ok: true });
    }
    return true;
  });

  // Watch for dynamic content (infinite scroll, SPA navigation)
  let lastUrl = window.location.href;
  const observer = new MutationObserver(() => {
    if (window.location.href !== lastUrl) {
      lastUrl = window.location.href;
      setTimeout(scrapeCurrentPage, 2000);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
})();
