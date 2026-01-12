"""Climate platform for THZ integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, WRITE_REGISTER_OFFSET, WRITE_REGISTER_LENGTH

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up THZ climate entities from a config entry."""
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    device = entry_data["device"]
    coordinators = entry_data["coordinators"]
    device_id = hass.data[DOMAIN]["device_id"]
    write_manager = hass.data[DOMAIN]["write_manager"]
    
    # Get the main coordinator (typically the one with temperature sensors)
    # We'll use the first available coordinator for updates
    main_coordinator = next(iter(coordinators.values()), None)
    
    if main_coordinator is None:
        _LOGGER.warning("No coordinator available for climate entity")
        return
    
    climate_entities = []
    
    # Check if we have the necessary parameters for HC1 (Heating Circuit 1)
    hc1_params = write_manager.get_parameters_by_prefix("p01_roomTempDayHC1")
    if hc1_params:
        climate_entities.append(
            THZClimate(
                main_coordinator,
                device,
                device_id,
                write_manager,
                "hc1",
                "Heating Circuit 1",
            )
        )
    
    # Check if we have parameters for HC2 (Heating Circuit 2)
    hc2_params = write_manager.get_parameters_by_prefix("p01_roomTempDayHC2")
    if hc2_params:
        climate_entities.append(
            THZClimate(
                main_coordinator,
                device,
                device_id,
                write_manager,
                "hc2",
                "Heating Circuit 2",
                entity_registry_enabled_default=False,  # HC2 hidden by default
            )
        )
    
    if climate_entities:
        async_add_entities(climate_entities, True)
        _LOGGER.info("Added %d climate entities", len(climate_entities))


class THZClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a THZ climate entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.AUTO, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = ["comfort", "eco", "off"]
    
    def __init__(
        self,
        coordinator,
        device,
        device_id: str,
        write_manager,
        circuit_id: str,
        circuit_name: str,
        entity_registry_enabled_default: bool = True,
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        
        self._device = device
        self._device_id = device_id
        self._write_manager = write_manager
        self._circuit_id = circuit_id
        self._circuit_name = circuit_name
        
        # Entity attributes
        self._attr_unique_id = f"{device_id}_climate_{circuit_id}"
        self._attr_name = f"THZ {circuit_name}"
        self._attr_entity_registry_enabled_default = entity_registry_enabled_default
        
        # Temperature parameters names based on circuit
        if circuit_id == "hc1":
            self._temp_day_param = "p01_roomTempDayHC1"
            self._temp_night_param = "p02_roomTempNightHC1"
            self._mode_param = "opMode"
        else:  # hc2
            self._temp_day_param = "p01_roomTempDayHC2"
            self._temp_night_param = "p02_roomTempNightHC2"
            self._mode_param = "opModeHC2"
        
        # Current state
        self._target_temperature = None
        self._current_temperature = None
        self._hvac_mode = HVACMode.AUTO
        self._preset_mode = "comfort"
    
    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": f"THZ {self._device_id}",
            "manufacturer": "Stiebel Eltron / Tecalor",
        }
    
    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        # Try to get current room temperature from coordinator data
        # This depends on having the right sensor in the data
        if self.coordinator.data:
            # For now, return None - in a real implementation, we'd parse
            # the coordinator data to find the current room temperature sensor
            pass
        return self._current_temperature
    
    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature
    
    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return self._hvac_mode
    
    @property
    def preset_mode(self) -> str | None:
        """Return current preset mode."""
        return self._preset_mode
    
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        _LOGGER.debug(
            "Setting target temperature for %s to %s°C",
            self._circuit_name,
            temperature,
        )
        
        # Determine which parameter to write based on preset mode
        param_name = (
            self._temp_day_param if self._preset_mode == "comfort"
            else self._temp_night_param
        )
        
        # Get parameter info from write manager
        param_info = self._write_manager.get_parameter(param_name)
        if not param_info:
            _LOGGER.error("Parameter %s not found in write manager", param_name)
            return
        
        # Convert temperature to device format (typically * 10 for one decimal)
        temp_value = int(temperature * 10)
        
        try:
            # Write the value to the device
            async with self._device.lock:
                success = await self.hass.async_add_executor_job(
                    self._device.write_value,
                    bytes.fromhex(param_info["register"]),
                    temp_value,
                )
            
            if success:
                self._target_temperature = temperature
                self.async_write_ha_state()
                _LOGGER.info(
                    "Successfully set %s target temperature to %s°C",
                    self._circuit_name,
                    temperature,
                )
            else:
                _LOGGER.error(
                    "Failed to set target temperature for %s", self._circuit_name
                )
        except Exception as err:
            _LOGGER.error(
                "Error setting target temperature for %s: %s",
                self._circuit_name,
                err,
            )
    
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        _LOGGER.debug("Setting HVAC mode for %s to %s", self._circuit_name, hvac_mode)
        
        # Get the operation mode parameter
        param_info = self._write_manager.get_parameter(self._mode_param)
        if not param_info:
            _LOGGER.warning(
                "Operation mode parameter %s not found", self._mode_param
            )
            return
        
        # Map HVAC mode to device value
        # This mapping may need adjustment based on actual device values
        mode_map = {
            HVACMode.OFF: 0,
            HVACMode.HEAT: 1,
            HVACMode.AUTO: 2,
        }
        
        mode_value = mode_map.get(hvac_mode)
        if mode_value is None:
            _LOGGER.error("Unsupported HVAC mode: %s", hvac_mode)
            return
        
        try:
            async with self._device.lock:
                success = await self.hass.async_add_executor_job(
                    self._device.write_value,
                    bytes.fromhex(param_info["register"]),
                    mode_value,
                )
            
            if success:
                self._hvac_mode = hvac_mode
                self.async_write_ha_state()
                _LOGGER.info(
                    "Successfully set %s HVAC mode to %s",
                    self._circuit_name,
                    hvac_mode,
                )
        except Exception as err:
            _LOGGER.error(
                "Error setting HVAC mode for %s: %s", self._circuit_name, err
            )
    
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        _LOGGER.debug("Setting preset mode for %s to %s", self._circuit_name, preset_mode)
        
        if preset_mode not in self._attr_preset_modes:
            _LOGGER.error("Unsupported preset mode: %s", preset_mode)
            return
        
        self._preset_mode = preset_mode
        self.async_write_ha_state()
    
    async def async_update(self) -> None:
        """Update the entity.
        
        Called by the coordinator when new data is available.
        """
        # Read current target temperature from device
        param_name = (
            self._temp_day_param if self._preset_mode == "comfort"
            else self._temp_night_param
        )
        
        param_info = self._write_manager.get_parameter(param_name)
        if not param_info:
            return
        
        try:
            async with self._device.lock:
                value_bytes = await self.hass.async_add_executor_job(
                    self._device.read_value,
                    bytes.fromhex(param_info["register"]),
                    WRITE_REGISTER_OFFSET,
                    WRITE_REGISTER_LENGTH,
                )
            
            if value_bytes:
                # Decode temperature (typically divide by 10)
                temp_raw = int.from_bytes(value_bytes, byteorder="big", signed=True)
                self._target_temperature = temp_raw / 10.0
        except Exception as err:
            _LOGGER.debug("Error reading target temperature: %s", err)
