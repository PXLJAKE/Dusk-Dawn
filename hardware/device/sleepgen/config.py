"""Configuration loading with sensible defaults."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

DEFAULTS: dict = {
    "device_id": "sleepgen",
    "name": "Soundlampe",
    "audio": {
        "sample_rate": 48000,
        "block": 2048,
        "device": None,  # None = system default (ALSA "default", shared via dmix)
        "fade_in_s": 8,
        "fade_out_min": 10,
    },
    "sounds": ["rain", "waves", "thunder", "wind", "fan", "white", "pink", "brown"],
    "presets": {
        "Regen": {"rain": 0.8, "brown": 0.3},
        "Gewitternacht": {"rain": 0.8, "thunder": 0.75, "wind": 0.35},
        "Meer": {"waves": 0.85, "wind": 0.25, "brown": 0.2},
        "Ventilator": {"fan": 0.8},
        "Brown Noise": {"brown": 0.8},
        "Pink Noise": {"pink": 0.7},
        "White Noise": {"white": 0.6},
    },
    "default_preset": "Regen",
    "resume_on_boot": True,
    "mqtt": {
        "enabled": True,
        "host": "homeassistant.local",
        "port": 1883,
        "username": None,
        "password": None,
        "discovery_prefix": "homeassistant",
        "base_topic": "sleepgen",
    },
    "hardware_volume": {
        "enabled": True,
        "card": 0,
        "control": "Digital",  # DigiAMP+ / TAS5756 volume control
    },
    "knob": {
        "enabled": True,
        "pin_a": 5,
        "pin_b": 6,
        "pin_button": 13,
        "step": 0.03,
    },
    "led": {
        "driver": "spi",  # "spi" or "none"
        "count": 30,
        "rgbw": True,
        "max_brightness": 0.7,  # limits current draw and heat inside the shade
    },
    "alarm": {
        "tone": "Glocken",        # Glocken / Klassisch / Vogelchor
        "minutes": 10,            # rings at most this long, a knob press stops it earlier
        "volume": 0.7,
        "min_device_volume": 0.5,  # amp volume is raised to at least this while ringing
        "grace_min": 20,          # after a power cut the alarm still rings if the lamp is back within this time
    },
    "alarms_file": "/var/lib/sleepgen/alarms.json",
    "state_file": "/var/lib/sleepgen/state.json",
}


def _merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "presets":
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load(path: str | Path | None) -> dict:
    if path is None or not Path(path).exists():
        return copy.deepcopy(DEFAULTS)
    with open(path, encoding="utf-8") as f:
        return _merge(DEFAULTS, yaml.safe_load(f) or {})
