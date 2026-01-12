"""Binary sensor platform for THZ integration."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Common error/alarm sensor definitions
# These are based on typical heat pump status indicators
BINARY_SENSOR_TYPES = {
    "alarm": {
        "name": "Alarm",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon": "mdi:alert",
        "sensor_name": "alarm",  # Name to look for in register maps
    },
    "error": {
        "name": "Error",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon": "mdi:alert-circle",
        "sensor_name": "error",
    },
    "warning": {
        "name": "Warning",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon": "mdi:alert-outline",
        "sensor_name": "warning",
    },
    "compressor_running": {
        "name": "Compressor Running",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "icon": "mdi:engine",
        "sensor_name": "compressor",
    },
    "heating_mode": {
        "name": "Heating Mode Active",
        "device_class": BinarySensorDeviceClass.HEAT,
        "icon": "mdi:fire",
        "sensor_name": "heatingMode",
    },
    "dhw_mode": {
        "name": "DHW Mode Active",
        "device_class": BinarySensorDeviceClass.HEAT,
        "icon": "mdi:water-boiler",
        "sensor_name": "dhwMode",
    },
    "defrost": {
        "name": "Defrost Active",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "icon": "mdi:snowflake-melt",
        "sensor_name": "defrost",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ binary sensor entities from a config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    device_id = hass.data[DOMAIN]["device_id"]
    register_manager = hass.data[DOMAIN]["register_manager"]
    
    binary_sensors = []
    
    # Get all available sensors from register maps
    all_registers = register_manager.get_all_registers()
    available_sensors = set()
    
    for block, entries in all_registers.items():
        for name, offset, length, decode_type, factor in entries:
            sensor_name = name.strip().lower()
            available_sensors.add(sensor_name)
    
    # Create binary sensors for each type that exists in the register maps
    for sensor_type, config in BINARY_SENSOR_TYPES.items():
        target_sensor = config["sensor_name"].lower()
        
        # Check if this sensor exists in any block
        found = False
        for sensor_name in available_sensors:
            if target_sensor in sensor_name:
                found = True
                break
        
        if not found:
            _LOGGER.debug(
                "Binary sensor type '%s' (looking for '%s') not found in register maps",
                sensor_type,
                target_sensor,
            )
            continue
        
        # Find the coordinator and block for this sensor
        for block, entries in all_registers.items():
            coordinator = coordinators.get(block)
            if coordinator is None:
                continue
            
            for name, offset, length, decode_type, factor in entries:
                sensor_name = name.strip()
                if target_sensor in sensor_name.lower():
                    # Create binary sensor
                    block_hex = block.removeprefix("pxx")
                    block_bytes = bytes.fromhex(block_hex)
                    
                    binary_sensors.append(
                        THZBinarySensor(
                            coordinator,
                            device_id,
                            sensor_type,
                            config,
                            block_bytes,
                            offset // 2,  # Convert to byte offset
                            length // 2 if length > 1 else 1,
                            decode_type,
                        )
                    )
                    _LOGGER.info("Created binary sensor: %s", config["name"])
                    break  # Only create one sensor per type
            
            if binary_sensors and binary_sensors[-1]._sensor_type == sensor_type:
                break  # Found and created this sensor type, move to next
    
    if binary_sensors:
        async_add_entities(binary_sensors, True)
        _LOGGER.info("Added %d binary sensors", len(binary_sensors))
    else:
        _LOGGER.info("No compatible binary sensors found in register maps")


class THZBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a THZ binary sensor."""
    
    def __init__(
        self,
        coordinator,
        device_id: str,
        sensor_type: str,
        config: dict,
        block: bytes,
        offset: int,
        length: int,
        decode_type: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        
        self._device_id = device_id
        self._sensor_type = sensor_type
        self._block = block
        self._offset = offset
        self._length = length
        self._decode_type = decode_type
        
        # Entity attributes
        self._attr_name = f"THZ {config['name']}"
        self._attr_unique_id = f"{device_id}_binary_{sensor_type}"
        self._attr_device_class = config.get("device_class")
        self._attr_icon = config.get("icon")
        
        # State
        self._attr_is_on = None
    
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"THZ {self._device_id}",
            "manufacturer": "Stiebel Eltron / Tecalor",
        }
    
    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return None
        
        try:
            # Extract the relevant bytes from coordinator data
            data = self.coordinator.data
            if len(data) < self._offset + self._length:
                _LOGGER.warning(
                    "Not enough data for %s: need %d bytes, got %d",
                    self._attr_name,
                    self._offset + self._length,
                    len(data),
                )
                return None
            
            raw_value = data[self._offset : self._offset + self._length]
            
            # Decode based on decode type
            if self._decode_type.startswith("bit"):
                # Extract specific bit
                bit_num = int(self._decode_type[3:])
                is_on = bool((raw_value[0] >> bit_num) & 0x01)
            elif self._decode_type.startswith("nbit"):
                # Extract specific bit and negate
                bit_num = int(self._decode_type[4:])
                is_on = not bool((raw_value[0] >> bit_num) & 0x01)
            elif self._decode_type == "hex":
                # Non-zero means on
                is_on = int.from_bytes(raw_value, byteorder="big") != 0
            else:
                # Default: non-zero means on
                is_on = int.from_bytes(raw_value, byteorder="big") != 0
            
            return is_on
            
        except Exception as err:
            _LOGGER.error(
                "Error decoding binary sensor %s: %s", self._attr_name, err
            )
            return None
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and self.coordinator.data is not None
