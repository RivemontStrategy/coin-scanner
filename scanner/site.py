"""The static pages: home, one page per signal type and one per coin, plus sitemap.xml, robots.txt and 404.html.
Links between pages are relative, so the same build works at rivemont.xyz and at the github.io address; canonical,
Open Graph and the sitemap use the configured base_url. No trackers. Third-party requests: coin icons (CoinCap's public
icon CDN), the chart library (jsDelivr) on coin pages, and live prices (Binance / OKX public APIs) from the browser."""
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


def icon(base: str, size: str = "") -> str:
    """The coin's logo from CoinCap's public icons, over a letter badge that shows when there is none."""
    return (f'<span class="ci{(" " + size) if size else ""}" data-l="{escape(base[:1])}"><img src="{ICON.format(quote(base.lower()))}" '
            f'alt="" loading="lazy" width="20" height="20" onerror="this.remove()"></span>')


def chip(sig: dict, with_tf: bool = True, link: str | None = None, tip: bool = False) -> str:
    """A signal chip: a dot in the signal's direction, the timeframe, a few words. With tip=True it is a button whose
    hover or tap shows its candle time and a link (static/app.js)."""
    k = KINDS[sig["kind"]]
    tf = f'<i>{escape(sig["tf"])}</i>' if with_tf else ""
    when = f'{sig["tf"]} candle of {bar_time(sig["t"])}'
    inner = f'{tf}{escape(k.short)}'
    attrs = f'class="chip {k.direction}" data-kind="{k.slug}" data-tf="{sig["tf"]}" data-dir="{k.direction}"'
    if tip:
        href = f' data-href="{escape(link)}"' if link else ""
        return (f'<button type="button" {attrs} data-title="{escape(k.title)}" data-when="{escape(when)}" '
                f'data-t="{sig["t"]}"{href}>{inner}</button>')
    title = escape(f"{k.title} · {when}")
    return (f'<a {attrs} title="{title}" href="{escape(link)}">{inner}</a>' if link
            else f'<span {attrs} title="{title}">{inner}</span>')


def status_line(ctx: Ctx) -> str:
    gen = ctx.scan["generated"]
    return (f'<p class="status"><span class="live" data-live>Prices loading</span>'
            f'<span>Signals updated {hhmm(gen)} UTC · next in <span data-next>~{ctx.scan.get("every_min", 15)}</span> min</span></p>')


def refs_html(ctx: Ctx, coin: str | None = None) -> str:
    if not ctx.refs:
        return ""
    btns = "".join(f'<a class="pill" href="{escape(r["url"])}" target="_blank" rel="sponsored nofollow noopener">'
                   f'{escape(("Trade " + coin + " on ") if coin else "")}{escape(r["name"])} ↗</a>' for r in ctx.refs)
    return (f'<aside class="refs" aria-label="Exchanges"><div class="row">{btns}</div>'
            f'<p class="fine">Referral links: we may earn a commission if you sign up. It costs you nothing.</p></aside>')


def page(ctx: Ctx, path: str, title: str, desc: str, body: str, ld: dict | None = None, head_extra: str = "") -> str:
    full_title = title if ctx.name in title else f"{title} · {ctx.name}"
    url = ctx.url(path)
    ld_html = f'<script type="application/ld+json">{json.dumps(ld, separators=(",", ":"))}</script>' if ld else ""
    gen = ctx.scan["generated"]
    a = lambda f: f'{ctx.href("assets/" + f)}?v={ASSET_V}'                      # noqa: E731
    return f"""<!doctype html>
<html lang="en" data-theme="dark">
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
<meta name="theme-color" content="#101010">
<link rel="icon" href="{ctx.href('assets/mark.svg')}" type="image/svg+xml">
<script>try{{if(localStorage.getItem("rv-theme")==="light")document.documentElement.dataset.theme="light"}}catch(e){{}}</script>
<link rel="preload" href="{a('fonts/geist-var-latin.woff2')}" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{a('style.css')}">
{head_extra}{ld_html}
</head>
<body data-every="{ctx.cfg.get("every_min", 15)}" data-gen="{gen}">
<header class="top"><div class="wrap">
<a class="brand" href="{ctx.href()}" aria-label="{escape(ctx.name)} home">{LOGO}<span>{escape(ctx.name.upper())}</span></a>
<nav><a href="{ctx.href()}">Scanner</a><a href="{ctx.href('signals/')}">Signals</a>
<button class="theme" type="button" aria-label="Light or dark">{THEME_ICON}</button></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
<p><b>Not financial advice.</b> Signals are computed automatically from public exchange data, on closed candles only,
and can be wrong or late.</p>
<p>Free during beta · Data: {escape(ctx.scan["source_label"])} public market data · Coin icons: CoinCap</p>
</footer>
<script src="{a('app.js')}" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- home

def compact_usd(x: float) -> str:
    for div, unit in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if x >= div:
            return f"${x / div:.2f}{unit}" if x / div < 100 else f"${x / div:.0f}{unit}"
    return f"${x:.0f}"


def home(ctx: Ctx) -> str:
    ctx.prefix = ""
    coins = ctx.scan["coins"]
    n_new = sum(len(c["new"]) for c in coins)
    n_coins = sum(1 for c in coins if c["new"])
    per = Counter(s["kind"] for c in coins for s in c["new"])
    n_bull = sum(n for k, n in per.items() if KINDS[k].direction == "bull")
    n_bear = n_new - n_bull
    kinds = "".join(f'<option value="{k.slug}">{escape(k.title)} ({per.get(k.slug, 0)})</option>'
                    for k in sorted(KINDS.values(), key=lambda k: -per.get(k.slug, 0)))
    rows = []
    for c in coins:
        chips = "".join(chip(s, link=ctx.href(coin_path(c["base"])), tip=True) for s in c["new"])
        live = escape(c["base"].upper() + "USDT")
        rows.append(
            f'<tr data-sym="{escape(c["base"].upper())}" data-vol="{c["qv"]:.0f}" data-chg="{c["change"]:.4f}" '
            f'data-n="{len(c["new"])}" data-rank="{c["rank"]}">'
            f'<td class="coin"><a href="{ctx.href(coin_path(c["base"]))}">{icon(c["base"])}'
            f'<span class="nm"><b>{escape(c["base"])}</b><small>Vol {escape(compact_usd(c["qv"]))}</small></span></a></td>'
            f'<td class="num px" data-price="{live}">{escape(usd(c["price"]))}</td>'
            f'<td class="num ch {updn(c["change"])}" data-chg-of="{live}">{pct(c["change"])}</td>'
            f'<td class="sigs">{chips}</td></tr>')
    body = f"""
<section class="head">
<div class="ht">
<h1>Crypto signal scanner</h1>
<p class="sub2">Top {len(coins)} coins · 1h, 4h and daily charts · closed candles only</p>
{status_line(ctx)}
</div>
<dl class="stats">
<div><dt>New signals</dt><dd class="num">{n_new}</dd></div>
<div><dt>Coins with signals</dt><dd class="num">{n_coins}<span class="soft"> / {len(coins)}</span></dd></div>
<div><dt>Bullish / bearish</dt><dd class="num">{n_bull}<span class="soft"> / </span>{n_bear}</dd></div>
</dl>
</section>
<section class="panel">
<div class="bar" aria-label="Filters">
<div class="seg" data-g="tf"><button type="button" class="on" data-v="">All</button><button type="button" data-v="1h">1h</button><button type="button" data-v="4h">4h</button><button type="button" data-v="1d">1d</button></div>
<div class="seg" data-g="dir"><button type="button" class="on" data-v="">Both</button><button type="button" data-v="bull">Bullish</button><button type="button" data-v="bear">Bearish</button></div>
<select id="kind" class="sel" aria-label="Signal type"><option value="">All signals ({n_new})</option>{kinds}</select>
<label class="tog"><input id="f-only" type="checkbox"><span>With signals</span></label>
<span class="grow"></span>
<input id="q" type="search" placeholder="Search coin" autocomplete="off" aria-label="Search coin">
<select id="sort" class="sel" aria-label="Sort"><option value="rank">Sort: volume</option><option value="n">Sort: most signals</option><option value="chg-desc">Sort: 24h gain</option><option value="chg-asc">Sort: 24h loss</option><option value="sym">Sort: name</option></select>
</div>
<table class="coins">
<thead><tr><th>Coin</th><th class="num">Price</th><th class="num">24h</th><th>New signals</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="empty" id="none" hidden>No coin matches these filters.</p>
<p id="count" class="fine" aria-live="polite"></p>
</section>
{refs_html(ctx)}"""
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": ctx.name, "url": ctx.url()}
    return page(ctx, "", f"{ctx.name}: {ctx.cfg['tagline']}",
                "Free crypto signal scanner: RSI, trend turns, golden and death crosses, double tops and bottoms, volume "
                "spikes and 30-day breakouts on the top 150 coins, refreshed every 15 minutes.", body, ld)


# ---------------------------------------------------------------- signal types

def signal_index(ctx: Ctx) -> str:
    ctx.prefix = "../"
    per = Counter(s["kind"] for c in ctx.scan["coins"] for s in c["new"])
    items = "".join(
        f'<a class="card" href="{ctx.href(signal_path(k.slug))}"><div class="ch"><span class="dot {k.direction}"></span>'
        f'<b>{escape(k.title)}</b><span class="num n">{per.get(k.slug, 0)}</span></div><p>{escape(k.about)}</p></a>'
        for k in KINDS.values())
    body = (f'<section class="hero slim"><p class="eyebrow">Signals</p><h1>Twelve signals, read on closed candles</h1>'
            f'<p class="sub">What each one means, and how many coins show it right now.</p></section>'
            f'<section class="cards">{items}</section>')
    return page(ctx, "signals/", "Crypto signals explained", "RSI, trend turns, golden and death crosses, double tops and "
                "bottoms, volume spikes and 30-day breakouts: what each signal means and which coins show it now.", body)


def signal_page(ctx: Ctx, slug: str) -> str:
    ctx.prefix = "../../"
    k = KINDS[slug]
    rows = []
    for c in ctx.scan["coins"]:
        for s in c["new"]:
            if s["kind"] != slug:
                continue
            live = escape(c["base"].upper() + "USDT")
            rows.append(f'<tr><td class="coin"><a href="{ctx.href(coin_path(c["base"]))}">{icon(c["base"])}<b>{escape(c["base"])}</b></a></td>'
                        f'<td><span class="tf">{escape(s["tf"])}</span></td>'
                        f'<td class="num px" data-price="{live}">{escape(usd(c["price"]))}</td>'
                        f'<td class="what">{escape(s["text"])}<span class="fine">{escape(s["tf"])} candle of {escape(bar_time(s["t"]))}</span></td></tr>')
    table = (f'<table class="coins list"><thead><tr><th>Coin</th><th>Chart</th><th class="num">Price</th><th>What happened</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table>' if rows else
             f'<p class="empty">No coin in the top {len(ctx.scan["coins"])} shows a new {escape(k.title.lower())} right now. '
             f'This page refreshes every 15 minutes.</p>')
    word = "bullish" if k.direction == "bull" else "bearish"
    body = (f'<section class="hero slim"><p class="eyebrow"><a href="{ctx.href("signals/")}">Signals</a> · usually read as {word}</p>'
            f'<h1><span class="dot {k.direction}"></span>{escape(k.title)} <span class="soft">· {len(rows)} now</span></h1>'
            f'<p class="sub">{escape(k.about)}</p>{status_line(ctx)}</section>{table}{refs_html(ctx)}')
    desc = f"Coins showing a {k.title.lower()} now on the 1h, 4h or daily chart, refreshed every 15 minutes. {k.about.split('. ')[0]}."
    return page(ctx, signal_path(slug), f"{k.title}: coins now", desc, body)


# ---------------------------------------------------------------- one coin

def coin_page(ctx: Ctx, c: dict, charts: dict) -> str:
    ctx.prefix = "../../"
    base = c["base"]
    tfs = ctx.cfg["timeframes"]
    live = escape(base.upper() + "USDT")
    tabs = "".join(f'<button type="button" data-tf="{tf}"{" class=on" if tf == "4h" else ""}>{tf}</button>' for tf in tfs)
    now_rows = []
    for tf in tfs:
        sigs = [s for s in c["new"] if s["tf"] == tf]
        rsi = c["rsi"].get(tf)
        chips = "".join(chip(s, with_tf=False, link=ctx.href(signal_path(s["kind"]))) for s in sigs) or '<span class="fine">No new signal</span>'
        now_rows.append(f'<div class="nr"><span class="tf">{tf}</span><div class="cs">{chips}</div>'
                        f'<span class="num rsi">RSI {"–" if rsi is None else f"{rsi:.0f}"}</span></div>')

    def item(s):
        k = KINDS[s["kind"]]
        return (f'<li><div class="when"><a class="chip {k.direction}" href="{ctx.href(signal_path(s["kind"]))}"><i>{escape(s["tf"])}</i>'
                f'{escape(k.title)}</a><span class="fine">{escape(s["tf"])} candle of {escape(bar_time(s["t"]))}</span></div>'
                f'<p>{escape(s["text"])}</p></li>')
    first, rest = c["history"][:20], c["history"][20:]
    hist = "".join(item(s) for s in first) or '<li class="fine">No signals in the period shown.</li>'
    more = (f'<details class="more"><summary>Show {len(rest)} more</summary><ul class="hist">{"".join(item(s) for s in rest)}</ul>'
            f'</details>' if rest else "")
    data = json.dumps({"tfs": charts}, separators=(",", ":")).replace("</", "<\\/")
    body = f"""
<section class="hero coinhero">
<p class="eyebrow"><a href="{ctx.href()}">Scanner</a> · #{c["rank"]} by 24h volume</p>
<div class="ct">
<h1>{icon(base, "lg")}{escape(base)}<span class="soft"> / USDT</span></h1>
<p class="quote"><span class="num big" data-price="{live}">{escape(usd(c["price"]))}</span><span class="num {updn(c["change"])}" data-chg-of="{live}" data-suffix=" 24h">{pct(c["change"])} 24h</span></p>
</div>
{status_line(ctx)}
</section>
<section class="chartcard">
<div class="seg tabs" role="tablist" aria-label="Timeframe">{tabs}</div>
<div id="chart" class="chart"><p class="fine">Loading the chart…</p></div>
<p class="fine">Closed candles only. ▲ bullish and ▼ bearish signals sit under and over their candle.</p>
<script type="application/json" id="chart-data">{data}</script>
</section>
<section class="now"><h2>Signals now</h2>{"".join(now_rows)}</section>
{refs_html(ctx, base)}
<section><h2>Recent signals</h2><ul class="hist">{hist}</ul>{more}</section>"""
    desc = (f"{base} signals now: RSI, trend turns, double tops and bottoms, volume spikes and 30-day breakouts on the "
            f"1h, 4h and daily charts, with a live price. Free, refreshed every 15 minutes.")
    return page(ctx, coin_path(base), f"{base} price and signals", desc, body,
                head_extra=f'<script src="{CHART_LIB}" defer></script>\n')


# ---------------------------------------------------------------- the rest

def not_found(ctx: Ctx) -> str:
    """Served for any missing address, at any depth: its links are absolute from the site root."""
    ctx.prefix = "/"
    return page(ctx, "404.html", "Page not found", "This page does not exist.",
                '<script>(function(){var p=location.pathname,l=p.toLowerCase();if(p!==l)location.replace(l+location.search+location.hash);})();</script>'
                '<section class="hero slim"><h1>Page not found</h1><p class="sub"><a href="/">Back to the scanner</a></p></section>')


def sitemap(ctx: Ctx) -> str:
    paths = ["", "signals/"] + [signal_path(s) for s in KINDS] + [coin_path(c["base"]) for c in ctx.scan["coins"]]
    day = datetime.fromtimestamp(ctx.scan["generated"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    urls = "".join(f"<url><loc>{escape(ctx.url(p))}</loc><lastmod>{day}</lastmod></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


def robots(ctx: Ctx) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {ctx.url('sitemap.xml')}\n"
