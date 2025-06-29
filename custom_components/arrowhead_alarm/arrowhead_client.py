"""Enhanced ECi client using ONLY MODE 4 commands with PIN requirements."""
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
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
    """ECi client using ONLY MODE 4 commands (ARMAREA, STAYAREA, DISARM with PIN)."""

    def __init__(self, host: str, port: int, user_pin: str, username: str = "admin", 
                 password: str = "admin"):
        """Initialize the ECi client for MODE 4 operation."""
        self.host = host
        self.port = port
        self.user_pin = user_pin
        self.username = username
        self.password = password
        
        # Firmware and protocol information
        self.firmware_version = None
        self.panel_model = None
        self.protocol_mode = ProtocolMode.MODE_4  # Force MODE 4
        self.supports_mode_4 = False
        self.mode_4_features_active = False
        self.areas_configured_at_p74e = False  # P74E (away) areas configured
        self.areas_configured_at_p76e = False  # P76E (stay) areas configured
        
        # Connection management
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_message = datetime.now()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 30
        
        # Initialize status dictionary optimized for ECi
        self._status: Dict[str, Any] = {
            # Basic alarm states
            "armed": False,
            "arming": False,
            "stay_mode": False,
            "ready_to_arm": False,
            "alarm": False,
            "status_message": "Unknown",
            "panel_type": "eci",
            "panel_name": PANEL_CONFIG["name"],
            
            # Firmware and protocol information
            "firmware_version": None,
            "panel_model": None,
            "protocol_mode": ProtocolMode.MODE_4.value,
            "supports_mode_4": False,
            "mode_4_features_active": False,
            "mode_4_only": True,  # This client only uses MODE 4
            
            # P74E/P76E configuration status
            "areas_configured_p74e": False,
            "areas_configured_p76e": False,
            
            # Enhanced area status (up to 32 areas for ECi)
            **{f"area_{chr(97 + i)}_armed": False for i in range(32)},  # area_a_armed to area_af_armed
            
            # Enhanced area status with MODE 4 user tracking
            **{f"area_{chr(97 + i)}_armed_by_user": None for i in range(32)},
            **{f"area_{chr(97 + i)}_alarm": False for i in range(32)},
            
            # Zone states (up to 248 for ECi)
            "zones": {},  # Will be populated based on detection
            "zone_alarms": {},
            "zone_troubles": {},
            "zone_bypassed": {},
            "zone_supervise_fail": {},  # ECi doesn't have RF, but kept for compatibility
            
            # Enhanced zone timing (MODE 4)
            "zone_entry_delays": {},  # zone_id: remaining_seconds
            "area_exit_delays": {},   # area_id: remaining_seconds
            
            # System states
            "battery_ok": True,
            "mains_ok": True,
            "tamper_alarm": False,
            "line_ok": True,
            "dialer_ok": True,
            "fuse_ok": True,
            "code_tamper": False,
            "dialer_active": False,
            
            # Outputs status
            "outputs": {},
            
            # MODE 4 Keypad alarms
            "keypad_panic_alarm": False,
            "keypad_fire_alarm": False,
            "keypad_medical_alarm": False,
            
            # Connection info
            "connection_state": self._connection_state.value,
            "last_update": None,
            "communication_errors": 0,
        }
        
        # Async tasks and queues
        self._response_queue = asyncio.Queue()
        self._auth_queue = asyncio.Queue()
        self._keep_alive_task: Optional[asyncio.Task] = None
        self._read_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        
        # Enhanced message parsing patterns for MODE 4
        self._zone_pattern = re.compile(r'^([A-Z]{2,5})(\d{1,3})(?:-(\d+))?$')  # Support timing info
        self._area_pattern = re.compile(r'^([ADESZ])(\d{1,2})(?:-U(\d+))?$')  # Support user tracking
        self._output_pattern = re.compile(r'^O([OR])(\d{1,2})$')
        self._version_pattern = re.compile(r'OK Version "(.+?)"')

    @property
    def is_connected(self) -> bool:
        """Return True if connected and authenticated."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> str:
        """Return current connection state."""
        return self._connection_state.value

    async def connect(self) -> bool:
        """Connect to the ECi system and force MODE 4."""
        if self._connection_state in [ConnectionState.CONNECTING, ConnectionState.AUTHENTICATING, ConnectionState.VERSION_CHECKING]:
            _LOGGER.warning("Connection attempt already in progress")
            return False

        self._connection_state = ConnectionState.CONNECTING
        self._update_status("connection_state", self._connection_state.value)
        
        try:
            _LOGGER.info("Connecting to ECi panel at %s:%s (MODE 4 ONLY)", self.host, self.port)
            
            # Create connection with timeout
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=10.0
            )
            
            # Start the response reader task
            self._read_task = asyncio.create_task(self._read_response())
            
            # Attempt authentication
            self._connection_state = ConnectionState.AUTHENTICATING
            self._update_status("connection_state", self._connection_state.value)
            
            auth_success = await self._authenticate()
            
            if auth_success:
                # Force MODE 4 and verify configuration
                await self._force_mode_4_and_verify()
                
                self._connection_state = ConnectionState.CONNECTED
                self._update_status("connection_state", self._connection_state.value)
                self._reconnect_attempts = 0
                
                # Start keep-alive task
                self._keep_alive_task = asyncio.create_task(self._keep_alive())
                
                _LOGGER.info("Successfully connected to ECi panel in MODE 4 ONLY mode")
                _LOGGER.info("P74E areas configured: %s, P76E areas configured: %s", 
                           self.areas_configured_at_p74e, self.areas_configured_at_p76e)
                return True
            else:
                raise ConnectionError("Authentication failed")
                
        except asyncio.TimeoutError:
            _LOGGER.error("Connection timeout to %s:%s", self.host, self.port)
            await self._handle_connection_error("Connection timeout")
            return False
        except Exception as err:
            _LOGGER.error("Connection error: %s", err)
            await self._handle_connection_error(str(err))
            return False

    async def _force_mode_4_and_verify(self) -> None:
        """Force MODE 4 and verify P74E/P76E configuration."""
        try:
            _LOGGER.info("Forcing MODE 4 and verifying configuration...")
            
            # Get firmware version first
            response = await self._send_command("VERSION", expect_response=True)
            if response:
                version_match = re.search(r'Version\s+"?([^"]+)"?', response)
                if version_match:
                    self.firmware_version = version_match.group(1)
                    _LOGGER.info("Detected firmware version: %s", self.firmware_version)
                    
                    # Check if MODE 4 is supported
                    if supports_mode_4(self.firmware_version):
                        self.supports_mode_4 = True
                        _LOGGER.info("MODE 4 supported by firmware %s", self.firmware_version)
                    else:
                        _LOGGER.error("MODE 4 NOT supported by firmware %s - requires 10.3.50+", self.firmware_version)
                        raise ConnectionError(f"MODE 4 not supported by firmware {self.firmware_version}")
            
            # Force switch to MODE 4
            _LOGGER.info("Switching to MODE 4...")
            mode_response = await self._send_command("MODE 4", expect_response=True)
            if mode_response and "OK" in mode_response:
                self.protocol_mode = ProtocolMode.MODE_4
                self.mode_4_features_active = True
                _LOGGER.info("Successfully switched to MODE 4")
            else:
                _LOGGER.error("Failed to switch to MODE 4: %r", mode_response)
                raise ConnectionError("Cannot switch to MODE 4")
            
            # Verify P74E and P76E configuration
            await self._verify_area_configuration()
                
            # Update status with protocol information
            self._status.update({
                "firmware_version": self.firmware_version,
                "protocol_mode": self.protocol_mode.value,
                "supports_mode_4": self.supports_mode_4,
                "mode_4_features_active": self.mode_4_features_active,
                "areas_configured_p74e": self.areas_configured_at_p74e,
                "areas_configured_p76e": self.areas_configured_at_p76e,
            })
            
            _LOGGER.info("MODE 4 configuration complete")
            
        except Exception as err:
            _LOGGER.error("Error configuring MODE 4: %s", err)
            raise ConnectionError(f"MODE 4 configuration failed: {err}")

    async def _verify_area_configuration(self) -> None:
        """Verify that areas are configured at P74E and P76E."""
        try:
            _LOGGER.info("Verifying P74E and P76E area configuration...")
            
            # Check P74E (required for ARMAREA)
            try:
                p74e_response = await self._send_command("P74E?", expect_response=True)
                if p74e_response and "P74E=" in p74e_response:
                    areas_str = p74e_response.split("P74E=")[1].strip()
                    if areas_str and areas_str != "0":
                        self.areas_configured_at_p74e = True
                        _LOGGER.info("P74E areas configured: %s", areas_str)
                    else:
                        _LOGGER.warning("No areas configured at P74E - ARMAREA commands will fail")
                else:
                    _LOGGER.warning("Could not query P74E configuration")
            except Exception as err:
                _LOGGER.warning("Error checking P74E: %s", err)
            
            # Check P76E (required for STAYAREA)  
            try:
                p76e_response = await self._send_command("P76E?", expect_response=True)
                if p76e_response and "P76E=" in p76e_response:
                    areas_str = p76e_response.split("P76E=")[1].strip()
                    if areas_str and areas_str != "0":
                        self.areas_configured_at_p76e = True
                        _LOGGER.info("P76E areas configured: %s", areas_str)
                    else:
                        _LOGGER.warning("No areas configured at P76E - STAYAREA commands will fail")
                else:
                    _LOGGER.warning("Could not query P76E configuration")
            except Exception as err:
                _LOGGER.warning("Error checking P76E: %s", err)
                
            # Log configuration warnings
            if not self.areas_configured_at_p74e:
                _LOGGER.error("WARNING: P74E not configured - ARMAREA commands will not work!")
            if not self.areas_configured_at_p76e:
                _LOGGER.error("WARNING: P76E not configured - STAYAREA commands will not work!")
                
        except Exception as err:
            _LOGGER.error("Error verifying area configuration: %s", err)

    async def _authenticate(self) -> bool:
        """Authenticate with ECi panel."""
        try:
            # ECi panels typically don't require login, try direct communication
            timeout = 3.0
            
            try:
                initial_response = await asyncio.wait_for(
                    self._get_next_response(), 
                    timeout=timeout
                )
                
                if "login:" in initial_response.lower():
                    return await self._handle_login_authentication(initial_response)
                else:
                    return await self._handle_direct_authentication()
            except asyncio.TimeoutError:
                return await self._handle_direct_authentication()
                
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return False

    async def _handle_login_authentication(self, initial_response: str) -> bool:
        """Handle login-based authentication."""
        try:
            await self._send_raw(f"{self.username}\n")
            
            password_prompt = await asyncio.wait_for(
                self._get_next_response(), 
                timeout=3.0
            )
            
            if "password:" in password_prompt.lower():
                await self._send_raw(f"{self.password}\n")
                
                welcome_msg = await asyncio.wait_for(
                    self._get_next_response(), 
                    timeout=3.0
                )
                
                if any(word in welcome_msg.lower() for word in ["welcome", "ready", "ok"]):
                    return True
                    
        except asyncio.TimeoutError:
            pass
            
        return False

    async def _handle_direct_authentication(self) -> bool:
        """Handle direct communication without login."""
        try:
            await self._send_raw("STATUS\n")
            
            response = await asyncio.wait_for(
                self._get_next_response(), 
                timeout=5.0
            )
            
            return bool(response)
                
        except asyncio.TimeoutError:
            pass
            
        return False

    # ===== MODE 4 ONLY ARM/DISARM METHODS =====

    async def arm_away_area(self, area: int) -> bool:
        """Arm specific area in away mode using ARMAREA command (MODE 4 only)."""
        try:
            _LOGGER.info("MODE 4: Arming area %d away using ARMAREA command", area)
            
            if not self.is_connected:
                _LOGGER.error("Cannot arm area %d: not connected to panel", area)
                return False
            
            if not self.mode_4_features_active:
                _LOGGER.error("MODE 4 not active - ARMAREA command not available")
                return False
                
            if not self.areas_configured_at_p74e:
                _LOGGER.error("Cannot use ARMAREA - areas not configured at P74E")
                return False
            
            # Validate area range (1-32 per protocol docs)
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number: %d (must be 1-32)", area)
                return False
            
            # Use ARMAREA command (MODE 4 only)
            command = f"ARMAREA {area}"
            _LOGGER.info("Sending MODE 4 command: %s", command)
            
            response = await self._send_command(command, expect_response=True)
            _LOGGER.info("ARMAREA response: %r", response)
            
            if response and "OK" in response:
                _LOGGER.info("ARMAREA %d successful", area)
                await asyncio.sleep(2)  # Wait for status update
                return True
            else:
                _LOGGER.error("ARMAREA %d failed: %r", area, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error in ARMAREA command for area %d: %s", area, err)
            return False

    async def arm_stay_area(self, area: int) -> bool:
        """Arm specific area in stay mode using STAYAREA command (MODE 4 only)."""
        try:
            _LOGGER.info("MODE 4: Arming area %d stay using STAYAREA command", area)
            
            if not self.is_connected:
                _LOGGER.error("Cannot arm area %d: not connected to panel", area)
                return False
            
            if not self.mode_4_features_active:
                _LOGGER.error("MODE 4 not active - STAYAREA command not available")
                return False
                
            if not self.areas_configured_at_p76e:
                _LOGGER.error("Cannot use STAYAREA - areas not configured at P76E")
                return False
            
            # Validate area range (1-32 per protocol docs)
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number: %d (must be 1-32)", area)
                return False
            
            # Use STAYAREA command (MODE 4 only)
            command = f"STAYAREA {area}"
            _LOGGER.info("Sending MODE 4 command: %s", command)
            
            response = await self._send_command(command, expect_response=True)
            _LOGGER.info("STAYAREA response: %r", response)
            
            if response and "OK" in response:
                _LOGGER.info("STAYAREA %d successful", area)
                await asyncio.sleep(2)  # Wait for status update
                return True
            else:
                _LOGGER.error("STAYAREA %d failed: %r", area, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error in STAYAREA command for area %d: %s", area, err)
            return False

    async def disarm_with_pin(self, user_pin: str = None) -> bool:
        """Disarm using DISARM x pin command (always requires PIN)."""
        try:
            # Use provided PIN or fall back to configured PIN
            pin_to_use = user_pin if user_pin else self.user_pin
            
            _LOGGER.info("MODE 4: Disarming with user PIN")
            
            if not self.is_connected:
                _LOGGER.error("Cannot disarm: not connected to panel")
                return False
            
            if not self.mode_4_features_active:
                _LOGGER.error("MODE 4 not active - DISARM command may not work properly")
                return False
            
            # Parse user_pin to extract user number and pin
            user_num, pin = self._parse_user_pin(pin_to_use)
            
            if not user_num or not pin:
                _LOGGER.error("Invalid user PIN format: %s (expected 'user pin', e.g., '1 123')", pin_to_use)
                return False
            
            # Validate user number range (1-2000 per protocol docs)
            try:
                user_number = int(user_num)
                if not (1 <= user_number <= 2000):
                    _LOGGER.error("Invalid user number: %d (must be 1-2000)", user_number)
                    return False
            except ValueError:
                _LOGGER.error("Invalid user number format: %s", user_num)
                return False
            
            # Use DISARM x pin command (MODE 4)
            command = f"DISARM {user_num} {pin}"
            _LOGGER.info("Sending MODE 4 command: DISARM %s [PIN_HIDDEN]", user_num)
            
            response = await self._send_command(command, expect_response=True)
            _LOGGER.info("DISARM response: %r", response)
            
            if response and "OK" in response:
                _LOGGER.info("DISARM successful")
                await asyncio.sleep(2)  # Wait for status update
                return True
            else:
                _LOGGER.error("DISARM failed: %r", response)
                return False
                
        except Exception as err:
            _LOGGER.error("Error in DISARM command: %s", err)
            return False

    # ===== GENERAL ARM/DISARM METHODS (deprecated - use area-specific) =====

    async def arm_away(self) -> bool:
        """Arm away - deprecated, use arm_away_area instead."""
        _LOGGER.warning("arm_away() is deprecated in MODE 4 - use arm_away_area() instead")
        # Default to area 1 for backward compatibility
        return await self.arm_away_area(1)

    async def arm_stay(self) -> bool:
        """Arm stay - deprecated, use arm_stay_area instead."""
        _LOGGER.warning("arm_stay() is deprecated in MODE 4 - use arm_stay_area() instead")
        # Default to area 1 for backward compatibility
        return await self.arm_stay_area(1)

    async def disarm(self) -> bool:
        """Disarm - deprecated, use disarm_with_pin instead."""
        _LOGGER.warning("disarm() is deprecated in MODE 4 - use disarm_with_pin() instead")
        return await self.disarm_with_pin()

    # ===== MODE 4 KEYPAD ALARM METHODS =====

    async def trigger_keypad_panic_alarm(self) -> bool:
        """Trigger keypad panic alarm (MODE 4 only)."""
        if not self.mode_4_features_active:
            _LOGGER.warning("Keypad alarms require MODE 4")
            return False
        
        try:
            response = await self._send_command("KPANICALARM", expect_response=True)
            return response and "OK" in response
        except Exception as err:
            _LOGGER.error("Error triggering keypad panic alarm: %s", err)
            return False

    async def trigger_keypad_fire_alarm(self) -> bool:
        """Trigger keypad fire alarm (MODE 4 only)."""
        if not self.mode_4_features_active:
            _LOGGER.warning("Keypad alarms require MODE 4")
            return False
        
        try:
            response = await self._send_command("KFIREALARM", expect_response=True)
            return response and "OK" in response
        except Exception as err:
            _LOGGER.error("Error triggering keypad fire alarm: %s", err)
            return False

    async def trigger_keypad_medical_alarm(self) -> bool:
        """Trigger keypad medical alarm (MODE 4 only)."""
        if not self.mode_4_features_active:
            _LOGGER.warning("Keypad alarms require MODE 4")
            return False
        
        try:
            response = await self._send_command("KMEDICALARM", expect_response=True)
            return response and "OK" in response
        except Exception as err:
            _LOGGER.error("Error triggering keypad medical alarm: %s", err)
            return False

    # ===== ZONE BYPASS METHODS =====

    async def bypass_zone(self, zone_number: int) -> bool:
        """Bypass a zone."""
        try:
            # Format zone number with leading zeros as per protocol (xxx = 001 -- 248)
            zone_str = f"{zone_number:03d}"
            command = f"BYPASS {zone_str}"
            _LOGGER.info("Sending bypass command: %s", command)
            await self._send_command(command)
            return True
        except Exception as err:
            _LOGGER.error("Error bypassing zone %d: %s", zone_number, err)
            return False

    async def unbypass_zone(self, zone_number: int) -> bool:
        """Remove bypass from a zone."""
        try:
            # Format zone number with leading zeros as per protocol (xxx = 001 -- 248)
            zone_str = f"{zone_number:03d}"
            command = f"UNBYPASS {zone_str}"
            _LOGGER.info("Sending unbypass command: %s", command)
            await self._send_command(command)
            return True
        except Exception as err:
            _LOGGER.error("Error unbypassing zone %d: %s", zone_number, err)
            return False

    # ===== OUTPUT CONTROL METHODS =====

    async def trigger_output(self, output_number: int, duration: int = 0) -> bool:
        """Trigger an output for specified duration (0 = toggle)."""
        try:
            if output_number > PANEL_CONFIG["max_outputs"]:
                return False
                
            if duration > 0:
                # Trigger for specific duration (seconds)
                await self._send_command(f"OUTPUTON {output_number} {duration}")
            else:
                # Toggle output
                await self._send_command(f"OUTPUTON {output_number}")
            return True
        except Exception:
            return False

    async def turn_output_on(self, output_number: int) -> bool:
        """Turn output on permanently."""
        try:
            if output_number > PANEL_CONFIG["max_outputs"]:
                return False
            await self._send_command(f"OUTPUTON {output_number}")
            return True
        except Exception:
            return False

    async def turn_output_off(self, output_number: int) -> bool:
        """Turn output off."""
        try:
            if output_number > PANEL_CONFIG["max_outputs"]:
                return False
            await self._send_command(f"OUTPUTOFF {output_number}")
            return True
        except Exception:
            return False

    # ===== UTILITY METHODS =====

    def _parse_user_pin(self, user_pin: str) -> tuple[Optional[str], Optional[str]]:
        """Parse user_pin format '1 123' into user number and PIN."""
        try:
            parts = user_pin.strip().split()
            if len(parts) >= 2:
                return parts[0], parts[1]
            else:
                _LOGGER.warning("Invalid user_pin format '%s'", user_pin)
                return None, None
        except Exception as err:
            _LOGGER.error("Error parsing user_pin '%s': %s", user_pin, err)
            return None, None

    def _update_status(self, key: str, value: Any) -> None:
        """Update status dictionary."""
        self._status[key] = value

    async def get_status(self) -> Dict[str, Any]:
        """Get current status."""
        if self.is_connected:
            try:
                await self._send_command("STATUS")
            except Exception:
                pass
                
        return self._status.copy()

    def configure_manual_outputs(self, max_outputs: int) -> None:
        """Configure outputs manually based on user selection."""
        _LOGGER.info("Configuring %d outputs for ECi panel (MODE 4)", max_outputs)
        
        manual_outputs = set(range(1, max_outputs + 1))
        self._status["outputs"] = {o: False for o in manual_outputs}
        
        self._status.update({
            "total_outputs_detected": max_outputs,
            "max_outputs_detected": max_outputs,
            "output_detection_method": "manual_configuration",
            "output_ranges": {"main_panel": list(manual_outputs)}
        })

    # Include all standard helper methods (connect, disconnect, message processing, etc.)
    # [Rest of the methods remain the same as previous version]
    
    async def disconnect(self) -> None:
        """Disconnect with proper cleanup."""
        self._connection_state = ConnectionState.DISCONNECTED
        self._update_status("connection_state", self._connection_state.value)
        
        for task in [self._keep_alive_task, self._read_task, self._reconnect_task]:
            if task and not task.done():
                task.cancel()
                
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
                
        self.reader = None
        self.writer = None

    async def _send_raw(self, data: str) -> None:
        """Send raw data to the connection."""
        if not self.writer:
            raise ConnectionError("No active connection")
        self.writer.write(data.encode())
        await self.writer.drain()

    async def _get_next_response(self) -> str:
        """Get next response from queue."""
        auth_task = asyncio.create_task(self._auth_queue.get())
        resp_task = asyncio.create_task(self._response_queue.get())
        
        done, pending = await asyncio.wait(
            [auth_task, resp_task], 
            return_when=asyncio.FIRST_COMPLETED,
            timeout=10.0
        )
        
        for task in pending:
            task.cancel()
            
        if done:
            return list(done)[0].result()
        else:
            raise asyncio.TimeoutError("No response received")

    async def _send_command(self, command: str, expect_response: bool = False) -> Optional[str]:
        """Send command with enhanced error handling."""
        if not self.is_connected:
            raise ConnectionError("Not connected to ECi panel")
            
        try:
            _LOGGER.debug("Sending command: %s", command)
            await self._send_raw(f"{command}\n")
            
            if expect_response:
                response = await asyncio.wait_for(
                    self._get_next_response(), 
                    timeout=10.0
                )
                _LOGGER.debug("Received response for '%s': %r", command, response)
                return response
                
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout waiting for response to command: %s", command)
            raise
        except Exception as err:
            _LOGGER.error("Error sending command '%s': %s", command, err)
            await self._handle_connection_error(f"Command error: {err}")
            raise
            
        return None

    def _process_message(self, message: str) -> None:
        """Process incoming messages with MODE 4 enhanced parsing."""
        try:
            # Try MODE 4 enhanced messages first
            if self._process_mode_4_message(message):
                return
            if self._process_system_message(message):
                return
            if self._process_area_message(message):
                return
            if self._process_zone_message(message):
                return
            if self._process_output_message(message):
                return
            if self._process_panel_specific_message(message):
                return
                
        except Exception as err:
            _LOGGER.error("Error processing message '%s': %s", message, err)

    def _process_mode_4_message(self, message: str) -> bool:
        """Process MODE 4 specific enhanced messages."""
        # Enhanced area messages with user tracking
        for pattern_name, pattern in MODE_4_STATUS_MESSAGES.items():
            if isinstance(pattern, str) and pattern in message:
                if pattern_name == "keypad_panic_alarm":
                    self._status["keypad_panic_alarm"] = True
                    self._status["status_message"] = "Keypad Panic Alarm"
                    return True
                elif pattern_name == "keypad_panic_clear":
                    self._status["keypad_panic_alarm"] = False
                    self._status["status_message"] = "Keypad Panic Cleared"
                    return True
                elif pattern_name == "keypad_fire_alarm":
                    self._status["keypad_fire_alarm"] = True
                    self._status["status_message"] = "Keypad Fire Alarm"
                    return True
                elif pattern_name == "keypad_fire_clear":
                    self._status["keypad_fire_alarm"] = False
                    self._status["status_message"] = "Keypad Fire Cleared"
                    return True
                elif pattern_name == "keypad_medical_alarm":
                    self._status["keypad_medical_alarm"] = True
                    self._status["status_message"] = "Keypad Medical Alarm"
                    return True
                elif pattern_name == "keypad_medical_clear":
                    self._status["keypad_medical_alarm"] = False
                    self._status["status_message"] = "Keypad Medical Cleared"
                    return True
            elif isinstance(pattern, str) and re.match(pattern, message):
                match = re.match(pattern, message)
                if pattern_name == "area_armed_by_user":
                    area, user = match.groups()
                    area_key = f"area_{chr(96 + int(area))}_armed"
                    user_key = f"area_{chr(96 + int(area))}_armed_by_user"
                    self._status[area_key] = True
                    self._status[user_key] = int(user)
                    self._status["status_message"] = f"Area {area} armed by user {user}"
                    return True
                elif pattern_name == "area_disarmed_by_user":
                    area, user = match.groups()
                    area_key = f"area_{chr(96 + int(area))}_armed"
                    user_key = f"area_{chr(96 + int(area))}_armed_by_user"
                    self._status[area_key] = False
                    self._status[user_key] = None
                    self._status["status_message"] = f"Area {area} disarmed by user {user}"
                    return True
                elif pattern_name == "area_stay_armed_by_user":
                    area, user = match.groups()
                    area_key = f"area_{chr(96 + int(area))}_armed"
                    user_key = f"area_{chr(96 + int(area))}_armed_by_user"
                    self._status[area_key] = True
                    self._status[user_key] = int(user)
                    self._status["stay_mode"] = True
                    self._status["status_message"] = f"Area {area} stay armed by user {user}"
                    return True
        
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
            "TA": ("tamper_alarm", True, "Panel Tamper Alarm"),
            "TR": ("tamper_alarm", False, "Panel Tamper Restored"),
            "LF": ("line_ok", False, "Telephone Line Fail"),
            "LR": ("line_ok", True, "Telephone Line Restored"),
            "DF": ("dialer_ok", False, "Dialer Fail"),
            "DR": ("dialer_ok", True, "Dialer Restored"),
            "FF": ("fuse_ok", False, "Fuse/Output Fail"),
            "FR": ("fuse_ok", True, "Fuse/Output Restored"),
            "CAL": ("dialer_active", True, "Dialer Active"),
            "CLF": ("dialer_active", False, "Call Finished"),
        }
        
        if message in system_messages:
            key, value, status_msg = system_messages[message]
            self._status[key] = value
            self._status["status_message"] = status_msg
            return True
            
        return False

    def _process_area_message(self, message: str) -> bool:
        """Process area-related messages for ECi (up to 32 areas)."""
        if message.startswith("A") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if 1 <= area_num <= 32:
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = True
                    any_armed = any(self._status.get(f"area_{chr(97 + i)}_armed", False) for i in range(32))
                    self._status["armed"] = any_armed
                    self._status["arming"] = False
                    self._status["status_message"] = f"Area {area_num} Armed"
                    return True
            except ValueError:
                pass
                
        elif message.startswith("D") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if 1 <= area_num <= 32:
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = False
                    any_armed = any(self._status.get(f"area_{chr(97 + i)}_armed", False) for i in range(32))
                    if not any_armed:
                        self._status["armed"] = False
                        self._status["status_message"] = "All Areas Disarmed"
                    else:
                        self._status["status_message"] = f"Area {area_num} Disarmed"
                    return True
            except ValueError:
                pass
                
        elif message.startswith("S") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if 1 <= area_num <= 32:
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = True
                    self._status["stay_mode"] = True
                    any_armed = any(self._status.get(f"area_{chr(97 + i)}_armed", False) for i in range(32))
                    self._status["armed"] = any_armed
                    self._status["arming"] = False
                    self._status["status_message"] = f"Area {area_num} Stay Armed"
                    return True
            except ValueError:
                pass
                
        return False

    def _process_zone_message(self, message: str) -> bool:
        """Process zone-related messages with ECi enhancements."""
        match = self._zone_pattern.match(message)
        if not match:
            return False
            
        code = match.group(1)
        try:
            zone_num = int(match.group(2))
            timing_info = match.group(3)
            
            zone_codes = {
                "ZO": ("zones", True, f"Zone {zone_num} Open"),
                "ZC": ("zones", False, f"Zone {zone_num} Closed"),
                "ZA": ("zone_alarms", True, f"Zone {zone_num} Alarm"),
                "ZR": ("zone_alarms", False, f"Zone {zone_num} Alarm Restored"),
                "ZT": ("zone_troubles", True, f"Zone {zone_num} Trouble"),
                "ZTR": ("zone_troubles", False, f"Zone {zone_num} Trouble Restored"),
                "ZBY": ("zone_bypassed", True, f"Zone {zone_num} Bypassed"),
                "ZBYR": ("zone_bypassed", False, f"Zone {zone_num} Bypass Restored"),
                "ZSA": ("zone_supervise_fail", True, f"Zone {zone_num} Supervise Fail"),
                "ZSR": ("zone_supervise_fail", False, f"Zone {zone_num} Supervise OK"),
                "ZEDS": ("zone_entry_delays", timing_info, f"Zone {zone_num} Entry Delay {timing_info}s"),
            }
            
            if code in zone_codes:
                key, value, status_msg = zone_codes[code]
                
                if key not in self._status:
                    self._status[key] = {}
                
                if code == "ZEDS" and timing_info:
                    self._status[key][zone_num] = int(timing_info)
                else:
                    self._status[key][zone_num] = value
                
                self._status["status_message"] = status_msg
                
                if code in ["ZA", "ZR"]:
                    self._status["alarm"] = any(self._status["zone_alarms"].values())
                    
                return True
                
        except (ValueError, IndexError):
            pass
            
        return False

    def _process_output_message(self, message: str) -> bool:
        """Process output-related messages."""
        if message.startswith("OO") or message.startswith("OR"):
            try:
                state = message.startswith("OO")
                output_num = int(message[2:])
                
                if "outputs" not in self._status:
                    self._status["outputs"] = {}
                
                self._status["outputs"][output_num] = state
                self._status["status_message"] = f"Output {output_num} {'On' if state else 'Off'}"
                return True
            except (ValueError, IndexError):
                pass
                
        return False

    def _process_panel_specific_message(self, message: str) -> bool:
        """Process ECi-specific panel messages."""
        if message.startswith("OK ArmAway"):
            self._status["armed"] = True
            self._status["arming"] = False
            self._status["stay_mode"] = False
            self._status["status_message"] = "Armed Away"
            return True
        elif message.startswith("OK ArmStay"):
            self._status["armed"] = True
            self._status["stay_mode"] = True
            self._status["arming"] = False
            self._status["status_message"] = "Armed Stay"
            return True
        elif message.startswith("OK Disarm"):
            self._status["armed"] = False
            self._status["alarm"] = False
            self._status["stay_mode"] = False
            for i in range(1, 33):
                area_key = f"area_{chr(96 + i)}_armed"
                if area_key in self._status:
                    self._status[area_key] = False
            self._status["status_message"] = "Disarmed"
            return True
            
        return False

    async def _read_response(self) -> None:
        """Read and process responses."""
        while self._connection_state != ConnectionState.DISCONNECTED:
            try:
                if not self.reader:
                    break
                    
                data = await asyncio.wait_for(self.reader.readline(), timeout=60.0)
                
                if not data:
                    await self._handle_connection_error("Server closed connection")
                    break
                    
                message = data.decode('utf-8', errors='ignore').strip()
                if message:
                    self._last_message = datetime.now()
                    self._update_status("last_update", self._last_message.isoformat())
                    
                    _LOGGER.debug("ECi MODE 4 message received: %r", message)
                    self._process_message(message)
                    
                    # Add to queues
                    try:
                        while not self._auth_queue.empty():
                            try:
                                self._auth_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                        while not self._response_queue.empty():
                            try:
                                self._response_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break
                                
                        self._auth_queue.put_nowait(message)
                        self._response_queue.put_nowait(message)
                        
                    except asyncio.QueueFull:
                        _LOGGER.warning("Response queues full, clearing")
                        self._auth_queue = asyncio.Queue()
                        self._response_queue = asyncio.Queue()
                        self._auth_queue.put_nowait(message)
                        self._response_queue.put_nowait(message)
                        
            except asyncio.TimeoutError:
                if self.is_connected:
                    await self._send_command("STATUS")
            except asyncio.CancelledError:
                break
            except Exception as err:
                _LOGGER.error("Error in read response loop: %s", err)
                await self._handle_connection_error(f"Read error: {err}")
                break

    async def _handle_connection_error(self, error_msg: str) -> None:
        """Handle connection errors."""
        self._connection_state = ConnectionState.ERROR
        self._update_status("connection_state", self._connection_state.value)
        self._status["communication_errors"] += 1
        
        await self.disconnect()
        
        if self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Automatic reconnection."""
        await asyncio.sleep(self._reconnect_delay)
        
        self._connection_state = ConnectionState.RECONNECTING
        self._update_status("connection_state", self._connection_state.value)
        
        success = await self.connect()
        if not success and self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_delay = min(self._reconnect_delay * 2, 300)
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _keep_alive(self) -> None:
        """Keep-alive task for ECi."""
        interval = 45
        threshold = 60
        
        while self.is_connected:
            try:
                await asyncio.sleep(interval)
                
                if (datetime.now() - self._last_message).total_seconds() > threshold:
                    await self._send_command("STATUS")
                    
            except asyncio.CancelledError:
                break
            except Exception:
                break