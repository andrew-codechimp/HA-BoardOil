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


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up boardoil services."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_CARD,
        async_get_card_service,
        schema=SERVICE_SCHEMA_GET_CARD,
        supports_response=SupportsResponse.ONLY,
    )
