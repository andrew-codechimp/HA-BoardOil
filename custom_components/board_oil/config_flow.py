"""Adds config flow for board_oil."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from awesomeversion import AwesomeVersion

if TYPE_CHECKING:
    from collections.abc import Mapping

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from .api import (
    BoardOilApiClient,
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientCommunicationError,
    BoardOilApiClientError,
)
from .const import DOMAIN, LOGGER, MIN_REQUIRED_BOARDOIL_VERSION

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_TOKEN): str,
        vol.Optional(CONF_VERIFY_SSL, default=True): bool,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


class BoardOilFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for BoardOil."""

    VERSION = 1

    host: str | None = None
    verify_ssl: bool = True

    async def check_connection(
        self,
        host: str,
        api_token: str,
        verify_ssl: bool,  # noqa: FBT001
    ) -> tuple[dict[str, str], str | None, str | None]:
        """Check connection to the BoardOil API."""
        client = BoardOilApiClient(
            host=host,
            api_token=api_token,
            session=async_create_clientsession(self.hass, verify_ssl=verify_ssl),
        )
        try:
            result_me = await client.async_get_me()
            client_id = result_me.get("data", {}).get("id", "")
            result_version = await client.async_get_version()
            version = result_version.get("data", {}).get("version", "")
        except BoardOilApiClientAuthenticationError:
            return {"base": "auth"}, None
        except BoardOilApiClientCommunicationError:
            return {"base": "connection"}, None
        except BoardOilApiClientError:
            LOGGER.exception("Unexpected error")
            return {"base": "unknown"}, None
        return {}, client_id, version

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            errors, client_id, version = await self.check_connection(
                user_input[CONF_HOST],
                user_input[CONF_API_TOKEN],
                user_input[CONF_VERIFY_SSL],
            )
            v = AwesomeVersion(version) if version else None
            if v.valid and v < MIN_REQUIRED_BOARDOIL_VERSION:
                errors["base"] = "boardoil_version"

            if not errors:
                await self.async_set_unique_id(
                    slugify(f"{user_input[CONF_HOST]}-{client_id}")
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Board Oil",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.host = entry_data[CONF_HOST]
        self.verify_ssl = entry_data.get(CONF_VERIFY_SSL, True)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input:
            if self.host is None:
                return self.async_abort(reason="reauth_failed")
            errors, client_id, version = await self.check_connection(
                self.host,
                user_input[CONF_API_TOKEN],
                self.verify_ssl,
            )
            v = AwesomeVersion(version) if version else None
            if v.valid and v < MIN_REQUIRED_BOARDOIL_VERSION:
                errors["base"] = "boardoil_version"

            if not errors:
                await self.async_set_unique_id(slugify(f"{self.host}-{client_id}"))
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        if user_input:
            errors, client_id, version = await self.check_connection(
                user_input[CONF_HOST],
                user_input[CONF_API_TOKEN],
                user_input[CONF_VERIFY_SSL],
            )
            v = AwesomeVersion(version) if version else None
            if v.valid and v < MIN_REQUIRED_BOARDOIL_VERSION:
                errors["base"] = "boardoil_version"

            if not errors:
                await self.async_set_unique_id(
                    slugify(f"{user_input[CONF_HOST]}-{client_id}")
                )
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                        CONF_VERIFY_SSL: user_input[CONF_VERIFY_SSL],
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
