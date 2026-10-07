"""Tests for BoardOil diagnostics."""

from custom_components.boardoil.diagnostics import async_get_config_entry_diagnostics
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import API_TOKEN, HOST, setup_integration


@pytest.mark.usefixtures("mock_api")
async def test_diagnostics(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics contain board data and version metadata without credentials."""
    await setup_integration(hass, mock_config_entry)
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    assert diagnostics == snapshot
    assert API_TOKEN not in str(diagnostics)
    assert HOST not in str(diagnostics)
