"""Tests for BoardOil loading, errors, polling, and cleanup."""

from datetime import timedelta
from unittest.mock import MagicMock

from custom_components.boardoil.api import (
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientCommunicationError,
    BoardOilApiClientError,
)
from custom_components.boardoil.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from custom_components.boardoil.models import Me, Version
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import COLUMN_ENTITY_ID, setup_integration

pytestmark = pytest.mark.usefixtures("mock_api")


@pytest.mark.parametrize(
    "verify_ssl",
    [pytest.param(True, id="verify-ssl"), pytest.param(False, id="self-signed")],
)
async def test_migrate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test version 1 entries migrate to the slugified account ID and username."""
    old_data = {**mock_config_entry.data, CONF_VERIFY_SSL: verify_ssl}
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        version=1,
        unique_id="https-boardoil-example-7",
        data=old_data,
    )
    mock_api.async_get_me.return_value = Me(7, "Alex.Test_User", "Alex", "client")

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.version == 2
    assert mock_config_entry.unique_id == "7-alex-test-user"
    assert mock_config_entry.data == old_data
    mock_api.async_get_me.assert_awaited_once()


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(BoardOilApiClientAuthenticationError("auth"), id="authentication"),
        pytest.param(BoardOilApiClientCommunicationError("offline"), id="connection"),
        pytest.param(BoardOilApiClientError("unexpected"), id="unexpected"),
    ],
)
async def test_migrate_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    exception: BoardOilApiClientError,
) -> None:
    """Test failed migrations preserve the old version, unique ID, and data."""
    old_data = dict(mock_config_entry.data)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, version=1, unique_id="https-boardoil-example-7"
    )
    mock_api.async_get_me.side_effect = exception

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.MIGRATION_ERROR
    assert mock_config_entry.version == 1
    assert mock_config_entry.unique_id == "https-boardoil-example-7"
    assert mock_config_entry.data == old_data


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup creates board devices, entities, actions, and runtime data."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.version == "1.5.0"
    assert mock_config_entry.runtime_data.build == "42"
    assert (
        len(
            er.async_entries_for_config_entry(
                entity_registry, mock_config_entry.entry_id
            )
        )
        == 7
    )
    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(devices) == 1
    assert devices[0].identifiers == {(DOMAIN, f"{mock_config_entry.entry_id}:1")}
    assert devices[0].sw_version == "1.5.0 (42)"
    assert set(hass.services.async_services()[DOMAIN]) == {
        "get_card",
        "get_cards",
        "add_card",
        "update_card",
        "delete_card",
        "archive_card",
        "add_card_comment",
    }


async def test_version_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test an initial connection error prevents setup."""
    mock_api.async_get_version.side_effect = BoardOilApiClientCommunicationError(
        "offline"
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_unsupported_version(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test an unsupported server version records the translated setup error."""
    mock_api.async_get_version.return_value = Version("1.4.0", "stable", "42", "abc123")
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "version_error"


async def test_initial_refresh_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: MagicMock
) -> None:
    """Test a failed first poll schedules a retry."""
    mock_api.async_get_boards.side_effect = BoardOilApiClientCommunicationError(
        "offline"
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_polling_and_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test scheduled polling stops after unloading and event listeners are removed."""
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    assert mock_api.async_get_boards.await_count == 1
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert mock_api.async_get_boards.await_count == 2
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(COLUMN_ENTITY_ID).state == "unavailable"
    assert coordinator._event_listeners == {}  # noqa: SLF001
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL + 1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert mock_api.async_get_boards.await_count == 2


async def test_options_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test entry changes reload the coordinator and entities."""
    await setup_integration(hass, mock_config_entry)
    previous_runtime = mock_config_entry.runtime_data
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_VERIFY_SSL: False}
    )
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not previous_runtime
