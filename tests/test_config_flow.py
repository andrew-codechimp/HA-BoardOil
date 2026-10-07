"""Tests for BoardOil setup, reauthentication, and reconfiguration flows."""

from unittest.mock import MagicMock

from custom_components.boardoil.api import (
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientCommunicationError,
    BoardOilApiClientError,
)
from custom_components.boardoil.const import DOMAIN
from custom_components.boardoil.models import Me, Version
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import API_TOKEN, HOST, UNIQUE_ID

pytestmark = pytest.mark.usefixtures("mock_api", "mock_setup_entry")


@pytest.mark.parametrize(
    "verify_ssl",
    [pytest.param(True, id="verify-ssl"), pytest.param(False, id="self-signed")],
)
async def test_user_flow(hass: HomeAssistant, verify_ssl: bool) -> None:
    """Test user setup stores credentials and identifies the host/account pair."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    data = {CONF_HOST: HOST, CONF_API_TOKEN: API_TOKEN, CONF_VERIFY_SSL: verify_ssl}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "BoardOil"
    assert result["data"] == data
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        pytest.param(
            BoardOilApiClientAuthenticationError("test"), "auth", id="authentication"
        ),
        pytest.param(
            BoardOilApiClientCommunicationError("test"), "connection", id="connection"
        ),
        pytest.param(BoardOilApiClientError("test"), "unknown", id="unexpected"),
    ],
)
@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_RECONFIGURE, SOURCE_REAUTH])
@pytest.mark.no_fail_on_log_exception
async def test_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    source: str,
    exception: BoardOilApiClientError,
    error: str,
) -> None:
    """Test flow connection errors leave the form open for another attempt."""
    mock_config_entry.add_to_hass(hass)
    mock_api.async_get_me.side_effect = exception
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data={SOURCE_REAUTH: dict(mock_config_entry.data)}.get(source),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SOURCE_REAUTH: {CONF_API_TOKEN: "replacement-token"}}.get(
            source, dict(mock_config_entry.data)
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize("source", [SOURCE_USER, SOURCE_RECONFIGURE, SOURCE_REAUTH])
async def test_unsupported_version(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    source: str,
) -> None:
    """Test every connection flow rejects an unsupported BoardOil version."""
    mock_config_entry.add_to_hass(hass)
    mock_api.async_get_version.return_value = Version("1.4.0", "stable", "42", "abc123")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data={SOURCE_REAUTH: dict(mock_config_entry.data)}.get(source),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SOURCE_REAUTH: {CONF_API_TOKEN: "replacement-token"}}.get(
            source, dict(mock_config_entry.data)
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "boardoil_version"}


async def test_duplicate_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same host/account cannot create a second entry."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=dict(mock_config_entry.data)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        pytest.param(SOURCE_REAUTH, "reauth_successful", id="reauth"),
        pytest.param(SOURCE_RECONFIGURE, "reconfigure_successful", id="reconfigure"),
    ],
)
async def test_update_credentials(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, source: str, reason: str
) -> None:
    """Test credentials update while preserving the configured host/account."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data={SOURCE_REAUTH: dict(mock_config_entry.data)}.get(source),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SOURCE_REAUTH: {CONF_API_TOKEN: "replacement-token"}}.get(
            source, {**mock_config_entry.data, CONF_API_TOKEN: "replacement-token"}
        ),
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason
    assert mock_config_entry.data == {
        CONF_HOST: HOST,
        CONF_API_TOKEN: "replacement-token",
        CONF_VERIFY_SSL: True,
    }


@pytest.mark.parametrize("source", [SOURCE_REAUTH, SOURCE_RECONFIGURE])
async def test_wrong_account(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    source: str,
) -> None:
    """Test reauthentication and reconfiguration cannot switch accounts."""
    mock_config_entry.add_to_hass(hass)
    mock_api.async_get_me.return_value = Me(8, "other", "Other", "client")
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": mock_config_entry.entry_id},
        data={SOURCE_REAUTH: dict(mock_config_entry.data)}.get(source),
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {SOURCE_REAUTH: {CONF_API_TOKEN: "replacement-token"}}.get(
            source, dict(mock_config_entry.data)
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_account"
    assert mock_config_entry.data[CONF_API_TOKEN] == API_TOKEN
