"""Schedule entity for THZ devices."""

import asyncio
from dataclasses import dataclass
from datetime import time, timedelta
import logging

from homeassistant.components.schedule import Schedule
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice
from .time import quarters_to_time, time_to_quarters

_LOGGER = logging.getLogger(__name__)

# Set update interval to 2 hours
SCAN_INTERVAL = timedelta(minutes=120)


@dataclass
class ScheduleInfo:
    """Represents a schedule slot."""

    start_time: time | None
    end_time: time | None
    days: list[int]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up THZ Time entities from a config entry.

    This function creates THZTime entities based on write registers of type "schedule"
    from the device's register map.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry to set up.
        async_add_entities: Callback to add new entities.

    Returns:
        None. Entities are added via the async_add_entities callback.

    Note:
        - Requires 'write_manager' and 'device' to be present in hass.data['thz']
        - Creates a THZTime entity for each register with type 'time'
        - Entity IDs are generated from the register name, converted to lowercase with spaces replaced by underscores
    """
    entities = []
    write_manager: RegisterMapManagerWrite = hass.data["thz"]["write_manager"]
    device: THZDevice = hass.data["thz"]["device"]
    write_registers = write_manager.get_all_registers()
    _LOGGER.debug("write_registers: %s", write_registers)
    for name, entry in write_registers.items():
        if entry["type"] == "schedule":
            _LOGGER.debug(
                "Creating Time for %s with command %s", name, entry["command"]
            )
            entity = THZSchedule(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
            )
            entities.append(entity)

    async_add_entities(entities, True)


class THZSchedule(Schedule):
    """Schedule entity for THZ devices.

    This class represents a schedule entity that can read and write schedule
    values from/to THZ devices. It handles conversion between quarter-hour
    based time values used by the device and standard time format used by
    Home Assistant.
    """

    def __init__(
        self,
        name: str,
        command: str,
        device: THZDevice,
        icon: str | None = None,
        unique_id: str | None = None,
    ) -> None:
        """Initialize the THZ Schedule entity.

        Args:
            name: The name of the entity.
            command: The command/register associated with this entity.
            device: The THZDevice instance to interact with.
            icon: Optional icon for the entity.
            unique_id: Optional unique ID for the entity.

        Note:
            The original code called super().__init__(config, editable=True) but
            'config' was never defined - this was a pre-existing bug. The Schedule
            helper entity in HA doesn't require config in its constructor.
        """
        super().__init__()

        self._attr_name = name
        self._command = command
        self.day_index = self._parse_day_from_name(name)  # e.g., 4 for Friday
        self._device = device
        self._attr_icon = icon or "mdi:clock"
        unique_suffix = name.lower().replace(' ', '_')
        self._attr_unique_id = (
            unique_id or f"thz_time_{command.lower()}_{unique_suffix}"
        )
        self._attr_native_value = None

    def _parse_day_from_name(self, name: str) -> int:
        """Extract day index from name (e.g., 'programDHW_Fr_0' -> 4 for Friday)."""
        parts = name.split("_")
        if len(parts) >= 2:
            day_str = parts[1]
            day_map = {
                "Mo": 0,
                "Tu": 1,
                "We": 2,
                "Th": 3,
                "Fr": 4,
                "Sa": 5,
                "So": 6,
                "Mo-Fr": [0, 1, 2, 3, 4],
                "Sa-So": [5, 6],
                "Mo-So": [0, 1, 2, 3, 4, 5, 6],
            }
            return day_map.get(day_str, 0)  # Default to Monday if unknown
        return 0

    async def async_update(self) -> None:
        """Fetch the single slot for this day."""
        try:
            schedule_list = await self.get_schedule_times_from_device()
            self._attr_native_value = schedule_list
        except (ValueError, TimeoutError) as exc:
            _LOGGER.error("Failed to update schedule for %s: %s", self._command, exc)
            self._attr_native_value = []

    async def get_schedule_times_from_device(self) -> list[ScheduleInfo]:
        """Retrieve schedule times from the device for this entity's day."""
        async with self._device.lock:
            raw_value = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                4,
                4
            )
            await asyncio.sleep(
                0.01
            )  # Short pause to ensure the device is ready

        # Schedule data format (from FHEM 7prog):
        # - raw_value[0]: start time (1 byte, 0-95 quarters)
        # - raw_value[1]: end time (1 byte, 0-95 quarters)
        start_time_raw = raw_value[0]
        end_time_raw = raw_value[1]
        start_time = quarters_to_time(start_time_raw)
        end_time = quarters_to_time(end_time_raw)
        return [
            ScheduleInfo(
                start_time=start_time, end_time=end_time, days=[self.day_index]
            )
        ]

    async def async_set_schedule(self, schedule: list[ScheduleInfo]) -> None:
        """Write the schedule to the device."""
        try:
            if not schedule:
                # Handle empty schedule (e.g., clear the slot)
                empty_time = time_to_quarters(None)
                # Read current data to preserve other bytes
                async with self._device.lock:
                    current_bytes = await self.hass.async_add_executor_job(
                        self._device.read_value,
                        bytes.fromhex(self._command),
                        "get",
                        4,
                        4,
                    )
                # Update only the time bytes (0 and 1)
                new_bytes = bytearray(current_bytes)
                new_bytes[0] = empty_time
                new_bytes[1] = empty_time
                async with self._device.lock:
                    await self.hass.async_add_executor_job(
                        self._device.write_value,
                        bytes.fromhex(self._command),
                        bytes(new_bytes),
                    )
                return
            slot = schedule[0]  # Only one slot per entity
            start_time = slot.start_time
            end_time = slot.end_time
            start_time_quarters = time_to_quarters(start_time)
            end_time_quarters = time_to_quarters(end_time)

            # Read current data to preserve other bytes
            async with self._device.lock:
                current_bytes = await self.hass.async_add_executor_job(
                    self._device.read_value,
                    bytes.fromhex(self._command),
                    "get",
                    4,
                    4,
                )

            # Update only the time bytes (0 and 1)
            new_bytes = bytearray(current_bytes)
            new_bytes[0] = start_time_quarters
            new_bytes[1] = end_time_quarters

            async with self._device.lock:
                await self.hass.async_add_executor_job(
                    self._device.write_value,
                    bytes.fromhex(self._command),
                    bytes(new_bytes),
                )

            await self.async_update()
        except Exception as exc:
            _LOGGER.error("Failed to set schedule for %s: %s", self._command, exc)
            raise

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self.name

    @property
    def icon(self) -> str | None:
        """Return the icon of the entity."""
        return self.icon

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self.unique_id
