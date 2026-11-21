"""Stream view: token check, MP3 output."""

from __future__ import annotations

import shutil
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from homeassistant.core import HomeAssistant

from custom_components.dusk_dawn.stream import SpotStream

HAVE_FFMPEG = shutil.which("ffmpeg") is not None


def _fake_encoder(self: SpotStream) -> list[str]:
    """Without ffmpeg: pass the PCM through unchanged (still exercises the pipeline)."""
    return ["cat"]


@pytest.fixture(autouse=True)
def maybe_mock_ffmpeg():
    if HAVE_FFMPEG:
        yield
        return
    with patch.object(SpotStream, "encoder_command", _fake_encoder):
        yield


async def test_stream_valid_token(
    hass: HomeAssistant, setup_spot: MockConfigEntry, hass_client_no_auth: ClientSessionGenerator
) -> None:
    rt = setup_spot.runtime_data
    await rt.async_play(preset="white_noise")
    stream = rt.stream
    client = await hass_client_no_auth()
    resp = await client.get(stream.path)
    assert resp.status == 200
    assert resp.headers["Content-Type"] == "audio/mpeg"
    data = b""
    while len(data) < 8192:
        chunk = await resp.content.read(4096)
        assert chunk, "stream ended"
        data += chunk
    if HAVE_FFMPEG:
        # MP3 frame sync (11 set bits) somewhere in the first bytes
        assert any(data[i] == 0xFF and data[i + 1] & 0xE0 == 0xE0 for i in range(len(data) - 1))
    assert stream.running
    assert stream.client_count == 1
    resp.close()

    # a new play session rotates the token; the old URL stops working
    old_path = stream.path
    await rt.async_stop()
    await rt.async_play()
    assert stream.path != old_path
    resp = await client.get(old_path)
    assert resp.status == 401

    await hass.config_entries.async_unload(setup_spot.entry_id)
    await hass.async_block_till_done()
    assert not stream.running


async def test_stream_wrong_token(
    hass: HomeAssistant, setup_spot: MockConfigEntry, hass_client_no_auth: ClientSessionGenerator
) -> None:
    client = await hass_client_no_auth()
    entry_id = setup_spot.entry_id
    resp = await client.get(f"/api/dusk_dawn/stream/{entry_id}.mp3?token=wrong")
    assert resp.status == 401
    resp = await client.get(f"/api/dusk_dawn/stream/{entry_id}.mp3")
    assert resp.status == 401
    resp = await client.get("/api/dusk_dawn/stream/unknown.mp3?token=x")
    assert resp.status == 404
    assert not setup_spot.runtime_data.stream.running


@pytest.mark.rust_engine
async def test_stream_with_rust_core(
    hass: HomeAssistant, setup_spot: MockConfigEntry, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Same pipeline with the optional Rust engine, if it is installed."""
    pytest.importorskip("dusk_dawn_core")
    rt = setup_spot.runtime_data
    assert type(rt.engine.inner).__module__.startswith("dusk_dawn_core")
    await rt.async_play(preset="regen")
    client = await hass_client_no_auth()
    resp = await client.get(rt.stream.path)
    assert resp.status == 200
    data = b""
    while len(data) < 8192:
        chunk = await resp.content.read(4096)
        assert chunk
        data += chunk
    resp.close()
    await hass.config_entries.async_unload(setup_spot.entry_id)
    await hass.async_block_till_done()
