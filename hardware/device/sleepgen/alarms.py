"""Alarms that live on the lamp itself.

Home Assistant only *edits* the alarm list (retained MQTT topic
``<base>/alarms/set``). The lamp keeps a copy on its SD card and rings by
itself, so the alarm still goes off when Home Assistant, the broker or the
network is down. After a power cut the lamp rings late if it is back within
``grace_min`` minutes of the alarm time.

Needs a correct clock. Without internet the Pi keeps the time it last saved
(systemd saves it regularly); for exact time after long outages add a
DS3231 battery RTC (see docs/ALARM_OFFLINE.md).
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:  # pragma: no cover
    from .app import App

log = logging.getLogger(__name__)

TONE_NAMES = {"bells": "Glocken", "classic": "Klassisch", "birds": "Vogelchor"}
_KEYS = ("enabled", "time", "days", "tone", "duration_min", "volume", "sunrise", "sunrise_min")


def _parse_hhmm(value: str) -> dtime:
    h, m = str(value).split(":")
    return dtime(int(h), int(m))


def _at(day: datetime, t: dtime) -> datetime:
    return day.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)


def next_ring(alarm: dict, after: datetime) -> datetime | None:
    """First ring strictly after ``after`` (naive local time, Monday = 0)."""
    t, days = _parse_hhmm(alarm["time"]), alarm.get("days") or []
    base = _at(after, t)
    for offset in range(8):
        cand = base + timedelta(days=offset)
        if cand > after and (not days or cand.weekday() in days):
            return cand
    return None


def prev_ring(alarm: dict, upto: datetime) -> datetime | None:
    """Last ring at or before ``upto``."""
    t, days = _parse_hhmm(alarm["time"]), alarm.get("days") or []
    base = _at(upto, t)
    for offset in range(8):
        cand = base - timedelta(days=offset)
        if cand <= upto and (not days or cand.weekday() in days):
            return cand
    return None


def clean_alarm(raw: dict) -> dict:
    a = {
        "id": str(raw["id"]),
        "enabled": bool(raw.get("enabled", True)),
        "time": str(raw["time"]),
        "days": sorted({int(d) for d in raw.get("days", []) if 0 <= int(d) <= 6}),
        "tone": raw.get("tone", "bells") if raw.get("tone") in TONE_NAMES else "bells",
        "duration_min": max(1, min(120, int(raw.get("duration_min", 10)))),
        "volume": max(0.0, min(1.0, float(raw.get("volume", 0.7)))),
        "sunrise": bool(raw.get("sunrise", False)),
        "sunrise_min": max(1, min(120, int(raw.get("sunrise_min", 30)))),
    }
    _parse_hhmm(a["time"])
    return a


class AlarmScheduler:
    def __init__(self, app: "App", path: str | Path, *, grace_min: float = 20,
                 now: Callable[[], datetime] = datetime.now):
        self.app = app
        self.path = Path(path)
        self.grace = timedelta(minutes=grace_min)
        self._now = now
        self.enabled = True
        self.alarms: list[dict] = []
        self.fired: dict[str, str] = {}      # alarm id -> ring time that already rang
        self.sunrise_done: dict[str, str] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ storage
    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text())
            self.enabled = bool(data.get("enabled", True))
            self.alarms = [clean_alarm(a) for a in data.get("alarms", [])]
            self.fired = {str(k): str(v) for k, v in data.get("fired", {}).items()}
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def save(self) -> None:
        data = {"enabled": self.enabled, "alarms": self.alarms, "fired": self.fired}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            os.replace(tmp, self.path)
        except OSError as exc:
            log.warning("could not save alarms: %s", exc)

    def snapshot(self) -> dict:
        with self._lock:
            return {"enabled": self.enabled, "alarms": [dict(a) for a in self.alarms]}

    # ------------------------------------------------------------ from Home Assistant
    def set_all(self, data: dict) -> None:
        """Replace the alarm list (retained message from Home Assistant).

        A new or edited alarm whose time already passed a moment ago does not
        ring at once; only unchanged alarms catch up after a power cut.
        """
        alarms = [clean_alarm(a) for a in data.get("alarms", [])]
        now = self._now()
        with self._lock:
            old = {a["id"]: a for a in self.alarms}
            for a in alarms:
                prev = old.get(a["id"])
                if prev is None or any(prev[k] != a[k] for k in ("time", "days", "enabled")):
                    p = prev_ring(a, now)
                    if p is not None:
                        self.fired[a["id"]] = p.isoformat()
                    self.sunrise_done.pop(a["id"], None)
            self.alarms = alarms
            self.enabled = bool(data.get("enabled", True))
            self.fired = {k: v for k, v in self.fired.items() if k in {a["id"] for a in alarms}}
        self.save()
        self.app.publish_state()

    # ------------------------------------------------------------ logic
    def tick(self, now: datetime | None = None) -> None:
        now = now or self._now()
        changed = False
        with self._lock:
            if not self.enabled:
                return
            for a in self.alarms:
                if not a["enabled"]:
                    continue
                if a["sunrise"]:
                    nxt = next_ring(a, now)
                    if nxt is not None:
                        start = nxt - timedelta(minutes=a["sunrise_min"])
                        key = nxt.isoformat()
                        if start <= now and self.sunrise_done.get(a["id"]) != key:
                            self.sunrise_done[a["id"]] = key
                            left = (nxt - now).total_seconds() / 60
                            if left >= 1:
                                self._sunrise(a, left)
                prev = prev_ring(a, now)
                if prev is not None and now - prev <= self.grace and self.fired.get(a["id"]) != prev.isoformat():
                    self.fired[a["id"]] = prev.isoformat()
                    changed = True
                    self._ring(a)
                    if not a["days"]:  # one-off: disable after it rang
                        a["enabled"] = False
        if changed:
            self.save()
            self.app.publish_state()

    def _ring(self, a: dict) -> None:
        log.info("alarm %s rings (%s)", a["id"], a["time"])
        try:
            self.app.start_alarm(TONE_NAMES[a["tone"]], a["duration_min"], a["volume"])
        except Exception:  # noqa: BLE001
            log.exception("alarm failed")

    def _sunrise(self, a: dict, minutes: float) -> None:
        log.info("sunrise for alarm %s (%.0f min)", a["id"], minutes)
        try:
            self.app.lamp.start_sunrise(minutes)
        except Exception:  # noqa: BLE001
            log.exception("sunrise failed")

    # ------------------------------------------------------------ thread
    def start(self) -> None:
        self.load()
        self._thread = threading.Thread(target=self._run, name="alarms", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(1.0):
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                log.exception("alarm tick failed")
