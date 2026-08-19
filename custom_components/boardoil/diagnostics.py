"""Diagnostics support for the BoardOil integration."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .data import BoardOilConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: BoardOilConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data

    return {
        "boardoil_version": data.version,
        "boardoil_build": data.build,
        "boards": [asdict(board) for board in data.coordinator.boards],
    }
