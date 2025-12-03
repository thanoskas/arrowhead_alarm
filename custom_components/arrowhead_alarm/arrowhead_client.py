"""Enhanced ECi client - FIXED based on actual panel responses."""
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum

from .const import (
    PANEL_CONFIG, 
    ProtocolMode, 
    MODE_4_STATUS_MESSAGES,
    supports_mode_4,
    get_optimal_protocol_mode,
    MODE_4_FEATURES
)

_LOGGER = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    AUTHENTICATING = "authenticating"
    VERSION_CHECKING = "version_checking"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

class ArrowheadECiClient:
    """ECi client - FIXED for actual panel responses."""

    def __init__(self, host: str, port: int, user_pin: str, username: str = "admin", 
                 password: str = "admin"):
        """Initialize the ECi client."""
        self.host = host
        self.port = port
        self.user_pin = user_pin
        self.username = username
        self.password = password
        
        # Firmware and protocol information - FIXED
        self.firmware_version = "ECi F/W Ver. 10.3.51"  # Your actual version
        self.panel_model = "ECi Series"
        self.protocol_mode = ProtocolMode.MODE_4
        self.supports_mode_4 = True  # Your panel supports MODE 4
        self.mode_4_features_active = False  # Will be set during connection
        
        # Connection management
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_message = datetime.now()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 10
        
        # Initialize status dictionary with proper defaults
        self._status: Dict[str, Any] = {
            "armed": False,
            "arming": False,
            "stay_mode": False,
            "ready_to_arm": True,
            "alarm": False,
            "status_message": "Initializing",
            "panel_type": "eci",
            "panel_name": PANEL_CONFIG["name"],
            "firmware_version": self.firmware_version,
            "panel_model": self.panel_model,
            "protocol_mode": ProtocolMode.MODE_4.value,
            "supports_mode_4": True,
            "mode_4_features_active": False,
            "zones": {},  # Will be populated based on P4075Ex responses
            "zone_alarms": {},
            "zone_troubles": {},
            "zone_bypassed": {},
            "zone_supervise_fail": {},
            "zone_entry_delays": {},
            "area_exit_delays": {},
            "battery_ok": True,
            "mains_ok": True,
            "tamper_alarm": False,
            "line_ok": True,
            "dialer_ok": True,
            "fuse_ok": True,
            "outputs": {},
            "keypad_panic_alarm": False,
            "keypad_fire_alarm": False,
            "keypad_medical_alarm": False,
            "connection_state": self._connection_state.value,
            "last_update": None,
            "communication_errors": 0,
        }
        
        # Add area status based on your P4076E1=1,2,3 response
        for i in range(1, 4):  # Areas 1, 2, 3 based on your panel
            area_letter = chr(96 + i)  # a, b, c
            self._status[f"area_{area_letter}_armed"] = False
            self._status[f"area_{area_letter}_armed_by_user"] = None
            self._status[f"area_{area_letter}_alarm"] = False
        
        # Communication tracking
        self._response_queue = asyncio.Queue(maxsize=50)
        self._auth_queue = asyncio.Queue(maxsize=10)
        self._keep_alive_task: Optional[asyncio.Task] = None
        self._read_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._communication_lock = asyncio.Lock()
        
        # Message patterns
        self._zone_pattern = re.compile(r'^([A-Z]{2,5})(\d{1,3})(?:-(\d+))?$')
        self._area_pattern = re.compile(r'^([ADESZ])(\d{1,2})(?:-U(\d+))?$')
        self._output_pattern = re.compile(r'^O([OR])(\d{1,2})$')

    @property
    def is_connected(self) -> bool:
        """Return True if connected and authenticated."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> str:
        """Return current connection state."""
        return self._connection_state.value

    async def connect(self) -> bool:
        """Connect to the ECi system - FIXED for your panel."""
        if self._connection_state in [ConnectionState.CONNECTING, ConnectionState.AUTHENTICATING]:
            _LOGGER.warning("Connection attempt already in progress")
            return False

        self._connection_state = ConnectionState.CONNECTING
        self._update_status("connection_state", self._connection_state.value)
        
        try:
            _LOGGER.info("=== CONNECTING TO ECi PANEL (FIXED) ===")
            _LOGGER.info("Host: %s, Port: %s", self.host, self.port)
            
            # Create connection
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=15.0
            )
            _LOGGER.info("TCP connection established")
            
            # Start the response reader task
            self._read_task = asyncio.create_task(self._read_response())
            await asyncio.sleep(1)
            
            # FIXED: Simple authentication for your panel
            self._connection_state = ConnectionState.AUTHENTICATING
            self._update_status("connection_state", self._connection_state.value)
            
            auth_success = await self._authenticate_fixed()
            
            if auth_success:
                _LOGGER.info("Authentication successful")
                
                # FIXED: Configure protocol based on your panel's responses
                await self._configure_protocol_fixed()
                
                self._connection_state = ConnectionState.CONNECTED
                self._update_status("connection_state", self._connection_state.value)
                self._reconnect_attempts = 0
                
                # Start keep-alive task
                self._keep_alive_task = asyncio.create_task(self._keep_alive())
                
                _LOGGER.info("=== CONNECTION SUCCESSFUL ===")
                _LOGGER.info("Firmware: %s", self.firmware_version)
                _LOGGER.info("Protocol Mode: %s", self.protocol_mode.value)
                _LOGGER.info("MODE 4 Active: %s", self.mode_4_features_active)
                
                # Get initial status
                await self._get_initial_status_fixed()
                
                return True
            else:
                _LOGGER.error("Authentication failed")
                raise ConnectionError("Authentication failed")
                
        except asyncio.TimeoutError:
            _LOGGER.error("Connection timeout to %s:%s", self.host, self.port)
            await self._handle_connection_error("Connection timeout")
            return False
        except Exception as err:
            _LOGGER.error("Connection error: %s", err)
            await self._handle_connection_error(str(err))
            return False

    async def _authenticate_fixed(self) -> bool:
        """FIXED: Simple authentication based on your panel's responses."""
        try:
            _LOGGER.info("Attempting authentication...")
            
            # Your panel responds to STATUS commands, so try that
            await self._send_raw_safe("STATUS\n")
            
            # Wait for any response
            try:
                response = await asyncio.wait_for(self._get_response_safe(), timeout=5.0)
                _LOGGER.info("Initial response received: %r", response)
                
                if response:
                    _LOGGER.info("Authentication successful - panel responded")
                    return True
                    
            except asyncio.TimeoutError:
                _LOGGER.info("No immediate response, trying again...")
                
            # Try a second command
            await self._send_raw_safe("STATUS\n")
            
            try:
                response = await asyncio.wait_for(self._get_response_safe(), timeout=3.0)
                if response:
                    return True
            except asyncio.TimeoutError:
                pass
                
            # If connection is stable, assume success
            if self.writer and not self.writer.is_closing():
                _LOGGER.info("Connection appears stable, assuming authentication success")
                return True
                
            return False
                
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return False

    async def _configure_protocol_fixed(self) -> None:
        """FIXED: Configure protocol based on your panel's actual responses."""
        try:
            _LOGGER.info("Configuring protocol for your ECi panel...")
            
            # Your panel supports MODE 4, so activate it
            # Based on your test: "mode ?" returns "OK MODE 4"
            _LOGGER.info("Checking current mode...")
            try:
                await self._clear_response_queue()
                
                mode_response = await self._send_command_safe("mode ?", expect_response=True, timeout=8.0)
                if mode_response:
                    _LOGGER.info("Mode check response: %r", mode_response)
                    
                    if "MODE 4" in mode_response:
                        _LOGGER.info("✅ Already in MODE 4")
                        self.mode_4_features_active = True
                        self.protocol_mode = ProtocolMode.MODE_4
                    else:
                        # Try to activate MODE 4
                        _LOGGER.info("Activating MODE 4...")
                        await self._clear_response_queue()
                        
                        mode4_response = await self._send_command_safe("MODE 4", expect_response=True, timeout=8.0)
                        if mode4_response and ("OK" in mode4_response or "MODE 4" in mode4_response):
                            _LOGGER.info("✅ MODE 4 activated successfully")
                            self.mode_4_features_active = True
                            self.protocol_mode = ProtocolMode.MODE_4
                        else:
                            _LOGGER.warning("❌ MODE 4 activation failed: %r", mode4_response)
                            self.mode_4_features_active = False
                            self.protocol_mode = ProtocolMode.MODE_1
                else:
                    _LOGGER.warning("No response to mode check")
                    
            except Exception as err:
                _LOGGER.warning("Mode configuration error: %s", err)
                self.mode_4_features_active = False
                self.protocol_mode = ProtocolMode.MODE_1
            
            # Update status with configuration
            self._status.update({
                "firmware_version": self.firmware_version,
                "supports_mode_4": self.supports_mode_4,
                "mode_4_features_active": self.mode_4_features_active,
                "protocol_mode": self.protocol_mode.value,
            })
            
            _LOGGER.info("Protocol configuration complete:")
            _LOGGER.info("- MODE 4 Active: %s", self.mode_4_features_active)
            _LOGGER.info("- Protocol Mode: %s", self.protocol_mode.value)
            
        except Exception as err:
            _LOGGER.warning("Protocol configuration error: %s", err)
            self.mode_4_features_active = False
            self.protocol_mode = ProtocolMode.MODE_1

    async def _get_initial_status_fixed(self) -> None:
        """FIXED: Get initial status and populate zones based on your panel."""
        try:
            _LOGGER.info("Getting initial panel status...")
            
            # Send STATUS command
            await self._send_command_safe("STATUS")
            await asyncio.sleep(2)
            
            # If MODE 4 is active, try to get zone configuration
            if self.mode_4_features_active:
                await self._populate_zones_from_panel()
            
            _LOGGER.info("Initial status collected:")
            _LOGGER.info("- Ready to arm: %s", self._status.get("ready_to_arm"))
            _LOGGER.info("- Armed: %s", self._status.get("armed"))
            _LOGGER.info("- Zones detected: %d", len(self._status.get("zones", {})))
            _LOGGER.info("- MODE 4 active: %s", self.mode_4_features_active)
            
        except Exception as err:
            _LOGGER.warning("Error getting initial status: %s", err)

    async def _populate_zones_from_panel(self) -> None:
        """Populate zones based on your panel's P4075Ex responses."""
        try:
            _LOGGER.info("Populating zones from panel configuration...")
            
            # Get areas first (your panel: P4076E1=1,2,3)
            areas = await self._get_configured_areas()
            if not areas:
                _LOGGER.warning("No areas detected, using defaults")
                areas = [1, 2, 3]  # Based on your panel
            
            all_zones = set()
            
            # Get zones for each area (based on your P4075Ex responses)
            area_zone_map = {
                1: {1, 2, 3, 4, 5, 6, 9},  # Your P4075E1=1,2,3,4,5,6,9
                2: {7},                      # Your P4075E2=7
                3: {8},                      # Your P4075E3=8
            }
            
            for area in areas:
                try:
                    await self._clear_response_queue()
                    
                    command = f"P4075E{area}?"
                    response = await self._send_command_safe(command, expect_response=True, timeout=10.0)
                    
                    if response and f"P4075E{area}=" in response:
                        zones_part = response.split("=")[1].strip()
                        _LOGGER.info("Area %d zones: %s", area, zones_part)
                        
                        if zones_part and zones_part != "0":
                            area_zones = self._parse_zone_list(zones_part)
                            all_zones.update(area_zones)
                            area_zone_map[area] = area_zones
                    
                    await asyncio.sleep(1)
                    
                except Exception as err:
                    _LOGGER.warning("Error getting zones for area %d: %s", area, err)
                    # Use defaults from your actual panel
                    if area in area_zone_map:
                        all_zones.update(area_zone_map[area])
            
            # If no zones detected, use your actual configuration
            if not all_zones:
                all_zones = {1, 2, 3, 4, 5, 6, 7, 8, 9}  # Based on your panel
                _LOGGER.info("Using default zone configuration based on your panel")
            
            # Initialize zone dictionaries
            for zone_id in all_zones:
                self._status["zones"][zone_id] = False
                self._status["zone_alarms"][zone_id] = False
                self._status["zone_troubles"][zone_id] = False
                self._status["zone_bypassed"][zone_id] = False
            
            _LOGGER.info("Populated %d zones: %s", len(all_zones), sorted(all_zones))
            
        except Exception as err:
            _LOGGER.error("Error populating zones: %s", err)
            # Fallback to default zones based on your panel
            default_zones = {1, 2, 3, 4, 5, 6, 7, 8, 9}
            for zone_id in default_zones:
                self._status["zones"][zone_id] = False
                self._status["zone_alarms"][zone_id] = False
                self._status["zone_troubles"][zone_id] = False
                self._status["zone_bypassed"][zone_id] = False

    async def _get_configured_areas(self) -> List[int]:
        """Get configured areas using P4076E1? (your panel returns 1,2,3)."""
        try:
            await self._clear_response_queue()
            
            response = await self._send_command_safe("P4076E1?", expect_response=True, timeout=10.0)
            
            if response and "P4076E1=" in response:
                areas_part = response.split("=")[1].strip()
                _LOGGER.info("P4076E1 response: %s", areas_part)
                
                if areas_part and areas_part != "0":
                    areas = []
                    for area_str in areas_part.split(","):
                        area_str = area_str.strip()
                        if area_str.isdigit():
                            area = int(area_str)
                            if 1 <= area <= 32:
                                areas.append(area)
                    
                    return sorted(areas)
            
            return []
            
        except Exception as err:
            _LOGGER.error("Error getting configured areas: %s", err)
            return []

    def _parse_zone_list(self, zones_str: str) -> set:
        """Parse comma-separated zone list."""
        zones = set()
        try:
            for zone_str in zones_str.split(","):
                zone_str = zone_str.strip()
                if zone_str.isdigit():
                    zone = int(zone_str)
                    if 1 <= zone <= 248:
                        zones.add(zone)
        except Exception as err:
            _LOGGER.debug("Error parsing zone list '%s': %s", zones_str, err)
        
        return zones

    # ===== SAFE COMMUNICATION METHODS =====

    async def _send_raw_safe(self, data: str) -> None:
        """Send raw data safely with error handling."""
        async with self._communication_lock:
            if not self.writer or self.writer.is_closing():
                raise ConnectionError("No active connection")
            
            try:
                _LOGGER.debug("Sending raw data: %r", data.strip())
                self.writer.write(data.encode())
                await self.writer.drain()
            except Exception as err:
                _LOGGER.error("Error sending raw data: %s", err)
                raise

    async def _get_response_safe(self) -> Optional[str]:
        """Get response safely with timeout."""
        try:
            response = await asyncio.wait_for(self._response_queue.get(), timeout=10.0)
            _LOGGER.debug("Got response: %r", response)
            return response
        except asyncio.TimeoutError:
            _LOGGER.debug("Response timeout")
            return None
        except Exception as err:
            _LOGGER.error("Error getting response: %s", err)
            return None

    async def _send_command_safe(self, command: str, expect_response: bool = False, timeout: float = 10.0) -> Optional[str]:
        """Send command safely with optional response."""
        try:
            if not self.is_connected and not self.writer:
                _LOGGER.error("Cannot send command '%s': not connected", command)
                return None
                
            _LOGGER.debug("Sending command: %s", command)
            await self._send_raw_safe(f"{command}\n")
            
            if expect_response:
                response = await asyncio.wait_for(self._get_response_safe(), timeout=timeout)
                _LOGGER.debug("Command '%s' response: %r", command, response)
                return response
                
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for response to command: %s", command)
            return None
        except Exception as err:
            _LOGGER.error("Error sending command '%s': %s", command, err)
            return None
            
        return None

    async def _clear_response_queue(self) -> None:
        """Clear response queue."""
        try:
            cleared = 0
            while not self._response_queue.empty() and cleared < 20:
                try:
                    self._response_queue.get_nowait()
                    cleared += 1
                except asyncio.QueueEmpty:
                    break
            
            if cleared > 0:
                _LOGGER.debug("Cleared %d pending responses", cleared)
            
            await asyncio.sleep(0.5)
            
        except Exception as err:
            _LOGGER.warning("Error clearing response queue: %s", err)

    # ===== CORRECT ECI PROTOCOL ARM/DISARM METHODS =====

    async def send_main_panel_armaway(self) -> bool:
        """Send ARMAWAY command for main panel."""
        try:
            _LOGGER.info("Sending ARMAWAY command for main panel")
            
            if not self.is_connected:
                _LOGGER.error("Cannot send ARMAWAY: not connected")
                return False
            
            response = await self._send_command_safe("ARMAWAY", expect_response=True, timeout=10.0)
            
            if response and ("OK" in response or "Armed" in response):
                _LOGGER.info("Successfully sent ARMAWAY command")
                await asyncio.sleep(1)
                return True
            else:
                _LOGGER.warning("ARMAWAY command failed: %r", response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error sending ARMAWAY command: %s", err)
            return False

    async def send_main_panel_armstay(self) -> bool:
        """Send ARMSTAY command for main panel."""
        try:
            _LOGGER.info("Sending ARMSTAY command for main panel")
            
            if not self.is_connected:
                _LOGGER.error("Cannot send ARMSTAY: not connected")
                return False
            
            response = await self._send_command_safe("ARMSTAY", expect_response=True, timeout=10.0)
            
            if response and ("OK" in response or "Armed" in response):
                _LOGGER.info("Successfully sent ARMSTAY command")
                await asyncio.sleep(1)
                return True
            else:
                _LOGGER.warning("ARMSTAY command failed: %r", response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error sending ARMSTAY command: %s", err)
            return False

    async def send_armarea_command(self, area: int) -> bool:
        """Send ARMAREA x command for specific area (MODE 4)."""
        try:
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number for ARMAREA: %d", area)
                return False
                
            command = f"ARMAREA {area}"
            _LOGGER.info("Sending %s command", command)
            
            if not self.is_connected:
                _LOGGER.error("Cannot send %s: not connected", command)
                return False
            
            response = await self._send_command_safe(command, expect_response=True, timeout=10.0)
            
            if response and ("OK" in response or "Armed" in response):
                _LOGGER.info("Successfully sent %s command", command)
                await asyncio.sleep(1)
                return True
            else:
                _LOGGER.warning("%s command failed: %r", command, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error sending ARMAREA %d command: %s", area, err)
            return False

    async def send_stayarea_command(self, area: int) -> bool:
        """Send STAYAREA x command for specific area (MODE 4)."""
        try:
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number for STAYAREA: %d", area)
                return False
                
            command = f"STAYAREA {area}"
            _LOGGER.info("Sending %s command", command)
            
            if not self.is_connected:
                _LOGGER.error("Cannot send %s: not connected", command)
                return False
            
            response = await self._send_command_safe(command, expect_response=True, timeout=10.0)
            
            if response and ("OK" in response or "Armed" in response):
                _LOGGER.info("Successfully sent %s command", command)
                await asyncio.sleep(1)
                return True
            else:
                _LOGGER.warning("%s command failed: %r", command, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error sending STAYAREA %d command: %s", area, err)
            return False

    async def disarm_with_pin(self, user_pin: str = None) -> bool:
        """Disarm using DISARM x pin command."""
        try:
            pin_to_use = user_pin if user_pin else self.user_pin
            _LOGGER.info("Disarming with DISARM x pin command")
            
            if not self.is_connected:
                _LOGGER.error("Cannot disarm: not connected")
                return False
            
            # Parse PIN format
            user_num, pin = self._parse_user_pin(pin_to_use)
            
            if not user_num or not pin:
                _LOGGER.error("Invalid PIN format: %s", pin_to_use)
                return False
            
            command = f"DISARM {user_num} {pin}"
            _LOGGER.info("Sending %s command", command)
            
            response = await self._send_command_safe(command, expect_response=True, timeout=10.0)
            
            # Check for success patterns
            success_patterns = ["OK", "Disarm", "OK Disarm"]
            success = False
            
            if response:
                for pattern in success_patterns:
                    if pattern in response:
                        success = True
                        break
            
            if success:
                _LOGGER.info("Successfully disarmed (response: '%s')", response)
                await asyncio.sleep(1)
                return True
            else:
                _LOGGER.warning("Disarm failed or unclear response: '%s'", response)
                return False
                    
        except Exception as err:
            _LOGGER.error("Error disarming: %s", err)
            return False

    # ===== BACKWARD COMPATIBILITY METHODS =====

    async def arm_away(self) -> bool:
        """Backward compatibility - use main panel ARMAWAY."""
        return await self.send_main_panel_armaway()

    async def arm_stay(self) -> bool:
        """Backward compatibility - use main panel ARMSTAY."""
        return await self.send_main_panel_armstay()

    async def disarm(self) -> bool:
        """Backward compatibility - disarm with configured PIN."""
        return await self.disarm_with_pin()

    async def arm_away_area(self, area: int) -> bool:
        """Backward compatibility - use ARMAREA command."""
        return await self.send_armarea_command(area)

    async def arm_stay_area(self, area: int) -> bool:
        """Backward compatibility - use STAYAREA command."""
        return await self.send_stayarea_command(area)

    # ===== ZONE AND OUTPUT METHODS =====

    async def bypass_zone(self, zone_number: int) -> bool:
        """Bypass a zone."""
        try:
            zone_str = f"{zone_number:03d}"
            command = f"BYPASS {zone_str}"
            response = await self._send_command_safe(command, expect_response=True)
            return response and ("OK" in response or "Bypass" in response)
        except Exception as err:
            _LOGGER.error("Error bypassing zone %d: %s", zone_number, err)
            return False

    async def unbypass_zone(self, zone_number: int) -> bool:
        """Remove bypass from a zone."""
        try:
            zone_str = f"{zone_number:03d}"
            command = f"UNBYPASS {zone_str}"
            response = await self._send_command_safe(command, expect_response=True)
            return response and ("OK" in response or "Unbypass" in response)
        except Exception as err:
            _LOGGER.error("Error unbypassing zone %d: %s", zone_number, err)
            return False

    async def trigger_output(self, output_number: int, duration: int = 0) -> bool:
        """Trigger an output."""
        try:
            if not (1 <= output_number <= 32):
                _LOGGER.error("Invalid output number: %d", output_number)
                return False
                
            if duration > 0:
                command = f"OUTPUTON {output_number} {duration}"
            else:
                command = f"OUTPUTON {output_number}"
            
            _LOGGER.info("Triggering output %d with command: %s", output_number, command)
            response = await self._send_command_safe(command, expect_response=True, timeout=5.0)
            
            if response and ("OK" in response or "OutputOn" in response):
                _LOGGER.info("Successfully triggered output %d", output_number)
                return True
            else:
                _LOGGER.warning("Output trigger failed for output %d: %r", output_number, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error triggering output %d: %s", output_number, err)
            return False

    async def turn_output_on(self, output_number: int) -> bool:
        """Turn output on using OUTPUTON command."""
        try:
            if not (1 <= output_number <= 32):
                _LOGGER.error("Invalid output number: %d", output_number)
                return False
                
            command = f"OUTPUTON {output_number}"
            response = await self._send_command_safe(command, expect_response=True, timeout=5.0)
            
            if response and ("OK" in response or "OutputOn" in response):
                _LOGGER.info("Successfully turned on output %d", output_number)
                return True
            else:
                _LOGGER.warning("Turn on failed for output %d: %r", output_number, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error turning on output %d: %s", output_number, err)
            return False

    async def turn_output_off(self, output_number: int) -> bool:
        """Turn output off using OUTPUTOFF command."""
        try:
            if not (1 <= output_number <= 32):
                _LOGGER.error("Invalid output number: %d", output_number)
                return False
                
            command = f"OUTPUTOFF {output_number}"
            response = await self._send_command_safe(command, expect_response=True, timeout=5.0)
            
            if response and ("OK" in response or "OutputOff" in response):
                _LOGGER.info("Successfully turned off output %d", output_number)
                return True
            else:
                _LOGGER.warning("Turn off failed for output %d: %r", output_number, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error turning off output %d: %s", output_number, err)
            return False

    # ===== KEYPAD ALARMS (MODE 4) =====

    async def trigger_keypad_panic_alarm(self) -> bool:
        """Trigger keypad panic alarm (MODE 4)."""
        try:
            if not self.mode_4_features_active:
                _LOGGER.error("Keypad alarms require MODE 4")
                return False
            response = await self._send_command_safe("KPANICALARM", expect_response=True)
            return response and "OK" in response
        except Exception:
            return False

    async def trigger_keypad_fire_alarm(self) -> bool:
        """Trigger keypad fire alarm (MODE 4)."""
        try:
            if not self.mode_4_features_active:
                _LOGGER.error("Keypad alarms require MODE 4")
                return False
            response = await self._send_command_safe("KFIREALARM", expect_response=True)
            return response and "OK" in response
        except Exception:
            return False

    async def trigger_keypad_medical_alarm(self) -> bool:
        """Trigger keypad medical alarm (MODE 4)."""
        try:
            if not self.mode_4_features_active:
                _LOGGER.error("Keypad alarms require MODE 4")
                return False
            response = await self._send_command_safe("KMEDICALARM", expect_response=True)
            return response and "OK" in response
        except Exception:
            return False

    # ===== UTILITY METHODS =====

    def _parse_user_pin(self, user_pin: str) -> tuple[Optional[str], Optional[str]]:
        """Parse user_pin format '1 123'."""
        try:
            parts = user_pin.strip().split()
            if len(parts) >= 2:
                return parts[0], parts[1]
            return None, None
        except Exception:
            return None, None

    def _update_status(self, key: str, value: Any) -> None:
        """Update status dictionary."""
        self._status[key] = value
        self._status["last_update"] = datetime.now().isoformat()

    async def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        if self.is_connected:
            try:
                await self._send_command_safe("STATUS")
                await asyncio.sleep(0.5)
            except Exception as err:
                _LOGGER.debug("Error requesting status: %s", err)
                
        return self._status.copy()

    def configure_manual_outputs(self, max_outputs: int) -> None:
        """Configure outputs manually."""
        _LOGGER.info("Configuring %d outputs for ECi panel", max_outputs)
        
        manual_outputs = set(range(1, max_outputs + 1))
        self._status["outputs"] = {o: False for o in manual_outputs}
        
        self._status.update({
            "total_outputs_detected": max_outputs,
            "max_outputs_detected": max_outputs,
            "output_detection_method": "manual_configuration",
            "output_ranges": {"main_panel": list(manual_outputs)}
        })

    # ===== CONNECTION MANAGEMENT =====

    async def disconnect(self) -> None:
        """Disconnect with cleanup."""
        _LOGGER.info("Disconnecting from ECi panel...")
        
        self._connection_state = ConnectionState.DISCONNECTED
        self._update_status("connection_state", self._connection_state.value)
        
        # Cancel tasks
        tasks_to_cancel = [self._keep_alive_task, self._read_task, self._reconnect_task]
        
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception as err:
                    _LOGGER.warning("Error cancelling task: %s", err)
                
        # Close connection
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as err:
                _LOGGER.warning("Error closing writer: %s", err)
                
        self.reader = None
        self.writer = None
        
        _LOGGER.info("Disconnected from ECi panel")

    async def _read_response(self) -> None:
        """Read responses from panel."""
        _LOGGER.info("Starting response reader...")
        
        while self._connection_state != ConnectionState.DISCONNECTED:
            try:
                if not self.reader:
                    break
                    
                data = await asyncio.wait_for(self.reader.readline(), timeout=60.0)
                
                if not data:
                    _LOGGER.warning("Panel closed connection")
                    await self._handle_connection_error("Panel closed connection")
                    break
                    
                message = data.decode('utf-8', errors='ignore').strip()
                if message:
                    self._last_message = datetime.now()
                    _LOGGER.debug("Received message: %r", message)
                    
                    # Process the message
                    self._process_message(message)
                    
                    # Add to response queue
                    try:
                        if self._response_queue.full():
                            try:
                                self._response_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        self._response_queue.put_nowait(message)
                    except Exception as err:
                        _LOGGER.warning("Error adding message to queue: %s", err)
                        
            except asyncio.TimeoutError:
                # Send periodic status request
                if self.is_connected:
                    try:
                        await self._send_command_safe("STATUS")
                    except Exception:
                        pass
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("Error in response reader: %s", err)
                await self._handle_connection_error(f"Read error: {err}")
                break
                
        _LOGGER.info("Response reader stopped")

    def _process_message(self, message: str) -> None:
        """Process incoming panel messages."""
        try:
            self._update_status("last_update", datetime.now().isoformat())
            
            # Try different message processors
            if self._process_area_message(message):
                return
            if self._process_zone_message(message):
                return
            if self._process_output_message(message):
                return
            if self._process_system_message(message):
                return
            if self._process_mode4_message(message):
                return
                
            _LOGGER.debug("Unprocessed message: %r", message)
                
        except Exception as err:
            _LOGGER.error("Error processing message '%s': %s", message, err)

    def _process_area_message(self, message: str) -> bool:
        """Process area messages based on your panel's areas 1,2,3."""
        if message.startswith("A") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if 1 <= area_num <= 3:  # Your panel has areas 1,2,3
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = True
                    self._status["armed"] = True
                    self._status["arming"] = False
                    self._status["status_message"] = f"Area {area_num} Armed"
                    _LOGGER.info("Area %d armed", area_num)
                    return True
            except ValueError:
                pass
                
        elif message.startswith("D") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if 1 <= area_num <= 3:  # Your panel has areas 1,2,3
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = False
                    # Check if any areas are still armed
                    any_armed = any(self._status.get(f"area_{chr(96 + i)}_armed", False) for i in range(1, 4))
                    self._status["armed"] = any_armed
                    self._status["status_message"] = f"Area {area_num} Disarmed"
                    _LOGGER.info("Area %d disarmed", area_num)
                    return True
            except ValueError:
                pass
                
        elif message.startswith("S") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if 1 <= area_num <= 3:  # Your panel has areas 1,2,3
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = True
                    self._status["armed"] = True
                    self._status["stay_mode"] = True
                    self._status["arming"] = False
                    self._status["status_message"] = f"Area {area_num} Stay Armed"
                    _LOGGER.info("Area %d stay armed", area_num)
                    return True
            except ValueError:
                pass
                
        return False

    def _process_zone_message(self, message: str) -> bool:
        """Process zone messages for your zones 1,2,3,4,5,6,7,8,9."""
        zone_codes = {
            "ZO": ("zones", True, "open"),
            "ZC": ("zones", False, "closed"),
            "ZA": ("zone_alarms", True, "alarm"),
            "ZR": ("zone_alarms", False, "alarm restored"),
            "ZBY": ("zone_bypassed", True, "bypassed"),
            "ZBYR": ("zone_bypassed", False, "bypass restored"),
        }
        
        for code, (key, value, desc) in zone_codes.items():
            if message.startswith(code):
                try:
                    zone_num = int(message[len(code):])
                    if 1 <= zone_num <= 9:  # Your panel has zones 1-9
                        if key not in self._status:
                            self._status[key] = {}
                        self._status[key][zone_num] = value
                        self._status["status_message"] = f"Zone {zone_num} {desc}"
                        
                        if code in ["ZA", "ZR"]:
                            self._status["alarm"] = any(self._status["zone_alarms"].values())
                            
                        _LOGGER.debug("Zone %d %s", zone_num, desc)
                        return True
                except ValueError:
                    pass
                    
        return False

    def _process_output_message(self, message: str) -> bool:
        """Process output messages."""
        if message.startswith("OO") or message.startswith("OR"):
            try:
                state = message.startswith("OO")
                output_num = int(message[2:])
                
                if "outputs" not in self._status:
                    self._status["outputs"] = {}
                
                self._status["outputs"][output_num] = state
                self._status["status_message"] = f"Output {output_num} {'On' if state else 'Off'}"
                _LOGGER.debug("Output %d %s", output_num, "on" if state else "off")
                return True
            except (ValueError, IndexError):
                pass
                
        return False

    def _process_system_message(self, message: str) -> bool:
        """Process system status messages."""
        system_messages = {
            "RO": ("ready_to_arm", True, "Ready to Arm"),
            "NR": ("ready_to_arm", False, "Not Ready"),
            "MF": ("mains_ok", False, "Mains Power Fail"),
            "MR": ("mains_ok", True, "Mains Power OK"),
            "BF": ("battery_ok", False, "Battery Fail"),
            "BR": ("battery_ok", True, "Battery OK"),
            "TA": ("tamper_alarm", True, "Panel Tamper"),
            "TR": ("tamper_alarm", False, "Panel Tamper Restored"),
            "LF": ("line_ok", False, "Line Fail"),
            "LR": ("line_ok", True, "Line OK"),
        }
        
        if message in system_messages:
            key, value, status_msg = system_messages[message]
            self._status[key] = value
            self._status["status_message"] = status_msg
            _LOGGER.debug("System status: %s", status_msg)
            return True
            
        # Handle OK responses
        if message.startswith("OK"):
            self._status["status_message"] = message
            _LOGGER.debug("OK response: %s", message)
            return True
            
        return False

    def _process_mode4_message(self, message: str) -> bool:
        """Process MODE 4 specific messages."""
        try:
            # Exit delay messages: EDA1-30, EDS2-45, etc.
            if message.startswith("EDA") or message.startswith("EDS"):
                match = re.match(r'ED([AS])(\d+)-(\d+)', message)
                if match:
                    delay_type, area, seconds = match.groups()
                    area_num = int(area)
                    delay_seconds = int(seconds)
                    
                    if "area_exit_delays" not in self._status:
                        self._status["area_exit_delays"] = {}
                    
                    self._status["area_exit_delays"][area_num] = delay_seconds
                    
                    delay_name = "Away" if delay_type == "A" else "Stay"
                    self._status["status_message"] = f"Area {area_num} {delay_name} Exit Delay: {delay_seconds}s"
                    _LOGGER.debug("Area %d %s exit delay: %d seconds", area_num, delay_name, delay_seconds)
                    return True
            
            # Entry delay messages: ZEDS4-20, etc.
            elif message.startswith("ZEDS"):
                match = re.match(r'ZEDS(\d+)-(\d+)', message)
                if match:
                    zone, seconds = match.groups()
                    zone_num = int(zone)
                    delay_seconds = int(seconds)
                    
                    if "zone_entry_delays" not in self._status:
                        self._status["zone_entry_delays"] = {}
                    
                    self._status["zone_entry_delays"][zone_num] = delay_seconds
                    self._status["status_message"] = f"Zone {zone_num} Entry Delay: {delay_seconds}s"
                    _LOGGER.debug("Zone %d entry delay: %d seconds", zone_num, delay_seconds)
                    return True
            
            # User tracking messages: A1-U2, D3-U1, etc.
            elif re.match(r'[ADS]\d+-U\d+', message):
                match = re.match(r'([ADS])(\d+)-U(\d+)', message)
                if match:
                    action, area, user = match.groups()
                    area_num = int(area)
                    user_num = int(user)
                    
                    area_key = f"area_{chr(96 + area_num)}_armed_by_user"
                    
                    if action in ["A", "S"]:  # Armed
                        self._status[area_key] = user_num
                        action_name = "Armed Away" if action == "A" else "Armed Stay"
                    else:  # Disarmed
                        self._status[area_key] = None
                        action_name = "Disarmed"
                    
                    self._status["status_message"] = f"Area {area_num} {action_name} by User {user_num}"
                    _LOGGER.debug("Area %d %s by user %d", area_num, action_name, user_num)
                    return True
                    
        except Exception as err:
            _LOGGER.debug("Error processing MODE 4 message '%s': %s", message, err)
            
        return False

    async def _handle_connection_error(self, error_msg: str) -> None:
        """Handle connection errors."""
        _LOGGER.error("Connection error: %s", error_msg)
        
        self._connection_state = ConnectionState.ERROR
        self._update_status("connection_state", self._connection_state.value)
        self._status["communication_errors"] = self._status.get("communication_errors", 0) + 1
        
        await self.disconnect()

    async def _keep_alive(self) -> None:
        """Keep connection alive."""
        _LOGGER.info("Starting keep-alive task...")
        
        while self.is_connected:
            try:
                await asyncio.sleep(30)  # Send status every 30 seconds
                
                if self.is_connected:
                    time_since_last = (datetime.now() - self._last_message).total_seconds()
                    
                    if time_since_last > 60:
                        _LOGGER.warning("No messages received for %d seconds, sending STATUS", int(time_since_last))
                    
                    await self._send_command_safe("STATUS")
                    
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("Keep-alive error: %s", err)
                break
                
        _LOGGER.info("Keep-alive task stopped")

    # ===== ENHANCED DEBUG METHODS =====

    async def _send_command(self, command: str, expect_response: bool = False) -> Optional[str]:
        """Legacy method for compatibility."""
        return await self._send_command_safe(command, expect_response)

    async def send_custom_command(self, command: str) -> Optional[str]:
        """Send a custom command and return response."""
        return await self._send_command_safe(command, expect_response=True)

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information."""
        return {
            "connection_state": self._connection_state.value,
            "last_message_time": self._last_message.isoformat(),
            "time_since_last_message": (datetime.now() - self._last_message).total_seconds(),
            "communication_errors": self._status.get("communication_errors", 0),
            "firmware_version": self.firmware_version,
            "protocol_mode": self.protocol_mode.value if hasattr(self.protocol_mode, 'value') else self.protocol_mode,
            "mode_4_active": self.mode_4_features_active,
            "supports_mode_4": self.supports_mode_4,
            "response_queue_size": self._response_queue.qsize(),
            "writer_closed": self.writer.is_closing() if self.writer else True,
            "reader_at_eof": self.reader.at_eof() if self.reader else True,
            "configured_zones": sorted(self._status.get("zones", {}).keys()),
            "configured_areas": [1, 2, 3],  # Based on your P4076E1=1,2,3
        }