"""Pure-Python fallback engine: API shape and basic behaviour."""

from __future__ import annotations

import numpy as np
import pytest

from custom_components.dusk_dawn.engine import ALARM_TONES, SOUNDS, Engine


def _pcm(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype="<i2")


def test_api_shape() -> None:
    engine = Engine(44100, seed=1)
    assert engine.rate == 44100
    assert engine.sounds() == SOUNDS
    assert SOUNDS == ["rain", "waves", "stream", "wind", "thunder", "birds",
                      "leaves", "fire", "fan", "white", "pink", "brown"]
    assert ALARM_TONES == ["bells", "classic", "birds"]
    assert engine.levels() == dict.fromkeys(SOUNDS, 0.0)
    assert engine.alarm_ringing is False


def test_silence_is_zero_and_sized() -> None:
    engine = Engine(seed=1)
    out = engine.render(2205)
    assert isinstance(out, bytes)
    assert len(out) == 2 * 2205
    assert not any(out)
    assert engine.render(0) == b""


@pytest.mark.parametrize("sound", SOUNDS)
def test_every_sound_renders(sound: str) -> None:
    engine = Engine(44100, seed=2)
    engine.set_level(sound, 0.8)
    assert engine.wait_ready(60)
    assert engine.levels()[sound] == 0.8
    # thunder/birds are sparse events: render long enough for the first one
    seconds = {"thunder": 21, "birds": 6}.get(sound, 1)
    pcm = np.concatenate([_pcm(engine.render(2205)) for _ in range(seconds * 20)])
    assert pcm.shape == (seconds * 20 * 2205,)
    assert np.abs(pcm).max() > 100
    assert np.abs(pcm).max() < 32767  # soft limiter keeps it below clipping


def test_level_smoothing_and_master_ramp() -> None:
    engine = Engine(seed=3)
    engine.set_level("white", 1.0)
    engine.wait_ready(10)
    first = _pcm(engine.render(441))
    later = np.concatenate([_pcm(engine.render(2205)) for _ in range(20)])
    assert np.abs(first).mean() < np.abs(later[-2205:]).mean()  # fades in, no click

    assert engine.master == 0.6  # default, same as the Rust core
    engine.set_master(1.0)
    engine.set_master(0.0, ramp_s=1.0)
    assert engine.master == 1.0
    engine.render(22050)
    assert 0.4 < engine.master < 0.6  # linear ramp, half way
    engine.render(44100)
    assert engine.master == 0.0
    tail = _pcm(engine.render(2205))
    assert np.abs(tail).max() == 0

    engine.set_master(0.7)
    assert engine.master == 0.7


@pytest.mark.parametrize("tone", ALARM_TONES)
def test_alarm(tone: str) -> None:
    engine = Engine(seed=4)
    engine.start_alarm(tone, seconds=1.0, volume=1.0, ramp_s=0.0)
    assert engine.alarm_ringing
    pcm = np.concatenate([_pcm(engine.render(4410)) for _ in range(9)])
    assert np.abs(pcm).max() > 1000
    engine.render(4410 * 2)
    assert not engine.alarm_ringing  # stops by itself after ``seconds``

    engine.start_alarm(tone, 60, 0.5)
    engine.stop_alarm()
    assert not engine.alarm_ringing
