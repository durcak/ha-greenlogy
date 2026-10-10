"""Klient pre API zákazníckeho portálu Greenlogy (portal.greenlogy.com).

API nie je verejne zdokumentované – správanie je odvodené z webového portálu
a môže sa bez upozornenia zmeniť.
"""

from __future__ import annotations

from datetime import UTC, datetime
import logging
from typing import Any

import aiohttp

from .const import API_URL, API_VERSION, CLIENT_ID, ORGANIZATION_ID

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=60)
_AUTH_STATUSES = (400, 401, 403, 404, 422)
_PAGE_LIMIT = 1000
_MAX_PAGES = 50


class GreenlogyError(Exception):
    """Všeobecná chyba komunikácie s Greenlogy."""


class GreenlogyAuthError(GreenlogyError):
    """Nesprávne prihlasovacie údaje alebo neplatná session."""


def iso_utc(value: datetime) -> str:
    """Formát času, ktorý používa portál, napr. 2026-01-31T23:00:00.000Z."""
    value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


class GreenlogyApi:
    """Prihlásenie a čítanie dát zo zákazníckeho portálu Greenlogy."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._csrf_token: str | None = None
        self._session_token: str | None = None

    def _headers(self) -> dict[str, str]:
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-version": API_VERSION,
        }
        if self._csrf_token:
            headers["x-csrf-token"] = self._csrf_token
        if self._session_token:
            headers["x-session-token"] = self._session_token
        return headers

    def _remember_session(self, response: aiohttp.ClientResponse) -> None:
        if token := response.headers.get("x-session-token"):
            self._session_token = token

    async def login(self) -> None:
        """Prihlási sa e-mailom a heslom, rovnako ako webový portál."""
        self._csrf_token = None
        self._session_token = None
        payload = {"email": self._email, "password": self._password, "clientId": CLIENT_ID}
        try:
            async with self._session.post(
                f"{API_URL}/auth/login", json=payload, headers=self._headers(), timeout=_TIMEOUT
            ) as response:
                self._remember_session(response)
                if response.status in _AUTH_STATUSES:
                    _LOGGER.debug("Prihlásenie zamietnuté: HTTP %s %s", response.status, (await response.text())[:200])
                    raise GreenlogyAuthError(f"Prihlásenie zlyhalo (HTTP {response.status})")
                response.raise_for_status()
                data = await response.json(content_type=None)
        except aiohttp.ClientError as err:
            raise GreenlogyError(f"Greenlogy API je nedostupné: {err}") from err
        if not isinstance(data, dict) or not data.get("csrfToken"):
            raise GreenlogyAuthError("Odpoveď na prihlásenie neobsahuje CSRF token")
        self._csrf_token = data["csrfToken"]

    async def _get(self, path: str, params: dict[str, str] | None = None, *, retry: bool = True) -> Any:
        if self._csrf_token is None:
            await self.login()
        url = f"{API_URL}/me/organizations/{ORGANIZATION_ID}{path}"
        try:
            async with self._session.get(url, params=params, headers=self._headers(), timeout=_TIMEOUT) as response:
                self._remember_session(response)
                status = response.status
                body = await response.json(content_type=None) if status == 200 else None
        except aiohttp.ClientError as err:
            raise GreenlogyError(f"Greenlogy API je nedostupné: {err}") from err
        if status in (401, 403):
            if retry:
                await self.login()
                return await self._get(path, params, retry=False)
            raise GreenlogyAuthError(f"Prístup zamietnutý (HTTP {status})")
        if status != 200:
            raise GreenlogyError(f"Greenlogy API vrátilo HTTP {status} pre {path}")
        return body

    async def virtual_batteries(self) -> list[dict[str, Any]]:
        """Aktívne služby virtuálnej batérie."""
        data = await self._get("/customer_services", {"active": "true", "type": "virtual_battery"})
        return data if isinstance(data, list) else []

    async def virtual_battery(self, service_id: str) -> dict[str, Any]:
        """Detail virtuálnej batérie vrátane aktuálneho stavu nabitia."""
        data = await self._get(f"/customer_services/virtual_battery/{service_id}")
        return data if isinstance(data, dict) else {}

    async def virtual_battery_flow(self, service_id: str, kind: str, since: datetime) -> float | None:
        """Odobratá (consumption) alebo pripísaná (production) energia od dátumu v kWh."""
        data = await self._get(f"/customer_services/virtual_battery/{service_id}/{kind}", {"from": iso_utc(since)})
        if isinstance(data, dict) and data.get("value") is not None:
            return float(data["value"])
        return None

    async def delivery_points(self) -> list[dict[str, Any]]:
        """Odberné a výrobné miesta zákazníka."""
        data = await self._get("/physical_delivery_points", {"seller": "false"})
        return data if isinstance(data, list) else []

    async def metering(
        self, delivery_point_id: str, start: datetime, end: datetime, resolution: str = "1h"
    ) -> list[dict[str, Any]]:
        """Namerané hodnoty z elektromera (resolution: 15m, 1h, 1d)."""
        rows: list[dict[str, Any]] = []
        for page in range(_MAX_PAGES):
            data = await self._get(
                f"/physical_delivery_points/{delivery_point_id}/metering",
                {
                    "offset": str(page * _PAGE_LIMIT),
                    "limit": str(_PAGE_LIMIT),
                    "unit": "kWh",
                    "from": iso_utc(start),
                    "to": iso_utc(end),
                    "resolution": resolution,
                    "timeTo": "true",
                },
            )
            if not isinstance(data, list):
                break
            rows.extend(data)
            if len(data) < _PAGE_LIMIT:
                break
        return rows
