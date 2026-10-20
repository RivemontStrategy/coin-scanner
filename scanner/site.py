"""The static pages: Markets (home), the Signals feed, Learn, one page per signal type and one per coin, plus sitemap.xml,
robots.txt and 404.html. Design (2026-10-20, owner's pick): concept B "Markets", soft charcoal monotone, stone light theme.
Links between pages are relative, so the same build works at rivemont.xyz and at the github.io address; canonical,
Open Graph and the sitemap use the configured base_url. No trackers. Third-party requests: coin icons (CoinCap's public
icon CDN, or CoinGecko's logo when the build got one), the chart library (jsDelivr) on coin pages, and live prices (Binance / OKX public APIs) from the browser."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote

from .signals import KINDS, bar_time, fmt

def _asset_version() -> str:
    """Short hash of the static CSS/JS, so browsers fetch them again whenever they change."""
    import hashlib
    from pathlib import Path
    h = hashlib.sha1()
    for name in ("style.css", "app.js"):
        f = Path(__file__).resolve().parent.parent / "static" / name
        if f.exists():
            h.update(f.read_bytes())
    return h.hexdigest()[:8]


ASSET_V = _asset_version()
CHART_LIB = "https://cdn.jsdelivr.net/npm/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"
ICON = "https://assets.coincap.io/assets/icons/{}@2x.png"
LOGO = ('<svg class="mark" viewBox="0 0 20 26" aria-hidden="true"><rect x="0" y="0" width="7" height="20" fill="currentColor"/>'
        '<rect x="11" y="5" width="7" height="20" fill="currentColor" opacity=".45"/></svg>')
THEME_ICON = ('<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="7.25" fill="none" stroke="currentColor" '
              'stroke-width="1.5"/><path d="M10 2.75a7.25 7.25 0 0 1 0 14.5z" fill="currentColor"/></svg>')


class Ctx:
    def __init__(self, cfg: dict, referrals: list[dict], scan: dict):
        self.cfg, self.scan = cfg, scan
        self.name = cfg["name"]
        self.base = cfg["base_url"].rstrip("/") + "/"
        self.refs = [r for r in referrals if (r.get("url") or "").strip()]
        self.prefix = ""                                   # set per page: "../" per folder level

    def url(self, path: str = "") -> str:
        return self.base + path.lstrip("/")

    def href(self, path: str = "") -> str:
        return (self.prefix + path.lstrip("/")) or "./"


def coin_path(base: str) -> str:
    return f"coin/{quote(base.lower())}/"


def signal_path(slug: str) -> str:
    return f"signals/{slug}/"


def usd(x: float) -> str:
    return "$" + fmt(x)


def pct(x: float) -> str:
    return ("+" if x > 0 else "−" if x < 0 else "") + f"{abs(x):.2f}%"


def updn(x: float) -> str:
    return "up" if x > 0 else "dn" if x < 0 else ""


def hhmm(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%H:%M")


TF_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


def name_of(c: dict) -> str:
    return c.get("name") or c["base"]


def icon(c: dict, size: str = "") -> str:
    """The coin's logo (CoinGecko when the build got one, else CoinCap's icon) over a letter that shows when none loads."""
    base = c["base"]
    src = c.get("img") or ICON.format(quote(base.lower()))
    return (f'<span class="ci{(" " + size) if size else ""}" data-l="{escape(base[:1])}"><img src="{escape(src)}" '
            f'alt="" loading="lazy" width="32" height="32" onerror="this.remove()"></span>')


def asset(ctx: Ctx, c: dict, sub: str) -> str:
    return (f'<a class="asset" href="{ctx.href(coin_path(c["base"]))}">{icon(c)}<span class="n"><b>{escape(name_of(c))}</b>'
            f'<small>{sub}</small></span></a>')


def compact_usd(x: float) -> str:
    for div, unit in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= div:
            return f"${x / div:.1f}{unit}" if x / div < 100 else f"${x / div:.0f}{unit}"
    return f"${x:.0f}"


def spark(points: list | None, w: int = 96, h: int = 28) -> str:
    if not points or len(points) < 2:
        return '<span class="faint">–</span>'
    lo, hi = min(points), max(points)
    rng = (hi - lo) or 1.0
    step = w / (len(points) - 1)
    d = "".join(f'{"L" if i else "M"}{i * step:.1f} {h - 2 - (v - lo) / rng * (h - 4):.1f}' for i, v in enumerate(points))
    tone = "sp-up" if points[-1] >= points[0] else "sp-dn"
    return f'<svg class="spark {tone}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true"><path d="{d}"/></svg>'


def rsi_cell(v) -> str:
    if v is None:
        return '<span class="faint">–</span>'
    cls = " hot" if v >= 70 else " cold" if v <= 30 else ""
    return (f'<span class="rsi{cls}"><span>{v:.0f}</span><span class="rb"><i style="width:{max(0, min(100, v)):.0f}%"></i></span></span>')


def arrow(direction: str) -> str:
    return f'<b class="{"up" if direction == "bull" else "dn"}">{"▲" if direction == "bull" else "▼"}</b>'


def when(s: dict) -> str:
    return f'{s["tf"]} candle of {bar_time(s["t"])}'


def status_line(ctx: Ctx) -> str:
    gen = ctx.scan["generated"]
    return (f'<p class="status"><span class="live" data-live>Prices loading</span>'
            f'<span>Signals updated {hhmm(gen)} UTC · next in <span data-next>~{ctx.scan.get("every_min", 15)}</span> min</span></p>')


def refs_html(ctx: Ctx, coin: str | None = None) -> str:
    if not ctx.refs:
        return ""
    btns = "".join(f'<a class="pill" href="{escape(r["url"])}" target="_blank" rel="sponsored nofollow noopener">'
                   f'{escape(("Trade " + coin + " on ") if coin else "")}{escape(r["name"])} ↗</a>' for r in ctx.refs)
    return (f'<aside class="refs" aria-label="Exchanges"><div class="pills">{btns}</div>'
            f'<p class="fine">Referral links: we may earn a commission if you sign up. It costs you nothing.</p></aside>')


NAV = (("", "Markets"), ("signals/", "Signals"), ("learn/", "Learn"))


def page(ctx: Ctx, path: str, title: str, desc: str, body: str, ld: dict | None = None, head_extra: str = "",
         nav: str = "") -> str:
    full_title = title if ctx.name in title else f"{title} · {ctx.name}"
    url = ctx.url(path)
    ld_html = f'<script type="application/ld+json">{json.dumps(ld, separators=(",", ":"))}</script>' if ld else ""
    gen = ctx.scan["generated"]
    a = lambda f: f'{ctx.href("assets/" + f)}?v={ASSET_V}'                      # noqa: E731
    links = "".join(f'<a href="{ctx.href(p)}"{" class=on" if p == nav else ""}>{t}</a>' for p, t in NAV)
    opts = "".join(f'<option value="{escape(c["base"])}">{escape(name_of(c))}</option>' for c in ctx.scan["coins"])
    return f"""<!doctype html>
<html lang="en" data-theme="charcoal">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(full_title)}</title>
<meta name="description" content="{escape(desc)}">
<link rel="canonical" href="{escape(url)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{escape(ctx.name)}">
<meta property="og:title" content="{escape(full_title)}">
<meta property="og:description" content="{escape(desc)}">
<meta property="og:url" content="{escape(url)}">
<meta name="twitter:card" content="summary">
<meta name="theme-color" content="#1f2023">
<link rel="icon" href="{ctx.href('assets/mark.svg')}" type="image/svg+xml">
<script>try{{if(localStorage.getItem("rv-theme")==="stone")document.documentElement.dataset.theme="stone"}}catch(e){{}}</script>
<link rel="preload" href="{a('fonts/geist-var-latin.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{a('style.css')}">
{head_extra}{ld_html}
</head>
<body data-every="{ctx.cfg.get("every_min", 15)}" data-gen="{gen}" data-root="{ctx.href()}">
<header class="top"><div class="in">
<a class="brand" href="{ctx.href()}" aria-label="{escape(ctx.name)} home">{LOGO}<span>{escape(ctx.name.upper())}</span></a>
<nav>{links}</nav><span class="sp"></span>
<form class="find" role="search"><input id="find" list="coins" type="search" placeholder="Search a coin" autocomplete="off" aria-label="Search a coin">
<datalist id="coins">{opts}</datalist></form>
<button class="theme" type="button" aria-label="Lighter or darker">{THEME_ICON}</button>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
<p><b>Not financial advice.</b> Signals are computed automatically from public exchange data, on closed candles only,
and can be wrong or late.</p>
<p>Free during beta · Data: {escape(ctx.scan["source_label"])} public market data · Names and logos: CoinGecko, CoinCap</p>
</footer>
<script src="{a('app.js')}" defer></script>
</body>
</html>
"""


def stats(items: list[tuple[str, str]]) -> str:
    return '<dl class="stats">' + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in items) + "</dl>"


# ---------------------------------------------------------------- Markets (home)

def home(ctx: Ctx) -> str:
    ctx.prefix = ""
    coins = ctx.scan["coins"]
    n_new = sum(len(c["new"]) for c in coins)
    n_coins = sum(1 for c in coins if c["new"])
    n_bull = sum(1 for c in coins for s in c["new"] if KINDS[s["kind"]].direction == "bull")
    share = round(n_bull / n_new * 100) if n_new else 0
    rows = []
    for c in coins:
        live = escape(c["base"].upper() + "USDT")
        rsi = c.get("rsi") or {}
        vals = [v for v in rsi.values() if v is not None]
        newest = sorted(c["new"], key=lambda s: -s["t"])
        if newest:
            s, k = newest[0], KINDS[newest[0]["kind"]]
            more = f" · +{len(newest) - 1} more" if len(newest) > 1 else ""
            last = (f'<a class="last" href="{ctx.href(coin_path(c["base"]))}" title="{escape(k.title)} · {escape(when(s))}" '
                    f'data-when="{escape(when(s))}">{arrow(k.direction)}<b>{escape(k.title)}</b><small>{escape(s["tf"])} chart{more}</small></a>')
        else:
            last = '<span class="faint">–</span>'
        rows.append(
            f'<tr data-sym="{escape(c["base"].upper())}" data-name="{escape(name_of(c).upper())}" data-rank="{c["rank"]}" '
            f'data-chg="{c["change"]:.4f}" data-n="{len(c["new"])}" data-ob="{int(any(v >= 70 for v in vals))}" '
            f'data-os="{int(any(v <= 30 for v in vals))}">'
            f'<td class="a">{asset(ctx, c, escape(c["base"]) + " · " + compact_usd(c["qv"]))}</td>'
            f'<td class="num" data-price="{live}">{escape(usd(c["price"]))}</td>'
            f'<td class="num {updn(c["change"])}" data-chg-of="{live}">{pct(c["change"])}</td>'
            f'<td class="sp hide-m">{spark(c.get("spark"))}</td>'
            + "".join(f'<td class="hide-m">{rsi_cell(rsi.get(tf))}</td>' for tf in ("1h", "4h", "1d"))
            + f'<td class="hide-m l">{last}</td></tr>')
    body = f"""
<section class="head">
<div><h1>Markets</h1>
<p class="sub">Top {len(coins)} coins · RSI and the newest signal on the 1h, 4h and daily charts · closed candles only</p>
{status_line(ctx)}</div>
{stats([("New signals", str(n_new)), ("Coins with signals", f'{n_coins}<span class="soft"> / {len(coins)}</span>'),
        ("Bullish share", f'{share}<span class="soft">%</span>')])}
</section>
<section class="panel">
<div class="tools">
<div class="pills" data-g="f"><button type="button" class="pill on" data-v="">All coins</button><button type="button" class="pill" data-v="sig">With new signals</button><button type="button" class="pill" data-v="ob">Overbought</button><button type="button" class="pill" data-v="os">Oversold</button></div>
<div class="pills" data-g="o"><button type="button" class="pill on" data-v="rank">Volume</button><button type="button" class="pill" data-v="chg">24h move</button><button type="button" class="pill" data-v="n">Signals</button></div>
</div>
<table class="mk">
<thead><tr><th class="a">Asset</th><th>Price</th><th>24h</th><th class="hide-m">7 days</th><th class="hide-m">RSI 1h</th><th class="hide-m">RSI 4h</th><th class="hide-m">RSI 1d</th><th class="hide-m l">Newest signal</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="empty" id="none" hidden>No coin matches.</p>
<p id="count" class="fine" aria-live="polite"></p>
</section>
{refs_html(ctx)}"""
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": ctx.name, "url": ctx.url()}
    return page(ctx, "", f"{ctx.name}: {ctx.cfg['tagline']}",
                "Free crypto signal scanner: RSI on the 1h, 4h and daily charts, trend turns, golden and death crosses, "
                "double tops and bottoms, volume spikes and 30-day breakouts on the top 150 coins, refreshed every 15 minutes.",
                body, ld, nav="")


# ---------------------------------------------------------------- Signals: the feed

def signals_feed(ctx: Ctx) -> str:
    ctx.prefix = "../"
    coins = ctx.scan["coins"]
    gen = ctx.scan["generated"]
    merged: dict[tuple, dict] = {}
    for c in coins:
        for s in c["new"]:
            key = (c["base"], s["tf"], s["t"], KINDS[s["kind"]].direction)
            if key in merged:
                merged[key]["kinds"].append(s["kind"])
            else:
                merged[key] = {"c": c, "s": s, "kinds": [s["kind"]]}
    items = sorted(merged.values(), key=lambda x: (-(x["s"]["t"] + TF_MS[x["s"]["tf"]]), x["c"]["rank"]))
    groups = (("Last 4 hours", 4 * 3_600_000), ("Earlier today", 24 * 3_600_000), ("Last 3 days", 10 ** 15))
    html, cur = [], None
    for x in items:
        c, s = x["c"], x["s"]
        closed = s["t"] + TF_MS[s["tf"]]
        g = next(i for i, (_, span) in enumerate(groups) if gen - closed < span)
        if g != cur:
            html.append(f'<div class="grp" data-grp>{groups[g][0]}</div>')
            cur = g
        k = KINDS[s["kind"]]
        titles = " · ".join(escape(KINDS[kk].title) for kk in x["kinds"])
        live = escape(c["base"].upper() + "USDT")
        html.append(
            f'<div class="fr" data-dir="{k.direction}" data-tf="{s["tf"]}"><time class="ago t" data-ts="{closed}"></time>'
            f'{asset(ctx, c, escape(c["base"]))}'
            f'<a class="sig" href="{ctx.href(coin_path(c["base"]))}" title="{escape(when(s))}"><b>{titles}</b><small>{escape(s["tf"])} chart</small></a>'
            f'<span class="dir {"up" if k.direction == "bull" else "dn"}">{"▲ Bullish" if k.direction == "bull" else "▼ Bearish"}</span>'
            f'<span class="px"><span class="num" data-price="{live}">{escape(usd(c["price"]))}</span>'
            f'<small class="num {updn(c["change"])}" data-chg-of="{live}">{pct(c["change"])}</small></span></div>')
    bull = sum(1 for c in coins for s in c["new"] if KINDS[s["kind"]].direction == "bull")
    bear = sum(len(c["new"]) for c in coins) - bull
    ob = sum(1 for c in coins for v in (c.get("rsi") or {}).values() if v is not None and v >= 70)
    os_ = sum(1 for c in coins for v in (c.get("rsi") or {}).values() if v is not None and v <= 30)
    tot = (bull + bear) or 1

    def mini(lst, right):
        return "".join(f'<div class="mr">{asset(ctx, c, escape(c["base"]))}{right(c)}</div>' for c in lst)
    def count_of(c):
        return f'<span class="muted num">{len(c["new"])}</span>'

    def move_of(c):
        return f'<span class="num {updn(c["change"])}">{pct(c["change"])}</span>'
    most = sorted((c for c in coins if c["new"]), key=lambda c: (-len(c["new"]), c["rank"]))[:5]
    movers = sorted(coins, key=lambda c: -abs(c["change"]))[:5]
    side = (f'<div class="card"><h3>Market mood · new signals</h3><div class="big num">{bull}<span class="soft"> / </span>{bear}</div>'
            f'<div class="split"><i style="width:{bull / tot * 100:.1f}%"></i></div><div class="kv"><span>Bullish</span><span>Bearish</span></div></div>'
            f'<div class="card"><h3>RSI extremes, all charts</h3><div class="kv"><span>Overbought (70+)</span><b class="num">{ob}</b></div>'
            f'<div class="kv"><span>Oversold (30 or less)</span><b class="num">{os_}</b></div></div>'
            f'<div class="card"><h3>Most signals</h3>{mini(most, count_of)}</div>'
            f'<div class="card"><h3>Biggest moves, 24h</h3>{mini(movers, move_of)}</div>')
    body = f"""
<div class="feed-grid">
<section>
<h1>What just changed</h1>
<p class="sub">New signals on the top {len(coins)} coins, newest first · closed candles only</p>
{status_line(ctx)}
<p class="mood-inline">Bullish <b class="num">{bull}</b> · Bearish <b class="num">{bear}</b> · Overbought <b class="num">{ob}</b> · Oversold <b class="num">{os_}</b></p>
<div class="tools">
<div class="pills" data-g="dir"><button type="button" class="pill on" data-v="">All</button><button type="button" class="pill" data-v="bull">Bullish</button><button type="button" class="pill" data-v="bear">Bearish</button></div>
<div class="pills" data-g="tf"><button type="button" class="pill on" data-v="">All charts</button><button type="button" class="pill" data-v="1h">1h</button><button type="button" class="pill" data-v="4h">4h</button><button type="button" class="pill" data-v="1d">1d</button></div>
</div>
<div class="feed" id="feed">{"".join(html) or '<p class="empty">No new signal right now.</p>'}</div>
<p class="empty" id="none" hidden>No signal matches.</p>
</section>
<aside class="side">{side}</aside>
</div>
{refs_html(ctx)}"""
    return page(ctx, "signals/", "New crypto signals now", "What just changed on the top 150 coins: RSI extremes, trend "
                "turns, crosses, double tops and bottoms, volume spikes and 30-day breakouts, newest first.", body, nav="signals/")


# ---------------------------------------------------------------- Learn and one signal type

def learn(ctx: Ctx) -> str:
    ctx.prefix = "../"
    per = Counter(s["kind"] for c in ctx.scan["coins"] for s in c["new"])
    items = "".join(
        f'<a class="card lc" href="{ctx.href(signal_path(k.slug))}"><div class="lh">{arrow(k.direction)}'
        f'<b>{escape(k.title)}</b><span class="num n">{per.get(k.slug, 0)} now</span></div><p>{escape(k.about)}</p></a>'
        for k in KINDS.values())
    body = (f'<section class="head"><div><h1>Learn the signals</h1>'
            f'<p class="sub">Twelve signals, read on closed candles. What each one means, and how many coins show it now.</p></div></section>'
            f'<section class="cards">{items}</section>')
    return page(ctx, "learn/", "Crypto signals explained", "RSI, trend turns, golden and death crosses, double tops and "
                "bottoms, volume spikes and 30-day breakouts: what each signal means and which coins show it now.", body, nav="learn/")


def signal_page(ctx: Ctx, slug: str) -> str:
    ctx.prefix = "../../"
    k = KINDS[slug]
    rows = []
    for c in ctx.scan["coins"]:
        for s in c["new"]:
            if s["kind"] != slug:
                continue
            live = escape(c["base"].upper() + "USDT")
            rows.append(f'<tr><td class="a">{asset(ctx, c, escape(c["base"]) + " · " + escape(s["tf"]) + " chart")}</td>'
                        f'<td class="num hide-m" data-price="{live}">{escape(usd(c["price"]))}</td>'
                        f'<td class="l what">{escape(s["text"])}<small>{escape(when(s))}</small></td></tr>')
    table = (f'<section class="panel"><table class="mk"><thead><tr><th class="a">Asset</th><th class="hide-m">Price</th>'
             f'<th class="l">What happened</th></tr></thead><tbody>{"".join(rows)}</tbody></table></section>' if rows else
             f'<section class="panel"><p class="empty">No coin in the top {len(ctx.scan["coins"])} shows a new '
             f'{escape(k.title.lower())} right now. This page refreshes every 15 minutes.</p></section>')
    word = "bullish" if k.direction == "bull" else "bearish"
    body = (f'<section class="head"><div><p class="crumb"><a href="{ctx.href("learn/")}">Learn</a> · usually read as {word}</p>'
            f'<h1>{arrow(k.direction)} {escape(k.title)}</h1><p class="sub wide">{escape(k.about)}</p>{status_line(ctx)}</div>'
            f'{stats([("Coins now", str(len(rows)))])}</section>{table}{refs_html(ctx)}')
    desc = f"Coins showing a {k.title.lower()} now on the 1h, 4h or daily chart, refreshed every 15 minutes. {k.about.split('. ')[0]}."
    return page(ctx, signal_path(slug), f"{k.title}: coins now", desc, body, nav="learn/")


# ---------------------------------------------------------------- one coin

def coin_page(ctx: Ctx, c: dict, charts: dict) -> str:
    ctx.prefix = "../../"
    base = c["base"]
    tfs = ctx.cfg["timeframes"]
    live = escape(base.upper() + "USDT")
    rsi = c.get("rsi") or {}
    tabs = "".join(f'<button type="button" class="pill{" on" if tf == "4h" else ""}" data-tf="{tf}">{tf}</button>' for tf in tfs)
    now_rows = []
    for tf in tfs:
        sigs = [s for s in c["new"] if s["tf"] == tf]
        links = "".join(f'<a class="tag" href="{ctx.href(signal_path(s["kind"]))}" title="{escape(when(s))}">'
                        f'{arrow(KINDS[s["kind"]].direction)}{escape(KINDS[s["kind"]].title)}</a>' for s in sigs) \
            or '<span class="faint">No new signal</span>'
        now_rows.append(f'<div class="nr"><span class="tfl">{tf}</span><div class="tags">{links}</div>{rsi_cell(rsi.get(tf))}</div>')

    def item(s):
        k = KINDS[s["kind"]]
        return (f'<li><div class="hw"><a class="tag" href="{ctx.href(signal_path(s["kind"]))}">{arrow(k.direction)}{escape(k.title)}</a>'
                f'<span class="faint">{escape(when(s))}</span></div><p>{escape(s["text"])}</p></li>')
    first, rest = c["history"][:20], c["history"][20:]
    hist = "".join(item(s) for s in first) or '<li class="faint">No signals in the period shown.</li>'
    more = (f'<details class="more"><summary class="pill">Show {len(rest)} more</summary><ul class="hist">{"".join(item(s) for s in rest)}</ul>'
            f'</details>' if rest else "")
    data = json.dumps({"tfs": charts}, separators=(",", ":")).replace("</", "<\\/")
    body = f"""
<section class="head coin">
<div><p class="crumb"><a href="{ctx.href()}">Markets</a> · #{c["rank"]} by 24h volume</p>
<div class="ct">{icon(c, "lg")}<div><h1>{escape(name_of(c))}</h1><p class="sub">{escape(base)} / USDT</p></div></div>
{status_line(ctx)}</div>
{stats([("Price", f'<span class="num" data-price="{live}">{escape(usd(c["price"]))}</span>'),
        ("24h", f'<span class="num {updn(c["change"])}" data-chg-of="{live}">{pct(c["change"])}</span>'),
        ("24h volume", compact_usd(c["qv"]))])}
</section>
<section class="panel chartp">
<div class="tools"><div class="pills tabs" role="tablist" aria-label="Timeframe">{tabs}</div>
<span class="fine">Closed candles · ▲ bullish and ▼ bearish signals sit under and over their candle</span></div>
<div id="chart" class="chart"><p class="fine">Loading the chart…</p></div>
<script type="application/json" id="chart-data">{data}</script>
</section>
<div class="two">
<section class="panel"><h2>Signals now</h2>{"".join(now_rows)}</section>
<section class="panel"><h2>Recent signals</h2><ul class="hist">{hist}</ul>{more}</section>
</div>
{refs_html(ctx, base)}"""
    desc = (f"{name_of(c)} ({base}) signals now: RSI, trend turns, double tops and bottoms, volume spikes and 30-day breakouts "
            f"on the 1h, 4h and daily charts, with a live price. Free, refreshed every 15 minutes.")
    return page(ctx, coin_path(base), f"{name_of(c)} ({base}) price and signals", desc, body,
                head_extra=f'<script src="{CHART_LIB}" defer></script>\n', nav="")


# ---------------------------------------------------------------- the rest

def not_found(ctx: Ctx) -> str:
    """Served for any missing address, at any depth: its links are absolute from the site root."""
    ctx.prefix = "/"
    return page(ctx, "404.html", "Page not found", "This page does not exist.",
                '<script>(function(){var p=location.pathname,l=p.toLowerCase();if(p!==l)location.replace(l+location.search+location.hash);})();</script>'
                '<section class="head"><div><h1>Page not found</h1><p class="sub"><a href="/">Back to Markets</a></p></div></section>')


def sitemap(ctx: Ctx) -> str:
    paths = ["", "signals/", "learn/"] + [signal_path(s) for s in KINDS] + [coin_path(c["base"]) for c in ctx.scan["coins"]]
    day = datetime.fromtimestamp(ctx.scan["generated"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    urls = "".join(f"<url><loc>{escape(ctx.url(p))}</loc><lastmod>{day}</lastmod></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


def robots(ctx: Ctx) -> str:
    return f"User-agent: *\nAllow: /\nDisallow: /lab/\nSitemap: {ctx.url('sitemap.xml')}\n"
