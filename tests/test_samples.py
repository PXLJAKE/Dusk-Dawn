"""Own recordings: decoding, seamless loop player, engine mixing, upload API."""

from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.core import HomeAssistant

from custom_components.dusk_dawn.engine import Engine
from custom_components.dusk_dawn.samples import (
    FileLayer,
    SampleEngine,
    SoundLibrary,
    DecodeError,
    TARGET_RMS,
)

RATE = 44100


def _make_audio(path: Path, seconds: float, freq: int = 440, amp: float = 0.2, fmt: str = "wav") -> Path:
    """A sine with a slow amplitude wobble, written by ffmpeg in the given container."""
    target = path / f"tone_{seconds}_{freq}.{fmt}"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency={freq}:duration={seconds}:sample_rate=22050", "-af", f"volume={amp}",
                    str(target)], check=True)
    return target


@pytest.fixture
def library(tmp_path: Path) -> SoundLibrary:
    lib = SoundLibrary(tmp_path / "lib", RATE)
    lib.load()
    return lib


@pytest.mark.parametrize("fmt", ["wav", "mp3", "flac", "ogg"])
def test_add_decodes_any_format_and_normalises(library: SoundLibrary, tmp_path: Path, fmt: str) -> None:
    src = _make_audio(tmp_path, 8, amp=0.4, fmt=fmt)
    entry = library.add("ffmpeg", "rain", src, "regen")
    assert abs(entry.duration - 8) < 0.3
    data = np.asarray(entry.array(), dtype=np.float64) / 32768 * entry.gain
    assert np.sqrt(np.mean(data**2)) == pytest.approx(TARGET_RMS, rel=0.1)
    # survives a restart
    again = SoundLibrary(library.root, RATE)
    again.load()
    assert [f.id for f in again.files("rain")] == [entry.id]
    assert again.listing()["rain"][0]["name"] == "regen"


def test_add_rejects_bad_input(library: SoundLibrary, tmp_path: Path) -> None:
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not audio at all")
    with pytest.raises(DecodeError):
        library.add("ffmpeg", "rain", junk, "x")
    with pytest.raises(DecodeError):
        library.add("ffmpeg", "rain", _make_audio(tmp_path, 1), "short")
    with pytest.raises(DecodeError):
        library.add("ffmpeg", "thunder", _make_audio(tmp_path, 6), "wrong sound")
    assert library.files("rain") == []
    assert not list(library.root.glob("*.raw"))


def test_delete_removes_file(library: SoundLibrary, tmp_path: Path) -> None:
    entry = library.add("ffmpeg", "fire", _make_audio(tmp_path, 6), "f")
    assert library.delete(entry.id) is not None
    assert not entry.path.exists()
    assert library.files("fire") == []
    assert library.delete(entry.id) is None


def test_layer_is_continuous_and_rotates(library: SoundLibrary, tmp_path: Path) -> None:
    a = library.add("ffmpeg", "wind", _make_audio(tmp_path, 20, 300), "a")
    b = library.add("ffmpeg", "wind", _make_audio(tmp_path, 20, 700), "b")
    layer = FileLayer(RATE, seed=3)
    layer.set_files([a, b])
    block = RATE // 20
    out = np.concatenate([layer.render(block) for _ in range(20 * 60)])  # 60 s
    assert len(out) == 60 * RATE
    # no clicks: the largest sample-to-sample jump of a loud sine is bounded by its slope
    assert np.max(np.abs(np.diff(out))) < 0.25
    # crossfades keep the level steady (no dip to silence) over the whole run
    rms = [np.sqrt(np.mean(out[i:i + RATE] ** 2)) for i in range(0, 59 * RATE, RATE)]
    assert min(rms) > 0.6 * max(rms)
    # both files were used (300 Hz and 700 Hz present)
    spec = np.abs(np.fft.rfft(out))
    freqs = np.fft.rfftfreq(len(out), 1 / RATE)
    assert spec[np.argmin(abs(freqs - 300))] > 10 * np.median(spec)
    assert spec[np.argmin(abs(freqs - 700))] > 10 * np.median(spec)


def test_layer_handles_short_and_changing_files(library: SoundLibrary, tmp_path: Path) -> None:
    short = library.add("ffmpeg", "birds", _make_audio(tmp_path, 4), "short")
    layer = FileLayer(RATE, seed=1)
    assert not np.any(layer.render(1000))  # nothing loaded: silence
    layer.set_files([short])
    out = np.concatenate([layer.render(2205) for _ in range(20 * 30)])  # 30 s from a 4 s file
    assert np.max(np.abs(np.diff(out))) < 0.25
    assert np.sqrt(np.mean(out**2)) > 0.05
    layer.set_files([])  # deleted while playing: fades out, then silent
    for _ in range(20 * 10):
        layer.render(2205)
    assert not np.any(layer.render(2205))


def test_engine_switches_between_synth_and_file(library: SoundLibrary, tmp_path: Path) -> None:
    engine = SampleEngine(Engine(RATE, seed=1), library, seed=1)
    engine.set_master(0.8)
    engine.set_level("rain", 0.8)
    assert engine.wait_ready(60)

    def rms(seconds: float = 1.0) -> float:
        data = np.frombuffer(b"".join(engine.render(2205) for _ in range(int(20 * seconds))), "<i2")
        return float(np.sqrt(np.mean((data / 32768.0) ** 2)))

    rms(1.0)  # let the level smoothing settle
    synth = rms()
    assert synth > 0.001
    with pytest.raises(ValueError):
        engine.set_source("thunder", "file")
    engine.set_source("rain", "file")  # no file yet: stays synthetic
    assert rms() > 0.001
    library.add("ffmpeg", "rain", _make_audio(tmp_path, 10, amp=0.5), "tone")
    engine.refresh("rain")
    rms(1.0)
    file_level = rms()
    assert file_level > 0.002
    assert engine.inner.levels()["rain"] == 0.0  # synth muted while the file plays
    engine.set_level("rain", 0.0)
    rms(1.0)
    assert rms() == 0.0
    engine.set_source("rain", "synth")
    assert engine.inner.levels()["rain"] == 0.0
    engine.set_level("rain", 0.8)
    assert engine.inner.levels()["rain"] == 0.8


def test_engine_master_scales_file_sound(library: SoundLibrary, tmp_path: Path) -> None:
    library.add("ffmpeg", "waves", _make_audio(tmp_path, 10, amp=0.5), "tone")
    engine = SampleEngine(Engine(RATE, seed=1), library, seed=1)
    engine.set_source("waves", "file")
    engine.set_level("waves", 1.0)
    engine.set_master(1.0)
    for _ in range(40):
        engine.render(2205)
    loud = np.abs(np.frombuffer(engine.render(2205), "<i2")).mean()
    engine.set_master(0.3)
    for _ in range(40):
        engine.render(2205)
    quiet = np.abs(np.frombuffer(engine.render(2205), "<i2")).mean()
    assert quiet < 0.5 * loud
    engine.set_master(0.0)
    for _ in range(40):
        engine.render(2205)
    assert not any(engine.render(2205))


async def test_upload_api_and_sources(
    hass: HomeAssistant,
    setup_spot: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    tmp_path: Path,
) -> None:
    client = await hass_client()
    ws = await hass_ws_client(hass)
    entry_id = setup_spot.entry_id

    async def call(payload):
        await ws.send_json_auto_id(payload)
        return await ws.receive_json()

    msg = await call({"type": "dusk_dawn/command", "entry_id": entry_id, "action": "set_source",
                      "sound": "rain", "mode": "file"})
    assert not msg["success"]  # nothing uploaded yet
    assert (await call({"type": "dusk_dawn/sounds"}))["result"]["files"]["rain"] == []

    audio = (await hass.async_add_executor_job(_make_audio, tmp_path, 8)).read_bytes()
    resp = await client.post("/api/dusk_dawn/upload/rain?name=Gartenregen.wav", data=audio)
    assert resp.status == 200, await resp.text()
    body = await resp.json()
    file_id = body["file"]["id"]
    assert body["file"]["name"] == "Gartenregen"
    assert body["files"]["rain"][0]["id"] == file_id

    assert (await client.post("/api/dusk_dawn/upload/thunder", data=audio)).status == 404
    assert (await client.post("/api/dusk_dawn/upload/rain", data=b"garbage")).status == 422

    msg = await call({"type": "dusk_dawn/command", "entry_id": entry_id, "action": "set_source",
                      "sound": "rain", "mode": "file"})
    assert msg["result"]["state"]["sources"]["rain"] == "file"
    assert setup_spot.runtime_data.engine.source("rain") == "file"

    msg = await call({"type": "dusk_dawn/sound_delete", "file_id": file_id})
    assert msg["success"] and msg["result"]["files"]["rain"] == []
    assert setup_spot.runtime_data.snapshot()["sources"]["rain"] == "synth"  # fell back
    assert (await call({"type": "dusk_dawn/sound_delete", "file_id": file_id}))["success"] is False
