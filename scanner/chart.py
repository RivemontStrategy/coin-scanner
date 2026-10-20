"""A small, dependency-free candlestick chart as inline SVG. Colours come from CSS classes, so the same markup works in
the dark and light themes."""
from __future__ import annotations

from html import escape

from .signals import Bar, Signal, KINDS, bar_time, fmt


def svg(bars: list[Bar], signals: list[Signal], width: int = 720, height: int = 260, label: str = "") -> str:
    if not bars:
        return '<p class="muted">No chart data.</p>'
    pad_l, pad_r, pad_t, pad_b = 4, 58, 10, 18
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    hi = max(b.h for b in bars)
    lo = min(b.l for b in bars)
    if hi == lo:
        hi, lo = hi * 1.001 + 1e-12, lo * 0.999
    n = len(bars)
    step = w / n
    body = max(1.0, step * 0.62)

    def y(p: float) -> float:
        return pad_t + (hi - p) / (hi - lo) * h

    parts = [f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label)}">']
    for k in range(5):                                       # price grid with labels on the right
        p = lo + (hi - lo) * k / 4
        yy = y(p)
        parts.append(f'<line class="grid" x1="{pad_l}" x2="{pad_l + w}" y1="{yy:.1f}" y2="{yy:.1f}"/>'
                     f'<text class="axis" x="{pad_l + w + 6}" y="{yy + 4:.1f}">{escape(fmt(p))}</text>')
    for i, b in enumerate(bars):
        x = pad_l + i * step + step / 2
        cls = "up" if b.c >= b.o else "dn"
        top, bot = y(max(b.o, b.c)), y(min(b.o, b.c))
        parts.append(f'<line class="wick {cls}" x1="{x:.1f}" x2="{x:.1f}" y1="{y(b.h):.1f}" y2="{y(b.l):.1f}"/>'
                     f'<rect class="body {cls}" x="{x - body / 2:.1f}" y="{top:.1f}" width="{body:.1f}" '
                     f'height="{max(1.0, bot - top):.1f}"/>')
    first = bars[0].t
    by_t = {b.t: i for i, b in enumerate(bars)}
    for s in signals:                                        # a marker under (bull) or over (bear) the signal's candle
        i = by_t.get(s.t)
        if i is None or s.t < first:
            continue
        x = pad_l + i * step + step / 2
        k = KINDS[s.kind]
        if k.direction == "bull":
            yy = y(bars[i].l) + 9
            pts = f"{x:.1f},{yy - 6:.1f} {x - 4:.1f},{yy:.1f} {x + 4:.1f},{yy:.1f}"
        else:
            yy = y(bars[i].h) - 9
            pts = f"{x:.1f},{yy + 6:.1f} {x - 4:.1f},{yy:.1f} {x + 4:.1f},{yy:.1f}"
        parts.append(f'<polygon class="mark {k.direction}" points="{pts}"><title>{escape(k.title)} · '
                     f'{escape(bar_time(s.t))}</title></polygon>')
    parts.append(f'<text class="axis" x="{pad_l}" y="{height - 4}">{escape(bar_time(bars[0].t)[:10])}</text>'
                 f'<text class="axis end" x="{pad_l + w}" y="{height - 4}">{escape(bar_time(bars[-1].t)[:10])}</text>')
    parts.append("</svg>")
    # the same facts in HTML too: on a phone the SVG's own labels would be too small to read
    meta = (f'<p class="chartmeta"><span>High <b>{escape(fmt(hi))}</b></span><span>Low <b>{escape(fmt(lo))}</b></span>'
            f'<span>{escape(bar_time(bars[0].t)[:10])} → {escape(bar_time(bars[-1].t)[:16])} UTC</span></p>')
    return "".join(parts) + meta
