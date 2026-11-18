"""Wires engine, lamp, hardware and Home Assistant together."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path

from . import __version__
from .engine import Engine
from .hardware import HardwareVolume
from .light import Lamp, NullDriver, SpiSk6812Driver
from .mqtt_ha import TIMER_OPTIONS, timer_option_minutes

log = logging.getLogger(__name__)


class App:
    def __init__(self, cfg: dict, *, hardware: bool = True):
        self.cfg = cfg
        self.version = __version__
        a = cfg["audio"]
        self.engine = Engine(
            sr=a["sample_rate"], sources=cfg["sounds"], fade_in_s=a["fade_in_s"],
            fade_out_s=a["fade_out_min"] * 60, on_change=self._changed,
        )
        self.timer_option = "Aus"
        self.lamp_follows_timer = False
        al = cfg["alarm"]
        self.alarm_tone = al["tone"]
        self.alarm_minutes = float(al["minutes"])
        self.engine.alarm_volume = float(al["volume"])
        self._volume_before_alarm: float | None = None

        led = cfg["led"]
        driver = NullDriver(led["count"])
        if hardware and led["driver"] == "spi":
            try:
                driver = SpiSk6812Driver(led["count"], rgbw=led["rgbw"], max_brightness=led["max_brightness"])
            except Exception as exc:  # noqa: BLE001
                log.warning("LEDs disabled: %s", exc)
        self.lamp = Lamp(driver, on_change=self._changed)

        hv = cfg["hardware_volume"]
        self.volume = HardwareVolume(hv["card"], hv["control"], hv["enabled"] and hardware, on_change=self._changed)

        self.mqtt = None
        self.knob = None
        self.audio = None
        self._dirty = threading.Event()
        self._stop = threading.Event()
        self.state_file = Path(cfg["state_file"])

    # ----------------------------------------------------------- actions
    def set_playing(self, on: bool):
        if on:
            if not any(l.level > 0 for l in self.engine.layers.values()):
                self.apply_preset(self.cfg["default_preset"])
            self.engine.play()
        else:
            self.engine.stop()
            self.timer_option = "Aus"

    def toggle_playing(self):
        self.set_playing(not self.engine.playing)

    def apply_preset(self, name: str):
        if name in self.cfg["presets"]:
            self.engine.apply_preset(name, self.cfg["presets"][name])

    def set_timer_option(self, option: str):
        minutes = timer_option_minutes(option)
        self.timer_option = option if minutes else "Aus"
        self.engine.set_timer(minutes or None)
        if minutes:
            self.set_playing(True)
            if self.lamp_follows_timer and self.lamp.state.on:
                self.lamp.start_sunset(minutes)

    # ----------------------------------------------------------- alarm
    def start_alarm(self):
        """Ring now. Stops after ``alarm_minutes`` or on a knob press."""
        floor = float(self.cfg["alarm"]["min_device_volume"])
        if not self.engine.alarm_ringing and self.volume.value < floor:
            self._volume_before_alarm = self.volume.value
            self.volume.set(floor)
        self.engine.start_alarm(self.alarm_tone, self.alarm_minutes)

    def stop_alarm(self):
        self.engine.stop_alarm()
        self._alarm_stopped()

    def _alarm_stopped(self):
        if self._volume_before_alarm is not None and not self.engine.alarm_ringing:
            v, self._volume_before_alarm = self._volume_before_alarm, None
            self.volume.set(v)

    def knob_click(self):
        """Press: stops a ringing alarm, otherwise sounds on/off."""
        if self.engine.alarm_ringing:
            self.stop_alarm()
        else:
            self.toggle_playing()

    def toggle_lamp(self):
        self.lamp.apply({"state": "OFF" if self.lamp.state.on else "ON"})

    # ----------------------------------------------------------- state
    def full_state(self) -> dict:
        st = self.engine.state()
        if st["timer_remaining_min"] is None and self.timer_option != "Aus":
            self.timer_option = "Aus"
        st.update(
            timer_option=self.timer_option,
            device_volume=round(self.volume.value, 3),
            sunrise_minutes=round(self.lamp.sunrise_minutes),
            lamp_follows_timer=self.lamp_follows_timer,
            alarm_tone=self.alarm_tone,
            alarm_minutes=round(self.alarm_minutes),
            alarm_volume=round(self.engine.alarm_volume, 3),
        )
        return st

    def _changed(self):
        self._dirty.set()

    def publish_state(self):
        self._changed()

    def save(self):
        s = self.full_state()
        data = {k: s[k] for k in ("playing", "master", "preset", "levels", "sunrise_minutes", "lamp_follows_timer",
                                  "alarm_tone", "alarm_minutes", "alarm_volume")}
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            os.replace(tmp, self.state_file)
        except OSError as exc:
            log.warning("could not save state: %s", exc)

    def restore(self):
        try:
            data = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            self.apply_preset(self.cfg["default_preset"])
            return
        for k, v in data.get("levels", {}).items():
            if k in self.engine.layers:
                self.engine.layers[k].level = float(v)
        self.engine.preset = data.get("preset")
        self.engine.master = float(data.get("master", 0.6))
        self.lamp.sunrise_minutes = float(data.get("sunrise_minutes", 30))
        self.lamp_follows_timer = bool(data.get("lamp_follows_timer", False))
        self.alarm_tone = data.get("alarm_tone", self.alarm_tone)
        self.alarm_minutes = float(data.get("alarm_minutes", self.alarm_minutes))
        self.engine.alarm_volume = float(data.get("alarm_volume", self.engine.alarm_volume))
        if data.get("playing") and self.cfg["resume_on_boot"]:
            self.engine.play()

    # ----------------------------------------------------------- run
    def start(self, *, audio=True, mqtt=True, knob=True):
        from .hardware import AudioOutput, Knob

        self.restore()
        if audio:
            a = self.cfg["audio"]
            self.audio = AudioOutput(self.engine.render, a["sample_rate"], a["block"], a["device"])
            self.audio.start()
        self.lamp.start()
        k = self.cfg["knob"]
        if knob and k["enabled"]:
            try:
                self.knob = Knob(k["pin_a"], k["pin_b"], k["pin_button"], k["step"],
                                 on_turn=self.volume.step, on_click=self.knob_click,
                                 on_hold=self.toggle_lamp)
            except Exception as exc:  # noqa: BLE001
                log.warning("knob disabled: %s", exc)
        if mqtt and self.cfg["mqtt"]["enabled"]:
            from .mqtt_ha import MqttBridge

            self.mqtt = MqttBridge(self)
            self.mqtt.start()

    def loop(self):
        """Publish state changes (debounced), save state, tick the timer display."""
        last_tick = 0.0
        while not self._stop.is_set():
            fired = self._dirty.wait(0.25)
            now = time.monotonic()
            if self.engine.timer_end is not None and now - last_tick > 30:
                fired = True
            if fired:
                self._dirty.clear()
                self._alarm_stopped()  # restores the amp volume once an alarm ran out
                last_tick = now
                if self.mqtt:
                    self.mqtt.publish()
                self.save()

    def stop(self):
        self._stop.set()
        if self.audio:
            self.audio.stop()
        self.lamp.stop()
        if self.mqtt:
            self.mqtt.stop()
        self.save()


__all__ = ["App", "TIMER_OPTIONS"]
