"""Procedural sound generators – pure-Python/numpy port of ``device/sleepgen/dsp.py``.

Home Assistant ships numpy but not scipy, so the IIR filters of the device
version (``scipy.signal.lfilter``) are replaced by :class:`IIR` and
:class:`TVBiquad`: the same difference equations, evaluated exactly but
block-wise with numpy (zero-state response as a matrix product with the
impulse response, plus the carried-over filter state). The noise generators,
rain, wind, waves, fire and thunder therefore follow the reference sample for
sample in structure, filters, rates and levels.

Differences to the device version:

* Output is mono (the stream is mono); stereo panning is dropped.
* Leaves and stream use :class:`Bed`, a seamless loop of noise shaped in the
  frequency domain, and short grain kernels; birds are built like the device
  version, with an FFT low-pass for distant birds.
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
    """RBJ cookbook biquad coefficients (normalised, a[0] == 1).

    With ``q = 1/sqrt(2)`` the low/high-pass equals a 2nd-order Butterworth
    (``scipy.signal.butter(2, ...)``): both use the pre-warped bilinear transform.
    """
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


BUTTER_Q = 1 / math.sqrt(2)


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


class _Stateful:
    """Direct-form-I state shared by the block IIR filters.

    A block of ``L`` samples is filtered exactly as ``y = h * u`` where ``u`` is
    the FIR (numerator) part of the input and ``h`` the impulse response of the
    all-pole part, truncated to ``L`` samples. The last outputs of the previous
    block enter ``u`` as an excitation of the first ``order`` samples, which
    reproduces the recursion ``y[n] = u[n] - a1 y[n-1] - ...`` without a
    per-sample Python loop.
    """

    def __init__(self, order: int):
        self.order = order
        self.xh = np.zeros(order)  # last inputs, most recent last
        self.yh = np.zeros(order)  # last outputs, most recent last

    def _excite(self, x: np.ndarray, b: np.ndarray, a: np.ndarray) -> np.ndarray:
        n_ord, size = self.order, len(x)
        xp = np.concatenate([self.xh, x])
        u = b[0] * x
        for k in range(1, n_ord + 1):
            u += b[k] * xp[n_ord - k : n_ord - k + size]
        yh = self.yh
        for m in range(min(n_ord, size)):
            u[m] -= sum(a[k] * yh[n_ord + m - k] for k in range(m + 1, n_ord + 1))
        self.xh = xp[-n_ord:].copy() if n_ord else self.xh
        return u

    def _keep(self, y: np.ndarray) -> None:
        if self.order:
            self.yh = np.concatenate([self.yh, y])[-self.order :].copy()


class IIR(_Stateful):
    """Streaming time-invariant IIR filter of any order (``lfilter(b, a)``)."""

    CHUNK = 512

    def __init__(self, b, a):
        b = np.asarray(b, float)
        a = np.asarray(a, float)
        b, a = b / a[0], a / a[0]
        order = max(len(a), len(b)) - 1
        super().__init__(order)
        self.b = np.pad(b, (0, order + 1 - len(b)))
        self.a = np.pad(a, (0, order + 1 - len(a)))
        g = np.zeros(self.CHUNK)  # impulse response of 1 / A(z)
        hist = [0.0] * order
        for i in range(self.CHUNK):
            v = (1.0 if i == 0 else 0.0) - sum(self.a[k] * hist[-k] for k in range(1, order + 1))
            g[i] = v
            hist = (hist + [v])[-order:] if order else hist
        idx = np.arange(self.CHUNK)
        lag = idx[:, None] - idx[None, :]
        self.toeplitz = np.where(lag >= 0, g[np.clip(lag, 0, None)], 0.0)

    def __call__(self, x: np.ndarray) -> np.ndarray:
        out = np.empty(len(x))
        for s in range(0, len(x), self.CHUNK):
            seg = x[s : s + self.CHUNK]
            size = len(seg)
            u = self._excite(seg, self.b, self.a)
            y = self.toeplitz[:size, :size] @ u
            self._keep(y)
            out[s : s + size] = y
        return out


class TVBiquad(_Stateful):
    """Biquad whose coefficients may change from block to block (state carried)."""

    def __init__(self):
        super().__init__(2)

    def __call__(self, x: np.ndarray, b, a) -> np.ndarray:
        b = np.asarray(b, float)
        a = np.asarray(a, float)
        size = len(x)
        u = self._excite(x, b, a)
        # impulse response of 1 / (1 + a1 z^-1 + a2 z^-2) from its poles
        disc = complex(a[1] * a[1] - 4 * a[2])
        p1 = (-a[1] + disc**0.5) / 2
        p2 = (-a[1] - disc**0.5) / 2
        k = np.arange(1, size + 1)
        if abs(p1 - p2) < 1e-9:
            g = (k * p1 ** (k - 1)).real
        else:
            g = ((p1**k - p2**k) / (p1 - p2)).real
        y = np.convolve(u, g)[:size]
        self._keep(y)
        return y


# ------------------------------------------------------------------ building blocks
class Bed:
    """A seamless loop of pink noise, shaped in the frequency domain, read block by block."""

    def __init__(self, rng: np.random.Generator, sr: int, *mags: Mag, length: int = LOOP):
        f = np.fft.rfftfreq(length, 1 / sr)
        spec = rng.standard_normal(len(f)) + 1j * rng.standard_normal(len(f))
        spec *= pink_mag(f)
        spec[0] = 0.0
        # normalise the *unfiltered* base so the filters keep their relative level
        base_rms = math.sqrt(2 * float(np.sum(np.abs(spec) ** 2))) / length
        spec *= TARGET_RMS / (base_rms or 1.0)
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

    def render(self, n: int, rate, gain=(0.2, 1.0), heavy: float = 0.0, tail=None) -> np.ndarray:
        """``rate``: grains per sample (scalar or per-sample array).

        ``tail`` = (alpha, cap, offset) multiplies each gain by
        ``min(pareto(alpha), cap) + offset``.
        """
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
            if tail:
                g *= np.minimum(rng.pareto(tail[0], k), tail[1]) + tail[2]
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


def _drop_tick(rng, sr):
    """Rain 1c: a raindrop tick, 4-12 ms noise burst band-passed at 1.8-6 kHz."""
    m = int(sr * rng.uniform(0.004, 0.012))
    x = rng.standard_normal(m) * np.exp(-np.arange(m) / (m / 5))
    return iir(*_biquad("bp", rng.uniform(1800, 6000), sr, rng.uniform(1.5, 3.0)), x)


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

    def white(self, n: int) -> np.ndarray:
        return self.rng.standard_normal(n)


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


class Leaves(_Calibrated):
    """Rustling leaves: gusts sweep through the canopy, thousands of soft grains."""

    name = "leaves"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        rng = self.rng
        self.grains = Grains(rng, [_grain(rng, sr, rng.uniform(0.004, 0.035), rng.uniform(1800, 7000),
                                          rng.uniform(0.8, 2.0)) for _ in range(64)])
        self.gust = SmoothRandom(rng, 0.0, 1.0, 2.6, sr)
        self.hiss = Bed(rng, sr, biquad_mag("hp", 2200, sr))
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
        self.bed = Bed(rng, sr, biquad_mag("bp", 900, sr, 0.5))
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


class WhiteNoise(Generator):
    name = "white"

    def render(self, n):
        return self.white(n) * TARGET_RMS


class PinkNoise(Generator):
    """Paul Kellet style -3 dB/octave filter."""

    name = "pink"
    B = (0.049922035, -0.095993537, 0.050612699, -0.004408786)
    A = (1.0, -2.494956002, 2.017265875, -0.522189400)

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.filt = IIR(self.B, self.A)

    def render(self, n):
        return self.filt(self.white(n)) * (TARGET_RMS / 0.0864)


class BrownNoise(Generator):
    """Integrated white noise with a gentle DC blocker."""

    name = "brown"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.leaky = IIR([1.0], [1.0, -0.997])
        self.dc = IIR(*_biquad("hp", 20, sr))

    def render(self, n):
        return self.dc(self.leaky(self.white(n))) * (TARGET_RMS / 7.5)


class Fan(Generator):
    """Steady air noise with a faint rotating hum."""

    name = "fan"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.pink = PinkNoise(sr, seed)
        self.lp = IIR(*_biquad("lp", 1400, sr, 0.6))
        self.phase = 0

    def render(self, n):
        y = self.lp(self.pink.render(n))
        t = (self.phase + np.arange(n)) / self.sr
        self.phase += n
        wobble = 1.0 + 0.04 * np.sin(2 * np.pi * 7.3 * t)
        hum = 0.012 * np.sin(2 * np.pi * 98 * t) * (1 + 0.3 * np.sin(2 * np.pi * 0.2 * t))
        return y * wobble * 1.25 + hum


class Rain(Generator):
    """Steady rain bed plus individual drops hitting surfaces ("Regen 1c").

    The original bed at 0.8 plus clearly audible single drops: 14 ticks/s and
    6 pitched 'plips'/s with a Pareto-weighted loudness.
    """

    name = "rain"
    LEVEL = 1.13  # long-term average of the hand-tuned bed is ~0.89 x TARGET_RMS
    TICKS_PER_S, PLIPS_PER_S, PLIP_GAIN = 14.0, 6.0, 0.35
    MIX = 1.21  # scales bed*0.8 + drops back to TARGET_RMS (mono)

    def __init__(self, sr, seed=None, drops_per_s=900):
        super().__init__(sr, seed)
        self.pink = PinkNoise(sr, seed)
        self.hp = IIR(*_biquad("hp", 500, sr))
        self.lp = IIR(*_biquad("lp", 7000, sr))
        self.drop = IIR(*_biquad("bp", 2800, sr, 0.9))
        self.rate = drops_per_s
        self.intensity = SmoothRandom(self.rng, 0.75, 1.15, 6.0, sr)
        self.ticks = Grains(self.rng, [_drop_tick(self.rng, sr) for _ in range(64)])
        self.plips = Grains(self.rng, [_drop_plip(self.rng, sr) for _ in range(64)])

    def render(self, n):
        bed = self.lp(self.hp(self.pink.render(n)))
        hits = np.zeros(n)
        idx = np.flatnonzero(self.rng.random(n) < self.rate / self.sr)
        hits[idx] = np.minimum(self.rng.pareto(3.0, len(idx)), 3.0)
        drops = self.drop(hits)
        base = (bed * 1.6 + drops * 0.35) * self.intensity.render(n) * self.LEVEL
        tail = (2.5, 3.0, 0.3)  # 0.7 = mean channel gain of the stereo original
        single = self.ticks.render(n, self.TICKS_PER_S / self.sr, (0.7, 0.7), tail=tail)
        single += self.plips.render(n, self.PLIPS_PER_S / self.sr, (0.7 * self.PLIP_GAIN,) * 2, tail=tail)
        return (base * 0.8 + single) * self.MIX


class Wind(Generator):
    """Gusty wind: band-limited noise with wandering cutoff and level."""

    name = "wind"
    BLOCK = 256

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.cut = SmoothRandom(self.rng, 250, 900, 4.0, sr / self.BLOCK)
        self.level = SmoothRandom(self.rng, 0.35, 1.2, 5.0, sr)
        self.lp = IIR(*_biquad("lp", 1800, sr, 0.6))
        self.bp = TVBiquad()

    def render(self, n):
        x = self.lp(self.white(n))
        out = np.empty_like(x)
        cuts = self.cut.render(math.ceil(n / self.BLOCK))
        for k, start in enumerate(range(0, n, self.BLOCK)):
            seg = x[start : start + self.BLOCK]
            out[start : start + len(seg)] = self.bp(seg, *_biquad("bp", float(cuts[k]), self.sr, 1.2))
        return out * self.level.render(n) * (TARGET_RMS / 0.120)


class Waves(Generator):
    """Ocean waves: swells that build, break and wash back out."""

    name = "waves"
    BLOCK = 256

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.pink = PinkNoise(sr, seed)
        self.brown = BrownNoise(sr, None if seed is None else seed + 1)
        self.lp = TVBiquad()
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
            seg = x[start : start + self.BLOCK]
            out[start : start + len(seg)] = self.lp(seg, *_biquad("lp", 300 + 3500 * e**1.5, self.sr, 0.6))
        return out * env * 3.2


def _pd_lop(f, sr):
    """Pure Data ``lop~``: one-pole low-pass."""
    k = min(1.0, 2 * math.pi * f / sr)
    return [k], [1.0, -(1 - k)]


def _pd_hip(f, sr):
    """Pure Data ``hip~``: one-pole high-pass."""
    c = max(0.0, 1 - 2 * math.pi * f / sr)
    return [(1 + c) / 2, -(1 + c) / 2], [1.0, -c]


def _pd_bp(f, q, sr):
    """Pure Data ``bp~``: two-pole resonator."""
    om = 2 * math.pi * f / sr
    r = max(0.0, 1 - om / q) if q > 0 else 0.0
    return [2 * (1 - r) * ((1 - r) + r * om), 0.0, 0.0], [1.0, -2 * r * math.cos(om), r * r]


FIRE_POST = [("hip", 1000), ("bp", 1200, 0.6), ("bp", 2600, 0.4), ("bp", 600, 0.2)]


class _IIRCols(IIR):
    """:class:`IIR` over the columns of a ``(CHUNK, cols)`` block, each column
    with its own state (one matrix product for all of them)."""

    def __init__(self, b, a, cols):
        super().__init__(b, a)
        self.xh = np.zeros((self.order, cols))
        self.yh = np.zeros((self.order, cols))

    def __call__(self, x: np.ndarray) -> np.ndarray:
        o, size = self.order, len(x)
        xp = np.concatenate([self.xh, x])
        u = self.b[0] * x
        for k in range(1, o + 1):
            u = u + self.b[k] * xp[o - k : o - k + size]
        for m in range(min(o, size)):
            for k in range(m + 1, o + 1):
                u[m] -= self.a[k] * self.yh[o + m - k]
        y = self.toeplitz[:size, :size] @ u
        self.xh = xp[-o:].copy()
        self.yh = np.concatenate([self.yh, y])[-o:].copy()
        return y


class Fire(Generator):
    """Fireplace after Andy Farnell, *Designing Sound*, Practical 11 ("Feuer G").

    Four fire voices (one per colour filter in FIRE_POST), summed x0.2. One
    voice is crackles (triggered when the RMS of 1 Hz low-passed noise over the
    last 1024 samples lands in 50..51 dB, checked every 512 samples; r = 0..29
    sets an r ms squared decay and a band-pass at 1500 + 500 r Hz), hiss (noise
    above 1 kHz gated by (10 x low-passed noise)^4 x 600) and lapping (noise
    through a 30 Hz resonator, x100, clipped), mixed 0.2 / 0.3 / 0.6. Mono:
    one fire (the device renders two, cross-mixed).
    """

    name = "fire"
    HOP = IIR.CHUNK
    VOICES = len(FIRE_POST)
    LEVEL = 0.81  # RMS -> TARGET_RMS

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        v = self.VOICES
        self.lop = _IIRCols(*_pd_lop(1, sr), v)
        self.hip1k = _IIRCols(*_pd_hip(1000, sr), v)
        self.res30 = _IIRCols(*_pd_bp(30, 5, sr), v)
        self.hip25a = _IIRCols(*_pd_hip(25, sr), v)
        self.hip25b = _IIRCols(*_pd_hip(25, sr), v)
        self.posts = [IIR(*(_pd_hip(p[1], sr) if p[0] == "hip" else _pd_bp(p[1], p[2], sr))) for p in FIRE_POST]
        self.crackles = [TVBiquad() for _ in range(v)]
        self.freq = [1500.0] * v
        self.envs: list[list[list[int]]] = [[] for _ in range(v)]
        self.prev_sq: np.ndarray | None = None
        self.buf = np.zeros(0)

    def _hop(self) -> np.ndarray:
        n, sr, v = self.HOP, self.sr, self.VOICES
        nz = self.rng.uniform(-1, 1, (n, v))
        lo = self.lop(nz)
        m = (lo * 10) ** 2
        mix = self.hip1k(nz) * (m * m * 600) * 0.3
        mix += self.hip25b(np.clip(self.hip25a(self.res30(nz) * 100), -0.9, 0.9)) * 0.36
        out = np.zeros(n)
        for c in range(v):
            y = mix[:, c]
            band = self.crackles[c](nz[:, c], *_pd_bp(self.freq[c], 1, sr))
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
                y = y + band * env * 0.2
            out += self.posts[c](y)
        sq = np.einsum("ij,ij->j", lo, lo)
        if self.prev_sq is not None:
            db = 100 + 20 * np.log10(np.maximum(np.sqrt((self.prev_sq + sq) / (2 * n)), 1e-10))
            for c in np.flatnonzero((db >= 50) & (db < 51)).tolist():
                r = int(self.rng.integers(0, 30))
                self.freq[c] = 1500.0 + 500.0 * r
                self.envs[c].append([0, max(1, int(sr * r / 1000))])
        self.prev_sq = sq
        return out * 0.2

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
        x = rng.standard_normal(n)
        lp = IIR(*_biquad("lp", rng.uniform(90, 220), sr, BUTTER_Q))
        rumble = lp(IIR([1.0], [1.0, -0.98])(x))
        attack = rng.uniform(0.05, 0.4) if close else rng.uniform(0.6, 1.8)
        env = np.minimum(t / attack, 1.0) * np.exp(-t / (dur / 3.2))
        # rolling: a few secondary swells
        for _ in range(rng.integers(2, 5)):
            c, w = rng.uniform(0.5, dur * 0.7), rng.uniform(0.3, 1.2)
            env *= 1 + 0.9 * np.exp(-(((t - c) / w) ** 2))
        out = rumble * env
        if close:
            crack = IIR(*_biquad("hp", 1500, sr, BUTTER_Q))(rng.standard_normal(n))
            out += crack * np.exp(-t / 0.25) * 0.02
        return _peak_norm(out) * rng.uniform(0.35, 0.8)


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
