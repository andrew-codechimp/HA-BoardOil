"""Tests for BoardOil HTTP requests, model conversion, and API errors."""

from dataclasses import asdict
import json
import socket

import aiohttp
from custom_components.boardoil.api import (
    BoardOilApiClient,
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientCommunicationError,
    BoardOilApiClientError,
)
from custom_components.boardoil.models import (
    Board,
    BoardSummary,
    CardType,
    Column,
    Me,
    Member,
    Slick,
    Tag,
    Version,
)
import pytest
from pytest_homeassistant_custom_component.common import load_fixture
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import API_TOKEN, HOST


@pytest.fixture
async def api_client(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,  # noqa: ARG001
) -> BoardOilApiClient:
    """Create a real API client after installing the HTTP mock."""
    return BoardOilApiClient(HOST, API_TOKEN, async_get_clientsession(hass))


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "data", "expected"),
    [
        pytest.param(
            "async_get_me",
            "auth/me",
            {},
            {"id": 7, "username": "alex", "displayName": "Alex", "role": "client"},
            Me(7, "alex", "Alex", "client"),
            id="account",
        ),
        pytest.param(
            "async_get_version",
            "version",
            {},
            {
                "version": "1.5.0",
                "channel": "stable",
                "build": "42",
                "commit": "abc123",
            },
            Version("1.5.0", "stable", "42", "abc123"),
            id="version",
        ),
        pytest.param(
            "async_get_boards",
            "boards",
            {},
            [{"id": 1, "name": "Work"}],
            [BoardSummary(1, "Work", "")],
            id="boards",
        ),
        pytest.param(
            "async_get_columns",
            "boards/1/columns",
            {"board_id": 1},
            [{"id": 10, "title": "To do"}],
            [Column(10, "To do")],
            id="columns",
        ),
        pytest.param(
            "async_get_card_types",
            "boards/1/card-types",
            {"board_id": 1},
            [{"id": 20, "name": "Task"}],
            [CardType(20, "Task")],
            id="card-types",
        ),
        pytest.param(
            "async_get_tags",
            "boards/1/tags",
            {"board_id": 1},
            [{"id": 30, "name": "Home"}],
            [Tag(30, "Home")],
            id="tags",
        ),
        pytest.param(
            "async_get_slicks",
            "boards/1/slicks",
            {"board_id": 1},
            [{"id": 40, "name": "Summer"}],
            [Slick(40, "Summer")],
            id="slicks",
        ),
        pytest.param(
            "async_get_members",
            "boards/1/members",
            {"board_id": 1},
            [{"userId": 7, "userName": "alex", "displayName": "Alex"}],
            [Member(7, "alex", "Alex")],
            id="members",
        ),
    ],
)
async def test_get_models(
    api_client: BoardOilApiClient,
    aioclient_mock: AiohttpClientMocker,
    method: str,
    path: str,
    kwargs: dict[str, int],
    data: object,
    expected: object,
) -> None:
    """Test API responses become typed models and requests carry authentication."""
    aioclient_mock.get(f"{HOST}/api/{path}", json={"data": data})
    assert await getattr(api_client, method)(**kwargs) == expected
    assert aioclient_mock.mock_calls[0][3] == {
        "Authorization": f"Bearer {API_TOKEN}",
        "Accept": "application/json",
    }


async def test_get_board(
    api_client: BoardOilApiClient, aioclient_mock: AiohttpClientMocker, board: Board
) -> None:
    """Test board conversion retains card metadata and skips non-object cards."""
    response = json.loads(load_fixture("board.json"))
    response["data"]["columns"][0]["cards"].append("invalid")
    aioclient_mock.get(f"{HOST}/api/boards/1", json=response)
    assert asdict(await api_client.async_get_board(1)) == asdict(board)


@pytest.mark.parametrize(
    ("method", "path", "kwargs", "http_method", "payload"),
    [
        pytest.param(
            "async_add_card",
            "boards/1/cards",
            {
                "board_id": 1,
                "column_id": None,
                "title": "New task",
                "description": "",
                "tag_names": None,
                "card_type_id": None,
                "slick_name": None,
                "assigned_user_id": None,
                "external_url": None,
            },
            "post",
            {
                "title": "New task",
                "description": "",
                "tagNames": [],
                "slickName": None,
                "externalUrl": None,
            },
            id="add-defaults",
        ),
        pytest.param(
            "async_add_card",
            "boards/1/cards",
            {
                "board_id": 1,
                "column_id": 10,
                "title": "New task",
                "description": "Details",
                "tag_names": ["Home"],
                "card_type_id": 20,
                "slick_name": "Summer",
                "assigned_user_id": 7,
                "external_url": "https://example.com",
            },
            "post",
            {
                "title": "New task",
                "description": "Details",
                "tagNames": ["Home"],
                "slickName": "Summer",
                "externalUrl": "https://example.com",
                "boardColumnId": 10,
                "cardTypeId": 20,
                "assignedUserId": 7,
            },
            id="add-all-fields",
        ),
        pytest.param(
            "async_update_card",
            "boards/1/cards/101",
            {
                "board_id": 1,
                "card_id": 101,
                "column_id": 11,
                "title": "Done",
                "description": "Details",
                "tag_names": ["Home"],
                "card_type_id": 20,
                "slick_name": "Summer",
                "assigned_user_id": 7,
                "external_url": "https://example.com",
            },
            "put",
            {
                "title": "Done",
                "description": "Details",
                "tagNames": ["Home"],
                "cardTypeId": 20,
                "boardColumnId": 11,
                "assignedUserId": 7,
                "slickName": "Summer",
                "externalUrl": "https://example.com",
            },
            id="update",
        ),
        pytest.param(
            "async_delete_card",
            "boards/1/cards/101",
            {"board_id": 1, "card_id": 101},
            "delete",
            None,
            id="delete",
        ),
        pytest.param(
            "async_archive_card",
            "boards/1/cards/101/archive",
            {"board_id": 1, "card_id": 101},
            "post",
            None,
            id="archive",
        ),
        pytest.param(
            "async_add_card_comment",
            "boards/1/cards/101/comments",
            {"board_id": 1, "card_id": 101, "comment": "Finished"},
            "post",
            {"text": "Finished"},
            id="comment",
        ),
    ],
)
async def test_card_requests(
    api_client: BoardOilApiClient,
    aioclient_mock: AiohttpClientMocker,
    method: str,
    path: str,
    kwargs: dict[str, object],
    http_method: str,
    payload: dict[str, object] | None,
) -> None:
    """Test card mutations use the expected endpoint, method, and JSON payload."""
    getattr(aioclient_mock, http_method)(
        f"{HOST}/api/{path}", json={"data": {"id": 101}}
    )
    assert await getattr(api_client, method)(**kwargs) == {"data": {"id": 101}}
    request_method, request_url, request_data, request_headers = (
        aioclient_mock.mock_calls[0]
    )
    assert request_method == http_method
    assert str(request_url) == f"{HOST}/api/{path}"
    assert request_data == payload
    assert request_headers["Authorization"] == f"Bearer {API_TOKEN}"


@pytest.mark.parametrize(
    "status", [pytest.param(401, id="unauthorized"), pytest.param(403, id="forbidden")]
)
async def test_authentication_error(
    api_client: BoardOilApiClient, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    """Test HTTP authentication failures retain their specific exception type."""
    aioclient_mock.get(f"{HOST}/api/auth/me", status=status)
    with pytest.raises(BoardOilApiClientAuthenticationError):
        await api_client.async_get_me()


@pytest.mark.parametrize("status", [400, 404, 500])
async def test_http_error(
    api_client: BoardOilApiClient, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    """Test failed HTTP responses become communication errors."""
    aioclient_mock.get(f"{HOST}/api/auth/me", status=status)
    with pytest.raises(BoardOilApiClientCommunicationError):
        await api_client.async_get_me()


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        pytest.param(TimeoutError(), BoardOilApiClientCommunicationError, id="timeout"),
        pytest.param(
            aiohttp.ClientError(),
            BoardOilApiClientCommunicationError,
            id="client-error",
        ),
        pytest.param(socket.gaierror(), BoardOilApiClientCommunicationError, id="dns"),
        pytest.param(
            ValueError("bad response"), BoardOilApiClientError, id="unexpected"
        ),
    ],
)
async def test_request_error(
    api_client: BoardOilApiClient,
    aioclient_mock: AiohttpClientMocker,
    exception: Exception,
    expected: type[BoardOilApiClientError],
) -> None:
    """Test network and unexpected failures are wrapped in the correct API error."""
    aioclient_mock.get(f"{HOST}/api/auth/me", exc=exception)
    with pytest.raises(expected):
        await api_client.async_get_me()
