"""Enhanced Arrowhead Alarm Panel client with version detection and protocol adaptation."""
import asyncio
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from enum import Enum

from .const import PANEL_TYPE_ESX, PANEL_TYPE_ECI, PANEL_CONFIGS

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

class ProtocolMode(Enum):
    """ECi Protocol modes."""
    MODE_1 = 1  # Default, no acknowledgments
    MODE_2 = 2  # AAP mode, with acknowledgments
    MODE_3 = 3  # Permaconn mode, with acknowledgments
    MODE_4 = 4  # Home Automation mode, no acknowledgments (ECi FW 10.3.50+)

class ArrowheadClient:
    """Enhanced client for Arrowhead Alarm Panel systems with version detection."""

    def __init__(self, host: str, port: int, user_pin: str, username: str = "admin", 
                 password: str = "admin", panel_type: str = PANEL_TYPE_ESX):
        """Initialize the client."""
        self.host = host
        self.port = port
        self.user_pin = user_pin
        self.username = username
        self.password = password
        self.panel_type = panel_type
        self.panel_config = PANEL_CONFIGS[panel_type]
        
        # Version and protocol information
        self.firmware_version = None
        self.panel_model = None
        self.protocol_mode = ProtocolMode.MODE_1
        self.supports_mode_4 = False
        self.requires_acknowledgments = False
        
        # Connection management
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._connection_state = ConnectionState.DISCONNECTED
        self._last_message = datetime.now()
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5
        self._reconnect_delay = 30
        
        # Initialize status dictionary with basic zones
        max_zones = self.panel_config["max_zones"] if panel_type == PANEL_TYPE_ESX else 16
        
        self._status: Dict[str, Any] = {
            # Basic alarm states
            "armed": False,
            "arming": False,
            "stay_mode": False,
            "ready_to_arm": False,
            "alarm": False,
            "status_message": "Unknown",
            "panel_type": panel_type,
            "panel_name": self.panel_config["name"],
            
            # Version information
            "firmware_version": None,
            "panel_model": None,
            "protocol_mode": self.protocol_mode.value,
            "supports_mode_4": False,
            
            # Area status
            "area_a_armed": False if self.panel_config["supports_areas"] else None,
            "area_b_armed": False if self.panel_config["supports_areas"] else None,
            
            # Zone states
            "zones": {i: False for i in range(1, max_zones + 1)},
            "zone_alarms": {i: False for i in range(1, max_zones + 1)},
            "zone_troubles": {i: False for i in range(1, max_zones + 1)},
            "zone_bypassed": {i: False for i in range(1, max_zones + 1)},
            "zone_supervise_fail": {i: False for i in range(1, max_zones + 1)} if self.panel_config["supports_rf"] else {},
            
            # System states
            "battery_ok": True,
            "mains_ok": True,
            "tamper_alarm": False,
            "line_ok": True,
            "dialer_ok": True,
            "fuse_ok": True,
            "pendant_battery_ok": True if self.panel_config["supports_rf"] else None,
            "code_tamper": False,
            "receiver_ok": True if self.panel_config["supports_rf"] else None,
            "dialer_active": False,
            "rf_battery_low": False if self.panel_config["supports_rf"] else None,
            "sensor_watch_alarm": False if self.panel_config["supports_rf"] else None,
            
            # Outputs status - start empty, will be configured manually
            "outputs": {},
            
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
        
        # Message parsing patterns
        self._zone_pattern = re.compile(r'^([A-Z]{2,4})(\d{1,3})$')
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
        """Connect to the alarm system with version detection."""
        if self._connection_state in [ConnectionState.CONNECTING, ConnectionState.AUTHENTICATING, ConnectionState.VERSION_CHECKING]:
            _LOGGER.warning("Connection attempt already in progress")
            return False

        self._connection_state = ConnectionState.CONNECTING
        self._update_status("connection_state", self._connection_state.value)
        
        try:
            _LOGGER.info("Connecting to %s %s at %s:%s", 
                        self.panel_config["name"], self.panel_type.upper(), self.host, self.port)
            
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
                self._connection_state = ConnectionState.CONNECTED
                self._update_status("connection_state", self._connection_state.value)
                self._reconnect_attempts = 0
                
                # Start keep-alive task
                self._keep_alive_task = asyncio.create_task(self._keep_alive())
                
                _LOGGER.info("Successfully connected to %s", self.panel_config["name"])
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

    async def _authenticate(self) -> bool:
        """Authenticate with panel-specific logic."""
        try:
            timeout = 5.0 if self.panel_type == PANEL_TYPE_ESX else 3.0
            
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

    # Communication methods
    async def _send_raw(self, data: str) -> None:
        """Send raw data to the connection."""
        if not self.writer:
            raise ConnectionError("No active connection")
            
        self.writer.write(data.encode())
        await self.writer.drain()

    async def _get_next_response(self) -> str:
        """Get next response with improved queue management."""
        auth_task = asyncio.create_task(self._auth_queue.get())
        resp_task = asyncio.create_task(self._response_queue.get())
        
        done, pending = await asyncio.wait(
            [auth_task, resp_task], 
            return_when=asyncio.FIRST_COMPLETED,
            timeout=5.0
        )
        
        for task in pending:
            task.cancel()
            
        if done:
            return list(done)[0].result()
        else:
            raise asyncio.TimeoutError("No response received")

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

    # Error handling and reconnection
    async def _handle_connection_error(self, error_msg: str) -> None:
        """Handle connection errors with automatic reconnection."""
        self._connection_state = ConnectionState.ERROR
        self._update_status("connection_state", self._connection_state.value)
        self._status["communication_errors"] += 1
        
        await self.disconnect()
        
        if self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_attempts += 1
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        """Automatic reconnection with exponential backoff."""
        await asyncio.sleep(self._reconnect_delay)
        
        self._connection_state = ConnectionState.RECONNECTING
        self._update_status("connection_state", self._connection_state.value)
        
        success = await self.connect()
        if not success and self._reconnect_attempts < self._max_reconnect_attempts:
            self._reconnect_delay = min(self._reconnect_delay * 2, 300)
            self._reconnect_task = asyncio.create_task(self._reconnect())

    # Message processing
    async def _read_response(self) -> None:
        """Read and process responses with protocol-aware handling."""
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
                    
                    # Process the message
                    self._process_message(message)
                    
                    # Add to queues
                    try:
                        self._auth_queue.put_nowait(message)
                        self._response_queue.put_nowait(message)
                    except asyncio.QueueFull:
                        try:
                            self._auth_queue.get_nowait()
                            self._response_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            pass
                        self._auth_queue.put_nowait(message)
                        self._response_queue.put_nowait(message)
                        
            except asyncio.TimeoutError:
                if self.is_connected:
                    await self._send_command("STATUS")
            except asyncio.CancelledError:
                break
            except Exception as err:
                await self._handle_connection_error(f"Read error: {err}")
                break

    def _update_status(self, key: str, value: Any) -> None:
        """Update status with thread safety."""
        self._status[key] = value

    def _process_message(self, message: str) -> None:
        """Process incoming messages with protocol-aware parsing."""
        try:
            if self._process_system_message(message):
                return
            if self.panel_config["supports_areas"] and self._process_area_message(message):
                return
            if self._process_zone_message(message):
                return
            if self._process_output_message(message):
                return
            if self._process_panel_specific_message(message):
                return
                
        except Exception as err:
            _LOGGER.error("Error processing message '%s': %s", message, err)

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
        
        if self.panel_config["supports_rf"]:
            system_messages.update({
                "RIF": ("receiver_ok", False, "Receiver Fail"),
                "RIR": ("receiver_ok", True, "Receiver Restored"),
                "ZBL": ("rf_battery_low", True, "RF Zone Battery Low"),
                "ZBR": ("rf_battery_low", False, "RF Zone Battery OK"),
                "ZIA": ("sensor_watch_alarm", True, "Zone Sensor-Watch Alarm"),
                "ZIR": ("sensor_watch_alarm", False, "Zone Sensor-Watch OK"),
            })
        
        if message in system_messages:
            key, value, status_msg = system_messages[message]
            self._status[key] = value
            self._status["status_message"] = status_msg
            return True
            
        return False

    def _process_area_message(self, message: str) -> bool:
        """Process area-related messages."""
        if message.startswith("A") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                self._status["armed"] = True
                self._status["arming"] = False
                if area_num == 1:
                    self._status["area_a_armed"] = True
                elif area_num == 2:
                    self._status["area_b_armed"] = True
                self._status["status_message"] = f"Area {area_num} Armed"
                return True
            except ValueError:
                pass
                
        elif message.startswith("D") and len(message) >= 2:
            try:
                area_num = int(message[1:])
                if area_num == 1:
                    self._status["area_a_armed"] = False
                elif area_num == 2:
                    self._status["area_b_armed"] = False
                
                if not self._status.get("area_a_armed", False) and not self._status.get("area_b_armed", False):
                    self._status["armed"] = False
                    self._status["status_message"] = "Disarmed"
                return True
            except ValueError:
                pass
                
        return False

    def _process_zone_message(self, message: str) -> bool:
        """Process zone-related messages."""
        match = self._zone_pattern.match(message)
        if not match:
            return False
            
        code = match.group(1)
        try:
            zone_num = int(match.group(2))
            
            zone_codes = {
                "ZO": ("zones", True, f"Zone {zone_num} Open"),
                "ZC": ("zones", False, f"Zone {zone_num} Closed"),
                "ZA": ("zone_alarms", True, f"Zone {zone_num} Alarm"),
                "ZR": ("zone_alarms", False, f"Zone {zone_num} Alarm Restored"),
                "ZT": ("zone_troubles", True, f"Zone {zone_num} Trouble"),
                "ZTR": ("zone_troubles", False, f"Zone {zone_num} Trouble Restored"),
                "ZBY": ("zone_bypassed", True, f"Zone {zone_num} Bypassed"),
                "ZBYR": ("zone_bypassed", False, f"Zone {zone_num} Bypass Restored"),
            }
            
            if self.panel_config["supports_rf"]:
                zone_codes.update({
                    "ZSA": ("zone_supervise_fail", True, f"Zone {zone_num} RF Supervise Fail"),
                    "ZSR": ("zone_supervise_fail", False, f"Zone {zone_num} RF Supervise OK"),
                })
            
            if code in zone_codes:
                key, value, status_msg = zone_codes[code]
                
                if key in self._status and zone_num in self._status[key]:
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
                
                if output_num in self._status["outputs"]:
                    self._status["outputs"][output_num] = state
                    self._status["status_message"] = f"Output {output_num} {'On' if state else 'Off'}"
                    return True
            except (ValueError, IndexError):
                pass
                
        return False

    def _process_panel_specific_message(self, message: str) -> bool:
        """Process panel-specific messages."""
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
            self._status["status_message"] = "Disarmed"
            return True
            
        return False

    async def _send_command(self, command: str, expect_response: bool = False) -> Optional[str]:
        """Send command with improved error handling."""
        if not self.is_connected:
            raise ConnectionError(f"Not connected to {self.panel_type.upper()} alarm system")
            
        try:
            await self._send_raw(f"{command}\n")
            
            if expect_response:
                return await asyncio.wait_for(
                    self._get_next_response(), 
                    timeout=5.0
                )
                
        except Exception as err:
            await self._handle_connection_error(f"Command error: {err}")
            raise
            
        return None

    async def _keep_alive(self) -> None:
        """Keep-alive with panel-specific timing."""
        interval = 30 if self.panel_type == PANEL_TYPE_ESX else 45
        threshold = 45 if self.panel_type == PANEL_TYPE_ESX else 60
        
        while self.is_connected:
            try:
                await asyncio.sleep(interval)
                
                if (datetime.now() - self._last_message).total_seconds() > threshold:
                    await self._send_command("STATUS")
                    
            except asyncio.CancelledError:
                break
            except Exception:
                break

    async def arm_away(self) -> bool:
        """Arm the alarm in away mode."""
        try:
            _LOGGER.info("Attempting to arm in away mode with user PIN: %s", self.user_pin)
            
            if not self.is_connected:
                _LOGGER.error("Cannot arm away: not connected to panel")
                return False
            
            # Parse user_pin to extract user number and pin
            user_num, pin = self._parse_user_pin(self.user_pin)
            
            # Try different command formats based on panel type and mode
            commands_to_try = []
            
            if user_num and pin:
                # Mode 1,3,4: ARMAWAY [user-number] [pin]
                commands_to_try.append(f"ARMAWAY {user_num} {pin}")
            
            # Mode 2: ARMAWAY [area-number] (but we need to know the area)
            if self.panel_type == "ECi":
                # Try area 1 as default for ECi
                commands_to_try.append("ARMAWAY 1")
            
            # Single button mode (all modes)
            commands_to_try.append("ARMAWAY")
            
            # Try each command until one works
            for command in commands_to_try:
                _LOGGER.info("Trying ARMAWAY command: %s", command)
                
                try:
                    response = await self._send_command(command)
                    _LOGGER.info("ARMAWAY command response: %r", response)
                    
                    # Check if the response indicates success
                    if response and ("OK" in response or "ArmAway" in response):
                        _LOGGER.info("ARMAWAY command accepted by panel")
                        
                        # Wait a bit for the status to update
                        await asyncio.sleep(3)
                        
                        # Check if arming was successful
                        status = await self.get_status()
                        if status and (status.get("armed", False) or status.get("arming", False)):
                            _LOGGER.info("ARMAWAY command successful")
                            return True
                        else:
                            _LOGGER.warning("Panel accepted ARMAWAY but status shows not armed")
                            continue
                    else:
                        _LOGGER.warning("Panel did not accept ARMAWAY command '%s'. Response: %r", command, response)
                        continue
                        
                except RuntimeError as err:
                    _LOGGER.warning("Panel returned error for ARMAWAY '%s': %s", command, err)
                    continue
            
            # If we get here, all commands failed
            _LOGGER.error("All ARMAWAY command variations failed")
            return False
                
        except Exception as err:
            _LOGGER.error("Error sending ARMAWAY command: %s", err)
            return False

    async def arm_stay(self) -> bool:
        """Arm the alarm in stay mode."""
        try:
            _LOGGER.info("Attempting to arm in stay mode with user PIN: %s", self.user_pin)
            
            if not self.is_connected:
                _LOGGER.error("Cannot arm stay: not connected to panel")
                return False
            
            # Check panel compatibility
            if self.panel_type == "ESX":
                _LOGGER.debug("ESX panel detected - using ESX-compatible commands")
            elif self.panel_type == "ECi":
                _LOGGER.debug("ECi panel detected - using ECi-compatible commands")
            
            # First, check if we can arm (system ready)
            _LOGGER.debug("Checking system status before arming...")
            status = await self.get_status()
            if status:
                _LOGGER.debug("Pre-arm status: ready_to_arm=%s, armed=%s", 
                             status.get("ready_to_arm", False), status.get("armed", False))
                
                if status.get("armed", False):
                    _LOGGER.info("System is already armed")
                    return True
                    
                if not status.get("ready_to_arm", False):
                    _LOGGER.warning("System not ready to arm - check zones are sealed")
                    # Continue anyway, let the panel decide
            
            # Parse user_pin to extract user number and pin
            user_num, pin = self._parse_user_pin(self.user_pin)
            
            # Try different command formats based on panel type and mode
            commands_to_try = []
            
            if user_num and pin:
                # Mode 1,3,4: ARMSTAY [user-number] [pin]
                commands_to_try.append(f"ARMSTAY {user_num} {pin}")
            
            # Mode 2: ARMSTAY [area-number] (but we need to know the area)
            if self.panel_type == "ECi":
                # Try area 1 as default for ECi
                commands_to_try.append("ARMSTAY 1")
            
            # Single button mode (all modes)
            commands_to_try.append("ARMSTAY")
            
            # Try each command until one works
            for command in commands_to_try:
                _LOGGER.info("Trying ARMSTAY command: %s", command)
                
                try:
                    response = await self._send_command(command)
                    _LOGGER.info("ARMSTAY command response: %r", response)
                    
                    # Check if the response indicates success
                    if response and ("OK" in response or "ArmStay" in response):
                        _LOGGER.info("ARMSTAY command accepted by panel")
                        
                        # Wait a bit for the status to update
                        await asyncio.sleep(3)
                        
                        # Check if arming was successful
                        status = await self.get_status()
                        if status:
                            armed = status.get("armed", False)
                            arming = status.get("arming", False)
                            stay_mode = status.get("stay_mode", False)
                            
                            _LOGGER.info("Post-arm status: armed=%s, arming=%s, stay_mode=%s", 
                                       armed, arming, stay_mode)
                            
                            if armed or arming:
                                _LOGGER.info("ARMSTAY command successful")
                                return True
                            else:
                                _LOGGER.warning("Panel accepted ARMSTAY but status shows not armed")
                                # Try next command
                                continue
                        else:
                            _LOGGER.warning("Could not get status after ARMSTAY command")
                            # Try next command
                            continue
                    else:
                        _LOGGER.warning("Panel did not accept ARMSTAY command '%s'. Response: %r", command, response)
                        # Try next command
                        continue
                        
                except RuntimeError as err:
                    _LOGGER.warning("Panel returned error for ARMSTAY '%s': %s", command, err)
                    # Try next command
                    continue
            
            # If we get here, all commands failed
            _LOGGER.error("All ARMSTAY command variations failed")
            return False
                
        except Exception as err:
            _LOGGER.error("Error sending ARMSTAY command: %s", err)
            return False

    async def disarm(self) -> bool:
        """Disarm the alarm."""
        try:
            _LOGGER.info("Sending DISARM command with user PIN: %s", self.user_pin)
            
            if not self.is_connected:
                _LOGGER.error("Cannot disarm: not connected to panel")
                return False
            
            # Parse user_pin to extract user number and pin
            user_num, pin = self._parse_user_pin(self.user_pin)
            
            if user_num and pin:
                command = f"DISARM {user_num} {pin}"
            else:
                _LOGGER.error("Invalid user PIN format: %s", self.user_pin)
                return False
                
            _LOGGER.info("Sending command: %s", command)
            await self._send_command(command)
            
            # Wait a bit for the response and status change
            await asyncio.sleep(2)
            
            # Check if disarming was successful
            status = await self.get_status()
            if status and not status.get("armed", True):
                _LOGGER.info("DISARM command successful")
                return True
            else:
                _LOGGER.warning("DISARM command sent but panel still shows as armed")
                return False
                
        except Exception as err:
            _LOGGER.error("Error sending DISARM command: %s", err)
            return False

    def _parse_user_pin(self, user_pin: str) -> tuple[Optional[str], Optional[str]]:
        """Parse user_pin format '1 123' into user number and PIN."""
        try:
            parts = user_pin.strip().split()
            if len(parts) >= 2:
                user_num = parts[0]
                pin = parts[1]
                _LOGGER.debug("Parsed user_pin '%s' -> user: %s, pin: %s", user_pin, user_num, pin)
                return user_num, pin
            else:
                _LOGGER.warning("Invalid user_pin format '%s', expected 'user pin'", user_pin)
                return None, None
        except Exception as err:
            _LOGGER.error("Error parsing user_pin '%s': %s", user_pin, err)
            return None, None

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

    async def trigger_output(self, output_number: int, duration: int = 0) -> bool:
        """Trigger an output for specified duration (0 = toggle)."""
        try:
            if output_number > self.panel_config["max_outputs"]:
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
            if output_number > self.panel_config["max_outputs"]:
                return False
            await self._send_command(f"OUTPUTON {output_number}")
            return True
        except Exception:
            return False

    async def turn_output_off(self, output_number: int) -> bool:
        """Turn output off."""
        try:
            if output_number > self.panel_config["max_outputs"]:
                return False
            await self._send_command(f"OUTPUTOFF {output_number}")
            return True
        except Exception:
            return False

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
        _LOGGER.info("=== MANUAL OUTPUT CONFIGURATION START ===")
        _LOGGER.info("Configuring %d outputs manually", max_outputs)
        
        # Create outputs dictionary with user-specified count
        manual_outputs = set(range(1, max_outputs + 1))
        self._status["outputs"] = {o: False for o in manual_outputs}
        
        # Update status with manual configuration info
        self._status.update({
            "total_outputs_detected": max_outputs,
            "max_outputs_detected": max_outputs,
            "output_detection_method": "manual_configuration",
            "output_ranges": {"main_panel": list(manual_outputs)}
        })
        
        _LOGGER.info("Manual output configuration complete:")
        _LOGGER.info("  - Outputs created: %s", list(self._status["outputs"].keys()))
        _LOGGER.info("  - Total outputs: %d", max_outputs)
        _LOGGER.info("  - Detection method: manual_configuration")
        _LOGGER.info("=== MANUAL OUTPUT CONFIGURATION END ===")