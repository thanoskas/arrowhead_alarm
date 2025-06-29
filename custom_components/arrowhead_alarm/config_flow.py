"""Simplified config flow for ECi-only Arrowhead Alarm Panel integration."""
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
    PANEL_CONFIG,
    CONF_AUTO_DETECT_ZONES,
    CONF_MAX_ZONES,
    CONF_AREAS,
    CONF_MAX_OUTPUTS,
    DEFAULT_MAX_OUTPUTS,
    supports_mode_4,
    get_optimal_protocol_mode,
    ProtocolMode,
)
from .arrowhead_eci_client import ArrowheadECiClient

_LOGGER = logging.getLogger(__name__)

class ArrowheadECiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ECi-only Arrowhead Alarm Panel."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self.discovery_info: Dict[str, Any] = {}
        self._test_client: Optional[ArrowheadECiClient] = None
        self._detected_config: Optional[Dict[str, Any]] = None
        self._firmware_info: Optional[Dict[str, Any]] = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step - connection setup."""
        errors = {}

        if user_input is not None:
            try:
                connection_info = await self._test_connection(user_input)
                if connection_info["success"]:
                    self.discovery_info.update(user_input)
                    self._detected_config = connection_info.get("detected_config")
                    self._firmware_info = connection_info.get("firmware_info")
                    
                    # Always proceed to zone configuration for ECi
                    return await self.async_step_zone_config()
                else:
                    errors["base"] = connection_info["error_type"]
                    
            except Exception as err:
                _LOGGER.exception("Unexpected error during connection test: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_connection_schema(user_input),
            errors=errors,
            description_placeholders={
                "panel_name": PANEL_CONFIG["name"],
                "default_port": str(PANEL_CONFIG["default_port"]),
                "max_zones": str(PANEL_CONFIG["max_zones"]),
                "max_outputs": str(PANEL_CONFIG["max_outputs"]),
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

        # Prepare zone configuration options with firmware info
        detected_zones = 0
        detected_areas = []
        max_detected = 16
        detection_status = "No detection attempted"
        firmware_status = "Unknown"
        protocol_mode_info = "Mode 1 (Default)"
        
        if self._firmware_info:
            firmware_version = self._firmware_info.get("version", "Unknown")
            protocol_mode = self._firmware_info.get("protocol_mode", 1)
            supports_mode4 = self._firmware_info.get("supports_mode_4", False)
            
            firmware_status = f"✅ {firmware_version}"
            if supports_mode4:
                protocol_mode_info = f"Mode {protocol_mode} (Enhanced Features Available)"
            else:
                protocol_mode_info = f"Mode {protocol_mode} (Standard)"
        
        if self._detected_config:
            detected_zones = self._detected_config.get("total_zones", 0)
            active_areas = self._detected_config.get("active_areas", set())
            if isinstance(active_areas, set):
                detected_areas = sorted(list(active_areas))
            elif isinstance(active_areas, list):
                detected_areas = sorted(active_areas)
            else:
                detected_areas = [1]
            max_detected = self._detected_config.get("max_zone", 16)
            detection_method = self._detected_config.get("detection_method", "unknown")
            
            _LOGGER.info("Zone config step - detected: zones=%d, areas=%s, max=%d, method=%s", 
                        detected_zones, detected_areas, max_detected, detection_method)
            
            if detection_method == "active_areas_query":
                detection_status = f"✅ Successfully detected via P4076E1 query"
            elif detection_method == "zones_in_areas_query":
                detection_status = f"✅ Successfully detected via P4075Ex queries"
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
                "panel_name": PANEL_CONFIG["name"],
                "firmware_status": firmware_status,
                "protocol_mode_info": protocol_mode_info,
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
            description += f"\n\n📝 Note: Showing first 16 zones only. The remaining {more_zones} zones can be renamed later in Settings → Integrations → Arrowhead ECi → Configure."

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

        # Show firmware-specific information
        mode_4_features = ""
        if self._firmware_info and self._firmware_info.get("supports_mode_4", False):
            mode_4_features = "\n\n🚀 **MODE 4 Enhanced Features Available:**\n• Enhanced area commands (ARMAREA, STAYAREA)\n• Keypad alarm functions\n• User tracking for arm/disarm events\n• Enhanced entry/exit delay timing"

        return self.async_show_form(
            step_id="output_config",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_MAX_OUTPUTS,
                    default=DEFAULT_MAX_OUTPUTS
                ): vol.All(cv.positive_int, vol.Range(min=1, max=PANEL_CONFIG["max_outputs"])),
            }),
            errors=errors,
            description_placeholders={
                "panel_name": PANEL_CONFIG["name"],
                "default_outputs": str(PANEL_CONFIG["default_outputs"]),
                "max_outputs": str(PANEL_CONFIG["max_outputs"]),
                "mode_4_features": mode_4_features,
            }
        )

    def _get_default_zone_name(self, zone_id: int) -> str:
        """Get default zone name with zero-padding format."""
        return f"Zone {zone_id:03d}"

    async def _test_connection(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection and detect ECi configuration."""
        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT, DEFAULT_PORT)
        user_pin = user_input.get(CONF_USER_PIN, DEFAULT_USER_PIN)
        username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
        password = user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)

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
            client = ArrowheadECiClient(host, port, user_pin, username, password)
            
            success = await asyncio.wait_for(client.connect(), timeout=20.0)
            
            if not success:
                return {"success": False, "error_type": "auth_failed", "status": "Authentication failed"}
                
            status = await asyncio.wait_for(client.get_status(), timeout=10.0)
            
            if not isinstance(status, dict):
                return {"success": False, "error_type": "invalid_response", "status": "Invalid response from ECi panel"}

            # Detect firmware and protocol capabilities
            firmware_info = await self._detect_firmware_info(client)
            
            # Detect zone configuration
            detected_config = None
            try:
                _LOGGER.info("=== ECi DETECTION START ===")
                detected_config = await self._detect_eci_configuration(client)
                _LOGGER.info("ECi detection completed: areas=%s, zones=%d, method=%s", 
                           detected_config.get("active_areas"), 
                           detected_config.get("total_zones", 0),
                           detected_config.get("detection_method", "unknown"))
                _LOGGER.info("=== ECi DETECTION END ===")
                
            except Exception as err:
                _LOGGER.error("ECi zone detection failed: %s", err)
                detected_config = {
                    "total_zones": 16,
                    "max_zone": 16,
                    "active_areas": {1},
                    "detected_zones": set(range(1, 17)),
                    "zones_in_areas": {1: set(range(1, 17))},
                    "detection_method": "fallback_error",
                    "error": str(err)
                }
        
            result = {
                "success": True,
                "error_type": None,
                "status": f"Connected successfully to {PANEL_CONFIG['name']}",
                "connection_state": status.get("connection_state", "unknown"),
                "zones_count": len([z for z in status.get("zones", {}).values() if z]),
                "system_armed": status.get("armed", False),
                "firmware_info": firmware_info,
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

    async def _detect_firmware_info(self, client) -> Dict[str, Any]:
        """Detect ECi firmware version and capabilities."""
        try:
            firmware_info = {
                "version": "Unknown",
                "protocol_mode": 1,
                "supports_mode_4": False,
                "optimal_mode": 1,
            }
            
            # Get firmware version
            version_response = await client._send_command("VERSION", expect_response=True)
            if version_response:
                import re
                version_match = re.search(r'Version\s+"?([^"]+)"?', version_response)
                if version_match:
                    firmware_version = version_match.group(1)
                    firmware_info["version"] = firmware_version
                    
                    # Check MODE 4 support
                    supports_mode4 = supports_mode_4(firmware_version)
                    firmware_info["supports_mode_4"] = supports_mode4
                    
                    # Set optimal protocol mode
                    optimal_mode = get_optimal_protocol_mode(firmware_version)
                    firmware_info["optimal_mode"] = optimal_mode
                    firmware_info["protocol_mode"] = optimal_mode
                    
                    _LOGGER.info("Firmware detected: %s, MODE 4 support: %s, Optimal mode: %d", 
                               firmware_version, supports_mode4, optimal_mode)
            
            return firmware_info
            
        except Exception as err:
            _LOGGER.error("Error detecting firmware info: %s", err)
            return {
                "version": "Unknown",
                "protocol_mode": 1,
                "supports_mode_4": False,
                "optimal_mode": 1,
            }

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
                "active_areas": {1},
                "detected_zones": set(range(1, 17)),
                "zones_in_areas": {1: set(range(1, 17))},
                "detection_method": "error_fallback"
            }

    async def _create_config_entry(self) -> FlowResult:
        """Create the final configuration entry."""
        unique_id = f"arrowhead_eci_{self.discovery_info[CONF_HOST]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        # Include firmware information in config
        if self._firmware_info:
            self.discovery_info.update({
                "firmware_version": self._firmware_info.get("version"),
                "protocol_mode": self._firmware_info.get("optimal_mode", 1),
                "supports_mode_4": self._firmware_info.get("supports_mode_4", False),
            })

        # Process zone configuration
        self._process_eci_zone_config()

        # Build description for config entry
        host = self.discovery_info[CONF_HOST]
        outputs = self.discovery_info.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
        zones = self.discovery_info.get(CONF_MAX_ZONES, "auto")
        areas = self.discovery_info.get(CONF_AREAS, "auto")
        
        # Build firmware info for description
        firmware_info = ""
        if self._firmware_info:
            version = self._firmware_info.get("version", "Unknown")
            mode = self._firmware_info.get("protocol_mode", 1)
            firmware_info = f" • Firmware: {version} (Mode {mode})"

        return self.async_create_entry(
            title=f"Arrowhead {PANEL_CONFIG['name']}",
            data=self.discovery_info,
            description_placeholders={
                "host": host,
                "panel_type": PANEL_CONFIG['name'],
                "outputs": str(outputs),
                "zones": str(zones),
                "areas": str(areas),
                "firmware_info": firmware_info,
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

    def _get_connection_schema(self, user_input: Optional[Dict[str, Any]] = None) -> vol.Schema:
        """Get the connection input schema."""
        if user_input is None:
            user_input = {}
            
        return vol.Schema({
            vol.Required(
                CONF_HOST, 
                default=user_input.get(CONF_HOST, "")
            ): cv.string,
            vol.Optional(
                CONF_PORT, 
                default=user_input.get(CONF_PORT, PANEL_CONFIG["default_port"])
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
        return ArrowheadECiOptionsFlowHandler(config_entry)


class ArrowheadECiOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle ECi options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input.get("configure_zone_names", False):
                # Remove the trigger and proceed to zone names
                base_options = {k: v for k, v in user_input.items() if k != "configure_zone_names"}
                return await self.async_step_zone_names(base_options)
            else:
                return self.async_create_entry(title="", data=user_input)

        # Get current configuration
        current_max_zones = self.config_entry.data.get(CONF_MAX_ZONES, 16)
        current_areas = self.config_entry.data.get(CONF_AREAS, [1])
        current_auto_detect = self.config_entry.data.get(CONF_AUTO_DETECT_ZONES, True)
        current_max_outputs = self.config_entry.data.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
        
        # Check if MODE 4 is supported
        supports_mode4 = self.config_entry.data.get("supports_mode_4", False)
        firmware_version = self.config_entry.data.get("firmware_version", "Unknown")
        
        mode_4_info = ""
        if supports_mode4:
            mode_4_info = f"\n\n🚀 **MODE 4 Features Active** (Firmware: {firmware_version})\n• Enhanced area commands\n• Keypad alarm functions\n• User tracking\n• Enhanced timing information"

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
                CONF_MAX_OUTPUTS,
                default=current_max_outputs
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=PANEL_CONFIG["max_outputs"])),
            vol.Optional(
                "configure_zone_names",
                default=False
            ): bool,
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(base_options),
            description_placeholders={
                "panel_name": PANEL_CONFIG["name"],
                "max_zones": "248",
                "max_outputs": str(PANEL_CONFIG["max_outputs"]),
                "mode_4_info": mode_4_info,
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
        return f"Zone {zone_id:03d}"