"""THZ Switch Entity Platform."""
import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.switch import ConfigEntry, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .entity_translations import get_translation_key
from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch entities for the THZ integration.

    This coroutine retrieves all write registers from the write manager,
    filters for switch-type registers, and creates THZSwitch entities for each one.
    The created entities are then added to Home Assistant.

    Args:
        hass: The Home Assistant instance.
        config_entry: The config entry that triggered this setup.
        async_add_entities: Callback function to register new entities.

    Returns:
        None
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
        if entry["type"] == "switch":
            _LOGGER.debug(
                "Creating Switch for %s with command %s", name, entry["command"]
            )
            entity = THZSwitch(
                name=name,
                command=entry["command"],
                min_value=entry["min"],
                max_value=entry["max"],
                step=entry.get("step", 1),
                unit=entry.get("unit", ""),
                device_class=entry.get("device_class"),
                device=device,
                icon=entry.get("icon"),
                unique_id=f"thz_{name.lower().replace(' ', '_')}",
                scan_interval=write_interval,
                device_id=device_id,
                translation_key=get_translation_key(name),
            )
            entities.append(entity)

    async_add_entities(entities, True)


class THZSwitch(SwitchEntity):
    """Represents a switch entity for a THZ device in Home Assistant.

    This class provides asynchronous methods to control and monitor a switch on a THZ device.
    It handles reading the switch state from the device, as well as turning the switch on and off
    by sending the appropriate commands. Thread safety is ensured by acquiring a lock on the device
    during communication operations.

    Attributes:
        _attr_should_poll (bool): Indicates if the entity should be polled for updates.
        _attr_name (str): The name of the switch entity.
        _command (str): The command code used to communicate with the device.
        _device: The device instance used for communication.
        _attr_icon (str): The icon representing the switch in the UI.
        _attr_unique_id (str): A unique identifier for the switch entity.
        _is_on (bool): The current state of the switch (on/off).
        name (str): The name of the switch.
        command (str): The command code for the switch.
        min_value (int): Minimum value for the switch (unused in this implementation).
        max_value (int): Maximum value for the switch (unused in this implementation).
        step (int): Step value for the switch (unused in this implementation).
        unit (str): Unit of measurement (unused in this implementation).
        device_class (str): Device class for the switch (unused in this implementation).
        device: The device instance for communication.
        icon (str, optional): Icon for the switch. Defaults to "mdi:eye".
        unique_id (str, optional): Unique identifier for the switch.

    Properties:
        is_on (bool): Returns the current state of the switch.

    Methods:
        async_update(): Asynchronously updates the state of the switch by reading its value from the device.
        turn_on(**kwargs): Asynchronously turns on the switch by sending a command to the device.
        turn_off(**kwargs): Asynchronously turns off the switch by sending a command to the device.
    """

    _attr_should_poll = True

    def __init__(
        self,
        name: str,
        command: str,
        min_value: int,
        max_value: int,
        step: int,
        unit: str,
        device_class: str,
        device,
        icon: str | None = None,
        unique_id: str | None = None,
        scan_interval: int | None = None,
        device_id: str | None = None,
        translation_key: str | None = None,
    ) -> None:
        """Initialize a new switch entity for the THZ integration.

        Args:
            name (str): The name of the switch.
            command (str): The command associated with the switch.
            min_value (int): The minimum value for the switch.
            max_value (int): The maximum value for the switch.
            step (int): The step size for value changes.
            unit (str): The unit of measurement for the switch.
            device_class (str): The device class for the switch.
            device: The device instance this switch is associated with.
            icon (str, optional): The icon to use for the switch. Defaults to "mdi:eye" if not provided.
            unique_id (str, optional): The unique identifier for the switch. If not provided, a unique ID is generated.
            scan_interval (int, optional): The scan interval in seconds for polling updates.
            device_id (str, optional): The device identifier for linking to device.
            translation_key (str, optional): Translation key for localization.
        """

        self._attr_name = name
        self._command = command
        self._device = device
        self._attr_icon = icon or "mdi:eye"
        self._attr_unique_id = (
            unique_id or f"thz_set_{command.lower()}_{name.lower().replace(' ', '_')}"
        )
        self._is_on = False
        self._device_id = device_id
        self._translation_key = translation_key
        # Enable entity name translation when translation_key is provided
        self._attr_has_entity_name = True
        # Always set SCAN_INTERVAL to avoid HA's 30-second default
        # Use provided scan_interval or fall back to DEFAULT_UPDATE_INTERVAL
        interval = scan_interval if scan_interval is not None else DEFAULT_UPDATE_INTERVAL
        self.SCAN_INTERVAL = timedelta(seconds=interval)

    @property
    def is_on(self) -> bool | None:
        """Return whether the switch is currently on.

        Returns:
            bool: True if the switch is on, False otherwise.

        Note:
            This property returns the entity's last known state and does not perform
            any I/O or communicate with the underlying device. Call the entity's
            update methods to refresh the state if necessary.
        """

        return self._is_on

    @property
    def name(self) -> str | None:
        """Return the name of the switch, or None if translation_key is set.
        
        When translation_key is set, Home Assistant will use the translation
        system to get the localized name. Return None in that case to allow
        the translation system to work properly.
        """
        if self._translation_key:
            return None
        return self._attr_name

    @property
    def translation_key(self) -> str | None:
        """Return the translation key for this switch, if available."""
        return self._translation_key

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        from .const import DOMAIN
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }

    # TODO debugging um die richtigen Werte zu bekommen
    async def async_update(self) -> None:
        """Asynchronously updates the state of the switch by reading its value from the device.

        This method acquires a lock on the device to ensure thread safety, sends a read command to the device,
        and interprets the returned value as an on/off state. It also includes a short pause to ensure the device
        is ready for the next operation.

        Side Effects:
            - Updates the internal `_is_on` attribute based on the value read from the device.

        Raises:
            Any exceptions raised by the underlying device communication methods.
        """

        # Read the value from the device and interpret as on/off
        _LOGGER.debug(
            "Updating switch %s with command %s", self._attr_name, self._command
        )
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value, bytes.fromhex(self._command), "get", 4, 2
            )
            await asyncio.sleep(
                0.01
            )  # Kurze Pause, um sicherzustellen, dass das Gerät bereit ist
        
        # Validate that we received data
        if not value_bytes:
            _LOGGER.warning(
                "No data received for switch %s, keeping previous value", self._attr_name
            )
            return
        
        try:
            value = int.from_bytes(value_bytes, byteorder="big", signed=False)
            self._is_on = bool(value)
        except (ValueError, IndexError, TypeError) as err:
            _LOGGER.error(
                "Error decoding switch %s: %s", self._attr_name, err, exc_info=True
            )
            # Keep previous value on error

    async def turn_on(self, **kwargs: Any) -> None:
        """Asynchronously turns on the switch by sending a command to the device.

        Acquires the device lock to ensure thread safety, then writes the 'on' value (1)
        to the device using the specified command. Updates the internal state to reflect
        that the switch is now on.

        Args:
            **kwargs: Additional keyword arguments (not used).

        Returns:
            None
        """

        value_int = 1
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                value_int.to_bytes(2, byteorder="big", signed=False),
            )
        self._is_on = True

    async def turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch by writing a zero value to the device.

        This method sends a command to the device to turn off the switch. It acquires
        a lock to ensure thread-safe access to the device, then writes a zero integer
        value (as 2 bytes in big-endian format) along with the command to the device.
        After the write operation completes, the internal state is updated to reflect
        that the switch is now off.

        Args:
            **kwargs: Additional keyword arguments (unused).

        Returns:
            None

        Raises:
            Any exceptions raised by self._device.write_value() will propagate.
        """

        value_int = 0
        async with self._device.lock:
            await self.hass.async_add_executor_job(
                self._device.write_value,
                bytes.fromhex(self._command),
                value_int.to_bytes(2, byteorder="big", signed=False),
            )
        self._is_on = False
