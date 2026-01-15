"""THZ Switch Entity Platform."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .base_entity import THZBaseEntity
from .entity_translations import get_translation_key
from .const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    WRITE_REGISTER_OFFSET,
    WRITE_REGISTER_LENGTH,
)
from .register_maps.register_map_manager import RegisterMapManagerWrite
from .thz_device import THZDevice
from .value_codec import THZValueCodec

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for the THZ integration."""
    write_manager: RegisterMapManagerWrite = hass.data[DOMAIN]["write_manager"]
    device: THZDevice = hass.data[DOMAIN]["device"]
    device_id = hass.data[DOMAIN]["device_id"]
    
    # Get write interval from config, default to DEFAULT_UPDATE_INTERVAL
    write_interval = config_entry.data.get("write_interval", DEFAULT_UPDATE_INTERVAL)
    
    write_registers = write_manager.get_all_registers()
    _LOGGER.debug("Loading switch platform with %d registers", len(write_registers))
    
    entities = []
    for name, entry in write_registers.items():
        if entry["type"] == "switch":
            _LOGGER.debug(
                "Creating THZSwitch for %s with command %s", name, entry["command"]
            )
            entity = THZSwitch(
                name=name,
                entry=entry,
                device=device,
                device_id=device_id,
                scan_interval=write_interval,
            )
            entities.append(entity)

    _LOGGER.info("Created %d switch entities", len(entities))
    async_add_entities(entities, True)




class THZSwitch(THZBaseEntity, SwitchEntity):
    """Representation of a THZ Switch entity."""

    def __init__(
        self,
        name: str,
        entry: dict,
        device: THZDevice,
        device_id: str,
        scan_interval: int | None = None,
    ) -> None:
        """Initialize a THZ switch entity.

        Args:
            name: The name of the switch.
            entry: The register entry dict containing configuration.
            device: The device instance this switch is associated with.
            device_id: The device identifier for linking to device.
            scan_interval: The scan interval in seconds for polling updates.
        """
        # Initialize base class with common properties
        super().__init__(
            name=name,
            command=entry["command"],
            device=device,
            device_id=device_id,
            icon=entry.get("icon"),
            scan_interval=scan_interval,
            translation_key=get_translation_key(name),
        )
        
        # Switch-specific attributes
        self._is_on = False

    @property
    def is_on(self) -> bool | None:
        """Return whether the switch is currently on."""
        return self._is_on

    async def async_update(self) -> None:
        """Update the switch state by reading the current value from the device."""
        _LOGGER.debug(
            "Updating switch %s with command %s", self._attr_name, self._command
        )
        
        async with self._device.lock:
            value_bytes = await self.hass.async_add_executor_job(
                self._device.read_value,
                bytes.fromhex(self._command),
                "get",
                WRITE_REGISTER_OFFSET,
                WRITE_REGISTER_LENGTH,
            )
            # Short pause to ensure the device is ready
            await asyncio.sleep(0.01)
        
        # Validate that we received data
        if not value_bytes:
            _LOGGER.warning(
                "No data received for switch %s, keeping previous value", self._attr_name
            )
            return
        
        _LOGGER.debug("Received bytes for %s: %s", self._attr_name, value_bytes.hex())
        
        try:
            # Use centralized codec for decoding
            self._is_on = THZValueCodec.decode_switch(value_bytes)
            _LOGGER.debug("Decoded switch state for %s: %s", self._attr_name, self._is_on)
        except (ValueError, IndexError, TypeError) as err:
            _LOGGER.error(
                "Error decoding switch %s: %s", self._attr_name, err, exc_info=True
            )
            # Keep previous value on error

    async def turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch by sending a command to the device."""
        _LOGGER.debug("Turning on switch %s", self._attr_name)
        
        try:
            # Use centralized codec for encoding
            value_bytes = THZValueCodec.encode_switch(True)
            
            async with self._device.lock:
                await self.hass.async_add_executor_job(
                    self._device.write_value,
                    bytes.fromhex(self._command),
                    value_bytes,
                )
            
            self._is_on = True
        except (ValueError, TypeError) as err:
            _LOGGER.error(
                "Error encoding switch %s to turn on: %s", 
                self._attr_name, err, exc_info=True
            )

    async def turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch by sending a command to the device."""
        _LOGGER.debug("Turning off switch %s", self._attr_name)
        
        try:
            # Use centralized codec for encoding
            value_bytes = THZValueCodec.encode_switch(False)
            
            async with self._device.lock:
                await self.hass.async_add_executor_job(
                    self._device.write_value,
                    bytes.fromhex(self._command),
                    value_bytes,
                )
            
            self._is_on = False
        except (ValueError, TypeError) as err:
            _LOGGER.error(
                "Error encoding switch %s to turn off: %s", 
                self._attr_name, err, exc_info=True
            )
