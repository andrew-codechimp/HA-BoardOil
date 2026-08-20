"""BoardOil API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout

from .models import (
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


class BoardOilApiClientError(Exception):
    """Exception to indicate a general API error."""


class BoardOilApiClientCommunicationError(
    BoardOilApiClientError,
):
    """Exception to indicate a communication error."""


class BoardOilApiClientAuthenticationError(
    BoardOilApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid credentials"
        raise BoardOilApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class BoardOilApiClient:
    """Sample API Client."""

    def __init__(
        self,
        host: str,
        api_token: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """BoardOil API Client."""
        self._host = host
        self._apitoken = api_token
        self._session = session

    async def async_get_me(self) -> Me:
        """Get me from the API."""
        response = await self._api_wrapper(
            method="get",
            path="auth/me",
        )
        return Me(
            id=response.get("data", {}).get("id", 0),
            username=response.get("data", {}).get("username", ""),
            display_name=response.get("data", {}).get("displayName", ""),
            role=response.get("data", {}).get("role", ""),
        )

    async def async_get_version(self) -> Version:
        """Get version from the API."""
        response = await self._api_wrapper(
            method="get",
            path="version",
        )
        return Version(
            version=response.get("data", {}).get("version", ""),
            channel=response.get("data", {}).get("channel", ""),
            build=response.get("data", {}).get("build", ""),
            commit=response.get("data", {}).get("commit", ""),
        )

    async def async_get_boards(self) -> list[BoardSummary]:
        """Get boards from the API."""
        response = await self._api_wrapper(
            method="get",
            path="boards",
        )
        return [
            BoardSummary(
                id=board.get("id"),
                name=board.get("name"),
                description=board.get("description", ""),
            )
            for board in response.get("data", [])
        ]

    async def async_get_board(self, board_id: int) -> Board:
        """Get board from the API."""
        response = await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}",
        )
        board_data = response.get("data", {})

        columns: list[ColumnWithCards] = []
        for column in board_data.get("columns", []):
            cards: list[Card] = []
            for card_data in column.get("cards", []):
                if not isinstance(card_data, dict):
                    continue
                cards.append(
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
                        assigned_user_display_name=card_data.get(
                            "assignedUserDisplayName"
                        ),
                        external_url=card_data.get("externalUrl"),
                        slick_id=card_data.get("slickId"),
                        slick_name=card_data.get("slickName"),
                        raw_data=card_data,
                    )
                )
            columns.append(
                ColumnWithCards(
                    id=column["id"],
                    title=column.get("title", ""),
                    cards=cards,
                )
            )

        return Board(
            id=board_id,
            name=board_data.get("name", ""),
            description=board_data.get("description", ""),
            columns=columns,
        )

    async def async_get_columns(self, board_id: int) -> list[Column]:
        """Get boards from the API."""
        response = await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}/columns",
        )
        return [
            Column(
                id=column.get("id"),
                title=column.get("title"),
            )
            for column in response.get("data", [])
        ]

    async def async_get_card_types(self, board_id: int) -> list[CardType]:
        """Get card types for the board."""
        response = await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}/card-types",
        )
        return [
            CardType(
                id=card_type.get("id"),
                name=card_type.get("name"),
            )
            for card_type in response.get("data", [])
        ]

    async def async_get_tags(self, board_id: int) -> list[Tag]:
        """Get tags for the board."""
        response = await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}/tags",
        )
        return [
            Tag(
                id=tag.get("id"),
                name=tag.get("name"),
            )
            for tag in response.get("data", [])
        ]

    async def async_get_slicks(self, board_id: int) -> list[Slick]:
        """Get slicks for the board."""
        response = await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}/slicks",
        )
        return [
            Slick(
                id=slick.get("id"),
                name=slick.get("name"),
            )
            for slick in response.get("data", [])
        ]

    async def async_get_members(self, board_id: int) -> list[Member]:
        """Get member for the board."""
        response = await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}/members",
        )
        return [
            Member(
                id=member.get("userId"),
                username=member.get("userName"),
                display_name=member.get("displayName"),
            )
            for member in response.get("data", [])
        ]

    async def async_add_card(
        self,
        board_id: int,
        column_id: int | None,
        title: str,
        description: str,
        tag_names: list[str] | None,
        card_type_id: int | None,
        slick_name: str | None,
        assigned_user_id: int | None,
        external_url: str | None,
    ) -> Any:
        """Post a card to the API."""
        payload: dict[str, Any] = {
            "title": title,
            "description": description,
            "tagNames": tag_names or [],
            "slickName": slick_name,
            "externalUrl": external_url,
        }
        if column_id is not None:
            payload["boardColumnId"] = column_id
        if card_type_id is not None:
            payload["cardTypeId"] = card_type_id
        if assigned_user_id is not None:
            payload["assignedUserId"] = assigned_user_id

        return await self._api_wrapper(
            method="post",
            path=f"boards/{board_id!s}/cards",
            data=payload,
            headers={"Content-type": "application/json; charset=UTF-8"},
        )

    async def async_update_card(
        self,
        board_id: int,
        card_id: int,
        title: str,
        description: str,
        tag_names: list[str] | None,
        card_type_id: int | None,
        column_id: int | None,
        assigned_user_id: int | None,
        slick_name: str | None,
        external_url: str | None,
    ) -> Any:
        """Update a card via the API."""
        payload: dict[str, Any] = {
            "title": title,
            "description": description,
            "tagNames": tag_names or [],
            "cardTypeId": card_type_id,
            "boardColumnId": column_id,
            "assignedUserId": assigned_user_id,
            "slickName": slick_name,
            "externalUrl": external_url,
        }

        return await self._api_wrapper(
            method="put",
            path=f"boards/{board_id!s}/cards/{card_id!s}",
            data=payload,
            headers={"Content-type": "application/json; charset=UTF-8"},
        )

    async def async_delete_card(
        self,
        board_id: int,
        card_id: int,
    ) -> Any:
        """Delete a card via the API."""
        return await self._api_wrapper(
            method="delete",
            path=f"boards/{board_id!s}/cards/{card_id!s}",
        )

    async def async_archive_card(
        self,
        board_id: int,
        card_id: int,
    ) -> Any:
        """Archive a card via the API."""
        return await self._api_wrapper(
            method="post",
            path=f"boards/{board_id!s}/cards/{card_id!s}/archive",
        )

    async def async_add_card_comment(
        self,
        board_id: int,
        card_id: int,
        comment: str,
    ) -> Any:
        """Add a comment to a card via the API."""
        payload: dict[str, Any] = {
            "text": comment,
        }
        return await self._api_wrapper(
            method="post",
            path=f"boards/{board_id!s}/cards/{card_id!s}/comments",
            data=payload,
            headers={"Content-type": "application/json; charset=UTF-8"},
        )

    async def _api_wrapper(
        self,
        method: str,
        path: str,
        data: dict | None = None,
        headers: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=f"{self._host}/api/{path}",
                    headers={
                        "Authorization": f"Bearer {self._apitoken}",
                        "Accept": "application/json",
                        **(headers or {}),
                    },
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise BoardOilApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise BoardOilApiClientCommunicationError(
                msg,
            ) from exception
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise BoardOilApiClientError(
                msg,
            ) from exception
