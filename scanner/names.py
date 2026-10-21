"""Coin names, logos and market data for the tables (Bitcoin over BTC, market cap, 1h and 7d moves), from CoinGecko's
public markets list (top 500 by market cap), plus the global market figures and the Fear & Greed index. Best effort: if
a source cannot be reached, the site shows what it has (ticker, CoinCap icon, our own 24h figures) and never fails."""
from __future__ import annotations

import json
import re
import time
import urllib.request

MARKETS = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={}"
           "&price_change_percentage=1h,24h,7d")
GLOBAL = "https://api.coingecko.com/api/v3/global"
FEAR_GREED = "https://api.alternative.me/fng/?limit=1"


def _get(url: str, timeout: float = 15.0):
    req = urllib.request.Request(url, headers={"User-Agent": "rivemont-scanner", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch(log=print, pages: int = 2) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in range(1, pages + 1):
        try:
            rows = _get(MARKETS.format(p))
        except Exception as e:                       # noqa: BLE001 - names are a nicety, never a reason to fail
            log(f"names: CoinGecko page {p} failed: {e}")
            break
        for m in rows:
            sym = str(m.get("symbol", "")).upper()
            if sym and sym not in out:               # the first one is the biggest by market cap
                out[sym] = {
                    "name": re.sub(r"\s*\(.*?\)\s*", " ", str(m.get("name") or sym)).strip(),
                    "img": str(m.get("image") or "").replace("/large/", "/small/"),
                    "mcap": m.get("market_cap"), "mcap_rank": m.get("market_cap_rank"),
                    "ch1h": m.get("price_change_percentage_1h_in_currency"),
                    "ch7d": m.get("price_change_percentage_7d_in_currency"),
                    "supply": m.get("circulating_supply"),
                }
        time.sleep(1.5)
    log(f"names: {len(out)} from CoinGecko")
    return out


def attach(coins: list[dict], log=print) -> None:
    names = fetch(log)
    for c in coins:
        n = names.get(c["base"].upper())
        if not n:
            continue
        c["name"], c["img"] = n["name"], n["img"]
        for k in ("mcap", "mcap_rank", "ch1h", "ch7d", "supply"):
            if n.get(k) is not None:
                c[k] = n[k]


def market(log=print) -> dict:
    """Total market cap and its 24h change, 24h volume, BTC and ETH dominance, Fear & Greed."""
    g: dict = {}
    try:
        d = _get(GLOBAL)["data"]
        g = {"mcap": d["total_market_cap"]["usd"], "mcap_ch": d.get("market_cap_change_percentage_24h_usd"),
             "vol": d["total_volume"]["usd"], "btc_dom": d["market_cap_percentage"].get("btc"),
             "eth_dom": d["market_cap_percentage"].get("eth")}
    except Exception as e:                           # noqa: BLE001
        log(f"global: CoinGecko failed: {e}")
    try:
        f = _get(FEAR_GREED)["data"][0]
        g["fng"], g["fng_label"] = int(f["value"]), str(f["value_classification"])
    except Exception as e:                           # noqa: BLE001
        log(f"global: Fear & Greed failed: {e}")
    return g
