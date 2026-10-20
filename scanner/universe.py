"""Which coins the scanner covers: the top USDT spot pairs by 24-hour quote volume, without stablecoins, fiat tokens
and leveraged tokens."""
from __future__ import annotations

import re

TOP_N = 150

STABLE = {
    "USDC", "USDT", "FDUSD", "TUSD", "BUSD", "DAI", "USDP", "USDD", "PYUSD", "USDE", "USDS", "USD1", "USDJ", "USDK",
    "USDN", "USDX", "USDQ", "USDR", "RLUSD", "BFUSD", "FRAX", "LUSD", "GUSD", "SUSD", "XUSD", "CUSD", "EURI", "EURC",
    "EURT", "AEUR", "EUR", "GBP", "AUD", "BRL", "TRY", "JPY", "UAH", "ZAR", "IDRT", "BIDR", "BVND", "VAI",
}
LEVERAGED_TAIL = re.compile(r"\d+[LS]$")                   # Gate / MEXC style: BTC3L, ETH5S
LEVERAGED_WORDS = ("UP", "DOWN", "BULL", "BEAR")            # old Binance style: BTCUP, ETHBULL


def is_stable(base: str, last: float, change_pct: float) -> bool:
    if base.upper() in STABLE:
        return True
    # anything else named like a dollar coin and trading at a dollar is a stablecoin too
    return "USD" in base.upper() and 0.97 <= last <= 1.03 and abs(change_pct) < 1.5


def is_leveraged(base: str, all_bases: set[str]) -> bool:
    b = base.upper()
    if LEVERAGED_TAIL.search(b) and LEVERAGED_TAIL.sub("", b) in all_bases:
        return True
    for w in LEVERAGED_WORDS:
        # BTCUP is leveraged when BTC is listed too; JUP is not (no "J")
        if b.endswith(w) and len(b) > len(w) and b[:-len(w)] in all_bases:
            return True
    return False


def top_pairs(tickers: list[dict], n: int = TOP_N) -> list[dict]:
    bases = {t["base"].upper() for t in tickers}
    keep = [t for t in tickers
            if t["last"] > 0 and t["quote_volume"] > 0
            and not is_stable(t["base"], t["last"], t["change_pct"])
            and not is_leveraged(t["base"], bases)]
    keep.sort(key=lambda t: t["quote_volume"], reverse=True)
    seen, out = set(), []
    for t in keep:                                         # one row per coin
        if t["base"].upper() in seen:
            continue
        seen.add(t["base"].upper())
        out.append(t)
        if len(out) >= n:
            break
    return out
