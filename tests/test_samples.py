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


@pytest.fixture
def snd(library: SoundLibrary) -> str:
    return library.add_sound("Waldbach").id


@pytest.mark.parametrize("fmt", ["wav", "mp3", "flac", "ogg"])
def test_add_decodes_any_format_and_normalises(library: SoundLibrary, snd: str, tmp_path: Path, fmt: str) -> None:
    src = _make_audio(tmp_path, 8, amp=0.4, fmt=fmt)
    entry = library.add("ffmpeg", snd, src, "regen")
    assert abs(entry.duration - 8) < 0.3
    data = np.asarray(entry.array(), dtype=np.float64) / 32768 * entry.gain
    assert np.sqrt(np.mean(data**2)) == pytest.approx(TARGET_RMS, rel=0.1)
    # survives a restart
    again = SoundLibrary(library.root, RATE)
    again.load()
    assert [f.id for f in again.files(snd)] == [entry.id]
    assert again.listing()["sounds"][0]["name"] == "Waldbach"
    assert again.listing()["sounds"][0]["files"][0]["name"] == "regen"


def test_unlimited_named_sounds(library: SoundLibrary) -> None:
    ids = [library.add_sound(f"Klang {i}").id for i in range(30)]  # no upper limit
    assert len(set(ids)) == 30 and all(i.startswith("own_") for i in ids)
    library.rename_sound(ids[0], "  Heizung ")
    assert library.name_of(ids[0]) == "Heizung"
    with pytest.raises(DecodeError):
        library.add_sound("   ")
    with pytest.raises(DecodeError):
        library.rename_sound("own_nope", "x")


def test_add_rejects_bad_input(library: SoundLibrary, snd: str, tmp_path: Path) -> None:
    junk = tmp_path / "junk.wav"
    junk.write_bytes(b"not audio at all")
    with pytest.raises(DecodeError):
        library.add("ffmpeg", snd, junk, "x")
    with pytest.raises(DecodeError):
        library.add("ffmpeg", snd, _make_audio(tmp_path, 1), "short")
    with pytest.raises(DecodeError):
        library.add("ffmpeg", "own_unknown", _make_audio(tmp_path, 6), "wrong sound")
    assert library.files(snd) == []
    assert not list(library.root.glob("*.raw"))


def test_delete_file_and_sound(library: SoundLibrary, snd: str, tmp_path: Path) -> None:
    entry = library.add("ffmpeg", snd, _make_audio(tmp_path, 6), "f")
    assert library.delete(entry.id) is not None
    assert not entry.path.exists()
    assert library.files(snd) == []
    assert library.delete(entry.id) is None
    e2 = library.add("ffmpeg", snd, _make_audio(tmp_path, 6, 500), "g")
    assert [f.id for f in library.delete_sound(snd)] == [e2.id]
    assert not e2.path.exists() and not library.has_sound(snd)


def test_old_library_is_migrated(tmp_path: Path) -> None:
    """Version 0.3.0 stored files per built-in sound; they become named own sounds."""
    import json  # noqa: PLC0415

    root = tmp_path / "old"
    root.mkdir()
    (root / "abc.raw").write_bytes(np.zeros(RATE * 5, dtype="<i2").tobytes())
    (root / "index.json").write_text(json.dumps({"files": [
        {"id": "abc", "sound": "fire", "name": "kamin", "duration": 5.0, "gain": 2.0, "added": 1.0}]}))
    lib = SoundLibrary(root, RATE)
    lib.load()
    (sound,) = lib.sounds()
    assert sound.id == "own_fire" and "Feuer" in sound.name
    assert [f.id for f in lib.files("own_fire")] == ["abc"]
    again = SoundLibrary(root, RATE)
    again.load()  # the migrated index was written back
    assert [c.id for c in again.sounds()] == ["own_fire"]


def test_layer_is_continuous_and_rotates(library: SoundLibrary, snd: str, tmp_path: Path) -> None:
    a = library.add("ffmpeg", snd, _make_audio(tmp_path, 20, 300), "a")
    b = library.add("ffmpeg", snd, _make_audio(tmp_path, 20, 700), "b")
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


def test_layer_handles_short_and_changing_files(library: SoundLibrary, snd: str, tmp_path: Path) -> None:
    short = library.add("ffmpeg", snd, _make_audio(tmp_path, 4), "short")
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


def test_engine_plays_own_sounds_next_to_synth(library: SoundLibrary, tmp_path: Path) -> None:
    engine = SampleEngine(Engine(RATE, seed=1), library, seed=1)
    engine.set_master(0.8)
    engine.set_level("rain", 0.8)
    assert engine.wait_ready(60)

    def rms(seconds: float = 1.0) -> float:
        data = np.frombuffer(b"".join(engine.render(2205) for _ in range(int(20 * seconds))), "<i2")
        return float(np.sqrt(np.mean((data / 32768.0) ** 2)))

    rms(1.0)
    assert rms() > 0.001  # synth rain
    a = library.add_sound("Heizung")
    b = library.add_sound("Bach")
    library.add("ffmpeg", a.id, _make_audio(tmp_path, 10, amp=0.5), "tone")
    library.add("ffmpeg", b.id, _make_audio(tmp_path, 10, 700, amp=0.5), "tone")
    engine.refresh()
    engine.set_level("rain", 0.0)
    assert engine.has_layer(a.id) and engine.has_layer(b.id)
    rms(1.0)
    assert rms() == 0.0  # own sounds still at 0
    engine.set_level(a.id, 0.8)
    rms(1.0)
    only_a = rms()
    assert only_a > 0.002
    engine.set_level(b.id, 0.8)
    rms(1.0)
    assert rms() > only_a  # two own sounds at once
    library.delete_sound(a.id)
    engine.refresh()
    assert not engine.has_layer(a.id) and engine.has_layer(b.id)
    engine.set_level(a.id, 1.0)  # deleted sound: ignored
    rms(0.5)


def test_engine_master_scales_file_sound(library: SoundLibrary, snd: str, tmp_path: Path) -> None:
    library.add("ffmpeg", snd, _make_audio(tmp_path, 10, amp=0.5), "tone")
    engine = SampleEngine(Engine(RATE, seed=1), library, seed=1)
    engine.set_level(snd, 1.0)
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


async def test_own_sound_api(
    hass: HomeAssistant,
    setup_spot: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    tmp_path: Path,
) -> None:
    client = await hass_client()
    ws = await hass_ws_client(hass)
    entry_id = setup_spot.entry_id
    rt = setup_spot.runtime_data

    async def call(payload):
        await ws.send_json_auto_id(payload)
        return await ws.receive_json()

    assert (await call({"type": "dusk_dawn/sounds"}))["result"]["sounds"] == []
    assert not (await call({"type": "dusk_dawn/sound_add", "name": "  "}))["success"]
    msg = await call({"type": "dusk_dawn/sound_add", "name": "Waldbach"})
    sound = msg["result"]["sound"]
    assert msg["result"]["sounds"][0]["name"] == "Waldbach"
    assert not (await call({"type": "dusk_dawn/command", "entry_id": entry_id, "action": "set_level",
                            "sound": "own_nope", "level": 0.5}))["success"]

    audio = (await hass.async_add_executor_job(_make_audio, tmp_path, 8)).read_bytes()
    resp = await client.post(f"/api/dusk_dawn/upload/{sound}?name=Gartenbach.wav", data=audio)
    assert resp.status == 200, await resp.text()
    body = await resp.json()
    file_id = body["file"]["id"]
    assert body["file"]["name"] == "Gartenbach"
    assert body["sounds"][0]["files"][0]["id"] == file_id
    assert (await client.post("/api/dusk_dawn/upload/own_nope", data=audio)).status == 404
    assert (await client.post(f"/api/dusk_dawn/upload/{sound}", data=b"garbage")).status == 422

    msg = await call({"type": "dusk_dawn/command", "entry_id": entry_id, "action": "set_level",
                      "sound": sound, "level": 0.6})
    assert msg["result"]["state"]["levels"][sound] == 0.6
    assert rt.engine.has_layer(sound)

    msg = await call({"type": "dusk_dawn/sound_rename", "sound": sound, "name": "Bach"})
    assert msg["result"]["sounds"][0]["name"] == "Bach"

    msg = await call({"type": "dusk_dawn/sound_delete", "file_id": file_id})
    assert msg["success"] and msg["result"]["sounds"][0]["files"] == []
    assert (await call({"type": "dusk_dawn/sound_delete", "file_id": file_id}))["success"] is False

    msg = await call({"type": "dusk_dawn/sound_remove", "sound": sound})
    assert msg["success"] and msg["result"]["sounds"] == []
    assert sound not in rt.snapshot()["levels"]  # its level is forgotten
    assert not rt.engine.has_layer(sound)


def test_master_taper_is_quieter_and_monotonic() -> None:
    from custom_components.dusk_dawn.state import _engine_gain, master_gain, master_taper  # noqa: PLC0415

    assert master_taper(0) == 0.0
    assert abs(master_gain(1.0) - 0.4) < 1e-9  # -8 dB at the top (it was 0 dB)
    prev = 0.0
    for i in range(1, 101):
        v = i / 100
        m = master_taper(v)
        assert m >= prev and 0 < m <= 1
        assert abs(_engine_gain(m) - master_gain(v)) < 1e-6 * max(1.0, master_gain(v)) + 1e-9
        prev = m
    assert master_gain(0.5) < 0.05 and master_gain(0.1) < 0.003  # much more room at the bottom
