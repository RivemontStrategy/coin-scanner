"""Plain indicator maths on lists of floats. Every function returns a list as long as its input, with None where the
indicator has not warmed up yet, so an index means the same bar everywhere."""
from __future__ import annotations


def sma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(values: list[float], n: int) -> list[float | None]:
    """Exponential moving average, seeded with the simple average of the first n values."""
    out: list[float | None] = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    prev = sum(values[:n]) / n
    out[n - 1] = prev
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def rsi(closes: list[float], n: int = 14) -> list[float | None]:
    """Wilder's RSI: the first value at index n, smoothed with 1/n after that."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= n:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_g, avg_l = gains / n, losses / n
    out[n] = _rsi_of(avg_g, avg_l)
    for i in range(n + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        avg_g = (avg_g * (n - 1) + max(d, 0.0)) / n
        avg_l = (avg_l * (n - 1) + max(-d, 0.0)) / n
        out[i] = _rsi_of(avg_g, avg_l)
    return out


def _rsi_of(g: float, l: float) -> float:
    if l == 0:
        return 100.0 if g > 0 else 50.0
    return 100 - 100 / (1 + g / l)


def atr(highs: list[float], lows: list[float], closes: list[float], n: int = 14) -> list[float | None]:
    """Wilder's average true range."""
    out: list[float | None] = [None] * len(closes)
    if len(closes) <= n:
        return out
    tr = [highs[0] - lows[0]] + [max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
                                 for i in range(1, len(closes))]
    prev = sum(tr[1:n + 1]) / n
    out[n] = prev
    for i in range(n + 1, len(closes)):
        prev = (prev * (n - 1) + tr[i]) / n
        out[i] = prev
    return out


def pivot_highs(highs: list[float], k: int) -> list[int]:
    """Indexes of swing highs: higher than the k bars on each side (ties on the left allowed, so a flat top counts
    once, at its last bar). Only pivots with k bars after them are returned: they are confirmed."""
    out = []
    for i in range(k, len(highs) - k):
        h = highs[i]
        if all(h >= highs[j] for j in range(i - k, i)) and all(h > highs[j] for j in range(i + 1, i + k + 1)):
            out.append(i)
    return out


def pivot_lows(lows: list[float], k: int) -> list[int]:
    out = []
    for i in range(k, len(lows) - k):
        v = lows[i]
        if all(v <= lows[j] for j in range(i - k, i)) and all(v < lows[j] for j in range(i + 1, i + k + 1)):
            out.append(i)
    return out
