"""Services for boardoil."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_ASSIGNED_USER,
    ATTR_BOARD,
    ATTR_CARD_ID,
    ATTR_CARD_TYPE,
    ATTR_COLUMN,
    ATTR_DESCRIPTION,
    ATTR_EXTERNAL_URL,
    ATTR_SLICK_NAME,
    ATTR_TAG_NAMES,
    ATTR_TITLE,
    DOMAIN,
)

if TYPE_CHECKING:
    from homeassistant.util.json import JsonObjectType, JsonValueType

    from .data import BoardOilConfigEntry

SERVICE_GET_CARD = "get_card"
SERVICE_SCHEMA_GET_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD): cv.string,
        vol.Required(ATTR_CARD_ID): cv.positive_int,
    }
)
SERVICE_GET_CARDS = "get_cards"
SERVICE_SCHEMA_GET_CARDS = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD): cv.string,
        vol.Optional(ATTR_COLUMN): cv.string,
    }
)
SERVICE_ADD_CARD = "add_card"
SERVICE_SCHEMA_ADD_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD): cv.string,
        vol.Required(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
        vol.Optional(ATTR_COLUMN): cv.string,
        vol.Optional(ATTR_CARD_TYPE): cv.string,
        vol.Optional(ATTR_TAG_NAMES): vol.Any(
            cv.string,
            vol.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
        vol.Optional(ATTR_SLICK_NAME): cv.string,
        vol.Optional(ATTR_ASSIGNED_USER): cv.string,
        vol.Optional(ATTR_EXTERNAL_URL): cv.string,
    }
)
SERVICE_UPDATE_CARD = "update_card"
SERVICE_SCHEMA_UPDATE_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD): cv.string,
        vol.Required(ATTR_CARD_ID): cv.positive_int,
        vol.Optional(ATTR_TITLE, default=""): cv.string,
        vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
        vol.Optional(ATTR_COLUMN): cv.string,
        vol.Optional(ATTR_CARD_TYPE): cv.string,
        vol.Optional(ATTR_TAG_NAMES): vol.Any(
            cv.string,
            vol.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
        vol.Optional(ATTR_SLICK_NAME): cv.string,
        vol.Optional(ATTR_ASSIGNED_USER): cv.string,
        vol.Optional(ATTR_EXTERNAL_URL): cv.string,
    }
)
SERVICE_DELETE_CARD = "delete_card"
SERVICE_SCHEMA_DELETE_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD): cv.string,
        vol.Required(ATTR_CARD_ID): cv.string,
    }
)
SERVICE_ARCHIVE_CARD = "archive_card"
SERVICE_SCHEMA_ARCHIVE_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD): cv.string,
        vol.Required(ATTR_CARD_ID): cv.string,
    }
)


def _is_valid_url(url: str) -> bool:
    """Return True if the string is a valid HTTP/HTTPS URL."""
    result = urlparse(url)
    return result.scheme in {"http", "https"} and bool(result.netloc)


def _normalize_tag_names(raw_tag_names: object) -> list[str]:
    """Normalize supported tag input formats to a list of names."""
    normalized: list[str] = []

    if raw_tag_names is None:
        return normalized

    if isinstance(raw_tag_names, str):
        normalized = [
            part.strip()
            for part in raw_tag_names.replace("\n", ",").split(",")
            if part.strip()
        ]
    elif isinstance(raw_tag_names, (list, tuple, set)):
        normalized = [str(item).strip() for item in raw_tag_names if str(item).strip()]
    elif isinstance(raw_tag_names, dict):
        nested_value = raw_tag_names.get("tag_names") or raw_tag_names.get("tags")
        if nested_value is not None:
            normalized = _normalize_tag_names(nested_value)
        else:
            value_tags = [
                value.strip()
                for value in raw_tag_names.values()
                if isinstance(value, str) and value.strip()
            ]
            normalized = value_tags or [
                key.strip() for key in raw_tag_names if key.strip()
            ]

    return normalized


class CardNotFoundError(HomeAssistantError):
    """Raised when a card id is not found in a board."""

    def __init__(self, board_id: int, card_id: int) -> None:
        """Initialize the exception."""
        msg = f"Card id {card_id} not found in board {board_id}"
        super().__init__(msg)


class BoardNotFoundError(HomeAssistantError):
    """Raised when a board id is not found."""

    def __init__(self, board: str | int) -> None:
        """Initialize the exception."""
        msg = f"Board {board} not found"
        super().__init__(msg)


class ColumnNotFoundError(HomeAssistantError):
    """Raised when a column id is not found in a board."""

    def __init__(self, board_id: int, column: str) -> None:
        """Initialize the exception."""
        msg = f"Column {column} not found in board {board_id}"
        super().__init__(msg)


class CardTypeNotFoundError(HomeAssistantError):
    """Raised when a card type id is not found in a board."""

    def __init__(self, board_id: int, card_type: str) -> None:
        """Initialize the exception."""
        msg = f"Card type {card_type} not found in board {board_id}"
        super().__init__(msg)


class UserNotFoundError(HomeAssistantError):
    """Raised when a user id is not found in a board."""

    def __init__(self, board_id: int, user: str) -> None:
        """Initialize the exception."""
        msg = f"User {user} not found in board {board_id}"
        super().__init__(msg)


async def get_board_id(entry: BoardOilConfigEntry, board_param: str) -> int:
    """Get the board id for a given board parameter."""

    boards = await entry.runtime_data.client.async_get_boards()
    matching_boards = [
        board
        for board in boards
        if board.name and board.name.casefold() == board_param.casefold()
    ]
    if not matching_boards or len(matching_boards) != 1:
        if board_param.isnumeric():
            return int(board_param)
        raise BoardNotFoundError(board_param)
    return matching_boards[0].id


async def get_column_id(
    entry: BoardOilConfigEntry, board_id: int, column_param: str | None
) -> int | None:
    """Get the column id for a given board and column parameter."""
    if column_param is None:
        return None

    columns = await entry.runtime_data.client.async_get_columns(board_id=board_id)
    matching_columns = [
        column
        for column in columns
        if column.title and column.title.casefold() == column_param.casefold()
    ]
    if not matching_columns or len(matching_columns) != 1:
        if column_param.isnumeric():
            return int(column_param)
        raise ColumnNotFoundError(board_id, column_param)
    return matching_columns[0].id


async def get_card_type_id(
    entry: BoardOilConfigEntry, board_id: int, card_type_param: str | None
) -> int | None:
    """Get the card type id for a given board and card type parameter."""
    if card_type_param is None:
        return None

    card_types = await entry.runtime_data.client.async_get_card_types(board_id=board_id)
    matching_card_types = [
        card_type
        for card_type in card_types
        if card_type.name and card_type.name.casefold() == card_type_param.casefold()
    ]
    if not matching_card_types or len(matching_card_types) != 1:
        if card_type_param.isnumeric():
            return int(card_type_param)
        raise CardTypeNotFoundError(board_id, card_type_param)
    return matching_card_types[0].id


async def get_user_id(
    entry: BoardOilConfigEntry, board_id: int, user_param: str | None
) -> int | None:
    """Get the user id for a given board and user parameter."""
    if user_param is None:
        return None

    members = await entry.runtime_data.client.async_get_members(board_id=board_id)
    matching_display_names = [
        member
        for member in members
        if member.display_name
        and member.display_name.casefold() == user_param.casefold()
    ]
    if not matching_display_names or len(matching_display_names) != 1:
        matching_usernames = [
            member
            for member in members
            if member.username and member.username.casefold() == user_param.casefold()
        ]
        if not matching_usernames or len(matching_usernames) != 1:
            if user_param.isnumeric():
                return int(user_param)
            raise UserNotFoundError(board_id, user_param)
        return matching_usernames[0].id
    return matching_display_names[0].id


async def async_get_card_service(call: ServiceCall) -> ServiceResponse:
    """Return card data for a given config entry, board id and card id."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_param = str(call.data[ATTR_BOARD])
    card_id = call.data[ATTR_CARD_ID]

    coordinator = entry.runtime_data.coordinator

    board_id = await get_board_id(entry, board_param)

    for board in coordinator.data:
        if board.id != board_id:
            continue

        for column in board.columns:
            for card in column.cards:
                if card.id != card_id:
                    continue

                return {
                    "card": {
                        **cast("JsonObjectType", card.raw_data),
                    },
                }

        raise CardNotFoundError(board_id=board_id, card_id=card_id)

    raise BoardNotFoundError(board.id)


async def async_get_cards_service(call: ServiceCall) -> ServiceResponse:
    """Return card data for a board, optionally filtered by column."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_param = str(call.data[ATTR_BOARD])
    column_param = call.data.get(ATTR_COLUMN)

    coordinator = entry.runtime_data.coordinator

    board_id = await get_board_id(entry, board_param)
    column_id = (
        await get_column_id(entry, board_id, column_param) if column_param else None
    )

    for board in coordinator.data:
        if board.id != board_id:
            continue

        cards: list[JsonValueType] = []
        if column_param is not None:
            matching_columns = [
                column for column in board.columns if column.id == column_id
            ]

            if not matching_columns:
                raise ColumnNotFoundError(board_id=board_id, column=column_param)
        else:
            matching_columns = board.columns

        for column in matching_columns:
            cards.extend(
                {
                    "card": {
                        **cast("JsonObjectType", card.raw_data),
                    },
                }
                for card in column.cards
            )

        return {
            "cards": cards,
        }

    raise BoardNotFoundError(board_param)


async def async_add_card_service(call: ServiceCall) -> None:
    """Add a card to a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    tag_names = _normalize_tag_names(call.data.get(ATTR_TAG_NAMES))
    url = call.data.get(ATTR_EXTERNAL_URL)
    if url and not _is_valid_url(url):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_url",
        )

    board_param = str(call.data[ATTR_BOARD])
    column_param = call.data.get(ATTR_COLUMN)
    card_type_param = call.data.get(ATTR_CARD_TYPE)
    assigned_user_param = call.data.get(ATTR_ASSIGNED_USER)

    board_id = await get_board_id(entry, board_param)
    column_id = (
        await get_column_id(entry, board_id, column_param) if column_param else None
    )
    card_type_id = (
        await get_card_type_id(entry, board_id, card_type_param)
        if card_type_param
        else None
    )
    assigned_user_id = (
        await get_user_id(entry, board_id, assigned_user_param)
        if assigned_user_param
        else None
    )

    await entry.runtime_data.client.async_add_card(
        board_id=board_id,
        column_id=column_id,
        title=call.data[ATTR_TITLE],
        description=call.data.get(ATTR_DESCRIPTION, ""),
        tag_names=tag_names,
        card_type_id=card_type_id,
        slick_name=call.data.get(ATTR_SLICK_NAME),
        assigned_user_id=assigned_user_id,
        external_url=url,
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_update_card_service(call: ServiceCall) -> None:
    """Update a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_param = str(call.data[ATTR_BOARD])
    card_id = call.data[ATTR_CARD_ID]
    column_param = call.data.get(ATTR_COLUMN)
    card_type_param = call.data.get(ATTR_CARD_TYPE)
    assigned_user_param = call.data.get(ATTR_ASSIGNED_USER)

    board_id = await get_board_id(entry, board_param)
    column_id = (
        await get_column_id(entry, board_id, column_param) if column_param else None
    )
    card_type_id = (
        await get_card_type_id(entry, board_id, card_type_param)
        if card_type_param
        else None
    )
    assigned_user_id = (
        await get_user_id(entry, board_id, assigned_user_param)
        if assigned_user_param
        else None
    )

    tag_names = _normalize_tag_names(call.data.get(ATTR_TAG_NAMES))
    url = call.data.get(ATTR_EXTERNAL_URL)
    if url and not _is_valid_url(url):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_url",
        )

    # Refresh coordinator to get latest data
    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()

    # Find existing card in coordinator data
    existing_card_raw: JsonObjectType | None = None

    for board in coordinator.data:
        if board.id != board_id:
            continue

        for column in board.columns:
            for card in column.cards:
                if card.id != card_id:
                    continue
                existing_card_raw = cast("JsonObjectType", card.raw_data)
                break
            if existing_card_raw:
                break

        if existing_card_raw is None:
            raise CardNotFoundError(board_id=board_id, card_id=card_id)
        break

    if existing_card_raw is None:
        raise BoardNotFoundError(board_id)

    # Apply new values to existing card data
    existing_title = existing_card_raw.get("title", "")
    existing_title_str: str = existing_title if isinstance(existing_title, str) else ""
    existing_description = existing_card_raw.get("description", "")
    existing_description_str: str = (
        existing_description if isinstance(existing_description, str) else ""
    )
    existing_tag_names = existing_card_raw.get("tagNames", [])
    existing_tag_names_list: list[str] = (
        [str(tag) for tag in existing_tag_names]
        if isinstance(existing_tag_names, list)
        else []
    )
    existing_external_url = existing_card_raw.get("externalUrl")
    existing_external_url_str: str | None = (
        existing_external_url
        if existing_external_url is None or isinstance(existing_external_url, str)
        else None
    )
    existing_card_type_id = existing_card_raw.get("cardTypeId")
    existing_card_type_id_int: int | None = (
        existing_card_type_id if isinstance(existing_card_type_id, int) else None
    )
    existing_assigned_user_id = existing_card_raw.get("assignedUserId")
    existing_assigned_user_id_int: int | None = (
        existing_assigned_user_id
        if isinstance(existing_assigned_user_id, int)
        else None
    )

    await entry.runtime_data.client.async_update_card(
        board_id=board_id,
        card_id=card_id,
        title=call.data.get(ATTR_TITLE) or existing_title_str,
        description=call.data.get(ATTR_DESCRIPTION) or existing_description_str,
        tag_names=tag_names or existing_tag_names_list,
        column_id=column_id or call.data.get(ATTR_COLUMN),
        card_type_id=card_type_id or existing_card_type_id_int,
        assigned_user_id=assigned_user_id or existing_assigned_user_id_int,
        slick_name=call.data.get(ATTR_SLICK_NAME, existing_card_raw.get("slickName")),
        external_url=url or existing_external_url_str,
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_delete_card_service(call: ServiceCall) -> None:
    """Delete a card from a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    board_param = str(call.data[ATTR_BOARD])
    board_id = await get_board_id(entry, board_param)

    await entry.runtime_data.client.async_delete_card(
        board_id=board_id,
        card_id=call.data[ATTR_CARD_ID],
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_archive_card_service(call: ServiceCall) -> None:
    """Archive a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    board_param = str(call.data[ATTR_BOARD])
    board_id = await get_board_id(entry, board_param)

    await entry.runtime_data.client.async_archive_card(
        board_id=board_id,
        card_id=call.data[ATTR_CARD_ID],
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up boardoil services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CARD,
        async_get_card_service,
        schema=SERVICE_SCHEMA_GET_CARD,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CARDS,
        async_get_cards_service,
        schema=SERVICE_SCHEMA_GET_CARDS,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_CARD,
        async_add_card_service,
        schema=SERVICE_SCHEMA_ADD_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_CARD,
        async_update_card_service,
        schema=SERVICE_SCHEMA_UPDATE_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_CARD,
        async_delete_card_service,
        schema=SERVICE_SCHEMA_DELETE_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ARCHIVE_CARD,
        async_archive_card_service,
        schema=SERVICE_SCHEMA_ARCHIVE_CARD,
        supports_response=SupportsResponse.NONE,
    )
