"""The signal detectors. Each takes a coin's closed bars on one timeframe (oldest first) and returns every event it
finds as a Signal, with the index of the bar where the event became known. The build marks an event as a "new
signal" when that bar is one of the last NEW_BARS closed bars."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NamedTuple

from . import indicators as ind

NEW_BARS = 3                 # an event in one of the last 3 closed bars is a "new signal"

RSI_LEN, RSI_HIGH, RSI_LOW = 14, 70.0, 30.0
RSI_REARM = 5.0             # after a signal, RSI must leave the zone by 5 points (below 65 / above 35) to fire again
STRUCT_K = 3                 # swing points: higher/lower than 3 bars on each side
STRUCT_MARGIN_ATR = 0.2      # the close must clear the swing level by a fifth of an ATR (a 0.01% poke is noise)
EMA_FAST, EMA_SLOW = 50, 200
DOUBLE_K = 5                 # double top/bottom peaks: swing points with 5 bars on each side
DOUBLE_TOL = 0.03            # the two peaks within 3% of each other...
DOUBLE_SAME = 0.5            # ...and closer to each other than half the dip between them (a shape, not two random highs)
DOUBLE_GAP = 5               # at least 5 bars apart
DOUBLE_DEPTH_ATR = 1.5       # the dip between them at least 1.5 ATR deep (filters out noise on flat charts)
DOUBLE_WAIT = 30             # the neckline must break within 30 bars of the second peak
VOL_LEN, VOL_MULT = 20, 3.0
RANGE_DAYS = 30


class Bar(NamedTuple):
    t: int          # open time, ms since epoch (UTC)
    o: float
    h: float
    l: float
    c: float
    v: float


@dataclass(frozen=True)
class Kind:
    slug: str       # used in URLs: /signals/<slug>/
    title: str
    direction: str  # "bull" or "bear"
    short: str      # the chip label
    about: str      # the plain-English explanation on the signal's page


KINDS: dict[str, Kind] = {k.slug: k for k in (
    Kind("rsi-oversold", "RSI oversold", "bull", "RSI < 30",
         "The 14-bar RSI dropped to 30 or below. Price has fallen fast relative to its recent moves. Traders watch for a "
         "bounce, but an oversold reading can stay oversold in a strong downtrend."),
    Kind("rsi-overbought", "RSI overbought", "bear", "RSI > 70",
         "The 14-bar RSI rose to 70 or above. Price has risen fast relative to its recent moves. Traders watch for a "
         "pause or pullback, but an overbought reading can stay overbought in a strong uptrend."),
    Kind("bullish-structure-break", "Bullish structure break", "bull", "Trend turn ▲",
         "The chart was making lower highs and lower lows (a downtrend), then a candle closed above the most recent "
         "swing high. That breaks the downtrend's structure and is an early sign the trend may be turning up."),
    Kind("bearish-structure-break", "Bearish structure break", "bear", "Trend turn ▼",
         "The chart was making higher highs and higher lows (an uptrend), then a candle closed below the most recent "
         "swing low. That breaks the uptrend's structure and is an early sign the trend may be turning down."),
    Kind("golden-cross", "Golden cross", "bull", "Golden cross",
         "The 50-bar exponential moving average crossed above the 200-bar one. A slow, widely followed sign that the "
         "longer-term trend has turned up."),
    Kind("death-cross", "Death cross", "bear", "Death cross",
         "The 50-bar exponential moving average crossed below the 200-bar one. A slow, widely followed sign that the "
         "longer-term trend has turned down."),
    Kind("double-bottom", "Double bottom", "bull", "Double bottom",
         "Price made two lows within 3% of each other, at least 5 bars apart, then closed above the high between them "
         "(the neckline). The pattern suggests sellers failed twice at the same level."),
    Kind("double-top", "Double top", "bear", "Double top",
         "Price made two highs within 3% of each other, at least 5 bars apart, then closed below the low between them "
         "(the neckline). The pattern suggests buyers failed twice at the same level."),
    Kind("volume-spike-up", "Volume spike (up candle)", "bull", "Volume ×3 ▲",
         "A candle traded at least 3 times the average volume of the 20 candles before it, and closed higher than it "
         "opened. Unusual volume often comes with news or a large buyer."),
    Kind("volume-spike-down", "Volume spike (down candle)", "bear", "Volume ×3 ▼",
         "A candle traded at least 3 times the average volume of the 20 candles before it, and closed lower than it "
         "opened. Unusual volume often comes with news or a large seller."),
    Kind("range-breakout", "30-day breakout", "bull", "30d high",
         "A daily candle closed above the highest price of the previous 30 days. Breakouts to new highs can start a new "
         "leg up, or fail and fall back into the range."),
    Kind("range-breakdown", "30-day breakdown", "bear", "30d low",
         "A daily candle closed below the lowest price of the previous 30 days. Breakdowns to new lows can start a new "
         "leg down, or fail and climb back into the range."),
)}


@dataclass
class Signal:
    kind: str
    tf: str
    index: int              # the bar where the event became known
    t: int                  # that bar's open time (ms)
    price: float            # that bar's close
    text: str               # plain-English line, with the numbers
    extra: dict = field(default_factory=dict)

    @property
    def direction(self) -> str:
        return KINDS[self.kind].direction

    def to_json(self) -> dict:
        return {"kind": self.kind, "tf": self.tf, "t": self.t, "price": self.price, "text": self.text,
                "dir": self.direction}


def bar_time(t_ms: int) -> str:
    return datetime.fromtimestamp(t_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def fmt(x: float) -> str:
    """A price with sensible precision for anything from BTC to tiny meme coins."""
    a = abs(x)
    if a >= 1000:
        return f"{x:,.0f}"
    if a >= 1:
        return f"{x:,.2f}"
    if a == 0:
        return "0"
    digits = 2
    while a < 1 and digits < 12:
        a *= 10
        digits += 1
    return f"{x:.{digits + 1}f}".rstrip("0").rstrip(".")


def _sig(kind: str, tf: str, bars: list[Bar], i: int, text: str, **extra) -> Signal:
    return Signal(kind, tf, i, bars[i].t, bars[i].c, text, extra)


# ---------------------------------------------------------------- 1. RSI

def detect_rsi(bars: list[Bar], tf: str) -> list[Signal]:
    r = ind.rsi([b.c for b in bars], RSI_LEN)
    out = []
    armed_hi = armed_lo = True                    # RSI hovering around 70 fires once, not on every wiggle
    for i in range(1, len(bars)):
        a, b = r[i - 1], r[i]
        if a is None or b is None:
            continue
        if b < RSI_HIGH - RSI_REARM:
            armed_hi = True
        if b > RSI_LOW + RSI_REARM:
            armed_lo = True
        if armed_hi and b >= RSI_HIGH > a:
            armed_hi = False
            out.append(_sig("rsi-overbought", tf, bars, i, f"RSI(14) rose to {b:.1f}, at or above 70, on the {tf} chart.",
                            rsi=round(b, 1)))
        elif armed_lo and b <= RSI_LOW < a:
            armed_lo = False
            out.append(_sig("rsi-oversold", tf, bars, i, f"RSI(14) fell to {b:.1f}, at or below 30, on the {tf} chart.",
                            rsi=round(b, 1)))
    return out


# ---------------------------------------------------------------- 2a. market structure

def detect_structure(bars: list[Bar], tf: str, k: int = STRUCT_K) -> list[Signal]:
    """A break of structure, using only swing points already confirmed at each bar (k bars after the swing)."""
    highs, lows = [b.h for b in bars], [b.l for b in bars]
    a = ind.atr(highs, lows, [b.c for b in bars], 14)
    ph, pl = ind.pivot_highs(highs, k), ind.pivot_lows(lows, k)
    out = []
    used_h: set[int] = set()
    used_l: set[int] = set()
    for i in range(1, len(bars)):
        sh = [j for j in ph if j + k <= i - 1]           # swing highs confirmed before this bar
        sl = [j for j in pl if j + k <= i - 1]
        if len(sh) < 2 or len(sl) < 2:
            continue
        h0, h1 = sh[-1], sh[-2]
        l0, l1 = sl[-1], sl[-2]
        c, pc = bars[i].c, bars[i - 1].c
        m = STRUCT_MARGIN_ATR * (a[i] or 0.0)
        down = highs[h0] < highs[h1] and lows[l0] < lows[l1]
        up = highs[h0] > highs[h1] and lows[l0] > lows[l1]
        if down and h0 not in used_h and c > highs[h0] + m and pc <= highs[h0] + m:
            used_h.add(h0)
            out.append(_sig("bullish-structure-break", tf, bars, i,
                            f"After lower highs and lower lows, the {tf} candle closed at {fmt(c)}, above the last swing "
                            f"high of {fmt(highs[h0])} ({bar_time(bars[h0].t)}).", level=highs[h0]))
        elif up and l0 not in used_l and c < lows[l0] - m and pc >= lows[l0] - m:
            used_l.add(l0)
            out.append(_sig("bearish-structure-break", tf, bars, i,
                            f"After higher highs and higher lows, the {tf} candle closed at {fmt(c)}, below the last swing "
                            f"low of {fmt(lows[l0])} ({bar_time(bars[l0].t)}).", level=lows[l0]))
    return out


# ---------------------------------------------------------------- 2b. EMA 50/200 crosses

def detect_ema_cross(bars: list[Bar], tf: str) -> list[Signal]:
    closes = [b.c for b in bars]
    f, s = ind.ema(closes, EMA_FAST), ind.ema(closes, EMA_SLOW)
    out = []
    for i in range(1, len(bars)):
        if None in (f[i - 1], s[i - 1], f[i], s[i]):
            continue
        before, now = f[i - 1] - s[i - 1], f[i] - s[i]
        if before <= 0 < now:
            out.append(_sig("golden-cross", tf, bars, i,
                            f"The 50-bar EMA ({fmt(f[i])}) crossed above the 200-bar EMA ({fmt(s[i])}) on the {tf} chart."))
        elif before >= 0 > now:
            out.append(_sig("death-cross", tf, bars, i,
                            f"The 50-bar EMA ({fmt(f[i])}) crossed below the 200-bar EMA ({fmt(s[i])}) on the {tf} chart."))
    return out


# ---------------------------------------------------------------- 3. double top / bottom

def detect_double(bars: list[Bar], tf: str) -> list[Signal]:
    highs, lows, closes = [b.h for b in bars], [b.l for b in bars], [b.c for b in bars]
    a = ind.atr(highs, lows, closes, 14)
    out = []
    out += _double(bars, tf, highs, lows, closes, a, top=True)
    out += _double(bars, tf, highs, lows, closes, a, top=False)
    return sorted(out, key=lambda s: s.index)


def _double(bars, tf, highs, lows, closes, a, top: bool) -> list[Signal]:
    k = DOUBLE_K
    peaks = ind.pivot_highs(highs, k) if top else ind.pivot_lows(lows, k)
    ext = highs if top else lows
    out = []
    used: set[int] = set()
    for p1, p2 in zip(peaks, peaks[1:]):
        if p2 - p1 < DOUBLE_GAP or p2 in used:
            continue
        v1, v2 = ext[p1], ext[p2]
        if abs(v1 - v2) / max(abs(v1), abs(v2)) > DOUBLE_TOL:
            continue
        between = range(p1 + 1, p2)
        if top:
            neck = min(lows[j] for j in between)
            depth = min(v1, v2) - neck
            extreme = max(v1, v2)
        else:
            neck = max(highs[j] for j in between)
            depth = neck - max(v1, v2)
            extreme = min(v1, v2)
        atr_now = a[p2]
        if atr_now is None or depth < DOUBLE_DEPTH_ATR * atr_now or abs(v1 - v2) > DOUBLE_SAME * depth:
            continue
        for i in range(p2 + 1, min(len(bars), p2 + DOUBLE_WAIT + 1)):
            # the pattern fails if price goes beyond both peaks before the neckline breaks
            if (top and highs[i] > extreme) or (not top and lows[i] < extreme):
                break
            broke = closes[i] < neck if top else closes[i] > neck
            if broke:
                known = max(i, p2 + k)              # the second peak is only confirmed k bars after it
                if known >= len(bars):
                    break
                used.add(p2)
                kind = "double-top" if top else "double-bottom"
                word = "highs" if top else "lows"
                side = "below" if top else "above"
                when = "" if known == i else f" Confirmed {k} candles after the second {word[:-1]}."
                out.append(_sig(kind, tf, bars, known,
                                f"Two {word} at {fmt(v1)} ({bar_time(bars[p1].t)}) and {fmt(v2)} ({bar_time(bars[p2].t)}), "
                                f"then the {tf} candle of {bar_time(bars[i].t)} closed at {fmt(closes[i])}, {side} the "
                                f"neckline at {fmt(neck)}.{when}",
                                neckline=neck, first=bars[p1].t, second=bars[p2].t, broke=bars[i].t))
                break
    return out


# ---------------------------------------------------------------- 4. volume spikes

def detect_volume(bars: list[Bar], tf: str) -> list[Signal]:
    out = []
    for i in range(VOL_LEN, len(bars)):
        avg = sum(b.v for b in bars[i - VOL_LEN:i]) / VOL_LEN
        if avg <= 0:
            continue
        m = bars[i].v / avg
        if m >= VOL_MULT:
            up = bars[i].c >= bars[i].o
            out.append(_sig("volume-spike-up" if up else "volume-spike-down", tf, bars, i,
                            f"The {tf} candle traded {m:.1f}× its 20-candle average volume and closed "
                            f"{'up' if up else 'down'} at {fmt(bars[i].c)}.", mult=round(m, 1)))
    return out


# ---------------------------------------------------------------- 5. 30-day range (daily only)

def detect_range(bars: list[Bar], tf: str) -> list[Signal]:
    if tf != "1d":
        return []
    n = RANGE_DAYS
    out = []
    for i in range(n + 1, len(bars)):
        hi = max(b.h for b in bars[i - n:i])
        lo = min(b.l for b in bars[i - n:i])
        prev_hi = max(b.h for b in bars[i - 1 - n:i - 1])
        prev_lo = min(b.l for b in bars[i - 1 - n:i - 1])
        c, pc = bars[i].c, bars[i - 1].c
        if c > hi and pc <= prev_hi:                     # the first close above, not every day of a trend
            out.append(_sig("range-breakout", tf, bars, i,
                            f"The daily candle closed at {fmt(c)}, above the 30-day high of {fmt(hi)}.", level=hi))
        elif c < lo and pc >= prev_lo:
            out.append(_sig("range-breakdown", tf, bars, i,
                            f"The daily candle closed at {fmt(c)}, below the 30-day low of {fmt(lo)}.", level=lo))
    return out


DETECTORS = (detect_rsi, detect_structure, detect_ema_cross, detect_double, detect_volume, detect_range)


def scan(bars: list[Bar], tf: str) -> list[Signal]:
    """Every event on these bars, oldest first."""
    out: list[Signal] = []
    for d in DETECTORS:
        out += d(bars, tf)
    return sorted(out, key=lambda s: (s.index, s.kind))


def is_new(sig: Signal, n_bars: int) -> bool:
    return sig.index >= n_bars - NEW_BARS
