"""Define events for the board_oil integration."""

import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.event import EventEntity
from homeassistant.const import ATTR_ID, ATTR_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    EVENT_TYPE_CARD_CREATED,
    EVENT_TYPE_CARD_MOVED,
    EVENT_TYPE_CARD_REMOVED,
    EVENT_TYPE_CARD_UPDATED,
)
from .coordinator import BoardData, BoardOilDataUpdateCoordinator, BoardOilEventData
from .data import BoardOilConfigEntry
from .entity import BoardOilEntity

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
        super().__init__(coordinator, board)
        self.key = "card"
        self.translation_key = "card"
        self.icon = "mdi:card-outline"
        self.event_types = [
            EVENT_TYPE_CARD_CREATED,
            EVENT_TYPE_CARD_MOVED,
            EVENT_TYPE_CARD_REMOVED,
            EVENT_TYPE_CARD_UPDATED,
        ]
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{board.id}_card_event"
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if TYPE_CHECKING:
            assert self._attr_unique_id

        self.async_on_remove(
            self.coordinator.async_add_event_listener(self._handle_event, self.board_id)
        )

    @callback
    def _handle_event(self, event_data: BoardOilEventData) -> None:
        """Handle the torrent events."""
        if event_data.board_id != self.board_id:
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
                "card_type_id": event_data.card_type_id,
                "card_type_name": event_data.card_type_name,
                "column_id": event_data.column_id,
                "column_name": event_data.column_name,
                "tags": event_data.tag_names,
            },
        )

        self.async_write_ha_state()
