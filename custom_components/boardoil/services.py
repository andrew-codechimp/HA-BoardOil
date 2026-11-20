"""Services for boardoil."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, cast
from urllib.parse import urlparse

import probatio

from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .api import (
    BoardOilApiClientCommunicationError,
)
from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.util.json import JsonObjectType, JsonValueType

    from .data import BoardOilConfigEntry


class BoardOilService(StrEnum):
    """Service names for BoardOil."""

    ADD_CARD = "add_card"
    ADD_CARD_COMMENT = "add_card_comment"
    ARCHIVE_CARD = "archive_card"
    DELETE_CARD = "delete_card"
    GET_CARD = "get_card"
    GET_CARDS = "get_cards"
    UPDATE_CARD = "update_card"


class BoardOilServiceArgument(StrEnum):
    """Service argument names for BoardOil."""

    ASSIGNED_USER = "assigned_user"
    BOARD = "board"
    CARD_ID = "card_id"
    CARD_TYPE = "card_type"
    COLUMN = "column"
    COMMENT = "comment"
    DESCRIPTION = "description"
    EXTERNAL_URL = "external_url"
    SLICK_NAME = "slick_name"
    TAG_NAMES = "tag_names"
    TITLE = "title"


SERVICE_SCHEMA_GET_CARD = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Required(BoardOilServiceArgument.CARD_ID): cv.positive_int,
    }
)
SERVICE_SCHEMA_GET_CARDS = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Optional(BoardOilServiceArgument.COLUMN): cv.string,
    }
)
SERVICE_SCHEMA_ADD_CARD = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Required(BoardOilServiceArgument.TITLE): cv.string,
        probatio.Optional(BoardOilServiceArgument.DESCRIPTION, default=""): cv.string,
        probatio.Optional(BoardOilServiceArgument.COLUMN): cv.string,
        probatio.Optional(BoardOilServiceArgument.CARD_TYPE): cv.string,
        probatio.Optional(BoardOilServiceArgument.TAG_NAMES): probatio.Any(
            cv.string,
            probatio.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
        probatio.Optional(BoardOilServiceArgument.SLICK_NAME): cv.string,
        probatio.Optional(BoardOilServiceArgument.ASSIGNED_USER): cv.string,
        probatio.Optional(BoardOilServiceArgument.EXTERNAL_URL): cv.string,
    }
)
SERVICE_SCHEMA_UPDATE_CARD = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Required(BoardOilServiceArgument.CARD_ID): cv.positive_int,
        probatio.Optional(BoardOilServiceArgument.TITLE, default=""): cv.string,
        probatio.Optional(BoardOilServiceArgument.DESCRIPTION, default=""): cv.string,
        probatio.Optional(BoardOilServiceArgument.COLUMN): cv.string,
        probatio.Optional(BoardOilServiceArgument.CARD_TYPE): cv.string,
        probatio.Optional(BoardOilServiceArgument.TAG_NAMES): probatio.Any(
            cv.string,
            probatio.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
        probatio.Optional(BoardOilServiceArgument.SLICK_NAME): cv.string,
        probatio.Optional(BoardOilServiceArgument.ASSIGNED_USER): cv.string,
        probatio.Optional(BoardOilServiceArgument.EXTERNAL_URL): cv.string,
    }
)
SERVICE_SCHEMA_DELETE_CARD = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Required(BoardOilServiceArgument.CARD_ID): cv.string,
    }
)
SERVICE_SCHEMA_ARCHIVE_CARD = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Required(BoardOilServiceArgument.CARD_ID): cv.string,
    }
)
SERVICE_SCHEMA_ADD_CARD_COMMENT = probatio.Schema(
    {
        probatio.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        probatio.Required(BoardOilServiceArgument.BOARD): cv.string,
        probatio.Required(BoardOilServiceArgument.CARD_ID): cv.positive_int,
        probatio.Required(BoardOilServiceArgument.COMMENT): cv.string,
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
        nested_value = raw_tag_names.get(
            BoardOilServiceArgument.TAG_NAMES
        ) or raw_tag_names.get("tags")
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


class CardNotFoundError(ServiceValidationError):
    """Raised when a card id is not found in a board."""

    def __init__(self, board_id: int, card_id: int) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="card_not_found",
            translation_placeholders={
                "board_id": str(board_id),
                "card_id": str(card_id),
            },
        )


class BoardNotFoundError(ServiceValidationError):
    """Raised when a board id is not found."""

    def __init__(self, board: str | int) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="board_not_found",
            translation_placeholders={"board": str(board)},
        )


class ColumnNotFoundError(ServiceValidationError):
    """Raised when a column id is not found in a board."""

    def __init__(self, board_id: int, column: str) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="column_not_found",
            translation_placeholders={"board_id": str(board_id), "column": column},
        )


class CardTypeNotFoundError(ServiceValidationError):
    """Raised when a card type id is not found in a board."""

    def __init__(self, board_id: int, card_type: str) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="card_type_not_found",
            translation_placeholders={
                "board_id": str(board_id),
                "card_type": card_type,
            },
        )


class UserNotFoundError(ServiceValidationError):
    """Raised when a user id is not found in a board."""

    def __init__(self, board_id: int, user: str) -> None:
        """Initialize the exception."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="user_not_found",
            translation_placeholders={"board_id": str(board_id), "user": user},
        )


async def _get_board_id(entry: BoardOilConfigEntry, board_param: str) -> int:
    """Get the board id for a given board parameter."""

    board_param = board_param.strip()
    try:
        boards = await entry.runtime_data.client.async_get_boards()
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex

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


async def _get_column_id(
    entry: BoardOilConfigEntry, board_id: int, column_param: str | None
) -> int | None:
    """Get the column id for a given board and column parameter."""
    if column_param is None:
        return None

    column_param = column_param.strip()

    try:
        columns = await entry.runtime_data.client.async_get_columns(board_id=board_id)
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex

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


async def _get_card_type_id(
    entry: BoardOilConfigEntry, board_id: int, card_type_param: str | None
) -> int | None:
    """Get the card type id for a given board and card type parameter."""
    if card_type_param is None:
        return None

    card_type_param = card_type_param.strip()

    try:
        card_types = await entry.runtime_data.client.async_get_card_types(
            board_id=board_id
        )
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex

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


async def _get_user_id(
    entry: BoardOilConfigEntry, board_id: int, user_param: str | None
) -> int | None:
    """Get the user id for a given board and user parameter."""
    if user_param is None:
        return None

    user_param = user_param.strip()

    try:
        members = await entry.runtime_data.client.async_get_members(board_id=board_id)
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex

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
    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    card_id = call.data[BoardOilServiceArgument.CARD_ID]

    coordinator = entry.runtime_data.coordinator

    board_id = await _get_board_id(entry, board_param)

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

    raise BoardNotFoundError(board_param)


async def async_get_cards_service(call: ServiceCall) -> ServiceResponse:
    """Return card data for a board, optionally filtered by column."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    column_param = call.data.get(BoardOilServiceArgument.COLUMN)

    coordinator = entry.runtime_data.coordinator

    board_id = await _get_board_id(entry, board_param)
    column_id = (
        await _get_column_id(entry, board_id, column_param) if column_param else None
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
    tag_names = _normalize_tag_names(call.data.get(BoardOilServiceArgument.TAG_NAMES))
    url = call.data.get(BoardOilServiceArgument.EXTERNAL_URL)
    if url and not _is_valid_url(url):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_url",
        )

    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    column_param = call.data.get(BoardOilServiceArgument.COLUMN)
    card_type_param = call.data.get(BoardOilServiceArgument.CARD_TYPE)
    assigned_user_param = call.data.get(BoardOilServiceArgument.ASSIGNED_USER)

    board_id = await _get_board_id(entry, board_param)
    column_id = (
        await _get_column_id(entry, board_id, column_param) if column_param else None
    )
    card_type_id = (
        await _get_card_type_id(entry, board_id, card_type_param)
        if card_type_param
        else None
    )
    assigned_user_id = (
        await _get_user_id(entry, board_id, assigned_user_param)
        if assigned_user_param
        else None
    )

    try:
        await entry.runtime_data.client.async_add_card(
            board_id=board_id,
            column_id=column_id,
            title=call.data[BoardOilServiceArgument.TITLE],
            description=call.data.get(BoardOilServiceArgument.DESCRIPTION, ""),
            tag_names=tag_names,
            card_type_id=card_type_id,
            slick_name=call.data.get(BoardOilServiceArgument.SLICK_NAME),
            assigned_user_id=assigned_user_id,
            external_url=url,
        )
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_update_card_service(call: ServiceCall) -> None:
    """Update a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    card_id = call.data[BoardOilServiceArgument.CARD_ID]
    column_param = call.data.get(BoardOilServiceArgument.COLUMN)
    card_type_param = call.data.get(BoardOilServiceArgument.CARD_TYPE)
    assigned_user_param = call.data.get(BoardOilServiceArgument.ASSIGNED_USER)

    board_id = await _get_board_id(entry, board_param)
    column_id = (
        await _get_column_id(entry, board_id, column_param) if column_param else None
    )
    card_type_id = (
        await _get_card_type_id(entry, board_id, card_type_param)
        if card_type_param
        else None
    )
    assigned_user_id = (
        await _get_user_id(entry, board_id, assigned_user_param)
        if assigned_user_param
        else None
    )

    tag_names = _normalize_tag_names(call.data.get(BoardOilServiceArgument.TAG_NAMES))
    url = call.data.get(BoardOilServiceArgument.EXTERNAL_URL)
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

    try:
        await entry.runtime_data.client.async_update_card(
            board_id=board_id,
            card_id=card_id,
            title=call.data.get(BoardOilServiceArgument.TITLE) or existing_title_str,
            description=call.data.get(BoardOilServiceArgument.DESCRIPTION)
            or existing_description_str,
            tag_names=tag_names or existing_tag_names_list,
            column_id=column_id or call.data.get(BoardOilServiceArgument.COLUMN),
            card_type_id=card_type_id or existing_card_type_id_int,
            assigned_user_id=assigned_user_id or existing_assigned_user_id_int,
            slick_name=call.data.get(
                BoardOilServiceArgument.SLICK_NAME, existing_card_raw.get("slickName")
            ),
            external_url=url or existing_external_url_str,
        )
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_delete_card_service(call: ServiceCall) -> None:
    """Delete a card from a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    board_id = await _get_board_id(entry, board_param)

    try:
        await entry.runtime_data.client.async_delete_card(
            board_id=board_id,
            card_id=call.data[BoardOilServiceArgument.CARD_ID],
        )
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_archive_card_service(call: ServiceCall) -> None:
    """Archive a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    board_id = await _get_board_id(entry, board_param)

    try:
        await entry.runtime_data.client.async_archive_card(
            board_id=board_id,
            card_id=call.data[BoardOilServiceArgument.CARD_ID],
        )
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_add_card_comment_service(call: ServiceCall) -> None:
    """Add a comment to a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    board_param = str(call.data[BoardOilServiceArgument.BOARD])
    board_id = await _get_board_id(entry, board_param)

    try:
        await entry.runtime_data.client.async_add_card_comment(
            board_id=board_id,
            card_id=call.data[BoardOilServiceArgument.CARD_ID],
            comment=call.data[BoardOilServiceArgument.COMMENT],
        )
    except BoardOilApiClientCommunicationError as ex:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="connection_error",
        ) from ex
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up boardoil services."""
    hass.services.async_register(
        DOMAIN,
        BoardOilService.GET_CARD,
        async_get_card_service,
        schema=SERVICE_SCHEMA_GET_CARD,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        BoardOilService.GET_CARDS,
        async_get_cards_service,
        schema=SERVICE_SCHEMA_GET_CARDS,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        BoardOilService.ADD_CARD,
        async_add_card_service,
        schema=SERVICE_SCHEMA_ADD_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        BoardOilService.UPDATE_CARD,
        async_update_card_service,
        schema=SERVICE_SCHEMA_UPDATE_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        BoardOilService.DELETE_CARD,
        async_delete_card_service,
        schema=SERVICE_SCHEMA_DELETE_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        BoardOilService.ARCHIVE_CARD,
        async_archive_card_service,
        schema=SERVICE_SCHEMA_ARCHIVE_CARD,
        supports_response=SupportsResponse.NONE,
    )
    hass.services.async_register(
        DOMAIN,
        BoardOilService.ADD_CARD_COMMENT,
        async_add_card_comment_service,
        schema=SERVICE_SCHEMA_ADD_CARD_COMMENT,
        supports_response=SupportsResponse.NONE,
    )
