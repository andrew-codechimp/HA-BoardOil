"""Adds config flow for board_oil."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_VERIFY_SSL
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

    def _build_user_schema(self, user_input: Mapping[str, Any] | None) -> vol.Schema:
        """Build schema used by user and reconfigure steps."""
        return vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=(user_input or {}).get(CONF_HOST, vol.UNDEFINED),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                    ),
                ),
                vol.Required(
                    CONF_API_TOKEN,
                    default=(user_input or {}).get(CONF_API_TOKEN, vol.UNDEFINED),
                ): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                    ),
                ),
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=(user_input or {}).get(CONF_VERIFY_SSL, True),
                ): selector.BooleanSelector(
                    selector.BooleanSelectorConfig(),
                ),
            },
        )

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
                    verify_ssl=user_input[CONF_VERIFY_SSL],
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
                        title="Board Oil",
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
            data_schema=self._build_user_schema(user_input),
            errors=_errors,
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
        _errors: dict[str, str] = {}
        if user_input:
            client_id = await self._test_credentials(
                self.host, user_input[CONF_API_TOKEN], self.verify_ssl
            )
            if not client_id:
                _errors["base"] = "auth"
            if not _errors:
                await self.async_set_unique_id(
                    slugify(f"{user_input[CONF_HOST]}-{client_id}")
                )
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]},
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            errors=_errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        _errors: dict[str, str] = {}
        defaults = user_input or self._get_reconfigure_entry().data
        if user_input:
            client_id = await self._test_credentials(
                user_input[CONF_HOST],
                user_input[CONF_API_TOKEN],
                user_input[CONF_VERIFY_SSL],
            )
            if not client_id:
                _errors["base"] = "auth"
            if not _errors:
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
            data_schema=self._build_user_schema(defaults),
            errors=_errors,
        )

    async def _test_credentials(
        self,
        host: str,
        api_token: str,
        verify_ssl: bool,  # noqa: FBT001
    ) -> str | None:
        """Validate credentials."""
        client = BoardOilApiClient(
            host=host,
            api_token=api_token,
            session=async_create_clientsession(self.hass, verify_ssl=verify_ssl),
        )
        result = await client.async_get_me()
        return result.get("data", {}).get("id", "")
