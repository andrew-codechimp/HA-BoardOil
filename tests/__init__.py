"""Tests for the BoardOil integration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.core import HomeAssistant

HOST = "https://boardoil.example"
API_TOKEN = "test-api-token"  # noqa: S105
ENTRY_ID = "boardoil-entry"
UNIQUE_ID = "https-boardoil-example-7"
COLUMN_ENTITY_ID = "sensor.boardoil_work_to_do"
EVENT_ENTITY_ID = "event.boardoil_work_card"


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration from a config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
