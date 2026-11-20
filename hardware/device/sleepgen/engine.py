"""Mixer: layers, master volume, fades, sleep timer.

The engine is driven purely by the number of samples rendered, so it behaves the
same in real time and in tests/offline renders. Control methods are safe to call
from other threads (MQTT, knob): they only assign plain attributes that the audio
thread picks up on its next block.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .dsp import GENERATORS, AlarmTone, Generator, make_generator


def volume_curve(v: float) -> float:
    """Map a 0..1 slider to a perceptually even gain (about 40 dB range)."""
    v = min(max(v, 0.0), 1.0)
    if v <= 0:
        return 0.0
    return float(10 ** ((v - 1.0) * 2.0)) * min(1.0, v * 10)


@dataclass
class Layer:
    source: str
    gen: Generator
    level: float = 0.0  # 0..1 as set by the user
    _gain: float = 0.0  # smoothed linear gain actually applied

    @property
    def target(self) -> float:
        return volume_curve(self.level)


@dataclass
class Engine:
    sr: int = 48000
    sources: list[str] = field(default_factory=lambda: list(GENERATORS))
    fade_in_s: float = 8.0
    fade_out_s: float = 600.0  # last 10 minutes of the sleep timer fade out
    seed: int | None = None
    on_change: Callable[[], None] | None = None

    def __post_init__(self):
        self.layers: dict[str, Layer] = {}
        for i, src in enumerate(self.sources):
            if "=" in src.split(":", 1)[0]:  # "rain=file:/home/admin/sounds/rain": own recording replaces the synth
                key, src = src.split("=", 1)
            elif src.startswith("file:"):
                key = src.rstrip("/").split("/")[-1].rsplit(".", 1)[0]
            else:
                key = src.removeprefix("gen:")
            seed = None if self.seed is None else self.seed + i
            self.layers[key] = Layer(src, make_generator(src, self.sr, seed))
        self.master = 0.6
        self._master_gain = volume_curve(self.master)
        self.playing = False
        self._fade = 0.0  # 0..1 start/stop fade
        self.clock = 0.0  # seconds of audio rendered
        self.timer_end: float | None = None
        self.preset: str | None = None
        self.alarm: AlarmTone | None = None
        self.alarm_end: float | None = None
        self.alarm_volume = 0.7
        self.alarm_ramp_s = 40.0
        self._alarm_t0 = 0.0
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- control
    def set_level(self, layer: str, level: float):
        self.layers[layer].level = min(max(float(level), 0.0), 1.0)
        self.preset = None
        self._changed()

    def set_master(self, level: float):
        self.master = min(max(float(level), 0.0), 1.0)
        self._changed()

    def apply_preset(self, name: str, levels: dict[str, float]):
        for key, layer in self.layers.items():
            layer.level = float(levels.get(key, 0.0))
        self.preset = name
        self._changed()

    def play(self):
        if not self.playing:
            self.playing = True
            self._changed()

    def stop(self):
        if self.playing:
            self.playing = False
            self.timer_end = None
            self._changed()

    def set_timer(self, minutes: float | None):
        """Sleep timer. ``None`` or 0 disables it."""
        self.timer_end = self.clock + minutes * 60 if minutes else None
        self._changed()

    # ---------------------------------------------------------------- alarm
    def start_alarm(self, tone: str = "Glocken", minutes: float = 10, volume: float | None = None):
        """Ring on top of everything; gets louder over ``alarm_ramp_s`` and stops
        by itself after ``minutes`` (or earlier via :meth:`stop_alarm`)."""
        with self._lock:
            self.alarm = AlarmTone(self.sr, self.seed, tone if tone in AlarmTone.TONES else "Glocken")
            self._alarm_t0 = self.clock
            self.alarm_end = self.clock + max(minutes, 0.1) * 60
            if volume is not None:
                self.alarm_volume = min(max(float(volume), 0.0), 1.0)
        self._changed()

    def stop_alarm(self):
        if self.alarm is not None:
            with self._lock:
                self.alarm, self.alarm_end = None, None
            self._changed()

    @property
    def alarm_ringing(self) -> bool:
        return self.alarm is not None

    @property
    def timer_remaining(self) -> float | None:
        if self.timer_end is None:
            return None
        return max(0.0, self.timer_end - self.clock)

    def state(self) -> dict:
        rem = self.timer_remaining
        return {
            "playing": self.playing,
            "master": round(self.master, 3),
            "preset": self.preset,
            "levels": {k: round(l.level, 3) for k, l in self.layers.items()},
            "timer_remaining_min": None if rem is None else round(rem / 60, 1),
            "alarm_ringing": self.alarm_ringing,
        }

    def _changed(self):
        if self.on_change:
            self.on_change()

    # ---------------------------------------------------------------- render
    def _timer_gain(self, t: np.ndarray) -> np.ndarray:
        if self.timer_end is None:
            return np.ones_like(t)
        remaining = np.maximum(self.timer_end - t, 0.0)
        x = np.minimum(remaining / max(self.fade_out_s, 1e-3), 1.0)
        return x**2.5  # slow at first, gently trailing into silence

    def render(self, n: int) -> np.ndarray:
        """Render ``n`` stereo frames as float32 in [-1, 1]."""
        with self._lock:
            t = self.clock + np.arange(1, n + 1) / self.sr
            out = np.zeros((n, 2))
            if self.playing or self._fade > 0:
                ramp = np.linspace(0, 1, n, endpoint=False)[:, None]
                for layer in self.layers.values():
                    target = layer.target
                    if layer._gain < 1e-5 and target < 1e-5:
                        layer._gain = 0.0
                        continue
                    g0 = layer._gain
                    g1 = g0 + (target - g0) * min(1.0, n / (0.08 * self.sr))
                    out += layer.gen.render(n) * (g0 + (g1 - g0) * ramp)
                    layer._gain = g1

                # start/stop fade
                step = n / self.sr / (self.fade_in_s if self.playing else 2.0)
                f0 = self._fade
                f1 = min(1.0, f0 + step) if self.playing else max(0.0, f0 - step)
                fade = (f0 + (f1 - f0) * ramp[:, 0]) ** 2
                self._fade = f1

                m0 = self._master_gain
                m1 = m0 + (volume_curve(self.master) - m0) * min(1.0, n / (0.05 * self.sr))
                master = m0 + (m1 - m0) * ramp[:, 0]
                self._master_gain = m1

                out *= (fade * master * self._timer_gain(t))[:, None]
            alarm_done = False
            if self.alarm is not None:
                age = t - self._alarm_t0
                ramp = 0.15 + 0.85 * np.minimum(age / max(self.alarm_ramp_s, 1e-3), 1.0)
                out += self.alarm.render(n) * (ramp * volume_curve(self.alarm_volume))[:, None]
                if self.alarm_end is not None and t[-1] >= self.alarm_end:
                    self.alarm, self.alarm_end, alarm_done = None, None, True
            out = np.tanh(out * 1.2) / 1.2  # soft limiter, transparent below ~-6 dBFS
            self.clock = float(t[-1])

            if self.timer_end is not None and self.clock >= self.timer_end:
                self.timer_end = None
                self.playing = False
                self._fade = 0.0
                fire = True
            else:
                fire = False
            fire = fire or alarm_done
        if fire:
            self._changed()
        return out.astype(np.float32)
