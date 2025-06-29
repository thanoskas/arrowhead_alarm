"""The Arrowhead ECi Alarm Panel integration with MODE 4 support."""
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
    PANEL_CONFIG,
    CONF_MAX_OUTPUTS,
    DEFAULT_MAX_OUTPUTS,
    DEFAULT_USER_PIN,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    ProtocolMode,
)
from .arrowhead_eci_client import ArrowheadECiClient
from .coordinator import ArrowheadECiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SWITCH, Platform.BUTTON]

# Enhanced service schemas for ECi with MODE 4 support
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
    vol.Required("area"): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
    vol.Optional("user_code"): cv.string,
    vol.Optional("use_mode_4", default=True): cv.boolean,  # Use MODE 4 commands if available
})

SERVICE_AREA_STATUS_SCHEMA = vol.Schema({
    vol.Required("area"): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
})

SERVICE_CUSTOM_COMMAND_SCHEMA = vol.Schema({
    vol.Required("command"): cv.string,
    vol.Optional("expect_response", default=False): cv.boolean,
})

SERVICE_BULK_AREAS_SCHEMA = vol.Schema({
    vol.Required("areas"): [vol.All(cv.positive_int, vol.Range(min=1, max=32))],
    vol.Optional("user_code"): cv.string,
    vol.Optional("delay", default=1): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=10)),
})

SERVICE_BULK_ARM_AREAS_SCHEMA = vol.Schema({
    vol.Required("areas"): [vol.All(cv.positive_int, vol.Range(min=1, max=32))],
    vol.Required("mode"): vol.In(["away", "stay", "home"]),
    vol.Optional("user_code"): cv.string,
    vol.Optional("delay", default=1): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=10)),
    vol.Optional("use_mode_4", default=True): cv.boolean,
})

SERVICE_EMERGENCY_DISARM_SCHEMA = vol.Schema({
    vol.Required("master_code"): cv.string,
})

# MODE 4 specific service schemas
SERVICE_KEYPAD_ALARM_SCHEMA = vol.Schema({
    vol.Required("alarm_type"): vol.In(["panic", "fire", "medical"]),
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Arrowhead ECi Panel from a config entry."""
    _LOGGER.info("=== SETTING UP ARROWHEAD ECi ALARM PANEL ===")
    _LOGGER.info("Entry ID: %s", entry.entry_id)
    _LOGGER.info("Entry data: %s", {k: v for k, v in entry.data.items() if k not in ['username', 'password', 'user_pin']})

    # Get configuration
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, 9000)
    user_pin = entry.data.get(CONF_USER_PIN, DEFAULT_USER_PIN)
    username = entry.data.get("username", DEFAULT_USERNAME)
    password = entry.data.get("password", DEFAULT_PASSWORD)
    
    _LOGGER.info("ECi Panel Configuration: %s", PANEL_CONFIG)

    # Create ECi client
    _LOGGER.info("Creating ArrowheadECiClient for %s:%s", host, port)
    client = ArrowheadECiClient(host, port, user_pin, username, password)

    # Test connection
    _LOGGER.info("Testing connection to ECi panel...")
    try:
        success = await asyncio.wait_for(client.connect(), timeout=30.0)
        if not success:
            _LOGGER.error("Failed to connect to ECi panel at %s:%s", host, port)
            raise ConfigEntryNotReady(f"Unable to connect to ECi panel at {host}:{port}")
            
        _LOGGER.info("Successfully connected to ECi panel")
        
        # Log firmware and protocol information
        firmware_version = client.firmware_version or "Unknown"
        protocol_mode = client.protocol_mode.value
        mode_4_active = client.mode_4_features_active
        
        _LOGGER.info("ECi Panel Info - Firmware: %s, Protocol Mode: %d, MODE 4 Active: %s", 
                    firmware_version, protocol_mode, mode_4_active)
        
        # Get initial status to verify communication
        _LOGGER.info("Getting initial status...")
        status = await asyncio.wait_for(client.get_status(), timeout=10.0)
        if not status:
            _LOGGER.error("Failed to get status from ECi panel")
            await client.disconnect()
            raise ConfigEntryNotReady("Unable to communicate with ECi panel")
            
        _LOGGER.info("Initial status received, status keys: %s", list(status.keys()))
        
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout connecting to ECi panel at %s:%s", host, port)
        raise ConfigEntryNotReady(f"Timeout connecting to ECi panel at {host}:{port}")
    except Exception as err:
        _LOGGER.error("Error connecting to ECi panel: %s", err)
        await client.disconnect()
        raise ConfigEntryNotReady(f"Error connecting to ECi panel: {err}")

    # Configure outputs manually before setting up coordinator
    max_outputs = entry.data.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
    _LOGGER.info("=== CONFIGURING OUTPUTS ===")
    _LOGGER.info("Configuring %d outputs before coordinator setup", max_outputs)
    
    try:
        client.configure_manual_outputs(max_outputs)
        _LOGGER.info("Manual output configuration complete: %d outputs", max_outputs)
    except Exception as err:
        _LOGGER.error("Error configuring manual outputs: %s", err)
        # Continue anyway with empty outputs
        client._status["outputs"] = {}

    # Create coordinator
    _LOGGER.info("=== CREATING COORDINATOR ===")
    scan_interval = entry.options.get("scan_interval", 30)
    coordinator = ArrowheadECiDataUpdateCoordinator(hass, client, scan_interval)
    
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
        "panel_config": PANEL_CONFIG,
        "firmware_info": {
            "version": client.firmware_version,
            "protocol_mode": client.protocol_mode.value,
            "mode_4_active": client.mode_4_features_active,
            "supports_mode_4": client.supports_mode_4,
        }
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
    
    _LOGGER.info("=== ARROWHEAD ECi ALARM PANEL SETUP COMPLETE ===")
    return True

async def _async_register_services(hass: HomeAssistant, entry_id: str, coordinator) -> None:
    """Register services for the Arrowhead ECi Panel with MODE 4 support."""
    
    def get_coordinator_for_service(call: ServiceCall):
        """Get coordinator for service call."""
        return coordinator

    def get_client_for_service(call: ServiceCall):
        """Get client for service call."""
        return coordinator.client

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
        client = get_client_for_service(call)
        coord = get_coordinator_for_service(call)
        output_number = call.data["output_number"]
        
        success = await client.turn_output_on(output_number)
        if not success:
            raise ServiceValidationError(f"Failed to turn on output {output_number}")
        await coord.async_request_refresh()

    async def turn_output_off_service(call: ServiceCall) -> None:
        """Handle turn output off service call."""
        client = get_client_for_service(call)
        coord = get_coordinator_for_service(call)
        output_number = call.data["output_number"]
        
        success = await client.turn_output_off(output_number)
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

    # ===== ENHANCED AREA-SPECIFIC ARM/DISARM SERVICES =====
    
    async def arm_away_area_service(call: ServiceCall) -> None:
        """Handle arm away area service call with MODE 4 support."""
        coord = get_coordinator_for_service(call)
        client = get_client_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        use_mode_4 = call.data.get("use_mode_4", True)
        
        # Try MODE 4 enhanced command first if available and requested
        if use_mode_4 and client.mode_4_features_active:
            success = await client.arm_away_area_mode4(area)
        else:
            success = await coord.async_arm_away_area(area, user_code)
        
        if not success:
            raise ServiceValidationError(f"Failed to arm area {area} in away mode")

    async def arm_stay_area_service(call: ServiceCall) -> None:
        """Handle arm stay area service call with MODE 4 support."""
        coord = get_coordinator_for_service(call)
        client = get_client_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        use_mode_4 = call.data.get("use_mode_4", True)
        
        # Try MODE 4 enhanced command first if available and requested
        if use_mode_4 and client.mode_4_features_active:
            success = await client.arm_stay_area_mode4(area)
        else:
            success = await coord.async_arm_stay_area(area, user_code)
        
        if not success:
            raise ServiceValidationError(f"Failed to arm area {area} in stay mode")

    async def arm_home_area_service(call: ServiceCall) -> None:
        """Handle arm home area service call (alias for stay)."""
        coord = get_coordinator_for_service(call)
        client = get_client_for_service(call)
        area = call.data["area"]
        user_code = call.data.get("user_code")
        use_mode_4 = call.data.get("use_mode_4", True)
        
        # Try MODE 4 enhanced command first if available and requested
        if use_mode_4 and client.mode_4_features_active:
            success = await client.arm_stay_area_mode4(area)
        else:
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

    # ===== MODE 4 KEYPAD ALARM SERVICES =====
    
    async def trigger_keypad_alarm_service(call: ServiceCall) -> None:
        """Handle keypad alarm service call (MODE 4 only)."""
        client = get_client_for_service(call)
        alarm_type = call.data["alarm_type"]
        
        if not client.mode_4_features_active:
            raise ServiceValidationError("Keypad alarms require MODE 4 (firmware 10.3.50+)")
        
        if alarm_type == "panic":
            success = await client.trigger_keypad_panic_alarm()
        elif alarm_type == "fire":
            success = await client.trigger_keypad_fire_alarm()
        elif alarm_type == "medical":
            success = await client.trigger_keypad_medical_alarm()
        else:
            raise ServiceValidationError(f"Invalid alarm type: {alarm_type}")
        
        if not success:
            raise ServiceValidationError(f"Failed to trigger {alarm_type} alarm")

    # ===== STATUS SERVICES =====
    
    async def get_area_status_service(call: ServiceCall) -> None:
        """Handle get area status service call."""
        coord = get_coordinator_for_service(call)
        area = call.data["area"]
        
        status = coord.get_area_status(area)
        _LOGGER.info("Area %d status: %s", area, status)
        
        # Fire an event with the status data
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
        client = get_client_for_service(call)
        command = call.data["command"]
        expect_response = call.data.get("expect_response", False)
        
        if expect_response:
            response = await client.send_custom_command(command)
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
        client = get_client_for_service(call)
        areas = call.data["areas"]
        mode = call.data["mode"]
        user_code = call.data.get("user_code")
        delay = call.data.get("delay", 1)
        use_mode_4 = call.data.get("use_mode_4", True)
        
        success_count = 0
        for area in areas:
            try:
                if mode == "away":
                    if use_mode_4 and client.mode_4_features_active:
                        success = await client.arm_away_area_mode4(area)
                    else:
                        success = await coord.async_arm_away_area(area, user_code)
                elif mode in ["stay", "home"]:
                    if use_mode_4 and client.mode_4_features_active:
                        success = await client.arm_stay_area_mode4(area)
                    else:
                        success = await coord.async_arm_stay_area(area, user_code)
                else:
                    raise ServiceValidationError(f"Invalid arm mode: {mode}")
                
                if success:
                    success_count += 1
                await asyncio.sleep(delay)  # Delay between commands
                
            except Exception as err:
                _LOGGER.error("Error arming area %d: %s", area, err)
        
        if success_count != len(areas):
            raise ServiceValidationError(f"Only {success_count}/{len(areas)} areas armed successfully")

    async def bulk_disarm_areas_service(call: ServiceCall) -> None:
        """Handle bulk disarm areas service call."""
        coord = get_coordinator_for_service(call)
        areas = call.data["areas"]
        user_code = call.data.get("user_code")
        delay = call.data.get("delay", 1)
        
        success_count = 0
        for area in areas:
            try:
                success = await coord.async_disarm_area(area, user_code)
                if success:
                    success_count += 1
                await asyncio.sleep(delay)  # Delay between commands
            except Exception as err:
                _LOGGER.error("Error disarming area %d: %s", area, err)
        
        if success_count != len(areas):
            raise ServiceValidationError(f"Only {success_count}/{len(areas)} areas disarmed successfully")

    # ===== SYSTEM CONTROL SERVICES =====
    
    async def panel_reset_service(call: ServiceCall) -> None:
        """Handle panel reset service call."""
        coord = get_coordinator_for_service(call)
        success = await coord.send_custom_command("REBOOT")
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
        
        # Enhanced area-specific arm/disarm services
        ("arm_away_area", arm_away_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        ("arm_stay_area", arm_stay_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        ("arm_home_area", arm_home_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        ("disarm_area", disarm_area_service, SERVICE_AREA_ARM_DISARM_SCHEMA),
        
        # MODE 4 keypad alarm services
        ("trigger_keypad_alarm", trigger_keypad_alarm_service, SERVICE_KEYPAD_ALARM_SCHEMA),
        
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
    _LOGGER.info("Unloading Arrowhead ECi Panel entry: %s", entry.entry_id)
    
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
    
    _LOGGER.info("Arrowhead ECi Panel entry unloaded: %s", unload_ok)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    _LOGGER.info("Reloading Arrowhead ECi Panel entry: %s", entry.entry_id)
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)