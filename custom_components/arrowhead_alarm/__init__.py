"""The Arrowhead Alarm Panel integration."""
import asyncio
import logging
from typing import Dict, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    DOMAIN,
    CONF_USER_PIN,
    CONF_PANEL_TYPE,
    PANEL_CONFIGS,
    CONF_MAX_OUTPUTS,
    DEFAULT_MAX_OUTPUTS,
    DEFAULT_USER_PIN,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
)
from .arrowhead_client import ArrowheadClient
from .coordinator import ArrowheadDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Arrowhead Alarm Panel from a config entry."""
    _LOGGER.info("=== SETTING UP ARROWHEAD ALARM PANEL ===")
    _LOGGER.info("Entry ID: %s", entry.entry_id)
    _LOGGER.info("Entry data: %s", {k: v for k, v in entry.data.items() if k not in ['username', 'password', 'user_pin']})

    # Get configuration
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 9000)
    user_pin = entry.data.get(CONF_USER_PIN, DEFAULT_USER_PIN)
    username = entry.data.get("username", DEFAULT_USERNAME)
    password = entry.data.get("password", DEFAULT_PASSWORD)
    panel_type = entry.data.get(CONF_PANEL_TYPE, "esx")
    
    # Get panel configuration
    panel_config = PANEL_CONFIGS.get(panel_type, PANEL_CONFIGS["esx"])
    _LOGGER.info("Panel type: %s, Config: %s", panel_type, panel_config)

    # Create client
    _LOGGER.info("Creating ArrowheadClient for %s:%s", host, port)
    client = ArrowheadClient(host, port, user_pin, username, password, panel_type)

    # Test connection
    _LOGGER.info("Testing connection to alarm panel...")
    try:
        success = await asyncio.wait_for(client.connect(), timeout=30.0)
        if not success:
            _LOGGER.error("Failed to connect to alarm panel at %s:%s", host, port)
            raise ConfigEntryNotReady(f"Unable to connect to alarm panel at {host}:{port}")
            
        _LOGGER.info("Successfully connected to alarm panel")
        
        # Get initial status to verify communication
        _LOGGER.info("Getting initial status...")
        status = await asyncio.wait_for(client.get_status(), timeout=10.0)
        if not status:
            _LOGGER.error("Failed to get status from alarm panel")
            await client.disconnect()
            raise ConfigEntryNotReady("Unable to communicate with alarm panel")
            
        _LOGGER.info("Initial status received, status keys: %s", list(status.keys()))
        
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout connecting to alarm panel at %s:%s", host, port)
        raise ConfigEntryNotReady(f"Timeout connecting to alarm panel at {host}:{port}")
    except Exception as err:
        _LOGGER.error("Error connecting to alarm panel: %s", err)
        await client.disconnect()
        raise ConfigEntryNotReady(f"Error connecting to alarm panel: {err}")

    # Configure outputs manually before setting up coordinator
    max_outputs = entry.data.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
    _LOGGER.info("=== CONFIGURING OUTPUTS ===")
    _LOGGER.info("Configuring %d outputs before coordinator setup", max_outputs)
    
    # Manual output configuration - add outputs directly to client status
    try:
        # Create outputs dictionary with user-specified count  
        manual_outputs = set(range(1, max_outputs + 1))
        client._status["outputs"] = {o: False for o in manual_outputs}
        
        # Update status with manual configuration info
        client._status.update({
            "total_outputs_detected": max_outputs,
            "max_outputs_detected": max_outputs,
            "output_detection_method": "manual_configuration",
            "output_ranges": {"main_panel": list(manual_outputs)}
        })
        
        _LOGGER.info("Manual output configuration complete:")
        _LOGGER.info("  - Outputs created: %s", list(client._status["outputs"].keys()))
        _LOGGER.info("  - Total outputs: %d", max_outputs)
        _LOGGER.info("  - Detection method: manual_configuration")
        
    except Exception as err:
        _LOGGER.error("Error configuring manual outputs: %s", err)
        # Continue anyway with empty outputs
        client._status["outputs"] = {}

    # Create coordinator
    _LOGGER.info("=== CREATING COORDINATOR ===")
    scan_interval = entry.options.get("scan_interval", 30)
    coordinator = ArrowheadDataUpdateCoordinator(hass, client, scan_interval)
    
    # Set up coordinator
    try:
        _LOGGER.info("Setting up coordinator...")
        await coordinator.async_setup()
        _LOGGER.info("Coordinator setup complete")
    except Exception as err:
        _LOGGER.error("Failed to set up coordinator: %s", err)
        await client.disconnect()
        raise ConfigEntryNotReady(f"Failed to set up coordinator: {err}")

    # Store data
    _LOGGER.info("=== STORING INTEGRATION DATA ===")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "panel_config": panel_config,
    }
    
    _LOGGER.info("Integration data stored, coordinator data keys: %s", 
                list(coordinator.data.keys()) if coordinator.data else "None")

    # Set up platforms
    _LOGGER.info("=== SETTING UP PLATFORMS ===")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.info("All platforms setup complete")

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    _LOGGER.info("=== ARROWHEAD ALARM PANEL SETUP COMPLETE ===")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Arrowhead Alarm Panel entry: %s", entry.entry_id)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up coordinator and client
        if entry.entry_id in hass.data[DOMAIN]:
            data = hass.data[DOMAIN][entry.entry_id]
            
            # Shutdown coordinator
            coordinator = data.get("coordinator")
            if coordinator:
                await coordinator.async_shutdown()
            
            # Disconnect client
            client = data.get("client")
            if client:
                try:
                    await client.disconnect()
                except Exception as err:
                    _LOGGER.error("Error disconnecting client: %s", err)
            
            # Remove from hass data
            hass.data[DOMAIN].pop(entry.entry_id)
    
    _LOGGER.info("Arrowhead Alarm Panel entry unloaded: %s", unload_ok)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading Arrowhead Alarm Panel entry: %s", entry.entry_id)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)