"""Tests for the dusk_dawn_core Python module against the contract
(integration/CONTRACT.md section 1) and the Python reference generators.

References are loaded from git history, so they stay fixed while device/
changes (this needs the full history, e.g. ``fetch-depth: 0`` in CI):

* white, pink, brown, fan, rain, wind, waves, fire, thunder: the original
  generators, ``device/sleepgen/dsp.py`` at commit 73c0381 (scipy biquads).
  Rust must match their loudness within 3 dB and their spectral centroid
  within 15 %.
* birds, leaves, stream: ``device/sleepgen`` at commit 3603211, the design the
  Rust versions were ported from (loudness within 3 dB).

The module is built with ``maturin develop --release`` (inside a virtualenv) or
``pip install`` if it is not importable yet. Set DUSK_DAWN_CORE_NO_BUILD=1 to
skip that step and use whatever is installed.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import os
import shutil
import subprocess
import sys
import tarfile
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


ORIGINAL_COMMIT = "73c0381"  # the original sound design (before the grain rework)
GRAIN_COMMIT = "3603211"  # birds, leaves and stream as ported to Rust
ORIGINAL_SOUNDS = ["white", "pink", "brown", "fan", "rain", "wind", "waves", "fire", "thunder"]
GRAIN_SOUNDS = ["birds", "leaves", "stream"]


def _git(*args: str) -> bytes:
    if not shutil.which("git"):
        pytest.skip("git not available")
    try:
        return subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True).stdout
    except subprocess.CalledProcessError as e:  # shallow clone without that commit
        pytest.skip(f"git {' '.join(args)} failed: {e.stderr.decode(errors='replace').strip()}")


@pytest.fixture(scope="session")
def orig(tmp_path_factory):
    """``dsp.py`` of commit 73c0381 as a throwaway module."""
    pytest.importorskip("scipy")
    path = tmp_path_factory.mktemp("orig") / "orig_dsp.py"
    path.write_bytes(_git("show", f"{ORIGINAL_COMMIT}:device/sleepgen/dsp.py"))
    spec = importlib.util.spec_from_file_location("orig_dsp_73c0381", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses look the module up
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def ref(tmp_path_factory):
    """The ``device/sleepgen`` engine of commit 3603211 (birds, leaves, stream)."""
    pytest.importorskip("scipy")
    root = tmp_path_factory.mktemp("ref")
    tar = root / "src.tar"
    tar.write_bytes(_git("archive", "--format=tar", GRAIN_COMMIT, "device/sleepgen"))
    with tarfile.open(tar) as tf:
        tf.extractall(root, filter="data")
    saved = {k: v for k, v in sys.modules.items() if k == "sleepgen" or k.startswith("sleepgen.")}
    for k in saved:
        del sys.modules[k]
    sys.path.insert(0, str(root / "device"))
    try:
        from sleepgen import engine  # noqa: PLC0415

        yield engine
    finally:
        sys.path.remove(str(root / "device"))


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


# ------------------------------------------------------------------ parity with the references
DURATION = {"thunder": 240.0, "birds": 90.0}
SEEDS = {"thunder": 3, "birds": 2}
BLOCK = 4096


def _limit(x):
    """The engines' soft limiter, so both sides are compared after it."""
    return np.tanh(x * 1.2) / 1.2


def _power_spectrum(x, nfft=8192):
    win = np.hanning(nfft)
    frames = len(x) // nfft
    if frames == 0:
        return np.zeros(nfft // 2 + 1)
    segs = x[: frames * nfft].reshape(frames, nfft) * win
    return np.sum(np.abs(np.fft.rfft(segs, axis=1)) ** 2, axis=0)


def _centroid(spec):
    f = np.fft.rfftfreq(2 * (len(spec) - 1), 1 / SR)
    return float(np.sum(f * spec) / max(np.sum(spec), 1e-30))


def _orig_take(orig, name, seed, seconds):
    """Left channel of the original generator (TARGET_RMS is per channel)."""
    gen = orig.GENERATORS[name](SR, seed)
    gen.render(SR)  # skip the first second, like the engine side
    x = np.concatenate([gen.render(BLOCK)[:, 0] for _ in range(int(seconds * SR / BLOCK))])
    return _limit(x)


def _rust_take(core, name, seed, seconds):
    eng = core.Engine(SR, seed=seed)
    eng.set_master(1.0)
    eng.set_level(name, 1.0)
    eng.render(SR)  # level smoothing
    return pcm(eng.render(int(seconds * SR)))


def _ref_rms(ref, name, seed, seconds):
    """Per-channel mean square of the (stereo) reference engine."""
    eng = ref.Engine(sr=SR, sources=[name], seed=seed, fade_in_s=0.01)
    eng.set_master(1.0)
    eng.set_level(name, 1.0)
    eng.play()
    eng.render(SR)
    x = np.concatenate([eng.render(BLOCK) for _ in range(int(seconds * SR / BLOCK))])
    return float(np.mean(np.square(x)))


@pytest.mark.parametrize("name", ORIGINAL_SOUNDS)
def test_matches_original_sound(core, orig, name):
    """Loudness within 3 dB and spectral centroid within 15 % of the original."""
    seconds = DURATION.get(name, 20.0)
    seeds = range(SEEDS.get(name, 3))
    ms_o, ms_c = [], []
    spec_o, spec_c = 0.0, 0.0
    for s in seeds:
        xo, xc = _orig_take(orig, name, s, seconds), _rust_take(core, name, s, seconds)
        ms_o.append(np.mean(xo**2))
        ms_c.append(np.mean(xc**2))
        spec_o = spec_o + _power_spectrum(xo)
        spec_c = spec_c + _power_spectrum(xc)
    r, c = np.sqrt(np.mean(ms_o)), np.sqrt(np.mean(ms_c))
    diff = db(c) - db(r)
    co, cc = _centroid(spec_o), _centroid(spec_c)
    print(
        f"{name}: original {db(r):+.2f} dB, rust {db(c):+.2f} dB re TARGET_RMS, diff {diff:+.2f} dB; "
        f"centroid original {co:.0f} Hz, rust {cc:.0f} Hz ({100 * (cc / co - 1):+.1f} %)"
    )
    assert abs(diff) <= 3.0
    assert abs(cc / co - 1) <= 0.15


@pytest.mark.parametrize("name", GRAIN_SOUNDS)
def test_rms_matches_reference_within_3db(core, ref, name):
    seconds = DURATION.get(name, 20.0)
    seeds = range(SEEDS.get(name, 3))
    r = np.sqrt(np.mean([_ref_rms(ref, name, s, seconds) for s in seeds]))
    c = np.sqrt(np.mean([np.mean(_rust_take(core, name, s, seconds) ** 2) for s in seeds]))
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
