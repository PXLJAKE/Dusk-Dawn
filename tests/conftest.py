"""Shared fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config

from custom_components.dusk_dawn.const import DOMAIN

SPOT_DATA: dict[str, Any] = {
    "name": "Bedroom",
    "speakers": ["media_player.bedroom"],
    "lights": ["light.bedside"],
    "presence": "binary_sensor.bedroom_presence",
    "diy_device": None,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom_components/ from the repo."""


@pytest.fixture(autouse=True)
def force_python_engine(request: pytest.FixtureRequest):
    """Use the pure-Python fallback unless a test is marked ``rust_engine``."""
    if request.node.get_closest_marker("rust_engine"):
        yield
        return
    from custom_components.dusk_dawn.engine import Engine  # noqa: PLC0415

    with patch("custom_components.dusk_dawn.load_engine_class", return_value=(Engine, "python")):
        yield


@pytest.fixture
def config_entry() -> MockConfigEntry:
    return MockConfigEntry(domain=DOMAIN, title="Bedroom", data=dict(SPOT_DATA))


@pytest.fixture
def play_media_calls(hass: HomeAssistant) -> list[ServiceCall]:
    async_mock_service(hass, "media_player", "media_stop")
    return async_mock_service(hass, "media_player", "play_media")


@pytest.fixture
def light_calls(hass: HomeAssistant) -> list[ServiceCall]:
    async_mock_service(hass, "light", "turn_off")
    return async_mock_service(hass, "light", "turn_on")


@pytest.fixture
async def setup_spot(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    play_media_calls: list[ServiceCall],
    light_calls: list[ServiceCall],
) -> AsyncGenerator[MockConfigEntry]:
    """A loaded spot; unloaded again after the test (stops encoder threads)."""
    await async_process_ha_core_config(hass, {"internal_url": "http://ha.local:8123"})
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    yield config_entry
    if config_entry.state.recoverable:
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
