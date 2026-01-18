"""Base entity classes for THZ integration.

This module provides base classes for THZ entities to reduce code duplication
across entity platforms (number, switch, select, time).
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.helpers.entity import Entity

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN, should_hide_entity_by_default

if TYPE_CHECKING:
    from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


class THZBaseEntity(Entity):
    """Base class for all THZ write entities (number, switch, select, time).
    
    This class provides common properties and initialization logic shared
    across all THZ entity types that communicate with write registers.
    """

    _attr_should_poll = True

    def __init__(
        self,
        name: str,
        command: str,
        device: THZDevice,
        device_id: str,
        icon: str | None = None,
        unique_id: str | None = None,
        scan_interval: int | None = None,
        translation_key: str | None = None,
    ) -> None:
        """Initialize base THZ entity.
        
        Args:
            name: The display name of the entity.
            command: The hex command string for device communication.
            device: The THZ device instance.
            device_id: The device identifier for registry linking.
            icon: Optional icon override (defaults to "mdi:eye").
            unique_id: Optional unique ID (auto-generated if not provided).
            scan_interval: Update interval in seconds (uses DEFAULT_UPDATE_INTERVAL if not provided).
            translation_key: Optional translation key for localization.
        """
        self._attr_name = name
        self._command = command
        self._device = device
        self._device_id = device_id
        self._attr_icon = icon or "mdi:eye"
        self._translation_key = translation_key
        
        # Generate unique ID if not provided
        self._attr_unique_id = (
            unique_id or self._generate_unique_id(command, name)
        )
        
        self._attr_has_entity_name = True
        
        # Configure update interval
        interval = scan_interval if scan_interval is not None else DEFAULT_UPDATE_INTERVAL
        self.SCAN_INTERVAL = timedelta(seconds=interval)
        
        # Set default visibility based on entity naming conventions
        #TODO check implementation, until then, keep entities visible by default
        #self._attr_entity_registry_enabled_default = not should_hide_entity_by_default(name)

    def _generate_unique_id(self, command: str, name: str) -> str:
        """Generate a unique identifier for the entity.
        
        Args:
            command: The command hex string.
            name: The entity name.
            
        Returns:
            A unique identifier string.
        """
        return f"thz_set_{command.lower()}_{name.lower().replace(' ', '_')}"

    @property
    def name(self) -> str | None:
        """Return the name of the entity.
        
        When translation_key is True, return None to use translation key.
        Otherwise, return the entity name for backward compatibility.
        """
        if self.translation_key is not None:
            return None
        return self._attr_name

    @property
    def translation_key(self) -> str | None:
        """Return the translation key for this entity, if available."""
        return self._translation_key

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the registry."""
        return self._attr_entity_registry_enabled_default

    @property
    def device_info(self):
        """Return device information to link this entity with the device."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
        }
