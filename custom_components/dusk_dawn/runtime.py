"""Per-spot runtime: state, persistence and all actions.

Every way of controlling a spot (entities, services, websocket, scheduler)
ends up in one of the ``async_*`` action methods here, so behaviour is the same
no matter where a command comes from.
"""

from __future__ import annotations

import copy
import logging
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_NAME
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_call_later, async_track_point_in_utc_time
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    ALARM_TONES,
    BUILTIN_PRESET_IDS,
    CONF_DIY_DEVICE,
    CONF_LIGHTS,
    CONF_PRESENCE,
    CONF_SPEAKERS,
    DEFAULT_PRESET,
    FADE_IN_S,
    FADE_OUT_STOP_S,
    NAME,
    NIGHT_LIGHT_BRIGHTNESS,
    NIGHT_LIGHT_KELVIN,
    SIGNAL_STATE,
    SOUNDS,
    STORAGE_KEY,
    STORAGE_VERSION,
    TIMER_FADE_MAX_S,
)
from .diy import DiyLamp
from .lights import LightController
from .native import engine_kind
from .scheduler import Scheduler
from .lights import hex_to_rgb
from .state import (
    alarm_taper,
    find_preset,
    master_taper,
    merge_stored,
    normalize_alarm,
    normalize_auto,
    normalize_scene,
    sort_presets,
)
from .samples import SampleEngine, is_own
from .stream import SpotStream
from .uploads import get_library

_LOGGER = logging.getLogger(__name__)

PREVIEW_S = 6.0
STREAM_MARKER = "/api/dusk_dawn/stream/"


class SpotError(HomeAssistantError):
    """A command could not be carried out (bad preset id, ...)."""


def spot_config(entry: ConfigEntry) -> dict[str, Any]:
    """Effective spot configuration: options override the initial data."""
    cfg = {**entry.data, **entry.options}
    return {
        CONF_NAME: cfg.get(CONF_NAME) or entry.title,
        CONF_SPEAKERS: list(cfg.get(CONF_SPEAKERS) or []),
        CONF_LIGHTS: list(cfg.get(CONF_LIGHTS) or []),
        CONF_PRESENCE: cfg.get(CONF_PRESENCE) or None,
        CONF_DIY_DEVICE: cfg.get(CONF_DIY_DEVICE) or None,
    }


class SpotRuntime:
    """Everything that belongs to one spot (one config entry)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, engine: Any | None, ffmpeg_binary: str) -> None:
        self.hass = hass
        self.entry = entry
        self.config = spot_config(entry)
        self.store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY.format(entry_id=entry.entry_id))
        self.state: dict[str, Any] = merge_stored(None)
        self.engine = engine
        self.stream: SpotStream | None = (
            SpotStream(hass, entry.entry_id, engine, ffmpeg_binary) if engine is not None else None
        )
        self.diy: DiyLamp | None = (
            DiyLamp(hass, self.config[CONF_DIY_DEVICE], self._diy_state, self._diy_alarms) if self.config[CONF_DIY_DEVICE] else None
        )
        self.lights_ctl = LightController(hass, self)
        self.scheduler = Scheduler(hass, self)
        self._output_active = False
        self._previewing = False
        self._unsubs: dict[str, CALLBACK_TYPE] = {}
        self._listeners: list[Callable[[], None]] = []

    # ------------------------------------------------------------ properties
    @property
    def entry_id(self) -> str:
        return self.entry.entry_id

    @property
    def name(self) -> str:
        return self.config[CONF_NAME]

    @property
    def speakers(self) -> list[str]:
        return self.config[CONF_SPEAKERS]

    @property
    def lights(self) -> list[str]:
        return self.config[CONF_LIGHTS]

    @property
    def presence(self) -> str | None:
        return self.config[CONF_PRESENCE]

    @property
    def presets(self) -> list[dict[str, Any]]:
        return self.state["presets"]

    def snapshot(self) -> dict[str, Any]:
        """A copy of the state for the websocket API."""
        return copy.deepcopy(self.state)

    def spot_info(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "name": self.name,
            "speakers": self.speakers,
            "lights": self.lights,
            "presence": self.presence,
            "diy_device": self.config[CONF_DIY_DEVICE],
            "engine": engine_kind(self.engine),
            "state": self.snapshot(),
        }

    def preset_name(self) -> str | None:
        preset = find_preset(self.presets, self.state["preset"]) if self.state["preset"] else None
        return preset["name"] if preset else None

    # ------------------------------------------------------------ lifecycle
    async def async_setup(self) -> None:
        self.state = merge_stored(await self.store.async_load())
        if self.engine is not None:
            self.engine.set_master(0.0)
            for sound, level in self.state["levels"].items():
                self.engine.set_level(sound, level)
        if self.diy:
            await self.diy.async_start()
            await self._push_alarms()
        self.scheduler.async_start()

    async def async_shutdown(self) -> None:
        for unsub in self._unsubs.values():
            unsub()
        self._unsubs.clear()
        self.scheduler.async_stop()
        self.lights_ctl.cancel_effect()
        if self.diy:
            self.diy.async_stop()
        if self.stream:
            await self.stream.async_shutdown()
        await self.store.async_save(self._stored())

    def _stored(self) -> dict[str, Any]:
        return {k: v for k, v in self.state.items() if k not in ("alarm_ringing", "next_alarm", "playing")}

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def async_changed(self) -> None:
        """Persist (debounced) and notify entities and websocket subscribers."""
        self.store.async_delay_save(self._stored, 2.0)
        for listener in list(self._listeners):
            listener()
        async_dispatcher_send(self.hass, SIGNAL_STATE, self.entry_id)

    def _timer(self, key: str, handle: CALLBACK_TYPE | None) -> None:
        if (old := self._unsubs.pop(key, None)) is not None:
            old()
        if handle is not None:
            self._unsubs[key] = handle

    # ------------------------------------------------------------ output (stream / speakers)
    def _stream_url(self) -> str | None:
        assert self.stream is not None
        try:
            base = get_url(self.hass, prefer_external=False)
        except NoURLAvailableError:
            _LOGGER.error("No internal URL available; set one under Settings > System > Network")
            return None
        return f"{base}{self.stream.path}"

    async def _ensure_output(self) -> None:
        """Make the speakers play our stream (new token each time it starts)."""
        if self.stream is None or self._output_active:
            return
        self.stream.rotate_token()
        self._output_active = True
        url = self._stream_url()
        if not url or not self.speakers:
            return
        title = f"{NAME} – {self.preset_name() or self.name}"
        await self.hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: self.speakers,
                "media_content_type": "music",
                "media_content_id": url,
                "extra": {"title": title},
            },
            blocking=False,
        )

    async def _release_output(self) -> None:
        """Stop the speakers again once nothing needs the stream."""
        if self.stream is None or not self._output_active:
            return
        if self.state["playing"] or self.state["alarm_ringing"] or self._previewing:
            return
        self._output_active = False
        ours = []
        for entity_id in self.speakers:
            st = self.hass.states.get(entity_id)
            content = st.attributes.get("media_content_id") if st else None
            # don't stop a speaker that is playing something else by now
            if st is not None and (content is None or STREAM_MARKER in str(content)):
                ours.append(entity_id)
        if ours:
            await self.hass.services.async_call(
                "media_player", "media_stop", {ATTR_ENTITY_ID: ours}, blocking=False
            )
        self.stream.close_clients()

    def is_our_stream(self, entity_id: str) -> bool:
        st = self.hass.states.get(entity_id)
        return bool(st and STREAM_MARKER in str(st.attributes.get("media_content_id", "")))

    # ------------------------------------------------------------ sound
    def _apply_levels(self, levels: dict[str, float]) -> None:
        known = [*SOUNDS, *(k for k in levels if is_own(k))]
        for sound in {*known, *(k for k in self.state["levels"] if is_own(k))}:
            level = min(max(float(levels.get(sound, 0.0)), 0.0), 1.0)
            self.state["levels"][sound] = level
            if self.engine is not None:
                self.engine.set_level(sound, level)

    async def async_play(
        self, preset: str | None = None, volume: float | None = None, timer: int | None = -1
    ) -> None:
        """Start the sounds. ``timer``: -1 keeps the setting, None/0 = off."""
        if preset:
            await self.async_apply_preset(preset, notify=False)
        elif not any(self.state["levels"].values()):
            await self.async_apply_preset(self.state["preset"] or DEFAULT_PRESET, notify=False)
        if volume is not None:
            self.state["volume"] = min(max(float(volume), 0.0), 1.0)
        if timer != -1:
            self.state["timer"]["minutes"] = timer or None
        was_playing = self.state["playing"]
        self.state["playing"] = True
        self._timer("stop", None)
        if self.diy:
            await self.diy.play(self.state["levels"], self.state["volume"], self.state["timer"]["minutes"])
        elif self.engine is not None:
            if not was_playing:
                self.engine.set_master(0.0)
                self._output_active = False  # new play session: new token, play_media again
            self.engine.set_master(master_taper(self.state["volume"]), FADE_IN_S if not was_playing else 0.5)
            await self._ensure_output()
        self._start_timer()
        self.async_changed()

    async def async_stop(self) -> None:
        self.state["playing"] = False
        self.state["timer"]["ends_at"] = None
        self._timer("timer_fade", None)
        self._timer("timer_end", None)
        if self.diy:
            await self.diy.stop()
        elif self.engine is not None:
            self.engine.set_master(0.0, FADE_OUT_STOP_S)

            async def _release(_now: datetime) -> None:
                self._unsubs.pop("stop", None)
                await self._release_output()

            self._timer("stop", async_call_later(self.hass, FADE_OUT_STOP_S + 0.5, _release))
        self.async_changed()

    async def async_toggle(self) -> None:
        if self.state["playing"]:
            await self.async_stop()
        else:
            await self.async_play()

    async def async_set_level(self, sound: str, level: float) -> None:
        if sound not in SOUNDS and not (is_own(sound) and get_library(self.hass).has_sound(sound)):
            raise SpotError(f"Unknown sound {sound!r}")
        level = min(max(float(level), 0.0), 1.0)
        self.state["levels"][sound] = level
        self.state["preset"] = None
        if self.engine is not None:
            self.engine.set_level(sound, level)
        if self.diy:
            await self.diy.set_level(sound, level)
        self.async_changed()

    @callback
    def async_library_changed(self) -> None:
        """A sound was added, renamed or deleted: forget the levels of sounds that are gone."""
        library = get_library(self.hass)
        for sound in [k for k in self.state["levels"] if is_own(k) and not library.has_sound(k)]:
            del self.state["levels"][sound]
        self.async_changed()

    async def async_set_volume(self, volume: float) -> None:
        self.state["volume"] = min(max(float(volume), 0.0), 1.0)
        if self.engine is not None and self.state["playing"]:
            self.engine.set_master(master_taper(self.state["volume"]), 0.3)
        if self.diy:
            await self.diy.set_volume(self.state["volume"])
        self.async_changed()

    async def async_apply_preset(self, preset_id: str, notify: bool = True) -> None:
        preset = find_preset(self.presets, preset_id)
        if preset is None:
            raise SpotError(f"Unknown preset {preset_id!r}")
        self._apply_levels(preset["levels"])
        self.state["preset"] = preset["id"]
        if self.diy:
            await self.diy.set_levels(self.state["levels"])
        if notify:
            self.async_changed()

    async def async_save_preset(self, name: str, icon: str | None = None, **extras: Any) -> str:
        """Save the current mix (plus optional volume/timer/light) as a new own scene, at the top."""
        data = {"name": name, "icon": icon, "levels": self.state["levels"],
                **{k: v for k, v in extras.items() if k in ("volume", "timer", "light")}}
        try:
            scene = normalize_scene(data)
        except (ValueError, TypeError) as err:
            raise SpotError(str(err)) from err
        preset_id = f"user_{secrets.token_hex(4)}"
        scene = {"id": preset_id, "builtin": False, "icon": "mdi:playlist-music", **scene}
        self.state["presets"] = sort_presets([scene, *self.presets])
        self.state["preset"] = preset_id
        self.async_changed()
        return preset_id

    async def async_update_preset(self, preset_id: str, data: dict[str, Any], take_mix: bool = False) -> None:
        """Edit a scene: name, icon, volume, timer, light; ``take_mix`` stores the current mix as its sounds."""
        preset = find_preset(self.presets, preset_id)
        if preset is None:
            raise SpotError(f"Unknown preset {preset_id!r}")
        data = {k: v for k, v in data.items() if k in ("name", "icon", "levels", "volume", "timer", "light")}
        if take_mix:
            data["levels"] = self.state["levels"]
        try:
            new = normalize_scene(data, preset)
        except (ValueError, TypeError) as err:
            raise SpotError(str(err)) from err
        if preset.get("builtin"):
            new["edited"] = True
        preset.clear()
        preset.update(new)
        self.async_changed()

    async def async_reorder_presets(self, order: list[str]) -> None:
        """Drag and drop: new order of the scene ids (own scenes always stay above the suggestions)."""
        pos = {pid: i for i, pid in enumerate(order)}
        ranked = sorted(enumerate(self.presets), key=lambda ip: (pos.get(ip[1]["id"], len(pos) + ip[0])))
        self.state["presets"] = sort_presets([p for _, p in ranked])
        self.async_changed()

    async def async_restore_presets(self) -> None:
        """Bring back the removed and edited built-in suggestions in their original form."""
        own = [p for p in self.presets if not p.get("builtin")]
        self.state["hidden_presets"] = []
        self.state["presets"] = merge_stored({"presets": own})["presets"]
        self.async_changed()

    async def async_delete_preset(self, preset_id: str) -> None:
        preset = find_preset(self.presets, preset_id)
        if preset is None or preset["id"] != preset_id:
            raise SpotError(f"Unknown preset {preset_id!r}")
        if preset.get("builtin"):  # a suggestion: hide it (restore_presets brings it back)
            self.state.setdefault("hidden_presets", []).append(preset_id)
        self.state["presets"] = [p for p in self.presets if p["id"] != preset_id]
        if self.state["preset"] == preset_id:
            self.state["preset"] = None
        self.async_changed()

    async def async_activate_scene(self, preset_id: str) -> None:
        """Start a scene: its sounds, and, where the scene sets them, volume, sleep timer and light."""
        preset = find_preset(self.presets, preset_id)
        if preset is None:
            raise SpotError(f"Unknown preset {preset_id!r}")
        timer = preset.get("timer", "keep")
        await self.async_play(preset=preset["id"], volume=preset.get("volume"),
                              timer=-1 if timer == "keep" else timer)
        await self._apply_scene_light(preset.get("light"))

    async def _apply_scene_light(self, light: dict[str, Any] | None) -> None:
        if not light or not (self.lights or self.diy is not None):
            return
        mode = light["mode"]

        def bri(pct: int) -> int:
            return max(0, min(255, round(pct * 255 / 100)))

        if mode == "off":
            await self.async_light(on=False)
        elif mode == "white":
            await self.async_light(on=True, brightness=bri(light["brightness"]), kelvin=light["kelvin"])
        elif mode == "color":
            await self.lights_ctl.async_set_color(hex_to_rgb(light["color"]), bri(light["brightness"]))
            self.async_changed()
        elif mode == "candle":
            await self.async_light(effect="candle", brightness=bri(light["brightness"]))
        elif mode == "gradient":
            self.lights_ctl.start_gradient(hex_to_rgb(light["color"]), bri(light["brightness"]),
                                           hex_to_rgb(light["to_color"]), bri(light["to_brightness"]),
                                           float(light["minutes"]))
            self.async_changed()
        elif mode == "fade":  # night light that dims out with the sleep timer (only if a light is wanted)
            if self.lights_ctl.any_on() or self.state["light"]["on"] or self.state["auto"]["night_light_with_sound"]:
                await self.async_light(on=True, brightness=bri(light["brightness"]), kelvin=light["kelvin"])
                if self.state["timer"]["minutes"]:
                    await self.async_light(effect="fade", minutes=self.state["timer"]["minutes"])

    # ------------------------------------------------------------ sleep timer
    async def async_set_timer(self, minutes: int | None) -> None:
        self.state["timer"]["minutes"] = int(minutes) if minutes else None
        if self.state["playing"]:
            if self.engine is not None:  # undo a fade that may have started
                self.engine.set_master(master_taper(self.state["volume"]), 2.0)
            if self.diy:
                await self.diy.set_timer(self.state["timer"]["minutes"])
            self._start_timer()
        self.async_changed()

    def _start_timer(self) -> None:
        """(Re)arm the running sleep timer from ``timer.minutes``."""
        self._timer("timer_fade", None)
        self._timer("timer_end", None)
        minutes = self.state["timer"]["minutes"]
        if not minutes or not self.state["playing"]:
            self.state["timer"]["ends_at"] = None
            return
        now = dt_util.utcnow()
        ends = now + timedelta(minutes=minutes)
        self.state["timer"]["ends_at"] = ends.isoformat()
        fade_s = min(TIMER_FADE_MAX_S, minutes * 60 / 3)

        @callback
        def _fade(_now: datetime) -> None:
            self._unsubs.pop("timer_fade", None)
            if self.engine is not None and self.state["playing"]:
                self.engine.set_master(0.0, fade_s)

        async def _end(_now: datetime) -> None:
            self._unsubs.pop("timer_end", None)
            self.state["timer"]["ends_at"] = None
            await self.async_stop()

        if self.engine is not None:
            self._timer("timer_fade", async_track_point_in_utc_time(self.hass, _fade, ends - timedelta(seconds=fade_s)))
        self._timer("timer_end", async_track_point_in_utc_time(self.hass, _end, ends))

    async def async_good_night(self) -> None:
        """Start the evening scene (Automatik → start scene, by default the editable „Gute Nacht“)."""
        scene = find_preset(self.presets, self.state["auto"].get("start_scene") or "") or find_preset(
            self.presets, "gute_nacht")
        if scene is not None:
            await self.async_activate_scene(scene["id"])
            return
        # no scene left (all removed): last sound with a warm, dimmed light
        await self.async_play(preset=self.state["preset"] or None)
        await self._apply_scene_light({"mode": "fade", "brightness": round(NIGHT_LIGHT_BRIGHTNESS * 100 / 255),
                                       "kelvin": NIGHT_LIGHT_KELVIN})

    # ------------------------------------------------------------ light
    async def async_light(
        self,
        on: bool | None = None,
        brightness: int | None = None,
        kelvin: int | None = None,
        effect: str | None = None,
        minutes: float | None = None,
    ) -> None:
        light = self.state["light"]
        if effect:
            if effect not in ("sunrise", "candle", "fade"):
                raise SpotError(f"Unknown light effect {effect!r}")
            if effect == "fade" and minutes is None:
                minutes = self.state["timer"]["minutes"] or 30
            if effect == "sunrise" and minutes is None:
                minutes = 30
            if self.diy:
                light.update(on=effect != "fade" or light["on"], effect=effect)
                await self.diy.effect(effect, minutes)
            elif effect == "sunrise":
                self.lights_ctl.start_sunrise(float(minutes or 30))
            elif effect == "fade":
                self.lights_ctl.start_fade(float(minutes or 30))
            else:
                if brightness is not None:
                    light["brightness"] = int(brightness)
                self.lights_ctl.start_candle()
        elif self.diy:
            if brightness is not None:
                light["brightness"] = int(min(max(brightness, 1), 255))
            if kelvin is not None:
                light["kelvin"] = int(kelvin)
                light["rgb"] = None
            if on is None:
                on = True if (brightness is not None or kelvin is not None) else light["on"]
            self.lights_ctl.cancel_effect()
            light.update(on=on, effect=None)
            await self.diy.light(on, light["brightness"], light["kelvin"], light.get("rgb"))
        else:
            await self.lights_ctl.async_set(on, brightness, kelvin)
        self.async_changed()

    # ------------------------------------------------------------ alarms
    async def async_set_alarm(self, alarm: dict[str, Any]) -> dict[str, Any]:
        alarms = self.state["alarms"]
        existing = next((a for a in alarms if alarm.get("id") and a["id"] == alarm["id"]), None)
        try:
            new = normalize_alarm(alarm, existing)
        except (ValueError, TypeError, KeyError) as err:
            raise SpotError(str(err)) from err
        if existing:
            alarms[alarms.index(existing)] = new
        else:
            alarms.append(new)
        self.scheduler.async_reschedule()
        await self._push_alarms()
        self.async_changed()
        return new

    async def async_delete_alarm(self, alarm_id: str) -> None:
        self.state["alarms"] = [a for a in self.state["alarms"] if a["id"] != alarm_id]
        self.scheduler.async_reschedule()
        await self._push_alarms()
        self.async_changed()

    async def async_set_alarms_enabled(self, enabled: bool) -> None:
        self.state["alarms_enabled"] = bool(enabled)
        self.scheduler.async_reschedule()
        await self._push_alarms()
        self.async_changed()

    async def _push_alarms(self) -> None:
        """The DIY lamp keeps and rings the alarms itself, so it also works while Home Assistant is down."""
        if self.diy:
            await self.diy.set_alarms(self.state["alarms"], self.state["alarms_enabled"])

    def _default_alarm(self) -> dict[str, Any]:
        return self.state["alarms"][0] if self.state["alarms"] else {"tone": "bells", "duration_min": 10,
                                                                       "volume": 0.6}

    async def async_ring(
        self, tone: str | None = None, duration_min: float | None = None, volume: float | None = None
    ) -> None:
        """Ring now: the alarm tone on top of the sounds, getting louder."""
        default = self._default_alarm()
        tone = tone or default["tone"]
        if tone not in ALARM_TONES:
            raise SpotError(f"Unknown alarm tone {tone!r}")
        duration_min = float(duration_min or default["duration_min"])
        volume = float(default["volume"] if volume is None else volume)
        self.state["alarm_ringing"] = True
        if self.diy:
            await self.diy.ring(tone, duration_min, volume)
        elif self.engine is not None:
            self.engine.start_alarm(tone, duration_min * 60, alarm_taper(volume), 40.0)
            await self._ensure_output()

        async def _end(_now: datetime) -> None:
            self._unsubs.pop("alarm_end", None)
            if self.state["alarm_ringing"]:
                await self.async_stop_alarm()

        self._timer("alarm_end", async_call_later(self.hass, duration_min * 60, _end))
        self.async_changed()

    async def async_stop_alarm(self) -> None:
        self._timer("alarm_end", None)
        was = self.state["alarm_ringing"]
        self.state["alarm_ringing"] = False
        if self.diy:
            if was:
                await self.diy.stop_alarm()
        elif self.engine is not None:
            self.engine.stop_alarm()
            await self._release_output()
        self.async_changed()

    async def async_preview_tone(self, tone: str) -> None:
        if tone not in ALARM_TONES:
            raise SpotError(f"Unknown alarm tone {tone!r}")
        volume = self._default_alarm()["volume"]
        if self.diy:
            await self.diy.ring(tone, 1, volume)

            async def _diy_end(_now: datetime) -> None:
                self._unsubs.pop("preview", None)
                if not self.state["alarm_ringing"] and self.diy:
                    await self.diy.stop_alarm()

            self._timer("preview", async_call_later(self.hass, PREVIEW_S, _diy_end))
            return
        if self.engine is None:
            return
        self._previewing = True
        self.engine.start_alarm(tone, PREVIEW_S, alarm_taper(volume), 0.0)
        await self._ensure_output()

        async def _end(_now: datetime) -> None:
            self._unsubs.pop("preview", None)
            self._previewing = False
            await self._release_output()

        self._timer("preview", async_call_later(self.hass, PREVIEW_S + 1, _end))

    # ------------------------------------------------------------ automation
    async def async_set_auto(self, auto: dict[str, Any]) -> None:
        try:
            self.state["auto"] = normalize_auto(auto, self.state["auto"])
        except (ValueError, TypeError) as err:
            raise SpotError(str(err)) from err
        self.scheduler.async_auto_changed()
        self.async_changed()

    # ------------------------------------------------------------ DIY feedback
    @callback
    def _diy_alarms(self, data: dict[str, Any]) -> None:
        """One-off alarms switch themselves off on the lamp after ringing; mirror that."""
        off = {a.get("id") for a in data.get("alarms", []) if not a.get("enabled", True)}
        changed = False
        for alarm in self.state["alarms"]:
            if alarm["id"] in off and alarm["enabled"] and not alarm["days"]:
                alarm["enabled"] = False
                changed = True
        if changed:
            self.scheduler.async_reschedule()
            self.async_changed()

    @callback
    def _diy_state(self, data: dict[str, Any]) -> None:
        """Mirror what the DIY lamp reports (it ends timers/alarms by itself)."""
        changed = False
        if "playing" in data and bool(data["playing"]) != self.state["playing"]:
            self.state["playing"] = bool(data["playing"])
            changed = True
        if "alarm_ringing" in data and bool(data["alarm_ringing"]) != self.state["alarm_ringing"]:
            self.state["alarm_ringing"] = bool(data["alarm_ringing"])
            changed = True
        if changed:
            self.async_changed()

