"""The Arrowhead Alarm Panel integration with enhanced service support."""
import asyncio
import logging
from typing import Dict, Any, List

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

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

# Service schemas
SERVICE_TRIGGER_OUTPUT_SCHEMA = vol.Schema({
    vol.Required("output_number"): cv.positive_int,
    vol.Optional("duration", default=0): cv.positive_int,
})

SERVICE_OUTPUT_CONTROL_SCHEMA = vol.Schema({
    vol.Required("output_number"): cv.positive_int,
})

SERVICE_ZONE_BYPASS_SCHEMA = vol.Schema({
    vol.Required("zone_number"): cv.positive_int,
})

SERVICE_BULK_BYPASS_SCHEMA = vol.Schema({
    vol.Required("zones"): [cv.positive_int],
    vol.Required("action"): vol.In(["bypass", "unbypass"]),
})

SERVICE_ARM_DISARM_SCHEMA = vol.Schema({
    vol.Optional("user_code"): cv.string,
})

SERVICE_AREA_ARM_DISARM_SCHEMA = vol.Schema({
    vol.Required("area"): vol.All(cv.positive_int, vol.Range(min=1, max=8)),
    vol.Optional("user_code"): cv.string,
})

SERVICE_AREA_STATUS_SCHEMA = vol.Schema({
    vol.Required("area"): vol.All(cv.positive_int, vol.Range(min=1, max=8)),
})

SERVICE_CUSTOM_COMMAND_SCHEMA = vol.Schema({
    vol.Required("command"): cv.string,
    vol.Optional("expect_response", default=False): cv.boolean,
})

SERVICE_BULK_AREAS_SCHEMA = vol.Schema({
    vol.Required("areas"): [vol.All(cv.positive_int, vol.Range(min=1, max=8))],
    vol.Optional("user_code"): cv.string,
})

SERVICE_BULK_ARM_AREAS_SCHEMA = vol.Schema({
    vol.Required("areas"): [vol.All(cv.positive_int, vol.Range(min=1, max=8))],
    vol.Required("mode"): vol.In(["away", "stay", "home"]),
    vol.Optional("user_code"): cv.string,
})

SERVICE_EMERGENCY_DISARM_SCHEMA = vol.Schema({
    vol.Required("master_code"): cv.string,
})

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

    # Register services
    _LOGGER.info("=== REGISTERING SERVICES ===")
    await _async_register_services(hass, entry.entry_id, coordinator)
    _LOGGER.info("Services registered")

    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    _LOGGER.info("=== ARROWHEAD ALARM PANEL SETUP COMPLETE ===")
    return True

async def _async_register_services(hass: HomeAssistant, entry_id: str, coordinator: ArrowheadDataUpdateCoordinator) -> None:
    """Register services for the Arrowhead Alarm Panel."""
    
    def get_coordinator_for_service(call: ServiceCall) -> ArrowheadDataUpdateCoordinator:
        """Get coordinator for service call."""
        # For now, use the provided coordinator
        # In the future, could support multiple panels by entry_id
        return coordinator

    # ===== OUTPUT CONTROL SERVICES =====
    
    async def trigger_output_service(call: ServiceCall) -> None:
        """Handle trigger output service call."""
        coord = get_coordinator_for_service(call)
        output_number = call.data["output_number"]
        duration = call.data.get("duration", 0)
        
        success = await coord.async_trigger_output(output_number, duration)
        if not success:
            raise ServiceValidationError(f"Failed to trigger output {output_number}")

    async def turn_output_on_service(call: ServiceCall) -> None:
        """Handle turn output on service call."""
        coord = get_coordinator_for_service(call)
        output_number = call.data["output_number"]
        
        success = await coord.client.turn_output_on(output_number)
        if not success:
            raise ServiceValidationError(f"Failed to turn on output {output_number}")
        await coord.async_request_refresh()

    async def turn_output_off_service(call: ServiceCall) -> None:
        """Handle turn output off service call."""
        coord = get_coordinator_for_service(call)
        output_number = call.data["output_number"]
        
        success = await coord.client.turn_output_off(output_number)
        if not success:
            raise ServiceValidationError(f"Failed to turn off output {output_number}")
        await coord.async_request_refresh()

    # ===== ZONE BYPASS SERVICES =====
    
    async def bypass_zone_service(call: ServiceCall) -> None:
        """Handle bypass zone service call."""
        coord = get_coordinator_for_service(call)
        zone_number = call.data["zone_number"]
        
        success = await coord.async_bypass_zone(zone_number)
        if not success:
            raise ServiceValidationError(f"Failed to bypass zone {zone_number}")

    async def unbypass_zone_service(call: ServiceCall) -> None:
        """Handle unbypass zone service call."""
        coord = get_coordinator_for_service(call)
        zone_number = call.data["zone_number"]
        
        success = await coord.async_unbypass_zone(zone_number)
        if not success:
            raise ServiceValidationError(f"Failed to unbypass zone {zone_number}")

    async def bulk_bypass_service(call: ServiceCall) -> None:
        """Handle bulk bypass service call."""
        coord = get_coordinator_for_service(call)
        zones = call.data["zones"]
        action = call.data["action"]
        bypass = action == "bypass"
        
        success = await coord.async_bulk_bypass_zones(zones, bypass)
        if not success:
            raise ServiceValidationError(f"Failed to {action} zones {zones}")

    # ===== GENERAL ARM/DISARM SERVICES =====
    
    async def arm_away_service(call: ServiceCall) -> None:
        """Handle arm away service call."""
        coord = get_coordinator_for_service(call)
        user_code = call.data.get("user_code")
        
        success = await coord.async_arm_away(user_code)
        if not success:
            raise ServiceValidationError("Failed to arm system in away mode")

    async def arm_stay_service(call: ServiceCall) -> None:
        """Handle arm stay service call."""
        coord = get_coordinator_for_service(call)
        user_code = call.data.get("user_code")
        
        success = await coord.async_arm_stay(user_code)
        if not success:
            raise ServiceValidationError("Failed to arm system in stay mode")

    async def arm_home_service(call: ServiceCall) -> None:
        """Handle arm home service call (alias for stay)."""
        coord = get_coordinator_for_service(call)
        user_code = call.data.get("user_code")
        
        success = await coord.async_arm_stay(user_code)
        if not success:
            raise ServiceValidationError("Failed to arm system in home mode")

    async def disarm_service(call: ServiceCall) -> None:
        """Handle disarm service call."""
        coord = get_coordinator_for_service(call)
        user_code = call.data.get("user_code")
        
        success = await coord.async_disarm(user_code)
        if not success:
            raise ServiceValidationError("Failed to disarm system")

    # ===== AREA-SPECIFIC ARM/DISARM SERVICES =====
    
    async def arm_away_area_service(call: ServiceCall) -> None:
        """Handle arm away area service call."""
        coord = get_coordinator_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        
        success = await coord.async_arm_away_area(area, user_code)
        if not success:
            raise ServiceValidationError(f"Failed to arm area {area} in away mode")

    async def arm_stay_area_service(call: ServiceCall) -> None:
        """Handle arm stay area service call."""
        coord = get_coordinator_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        
        success = await coord.async_arm_stay_area(area, user_code)
        if not success:
            raise ServiceValidationError(f"Failed to arm area {area} in stay mode")

    async def arm_home_area_service(call: ServiceCall) -> None:
        """Handle arm home area service call (alias for stay)."""
        coord = get_coordinator_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        
        success = await coord.async_arm_stay_area(area, user_code)
        if not success:
            raise ServiceValidationError(f"Failed to arm area {area} in home mode")

    async def disarm_area_service(call: ServiceCall) -> None:
        """Handle disarm area service call."""
        coord = get_coordinator_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        
        success = await coord.async_disarm_area(area, user_code)
        if not success:
            raise ServiceValidationError(f"Failed to disarm area {area}")

    # ===== STATUS SERVICES =====
    
    async def get_area_status_service(call: ServiceCall) -> None:
        """Handle get area status service call."""
        coord = get_coordinator_for_service(call)
        area = call.data["area"]
        
        status = coord.get_area_status(area)
        _LOGGER.info("Area %d status: %s", area, status)
        
        # Could fire an event with the status data
        hass.bus.async_fire(f"{DOMAIN}_area_status", {
            "area": area,
            "status": status
        })

    async def get_all_areas_status_service(call: ServiceCall) -> None:
        """Handle get all areas status service call."""
        coord = get_coordinator_for_service(call)
        
        status = coord.get_all_areas_status()
        _LOGGER.info("All areas status: %s", status)
        
        # Fire an event with all areas status
        hass.bus.async_fire(f"{DOMAIN}_all_areas_status", {
            "areas_status": status
        })

    async def refresh_status_service(call: ServiceCall) -> None:
        """Handle refresh status service call."""
        coord = get_coordinator_for_service(call)
        await coord.async_request_refresh()

    # ===== CUSTOM COMMAND SERVICES =====
    
    async def send_custom_command_service(call: ServiceCall) -> None:
        """Handle send custom command service call."""
        coord = get_coordinator_for_service(call)
        command = call.data["command"]
        expect_response = call.data.get("expect_response", False)
        
        if expect_response:
            response = await coord.client.send_custom_command(command)
            _LOGGER.info("Custom command '%s' response: %r", command, response)
            
            # Fire an event with the response
            hass.bus.async_fire(f"{DOMAIN}_command_response", {
                "command": command,
                "response": response
            })
        else:
            success = await coord.send_custom_command(command)
            if not success:
                raise ServiceValidationError(f"Failed to send command: {command}")

    # ===== BULK OPERATIONS SERVICES =====
    
    async def bulk_arm_areas_service(call: ServiceCall) -> None:
        """Handle bulk arm areas service call."""
        coord = get_coordinator_for_service(call)
        areas = call.data["areas"]
        mode = call.data["mode"]
        user_code = call.data.get("user_code")
        
        success_count = 0
        for area in areas:
            if mode in ["away"]:
                success = await coord.async_arm_away_area(area, user_code)
            elif mode in ["stay", "home"]:
                success = await coord.async_arm_stay_area(area, user_code)
            else:
                raise ServiceValidationError(f"Invalid arm mode: {mode}")
            
            if success:
                success_count += 1
            await asyncio.sleep(1)  # Delay between commands
        
        if success_count != len(areas):
            raise ServiceValidationError(f"Only {success_count}/{len(areas)} areas armed successfully")

    async def bulk_disarm_areas_service(call: ServiceCall) -> None:
        """Handle bulk disarm areas service call."""
        coord = get_coordinator_for_service(call)
        areas = call.data["areas"]
        user_code = call.data.get("user_code")
        
        success_count = 0
        for area in areas:
            success = await coord.async_disarm_area(area, user_code)
            if success:
                success_count += 1
            await asyncio.sleep(1)  # Delay between commands
        
        if success_count != len(areas):
            raise ServiceValidationError(f"Only {success_count}/{len(areas)} areas disarmed successfully")

    # ===== SYSTEM CONTROL SERVICES =====
    
    async def panel_reset_service(call: ServiceCall) -> None:
        """Handle panel reset service call."""
        coord = get_coordinator_for_service(call)
        success = await coord.send_custom_command("RESET")
        if not success:
            raise ServiceValidationError("Failed to reset panel")

    async def panel_test_service(call: ServiceCall) -> None:
        """Handle panel test service call."""
        coord = get_coordinator_for_service(call)
        success = await coord.send_custom_command("TEST")
        if not success:
            raise ServiceValidationError("Failed to initiate panel test")

    async def emergency_disarm_service(call: ServiceCall) -> None:
        """Handle emergency disarm service call."""
        coord = get_coordinator_for_service(call)
        master_code = call.data["master_code"]
        
        # Try emergency disarm command
        success = await coord.send_custom_command(f"DISARM {master_code}")
        if not success:
            raise ServiceValidationError("Emergency disarm failed")

    # Register all services
    services = [
        # Output control services
        ("trigger_output", trigger_output_service, SERVICE_TRIGGER_OUTPUT_SCHEMA),
        ("turn_output_on", turn_output_on_service, SERVICE_OUTPUT_CONTROL_SCHEMA),
        ("turn_output_off", turn_output_off_service, SERVICE_OUTPUT_CONTROL_SCHEMA),
        
        # Zone bypass services
        ("bypass_zone", bypass_zone_service, SERVICE_ZONE_BYPASS_SCHEMA),
        ("unbypass_zone", unbypass_zone_service, SERVICE_ZONE_BYPASS_SCHEMA),
        ("bulk_bypass", bulk_bypass_service, SERVICE_BULK_BYPASS_SCHEMA),
        
        # General arm/disarm services
        ("arm_away", arm_away_service, SERVICE_ARM_DISARM_SCHEMA),
        ("arm_stay", arm_stay_service, SERVICE_ARM_DISARM_SCHEMA),
        ("arm_home", arm_home_service, SERVICE_ARM_DISARM_SCHEMA),
        ("disarm", disarm_service, SERVICE_ARM_DISARM_SCHEMA),
        
        # Area-specific arm/disarm services
        ("arm_away_area", arm_away_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        ("arm_stay_area", arm_stay_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        ("arm_home_area", arm_home_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        ("disarm_area", disarm_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        
        # Status services
        ("get_area_status", get_area_status_service, SERVICE_AREA_STATUS_SCHEMA),
        ("get_all_areas_status", get_all_areas_status_service, {}),
        ("refresh_status", refresh_status_service, {}),
        
        # Custom command services
        ("send_custom_command", send_custom_command_service, SERVICE_CUSTOM_COMMAND_SCHEMA),
        
        # Bulk operations services
        ("bulk_arm_areas", bulk_arm_areas_service, SERVICE_BULK_ARM_AREAS_SCHEMA),
        ("bulk_disarm_areas", bulk_disarm_areas_service, SERVICE_BULK_AREAS_SCHEMA),
        
        # System control services
        ("panel_reset", panel_reset_service, {}),
        ("panel_test", panel_test_service, {}),
        ("emergency_disarm", emergency_disarm_service, SERVICE_EMERGENCY_DISARM_SCHEMA),
    ]
    
    # Register each service
    for service_name, service_func, service_schema in services:
        if not hass.services.has_service(DOMAIN, service_name):
            hass.services.async_register(
                DOMAIN,
                service_name,
                service_func,
                schema=service_schema
            )
            _LOGGER.debug("Registered service: %s.%s", DOMAIN, service_name)
        else:
            _LOGGER.debug("Service already registered: %s.%s", DOMAIN, service_name)


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
    
    # Note: We don't unregister services here as they might be used by other instances
    # Services will be cleaned up when Home Assistant shuts down
    
    _LOGGER.info("Arrowhead Alarm Panel entry unloaded: %s", unload_ok)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading Arrowhead Alarm Panel entry: %s", entry.entry_id)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)