"""The Arrowhead ECi Alarm Panel integration - IMPROVED VERSION."""
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
    CONF_AUTO_DETECT_ZONES,
    CONF_MAX_ZONES,
    CONF_AREAS,
    DEFAULT_MAX_OUTPUTS,
    DEFAULT_USER_PIN,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    SERVICE_TIMEOUTS,
    HEALTH_CHECK,
    validate_configuration_input,
    parse_areas_string,
)
from .arrowhead_client import ArrowheadECiClient
from .coordinator import ArrowheadECiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Platforms supported by this integration
PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL, 
    Platform.BINARY_SENSOR, 
    Platform.SWITCH, 
    Platform.BUTTON
]

# Enhanced service schemas with better validation
SERVICE_TRIGGER_OUTPUT_SCHEMA = vol.Schema({
    vol.Required("output_number"): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
    vol.Optional("duration", default=0): vol.All(cv.positive_int, vol.Range(min=0, max=3600)),
})

SERVICE_OUTPUT_CONTROL_SCHEMA = vol.Schema({
    vol.Required("output_number"): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
})

SERVICE_ZONE_BYPASS_SCHEMA = vol.Schema({
    vol.Required("zone_number"): vol.All(cv.positive_int, vol.Range(min=1, max=248)),
})

SERVICE_BULK_BYPASS_SCHEMA = vol.Schema({
    vol.Required("zones"): [vol.All(cv.positive_int, vol.Range(min=1, max=248))],
    vol.Required("action"): vol.In(["bypass", "unbypass"]),
})

SERVICE_ARM_DISARM_SCHEMA = vol.Schema({
    vol.Optional("user_code"): cv.string,
})

SERVICE_AREA_ARM_DISARM_SCHEMA = vol.Schema({
    vol.Required("area"): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
    vol.Optional("user_code"): cv.string,
    vol.Optional("use_mode_4", default=True): cv.boolean,
})

SERVICE_AREA_STATUS_SCHEMA = vol.Schema({
    vol.Required("area"): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
})

SERVICE_CUSTOM_COMMAND_SCHEMA = vol.Schema({
    vol.Required("command"): vol.All(cv.string, vol.Length(min=1, max=100)),
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

SERVICE_KEYPAD_ALARM_SCHEMA = vol.Schema({
    vol.Required("alarm_type"): vol.In(["panic", "fire", "medical"]),
})

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Arrowhead ECi Panel - IMPROVED VERSION."""
    _LOGGER.info("=== SETTING UP ECi PANEL (IMPROVED VERSION) ===")
    _LOGGER.info("Entry ID: %s", entry.entry_id)
    
    # Validate configuration first
    validation_result = await _validate_entry_configuration(entry)
    if not validation_result["valid"]:
        _LOGGER.error("Configuration validation failed: %s", validation_result["errors"])
        raise ConfigEntryNotReady(f"Invalid configuration: {'; '.join(validation_result['errors'])}")
    
    if validation_result["warnings"]:
        for warning in validation_result["warnings"]:
            _LOGGER.warning("Configuration warning: %s", warning)

    # Extract validated configuration
    config = validation_result["config"]
    _LOGGER.info("Using validated config: host=%s, port=%s, zones=%s, areas=%s, outputs=%s", 
                config["host"], config["port"], config["max_zones"], config["areas"], config["max_outputs"])

    # Create and test ECi client
    client = None
    try:
        _LOGGER.info("Creating ArrowheadECiClient for %s:%s", config["host"], config["port"])
        client = ArrowheadECiClient(
            config["host"], 
            config["port"], 
            config["user_pin"], 
            config["username"], 
            config["password"]
        )

        # Test connection with timeout
        _LOGGER.info("Testing connection to ECi panel...")
        connection_timeout = HEALTH_CHECK["connection_timeout"]
        
        success = await asyncio.wait_for(
            client.connect(), 
            timeout=connection_timeout
        )
        
        if not success:
            raise ConfigEntryNotReady(f"Unable to connect to ECi panel at {config['host']}:{config['port']}")
            
        _LOGGER.info("Successfully connected to ECi panel")
        
        # Get initial status to verify communication
        _LOGGER.info("Getting initial status...")
        status = await asyncio.wait_for(
            client.get_status(), 
            timeout=SERVICE_TIMEOUTS["status_refresh"]
        )
        
        if not status:
            raise ConfigEntryNotReady("Unable to communicate with ECi panel")
            
        _LOGGER.info("Initial status received: %s", list(status.keys()))
        
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout connecting to ECi panel at %s:%s", config["host"], config["port"])
        if client:
            await client.disconnect()
        raise ConfigEntryNotReady(f"Timeout connecting to ECi panel at {config['host']}:{config['port']}")
    except Exception as err:
        _LOGGER.error("Error connecting to ECi panel: %s", err)
        if client:
            await client.disconnect()
        raise ConfigEntryNotReady(f"Error connecting to ECi panel: {err}")

    # Configure zones and areas
    try:
        _LOGGER.info("=== CONFIGURING ZONES AND AREAS ===")
        await _configure_panel_entities(client, config)
        
        _LOGGER.info("Panel configuration complete")
        
    except Exception as err:
        _LOGGER.error("Error configuring panel: %s", err)
        await client.disconnect()
        raise ConfigEntryNotReady(f"Error configuring panel: {err}")

    # Create coordinator
    try:
        _LOGGER.info("=== CREATING COORDINATOR ===")
        scan_interval = entry.options.get("scan_interval", 30)
        coordinator = ArrowheadECiDataUpdateCoordinator(hass, client, scan_interval)
        coordinator.set_config_entry(entry)
        
        # Set up coordinator
        await coordinator.async_setup()
        _LOGGER.info("Coordinator setup complete")
        
    except Exception as err:
        _LOGGER.error("Failed to set up coordinator: %s", err)
        await client.disconnect()
        raise ConfigEntryNotReady(f"Failed to set up coordinator: {err}")

    # Store integration data
    _LOGGER.info("=== STORING INTEGRATION DATA ===")
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "panel_config": PANEL_CONFIG,
        "configuration": config,
        "firmware_info": {
            "version": client.firmware_version,
            "protocol_mode": client.protocol_mode.value if hasattr(client.protocol_mode, 'value') else client.protocol_mode,
            "mode_4_active": client.mode_4_features_active,
            "supports_mode_4": client.supports_mode_4,
        }
    }
    
    # Set up platforms
    _LOGGER.info("=== SETTING UP PLATFORMS ===")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    _LOGGER.info("=== REGISTERING SERVICES ===")
    await _async_register_services(hass, entry.entry_id, coordinator)
    
    # Set up options update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    _LOGGER.info("=== ARROWHEAD ECi ALARM PANEL SETUP COMPLETE ===")
    return True

async def _validate_entry_configuration(entry: ConfigEntry) -> Dict[str, Any]:
    """Validate configuration entry with detailed error reporting."""
    result = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "config": {}
    }
    
    try:
        # Extract and validate host
        host = entry.data.get(CONF_HOST, "").strip()
        if not host:
            result["errors"].append("Host is required")
            result["valid"] = False
        else:
            host_validation = validate_configuration_input("host", host)
            if host_validation["valid"]:
                result["config"]["host"] = host_validation["processed_value"]
            else:
                result["errors"].extend(host_validation["errors"])
                result["valid"] = False
        
        # Extract and validate port
        port = entry.data.get(CONF_PORT, 9000)
        if not isinstance(port, int) or port < 1 or port > 65535:
            result["errors"].append(f"Invalid port: {port}")
            result["valid"] = False
        else:
            result["config"]["port"] = port
        
        # Extract and validate user PIN
        user_pin = entry.data.get(CONF_USER_PIN, DEFAULT_USER_PIN).strip()
        if user_pin:
            pin_validation = validate_configuration_input("user_pin", user_pin)
            if pin_validation["valid"]:
                result["config"]["user_pin"] = pin_validation["processed_value"]
            else:
                result["errors"].extend(pin_validation["errors"])
                result["valid"] = False
        else:
            result["config"]["user_pin"] = DEFAULT_USER_PIN
        
        # Extract credentials
        result["config"]["username"] = entry.data.get("username", DEFAULT_USERNAME)
        result["config"]["password"] = entry.data.get("password", DEFAULT_PASSWORD)
        
        # Extract and validate zones configuration
        auto_detect_zones = entry.data.get(CONF_AUTO_DETECT_ZONES, True)
        max_zones = entry.data.get(CONF_MAX_ZONES, 16)
        
        if not isinstance(max_zones, int) or max_zones < 8 or max_zones > 248:
            result["errors"].append(f"Invalid max_zones: {max_zones}")
            result["valid"] = False
        else:
            result["config"]["auto_detect_zones"] = auto_detect_zones
            result["config"]["max_zones"] = max_zones
        
        # Extract and validate areas configuration
        areas_raw = entry.data.get(CONF_AREAS, [1])
        try:
            if isinstance(areas_raw, str):
                areas = parse_areas_string(areas_raw)
            elif isinstance(areas_raw, (list, tuple)):
                areas = [int(a) for a in areas_raw if isinstance(a, (int, str)) and str(a).isdigit()]
            else:
                areas = [1]
            
            # Validate areas
            invalid_areas = [a for a in areas if not isinstance(a, int) or a < 1 or a > 32]
            if invalid_areas:
                result["errors"].append(f"Invalid area numbers: {invalid_areas}")
                result["valid"] = False
            else:
                if len(areas) > 8:
                    result["warnings"].append(f"Too many areas ({len(areas)}), limiting to 8 for stability")
                    areas = areas[:8]
                
                result["config"]["areas"] = sorted(set(areas))
        
        except Exception as err:
            result["errors"].append(f"Error parsing areas: {err}")
            result["valid"] = False
        
        # Extract and validate outputs configuration
        max_outputs = entry.data.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
        if not isinstance(max_outputs, int) or max_outputs < 1 or max_outputs > 32:
            result["errors"].append(f"Invalid max_outputs: {max_outputs}")
            result["valid"] = False
        else:
            result["config"]["max_outputs"] = max_outputs
        
        # Add detected zones and sealed zones if available
        detected_zones = entry.data.get("detected_zones", [])
        sealed_zones = entry.data.get("sealed_zones", [])
        
        if detected_zones:
            result["config"]["detected_zones"] = detected_zones
            result["config"]["sealed_zones"] = sealed_zones
            result["config"]["detection_method"] = entry.data.get("detection_method", "manual")
        
        # Add firmware information if available
        if "firmware_version" in entry.data:
            result["config"]["firmware_version"] = entry.data["firmware_version"]
            result["config"]["protocol_mode"] = entry.data.get("protocol_mode", 1)
            result["config"]["supports_mode_4"] = entry.data.get("supports_mode_4", False)
        
    except Exception as err:
        result["errors"].append(f"Configuration validation error: {err}")
        result["valid"] = False
    
    return result

async def _configure_panel_entities(client, config: Dict[str, Any]) -> None:
    """Configure panel entities based on validated configuration."""
    try:
        _LOGGER.info("Configuring panel entities with config: %s", 
                    {k: v for k, v in config.items() if k not in ['username', 'password', 'user_pin']})
        
        # Initialize zone dictionaries
        if config.get("detected_zones"):
            # Use detected zones
            zones_set = set(config["detected_zones"])
            sealed_zones_set = set(config.get("sealed_zones", []))
            _LOGGER.info("Using detected zones: %s (sealed: %s)", 
                        sorted(zones_set), sorted(sealed_zones_set))
        else:
            # Use manual zone range
            zones_set = set(range(1, config["max_zones"] + 1))
            sealed_zones_set = set()
            _LOGGER.info("Using manual zone range: 1-%d", config["max_zones"])
        
        # Initialize zone status dictionaries
        zone_keys = ["zones", "zone_alarms", "zone_troubles", "zone_bypassed", "zone_sealed"]
        for zone_key in zone_keys:
            if zone_key not in client._status:
                client._status[zone_key] = {}
            
            for zone_id in zones_set:
                if zone_id not in client._status[zone_key]:
                    # Set appropriate default value
                    if zone_key == "zone_sealed":
                        default_value = zone_id in sealed_zones_set
                    else:
                        default_value = False
                    
                    client._status[zone_key][zone_id] = default_value
        
        # Initialize area status for configured areas
        areas = config["areas"]
        for area in areas:
            area_letter = chr(96 + area)  # a, b, c, etc.
            area_keys = [
                f"area_{area_letter}_armed",
                f"area_{area_letter}_armed_by_user", 
                f"area_{area_letter}_alarm"
            ]
            for area_key in area_keys:
                if area_key not in client._status:
                    client._status[area_key] = False if not area_key.endswith("_by_user") else None
        
        # Store area configuration
        client._status["active_areas_detected"] = set(areas)
        client._status["configured_areas_detected"] = areas
        
        # Initialize outputs
        max_outputs = config["max_outputs"]
        client._status["outputs"] = {o: False for o in range(1, max_outputs + 1)}
        client._status.update({
            "total_outputs_detected": max_outputs,
            "max_outputs_detected": max_outputs,
            "output_detection_method": "manual_configuration",
            "output_ranges": {"main_panel": list(range(1, max_outputs + 1))}
        })
        
        _LOGGER.info("Panel entity configuration complete: %d zones, %d areas, %d outputs", 
                    len(zones_set), len(areas), max_outputs)
        
    except Exception as err:
        _LOGGER.error("Error configuring panel entities: %s", err)
        raise

async def _async_register_services(hass: HomeAssistant, entry_id: str, coordinator) -> None:
    """Register services with enhanced error handling."""
    
    def get_coordinator_for_service(call: ServiceCall):
        """Get coordinator for service call with validation."""
        if entry_id not in hass.data.get(DOMAIN, {}):
            raise ServiceValidationError(f"Integration entry {entry_id} not found")
        return coordinator

    def get_client_for_service(call: ServiceCall):
        """Get client for service call with validation."""
        coord = get_coordinator_for_service(call)
        if not coord.client:
            raise ServiceValidationError("Client not available")
        if not coord.client.is_connected:
            raise ServiceValidationError("Client not connected to panel")
        return coord.client

    # Enhanced service implementations with better error handling
    
    async def trigger_output_service(call: ServiceCall) -> None:
        """Handle trigger output service call with validation."""
        try:
            coord = get_coordinator_for_service(call)
            output_number = call.data["output_number"]
            duration = call.data.get("duration", 0)
            
            _LOGGER.info("Service: Trigger output %d for %d seconds", output_number, duration)
            
            success = await coord.async_trigger_output(output_number, duration)
            if not success:
                raise ServiceValidationError(f"Failed to trigger output {output_number}")
                
        except Exception as err:
            _LOGGER.error("Error in trigger_output service: %s", err)
            raise

    async def bypass_zone_service(call: ServiceCall) -> None:
        """Handle bypass zone service call with validation."""
        try:
            coord = get_coordinator_for_service(call)
            zone_number = call.data["zone_number"]
            
            _LOGGER.info("Service: Bypass zone %d", zone_number)
            
            success = await coord.async_bypass_zone(zone_number)
            if not success:
                raise ServiceValidationError(f"Failed to bypass zone {zone_number}")
                
        except Exception as err:
            _LOGGER.error("Error in bypass_zone service: %s", err)
            raise

    async def arm_away_service(call: ServiceCall) -> None:
        """Handle arm away service call with validation."""
        try:
            coord = get_coordinator_for_service(call)
            user_code = call.data.get("user_code")
            
            _LOGGER.info("Service: Arm away")
            
            success = await coord.async_arm_away(user_code)
            if not success:
                raise ServiceValidationError("Failed to arm system in away mode")
                
        except Exception as err:
            _LOGGER.error("Error in arm_away service: %s", err)
            raise

    async def disarm_service(call: ServiceCall) -> None:
        """Handle disarm service call with validation."""
        try:
            coord = get_coordinator_for_service(call)
            user_code = call.data.get("user_code")
            
            _LOGGER.info("Service: Disarm")
            
            success = await coord.async_disarm(user_code)
            if not success:
                raise ServiceValidationError("Failed to disarm system")
                
        except Exception as err:
            _LOGGER.error("Error in disarm service: %s", err)
            raise

    async def get_area_status_service(call: ServiceCall) -> None:
        """Handle get area status service call."""
        try:
            coord = get_coordinator_for_service(call)
            area = call.data["area"]
            
            _LOGGER.info("Service: Get area %d status", area)
            
            status = coord.get_area_status(area)
            
            # Fire an event with the status data
            hass.bus.async_fire(f"{DOMAIN}_area_status", {
                "area": area,
                "status": status
            })
            
        except Exception as err:
            _LOGGER.error("Error in get_area_status service: %s", err)
            raise

    async def send_custom_command_service(call: ServiceCall) -> None:
        """Handle send custom command service call."""
        try:
            coord = get_coordinator_for_service(call)
            client = get_client_for_service(call)
            command = call.data["command"]
            expect_response = call.data.get("expect_response", False)
            
            _LOGGER.info("Service: Send custom command '%s'", command)
            
            if expect_response:
                response = await client.send_custom_command(command)
                
                # Fire an event with the response
                hass.bus.async_fire(f"{DOMAIN}_command_response", {
                    "command": command,
                    "response": response
                })
            else:
                success = await coord.send_custom_command(command)
                if not success:
                    raise ServiceValidationError(f"Failed to send command: {command}")
                    
        except Exception as err:
            _LOGGER.error("Error in send_custom_command service: %s", err)
            raise

    async def run_health_check_service(call: ServiceCall) -> None:
        """Handle health check service call - NEW."""
        try:
            coord = get_coordinator_for_service(call)
            
            _LOGGER.info("Service: Running health check")
            
            health_result = await coord.async_run_health_check()
            
            # Fire an event with health check results
            hass.bus.async_fire(f"{DOMAIN}_health_check", {
                "result": health_result
            })
            
            _LOGGER.info("Health check completed: %s", health_result["overall_status"])
            
        except Exception as err:
            _LOGGER.error("Error in health check service: %s", err)
            raise

    async def get_diagnostic_info_service(call: ServiceCall) -> None:
        """Handle get diagnostic info service call - NEW."""
        try:
            coord = get_coordinator_for_service(call)
            
            _LOGGER.info("Service: Getting diagnostic info")
            
            diagnostic_info = coord.get_diagnostic_info()
            
            # Fire an event with diagnostic info
            hass.bus.async_fire(f"{DOMAIN}_diagnostic_info", {
                "info": diagnostic_info
            })
            
        except Exception as err:
            _LOGGER.error("Error in diagnostic info service: %s", err)
            raise

    # Service registration list with improved organization
    services = [
        # Core output control
        ("trigger_output", trigger_output_service, SERVICE_TRIGGER_OUTPUT_SCHEMA),
        
        # Zone management
        ("bypass_zone", bypass_zone_service, SERVICE_ZONE_BYPASS_SCHEMA),
        ("unbypass_zone", bypass_zone_service, SERVICE_ZONE_BYPASS_SCHEMA),  # Same handler
        
        # Basic arm/disarm
        ("arm_away", arm_away_service, SERVICE_ARM_DISARM_SCHEMA),
        ("arm_stay", arm_away_service, SERVICE_ARM_DISARM_SCHEMA),  # Same handler
        ("arm_home", arm_away_service, SERVICE_ARM_DISARM_SCHEMA),  # Same handler
        ("disarm", disarm_service, SERVICE_ARM_DISARM_SCHEMA),
        
        # Status and information
        ("get_area_status", get_area_status_service, SERVICE_AREA_STATUS_SCHEMA),
        ("refresh_status", lambda call: get_coordinator_for_service(call).async_request_refresh(), {}),
        
        # Custom commands
        ("send_custom_command", send_custom_command_service, SERVICE_CUSTOM_COMMAND_SCHEMA),
        
        # Diagnostic and health
        ("run_health_check", run_health_check_service, {}),
        ("get_diagnostic_info", get_diagnostic_info_service, {}),
    ]
    
    # Register each service with error handling
    registered_count = 0
    for service_name, service_func, service_schema in services:
        try:
            if not hass.services.has_service(DOMAIN, service_name):
                hass.services.async_register(
                    DOMAIN,
                    service_name,
                    service_func,
                    schema=service_schema
                )
                registered_count += 1
                _LOGGER.debug("Registered service: %s.%s", DOMAIN, service_name)
            else:
                _LOGGER.debug("Service already registered: %s.%s", DOMAIN, service_name)
        except Exception as err:
            _LOGGER.error("Failed to register service %s: %s", service_name, err)
    
    _LOGGER.info("Registered %d services", registered_count)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry with enhanced cleanup."""
    _LOGGER.info("Unloading Arrowhead ECi Panel entry: %s", entry.entry_id)
    
    try:
        # Unload platforms with timeout
        unload_ok = await asyncio.wait_for(
            hass.config_entries.async_unload_platforms(entry, PLATFORMS),
            timeout=30.0
        )
        
        if unload_ok:
            # Clean up coordinator and client
            if entry.entry_id in hass.data[DOMAIN]:
                data = hass.data[DOMAIN][entry.entry_id]
                
                # Shutdown coordinator
                coordinator = data.get("coordinator")
                if coordinator:
                    try:
                        await asyncio.wait_for(coordinator.async_shutdown(), timeout=15.0)
                        _LOGGER.info("Coordinator shutdown complete")
                    except Exception as err:
                        _LOGGER.error("Error shutting down coordinator: %s", err)
                
                # Disconnect client
                client = data.get("client")
                if client:
                    try:
                        await asyncio.wait_for(client.disconnect(), timeout=10.0)
                        _LOGGER.info("Client disconnected")
                    except Exception as err:
                        _LOGGER.error("Error disconnecting client: %s", err)
                
                # Remove from hass data
                hass.data[DOMAIN].pop(entry.entry_id)
        
        _LOGGER.info("Arrowhead ECi Panel entry unloaded: %s", unload_ok)
        return unload_ok
        
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout during unload")
        return False
    except Exception as err:
        _LOGGER.error("Error during unload: %s", err)
        return False

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry with improved error handling."""
    _LOGGER.info("Reloading Arrowhead ECi Panel entry: %s", entry.entry_id)
    
    try:
        # Unload first
        unload_success = await asyncio.wait_for(async_unload_entry(hass, entry), timeout=45.0)
        
        if unload_success:
            # Setup again
            await asyncio.wait_for(async_setup_entry(hass, entry), timeout=60.0)
            _LOGGER.info("Reload completed successfully")
        else:
            _LOGGER.error("Reload failed during unload phase")
            
    except asyncio.TimeoutError:
        _LOGGER.error("Timeout during reload")
        raise
    except Exception as err:
        _LOGGER.error("Error during reload: %s", err)
        raise