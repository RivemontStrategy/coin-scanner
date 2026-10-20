"""The static pages: home, one page per signal type and one per coin, plus sitemap.xml, robots.txt and 404.html.
Plain HTML, one stylesheet and one small script; no trackers, no third-party requests."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from urllib.parse import urlparse

from .signals import KINDS, bar_time, fmt

TF_NAME = {"1h": "1-hour", "4h": "4-hour", "1d": "daily"}
ASSET_V = "1"          # bump to refresh cached CSS/JS


class Ctx:
    def __init__(self, cfg: dict, referrals: list[dict], scan: dict):
        self.cfg, self.scan = cfg, scan
        self.name = cfg["name"]
        self.base = cfg["base_url"].rstrip("/") + "/"
        self.root = urlparse(self.base).path or "/"
        self.refs = [r for r in referrals if (r.get("url") or "").strip()]

    def url(self, path: str = "") -> str:
        return self.base + path.lstrip("/")

    def href(self, path: str = "") -> str:
        return self.root + path.lstrip("/")


def coin_path(base: str) -> str:
    return f"coin/{base.lower()}/"


def signal_path(slug: str) -> str:
    return f"signals/{slug}/"


def _ago_time(ms: int) -> str:
    iso = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f'<time class="ago" datetime="{iso}" data-ts="{ms}">{escape(bar_time(ms))}</time>'


def _pct(x: float) -> str:
    sign = "+" if x > 0 else "−" if x < 0 else ""
    return f"{sign}{abs(x):.2f}%"


def chip(sig: dict, with_tf: bool = True, link: str | None = None) -> str:
    k = KINDS[sig["kind"]]
    tf = f'<b>{escape(sig["tf"])}</b> ' if with_tf else ""
    title = f'{k.title} · {sig["tf"]} · {bar_time(sig["t"])}'
    inner = f'{tf}{escape(k.short)}'
    attrs = f'class="chip {k.direction}" data-kind="{k.slug}" data-tf="{sig["tf"]}" data-dir="{k.direction}" title="{escape(title)}"'
    return f'<a {attrs} href="{escape(link)}">{inner}</a>' if link else f'<span {attrs}>{inner}</span>'


def refs_html(ctx: Ctx, coin: str | None = None) -> str:
    if not ctx.refs:
        return ""
    btns = "".join(f'<a class="btn" href="{escape(r["url"])}" target="_blank" rel="sponsored nofollow noopener">'
                   f'{escape(("Trade " + coin + " on ") if coin else "Open ")}{escape(r["name"])}</a>' for r in ctx.refs)
    return (f'<aside class="refs" aria-label="Exchanges"><div class="btns">{btns}</div>'
            f'<p class="muted small">Referral links: we may earn a commission if you sign up. It costs you nothing.</p></aside>')


def page(ctx: Ctx, path: str, title: str, desc: str, body: str, ld: dict | None = None) -> str:
    full_title = title if ctx.name in title else f"{title} · {ctx.name}"
    url = ctx.url(path)
    ld_html = f'<script type="application/ld+json">{json.dumps(ld, separators=(",", ":"))}</script>' if ld else ""
    gen = ctx.scan["generated"]
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
<meta name="theme-color" content="#0e1013">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect width='16' height='16' rx='4' fill='%2311151a'/%3E%3Cpath d='M3 11l3-3 2 2 5-5' stroke='%2346c38a' stroke-width='2' fill='none'/%3E%3C/svg%3E">
<script>try{{var t=localStorage.getItem("cs-theme");if(t)document.documentElement.dataset.theme=t;else if(matchMedia("(prefers-color-scheme: light)").matches)document.documentElement.dataset.theme="light"}}catch(e){{}}</script>
<link rel="stylesheet" href="{ctx.href('assets/style.css')}?v={ASSET_V}">
{ld_html}
</head>
<body>
<header class="top"><div class="wrap">
<a class="logo" href="{ctx.href()}">{escape(ctx.name)}</a>
<nav><a href="{ctx.href('signals/')}">Signals</a><span class="beta">Free during beta</span>
<button class="theme" type="button" aria-label="Switch light or dark"><svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.5" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1.5a6.5 6.5 0 0 1 0 13z" fill="currentColor"/></svg></button></nav>
</div></header>
<main class="wrap">
{body}
</main>
<footer class="wrap foot">
<p><strong>Not financial advice.</strong> Signals are computed automatically from public exchange data and can be wrong
or late. Do your own research.</p>
<p>Free during beta · Data from {escape(ctx.scan["source_label"])}'s public market data, closed candles only · Updated {_ago_time(gen)}</p>
</footer>
<script src="{ctx.href('assets/app.js')}?v={ASSET_V}" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- home

def home(ctx: Ctx) -> str:
    coins = ctx.scan["coins"]
    kinds_opts = "".join(f'<option value="{k.slug}">{escape(k.title)}</option>' for k in KINDS.values())
    rows = []
    for c in coins:
        chips = "".join(chip(s, link=ctx.href(coin_path(c["base"]))) for s in c["new"])
        cls = "up" if c["change"] > 0 else "dn" if c["change"] < 0 else ""
        rows.append(
            f'<tr data-sym="{escape(c["base"])}" data-vol="{c["qv"]:.0f}" data-chg="{c["change"]:.4f}" '
            f'data-n="{len(c["new"])}" data-rank="{c["rank"]}">'
            f'<td class="coin"><a href="{ctx.href(coin_path(c["base"]))}"><b>{escape(c["base"])}</b></a>'
            f'<span class="muted small">#{c["rank"]}</span></td>'
            f'<td class="num">{escape(fmt(c["price"]))}</td>'
            f'<td class="num {cls}">{_pct(c["change"])}</td>'
            f'<td class="sigs">{chips or "<span class=muted>–</span>"}</td></tr>')
    n_new = sum(len(c["new"]) for c in coins)
    n_coins = sum(1 for c in coins if c["new"])
    body = f"""
<section class="hero">
<h1>Crypto signal scanner</h1>
<p class="lead">{escape(ctx.cfg["tagline"])}</p>
<p class="muted">{n_new} new signals on {n_coins} of the top {len(coins)} coins, from the last 3 closed candles on the
1-hour, 4-hour and daily charts. Updated {_ago_time(ctx.scan["generated"])}.</p>
</section>
{refs_html(ctx)}
<section class="filters" aria-label="Filters">
<input id="q" type="search" placeholder="Search coin" autocomplete="off" aria-label="Search coin">
<select id="f-kind" aria-label="Signal"><option value="">All signals</option>{kinds_opts}</select>
<select id="f-tf" aria-label="Timeframe"><option value="">All timeframes</option><option value="1h">1h</option><option value="4h">4h</option><option value="1d">1d</option></select>
<select id="f-dir" aria-label="Direction"><option value="">Any direction</option><option value="bull">Bullish</option><option value="bear">Bearish</option></select>
<label class="check"><input id="f-only" type="checkbox"> Only coins with new signals</label>
<select id="sort" aria-label="Sort"><option value="rank">Sort: volume</option><option value="n">Sort: most signals</option><option value="chg-desc">Sort: 24h gain</option><option value="chg-asc">Sort: 24h loss</option><option value="sym">Sort: name</option></select>
</section>
<p id="count" class="muted small" aria-live="polite"></p>
<div class="tablewrap"><table class="coins">
<thead><tr><th>Coin</th><th class="num">Price</th><th class="num">24h</th><th>New signals</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<section class="kinds"><h2>What the signals mean</h2><ul class="kindlist">
{"".join(f'<li><a href="{ctx.href(signal_path(k.slug))}">{escape(k.title)}</a> <span class="muted">{escape(k.about.split(". ")[0])}.</span></li>' for k in KINDS.values())}
</ul></section>"""
    ld = {"@context": "https://schema.org", "@type": "WebSite", "name": ctx.name, "url": ctx.url()}
    return page(ctx, "", f"{ctx.name}: free crypto signal scanner", ctx.cfg["tagline"], body, ld)


# ---------------------------------------------------------------- one signal type

def signal_index(ctx: Ctx) -> str:
    items = []
    for k in KINDS.values():
        n = sum(1 for c in ctx.scan["coins"] for s in c["new"] if s["kind"] == k.slug)
        items.append(f'<li><a href="{ctx.href(signal_path(k.slug))}"><b>{escape(k.title)}</b></a> '
                     f'<span class="chipcount {k.direction}">{n} now</span><br><span class="muted">{escape(k.about)}</span></li>')
    body = (f'<h1>Signals</h1><p class="lead">Every signal the scanner looks for, and how many coins show it right now.</p>'
            f'<ul class="kindlist big">{"".join(items)}</ul>')
    return page(ctx, "signals/", "Crypto signals explained", "RSI, trend changes, golden and death crosses, double tops and "
                "bottoms, volume spikes and 30-day breakouts: what each signal means and which coins show it now.", body)


def signal_page(ctx: Ctx, slug: str) -> str:
    k = KINDS[slug]
    rows = []
    for c in ctx.scan["coins"]:
        for s in c["new"]:
            if s["kind"] != slug:
                continue
            rows.append(f'<tr><td class="coin"><a href="{ctx.href(coin_path(c["base"]))}"><b>{escape(c["base"])}</b></a></td>'
                        f'<td>{escape(s["tf"])}</td><td class="num">{escape(fmt(c["price"]))}</td>'
                        f'<td class="small">{escape(s["text"])}<br><span class="muted">{escape(bar_time(s["t"]))}</span></td></tr>')
    table = (f'<div class="tablewrap"><table class="coins"><thead><tr><th>Coin</th><th>Chart</th><th class="num">Price</th>'
             f'<th>What happened</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>' if rows else
             f'<p class="empty">No coin in the top {len(ctx.scan["coins"])} shows a new {escape(k.title.lower())} right now. '
             f'This page updates every 30 minutes.</p>')
    word = "bullish" if k.direction == "bull" else "bearish"
    body = (f'<p class="crumbs"><a href="{ctx.href("signals/")}">Signals</a></p>'
            f'<h1>{escape(k.title)}: coins now</h1><p class="lead">{escape(k.about)}</p>'
            f'<p class="muted">Usually read as a {word} sign. Coins below showed it in one of their last 3 closed candles. '
            f'Updated {_ago_time(ctx.scan["generated"])}.</p>{table}{refs_html(ctx)}')
    desc = f"Coins showing a {k.title.lower()} now on the 1h, 4h or daily chart, updated every 30 minutes. {k.about.split('. ')[0]}."
    return page(ctx, signal_path(slug), f"{k.title} scanner: coins now", desc, body)


# ---------------------------------------------------------------- one coin

def coin_page(ctx: Ctx, c: dict, charts: dict[str, str]) -> str:
    base = c["base"]
    tfs = ctx.cfg["timeframes"]
    cls = "up" if c["change"] > 0 else "dn" if c["change"] < 0 else ""
    tabs = "".join(f'<input type="radio" name="tf" id="tf-{tf}"{" checked" if tf == "4h" else ""}>'
                   f'<label for="tf-{tf}">{tf}</label>' for tf in tfs)
    panes = "".join(f'<div class="pane" data-tf="{tf}">{charts.get(tf, "")}</div>' for tf in tfs)
    now_rows = []
    for tf in tfs:
        sigs = [s for s in c["new"] if s["tf"] == tf]
        rsi = c["rsi"].get(tf)
        chips = "".join(chip(s, with_tf=False, link=ctx.href(signal_path(s["kind"]))) for s in sigs) or '<span class="muted">No new signal</span>'
        now_rows.append(f'<tr><th>{tf}</th><td>{chips}</td><td class="num muted">RSI {"–" if rsi is None else f"{rsi:.0f}"}</td></tr>')
    hist = "".join(f'<li><div class="when"><a class="chip {KINDS[s["kind"]].direction}" href="{ctx.href(signal_path(s["kind"]))}">'
                   f'{escape(s["tf"])} · {escape(KINDS[s["kind"]].title)}</a><span class="muted small">{escape(bar_time(s["t"]))}</span></div>'
                   f'<span>{escape(s["text"])}</span></li>'
                   for s in c["history"]) or '<li class="muted">No signals in the period shown.</li>'
    body = f"""
<p class="crumbs"><a href="{ctx.href()}">All coins</a></p>
<div class="coinhead"><h1>{escape(base)} <span class="muted">/ USDT</span></h1>
<p class="price"><b>{escape(fmt(c["price"]))}</b> <span class="{cls}">{_pct(c["change"])} 24h</span></p></div>
<section class="chartbox">{tabs}{panes}<p class="muted small">Closed candles only. ▲ bullish and ▼ bearish signals are
marked under and over their candle.</p></section>
<section><h2>Signals now</h2><table class="now">{"".join(now_rows)}</table></section>
{refs_html(ctx, base)}
<section><h2>Recent signals</h2><ul class="hist">{hist}</ul></section>"""
    desc = (f"{base} signals now: RSI, trend changes, double tops and bottoms, volume spikes and 30-day breakouts on the "
            f"1h, 4h and daily charts. Free, updated every 30 minutes.")
    return page(ctx, coin_path(base), f"{base} signals: RSI, trend and breakouts", desc, body)


# ---------------------------------------------------------------- the rest

def not_found(ctx: Ctx) -> str:
    return page(ctx, "404.html", "Page not found", "This page does not exist.",
                f'<h1>Page not found</h1><p><a href="{ctx.href()}">Back to all coins</a></p>')


def sitemap(ctx: Ctx) -> str:
    paths = ["", "signals/"] + [signal_path(s) for s in KINDS] + [coin_path(c["base"]) for c in ctx.scan["coins"]]
    day = datetime.fromtimestamp(ctx.scan["generated"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    urls = "".join(f"<url><loc>{escape(ctx.url(p))}</loc><lastmod>{day}</lastmod></url>" for p in paths)
    return f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'


def robots(ctx: Ctx) -> str:
    return f"User-agent: *\nAllow: /\nSitemap: {ctx.url('sitemap.xml')}\n"
