"""Sensor platform for board_oil."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, LOGGER
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
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    entities = {
        entity.key: entity for entity in _create_entities(coordinator, coordinator.data)
    }

    async_add_entities(list(entities.values()))

    @callback
    def _async_sync_entities() -> None:
        expected_board_identifiers = {
            f"{entry.entry_id}:{board.id}" for board in coordinator.data
        }
        latest_keys = {
            _build_entity_key(board_id=board.id, column_id=column.id)
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
            if entity.unique_id is None:
                continue
            entity_id = entity_registry.async_get_entity_id(
                SENSOR_DOMAIN,
                DOMAIN,
                entity.unique_id,
            )
            if entity_id:
                entity_registry.async_remove(entity_id)

        # Remove devices for boards that no longer exist in coordinator data.
        for device in dr.async_entries_for_config_entry(
            device_registry,
            entry.entry_id,
        ):
            device_identifiers = {
                identifier
                for device_domain, identifier in device.identifiers
                if device_domain == DOMAIN
            }
            if not device_identifiers:
                continue

            if device_identifiers & expected_board_identifiers:
                continue

            for entity_entry in er.async_entries_for_device(
                entity_registry,
                device.id,
                include_disabled_entities=True,
            ):
                LOGGER.debug(
                    "Removing orphaned Board Oil entity %s from device %s",
                    entity_entry.entity_id,
                    device.id,
                )
                entity_registry.async_remove(entity_entry.entity_id)

            LOGGER.debug(
                "Removing orphaned Board Oil device %s identifiers=%s",
                device.id,
                sorted(device_identifiers),
            )
            device_registry.async_remove_device(device.id)

    # Run once on setup so orphan cleanup happens immediately, not only on refresh.
    _async_sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_sync_entities))


def _build_entity_key(board_id: int, column_id: int) -> str:
    """Build a stable key for a board and column pair."""
    return f"{board_id}:{column_id}"


def _create_entities(
    coordinator: BoardOilDataUpdateCoordinator,
    boards: list[BoardData],
) -> list[BoardOilColumnCardCountSensor]:
    """Create sensors for all board columns."""
    return [
        BoardOilColumnCardCountSensor(
            coordinator=coordinator,
            board=board,
            column=column,
        )
        for board in boards
        for column in board.columns
    ]


class BoardOilColumnCardCountSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of cards for a board column."""

    _unrecorded_attributes = frozenset(
        {"board_id", "board_name", "column_id", "column_title", "cards"}
    )

    @property
    def board_name(self) -> str:
        """Return the board name for entity-id migration."""
        return self._board_name

    @property
    def column_name(self) -> str:
        """Return the column name for entity-id migration."""
        return self._column_name

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
        column: ColumnData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.has_entity_name = True
        self._board_id = board.id
        self._board_name = board.name
        self._column_id = column.id
        self._column_name = column.title
        self.key = _build_entity_key(board_id=board.id, column_id=column.id)
        self.icon = "mdi:table-column"
        self._attr_name = column.title
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{board.id}_{column.id}_card_count"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.config_entry.entry_id}:{board.id}")},
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
                    "card_type_id": card.card_type_id,
                    "card_type_name": card.card_type_name,
                    "title": card.title,
                }
                for card in column.cards
            ],
        }

    def _get_board_and_column(self) -> tuple[int, str, ColumnData]:
        """Get latest board and column data from coordinator."""
        for board in self.coordinator.data:
            if board.id != self._board_id:
                continue
            for column in board.columns:
                if column.id == self._column_id:
                    return board.id, board.name, column

        return (
            self._board_id,
            self._board_name,
            ColumnData(
                id=self._column_id,
                title=self._column_name,
                cards=[],
            ),
        )
