"""Adds config flow for boardoil."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.loader import async_get_loaded_integration
from slugify import slugify

from .api import (
    BoardOilApiClient,
    BoardOilApiClientAuthenticationError,
    BoardOilApiClientCommunicationError,
    BoardOilApiClientError,
)
from .const import DOMAIN, LOGGER

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_TOKEN): str,
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

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                client_id = await self._test_credentials(
                    host=user_input[CONF_HOST],
                    api_token=user_input[CONF_API_TOKEN],
                )
                if not client_id:
                    _errors["base"] = "auth"
            except BoardOilApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except BoardOilApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except BoardOilApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                if not _errors:
                    await self.async_set_unique_id(
                        unique_id=slugify(f"{user_input[CONF_HOST]}-{client_id}"),
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_HOST],
                        data=user_input,
                    )

        integration = async_get_loaded_integration(self.hass, DOMAIN)
        assert integration.documentation is not None, (  # noqa: S101
            "Integration documentation URL is not set in manifest.json"
        )

        return self.async_show_form(
            step_id="user",
            description_placeholders={
                "documentation_url": integration.documentation,
            },
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=(user_input or {}).get(CONF_HOST, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(CONF_API_TOKEN): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        self.host = entry_data[CONF_HOST]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        if user_input:
            errors, user_id = await self._test_credentials(
                self.host,
                user_input[CONF_API_TOKEN],
            )
            if not errors:
                await self.async_set_unique_id(user_id)
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
            client_id = await self._test_credentials(
                user_input[CONF_HOST],
                user_input[CONF_API_TOKEN],
            )
            if not errors:
                await self.async_set_unique_id(
                    slugify(f"{user_input[CONF_HOST]}-{client_id}"),
                )
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    data_updates={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                    },
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

    async def _test_credentials(self, host: str, api_token: str) -> str | None:
        """Validate credentials."""
        client = BoardOilApiClient(
            host=host,
            api_token=api_token,
            session=async_create_clientsession(self.hass),
        )
        result = await client.async_get_me()
        return result.get("data", {}).get("id", "")
