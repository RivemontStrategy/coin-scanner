// Markets filters and sorting, the signals feed filters, coin search, live prices, "N min ago", the candle chart and
// the theme switch. No tracking: the only requests are to public exchange price endpoints (Binance's data mirror, OKX
// as a fallback) and, on coin pages, the chart library.
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var LIVE_MS = 45000;
  var root = document.body.dataset.root || "./";

  // ---------------------------------------------------------------- theme: soft charcoal, or stone
  var tb = document.querySelector(".theme");
  if (tb) tb.addEventListener("click", function () {
    var d = document.documentElement, t = d.dataset.theme === "stone" ? "charcoal" : "stone";
    d.dataset.theme = t;
    try { localStorage.setItem("rv-theme", t); } catch (e) {}
    document.dispatchEvent(new Event("rv-theme"));
  });

  // ---------------------------------------------------------------- search a coin
  var find = $("find");
  if (find) {
    var opts = Array.prototype.map.call(document.querySelectorAll("#coins option"), function (o) { return [o.value, o.textContent]; });
    var go = function () {
      var q = find.value.trim().toUpperCase(); if (!q) return;
      var hit = opts.filter(function (o) { return o[0].toUpperCase() === q || o[1].toUpperCase() === q; })[0] ||
        opts.filter(function (o) { return o[0].toUpperCase().indexOf(q) === 0 || o[1].toUpperCase().indexOf(q) === 0; })[0];
      if (hit) location.href = root.replace(/\/?$/, "/").replace(/^\.\/$/, "") + "coin/" + hit[0].toLowerCase() + "/";
    };
    find.form.addEventListener("submit", function (e) { e.preventDefault(); go(); });
    find.addEventListener("change", function () { if (opts.some(function (o) { return o[0] === find.value; })) go(); });
    find.addEventListener("input", function () { document.dispatchEvent(new Event("rv-find")); });
  }

  // ---------------------------------------------------------------- times
  function agoText(ms) {
    var m = Math.max(0, Math.round((Date.now() - ms) / 60000));
    return m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago";
  }
  function agoShort(ms) {
    var m = Math.max(1, Math.round((Date.now() - ms) / 60000));
    return m < 60 ? m + "m" : m < 1440 ? Math.round(m / 60) + "h" : Math.round(m / 1440) + "d";
  }
  function nextScan() {
    // a new scan is published about every 15 minutes after the last one
    var every = Number(document.body.dataset.every || 15), gen = Number(document.body.dataset.gen);
    var left = Math.round((gen + (every + 1) * 60000 - Date.now()) / 60000);
    return left >= 1 ? left : null;
  }
  function tick() {
    document.querySelectorAll("time.ago").forEach(function (el) {
      el.textContent = el.classList.contains("t") ? agoShort(Number(el.dataset.ts)) : agoText(Number(el.dataset.ts));
    });
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
        layout: {background: {type: "solid", color: css("--bg")}, textColor: css("--faint"), fontFamily: "Geist Mono, ui-monospace, monospace", fontSize: 11},
        grid: {vertLines: {visible: false}, horzLines: {color: css("--line2")}},
        rightPriceScale: {borderVisible: false, scaleMargins: {top: 0.12, bottom: 0.08}},
        timeScale: {borderVisible: false, timeVisible: tf !== "1d", secondsVisible: false},
        crosshair: {mode: 0, vertLine: {color: css("--line"), labelBackgroundColor: css("--text")}, horzLine: {color: css("--line"), labelBackgroundColor: css("--text")}},
        handleScroll: {vertTouchDrag: false},
        localization: {locale: "en-US", priceFormatter: function (v) { return v.toLocaleString("en-US", {minimumFractionDigits: p, maximumFractionDigits: p}); }}
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
    document.querySelectorAll(".tabs .pill").forEach(function (b) {
      b.addEventListener("click", function () {
        tf = b.dataset.tf;
        document.querySelectorAll(".tabs .pill").forEach(function (x) { x.classList.toggle("on", x === b); });
        draw();
      });
    });
    document.addEventListener("rv-theme", draw);
    if (window.LightweightCharts) draw(); else window.addEventListener("load", draw);
  }

  // ---------------------------------------------------------------- pill groups
  function pills(group, st, onchange) {
    document.querySelectorAll('.pills[data-g="' + group + '"] .pill').forEach(function (b) {
      b.addEventListener("click", function () { st[group] = b.dataset.v; onchange(); });
    });
  }
  function mark(st) {
    document.querySelectorAll(".pills[data-g]").forEach(function (g) {
      g.querySelectorAll(".pill").forEach(function (b) { b.classList.toggle("on", b.dataset.v === st[g.dataset.g]); });
    });
  }

  // ---------------------------------------------------------------- Markets: filters, sorting, search
  var mk = document.querySelector("table.mk tbody");
  if (mk && $("count")) {
    var rows = Array.prototype.slice.call(mk.rows), KEY = "rv-markets", ms = {f: "", o: "rank"};
    try { var sv = JSON.parse(localStorage.getItem(KEY) || "{}"); if (typeof sv.f === "string") ms.f = sv.f; if (typeof sv.o === "string") ms.o = sv.o; } catch (e) {}
    var applyMk = function () {
      var q = find ? find.value.trim().toUpperCase() : "", shown = 0;
      var num = function (r, k) { return Number(r.dataset[k]); };
      var cmp = {rank: function (a, b) { return num(a, "rank") - num(b, "rank"); },
        chg: function (a, b) { return Math.abs(num(b, "chg")) - Math.abs(num(a, "chg")); },
        n: function (a, b) { return num(b, "n") - num(a, "n") || num(a, "rank") - num(b, "rank"); }}[ms.o] || function () { return 0; };
      rows.sort(cmp).forEach(function (r) { mk.appendChild(r); });
      rows.forEach(function (r) {
        var vis = (!q || r.dataset.sym.indexOf(q) === 0 || r.dataset.name.indexOf(q) === 0) &&
          (!ms.f || (ms.f === "sig" && num(r, "n") > 0) || (ms.f === "ob" && r.dataset.ob === "1") || (ms.f === "os" && r.dataset.os === "1"));
        r.hidden = !vis; if (vis) shown++;
      });
      $("count").textContent = shown === rows.length ? rows.length + " coins" : shown + " of " + rows.length + " coins";
      $("none").hidden = shown > 0;
      mark(ms);
      try { localStorage.setItem(KEY, JSON.stringify(ms)); } catch (e) {}
    };
    pills("f", ms, applyMk); pills("o", ms, applyMk);
    document.addEventListener("rv-find", applyMk);
    applyMk();
  }

  // ---------------------------------------------------------------- Signals feed: direction and chart filters
  var feed = $("feed");
  if (feed) {
    var fs = {dir: "", tf: ""};
    var applyFeed = function () {
      var shown = 0, groupHead = null, groupHas = false;
      Array.prototype.forEach.call(feed.children, function (el) {
        if (el.hasAttribute("data-grp")) { if (groupHead) groupHead.hidden = !groupHas; groupHead = el; groupHas = false; return; }
        var vis = (!fs.dir || el.dataset.dir === fs.dir) && (!fs.tf || el.dataset.tf === fs.tf);
        el.hidden = !vis; if (vis) { shown++; groupHas = true; }
      });
      if (groupHead) groupHead.hidden = !groupHas;
      $("none").hidden = shown > 0 || !feed.querySelector(".fr");
      mark(fs);
    };
    pills("dir", fs, applyFeed); pills("tf", fs, applyFeed);
    applyFeed();
  }
})();
