"""Custom types for boardoil."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import BoardOilApiClient
    from .coordinator import BoardOilDataUpdateCoordinator


type BoardOilConfigEntry = ConfigEntry[BoardOilData]


@dataclass
class BoardOilData:
    """Data for the BoardOil integration."""

    client: BoardOilApiClient
    coordinator: BoardOilDataUpdateCoordinator
    integration: Integration
