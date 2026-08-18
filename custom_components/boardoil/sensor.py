"""Sensor platform for boardoil."""

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import BoardData, BoardOilDataUpdateCoordinator, ColumnData
from .data import BoardOilConfigEntry
from .entity import BoardOilEntity


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
            _build_column_entity_key(board_id=board.id, column_id=column.id)
            for board in coordinator.data
            for column in board.columns
        }
        latest_keys.update(
            {
                _build_card_types_entity_key(board_id=board.id)
                for board in coordinator.data
            }
        )
        latest_keys.update(
            {_build_tags_entity_key(board_id=board.id) for board in coordinator.data}
        )
        latest_keys.update(
            {_build_slicks_entity_key(board_id=board.id) for board in coordinator.data}
        )
        latest_keys.update(
            {_build_members_entity_key(board_id=board.id) for board in coordinator.data}
        )
        existing_keys = set(entities)

        added_keys = latest_keys - existing_keys
        if added_keys:
            new_entities = [
                entity
                for entity in _create_entities(coordinator, coordinator.data)
                if entity.key in added_keys  # type: ignore[attr-defined]
            ]
            for entity in new_entities:
                entities[entity.key] = entity  # type: ignore[attr-defined]

        removed_keys = existing_keys - latest_keys
        for key in removed_keys:
            entity = entities.pop(key)

            # Ensure deleted columns are removed from state immediately.
            if entity.hass is not None:
                hass.async_create_task(entity.async_remove(force_remove=True))

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
                    "Removing orphaned BoardOil entity %s from device %s",
                    entity_entry.entity_id,
                    device.id,
                )
                entity_registry.async_remove(entity_entry.entity_id)

            LOGGER.debug(
                "Removing orphaned BoardOil device %s identifiers=%s",
                device.id,
                sorted(device_identifiers),
            )
            device_registry.async_remove_device(device.id)

    # Run once on setup so orphan cleanup happens immediately, not only on refresh.
    _async_sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_sync_entities))


def _build_column_entity_key(board_id: int, column_id: int) -> str:
    """Build a stable key for a board and column pair."""
    return f"column:{board_id}:{column_id}"


def _build_card_types_entity_key(board_id: int) -> str:
    """Build a stable key for a board's card types."""
    return f"card_types:{board_id}"


def _build_tags_entity_key(board_id: int) -> str:
    """Build a stable key for a board's tags."""
    return f"tags:{board_id}"


def _build_slicks_entity_key(board_id: int) -> str:
    """Build a stable key for a board's slicks."""
    return f"slicks:{board_id}"


def _build_members_entity_key(board_id: int) -> str:
    """Build a stable key for a board's members."""
    return f"members:{board_id}"


def _create_entities(
    coordinator: BoardOilDataUpdateCoordinator,
    boards: list[BoardData],
) -> list[BoardOilEntity]:
    """Create sensors for all board columns and card types."""
    entities: list[BoardOilEntity] = []

    # Add column sensors
    entities.extend(
        [
            BoardOilColumnCardCountSensor(
                coordinator=coordinator,
                board=board,
                column=column,
            )
            for board in boards
            for column in board.columns
        ]
    )

    # Add card type sensors
    entities.extend(
        [
            BoardOilCardTypesSensor(
                coordinator=coordinator,
                board=board,
            )
            for board in boards
        ]
    )

    # Add tags sensors
    entities.extend(
        [
            BoardOilTagsSensor(
                coordinator=coordinator,
                board=board,
            )
            for board in boards
        ]
    )

    # Add slicks sensors
    entities.extend(
        [
            BoardOilSlicksSensor(
                coordinator=coordinator,
                board=board,
            )
            for board in boards
        ]
    )

    # Add members sensors
    entities.extend(
        [
            BoardOilMembersSensor(
                coordinator=coordinator,
                board=board,
            )
            for board in boards
        ]
    )

    return entities


class BoardOilColumnCardCountSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of cards for a board column."""

    _unrecorded_attributes = frozenset(
        {
            "board_id",
            "board_name",
            "column_id",
            "column_title",
            "cards",
        }
    )

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
        super().__init__(coordinator, board)
        self._column_id = column.id
        self._column_name = column.title
        self.key = _build_column_entity_key(board_id=board.id, column_id=column.id)
        self.icon = "mdi:table-column"
        self._attr_name = column.title
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{board.id}_{column.id}_card_count"
        )
        self._attr_translation_key = "card_count"

    @property
    def native_value(self) -> int:
        """Return the number of cards in this column."""
        return len(self._get_board_and_column()[2].cards)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_metadata_from_latest_data()
        super()._handle_coordinator_update()

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
            if board.id != self.board_id:
                continue
            for column in board.columns:
                if column.id == self._column_id:
                    return board.id, board.name, column

        return (
            self.board_id,
            self.board_name,
            ColumnData(
                id=self._column_id,
                title=self._column_name,
                cards=[],
            ),
        )

    def _sync_metadata_from_latest_data(self) -> None:
        """Sync entity metadata fields from the latest coordinator data."""
        _, board_name, column = self._get_board_and_column()
        self.board_name = board_name

        if self._column_name != column.title:
            self._column_name = column.title
            self._attr_name = column.title


class BoardOilCardTypesSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of card types for a board."""

    _unrecorded_attributes = frozenset(
        {
            "board_id",
            "board_name",
            "card_types",
        }
    )

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, board)
        self.key = _build_card_types_entity_key(board_id=board.id)
        self._attr_translation_key = "card_types"
        self._attr_name = "Card Types"
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{board.id}_card_types"
        )
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the number of card types."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        if board is None:
            return 0
        return len(board.card_types)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        card_types_list = board.card_types if board else []
        return {
            "board_id": self.board_id,
            "board_name": self.board_name,
            "card_types": [
                {
                    "id": card_type.id,
                    "name": card_type.name,
                }
                for card_type in card_types_list
            ],
        }


class BoardOilTagsSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of tags for a board."""

    _unrecorded_attributes = frozenset(
        {
            "board_id",
            "board_name",
            "tags",
        }
    )

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, board)
        self.key = _build_tags_entity_key(board_id=board.id)
        self._attr_translation_key = "tags"
        self._attr_name = "Tags"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{board.id}_tags"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the number of tags."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        if board is None:
            return 0
        return len(board.tags)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        tag_list = board.tags if board else []
        return {
            "board_id": self.board_id,
            "board_name": self.board_name,
            "tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                }
                for tag in tag_list
            ],
        }


class BoardOilSlicksSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of slicks for a board."""

    _unrecorded_attributes = frozenset(
        {
            "board_id",
            "board_name",
            "slicks",
        }
    )

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, board)
        self.key = _build_slicks_entity_key(board_id=board.id)
        self._attr_translation_key = "slicks"
        self._attr_name = "Slicks"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{board.id}_slicks"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the number of slicks."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        if board is None:
            return 0
        return len(board.slicks)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        slick_list = board.slicks if board else []
        return {
            "board_id": self.board_id,
            "board_name": self.board_name,
            "slicks": [
                {
                    "id": slick.id,
                    "name": slick.name,
                }
                for slick in slick_list
            ],
        }


class BoardOilMembersSensor(BoardOilEntity, SensorEntity):
    """Sensor showing number of members for a board."""

    _unrecorded_attributes = frozenset(
        {
            "board_id",
            "board_name",
            "members",
        }
    )

    def __init__(
        self,
        coordinator: BoardOilDataUpdateCoordinator,
        board: BoardData,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, board)
        self.key = _build_members_entity_key(board_id=board.id)
        self._attr_translation_key = "members"
        self._attr_name = "Members"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{board.id}_members"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int:
        """Return the number of members."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        if board is None:
            return 0
        return len(board.members)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        board = next(
            (b for b in self.coordinator.data if b.id == self.board_id),
            None,
        )
        member_list = board.members if board else []
        return {
            "board_id": self.board_id,
            "board_name": self.board_name,
            "members": [
                {
                    "id": member.id,
                    "username": member.username,
                    "display_name": member.display_name,
                }
                for member in member_list
            ],
        }
