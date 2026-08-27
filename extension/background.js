/**
 * TikTok Drama Downloader Extension Background Service Worker
 * Acts as an elevated proxy to communicate with localhost Desktop App without CSP/PNA blocking.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "send_to_bridge") {
    fetch("http://127.0.0.1:54321/api/receive-links", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload)
    })
      .then(resp => resp.json())
      .then(data => sendResponse({ success: true, data: data }))
      .catch(err => sendResponse({ success: false, error: err.message }));
    return true; // Keep message channel open for async response
  }
});
