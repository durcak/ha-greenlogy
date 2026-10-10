"""Načítanie dát z Greenlogy a import hodinových meraní do štatistík HA."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
    statistic_during_period,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import GreenlogyApi, GreenlogyAuthError, GreenlogyError
from .const import DOMAIN, HISTORY_START, STAT_EXPORT, STAT_IMPORT, STAT_USABLE, UPDATE_INTERVAL

try:  # HA 2025.4+
    from homeassistant.components.recorder.models import StatisticMeanType
except ImportError:  # pragma: no cover
    StatisticMeanType = None

try:
    from homeassistant.util.unit_conversion import EnergyConverter
except ImportError:  # pragma: no cover
    EnergyConverter = None

_LOGGER = logging.getLogger(__name__)

# Merania staršie ako toto sa považujú za definitívne – prázdne obdobie sa preskočí.
_SETTLED_AFTER = timedelta(days=7)

STAT_NAMES = {
    STAT_IMPORT: "Greenlogy odber zo siete",
    STAT_EXPORT: "Greenlogy dodávka do siete",
    STAT_USABLE: "Greenlogy výroba pripísaná do VB",
}

type RowFetcher = Callable[[datetime, datetime], Awaitable[list[dict[str, Any]]]]


@dataclass
class DeliveryPoint:
    """Odberné alebo výrobné miesto."""

    id: str
    eic: str | None
    history_start: datetime


@dataclass
class GreenlogyData:
    """Aktuálne hodnoty pre senzory."""

    battery: float | None = None
    battery_consumed: float | None = None
    battery_produced: float | None = None
    battery_carried_over: float | None = None
    usable_since: float | None = None
    not_credited_since: float | None = None
    usable_from: date | None = None
    period_start: date | None = None
    product: str | None = None
    contract: str | None = None
    price_high: float | None = None
    price_low: float | None = None
    import_yesterday: float | None = None
    export_yesterday: float | None = None
    metering_until: datetime | None = None


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    parsed = dt_util.parse_datetime(value)
    return dt_util.as_utc(parsed) if parsed else None


class GreenlogyCoordinator(DataUpdateCoordinator[GreenlogyData]):
    """Pravidelne sťahuje stav virtuálnej batérie a merania elektromera."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, api: GreenlogyApi) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.api = api
        self._points: dict[str, DeliveryPoint] | None = None
        self._battery_id: str | None = None

    async def _async_update_data(self) -> GreenlogyData:
        try:
            return await self._fetch()
        except GreenlogyAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except GreenlogyError as err:
            raise UpdateFailed(str(err)) from err

    async def _fetch(self) -> GreenlogyData:
        data = GreenlogyData()
        await self._fetch_virtual_battery(data)

        today = dt_util.start_of_local_day()
        yesterday = today - timedelta(days=1)
        points = await self._delivery_points()
        for key, point in points.items():
            rows = [
                r
                for r in await self.api.metering(point.id, yesterday, today - timedelta(milliseconds=1), "1d")
                if not r.get("placeholder")
            ]
            if rows:
                value = round(sum(_float(r.get("_value")) or 0.0 for r in rows), 3)
                if key == STAT_IMPORT:
                    data.import_yesterday = value
                else:
                    data.export_yesterday = value
            until = await self._import_statistics(
                key,
                point.history_start,
                lambda start, end, point=point: self.api.metering(point.id, start, end, "1h"),
                chunk_days=31,
            )
            if until and (data.metering_until is None or until > data.metering_until):
                data.metering_until = until

        if self._battery_id and STAT_EXPORT in points:
            battery_id = self._battery_id
            await self._import_statistics(
                STAT_USABLE,
                points[STAT_EXPORT].history_start,
                lambda start, end: self.api.virtual_battery_metering(battery_id, "usable_production", start, end),
                chunk_days=10,  # 15-minútové hodnoty, aby sa zmestili do jednej strany
            )
            await self._usable_since(data)
        return data

    async def _fetch_virtual_battery(self, data: GreenlogyData) -> None:
        services = await self.api.virtual_batteries()
        if not services:
            return
        service = services[0]
        self._battery_id = service["id"]
        detail = await self.api.virtual_battery(service["id"])
        accumulated = (detail.get("virtualBattery") or {}).get("accumulatedProduction") or {}
        data.battery = _float(accumulated.get("value"))
        data.product = (service.get("product") or {}).get("name")
        contract = service.get("contract") or {}
        data.contract = contract.get("number")
        data.price_high = _float(contract.get("priceAverage1THT"))
        data.price_low = _float(contract.get("priceAverageLT"))

        period_start = self._period_start(service.get("effectiveFrom") or service.get("validFrom"))
        if period_start is None:
            return
        data.period_start = period_start
        # Portál posiela koniec prvého dňa obdobia (lokálny čas) – robíme to rovnako.
        since = dt_util.start_of_local_day(period_start) + timedelta(days=1) - timedelta(milliseconds=1)
        data.battery_consumed = await self.api.virtual_battery_flow(service["id"], "consumption", since)
        data.battery_produced = await self.api.virtual_battery_flow(service["id"], "production", since)
        if None not in (data.battery, data.battery_consumed, data.battery_produced):
            # stav = prenesené z minulého zúčtovania + vyrobené − spotrebované od zúčtovania
            data.battery_carried_over = round(data.battery - data.battery_produced + data.battery_consumed, 3)

    async def _usable_since(self, data: GreenlogyData) -> None:
        """Využiteľná a nepripísaná výroba od zúčtovania zo štatistík (oneskorenie max. jeden cyklus)."""
        if data.period_start is None:
            return
        start = dt_util.as_utc(dt_util.start_of_local_day(data.period_start))
        recorder = get_instance(self.hass)
        usable_id = f"{DOMAIN}:{STAT_USABLE}"
        # Využiteľná výroba nemusí existovať za celé obdobie – porovnávame len od jej prvého dňa.
        days = await recorder.async_add_executor_job(
            statistics_during_period, self.hass, start, None, {usable_id}, "day", None, {"change"}
        )
        if not days.get(usable_id):
            return
        first = days[usable_id][0]["start"]
        first = dt_util.utc_from_timestamp(first) if isinstance(first, (int, float)) else dt_util.as_utc(first)
        start = max(start, first)
        data.usable_from = dt_util.as_local(start).date()
        usable = await recorder.async_add_executor_job(
            statistic_during_period, self.hass, start, None, usable_id, {"change"}, None
        )
        export = await recorder.async_add_executor_job(
            statistic_during_period, self.hass, start, None, f"{DOMAIN}:{STAT_EXPORT}", {"change"}, None
        )
        usable_change = _float((usable or {}).get("change"))
        export_change = _float((export or {}).get("change"))
        if usable_change is None:
            return
        data.usable_since = round(usable_change, 3)
        if export_change is not None:
            data.not_credited_since = round(max(export_change - usable_change, 0.0), 3)

    @staticmethod
    def _period_start(effective_from: Any) -> date | None:
        """Začiatok aktuálneho ročného obdobia virtuálnej batérie (výročie začiatku účinnosti)."""
        start = _parse_utc(effective_from)
        if start is None:
            return None
        first = dt_util.as_local(start).date()
        today = dt_util.now().date()
        try:
            candidate = first.replace(year=today.year)
        except ValueError:  # 29. február
            candidate = first.replace(year=today.year, day=28)
        if candidate > today:
            candidate = candidate.replace(year=today.year - 1)
        return candidate

    async def _delivery_points(self) -> dict[str, DeliveryPoint]:
        if self._points is not None:
            return self._points
        points: dict[str, DeliveryPoint] = {}
        for item in await self.api.delivery_points():
            if item.get("deletedAt"):
                continue
            target = None
            history_start = None
            for header in item.get("meteringHeaders") or []:
                if header.get("source") == "okte" and header.get("operationType") == "download":
                    target = header.get("target")
                    history_start = _parse_utc(header.get("startAt"))
                    break
            if target is None:
                target = "production" if item.get("measurementType") == 1 or item.get("productionSourcePower") else "consumption"
            key = STAT_EXPORT if target == "production" else STAT_IMPORT
            if key in points:
                _LOGGER.warning("Viac miest typu %s, používam prvé (%s)", target, points[key].eic)
                continue
            points[key] = DeliveryPoint(
                id=item["id"],
                eic=item.get("eic"),
                history_start=history_start
                or dt_util.as_utc(dt_util.start_of_local_day(dt_util.parse_date(HISTORY_START))),
            )
        self._points = points
        return points

    def _metadata(self, key: str) -> StatisticMetaData:
        meta: dict[str, Any] = {
            "has_sum": True,
            "name": STAT_NAMES[key],
            "source": DOMAIN,
            "statistic_id": f"{DOMAIN}:{key}",
            "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
        }
        fields = getattr(StatisticMetaData, "__annotations__", {})
        if StatisticMeanType is not None and "mean_type" in fields:
            meta["mean_type"] = StatisticMeanType.NONE
        else:
            meta["has_mean"] = False
        if EnergyConverter is not None and "unit_class" in fields:
            meta["unit_class"] = EnergyConverter.UNIT_CLASS
        return StatisticMetaData(**meta)

    async def _import_statistics(
        self, key: str, history_start: datetime, fetch: RowFetcher, *, chunk_days: int
    ) -> datetime | None:
        """Doplní hodinové hodnoty od posledného importu po koniec včerajška.

        Jemnejšie hodnoty (napr. 15-minútové) sa sčítajú po hodinách.
        """
        statistic_id = f"{DOMAIN}:{key}"
        last = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
        )
        if last.get(statistic_id):
            row = last[statistic_id][0]
            start = row["start"]
            last_start = dt_util.utc_from_timestamp(start) if isinstance(start, (int, float)) else dt_util.as_utc(start)
            next_hour = last_start + timedelta(hours=1)
            running = float(row.get("sum") or 0.0)
        else:
            next_hour = history_start.replace(minute=0, second=0, microsecond=0)
            running = 0.0

        end = dt_util.as_utc(dt_util.start_of_local_day())
        settled = end - _SETTLED_AFTER
        stats: list[StatisticData] = []
        chunk = next_hour
        while chunk < end:
            chunk_end = min(chunk + timedelta(days=chunk_days), end)
            hours: dict[datetime, float] = {}
            for r in await fetch(chunk, chunk_end - timedelta(milliseconds=1)):
                if r.get("placeholder"):
                    continue
                t = _parse_utc(r.get("_time"))
                if t is None or not next_hour <= t < end:
                    continue
                hour = t.replace(minute=0, second=0, microsecond=0)
                hours[hour] = hours.get(hour, 0.0) + (_float(r.get("_value")) or 0.0)
            for hour in sorted(hours):
                running += hours[hour]
                stats.append(StatisticData(start=hour, state=running, sum=running))
                next_hour = hour + timedelta(hours=1)
            if not hours and chunk_end > settled:
                break  # novšie dáta ešte nie sú k dispozícii
            if hours and next_hour < chunk_end and chunk_end > settled:
                break  # zvyšok obdobia ešte nie je nameraný, skúsime nabudúce
            chunk = chunk_end

        if stats:
            async_add_external_statistics(self.hass, self._metadata(key), stats)
            _LOGGER.debug("%s: importovaných %s hodín do %s", statistic_id, len(stats), next_hour)
        return next_hour if (stats or last.get(statistic_id)) else None
