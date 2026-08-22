"""Define events for the boardoil integration."""

import logging
from typing import TYPE_CHECKING, override

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    ATTR_CARD_ID,
    ATTR_CARD_TYPE_ID,
    ATTR_CARD_TYPE_NAME,
    ATTR_COLUMN_ID,
    ATTR_COLUMN_NAME,
    ATTR_SLICK_NAME,
    ATTR_TAG_NAMES,
    ATTR_TITLE,
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
                ATTR_TITLE: event_data.title,
                ATTR_CARD_ID: event_data.card_id,
                ATTR_CARD_TYPE_ID: event_data.card_type_id,
                ATTR_CARD_TYPE_NAME: event_data.card_type_name,
                ATTR_COLUMN_ID: event_data.column_id,
                ATTR_COLUMN_NAME: event_data.column_name,
                ATTR_TAG_NAMES: event_data.tag_names,
                ATTR_SLICK_NAME: event_data.slick_name,
            },
        )

        self.async_write_ha_state()
