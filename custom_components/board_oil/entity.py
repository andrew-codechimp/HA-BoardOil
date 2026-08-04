"""Board Oil Entity class."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import BoardOilDataUpdateCoordinator


class BoardOilEntity(CoordinatorEntity[BoardOilDataUpdateCoordinator]):
    """BoardOilEntity class."""

    def __init__(self, coordinator: BoardOilDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
