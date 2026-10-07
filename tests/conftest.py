"""Shared fixtures for BoardOil tests."""

from collections.abc import Generator
from dataclasses import replace
import json
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.boardoil.const import DOMAIN
from custom_components.boardoil.models import (
    Board,
    BoardSummary,
    Card,
    CardType,
    Column,
    ColumnWithCards,
    Me,
    Member,
    Slick,
    Tag,
    Version,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, load_fixture
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL

from . import API_TOKEN, ENTRY_ID, HOST, UNIQUE_ID


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Select the Home Assistant serializer regardless of plugin load order."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in Home Assistant."""


@pytest.fixture(autouse=True)
def freeze_setup_time(freezer: FrozenDateTimeFactory) -> None:
    """Keep event timestamps and polling deadlines stable."""
    freezer.move_to("2026-07-01T12:00:00+00:00")


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a BoardOil entry using a test host and token."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=UNIQUE_ID,
        title="BoardOil",
        version=1,
        data={CONF_HOST: HOST, CONF_API_TOKEN: API_TOKEN, CONF_VERIFY_SSL: True},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Isolate config flow data from integration setup."""
    with patch(
        "custom_components.boardoil.async_setup_entry", return_value=True
    ) as setup:
        yield setup


@pytest.fixture
def card() -> Card:
    """Create a card with metadata and its original API payload."""
    raw_data = json.loads(load_fixture("board.json"))["data"]["columns"][0]["cards"][0]
    return Card(
        id=101,
        card_type_id=20,
        card_type_name="Task",
        card_type_emoji="",
        title="Water the plants",
        description="Check the soil first",
        sort_key="a0",
        tag_names=["Home"],
        updated_at_utc="2026-06-30T10:00:00Z",
        assigned_user_id=7,
        assigned_user_display_name="Alex",
        external_url="https://example.com/plants",
        slick_id=40,
        slick_name="Summer",
        raw_data=raw_data,
    )


@pytest.fixture
def board(card: Card) -> Board:
    """Create a board containing a populated and an empty column."""
    return Board(
        id=1,
        name="Work",
        description="Tasks for the week",
        columns=[ColumnWithCards(10, "To do", [card]), ColumnWithCards(11, "Done", [])],
    )


@pytest.fixture
def changed_board(request: pytest.FixtureRequest, board: Board, card: Card) -> Board:
    """Return independent board data for each polling transition."""
    columns = {
        "created": [
            ColumnWithCards(10, "To do", [card, replace(card, id=102)]),
            ColumnWithCards(11, "Done", []),
        ],
        "removed": [ColumnWithCards(10, "To do", []), ColumnWithCards(11, "Done", [])],
        "moved": [
            ColumnWithCards(10, "To do", []),
            ColumnWithCards(11, "Done", [card]),
        ],
        "updated": [
            ColumnWithCards(
                10,
                "To do",
                [
                    replace(
                        card,
                        title="Updated task",
                        updated_at_utc="2026-07-01T12:00:00Z",
                    )
                ],
            ),
            ColumnWithCards(11, "Done", []),
        ],
        "unchanged": board.columns,
    }[request.param]
    return replace(board, columns=columns)


@pytest.fixture
def mock_api(board: Board) -> Generator[MagicMock]:
    """Mock the external API while retaining Home Assistant's runtime behavior."""
    with (
        patch(
            "custom_components.boardoil.BoardOilApiClient", autospec=True
        ) as client_class,
        patch("custom_components.boardoil.config_flow.BoardOilApiClient", client_class),
    ):
        client = client_class.return_value
        client.async_get_me.return_value = Me(7, "alex", "Alex", "client")
        client.async_get_version.return_value = Version(
            "1.5.0", "stable", "42", "abc123"
        )
        client.async_get_boards.return_value = [
            BoardSummary(1, "Work", "Tasks for the week")
        ]
        client.async_get_board.return_value = board
        client.async_get_columns.return_value = [
            Column(10, "To do"),
            Column(11, "Done"),
        ]
        client.async_get_card_types.return_value = [CardType(20, "Task")]
        client.async_get_tags.return_value = [Tag(30, "Home")]
        client.async_get_slicks.return_value = [Slick(40, "Summer")]
        client.async_get_members.return_value = [Member(7, "alex", "Alex")]
        yield client
