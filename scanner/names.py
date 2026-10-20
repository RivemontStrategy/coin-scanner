"""Coin names and logos for the tables (Bitcoin over BTC), from CoinGecko's public markets list (top 500 by market cap).
Best effort: if CoinGecko cannot be reached, coins keep their ticker as the name and CoinCap's icon."""
from __future__ import annotations

import json
import re
import urllib.request

URL = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={}"


def fetch(log=print, pages: int = 2, timeout: float = 15.0) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for p in range(1, pages + 1):
        try:
            req = urllib.request.Request(URL.format(p), headers={"User-Agent": "rivemont-scanner", "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                rows = json.loads(r.read())
        except Exception as e:                       # noqa: BLE001 - names are a nicety, never a reason to fail
            log(f"names: CoinGecko page {p} failed: {e}")
            break
        for m in rows:
            sym = str(m.get("symbol", "")).upper()
            if sym and sym not in out:               # the first one is the biggest by market cap
                name = re.sub(r"\s*\(.*?\)\s*", " ", str(m.get("name") or sym)).strip()
                img = str(m.get("image") or "").replace("/large/", "/small/")
                out[sym] = (name, img)
    log(f"names: {len(out)} from CoinGecko")
    return out


def attach(coins: list[dict], log=print) -> None:
    names = fetch(log)
    for c in coins:
        n = names.get(c["base"].upper())
        if n:
            c["name"], c["img"] = n[0], n[1]
