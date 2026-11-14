"""Procedural sound generators.

Every generator produces stereo float32 blocks shaped (n, 2) with a loudness of
roughly -18 dBFS RMS at gain 1.0, so layers can be mixed without surprises.
Everything is synthesised live: no sample files, no licensing questions, and no
audible loop points. File based loops are supported via :class:`FileLoop`.
"""

from __future__ import annotations

import math
import threading
import wave
from dataclasses import dataclass, field

import numpy as np
from scipy import signal

TARGET_RMS = 0.125  # about -18 dBFS


def _lfilter(b, a, x, zi):
    """lfilter over axis 0 for stereo input, keeping state in ``zi``."""
    y, zf = signal.lfilter(b, a, x, axis=0, zi=zi)
    return y, zf


def _zi(b, a, channels=2):
    order = max(len(a), len(b)) - 1
    return np.zeros((order, channels))


def _biquad(kind: str, f0: float, sr: int, q: float = 0.707):
    """RBJ cookbook biquad coefficients."""
    w0 = 2 * math.pi * min(f0, sr * 0.45) / sr
    alpha = math.sin(w0) / (2 * q)
    cw = math.cos(w0)
    if kind == "lp":
        b = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2]
    elif kind == "hp":
        b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
    elif kind == "bp":
        b = [alpha, 0.0, -alpha]
    else:
        raise ValueError(kind)
    a = [1 + alpha, -2 * cw, 1 - alpha]
    return np.array(b) / a[0], np.array(a) / a[0]


class Generator:
    """Base class. Subclasses implement :meth:`render`."""

    name = "base"

    def __init__(self, sr: int, seed: int | None = None):
        self.sr = sr
        self.rng = np.random.default_rng(seed)

    def render(self, n: int) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def white(self, n: int) -> np.ndarray:
        return self.rng.standard_normal((n, 2))


class SmoothRandom:
    """Slowly wandering random value in [lo, hi], interpolated per sample."""

    def __init__(self, rng, lo, hi, period_s, sr):
        self.rng, self.lo, self.hi, self.sr = rng, lo, hi, sr
        self.period = max(1, int(period_s * sr))
        self.cur = rng.uniform(lo, hi)
        self.nxt = rng.uniform(lo, hi)
        self.pos = 0

    def render(self, n: int) -> np.ndarray:
        out = np.empty(n)
        i = 0
        while i < n:
            take = min(n - i, self.period - self.pos)
            t = (self.pos + np.arange(take)) / self.period
            t = 0.5 - 0.5 * np.cos(np.pi * t)  # smooth step
            out[i : i + take] = self.cur + (self.nxt - self.cur) * t
            i += take
            self.pos += take
            if self.pos >= self.period:
                self.pos = 0
                self.cur = self.nxt
                self.nxt = self.rng.uniform(self.lo, self.hi)
        return out


class WhiteNoise(Generator):
    name = "white"

    def render(self, n):
        return self.white(n) * TARGET_RMS


class PinkNoise(Generator):
    """Paul Kellet style -3 dB/octave filter."""

    name = "pink"
    B = np.array([0.049922035, -0.095993537, 0.050612699, -0.004408786])
    A = np.array([1.0, -2.494956002, 2.017265875, -0.522189400])

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.zi = _zi(self.B, self.A)

    def render(self, n):
        y, self.zi = _lfilter(self.B, self.A, self.white(n), self.zi)
        return y * (TARGET_RMS / 0.0864)


class BrownNoise(Generator):
    """Integrated white noise with a gentle DC blocker."""

    name = "brown"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.b, self.a = np.array([1.0]), np.array([1.0, -0.997])
        self.zi = _zi(self.b, self.a)
        self.hb, self.ha = _biquad("hp", 20, sr)
        self.hzi = _zi(self.hb, self.ha)

    def render(self, n):
        y, self.zi = _lfilter(self.b, self.a, self.white(n), self.zi)
        y, self.hzi = _lfilter(self.hb, self.ha, y, self.hzi)
        return y * (TARGET_RMS / 7.5)


class Fan(Generator):
    """Steady air noise with a faint rotating hum."""

    name = "fan"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.pink = PinkNoise(sr, seed)
        self.b, self.a = _biquad("lp", 1400, sr, 0.6)
        self.zi = _zi(self.b, self.a)
        self.phase = 0.0

    def render(self, n):
        y, self.zi = _lfilter(self.b, self.a, self.pink.render(n), self.zi)
        t = (self.phase + np.arange(n)) / self.sr
        self.phase += n
        wobble = 1.0 + 0.04 * np.sin(2 * np.pi * 7.3 * t)
        hum = 0.012 * np.sin(2 * np.pi * 98 * t) * (1 + 0.3 * np.sin(2 * np.pi * 0.2 * t))
        return y * wobble[:, None] * 1.25 + hum[:, None]


class Grains:
    """Scatter short sound grains (drops, crackles, bubbles, leaves) over a block.

    A bank of pre-built mono kernels is drawn from at random; each grain gets its
    own gain and stereo position. Grain tails that run past the block end are
    carried into the next block, so nothing is cut off.
    """

    def __init__(self, rng, kernels: list[np.ndarray]):
        self.rng = rng
        self.kernels = kernels
        self.maxlen = max(len(k) for k in kernels)
        self.carry = np.zeros((0, 2))

    def render(self, n: int, rate, gain=(0.2, 1.0), width=0.8, heavy: float = 0.0) -> np.ndarray:
        """``rate``: grains per sample (scalar or per-sample array).

        ``heavy`` > 0 adds a long tail to the gain distribution (a few grains
        much louder than the rest, like the odd close raindrop).
        """
        rng = self.rng
        buf = np.zeros((n + self.maxlen, 2))
        buf[: len(self.carry)] += self.carry
        if np.ndim(rate) == 0:
            k = rng.poisson(max(float(rate), 0.0) * n)
            pos = rng.integers(0, n, k) if k else np.zeros(0, int)
            scale = np.ones(k)
        else:
            rate = np.maximum(np.asarray(rate, float), 0.0)
            total = float(rate.sum())
            k = rng.poisson(total) if total > 0 else 0
            if k:
                cdf = np.cumsum(rate) / total
                pos = np.minimum(np.searchsorted(cdf, rng.random(k)), n - 1)
            else:
                pos = np.zeros(0, int)
            scale = np.ones(k)
        if k:
            g = rng.uniform(gain[0], gain[1], k) * scale
            if heavy:
                g *= 1.0 + np.minimum(rng.pareto(heavy, k), 4.0)
            pan = rng.uniform(-width, width, k)
            idx = rng.integers(0, len(self.kernels), k)
            for p, gi, pi, ki in zip(pos, g, pan, idx):
                ker = self.kernels[ki]
                buf[p : p + len(ker), 0] += ker * gi * (1 - pi)
                buf[p : p + len(ker), 1] += ker * gi * (1 + pi)
        self.carry = buf[n:].copy()
        return buf[:n]


# ------------------------------------------------------------------ grain kernels
def _plip(rng, sr, f0, dur, rise, click=0.15):
    """Water drop: a short sine that glides *upwards* (the typical 'plip')."""
    m = max(8, int(dur * sr))
    t = np.arange(m) / sr
    f = f0 * (1 + rise * (t / dur) ** 0.7)
    ph = 2 * np.pi * np.cumsum(f) / sr
    env = (1 - np.exp(-t / 0.0006)) * np.exp(-t / (dur / 3.5))
    k = np.sin(ph) * env
    if click:
        c = rng.standard_normal(m) * np.exp(-t / 0.0007)
        k += click * c
    return k / (np.max(np.abs(k)) or 1)


def _tick(rng, sr, tau, f0, q=1.2, dur=None):
    """Short filtered noise burst: a tap, a crackle or a leaf brushing."""
    dur = dur or tau * 7
    m = max(8, int(dur * sr))
    t = np.arange(m) / sr
    x = rng.standard_normal(m) * np.exp(-t / tau)
    b, a = _biquad("bp", f0, sr, q)
    k = signal.lfilter(b, a, x)
    return k / (np.max(np.abs(k)) or 1)


def _cluster(rng, sr, n_ticks, span, f_lo, f_hi):
    """Several crackles in quick succession: the 'tsk-tsk-tsk' of burning wood."""
    m = int(span * sr) + int(0.02 * sr)
    out = np.zeros(m)
    for _ in range(n_ticks):
        k = _tick(rng, sr, rng.uniform(0.0002, 0.0015), rng.uniform(f_lo, f_hi), 0.9)
        p = int(rng.uniform(0, span) * sr)
        out[p : p + len(k)] += k[: m - p] * rng.uniform(0.3, 1.0)
    return out / (np.max(np.abs(out)) or 1)


def _grain(rng, sr, dur, f0, q):
    """Leaf grain: soft-edged noise snippet, band-limited."""
    m = max(16, int(dur * sr))
    x = rng.standard_normal(m) * np.hanning(m) ** 0.6
    b, a = _biquad("bp", f0, sr, q)
    k = signal.lfilter(b, a, x)
    return k / (np.max(np.abs(k)) or 1)


def _norm(gen_render, sr, seconds=8.0, block=4096):
    """Measure a generator's raw RMS so it can be calibrated to TARGET_RMS."""
    x = np.concatenate([gen_render(block) for _ in range(int(seconds * sr / block))])
    return float(np.sqrt(np.mean(x**2))) or 1.0


class _Calibrated(Generator):
    """Generator whose raw output is scaled to TARGET_RMS once at start-up."""

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self._gain = 1.0

    def _calibrate(self, seconds=8.0):
        self._gain = TARGET_RMS / _norm(self._raw, self.sr, seconds)

    def render(self, n):
        return self._raw(n) * self._gain


class Rain(_Calibrated):
    """Rain: a soft bed, the patter on surfaces, and clearly audible single drops."""

    name = "rain"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.pink = PinkNoise(sr, seed)
        self.hb, self.ha = _biquad("hp", 600, sr)
        self.lb, self.la = _biquad("lp", 6500, sr)
        self.hzi, self.lzi = _zi(self.hb, self.ha), _zi(self.lb, self.la)
        # patter: thousands of tiny taps on leaves, roof and window
        self.patter = Grains(rng, [_tick(rng, sr, rng.uniform(0.0003, 0.0012), rng.uniform(2500, 7000), 1.5)
                                   for _ in range(48)])
        # clear drops: the 'plip' of drops falling into puddles and gutters
        self.drops = Grains(rng, [_plip(rng, sr, rng.uniform(1400, 4200), rng.uniform(0.012, 0.035),
                                        rng.uniform(0.25, 0.9)) for _ in range(64)])
        # heavy drops dripping from the gutter / branches close by
        self.big = Grains(rng, [_plip(rng, sr, rng.uniform(700, 1500), rng.uniform(0.03, 0.06),
                                      rng.uniform(0.4, 1.2), click=0.3) for _ in range(24)])
        self.intensity = SmoothRandom(rng, 0.7, 1.15, 6.0, sr)
        self._calibrate()

    def _raw(self, n):
        sr = self.sr
        bed, self.hzi = _lfilter(self.hb, self.ha, self.pink.render(n), self.hzi)
        bed, self.lzi = _lfilter(self.lb, self.la, bed, self.lzi)
        env = self.intensity.render(n)
        patter = self.patter.render(n, 1400 / sr * env, (0.05, 0.25), 0.9)
        drops = self.drops.render(n, 22 / sr * env, (0.15, 0.5), 0.85, heavy=2.5)
        big = self.big.render(n, 2.5 / sr, (0.4, 0.9), 0.7)
        return (bed * 0.9 + patter * 0.35 + drops * 0.55 + big * 0.6) * env[:, None]


class Leaves(_Calibrated):
    """Rustling leaves: gusts sweep through the canopy, thousands of soft grains."""

    name = "leaves"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.grains = Grains(rng, [_grain(rng, sr, rng.uniform(0.004, 0.035), rng.uniform(1800, 7000),
                                          rng.uniform(0.8, 2.0)) for _ in range(64)])
        self.gust = SmoothRandom(rng, 0.0, 1.0, 2.6, sr)
        self.pink = PinkNoise(sr, None if seed is None else seed + 5)
        self.hb, self.ha = _biquad("hp", 2200, sr)
        self.hzi = _zi(self.hb, self.ha)
        self._calibrate()

    def _raw(self, n):
        g = self.gust.render(n) ** 2
        rate = (60 + 2600 * g) / self.sr
        x = self.grains.render(n, rate, (0.1, 0.6), 0.95)
        hiss, self.hzi = _lfilter(self.hb, self.ha, self.pink.render(n), self.hzi)
        return x + hiss * (0.05 + 0.5 * g)[:, None]


class Stream(_Calibrated):
    """Forest brook: babbling water with bubbles and little splashes."""

    name = "stream"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.pink = PinkNoise(sr, seed)
        self.bb, self.ba = _biquad("bp", 900, sr, 0.5)
        self.bzi = _zi(self.bb, self.ba)
        self.bubbles = Grains(rng, [_plip(rng, sr, rng.uniform(500, 2200), rng.uniform(0.008, 0.025),
                                          rng.uniform(0.6, 2.0), click=0.05) for _ in range(64)])
        self.splash = Grains(rng, [_tick(rng, sr, rng.uniform(0.002, 0.008), rng.uniform(1500, 5000), 0.7)
                                   for _ in range(24)])
        self.babble = SmoothRandom(rng, 0.5, 1.2, 0.15, sr)
        self._calibrate()

    def _raw(self, n):
        sr = self.sr
        bed, self.bzi = _lfilter(self.bb, self.ba, self.pink.render(n), self.bzi)
        mod = self.babble.render(n)
        bub = self.bubbles.render(n, 70 / sr * mod, (0.15, 0.6), 0.9)
        spl = self.splash.render(n, 8 / sr, (0.1, 0.4), 0.9)
        return bed * mod[:, None] * 1.4 + bub * 0.6 + spl * 0.3


class Wind(Generator):
    """Gusty wind: band-limited noise with wandering cutoff and level."""

    name = "wind"
    BLOCK = 256

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.cut = SmoothRandom(self.rng, 250, 900, 4.0, sr / self.BLOCK)
        self.level = SmoothRandom(self.rng, 0.35, 1.2, 5.0, sr)
        self.zi = np.zeros((2, 2))
        self.lb, self.la = _biquad("lp", 1800, sr, 0.6)
        self.lzi = _zi(self.lb, self.la)

    def render(self, n):
        x, self.lzi = _lfilter(self.lb, self.la, self.white(n), self.lzi)
        out = np.empty_like(x)
        cuts = self.cut.render(math.ceil(n / self.BLOCK))
        for k, start in enumerate(range(0, n, self.BLOCK)):
            b, a = _biquad("bp", float(cuts[k]), self.sr, 1.2)
            seg = x[start : start + self.BLOCK]
            out[start : start + len(seg)], self.zi = _lfilter(b, a, seg, self.zi)
        return out * self.level.render(n)[:, None] * (TARGET_RMS / 0.120)


@dataclass(eq=False)
class _Wave:
    start: int
    swell: np.ndarray   # (m, 2) low rolling body of the wave
    crash: np.ndarray   # (m, 2) the break: bright, broadband
    wash: np.ndarray    # (m, 2) foam and backwash running up the beach


class Waves(_Calibrated):
    """Ocean surf. Each wave swells, breaks with a bright crash and then washes
    out as fizzing foam (thousands of tiny bubbles) while the next one builds.
    Waves overlap, sit at different places in the stereo field and vary in size.
    """

    name = "waves"
    BLOCK = 256

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.pink = PinkNoise(sr, seed)
        self.brown = BrownNoise(sr, None if seed is None else seed + 1)
        self.wpink = PinkNoise(sr, None if seed is None else seed + 2)
        self.lb, self.la = _biquad("lp", 380, sr, 0.6)
        self.lzi = _zi(self.lb, self.la)
        self.bedb, self.beda = _biquad("lp", 650, sr, 0.6)
        self.bedzi = _zi(self.bedb, self.beda)
        self.hb, self.ha = _biquad("hp", 1800, sr)
        self.hzi = _zi(self.hb, self.ha)
        self.czi = np.zeros((2, 2))
        self.foam = Grains(rng, [_plip(rng, sr, rng.uniform(2000, 6500), rng.uniform(0.003, 0.012),
                                       rng.uniform(0.5, 2.5), click=0.4) for _ in range(64)])
        self.pos = 0
        self.next_start = 0
        self.waves: list[_Wave] = []
        self._calibrate(16.0)

    def _new_wave(self, start):
        rng, sr = self.rng, self.sr
        rise, fall = rng.uniform(2.8, 4.5), rng.uniform(6.0, 9.0)
        size = rng.uniform(0.55, 1.0)
        m = int((rise + fall) * sr)
        t = np.arange(m) / sr
        swell = np.where(t < rise, (t / rise) ** 2, np.exp(-(t - rise) / (fall / 2.2)))
        # the crest curls over (hiss grows for ~1.3 s), breaks, then fades
        curl = np.clip((t - (rise - 1.3)) / 1.3, 0.0, 1.0)
        tc = np.maximum(t - rise, 0.0)
        crash = np.where(t < rise, curl**2.5, np.exp(-tc / rng.uniform(0.9, 1.6)))
        wash = np.where(t < rise, 0.0, (1 - np.exp(-tc / 0.7)) * np.exp(-tc / (fall / 2.5)))
        taper = np.minimum(1.0, (m - np.arange(m)) / (1.5 * sr))  # no hard cut at the end
        swell, crash, wash = swell * taper, crash * taper, wash * taper
        pan = rng.uniform(-0.45, 0.45)
        lr = np.array([1 - pan, 1 + pan])
        return _Wave(start, swell[:, None] * lr * size, crash[:, None] * lr * size * rng.uniform(0.6, 1.0),
                     wash[:, None] * lr * size)

    def _envelopes(self, n):
        while self.next_start < self.pos + n:
            self.waves.append(self._new_wave(self.next_start))
            self.next_start += int(self.rng.uniform(5.0, 9.5) * self.sr)
        sw, cr, wa = (np.zeros((n, 2)) for _ in range(3))
        for w in list(self.waves):
            a = max(self.pos, w.start)
            b = min(self.pos + n, w.start + len(w.swell))
            if b > a:
                s, d = slice(a - w.start, b - w.start), slice(a - self.pos, b - self.pos)
                sw[d] += w.swell[s]
                cr[d] += w.crash[s]
                wa[d] += w.wash[s]
            if w.start + len(w.swell) <= self.pos + n:
                self.waves.remove(w)
        self.pos += n
        return sw, cr, wa

    def _raw(self, n):
        sr = self.sr
        sw, cr, wa = self._envelopes(n)
        body, self.lzi = _lfilter(self.lb, self.la, self.brown.render(n), self.lzi)
        bed, self.bedzi = _lfilter(self.bedb, self.beda, self.wpink.render(n), self.bedzi)
        # crash: pink noise through a low-pass that opens up as the wave breaks
        x = self.pink.render(n)
        crash = np.empty_like(x)
        cmax = cr.max(axis=1)
        for start in range(0, n, self.BLOCK):
            e = float(cmax[start])
            b, a = _biquad("lp", 500 + 7000 * min(e, 1.0) ** 0.8, sr, 0.6)
            seg = x[start : start + self.BLOCK]
            crash[start : start + len(seg)], self.czi = _lfilter(b, a, seg, self.czi)
        hiss, self.hzi = _lfilter(self.hb, self.ha, self.white(n), self.hzi)
        wmax = wa.max(axis=1)
        foam = self.foam.render(n, 900 / sr * wmax, (0.05, 0.3), 0.9)
        return (bed * 0.35 + body * sw * 1.4 + crash * cr * 1.6 + hiss * wa * 0.18 + foam * 0.5)


class Fire(_Calibrated):
    """Fireplace: low roar, soft hiss, and clearly audible crackles and pops."""

    name = "fire"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.brown = BrownNoise(sr, seed)
        self.lb, self.la = _biquad("lp", 420, sr)
        self.lzi = _zi(self.lb, self.la)
        self.pink = PinkNoise(sr, None if seed is None else seed + 3)
        self.hb, self.ha = _biquad("hp", 3000, sr)
        self.hzi = _zi(self.hb, self.ha)
        self.ticks = Grains(rng, [_tick(rng, sr, rng.uniform(0.0002, 0.0012), rng.uniform(1800, 6500), 0.9)
                                  for _ in range(48)])
        self.clusters = Grains(rng, [_cluster(rng, sr, int(rng.integers(3, 12)), rng.uniform(0.03, 0.18),
                                              1500, 6000) for _ in range(32)])
        self.pops = Grains(rng, [_tick(rng, sr, rng.uniform(0.003, 0.012), rng.uniform(500, 1400), 1.4)
                                 for _ in range(16)])
        self.activity = SmoothRandom(rng, 0.3, 1.0, 2.0, sr)
        self._calibrate()

    def _raw(self, n):
        sr = self.sr
        act = self.activity.render(n)
        roar, self.lzi = _lfilter(self.lb, self.la, self.brown.render(n), self.lzi)
        hiss, self.hzi = _lfilter(self.hb, self.ha, self.pink.render(n), self.hzi)
        ticks = self.ticks.render(n, 45 / sr * act, (0.1, 0.5), 0.8, heavy=2.5)
        cl = self.clusters.render(n, 2.2 / sr * act, (0.3, 0.9), 0.7)
        pops = self.pops.render(n, 0.35 / sr, (0.6, 1.0), 0.6)
        return roar * 0.55 + hiss * 0.08 * act[:, None] + ticks * 0.45 + cl * 0.55 + pops * 0.7


@dataclass(eq=False)
class _Event:
    buf: np.ndarray
    pos: int = 0


class EventGenerator(Generator):
    """Base for sparse one-shot events (thunder, birds).

    The next event is prepared in a background thread, so building a long
    thunder roll never stalls the audio thread on a slow Pi.
    """

    def __init__(self, sr, seed=None, every=(30.0, 120.0)):
        super().__init__(sr, seed)
        self.every = every
        self.countdown = int(self.rng.uniform(min(3.0, every[0]), max(3.0, every[0])) * sr)
        self.active: list[_Event] = []
        self._ready: np.ndarray | None = None
        self._worker: threading.Thread | None = None

    def make_event(self) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def _prepare(self):
        self._ready = self.make_event()

    def _prepare_async(self):
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._prepare, daemon=True)
            self._worker.start()

    def trigger(self):
        buf, self._ready = self._ready, None
        if buf is None:
            buf = self.make_event()
        self.active.append(_Event(buf))
        self._prepare_async()

    def render(self, n):
        out = np.zeros((n, 2))
        self.countdown -= n
        if self.countdown <= 0:
            self.trigger()
            self.countdown = int(self.rng.uniform(*self.every) * self.sr)
        for ev in list(self.active):
            take = min(n, len(ev.buf) - ev.pos)
            out[:take] += ev.buf[ev.pos : ev.pos + take]
            ev.pos += take
            if ev.pos >= len(ev.buf):
                self.active.remove(ev)
        return out


class Thunder(EventGenerator):
    """Thunder you can hear on a small speaker: a sharp crack for close strikes,
    a rolling, crackling middle part and a long rumble that fades away.

    Most of the energy of real thunder is below 80 Hz, which a 4" driver cannot
    play. The rumble is therefore voiced around 120-500 Hz, where the speaker
    is strong, and the 'roll' gets its own bursts so it stays recognisable.
    """

    name = "thunder"

    def __init__(self, sr, seed=None, every=(20.0, 70.0)):
        super().__init__(sr, seed, every)

    def make_event(self):
        sr, rng = self.sr, self.rng
        dur = rng.uniform(7, 14)
        n = int(dur * sr)
        t = np.arange(n) / sr
        close = rng.random() < 0.45
        x = rng.standard_normal((n, 2))
        b, a = signal.butter(2, rng.uniform(260, 520) / (sr / 2), "low")
        rumble = signal.lfilter(b, a, signal.lfilter([1.0], [1.0, -0.97], x, axis=0), axis=0)
        rumble /= np.max(np.abs(rumble)) or 1
        attack = rng.uniform(0.02, 0.15) if close else rng.uniform(0.5, 1.5)
        env = np.minimum(t / attack, 1.0) * np.exp(-t / (dur / 3.0))
        for _ in range(rng.integers(3, 6)):  # rolling swells
            c, w = rng.uniform(0.6, dur * 0.65), rng.uniform(0.25, 0.9)
            env *= 1 + 1.2 * np.exp(-(((t - c) / w) ** 2))
        out = rumble * env[:, None]
        # the roll: a train of mid-frequency bursts in the first seconds
        rb, ra = signal.butter(2, [180 / (sr / 2), 1400 / (sr / 2)], "band")
        roll = signal.lfilter(rb, ra, rng.standard_normal((n, 2)), axis=0)
        roll /= np.max(np.abs(roll)) or 1
        renv = np.zeros(n)
        t0 = 0.0 if close else attack * 0.6
        for i in range(rng.integers(4, 10)):
            c = t0 + rng.uniform(0, 3.5)
            renv += rng.uniform(0.3, 1.0) * np.exp(-np.abs(t - c) / rng.uniform(0.04, 0.2)) * np.exp(-c / 3)
        out += roll * renv[:, None] * 0.9
        if close:  # the crack: a bright, sudden split
            hb, ha = signal.butter(2, 900 / (sr / 2), "high")
            crack = signal.lfilter(hb, ha, rng.standard_normal((n, 2)), axis=0)
            crack /= np.max(np.abs(crack)) or 1
            out += crack * (np.exp(-t / 0.12) + 0.5 * np.exp(-np.abs(t - 0.18) / 0.05))[:, None] * 0.9
        pan = rng.uniform(-0.5, 0.5)
        out[:, 0] *= 1 - pan
        out[:, 1] *= 1 + pan
        peak = np.max(np.abs(out)) or 1.0
        return out / peak * rng.uniform(0.45, 0.85)


class Birds(EventGenerator):
    """A lively dawn chorus: several 'species' from near and far.

    * chirps   short swept notes in phrases (finch, sparrow)
    * trills   fast repeated notes (wren, robin)
    * whistles slow melodic glides with vibrato (blackbird)
    * cuckoo   rare, far away
    """

    name = "birds"

    def __init__(self, sr, seed=None, every=(1.2, 4.5)):
        super().__init__(sr, seed, every)

    def _note(self, f0, f1, d, vib=0.0, vib_hz=0.0, harm=0.0):
        sr = self.sr
        m = int(d * self.sr)
        t = np.arange(m) / sr
        f = f0 + (f1 - f0) * t / d
        if vib:
            f = f * (1 + vib * np.sin(2 * np.pi * vib_hz * t))
        ph = 2 * np.pi * np.cumsum(f) / sr
        env = np.sin(np.pi * t / d) ** 2
        return (np.sin(ph) + harm * np.sin(2 * ph)) * env

    def _gap(self, lo, hi):
        return np.zeros(int(self.rng.uniform(lo, hi) * self.sr))

    def make_event(self):
        sr, rng = self.sr, self.rng
        kind = rng.choice(["chirp", "trill", "whistle", "cuckoo"], p=[0.42, 0.25, 0.28, 0.05])
        parts = []
        if kind == "chirp":
            base = rng.uniform(2800, 5500)
            for _ in range(rng.integers(3, 10)):
                f0 = base * rng.uniform(0.85, 1.15)
                parts += [self._note(f0, f0 * rng.uniform(0.6, 1.5), rng.uniform(0.03, 0.14)), self._gap(0.02, 0.1)]
        elif kind == "trill":
            f0 = rng.uniform(3500, 6500)
            rate = rng.uniform(12, 24)
            for i in range(int(rng.uniform(0.6, 1.6) * rate)):
                parts += [self._note(f0, f0 * 0.82, 0.6 / rate), np.zeros(int(0.4 / rate * sr))]
                f0 *= rng.uniform(0.985, 1.01)
        elif kind == "whistle":
            for _ in range(rng.integers(3, 7)):
                f0 = rng.uniform(1700, 3400)
                parts += [self._note(f0, f0 * rng.uniform(0.75, 1.3), rng.uniform(0.12, 0.38),
                                     vib=0.015, vib_hz=rng.uniform(25, 45), harm=0.15), self._gap(0.04, 0.18)]
        else:
            f0 = rng.uniform(560, 700)
            for _ in range(rng.integers(2, 4)):
                parts += [self._note(f0, f0, 0.22, harm=0.1), self._gap(0.06, 0.1),
                          self._note(f0 * 0.8, f0 * 0.8, 0.3, harm=0.1), self._gap(0.6, 0.9)]
        mono = np.concatenate(parts)
        near = rng.random()
        if near < 0.4:  # far away: quieter and duller
            b, a = signal.butter(1, 3500 / (sr / 2), "low")
            mono = signal.lfilter(b, a, mono) * 1.6
            level = rng.uniform(0.04, 0.09)
        else:
            level = rng.uniform(0.09, 0.2)
        if kind == "cuckoo":
            level = 0.06
        mono = mono / (np.max(np.abs(mono)) or 1) * level
        pan = rng.uniform(-0.85, 0.85)
        return np.stack([mono * (1 - pan), mono * (1 + pan)], axis=1)


class AlarmTone(Generator):
    """Alarm sounds. Not a mixer layer: the engine plays them on top of
    everything while the alarm rings, slowly getting louder.

    * Glocken   a soft bell arpeggio (inharmonic partials like a glockenspiel)
    * Klassisch two-tone beep pattern
    * Vogelchor a dense, loud dawn chorus
    """

    name = "alarm"
    TONES = ["Glocken", "Klassisch", "Vogelchor"]

    def __init__(self, sr, seed=None, tone="Glocken"):
        super().__init__(sr, seed)
        self.tone = tone
        self.pos = 0
        self.loop = self._build(tone)
        self.birds = Birds(sr, seed, every=(0.3, 1.2))

    def _bell(self, f, d):
        sr = self.sr
        t = np.arange(int(d * sr)) / sr
        x = np.zeros_like(t)
        for ratio, amp, tau in ((1.0, 1.0, 0.9), (2.76, 0.45, 0.35), (5.40, 0.25, 0.18), (8.93, 0.12, 0.1)):
            x += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t / tau)
        return x * (1 - np.exp(-t / 0.002))

    def _build(self, tone):
        sr = self.sr
        if tone == "Klassisch":
            t = np.arange(int(0.12 * sr)) / sr
            beep = np.sign(np.sin(2 * np.pi * 880 * t)) * 0.35 + np.sin(2 * np.pi * 1760 * t) * 0.2
            beep *= np.minimum(1, np.minimum(t, t[-1] - t) / 0.005)
            gap = np.zeros(int(0.1 * sr))
            mono = np.concatenate([beep, gap, beep, gap, beep, gap, beep, np.zeros(int(0.7 * sr))])
        else:  # Glocken
            notes = [523.25, 659.25, 783.99, 1046.5, 783.99, 659.25]
            step = int(0.28 * sr)
            mono = np.zeros(step * len(notes) + int(1.2 * sr))
            for i, f in enumerate(notes):
                b = self._bell(f, 1.6)
                mono[i * step : i * step + len(b)] += b[: len(mono) - i * step]
        mono = mono / np.max(np.abs(mono)) * 0.7
        return np.stack([mono, mono], axis=1)

    def render(self, n):
        if self.tone == "Vogelchor":
            return self.birds.render(n) * 6.0
        out = np.empty((n, 2))
        i = 0
        while i < n:
            take = min(n - i, len(self.loop) - self.pos)
            out[i : i + take] = self.loop[self.pos : self.pos + take]
            i += take
            self.pos = (self.pos + take) % len(self.loop)
        return out


@dataclass
class FileLoop(Generator):
    """Seamless loop of a WAV file with an equal-power crossfade at the seam."""

    path: str = ""
    sr: int = 48000
    xfade_s: float = 2.0
    data: np.ndarray = field(init=False, repr=False)
    pos: int = field(init=False, default=0)

    def __post_init__(self):
        with wave.open(self.path, "rb") as w:
            ch, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(w.getnframes())
        if width != 2:
            raise ValueError("Only 16-bit PCM WAV files are supported")
        x = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
        x = x.reshape(-1, ch)
        if ch == 1:
            x = np.repeat(x, 2, axis=1)
        if rate != self.sr:
            x = signal.resample_poly(x, self.sr, rate, axis=0)
        xf = min(int(self.xfade_s * self.sr), len(x) // 4)
        if xf > 0:
            t = np.linspace(0, np.pi / 2, xf)[:, None]
            head, tail = x[:xf], x[-xf:]
            x = x[:-xf].copy()
            x[:xf] = head * np.sin(t) + tail * np.cos(t)
        rms = np.sqrt(np.mean(x**2)) or 1.0
        self.data = x * (TARGET_RMS / rms)

    def render(self, n):
        out = np.empty((n, 2))
        i = 0
        while i < n:
            take = min(n - i, len(self.data) - self.pos)
            out[i : i + take] = self.data[self.pos : self.pos + take]
            i += take
            self.pos = (self.pos + take) % len(self.data)
        return out


GENERATORS = {
    cls.name: cls
    for cls in (WhiteNoise, PinkNoise, BrownNoise, Fan, Rain, Wind, Waves, Fire, Thunder, Birds, Leaves, Stream)
}

LABELS_DE = {
    "white": "White Noise",
    "pink": "Pink Noise",
    "brown": "Brown Noise",
    "fan": "Ventilator",
    "rain": "Regen",
    "wind": "Wind",
    "waves": "Meereswellen",
    "fire": "Kaminfeuer",
    "thunder": "Gewitter",
    "birds": "Vögel",
    "leaves": "Blätterrauschen",
    "stream": "Bach",
}


def make_generator(source: str, sr: int, seed: int | None = None) -> Generator:
    """Create a generator from ``gen:<name>``/``<name>`` or ``file:<path.wav>``."""
    if source.startswith("file:"):
        return FileLoop(path=source[5:], sr=sr)
    name = source[4:] if source.startswith("gen:") else source
    if name not in GENERATORS:
        raise KeyError(f"Unknown sound '{name}'. Known: {', '.join(GENERATORS)}")
    return GENERATORS[name](sr, seed)
