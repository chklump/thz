import asyncio
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from datetime import datetime, time, timedelta

from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice
from .time import quarters_to_time, time_to_quarters

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):

    entities = []
    schedules = []
    write_manager: RegisterMapManagerWrite = hass.data["thz"]["write_manager"]
    device: THZDevice = hass.data["thz"]["device"]
    write_registers = write_manager.get_all_registers()
    _LOGGER.debug("write_registers: %s", write_registers)

    for name, entry in write_registers.items():
        if entry["type"] == "schedule":
            _LOGGER.debug(
                "Creating schedule for %s with command %s", name, entry["command"]
            )

        schedule = THZSchedule(
                name=name,
                command=entry["command"],
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
                start_time=None,
                end_time=None,
            )
        schedules.append(schedule)

    entity = None
    for schedule in schedules:
        start_time, end_time = await schedule.get_schedule_times_from_device()

        # Convert start_time and end_time (time objects) to datetime for the day
        # defined in schedule.day_index, so they can be safely compared/filtered.
        event_start, event_end = calculate_event_times(schedule, start_time, end_time)

        event = {
            "summary": schedule.name,
            "start": event_start,
            "end": event_end,
        }

        if schedule.name.endswith("0"):
            entity = THZCalendar(
                name=schedule.name,
                schedules=[event],
                device=device,
                icon=schedule._attr_icon,
                unique_id=schedule._attr_unique_id,
            )

            entities.append(entity)
        else:
            entity = entities[-1]
            entity.schedules.append([event])

            entities[-1] = entity


    async_add_entities(entities, True)

def calculate_event_times(schedule: THZSchedule, start_time: time, end_time: time) -> tuple[datetime, datetime]:
    event_start = start_time
    event_end = end_time

    if isinstance(start_time, time) and isinstance(end_time, time):
        today = datetime.now().date()
            # Assume schedule.day_index uses the same convention as date.weekday()
        days_ahead = (schedule.day_index - today.weekday()) % 7
        event_date = today + timedelta(days=days_ahead)
        event_start = datetime.combine(event_date, start_time)
        event_end = datetime.combine(event_date, end_time)
    return event_start,event_end

class THZCalendar(CalendarEntity):
    def __init__(
        self,
        name: str,
        schedules: list[dict],
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
        """
        self._attr_name = name
        self._device = device
        self._attr_icon = icon or "mdi:clock"
        self._attr_unique_id = unique_id
        self._attr_native_value = None
        self._schedules = schedules

    @property
    def event(self):
        # Return the next event
        now = datetime.now()
        for sched in self._schedules:
            if sched["start"] > now:
                return CalendarEvent(
                    summary=sched["summary"],
                    start=sched["start"],
                    end=sched["end"],
                )
        return None

    async def async_get_events(self, hass, start_date, end_date):
        # Return all events in the range
        return [
            CalendarEvent(
                summary=sched["summary"],
                start=sched["start"],
                end=sched["end"],
            )
            for sched in self._schedules
            if sched["start"] >= start_date and sched["end"] <= end_date
        ]

class THZSchedule():
    def __init__(
        self,
        name: str,
        command: str,
        device: THZDevice,
        start_time: datetime | None,
        end_time: datetime | None,
        icon: str | None = None,
        unique_id: str | None = None,
    ) -> None:

        self._attr_name = name
        self._command = command
        self.day_index = self._parse_day_from_name(name)  # e.g., 4 for Friday
        self._device = device
        self._start_time = start_time
        self._end_time = end_time
        self._attr_icon = icon or "mdi:clock"
        self._attr_unique_id = (
            unique_id or f"thz_time_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._attr_native_value = None
        # To get the schedule times, you must await the async function in an async context
        # Example usage in an async method:
        # self._start_time, self._end_time = await self.get_schedule_times_from_device()
        # For __init__, consider initializing with None or fetching times later in an async setup
        self._start_time = None
        self._end_time = None

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
    
    async def get_schedule_times_from_device(self) -> tuple[time|None, time|None]:
        """Retrieve schedule times from the device for this entity's day."""
        async with self._device.lock:
            raw_value = self._device.read_value(
                bytes.fromhex(self._command), "get", 4, 4
            )
            await asyncio.sleep(
                0.01
            )  # Kurze Pause, um sicherzustellen, dass das Gerät bereit ist

        start_time_raw = int.from_bytes(
            raw_value[0:2], byteorder="little", signed=False
        )
        end_time_raw = int.from_bytes(raw_value[2:4], byteorder="little", signed=False)
        start_time = quarters_to_time(start_time_raw)
        end_time = quarters_to_time(end_time_raw)
        return start_time, end_time
