# custom_components/thz/sensor.py
"""THZ Sensor Platform for Home Assistant.

This module provides the sensor platform for the THZ integration in Home Assistant.
It defines the setup routine for sensor entities, decoding logic for raw sensor data,
and a generic sensor entity class for representing THZ device sensors.
Key Components:
- async_setup_entry: Asynchronous setup for THZ sensor entities from a config entry.
- decode_value: Utility function to decode raw bytes from the device into meaningful values.
- normalize_entry: Helper to standardize sensor entry definitions.
- THZGenericSensor: Entity class representing a generic THZ sensor, handling state updates and metadata.
The integration reads register mappings from the THZ device, decodes sensor values according
to their metadata, and exposes them as Home Assistant sensor entities.
"""
from __future__ import annotations

import logging
import struct

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, should_hide_entity_by_default
from .register_maps.register_map_manager import RegisterMapManager
from .sensor_meta import SENSOR_META
from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up THZ sensor entities from a config entry.

    This function initializes sensor entities for the THZ integration by retrieving register mappings,
    creating sensor metadata, and adding the entities to Home Assistant.

    Args:
        hass (HomeAssistant): The Home Assistant instance.
        config_entry (ConfigEntry): The configuration entry for this integration.
        async_add_entities (AddConfigEntryEntitiesCallback): Callback to add entities to Home Assistant.

    Returns:
        None
    """

    # Get data from hass.data
    register_manager: RegisterMapManager = hass.data[DOMAIN]["register_manager"]
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    coordinators = entry_data["coordinators"]
    device_id = hass.data[DOMAIN]["device_id"]

    # Create sensors
    sensors = []
    seen_sensor_names = set()  # Track sensor names to avoid duplicates
    all_registers = register_manager.get_all_registers()
    for block, entries in all_registers.items():
        # Get the coordinator for this block
        coordinator = coordinators.get(block)
        if coordinator is None:
            _LOGGER.warning("No coordinator found for block %s, skipping sensors", block)
            continue
        
        block_hex = block.removeprefix("pxx")  # Remove "pxx" prefix
        block_bytes = bytes.fromhex(block_hex)
        for name, offset, length, decode_type, factor in entries:
            sensor_name = name.strip()
            
            # Skip duplicate sensor names - only create the first occurrence
            if sensor_name in seen_sensor_names:
                _LOGGER.debug(
                    "Skipping duplicate sensor '%s' in block %s (already created)",
                    sensor_name,
                    block,
                )
                continue
            
            seen_sensor_names.add(sensor_name)
            
            meta = SENSOR_META.get(sensor_name, {})
            entry = {
                "name": sensor_name,
                "offset": offset // 2,  # Register offset in bytes
                "length": (length + 1)
                // 2,  # Register length in bytes; +1 to always have at least 1 byte
                "decode": decode_type,
                "factor": factor,
                "unit": meta.get("unit"),
                "device_class": meta.get("device_class"),
                "state_class": meta.get("state_class"),
                "icon": meta.get("icon"),
                "translation_key": meta.get("translation_key"),
            }
            sensors.append(
                THZGenericSensor(coordinator, entry=entry, block=block_bytes, device_id=device_id)
            )
    async_add_entities(sensors, True)


def decode_value(raw: bytes, decode_type: str, factor: float = 1.0) -> int | float | bool | str:
    """Decode a raw byte value according to the specified decode type.

    Args:
        raw (bytes): The raw bytes to decode.
        decode_type (str): The type of decoding to apply. Supported types:
            - "hex2int": Interprets the bytes as a signed integer and divides by `factor`.
            - "hex": Interprets the bytes as an unsigned integer.
            - "bitX": Extracts bit number X (e.g., "bit3" extracts the 3rd bit).
            - "nbitX": Returns the negation of bit number X (e.g., "nbit2" negates the 2nd bit).
            - "esp_mant": Decodes a value using a mantissa and exponent representation.
            - Any other value: Returns the hexadecimal representation of the bytes.
        factor (float, optional): The divisor for "hex2int" decoding. Defaults to 1.0.

    Returns:
        int, float, bool, or str: The decoded value, type depends on `decode_type`.
    """

    if decode_type == "hex2int":
        # raw = raw[:2]  # Nur 2 Byte nutzen, Register meint mit 4 Anzahl Zeichen im Hex-String
        return int.from_bytes(raw, byteorder="big", signed=True) / factor
    if decode_type == "hex":
        # raw = raw[:2]  # Nur 2 Byte nutzen, Register meint mit 4 Anzahl Zeichen im Hex-String
        return int.from_bytes(raw, byteorder="big")
    if decode_type.startswith("bit"):
        bitnum = int(decode_type[3:])
        # _LOGGER.debug(f"Decode bit {bitnum} from raw {raw.hex()}")
        return bool((raw[0] >> bitnum) & 0x01)
    if decode_type.startswith("nbit"):
        bitnum = int(decode_type[4:])
        # _LOGGER.debug(f"Decode bit {bitnum} from raw {raw.hex()}")
        return not bool((raw[0] >> bitnum) & 0x01)
    if decode_type == "esp_mant":
        # To mimic: sprintf("%.3f", unpack('f', pack('L', reverse(hex($value)))))
        # The FHEM code reverses bytes and unpacks, which is equivalent to big-endian
        mant = struct.unpack('>f', raw)[0]
        return round(mant, 3)
    
    return raw.hex()


def normalize_entry(entry):  # um nach und nach Mapping zu erweitern
    """Normalize a sensor entry to a standard dictionary format.

    This function accepts either a tuple or a dictionary representing a sensor entry.
    If a tuple is provided, it is unpacked into a dictionary with predefined keys.
    If a dictionary is provided, it is returned as-is.
    Raises a ValueError if the entry is of an unsupported type.

    Args:
        entry (tuple or dict): The sensor entry to normalize. If a tuple, it should contain
            (name, offset, length, decode, factor).

    Returns:
        dict: A dictionary containing the normalized sensor entry.

    Raises:
        ValueError: If the entry is not a tuple or dictionary.
    """

    if isinstance(entry, tuple):
        name, offset, length, decode, factor = entry
        return {
            "name": name.strip(),
            "offset": offset,
            "length": length,
            "decode": decode,
            "factor": factor,
            "unit": None,
            "device_class": None,
            "state_class": None,
            "icon": None,
            "translation_key": None,
        }
    if isinstance(entry, dict):
        return entry

    raise ValueError("Unsupported sensor entry format.")


class THZGenericSensor(CoordinatorEntity, SensorEntity):
    """Represents a generic sensor entity for the THZ integration.

    This class is responsible for managing the state and properties of a sensor
    associated with a THZ device. It uses a coordinator to poll data from the device
    at configurable intervals, then decodes the relevant bytes for this sensor.
    
    Attributes:
        _block: Block identifier associated with the sensor.
        _offset: Offset within the block for sensor data.
        _length: Length of the sensor data in bytes.
        _decode_type: Type used to decode the sensor data.
        _factor: Factor to apply to the decoded value.
        _unit (str, optional): Unit of measurement for the sensor.
        _device_class (str, optional): Device class for the sensor.
        _icon (str, optional): Icon representing the sensor.
        _translation_key (str, optional): Translation key for localization.

    Properties:
        name (str | None): The name of the sensor.
        native_value (StateType | int | float | bool | str | None): The native value of the sensor.
        native_unit_of_measurement: The native unit of measurement for this sensor.
        device_class (str | None): The device class of the sensor.
        icon (str | None): The icon to use in the frontend.
        translation_key (str | None): The translation key for this sensor.
        unique_id (str | None): A unique identifier for the sensor entity.
    """

    def __init__(self, coordinator, entry, block, device_id) -> None:
        """Initialize a sensor instance with the provided configuration.

        Args:
            coordinator: The DataUpdateCoordinator for this sensor's block.
            entry (dict): The configuration entry for the sensor.
            block: The block associated with the sensor.
            device_id: The unique device identifier.

        Attributes:
            _name (str): Name of the sensor.
            _block: Block associated with the sensor.
            _offset: Offset value from the configuration.
            _length: Length value from the configuration.
            _decode_type: Decode type for the sensor data.
            _factor: Factor to apply to the sensor value.
            _unit (str, optional): Unit of measurement.
            _device_class (str, optional): Device class for the sensor.
            _icon (str, optional): Icon representing the sensor.
            _translation_key (str, optional): Translation key for localization.
            _device_id: Device identifier for linking to device.
        """
        super().__init__(coordinator)

        e = normalize_entry(entry)
        self._name = e["name"]
        self._block = block
        self._offset = e["offset"]
        self._length = e["length"]
        self._decode_type = e["decode"]
        self._factor = e["factor"]
        self._unit = e.get("unit")
        self._device_class = e.get("device_class")
        self._state_class = e.get("state_class")
        self._icon = e.get("icon")
        self._translation_key = e.get("translation_key")
        self._device_id = device_id
        
        # Enable entity name translation only when translation_key is provided
        # This prevents entities from showing as just the device name when no translation exists
        self._attr_has_entity_name = self._translation_key is not None
        self._attr_entity_registry_enabled_default = not should_hide_entity_by_default(self._name)

    @property
    def name(self) -> str | None:
        """Return the name of the sensor.
        
        When has_entity_name is True, return None to use translation key.
        Otherwise, return the entity name for backward compatibility.
        """
        if self._attr_has_entity_name:
            return None
        return self._name

    @property
    def native_value(self) -> StateType | int | float | bool | str | None:
        """Return the native value of the sensor.

        Returns:
        -------
        StateType | int | float | bool | str | None
            The native value of the sensor.
        """
        if self.coordinator.data is None:
            return None
        
        try:
            payload = self.coordinator.data
            # Validate payload length before slicing
            if len(payload) < self._offset + self._length:
                _LOGGER.warning(
                    "Payload too short for sensor %s: expected at least %d bytes, got %d",
                    self._name,
                    self._offset + self._length,
                    len(payload),
                )
                return None
            raw_bytes = payload[self._offset : self._offset + self._length]
            return decode_value(raw_bytes, self._decode_type, self._factor)
        except (ValueError, IndexError, TypeError) as err:
            _LOGGER.error(
                "Error decoding sensor %s: %s", self._name, err, exc_info=True
            )
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the native unit of measurement for this sensor.

        This property provides the unit in which the sensor's value is measured natively,
        such as "°C" for temperature or "%" for humidity. If the unit is not defined,
        returns None.

        Returns:
        ------
            str | None: The native unit of measurement, or None if not set.
        """
        return self._unit

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor.

        Returns:
        -------
            SensorDeviceClass | None: The device class, or None if not set.
        """
        return self._device_class

    @property
    def state_class(self) -> SensorStateClass | None:
        """Return the state class of the sensor.

        Returns:
        -------
            SensorStateClass | None: The state class for long-term statistics, or None if not set.
        """
        return self._state_class

    @property
    def icon(self) -> str | None:
        """Return the icon to use in the frontend.

        Returns:
        -------
            str | None: The icon string, or None if no icon is set.
        """
        return self._icon

    @property
    def translation_key(self) -> str | None:
        """Return the translation key for this sensor, if available.

        Returns:
        -------
            str | None: The translation key as a string, or None if not set.
        """
        return self._translation_key

    @property
    def unique_id(self) -> str | None:
        """Return a unique identifier for the sensor entity.

        Returns:
        -------
            str | None: A string representing the unique ID of the sensor, or None if not available.
        """

        return (
            f"thz_{self._block}_{self._offset}_{self._name.lower().replace(' ', '_')}"
        )

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }
