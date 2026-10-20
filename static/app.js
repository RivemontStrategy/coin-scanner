// Filters, sorting, "updated N minutes ago" and the theme switch. No tracking, no network requests.
(function () {
  var $ = function (id) { return document.getElementById(id); };

  // theme
  var tb = document.querySelector(".theme");
  if (tb) tb.addEventListener("click", function () {
    var d = document.documentElement, t = d.dataset.theme === "light" ? "dark" : "light";
    d.dataset.theme = t;
    try { localStorage.setItem("cs-theme", t); } catch (e) {}
  });

  // "updated 12 min ago"
  function ago() {
    var now = Date.now();
    document.querySelectorAll("time.ago").forEach(function (el) {
      var m = Math.max(0, Math.round((now - Number(el.dataset.ts)) / 60000));
      el.textContent = m < 1 ? "just now" : m < 60 ? m + " min ago" : m < 1440 ? Math.round(m / 60) + " h ago" : Math.round(m / 1440) + " days ago";
      el.title = el.getAttribute("datetime");
    });
  }
  ago(); setInterval(ago, 30000);

  // home: filter and sort
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
