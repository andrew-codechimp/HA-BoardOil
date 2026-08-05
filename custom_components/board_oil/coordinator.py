"""DataUpdateCoordinator for board_oil."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientError,
)

if TYPE_CHECKING:
    from .data import BoardOilConfigEntry

from .const import (
    EVENT_TYPE_CARD_CREATED,
    EVENT_TYPE_CARD_MOVED,
    EVENT_TYPE_CARD_REMOVED,
    EVENT_TYPE_CARD_UPDATED,
    LOGGER,
)

type EventCallback = Callable[[BoardOilEventData], None]


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
    card_type_id: int
    card_type_name: str
    card_type_emoji: str
    title: str
    description: str
    sort_key: str
    tag_names: list[str]
    updated_at_utc: str
    assigned_user_id: int | None
    assigned_user_name: str | None
    external_url: str | None
    slick_id: int | None
    slick_name: str | None
    raw_data: dict[str, Any]


@dataclass
class BoardOilEventData:
    """Data for a single event."""

    event_type: str
    card_id: int
    board_id: int
    card_type_id: int
    card_type_name: str
    card_type_emoji: str
    title: str
    description: str
    sort_key: str
    tag_names: list[str]
    updated_at_utc: str
    assigned_user_id: int | None
    assigned_user_name: str | None
    external_url: str | None
    slick_id: int | None = None
    slick_name: str | None = None
    old_column_id: int | None = None
    new_column_id: int | None = None


class CardChangeType(StrEnum):
    """Enumeration of card change types."""

    CREATED = EVENT_TYPE_CARD_CREATED
    MOVED = EVENT_TYPE_CARD_MOVED
    UPDATED = EVENT_TYPE_CARD_UPDATED
    REMOVED = EVENT_TYPE_CARD_REMOVED


@dataclass
class CardChange:
    """Represents changes to a single card."""

    card_id: int
    board_id: int
    change_type: CardChangeType
    old_card: Card | None = None
    new_card: Card | None = None
    old_column_id: int | None = None
    new_column_id: int | None = None


@dataclass
class BoardChanges:
    """Represents all changes detected in a board."""

    board_id: int
    card_changes: list[CardChange]

    def new_cards(self) -> list[CardChange]:
        """Get all new cards."""
        return [c for c in self.card_changes if c.change_type == CardChangeType.CREATED]

    def removed_cards(self) -> list[CardChange]:
        """Get all removed cards (deleted or archived)."""
        return [c for c in self.card_changes if c.change_type == CardChangeType.REMOVED]

    def moved_cards(self) -> list[CardChange]:
        """Get all cards that changed columns."""
        return [c for c in self.card_changes if c.change_type == CardChangeType.MOVED]

    def updated_cards(self) -> list[CardChange]:
        """Get all modified cards."""
        return [c for c in self.card_changes if c.change_type == CardChangeType.UPDATED]

    def has_changes(self) -> bool:
        """Check if any changes were detected."""
        return len(self.card_changes) > 0


class BoardOilDataUpdateCoordinator(DataUpdateCoordinator[list[BoardData]]):
    """Class to manage fetching data from the API."""

    config_entry: BoardOilConfigEntry

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the coordinator."""
        super().__init__(*args, **kwargs)
        self.boards: list[BoardData] = []
        self._previous_boards: list[BoardData] = []
        self._event_listeners: dict[int | str, EventCallback] = {}
        self._first_refresh: bool = True

    def get_board_changes(self, board_id: int) -> BoardChanges:
        """Compare current board state with previous and return detected changes.

        Args:
            board_id: The board ID to check for changes

        Returns:
            BoardChanges object containing all detected changes

        """
        old_board = next((b for b in self._previous_boards if b.id == board_id), None)
        new_board = next((b for b in self.boards if b.id == board_id), None)

        changes: list[CardChange] = []

        if new_board is None:
            # Board was deleted
            if old_board is not None:
                removed_changes = [
                    CardChange(
                        card_id=card.id,
                        board_id=board_id,
                        change_type=CardChangeType.REMOVED,
                        old_card=card,
                        old_column_id=column.id,
                    )
                    for column in old_board.columns
                    for card in column.cards
                ]
                changes.extend(removed_changes)
            return BoardChanges(board_id=board_id, card_changes=changes)

        if old_board is None:
            # Board is new, all cards are new
            new_changes = [
                CardChange(
                    card_id=card.id,
                    board_id=board_id,
                    change_type=CardChangeType.CREATED,
                    new_card=card,
                    new_column_id=column.id,
                )
                for column in new_board.columns
                for card in column.cards
            ]
            changes.extend(new_changes)
            return BoardChanges(board_id=board_id, card_changes=changes)

        # Build maps of cards by ID for comparison
        old_cards_map: dict[int, tuple[Card, int]] = {}  # card_id -> (card, column_id)
        for column in old_board.columns:
            for card in column.cards:
                old_cards_map[card.id] = (card, column.id)

        new_cards_map: dict[int, tuple[Card, int]] = {}  # card_id -> (card, column_id)
        for column in new_board.columns:
            for card in column.cards:
                new_cards_map[card.id] = (card, column.id)

        # Detect new and modified cards
        new_or_modified = []
        for card_id, (new_card, new_column_id) in new_cards_map.items():
            if card_id not in old_cards_map:
                # New card
                new_or_modified.append(
                    CardChange(
                        card_id=card_id,
                        board_id=board_id,
                        change_type=CardChangeType.CREATED,
                        new_card=new_card,
                        new_column_id=new_column_id,
                    )
                )
            else:
                old_card, old_column_id = old_cards_map[card_id]

                # Check if column changed
                if old_column_id != new_column_id:
                    new_or_modified.append(
                        CardChange(
                            card_id=card_id,
                            board_id=board_id,
                            change_type=CardChangeType.MOVED,
                            old_card=old_card,
                            new_card=new_card,
                            old_column_id=old_column_id,
                            new_column_id=new_column_id,
                        )
                    )
                # Check if card content changed
                elif self._card_changed(old_card, new_card):
                    new_or_modified.append(
                        CardChange(
                            card_id=card_id,
                            board_id=board_id,
                            change_type=CardChangeType.UPDATED,
                            old_card=old_card,
                            new_card=new_card,
                            old_column_id=old_column_id,
                            new_column_id=new_column_id,
                        )
                    )
        changes.extend(new_or_modified)

        # Detect removed cards (deleted or archived)
        removed = [
            CardChange(
                card_id=card_id,
                board_id=board_id,
                change_type=CardChangeType.REMOVED,
                old_card=old_card,
                old_column_id=old_column_id,
            )
            for card_id, (old_card, old_column_id) in old_cards_map.items()
            if card_id not in new_cards_map
        ]
        changes.extend(removed)

        return BoardChanges(board_id=board_id, card_changes=changes)

    def _card_changed(self, old_card: Card, new_card: Card) -> bool:
        """Check if a card's content has changed."""
        return old_card.updated_at_utc != new_card.updated_at_utc

    async def _async_update_data(self) -> list[BoardData]:
        """Update data via client."""
        # Store previous boards for change detection
        self._previous_boards = self.boards.copy()

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
                            id=card_data["id"],
                            card_type_id=card_data["cardTypeId"],
                            card_type_name=card_data["cardTypeName"],
                            card_type_emoji=card_data.get("cardTypeEmoji", ""),
                            title=card_data.get("title", ""),
                            description=card_data.get("description", ""),
                            sort_key=card_data.get("sortKey", ""),
                            tag_names=card_data.get("tagNames", []),
                            updated_at_utc=card_data.get("updatedAtUtc", ""),
                            assigned_user_id=card_data.get("assignedUserId"),
                            assigned_user_name=card_data.get("assignedUserName"),
                            external_url=card_data.get("externalUrl"),
                            slick_id=card_data.get("slickId"),
                            slick_name=card_data.get("slickName"),
                            raw_data=card_data,
                        )
                        for card in column.get("cards", [])
                        if isinstance(card, dict)
                        if (card_data := dict(card))
                    ]
                    columns.append(
                        ColumnData(
                            id=column["id"],
                            title=column.get("title", ""),
                            cards=cards,
                        )
                    )

                self.boards.append(
                    BoardData(
                        id=board_id,
                        name=board_data.get("name", ""),
                        columns=columns,
                    )
                )

        except BoardOilApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except BoardOilApiClientError as exception:
            raise UpdateFailed(exception) from exception

        if self._first_refresh:
            for board in self.boards:
                changes = self.get_board_changes(board.id)
                if changes.has_changes():
                    LOGGER.debug(
                        "Detected changes in board %s: %s", board.name, changes
                    )
                    for change in changes.card_changes:
                        card = (
                            change.new_card
                            if change.new_card is not None
                            else change.old_card
                        )
                        event = BoardOilEventData(
                            event_type=change.change_type.value,
                            card_id=change.card_id,
                            board_id=change.board_id,
                            card_type_id=card.card_type_id,
                            card_type_name=card.card_type_name,
                            card_type_emoji=card.card_type_emoji,
                            title=card.title,
                            description=card.description,
                            sort_key=card.sort_key,
                            tag_names=card.tag_names,
                            updated_at_utc=card.updated_at_utc,
                            assigned_user_id=card.assigned_user_id,
                            assigned_user_name=card.assigned_user_name,
                            external_url=card.external_url,
                            slick_id=card.slick_id,
                            slick_name=card.slick_name,
                            old_column_id=change.old_column_id,
                            new_column_id=change.new_column_id,
                        )
                        self._async_notify_event_listeners(event)

        self._first_refresh = False

        return self.boards

    @callback
    def async_add_event_listener(
        self, update_callback: EventCallback, target_event_id: int | str
    ) -> Callable[[], None]:
        """Listen for updates."""
        self._event_listeners[target_event_id] = update_callback
        return partial(self.__async_remove_listener_internal, target_event_id)

    def __async_remove_listener_internal(self, listener_id: int | str) -> None:
        self._event_listeners.pop(listener_id, None)

    @callback
    def _async_notify_event_listeners(self, event: BoardOilEventData) -> None:
        """Notify event listeners in the event loop."""
        for listener in list(self._event_listeners.values()):
            listener(event)
