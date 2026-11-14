"""Lamp: colour maths, effects (sunrise, candle, fall-asleep) and LED drivers."""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol

EFFECT_SUNRISE = "Sonnenaufgang"
EFFECT_CANDLE = "Kerze"
EFFECT_SUNSET = "Einschlafen"
EFFECTS = [EFFECT_SUNRISE, EFFECT_CANDLE, EFFECT_SUNSET]

# colour of the SK6812 "warm white" chip (about 3000 K) in linear RGB
WARM_WHITE = (1.0, 0.706, 0.42)


def kelvin_to_rgb(k: float) -> tuple[float, float, float]:
    """Black body approximation (Tanner Helland), returns 0..1 per channel."""
    t = max(1000.0, min(k, 12000.0)) / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * (t - 60) ** -0.1332047592
        g = 288.1221695283 * (t - 60) ** -0.0755148492
        b = 255.0
    clamp = lambda v: max(0.0, min(v, 255.0)) / 255.0  # noqa: E731
    return clamp(r), clamp(g), clamp(b)


def rgb_to_rgbw(r: float, g: float, b: float) -> tuple[float, float, float, float]:
    """Move as much as possible onto the warm white chip (nicer light, less current)."""
    w = min(r / WARM_WHITE[0], g / WARM_WHITE[1], b / WARM_WHITE[2], 1.0)
    return (
        max(0.0, r - w * WARM_WHITE[0]),
        max(0.0, g - w * WARM_WHITE[1]),
        max(0.0, b - w * WARM_WHITE[2]),
        w,
    )


def sunrise_color(p: float) -> tuple[float, tuple[float, float, float]]:
    """Brightness (0..1) and RGB for sunrise progress p in 0..1.

    Starts as a faint deep red glow, passes through orange and ends in a
    bright neutral white, like dawn light through a window.
    """
    p = max(0.0, min(p, 1.0))
    bri = 0.004 + 0.996 * p**2.2
    kelvin = 1000 + 3000 * p**0.8
    r, g, b = kelvin_to_rgb(kelvin)
    if p < 0.25:  # extra red in the very first minutes
        g *= 0.4 + 2.4 * p
        b *= 4 * p
    return bri, (r, g, b)


class LedDriver(Protocol):
    count: int

    def show(self, pixels: list[tuple[float, float, float, float]]) -> None: ...


class NullDriver:
    """Used when no LEDs are attached (development, demo)."""

    def __init__(self, count: int = 1):
        self.count = count
        self.last: list[tuple[float, float, float, float]] = []

    def show(self, pixels):
        self.last = list(pixels)


class SpiSk6812Driver:
    """SK6812 RGBW (or WS2812 RGB) on the Pi's SPI MOSI pin (GPIO10).

    Each LED bit becomes three SPI bits at 2.4 MHz: 1 -> 110, 0 -> 100.
    Requires ``dtparam=spi=on`` and a fixed core clock (see docs/SETUP.md).
    A 74AHCT125 level shifter between GPIO10 and DIN is recommended.
    """

    def __init__(self, count: int, rgbw: bool = True, bus: int = 0, dev: int = 0,
                 max_brightness: float = 0.7, gamma: float = 2.2):
        import spidev  # imported lazily so development machines do not need it

        self.count, self.rgbw = count, rgbw
        self.max_brightness, self.gamma = max_brightness, gamma
        self.spi = spidev.SpiDev()
        self.spi.open(bus, dev)
        self.spi.max_speed_hz = 2_400_000
        self.spi.mode = 0
        lut = []
        for byte in range(256):
            bits = 0
            for i in range(7, -1, -1):
                bits = (bits << 3) | (0b110 if byte >> i & 1 else 0b100)
            lut.append(bits.to_bytes(3, "big"))
        self._lut = lut

    def _byte(self, v: float) -> int:
        return int(round(255 * (max(0.0, min(v, 1.0)) * self.max_brightness) ** self.gamma))

    def show(self, pixels):
        out = bytearray()
        for r, g, b, w in pixels:
            chans = (g, r, b, w) if self.rgbw else (g + w * WARM_WHITE[1], r + w, b + w * WARM_WHITE[2])
            for c in chans:
                out += self._lut[self._byte(c)]
        out += bytes(64)  # >80 us low = latch
        self.spi.writebytes2(out)


@dataclass
class LampState:
    on: bool = False
    brightness: int = 180  # 0..255
    kelvin: int = 2700
    rgb: tuple[int, int, int] | None = None  # set when the user picked a colour
    effect: str | None = None


class Lamp:
    """Lamp logic, independent of the LED hardware. Thread safe."""

    def __init__(self, driver: LedDriver, on_change: Callable[[], None] | None = None,
                 fps: int = 40, clock: Callable[[], float] = time.monotonic):
        self.driver, self.on_change, self.fps, self.clock = driver, on_change, fps, clock
        self.state = LampState()
        self.sunrise_minutes = 30.0
        self.sunset_minutes = 30.0
        self._effect_start = 0.0
        self._effect_from_bri = 1.0
        self._flicker = [random.random() for _ in range(driver.count)]
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------- control
    def apply(self, cmd: dict):
        """Apply a Home Assistant JSON light command."""
        with self._lock:
            s = self.state
            if "brightness" in cmd:
                s.brightness = int(max(1, min(cmd["brightness"], 255)))
            if "color_temp_kelvin" in cmd:
                s.kelvin, s.rgb = int(cmd["color_temp_kelvin"]), None
            elif "color_temp" in cmd:  # mireds
                s.kelvin, s.rgb = int(1_000_000 / max(cmd["color_temp"], 1)), None
            if "color" in cmd and {"r", "g", "b"} <= set(cmd["color"]):
                c = cmd["color"]
                s.rgb = (int(c["r"]), int(c["g"]), int(c["b"]))
            if "effect" in cmd:
                self._start_effect(cmd["effect"], cmd.get("transition"))
            elif cmd.get("state") == "ON" and {"brightness", "color", "color_temp", "color_temp_kelvin"} & set(cmd):
                s.effect = None  # an explicit colour/brightness ends an effect
            if cmd.get("state") == "OFF":
                s.on, s.effect = False, None
            elif cmd.get("state") == "ON":
                s.on = True
        self._changed()

    def start_sunrise(self, minutes: float | None = None):
        with self._lock:
            self._start_effect(EFFECT_SUNRISE, minutes * 60 if minutes else None)
            self.state.on = True
        self._changed()

    def start_sunset(self, minutes: float | None = None):
        with self._lock:
            self._start_effect(EFFECT_SUNSET, minutes * 60 if minutes else None)
            self.state.on = True
        self._changed()

    def _start_effect(self, effect: str | None, transition_s: float | None):
        s = self.state
        if effect not in EFFECTS:
            s.effect = None
            return
        if effect == EFFECT_SUNRISE and transition_s:
            self.sunrise_minutes = transition_s / 60
        if effect == EFFECT_SUNSET and transition_s:
            self.sunset_minutes = transition_s / 60
        self._effect_from_bri = s.brightness / 255 if s.on else 0.6
        self._effect_start = self.clock()
        s.effect = effect

    def ha_state(self) -> dict:
        s = self.state
        out = {"state": "ON" if s.on else "OFF", "brightness": s.brightness, "effect": s.effect}
        if s.rgb:
            out.update(color_mode="rgb", color={"r": s.rgb[0], "g": s.rgb[1], "b": s.rgb[2]})
        else:
            out.update(color_mode="color_temp", color_temp_kelvin=s.kelvin)
        return out

    def _changed(self):
        if self.on_change:
            self.on_change()

    # ------------------------------------------------------------- render
    def frame(self) -> list[tuple[float, float, float, float]]:
        """Compute one frame of RGBW pixel values (0..1)."""
        with self._lock:
            s = self.state
            n = self.driver.count
            if not s.on:
                return [(0.0, 0.0, 0.0, 0.0)] * n
            now = self.clock()
            bri = s.brightness / 255
            rgb = tuple(v / 255 for v in s.rgb) if s.rgb else kelvin_to_rgb(s.kelvin)
            ended = False

            if s.effect == EFFECT_SUNRISE:
                p = (now - self._effect_start) / max(self.sunrise_minutes * 60, 1)
                b, rgb = sunrise_color(p)
                bri = b * (s.brightness / 255 if p < 1 else 1.0)
                if p >= 1:  # stay at full daylight afterwards
                    s.effect, s.brightness, s.kelvin, s.rgb = None, 255, 4000, None
                    ended = True
            elif s.effect == EFFECT_SUNSET:
                p = (now - self._effect_start) / max(self.sunset_minutes * 60, 1)
                k = 2700 - 900 * min(p, 1)
                rgb = kelvin_to_rgb(k)
                bri = self._effect_from_bri * max(0.0, 1 - p) ** 2
                if p >= 1:
                    s.on, s.effect = False, None
                    ended = True
            pixels = []
            for i in range(n):
                b = bri
                if s.effect == EFFECT_CANDLE:
                    self._flicker[i] += random.uniform(-0.15, 0.15)
                    self._flicker[i] = min(max(self._flicker[i], 0.0), 1.0)
                    b *= 0.55 + 0.45 * self._flicker[i]
                    c = kelvin_to_rgb(1800 + 400 * self._flicker[i])
                else:
                    c = rgb
                r, g, bb, w = rgb_to_rgbw(*c)
                pixels.append((r * b, g * b, bb * b, w * b))
        if ended:
            self._changed()
        return pixels

    def run(self):
        last = None
        while not self._stop.is_set():
            px = self.frame()
            if px != last:
                self.driver.show(px)
                last = px
            self._stop.wait(1 / self.fps)

    def start(self):
        self._thread = threading.Thread(target=self.run, name="lamp", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        self.driver.show([(0.0, 0.0, 0.0, 0.0)] * self.driver.count)
