"""boardoil Entity class."""

from __future__ import annotations

from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoardData, BoardOilDataUpdateCoordinator


class BoardOilEntity(CoordinatorEntity[BoardOilDataUpdateCoordinator]):
    """BoardOilEntity class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.board_id = board.id
        self.board_name = board.name

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}:{board.id}")},
            entry_type=DeviceEntryType.SERVICE,
            name=f"BoardOil - {board.name}",
            sw_version=(
                f"{coordinator.config_entry.runtime_data.version} "
                f"({coordinator.config_entry.runtime_data.build})"
            ),
            configuration_url=(
                f"{coordinator.config_entry.data[CONF_HOST].rstrip('/')}/boards/"
                f"{board.id}"
            ),
        )
