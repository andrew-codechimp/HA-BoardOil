"""Custom integration to integrate boardoil with Home Assistant.

For more details about this integration, please refer to
https://github.com/andrew-codechimp/ha-boardoil
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from awesomeversion.awesomeversion import AwesomeVersion

from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_VERIFY_SSL,
    Platform,
    __version__ as HA_VERSION,  # noqa: N812
)
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_loaded_integration

from .api import BoardOilApiClient, BoardOilApiClientError
from .const import DOMAIN, LOGGER, MIN_HA_VERSION, MIN_REQUIRED_BOARDOIL_VERSION
from .coordinator import BoardOilDataUpdateCoordinator
from .data import BoardOilData
from .services import async_setup_services

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType

    from .data import BoardOilConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.EVENT,
    Platform.SENSOR,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # noqa: ARG001
    """Integration setup."""
    if AwesomeVersion(HA_VERSION) < AwesomeVersion(MIN_HA_VERSION):  # pragma: no cover
        msg = (
            "This integration requires at least Home Assistant version "
            f"{MIN_HA_VERSION}, you are running version {HA_VERSION}. "
            "Please upgrade Home Assistant to continue using this integration."
        )
        _LOGGER.critical(msg)
        return False

    # Register custom services
    await async_setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoardOilConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    client = BoardOilApiClient(
        host=entry.data[CONF_HOST],
        api_token=entry.data[CONF_API_TOKEN],
        session=async_get_clientsession(
            hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True)
        ),
    )
    try:
        response = await client.async_get_version()
        version = response.get("data", {}).get("version", "")
        build = response.get("data", {}).get("build", "")
    except BoardOilApiClientError as exception:
        LOGGER.error("Error connecting to BoardOil API: %s", exception)
        return False

    v = AwesomeVersion(version)
    if v.valid and v < MIN_REQUIRED_BOARDOIL_VERSION:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="version_error",
            translation_placeholders={
                "boardoil_version": version,
                "min_version": MIN_REQUIRED_BOARDOIL_VERSION,
            },
        )

    coordinator = BoardOilDataUpdateCoordinator(hass, entry)
    entry.runtime_data = BoardOilData(
        client=client,
        integration=async_get_loaded_integration(hass, entry.domain),
        coordinator=coordinator,
        version=version,
        build=build,
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
