'''Schedule entity for THZ devices.'''
import asyncio
import logging
from datetime import time

from homeassistant.components.schedule import ScheduleEntity, ScheduleInfo    # pyright: ignore[reportMissingImports, reportMissingModuleSource]
from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice
from .time import time_to_quarters, quarters_to_time

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
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
            _LOGGER.debug("Creating Time for %s with command %s", name, entry['command'])
            entity = THZSchedule(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
            )
            entities.append(entity)



    async_add_entities(entities, True)

class THZSchedule(ScheduleEntity):
    """Schedule entity for THZ devices.
    This class represents a schedule entity that can read and write schedule values from/to THZ devices.
    It handles conversion between quarter-hour based time values used by the device and standard
    time format used by Home Assistant.
    """

    def __init__(self, name: str, command: str, device: THZDevice, icon: str | None = None, unique_id: str | None = None):
        """Initialize the THZ Schedule entity.
        Args:
            name: The name of the entity.
            command: The command/register associated with this entity.
            device: The THZDevice instance to interact with.
            icon: Optional icon for the entity.
            unique_id: Optional unique ID for the entity.
        """
        self._attr_name = name
        self._command = command
        self.day_index = self._parse_day_from_name(name)  # e.g., 4 for Friday
        self._device = device
        self._attr_icon = icon or "mdi:clock"
        self._attr_unique_id = unique_id or f"thz_time_{command.lower()}_{name.lower().replace(' ', '_')}"
        self._attr_native_value = None

    def _parse_day_from_name(self, name: str) -> int:
        """Extract day index from name (e.g., 'programDHW_Fr_0' -> 4 for Friday)."""
        parts = name.split('_')
        if len(parts) >= 2:
            day_str = parts[1]
            day_map = {'Mo': 0, 'Tu': 1, 'We': 2, 'Th': 3, 'Fr': 4, 'Sa': 5, 'So': 6, 'Mo-Fr': [0, 1, 2, 3, 4], 'Sa-So': [5, 6], 'Mo-So': [0, 1, 2, 3, 4, 5, 6]}
            return day_map.get(day_str, 0)  # Default to Monday if unknown
        return 0

    async def async_update(self) -> None:
        """Fetch the single slot for this day."""
        try:
            schedule_list = await self.get_schedule_times_from_device()
            self._attr_native_value = schedule_list
        except (ValueError, asyncio.TimeoutError) as exc:
            _LOGGER.error("Failed to update schedule for %s: %s", self._command, exc)
            self._attr_native_value = []

    async def get_schedule_times_from_device(self) -> list[ScheduleInfo]:
        """Retrieve schedule times from the device for this entity's day."""
        async with self._device.lock:
            raw_value = self._device.read_value(bytes.fromhex(self._command), "get", 4, 4)
            await asyncio.sleep(0.01)  # Kurze Pause, um sicherzustellen, dass das Gerät bereit ist

        start_time_raw = int.from_bytes(raw_value[0:2], byteorder='little', signed=False)
        end_time_raw = int.from_bytes(raw_value[2:4], byteorder='little', signed=False)
        start_time = quarters_to_time(start_time_raw)
        end_time = quarters_to_time(end_time_raw)
        return [ScheduleInfo(start_time=start_time, end_time=end_time, days=[self.day_index])]


    async def async_set_schedule(self, schedule: list[ScheduleInfo]) -> None:
        """Write the schedule to the device."""
        try:
            if not schedule:
                # Handle empty schedule (e.g., clear the slot)
                empty_time = time_to_quarters(None)
                empty_time_bytes = empty_time.to_bytes(2, byteorder='little', signed=False) 
                await self.hass.async_add_executor_job(
                    self._device.write_value, self._command, empty_time_bytes + empty_time_bytes
                )
                return
            slot = schedule[0]  # Only one slot per entity
            start_time = slot.start_time
            end_time = slot.end_time
            start_time_quarters = time_to_quarters(start_time)
            end_time_quarters = time_to_quarters(end_time)
            start_time = start_time_quarters.to_bytes(2, byteorder='little', signed=False)
            end_time = end_time_quarters.to_bytes(2, byteorder='little', signed=False)

            await self.hass.async_add_executor_job(
                self._device.write_value, self._command, start_time + end_time
            )
            await self.async_update()
        except Exception as exc:
            _LOGGER.error("Failed to set schedule for %s: %s", self._command, exc)
            raise

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def icon(self) -> str | None:
        """Return the icon of the entity."""
        return self._icon

    @property
    def unique_id(self) -> str | None:
        """Return the unique ID of the entity."""
        return self._unique_id
