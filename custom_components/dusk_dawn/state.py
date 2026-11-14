"""Runtime state model (contract section 2): defaults, validation, helpers."""

from __future__ import annotations

import copy
import re
import secrets
from datetime import datetime, time, timedelta
from typing import Any

from .const import ALARM_TONES, BUILTIN_PRESETS, SOUNDS

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DEFAULT_AUTO: dict[str, Any] = {
    "presence_start": False,
    "presence_from": "20:00",
    "presence_to": "02:00",
    "presence_stop_min": 15,
    "pause_on_music": False,
    "night_light_with_sound": False,
}

DEFAULT_ALARM: dict[str, Any] = {
    "enabled": True,
    "time": "07:00",
    "days": [0, 1, 2, 3, 4],
    "tone": "bells",
    "duration_min": 10,
    "volume": 0.6,
    "sunrise": True,
    "sunrise_min": 30,
}


def default_state() -> dict[str, Any]:
    """A fresh runtime state."""
    return {
        "playing": False,
        "preset": None,
        "levels": dict.fromkeys(SOUNDS, 0.0),
        "volume": 0.5,
        "timer": {"minutes": None, "ends_at": None},
        # "effect" is an addition to the contract: the running light effect, if any
        "light": {"on": False, "brightness": 128, "kelvin": 2700, "effect": None},
        "alarms": [],
        # addition to the contract: master switch behind switch.alarms_enabled
        "alarms_enabled": True,
        "auto": dict(DEFAULT_AUTO),
        "presets": copy.deepcopy(BUILTIN_PRESETS),
        "alarm_ringing": False,
        "next_alarm": None,
    }


def merge_stored(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Merge a stored state over the defaults; transient fields are reset."""
    state = default_state()
    if not stored:
        return state
    for key in ("preset", "volume", "alarms", "alarms_enabled"):
        if key in stored:
            state[key] = stored[key]
    state["levels"].update({k: float(v) for k, v in stored.get("levels", {}).items() if k in SOUNDS})
    state["timer"]["minutes"] = stored.get("timer", {}).get("minutes")
    light = stored.get("light", {})
    state["light"].update({k: light[k] for k in ("brightness", "kelvin") if k in light})
    state["auto"].update({k: v for k, v in stored.get("auto", {}).items() if k in DEFAULT_AUTO})
    # built-ins always come from the code (so fixes reach users), user presets from storage
    user = [{**p, "builtin": False} for p in stored.get("presets", []) if str(p.get("id", "")).startswith("user_")]
    state["presets"].extend(user)
    state["alarms"] = [normalize_alarm(a) for a in state["alarms"]]
    return state


def _clamp(value: Any, lo: float, hi: float) -> float:
    return min(max(float(value), lo), hi)


def normalize_alarm(alarm: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate an alarm dict, filling gaps from ``existing`` or the defaults."""
    out = dict(DEFAULT_ALARM)
    if existing:
        out.update(existing)
    out.update({k: v for k, v in alarm.items() if k in DEFAULT_ALARM or k == "id"})
    if not TIME_RE.match(str(out["time"])):
        raise ValueError(f"invalid time {out['time']!r}, expected HH:MM")
    days = sorted({int(d) for d in out["days"]})
    if any(d < 0 or d > 6 for d in days):
        raise ValueError("days must be 0..6 (Monday = 0)")
    if out["tone"] not in ALARM_TONES:
        raise ValueError(f"unknown tone {out['tone']!r}")
    return {
        "id": str(out.get("id") or secrets.token_hex(4)),
        "enabled": bool(out["enabled"]),
        "time": str(out["time"]),
        "days": days,
        "tone": out["tone"],
        "duration_min": int(_clamp(out["duration_min"], 1, 120)),
        "volume": _clamp(out["volume"], 0, 1),
        "sunrise": bool(out["sunrise"]),
        "sunrise_min": int(_clamp(out["sunrise_min"], 1, 120)),
    }


def normalize_auto(auto: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    out = dict(current)
    for key, value in auto.items():
        if key not in DEFAULT_AUTO:
            raise ValueError(f"unknown auto option {key!r}")
        if key in ("presence_from", "presence_to"):
            if not TIME_RE.match(str(value)):
                raise ValueError(f"invalid time {value!r}, expected HH:MM")
            out[key] = str(value)
        elif key == "presence_stop_min":
            out[key] = int(_clamp(value, 0, 240))
        else:
            out[key] = bool(value)
    return out


def parse_hhmm(value: str) -> time:
    hours, minutes = value.split(":")
    return time(int(hours), int(minutes))


def in_window(now: time, start: str, end: str) -> bool:
    """Is ``now`` within [start, end)? Windows may wrap around midnight."""
    s, e = parse_hhmm(start), parse_hhmm(end)
    if s <= e:
        return s <= now < e
    return now >= s or now < e


def next_ring(alarm: dict[str, Any], after: datetime) -> datetime | None:
    """Next ring time of ``alarm`` strictly after ``after`` (timezone-aware)."""
    t = parse_hhmm(alarm["time"])
    days = alarm["days"]
    base = after.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
    for offset in range(8):
        # aware datetime arithmetic keeps the wall clock time across DST changes
        candidate = base + timedelta(days=offset)
        if candidate > after and (not days or candidate.weekday() in days):
            return candidate
    return None


def find_preset(presets: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """Look a preset up by id or (case-insensitive) name."""
    for p in presets:
        if p["id"] == key:
            return p
    low = key.casefold()
    for p in presets:
        if p["name"].casefold() == low:
            return p
    return None
