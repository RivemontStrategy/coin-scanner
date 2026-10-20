// Filters, sorting, chip details, live prices, "updated N min ago" and the theme switch. No tracking: the only
// requests are to public exchange price endpoints (Binance's data mirror, OKX as a fallback).
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var LIVE_MS = 45000;

  // ---------------------------------------------------------------- theme
  var tb = document.querySelector(".theme");
  if (tb) tb.addEventListener("click", function () {
    var d = document.documentElement, t = d.dataset.theme === "dark" ? "light" : "dark";
    d.dataset.theme = t;
    try { localStorage.setItem("rv-theme", t); } catch (e) {}
    document.dispatchEvent(new Event("rv-theme"));
  });

  // ---------------------------------------------------------------- times
  function agoText(ms) {
    var m = Math.max(0, Math.round((Date.now() - ms) / 60000));
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago";
  }
  function nextScan() {
    // the scan runs at these minutes past each hour (UTC) and takes about 3 minutes
    var mins = (document.body.dataset.cron || "2,17,32,47").split(",").map(Number), now = new Date(), best = null;
    for (var h = 0; h < 2 && best === null; h++) {
      for (var i = 0; i < mins.length; i++) {
        var t = new Date(now); t.setUTCHours(now.getUTCHours() + h, mins[i] + 3, 0, 0);
        if (t > now && Number(document.body.dataset.gen) < t.getTime() - 4 * 60000) { best = t; break; }
      }
    }
    return best ? Math.max(1, Math.round((best - now) / 60000)) : null;
  }
  function tick() {
    document.querySelectorAll("time.ago").forEach(function (el) { el.textContent = agoText(Number(el.dataset.ts)); });
    var n = nextScan();
    document.querySelectorAll("[data-next]").forEach(function (el) { el.textContent = n === null ? "a few" : n; });
  }
  tick(); setInterval(tick, 30000);

  // ---------------------------------------------------------------- live prices
  function fmt(x) {
    var a = Math.abs(x);
    if (a >= 1000) return x.toLocaleString("en-US", {maximumFractionDigits: 0});
    if (a >= 1) return x.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
    if (a === 0) return "0";
    var d = 2; while (a < 1 && d < 12) { a *= 10; d++; }
    return x.toFixed(d + 1).replace(/0+$/, "").replace(/\.$/, "");
  }
  function pct(x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(2) + "%"; }
  var priceEls = document.querySelectorAll("[data-price]"), liveEls = document.querySelectorAll("[data-live]");
  var symbols = Array.from(new Set(Array.prototype.map.call(priceEls, function (el) { return el.dataset.price; })));
  var source = "binance", lastOk = 0;

  function fromBinance() {
    var url = "https://data-api.binance.vision/api/v3/ticker/24hr?type=MINI&symbols=" + encodeURIComponent(JSON.stringify(symbols));
    return fetch(url).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (rows) {
      var out = {};
      rows.forEach(function (t) { var o = +t.openPrice, l = +t.lastPrice; out[t.symbol] = {p: l, c: o ? (l / o - 1) * 100 : 0}; });
      return out;
    });
  }
  function fromOkx() {
    return fetch("https://www.okx.com/api/v5/market/tickers?instType=SPOT").then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (j) {
      var out = {};
      (j.data || []).forEach(function (t) {
        if (!/-USDT$/.test(t.instId)) return;
        var l = +t.last, o = +t.open24h; out[t.instId.replace("-", "")] = {p: l, c: o ? (l / o - 1) * 100 : 0};
      });
      return out;
    });
  }
  function paint(prices) {
    priceEls.forEach(function (el) {
      var q = prices[el.dataset.price]; if (!q) return;
      var txt = "$" + fmt(q.p);
      if (el.textContent !== txt) { el.textContent = txt; el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
    });
    document.querySelectorAll("[data-chg-of]").forEach(function (el) {
      var q = prices[el.dataset.chgOf]; if (!q) return;
      el.textContent = pct(q.c) + (el.dataset.suffix || "");
      el.classList.toggle("up", q.c > 0); el.classList.toggle("dn", q.c < 0);
      var tr = el.closest("tr"); if (tr) tr.dataset.chg = q.c.toFixed(4);
    });
  }
  function liveLabel() {
    var s = lastOk ? Math.round((Date.now() - lastOk) / 1000) : null;
    liveEls.forEach(function (el) {
      el.textContent = s === null ? "Live prices unavailable" : "Live prices · " + (s < 5 ? "just now" : s + " s ago");
      el.classList.toggle("on", s !== null && s < 120);
    });
  }
  function refresh() {
    if (!symbols.length || document.hidden) return;
    var get = source === "binance" ? fromBinance : fromOkx;
    get().catch(function () {          // e.g. a coin Binance does not list: the whole request fails, so use OKX
      source = source === "binance" ? "okx" : "binance";
      return (source === "binance" ? fromBinance : fromOkx)();
    }).then(function (p) { paint(p); lastOk = Date.now(); liveLabel(); }).catch(function () { liveLabel(); });
  }
  if (symbols.length) {
    refresh(); setInterval(refresh, LIVE_MS); setInterval(liveLabel, 5000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden && Date.now() - lastOk > LIVE_MS) refresh(); });
  }

  // ---------------------------------------------------------------- chip details (hover on a computer, tap on a phone)
  var tip = document.createElement("div");
  tip.className = "tip"; tip.hidden = true; tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  var tipFor = null;
  function showTip(chip) {
    tipFor = chip;
    tip.innerHTML = "";
    var b = document.createElement("b"); b.textContent = chip.dataset.title; tip.appendChild(b);
    var w = document.createElement("span"); w.textContent = chip.dataset.when + " (" + agoText(Number(chip.dataset.t)) + ")"; tip.appendChild(w);
    if (chip.dataset.href) { var a = document.createElement("a"); a.href = chip.dataset.href; a.textContent = "Open the chart →"; tip.appendChild(a); }
    tip.hidden = false;
    var r = chip.getBoundingClientRect(), tw = tip.offsetWidth;
    tip.style.left = Math.max(8, Math.min(window.innerWidth - tw - 8, r.left + window.scrollX)) + "px";
    tip.style.top = (r.bottom + window.scrollY + 6) + "px";
  }
  function hideTip() { tip.hidden = true; tipFor = null; }
  document.addEventListener("click", function (e) {
    var c = e.target.closest("button.chip");
    if (c) { if (tipFor === c) hideTip(); else showTip(c); return; }
    if (!e.target.closest(".tip")) hideTip();
  });
  document.addEventListener("mouseover", function (e) {
    var c = e.target.closest && e.target.closest("button.chip");
    if (c && matchMedia("(hover: hover)").matches) showTip(c);
  });
  document.addEventListener("mouseout", function (e) {
    var c = e.target.closest && e.target.closest("button.chip");
    if (c && matchMedia("(hover: hover)").matches && !(e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest(".tip"))) hideTip();
  });
  tip.addEventListener("mouseleave", function () { if (matchMedia("(hover: hover)").matches) hideTip(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") hideTip(); });
  window.addEventListener("scroll", function () { if (tipFor && !matchMedia("(hover: hover)").matches) return; hideTip(); }, {passive: true});

  // ---------------------------------------------------------------- coin page: the candle chart with its signals
  var cd = $("chart-data"), box = $("chart");
  if (cd && box) {
    var D = JSON.parse(cd.textContent).tfs, tf = "4h", chart = null;
    var css = function (n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); };
    var draw = function () {
      var d = D[tf];
      if (!window.LightweightCharts || !d) { box.innerHTML = '<p class="fine">The chart could not load.</p>'; return; }
      if (chart) { chart.remove(); chart = null; }
      box.innerHTML = "";
      var last = d.c.length ? d.c[d.c.length - 1][4] : 1, p = Math.max(0, Math.min(8, 4 - Math.floor(Math.log10(Math.abs(last) || 1))));
      chart = LightweightCharts.createChart(box, {
        autoSize: true,
        layout: {background: {type: "solid", color: css("--surface")}, textColor: css("--faint"), fontFamily: "Geist Mono, ui-monospace, monospace", fontSize: 11},
        grid: {vertLines: {visible: false}, horzLines: {color: css("--line-2")}},
        rightPriceScale: {borderVisible: false, scaleMargins: {top: 0.12, bottom: 0.08}},
        timeScale: {borderVisible: false, timeVisible: tf !== "1d", secondsVisible: false},
        crosshair: {mode: 0, vertLine: {color: css("--line"), labelBackgroundColor: css("--text")}, horzLine: {color: css("--line"), labelBackgroundColor: css("--text")}},
        handleScroll: {vertTouchDrag: false},
        localization: {priceFormatter: function (v) { return v.toLocaleString("en-US", {minimumFractionDigits: p, maximumFractionDigits: p}); }}
      });
      var up = css("--up"), dn = css("--dn");
      var series = chart.addCandlestickSeries({upColor: up, downColor: dn, wickUpColor: up, wickDownColor: dn, borderVisible: false,
        priceFormat: {type: "price", precision: p, minMove: Math.pow(10, -p)}});
      series.setData(d.c.map(function (r) { return {time: r[0], open: r[1], high: r[2], low: r[3], close: r[4]}; }));
      series.setMarkers(d.m.slice().sort(function (a, b) { return a[0] - b[0]; }).map(function (m) {
        var bull = m[1] === "bull";
        return {time: m[0], position: bull ? "belowBar" : "aboveBar", color: bull ? up : dn, shape: bull ? "arrowUp" : "arrowDown", size: 0.8};
      }));
      chart.timeScale().fitContent();
    };
    document.querySelectorAll(".tabs button").forEach(function (b) {
      b.addEventListener("click", function () {
        tf = b.dataset.tf;
        document.querySelectorAll(".tabs button").forEach(function (x) { x.classList.toggle("on", x === b); });
        draw();
      });
    });
    document.addEventListener("rv-theme", draw);
    if (window.LightweightCharts) draw(); else window.addEventListener("load", draw);
  }

  // ---------------------------------------------------------------- home: filters and sorting
  var body = document.querySelector("table.coins tbody");
  if (!body || !$("q")) return;
  var rows = Array.prototype.slice.call(body.rows);
  var KEY = "rv-filters", st = {kind: "", tf: "", dir: "", only: false, sort: "rank"};
  try { var saved = JSON.parse(localStorage.getItem(KEY) || "{}"); Object.keys(st).forEach(function (k) { if (k in saved) st[k] = saved[k]; }); } catch (e) {}

  function apply() {
    var q = $("q").value.trim().toUpperCase(), sigFilter = !!(st.kind || st.tf || st.dir), shown = 0;
    rows.forEach(function (r) {
      var hit = 0;
      r.querySelectorAll(".chip").forEach(function (c) {
        var ok = (!st.kind || c.dataset.kind === st.kind) && (!st.tf || c.dataset.tf === st.tf) && (!st.dir || c.dataset.dir === st.dir);
        c.classList.toggle("dim", sigFilter && !ok);
        if (ok) hit++;
      });
      var vis = (!q || r.dataset.sym.indexOf(q) === 0) && (!(st.only || sigFilter) || hit > 0);
      r.hidden = !vis;
      if (vis) shown++;
    });
    $("count").textContent = shown === rows.length ? rows.length + " coins" : shown + " of " + rows.length + " coins";
    $("none").hidden = shown > 0;
    document.querySelectorAll(".kinds .pill").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.k === st.kind)); });
    document.querySelectorAll(".seg[data-g]").forEach(function (g) {
      g.querySelectorAll("button").forEach(function (b) { b.classList.toggle("on", b.dataset.v === st[g.dataset.g]); });
    });
    $("f-only").checked = st.only;
    try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {}
  }
  function sort() {
    var num = function (r, k) { return Number(r.dataset[k]); };
    var cmp = {
      rank: function (a, b) { return num(a, "rank") - num(b, "rank"); },
      n: function (a, b) { return num(b, "n") - num(a, "n") || num(a, "rank") - num(b, "rank"); },
      "chg-desc": function (a, b) { return num(b, "chg") - num(a, "chg"); },
      "chg-asc": function (a, b) { return num(a, "chg") - num(b, "chg"); },
      sym: function (a, b) { return a.dataset.sym < b.dataset.sym ? -1 : 1; }
    }[st.sort] || function () { return 0; };
    rows.sort(cmp).forEach(function (r) { body.appendChild(r); });
  }
  document.querySelectorAll(".kinds .pill").forEach(function (b) {
    b.addEventListener("click", function () { st.kind = st.kind === b.dataset.k ? "" : b.dataset.k; apply(); });
  });
  document.querySelectorAll(".seg[data-g] button").forEach(function (b) {
    b.addEventListener("click", function () { st[b.parentNode.dataset.g] = b.dataset.v; apply(); });
  });
  $("f-only").addEventListener("change", function () { st.only = $("f-only").checked; apply(); });
  $("q").addEventListener("input", apply);
  if ($("sort").querySelector('option[value="' + st.sort + '"]')) $("sort").value = st.sort;
  $("sort").addEventListener("change", function () { st.sort = $("sort").value; sort(); apply(); });
  sort(); apply();
})();
