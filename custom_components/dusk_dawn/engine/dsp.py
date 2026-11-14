"""Procedural sound generators – pure-Python/numpy port of ``device/sleepgen/dsp.py``.

Differences to the device version, all made so the fallback runs inside Home
Assistant without scipy and stays cheap enough for real time:

* Output is mono (the stream is mono), grains are no longer panned.
* Long noise beds (pink, brown, filtered rain bed, ...) are synthesised once as
  periodic noise directly in the frequency domain with the magnitude response
  of the original filter chain. A ~24 s loop of shaped noise has no seam
  (it is periodic by construction) and costs one array slice per block.
* The two time-varying filters of the original (wind band-pass, wave crash
  low-pass) are approximated by equal-power crossfades between fixed beds.
* Short grain kernels use an exact causal biquad (plain Python loop, run once).

Levels and the overall character (calibration to the same RMS, grain rates and
gains, envelopes) follow the reference implementation.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

TARGET_RMS = 0.125  # about -18 dBFS
LOOP = 1 << 20  # ~23.8 s at 44.1 kHz

Mag = Callable[[np.ndarray], np.ndarray]


# ------------------------------------------------------------------ filter helpers
def _biquad(kind: str, f0: float, sr: int, q: float = 0.707) -> tuple[list[float], list[float]]:
    """RBJ cookbook biquad coefficients (normalised, a[0] == 1)."""
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
    return [v / a[0] for v in b], [v / a[0] for v in a]


def biquad_mag(kind: str, f0: float, sr: int, q: float = 0.707) -> Mag:
    """Magnitude response of a biquad, as a function of frequency in Hz."""
    b, a = _biquad(kind, f0, sr, q)

    def mag(f: np.ndarray) -> np.ndarray:
        z = np.exp(-2j * np.pi * f / sr)
        num = b[0] + b[1] * z + b[2] * z * z
        den = a[0] + a[1] * z + a[2] * z * z
        return np.abs(num / den)

    return mag


def butter_lp_mag(fc: float, order: int = 2) -> Mag:
    return lambda f: 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))


def butter_hp_mag(fc: float, order: int = 2) -> Mag:
    return lambda f: 1.0 / np.sqrt(1.0 + (fc / np.maximum(f, 1e-3)) ** (2 * order))


def butter_bp_mag(lo: float, hi: float, order: int = 2) -> Mag:
    f0sq, bw = lo * hi, hi - lo

    def mag(f: np.ndarray) -> np.ndarray:
        f = np.maximum(f, 1e-3)
        return 1.0 / np.sqrt(1.0 + ((f * f - f0sq) / (f * bw)) ** (2 * order))

    return mag


def leaky_mag(pole: float, sr: int) -> Mag:
    """|1 / (1 - pole z^-1)|: the leaky integrator used for brown noise."""
    return lambda f: 1.0 / np.abs(1.0 - pole * np.exp(-2j * np.pi * f / sr))


def pink_mag(f: np.ndarray) -> np.ndarray:
    """-3 dB/octave, flattened below 10 Hz like the Kellet filter."""
    return 1.0 / np.sqrt(np.maximum(f, 10.0))


def iir(b: list[float], a: list[float], x: np.ndarray) -> np.ndarray:
    """Causal biquad for short arrays (grain kernels). Plain Python, run once."""
    b0, b1, b2 = b
    _, a1, a2 = a
    out = [0.0] * len(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, xi in enumerate(x.tolist()):
        y = b0 * xi + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y
        x2, x1, y2, y1 = x1, xi, y1, y
    return np.asarray(out)


def fft_filter(x: np.ndarray, sr: int, *mags: Mag) -> np.ndarray:
    """Zero-phase magnitude filtering of a finite array (for one-shot events)."""
    n = len(x)
    size = 1 << (int(n * 1.25) - 1).bit_length()  # padding against wrap-around
    spec = np.fft.rfft(x, size)
    f = np.fft.rfftfreq(size, 1 / sr)
    for m in mags:
        spec *= m(f)
    return np.fft.irfft(spec, size)[:n]


def _peak_norm(x: np.ndarray) -> np.ndarray:
    return x / (np.max(np.abs(x)) or 1.0)


# ------------------------------------------------------------------ building blocks
class Bed:
    """A seamless loop of shaped noise, read block by block."""

    def __init__(self, rng: np.random.Generator, sr: int, base: str, *mags: Mag, length: int = LOOP):
        f = np.fft.rfftfreq(length, 1 / sr)
        spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
        if base == "pink":
            shape, rms = pink_mag(f), TARGET_RMS
        elif base == "brown":
            shape = leaky_mag(0.997, sr)(f) * biquad_mag("hp", 20, sr)(f)
            rms = TARGET_RMS
        else:  # white noise with unit variance, like ``rng.standard_normal``
            shape, rms = np.ones_like(f), 1.0
        spec *= shape
        spec[0] = 0.0
        # normalise the *unfiltered* base so the filters keep their relative level
        base_rms = math.sqrt(2 * float(np.sum(np.abs(spec) ** 2))) / length
        spec *= rms / (base_rms or 1.0)
        for m in mags:
            spec *= m(f)
        self.data = np.fft.irfft(spec, length).astype(np.float32)
        self.pos = int(rng.integers(0, length))

    def render(self, n: int) -> np.ndarray:
        d, p = self.data, self.pos
        if p + n <= len(d):
            out = d[p : p + n]
        else:
            out = np.concatenate([d[p:], d[: (p + n) - len(d)]])
        self.pos = (p + n) % len(d)
        return out.astype(np.float64)


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


class Grains:
    """Scatter short mono grains (drops, crackles, leaves) over a block.

    Grain tails that run past the block end are carried into the next block.
    """

    def __init__(self, rng, kernels: list[np.ndarray]):
        self.rng = rng
        self.kernels = kernels
        self.maxlen = max(len(k) for k in kernels)
        self.carry = np.zeros(0)

    def render(self, n: int, rate, gain=(0.2, 1.0), heavy: float = 0.0) -> np.ndarray:
        """``rate``: grains per sample (scalar or per-sample array)."""
        rng = self.rng
        buf = np.zeros(n + self.maxlen)
        buf[: len(self.carry)] += self.carry
        if np.ndim(rate) == 0:
            k = int(rng.poisson(max(float(rate), 0.0) * n))
            pos = rng.integers(0, n, k) if k else np.zeros(0, int)
        else:
            rate = np.maximum(np.asarray(rate, float), 0.0)
            total = float(rate.sum())
            k = int(rng.poisson(total)) if total > 0 else 0
            if k:
                cdf = np.cumsum(rate) / total
                pos = np.minimum(np.searchsorted(cdf, rng.random(k)), n - 1)
            else:
                pos = np.zeros(0, int)
        if k:
            g = rng.uniform(gain[0], gain[1], k)
            if heavy:
                g *= 1.0 + np.minimum(rng.pareto(heavy, k), 4.0)
            idx = rng.integers(0, len(self.kernels), k)
            kernels = self.kernels
            for p, gi, ki in zip(pos.tolist(), g.tolist(), idx.tolist(), strict=True):
                ker = kernels[ki]
                buf[p : p + len(ker)] += ker * gi
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
        k += click * rng.standard_normal(m) * np.exp(-t / 0.0007)
    return _peak_norm(k)


def _tick(rng, sr, tau, f0, q=1.2, dur=None):
    """Short filtered noise burst: a tap, a crackle or a leaf brushing."""
    dur = dur or tau * 7
    m = max(8, int(dur * sr))
    t = np.arange(m) / sr
    x = rng.standard_normal(m) * np.exp(-t / tau)
    return _peak_norm(iir(*_biquad("bp", f0, sr, q), x))


def _cluster(rng, sr, n_ticks, span, f_lo, f_hi):
    """Several crackles in quick succession: the 'tsk-tsk-tsk' of burning wood."""
    m = int(span * sr) + int(0.02 * sr)
    out = np.zeros(m)
    for _ in range(n_ticks):
        k = _tick(rng, sr, rng.uniform(0.0002, 0.0015), rng.uniform(f_lo, f_hi), 0.9)
        p = int(rng.uniform(0, span) * sr)
        out[p : p + len(k)] += k[: m - p] * rng.uniform(0.3, 1.0)
    return _peak_norm(out)


def _grain(rng, sr, dur, f0, q):
    """Leaf grain: soft-edged noise snippet, band-limited."""
    m = max(16, int(dur * sr))
    x = rng.standard_normal(m) * np.hanning(m) ** 0.6
    return _peak_norm(iir(*_biquad("bp", f0, sr, q), x))


# ------------------------------------------------------------------ generators
class Generator:
    """Base class: ``render(n)`` returns ``n`` mono float64 samples."""

    name = "base"

    def __init__(self, sr: int, seed: int | None = None):
        self.sr = sr
        self.rng = np.random.default_rng(seed)

    def render(self, n: int) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError


class _Calibrated(Generator):
    """Generator whose raw output is scaled to TARGET_RMS once at start-up."""

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self._gain = 1.0

    def _calibrate(self, seconds=6.0, block=4096):
        x = np.concatenate([self._raw(block) for _ in range(int(seconds * self.sr / block))])
        self._gain = TARGET_RMS / (float(np.sqrt(np.mean(x**2))) or 1.0)

    def _raw(self, n):  # pragma: no cover - interface
        raise NotImplementedError

    def render(self, n):
        return self._raw(n) * self._gain


class WhiteNoise(Generator):
    name = "white"

    def render(self, n):
        return self.rng.standard_normal(n) * TARGET_RMS


class PinkNoise(Generator):
    name = "pink"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.bed = Bed(self.rng, sr, "pink")

    def render(self, n):
        return self.bed.render(n)


class BrownNoise(Generator):
    name = "brown"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.bed = Bed(self.rng, sr, "brown")

    def render(self, n):
        return self.bed.render(n)


class Fan(Generator):
    """Steady air noise with a faint rotating hum."""

    name = "fan"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.bed = Bed(self.rng, sr, "pink", biquad_mag("lp", 1400, sr, 0.6))
        self.phase = 0

    def render(self, n):
        t = (self.phase + np.arange(n)) / self.sr
        self.phase += n
        wobble = 1.0 + 0.04 * np.sin(2 * np.pi * 7.3 * t)
        hum = 0.012 * np.sin(2 * np.pi * 98 * t) * (1 + 0.3 * np.sin(2 * np.pi * 0.2 * t))
        return self.bed.render(n) * wobble * 1.25 + hum


class Rain(_Calibrated):
    """Rain: a soft bed, the patter on surfaces, and clearly audible single drops."""

    name = "rain"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.bed = Bed(rng, sr, "pink", biquad_mag("hp", 600, sr), biquad_mag("lp", 6500, sr))
        self.patter = Grains(rng, [_tick(rng, sr, rng.uniform(0.0003, 0.0012), rng.uniform(2500, 7000), 1.5)
                                   for _ in range(48)])
        self.drops = Grains(rng, [_plip(rng, sr, rng.uniform(1400, 4200), rng.uniform(0.012, 0.035),
                                        rng.uniform(0.25, 0.9)) for _ in range(64)])
        self.big = Grains(rng, [_plip(rng, sr, rng.uniform(700, 1500), rng.uniform(0.03, 0.06),
                                      rng.uniform(0.4, 1.2), click=0.3) for _ in range(24)])
        self.intensity = SmoothRandom(rng, 0.7, 1.15, 6.0, sr)
        self._calibrate()

    def _raw(self, n):
        sr = self.sr
        env = self.intensity.render(n)
        patter = self.patter.render(n, 1400 / sr * env, (0.05, 0.25))
        drops = self.drops.render(n, 22 / sr * env, (0.15, 0.5), heavy=2.5)
        big = self.big.render(n, 2.5 / sr, (0.4, 0.9))
        return (self.bed.render(n) * 0.9 + patter * 0.35 + drops * 0.55 + big * 0.6) * env


class Leaves(_Calibrated):
    """Rustling leaves: gusts sweep through the canopy, thousands of soft grains."""

    name = "leaves"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.grains = Grains(rng, [_grain(rng, sr, rng.uniform(0.004, 0.035), rng.uniform(1800, 7000),
                                          rng.uniform(0.8, 2.0)) for _ in range(64)])
        self.gust = SmoothRandom(rng, 0.0, 1.0, 2.6, sr)
        self.hiss = Bed(rng, sr, "pink", biquad_mag("hp", 2200, sr))
        self._calibrate()

    def _raw(self, n):
        g = self.gust.render(n) ** 2
        x = self.grains.render(n, (60 + 2600 * g) / self.sr, (0.1, 0.6))
        return x + self.hiss.render(n) * (0.05 + 0.5 * g)


class Stream(_Calibrated):
    """Forest brook: babbling water with bubbles and little splashes."""

    name = "stream"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.bed = Bed(rng, sr, "pink", biquad_mag("bp", 900, sr, 0.5))
        self.bubbles = Grains(rng, [_plip(rng, sr, rng.uniform(500, 2200), rng.uniform(0.008, 0.025),
                                          rng.uniform(0.6, 2.0), click=0.05) for _ in range(64)])
        self.splash = Grains(rng, [_tick(rng, sr, rng.uniform(0.002, 0.008), rng.uniform(1500, 5000), 0.7)
                                   for _ in range(24)])
        self.babble = SmoothRandom(rng, 0.5, 1.2, 0.15, sr)
        self._calibrate()

    def _raw(self, n):
        sr = self.sr
        mod = self.babble.render(n)
        bub = self.bubbles.render(n, 70 / sr * mod, (0.15, 0.6))
        spl = self.splash.render(n, 8 / sr, (0.1, 0.4))
        return self.bed.render(n) * mod * 1.4 + bub * 0.6 + spl * 0.3


def _xfade(beds: list[Bed], pos: np.ndarray, n: int) -> np.ndarray:
    """Equal-power crossfade between beds; ``pos`` in [0, len(beds) - 1] per sample."""
    out = np.zeros(n)
    for i, bed in enumerate(beds):
        w = np.clip(1.0 - np.abs(pos - i), 0.0, 1.0)
        if np.any(w > 0):
            out += bed.render(n) * np.sin(w * np.pi / 2)
        else:
            bed.pos = (bed.pos + n) % len(bed.data)
    return out


class Wind(Generator):
    """Gusty wind: band-limited noise with wandering centre frequency and level."""

    name = "wind"
    CENTRES = (250.0, 420.0, 900.0)

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        lp = biquad_mag("lp", 1800, sr, 0.6)
        self.beds = [Bed(self.rng, sr, "white", lp, biquad_mag("bp", c, sr, 1.2)) for c in self.CENTRES]
        self.cut = SmoothRandom(self.rng, 250, 900, 4.0, sr)
        self.level = SmoothRandom(self.rng, 0.35, 1.2, 5.0, sr)
        self._norm = [TARGET_RMS / (float(np.sqrt(np.mean(b.data.astype(np.float64) ** 2))) or 1.0)
                      for b in self.beds]
        for b, g in zip(self.beds, self._norm, strict=True):
            b.data *= g

    def render(self, n):
        logc = np.log(self.cut.render(n))
        lc = np.log(self.CENTRES)
        pos = np.interp(logc, lc, np.arange(len(lc)))
        return _xfade(self.beds, pos, n) * self.level.render(n)


@dataclass(eq=False)
class _Wave:
    start: int
    swell: np.ndarray
    crash: np.ndarray
    wash: np.ndarray


class Waves(_Calibrated):
    """Ocean surf: each wave swells, breaks with a bright crash and washes out
    as fizzing foam while the next one builds. Waves overlap and vary in size."""

    name = "waves"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.body = Bed(rng, sr, "brown", biquad_mag("lp", 380, sr, 0.6))
        self.bed = Bed(rng, sr, "pink", biquad_mag("lp", 650, sr, 0.6))
        # the crash low-pass opens from 500 Hz to 7.5 kHz as the wave breaks
        self.crash = [Bed(rng, sr, "pink", biquad_mag("lp", 500, sr, 0.6)),
                      Bed(rng, sr, "pink", biquad_mag("lp", 2200, sr, 0.6)),
                      Bed(rng, sr, "pink", biquad_mag("lp", 7500, sr, 0.6))]
        self.hiss = Bed(rng, sr, "white", biquad_mag("hp", 1800, sr))
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
        curl = np.clip((t - (rise - 1.3)) / 1.3, 0.0, 1.0)
        tc = np.maximum(t - rise, 0.0)
        crash = np.where(t < rise, curl**2.5, np.exp(-tc / rng.uniform(0.9, 1.6)))
        wash = np.where(t < rise, 0.0, (1 - np.exp(-tc / 0.7)) * np.exp(-tc / (fall / 2.5)))
        taper = np.minimum(1.0, (m - np.arange(m)) / (1.5 * sr))
        return _Wave(start, swell * taper * size, crash * taper * size * rng.uniform(0.6, 1.0),
                     wash * taper * size)

    def _envelopes(self, n):
        while self.next_start < self.pos + n:
            self.waves.append(self._new_wave(self.next_start))
            self.next_start += int(self.rng.uniform(5.0, 9.5) * self.sr)
        sw, cr, wa = np.zeros(n), np.zeros(n), np.zeros(n)
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
        sw, cr, wa = self._envelopes(n)
        crash = _xfade(self.crash, 2.0 * np.minimum(cr, 1.0) ** 0.8, n)
        foam = self.foam.render(n, 900 / self.sr * wa, (0.05, 0.3))
        return (self.bed.render(n) * 0.35 + self.body.render(n) * sw * 1.4 + crash * cr * 1.6
                + self.hiss.render(n) * wa * 0.18 + foam * 0.5)


class Fire(_Calibrated):
    """Fireplace: low roar, soft hiss, and clearly audible crackles and pops."""

    name = "fire"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.roar = Bed(rng, sr, "brown", biquad_mag("lp", 420, sr))
        self.hiss = Bed(rng, sr, "pink", biquad_mag("hp", 3000, sr))
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
        ticks = self.ticks.render(n, 45 / sr * act, (0.1, 0.5), heavy=2.5)
        cl = self.clusters.render(n, 2.2 / sr * act, (0.3, 0.9))
        pops = self.pops.render(n, 0.35 / sr, (0.6, 1.0))
        return (self.roar.render(n) * 0.55 + self.hiss.render(n) * 0.08 * act
                + ticks * 0.45 + cl * 0.55 + pops * 0.7)


@dataclass(eq=False)
class _Event:
    buf: np.ndarray
    pos: int = 0


class EventGenerator(Generator):
    """Base for sparse one-shot events (thunder, birds).

    The next event is prepared in a short-lived background thread, so building
    a long thunder roll never stalls the audio thread.
    """

    def __init__(self, sr, seed=None, every=(30.0, 120.0)):
        super().__init__(sr, seed)
        self.every = every
        self.countdown = int(self.rng.uniform(min(3.0, every[0]), max(3.0, every[0])) * sr)
        self.active: list[_Event] = []
        self._ready: np.ndarray | None = None
        self._worker: threading.Thread | None = None
        self._rng_lock = threading.Lock()

    def make_event(self) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def _make(self) -> np.ndarray:
        with self._rng_lock:
            return self.make_event()

    def _prepare(self):
        self._ready = self._make()

    def _prepare_async(self):
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(target=self._prepare, name="dusk_dawn_event", daemon=True)
            self._worker.start()

    def trigger(self):
        buf, self._ready = self._ready, None
        if buf is None:
            buf = self._make()
        self.active.append(_Event(buf))
        self._prepare_async()

    def render(self, n):
        out = np.zeros(n)
        self.countdown -= n
        if self.countdown <= 0:
            self.trigger()
            with self._rng_lock:
                self.countdown = int(self.rng.uniform(*self.every) * self.sr)
        for ev in list(self.active):
            take = min(n, len(ev.buf) - ev.pos)
            out[:take] += ev.buf[ev.pos : ev.pos + take]
            ev.pos += take
            if ev.pos >= len(ev.buf):
                self.active.remove(ev)
        return out


class Thunder(EventGenerator):
    """Thunder for small speakers: crack for close strikes, a rolling middle part
    and a long rumble voiced around 120-500 Hz."""

    name = "thunder"

    def __init__(self, sr, seed=None, every=(20.0, 70.0)):
        super().__init__(sr, seed, every)

    def make_event(self):
        sr, rng = self.sr, self.rng
        dur = rng.uniform(7, 14)
        n = int(dur * sr)
        t = np.arange(n) / sr
        close = rng.random() < 0.45
        rumble = fft_filter(rng.standard_normal(n), sr, leaky_mag(0.97, sr), butter_lp_mag(rng.uniform(260, 520)))
        rumble = _peak_norm(rumble)
        attack = rng.uniform(0.02, 0.15) if close else rng.uniform(0.5, 1.5)
        env = np.minimum(t / attack, 1.0) * np.exp(-t / (dur / 3.0))
        for _ in range(rng.integers(3, 6)):  # rolling swells
            c, w = rng.uniform(0.6, dur * 0.65), rng.uniform(0.25, 0.9)
            env *= 1 + 1.2 * np.exp(-(((t - c) / w) ** 2))
        out = rumble * env
        roll = _peak_norm(fft_filter(rng.standard_normal(n), sr, butter_bp_mag(180, 1400)))
        renv = np.zeros(n)
        t0 = 0.0 if close else attack * 0.6
        for _ in range(rng.integers(4, 10)):
            c = t0 + rng.uniform(0, 3.5)
            renv += rng.uniform(0.3, 1.0) * np.exp(-np.abs(t - c) / rng.uniform(0.04, 0.2)) * np.exp(-c / 3)
        out += roll * renv * 0.9
        if close:  # the crack: a bright, sudden split
            crack = _peak_norm(fft_filter(rng.standard_normal(n), sr, butter_hp_mag(900)))
            out += crack * (np.exp(-t / 0.12) + 0.5 * np.exp(-np.abs(t - 0.18) / 0.05)) * 0.9
        return _peak_norm(out) * rng.uniform(0.45, 0.85)


class Birds(EventGenerator):
    """A lively dawn chorus: chirps, trills, whistles and a rare cuckoo."""

    name = "birds"

    def __init__(self, sr, seed=None, every=(1.2, 4.5)):
        super().__init__(sr, seed, every)

    def _note(self, f0, f1, d, vib=0.0, vib_hz=0.0, harm=0.0):
        sr = self.sr
        m = int(d * sr)
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
        parts: list[np.ndarray] = []
        if kind == "chirp":
            base = rng.uniform(2800, 5500)
            for _ in range(rng.integers(3, 10)):
                f0 = base * rng.uniform(0.85, 1.15)
                parts += [self._note(f0, f0 * rng.uniform(0.6, 1.5), rng.uniform(0.03, 0.14)), self._gap(0.02, 0.1)]
        elif kind == "trill":
            f0 = rng.uniform(3500, 6500)
            rate = rng.uniform(12, 24)
            for _ in range(int(rng.uniform(0.6, 1.6) * rate)):
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
        if rng.random() < 0.4:  # far away: quieter and duller
            mono = fft_filter(mono, sr, butter_lp_mag(3500, 1)) * 1.6
            level = rng.uniform(0.04, 0.09)
        else:
            level = rng.uniform(0.09, 0.2)
        if kind == "cuckoo":
            level = 0.06
        return _peak_norm(mono) * level


class AlarmTone(Generator):
    """Alarm sounds, played on top of everything while the alarm rings.

    * bells    a soft bell arpeggio (inharmonic partials like a glockenspiel)
    * classic  two-tone beep pattern
    * birds    a dense, loud dawn chorus
    """

    name = "alarm"
    TONES = ("bells", "classic", "birds")

    def __init__(self, sr, seed=None, tone="bells"):
        super().__init__(sr, seed)
        self.tone = tone if tone in self.TONES else "bells"
        self.pos = 0
        if self.tone == "birds":
            self.birds = Birds(sr, seed, every=(0.3, 1.2))
            self.birds.countdown = 0
        else:
            self.loop = self._build(self.tone)

    def _bell(self, f, d):
        sr = self.sr
        t = np.arange(int(d * sr)) / sr
        x = np.zeros_like(t)
        for ratio, amp, tau in ((1.0, 1.0, 0.9), (2.76, 0.45, 0.35), (5.40, 0.25, 0.18), (8.93, 0.12, 0.1)):
            x += amp * np.sin(2 * np.pi * f * ratio * t) * np.exp(-t / tau)
        return x * (1 - np.exp(-t / 0.002))

    def _build(self, tone):
        sr = self.sr
        if tone == "classic":
            t = np.arange(int(0.12 * sr)) / sr
            beep = np.sign(np.sin(2 * np.pi * 880 * t)) * 0.35 + np.sin(2 * np.pi * 1760 * t) * 0.2
            beep *= np.minimum(1, np.minimum(t, t[-1] - t) / 0.005)
            gap = np.zeros(int(0.1 * sr))
            mono = np.concatenate([beep, gap, beep, gap, beep, gap, beep, np.zeros(int(0.7 * sr))])
        else:  # bells
            notes = [523.25, 659.25, 783.99, 1046.5, 783.99, 659.25]
            step = int(0.28 * sr)
            mono = np.zeros(step * len(notes) + int(1.2 * sr))
            for i, f in enumerate(notes):
                b = self._bell(f, 1.6)
                mono[i * step : i * step + len(b)] += b[: len(mono) - i * step]
        return _peak_norm(mono) * 0.7

    def render(self, n):
        if self.tone == "birds":
            return self.birds.render(n) * 6.0
        out = np.empty(n)
        i = 0
        while i < n:
            take = min(n - i, len(self.loop) - self.pos)
            out[i : i + take] = self.loop[self.pos : self.pos + take]
            i += take
            self.pos = (self.pos + take) % len(self.loop)
        return out


GENERATORS: dict[str, type[Generator]] = {
    cls.name: cls
    for cls in (Rain, Waves, Stream, Wind, Thunder, Birds, Leaves, Fire, Fan, WhiteNoise, PinkNoise, BrownNoise)
}
