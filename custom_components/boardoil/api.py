"""BoardOil API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout


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

    async def async_get_me(self) -> Any:
        """Get me from the API."""
        return await self._api_wrapper(
            method="get",
            path="auth/me",
        )

    async def async_get_version(self) -> Any:
        """Get version from the API."""
        return await self._api_wrapper(
            method="get",
            path="version",
        )

    async def async_get_boards(self) -> Any:
        """Get boards from the API."""
        return await self._api_wrapper(
            method="get",
            path="boards",
        )

    async def async_get_board(self, board_id: int) -> Any:
        """Get board from the API."""
        return await self._api_wrapper(
            method="get",
            path=f"boards/{board_id!s}",
        )

    async def async_set_title(self, value: str) -> Any:
        """Get data from the API."""
        return await self._api_wrapper(
            method="patch",
            path="https://jsonplaceholder.typicode.com/posts/1",
            data={"title": value},
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
