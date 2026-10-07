"""Tests for card actions, targeting, validation, and response data."""

from unittest.mock import MagicMock, patch

from custom_components.boardoil.api import BoardOilApiClientCommunicationError
from custom_components.boardoil.const import DOMAIN
from custom_components.boardoil.services import _normalize_tag_names
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from . import setup_integration

pytestmark = pytest.mark.usefixtures("mock_api")


@pytest.mark.parametrize(
    ("action", "data", "api_method", "expected"),
    [
        pytest.param(
            "add_card",
            {"title": "New task"},
            "async_add_card",
            {
                "board_id": 1,
                "column_id": None,
                "title": "New task",
                "description": "",
                "tag_names": [],
                "card_type_id": None,
                "slick_name": None,
                "assigned_user_id": None,
                "external_url": None,
            },
            id="add-defaults",
        ),
        pytest.param(
            "add_card",
            {
                "title": "New task",
                "description": "Details",
                "column": " to DO ",
                "card_type": " TASK ",
                "tag_names": " Home, Urgent\nWeekly ",
                "slick_name": "Summer",
                "assigned_user": " aLEX ",
                "external_url": "https://example.com/new",
            },
            "async_add_card",
            {
                "board_id": 1,
                "column_id": 10,
                "title": "New task",
                "description": "Details",
                "tag_names": ["Home", "Urgent", "Weekly"],
                "card_type_id": 20,
                "slick_name": "Summer",
                "assigned_user_id": 7,
                "external_url": "https://example.com/new",
            },
            id="add-names",
        ),
        pytest.param(
            "add_card",
            {
                "title": "New task",
                "column": "10",
                "card_type": "20",
                "assigned_user": "7",
            },
            "async_add_card",
            {
                "board_id": 1,
                "column_id": 10,
                "title": "New task",
                "description": "",
                "tag_names": [],
                "card_type_id": 20,
                "slick_name": None,
                "assigned_user_id": 7,
                "external_url": None,
            },
            id="add-numeric-ids",
        ),
        pytest.param(
            "update_card",
            {"card_id": 101, "title": "Updated"},
            "async_update_card",
            {
                "board_id": 1,
                "card_id": 101,
                "title": "Updated",
                "description": "Check the soil first",
                "tag_names": ["Home"],
                "column_id": None,
                "card_type_id": 20,
                "assigned_user_id": 7,
                "slick_name": "Summer",
                "external_url": "https://example.com/plants",
            },
            id="update-preserves-fields",
        ),
        pytest.param(
            "update_card",
            {
                "card_id": 101,
                "title": "Finished",
                "description": "All done",
                "column": "Done",
                "card_type": "Task",
                "assigned_user": "Alex",
                "tag_names": ["Weekly"],
                "slick_name": "Winter",
                "external_url": "http://example.com/finished",
            },
            "async_update_card",
            {
                "board_id": 1,
                "card_id": 101,
                "title": "Finished",
                "description": "All done",
                "tag_names": ["Weekly"],
                "column_id": 11,
                "card_type_id": 20,
                "assigned_user_id": 7,
                "slick_name": "Winter",
                "external_url": "http://example.com/finished",
            },
            id="update-all-fields",
        ),
        pytest.param(
            "delete_card",
            {"card_id": "101"},
            "async_delete_card",
            {"board_id": 1, "card_id": "101"},
            id="delete",
        ),
        pytest.param(
            "archive_card",
            {"card_id": "101"},
            "async_archive_card",
            {"board_id": 1, "card_id": "101"},
            id="archive",
        ),
        pytest.param(
            "add_card_comment",
            {"card_id": 101, "comment": "Finished"},
            "async_add_card_comment",
            {"board_id": 1, "card_id": 101, "comment": "Finished"},
            id="comment",
        ),
    ],
)
async def test_mutation_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    action: str,
    data: dict[str, object],
    api_method: str,
    expected: dict[str, object],
) -> None:
    """Test actions resolve names and IDs, send the right fields, and request a refresh."""
    await setup_integration(hass, mock_config_entry)
    with patch.object(
        mock_config_entry.runtime_data.coordinator, "async_request_refresh"
    ) as refresh:
        await hass.services.async_call(
            DOMAIN,
            action,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                "board": " wORK ",
                **data,
            },
            blocking=True,
        )
        getattr(mock_api, api_method).assert_awaited_once_with(**expected)
        refresh.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("action", "data"),
    [
        pytest.param("get_card", {"card_id": 101}, id="single-card"),
        pytest.param("get_cards", {}, id="all-cards"),
        pytest.param("get_cards", {"column": "To do"}, id="column-name"),
        pytest.param("get_cards", {"column": "10"}, id="column-id"),
        pytest.param("get_cards", {"column": "Done"}, id="empty-column"),
    ],
)
async def test_response_actions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    action: str,
    data: dict[str, object],
    snapshot: SnapshotAssertion,
) -> None:
    """Test response actions return the original API card payloads."""
    await setup_integration(hass, mock_config_entry)
    response = await hass.services.async_call(
        DOMAIN,
        action,
        {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, "board": "1", **data},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


@pytest.mark.parametrize(
    ("data", "translation_key"),
    [
        pytest.param({"board": "Missing"}, "board_not_found", id="board"),
        pytest.param({"column": "Missing"}, "column_not_found", id="column"),
        pytest.param({"card_type": "Missing"}, "card_type_not_found", id="card-type"),
        pytest.param({"assigned_user": "Missing"}, "user_not_found", id="user"),
    ],
)
async def test_missing_targets(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    data: dict[str, str],
    translation_key: str,
) -> None:
    """Test unknown named targets fail before creating a card."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            "add_card",
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                "board": "Work",
                "title": "New task",
                **data,
            },
            blocking=True,
        )
    assert error.value.translation_key == translation_key
    mock_api.async_add_card.assert_not_awaited()


@pytest.mark.parametrize(
    ("action", "data", "translation_key"),
    [
        pytest.param(
            "get_card", {"card_id": 999}, "card_not_found", id="get-missing-card"
        ),
        pytest.param(
            "get_cards", {"column": "999"}, "column_not_found", id="get-missing-column"
        ),
    ],
)
async def test_missing_response_target(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    action: str,
    data: dict[str, object],
    translation_key: str,
) -> None:
    """Test response actions validate missing cards and numeric column targets."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            action,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, "board": "Work", **data},
            blocking=True,
            return_response=True,
        )
    assert error.value.translation_key == translation_key


@pytest.mark.parametrize("action", ["get_card", "get_cards"])
async def test_missing_board(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    action: str,
) -> None:
    """Test response actions on an empty instance return a translated missing-board error."""
    mock_api.async_get_boards.return_value = []
    await setup_integration(hass, mock_config_entry)
    data = {"get_card": {"card_id": 101}, "get_cards": {}}[action]
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            action,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, "board": "999", **data},
            blocking=True,
            return_response=True,
        )
    assert error.value.translation_key == "board_not_found"
    assert error.value.translation_placeholders == {"board": "999"}


@pytest.mark.parametrize("action", ["add_card", "update_card"])
@pytest.mark.parametrize("url", ["ftp://example.com", "https://", "invalid"])
async def test_invalid_url(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    action: str,
    url: str,
) -> None:
    """Test card actions reject invalid external URLs before mutation."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(ServiceValidationError) as error:
        await hass.services.async_call(
            DOMAIN,
            action,
            {
                ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id,
                "board": "Work",
                "external_url": url,
                **{"add_card": {"title": "New task"}, "update_card": {"card_id": 101}}[
                    action
                ],
            },
            blocking=True,
        )
    assert error.value.translation_key == "invalid_url"
    mock_api.async_add_card.assert_not_awaited()
    mock_api.async_update_card.assert_not_awaited()


@pytest.mark.parametrize(
    ("action", "data", "method"),
    [
        pytest.param("add_card", {"title": "New task"}, "async_add_card", id="add"),
        pytest.param(
            "update_card",
            {"card_id": 101, "title": "Updated"},
            "async_update_card",
            id="update",
        ),
        pytest.param(
            "delete_card", {"card_id": "101"}, "async_delete_card", id="delete"
        ),
        pytest.param(
            "archive_card", {"card_id": "101"}, "async_archive_card", id="archive"
        ),
        pytest.param(
            "add_card_comment",
            {"card_id": 101, "comment": "Finished"},
            "async_add_card_comment",
            id="comment",
        ),
    ],
)
async def test_mutation_connection_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: MagicMock,
    action: str,
    data: dict[str, object],
    method: str,
) -> None:
    """Test mutation transport failures become translated Home Assistant errors."""
    await setup_integration(hass, mock_config_entry)
    getattr(mock_api, method).side_effect = BoardOilApiClientCommunicationError(
        "offline"
    )
    with pytest.raises(HomeAssistantError) as error:
        await hass.services.async_call(
            DOMAIN,
            action,
            {ATTR_CONFIG_ENTRY_ID: mock_config_entry.entry_id, "board": "Work", **data},
            blocking=True,
        )
    assert error.value.translation_key == "connection_error"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(None, [], id="none"),
        pytest.param(
            " Home, Urgent\nWeekly, ", ["Home", "Urgent", "Weekly"], id="text"
        ),
        pytest.param([" Home ", "", "Urgent"], ["Home", "Urgent"], id="list"),
        pytest.param(
            {"tag_names": ["Home", "Urgent"]}, ["Home", "Urgent"], id="nested-tag-names"
        ),
        pytest.param({"tags": "Home,Urgent"}, ["Home", "Urgent"], id="nested-tags"),
        pytest.param(
            {"first": "Home", "second": "Urgent"},
            ["Home", "Urgent"],
            id="mapping-values",
        ),
        pytest.param(
            {"Home": True, "Urgent": True}, ["Home", "Urgent"], id="mapping-keys"
        ),
    ],
)
def test_tag_normalization(raw: object, expected: list[str]) -> None:
    """Test supported tag formats normalize whitespace and empty values."""
    assert _normalize_tag_names(raw) == expected
