"""Config and options flow."""

from __future__ import annotations

from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.dusk_dawn.const import DOMAIN

from .conftest import SPOT_DATA


async def test_user_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("custom_components.dusk_dawn.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": " Bedroom ", "speakers": ["media_player.bedroom"], "lights": ["light.bedside"]},
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bedroom"
    assert result["data"] == {
        "name": "Bedroom",
        "speakers": ["media_player.bedroom"],
        "lights": ["light.bedside"],
        "presence": None,
        "diy_device": None,
    }


async def test_user_flow_empty_name(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "  "})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"name": "name_required"}


async def test_duplicate_name_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, title="Bedroom", data=dict(SPOT_DATA)).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Bedroom"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="Bedroom", data=dict(SPOT_DATA))
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    with patch("custom_components.dusk_dawn.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"name": "Guest room", "speakers": ["media_player.guest"], "diy_device": "sleepgen"},
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        "name": "Guest room",
        "speakers": ["media_player.guest"],
        "lights": [],
        "presence": None,
        "diy_device": "sleepgen",
    }
