"""Init file for THZ integration."""

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_UPDATE_INTERVAL, DOMAIN
from .thz_device import THZDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up THZ from config entry."""

    log_level_str = config_entry.data.get("log_level", "info")
    _LOGGER.setLevel(getattr(logging, log_level_str.upper(), logging.INFO))
    _LOGGER.info("Loglevel gesetzt auf: %s", log_level_str)
    _LOGGER.debug(
        "THZ async_setup_entry aufgerufen mit entry: %s", config_entry.as_dict()
    )

    hass.data.setdefault(DOMAIN, {})

    data = config_entry.data
    conn_type = data["connection_type"]

    # 1. Device "roh" initialisieren
    if conn_type == "ip":
        device = THZDevice(connection="ip", host=data["host"], tcp_port=data["port"])
    elif conn_type == "usb":
        device = THZDevice(connection="usb", port=data["device"])
    else:
        raise ValueError("Ungültiger Verbindungstyp")

    await device.async_initialize(hass)

    # 2. Firmware abfragen
    _LOGGER.info(
        "THZ-Device vollständig initialisiert (FW %s)", device.firmware_version
    )

    # --- create / update device in Home Assistant device registry using alias/area ---

    dev_reg = dr.async_get(hass)
    # prefer a stable id from the device; fall back to conn info
    unique_id = (
        getattr(device, "unique_id", None)
        or getattr(device, "serial", None)
        or f"{conn_type}-{data.get('host') or data.get('device')}"
    )
    device_name = data.get("alias") or f"THZ {data.get('host') or data.get('device')}"
    device_entry = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, unique_id)},
        name=device_name,
        manufacturer="Stiebel Eltron / Tecalor",
        model=f"LWZ/THZ (FW: {device.firmware_version})",
        sw_version=device.firmware_version,
        suggested_area=data.get("area"),
    )
    _LOGGER.debug("Device registry entry created/updated: %s", device_entry.id)

    # # 3. Mapping laden
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["write_manager"] = device.write_register_map_manager
    hass.data[DOMAIN]["register_manager"] = device.register_map_manager

    # 4. Device speichern
    hass.data[DOMAIN]["device"] = device
    hass.data[DOMAIN]["device_id"] = unique_id

    # 5. Prepare dict for storing all coordinators
    coordinators = {}
    refresh_intervals = config_entry.data.get("refresh_intervals", {})
    
    # If refresh_intervals is empty or missing, populate with defaults for all available blocks
    if not refresh_intervals:
        available_blocks = device.available_reading_blocks
        if available_blocks:
            _LOGGER.warning(
                "No refresh_intervals found in config, using default interval of %s seconds for %d blocks",
                DEFAULT_UPDATE_INTERVAL,
                len(available_blocks)
            )
            refresh_intervals = {
                block: DEFAULT_UPDATE_INTERVAL
                for block in available_blocks
            }
        else:
            _LOGGER.error(
                "No available reading blocks found on device and no refresh_intervals in config"
            )
            # Continue with empty dict - no coordinators or sensors will be created
    else:
        _LOGGER.debug(
            "Creating coordinators with refresh intervals: %s", refresh_intervals
        )
    
    # Create a coordinator for each block with its own interval
    for block, interval in refresh_intervals.items():
        _LOGGER.debug(
            "Creating coordinator for block %s with interval %s seconds", block, interval
        )
        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"THZ {block}",
            update_interval=timedelta(seconds=int(interval)),
            update_method=lambda b=block: _async_update_block(hass, device, b),
        )
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info(
            "Initial data fetch completed for block %s, data available: %s",
            block,
            coordinator.data is not None,
        )
        coordinators[block] = coordinator

    # im hass.data speichern
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "device": device,
        "coordinators": coordinators,
    }

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(
        config_entry, ["sensor", "number", "switch", "select", "time"]
    )

    return True


async def _async_update_block(hass: HomeAssistant, device: THZDevice, block_name: str):
    """Wird vom Coordinator aufgerufen, um einen Block zu lesen."""
    block_bytes = bytes.fromhex(block_name.removeprefix("pxx"))
    try:
        _LOGGER.debug("Lese Block %s", block_name)
        async with device.lock:
            return await hass.async_add_executor_job(device.read_block, block_bytes, "get")
    except Exception as err:
        raise UpdateFailed(f"Fehler beim Lesen von {block_name}: {err}") from err


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remove Config Entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["sensor", "select", "number", "time", "switch"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
