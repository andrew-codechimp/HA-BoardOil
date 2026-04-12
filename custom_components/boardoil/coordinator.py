"""DataUpdateCoordinator for boardoil."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientError,
)

if TYPE_CHECKING:
    from .data import BoardOilConfigEntry


@dataclass
class BoardData:
    """Data class for board data."""

    id: int
    name: str
    columns: list[ColumnData]


@dataclass
class ColumnData:
    """Data class for column data."""

    id: int
    title: str
    cards: list[Card]


@dataclass
class Card:
    """Data class for card data."""

    id: int
    card_type_name: str
    title: str
    description: str
    raw_data: dict[str, Any]


class BoardOilDataUpdateCoordinator(DataUpdateCoordinator[list[BoardData]]):
    """Class to manage fetching data from the API."""

    config_entry: BoardOilConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(*args, **kwargs)
        self.boards: list[BoardData] = []

    async def _async_update_data(self) -> list[BoardData]:
        """Update data via client."""
        client = self.config_entry.runtime_data.client
        try:
            board_list = await client.async_get_boards()
            self.boards = []

            for board_summary in board_list.get("data", []):
                board_id = board_summary.get("id")
                if board_id is None:
                    continue

                board = await client.async_get_board(board_id)
                board_data = board.get("data", {})

                columns: list[ColumnData] = []
                for column in board_data.get("columns", []):
                    cards = [
                        Card(
                            id=card_data.get("id", 0),
                            card_type_name=card_data.get("cardTypeName", ""),
                            title=card_data.get("title", ""),
                            description=card_data.get("description", ""),
                            raw_data=card_data,
                        )
                        for card in column.get("cards", [])
                        if isinstance(card, dict)
                        if (card_data := dict(card))
                    ]
                    columns.append(
                        ColumnData(
                            id=column.get("id", 0),
                            title=column.get("title", ""),
                            cards=cards,
                        )
                    )

                self.boards.append(
                    BoardData(
                        id=board_data.get("id", board_id),
                        name=board_data.get("name", ""),
                        columns=columns,
                    )
                )

        except BoardOilApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except BoardOilApiClientError as exception:
            raise UpdateFailed(exception) from exception
        else:
            return self.boards
