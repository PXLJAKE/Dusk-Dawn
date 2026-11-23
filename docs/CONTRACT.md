# Dusk & Dawn – Schnittstellen (verbindlich für alle Teile)

Integration domain: `dusk_dawn`. Display name "Dusk & Dawn". UI strings German + English.
Repo layout (HACS requires `custom_components/` at repo root):

```
custom_components/dusk_dawn/   HA integration (Python)          -> worker "integration"
custom_components/dusk_dawn/frontend/dusk-dawn-panel.js          -> worker "panel"
custom_components/dusk_dawn/engine/  pure-Python fallback engine -> worker "integration"
core/                          Rust crate + PyO3 module          -> worker "core"
hacs.json, .github/workflows/  release + wheels                  -> core (wheels), integration (hacs/hassfest)
```

## 1. Sound engine API (Python, same for Rust module and Python fallback)

Rust module import name: `dusk_dawn_core`. Fallback: `custom_components/dusk_dawn/engine` (a port of `hardware/device/sleepgen/dsp.py` + `engine.py`).
Loader in integration: `try: from dusk_dawn_core import Engine` / `except ImportError: from .engine import Engine`.
The Rust wheel is OPTIONAL (not in manifest requirements until published on PyPI).

```python
SOUNDS = ["rain","waves","wind","thunder","fan","white","pink","brown"]   # built-in; own sounds are extra ids "own_<hex>" mixed by the integration
ALARM_TONES = ["bells","classic","birds"]

class Engine:
    def __init__(self, rate: int = 44100, seed: int | None = None): ...
    rate: int                                   # read-only
    def sounds(self) -> list[str]: ...          # == SOUNDS
    def set_level(self, sound: str, level: float) -> None   # 0..1, smoothed ~0.5 s inside engine
    def levels(self) -> dict[str, float]
    def set_master(self, volume: float, ramp_s: float = 0.0) -> None  # 0..1, linear ramp
    master: float                               # current (ramping) value
    def start_alarm(self, tone: str, seconds: float, volume: float, ramp_s: float = 40.0) -> None
    def stop_alarm(self) -> None
    alarm_ringing: bool
    def render(self, frames: int) -> bytes      # mono, signed 16-bit little endian, len == 2*frames
```
- Sound character must match `hardware/device/sleepgen/dsp.py` (current reference, incl. calibration to equal loudness, soft limiter tanh).
- `render` must be cheap enough for real time: target < 5 % of one core for 4 active sounds at 44.1 kHz in Rust.
- Silence (all levels 0, no alarm) must cost ~nothing.

## 2. Integration model

One config entry = one "Schlafplatz" (spot). Entry data/options:
```
name: str
speakers: list[str]          # media_player entity_ids (stream targets)
lights: list[str]            # light entity_ids
presence: str | None         # binary_sensor entity_id
diy_device: str | None       # MQTT device id of a DIY Soundlampe (hardware/device/sleepgen), optional
```
Runtime state (stored with `homeassistant.helpers.storage.Store`, key `dusk_dawn.<entry_id>`):
```
playing: bool, preset: str|None, levels: {sound: float}, volume: float (0..1),
timer: {minutes: int|None, ends_at: iso|None},
light: {on: bool, brightness: int 0..255, kelvin: int},
alarms: [ {id, enabled, time "HH:MM", days [0..6 Mon=0], tone, duration_min, volume, sunrise: bool, sunrise_min} ],
auto: {presence_start: bool, presence_from "HH:MM", presence_to "HH:MM", presence_stop_min: int,
       presence_mode: "presence"|"window", presence_min: int (minutes somebody must be there before sounds start),
       pause_on_music: bool, night_light_with_sound: bool},
presets: [ {id, name, icon, levels} ]    # built-ins + user presets (built-ins: copy from hardware/device/sleepgen/config.py)
alarm_ringing: bool, next_alarm: iso|None
```

Entities per spot (has_entity_name, device = the spot):
- switch `sound` (play/stop), select `preset`, number `volume`, select `timer` (Aus/15/30/45/60/90 min),
- number per sound `level_<sound>` (entity_category config, disabled by default except the 4 most common),
- switch `alarm_<n>` for each alarm? -> keep simple: switch `alarms_enabled`, time `next_alarm_time` (first alarm), sensor `next_alarm` (timestamp),
- button `good_night`, button `stop_alarm`, binary_sensor `alarm_ringing`.

Services (domain `dusk_dawn`, target = config entry / device): `play` {preset?, volume?, timer?}, `stop`, `good_night`, `ring` {tone?, duration?}, `stop_alarm`.

## 3. Audio streaming

- HTTP view `GET /api/dusk_dawn/stream/{entry_id}.mp3?token=<t>` (requires_auth=False, token = secrets.token_urlsafe, rotates on each play).
- One engine + one ffmpeg encoder per spot (binary from HA ffmpeg integration `get_ffmpeg_manager(hass).binary`), PCM s16le mono 44100 -> MP3 128k CBR, fan-out to all connected HTTP clients.
- Engine renders in an executor thread in 50 ms blocks, keeps ~real time (no unbounded buffering).
- Start: `media_player.play_media` with `media_content_type: music`, `media_content_id: <get_url(hass, prefer_external=False)>/api/...`, extra `{"title": "Dusk & Dawn – <preset>"}`.
- DIY lamp (`diy_device` set): do NOT stream; send MQTT commands to the device's existing topics (see hardware/device/sleepgen/mqtt_ha.py) instead.

## 4. Websocket API (panel <-> integration)

All commands require admin=False (normal users may control). Messages:
- `dusk_dawn/spots` -> `{spots: [{entry_id, name, speakers, lights, presence, diy_device, state: <runtime state>}]}`
- `dusk_dawn/subscribe` -> subscription; sends `{entry_id, state}` on every change (debounced 100 ms).
- `dusk_dawn/command` {entry_id, action, ...}; actions:
  `play` {preset?}, `stop`, `toggle`, `set_level` {sound, level}, `set_volume` {volume},
  `apply_preset` {preset_id}, `save_preset` {name, icon}, `delete_preset` {preset_id},
  `set_timer` {minutes|null}, `good_night`,
  `light` {on?, brightness?, kelvin?, effect?: "sunrise"|"candle"|"fade"},
  `set_alarm` {alarm}, `delete_alarm` {alarm_id}, `ring` {tone?}, `stop_alarm`, `preview_tone` {tone},
  `set_auto` {auto}
  -> result `{state}`
- `dusk_dawn/config` {entry_id, speakers?, lights?, presence?, name?} (admin only) -> updates entry options.
- `dusk_dawn/entities` -> lists media_player / light / binary_sensor(occupancy, motion, presence) entities for the settings pickers: `[{entity_id, name, domain, device_class}]`.

## 5. Panel

Registered by the integration via `panel_custom.async_register_panel(hass, webcomponent_name="dusk-dawn-panel", frontend_url_path="dusk-dawn", sidebar_title="Dusk & Dawn", sidebar_icon="mdi:weather-night", module_url="/dusk_dawn_static/dusk-dawn-panel.js?v=<version>", embed_iframe=False, require_admin=False)`; static path via `hass.http.async_register_static_paths([StaticPathConfig("/dusk_dawn_static", <frontend dir>, True)])`.
Panel is ONE self-contained ES module (no build step, no CDN imports), plain `HTMLElement` + shadow DOM. HA sets properties `hass`, `narrow`, `panel`, `route` on it. Use `this.hass.connection.subscribeMessage` / `this.hass.callWS`.
Look: like docs/demo/index.html (night blue, brass accents) but ordered by task (see plan): spot switcher; "Jetzt" (big play button, volume, timer chips, light, Gute-Nacht button); "Klänge" (preset tiles + mixer grouped Wasser/Wetter/Natur/Rauschen); "Wecker" (list, weekday chips, tone preview, sunrise); "Automatik" (toggles); settings gear (pickers via `dusk_dawn/entities`, admin only). Language from `hass.language` (de/en). Responsive (`narrow`), light text contrast AA.
