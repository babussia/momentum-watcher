console.log("⚡ momentum.js LOADED");

const momentumBody = document.getElementById("momentum-body");

// track which symbols already auto-loaded
const autoLoadedSymbols = new Set();


// seen momentum EVENTS (symbol + timestamp)
const seenEventIds = new Set();

// last % per symbol (for increase detection)
const lastMomentumPct = {};

// preload sound
const momentumSound = new Audio("/static/sounds/momentum.mp3");
momentumSound.volume = 0.6;

// unlock audio on first user interaction
document.addEventListener(
  "click",
  () => {
    momentumSound.play().catch(() => {});
  },
  { once: true }
);

// format helpers
function fmtVol(v) {
  if (!v) return "—";
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(1) + "K";
  return v;
}

async function updateMomentum() {
  try {
    const res = await fetch("/momentum/data");
    if (!res.ok) return;

    const data = await res.json();
    if (!Array.isArray(data)) return;

    for (const row of data) {
      const eventId = `${row.symbol}-${row.ts}`;

      // ❌ already processed
      if (seenEventIds.has(eventId)) continue;
      seenEventIds.add(eventId);

      // 🚀 AUTO-LOAD OVERVIEW + NEWS ON FIRST MOMENTUM APPEARANCE
        if (!autoLoadedSymbols.has(row.symbol)) {
        autoLoadedSymbols.add(row.symbol);

        console.log("🚀 Auto-loading details for:", row.symbol);

        // small delay = smoother UX (optional but recommended)
        setTimeout(() => {
            fetchStockDetails(row.symbol);
        }, 150);
        }


      const prevPct = lastMomentumPct[row.symbol];
      const currPct = row.chg;

      // 🔊 sound logic
      let playSound = false;

      // new symbol OR stronger momentum
      if (prevPct === undefined || currPct > prevPct) {
        playSound = true;
      }

      if (playSound) {
        momentumSound.currentTime = 0;
        momentumSound.play().catch(() => {});
      }

      lastMomentumPct[row.symbol] = currPct;

      const tr = document.createElement("tr");
      tr.className =
        "hover:bg-slate-800 cursor-pointer momentum-flash";

      tr.innerHTML = `
        <td class="py-1 pr-2">
          <span
            class="text-sky-400 hover:underline font-semibold momentum-symbol"
            data-symbol="${row.symbol}"
          >
            ${row.symbol}
          </span>
        </td>
        <td class="py-1 pr-2">${row.price}</td>
        <td class="py-1 pr-2 text-green-400">${row.chg}%</td>
        <td class="py-1 pr-2">${row.five_min}%</td>
        <td class="py-1 pr-2">—</td>
        <td class="py-1 pr-2">${fmtVol(row.volume)}</td>
        <td class="py-1 pr-2">${row.spread ?? "—"}</td>
        <td class="py-1">${row.time}</td>
      `;

      // 🔝 newest on top
      momentumBody.prepend(tr);

      // 🧹 hard cap: ONLY 15 ROWS
      while (momentumBody.children.length > 15) {
        momentumBody.removeChild(momentumBody.lastChild);
      }
    }
  } catch (err) {
    console.error("Momentum update failed:", err);
  }
}

// click handler (same as HOD)
// document.addEventListener("click", (e) => {
//   const el = e.target.closest(".momentum-symbol");
//   if (!el) return;

//   const symbol = el.dataset.symbol;
//   console.log("📈 Momentum click:", symbol);
//   fetchStockDetails(symbol);
//   sendToTradeZero(symbol); 
// });

// document.addEventListener("click", (e) => {
//   const el = e.target.closest(".momentum-symbol");
//   if (!el) return;

//   const symbol = el.dataset.symbol;
//   console.log("📈 Momentum click:", symbol);

//   fetchStockDetails(symbol);
//   sendToTradeZero(target.dataset.symbol);
// });
document.addEventListener("click", (e) => {
  const el = e.target.closest(".momentum-symbol");
  if (!el) return;

  const symbol = el.dataset.symbol;
  console.log("📈 Momentum click:", symbol);

  // 1️⃣ show overview + news + charts
  fetchStockDetails(symbol);

  // 2️⃣ send to TradeZero Market Depth
  sendToTradeZero(symbol);
});


setInterval(updateMomentum, 1000);
updateMomentum();