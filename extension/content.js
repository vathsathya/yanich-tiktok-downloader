/**
 * TikTok Drama Episode Extractor & Bridge Client
 * Standardized string concatenation, 0-syntax errors on any browser or bookmarklet.
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

  var oldModal = document.getElementById("tt-extractor-modal");
  if (oldModal) oldModal.remove();
  var oldToast = document.getElementById("tt-scan-toast");
  if (oldToast) oldToast.remove();

  var toast = document.createElement("div");
  toast.id = "tt-scan-toast";
  toast.style.cssText = "position:fixed;top:24px;right:24px;z-index:2147483647;background:#090d16;color:#06b6d4;border:1px solid #1e293b;border-radius:30px;padding:12px 24px;font-family:system-ui,-apple-system,sans-serif;font-size:13px;font-weight:700;box-shadow:0 8px 30px rgba(0,0,0,0.8);display:flex;align-items:center;gap:8px;";
  document.body.appendChild(toast);

  var updateToast = function(msg) {
    if (toast) toast.innerHTML = msg;
  };

  updateToast("<span>⏳</span> <span>Locating Episodes...</span>");

  // Instant Drama API Fetcher using signed performance entries or direct API
  try {
    var perfEntries = window.performance ? window.performance.getEntriesByType("resource") : [];
    var signedUrl = "";
    for (var p = perfEntries.length - 1; p >= 0; p--) {
      if (perfEntries[p].name && perfEntries[p].name.includes("/api/drama/episode/item_list/")) {
        signedUrl = perfEntries[p].name;
        break;
      }
    }

    var baseApiUrl = "";
    if (signedUrl) {
      baseApiUrl = signedUrl.replace(/count=\d+/, "count=100");
    } else {
      var dramaIdMatch = window.location.pathname.match(/\/episode\/(\d+)/) || window.location.pathname.match(/\/shortdrama\/(\d+)/);
      if (dramaIdMatch && dramaIdMatch[1]) {
        baseApiUrl = "/api/drama/episode/item_list/?drama_id=" + dramaIdMatch[1] + "&count=100";
      }
    }

    if (baseApiUrl) {
      updateToast("<span>⚡</span> <span>Instant Fetching All Episodes via Drama API...</span>");
      var cursor = 0;
      var hasMore = true;
      var pageCount = 0;

      while (hasMore && pageCount < 5) {
        pageCount++;
        var curUrl = baseApiUrl.includes("cursor=") ? baseApiUrl.replace(/cursor=\d+/, "cursor=" + cursor) : baseApiUrl + "&cursor=" + cursor;
        var apiResp = await fetch(curUrl, { credentials: "include" });
        if (!apiResp.ok) break;

        var apiJson = await apiResp.json();
        var itemList = (apiJson && apiJson.itemList) || [];
        if (itemList.length === 0) break;

        for (var idx = 0; idx < itemList.length; idx++) {
          var item = itemList[idx];
          var epNum = (item.dramaInfo && item.dramaInfo.dramaEpisodeNumber) || (results.length + 1);
          var authorName = (item.author && item.author.uniqueId) || "tiktok";
          var videoId = item.id;
          var canonicalUrl = "https://www.tiktok.com/@" + authorName + "/video/" + videoId;
          var covUrl = (item.video && item.video.cover && item.video.cover.urlList && item.video.cover.urlList[0]) || "";
          var vUrl = (item.video && item.video.playAddr) || "";

          var exists = false;
          for (var r = 0; r < results.length; r++) {
            if (results[r].episode === epNum || results[r].url === canonicalUrl) { exists = true; break; }
          }
          if (!exists) {
            results.push({
              episode: epNum,
              url: canonicalUrl,
              video_url: vUrl,
              cover_url: covUrl,
              label: "Ep " + epNum
            });
          }
        }

        if (apiJson.hasMore && apiJson.cursor !== undefined && apiJson.cursor !== cursor) {
          cursor = apiJson.cursor;
        } else {
          hasMore = false;
        }
      }
    }
  } catch (e) {}

  if (results.length === 0) {
    var allElems = Array.from(document.querySelectorAll("*"));
    var header = allElems.find(function(e) {
      return (e.textContent || "").trim() === "Episodes" && e.children.length === 0;
    });

    if (!header) {
      if (toast) toast.remove();
      alert("⚠️ Episodes section not found! Please open the 'About' tab of a TikTok drama series.");
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

  var getDirectVideoUrl = function() {
    var vidElem = document.querySelector("video");
    if (vidElem) {
      var src = vidElem.src || vidElem.currentSrc || "";
      if (src && !src.startsWith("blob:") && src.startsWith("http")) {
        return src;
      }
    }
    try {
      var entries = window.performance.getEntriesByType("resource");
      for (var i = entries.length - 1; i >= 0; i--) {
        var name = entries[i].name || "";
        if (name.startsWith("http") && 
            (name.includes("tiktokcdn.com") || name.includes("byteoversea.com") || name.includes("/video/tos/") || name.includes("v16-webapp") || name.includes("v19-webapp")) &&
            !name.match(/\.(jpg|jpeg|png|webp|gif|js|css|json)($|\?)/i)) {
          return name;
        }
      }
    } catch (e) {}
    
    try {
      var rehyEl = document.getElementById("__UNIVERSAL_DATA_FOR_REHYDRATION__");
      if (rehyEl && rehyEl.textContent) {
        var parsed = JSON.parse(rehyEl.textContent);
        var scopes = (parsed && parsed.__DEFAULT_SCOPE__) || {};
        var vdetail = scopes["webapp.video-detail"] || {};
        var istruct = (vdetail.itemInfo && vdetail.itemInfo.itemStruct) || {};
        var vinfo = istruct.video || {};
        var playAddr = vinfo.playAddr || vinfo.downloadAddr;
        if (playAddr && playAddr.startsWith("http")) return playAddr;
      }
    } catch (e) {}

    try {
      var scripts = document.querySelectorAll("script");
      for (var s = 0; s < scripts.length; s++) {
        var stext = scripts[s].textContent || "";
        var m = stext.match(/"playAddr"\s*:\s*"(https?:\\\/\\\/[^"]+)"/) || stext.match(/"downloadAddr"\s*:\s*"(https?:\\\/\\\/[^"]+)"/);
        if (m && m[1]) {
          return m[1].replace(/\\u002F/g, "/").replace(/\\\//g, "/");
        }
      }
    } catch (e) {}

    return "";
  };

  var getCoverUrl = function() {
    var coverElem = document.querySelector("video[poster], img.drama-cover, img.poster-img, [data-e2e=\"series-cover\"] img, [data-e2e=\"video-cover\"] img");
    if (coverElem) {
      var src = coverElem.getAttribute("poster") || coverElem.src || "";
      if (src && src.startsWith("http") && !src.startsWith("blob:")) return src;
    }
    try {
      var rehyEl = document.getElementById("__UNIVERSAL_DATA_FOR_REHYDRATION__");
      if (rehyEl && rehyEl.textContent) {
        var parsed = JSON.parse(rehyEl.textContent);
        var scopes = (parsed && parsed.__DEFAULT_SCOPE__) || {};
        var vdetail = scopes["webapp.video-detail"] || {};
        var istruct = (vdetail.itemInfo && vdetail.itemInfo.itemStruct) || {};
        var vinfo = istruct.video || {};
        var cov = vinfo.cover || vinfo.originCover || (istruct.author && istruct.author.avatarLarger);
        if (cov && cov.startsWith("http")) return cov;
      }
    } catch (e) {}
    return "";
  };

  for (var t = 0; t < tabs.length; t++) {
    var curr = getTabs();
    if (curr[t]) {
      updateToast("<span>📑</span> <span>Switching Episode Tab " + (t + 1) + "/" + tabs.length + "...</span>");
      triggerClick(curr[t]);
      await randomDelay(650, 950);
    }

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

      updateToast("<span>⏳</span> <span>Scanning Episode " + num + " (" + (i + 1) + "/" + eps.length + ")...</span>");

      if (!url) {
        triggerClick(el);
        document.querySelectorAll("video").forEach(function(v) { v.muted = true; try { v.pause(); } catch (e) {} });
        await randomDelay(550, 850);
        url = window.location.href;
      } else {
        await randomDelay(80, 160);
      }

      var directVideoUrl = getDirectVideoUrl();
      var coverUrl = getCoverUrl();

      var exists = false;
      for (var k = 0; k < results.length; k++) {
        if (results[k].episode === num) { exists = true; break; }
      }
      if (url && !exists) {
        results.push({ episode: num, url: url, video_url: directVideoUrl, cover_url: coverUrl, label: "Ep " + num });
      }
    }
  }
  }

  if (toast) toast.remove();

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
    dramaTitle = (document.title || "").replace(/\|.*$/, "").trim() || "TikTok Drama";
  }

  var sendToBridge = async function(statusElem) {
    if (statusElem) statusElem.innerHTML = "⏳ Sending to Desktop App (127.0.0.1:54321)...";

    var payload = { title: dramaTitle, total_episodes: results.length, episodes: results, urls: urls };
    var payloadStr = JSON.stringify(payload);

    // 1. Auto-copy URLs to clipboard as instant guarantee
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(urls.join("\n"));
      }
    } catch (e) {}

    // 2. Extension messaging (100% CSP-exempt via background service worker)
    if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.sendMessage) {
      try {
        var res = await new Promise(function(resolve) {
          chrome.runtime.sendMessage({
            action: "send_to_bridge",
            payload: payload
          }, resolve);
        });
        if (res && res.success && res.data && res.data.status === "success") {
          if (statusElem) {
            statusElem.innerHTML = "🟢 <b>Sent successfully!</b> Desktop App loaded " + results.length + " episodes.";
            statusElem.style.color = "#34d399";
          }
          return true;
        }
      } catch (e) {}
    }

    // 3. Hidden Form POST submission (100% CSP-compliant, zero fetch errors)
    try {
      var iframeName = "tt_bridge_frame_" + Date.now();
      var iframe = document.createElement("iframe");
      iframe.name = iframeName;
      iframe.style.cssText = "display:none;position:absolute;width:0;height:0;border:0;";
      document.body.appendChild(iframe);

      var form = document.createElement("form");
      form.target = iframeName;
      form.action = "http://127.0.0.1:54321/api/receive-links";
      form.method = "POST";
      form.enctype = "application/x-www-form-urlencoded";
      form.style.display = "none";

      var input = document.createElement("input");
      input.type = "hidden";
      input.name = "payload";
      input.value = payloadStr;
      form.appendChild(input);
      document.body.appendChild(form);

      form.submit();
      setTimeout(function() {
        try { form.remove(); iframe.remove(); } catch (e) {}
      }, 3000);

      if (statusElem) {
        statusElem.innerHTML = "🟢 <b>Sent to Desktop App!</b> (" + results.length + " episodes transferred & copied to clipboard)";
        statusElem.style.color = "#34d399";
      }
      return true;
    } catch (e) {}

    if (statusElem) {
      statusElem.innerHTML = "📋 <b>Links Copied to Clipboard!</b> Press <b>Ctrl+V</b> in Desktop App to load " + results.length + " episodes.";
      statusElem.style.color = "#38bdf8";
    }
    return false;
  };

  var modal = document.createElement("div");
  modal.id = "tt-extractor-modal";
  modal.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:2147483647;background:#0d1322;color:#f8fafc;border:1px solid #1e293b;border-radius:16px;padding:24px;width:90%;max-width:540px;box-shadow:0 25px 60px rgba(0,0,0,0.9);font-family:system-ui,-apple-system,sans-serif;";
  
  modal.innerHTML = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;border-bottom:1px solid #1e293b;padding-bottom:12px;">'
    + '<div>'
    + '<h2 style="margin:0;font-size:18px;color:#06b6d4;display:flex;align-items:center;gap:8px;">'
    + '<span>🎬</span> <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:380px;">' + dramaTitle + '</span>'
    + '</h2>'
    + '<div style="font-size:12px;color:#94a3b8;margin-top:4px;">Scanned <b>' + results.length + '</b> episodes successfully</div>'
    + '</div>'
    + '<button id="tt-modal-close" style="background:#1e293b;color:#94a3b8;border:none;width:32px;height:32px;border-radius:50%;cursor:pointer;font-size:16px;font-weight:bold;">✕</button>'
    + '</div>'
    + '<div id="tt-bridge-status" style="font-size:13px;padding:10px 14px;background:#090d16;border:1px solid #1e293b;border-radius:8px;margin-bottom:14px;color:#94a3b8;">'
    + '⏳ Connecting to Desktop App...'
    + '</div>'
    + '<textarea id="tt-urls-area" readonly style="width:100%;height:140px;background:#070b14;color:#38bdf8;border:1px solid #1e293b;border-radius:8px;padding:10px;font-family:monospace;font-size:11px;resize:vertical;box-sizing:border-box;outline:none;margin-bottom:16px;"></textarea>'
    + '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
    + '<button id="tt-btn-send" style="flex:1;min-width:140px;background:#06b6d4;color:#090d16;border:none;padding:10px 16px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:13px;box-shadow:0 4px 15px rgba(6,182,212,0.3);">'
    + '🚀 Send to Desktop App'
    + '</button>'
    + '<button id="tt-btn-copy" style="flex:1;min-width:130px;background:#1e293b;color:#f8fafc;border:1px solid #334155;padding:10px 16px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:13px;">'
    + '📋 Copy All URLs'
    + '</button>'
    + '<button id="tt-btn-download" style="background:#1e293b;color:#94a3b8;border:1px solid #334155;padding:10px 14px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:13px;" title="Download as text file">'
    + '💾 Save .txt'
    + '</button>'
    + '</div>';

  document.body.appendChild(modal);

  var urlsArea = document.getElementById("tt-urls-area");
  var statusBox = document.getElementById("tt-bridge-status");
  var btnSend = document.getElementById("tt-btn-send");
  var btnCopy = document.getElementById("tt-btn-copy");
  var btnDownload = document.getElementById("tt-btn-download");
  var btnClose = document.getElementById("tt-modal-close");

  urlsArea.value = urls.join("\n");

  btnClose.onclick = function() { modal.remove(); };
  btnSend.onclick = function() { sendToBridge(statusBox); };

  btnCopy.onclick = function() {
    urlsArea.select();
    try {
      navigator.clipboard.writeText(urls.join("\n"));
    } catch (e) {
      document.execCommand("copy");
    }
    btnCopy.textContent = "✅ Copied!";
    btnCopy.style.color = "#34d399";
    setTimeout(function() {
      btnCopy.textContent = "📋 Copy All URLs";
      btnCopy.style.color = "#f8fafc";
    }, 2000);
  };

  btnDownload.onclick = function() {
    var blob = new Blob([urls.join("\n")], { type: "text/plain;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = (dramaTitle.replace(/[^a-zA-Z0-9_\u1780-\u17FF]/g, "_") || "TikTok_Episodes") + ".txt";
    a.click();
  };

  await sendToBridge(statusBox);
})();
