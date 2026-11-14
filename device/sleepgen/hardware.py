"""Hardware glue: amplifier volume (ALSA), volume knob (GPIO), audio output."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
from typing import Callable

log = logging.getLogger(__name__)


class HardwareVolume:
    """Device volume through an ALSA mixer control (affects music *and* sounds).

    Uses ``amixer -M`` so 0..1 maps to a perceptually even scale.
    Falls back to an in-memory value when no mixer is available.
    """

    def __init__(self, card: int = 0, control: str = "Digital", enabled: bool = True,
                 on_change: Callable[[], None] | None = None):
        self.card, self.control, self.on_change = card, control, on_change
        self.available = enabled and shutil.which("amixer") is not None
        self._value = 0.5
        if self.available:
            try:
                self._value = self._read()
            except Exception as exc:  # noqa: BLE001
                log.warning("ALSA mixer %r not usable (%s); using software volume", control, exc)
                self.available = False

    def _read(self) -> float:
        out = subprocess.run(
            ["amixer", "-M", "-c", str(self.card), "sget", self.control],
            check=True, capture_output=True, text=True,
        ).stdout
        m = re.search(r"\[(\d+)%\]", out)
        if not m:
            raise RuntimeError("no volume in amixer output")
        return int(m.group(1)) / 100

    @property
    def value(self) -> float:
        return self._value

    def set(self, v: float):
        v = round(min(max(v, 0.0), 1.0), 3)
        self._value = v
        if self.available:
            subprocess.run(
                ["amixer", "-q", "-M", "-c", str(self.card), "sset", self.control, f"{int(v * 100)}%"],
                check=False,
            )
        if self.on_change:
            self.on_change()

    def step(self, delta: float):
        self.set(self._value + delta)


class Knob:
    """Rotary encoder: turn = volume, click = sounds on/off, hold = lamp on/off."""

    def __init__(self, pin_a: int, pin_b: int, pin_button: int, step: float,
                 on_turn: Callable[[float], None], on_click: Callable[[], None],
                 on_hold: Callable[[], None]):
        from gpiozero import Button, RotaryEncoder  # only on the Pi

        self.enc = RotaryEncoder(pin_a, pin_b, max_steps=0, bounce_time=0.002)
        self.enc.when_rotated_clockwise = lambda: on_turn(step)
        self.enc.when_rotated_counter_clockwise = lambda: on_turn(-step)
        self.btn = Button(pin_button, pull_up=True, bounce_time=0.03, hold_time=1.2)
        self._held = False

        def held():
            self._held = True
            on_hold()

        def released():
            if not self._held:
                on_click()
            self._held = False

        self.btn.when_held = held
        self.btn.when_released = released


class AudioOutput(threading.Thread):
    """Pulls blocks from the engine and writes them to the sound card."""

    def __init__(self, render: Callable[[int], object], sr: int, block: int, device=None):
        super().__init__(name="audio", daemon=True)
        self.render, self.sr, self.block, self.device = render, sr, block, device
        self._stop = threading.Event()

    def run(self):
        import sounddevice as sd

        with sd.OutputStream(samplerate=self.sr, channels=2, dtype="float32",
                             blocksize=self.block, device=self.device, latency="high") as stream:
            log.info("audio running: %s Hz, block %s, device %s", self.sr, self.block, self.device)
            while not self._stop.is_set():
                stream.write(self.render(self.block))

    def stop(self):
        self._stop.set()
