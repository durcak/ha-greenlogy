"""Integrácia Greenlogy – virtuálna batéria a merania elektromera."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import GreenlogyApi
from .coordinator import GreenlogyCoordinator

PLATFORMS = [Platform.SENSOR]

type GreenlogyConfigEntry = ConfigEntry[GreenlogyCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: GreenlogyConfigEntry) -> bool:
    """Nastaví integráciu z konfiguračného záznamu."""
    # Vlastný cookie jar – session Greenlogy sa nemieša s ostatnými integráciami.
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    api = GreenlogyApi(session, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    coordinator = GreenlogyCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreenlogyConfigEntry) -> bool:
    """Odstráni integráciu."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
