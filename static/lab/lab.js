// Concepts: load the live scan (this site) plus coin names and 7-day lines (CoinGecko public API, browser only).
window.LAB = (function () {
  var K = {"rsi-oversold": ["RSI oversold", "bull"], "rsi-overbought": ["RSI overbought", "bear"],
    "bullish-structure-break": ["Trend turned up", "bull"], "bearish-structure-break": ["Trend turned down", "bear"],
    "golden-cross": ["Golden cross", "bull"], "death-cross": ["Death cross", "bear"], "double-bottom": ["Double bottom", "bull"],
    "double-top": ["Double top", "bear"], "volume-spike-up": ["Volume spike, up candle", "bull"],
    "volume-spike-down": ["Volume spike, down candle", "bear"], "range-breakout": ["30-day breakout", "bull"],
    "range-breakdown": ["30-day breakdown", "bear"]};
  function fmt(x) {
    var a = Math.abs(x);
    if (a >= 1000) return x.toLocaleString("en-US", {maximumFractionDigits: 0});
    if (a >= 1) return x.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
    var d = 2; while (a < 1 && a > 0 && d < 12) { a *= 10; d++; }
    return x.toFixed(d + 1).replace(/0+$/, "").replace(/\.$/, "");
  }
  function usd(x) { return "$" + fmt(x); }
  function pct(x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x).toFixed(2) + "%"; }
  function cls(x) { return x > 0 ? "up" : x < 0 ? "dn" : ""; }
  function ago(t) {
    var m = Math.max(1, Math.round((Date.now() - t) / 60000));
    return m < 60 ? m + "m" : m < 1440 ? Math.round(m / 60) + "h" : Math.round(m / 1440) + "d";
  }
  function compact(x) { return x >= 1e9 ? "$" + (x / 1e9).toFixed(1) + "B" : x >= 1e6 ? "$" + (x / 1e6).toFixed(1) + "M" : "$" + Math.round(x / 1e3) + "K"; }
  function icon(c) {
    var src = c.img || ("https://assets.coincap.io/assets/icons/" + c.base.toLowerCase() + "@2x.png");
    return '<span class="logo-i">' + c.base[0] + '<img src="' + src + '" alt="" loading="lazy" onerror="this.remove()"></span>';
  }
  function spark(p, w, h) {
    if (!p || p.length < 2) return "";
    var lo = Math.min.apply(null, p), hi = Math.max.apply(null, p), r = hi - lo || 1, step = w / (p.length - 1);
    var d = p.map(function (v, i) { return (i ? "L" : "M") + (i * step).toFixed(1) + " " + (h - 2 - (v - lo) / r * (h - 4)).toFixed(1); }).join("");
    return '<svg width="' + w + '" height="' + h + '" viewBox="0 0 ' + w + " " + h + '"><path d="' + d + '" fill="none" stroke="' +
      (p[p.length - 1] >= p[0] ? "var(--muted)" : "var(--faint)") + '" stroke-width="1.3"/></svg>';
  }
  function load() {
    var scan = fetch("../data/scan.json").then(function (r) { return r.json(); });
    var cg = fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&sparkline=true")
      .then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; });
    return Promise.all([scan, cg]).then(function (x) {
      var s = x[0], by = {};
      x[1].forEach(function (m) { var k = m.symbol.toUpperCase(); if (!by[k]) by[k] = m; });
      s.coins.forEach(function (c) {
        var m = by[c.base.toUpperCase()];
        c.name = m ? m.name.replace(/\s*\(.*\)\s*/g, "") : c.base; c.img = m ? m.image : null;
        c.spark = m && m.sparkline_in_7d ? m.sparkline_in_7d.price.filter(function (_, i) { return i % 4 === 0; }) : null;
      });
      return s;
    });
  }
  return {K: K, fmt: fmt, usd: usd, pct: pct, cls: cls, ago: ago, compact: compact, icon: icon, spark: spark, load: load};
})();
