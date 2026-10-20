"""Public market-data sources, tried in order until one works from where the build runs. GitHub's runners are in the
US, where api.binance.com answers 451, so Binance's public data mirror comes first, then OKX, Gate and MEXC.
Only public endpoints, no keys."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from .signals import Bar

UA = "coin-scanner (+https://github.com/RivemontStrategy/coin-scanner)"
TF_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}


class SourceError(Exception):
    pass


class Source:
    name = "base"
    max_limit = 1000
    min_gap = 0.05                 # seconds between requests (all threads together)

    def __init__(self):
        self._lock = threading.Lock()
        self._next = 0.0

    def _get(self, url: str, tries: int = 3):
        for attempt in range(tries):
            with self._lock:                          # simple shared pacing, so parallel threads stay polite
                wait = self._next - time.monotonic()
                if wait > 0:
                    time.sleep(wait)
                self._next = time.monotonic() + self.min_gap
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code in (418, 429) or e.code >= 500:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise SourceError(f"{self.name}: HTTP {e.code} for {url}") from e
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
                if attempt == tries - 1:
                    raise SourceError(f"{self.name}: {e} for {url}") from e
                time.sleep(2 * (attempt + 1))
        raise SourceError(f"{self.name}: gave up on {url}")

    def tickers(self) -> list[dict]:
        """USDT spot pairs: {"base", "symbol", "last", "change_pct", "quote_volume"}."""
        raise NotImplementedError

    def klines(self, symbol: str, tf: str, limit: int) -> list[Bar]:
        """Closed candles only, oldest first."""
        raise NotImplementedError


def closed(bars: list[Bar], tf: str, now_ms: int | None = None) -> list[Bar]:
    now = int(time.time() * 1000) if now_ms is None else now_ms
    return [b for b in bars if b.t + TF_MS[tf] <= now]


def _change(last: float, open_: float) -> float:
    return (last / open_ - 1) * 100 if open_ else 0.0


class BinanceVision(Source):
    name = "binance"
    base = "https://data-api.binance.vision/api/v3"
    max_limit = 1000
    min_gap = 0.05

    def tickers(self):
        # the 24h list still carries delisted pairs with their last day's volume: keep the ones trading now
        info = self._get(f"{self.base}/exchangeInfo?symbolStatus=TRADING&showPermissionSets=false")
        live = {x["symbol"] for x in info.get("symbols", []) if x.get("quoteAsset") == "USDT" and x.get("status") == "TRADING"}
        out = []
        for t in self._get(f"{self.base}/ticker/24hr"):
            s = t.get("symbol", "")
            if s not in live or float(t.get("quoteVolume") or 0) <= 0:
                continue
            last = float(t["lastPrice"])
            out.append({"base": s[:-4], "symbol": s, "last": last,
                        "change_pct": _change(last, float(t.get("openPrice") or 0)),
                        "quote_volume": float(t["quoteVolume"])})
        return out

    def klines(self, symbol, tf, limit):
        q = urllib.parse.urlencode({"symbol": symbol, "interval": tf, "limit": min(limit, self.max_limit)})
        rows = self._get(f"{self.base}/klines?{q}")
        return closed([Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in rows], tf)


class Okx(Source):
    name = "okx"
    base = "https://www.okx.com/api/v5/market"
    max_limit = 300
    min_gap = 0.06                 # public candles: 40 requests per 2 seconds
    BAR = {"1h": "1H", "4h": "4H", "1d": "1Dutc"}

    def tickers(self):
        out = []
        for t in self._get(f"{self.base}/tickers?instType=SPOT").get("data", []):
            inst = t.get("instId", "")
            if not inst.endswith("-USDT"):
                continue
            last = float(t.get("last") or 0)
            out.append({"base": inst[:-5], "symbol": inst, "last": last,
                        "change_pct": _change(last, float(t.get("open24h") or 0)),
                        "quote_volume": float(t.get("volCcy24h") or 0)})
        return out

    def klines(self, symbol, tf, limit):
        q = urllib.parse.urlencode({"instId": symbol, "bar": self.BAR[tf], "limit": min(limit, self.max_limit)})
        rows = self._get(f"{self.base}/candles?{q}").get("data", [])
        bars = [Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
                for r in rows if len(r) < 9 or r[8] == "1"]   # confirm == "1": the candle is closed
        return closed(sorted(bars), tf)


class Gate(Source):
    name = "gate"
    base = "https://api.gateio.ws/api/v4/spot"
    max_limit = 1000
    min_gap = 0.06

    def tickers(self):
        out = []
        for t in self._get(f"{self.base}/tickers"):
            pair = t.get("currency_pair", "")
            if not pair.endswith("_USDT"):
                continue
            out.append({"base": pair[:-5], "symbol": pair, "last": float(t.get("last") or 0),
                        "change_pct": float(t.get("change_percentage") or 0),
                        "quote_volume": float(t.get("quote_volume") or 0)})
        return out

    def klines(self, symbol, tf, limit):
        q = urllib.parse.urlencode({"currency_pair": symbol, "interval": tf, "limit": min(limit, self.max_limit)})
        rows = self._get(f"{self.base}/candlesticks?{q}")
        # [time (s), quote volume, close, high, low, open, base volume, closed]
        bars = [Bar(int(r[0]) * 1000, float(r[5]), float(r[3]), float(r[4]), float(r[2]), float(r[6]))
                for r in rows if len(r) < 8 or str(r[7]).lower() == "true"]
        return closed(sorted(bars), tf)


class Mexc(Source):
    name = "mexc"
    base = "https://api.mexc.com/api/v3"
    max_limit = 1000
    min_gap = 0.06
    INTERVAL = {"1h": "60m", "4h": "4h", "1d": "1d"}

    def tickers(self):
        out = []
        for t in self._get(f"{self.base}/ticker/24hr"):
            s = t.get("symbol", "")
            if not s.endswith("USDT"):
                continue
            last = float(t.get("lastPrice") or 0)
            out.append({"base": s[:-4], "symbol": s, "last": last,
                        "change_pct": _change(last, float(t.get("openPrice") or 0)),
                        "quote_volume": float(t.get("quoteVolume") or 0)})
        return out

    def klines(self, symbol, tf, limit):
        q = urllib.parse.urlencode({"symbol": symbol, "interval": self.INTERVAL[tf], "limit": min(limit, self.max_limit)})
        rows = self._get(f"{self.base}/klines?{q}")
        return closed([Bar(int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])) for r in rows], tf)


ORDER = (BinanceVision, Okx, Gate, Mexc)


def pick(log=print, min_pairs: int = 50) -> tuple[Source, list[dict]]:
    """The first source whose tickers answer with enough USDT pairs and whose candles work."""
    errors = []
    only = os.environ.get("SCANNER_SOURCE")          # force one source, e.g. to test a fallback
    for cls in [c for c in ORDER if not only or c.name == only]:
        src = cls()
        try:
            tk = src.tickers()
            if len(tk) < min_pairs:
                raise SourceError(f"{src.name}: only {len(tk)} USDT pairs")
            top = max(tk, key=lambda t: t["quote_volume"])
            if not src.klines(top["symbol"], "1h", 5):
                raise SourceError(f"{src.name}: no candles for {top['symbol']}")
            log(f"source: {src.name} ({len(tk)} USDT pairs)")
            return src, tk
        except Exception as e:                            # noqa: BLE001 - any failure moves on to the next source
            errors.append(str(e))
            log(f"source {src.name} failed: {e}")
    raise SourceError("no data source worked: " + " | ".join(errors))
