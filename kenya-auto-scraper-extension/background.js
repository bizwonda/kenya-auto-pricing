// Background service worker
// Manages badge updates and cross-tab communication

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.action === "updateBadge") {
    const count = msg.count || 0;
    const text = count > 999 ? "999+" : String(count);
    chrome.action.setBadgeText({ text: text, tabId: sender.tab?.id });
    chrome.action.setBadgeBackgroundColor({ color: "#00c853" });

    if (msg.newCount > 0) {
      chrome.action.setBadgeText({ text: text });
      // Flash effect — briefly set to a brighter color
      chrome.action.setBadgeBackgroundColor({ color: "#00e676" });
      setTimeout(() => {
        chrome.action.setBadgeBackgroundColor({ color: "#00c853" });
      }, 2000);
    }
  }
  return true;
});

// Initialize badge on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.get({ listings: [] }, (data) => {
    const count = (data.listings || []).length;
    if (count > 0) {
      chrome.action.setBadgeText({ text: String(count) });
      chrome.action.setBadgeBackgroundColor({ color: "#00c853" });
    }
  });
});
