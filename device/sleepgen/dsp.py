"""Procedural sound generators.

Every generator produces stereo float32 blocks shaped (n, 2) with a loudness of
roughly -18 dBFS RMS at gain 1.0, so layers can be mixed without surprises.
Everything is synthesised live: no sample files, no licensing questions, and no
audible loop points. File based loops are supported via :class:`FileLoop`.
"""

from __future__ import annotations

import math
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


class Rain(Generator):
    """Steady rain bed plus individual drops hitting surfaces."""

    name = "rain"

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

    def render(self, n):
        bed, self.hzi = _lfilter(self.hb, self.ha, self.pink.render(n), self.hzi)
        bed, self.lzi = _lfilter(self.lb, self.la, bed, self.lzi)
        p = self.rate / self.sr
        hits = (self.rng.random((n, 2)) < p) * np.minimum(self.rng.pareto(3.0, (n, 2)), 3.0)
        drops, self.dzi = _lfilter(self.db, self.da, hits, self.dzi)
        env = self.intensity.render(n)[:, None]
        return (bed * 1.6 + drops * 0.35) * env


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


class Fire(Generator):
    """Crackling fireplace: low roar plus random crackles and pops."""

    name = "fire"

    def __init__(self, sr, seed=None):
        super().__init__(sr, seed)
        self.brown = BrownNoise(sr, seed)
        self.lb, self.la = _biquad("lp", 500, sr)
        self.lzi = _zi(self.lb, self.la)
        self.cb, self.ca = _biquad("hp", 1800, sr)
        self.czi = _zi(self.cb, self.ca)
        self.activity = SmoothRandom(self.rng, 2, 40, 1.5, sr)

    def render(self, n):
        roar, self.lzi = _lfilter(self.lb, self.la, self.brown.render(n), self.lzi)
        rate = self.activity.render(n) / self.sr
        hits = (self.rng.random((n, 2)) < rate[:, None]) * self.rng.uniform(-1, 1, (n, 2))
        hits *= np.minimum(self.rng.pareto(2.5, (n, 2)), 3.0) + 0.2
        crackle, self.czi = _lfilter(self.cb, self.ca, hits, self.czi)
        return roar * 0.8 + crackle * 0.5


@dataclass
class _Event:
    buf: np.ndarray
    pos: int = 0


class EventGenerator(Generator):
    """Base for sparse one-shot events (thunder, birds)."""

    def __init__(self, sr, seed=None, every=(30.0, 120.0)):
        super().__init__(sr, seed)
        self.every = every
        self.countdown = int(self.rng.uniform(3, every[0]) * sr)
        self.active: list[_Event] = []

    def make_event(self) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def trigger(self):
        self.active.append(_Event(self.make_event()))

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
    """Short songbird phrases built from swept sine chirps."""

    name = "birds"

    def __init__(self, sr, seed=None, every=(3.0, 12.0)):
        super().__init__(sr, seed, every)

    def make_event(self):
        sr, rng = self.sr, self.rng
        base = rng.uniform(2500, 5000)
        notes = []
        for _ in range(rng.integers(3, 9)):
            d = rng.uniform(0.04, 0.18)
            m = int(d * sr)
            t = np.arange(m) / sr
            f = base * (1 + rng.uniform(-0.35, 0.35) * t / d)
            ph = 2 * np.pi * np.cumsum(f) / sr
            ph += rng.uniform(0.5, 3) * np.sin(2 * np.pi * rng.uniform(30, 90) * t)
            env = np.sin(np.pi * t / d) ** 2
            notes.append(np.sin(ph) * env)
            notes.append(np.zeros(int(rng.uniform(0.02, 0.12) * sr)))
        mono = np.concatenate(notes) * rng.uniform(0.04, 0.12)
        pan = rng.uniform(-0.8, 0.8)
        return np.stack([mono * (1 - pan), mono * (1 + pan)], axis=1)


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
    for cls in (WhiteNoise, PinkNoise, BrownNoise, Fan, Rain, Wind, Waves, Fire, Thunder, Birds)
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
}


def make_generator(source: str, sr: int, seed: int | None = None) -> Generator:
    """Create a generator from ``gen:<name>``/``<name>`` or ``file:<path.wav>``."""
    if source.startswith("file:"):
        return FileLoop(path=source[5:], sr=sr)
    name = source[4:] if source.startswith("gen:") else source
    if name not in GENERATORS:
        raise KeyError(f"Unknown sound '{name}'. Known: {', '.join(GENERATORS)}")
    return GENERATORS[name](sr, seed)
