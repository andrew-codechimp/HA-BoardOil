"""Define events for the board_oil integration."""

import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.const import ATTR_ID, ATTR_NAME, CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    EVENT_TYPE_CARD_CREATED,
    EVENT_TYPE_CARD_MOVED,
    EVENT_TYPE_CARD_REMOVED,
    EVENT_TYPE_CARD_UPDATED,
)
from .coordinator import BoardOilDataUpdateCoordinator, BoardOilEventData
from .data import BoardOilConfigEntry
from .entity import BoardOilEntity

if TYPE_CHECKING:
    from .coordinator import BoardData

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    config_entry: BoardOilConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the BoardOil event platform."""
    coordinator = config_entry.runtime_data.coordinator

    entities = [BoardOilEvent(coordinator, board) for board in coordinator.data]
    async_add_entities(entities)


class BoardOilEvent(BoardOilEntity, EventEntity):
    """Representation of a BoardOil event entity."""

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._board_id = board.id
        self._board_name = board.name
        self.has_entity_name = True
        self.entity_description = EventEntityDescription(
            key="card",
            translation_key="card",
            event_types=[
                EVENT_TYPE_CARD_CREATED,
                EVENT_TYPE_CARD_MOVED,
                EVENT_TYPE_CARD_REMOVED,
                EVENT_TYPE_CARD_UPDATED,
            ],
        )
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{board.id}_card_event"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}:{board.id}")},
            entry_type=DeviceEntryType.SERVICE,
            name=f"Board Oil - {board.name}",
            sw_version=(
                f"{coordinator.config_entry.runtime_data.version} "
                f"({coordinator.config_entry.runtime_data.build})"
            ),
            configuration_url=(
                f"{coordinator.config_entry.data[CONF_HOST].rstrip('/')}/boards/"
                f"{board.id}"
            ),
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if TYPE_CHECKING:
            assert self._attr_unique_id

        self.async_on_remove(
            self.coordinator.async_add_event_listener(
                self._handle_event, self._board_id
            )
        )

    @callback
    def _handle_event(self, event_data: BoardOilEventData) -> None:
        """Handle the torrent events."""
        if event_data.board_id != self._board_id:
            return

        event_type = event_data.event_type

        if event_type not in self.event_types:
            _LOGGER.warning("Event type %s is not known", event_type)
            return

        self._trigger_event(
            event_type,
            {
                ATTR_NAME: event_data.title,
                ATTR_ID: event_data.card_id,
            },
        )

        self.async_write_ha_state()
