"""Enhanced config flow for Arrowhead Alarm Panel integration with zone detection."""
import asyncio
import logging
import voluptuous as vol
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN, 
    DEFAULT_PORT, 
    CONF_USER_PIN, 
    DEFAULT_USER_PIN,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
    CONF_PANEL_TYPE,
    DEFAULT_PANEL_TYPE,
    PANEL_TYPES,
    PANEL_TYPE_ESX,
    PANEL_TYPE_ECI,
    PANEL_CONFIGS,
    CONF_AUTO_DETECT_ZONES,
    CONF_MAX_ZONES,
    CONF_AREAS,
    CONF_MAX_OUTPUTS,
    DEFAULT_MAX_OUTPUTS
)
from .arrowhead_client import ArrowheadClient

_LOGGER = logging.getLogger(__name__)

class ArrowheadAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Enhanced config flow for Arrowhead Alarm Panel with zone detection."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self.discovery_info: Dict[str, Any] = {}
        self._test_client: Optional[ArrowheadClient] = None
        self._detected_config: Optional[Dict[str, Any]] = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step - panel type selection."""
        errors = {}

        if user_input is not None:
            self.discovery_info.update(user_input)
            return await self.async_step_connection()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_PANEL_TYPE,
                    default=DEFAULT_PANEL_TYPE
                ): vol.In(PANEL_TYPES),
            }),
            description_placeholders={
                "esx_description": f"{PANEL_CONFIGS[PANEL_TYPE_ESX]['name']} - Supports up to {PANEL_CONFIGS[PANEL_TYPE_ESX]['max_zones']} zones and {PANEL_CONFIGS[PANEL_TYPE_ESX]['max_outputs']} outputs",
                "eci_description": f"{PANEL_CONFIGS[PANEL_TYPE_ECI]['name']} - Supports up to {PANEL_CONFIGS[PANEL_TYPE_ECI]['max_zones']} zones and {PANEL_CONFIGS[PANEL_TYPE_ECI]['max_outputs']} outputs",
            }
        )

    async def async_step_connection(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the connection configuration step."""
        errors = {}

        if user_input is not None:
            full_config = {**self.discovery_info, **user_input}
            
            try:
                connection_info = await self._test_connection(full_config)
                if connection_info["success"]:
                    self.discovery_info.update(full_config)
                    self._detected_config = connection_info.get("detected_config")
                    
                    # For ECi panels, show zone configuration step
                    if full_config[CONF_PANEL_TYPE] == PANEL_TYPE_ECI:
                        return await self.async_step_zone_config()
                    else:
                        return await self.async_step_output_config()
                else:
                    errors["base"] = connection_info["error_type"]
                    
            except Exception as err:
                _LOGGER.exception("Unexpected error during connection test: %s", err)
                errors["base"] = "unknown"

        panel_type = self.discovery_info.get(CONF_PANEL_TYPE, DEFAULT_PANEL_TYPE)
        panel_config = PANEL_CONFIGS[panel_type]
        
        return self.async_show_form(
            step_id="connection",
            data_schema=self._get_connection_schema(user_input, panel_type),
            errors=errors,
            description_placeholders={
                "panel_name": panel_config["name"],
                "default_port": str(panel_config["default_port"]),
                "max_zones": str(panel_config["max_zones"]),
                "max_outputs": str(panel_config["max_outputs"]),
            }
        )

    async def async_step_zone_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle ECi zone configuration step."""
        errors = {}

        if user_input is not None:
            self.discovery_info.update(user_input)
            
            # Check if user wants to name zones
            if user_input.get("configure_zone_names", False):
                return await self.async_step_zone_names()
            else:
                return await self.async_step_output_config()

        # Get panel configuration
        panel_type = self.discovery_info.get(CONF_PANEL_TYPE, DEFAULT_PANEL_TYPE)
        panel_config = PANEL_CONFIGS[panel_type]

        # Prepare zone configuration options
        detected_zones = 0
        detected_areas = []
        max_detected = 16
        detection_status = "No detection attempted"
        
        if self._detected_config:
            detected_zones = self._detected_config.get("total_zones", 0)
            # FIXED: Handle both set and list formats for active_areas
            active_areas = self._detected_config.get("active_areas", set())
            if isinstance(active_areas, set):
                detected_areas = sorted(list(active_areas))
            elif isinstance(active_areas, list):
                detected_areas = sorted(active_areas)
            else:
                detected_areas = [1]  # Fallback
            max_detected = self._detected_config.get("max_zone", 16)
            detection_method = self._detected_config.get("detection_method", "unknown")
            
            _LOGGER.info("Zone config step - detected: zones=%d, areas=%s, max=%d, method=%s", 
                        detected_zones, detected_areas, max_detected, detection_method)
            
            # Set status message based on detection results
            if detection_method == "active_areas_query":
                detection_status = f"✅ Successfully detected via panel query"
            elif detection_method == "status_parsing":
                detection_status = f"⚠️ Detected via status parsing"
            elif detection_method in ["fallback", "error_fallback"]:
                detection_status = f"❌ Auto-detection failed, using defaults"
            else:
                detection_status = f"❓ Detection method: {detection_method}"

        return self.async_show_form(
            step_id="zone_config",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_AUTO_DETECT_ZONES,
                    default=True
                ): bool,
                vol.Optional(
                    CONF_MAX_ZONES,
                    default=max_detected
                ): vol.All(cv.positive_int, vol.Range(min=8, max=248)),
                vol.Optional(
                    CONF_AREAS,
                    default=",".join(map(str, detected_areas)) if detected_areas else "1"
                ): cv.string,
                vol.Optional(
                    "configure_zone_names",
                    default=False
                ): bool,
            }),
            errors=errors,
            description_placeholders={
                "panel_name": panel_config["name"],
                "detected_zones": str(detected_zones) if detected_zones > 0 else "Auto-detection failed",
                "detected_areas": ",".join(map(str, detected_areas)) if detected_areas else "Auto-detection failed", 
                "max_detected": str(max_detected),
                "detection_status": detection_status,
            }
        )

    async def async_step_zone_names(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Configure zone names (optional step)."""
        errors = {}

        if user_input is not None:
            # Extract zone names and store them
            zone_names = {}
            for key, value in user_input.items():
                if key.startswith("zone_") and key.endswith("_name"):
                    zone_names[key] = value
            
            if zone_names and not user_input.get("skip_zone_naming", False):
                self.discovery_info["zone_names"] = zone_names
                
            return await self.async_step_output_config()

        # Only show if we have detected zones
        if not self._detected_config or not self._detected_config.get("detected_zones"):
            return await self.async_step_output_config()

        detected_zones = sorted(self._detected_config.get("detected_zones", []))
        
        # Create schema for zone naming
        schema_dict = {}
        
        # Add option to skip zone naming
        schema_dict[vol.Optional("skip_zone_naming", default=False)] = bool
        
        # Add zone name fields for detected zones (limit to first 16 for UI)
        for zone_id in detected_zones[:16]:  
            default_name = self._get_default_zone_name(zone_id)
            schema_dict[vol.Optional(f"zone_{zone_id}_name", default=default_name)] = cv.string

        # If there are more than 16 zones, show a note
        more_zones = len(detected_zones) - 16
        description = f"Customize names for your {len(detected_zones)} detected zones"
        if more_zones > 0:
            description += f"\n\n📝 Note: Showing first 16 zones only. The remaining {more_zones} zones can be renamed later in Settings → Integrations → Arrowhead Alarm Panel → Configure."

        return self.async_show_form(
            step_id="zone_names",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "zone_count": str(len(detected_zones)),
                "max_zone": str(max(detected_zones)) if detected_zones else "16",
                "description": description,
            }
        )

    async def async_step_output_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle output configuration step."""
        errors = {}

        if user_input is not None:
            self.discovery_info.update(user_input)
            return await self._create_config_entry()

        panel_type = self.discovery_info.get(CONF_PANEL_TYPE, DEFAULT_PANEL_TYPE)
        panel_config = PANEL_CONFIGS[panel_type]

        return self.async_show_form(
            step_id="output_config",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_MAX_OUTPUTS,
                    default=DEFAULT_MAX_OUTPUTS
                ): vol.All(cv.positive_int, vol.Range(min=1, max=panel_config["max_outputs"])),
            }),
            errors=errors,
            description_placeholders={
                "panel_name": panel_config["name"],
                "default_outputs": str(panel_config["default_outputs"]),
                "max_outputs": str(panel_config["max_outputs"]),
            }
        )

    def _get_default_zone_name(self, zone_id: int) -> str:
        """Get default zone name with zero-padding format only."""
        # Always use zero-padded format for consistency
        return f"Zone {zone_id:03d}"

    async def _test_connection(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection and detect panel configuration."""
        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT, DEFAULT_PORT)
        user_pin = user_input.get(CONF_USER_PIN, DEFAULT_USER_PIN)
        username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
        password = user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)
        panel_type = user_input.get(CONF_PANEL_TYPE, DEFAULT_PANEL_TYPE)

        # Test basic TCP connectivity
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            
        except asyncio.TimeoutError:
            return {"success": False, "error_type": "timeout", "status": "Connection timeout"}
        except ConnectionRefusedError:
            return {"success": False, "error_type": "connection_refused", "status": "Connection refused"}
        except Exception as err:
            return {"success": False, "error_type": "cannot_connect", "status": f"Connection failed: {err}"}

        # Test full client functionality
        client = None
        try:
            client = ArrowheadClient(host, port, user_pin, username, password, panel_type)
            
            success = await asyncio.wait_for(client.connect(), timeout=20.0)
            
            if not success:
                return {"success": False, "error_type": "auth_failed", "status": "Authentication failed"}
                
            status = await asyncio.wait_for(client.get_status(), timeout=10.0)
            
            if not isinstance(status, dict):
                return {"success": False, "error_type": "invalid_response", "status": "Invalid response from alarm system"}

            # For ECi panels, try to detect zone configuration
            detected_config = None
            if panel_type == PANEL_TYPE_ECI:
                try:
                    _LOGGER.info("=== ECi DETECTION START ===")
                    _LOGGER.info("Attempting ECi zone detection during connection test")
                    
                    # Test the specific command first
                    test_response = await client._send_command("P4076E1?", expect_response=True)
                    _LOGGER.info("Manual test of P4076E1?: %r", test_response)
                    
                    detected_config = await self._detect_eci_configuration(client)
                    _LOGGER.info("ECi detection completed: areas=%s, zones=%d, method=%s", 
                               detected_config.get("active_areas"), 
                               detected_config.get("total_zones", 0),
                               detected_config.get("detection_method", "unknown"))
                    _LOGGER.info("=== ECi DETECTION END ===")
                    
                except Exception as err:
                    _LOGGER.error("ECi zone detection failed: %s", err)
                    import traceback
                    _LOGGER.error("Full traceback: %s", traceback.format_exc())
                    
                    # FIXED: Use sets instead of lists, ensure proper format
                    detected_config = {
                        "total_zones": 16,
                        "max_zone": 16,
                        "active_areas": {1},  # Changed from [1] to {1}
                        "detected_zones": set(range(1, 17)),  # Add detected_zones
                        "zones_in_areas": {1: set(range(1, 17))},  # Add zones_in_areas
                        "detection_method": "fallback_error",
                        "error": str(err)
                    }
        
            panel_name = PANEL_TYPES.get(panel_type, panel_type)
            
            result = {
                "success": True,
                "error_type": None,
                "status": f"Connected successfully to {panel_name}",
                "connection_state": status.get("connection_state", "unknown"),
                "zones_count": len([z for z in status.get("zones", {}).values() if z]),
                "system_armed": status.get("armed", False),
                "panel_type": panel_type,
                "firmware_version": status.get("firmware_version"),
                "panel_model": status.get("panel_model"),
            }
            
            if detected_config:
                result["detected_config"] = detected_config
                
            return result
            
        except asyncio.TimeoutError:
            return {"success": False, "error_type": "timeout", "status": "Client connection timeout"}
        except Exception as err:
            return {"success": False, "error_type": "client_error", "status": f"Client error: {err}"}
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def _detect_eci_configuration(self, client) -> Dict[str, Any]:
        """Detect ECi panel configuration during setup."""
        try:
            _LOGGER.info("Starting ECi configuration detection")
            from .eci_zone_detection import ECiZoneManager
            
            zone_manager = ECiZoneManager(client)
            config = await zone_manager.detect_panel_configuration()
            
            _LOGGER.info("ECi detection results: %s", {
                "areas": list(config.get("active_areas", set())),
                "zones": len(config.get("detected_zones", set())),
                "method": config.get("detection_method", "unknown")
            })
            
            return config
            
        except Exception as err:
            _LOGGER.error("Error during ECi configuration detection: %s", err)
            return {
                "total_zones": 16,
                "max_zone": 16,
                "active_areas": {1},  # Ensure set format
                "detected_zones": set(range(1, 17)),
                "zones_in_areas": {1: set(range(1, 17))},
                "detection_method": "error_fallback"
            }

    async def _create_config_entry(self) -> FlowResult:
        """Create the final configuration entry."""
        unique_id = f"arrowhead_{self.discovery_info[CONF_PANEL_TYPE]}_{self.discovery_info[CONF_HOST]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        panel_name = PANEL_TYPES[self.discovery_info[CONF_PANEL_TYPE]]
        
        # Process zone configuration for ECi panels
        if self.discovery_info[CONF_PANEL_TYPE] == PANEL_TYPE_ECI:
            self._process_eci_zone_config()

        # Build description for config entry
        host = self.discovery_info[CONF_HOST]
        outputs = self.discovery_info.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
        
        # Add zone info for ECi
        zones_info = ""
        if self.discovery_info[CONF_PANEL_TYPE] == PANEL_TYPE_ECI:
            zones = self.discovery_info.get(CONF_MAX_ZONES, "auto")
            areas = self.discovery_info.get(CONF_AREAS, "auto")
            zones_info = f" • {zones} zones, areas {areas}"

        return self.async_create_entry(
            title=f"Arrowhead {panel_name}",
            data=self.discovery_info,
            description_placeholders={
                "host": host,
                "panel_type": panel_name,
                "outputs": str(outputs),
                "zones_info": zones_info,
            }
        )

    def _process_eci_zone_config(self):
        """Process ECi zone configuration from user input."""
        auto_detect = self.discovery_info.get(CONF_AUTO_DETECT_ZONES, True)
        
        if not auto_detect:
            max_zones = self.discovery_info.get(CONF_MAX_ZONES, 16)
            areas_str = self.discovery_info.get(CONF_AREAS, "1")
            
            try:
                areas = [int(x.strip()) for x in areas_str.split(",") if x.strip().isdigit()]
                if not areas:
                    areas = [1]
            except ValueError:
                areas = [1]
                
            self.discovery_info[CONF_MAX_ZONES] = max_zones
            self.discovery_info[CONF_AREAS] = areas
            
        else:
            if self._detected_config:
                detected_max = self._detected_config.get("max_zone", 16)
                detected_areas_set = self._detected_config.get("active_areas", {1})
                
                # Convert set to list for storage
                if isinstance(detected_areas_set, set):
                    detected_areas = list(detected_areas_set)
                else:
                    detected_areas = list(detected_areas_set) if detected_areas_set else [1]
                
                user_max = self.discovery_info.get(CONF_MAX_ZONES)
                user_areas_str = self.discovery_info.get(CONF_AREAS)
                
                if user_max and user_max != detected_max:
                    self.discovery_info[CONF_MAX_ZONES] = min(user_max, detected_max)
                else:
                    self.discovery_info[CONF_MAX_ZONES] = detected_max
                    
                if user_areas_str:
                    try:
                        user_areas = [int(x.strip()) for x in user_areas_str.split(",") if x.strip().isdigit()]
                        if user_areas:
                            self.discovery_info[CONF_AREAS] = user_areas
                        else:
                            self.discovery_info[CONF_AREAS] = detected_areas
                    except ValueError:
                        self.discovery_info[CONF_AREAS] = detected_areas
                else:
                    self.discovery_info[CONF_AREAS] = detected_areas

    def _get_connection_schema(self, user_input: Optional[Dict[str, Any]] = None, panel_type: str = None) -> vol.Schema:
        """Get the connection input schema based on panel type."""
        if user_input is None:
            user_input = {}
            
        if panel_type is None:
            panel_type = DEFAULT_PANEL_TYPE
            
        panel_config = PANEL_CONFIGS[panel_type]
        
        return vol.Schema({
            vol.Required(
                CONF_HOST, 
                default=user_input.get(CONF_HOST, "")
            ): cv.string,
            vol.Optional(
                CONF_PORT, 
                default=user_input.get(CONF_PORT, panel_config["default_port"])
            ): cv.port,
            vol.Optional(
                CONF_USER_PIN, 
                default=user_input.get(CONF_USER_PIN, DEFAULT_USER_PIN)
            ): cv.string,
            vol.Optional(
                CONF_USERNAME, 
                default=user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
            ): cv.string,
            vol.Optional(
                CONF_PASSWORD, 
                default=user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)
            ): cv.string,
        })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ArrowheadAlarmOptionsFlowHandler(config_entry)


class ArrowheadAlarmOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Arrowhead Alarm Panel options with zone configuration."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self.panel_type = config_entry.data.get(CONF_PANEL_TYPE, DEFAULT_PANEL_TYPE)
        self.panel_config = PANEL_CONFIGS[self.panel_type]

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input.get("configure_zone_names", False):
                # Remove the trigger and proceed to zone names
                base_options = {k: v for k, v in user_input.items() if k != "configure_zone_names"}
                return await self.async_step_zone_names(base_options)
            else:
                return self.async_create_entry(title="", data=user_input)

        # Get current zone configuration
        current_max_zones = self.config_entry.data.get(CONF_MAX_ZONES, self.panel_config["max_zones"])
        current_areas = self.config_entry.data.get(CONF_AREAS, [1])
        current_auto_detect = self.config_entry.data.get(CONF_AUTO_DETECT_ZONES, True)
        
        # Get current output configuration
        current_max_outputs = self.config_entry.data.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)

        # Base options schema
        base_options = {
            vol.Optional(
                "scan_interval",
                default=self.config_entry.options.get("scan_interval", 30)
            ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
            vol.Optional(
                "timeout",
                default=self.config_entry.options.get("timeout", 10)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
            vol.Optional(
                "enable_debug_logging",
                default=self.config_entry.options.get("enable_debug_logging", False)
            ): bool,
        }

        # Add ECi-specific zone options
        if self.panel_type == PANEL_TYPE_ECI:
            eci_options = {
                vol.Optional(
                    CONF_AUTO_DETECT_ZONES,
                    default=current_auto_detect
                ): bool,
                vol.Optional(
                    CONF_MAX_ZONES,
                    default=current_max_zones
                ): vol.All(vol.Coerce(int), vol.Range(min=8, max=248)),
                vol.Optional(
                    CONF_AREAS,
                    default=",".join(map(str, current_areas)) if isinstance(current_areas, list) else str(current_areas)
                ): cv.string,
                vol.Optional(
                    "configure_zone_names",
                    default=False
                ): bool,
            }
            base_options.update(eci_options)

        # Add output configuration options for all panel types
        output_options = {
            vol.Optional(
                CONF_MAX_OUTPUTS,
                default=current_max_outputs
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=self.panel_config["max_outputs"])),
        }
        base_options.update(output_options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(base_options),
            description_placeholders={
                "panel_name": self.panel_config["name"],
                "max_zones": str(self.panel_config["max_zones"]) if self.panel_type == PANEL_TYPE_ESX else "248",
                "max_outputs": str(self.panel_config["max_outputs"]),
            }
        )

    async def async_step_zone_names(self, base_options: Dict[str, Any]) -> FlowResult:
        """Configure zone names in options."""
        if "zone_names" in base_options:
            # User submitted zone names
            return self.async_create_entry(title="", data=base_options)
            
        # Get current zone names
        current_zone_names = self.config_entry.options.get("zone_names", {})
        
        # Get detected zones from coordinator if available
        detected_zones = []
        
        if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]["coordinator"]
            if coordinator.data and "zones" in coordinator.data:
                detected_zones = sorted(coordinator.data["zones"].keys())
        
        # If no zones detected, use default range
        if not detected_zones:
            max_zones = self.config_entry.data.get(CONF_MAX_ZONES, 16)
            detected_zones = list(range(1, min(max_zones + 1, 17)))  # Limit to 16 for UI
        
        # Create schema for zone naming
        schema_dict = {}
        
        for zone_id in detected_zones[:16]:  # Limit to 16 zones for UI
            current_name = current_zone_names.get(f"zone_{zone_id}", self._get_default_zone_name(zone_id))
            schema_dict[vol.Optional(f"zone_{zone_id}_name", default=current_name)] = cv.string
        
        return self.async_show_form(
            step_id="zone_names",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "zone_count": len(detected_zones),
            }
        )

    def _get_default_zone_name(self, zone_id: int) -> str:
        """Get default zone name with zero-padding."""
        # First check for common specific names for zones 1-16
        common_names = {
            1: "Front Door",
            2: "Back Door", 
            3: "Living Room",
            4: "Kitchen",
            5: "Bedroom",
            6: "Garage Door",
            7: "Basement",
            8: "Upstairs",
            9: "Office",
            10: "Patio Door",
            11: "Window 1",
            12: "Window 2",
            13: "Motion 1",
            14: "Motion 2",
            15: "Smoke Detector",
            16: "Glass Break"
        }
        
        # Use specific name if available for zones 1-16, otherwise use padded format
        if zone_id in common_names:
            return common_names[zone_id]
        else:
            return f"Zone {zone_id:03d}"