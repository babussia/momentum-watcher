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
          <td>${s.symbol}</td>
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

