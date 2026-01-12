"""Time entity for THZ devices."""
from __future__ import annotations

import asyncio
import logging
from datetime import time, timedelta

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    should_hide_entity_by_default,
    TIME_VALUE_UNSET,
    WRITE_REGISTER_OFFSET,
    WRITE_REGISTER_LENGTH,
)
from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


def time_to_quarters(t: time | None) -> int:
    """Convert a time object to the number of 15-minute intervals since midnight.

    Parameters
    ----------
    t : datetime.time | None
        The time to convert. If None, a sentinel value of 128 (0x80) is returned.

    Returns:
    -------
    int
        The count of 15-minute intervals since midnight:
        - 0 represents 00:00,
        - each hour adds 4 intervals,
        - minutes are floored to the nearest 15-minute boundary (minute // 15).
        Valid normal values range from 0 to 95 (00:00 through 23:45). 128 is used as a special sentinel for unset/None.

    Examples:
    --------
    >>> from datetime import time
    >>> time_to_quarters(time(0, 0))
    0
    >>> time_to_quarters(time(1, 30))
    6
    >>> time_to_quarters(None)
    128
    """
    if t is None:
        return TIME_VALUE_UNSET  # 0x80 sentinel value for "no time"
    return t.hour * 4 + (t.minute // 15)


def quarters_to_time(num: int) -> time | None:
    """Convert a count of 15-minute intervals since midnight to a datetime.time.

    Parameters
    ----------
    num : int
        Number of 15-minute intervals (quarters) since midnight. The expected range is
        0–95 (0 => 00:00, 95 => 23:45). A special sentinel value 0x80 indicates "no time"
        and causes the function to return None.

    Returns:
    -------
    datetime.time | None
        A datetime.time representing the corresponding hour and minute, where the hour is
        computed as num // 4 and the minutes as (num % 4) * 15. If num == 0x80, returns None.

    Notes:
    -----
    - The function validates the 0–95 range and logs a warning for out-of-range values.
    - Invalid values are clamped to the valid range (0-95) to prevent crashes.

    Examples:
    --------
    >>> quarters_to_time(0)    # 00:00
    datetime.time(0, 0)
    >>> quarters_to_time(1)    # 00:15
    datetime.time(0, 15)
    >>> quarters_to_time(95)   # 23:45
    datetime.time(23, 45)
    >>> quarters_to_time(0x80) # sentinel for "no time"
    None
    """
    if num == TIME_VALUE_UNSET:
        return None
    
    # Validate range and clamp if necessary
    if num < 0 or num > 95:
        _LOGGER.warning(
            "Invalid quarters value %s (expected 0-95). Value will be clamped. "
            "This may indicate a byte order issue in reading the time value.",
            num
        )
        num = max(0, min(95, num))
    
    quarters = num % 4
    hour = (num - quarters) // 4
    _LOGGER.debug("Converting %s to time: %s:%s", num, hour, quarters * 15)
    return time(hour, quarters * 15)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up THZ Time entities from a config entry.

    This function creates THZTime entities based on write registers of type "time"
    from the device's register map. It also creates start and end time entities
    for schedule-type registers.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry to set up.
        async_add_entities: Callback to add new entities.

    Returns:
        None. Entities are added via the async_add_entities callback.

    Note:
        - Requires 'write_manager' and 'device' to be present in hass.data['thz']
        - Creates a THZTime entity for each register with type 'time'
        - Creates THZScheduleTime entities (start and end) for each register with type 'schedule'
        - Entity IDs are generated from the register name, converted to lowercase with spaces replaced by underscores
    """
    entities = []
    write_manager: RegisterMapManagerWrite = hass.data[DOMAIN]["write_manager"]
    device: THZDevice = hass.data[DOMAIN]["device"]
    device_id = hass.data[DOMAIN]["device_id"]
    
    # Get write interval from config, default to DEFAULT_UPDATE_INTERVAL
    write_interval = config_entry.data.get("write_interval", DEFAULT_UPDATE_INTERVAL)
    
    write_registers = write_manager.get_all_registers()
    _LOGGER.debug("write_registers: %s", write_registers)
    for name, entry in write_registers.items():
        if entry["type"] == "time":
            _LOGGER.debug(
                "Creating Time for %s with command %s", name, entry["command"]
            )
            entity = THZTime(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
                scan_interval=write_interval,
                device_id=device_id,
            )
            entities.append(entity)
        elif entry["type"] == "schedule":
            _LOGGER.debug(
                "Creating Schedule Start and End Time for %s with command %s", name, entry["command"]
            )
            # Create start time entity
            start_entity = THZScheduleTime(
                name=f"{name} Start",
                command=entry["command"],
                device=device,
                icon=entry.get("icon", "mdi:calendar-clock"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}_start",
                time_type="start",
                scan_interval=write_interval,
                device_id=device_id,
            )
            entities.append(start_entity)

            # Create end time entity
            end_entity = THZScheduleTime(
                name=f"{name} End",
                command=entry["command"],
                device=device,
                icon=entry.get("icon", "mdi:calendar-clock"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}_end",
                time_type="end",
                scan_interval=write_interval,
                device_id=device_id,
            )
            entities.append(end_entity)

    async_add_entities(entities, True)


class THZTime(TimeEntity):
    """Time entity for THZ devices.

    This class represents a time entity that can read and write time values from/to THZ devices.
    It handles conversion between quarter-hour based time values used by the device and standard
    time format used by Home Assistant.

    Attributes:
        _attr_should_poll (bool): Indicates if entity should be polled for updates.
        _attr_name (str): Name of the entity.
        _command (str): Command hex string to communicate with device.
        _device (THZDevice): Device instance this entity belongs to.
        _attr_icon (str): Icon to display for this entity.
        _attr_unique_id (str): Unique ID for this entity.
        _attr_native_value (str): Current time value in HH:MM format.

    Args:
        name (str): Name of the time entity.
        command (str): Hex command string for device communication.
        device (THZDevice): THZ device instance.
        icon (str, optional): Custom icon for the entity. Defaults to "mdi:clock".
        unique_id (str, optional): Custom unique ID. Defaults to generated ID based on command and name.
    """

    _attr_should_poll = True

    def __init__(self, name, command, device, icon=None, unique_id=None, scan_interval=None, device_id=None) -> None:
        """Initialize a new instance of the class.

        Args:
            name (str): The name of the entity.
            command (str): The command associated with the entity.
            device: The device instance this entity is associated with.
            icon (str, optional): The icon to use for this entity. Defaults to "mdi:clock" if not provided.
            unique_id (str, optional): A unique identifier for this entity. If not provided, a unique ID is generated.
            scan_interval (int, optional): The scan interval in seconds for polling updates.
            device_id (str, optional): The device identifier for linking to device.
        """

        self._attr_name = name
        self._command = command
        self._device = device
        self._attr_icon = icon or "mdi:clock"
        self._attr_unique_id = (
            unique_id or f"thz_time_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._attr_native_value = None
        self._device_id = device_id
        
        # Always set SCAN_INTERVAL to avoid HA's 30-second default
        # Use provided scan_interval or fall back to DEFAULT_UPDATE_INTERVAL
        interval = scan_interval if scan_interval is not None else DEFAULT_UPDATE_INTERVAL
        self.SCAN_INTERVAL = timedelta(seconds=interval)
        self._attr_entity_registry_enabled_default = not should_hide_entity_by_default(name)

    @property
    def name(self) -> str | None:
        """Return the name of the time entity.
        
        Always return the entity name to ensure descriptive names are displayed.
        """
        return self._attr_name

    @property
    def native_value(self):
        """Return the native value of the time."""
        return self._attr_native_value

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        from .const import DOMAIN
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }

    async def async_update(self):
        """Fetch new state data for the time."""
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                WRITE_REGISTER_OFFSET,
                WRITE_REGISTER_LENGTH,
            )
            await asyncio.sleep(
                0.01
            )  # Short pause to ensure the device is ready
        # Time values are stored as single bytes (0-95 quarters)
        num = value_bytes[0]
        self._attr_native_value = quarters_to_time(num)

    async def async_set_native_value(self, value: str):
        """Set new value for the time."""

        # Convert string (e.g., "12:30") to datetime.time
        if value is None:
            t_value = None
        else:
            hour, minute = map(int, value.split(":"))
            t_value = time(hour, minute)
        num = time_to_quarters(t_value)
        # Write as 2 bytes to match the protocol's read format (offset=4, length=2)
        # even though only the first byte contains the meaningful time value (0-95 quarters).
        # Second byte is set to 0 as it appears to be unused by the device.
        num_bytes = bytes([num, 0])
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value, bytes.fromhex(self._command), num_bytes
            )
            await asyncio.sleep(
                0.01
            )  # Kurze Pause, um sicherzustellen, dass das Gerät bereit ist
        self._attr_native_value = t_value


class THZScheduleTime(TimeEntity):
    """Time entity for THZ schedule start/end times.

    This class represents a time entity that can read and write schedule start or end times
    from/to THZ devices. Each schedule has two time values (start and end) stored sequentially
    in the device's memory.

    Attributes:
        _attr_should_poll (bool): Indicates if entity should be polled for updates.
        _attr_name (str): Name of the entity.
        _command (str): Command hex string to communicate with device.
        _device (THZDevice): Device instance this entity belongs to.
        _attr_icon (str): Icon to display for this entity.
        _attr_unique_id (str): Unique ID for this entity.
        _attr_native_value (str): Current time value in HH:MM format.
        _time_type (str): Either "start" or "end" to indicate which time value this entity represents.

    Args:
        name (str): Name of the time entity.
        command (str): Hex command string for device communication.
        device (THZDevice): THZ device instance.
        time_type (str): Either "start" or "end".
        icon (str, optional): Custom icon for the entity. Defaults to "mdi:calendar-clock".
        unique_id (str, optional): Custom unique ID. Defaults to generated ID based on command and name.
    """

    _attr_should_poll = True

    def __init__(self, name, command, device, time_type, icon=None, unique_id=None, scan_interval=None, device_id=None) -> None:
        """Initialize a new instance of the schedule time class.

        Args:
            name (str): The name of the entity.
            command (str): The command associated with the entity.
            device: The device instance this entity is associated with.
            time_type (str): Either "start" or "end".
            icon (str, optional): The icon to use for this entity. Defaults to "mdi:calendar-clock" if not provided.
            unique_id (str, optional): A unique identifier for this entity. If not provided, a unique ID is generated.
            scan_interval (int, optional): The scan interval in seconds for polling updates.
            device_id (str, optional): The device identifier for linking to device.
        """

        self._attr_name = name
        self._command = command
        self._device = device
        self._time_type = time_type
        self._attr_icon = icon or "mdi:calendar-clock"
        self._attr_unique_id = (
            unique_id or f"thz_schedule_time_{command.lower()}_{name.lower().replace(' ', '_')}_{time_type}"
        )
        self._attr_native_value = None
        self._device_id = device_id
        
        # Always set SCAN_INTERVAL to avoid HA's 30-second default
        # Use provided scan_interval or fall back to DEFAULT_UPDATE_INTERVAL
        interval = scan_interval if scan_interval is not None else DEFAULT_UPDATE_INTERVAL
        self.SCAN_INTERVAL = timedelta(seconds=interval)
        self._attr_entity_registry_enabled_default = not should_hide_entity_by_default(name)

    @property
    def name(self) -> str | None:
        """Return the name of the schedule time entity.
        
        Always return the entity name to ensure descriptive names are displayed.
        """
        return self._attr_name

    @property
    def native_value(self):
        """Return the native value of the time."""
        return self._attr_native_value

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        from .const import DOMAIN
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }

    async def async_update(self):
        """Fetch new state data for the schedule time."""
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value, bytes.fromhex(self._command), "get", 4, 4
            )
            await asyncio.sleep(
                0.01
            )  # Kurze Pause, um sicherzustellen, dass das Gerät bereit ist

        # Schedule data format (from FHEM 7prog):
        # - Bytes 0-3: header/other data
        # - Byte 4 (offset 8 hex digits): start time (1 byte, 0-95 quarters)
        # - Byte 5 (offset 10 hex digits): end time (1 byte, 0-95 quarters)
        # However, read_value returns data starting at offset 4, so:
        # - value_bytes[0]: start time
        # - value_bytes[1]: end time
        if self._time_type == "start":
            num = value_bytes[0]
        else:  # "end"
            num = value_bytes[1]

        self._attr_native_value = quarters_to_time(num)

    async def async_set_native_value(self, value: str):
        """Set new value for the schedule time."""

        # Convert string (e.g., "12:30") to datetime.time
        if value is None:
            t_value = None
        else:
            try:
                parts = value.split(":")
                if len(parts) != 2:
                    raise ValueError(f"Invalid time format: {value}")
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"Invalid time values: hour={hour}, minute={minute}")
                t_value = time(hour, minute)
            except (ValueError, AttributeError) as e:
                _LOGGER.error("Failed to parse time value '%s': %s", value, e)
                raise

        new_num = time_to_quarters(t_value)

        # Read the current schedule data (4 bytes)
        async with self._device.lock:
            current_bytes = await self.hass.async_add_executor_job(
                self._device.read_value, bytes.fromhex(self._command), "get", 4, 4
            )
            await asyncio.sleep(0.01)

        # Time values are single bytes (0-95 quarters)
        # Modify only the relevant byte (start at byte 0 or end at byte 1)
        new_bytes = bytearray(current_bytes)
        if self._time_type == "start":
            new_bytes[0] = new_num
        else:  # "end"
            new_bytes[1] = new_num

        # Write the modified schedule data back to device
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value, bytes.fromhex(self._command), bytes(new_bytes)
            )
            await asyncio.sleep(0.01)

        # Set to the rounded time value that was actually written to the device
        self._attr_native_value = quarters_to_time(new_num)
