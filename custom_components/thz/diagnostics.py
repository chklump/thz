"""Diagnostics support for THZ integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# Keys to redact from diagnostics for privacy
TO_REDACT = {
    "host",
    "device",
    "unique_id",
    "serial",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.
    
    Provides comprehensive diagnostic information about the THZ integration
    for troubleshooting purposes. Includes device information, firmware version,
    connection status, available blocks, coordinator states, and entity counts.
    
    Args:
        hass: Home Assistant instance
        config_entry: The config entry to get diagnostics for
        
    Returns:
        Dictionary containing diagnostic information with sensitive data redacted
    """
    entry_data = hass.data[DOMAIN].get(config_entry.entry_id, {})
    device = entry_data.get("device")
    coordinators = entry_data.get("coordinators", {})
    
    # Gather coordinator diagnostics
    coordinator_info = {}
    for block_name, coordinator in coordinators.items():
        coordinator_info[block_name] = {
            "last_update_success": coordinator.last_update_success,
            "last_update_time": coordinator.last_update_time.isoformat() if coordinator.last_update_time else None,
            "update_interval": str(coordinator.update_interval) if coordinator.update_interval else None,
            "data_available": coordinator.data is not None,
            "data_size_bytes": len(coordinator.data) if coordinator.data else 0,
        }
    
    # Gather device diagnostics
    device_info = {}
    if device:
        device_info = {
            "connection_type": device.connection,
            "firmware_version": device.firmware_version,
            "initialized": device._initialized,
            "connection_open": device.ser is not None,
            "available_reading_blocks": list(device.available_reading_blocks) if hasattr(device, "available_reading_blocks") else [],
            "register_map_loaded": device.register_map_manager is not None,
            "write_map_loaded": device.write_register_map_manager is not None,
        }
        
        # Add connection-specific info
        if device.connection == "usb":
            device_info["port"] = device.port
            device_info["baudrate"] = device.baudrate
        elif device.connection == "ip":
            device_info["host"] = device.host
            device_info["tcp_port"] = device.tcp_port
            
        device_info["read_timeout"] = device.read_timeout
    
    # Get entity registry to count entities
    entity_registry = hass.helpers.entity_registry.async_get(hass)
    entities = hass.helpers.entity_registry.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    
    entity_counts = {
        "total": len(entities),
        "enabled": sum(1 for e in entities if not e.disabled),
        "disabled": sum(1 for e in entities if e.disabled),
    }
    
    # Count by platform
    platform_counts = {}
    for entity in entities:
        platform = entity.domain
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
    
    diagnostics = {
        "config_entry": {
            "title": config_entry.title,
            "version": config_entry.version,
            "data": async_redact_data(config_entry.data, TO_REDACT),
        },
        "device": device_info,
        "coordinators": coordinator_info,
        "entities": {
            "counts": entity_counts,
            "by_platform": platform_counts,
        },
    }
    
    return diagnostics
