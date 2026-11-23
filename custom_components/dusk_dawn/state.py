"""Runtime state model (contract section 2): defaults, validation, helpers."""

from __future__ import annotations

import copy
import re
import secrets
from datetime import datetime, time, timedelta
from typing import Any

from .const import ALARM_TONES, BUILTIN_PRESETS, SOUNDS
from .samples import FILE_SOUNDS

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")

DEFAULT_AUTO: dict[str, Any] = {
    "presence_start": False,
    "presence_from": "20:00",
    "presence_to": "02:00",
    "presence_stop_min": 15,
    "presence_mode": "presence",  # "presence": only with someone there; "window": by time only
    "presence_min": 10,           # presence mode: somebody must be there this long (minutes) before sounds start
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
        # "synth" or "file" (own recordings) for the sounds in samples.FILE_SOUNDS
        "sources": dict.fromkeys(FILE_SOUNDS, "synth"),
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
    state["sources"].update({k: v for k, v in stored.get("sources", {}).items()
                             if k in FILE_SOUNDS and v in ("synth", "file")})
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
        elif key == "presence_min":
            out[key] = int(_clamp(value, 0, 120))
        elif key == "presence_mode":
            if value not in ("presence", "window"):
                raise ValueError(f"invalid presence_mode {value!r}")
            out[key] = value
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


# Volume taper of the synthesised sounds. The old slider (0 dB at 100 %, -20 dB at 50 %) was too loud next to
# music from AirPlay / Music Assistant, so the slider now tops out at -8 dB and falls off faster (about 56 dB
# down at 10 %). ``master_taper`` converts a slider position into the value the engines' own curve needs.
TAPER_TOP = 0.4      # gain at slider 100 %  (-8 dB)
TAPER_SLOPE = 2.4    # decades of gain over the slider range


def _engine_gain(m: float) -> float:
    """Gain the engines' ``volume_curve`` gives to master value ``m`` (same formula as the Rust core)."""
    return 0.0 if m <= 0 else 10 ** ((m - 1.0) * 2.0) * min(1.0, m * 10)


def master_gain(v: float) -> float:
    """Target gain for slider position ``v`` (0..1)."""
    v = min(max(float(v), 0.0), 1.0)
    return 0.0 if v <= 0 else TAPER_TOP * 10 ** ((v - 1.0) * TAPER_SLOPE) * min(1.0, v * 10)


def _engine_master_for(gain: float) -> float:
    """Inverse of ``_engine_gain``: the engine value that gives ``gain``."""
    if gain <= 0:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _engine_gain(mid) < gain:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def master_taper(v: float) -> float:
    """Master value for the engines (0..1) that yields ``master_gain(v)``."""
    return _engine_master_for(master_gain(v))


ALARM_TRIM = 0.5  # alarm tones were too loud: half the amplitude (-6 dB) at every slider position


def alarm_taper(v: float) -> float:
    """Alarm volume for the engines that is ``ALARM_TRIM`` times as loud as the slider position ``v`` used to be."""
    return _engine_master_for(ALARM_TRIM * _engine_gain(min(max(float(v), 0.0), 1.0)))
