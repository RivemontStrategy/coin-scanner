// Filters, sorting, chip details, live prices, "updated N min ago" and the theme switch. No tracking: the only
// requests are to public exchange price endpoints (Binance's data mirror, OKX as a fallback).
(function () {
  var $ = function (id) { return document.getElementById(id); };
  var LIVE_MS = 45000;

  // ---------------------------------------------------------------- theme
  var tb = document.querySelector(".theme");
  if (tb) tb.addEventListener("click", function () {
    var d = document.documentElement, t = d.dataset.theme === "light" ? "dark" : "light";
    d.dataset.theme = t;
    try { localStorage.setItem("cs-theme", t); } catch (e) {}
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
      el.textContent = s === null ? "Live prices unavailable" : "Live prices · " + (source === "okx" ? "OKX" : "Binance") + " · " + (s < 5 ? "just now" : s + " s ago");
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

  // ---------------------------------------------------------------- home: filter and sort
  var body = document.querySelector("table.coins tbody");
  if (!body || !$("q")) return;
  var rows = Array.prototype.slice.call(body.rows);
  var KEY = "cs-filters";

  function apply() {
    var q = $("q").value.trim().toUpperCase(), kind = $("f-kind").value, tf = $("f-tf").value, dir = $("f-dir").value;
    var only = $("f-only").checked, sigFilter = !!(kind || tf || dir), shown = 0;
    rows.forEach(function (r) {
      var chips = r.querySelectorAll(".chip"), hit = 0;
      chips.forEach(function (c) {
        var ok = (!kind || c.dataset.kind === kind) && (!tf || c.dataset.tf === tf) && (!dir || c.dataset.dir === dir);
        c.classList.toggle("dim", sigFilter && !ok);
        if (ok) hit++;
      });
      var vis = (!q || r.dataset.sym.indexOf(q) === 0) && (!(only || sigFilter) || hit > 0);
      r.hidden = !vis;
      if (vis) shown++;
    });
    $("count").textContent = shown + " of " + rows.length + " coins";
    try { localStorage.setItem(KEY, JSON.stringify({kind: kind, tf: tf, dir: dir, only: only, sort: $("sort").value})); } catch (e) {}
  }

  function sort() {
    var s = $("sort").value, num = function (r, k) { return Number(r.dataset[k]); };
    var cmp = {
      rank: function (a, b) { return num(a, "rank") - num(b, "rank"); },
      n: function (a, b) { return num(b, "n") - num(a, "n") || num(a, "rank") - num(b, "rank"); },
      "chg-desc": function (a, b) { return num(b, "chg") - num(a, "chg"); },
      "chg-asc": function (a, b) { return num(a, "chg") - num(b, "chg"); },
      sym: function (a, b) { return a.dataset.sym < b.dataset.sym ? -1 : 1; }
    }[s] || function () { return 0; };
    rows.sort(cmp).forEach(function (r) { body.appendChild(r); });
  }

  try {
    var saved = JSON.parse(localStorage.getItem(KEY) || "{}");
    ["kind", "tf", "dir", "sort"].forEach(function (k) {
      var el = $(k === "sort" ? "sort" : "f-" + k);
      if (saved[k] && el.querySelector('option[value="' + saved[k] + '"]')) el.value = saved[k];
    });
    $("f-only").checked = !!saved.only;
  } catch (e) {}

  ["q", "f-kind", "f-tf", "f-dir", "f-only"].forEach(function (id) { $(id).addEventListener("input", apply); $(id).addEventListener("change", apply); });
  $("sort").addEventListener("change", function () { sort(); apply(); });
  sort(); apply();
})();
