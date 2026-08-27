/**
 * TikTok Drama Episode Extractor & Bridge Client
 * Human-like Randomized Delays & Live Scanning Feedback.
 */
(async function getTikTokEpisodesAndBridge() {
  var results = [];
  var randomDelay = function(min, max) {
    return new Promise(function(resolve) {
      var ms = Math.floor(Math.random() * (max - min + 1)) + min;
      setTimeout(resolve, ms);
    });
  };

  var triggerClick = function(el) {
    ["mousedown", "mouseup", "click"].forEach(function(t) {
      el.dispatchEvent(new MouseEvent(t, { view: window, bubbles: true, cancelable: true }));
    });
  };

  // Create or update floating scanner toast on screen
  var toast = document.getElementById("tt-scan-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "tt-scan-toast";
    toast.style.cssText = "position:fixed;top:24px;right:24px;z-index:99999999;background:#090d16;color:#06b6d4;border:1px solid #1e293b;border-radius:30px;padding:12px 24px;font-family:system-ui,-apple-system,sans-serif;font-size:13px;font-weight:700;box-shadow:0 8px 30px rgba(0,0,0,0.8);display:flex;align-items:center;gap:8px;";
    document.body.appendChild(toast);
  }
  var updateToast = function(msg) {
    if (toast) toast.innerHTML = msg;
  };

  updateToast("<span>⏳</span> <span>Locating Episodes...</span>");

  var allElems = Array.from(document.querySelectorAll("*"));
  var header = allElems.find(function(e) {
    return (e.textContent || "").trim() === "Episodes" && e.children.length === 0;
  });

  if (!header) {
    if (toast) toast.remove();
    alert("⚠️ Episodes section not found! Please make sure you are on the About tab of a TikTok drama series.");
    return;
  }

  var container = header.parentElement;
  var getTabs = function() {
    return Array.from(container.querySelectorAll("*")).filter(function(e) {
      return /^\d+-\d+$/.test((e.textContent || "").trim()) && e.children.length === 0;
    });
  };

  var tabs = getTabs();
  if (tabs.length === 0) tabs = [null];

  for (var t = 0; t < tabs.length; t++) {
    var curr = getTabs();
    if (curr[t]) {
      updateToast("<span>📑</span> <span>Switching Episode Tab " + (t + 1) + "/" + tabs.length + "...</span>");
      triggerClick(curr[t]);
      // Human-like random delay for tab transition
      await randomDelay(650, 950);
    }

    // Auto-scroll episode container to mount virtualized lazy elements
    if (container && container.scrollHeight > container.clientHeight) {
      container.scrollTop = container.scrollHeight;
      await randomDelay(150, 300);
      container.scrollTop = 0;
      await randomDelay(100, 200);
    }

    var eps = Array.from(container.querySelectorAll("*")).filter(function(e) {
      var txt = (e.textContent || "").trim();
      return /^\d+$/.test(txt) && e.children.length === 0 && e.getBoundingClientRect().height > 0 && parseInt(txt, 10) <= 500;
    });

    for (var i = 0; i < eps.length; i++) {
      var el = eps[i];
      var num = parseInt((el.textContent || "").trim(), 10);
      var plink = el.closest("a") || el.querySelector("a") || (el.parentElement ? el.parentElement.closest("a") : null);
      var url = plink ? plink.href : "";

      updateToast("<span>⏳</span> <span>Scanning Episode " + num + " (Paced)...</span>");

      if (!url) {
        triggerClick(el);
        // Human-like random delay for single-page router settling
        await randomDelay(550, 850);
        url = window.location.href;
      } else {
        // Subtle resting pace between element reads
        await randomDelay(100, 200);
      }

      var exists = false;
      for (var k = 0; k < results.length; k++) {
        if (results[k].episode === num) { exists = true; break; }
      }
      if (url && !exists) {
        results.push({ episode: num, url: url, label: "Ep " + num });
      }
    }
  }

  results.sort(function(a, b) { return a.episode - b.episode; });
  var urls = results.map(function(item) { return item.url; });

  var dramaTitle = "";
  var selectors = ["[data-e2e=\"series-title\"]", "h1", "h2", ".series-title", ".drama-title"];
  for (var s = 0; s < selectors.length; s++) {
    var selEl = document.querySelector(selectors[s]);
    if (selEl && (selEl.textContent || "").trim()) {
      var txtVal = (selEl.textContent || "").trim();
      if (txtVal && !/^\d+$/.test(txtVal) && txtVal !== "Episodes" && txtVal !== "About") {
        dramaTitle = txtVal;
        break;
      }
    }
  }
  if (!dramaTitle) {
    dramaTitle = (document.title || "").replace(/\|.*$/, "").trim();
  }

  updateToast("<span>📤</span> <span>Sending " + results.length + " Episodes to App...</span>");

  try {
    var resp = await fetch("http://127.0.0.1:54321/api/receive-links", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: dramaTitle, total_episodes: results.length, episodes: results, urls: urls })
    });
    var d = await resp.json();
    if (d.status === "success") {
      updateToast("<span style='color:#34d399;'>✅ Sent " + results.length + " Episodes to App!</span>");
      setTimeout(function() { if (toast) toast.remove(); }, 3000);
      return;
    }
  } catch (err) {}

  if (toast) toast.remove();
  navigator.clipboard.writeText(urls.join(String.fromCharCode(10)));
  alert("Scanned " + results.length + " episodes! (Copied to clipboard because Desktop App is offline)");
})();
