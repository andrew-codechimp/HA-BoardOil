"""Tests for BoardOil diagnostics."""

from custom_components.boardoil.diagnostics import async_get_config_entry_diagnostics
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
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


@pytest.mark.parametrize(
    "state",
    [
        pytest.param(ConfigEntryState.SETUP_ERROR, id="setup-error"),
        pytest.param(ConfigEntryState.SETUP_RETRY, id="setup-retry"),
    ],
)
async def test_diagnostics_before_setup(
    hass: HomeAssistant, state: ConfigEntryState
) -> None:
    """Return setup state when runtime data has not been assigned."""
    entry = MockConfigEntry(domain="boardoil", state=state)

    assert await async_get_config_entry_diagnostics(hass, entry) == {
        "state": state.value
    }


@pytest.mark.usefixtures("mock_api")
async def test_diagnostics_after_unload(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Download diagnostics after Home Assistant deletes runtime data."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert not hasattr(mock_config_entry, "runtime_data")

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == {"state": ConfigEntryState.NOT_LOADED.value}
