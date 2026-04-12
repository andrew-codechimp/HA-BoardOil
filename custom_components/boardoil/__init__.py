"""
Custom integration to integrate boardoil with Home Assistant.

For more details about this integration, please refer to
https://github.com/andrew-codechimp/ha-boardoil
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.loader import async_get_loaded_integration

from .api import BoardOilApiClient
from .const import DOMAIN, LOGGER
from .coordinator import BoardOilDataUpdateCoordinator
from .data import BoardOilData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import BoardOilConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoardOilConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    client = BoardOilApiClient(
        host=entry.data[CONF_HOST],
        api_token=entry.data[CONF_API_TOKEN],
        session=async_get_clientsession(hass),
    )
    try:
        response = await client.async_get_version()
        version = response.get("data", {}).get("version", "")
        build = response.get("data", {}).get("build", "")
    except Exception as exception:
        LOGGER.error("Error connecting to BoardOil API: %s", exception)
        return False

    coordinator = BoardOilDataUpdateCoordinator(
        hass=hass,
        logger=LOGGER,
        name=DOMAIN,
        update_interval=timedelta(hours=1),
    )
    entry.runtime_data = BoardOilData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
        version=version,
        build=build,
    )

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        entry_type=DeviceEntryType.SERVICE,
        sw_version=f"{entry.runtime_data.version} ({entry.runtime_data.build})",
        configuration_url=entry.data[CONF_HOST],
    )

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: BoardOilConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: BoardOilConfigEntry,
) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
