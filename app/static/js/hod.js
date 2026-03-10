console.log("📈 hod.js LOADED", window.__CHARTS_LOADED__);
// =======================
// High of Day (HOD) logic
// =======================

let sortDirection = "desc";
let lastData = {}; // store last state for diff checking

// ✅ Format volume numbers like 6.42M, 312K, etc.
function formatVolume(vol) {
  if (vol >= 1_000_000_000) return (vol / 1_000_000_000).toFixed(2) + "B";
  if (vol >= 1_000_000) return (vol / 1_000_000).toFixed(2) + "M";
  if (vol >= 1_000) return (vol / 1_000).toFixed(2) + "K";
  return vol.toString();
}

// ✅ Fetch and update HOD table
async function updateHOD() {
  try {
    const res = await fetch(window.location.origin + "/hod/data");
    const data = await res.json();
    const tbody = document.getElementById("hod-body");
    if (!tbody) return;

    if (!data.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="text-slate-500 text-center py-2">No data</td></tr>`;
      return;
    }

    // ✅ Sort data by % change every refresh
    data.sort((a, b) =>
      sortDirection === "desc" ? b.chg - a.chg : a.chg - b.chg
    );

    // ✅ Always rebuild full table on sort toggle or data change
    tbody.innerHTML = data
      .map(
        (s) => `
        <tr id="row-${s.symbol}">
          <td> <span class="hod-symbol cursor-pointer text-sky-400 hover:underline" data-symbol="${s.symbol}">${s.symbol}</span></td>
          <td id="price-${s.symbol}">${s.price.toFixed(2)}</td>
          <td id="chg-${s.symbol}" class="${
            s.chg > 0
              ? "text-green-400"
              : s.chg < 0
              ? "text-red-400"
              : ""
          }">${s.chg.toFixed(2)}%</td>
          <td>${s.float}</td>
          <td>${s.spread}</td>
          <td id="vol-${s.symbol}">${formatVolume(s.volume)}</td>
          <td id="time-${s.symbol}">${s.time}</td>
        </tr>`
      )
      .join("");

    // ✅ Save last data state
    data.forEach((s) => (lastData[s.symbol] = s));
  } catch (err) {
    console.error("Error fetching HOD data:", err);
  }
}

// document.addEventListener("click", (e) => {
//   const target = e.target.closest(".hod-symbol");
//   if (!target) return;

//   console.log("🖱 Clicked symbol:", target.dataset.symbol);

//   fetchStockDetails(target.dataset.symbol);
//   sendToTradeZero(symbol);
// });

document.addEventListener("click", (e) => {
  const target = e.target.closest(".hod-symbol");
  if (!target) return;

  const symbol = target.dataset.symbol; // ✅ THIS WAS MISSING
  if (!symbol) return;

  console.log("🖱 Clicked symbol:", symbol);

  fetchStockDetails(symbol);
  sendToTradeZero(target.dataset.symbol);
});




// === Auto refresh every 3s ===
setInterval(updateHOD, 3000);
updateHOD();

// === Sort toggle on % Chg header ===
document.addEventListener("DOMContentLoaded", () => {
  const hodTable = document.querySelector("#hod-body")?.closest("table");
  if (!hodTable) return;

  const chgHeader = Array.from(hodTable.querySelectorAll("th")).find((th) =>
    th.textContent.trim().includes("% Chg")
  );

  if (!chgHeader) return;

  // add visual arrow + click listener
  const updateArrow = () => {
    chgHeader.textContent = sortDirection === "desc" ? "% Chg ↓" : "% Chg ↑";
  };

  chgHeader.style.cursor = "pointer";
  updateArrow();

  chgHeader.addEventListener("click", () => {
    sortDirection = sortDirection === "desc" ? "asc" : "desc";
    updateArrow();
    updateHOD();
  });
});

// async function fetchStockDetails(symbol) {
//   console.log("📈 fetchStockDetails called for:", symbol);

//   showStockLoading(symbol);

//   // 🔥 THIS is what was missing
//   renderTradingViewChart("chart-1m", `NASDAQ:${symbol}`, "1");
//   renderTradingViewChart("chart-5m", `NASDAQ:${symbol}`, "5");

//   // Let the DOM paint charts first
//   await new Promise(requestAnimationFrame);

//   try {
//     const res = await fetch(`/news-overview/${symbol}`);
//     const data = await res.json();

//     renderStockOverview(data);
//     renderStockNews(data);
//   } catch (err) {
//     console.error(err);
//   }
// }
async function fetchStockDetails(symbol) {
  console.log("📊 fetchStockDetails:", symbol);

  showStockLoading(symbol);

  try {
    const res = await fetch(`/news-overview/${symbol}`);
    if (!res.ok) throw new Error("Failed to load stock data");

    const data = await res.json();

    // 1️⃣ Render text content first
    renderStockOverview(data);
    renderStockNews(data);

    // 2️⃣ THEN render charts (THIS was missing)
    renderTradingViewChart("chart-1m", `NASDAQ:${symbol}`, "1");
    renderTradingViewChart("chart-5m", `NASDAQ:${symbol}`, "5");

  } catch (err) {
    console.error("❌ fetchStockDetails error:", err);
  }
}




// =======================
// Render functions
// =======================
function renderStockOverview(data) {
  const el = document.getElementById("overview");
  if (!el) return;

  el.innerHTML = `
    <div class="space-y-1">
      <div><span class="text-slate-500">Symbol:</span> <span class="text-slate-200 font-semibold">${data.symbol}</span></div>
      <div><span class="text-slate-500">Market Cap:</span> <span class="text-slate-200">${data.market_cap || "—"}</span></div>
      <div><span class="text-slate-500">Float:</span> <span class="text-slate-200">${data.float || "—"}</span></div>
      <div><span class="text-slate-500">Short %:</span> <span class="text-slate-200">${data.short_percent || "—"}</span></div>
      <div><span class="text-slate-500">Sector:</span> <span class="text-slate-200">${data.sector || "—"}</span></div>
      <div><span class="text-slate-500">Industry:</span> <span class="text-slate-200">${data.industry || "—"}</span></div>
      <div><span class="text-slate-500">Country:</span> <span class="text-slate-200">${data.country || "—"}</span></div>
    </div>
  `;
}



function renderStockNews(data) {
  const el = document.getElementById("news");
  if (!el) return;

  const fullText = data.news_content || "";
  const previewLen = 700;
  const isLong = fullText.length > previewLen;

  const preview = isLong
    ? fullText.slice(0, previewLen) + "…"
    : fullText;

  el.innerHTML = `
    <div class="font-semibold text-slate-200">
      ${data.news_title || "No headline available"}
    </div>

    <div class="text-xs text-slate-500 mb-2">
      ${data.news_date || ""} ${data.news_time || ""}
    </div>

    ${
      data.summary
        ? `<div class="mb-2 text-slate-300">${data.summary}</div>`
        : ""
    }

    <div id="news-text"
         class="leading-relaxed"
         data-expanded="false"
         data-preview="${encodeURIComponent(preview)}"
         data-full="${encodeURIComponent(fullText)}">
      ${preview}
    </div>

    ${
      isLong
        ? `<button id="toggle-news"
                   class="mt-2 text-sky-400 hover:underline text-xs">
              Show more
           </button>`
        : ""
    }
  `;

  const btn = document.getElementById("toggle-news");
  const text = document.getElementById("news-text");

  if (btn && text) {
    btn.addEventListener("click", () => {
      const expanded = text.dataset.expanded === "true";

      if (expanded) {
        text.innerText = decodeURIComponent(text.dataset.preview);
        btn.innerText = "Show more";
        text.dataset.expanded = "false";
      } else {
        text.innerText = decodeURIComponent(text.dataset.full);
        btn.innerText = "Show less";
        text.dataset.expanded = "true";
      }
    });
  }
}

function showStockLoading(symbol) {
  const overview = document.getElementById("overview");
  const news = document.getElementById("news");

  if (overview) {
    overview.innerHTML = `
      <div class="animate-pulse text-slate-400">
        Loading overview for
        <span class="text-sky-400 font-semibold">${symbol}</span>…
      </div>
    `;
  }

  if (news) {
    news.innerHTML = `
      <div class="animate-pulse text-slate-400 mb-2">
        Loading news for
        <span class="text-sky-400 font-semibold">${symbol}</span>…
      </div>

      <div class="animate-pulse space-y-2">
        <div class="h-4 bg-slate-700 rounded w-3/4"></div>
        <div class="h-3 bg-slate-700 rounded w-full"></div>
        <div class="h-3 bg-slate-700 rounded w-5/6"></div>
      </div>
    `;
  }
}

