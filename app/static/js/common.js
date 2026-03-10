function sendToTradeZero(symbol) {
  fetch("/ahk/symbol", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol })
  }).catch(() => {});
}