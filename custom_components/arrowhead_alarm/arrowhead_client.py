"""Enhanced ECi client - FINAL CORRECTED VERSION.

TWO-TIER AREA CONTROL SYSTEM:
==============================

MAIN PANEL ENTITY (alarm_control_panel.arrowhead_eci_series):
- Uses simple ARMAWAY / ARMSTAY commands (MODE 4)
- Controls ALL configured areas simultaneously
- Example: ARMAWAY → Arms Area 1, Area 2, Area 3 all together
- DISARM: Uses MODE 4 format (DISARM user# pin) → Disarms ALL areas

AREA-SPECIFIC ENTITIES (alarm_control_panel.arrowhead_eci_series_area_1, etc):
- ARM: Uses MODE 4 commands (ARMAREA x / STAYAREA x)
  * Controls ONLY the specified area
  * Example: ARMAREA 1 → Arms ONLY Area 1
  * Requires P74E (away) and P76E (stay) to be configured in panel
  
- DISARM: Uses MODE 2 temporarily (DISARM area# pin)
  * Switches to MODE 2, disarms specific area, switches back to MODE 4
  * Example: DISARM 1 1234 (in MODE 2) → Disarms ONLY Area 1
  * Automatic mode switching ensures correct operation

DISARM BEHAVIOR:
================
MODE 4 (Main Panel):
- DISARM x pin → x = user number (1-2000), disarms ALL areas
- Example: DISARM 1 1234 → User 1 disarms all areas

MODE 2 (Area-Specific):
- DISARM x pin → x = area number (1-32), disarms ONLY that area
- Example: DISARM 1 1234 → Disarms Area 1 only
- Client handles MODE 2/4 switching automatically

PANEL CONFIGURATION REQUIRED:
- P74E = Areas that can be armed away individually
- P76E = Areas that can be armed stay individually
- If not configured, ARMAREA/STAYAREA commands will fail with ERR 2
"""
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum

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
    """ECi client with correct single area detection."""

    def __init__(self, host: str, port: int, user_pin: str, username: str = "admin", 
                 password: str = "admin", debug_raw_comms: bool = True):
        """Initialize the ECi client."""
        self.host = host
        self.port = port
        self.user_pin = user_pin
        self.username = username
        self.password = password
        self.debug_raw_comms = debug_raw_comms
        
        # Firmware and protocol information
        self.firmware_version = "Unknown"
        self.panel_model = "ECi Series"
        self.protocol_mode = "MODE_1"
        self.supports_mode_4 = False
        self.mode_4_features_active = False
        
        # Area configuration - Default to single area
        self.configured_areas = [1]
        self.single_area_mode = True
        
        # Connection management
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_message = datetime.now()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        self._reconnect_delay = 10
        
        # Initialize status dictionary
        self._status: Dict[str, Any] = {
            "armed": False,
            "arming": False,
            "stay_mode": False,
            "ready_to_arm": True,
            "alarm": False,
            "status_message": "Initializing",
            "panel_type": "eci",
            "panel_name": "ECi Series",
            "firmware_version": self.firmware_version,
            "panel_model": self.panel_model,
            "protocol_mode": self.protocol_mode,
            "supports_mode_4": self.supports_mode_4,
            "mode_4_features_active": False,
            "single_area_mode": True,
            "configured_areas": [1],
            "zones": {},
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
        
        # Add area status
        for i in range(1, 4):
            area_letter = chr(96 + i)
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

    def set_configured_areas(self, areas: List[int]) -> None:
        """
        Set configured areas from integration setup.
        
        Two-tier control system:
        - Main panel commands (ARMAWAY/ARMSTAY): Control ALL areas at once
        - Area-specific commands (ARMAREA x/STAYAREA x): Control individual areas (MODE 4 only)
        """
        self.configured_areas = sorted(areas) if areas else [1]
        
        # Single area mode only affects main panel behavior
        # Area-specific commands ALWAYS use MODE 4
        self.single_area_mode = (len(self.configured_areas) == 1 and self.configured_areas[0] == 1)
        
        self._status["configured_areas"] = self.configured_areas
        self._status["single_area_mode"] = self.single_area_mode
        
        _LOGGER.info("=" * 60)
        _LOGGER.info("⚙️  AREA CONFIGURATION")
        _LOGGER.info("=" * 60)
        _LOGGER.info("Configured areas: %s", self.configured_areas)
        _LOGGER.info("Main panel commands: ARMAWAY/ARMSTAY (all areas)")
        _LOGGER.info("Area-specific commands: ARMAREA x/STAYAREA x (MODE 4)")
        _LOGGER.info("=" * 60)

    @property
    def is_connected(self) -> bool:
        """Return True if connected and authenticated."""
        return self._connection_state == ConnectionState.CONNECTED

    @property
    def connection_state(self) -> str:
        """Return current connection state."""
        return self._connection_state.value

    async def connect(self) -> bool:
        """Connect to the ECi system."""
        if self._connection_state in [ConnectionState.CONNECTING, ConnectionState.AUTHENTICATING]:
            _LOGGER.warning("Connection attempt already in progress")
            return False

        self._connection_state = ConnectionState.CONNECTING
        self._update_status("connection_state", self._connection_state.value)
        
        try:
            _LOGGER.info("Connecting to ECi panel at %s:%s", self.host, self.port)
            
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=15.0
            )
            _LOGGER.info("TCP connection established")
            
            self._read_task = asyncio.create_task(self._read_response())
            await asyncio.sleep(1)
            
            self._connection_state = ConnectionState.AUTHENTICATING
            self._update_status("connection_state", self._connection_state.value)
            
            auth_success = await self._authenticate()
            
            if auth_success:
                _LOGGER.info("Authentication successful")
                await self._configure_protocol()
                
                self._connection_state = ConnectionState.CONNECTED
                self._update_status("connection_state", self._connection_state.value)
                self._reconnect_attempts = 0
                
                self._keep_alive_task = asyncio.create_task(self._keep_alive())
                
                _LOGGER.info("Connection successful - MODE 4: %s, Single area: %s", 
                           self.mode_4_features_active, self.single_area_mode)
                
                await self._get_initial_status()
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

    async def _authenticate(self) -> bool:
        """Authenticate with the panel."""
        try:
            _LOGGER.info("Attempting authentication")
            await self._send_raw_safe("STATUS\n")
            
            try:
                response = await asyncio.wait_for(self._get_response_safe(), timeout=5.0)
                if response:
                    _LOGGER.info("Authentication successful - panel responded")
                    return True
            except asyncio.TimeoutError:
                pass
            
            await self._send_raw_safe("STATUS\n")
            try:
                response = await asyncio.wait_for(self._get_response_safe(), timeout=3.0)
                if response:
                    return True
            except asyncio.TimeoutError:
                pass
            
            if self.writer and not self.writer.is_closing():
                _LOGGER.info("Connection stable, assuming authentication success")
                return True
            
            return False
                
        except Exception as err:
            _LOGGER.error("Authentication error: %s", err)
            return False

    async def _configure_protocol(self) -> None:
        """Configure protocol mode."""
        try:
            _LOGGER.info("Configuring protocol")
            
            try:
                await self._clear_response_queue()
                mode_response = await self._send_command_safe("mode ?", expect_response=True, timeout=8.0)
                
                if mode_response and "MODE 4" in mode_response:
                    _LOGGER.info("Panel in MODE 4")
                    self.mode_4_features_active = True
                    self.protocol_mode = "MODE_4"
                    self.supports_mode_4 = True
                else:
                    _LOGGER.info("Activating MODE 4")
                    await self._clear_response_queue()
                    mode4_response = await self._send_command_safe("MODE 4", expect_response=True, timeout=8.0)
                    
                    if mode4_response and ("OK" in mode4_response or "MODE 4" in mode4_response):
                        _LOGGER.info("MODE 4 activated successfully")
                        self.mode_4_features_active = True
                        self.protocol_mode = "MODE_4"
                        self.supports_mode_4 = True
                    else:
                        _LOGGER.warning("MODE 4 activation failed, using MODE 1")
                        self.mode_4_features_active = False
                        self.protocol_mode = "MODE_1"
                        self.supports_mode_4 = False
            except Exception as err:
                _LOGGER.warning("Mode configuration error: %s", err)
                self.mode_4_features_active = False
                self.protocol_mode = "MODE_1"
                self.supports_mode_4 = False
            
            self._status.update({
                "firmware_version": self.firmware_version,
                "supports_mode_4": self.supports_mode_4,
                "mode_4_features_active": self.mode_4_features_active,
                "protocol_mode": self.protocol_mode,
            })
            
            _LOGGER.info("Protocol: %s, MODE 4 active: %s", self.protocol_mode, self.mode_4_features_active)
            
        except Exception as err:
            _LOGGER.warning("Protocol configuration error: %s", err)

    async def _get_initial_status(self) -> None:
        """Get initial panel status."""
        try:
            await self._send_command_safe("STATUS")
            await asyncio.sleep(2)
            
            if self.mode_4_features_active:
                await self._populate_zones_from_panel()
            
        except Exception as err:
            _LOGGER.warning("Error getting initial status: %s", err)

    async def _populate_zones_from_panel(self) -> None:
        """Populate zones from panel configuration."""
        try:
            areas = self.configured_areas if self.configured_areas else [1, 2, 3]
            
            all_zones = set()
            
            for area in areas:
                try:
                    await self._clear_response_queue()
                    command = f"P4075E{area}?"
                    response = await self._send_command_safe(command, expect_response=True, timeout=10.0)
                    
                    if response and f"P4075E{area}=" in response:
                        zones_part = response.split("=")[1].strip()
                        if zones_part and zones_part != "0":
                            area_zones = self._parse_zone_list(zones_part)
                            all_zones.update(area_zones)
                    
                    await asyncio.sleep(1)
                except Exception as err:
                    _LOGGER.warning("Error getting zones for area %d: %s", area, err)
            
            if not all_zones:
                all_zones = {1, 2, 3, 4, 5, 6, 7, 8, 9}
            
            for zone_id in all_zones:
                self._status["zones"][zone_id] = False
                self._status["zone_alarms"][zone_id] = False
                self._status["zone_troubles"][zone_id] = False
                self._status["zone_bypassed"][zone_id] = False
            
            _LOGGER.info("Populated %d zones", len(all_zones))
            
        except Exception as err:
            _LOGGER.error("Error populating zones: %s", err)

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
        except Exception:
            pass
        return zones

    async def _send_raw_safe(self, data: str) -> None:
        """Send raw data safely with debug logging."""
        async with self._communication_lock:
            if not self.writer or self.writer.is_closing():
                raise ConnectionError("No active connection")
            
            try:
                if self.debug_raw_comms:
                    _LOGGER.info("📤 RAW TX: %r", data.strip())
                
                self.writer.write(data.encode())
                await self.writer.drain()
            except Exception as err:
                _LOGGER.error("Error sending data: %s", err)
                raise

    async def _get_response_safe(self) -> Optional[str]:
        """Get response safely with debug logging."""
        try:
            response = await asyncio.wait_for(self._response_queue.get(), timeout=10.0)
            
            if self.debug_raw_comms and response:
                _LOGGER.info("📥 RAW RX: %r", response)
            
            return response
        except asyncio.TimeoutError:
            if self.debug_raw_comms:
                _LOGGER.warning("⏱️ Response timeout (10s)")
            return None
        except Exception as err:
            if self.debug_raw_comms:
                _LOGGER.error("❌ Response error: %s", err)
            return None

    async def _send_command_safe(self, command: str, expect_response: bool = False, timeout: float = 10.0) -> Optional[str]:
        """Send command safely with debug logging."""
        try:
            if not self.is_connected and not self.writer:
                if self.debug_raw_comms:
                    _LOGGER.error("❌ Cannot send '%s': not connected", command)
                return None
            
            await self._send_raw_safe(f"{command}\n")
            
            if expect_response:
                response = await asyncio.wait_for(self._get_response_safe(), timeout=timeout)
                
                if self.debug_raw_comms:
                    if response:
                        _LOGGER.info("✅ Command '%s' → Response: %r", command, response)
                    else:
                        _LOGGER.warning("⚠️ Command '%s' → No response", command)
                
                return response
        except asyncio.TimeoutError:
            if self.debug_raw_comms:
                _LOGGER.warning("⏱️ Command '%s' timeout (%ss)", command, timeout)
            return None
        except Exception as err:
            if self.debug_raw_comms:
                _LOGGER.error("❌ Command '%s' error: %s", command, err)
            return None
        return None

    async def _clear_response_queue(self) -> None:
        """Clear response queue to avoid stale responses."""
        try:
            cleared = 0
            # Clear ALL queued messages (up to 50)
            while not self._response_queue.empty() and cleared < 50:
                try:
                    self._response_queue.get_nowait()
                    cleared += 1
                except asyncio.QueueEmpty:
                    break
            
            if cleared > 0 and self.debug_raw_comms:
                _LOGGER.debug("🗑️ Cleared %d queued responses", cleared)
            
            # Wait longer for any in-flight messages to arrive
            await asyncio.sleep(0.8)
            
            # Clear again any that arrived during the wait
            cleared2 = 0
            while not self._response_queue.empty() and cleared2 < 10:
                try:
                    self._response_queue.get_nowait()
                    cleared2 += 1
                except asyncio.QueueEmpty:
                    break
            
            if cleared2 > 0 and self.debug_raw_comms:
                _LOGGER.debug("🗑️ Cleared %d more responses after wait", cleared2)
                
        except Exception:
            pass

    # ===== ARM/DISARM METHODS =====

    async def send_armarea_command(self, area: int) -> bool:
        """
        Arm away for specified area.
        ALWAYS uses MODE 4 ARMAREA x command for individual area control.
        """
        try:
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number: %d", area)
                return False
            
            if not self.is_connected:
                _LOGGER.error("Cannot arm: not connected")
                return False
            
            if not self.mode_4_features_active:
                _LOGGER.error("MODE 4 not active, cannot use ARMAREA")
                return False
            
            await self._clear_response_queue()
            
            command = f"ARMAREA {area}"
            _LOGGER.info("🏢 Area-specific arming: %s", command)
            
            response = await self._send_command_safe(command, expect_response=True, timeout=8.0)
            
            if response and ("OK" in response and "Arm" in response):
                _LOGGER.info("✅ %s successful", command)
                await asyncio.sleep(1.5)
                return True
            else:
                _LOGGER.error("❌ %s failed: %r", command, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Exception arming away area %d: %s", area, err)
            return False

    async def send_stayarea_command(self, area: int) -> bool:
        """
        Arm stay for specified area.
        ALWAYS uses MODE 4 STAYAREA x command for individual area control.
        """
        try:
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number: %d", area)
                return False
            
            if not self.is_connected:
                _LOGGER.error("Cannot arm: not connected")
                return False
            
            if not self.mode_4_features_active:
                _LOGGER.error("MODE 4 not active, cannot use STAYAREA")
                return False
            
            await self._clear_response_queue()
            
            command = f"STAYAREA {area}"
            _LOGGER.info("🏢 Area-specific stay arming: %s", command)
            
            response = await self._send_command_safe(command, expect_response=True, timeout=8.0)
            
            if response and ("OK" in response and "Stay" in response):
                _LOGGER.info("✅ %s successful", command)
                await asyncio.sleep(1.5)
                return True
            else:
                _LOGGER.error("❌ %s failed: %r", command, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Exception arming stay area %d: %s", area, err)
            return False

    async def _switch_protocol_mode(self, mode: int) -> bool:
        """
        Temporarily switch protocol mode.
        
        Args:
            mode: Protocol mode (2 or 4)
            
        Returns:
            True if mode switch successful
        """
        try:
            await self._clear_response_queue()
            
            command = f"MODE {mode}"
            _LOGGER.info("🔄 Switching to MODE %d", mode)
            
            response = await self._send_command_safe(command, expect_response=True, timeout=8.0)
            
            if response and ("OK" in response or f"MODE {mode}" in response):
                _LOGGER.info("✅ MODE %d activated", mode)
                
                # Update internal state
                if mode == 4:
                    self.mode_4_features_active = True
                    self.protocol_mode = "MODE_4"
                elif mode == 2:
                    self.mode_4_features_active = False
                    self.protocol_mode = "MODE_2"
                
                # Small delay to let panel settle
                await asyncio.sleep(0.5)
                return True
            else:
                _LOGGER.error("❌ MODE %d switch failed: %r", mode, response)
                return False
                
        except Exception as err:
            _LOGGER.error("Exception switching to MODE %d: %s", mode, err)
            return False

    async def disarm_all_areas(self, user_pin: str = None) -> bool:
        """
        Disarm ALL areas using MODE 4 DISARM command.
        Format: DISARM x pin where x = user number (1-2000)
        """
        try:
            pin_to_use = user_pin if user_pin else self.user_pin
            
            if not pin_to_use or ' ' not in pin_to_use:
                _LOGGER.error("❌ Invalid user code format. Expected 'user_number pin' (e.g. '1 1234')")
                return False
            
            parts = pin_to_use.split(' ', 1)
            user_num = parts[0].strip()
            pin = parts[1].strip()
            
            try:
                user_int = int(user_num)
                if not (1 <= user_int <= 2000):
                    _LOGGER.error("❌ Invalid user number: %d (must be 1-2000)", user_int)
                    return False
            except ValueError:
                _LOGGER.error("❌ Invalid user number format: %s", user_num)
                return False
            
            await self._clear_response_queue()
            
            command = f"DISARM {user_num} {pin}"
            _LOGGER.info("🔓 Disarming ALL areas as user %s (MODE 4)", user_num)
            
            response = await self._send_command_safe(command, expect_response=True, timeout=8.0)
            
            if response and ("OK" in response and "Disarm" in response):
                _LOGGER.info("✅ DISARM successful (all areas)")
                await asyncio.sleep(1.5)
                return True
            else:
                _LOGGER.error("❌ DISARM failed: %r", response)
                return False
                
        except Exception as err:
            _LOGGER.error("❌ Exception during disarm: %s", err)
            return False

    async def disarm_area(self, area: int, pin: str) -> bool:
        """
        Disarm ONLY specified area using MODE 2 DISARM command.
        
        Strategy:
        1. Switch to MODE 2 temporarily
        2. Use DISARM x pin where x = area number (1-32)
        3. Switch back to MODE 4
        
        Args:
            area: Area number (1-32)
            pin: User PIN code (just the PIN, not "user_number pin")
            
        Returns:
            True if area disarmed successfully
        """
        try:
            if not (1 <= area <= 32):
                _LOGGER.error("Invalid area number: %d", area)
                return False
            
            if not self.is_connected:
                _LOGGER.error("Cannot disarm: not connected")
                return False
            
            # Save current mode
            original_mode = 4 if self.mode_4_features_active else 1
            
            _LOGGER.info("🔄 Individual disarm Area %d - switching to MODE 2", area)
            
            # Step 1: Switch to MODE 2
            if not await self._switch_protocol_mode(2):
                _LOGGER.error("Failed to switch to MODE 2")
                return False
            
            try:
                # Step 2: Disarm the area
                await self._clear_response_queue()
                
                command = f"DISARM {area} {pin}"
                _LOGGER.info("🔓 Disarming Area %d with MODE 2", area)
                
                response = await self._send_command_safe(command, expect_response=True, timeout=8.0)
                
                if response and ("OK" in response and "Disarm" in response):
                    _LOGGER.info("✅ Area %d disarmed successfully", area)
                    success = True
                else:
                    _LOGGER.error("❌ Area %d disarm failed: %r", area, response)
                    success = False
                
                # Wait for status update
                await asyncio.sleep(1.5)
                
            finally:
                # Step 3: Always switch back to original mode
                if original_mode == 4:
                    _LOGGER.info("🔄 Switching back to MODE 4")
                    await self._switch_protocol_mode(4)
            
            return success
                
        except Exception as err:
            _LOGGER.error("Exception during area %d disarm: %s", area, err)
            # Try to restore MODE 4
            try:
                await self._switch_protocol_mode(4)
            except Exception:
                pass
            return False

    async def send_main_panel_armaway(self) -> bool:
        """
        Send ARMAWAY for main panel.
        Arms ALL configured areas at once using simple ARMAWAY command.
        """
        try:
            if not self.is_connected:
                return False
            
            await self._clear_response_queue()
            
            _LOGGER.info("🏠 Main panel: ARMAWAY (all areas)")
            response = await self._send_command_safe("ARMAWAY", expect_response=True, timeout=8.0)
            
            if response and ("OK" in response and "Arm" in response):
                _LOGGER.info("✅ ARMAWAY successful (all areas)")
                await asyncio.sleep(1.5)
                return True
            else:
                _LOGGER.error("❌ ARMAWAY failed: %r", response)
                return False
        except Exception as err:
            _LOGGER.error("Exception arming main panel: %s", err)
            return False

    async def send_main_panel_armstay(self) -> bool:
        """
        Send ARMSTAY for main panel.
        Arms ALL configured areas at once using simple ARMSTAY command.
        """
        try:
            if not self.is_connected:
                return False
            
            await self._clear_response_queue()
            
            _LOGGER.info("🏠 Main panel: ARMSTAY (all areas)")
            response = await self._send_command_safe("ARMSTAY", expect_response=True, timeout=8.0)
            
            if response and ("OK" in response and ("Arm" in response or "Stay" in response)):
                _LOGGER.info("✅ ARMSTAY successful (all areas)")
                await asyncio.sleep(1.5)
                return True
            else:
                _LOGGER.error("❌ ARMSTAY failed: %r", response)
                return False
        except Exception as err:
            _LOGGER.error("Exception stay arming main panel: %s", err)
            return False

    async def arm_away(self) -> bool:
        """Backward compatibility - arms ALL areas."""
        return await self.send_main_panel_armaway()

    async def arm_stay(self) -> bool:
        """Backward compatibility - arms ALL areas."""
        return await self.send_main_panel_armstay()

    async def disarm(self) -> bool:
        """Backward compatibility - disarms ALL areas."""
        return await self.disarm_all_areas()
    
    async def disarm_with_pin(self, user_pin: str = None) -> bool:
        """Backward compatibility - disarms ALL areas."""
        return await self.disarm_all_areas(user_pin)

    async def arm_away_area(self, area: int) -> bool:
        """Backward compatibility - arms specific area."""
        return await self.send_armarea_command(area)

    async def arm_stay_area(self, area: int) -> bool:
        """Backward compatibility - arms specific area."""
        return await self.send_stayarea_command(area)
    
    async def disarm_area_with_pin(self, area: int, pin: str) -> bool:
        """Backward compatibility - disarms specific area."""
        return await self.disarm_area(area, pin)

    # ===== ZONE AND OUTPUT METHODS =====

    async def bypass_zone(self, zone_number: int) -> bool:
        """Bypass a zone."""
        try:
            zone_str = f"{zone_number:03d}"
            command = f"BYPASS {zone_str}"
            response = await self._send_command_safe(command, expect_response=True)
            return response and ("OK" in response or "Bypass" in response)
        except Exception:
            return False

    async def unbypass_zone(self, zone_number: int) -> bool:
        """Remove bypass from a zone."""
        try:
            zone_str = f"{zone_number:03d}"
            command = f"UNBYPASS {zone_str}"
            response = await self._send_command_safe(command, expect_response=True)
            return response and ("OK" in response or "Unbypass" in response)
        except Exception:
            return False

    async def trigger_output(self, output_number: int, duration: int = 0) -> bool:
        """Trigger an output."""
        try:
            if not (1 <= output_number <= 32):
                return False
            
            if duration > 0:
                command = f"OUTPUTON {output_number} {duration}"
            else:
                command = f"OUTPUTON {output_number}"
            
            response = await self._send_command_safe(command, expect_response=True, timeout=5.0)
            return response and ("OK" in response or "OutputOn" in response)
        except Exception:
            return False

    async def turn_output_on(self, output_number: int) -> bool:
        """Turn output on."""
        try:
            if not (1 <= output_number <= 32):
                return False
            
            command = f"OUTPUTON {output_number}"
            response = await self._send_command_safe(command, expect_response=True, timeout=5.0)
            return response and ("OK" in response or "OutputOn" in response)
        except Exception:
            return False

    async def turn_output_off(self, output_number: int) -> bool:
        """Turn output off."""
        try:
            if not (1 <= output_number <= 32):
                return False
            
            command = f"OUTPUTOFF {output_number}"
            response = await self._send_command_safe(command, expect_response=True, timeout=5.0)
            return response and ("OK" in response or "OutputOff" in response)
        except Exception:
            return False

    async def trigger_keypad_panic_alarm(self) -> bool:
        """Trigger keypad panic alarm (MODE 4)."""
        try:
            if not self.mode_4_features_active:
                return False
            response = await self._send_command_safe("KPANICALARM", expect_response=True)
            return response and "OK" in response
        except Exception:
            return False

    async def trigger_keypad_fire_alarm(self) -> bool:
        """Trigger keypad fire alarm (MODE 4)."""
        try:
            if not self.mode_4_features_active:
                return False
            response = await self._send_command_safe("KFIREALARM", expect_response=True)
            return response and "OK" in response
        except Exception:
            return False

    async def trigger_keypad_medical_alarm(self) -> bool:
        """Trigger keypad medical alarm (MODE 4)."""
        try:
            if not self.mode_4_features_active:
                return False
            response = await self._send_command_safe("KMEDICALARM", expect_response=True)
            return response and "OK" in response
        except Exception:
            return False

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
            except Exception:
                pass
        return self._status.copy()

    def configure_manual_outputs(self, max_outputs: int) -> None:
        """Configure outputs manually."""
        manual_outputs = set(range(1, max_outputs + 1))
        self._status["outputs"] = {o: False for o in manual_outputs}

    async def disconnect(self) -> None:
        """Disconnect from panel."""
        _LOGGER.info("Disconnecting")
        
        self._connection_state = ConnectionState.DISCONNECTED
        self._update_status("connection_state", self._connection_state.value)
        
        tasks_to_cancel = [self._keep_alive_task, self._read_task, self._reconnect_task]
        
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
                except Exception:
                    pass
        
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        
        self.reader = None
        self.writer = None

    async def _read_response(self) -> None:
        """Read responses from panel."""
        while self._connection_state != ConnectionState.DISCONNECTED:
            try:
                if not self.reader:
                    break
                
                data = await asyncio.wait_for(self.reader.readline(), timeout=60.0)
                
                if not data:
                    await self._handle_connection_error("Panel closed connection")
                    break
                
                message = data.decode('utf-8', errors='ignore').strip()
                if message:
                    self._last_message = datetime.now()
                    self._process_message(message)
                    
                    try:
                        if self._response_queue.full():
                            try:
                                self._response_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                        self._response_queue.put_nowait(message)
                    except Exception:
                        pass
            except asyncio.TimeoutError:
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

    def _process_message(self, message: str) -> None:
        """Process incoming messages."""
        try:
            self._update_status("last_update", datetime.now().isoformat())
            
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
        except Exception:
            pass

    def _process_area_message(self, message: str) -> bool:
        """Process area messages."""
        # A1, A2, A3 or A1-U1 = Area armed away
        if message.startswith("A") and len(message) >= 2:
            try:
                parts = message[1:].split('-')
                area_num = int(parts[0])
                
                if 1 <= area_num <= 3:
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = True
                    self._status["armed"] = True
                    self._status["arming"] = False
                    self._status["stay_mode"] = False
                    if self.debug_raw_comms:
                        _LOGGER.info("🔒 Area %d armed (away)", area_num)
                    return True
            except (ValueError, IndexError):
                pass
        
        # D1, D2, D3 or D1-U1 = Area disarmed
        elif message.startswith("D") and len(message) >= 2:
            try:
                parts = message[1:].split('-')
                area_num = int(parts[0])
                
                if 1 <= area_num <= 3:
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = False
                    any_armed = any(self._status.get(f"area_{chr(96 + i)}_armed", False) for i in range(1, 4))
                    self._status["armed"] = any_armed
                    self._status["stay_mode"] = False
                    if self.debug_raw_comms:
                        _LOGGER.info("🔓 Area %d disarmed", area_num)
                    return True
            except (ValueError, IndexError):
                pass
        
        # S1, S2, S3 = Area armed stay
        elif message.startswith("S") and len(message) >= 2:
            try:
                parts = message[1:].split('-')
                area_num = int(parts[0])
                
                if 1 <= area_num <= 3:
                    area_key = f"area_{chr(96 + area_num)}_armed"
                    self._status[area_key] = True
                    self._status["armed"] = True
                    self._status["stay_mode"] = True
                    self._status["arming"] = False
                    if self.debug_raw_comms:
                        _LOGGER.info("🏠 Area %d armed (stay)", area_num)
                    return True
            except (ValueError, IndexError):
                pass
        
        # RO1, RO2, RO3 = Ready to arm
        elif message.startswith("RO") and len(message) >= 3:
            try:
                area_num = int(message[2:])
                if 1 <= area_num <= 3:
                    self._status["ready_to_arm"] = True
                    if self.debug_raw_comms:
                        _LOGGER.debug("✓ Area %d ready to arm", area_num)
                    return True
            except ValueError:
                pass
        
        # NR1, NR2, NR3 = Not ready
        elif message.startswith("NR") and len(message) >= 3:
            try:
                area_num = int(message[2:])
                if 1 <= area_num <= 3:
                    self._status["ready_to_arm"] = False
                    if self.debug_raw_comms:
                        _LOGGER.debug("⚠️ Area %d not ready", area_num)
                    return True
            except ValueError:
                pass
        
        return False

    def _process_zone_message(self, message: str) -> bool:
        """Process zone messages."""
        zone_codes = {
            "ZO": ("zones", True),
            "ZC": ("zones", False),
            "ZA": ("zone_alarms", True),
            "ZR": ("zone_alarms", False),
            "ZBY": ("zone_bypassed", True),
            "ZBYR": ("zone_bypassed", False),
        }
        
        for code, (key, value) in zone_codes.items():
            if message.startswith(code):
                try:
                    zone_num = int(message[len(code):])
                    if key not in self._status:
                        self._status[key] = {}
                    self._status[key][zone_num] = value
                    if code in ["ZA", "ZR"]:
                        self._status["alarm"] = any(self._status["zone_alarms"].values())
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
                return True
            except (ValueError, IndexError):
                pass
        return False

    def _process_system_message(self, message: str) -> bool:
        """Process system messages."""
        system_messages = {
            "RO": ("ready_to_arm", True),
            "NR": ("ready_to_arm", False),
            "MF": ("mains_ok", False),
            "MR": ("mains_ok", True),
            "BF": ("battery_ok", False),
            "BR": ("battery_ok", True),
            "TA": ("tamper_alarm", True),
            "TR": ("tamper_alarm", False),
            "LF": ("line_ok", False),
            "LR": ("line_ok", True),
        }
        
        if message in system_messages:
            key, value = system_messages[message]
            self._status[key] = value
            return True
        
        if message.startswith("OK"):
            return True
        
        return False

    def _process_mode4_message(self, message: str) -> bool:
        """Process MODE 4 specific messages."""
        try:
            # EA1, ES1, EDA1-30, EDS1-30, AR1, etc.
            if (message.startswith("EA") or message.startswith("ES") or 
                message.startswith("EDA") or message.startswith("EDS") or
                message.startswith("ZEDS") or message.startswith("AR")):
                return True
        except Exception:
            pass
        return False

    async def _handle_connection_error(self, error_msg: str) -> None:
        """Handle connection errors."""
        self._connection_state = ConnectionState.ERROR
        self._update_status("connection_state", self._connection_state.value)
        self._status["communication_errors"] = self._status.get("communication_errors", 0) + 1
        await self.disconnect()

    async def _keep_alive(self) -> None:
        """Keep connection alive."""
        while self.is_connected:
            try:
                await asyncio.sleep(30)
                if self.is_connected:
                    await self._send_command_safe("STATUS")
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def send_custom_command(self, command: str) -> Optional[str]:
        """Send custom command."""
        return await self._send_command_safe(command, expect_response=True)

    def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information."""
        return {
            "connection_state": self._connection_state.value,
            "mode_4_active": self.mode_4_features_active,
            "protocol_mode": self.protocol_mode,
            "single_area_mode": self.single_area_mode,
            "configured_areas": self.configured_areas,
            "debug_raw_comms": self.debug_raw_comms,
        }
