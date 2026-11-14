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

    def render(self, n: int, rate, gain=(0.2, 1.0), width=0.8, heavy: float = 0.0, tail=None) -> np.ndarray:
        """``rate``: grains per sample (scalar or per-sample array).

        ``heavy`` > 0 adds a long tail to the gain distribution (a few grains
        much louder than the rest, like the odd close raindrop).
        ``tail`` = (alpha, cap, offset) multiplies each gain by
        ``min(pareto(alpha), cap) + offset`` instead.
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
            if tail:
                g *= np.minimum(rng.pareto(tail[0], k), tail[1]) + tail[2]
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


def _drop_tick(rng, sr):
    """Rain 1c: a raindrop tick, 4-12 ms noise burst band-passed at 1.8-6 kHz."""
    m = int(sr * rng.uniform(0.004, 0.012))
    x = rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 5))
    b, a = _biquad("bp", rng.uniform(1800, 6000), sr, rng.uniform(1.5, 3.0))
    return signal.lfilter(b, a, x)


def _drop_plip(rng, sr):
    """Rain 1c: a pitched 'plip', 12-30 ms sine gliding up from 0.9-2.6 kHz."""
    m = int(sr * rng.uniform(0.012, 0.03))
    t = np.arange(m) / sr
    f = rng.uniform(900, 2600) * (1 + t / t[-1] * rng.uniform(0.3, 0.9))
    return np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t / (m / sr / 4))


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


class Rain(Generator):
    """Steady rain bed plus individual drops hitting surfaces ("Regen 1c").

    The original bed (pink noise 500-7000 Hz plus a dense 2.8 kHz drop layer)
    at 0.8, plus clearly audible single drops: 14 ticks/s and 6 pitched
    'plips'/s with a Pareto-weighted loudness and random stereo position.
    """

    name = "rain"
    LEVEL = 1.13  # long-term average of the hand-tuned bed is ~0.89 x TARGET_RMS
    TICKS_PER_S, PLIPS_PER_S, PLIP_GAIN = 14.0, 6.0, 0.35
    MIX = 1.16  # scales bed*0.8 + drops back to TARGET_RMS

    def __init__(self, sr, seed=None, drops_per_s=900):
        super().__init__(sr, seed)
        self.pink = PinkNoise(sr, seed)
        self.hb, self.ha = _biquad("hp", 500, sr)
        self.lb, self.la = _biquad("lp", 7000, sr)
        self.hzi, self.lzi = _zi(self.hb, self.ha), _zi(self.lb, self.la)
        self.db, self.da = _biquad("bp", 2800, sr, 0.9)
        self.dzi = _zi(self.db, self.da)
        self.rate = drops_per_s
        self.intensity = SmoothRandom(self.rng, 0.75, 1.15, 6.0, sr)
        self.ticks = Grains(self.rng, [_drop_tick(self.rng, sr) for _ in range(64)])
        self.plips = Grains(self.rng, [_drop_plip(self.rng, sr) for _ in range(64)])

    def render(self, n):
        bed, self.hzi = _lfilter(self.hb, self.ha, self.pink.render(n), self.hzi)
        bed, self.lzi = _lfilter(self.lb, self.la, bed, self.lzi)
        p = self.rate / self.sr
        hits = (self.rng.random((n, 2)) < p) * np.minimum(self.rng.pareto(3.0, (n, 2)), 3.0)
        drops, self.dzi = _lfilter(self.db, self.da, hits, self.dzi)
        env = self.intensity.render(n)[:, None]
        base = (bed * 1.6 + drops * 0.35) * env * self.LEVEL
        # stereo gains 0.4..1.0 per channel, as (1 -/+ pan) * 0.7 with |pan| <= 0.43
        tail = (2.5, 3.0, 0.3)
        single = self.ticks.render(n, self.TICKS_PER_S / self.sr, (0.7, 0.7), 0.43, tail=tail)
        single += self.plips.render(n, self.PLIPS_PER_S / self.sr, (0.7 * self.PLIP_GAIN,) * 2, 0.43, tail=tail)
        return (base * 0.8 + single) * self.MIX


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


class Waves(Generator):
    """Ocean waves: swells that build, break and wash back out."""

    name = "waves"
    BLOCK = 256

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.pink = PinkNoise(sr, seed)
        self.brown = BrownNoise(sr, None if seed is None else seed + 1)
        self.zi = np.zeros((2, 2))
        self.env = np.zeros(0)
        self.env_pos = 0

    def _new_wave(self):
        sr = self.sr
        rise = self.rng.uniform(2.5, 4.0)
        fall = self.rng.uniform(4.0, 7.0)
        gap = self.rng.uniform(0.0, 1.5)
        peak = self.rng.uniform(0.6, 1.0)
        t_r = np.linspace(0, 1, int(rise * sr), endpoint=False)
        t_f = np.linspace(0, 1, int(fall * sr), endpoint=False)
        floor = 0.12
        up = floor + (peak - floor) * t_r**2.2
        down = floor + (peak - floor) * np.exp(-3.5 * t_f) * (1 - t_f)
        tail = np.full(int(gap * sr), floor)
        return np.concatenate([up, down, tail])

    def _envelope(self, n):
        out = np.empty(n)
        i = 0
        while i < n:
            if self.env_pos >= len(self.env):
                self.env, self.env_pos = self._new_wave(), 0
            take = min(n - i, len(self.env) - self.env_pos)
            out[i : i + take] = self.env[self.env_pos : self.env_pos + take]
            i += take
            self.env_pos += take
        return out

    def render(self, n):
        env = self._envelope(n)
        x = self.pink.render(n) * 0.7 + self.brown.render(n) * 0.6
        out = np.empty_like(x)
        for start in range(0, n, self.BLOCK):
            e = float(env[start])
            b, a = _biquad("lp", 300 + 3500 * e**1.5, self.sr, 0.6)
            seg = x[start : start + self.BLOCK]
            out[start : start + len(seg)], self.zi = _lfilter(b, a, seg, self.zi)
        # slight stereo motion so the surf seems to roll across the room
        pan = 0.15 * np.sin(np.cumsum(np.full(n, 2 * np.pi * 0.05 / self.sr)) + self.env_pos)
        out[:, 0] *= 1 - pan
        out[:, 1] *= 1 + pan
        return out * env[:, None] * 3.2


def _pd_lop(f, sr):
    """Pure Data ``lop~``: one-pole low-pass."""
    k = min(1.0, 2 * math.pi * f / sr)
    return np.array([k]), np.array([1.0, -(1 - k)])


def _pd_hip(f, sr):
    """Pure Data ``hip~``: one-pole high-pass."""
    c = max(0.0, 1 - 2 * math.pi * f / sr)
    return np.array([(1 + c) / 2, -(1 + c) / 2]), np.array([1.0, -c])


def _pd_bp(f, q, sr):
    """Pure Data ``bp~``: two-pole resonator."""
    om = 2 * math.pi * f / sr
    r = max(0.0, 1 - om / q) if q > 0 else 0.0
    return np.array([2 * (1 - r) * ((1 - r) + r * om), 0.0, 0.0]), np.array([1.0, -2 * r * math.cos(om), r * r])


class _Filt:
    """lfilter over axis 0 with carried state (mono or several columns)."""

    def __init__(self, ba, cols):
        self.b, self.a = ba
        self.zi = np.zeros((max(len(self.a), len(self.b)) - 1, cols))

    def __call__(self, x):
        y, self.zi = signal.lfilter(self.b, self.a, x, axis=0, zi=self.zi)
        return y


FIRE_POST = [("hip", 1000), ("bp", 1200, 0.6), ("bp", 2600, 0.4), ("bp", 600, 0.2)]


class Fire(Generator):
    """Fireplace after Andy Farnell, *Designing Sound*, Practical 11 ("Feuer G").

    Each side is a sum of four fire voices, each through its own colour filter
    (FIRE_POST), x0.2. Left and right are independent fires cross-mixed
    0.8 / 0.2. One voice is

    * crackles: the RMS of 1 Hz low-passed noise is measured every 512 samples
      over the last 1024; when it lands in 50..51 dB (Pd scale, 100 dB = 1.0)
      a crackle fires: r = 0..29 sets a decay of r ms (squared ramp) and the
      noise band-pass to 1500 + 500 r Hz, Q 1,
    * hissing: noise above 1 kHz, gated by (10 x low-passed noise)^4 x 600,
    * lapping (the flames): noise through a 30 Hz resonator, x100, clipped,

    mixed 0.2 / 0.3 / 0.6. All filters are Pure Data's (lop~, hip~, bp~).
    """

    name = "fire"
    HOP = 512
    VOICES = 2 * len(FIRE_POST)  # columns 0-3 left fire, 4-7 right fire
    LEVEL = 0.98  # per-channel RMS -> TARGET_RMS

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        v = self.VOICES
        self.lop = _Filt(_pd_lop(1, sr), v)
        self.hip1k = _Filt(_pd_hip(1000, sr), v)
        self.res30 = _Filt(_pd_bp(30, 5, sr), v)
        self.hip25a = _Filt(_pd_hip(25, sr), v)
        self.hip25b = _Filt(_pd_hip(25, sr), v)
        posts = [_pd_hip(p[1], sr) if p[0] == "hip" else _pd_bp(p[1], p[2], sr) for p in FIRE_POST]
        self.posts = [_Filt(posts[i % len(posts)], 1) for i in range(v)]
        self.crackle_zi = [np.zeros((2, 1)) for _ in range(v)]
        self.freq = [1500.0] * v
        self.envs = [[] for _ in range(v)]  # [position, length] of running crackle envelopes
        self.prev_sq = None
        self.buf = np.zeros((0, 2))

    def _hop(self):
        n, sr, v = self.HOP, self.sr, self.VOICES
        nz = self.rng.uniform(-1, 1, (n, v))
        lo = self.lop(nz)
        m = (lo * 10) ** 2
        hiss = self.hip1k(nz) * (m * m * 600)
        lap = self.hip25b(np.clip(self.hip25a(self.res30(nz) * 100), -0.9, 0.9)) * 0.6
        mix = hiss * 0.3 + lap * 0.6
        out = np.empty((n, v))
        for c in range(v):
            b, a = _pd_bp(self.freq[c], 1, sr)
            band, self.crackle_zi[c] = signal.lfilter(b, a, nz[:, c : c + 1], axis=0, zi=self.crackle_zi[c])
            if self.envs[c]:
                env = np.zeros(n)
                keep = []
                for e in self.envs[c]:
                    pos, length = e
                    j = np.arange(pos, min(length, pos + n))
                    ramp = (1 - j / (length - 1)) ** 2 if length > 1 else np.ones(len(j))
                    env[: len(j)] = np.maximum(env[: len(j)], ramp)
                    e[0] += n
                    if e[0] < length:
                        keep.append(e)
                self.envs[c] = keep
                mix[:, c] += band[:, 0] * env * 0.2
            out[:, c] = self.posts[c](mix[:, c : c + 1])[:, 0]
        sq = np.einsum("ij,ij->j", lo, lo)
        if self.prev_sq is not None:
            rms = np.sqrt((self.prev_sq + sq) / (2 * n))
            db = 100 + 20 * np.log10(np.maximum(rms, 1e-10))
            for c in np.flatnonzero((db >= 50) & (db < 51)):
                r = int(self.rng.integers(0, 30))
                self.freq[c] = 1500.0 + 500.0 * r
                self.envs[c].append([0, max(1, int(sr * r / 1000))])
        self.prev_sq = sq
        h = len(FIRE_POST)
        a, b = out[:, :h].sum(1) * 0.2, out[:, h:].sum(1) * 0.2
        return np.stack([a * 0.8 + b * 0.2, b * 0.8 + a * 0.2], 1)

    def render(self, n):
        parts = [self.buf]
        have = len(self.buf)
        while have < n:
            parts.append(self._hop())
            have += self.HOP
        buf = np.concatenate(parts)
        self.buf = buf[n:]
        return buf[:n] * self.LEVEL


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
    """Distant rolling thunder, sometimes with a closer crack."""

    name = "thunder"

    def __init__(self, sr, seed=None, every=(25.0, 90.0)):
        super().__init__(sr, seed, every)
        self.countdown = int(self.rng.uniform(3.0, 20.0) * sr)  # first roll soon after switching on

    def make_event(self):
        sr, rng = self.sr, self.rng
        dur = rng.uniform(6, 13)
        n = int(dur * sr)
        t = np.arange(n) / sr
        close = rng.random() < 0.3
        x = rng.standard_normal((n, 2))
        b, a = signal.butter(2, rng.uniform(90, 220) / (sr / 2), "low")
        rumble = signal.lfilter(b, a, signal.lfilter([1.0], [1.0, -0.98], x, axis=0), axis=0)
        attack = rng.uniform(0.05, 0.4) if close else rng.uniform(0.6, 1.8)
        env = np.minimum(t / attack, 1.0) * np.exp(-t / (dur / 3.2))
        # rolling: a few secondary swells
        for _ in range(rng.integers(2, 5)):
            c, w = rng.uniform(0.5, dur * 0.7), rng.uniform(0.3, 1.2)
            env *= 1 + 0.9 * np.exp(-(((t - c) / w) ** 2))
        out = rumble * env[:, None]
        if close:
            hb, ha = signal.butter(2, 1500 / (sr / 2), "high")
            crack = signal.lfilter(hb, ha, rng.standard_normal((n, 2)), axis=0)
            out += crack * np.exp(-t / 0.25)[:, None] * 0.02
        pan = rng.uniform(-0.5, 0.5)
        out[:, 0] *= 1 - pan
        out[:, 1] *= 1 + pan
        peak = np.max(np.abs(out)) or 1.0
        return out / peak * rng.uniform(0.35, 0.8)


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
