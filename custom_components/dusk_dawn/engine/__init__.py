"""Pure-Python fallback of the Dusk & Dawn sound engine.

Implements the Engine API of the contract (section 1). The Rust module
``dusk_dawn_core`` exposes the same API and is preferred when installed.

Generators are built lazily in a background thread the first time a sound
gets a level above zero, so an idle engine costs neither memory nor CPU and
``set_level`` never blocks the caller.
"""

from __future__ import annotations

import threading

import numpy as np

from .dsp import GENERATORS, AlarmTone, Generator

SOUNDS = ["rain", "waves", "stream", "wind", "thunder", "birds", "leaves", "fire", "fan", "white", "pink", "brown"]
ALARM_TONES = ["bells", "classic", "birds"]

LEVEL_SMOOTH_S = 0.15  # time constant, ~0.5 s to settle
SILENT = 1e-5


def volume_curve(v: float) -> float:
    """Map a 0..1 slider to a perceptually even gain (about 40 dB range)."""
    v = min(max(v, 0.0), 1.0)
    if v <= 0:
        return 0.0
    return float(10 ** ((v - 1.0) * 2.0)) * min(1.0, v * 10)


class Engine:
    """Mixer for the procedural sounds plus the alarm tone. Thread safe."""

    def __init__(self, rate: int = 44100, seed: int | None = None) -> None:
        self._rate = int(rate)
        self._seed = seed
        self._lock = threading.RLock()
        self._levels: dict[str, float] = dict.fromkeys(SOUNDS, 0.0)
        self._gains: dict[str, float] = dict.fromkeys(SOUNDS, 0.0)
        self._gens: dict[str, Generator] = {}
        self._building: dict[str, threading.Thread] = {}
        # master: linear ramp of the 0..1 value, mapped through volume_curve
        self._master = 0.6  # same default as the Rust core
        self._master_target = 0.6
        self._master_step = 0.0  # change per sample while ramping
        self._alarm: AlarmTone | None = None
        self._alarm_age = 0  # samples since the alarm started
        self._alarm_len = 0
        self._alarm_volume = 0.7
        self._alarm_ramp = 0

    # ------------------------------------------------------------ properties
    @property
    def rate(self) -> int:
        return self._rate

    @property
    def master(self) -> float:
        return self._master

    @property
    def alarm_ringing(self) -> bool:
        return self._alarm is not None

    def sounds(self) -> list[str]:
        return list(SOUNDS)

    def levels(self) -> dict[str, float]:
        return dict(self._levels)

    # ------------------------------------------------------------ control
    def set_level(self, sound: str, level: float) -> None:
        if sound not in self._levels:
            raise KeyError(sound)
        level = min(max(float(level), 0.0), 1.0)
        with self._lock:
            self._levels[sound] = level
            if level > 0 and sound not in self._gens and sound not in self._building:
                self._build_async(sound)

    def set_master(self, volume: float, ramp_s: float = 0.0) -> None:
        volume = min(max(float(volume), 0.0), 1.0)
        with self._lock:
            self._master_target = volume
            if ramp_s <= 0:
                self._master, self._master_step = volume, 0.0
            else:
                self._master_step = (volume - self._master) / (ramp_s * self._rate)

    def start_alarm(self, tone: str, seconds: float, volume: float, ramp_s: float = 40.0) -> None:
        alarm = AlarmTone(self._rate, self._seed, tone)
        with self._lock:
            self._alarm = alarm
            self._alarm_age = 0
            self._alarm_len = int(max(seconds, 0.1) * self._rate)
            self._alarm_volume = min(max(float(volume), 0.0), 1.0)
            self._alarm_ramp = int(max(ramp_s, 0.0) * self._rate)

    def stop_alarm(self) -> None:
        with self._lock:
            self._alarm = None

    # ------------------------------------------------------------ helpers
    def _seed_for(self, sound: str) -> int | None:
        return None if self._seed is None else self._seed + SOUNDS.index(sound)

    def _build(self, sound: str) -> None:
        gen = GENERATORS[sound](self._rate, self._seed_for(sound))
        with self._lock:
            self._gens[sound] = gen
            self._building.pop(sound, None)

    def _build_async(self, sound: str) -> None:
        thread = threading.Thread(target=self._build, args=(sound,), name=f"dusk_dawn_build_{sound}", daemon=True)
        self._building[sound] = thread
        thread.start()

    def wait_ready(self, timeout: float | None = None) -> bool:
        """Block until all requested generators are built (tests, offline renders)."""
        for thread in list(self._building.values()):
            thread.join(timeout)
        return not self._building

    # ------------------------------------------------------------ render
    def render(self, frames: int) -> bytes:
        """Render ``frames`` mono samples as signed 16-bit little endian."""
        n = int(frames)
        if n <= 0:
            return b""
        with self._lock:
            active = [
                s for s in SOUNDS
                if s in self._gens and (self._gains[s] > SILENT or self._levels[s] > 0)
            ]
            master_idle = self._master_step == 0.0
            if not active and self._alarm is None:
                if not master_idle:
                    self._advance_master(n)
                return bytes(2 * n)  # silence costs nothing

            out = np.zeros(n)
            if active:
                ramp = np.arange(1, n + 1) / n
                k = min(1.0, n / (LEVEL_SMOOTH_S * self._rate))
                for s in active:
                    g0 = self._gains[s]
                    target = volume_curve(self._levels[s])
                    g1 = g0 + (target - g0) * k
                    if g1 < SILENT and target == 0.0:
                        g1 = 0.0
                    self._gains[s] = g1
                    out += self._gens[s].render(n) * (g0 + (g1 - g0) * ramp)
                m0 = self._master
                m1 = self._advance_master(n)
                curve0, curve1 = volume_curve(m0), volume_curve(m1)
                out *= curve0 + (curve1 - curve0) * ramp
            elif not master_idle:
                self._advance_master(n)

            if self._alarm is not None:
                age = self._alarm_age + np.arange(n)
                if self._alarm_ramp > 0:
                    env = 0.15 + 0.85 * np.minimum(age / self._alarm_ramp, 1.0)
                else:
                    env = np.ones(n)
                out += self._alarm.render(n) * env * volume_curve(self._alarm_volume)
                self._alarm_age += n
                if self._alarm_age >= self._alarm_len:
                    self._alarm = None

        out = np.tanh(out * 1.2) / 1.2  # soft limiter, transparent below ~-6 dBFS
        return (np.clip(out, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()

    def _advance_master(self, n: int) -> float:
        """Move the master ramp by ``n`` samples, return the new value."""
        if self._master_step:
            m = self._master + self._master_step * n
            if (self._master_step > 0 and m >= self._master_target) or (
                self._master_step < 0 and m <= self._master_target
            ):
                m, self._master_step = self._master_target, 0.0
            self._master = m
        return self._master


__all__ = ["ALARM_TONES", "SOUNDS", "Engine", "volume_curve"]
