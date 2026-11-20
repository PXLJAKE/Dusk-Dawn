"""Own sound recordings: library on disk and a seamless-loop player.

Users upload long recordings (five minutes or more) for the nature sounds. Each
file is decoded once with ffmpeg to mono 16-bit PCM at the engine rate, stored as
a raw file (memory mapped on playback, so a 30 minute file costs no RAM) and
loudness-normalised with a stored gain. :class:`FileLayer` plays the files of one
sound as an endless chain of random segments with long equal-power crossfades,
rotating between the files, so the loop never repeats at the same place.

:class:`SampleEngine` wraps the synth engine (Rust or Python) and mixes the file
layers into its output. A sound can be switched between "synth" and "file".
"""

from __future__ import annotations

import json
import logging
import math
import os
import secrets
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

_LOGGER = logging.getLogger(__name__)

# sounds that can be replaced by recordings
FILE_SOUNDS = ("rain", "waves", "wind", "birds", "leaves", "fire")

TARGET_RMS = 0.10  # loudness every recording is normalised to (full scale = 1.0)
MAX_GAIN = 12.0  # never amplify very quiet recordings by more than ~21 dB
MIN_DURATION_S = 3.0
MAX_DURATION_S = 3 * 3600.0
MAX_FILES_PER_SOUND = 12
CROSSFADE_S = 6.0
SEGMENT_MIN_S = 45.0
SEGMENT_MAX_S = 150.0
DRIFT_DB = 1.2  # slow loudness drift of a layer, +-
DRIFT_PERIOD_S = 55.0

_SILENT = 1e-5


def volume_curve(v: float) -> float:
    """Same slider-to-gain mapping as the synth engine."""
    v = min(max(v, 0.0), 1.0)
    if v <= 0:
        return 0.0
    return float(10 ** ((v - 1.0) * 2.0)) * min(1.0, v * 10)


# --------------------------------------------------------------------------- decoding
class DecodeError(Exception):
    """The uploaded file could not be turned into audio."""


@dataclass(frozen=True)
class SampleFile:
    id: str
    sound: str
    name: str
    duration: float
    gain: float
    added: float
    path: Path

    def info(self) -> dict[str, Any]:
        return {"id": self.id, "sound": self.sound, "name": self.name,
                "duration": round(self.duration, 1), "added": self.added}

    def array(self) -> np.ndarray:
        return np.memmap(self.path, dtype="<i2", mode="r")


def decode_to_raw(ffmpeg: str, source: Path, target: Path, rate: int) -> None:
    """ffmpeg any audio (or video) file to raw mono s16le."""
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(source), "-vn", "-sn",
           "-ac", "1", "-ar", str(rate), "-f", "s16le", str(target)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=1800, check=False)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired) as err:
        raise DecodeError(f"ffmpeg failed: {err}") from err
    if proc.returncode != 0 or not target.exists() or target.stat().st_size < 2:
        msg = proc.stderr.decode(errors="replace").strip().splitlines()
        raise DecodeError(msg[-1] if msg else "not an audio file")


def measure(path: Path, rate: int) -> tuple[float, float]:
    """(duration in s, rms of the file as 0..1), computed in chunks."""
    data = np.memmap(path, dtype="<i2", mode="r")
    n = len(data)
    chunk = rate * 30
    acc = 0.0
    for i in range(0, n, chunk):
        part = np.asarray(data[i:i + chunk], dtype=np.float64) / 32768.0
        acc += float(np.dot(part, part))
    rms = math.sqrt(acc / n) if n else 0.0
    del data
    return n / rate, rms


# --------------------------------------------------------------------------- library
class SoundLibrary:
    """All uploaded recordings, shared by every spot. Blocking methods run in an executor."""

    def __init__(self, root: Path, rate: int = 44100) -> None:
        self.root = Path(root)
        self.rate = rate
        self._lock = threading.Lock()
        self._files: dict[str, SampleFile] = {}
        self._loaded = False

    # ---- persistence
    @property
    def _index(self) -> Path:
        return self.root / "index.json"

    def load(self) -> None:
        with self._lock:
            self._files = {}
            try:
                items = json.loads(self._index.read_text(encoding="utf-8")).get("files", [])
            except (OSError, ValueError):
                items = []
            for it in items:
                try:
                    path = self.root / f"{it['id']}.raw"
                    if it["sound"] in FILE_SOUNDS and path.exists():
                        self._files[it["id"]] = SampleFile(
                            id=it["id"], sound=it["sound"], name=str(it.get("name", it["id"])),
                            duration=float(it["duration"]), gain=float(it["gain"]),
                            added=float(it.get("added", 0)), path=path)
                except (KeyError, TypeError, ValueError):
                    continue
            self._loaded = True

    def _save(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        items = [{"id": f.id, "sound": f.sound, "name": f.name, "duration": f.duration, "gain": f.gain,
                  "added": f.added} for f in self._files.values()]
        tmp = self._index.with_suffix(".tmp")
        tmp.write_text(json.dumps({"files": items}), encoding="utf-8")
        os.replace(tmp, self._index)

    def files(self, sound: str) -> list[SampleFile]:
        with self._lock:
            return sorted((f for f in self._files.values() if f.sound == sound), key=lambda f: f.added)

    def listing(self) -> dict[str, list[dict[str, Any]]]:
        return {s: [f.info() for f in self.files(s)] for s in FILE_SOUNDS}

    def get(self, file_id: str) -> SampleFile | None:
        with self._lock:
            return self._files.get(file_id)

    # ---- changes
    def add(self, ffmpeg: str, sound: str, source: Path, name: str) -> SampleFile:
        """Decode ``source`` and add it. Raises DecodeError."""
        if sound not in FILE_SOUNDS:
            raise DecodeError(f"{sound} cannot use own files")
        if len(self.files(sound)) >= MAX_FILES_PER_SOUND:
            raise DecodeError(f"at most {MAX_FILES_PER_SOUND} files per sound")
        self.root.mkdir(parents=True, exist_ok=True)
        file_id = secrets.token_hex(6)
        target = self.root / f"{file_id}.raw"
        try:
            decode_to_raw(ffmpeg, source, target, self.rate)
            duration, rms = measure(target, self.rate)
            if duration < MIN_DURATION_S:
                raise DecodeError(f"too short ({duration:.1f} s, at least {MIN_DURATION_S:.0f} s)")
            if duration > MAX_DURATION_S:
                raise DecodeError("too long (at most 3 hours)")
            if rms < 1e-4:
                raise DecodeError("the recording is silent")
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        gain = min(TARGET_RMS / rms, MAX_GAIN)
        entry = SampleFile(file_id, sound, name[:80] or "Aufnahme", duration, gain, time.time(), target)
        with self._lock:
            self._files[file_id] = entry
            self._save()
        return entry

    def delete(self, file_id: str) -> SampleFile | None:
        with self._lock:
            entry = self._files.pop(file_id, None)
            if entry is not None:
                self._save()
        if entry is not None:
            entry.path.unlink(missing_ok=True)
        return entry


# --------------------------------------------------------------------------- player
class _Voice:
    """One segment of one file, faded in and out."""

    def __init__(self, entry: SampleFile, data: np.ndarray, start: int, length: int, xfade: int,
                 fade_in: bool = True) -> None:
        self.entry = entry
        self.data = data
        self.start = start
        self.length = length
        self.xfade = xfade
        self.age = 0
        self.fade_in = fade_in
        self.spawned_next = False

    @property
    def done(self) -> bool:
        return self.age >= self.length

    def render(self, n: int) -> np.ndarray:
        take = min(n, self.length - self.age)
        out = np.zeros(n)
        if take <= 0:
            return out
        a = self.start + self.age
        seg = np.asarray(self.data[a:a + take], dtype=np.float64) / 32768.0
        take = len(seg)
        idx = self.age + np.arange(take)
        fin = np.minimum(idx / self.xfade, 1.0) if self.fade_in and self.xfade > 0 else np.ones(take)
        fout = np.clip((self.length - idx) / self.xfade, 0.0, 1.0) if self.xfade > 0 else np.ones(take)
        out[:take] = seg * np.sin(fin * math.pi / 2) * np.sin(fout * math.pi / 2) * self.entry.gain
        self.age += n
        return out


class FileLayer:
    """Endless, non-repeating playback of a set of recordings."""

    def __init__(self, rate: int, seed: int | None = None) -> None:
        self.rate = rate
        self._rng = np.random.default_rng(seed)
        self._files: list[SampleFile] = []
        self._voices: list[_Voice] = []
        self._order: list[str] = []
        self._last_id: str | None = None
        self._t = 0
        self._phase = float(self._rng.uniform(0, 2 * math.pi))
        self._lock = threading.Lock()

    @property
    def has_files(self) -> bool:
        return bool(self._files)

    def set_files(self, files: list[SampleFile]) -> None:
        with self._lock:
            self._files = list(files)
            keep = {f.id for f in files}
            self._order = [i for i in self._order if i in keep]
            for v in self._voices:  # a deleted file fades out instead of cutting off
                if v.entry.id not in keep:
                    v.length = min(v.length, v.age + v.xfade)
                    v.spawned_next = True

    def _pick(self) -> SampleFile | None:
        if not self._files:
            return None
        by_id = {f.id: f for f in self._files}
        self._order = [i for i in self._order if i in by_id]
        if not self._order:
            ids = list(by_id)
            self._rng.shuffle(ids)
            if len(ids) > 1 and ids[0] == self._last_id:  # no immediate repeat at the shuffle seam
                ids.append(ids.pop(0))
            self._order = ids
        self._last_id = self._order.pop(0)
        return by_id[self._last_id]

    def _spawn(self, fade_in: bool = True) -> _Voice | None:
        entry = self._pick()
        if entry is None:
            return None
        data = entry.array()
        total = len(data)
        xfade = int(min(CROSSFADE_S * self.rate, total / 4))
        seg = int(self._rng.uniform(SEGMENT_MIN_S, SEGMENT_MAX_S) * self.rate)
        seg = max(min(seg, total), min(total, 2 * xfade + 1))
        start = int(self._rng.integers(0, max(1, total - seg + 1)))
        return _Voice(entry, data, start, min(seg, total - start), xfade, fade_in)

    def render(self, n: int) -> np.ndarray:
        with self._lock:
            if not self._voices:
                if (v := self._spawn(fade_in=False)) is not None:
                    self._voices.append(v)
            out = np.zeros(n)
            for v in list(self._voices):
                out += v.render(n)
                if not v.spawned_next and v.length - v.age <= v.xfade:
                    v.spawned_next = True
                    nxt = self._spawn()
                    if nxt is not None:
                        self._voices.append(nxt)
                if v.done:
                    self._voices.remove(v)
            # slow drift so the bed never feels static
            t = self._t + np.arange(n)
            drift = 10 ** (DRIFT_DB * np.sin(2 * math.pi * t / (DRIFT_PERIOD_S * self.rate) + self._phase) / 20)
            self._t += n
            return out * drift


# --------------------------------------------------------------------------- engine wrapper
class SampleEngine:
    """The synth engine plus file layers for the sounds in :data:`FILE_SOUNDS`."""

    def __init__(self, inner: Any, library: SoundLibrary, seed: int | None = None) -> None:
        self.inner = inner
        self.library = library
        self._rate = int(inner.rate)
        self._layers = {s: FileLayer(self._rate, None if seed is None else seed + i)
                        for i, s in enumerate(FILE_SOUNDS)}
        self._source = dict.fromkeys(FILE_SOUNDS, "synth")
        self._levels = dict.fromkeys(FILE_SOUNDS, 0.0)
        self._gains = dict.fromkeys(FILE_SOUNDS, 0.0)
        self._master = 0.0
        self._master_target = 0.0
        self._master_step = 0.0
        self._lock = threading.Lock()
        self.refresh()

    # ---- pass-through
    def __getattr__(self, name: str) -> Any:  # sounds(), levels(), wait_ready(), alarm_ringing, ...
        return getattr(self.inner, name)

    @property
    def rate(self) -> int:
        return self._rate

    # ---- sources
    def refresh(self, sound: str | None = None) -> None:
        """Re-read the library (after an upload or delete)."""
        for s in (sound,) if sound else FILE_SOUNDS:
            if s in self._layers:
                self._layers[s].set_files(self.library.files(s))
                self._apply(s)

    def source(self, sound: str) -> str:
        return self._source.get(sound, "synth")

    def set_source(self, sound: str, mode: str) -> None:
        if sound not in self._layers or mode not in ("synth", "file"):
            raise ValueError(f"bad source {mode!r} for {sound!r}")
        self._source[sound] = mode
        self._apply(sound)

    def _file_active(self, sound: str) -> bool:
        return self._source[sound] == "file" and self._layers[sound].has_files

    def _apply(self, sound: str) -> None:
        level = self._levels[sound]
        self.inner.set_level(sound, 0.0 if self._file_active(sound) else level)

    def set_level(self, sound: str, level: float) -> None:
        if sound in self._layers:
            self._levels[sound] = min(max(float(level), 0.0), 1.0)
            self._apply(sound)
        else:
            self.inner.set_level(sound, level)

    # ---- master
    def set_master(self, volume: float, ramp_s: float = 0.0) -> None:
        self.inner.set_master(volume, ramp_s)
        volume = min(max(float(volume), 0.0), 1.0)
        with self._lock:
            self._master_target = volume
            if ramp_s <= 0:
                self._master, self._master_step = volume, 0.0
            else:
                self._master_step = (volume - self._master) / (ramp_s * self._rate)

    def _advance_master(self, n: int) -> float:
        if self._master_step:
            m = self._master + self._master_step * n
            if (self._master_step > 0 and m >= self._master_target) or (
                self._master_step < 0 and m <= self._master_target
            ):
                m, self._master_step = self._master_target, 0.0
            self._master = m
        return self._master

    # ---- render
    def render(self, frames: int) -> bytes:
        n = int(frames)
        base = self.inner.render(n)
        if n <= 0:
            return base
        with self._lock:
            active = [s for s in FILE_SOUNDS if self._file_active(s) and (self._gains[s] > _SILENT
                                                                         or self._levels[s] > 0)]
            m0 = self._master
            m1 = self._advance_master(n)
        if not active:
            return base
        ramp = np.arange(1, n + 1) / n
        k = min(1.0, n / (0.15 * self._rate))
        mix = np.zeros(n)
        for s in active:
            g0 = self._gains[s]
            target = volume_curve(self._levels[s])
            g1 = g0 + (target - g0) * k
            if g1 < _SILENT and target == 0.0:
                g1 = 0.0
            self._gains[s] = g1
            mix += self._layers[s].render(n) * (g0 + (g1 - g0) * ramp)
        c0, c1 = volume_curve(m0), volume_curve(m1)
        mix *= c0 + (c1 - c0) * ramp
        mix = np.tanh(mix * 1.2) / 1.2
        out = np.frombuffer(base, dtype="<i2").astype(np.float64) / 32768.0 + mix
        return (np.clip(out, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def unwrap(engine: Any) -> Any:
    return getattr(engine, "inner", engine) if isinstance(engine, SampleEngine) else engine
