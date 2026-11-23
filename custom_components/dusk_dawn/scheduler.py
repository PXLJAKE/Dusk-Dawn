"""Alarms and automations of one spot.

* Alarms: ring at HH:MM on the chosen weekdays (Mon = 0); optionally start a
  sunrise ``sunrise_min`` minutes before. One timer is armed for the next
  event; after it fired the next one is computed. With a DIY lamp the lamp
  itself rings (it stores the list), so only ``next_alarm`` is computed here.
* Presence: start the good-night routine once somebody has been there for
  ``presence_min`` minutes in a row inside the time window (once per stay, a
  sensor dropout or a short flicker does not count); stop sounds and lights
  after presence has been gone for ``presence_stop_min`` minutes. In "window"
  mode no sensor is needed: sounds start at the window start and stop at its end.
* Pause on music: stop the sounds when another media player starts playing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON, STATE_PLAYING
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.util import dt as dt_util

from .state import in_window, next_ring

if TYPE_CHECKING:
    from .runtime import SpotRuntime

_LOGGER = logging.getLogger(__name__)


class Scheduler:
    def __init__(self, hass: HomeAssistant, runtime: SpotRuntime) -> None:
        self.hass = hass
        self.rt = runtime
        self._alarm_unsub: CALLBACK_TYPE | None = None
        self._presence_stop: CALLBACK_TYPE | None = None
        self._presence_start: CALLBACK_TYPE | None = None
        self._window_unsub: CALLBACK_TYPE | None = None
        self._presence_episode_done = False  # good night already started (or skipped) during this stay
        self._window_started = False
        self._unsubs: list[CALLBACK_TYPE] = []
        self._planned: list[tuple[str, dict[str, Any], datetime]] = []
        self._sunrise_started: set[tuple[str, str]] = set()  # (alarm id, ring time)

    # ------------------------------------------------------------ lifecycle
    @callback
    def async_start(self) -> None:
        self.async_reschedule()
        # somebody already there when Home Assistant (re)starts: that stay does not start anything
        self._presence_episode_done = self._presence_on()
        self._arm_window()
        if self.rt.presence:
            self._unsubs.append(
                async_track_state_change_event(self.hass, [self.rt.presence], self._presence_changed)
            )
        self._unsubs.append(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._media_changed, event_filter=self._media_filter)
        )

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        self._cancel_alarm_timer()
        self._cancel_presence_stop()
        self._cancel_presence_timer()
        self._cancel_window()

    def _cancel_alarm_timer(self) -> None:
        if self._alarm_unsub:
            self._alarm_unsub()
            self._alarm_unsub = None

    # ------------------------------------------------------------ alarms
    def _enabled_alarms(self) -> list[dict[str, Any]]:
        if not self.rt.state["alarms_enabled"]:
            return []
        return [a for a in self.rt.state["alarms"] if a["enabled"]]

    @callback
    def async_reschedule(self, after: datetime | None = None) -> None:
        """Arm the timer for the next sunrise start or ring."""
        self._cancel_alarm_timer()
        now = dt_util.now()
        ref = dt_util.as_local(after) if after else now
        events: list[tuple[datetime, str, dict[str, Any], datetime]] = []
        next_ring_at: datetime | None = None
        for alarm in self._enabled_alarms():
            ring = next_ring(alarm, ref)
            if ring is None:
                continue
            if next_ring_at is None or ring < next_ring_at:
                next_ring_at = ring
            if self.rt.diy:
                continue  # the lamp rings and runs the sunrise itself (works without Home Assistant)
            events.append((ring, "ring", alarm, ring))
            if alarm["sunrise"]:
                start = ring - timedelta(minutes=alarm["sunrise_min"])
                key = (alarm["id"], ring.isoformat())
                if start > ref:
                    events.append((start, "sunrise", alarm, ring))
                elif key not in self._sunrise_started and (ring - now) >= timedelta(minutes=1):
                    # alarm set (or HA started) inside the sunrise window: catch up
                    self._sunrise_started.add(key)
                    self.rt.entry.async_create_task(
                        self.hass, self._start_sunrise(alarm, (ring - now).total_seconds() / 60)
                    )

        nxt = next_ring_at.isoformat() if next_ring_at else None
        if self.rt.state["next_alarm"] != nxt:
            self.rt.state["next_alarm"] = nxt
            self.rt.async_changed()  # does not reschedule, so no recursion

        if not events:
            self._planned = []
            return
        first = min(e[0] for e in events)
        self._planned = [(kind, alarm, ring) for when, kind, alarm, ring in events if when == first]
        self._alarm_unsub = async_track_point_in_utc_time(self.hass, self._fire, dt_util.as_utc(first))

    async def _fire(self, now: datetime) -> None:
        self._alarm_unsub = None
        planned, self._planned = self._planned, []
        fired_at: datetime | None = None
        for kind, alarm, ring in planned:
            if kind == "sunrise":
                fired_at = ring - timedelta(minutes=alarm["sunrise_min"])
                self._sunrise_started.add((alarm["id"], ring.isoformat()))
                await self._start_sunrise(alarm, alarm["sunrise_min"])
            else:
                fired_at = ring
                _LOGGER.debug("Alarm %s rings (%s)", alarm["id"], self.rt.name)
                await self.rt.async_ring(alarm["tone"], alarm["duration_min"], alarm["volume"])
                if not alarm["days"]:  # one-off alarm: rings once, then disables itself
                    for stored in self.rt.state["alarms"]:
                        if stored["id"] == alarm["id"]:
                            stored["enabled"] = False
                    self.rt.async_changed()
        # keep the set from growing forever
        cutoff = (dt_util.now() - timedelta(days=1)).isoformat()
        self._sunrise_started = {k for k in self._sunrise_started if k[1] >= cutoff}
        self.async_reschedule(after=fired_at)

    async def _start_sunrise(self, alarm: dict[str, Any], minutes: float) -> None:
        _LOGGER.debug("Sunrise for alarm %s (%.0f min)", alarm["id"], minutes)
        if self.rt.lights or self.rt.diy:
            await self.rt.async_light(effect="sunrise", minutes=minutes)

    # ------------------------------------------------------------ presence / time window
    def _presence_on(self) -> bool:
        state = self.hass.states.get(self.rt.presence) if self.rt.presence else None
        return state is not None and state.state == STATE_ON

    def _cancel_presence_timer(self) -> None:
        if self._presence_start:
            self._presence_start()
            self._presence_start = None

    def _cancel_presence_stop(self) -> None:
        if self._presence_stop:
            self._presence_stop()
            self._presence_stop = None

    @callback
    def async_auto_changed(self) -> None:
        """The automation settings changed: re-arm the window edges and drop a pending start."""
        self._cancel_presence_timer()
        self._arm_window()

    def _presence_ready(self) -> bool:
        """Presence mode on, sensor chosen, somebody there for ``presence_min`` minutes in a row."""
        auto = self.rt.state["auto"]
        if not (auto["presence_start"] and auto["presence_mode"] == "presence" and self._presence_on()):
            return False
        state = self.hass.states.get(self.rt.presence)
        return state is not None and dt_util.utcnow() - state.last_changed >= timedelta(minutes=auto["presence_min"])

    async def _maybe_start_by_presence(self) -> None:
        """Start the good-night routine once per stay: only inside the window and after ``presence_min``."""
        auto = self.rt.state["auto"]
        if self._presence_episode_done or not self._presence_ready():
            return
        if not in_window(dt_util.now().time(), auto["presence_from"], auto["presence_to"]):
            return  # the window start checks again
        self._presence_episode_done = True
        if not self.rt.state["playing"] and not self.rt.state["alarm_ringing"]:
            _LOGGER.debug("Presence for %s min, starting good night (%s)", auto["presence_min"], self.rt.name)
            await self.rt.async_good_night()

    async def _presence_changed(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None:
            return
        auto = self.rt.state["auto"]
        if new.state == STATE_ON:
            self._cancel_presence_stop()
            if old is not None and old.state == STATE_ON:
                return  # only attributes changed
            self._cancel_presence_timer()
            if auto["presence_start"] and auto["presence_mode"] == "presence":
                minutes = auto["presence_min"]
                if minutes > 0:
                    self._presence_start = async_call_later(self.hass, minutes * 60 + 1, self._presence_confirmed)
                else:
                    await self._maybe_start_by_presence()
        else:
            self._cancel_presence_timer()  # a short flicker or a sensor dropout does not count
            if new.state == STATE_OFF:
                self._presence_episode_done = False
                minutes = auto["presence_stop_min"]
                if (
                    old is not None
                    and old.state == STATE_ON
                    and auto["presence_start"]
                    and auto["presence_mode"] == "presence"
                    and minutes > 0
                    and self.rt.state["playing"]
                ):
                    self._presence_stop = async_call_later(self.hass, minutes * 60, self._presence_gone)

    async def _presence_confirmed(self, _now: datetime) -> None:
        self._presence_start = None
        await self._maybe_start_by_presence()

    async def _presence_gone(self, _now: datetime) -> None:
        self._presence_stop = None
        if self.rt.state["playing"]:
            _LOGGER.debug("Nobody there any more, stopping (%s)", self.rt.name)
            await self.rt.async_stop()
            if self.rt.lights or self.rt.diy:
                await self.rt.async_light(on=False)

    # window edges: presence mode re-checks at the start, "window" mode starts and stops by time alone
    def _cancel_window(self) -> None:
        if self._window_unsub:
            self._window_unsub()
            self._window_unsub = None

    @callback
    def _arm_window(self) -> None:
        self._cancel_window()
        auto = self.rt.state["auto"]
        if not auto["presence_start"]:
            return
        now = dt_util.now()
        edges = []
        for key in ("presence_from", "presence_to"):
            edge = next_ring({"time": auto[key], "days": []}, now)
            if edge is not None:
                edges.append(edge)
        if edges:
            self._window_unsub = async_track_point_in_utc_time(self.hass, self._window_edge, dt_util.as_utc(min(edges)))

    async def _window_edge(self, _now: datetime) -> None:
        self._window_unsub = None
        auto = self.rt.state["auto"]
        if auto["presence_start"]:
            # a minute of slack: the timer fires on the edge, the clock may be a hair before it
            inside = in_window((dt_util.now() + timedelta(seconds=30)).time(), auto["presence_from"], auto["presence_to"])
            if auto["presence_mode"] == "window":
                if inside:
                    if not self.rt.state["playing"] and not self.rt.state["alarm_ringing"]:
                        self._window_started = True
                        await self.rt.async_good_night()
                elif self._window_started:
                    self._window_started = False
                    if self.rt.state["playing"]:
                        await self.rt.async_stop()
                        if self.rt.lights or self.rt.diy:
                            await self.rt.async_light(on=False)
            elif inside:
                await self._maybe_start_by_presence()
        self._arm_window()

    # ------------------------------------------------------------ pause on music
    @callback
    def _media_filter(self, data: EventStateChangedData) -> bool:
        entity_id = data["entity_id"]
        if not entity_id.startswith("media_player.") or entity_id in self.rt.speakers:
            return False
        new, old = data["new_state"], data["old_state"]
        return (
            new is not None
            and new.state == STATE_PLAYING
            and (old is None or old.state != STATE_PLAYING)
            and "/api/dusk_dawn/stream/" not in str(new.attributes.get("media_content_id", ""))
        )

    async def _media_changed(self, event: Event[EventStateChangedData]) -> None:
        if self.rt.state["auto"]["pause_on_music"] and self.rt.state["playing"]:
            _LOGGER.debug("%s started playing, pausing sounds", event.data["entity_id"])
            await self.rt.async_stop()
