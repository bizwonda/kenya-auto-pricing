// Popup UI logic

const el = (id) => document.getElementById(id);

// --- Load state ---
async function refreshUI() {
  const { listings = [] } = await chrome.storage.local.get({ listings: [] });

  el("totalCount").textContent = listings.length;

  // Source breakdown
  const bySource = {};
  listings.forEach((l) => {
    const src = l.source || "Unknown";
    bySource[src] = (bySource[src] || 0) + 1;
  });

  const sourceList = el("sourceList");
  sourceList.innerHTML = Object.entries(bySource)
    .sort((a, b) => b[1] - a[1])
    .map(
      ([name, count]) => `
      <div class="source-item">
        <span class="source-name">${name}</span>
        <span class="source-count">${count}</span>
      </div>`
    )
    .join("");

  // Model preview (top 10 most collected)
  const byModel = {};
  listings.forEach((l) => {
    const key = `${l.make || "?"} ${l.model || "?"}`;
    byModel[key] = (byModel[key] || 0) + 1;
  });
  const topModels = Object.entries(byModel)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);

  const preview = el("modelPreview");
  if (topModels.length > 0) {
    preview.innerHTML = `<div style="font-size:11px;color:#888;margin-bottom:6px">Top models collected</div>`
      + topModels
        .map(([name, count]) => `<div><b>${name}</b> — ${count} listings</div>`)
        .join("");
  }

  // Active site
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url) {
      const url = new URL(tab.url);
      const host = url.hostname.replace("www.", "");
      const known = {
        "cheki.co.ke": "✅ On Cheki Kenya",
        "jiji.co.ke": "✅ On Jiji Kenya",
        "pigiame.co.ke": "✅ On PigiaMe",
        "sbtjapan.com": "✅ On SBT Japan",
        "tradecarview.com": "✅ On TradeCarView",
      };
      el("activeSite").textContent = known[host] || `🌐 ${host}`;
    }
  } catch (e) {
    el("activeSite").textContent = "Open a car site";
  }
}

// --- Scrape current page ---
el("scrapeBtn").addEventListener("click", async () => {
  el("status").textContent = "Scanning...";
  el("status").className = "";

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      el("status").textContent = "No active tab";
      return;
    }

    const response = await chrome.tabs.sendMessage(tab.id, { action: "scrapeNow" });
    if (response?.ok) {
      el("status").textContent = "✅ Scraped! Check the page for results.";
      el("status").className = "good";
    } else {
      el("status").textContent = "Open a supported car site first";
    }

    setTimeout(refreshUI, 500);
  } catch (e) {
    el("status").textContent = "Open Cheki, Jiji, PigiaMe, or SBT Japan";
  }
});

// --- Export JSON ---
el("exportJson").addEventListener("click", async () => {
  const { listings = [] } = await chrome.storage.local.get({ listings: [] });
  if (listings.length === 0) {
    el("status").textContent = "No data to export";
    return;
  }

  const json = JSON.stringify(listings, null, 2);
  const blob = new Blob([json], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = `kenya-car-listings-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);

  el("status").textContent = `✅ Exported ${listings.length} listings as JSON`;
  el("status").className = "good";
});

// --- Export CSV ---
el("exportCsv").addEventListener("click", async () => {
  const { listings = [] } = await chrome.storage.local.get({ listings: [] });
  if (listings.length === 0) {
    el("status").textContent = "No data to export";
    return;
  }

  const headers = [
    "source", "make", "model", "year", "mileage_km", "engine_cc",
    "transmission", "price_kes", "price_usd", "location", "url", "scraped_at",
  ];

  const rows = listings.map((l) =>
    headers
      .map((h) => {
        const v = l[h];
        if (v === null || v === undefined) return "";
        if (typeof v === "string" && v.includes(",")) return `"${v}"`;
        return String(v);
      })
      .join(",")
  );

  const csv = [headers.join(","), ...rows].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  a.download = `kenya-car-listings-${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);

  el("status").textContent = `✅ Exported ${listings.length} listings as CSV`;
  el("status").className = "good";
});

// --- Clear ---
el("clearBtn").addEventListener("click", async () => {
  if (!confirm("Delete all collected listings?")) return;

  await chrome.storage.local.set({ listings: [] });
  chrome.action.setBadgeText({ text: "" });
  await refreshUI();
  el("status").textContent = "Cleared";
});

// --- Init ---
refreshUI();

// Listen for storage changes
chrome.storage.onChanged.addListener((changes) => {
  if (changes.listings) refreshUI();
});
