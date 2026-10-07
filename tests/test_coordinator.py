"""Tests for board polling, card change detection, and event dispatch."""

from dataclasses import asdict
from unittest.mock import MagicMock, Mock

from custom_components.boardoil.api import (
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientCommunicationError,
)
from custom_components.boardoil.coordinator import BoardOilEventData
from custom_components.boardoil.models import Board, BoardSummary
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_api")


@pytest.mark.parametrize(
    ("changed_board", "expected_type", "expected_id", "old_column", "new_column"),
    [
        pytest.param("created", "card_created", 102, None, 10, id="created"),
        pytest.param("removed", "card_removed", 101, 10, None, id="removed"),
        pytest.param("moved", "card_moved", 101, 10, 11, id="moved"),
        pytest.param("updated", "card_updated", 101, 10, 10, id="updated"),
    ],
    indirect=["changed_board"],
)
async def test_card_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    changed_board: Board,
    expected_type: str,
    expected_id: int,
    old_column: int | None,
    new_column: int | None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test refreshes detect changes and deliver full card metadata to listeners."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    events: list[BoardOilEventData] = []
    unsubscribe = coordinator.async_add_event_listener(events.append, "test-listener")
    mock_api.async_get_board.return_value = changed_board
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    changes = coordinator.get_board_changes(1)
    assert changes.has_changes()
    assert len(changes.card_changes) == 1
    change = changes.card_changes[0]
    assert (
        change.change_type.value,
        change.card_id,
        change.old_column_id,
        change.new_column_id,
    ) == (expected_type, expected_id, old_column, new_column)
    filtered = {
        "card_created": changes.new_cards,
        "card_removed": changes.removed_cards,
        "card_moved": changes.moved_cards,
        "card_updated": changes.updated_cards,
    }
    assert filtered[expected_type]() == changes.card_changes
    assert len(events) == 1
    assert asdict(events[0]) == snapshot
    unsubscribe()
    await coordinator.async_refresh()
    assert len(events) == 1


async def test_first_and_unchanged_refresh(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test existing cards at startup and unchanged polls do not trigger events."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    listener = Mock()
    unsubscribe = coordinator.async_add_event_listener(listener, "test-listener")
    await coordinator.async_refresh()
    assert not coordinator.get_board_changes(1).has_changes()
    listener.assert_not_called()
    unsubscribe()
    unsubscribe()


async def test_board_removed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test a deleted board reports removal of its cards in the change set."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_boards.return_value = []
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    changes = coordinator.get_board_changes(1)
    assert len(changes.removed_cards()) == 1
    assert changes.removed_cards()[0].card_id == 101
    assert not coordinator.get_board_changes(999).has_changes()


async def test_new_board(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test a board appearing after startup reports its existing cards as created."""
    mock_api.async_get_boards.return_value = []
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_boards.return_value = [BoardSummary(1, "Work", "")]
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert len(coordinator.get_board_changes(1).new_cards()) == 1


@pytest.mark.parametrize(
    ("exception", "translation_key"),
    [
        pytest.param(
            BoardOilApiClientCommunicationError("offline"),
            "update_failed",
            id="communication",
        ),
        pytest.param(
            BoardOilApiClientAuthenticationError("expired"),
            "auth_failed",
            id="authentication",
        ),
    ],
)
async def test_poll_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    exception: Exception,
    translation_key: str,
) -> None:
    """Test polling errors retain a translated exception and mark data unavailable."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_boards.side_effect = exception
    coordinator = mock_config_entry.runtime_data.coordinator
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.last_exception.translation_key == translation_key
