"""Konfiguračný formulár Greenlogy (e-mail a heslo zo zákazníckeho portálu)."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import GreenlogyApi, GreenlogyAuthError, GreenlogyError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

EMAIL_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username"))
PASSWORD_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password"))


class GreenlogyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pridanie účtu Greenlogy."""

    VERSION = 1

    async def _validate(self, email: str, password: str) -> dict[str, str]:
        session = async_create_clientsession(self.hass, cookie_jar=aiohttp.CookieJar())
        api = GreenlogyApi(session, email, password)
        try:
            await api.login()
            await api.virtual_batteries()
        except GreenlogyAuthError:
            return {"base": "invalid_auth"}
        except GreenlogyError:
            return {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Neočakávaná chyba pri overení účtu Greenlogy")
            return {"base": "unknown"}
        return {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Prvý krok – e-mail a heslo."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            errors = await self._validate(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(
                    title=email, data={CONF_EMAIL: email, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): EMAIL_SELECTOR, vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Heslo prestalo platiť."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Zadanie nového hesla."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = await self._validate(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if not errors:
                return self.async_update_reload_and_abort(entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): PASSWORD_SELECTOR}),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
