"""Senzory Greenlogy."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GreenlogyConfigEntry
from .const import DOMAIN
from .coordinator import GreenlogyCoordinator, GreenlogyData

PRICE_UNIT = "€/kWh"


@dataclass(frozen=True, kw_only=True)
class GreenlogySensorDescription(SensorEntityDescription):
    """Popis senzora Greenlogy."""

    value_fn: Callable[[GreenlogyData], Any]
    attrs_fn: Callable[[GreenlogyData], dict[str, Any]] | None = None


def _period(data: GreenlogyData) -> dict[str, Any]:
    return {"od": data.period_start.isoformat()} if data.period_start else {}


SENSORS: tuple[GreenlogySensorDescription, ...] = (
    GreenlogySensorDescription(
        key="virtual_battery",
        translation_key="virtual_battery",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.battery,
        attrs_fn=lambda d: {"produkt": d.product, "zmluva": d.contract},
    ),
    GreenlogySensorDescription(
        key="virtual_battery_consumed",
        translation_key="virtual_battery_consumed",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=0,
        value_fn=lambda d: d.battery_consumed,
        attrs_fn=_period,
    ),
    GreenlogySensorDescription(
        key="virtual_battery_produced",
        translation_key="virtual_battery_produced",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=0,
        value_fn=lambda d: d.battery_produced,
        attrs_fn=_period,
    ),
    GreenlogySensorDescription(
        key="virtual_battery_carried_over",
        translation_key="virtual_battery_carried_over",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=0,
        value_fn=lambda d: d.battery_carried_over,
        attrs_fn=_period,
    ),
    GreenlogySensorDescription(
        key="usable_since",
        translation_key="usable_since",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=0,
        value_fn=lambda d: d.usable_since,
        attrs_fn=lambda d: {"od": d.usable_from.isoformat()} if d.usable_from else {},
    ),
    GreenlogySensorDescription(
        key="not_credited_since",
        translation_key="not_credited_since",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=0,
        value_fn=lambda d: d.not_credited_since,
        attrs_fn=lambda d: {"od": d.usable_from.isoformat()} if d.usable_from else {},
    ),
    GreenlogySensorDescription(
        key="import_yesterday",
        translation_key="import_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        value_fn=lambda d: d.import_yesterday,
    ),
    GreenlogySensorDescription(
        key="export_yesterday",
        translation_key="export_yesterday",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        suggested_display_precision=1,
        value_fn=lambda d: d.export_yesterday,
    ),
    GreenlogySensorDescription(
        key="metering_until",
        translation_key="metering_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.metering_until,
    ),
    GreenlogySensorDescription(
        key="price_high",
        translation_key="price_high",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=4,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.price_high,
    ),
    GreenlogySensorDescription(
        key="price_low",
        translation_key="price_low",
        native_unit_of_measurement=PRICE_UNIT,
        suggested_display_precision=4,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.price_low,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreenlogyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Pridá senzory pre konfiguračný záznam."""
    coordinator = entry.runtime_data
    async_add_entities(GreenlogySensor(coordinator, entry.entry_id, description) for description in SENSORS)


class GreenlogySensor(CoordinatorEntity[GreenlogyCoordinator], SensorEntity):
    """Senzor s hodnotou z Greenlogy."""

    _attr_has_entity_name = True
    entity_description: GreenlogySensorDescription

    def __init__(self, coordinator: GreenlogyCoordinator, entry_id: str, description: GreenlogySensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Greenlogy",
            manufacturer="Greenlogy",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://portal.greenlogy.com",
        )

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return {k: v for k, v in self.entity_description.attrs_fn(self.coordinator.data).items() if v is not None}
