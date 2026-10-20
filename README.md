# Coin Scanner

A free, static crypto signal scanner. Every 15 minutes a GitHub Actions job reads public market data for the top 150
USDT spot pairs (by 24-hour volume, without the non-coins listed in `config/exclude.json` and leveraged tokens), computes signals on the 1-hour, 4-hour
and daily candles, builds a static site and publishes it on GitHub Pages. No server, no database, no trackers, no cost.

## Signals

A signal is "new" when it happened in one of the last 3 closed candles. Each one comes with a plain-English line and
the candle time.

| Signal | Rule |
|---|---|
| RSI oversold / overbought | RSI(14) crosses to ≤ 30 / ≥ 70. Fires again only after RSI has left the zone by 5 points. |
| Bullish / bearish structure break | Lower highs and lower lows (or higher highs and higher lows) on confirmed swing points (3 candles each side), then a close beyond the last swing high (low) by at least 0.2 ATR. |
| Golden / death cross | EMA 50 crosses above / below EMA 200 (400 candles are read so the EMA 200 is warmed up). |
| Double top / bottom | Two swing points (5 candles each side) within 3% of each other and closer than half the dip between them, at least 5 candles apart, dip ≥ 1.5 ATR; then a close through the neckline within 30 candles. Shown from the candle the second peak is confirmed. |
| Volume spike | Volume ≥ 3× the average of the previous 20 candles (up or down candle). |
| 30-day breakout / breakdown | Daily close above the previous 30 days' high / below their low, first day only. |

Checks on real candles, with the numbers behind each example and how often each signal fires: `docs/detector-checks.md`
(regenerate with `python scripts/check_signals.py`).

## Live prices

Prices and 24-hour changes refresh in the visitor's browser every 45 seconds straight from Binance's public data
mirror (OKX as a fallback); both allow browser requests. Signals use closed candles only and refresh with the scan;
the page shows when they were computed and when the next scan is due.

## Data sources

Tried in order until one works from the runner: Binance's public data mirror (`data-api.binance.vision`, since
`api.binance.com` answers 451 to US IPs), OKX, Gate, MEXC. Only closed candles are used. `python scripts/probe.py`
prints which ones answer (the `probe data sources` workflow runs it on a GitHub runner).

## Run locally

    python -m unittest discover -s tests
    python -m scanner.build --out _site          # about a minute; TOP_N=10 for a quick run
    SCANNER_SOURCE=okx TOP_N=10 python -m scanner.build --out _site   # force one source

Python 3.11+, standard library only.

## Settings

- `config/site.json`: the site name (temporary: "Coin Scanner"), tagline, address (`base_url`), number of coins,
  timeframes. `SITE_URL` / `SITE_NAME` environment variables override them.
- `config/exclude.json`: stablecoins, tokenized stocks and ETFs, gold tokens and wrapped duplicates kept out of the
  list (the build log prints a `check:` line for new stock-like tickers ending in B).
- `config/referrals.json`: exchange buttons. A button is shown only when its `url` is filled in.

## Publishing (one-time)

Settings → Pages → Build and deployment → Source: **GitHub Actions**. The `scan and publish` workflow then runs on
every push to `main`, every 15 minutes (minutes 2, 17, 32, 47), and on demand (Actions → scan and publish → Run workflow).

GitHub pauses scheduled workflows in a public repository after 60 days without any repository activity; a commit
(or re-enabling the workflow in the Actions tab) starts them again.

Not financial advice.
