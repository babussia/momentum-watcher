console.log("📊 charts.js LOADED");
window.__CHARTS_LOADED__ = true;

function renderTradingViewChart(containerId, symbol, interval) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = "";

  new TradingView.widget({
    container_id: containerId,

    symbol,
    interval,
    timezone: "America/New_York",
    theme: "dark",
    style: 1, // candles

    // ✅ KEEP YOUR SIZE LOGIC EXACTLY
    autosize: false,
    width: "100%",
    height: "100%",

    hide_top_toolbar: true,
    hide_side_toolbar: true,
    allow_symbol_change: false,

    // ✅ IMPORTANT:
    // The embed widget often cannot load tv-basicstudies by id in this context,
    // which causes "Cannot get study" and "has no plot/input" spam.
    // So we remove studies + studies_overrides completely to stop errors.
    studies: [],

    // ✅ Remove invalid overrides for studies (caused the errors)
    // studies_overrides: {},

    overrides: {
      "paneProperties.background": "#0b1220",
      "paneProperties.vertGridProperties.color": "#1e293b",
      "paneProperties.horzGridProperties.color": "#1e293b",

      "mainSeriesProperties.candleStyle.upColor": "#26a69a",
      "mainSeriesProperties.candleStyle.downColor": "#ef5350",

      "scalesProperties.textColor": "#94a3b8",
      "symbolWatermarkProperties.transparency": 90,
    },

    // ✅ Optional: reduces extra internal chatter / UI elements
    hide_legend: false,
    withdateranges: true,
  });
}

