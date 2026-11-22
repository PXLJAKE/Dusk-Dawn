"""Alarms and automations of one spot.

* Alarms: ring at HH:MM on the chosen weekdays (Mon = 0); optionally start a
  sunrise ``sunrise_min`` minutes before. One timer is armed for the next
  event; after it fired the next one is computed. With a DIY lamp the lamp
  itself rings (it stores the list), so only ``next_alarm`` is computed here.
* Presence: start the good-night routine when presence is detected inside the
  time window; stop sounds and lights after presence has been gone for
  ``presence_stop_min`` minutes.
* Pause on music: stop the sounds when another media player starts playing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_STATE_CHANGED, STATE_ON, STATE_PLAYING
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
        self._unsubs: list[CALLBACK_TYPE] = []
        self._planned: list[tuple[str, dict[str, Any], datetime]] = []
        self._sunrise_started: set[tuple[str, str]] = set()  # (alarm id, ring time)

    # ------------------------------------------------------------ lifecycle
    @callback
    def async_start(self) -> None:
        self.async_reschedule()
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
        if self._presence_stop:
            self._presence_stop()
            self._presence_stop = None

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

    # ------------------------------------------------------------ presence
    async def _presence_changed(self, event: Event[EventStateChangedData]) -> None:
        new, old = event.data["new_state"], event.data["old_state"]
        if new is None:
            return
        auto = self.rt.state["auto"]
        if new.state == STATE_ON:
            if self._presence_stop:
                self._presence_stop()
                self._presence_stop = None
            if old is not None and old.state == STATE_ON:
                return
            if (
                auto["presence_start"]
                and not self.rt.state["playing"]
                and not self.rt.state["alarm_ringing"]
                and in_window(dt_util.now().time(), auto["presence_from"], auto["presence_to"])
            ):
                _LOGGER.debug("Presence detected, starting good night (%s)", self.rt.name)
                await self.rt.async_good_night()
        elif old is not None and old.state == STATE_ON:
            minutes = auto["presence_stop_min"]
            if auto["presence_start"] and minutes > 0 and self.rt.state["playing"]:
                self._presence_stop = async_call_later(self.hass, minutes * 60, self._presence_gone)

    async def _presence_gone(self, _now: datetime) -> None:
        self._presence_stop = None
        if self.rt.state["playing"]:
            _LOGGER.debug("Nobody there any more, stopping (%s)", self.rt.name)
            await self.rt.async_stop()
            if self.rt.lights or self.rt.diy:
                await self.rt.async_light(on=False)

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
