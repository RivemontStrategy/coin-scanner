"""Which public data sources answer from here (run on a GitHub runner by .github/workflows/probe.yml).
Prints one line per source and endpoint; exits 0 when at least one source works end to end."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scanner import sources  # noqa: E402

ok_any = False
for cls in sources.ORDER:
    src = cls()
    t0 = time.time()
    try:
        tk = src.tickers()
        top = max(tk, key=lambda t: t["quote_volume"])
        bars = {tf: len(src.klines(top["symbol"], tf, 400)) for tf in ("1h", "4h", "1d")}
        print(f"OK    {src.name:8} {len(tk)} USDT pairs, top {top['symbol']}, closed candles {bars}, {time.time() - t0:.1f}s")
        ok_any = True
    except Exception as e:  # noqa: BLE001
        print(f"FAIL  {src.name:8} {e}")
sys.exit(0 if ok_any else 1)
