/**
 * TikTok Drama Downloader Content Script (Manifest V3)
 * Human-like Randomized Delays & Live Scanning Feedback.
 */
(function initTikTokDramaExtension() {
  const BRIDGE_URL = 'http://127.0.0.1:54321';
  let floatingBtn = null;

  const randomDelay = (min, max) => new Promise(resolve => {
    const ms = Math.floor(Math.random() * (max - min + 1)) + min;
    setTimeout(resolve, ms);
  });

  const triggerClick = (el) => {
    ['mousedown', 'mouseup', 'click'].forEach(eventType => {
      el.dispatchEvent(new MouseEvent(eventType, { view: window, bubbles: true, cancelable: true }));
    });
  };

  function createFloatingButton() {
    if (document.getElementById('tt-drama-dl-btn')) return;

    floatingBtn = document.createElement('div');
    floatingBtn.id = 'tt-drama-dl-btn';
    floatingBtn.style.cssText = `
      position: fixed;
      bottom: 28px;
      right: 28px;
      z-index: 9999999;
      background: #090d16;
      color: #06b6d4;
      border: 1px solid #1e293b;
      padding: 12px 20px;
      border-radius: 30px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.7);
      display: flex;
      align-items: center;
      gap: 10px;
      cursor: pointer;
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 14px;
      font-weight: 700;
      transition: all 0.2s ease;
      user-select: none;
    `;
    floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;

    floatingBtn.onmouseenter = () => {
      floatingBtn.style.transform = 'scale(1.05)';
      floatingBtn.style.borderColor = '#06b6d4';
      floatingBtn.style.boxShadow = '0 8px 35px rgba(6,182,212,0.4)';
    };
    floatingBtn.onmouseleave = () => {
      floatingBtn.style.transform = 'scale(1)';
      floatingBtn.style.borderColor = '#1e293b';
      floatingBtn.style.boxShadow = '0 8px 30px rgba(0,0,0,0.7)';
    };

    floatingBtn.onclick = runExtractionAndSend;
    document.body.appendChild(floatingBtn);
  }

  async function runExtractionAndSend() {
    if (!floatingBtn) return;
    floatingBtn.innerHTML = `<span>⏳</span> <span>Locating Episodes...</span>`;

    try {
      const results = [];

      // 1. Find Episodes Section
      const episodeHeader = Array.from(document.querySelectorAll('*'))
        .find(el => el.textContent?.trim() === 'Episodes' && el.children.length === 0);

      if (!episodeHeader) {
        alert('⚠️ Episodes section not found! Please make sure you are on the "About" tab of a TikTok Drama series.');
        floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;
        return;
      }

      const episodesContainer = episodeHeader.parentElement;

      // 2. Scan Tab Ranges (e.g. 1-24, 25-48...)
      const getTabs = () => Array.from(episodesContainer.querySelectorAll('*'))
        .filter(el => /^\d+-\d+$/.test(el.textContent?.trim()) && el.children.length === 0);

      let tabs = getTabs();
      if (tabs.length === 0) tabs = [null];

      for (let t = 0; t < tabs.length; t++) {
        const currentTabs = getTabs();
        if (currentTabs[t]) {
          floatingBtn.innerHTML = `<span>📑</span> <span>Tab ${t + 1}/${tabs.length}...</span>`;
          triggerClick(currentTabs[t]);
          // Human-like random delay for tab transition
          await randomDelay(650, 950);
        }

        // Auto-scroll episode container to mount virtualized lazy elements
        if (episodesContainer && episodesContainer.scrollHeight > episodesContainer.clientHeight) {
          episodesContainer.scrollTop = episodesContainer.scrollHeight;
          await randomDelay(150, 300);
          episodesContainer.scrollTop = 0;
          await randomDelay(100, 200);
        }

        // 3. Scan Episode Buttons
        const epElements = Array.from(episodesContainer.querySelectorAll('*'))
          .filter(el => {
            const text = el.textContent?.trim();
            return /^\d+$/.test(text) && 
                   el.children.length === 0 && 
                   el.getBoundingClientRect().height > 0 &&
                   parseInt(text) <= 500;
          });

        for (let i = 0; i < epElements.length; i++) {
          const el = epElements[i];
          const epNum = parseInt(el.textContent.trim());

          floatingBtn.innerHTML = `<span>⏳</span> <span>Ep ${epNum} (Paced)...</span>`;

          const parentLink = el.closest('a') || el.querySelector('a') || el.parentElement?.closest('a');
          let targetUrl = parentLink ? parentLink.href : '';

          if (!targetUrl) {
            triggerClick(el);
            // Human-like random delay for router settling
            await randomDelay(550, 850); 
            targetUrl = window.location.href;
          } else {
            // Resting pace between reads
            await randomDelay(100, 200);
          }

          if (targetUrl && !results.some(item => item.episode === epNum)) {
            results.push({ episode: epNum, url: targetUrl, label: "Ep " + epNum });
          }
        }
      }

      results.sort((a, b) => a.episode - b.episode);
      const urlsArray = results.map(item => item.url);

      if (results.length === 0) {
        alert('⚠️ No episodes detected. Please make sure episode buttons are visible on screen.');
        floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;
        return;
      }

      // Extract Drama Title from Page
      let dramaTitle = '';
      const titleSelectors = ['[data-e2e="series-title"]', 'h1', 'h2', '[data-e2e="user-title"]', '.series-title', '.drama-title'];
      for (const sel of titleSelectors) {
        const el = document.querySelector(sel);
        if (el && el.textContent?.trim()) {
          const txt = el.textContent.trim();
          if (txt && !/^\d+$/.test(txt) && txt !== 'Episodes' && txt !== 'About') {
            dramaTitle = txt;
            break;
          }
        }
      }
      if (!dramaTitle) {
        dramaTitle = document.title.replace(/\|.*$/, '').replace(/-.*$/, '').trim();
      }
      dramaTitle = dramaTitle.replace(/[\\/:*?"<>|]/g, '_').trim();

      floatingBtn.innerHTML = `<span>📤</span> <span>Sending ${results.length} Ep to App...</span>`;

      // Transmit Structured JSON to Local Bridge
      try {
        const resp = await fetch(`${BRIDGE_URL}/api/receive-links`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: dramaTitle,
            total_episodes: results.length,
            episodes: results,
            urls: urlsArray
          })
        });
        const data = await resp.json();

        if (data.status === 'success') {
          floatingBtn.innerHTML = `<span>✅</span> <span>Sent ${results.length} Episodes!</span>`;
          floatingBtn.style.borderColor = '#10b981';
          floatingBtn.style.color = '#34d399';
          setTimeout(() => {
            floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;
            floatingBtn.style.borderColor = '#1e293b';
            floatingBtn.style.color = '#06b6d4';
          }, 3500);
        } else {
          alert('Bridge Error: ' + JSON.stringify(data));
          floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;
        }
      } catch (err) {
        navigator.clipboard.writeText(urlsArray.join('\n'));
        alert(`⚠️ Could not reach Desktop App (http://127.0.0.1:54321).\n\nCopied ${urlsArray.length} episode links to clipboard!`);
        floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;
      }

    } catch (ex) {
      alert('Scanning error: ' + ex.message);
      floatingBtn.innerHTML = `<span>🚀</span> <span>Send Drama to App</span>`;
    }
  }

  // Periodic check to show floating button on drama series pages
  setInterval(() => {
    const hasEpisodes = Array.from(document.querySelectorAll('*')).some(e => e.textContent?.trim() === 'Episodes' && e.children.length === 0);
    if (hasEpisodes) {
      createFloatingButton();
    }
  }, 2000);
})();
