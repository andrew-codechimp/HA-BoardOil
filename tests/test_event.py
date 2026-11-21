"""Tests for BoardOil event entities and board-specific card events."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from custom_components.boardoil.models import Board
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.restore_state import RestoreEntity

from . import EVENT_ENTITY_ID, setup_integration

pytestmark = pytest.mark.usefixtures("mock_api")


async def test_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test event metadata and startup does not trigger existing card events."""
    with patch("custom_components.boardoil.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)
    assert hass.states.get(EVENT_ENTITY_ID).state == "unknown"


@pytest.mark.parametrize(
    ("changed_board", "event_type"),
    [
        pytest.param("created", "card_created", id="created"),
        pytest.param("updated", "card_updated", id="updated"),
        pytest.param("moved", "card_moved", id="moved"),
        pytest.param("removed", "card_removed", id="removed"),
    ],
    indirect=["changed_board"],
)
async def test_card_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    changed_board: Board,
    event_type: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test card changes update the event entity with type and card metadata."""
    await setup_integration(hass, mock_config_entry)
    mock_api.async_get_board.return_value = changed_board
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(EVENT_ENTITY_ID)
    assert state.attributes["event_type"] == event_type
    assert state == snapshot


@pytest.mark.parametrize("changed_board", ["updated"], indirect=True)
async def test_entity_id_changed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    board: Board,
    changed_board: Board,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test repeated renames preserve events, subscriptions, and restore state."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    registry_id = entity_registry.async_get(EVENT_ENTITY_ID).id
    mock_api.async_get_board.return_value = changed_board
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    entity_id = EVENT_ENTITY_ID

    with patch.object(
        RestoreEntity,
        "async_get_last_state",
        autospec=True,
        side_effect=RestoreEntity.async_get_last_state,
    ) as restore_state:
        for new_entity_id, updated_board in (
            ("event.renamed_board_cards", board),
            ("event.renamed_board_cards_again", changed_board),
        ):
            previous_state = hass.states.get(entity_id)
            entity_registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
            await hass.async_block_till_done()

            assert hass.states.get(entity_id) is None
            state = hass.states.get(new_entity_id)
            assert state.state == previous_state.state
            assert state.attributes == previous_state.attributes
            assert entity_registry.async_get(new_entity_id).id == registry_id
            entity_id = new_entity_id

            freezer.tick(timedelta(seconds=1))
            mock_api.async_get_board.return_value = updated_board
            await coordinator.async_refresh()
            await hass.async_block_till_done()

            state = hass.states.get(entity_id)
            assert state.state != previous_state.state
            assert state.attributes["event_type"] == "card_updated"
            assert state.attributes["title"] == updated_board.columns[0].cards[0].title

        restore_state.assert_not_awaited()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert coordinator._event_listeners == {}  # noqa: SLF001

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    restored_state = hass.states.get(entity_id)
    assert restored_state.state == state.state
    assert restored_state.attributes == state.attributes
    assert entity_registry.async_get(entity_id).id == registry_id

    freezer.tick(timedelta(seconds=1))
    mock_api.async_get_board.return_value = board
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != restored_state.state
    assert (
        hass.states.get(entity_id).attributes["title"]
        == board.columns[0].cards[0].title
    )
