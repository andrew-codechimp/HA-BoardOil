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
    ATTR_ASSIGNED_USER_ID,
    ATTR_BOARD_ID,
    ATTR_CARD_ID,
    ATTR_CARD_TYPE_ID,
    ATTR_COLUMN_ID,
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
        vol.Required(ATTR_BOARD_ID): cv.positive_int,
        vol.Required(ATTR_CARD_ID): cv.positive_int,
    }
)
SERVICE_GET_CARDS = "get_cards"
SERVICE_SCHEMA_GET_CARDS = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD_ID): cv.positive_int,
        vol.Optional(ATTR_COLUMN_ID): cv.positive_int,
    }
)
SERVICE_ADD_CARD = "add_card"
SERVICE_SCHEMA_ADD_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD_ID): cv.positive_int,
        vol.Optional(ATTR_COLUMN_ID): cv.positive_int,
        vol.Optional(ATTR_CARD_TYPE_ID): cv.positive_int,
        vol.Required(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
        vol.Optional(ATTR_TAG_NAMES): vol.Any(
            cv.string,
            vol.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
        vol.Optional(ATTR_SLICK_NAME): cv.string,
        vol.Optional(ATTR_EXTERNAL_URL): cv.string,
    }
)
SERVICE_UPDATE_CARD = "update_card"
SERVICE_SCHEMA_UPDATE_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD_ID): cv.positive_int,
        vol.Required(ATTR_CARD_ID): cv.positive_int,
        vol.Required(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_DESCRIPTION, default=""): cv.string,
        vol.Optional(ATTR_TAG_NAMES): vol.Any(
            cv.string,
            vol.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
        vol.Optional(ATTR_COLUMN_ID): cv.positive_int,
        vol.Optional(ATTR_CARD_TYPE_ID): cv.positive_int,
        vol.Optional(ATTR_ASSIGNED_USER_ID): cv.positive_int,
        vol.Optional(ATTR_SLICK_NAME): cv.string,
        vol.Optional(ATTR_EXTERNAL_URL): cv.string,
    }
)
SERVICE_DELETE_CARD = "delete_card"
SERVICE_SCHEMA_DELETE_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD_ID): cv.positive_int,
        vol.Required(ATTR_CARD_ID): cv.positive_int,
    }
)
SERVICE_ARCHIVE_CARD = "archive_card"
SERVICE_SCHEMA_ARCHIVE_CARD = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_BOARD_ID): cv.positive_int,
        vol.Required(ATTR_CARD_ID): cv.positive_int,
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

    def __init__(self, board_id: int) -> None:
        """Initialize the exception."""
        msg = f"Board id {board_id} not found"
        super().__init__(msg)


class ColumnNotFoundError(HomeAssistantError):
    """Raised when a column id is not found in a board."""

    def __init__(self, board_id: int, column_id: int) -> None:
        """Initialize the exception."""
        msg = f"Column id {column_id} not found in board {board_id}"
        super().__init__(msg)


async def async_get_card_service(call: ServiceCall) -> ServiceResponse:
    """Return card data for a given config entry, board id and card id."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_id = call.data[ATTR_BOARD_ID]
    card_id = call.data[ATTR_CARD_ID]

    coordinator = entry.runtime_data.coordinator

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

    raise BoardNotFoundError(board_id)


async def async_get_cards_service(call: ServiceCall) -> ServiceResponse:
    """Return card data for a board, optionally filtered by column."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_id = call.data[ATTR_BOARD_ID]
    column_id = call.data.get(ATTR_COLUMN_ID)

    coordinator = entry.runtime_data.coordinator

    for board in coordinator.data:
        if board.id != board_id:
            continue

        cards: list[JsonValueType] = []
        matching_columns = (
            [column for column in board.columns if column.id == column_id]
            if column_id is not None
            else board.columns
        )

        if column_id is not None and not matching_columns:
            raise ColumnNotFoundError(board_id=board_id, column_id=column_id)

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

    raise BoardNotFoundError(board_id)


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

    await entry.runtime_data.client.async_add_card(
        board_id=call.data[ATTR_BOARD_ID],
        column_id=call.data.get(ATTR_COLUMN_ID),
        title=call.data[ATTR_TITLE],
        description=call.data.get(ATTR_DESCRIPTION, ""),
        tag_names=tag_names,
        card_type_id=call.data.get(ATTR_CARD_TYPE_ID),
        slick_name=call.data.get(ATTR_SLICK_NAME),
        external_url=url,
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_update_card_service(call: ServiceCall) -> None:
    """Update a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )
    board_id = call.data[ATTR_BOARD_ID]
    card_id = call.data[ATTR_CARD_ID]

    tag_names = _normalize_tag_names(call.data.get(ATTR_TAG_NAMES))
    url = call.data.get(ATTR_EXTERNAL_URL)
    if url and not _is_valid_url(url):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_url",
        )

    # Find existing card in coordinator data
    coordinator = entry.runtime_data.coordinator
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

    await entry.runtime_data.client.async_update_card(
        board_id=board_id,
        card_id=card_id,
        title=call.data[ATTR_TITLE],
        description=call.data.get(ATTR_DESCRIPTION) or existing_description_str,
        tag_names=tag_names or existing_tag_names_list,
        column_id=call.data.get(ATTR_COLUMN_ID),
        card_type_id=call.data.get(
            ATTR_CARD_TYPE_ID, existing_card_raw.get("cardTypeId")
        ),
        assigned_user_id=call.data.get(
            ATTR_ASSIGNED_USER_ID, existing_card_raw.get("assignedUserId")
        ),
        slick_name=call.data.get(ATTR_SLICK_NAME, existing_card_raw.get("slickName")),
        external_url=url or existing_external_url_str,
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_delete_card_service(call: ServiceCall) -> None:
    """Delete a card from a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    await entry.runtime_data.client.async_delete_card(
        board_id=call.data[ATTR_BOARD_ID],
        card_id=call.data[ATTR_CARD_ID],
    )
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_archive_card_service(call: ServiceCall) -> None:
    """Archive a card on a board."""
    entry: BoardOilConfigEntry = service.async_get_config_entry(
        call.hass, DOMAIN, call.data[ATTR_CONFIG_ENTRY_ID]
    )

    await entry.runtime_data.client.async_archive_card(
        board_id=call.data[ATTR_BOARD_ID],
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
