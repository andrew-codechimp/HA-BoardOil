"""Tests for column sensors, diagnostic sensors, and dynamic registry cleanup."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

from custom_components.boardoil.api import BoardOilApiClientCommunicationError
from custom_components.boardoil.const import DOMAIN
from custom_components.boardoil.models import Board, ColumnWithCards
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import COLUMN_ENTITY_ID, setup_integration

pytestmark = pytest.mark.usefixtures("mock_api")


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor states, card attributes, metadata, and board device associations."""
    with patch("custom_components.boardoil.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_column_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    board: Board,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a column appearing after setup creates a registered count sensor."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_board.return_value = replace(
        board, columns=[*board.columns, ColumnWithCards(12, "In progress", [])]
    )
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    entity_id = entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_1_12_card_count"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "0"
    assert hass.states.get(entity_id).attributes["column_title"] == "In progress"


async def test_column_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    board: Board,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test deleting a column removes its state and registry entry."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_board.return_value = replace(board, columns=[board.columns[1]])
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert entity_registry.async_get(COLUMN_ENTITY_ID) is None
    assert hass.states.get(COLUMN_ENTITY_ID) is None


async def test_column_renamed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    board: Board,
) -> None:
    """Test column renaming updates metadata while preserving its entity ID."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_board.return_value = replace(
        board,
        name="Tasks",
        columns=[replace(board.columns[0], title="Backlog"), board.columns[1]],
    )
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(COLUMN_ENTITY_ID)
    assert state.state == "1"
    assert state.attributes["column_title"] == "Backlog"
    assert state.attributes["board_name"] == "Tasks"
    assert state.attributes["friendly_name"] == "BoardOil - Work Backlog"


async def test_board_removed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test deleting a board removes all its entities and its device."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_boards.return_value = []
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )


async def test_orphan_cleanup_on_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a board removed while unloaded is cleaned up on the next setup."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    mock_api.async_get_boards.return_value = []
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert not dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )


async def test_poll_failure_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
) -> None:
    """Test failed polls make sensors unavailable and successful polls recover them."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_boards.side_effect = BoardOilApiClientCommunicationError(
        "offline"
    )
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(COLUMN_ENTITY_ID).state == "unavailable"
    mock_api.async_get_boards.side_effect = None
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(COLUMN_ENTITY_ID).state == "1"
