import json
import tempfile
import unittest
from pathlib import Path

from scanner import build, site, sources, universe
from scanner.signals import Bar


def t(base, qv, last=10.0, chg=1.0):
    return {"base": base, "symbol": base + "USDT", "last": last, "change_pct": chg, "quote_volume": qv}


class Universe(unittest.TestCase):
    def test_stables_and_leveraged_are_out(self):
        tk = [t("BTC", 9e9), t("USDC", 8e9, 1.0, 0.0), t("FDUSD", 7e9, 1.0, 0.01), t("BTCUP", 6e9), t("ETH3L", 5e9),
              t("ETH", 4e9), t("JUP", 3e9), t("NEWUSD", 2e9, 1.001, 0.02), t("EUR", 1e9, 1.08, 0.1)]
        got = [p["base"] for p in universe.top_pairs(tk)]
        self.assertEqual(got, ["BTC", "ETH", "JUP"])

    def test_top_n_by_volume(self):
        tk = [t(f"C{i}", float(i)) for i in range(1, 300)]
        got = universe.top_pairs(tk, 150)
        self.assertEqual(len(got), 150)
        self.assertEqual(got[0]["base"], "C299")


class Closed(unittest.TestCase):
    def test_open_candle_is_dropped(self):
        h = 3_600_000
        bars = [Bar(0, 1, 1, 1, 1, 1), Bar(h, 1, 1, 1, 1, 1)]
        self.assertEqual(len(sources.closed(bars, "1h", now_ms=2 * h)), 2)
        self.assertEqual(len(sources.closed(bars, "1h", now_ms=2 * h - 1)), 1)


class Pages(unittest.TestCase):
    def setUp(self):
        sig = {"kind": "rsi-oversold", "tf": "4h", "t": 1_760_000_000_000, "price": 9.5,
               "text": "RSI(14) fell to 28.0, at or below 30, on the 4h chart.", "dir": "bull"}
        self.data = {"generated": 1_760_000_100_000, "source": "binance", "source_label": "Binance",
                     "timeframes": ["1h", "4h", "1d"],
                     "coins": [{"base": "ABC", "symbol": "ABCUSDT", "price": 9.5, "change": -3.2, "qv": 1e8, "rank": 1,
                                "rsi": {"1h": 40.0, "4h": 28.0, "1d": None}, "new": [sig], "history": [sig]},
                               {"base": "XYZ", "symbol": "XYZUSDT", "price": 0.0012345, "change": 2.0, "qv": 1e7, "rank": 2,
                                "rsi": {}, "new": [], "history": []}]}
        self.cfg = {"name": "Test Scanner", "tagline": "Tagline.", "base_url": "https://example.github.io/coin-scanner/",
                    "timeframes": ["1h", "4h", "1d"], "bars": 200, "history_limit": 40}

    def write(self, refs):
        d = Path(tempfile.mkdtemp())
        build.write(d, self.cfg, refs, self.data, {"ABC": {"4h": "<svg></svg>"}})
        return d

    def test_every_page_and_file(self):
        d = self.write([])
        for rel in ("index.html", "signals/index.html", "signals/rsi-oversold/index.html", "coin/abc/index.html",
                    "coin/xyz/index.html", "404.html", "sitemap.xml", "robots.txt", "data/scan.json",
                    "assets/style.css", "assets/app.js", ".nojekyll"):
            self.assertTrue((d / rel).exists(), rel)
        home = (d / "index.html").read_text()
        self.assertIn('<link rel="canonical" href="https://example.github.io/coin-scanner/">', home)
        self.assertIn('href="/coin-scanner/coin/abc/"', home)
        self.assertIn("Not financial advice", home)
        self.assertIn("Free during beta", home)
        self.assertIn('property="og:title"', home)
        sm = (d / "sitemap.xml").read_text()
        self.assertIn("https://example.github.io/coin-scanner/coin/xyz/", sm)
        self.assertIn("Sitemap: https://example.github.io/coin-scanner/sitemap.xml", (d / "robots.txt").read_text())
        page = (d / "signals/rsi-oversold/index.html").read_text()
        self.assertIn("ABC", page)
        self.assertIn("No coin", (d / "signals/golden-cross/index.html").read_text())
        json.loads((d / "data/scan.json").read_text())

    def test_no_trackers_or_third_party_requests(self):
        d = self.write([])
        for p in d.rglob("*.html"):
            html = p.read_text()
            for bad in ("google-analytics", "googletagmanager", "gtag(", "facebook.net", "fonts.googleapis", "<iframe"):
                self.assertNotIn(bad, html, f"{bad} in {p}")

    def test_referral_buttons_only_with_a_link(self):
        d = self.write([{"id": "bybit", "name": "Bybit", "url": ""}])
        self.assertNotIn("Bybit", (d / "index.html").read_text())
        d = self.write([{"id": "bybit", "name": "Bybit", "url": "https://example.com/ref"}])
        home = (d / "index.html").read_text()
        self.assertIn('href="https://example.com/ref"', home)
        self.assertIn('rel="sponsored nofollow noopener"', home)

    def test_tiny_prices_keep_their_digits(self):
        self.assertEqual(site.fmt(0.0012346), "0.001235")
        self.assertEqual(site.fmt(64250.4), "64,250")


if __name__ == "__main__":
    unittest.main()
