"""Tests for the dusk_dawn_core Python module against the contract
(integration/CONTRACT.md section 1) and the Python reference engine
(device/sleepgen).

The module is built with ``maturin develop --release`` (inside a virtualenv) or
``pip install`` if it is not importable yet. Set DUSK_DAWN_CORE_NO_BUILD=1 to
skip that step and use whatever is installed.
"""

from __future__ import annotations

import importlib
import inspect
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

CORE = Path(__file__).resolve().parents[1]
REPO = CORE.parent
SR = 44100

SOUNDS = ["rain", "waves", "stream", "wind", "thunder", "birds", "leaves", "fire", "fan", "white", "pink", "brown"]
ALARM_TONES = ["bells", "classic", "birds"]


def _build():
    if os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX"):
        cmd = [sys.executable, "-m", "maturin", "develop", "--release", "-m", str(CORE / "Cargo.toml")]
    else:
        cmd = [sys.executable, "-m", "pip", "install", "--quiet", str(CORE)]
    subprocess.run(cmd, check=True, cwd=CORE)


@pytest.fixture(scope="session")
def core():
    try:
        return importlib.import_module("dusk_dawn_core")
    except ImportError:
        if os.environ.get("DUSK_DAWN_CORE_NO_BUILD"):
            pytest.skip("dusk_dawn_core not installed")
    _build()
    importlib.invalidate_caches()
    return importlib.import_module("dusk_dawn_core")


@pytest.fixture(scope="session")
def ref():
    pytest.importorskip("scipy")
    sys.path.insert(0, str(REPO / "device"))
    from sleepgen import engine

    return engine


def pcm(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype="<i2").astype(np.float64) / 32767.0


def rms(x) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else 0.0


def db(x: float) -> float:
    return 20 * np.log10(max(x, 1e-12) / 0.125)


# ------------------------------------------------------------------ API shape
def test_module_constants(core):
    assert core.SOUNDS == SOUNDS
    assert core.ALARM_TONES == ALARM_TONES


def test_api_shape(core):
    eng = core.Engine()
    assert eng.rate == 44100
    assert core.Engine(22050, seed=3).rate == 22050
    assert core.Engine(rate=48000, seed=None).rate == 48000
    assert eng.sounds() == SOUNDS
    lv = eng.levels()
    assert isinstance(lv, dict) and list(lv) == SOUNDS and all(v == 0.0 for v in lv.values())
    assert isinstance(eng.master, float) and 0.0 <= eng.master <= 1.0
    assert eng.alarm_ringing is False
    for attr in ("rate", "master", "alarm_ringing"):
        with pytest.raises(AttributeError):
            setattr(eng, attr, 1)
    for meth in ("sounds", "set_level", "levels", "set_master", "start_alarm", "stop_alarm", "render"):
        assert callable(getattr(eng, meth))
    sig = inspect.signature(core.Engine.set_master)
    assert sig.parameters["ramp_s"].default == 0.0
    sig = inspect.signature(core.Engine.start_alarm)
    assert sig.parameters["ramp_s"].default == 40.0
    assert list(sig.parameters)[1:] == ["tone", "seconds", "volume", "ramp_s"]


def test_set_level_and_levels(core):
    eng = core.Engine(SR, seed=1)
    eng.set_level("rain", 0.4)
    eng.set_level("waves", 2.0)  # clamped
    eng.set_level("wind", -1)
    assert eng.levels()["rain"] == pytest.approx(0.4)
    assert eng.levels()["waves"] == 1.0
    assert eng.levels()["wind"] == 0.0
    with pytest.raises(KeyError):
        eng.set_level("nope", 0.5)


def test_bad_arguments(core):
    with pytest.raises(ValueError):
        core.Engine(100)
    eng = core.Engine(SR, seed=1)
    with pytest.raises((ValueError, OverflowError)):
        eng.render(-1)


# ------------------------------------------------------------------ render format
@pytest.mark.parametrize("frames", [0, 1, 255, 256, 257, 2205, 44100])
def test_render_length_and_type(core, frames):
    eng = core.Engine(SR, seed=2)
    eng.set_level("pink", 1.0)
    out = eng.render(frames)
    assert isinstance(out, bytes)
    assert len(out) == 2 * frames


def test_render_is_s16le_mono_in_range(core):
    eng = core.Engine(SR, seed=2)
    eng.set_master(1.0)
    eng.set_level("white", 1.0)
    x = pcm(eng.render(SR * 2))[SR:]
    # white noise at TARGET_RMS through the soft limiter: ~-18 dBFS, no clipping
    assert abs(db(rms(x))) < 1.0
    assert np.max(np.abs(x)) < 1 / 1.2 + 1e-3


def test_silence_when_all_levels_zero(core):
    eng = core.Engine(SR, seed=3)
    assert pcm(eng.render(SR)).max() == 0.0
    eng.set_level("rain", 1.0)
    assert rms(pcm(eng.render(SR))) > 0.01
    eng.set_level("rain", 0.0)
    eng.render(2 * SR)  # level smoothing has finished
    assert not np.any(pcm(eng.render(SR)))


def test_level_smoothing_about_half_a_second(core):
    eng = core.Engine(SR, seed=4)
    eng.set_master(1.0)
    eng.set_level("pink", 1.0)
    first = pcm(eng.render(SR // 50))  # 20 ms
    eng.render(SR // 2)
    steady = pcm(eng.render(SR))
    assert rms(first) < 0.5 * rms(steady)


def test_master_ramp(core):
    eng = core.Engine(SR, seed=5)
    eng.set_master(0.0)
    assert eng.master == 0.0
    eng.set_master(1.0, ramp_s=4.0)
    eng.render(2 * SR)
    assert eng.master == pytest.approx(0.5, abs=0.01)
    eng.render(3 * SR)
    assert eng.master == 1.0
    eng.set_level("pink", 1.0)
    eng.set_master(0.0)
    eng.render(SR)
    assert not np.any(pcm(eng.render(SR)))


# ------------------------------------------------------------------ alarm
@pytest.mark.parametrize("tone", ALARM_TONES)
def test_alarm_rings_and_stops_after_duration(core, tone):
    eng = core.Engine(SR, seed=6)
    eng.start_alarm(tone, 3.0, 0.8, ramp_s=1.0)
    assert eng.alarm_ringing is True
    x = pcm(eng.render(int(2.9 * SR)))
    assert rms(x) > 0.01  # audible although every level is 0
    assert eng.alarm_ringing is True
    eng.render(int(0.2 * SR))
    assert eng.alarm_ringing is False
    assert not np.any(pcm(eng.render(SR)))


def test_alarm_ramp_and_stop(core):
    eng = core.Engine(SR, seed=7)
    eng.start_alarm("classic", 600, 1.0)  # default ramp 40 s
    early = rms(pcm(eng.render(3 * SR)))
    eng.render(40 * SR)
    late = rms(pcm(eng.render(3 * SR)))
    assert late > 3 * early  # 15 % -> 100 %
    eng.stop_alarm()
    assert eng.alarm_ringing is False
    eng.render(SR // 10)
    assert not np.any(pcm(eng.render(SR)))


def test_alarm_on_top_of_sounds(core):
    eng = core.Engine(SR, seed=8)
    eng.set_level("rain", 0.5)
    eng.render(SR)
    base = rms(pcm(eng.render(2 * SR)))
    eng.start_alarm("bells", 60, 1.0, ramp_s=0.0)
    assert rms(pcm(eng.render(2 * SR))) > 2 * base


# ------------------------------------------------------------------ determinism
def _take(core, seed):
    eng = core.Engine(SR, seed=seed)
    for s in ("rain", "waves", "thunder", "birds"):
        eng.set_level(s, 0.8)
    eng.start_alarm("birds", 2.0, 0.5, 1.0)
    return b"".join(eng.render(2205) for _ in range(80))


def test_determinism_with_seed(core):
    a, b, c = _take(core, 123), _take(core, 123), _take(core, 124)
    assert a == b
    assert a != c


def test_unseeded_engines_differ(core):
    e1, e2 = core.Engine(SR), core.Engine(SR)
    for e in (e1, e2):
        e.set_level("white", 1.0)
    assert e1.render(4410) != e2.render(4410)


# ------------------------------------------------------------------ loudness parity
DURATION = {"thunder": 240.0, "birds": 90.0}
SEEDS = {"thunder": 3, "birds": 2}


def _ref_rms(ref, name, seed, seconds):
    """Per-channel RMS of the reference (stereo) engine; TARGET_RMS is per channel."""
    eng = ref.Engine(sr=SR, sources=[name], seed=seed, fade_in_s=0.01)
    eng.set_master(1.0)
    eng.set_level(name, 1.0)
    eng.play()
    eng.render(SR)
    x = np.concatenate([eng.render(4096) for _ in range(int(seconds * SR / 4096))])
    return float(np.mean(np.square(x)))


def _rust_rms(core, name, seed, seconds):
    eng = core.Engine(SR, seed=seed)
    eng.set_master(1.0)
    eng.set_level(name, 1.0)
    eng.render(SR)
    return float(np.mean(np.square(pcm(eng.render(int(seconds * SR))))))


@pytest.mark.parametrize("name", SOUNDS)
def test_rms_matches_reference_within_3db(core, ref, name):
    seconds = DURATION.get(name, 20.0)
    seeds = range(SEEDS.get(name, 3))
    r = np.sqrt(np.mean([_ref_rms(ref, name, s, seconds) for s in seeds]))
    c = np.sqrt(np.mean([_rust_rms(core, name, s, seconds) for s in seeds]))
    diff = db(c) - db(r)
    print(f"{name}: reference {db(r):+.2f} dB, rust {db(c):+.2f} dB re TARGET_RMS, diff {diff:+.2f} dB")
    assert abs(diff) <= 3.0


# ------------------------------------------------------------------ threads / speed
def test_control_from_other_thread_while_rendering(core):
    eng = core.Engine(SR, seed=9)
    stop = threading.Event()
    errors = []

    def renderer():
        try:
            while not stop.is_set():
                assert len(eng.render(2205)) == 4410
        except Exception as e:  # pragma: no cover
            errors.append(e)

    t = threading.Thread(target=renderer)
    t.start()
    try:
        for i in range(300):
            eng.set_level(SOUNDS[i % 12], (i % 7) / 7)
            eng.set_master((i % 5) / 5, 0.1)
            _ = eng.levels(), eng.master, eng.alarm_ringing
    finally:
        stop.set()
        t.join()
    assert not errors


def test_fast_enough_for_real_time(core):
    eng = core.Engine(SR, seed=10)
    for s in ("rain", "waves", "wind", "birds"):
        eng.set_level(s, 0.8)
    eng.render(SR)
    t0 = time.perf_counter()
    for _ in range(200):  # 10 s of audio
        eng.render(2205)
    share = (time.perf_counter() - t0) / 10.0
    # contract target: < 5 % of a core in Rust; generous margin for slow CI runners
    assert share < 0.10, f"{share:.1%} of one core"
