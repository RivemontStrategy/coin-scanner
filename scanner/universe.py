"""Which coins the scanner covers: the top USDT spot pairs by 24-hour quote volume, without what config/exclude.json
lists (stablecoins, tokenized stocks and ETFs, gold tokens, wrapped duplicates) and without leveraged tokens."""
from __future__ import annotations

import json
import re
from pathlib import Path

TOP_N = 150
EXCLUDE_FILE = Path(__file__).resolve().parents[1] / "config" / "exclude.json"


def excluded() -> set[str]:
    """Every base asset listed in config/exclude.json (stablecoins, tokenized stocks, gold, wrapped duplicates)."""
    data = json.loads(EXCLUDE_FILE.read_text())
    return {b.upper() for k, v in data.items() if not k.startswith("_") for b in v}


LEVERAGED_TAIL = re.compile(r"\d+[LS]$")                   # Gate / MEXC style: BTC3L, ETH5S
LEVERAGED_WORDS = ("UP", "DOWN", "BULL", "BEAR")            # old Binance style: BTCUP, ETHBULL


def is_stable(base: str, last: float, change_pct: float) -> bool:
    """A dollar coin missing from the list: named like one and trading at a dollar."""
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


def top_pairs(tickers: list[dict], n: int = TOP_N, exclude: set[str] | None = None) -> list[dict]:
    bases = {t["base"].upper() for t in tickers}
    out_list = excluded() if exclude is None else exclude
    keep = [t for t in tickers
            if t["last"] > 0 and t["quote_volume"] > 0
            and t["base"].upper() not in out_list
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
