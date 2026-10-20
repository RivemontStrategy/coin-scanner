"""Each detector on synthetic candles: it fires where the pattern is, and stays quiet where it is not.
Run: python -m unittest discover -s tests"""
import math
import unittest

from scanner import indicators as ind
from scanner import signals as S
from scanner.signals import Bar

H = 3_600_000


def bars_from(closes, vols=None, spread=0.004):
    """Candles whose open is the previous close and whose high/low sit a little outside the body."""
    out, prev = [], closes[0]
    for i, c in enumerate(closes):
        o = prev
        out.append(Bar(i * H, o, max(o, c) * (1 + spread), min(o, c) * (1 - spread), c,
                       (vols[i] if vols else 100.0)))
        prev = c
    return out


def zigzag(points, steps=6):
    """Straight lines between the given prices, `steps` candles per leg."""
    out = []
    for a, b in zip(points, points[1:]):
        for k in range(steps):
            out.append(a + (b - a) * k / steps)
    out.append(points[-1])
    return out


def kinds(sigs):
    return [s.kind for s in sigs]


class Indicators(unittest.TestCase):
    def test_rsi_extremes(self):
        up = ind.rsi([float(i) for i in range(1, 40)])
        self.assertEqual(up[-1], 100.0)
        down = ind.rsi([float(40 - i) for i in range(40)])
        self.assertEqual(down[-1], 0.0)
        self.assertIsNone(up[13])
        self.assertIsNotNone(up[14])

    def test_ema_seed_and_length(self):
        e = ind.ema([1.0] * 10 + [2.0] * 10, 5)
        self.assertIsNone(e[3])
        self.assertAlmostEqual(e[4], 1.0)
        self.assertGreater(e[-1], 1.9)
        self.assertEqual(len(e), 20)

    def test_pivots_need_bars_on_both_sides(self):
        highs = [1, 2, 3, 9, 3, 2, 1, 2, 3]
        self.assertEqual(ind.pivot_highs(highs, 3), [3])
        self.assertEqual(ind.pivot_highs(highs[:5], 3), [])       # not confirmed yet


class Rsi(unittest.TestCase):
    def test_fires_once_on_the_cross(self):
        closes = [100 + math.sin(i / 3) for i in range(40)] + [100 + 2 * k for k in range(1, 12)]
        sigs = S.detect_rsi(bars_from(closes), "1h")
        self.assertIn("rsi-overbought", kinds(sigs))
        self.assertEqual(kinds(sigs).count("rsi-overbought"), 1)
        self.assertNotIn("rsi-oversold", kinds(sigs))

    def test_oversold(self):
        closes = [100 + math.sin(i / 3) for i in range(40)] + [100 - 2 * k for k in range(1, 12)]
        self.assertIn("rsi-oversold", kinds(S.detect_rsi(bars_from(closes), "4h")))

    def test_hovering_in_the_zone_fires_once(self):
        # a steep fall into oversold, then small wiggles that cross 30 back and forth
        closes = [100 + math.sin(i / 3) for i in range(40)] + [100 - 2 * k for k in range(1, 10)]
        closes += [closes[-1] + (0.6 if k % 2 else -0.6) for k in range(12)]
        sigs = S.detect_rsi(bars_from(closes), "1h")
        self.assertEqual(kinds(sigs).count("rsi-oversold"), 1)

    def test_quiet_on_a_calm_chart(self):
        closes = [100 + math.sin(i / 2) for i in range(80)]
        self.assertEqual(S.detect_rsi(bars_from(closes), "1h"), [])


class Structure(unittest.TestCase):
    def test_bullish_break_after_a_downtrend(self):
        # lower highs and lower lows, then a rally above the last swing high (110)
        closes = zigzag([130, 115, 125, 110, 118, 104, 110, 100, 125], steps=6)
        sigs = S.detect_structure(bars_from(closes, spread=0.001), "4h")
        self.assertIn("bullish-structure-break", kinds(sigs))
        self.assertNotIn("bearish-structure-break", kinds(sigs))
        s = [x for x in sigs if x.kind == "bullish-structure-break"][0]
        self.assertGreater(s.price, s.extra["level"])

    def test_bearish_break_after_an_uptrend(self):
        closes = zigzag([70, 85, 75, 90, 82, 96, 90, 100, 75], steps=6)
        sigs = S.detect_structure(bars_from(closes, spread=0.001), "4h")
        self.assertIn("bearish-structure-break", kinds(sigs))

    def test_no_break_inside_a_range(self):
        closes = zigzag([100, 110, 100, 110, 100, 110, 100, 110], steps=6)
        self.assertEqual(S.detect_structure(bars_from(closes, spread=0.001), "1h"), [])


class EmaCross(unittest.TestCase):
    def test_golden_and_death_cross(self):
        down = [200 - i * 0.5 for i in range(260)]
        up = [down[-1] + i * 1.5 for i in range(1, 200)]
        sigs = S.detect_ema_cross(bars_from(down + up), "1d")
        self.assertEqual(kinds(sigs), ["golden-cross"])
        again = up[-1]
        fall = [again - i * 2 for i in range(1, 200)]
        sigs = S.detect_ema_cross(bars_from(down + up + fall), "1d")
        self.assertEqual(kinds(sigs), ["golden-cross", "death-cross"])

    def test_needs_200_bars(self):
        self.assertEqual(S.detect_ema_cross(bars_from([float(i) for i in range(150)]), "1d"), [])


class Double(unittest.TestCase):
    def test_double_top_breaks_the_neckline(self):
        # rise, peak 120, dip to 100 (neckline), second peak 119 (within 3%), then a fall below 100
        closes = zigzag([90, 120, 100, 119, 92], steps=8) + [92] * 6
        sigs = S.detect_double(bars_from(closes, spread=0.002), "4h")
        self.assertEqual(kinds(sigs), ["double-top"])
        self.assertLess(sigs[0].price, sigs[0].extra["neckline"])

    def test_double_bottom(self):
        closes = zigzag([130, 100, 120, 101, 128], steps=8) + [128] * 6
        self.assertEqual(kinds(S.detect_double(bars_from(closes, spread=0.002), "1d")), ["double-bottom"])

    def test_peaks_too_far_apart_in_price(self):
        closes = zigzag([90, 120, 100, 108, 92], steps=8) + [92] * 6       # 120 vs 108: 10% apart
        self.assertEqual(S.detect_double(bars_from(closes, spread=0.002), "4h"), [])

    def test_peaks_further_apart_than_half_the_dip(self):
        # 120 and 117 are within 3%, but the dip to 115 is shallow: the "pattern" is just a wobble
        closes = zigzag([90, 120, 115, 117, 92], steps=8) + [92] * 6
        self.assertEqual(S.detect_double(bars_from(closes, spread=0.002), "4h"), [])

    def test_no_signal_without_the_neckline_break(self):
        closes = zigzag([90, 120, 100, 119, 105], steps=8) + [105] * 6
        self.assertEqual(S.detect_double(bars_from(closes, spread=0.002), "4h"), [])

    def test_event_waits_for_the_second_peak_to_be_confirmed(self):
        closes = zigzag([90, 120, 100, 119], steps=8) + [80, 79, 78, 77, 76, 75, 74]
        sigs = S.detect_double(bars_from(closes, spread=0.002), "4h")
        self.assertEqual(len(sigs), 1)
        second_peak = 24
        self.assertGreaterEqual(sigs[0].index, second_peak + S.DOUBLE_K)


class Volume(unittest.TestCase):
    def test_three_times_average(self):
        closes = [100.0] * 30 + [101.0]
        vols = [100.0] * 30 + [350.0]
        sigs = S.detect_volume(bars_from(closes, vols), "1h")
        self.assertEqual(kinds(sigs), ["volume-spike-up"])
        self.assertEqual(sigs[0].index, 30)

    def test_below_three_times_is_quiet(self):
        closes = [100.0] * 30 + [99.0]
        vols = [100.0] * 30 + [290.0]
        self.assertEqual(S.detect_volume(bars_from(closes, vols), "1h"), [])

    def test_down_candle(self):
        closes = [100.0] * 30 + [95.0]
        vols = [100.0] * 30 + [400.0]
        self.assertEqual(kinds(S.detect_volume(bars_from(closes, vols), "1h")), ["volume-spike-down"])


class Range30(unittest.TestCase):
    def test_breakout_fires_on_the_first_close_above(self):
        closes = [100 + math.sin(i) for i in range(40)] + [104, 106, 108]
        sigs = S.detect_range(bars_from(closes, spread=0.001), "1d")
        self.assertEqual(kinds(sigs), ["range-breakout"])
        self.assertEqual(sigs[0].index, 40)

    def test_breakdown(self):
        closes = [100 + math.sin(i) for i in range(40)] + [96]
        self.assertEqual(kinds(S.detect_range(bars_from(closes, spread=0.001), "1d")), ["range-breakdown"])

    def test_daily_only(self):
        closes = [100 + math.sin(i) for i in range(40)] + [104]
        self.assertEqual(S.detect_range(bars_from(closes, spread=0.001), "4h"), [])


class NewWindow(unittest.TestCase):
    def test_last_three_closed_bars_are_new(self):
        closes = [100.0] * 30 + [101.0]
        vols = [100.0] * 30 + [400.0]
        b = bars_from(closes, vols)
        s = S.detect_volume(b, "1h")[0]
        self.assertTrue(S.is_new(s, len(b)))
        self.assertTrue(S.is_new(s, len(b) + 2))
        self.assertFalse(S.is_new(s, len(b) + 3))

    def test_every_kind_has_words(self):
        for k in S.KINDS.values():
            self.assertIn(k.direction, ("bull", "bear"))
            self.assertTrue(k.about.endswith("."))


if __name__ == "__main__":
    unittest.main()
