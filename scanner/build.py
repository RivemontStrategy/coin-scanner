"""Fetch, scan, write the site.

    python -m scanner.build --out _site

Fails (non-zero exit) when no data source works or too few coins could be read, so a bad run never replaces the
last good site."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import chart, site, sources, universe
from .signals import KINDS, is_new, scan

ROOT = Path(__file__).resolve().parents[1]
FETCH = 400            # candles fetched per chart: the 200-bar EMA needs history before the 200 bars shown
CHART_BARS = 120       # candles drawn on a coin's chart
SOURCE_LABEL = {"binance": "Binance", "okx": "OKX", "gate": "Gate", "mexc": "MEXC"}


def load_config() -> tuple[dict, list[dict]]:
    cfg = json.loads((ROOT / "config" / "site.json").read_text())
    if os.environ.get("SITE_URL"):
        cfg["base_url"] = os.environ["SITE_URL"]
    if os.environ.get("TOP_N"):
        cfg["top_n"] = int(os.environ["TOP_N"])
    if os.environ.get("SITE_NAME"):
        cfg["name"] = os.environ["SITE_NAME"]
    refs = json.loads((ROOT / "config" / "referrals.json").read_text()).get("exchanges", [])
    return cfg, refs


def analyse(src: sources.Source, pair: dict, tfs: list[str], keep: int, hist_limit: int):
    """One coin: candles per timeframe, every signal, the new ones, RSI now, and the chart bars."""
    from . import indicators
    new, history, rsi_now, bars_by_tf, sigs_by_tf = [], [], {}, {}, {}
    for tf in tfs:
        bars = src.klines(pair["symbol"], tf, FETCH)
        if len(bars) < 30:
            continue
        sigs = scan(bars, tf)
        shown_from = max(0, len(bars) - keep)
        r = indicators.rsi([b.c for b in bars])
        rsi_now[tf] = None if r[-1] is None else round(r[-1], 1)
        for s in sigs:
            if s.index < shown_from:
                continue
            j = s.to_json()
            history.append(j)
            if is_new(s, len(bars)):
                new.append(j)
        bars_by_tf[tf] = bars[-CHART_BARS:]
        sigs_by_tf[tf] = [s for s in sigs if s.t >= bars_by_tf[tf][0].t]
    if not bars_by_tf:
        return None
    order = {tf: i for i, tf in enumerate(tfs)}
    new.sort(key=lambda s: (order[s["tf"]], -s["t"]))
    history.sort(key=lambda s: -s["t"])
    coin = {"base": pair["base"], "symbol": pair["symbol"], "price": pair["last"], "change": pair["change_pct"],
            "qv": pair["quote_volume"], "rsi": rsi_now, "new": new, "history": history[:hist_limit]}
    return coin, bars_by_tf, sigs_by_tf


def run(out: Path, log=print) -> dict:
    cfg, refs = load_config()
    t0 = time.time()
    src, tickers = sources.pick(log)
    pairs = universe.top_pairs(tickers, cfg.get("top_n", universe.TOP_N))
    log(f"coins: {len(pairs)}")
    tfs = cfg["timeframes"]
    workers = {"binance": 8, "okx": 4, "gate": 6, "mexc": 6}.get(src.name, 4)

    def one(p):
        try:
            return analyse(src, p, tfs, cfg["bars"], cfg["history_limit"])
        except Exception as e:                            # noqa: BLE001 - one coin's failure never stops the run
            log(f"skip {p['symbol']}: {e}")
            return None

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(one, pairs))
    done = [(i, r) for i, r in enumerate(results) if r]
    if len(done) < max(min(20, len(pairs)), len(pairs) // 2):
        raise SystemExit(f"only {len(done)} of {len(pairs)} coins could be read; keeping the last site")
    coins, charts = [], {}
    for rank, (_i, (coin, bars_by_tf, sigs_by_tf)) in enumerate(done, 1):
        coin["rank"] = rank
        coins.append(coin)
        charts[coin["base"]] = {tf: chart.svg(b, sigs_by_tf[tf], label=f'{coin["base"]} {tf} candles')
                                for tf, b in bars_by_tf.items()}
    data = {"generated": int(time.time() * 1000), "source": src.name,
            "source_label": SOURCE_LABEL.get(src.name, src.name), "timeframes": tfs, "coins": coins}
    write(out, cfg, refs, data, charts)
    log(f"done: {len(coins)} coins, {sum(len(c['new']) for c in coins)} new signals, {time.time() - t0:.0f}s")
    return data


def write(out: Path, cfg: dict, refs: list[dict], data: dict, charts: dict) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    ctx = site.Ctx(cfg, refs, data)

    def put(rel: str, text: str):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    put("index.html", site.home(ctx))
    put("signals/index.html", site.signal_index(ctx))
    for slug in KINDS:
        put(f"signals/{slug}/index.html", site.signal_page(ctx, slug))
    for c in data["coins"]:
        put(f"coin/{c['base'].lower()}/index.html", site.coin_page(ctx, c, charts.get(c["base"], {})))
    put("404.html", site.not_found(ctx))
    put("sitemap.xml", site.sitemap(ctx))
    put("robots.txt", site.robots(ctx))
    put("data/scan.json", json.dumps(data, separators=(",", ":")))
    put(".nojekyll", "")
    for f in ("style.css", "app.js"):
        shutil.copy(ROOT / "static" / f, out / "assets" / f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_site")
    a = ap.parse_args(argv)
    run(Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
