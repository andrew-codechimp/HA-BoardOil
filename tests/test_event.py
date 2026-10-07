"""Tests for BoardOil event entities and board-specific card events."""

from unittest.mock import MagicMock, patch

from custom_components.boardoil.models import Board
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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
