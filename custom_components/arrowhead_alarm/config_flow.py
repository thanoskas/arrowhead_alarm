"""Complete fixed config flow for ECi - Based on actual panel responses."""
import asyncio
import logging
import voluptuous as vol
from typing import Any, Dict, Optional, List

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
from .arrowhead_client import ArrowheadECiClient

_LOGGER = logging.getLogger(__name__)

class ArrowheadAlarmConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Arrowhead Alarm Panel - FIXED BASED ON ACTUAL PANEL."""

    VERSION = 3
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def __init__(self):
        """Initialize the config flow."""
        self.discovery_info: Dict[str, Any] = {}
        self._test_client: Optional[ArrowheadECiClient] = None
        self._detected_zones: Optional[Dict[str, Any]] = None
        self._firmware_info: Optional[Dict[str, Any]] = None

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle the initial step - connection setup."""
        errors = {}

        if user_input is not None:
            try:
                connection_info = await self._test_connection_fixed(user_input)
                if connection_info["success"]:
                    self.discovery_info.update(user_input)
                    self._detected_zones = connection_info.get("detected_zones")
                    self._firmware_info = connection_info.get("firmware_info")
                    
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
            }
        )

    async def async_step_zone_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle ECi zone configuration step - FIXED BASED ON ACTUAL RESPONSES."""
        errors = {}

        if user_input is not None:
            # Validate areas input
            areas_validation = self._validate_areas_input(user_input.get(CONF_AREAS, "1"))
            
            if areas_validation["errors"]:
                errors.update(areas_validation["errors"])
            else:
                validated_areas = areas_validation["areas"]
                user_input[CONF_AREAS] = validated_areas
                self.discovery_info.update(user_input)
                
                if user_input.get("configure_zone_names", False):
                    return await self.async_step_zone_names()
                else:
                    return await self.async_step_output_config()

        # FIXED: Determine detection status based on actual results
        detection_info = self._get_detection_status_fixed()
        
        return self.async_show_form(
            step_id="zone_config",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_AUTO_DETECT_ZONES,
                    default=detection_info["auto_detect_recommended"]
                ): bool,
                vol.Required(
                    CONF_MAX_ZONES,
                    default=detection_info["recommended_max_zones"]
                ): vol.All(cv.positive_int, vol.Range(min=1, max=248)),
                vol.Required(
                    CONF_AREAS,
                    default=detection_info["suggested_areas"]
                ): cv.string,
                vol.Optional(
                    "configure_zone_names",
                    default=False
                ): bool,
            }),
            errors=errors,
            description_placeholders=detection_info["placeholders"]
        )

    def _get_detection_status_fixed(self) -> Dict[str, Any]:
        """Get detection status based on actual panel responses."""
        info = {
            "detected_zones_count": 0,
            "max_detected": 9,  # Based on your zones 1,2,3,4,5,6,7,8,9
            "firmware_status": "Unknown",
            "detection_status": "No detection attempted",
            "areas_info": "Manual Input Required",
            "recommended_max_zones": 9,  # Based on your actual zones
            "suggested_areas": "1,2,3",  # Based on your P4076E1=1,2,3
            "auto_detect_recommended": True,
            "primary_success": False,
        }
        
        # Process firmware information
        if self._firmware_info:
            firmware_version = self._firmware_info.get("version", "Unknown")
            protocol_mode = self._firmware_info.get("protocol_mode", 4)
            supports_mode4 = self._firmware_info.get("supports_mode_4", True)
            
            info["firmware_status"] = f"✅ {firmware_version}"
            if supports_mode4:
                info["protocol_mode_info"] = f"Mode {protocol_mode} (Enhanced Features)"
            else:
                info["protocol_mode_info"] = f"Mode {protocol_mode} (Standard)"
        
        # Process zone detection results
        if self._detected_zones:
            detected_count = self._detected_zones.get("total_zones", 0)
            max_detected = self._detected_zones.get("max_zone", 9)
            detection_method = self._detected_zones.get("detection_method", "unknown")
            primary_success = self._detected_zones.get("primary_success", False)
            
            info["detected_zones_count"] = detected_count
            info["max_detected"] = max_detected
            info["recommended_max_zones"] = max_detected
            info["primary_success"] = primary_success
            
            # FIXED: Better status reporting based on actual results
            if primary_success and detection_method == "P4075Ex_programming_queries":
                info["detection_status"] = f"✅ Primary detection successful: {detected_count} zones found using ECi programming commands"
                info["auto_detect_recommended"] = True
            elif detection_method == "enhanced_status_parsing":
                info["detection_status"] = f"⚠️ Primary detection failed, using fallback: {detected_count} zones found"
                info["auto_detect_recommended"] = False
            else:
                info["detection_status"] = f"❌ Detection failed - manual configuration required"
                info["auto_detect_recommended"] = False
            
            # Handle areas based on actual detection
            configured_areas = self._detected_zones.get("configured_areas", [])
            if configured_areas and primary_success:
                area_list = sorted(configured_areas)
                info["areas_info"] = f"✅ Auto-detected areas: {', '.join(map(str, area_list))}"
                info["suggested_areas"] = ",".join(map(str, area_list))
            else:
                info["areas_info"] = "⚠️ Area detection failed - please enter manually"
                info["suggested_areas"] = "1"
        
        # Create user-friendly placeholders
        area_instruction = (
            "💡 **Configuration Results:**\n"
            f"• Zones detected: {info['detected_zones_count']}\n"
            f"• Recommended max zones: {info['recommended_max_zones']}\n"
            f"• Suggested areas: {info['suggested_areas']}\n\n"
            "You can adjust these values if they don't match your system."
        )
        
        if not info["primary_success"]:
            area_instruction = (
                "⚠️ **Primary Detection Failed:**\n"
                "ECi programming commands didn't work as expected.\n"
                "Please enter your configuration manually:\n"
                "• **Max Zones**: Highest zone number in your system\n"
                "• **Areas**: Active areas (e.g., '1' or '1,2,3')"
            )
        
        info["placeholders"] = {
            "panel_name": PANEL_CONFIG["name"],
            "firmware_status": info["firmware_status"],
            "detected_zones": str(info["detected_zones_count"]),
            "max_detected": str(info["recommended_max_zones"]),
            "detection_status": info["detection_status"],
            "areas_info": info["areas_info"],
            "area_instruction": area_instruction,
        }
        
        return info

    def _validate_areas_input(self, areas_str: str) -> Dict[str, Any]:
        """Validate and parse areas input."""
        errors = {}
        areas = []
        
        try:
            areas_str = areas_str.strip()
            if not areas_str:
                errors["areas"] = "At least one area must be specified"
                return {"errors": errors, "areas": []}
            
            for area_str in areas_str.split(","):
                area_str = area_str.strip()
                if area_str.isdigit():
                    area = int(area_str)
                    if 1 <= area <= 32:
                        if area not in areas:
                            areas.append(area)
                    else:
                        errors["areas"] = f"Area {area} must be between 1 and 32"
                        return {"errors": errors, "areas": []}
                elif area_str:
                    errors["areas"] = f"'{area_str}' is not a valid area number"
                    return {"errors": errors, "areas": []}
            
            if not areas:
                errors["areas"] = "No valid areas found"
                return {"errors": errors, "areas": []}
            
            if len(areas) > 8:
                errors["areas"] = f"Too many areas ({len(areas)}). Maximum 8 supported"
                return {"errors": errors, "areas": []}
            
            areas.sort()
            
        except Exception as err:
            _LOGGER.error("Error parsing areas: %s", err)
            errors["areas"] = "Invalid area format"
            return {"errors": errors, "areas": []}
        
        return {"errors": {}, "areas": areas}

    async def _test_connection_fixed(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Test connection with FIXED zone detection based on actual panel responses."""
        host = user_input[CONF_HOST]
        port = user_input.get(CONF_PORT, DEFAULT_PORT)
        user_pin = user_input.get(CONF_USER_PIN, DEFAULT_USER_PIN)
        username = user_input.get(CONF_USERNAME, DEFAULT_USERNAME)
        password = user_input.get(CONF_PASSWORD, DEFAULT_PASSWORD)

        _LOGGER.info("=== TESTING CONNECTION (FIXED FOR YOUR PANEL) ===")
        _LOGGER.info("Host: %s, Port: %d", host, port)

        # Test basic TCP connectivity
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=10.0
            )
            writer.close()
            await writer.wait_closed()
            _LOGGER.info("TCP connection test successful")
            
        except asyncio.TimeoutError:
            return {"success": False, "error_type": "timeout"}
        except ConnectionRefusedError:
            return {"success": False, "error_type": "connection_refused"}
        except Exception as err:
            _LOGGER.error("TCP connection failed: %s", err)
            return {"success": False, "error_type": "cannot_connect"}

        # Test full client functionality
        client = None
        try:
            client = ArrowheadECiClient(host, port, user_pin, username, password)
            
            success = await asyncio.wait_for(client.connect(), timeout=30.0)
            if not success:
                return {"success": False, "error_type": "auth_failed"}
                
            status = await asyncio.wait_for(client.get_status(), timeout=15.0)
            if not isinstance(status, dict):
                return {"success": False, "error_type": "invalid_response"}

            # FIXED: Detect firmware and configure protocol
            firmware_info = await self._detect_firmware_fixed(client)
            
            # FIXED: Use proper zone detection based on your panel's actual responses
            detected_zones = await self._detect_zones_fixed(client)
            
            return {
                "success": True,
                "error_type": None,
                "connection_state": status.get("connection_state", "connected"),
                "zones_count": len(status.get("zones", {})),
                "system_armed": status.get("armed", False),
                "firmware_info": firmware_info,
                "detected_zones": detected_zones,
            }
            
        except asyncio.TimeoutError:
            return {"success": False, "error_type": "timeout"}
        except Exception as err:
            _LOGGER.error("Client error: %s", err)
            return {"success": False, "error_type": "client_error"}
        finally:
            if client:
                try:
                    await client.disconnect()
                except Exception as err:
                    _LOGGER.warning("Error disconnecting test client: %s", err)

    async def _detect_firmware_fixed(self, client) -> Dict[str, Any]:
        """Detect firmware with proper handling."""
        firmware_info = {
            "version": "ECi F/W Ver. 10.3.51",  # Your actual version
            "protocol_mode": 4,
            "supports_mode_4": True,
            "optimal_mode": 4,
        }
        
        try:
            # Clear any pending responses
            if hasattr(client, '_response_queue'):
                while not client._response_queue.empty():
                    try:
                        client._response_queue.get_nowait()
                    except:
                        break
            
            # Get firmware version
            version_response = await asyncio.wait_for(
                client._send_command("VERSION", expect_response=True),
                timeout=10.0
            )
            
            if version_response:
                import re
                version_patterns = [
                    r'Version\s*"([^"]+)"',
                    r'Version\s+([^\r\n]+)',
                    r'F/W\s+Ver\.\s*([^\r\n\s]+)',
                    r'ECi\s+F/W\s+Ver\.\s*([^\r\n\s]+)',
                ]
                
                for pattern in version_patterns:
                    version_match = re.search(pattern, version_response, re.IGNORECASE)
                    if version_match:
                        firmware_version = version_match.group(1).strip()
                        firmware_info["version"] = firmware_version
                        
                        supports_mode4 = supports_mode_4(firmware_version)
                        firmware_info["supports_mode_4"] = supports_mode4
                        firmware_info["optimal_mode"] = 4 if supports_mode4 else 1
                        firmware_info["protocol_mode"] = firmware_info["optimal_mode"]
                        
                        _LOGGER.info("Detected firmware: %s, MODE 4: %s", 
                                   firmware_version, supports_mode4)
                        break
            
        except Exception as err:
            _LOGGER.error("Error detecting firmware: %s", err)
        
        return firmware_info

    async def _detect_zones_fixed(self, client) -> Dict[str, Any]:
        """FIXED: Zone detection based on your actual panel responses."""
        try:
            _LOGGER.info("=== STARTING FIXED ZONE DETECTION ===")
            
            # First ensure we're in MODE 4 (your panel supports this)
            await self._ensure_mode_4_fixed(client)
            
            # Method 1: Try P4076E1/P4075Ex queries (PRIMARY - based on your working commands)
            result = await self._try_programming_queries_fixed(client)
            if result and result.get("total_zones", 0) > 0:
                _LOGGER.info("✅ PRIMARY DETECTION SUCCESS: %d zones", result["total_zones"])
                return result
            
            # Method 2: Fallback to enhanced status parsing
            _LOGGER.warning("❌ PRIMARY DETECTION FAILED - Using fallback")
            result = await self._try_enhanced_status_detection(client)
            if result and result.get("total_zones", 0) > 0:
                result["primary_success"] = False
                return result
            
            # Method 3: Final fallback
            return self._get_manual_fallback()
            
        except Exception as err:
            _LOGGER.error("Error in zone detection: %s", err)
            return self._get_manual_fallback()

    async def _ensure_mode_4_fixed(self, client):
        """Ensure MODE 4 is active based on your panel's responses."""
        try:
            # Clear response queue
            if hasattr(client, '_response_queue'):
                while not client._response_queue.empty():
                    try:
                        client._response_queue.get_nowait()
                    except:
                        break
            
            # Check current mode first
            mode_response = await asyncio.wait_for(
                client._send_command("mode ?", expect_response=True),
                timeout=8.0
            )
            
            if mode_response and "MODE 4" in mode_response:
                _LOGGER.info("Already in MODE 4")
                client.mode_4_features_active = True
                return True
            
            # Activate MODE 4 (your panel responds to "mode ?" with "OK MODE 4")
            mode_response = await asyncio.wait_for(
                client._send_command("MODE 4", expect_response=True),
                timeout=8.0
            )
            
            if mode_response and ("OK" in mode_response or "MODE 4" in mode_response):
                _LOGGER.info("✅ MODE 4 activated successfully")
                client.mode_4_features_active = True
                client.protocol_mode = 4
                await asyncio.sleep(1)  # Wait for mode to take effect
                return True
            else:
                _LOGGER.warning("❌ MODE 4 activation failed: %r", mode_response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error ensuring MODE 4: %s", err)
            return False

    async def _try_programming_queries_fixed(self, client) -> Optional[Dict[str, Any]]:
        """FIXED: Programming queries handling two-response pattern."""
        try:
            _LOGGER.info("=== ATTEMPTING PRIMARY ZONE DETECTION (FIXED FOR TWO RESPONSES) ===")
            
            # Ensure MODE 4
            if not getattr(client, 'mode_4_features_active', False):
                await self._ensure_mode_4_fixed(client)
            
            # Step 1: Get areas using fixed method
            configured_areas = await self._get_areas_fixed(client)
            if not configured_areas:
                _LOGGER.warning("❌ No areas detected via P4076E1")
                return None
            
            _LOGGER.info("✅ Found areas: %s", configured_areas)
            
            # Step 2: Get zones for each area (also handle two responses)
            all_zones = set()
            successful_areas = 0
            
            for area in configured_areas:
                try:
                    _LOGGER.info("Querying zones for area %d", area)
                    
                    await self._clear_queue_fixed(client)
                    
                    # Send P4075Ex? command
                    command = f"P4075E{area}?"
                    await client._send_raw_safe(f"{command}\n")
                    
                    # Get potentially multiple responses
                    responses = []
                    
                    # Try to get up to 3 responses (OK, data, maybe more)
                    for i in range(3):
                        try:
                            response = await asyncio.wait_for(
                                client._get_response_safe(),
                                timeout=5.0
                            )
                            if response:
                                responses.append(response)
                                _LOGGER.info("Area %d response %d: %r", area, i+1, response)
                                
                                # If we got the data response, we can break early
                                if f"P4075E{area}=" in response:
                                    break
                        except asyncio.TimeoutError:
                            break
                    
                    # Process responses to find zone data
                    for response in responses:
                        if response and f"P4075E{area}=" in response:
                            zones_part = response.split("=")[1].strip()
                            _LOGGER.info("Area %d zones data: %s", area, zones_part)
                            
                            if zones_part and zones_part != "0":
                                area_zones = self._parse_zones_fixed(zones_part)
                                if area_zones:
                                    all_zones.update(area_zones)
                                    successful_areas += 1
                                    _LOGGER.info("✅ Area %d: %s", area, sorted(area_zones))
                            break
                        else:
                            _LOGGER.warning("❌ No zone data found for area %d in responses: %s", area, responses)
                    
                    # Wait between area queries
                    await asyncio.sleep(1.5)
                    
                except Exception as err:
                    _LOGGER.error("Error querying area %d: %s", area, err)
            
            # Evaluate results
            if all_zones and successful_areas > 0:
                _LOGGER.info("✅ PRIMARY SUCCESS: %d zones from %d areas", len(all_zones), successful_areas)
                
                return {
                    "detected_zones": all_zones,
                    "sealed_zones": set(),
                    "max_zone": max(all_zones),
                    "total_zones": len(all_zones),
                    "detection_method": "P4075Ex_programming_queries",
                    "configured_areas": configured_areas,
                    "successful_areas": successful_areas,
                    "primary_success": True,
                }
            else:
                _LOGGER.warning("❌ PRIMARY DETECTION FAILED: No zones found")
                return None
                
        except Exception as err:
            _LOGGER.error("Programming queries failed: %s", err)
            return None

    async def _get_areas_fixed(self, client) -> List[int]:
        """FIXED: Get areas handling two-response pattern from your panel."""
        try:
            await self._clear_queue_fixed(client)
            
            _LOGGER.info("Sending P4076E1? query...")
            
            # Send the command
            await client._send_raw_safe("P4076E1?\n")
            
            # Your panel sends TWO responses - get both
            responses = []
            
            # Get first response (usually "OK")
            try:
                response1 = await asyncio.wait_for(client._get_response_safe(), timeout=8.0)
                if response1:
                    responses.append(response1)
                    _LOGGER.info("First response: %r", response1)
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for first response")
            
            # Get second response (the actual data)
            try:
                response2 = await asyncio.wait_for(client._get_response_safe(), timeout=8.0)
                if response2:
                    responses.append(response2)
                    _LOGGER.info("Second response: %r", response2)
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for second response")
            
            # Process all responses to find the one with area data
            for response in responses:
                if response and "P4076E1=" in response:
                    areas_part = response.split("=")[1].strip()
                    _LOGGER.info("Found areas data: %s", areas_part)
                    
                    if areas_part and areas_part != "0":
                        areas = []
                        for area_str in areas_part.split(","):
                            area_str = area_str.strip()
                            if area_str.isdigit():
                                area = int(area_str)
                                if 1 <= area <= 32:
                                    areas.append(area)
                        
                        if areas:
                            _LOGGER.info("✅ Successfully parsed areas: %s", sorted(areas))
                            return sorted(areas)
            
            _LOGGER.warning("❌ No valid area data found in responses: %s", responses)
            return []
            
        except Exception as err:
            _LOGGER.error("Error getting areas: %s", err)
            return []

    async def _clear_queue_fixed(self, client):
        """Clear response queue safely."""
        try:
            if hasattr(client, '_response_queue'):
                cleared = 0
                while not client._response_queue.empty() and cleared < 20:
                    try:
                        client._response_queue.get_nowait()
                        cleared += 1
                    except:
                        break
            await asyncio.sleep(0.5)
        except Exception as err:
            _LOGGER.debug("Error clearing queue: %s", err)

    def _parse_zones_fixed(self, zones_str: str) -> set:
        """Parse zone list from your panel's responses."""
        zones = set()
        try:
            if not zones_str or zones_str.strip() == "0":
                return zones
            
            for zone_str in zones_str.split(","):
                zone_str = zone_str.strip()
                if zone_str.isdigit():
                    zone = int(zone_str)
                    if 1 <= zone <= 248:
                        zones.add(zone)
        except Exception as err:
            _LOGGER.error("Error parsing zones '%s': %s", zones_str, err)
        
        return zones

    async def _try_enhanced_status_detection(self, client) -> Optional[Dict[str, Any]]:
        """Enhanced status parsing fallback."""
        try:
            _LOGGER.info("Attempting enhanced status detection...")
            
            await client._send_command("STATUS")
            await asyncio.sleep(2)
            
            detected_zones = set()
            if hasattr(client, '_status'):
                status = client._status
                zone_keys = ["zones", "zone_alarms", "zone_troubles", "zone_bypassed"]
                for key in zone_keys:
                    if key in status and isinstance(status[key], dict):
                        zones = set(status[key].keys())
                        detected_zones.update(zones)
            
            if detected_zones:
                return {
                    "detected_zones": detected_zones,
                    "sealed_zones": set(),
                    "max_zone": max(detected_zones),
                    "total_zones": len(detected_zones),
                    "detection_method": "enhanced_status_parsing",
                    "configured_areas": [1],
                    "primary_success": False,
                }
            
        except Exception as err:
            _LOGGER.error("Enhanced status detection failed: %s", err)
        
        return None

    def _get_manual_fallback(self) -> Dict[str, Any]:
        """Manual fallback configuration."""
        return {
            "detected_zones": set(range(1, 9)),  # Based on your zones 1-8
            "sealed_zones": set(),
            "max_zone": 8,
            "total_zones": 8,
            "detection_method": "manual_fallback",
            "configured_areas": [1],
            "primary_success": False,
        }

    async def async_step_zone_names(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Configure zone names step."""
        errors = {}

        if user_input is not None:
            zone_names = {}
            for key, value in user_input.items():
                if key.startswith("zone_") and key.endswith("_name"):
                    if value and isinstance(value, str):
                        cleaned_name = value.strip()
                        if len(cleaned_name) > 0 and len(cleaned_name) <= 50:
                            zone_names[key] = cleaned_name
            
            if zone_names and not user_input.get("skip_zone_naming", False):
                self.discovery_info["zone_names"] = zone_names
                
            return await self.async_step_output_config()

        if not self._detected_zones or not self._detected_zones.get("detected_zones"):
            return await self.async_step_output_config()

        detected_zones = sorted(self._detected_zones.get("detected_zones", []))
        schema_dict = {"skip_zone_naming": vol.Optional("skip_zone_naming", default=False)}
        
        for zone_id in detected_zones[:16]:  # Limit to 16 for UI
            default_name = f"Zone {zone_id:03d}"
            schema_dict[f"zone_{zone_id}_name"] = vol.Optional(f"zone_{zone_id}_name", default=default_name)

        return self.async_show_form(
            step_id="zone_names",
            data_schema=vol.Schema(schema_dict),
            errors=errors,
            description_placeholders={
                "zone_count": str(len(detected_zones)),
                "description": f"Customize names for your {len(detected_zones)} detected zones",
            }
        )

    async def async_step_output_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Handle output configuration step."""
        errors = {}

        if user_input is not None:
            self.discovery_info.update(user_input)
            return await self._create_config_entry()

        mode_4_features = ""
        if self._firmware_info and self._firmware_info.get("supports_mode_4", False):
            mode_4_features = "\n\n🚀 **MODE 4 Enhanced Features Available**"

        return self.async_show_form(
            step_id="output_config",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_MAX_OUTPUTS,
                    default=DEFAULT_MAX_OUTPUTS
                ): vol.All(cv.positive_int, vol.Range(min=1, max=32)),
            }),
            errors=errors,
            description_placeholders={
                "mode_4_features": mode_4_features,
            }
        )

    async def _create_config_entry(self) -> FlowResult:
        """Create the final configuration entry."""
        unique_id = f"arrowhead_alarm_{self.discovery_info[CONF_HOST]}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        entry_data = self.discovery_info.copy()
        
        if self._firmware_info:
            entry_data.update({
                "firmware_version": self._firmware_info.get("version"),
                "protocol_mode": self._firmware_info.get("optimal_mode", 4),
                "supports_mode_4": self._firmware_info.get("supports_mode_4", True),
            })

        if self._detected_zones:
            entry_data.update({
                "detected_zones": list(self._detected_zones.get("detected_zones", [])),
                "sealed_zones": list(self._detected_zones.get("sealed_zones", [])),
                "detection_method": self._detected_zones.get("detection_method", "manual"),
                "detected_zones_data": self._detected_zones,
            })
            
            if "configured_areas" in self._detected_zones:
                entry_data["auto_detected_areas"] = self._detected_zones["configured_areas"]

        self._process_final_config(entry_data)

        host = entry_data[CONF_HOST]
        zones = entry_data.get(CONF_MAX_ZONES, "auto")
        areas = entry_data.get(CONF_AREAS, [1])
        
        if isinstance(areas, list):
            areas_str = ",".join(map(str, areas))
        else:
            areas_str = str(areas)

        return self.async_create_entry(
            title=f"Arrowhead ECi Panel ({host})",
            data=entry_data,
            description_placeholders={
                "host": host,
                "zones": str(zones),
                "areas": areas_str,
            }
        )

    def _process_final_config(self, entry_data: Dict[str, Any]):
        """Process and validate final configuration."""
        auto_detect = entry_data.get(CONF_AUTO_DETECT_ZONES, True)
        
        # Process areas
        areas = entry_data.get(CONF_AREAS, [1])
        if isinstance(areas, str):
            try:
                areas = [int(x.strip()) for x in areas.split(",") if x.strip().isdigit()]
            except:
                areas = [1]
        elif not isinstance(areas, list):
            areas = [1]
        
        valid_areas = [area for area in areas if isinstance(area, int) and 1 <= area <= 32]
        if not valid_areas:
            valid_areas = [1]
        
        if len(valid_areas) > 8:
            valid_areas = valid_areas[:8]
        
        entry_data[CONF_AREAS] = valid_areas
        
        # Process zones
        if auto_detect and self._detected_zones:
            detected_zones = self._detected_zones.get("detected_zones", set())
            detected_max = self._detected_zones.get("max_zone", 8)
            
            user_max = entry_data.get(CONF_MAX_ZONES)
            if user_max and user_max != detected_max:
                final_max = min(user_max, detected_max)
            else:
                final_max = detected_max
            
            entry_data[CONF_MAX_ZONES] = final_max
        
        _LOGGER.info("Final config: auto_zones=%s, max_zones=%d, areas=%s", 
                    auto_detect, entry_data[CONF_MAX_ZONES], valid_areas)

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
                default=user_input.get(CONF_PORT, DEFAULT_PORT)
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
    """Handle options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input.get("configure_zone_names", False):
                base_options = {k: v for k, v in user_input.items() if k != "configure_zone_names"}
                return await self.async_step_zone_names(base_options)
            else:
                # Validate areas before saving
                if CONF_AREAS in user_input:
                    areas_str = user_input[CONF_AREAS]
                    try:
                        areas = [int(x.strip()) for x in areas_str.split(",") if x.strip().isdigit()]
                        if len(areas) > 8:
                            areas = areas[:8]
                            user_input[CONF_AREAS] = ",".join(map(str, areas))
                    except (ValueError, AttributeError):
                        user_input[CONF_AREAS] = "1"
                        
                return self.async_create_entry(title="", data=user_input)

        # Get current configuration
        current_max_zones = self.config_entry.data.get(CONF_MAX_ZONES, 16)
        current_areas = self.config_entry.data.get(CONF_AREAS, [1])
        current_auto_detect = self.config_entry.data.get(CONF_AUTO_DETECT_ZONES, True)
        current_max_outputs = self.config_entry.data.get(CONF_MAX_OUTPUTS, DEFAULT_MAX_OUTPUTS)
        
        # Format current areas for display
        if isinstance(current_areas, list):
            display_areas = ",".join(map(str, current_areas))
        else:
            display_areas = str(current_areas)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
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
                vol.Required(
                    CONF_AREAS,
                    default=display_areas
                ): cv.string,
                vol.Optional(
                    CONF_MAX_OUTPUTS,
                    default=current_max_outputs
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
                vol.Optional(
                    "configure_zone_names",
                    default=False
                ): bool,
            }),
        )

    async def async_step_zone_names(self, base_options: Dict[str, Any]) -> FlowResult:
        """Configure zone names in options."""
        if "zone_names" in base_options:
            return self.async_create_entry(title="", data=base_options)
            
        current_zone_names = self.config_entry.options.get("zone_names", {})
        
        # Get detected zones from coordinator if available
        detected_zones = []
        
        if DOMAIN in self.hass.data and self.config_entry.entry_id in self.hass.data[DOMAIN]:
            coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]["coordinator"]
            if coordinator.data and "zones" in coordinator.data:
                detected_zones = sorted(coordinator.data["zones"].keys())[:16]
        
        if not detected_zones:
            max_zones = min(self.config_entry.data.get(CONF_MAX_ZONES, 16), 16)
            detected_zones = list(range(1, max_zones + 1))
        
        # Create schema for zone naming
        schema_dict = {}
        
        for zone_id in detected_zones:
            current_name = current_zone_names.get(f"zone_{zone_id}_name", f"Zone {zone_id:03d}")
            schema_dict[vol.Optional(f"zone_{zone_id}_name", default=current_name)] = cv.string
        
        return self.async_show_form(
            step_id="zone_names",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "zone_count": len(detected_zones),
            }
        )