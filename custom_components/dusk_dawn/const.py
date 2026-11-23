"""Constants for Dusk & Dawn."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "dusk_dawn"
NAME: Final = "Dusk & Dawn"

CONF_SPEAKERS: Final = "speakers"
CONF_LIGHTS: Final = "lights"
CONF_PRESENCE: Final = "presence"
CONF_DIY_DEVICE: Final = "diy_device"

STORAGE_VERSION: Final = 1
STORAGE_KEY: Final = "dusk_dawn.{entry_id}"  # contract: dusk_dawn.<entry_id>

# HTTP / panel
STREAM_URL: Final = "/api/dusk_dawn/stream/{entry_id}.mp3"
UPLOAD_URL: Final = "/api/dusk_dawn/upload/{sound}"
STATIC_URL: Final = "/dusk_dawn_static"
PANEL_URL_PATH: Final = "dusk-dawn"
PANEL_COMPONENT: Final = "dusk-dawn-panel"
PANEL_FILE: Final = "dusk-dawn-panel.js"
PANEL_ICON: Final = "mdi:weather-night"

# Dispatcher signal fired with the entry_id whenever a spot's state changes
SIGNAL_STATE: Final = "dusk_dawn_state"

SAMPLE_RATE: Final = 44100
BLOCK_S: Final = 0.05  # engine renders 50 ms blocks

# Order matters: this is the order of the mixer in the panel and of the entities
SOUNDS: Final = [
    "rain",
    "waves",
    "wind",
    "thunder",
    "fan",
    "white",
    "pink",
    "brown",
]
ALARM_TONES: Final = ["bells", "classic", "birds"]
# Level entities enabled by default (the rest is disabled to keep the device page tidy)
DEFAULT_ENABLED_LEVELS: Final = {"rain", "waves", "brown"}
# Synth sounds that were removed (the lamp still knows them; they are set to 0 there)
REMOVED_SOUNDS: Final = ["stream", "birds", "leaves", "fire"]

TIMER_OPTIONS: Final = [None, 15, 30, 45, 60, 90]  # minutes, None = off
FADE_IN_S: Final = 8.0
FADE_OUT_STOP_S: Final = 2.0
TIMER_FADE_MAX_S: Final = 600.0  # last 10 minutes of the sleep timer fade out

DEFAULT_VOLUME: Final = 0.5
NIGHT_LIGHT_BRIGHTNESS: Final = 60
NIGHT_LIGHT_KELVIN: Final = 2200

SOUND_ICONS: Final = {  # also in icons.json
    "rain": "mdi:weather-pouring",
    "waves": "mdi:waves",
    "wind": "mdi:weather-windy",
    "thunder": "mdi:weather-lightning",
    "fan": "mdi:fan",
    "white": "mdi:waveform",
    "pink": "mdi:waveform",
    "brown": "mdi:waveform",
}

# Built-in presets, copied from hardware/device/sleepgen/config.py
BUILTIN_PRESETS: Final = [
    {
        "id": "gute_nacht",
        "name": "Gute Nacht",
        "builtin": True,
        "icon": "mdi:weather-night",
        "levels": {"rain": 0.8, "brown": 0.3},
        # warm dimmed light that fades out with the sleep timer; the timer itself is left as it is
        "light": {"mode": "fade", "brightness": 24, "kelvin": 2200},
    },
    {
        "id": "regen",
        "name": "Regen",
        "builtin": True,
        "icon": "mdi:weather-pouring",
        "levels": {"rain": 0.8, "brown": 0.3},
    },
    {
        "id": "gewitternacht",
        "name": "Gewitternacht",
        "builtin": True,
        "icon": "mdi:weather-lightning-rainy",
        "levels": {"rain": 0.8, "thunder": 0.75, "wind": 0.35},
    },
    {
        "id": "meer",
        "name": "Meer",
        "builtin": True,
        "icon": "mdi:waves",
        "levels": {"waves": 0.85, "wind": 0.25, "brown": 0.2},
    },
    {"id": "ventilator", "name": "Ventilator", "builtin": True, "icon": "mdi:fan", "levels": {"fan": 0.8}},
    {"id": "brown_noise", "name": "Brown Noise", "builtin": True, "icon": "mdi:waveform", "levels": {"brown": 0.8}},
    {"id": "pink_noise", "name": "Pink Noise", "builtin": True, "icon": "mdi:waveform", "levels": {"pink": 0.7}},
    {"id": "white_noise", "name": "White Noise", "builtin": True, "icon": "mdi:waveform", "levels": {"white": 0.6}},
]
BUILTIN_PRESET_IDS: Final = {p["id"] for p in BUILTIN_PRESETS}
DEFAULT_PRESET: Final = "regen"

# DIY Soundlampe (hardware/device/sleepgen) – MQTT names it uses
DIY_BASE_TOPIC: Final = "sleepgen/{device}"
DIY_TONES: Final = {"bells": "Glocken", "classic": "Klassisch", "birds": "Vogelchor"}
DIY_EFFECTS: Final = {"sunrise": "Sonnenaufgang", "candle": "Kerze", "fade": "Einschlafen"}
DIY_TIMER_OPTIONS: Final = (15, 30, 45, 60, 90, 120)

ATTR_PRESET: Final = "preset"
ATTR_VOLUME: Final = "volume"
ATTR_TIMER: Final = "timer"
ATTR_TONE: Final = "tone"
ATTR_DURATION: Final = "duration"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"

SERVICE_PLAY: Final = "play"
SERVICE_STOP: Final = "stop"
SERVICE_GOOD_NIGHT: Final = "good_night"
SERVICE_RING: Final = "ring"
SERVICE_STOP_ALARM: Final = "stop_alarm"
