"""Services for boardoil."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

if TYPE_CHECKING:
    from .data import BoardOilConfigEntry

SERVICE_GET_CARD = "get_card"
SERVICE_SCHEMA_GET_CARD = vol.Schema(
    {
        vol.Required("config_entry"): cv.string,
        vol.Required("board_id"): cv.positive_int,
        vol.Required("card_id"): cv.positive_int,
    }
)
SERVICE_ADD_CARD = "add_card"
SERVICE_SCHEMA_ADD_CARD = vol.Schema(
    {
        vol.Required("config_entry"): cv.string,
        vol.Required("board_id"): cv.positive_int,
        vol.Required("column_id"): cv.positive_int,
        vol.Required("card_type_id"): cv.positive_int,
        vol.Required("title"): cv.string,
        vol.Required("description"): cv.string,
        vol.Optional("tag_names"): vol.Any(
            cv.string,
            vol.All(cv.ensure_list, [cv.string]),
            {cv.string: object},
        ),
    }
)


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


class InvalidConfigEntryError(HomeAssistantError):
    """Raised when a config entry id is invalid for this domain."""

    def __init__(self) -> None:
        """Initialize the exception."""
        msg = "Invalid BoardOil config entry"
        super().__init__(msg)


async def async_get_card_service(call: ServiceCall) -> dict[str, object]:
    """Return card data for a given config entry, board id and card id."""
    config_entry_id = call.data["config_entry"]
    board_id = call.data["board_id"]
    card_id = call.data["card_id"]

    entry = call.hass.config_entries.async_get_entry(config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise InvalidConfigEntryError

    boardoil_entry = cast("BoardOilConfigEntry", entry)
    coordinator = boardoil_entry.runtime_data.coordinator

    for board in coordinator.data:
        if board.id != board_id:
            continue

        for column in board.columns:
            for card in column.cards:
                if card.id != card_id:
                    continue

                return {
                    "config_entry": config_entry_id,
                    "board": {
                        "id": board.id,
                        "name": board.name,
                    },
                    "column": {
                        "id": column.id,
                        "title": column.title,
                    },
                    "card": {
                        **card.raw_data,
                    },
                }

        raise CardNotFoundError(board_id=board_id, card_id=card_id)

    raise BoardNotFoundError(board_id)


async def async_add_card_service(call: ServiceCall) -> None:
    """Add a card to a board column."""
    config_entry_id = call.data["config_entry"]

    entry = call.hass.config_entries.async_get_entry(config_entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise InvalidConfigEntryError

    tag_names = _normalize_tag_names(call.data.get("tag_names"))

    boardoil_entry = cast("BoardOilConfigEntry", entry)
    await boardoil_entry.runtime_data.client.async_add_card(
        board_id=call.data["board_id"],
        column_id=call.data["column_id"],
        title=call.data["title"],
        description=call.data["description"],
        tag_names=tag_names,
        card_type_id=call.data["card_type_id"],
    )
    await boardoil_entry.runtime_data.coordinator.async_request_refresh()


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
        SERVICE_ADD_CARD,
        async_add_card_service,
        schema=SERVICE_SCHEMA_ADD_CARD,
        supports_response=SupportsResponse.NONE,
    )
