"""Sensor platform for boardoil."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import ColumnData
from .entity import BoardOilEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BoardData, BoardOilDataUpdateCoordinator
    from .data import BoardOilConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BoardOilConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator
    entity_registry = er.async_get(hass)

    entities = {
        entity.key: entity for entity in _create_entities(coordinator, coordinator.data)
    }

    async_add_entities(list(entities.values()))

    @callback
    def _async_sync_entities() -> None:
        latest_keys = {
            _build_entity_key(board_name=board.name, column_name=column.title)
            for board in coordinator.data
            for column in board.columns
        }
        existing_keys = set(entities)

        added_keys = latest_keys - existing_keys
        if added_keys:
            new_entities = [
                entity
                for entity in _create_entities(coordinator, coordinator.data)
                if entity.key in added_keys
            ]
            for entity in new_entities:
                entities[entity.key] = entity
            async_add_entities(new_entities)

        removed_keys = existing_keys - latest_keys
        for key in removed_keys:
            entity = entities.pop(key)
            entity_id = entity_registry.async_get_entity_id(
                SENSOR_DOMAIN,
                DOMAIN,
                entity.unique_id,
            )
            if entity_id:
                entity_registry.async_remove(entity_id)

    entry.async_on_unload(coordinator.async_add_listener(_async_sync_entities))


def _build_entity_key(board_name: str, column_name: str) -> str:
    """Build a stable key for a board and column pair."""
    return f"{slugify(board_name)}::{slugify(column_name)}"


def _create_entities(
    coordinator: BoardOilDataUpdateCoordinator,
    boards: list[BoardData],
) -> list[BoardOilColumnCardCountSensor]:
    """Create sensors for all board columns."""
    return [
        BoardOilColumnCardCountSensor(
            coordinator=coordinator,
            board_name=board.name,
            column_name=column.title,
        )
        for board in boards
        for column in board.columns
    ]


class BoardOilColumnCardCountSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of cards for a board column."""

    _unrecorded_attributes = frozenset({"cards"})

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board_name: str,
        column_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.has_entity_name = True
        self._board_name = board_name
        self._column_name = column_name
        self.key = _build_entity_key(board_name=board_name, column_name=column_name)
        self.icon = "mdi:table-column"
        self._attr_name = f"{board_name} - {column_name}"
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_"
            f"{slugify(board_name)}_{slugify(column_name)}_card_count"
        )
        self._attr_native_unit_of_measurement = "cards"

    @property
    def native_value(self) -> int:
        """Return the number of cards in this column."""
        return len(self._get_board_and_column()[2].cards)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        board_id, board_name, column = self._get_board_and_column()
        return {
            "board_id": board_id,
            "board_name": board_name,
            "column_id": column.id,
            "column_title": column.title,
            "cards": [
                {
                    "id": card.id,
                    "card_type_name": card.card_type_name,
                    "title": card.title,
                }
                for card in column.cards
            ],
        }

    def _get_board_and_column(self) -> tuple[int, str, ColumnData]:
        """Get latest board and column data from coordinator."""
        for board in self.coordinator.data:
            if board.name != self._board_name:
                continue
            for column in board.columns:
                if column.title == self._column_name:
                    return board.id, board.name, column

        return 0, self._board_name, ColumnData(id=0, title=self._column_name, cards=[])
