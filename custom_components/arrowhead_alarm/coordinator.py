"""Data update coordinator for Arrowhead ECi Panel - IMPROVED VERSION."""
import asyncio
import logging
from datetime import timedelta, datetime
from typing import Dict, Any, Optional, List
from enum import Enum

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import DOMAIN, HEALTH_CHECK, SERVICE_TIMEOUTS

_LOGGER = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Represents the connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"

class ArrowheadECiDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Arrowhead ECi panel - IMPROVED VERSION."""

    def __init__(self, hass: HomeAssistant, client, update_interval: int = 30):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self._client = client
        self._connection_state = ConnectionState.DISCONNECTED
        self._connection_state_callbacks = []
        self._last_successful_update = None
        self._consecutive_failures = 0
        self._health_metrics = {
            "total_updates": 0,
            "successful_updates": 0,
            "failed_updates": 0,
            "connection_errors": 0,
            "last_error": None,
            "last_error_time": None,
            "average_response_time": 0.0,
            "response_times": [],
        }
        
        # Enhanced reconnection logic
        self._reconnect_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = HEALTH_CHECK["max_consecutive_failures"]
        self._reconnect_delay = HEALTH_CHECK["reconnect_delay_base"]
        
        # Status tracking
        self._last_zone_count = 0
        self._last_output_count = 0
        self._config_entry: Optional[ConfigEntry] = None
        
    @property
    def connection_state(self) -> ConnectionState:
        """Return the current connection state."""
        return self._connection_state
        
    @property
    def health_metrics(self) -> Dict[str, Any]:
        """Return health metrics."""
        return self._health_metrics.copy()
        
    @property
    def success_rate(self) -> float:
        """Return success rate percentage."""
        total = self._health_metrics["total_updates"]
        if total == 0:
            return 0.0
        return (self._health_metrics["successful_updates"] / total) * 100
        
    @callback
    def async_add_connection_state_listener(self, update_callback) -> callable:
        """Add a callback for connection state changes."""
        self._connection_state_callbacks.append(update_callback)
        
        def remove_listener():
            """Remove the listener."""
            if update_callback in self._connection_state_callbacks:
                self._connection_state_callbacks.remove(update_callback)
                
        return remove_listener

    def _update_connection_state(self, new_state: ConnectionState) -> None:
        """Update connection state and notify listeners."""
        if self._connection_state != new_state:
            old_state = self._connection_state
            self._connection_state = new_state
            _LOGGER.debug("Connection state changed from %s to %s", old_state.value, new_state.value)
            
            # Update health metrics
            if new_state == ConnectionState.ERROR:
                self._health_metrics["connection_errors"] += 1
            
            # Notify all listeners
            for callback in self._connection_state_callbacks:
                try:
                    callback(new_state)
                except Exception as err:
                    _LOGGER.error("Error in connection state callback: %s", err)

    def set_config_entry(self, config_entry: ConfigEntry) -> None:
        """Set the config entry for reference."""
        self._config_entry = config_entry

    async def async_setup(self) -> None:
        """Set up the coordinator - IMPROVED."""
        _LOGGER.info("Setting up ArrowheadECiDataUpdateCoordinator (IMPROVED)")
        
        # Set initial state
        self._update_connection_state(ConnectionState.CONNECTING)
        
        # Initialize health metrics
        self._health_metrics["setup_time"] = dt_util.utcnow().isoformat()
        
        # Perform first refresh to validate connection
        try:
            await self.async_config_entry_first_refresh()
            _LOGGER.info("ArrowheadECiDataUpdateCoordinator setup complete")
        except Exception as err:
            _LOGGER.error("Failed to setup coordinator: %s", err)
            self._update_connection_state(ConnectionState.ERROR)
            self._record_error(err)
            raise

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh with enhanced validation."""
        try:
            _LOGGER.info("Starting first refresh for ECi coordinator")
            start_time = dt_util.utcnow()
            
            # Ensure client is connected with timeout
            if not self._client.is_connected:
                _LOGGER.info("Client not connected, attempting connection")
                
                connection_timeout = HEALTH_CHECK["connection_timeout"]
                success = await asyncio.wait_for(
                    self._client.connect(),
                    timeout=connection_timeout
                )
                
                if not success:
                    raise UpdateFailed("Failed to connect to ECi panel during first refresh")
            
            # Get initial status with retry logic
            data = await self._async_update_data_with_retry()
            
            # Calculate response time
            response_time = (dt_util.utcnow() - start_time).total_seconds()
            self._update_response_time(response_time)
            
            # Validate essential data
            validation_result = self._validate_initial_data(data)
            if not validation_result["valid"]:
                raise UpdateFailed(f"Invalid initial data: {validation_result['errors']}")
            
            # Set data if not set by parent class
            if not self.data and data:
                self.data = data
            
            # Log success metrics
            zones = self.data.get("zones", {})
            outputs = self.data.get("outputs", {})
            self._last_zone_count = len(zones)
            self._last_output_count = len(outputs)
            
            _LOGGER.info("First refresh complete - %d zones, %d outputs, %.2fs response time", 
                       self._last_zone_count, self._last_output_count, response_time)
            
            # Log MODE 4 status
            if self.data.get("mode_4_features_active"):
                _LOGGER.info("MODE 4 features active - Enhanced capabilities available")
            
            # Update connection state
            self._update_connection_state(ConnectionState.CONNECTED)
            self._health_metrics["successful_updates"] += 1
            
        except Exception as err:
            _LOGGER.error("Error during first refresh: %s", err)
            self._record_error(err)
            raise UpdateFailed(f"First refresh failed: {err}")

    def _validate_initial_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate initial data structure."""
        validation = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        if not isinstance(data, dict):
            validation["valid"] = False
            validation["errors"].append("Data is not a dictionary")
            return validation
        
        # Check for essential keys
        essential_keys = ["zones", "outputs", "connection_state"]
        for key in essential_keys:
            if key not in data:
                validation["warnings"].append(f"Missing key: {key}")
        
        # Validate zones structure
        zones = data.get("zones", {})
        if not isinstance(zones, dict):
            validation["errors"].append("Zones is not a dictionary")
            validation["valid"] = False
        elif len(zones) == 0:
            validation["warnings"].append("No zones detected")
        
        # Validate outputs structure
        outputs = data.get("outputs", {})
        if not isinstance(outputs, dict):
            validation["errors"].append("Outputs is not a dictionary")
            validation["valid"] = False
        
        # Check connection state
        connection_state = data.get("connection_state")
        if connection_state not in ["connected", "connecting"]:
            validation["warnings"].append(f"Unexpected connection state: {connection_state}")
        
        return validation

    async def _async_update_data_with_retry(self) -> Dict[str, Any]:
        """Update data with retry logic."""
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                return await self._async_update_data()
            except Exception as err:
                last_error = err
                _LOGGER.warning("Update attempt %d/%d failed: %s", 
                              attempt + 1, max_retries, err)
                
                if attempt < max_retries - 1:
                    # Wait before retry
                    await asyncio.sleep(1 * (attempt + 1))
        
        # All retries failed
        raise last_error

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the ECi panel with enhanced error handling."""
        start_time = dt_util.utcnow()
        
        try:
            self._health_metrics["total_updates"] += 1
            
            # Ensure connection with timeout
            if not self._client.is_connected:
                _LOGGER.debug("Client disconnected, attempting reconnection")
                
                # Cancel any existing reconnect task
                if self._reconnect_task and not self._reconnect_task.done():
                    self._reconnect_task.cancel()
                
                self._update_connection_state(ConnectionState.RECONNECTING)
                
                success = await asyncio.wait_for(
                    self._client.connect(),
                    timeout=HEALTH_CHECK["connection_timeout"]
                )
                
                if not success:
                    raise UpdateFailed("Failed to reconnect to ECi panel")
            
            # Get status from client with timeout
            status = await asyncio.wait_for(
                self._client.get_status(),
                timeout=SERVICE_TIMEOUTS["status_refresh"]
            )
            
            if status is None:
                raise UpdateFailed("No data received from ECi panel")
            
            # Validate status data
            if not isinstance(status, dict):
                raise UpdateFailed(f"Invalid status data type: {type(status)}")
            
            # Update response time metrics
            response_time = (dt_util.utcnow() - start_time).total_seconds()
            self._update_response_time(response_time)
            
            # Update connection state and metrics
            self._update_connection_state(ConnectionState.CONNECTED)
            self._consecutive_failures = 0
            self._reconnect_attempts = 0
            self._health_metrics["successful_updates"] += 1
            self._last_successful_update = dt_util.utcnow()
            
            # Add coordinator metadata
            status.update({
                "coordinator_success_rate": self.success_rate,
                "coordinator_last_update": dt_util.utcnow().isoformat(),
                "coordinator_response_time": response_time,
            })
            
            return status
            
        except asyncio.TimeoutError as err:
            self._handle_update_error(f"Timeout during update: {err}")
            raise UpdateFailed("Timeout communicating with ECi panel")
        except Exception as err:
            self._handle_update_error(f"Error during update: {err}")
            raise UpdateFailed(f"Error communicating with ECi panel: {err}")

    def _update_response_time(self, response_time: float) -> None:
        """Update response time metrics."""
        self._health_metrics["response_times"].append(response_time)
        
        # Keep only last 50 response times
        if len(self._health_metrics["response_times"]) > 50:
            self._health_metrics["response_times"] = self._health_metrics["response_times"][-50:]
        
        # Calculate average
        times = self._health_metrics["response_times"]
        self._health_metrics["average_response_time"] = sum(times) / len(times)

    def _handle_update_error(self, error_msg: str) -> None:
        """Handle update errors with enhanced logic."""
        _LOGGER.error("Update error: %s", error_msg)
        
        self._consecutive_failures += 1
        self._health_metrics["failed_updates"] += 1
        self._record_error(error_msg)
        
        # Update connection state
        if self._consecutive_failures >= self._max_reconnect_attempts:
            self._update_connection_state(ConnectionState.ERROR)
        else:
            self._update_connection_state(ConnectionState.RECONNECTING)
        
        # Schedule reconnection if needed
        if (self._consecutive_failures <= self._max_reconnect_attempts and 
            (not self._reconnect_task or self._reconnect_task.done())):
            self._reconnect_task = asyncio.create_task(self._handle_reconnection())

    def _record_error(self, error: Any) -> None:
        """Record error in health metrics."""
        error_str = str(error)
        self._health_metrics["last_error"] = error_str
        self._health_metrics["last_error_time"] = dt_util.utcnow().isoformat()
        
        # Keep error history (last 10 errors)
        if "error_history" not in self._health_metrics:
            self._health_metrics["error_history"] = []
        
        self._health_metrics["error_history"].append({
            "error": error_str,
            "time": dt_util.utcnow().isoformat(),
            "consecutive_failures": self._consecutive_failures,
        })
        
        if len(self._health_metrics["error_history"]) > 10:
            self._health_metrics["error_history"] = self._health_metrics["error_history"][-10:]

    async def _handle_reconnection(self) -> None:
        """Handle reconnection with exponential backoff."""
        try:
            # Calculate delay with exponential backoff
            delay = min(
                self._reconnect_delay * (2 ** self._reconnect_attempts),
                HEALTH_CHECK["reconnect_delay_max"]
            )
            
            _LOGGER.info("Scheduling reconnection in %d seconds (attempt %d)", 
                        delay, self._reconnect_attempts + 1)
            
            await asyncio.sleep(delay)
            
            if self._client.is_connected:
                _LOGGER.info("Client reconnected while waiting")
                return
            
            _LOGGER.info("Attempting to reconnect to ECi panel")
            self._reconnect_attempts += 1
            
            success = await asyncio.wait_for(
                self._client.connect(),
                timeout=HEALTH_CHECK["connection_timeout"]
            )
            
            if success:
                _LOGGER.info("Reconnection successful")
                self._reconnect_attempts = 0
                self._consecutive_failures = 0
                await self.async_request_refresh()
            else:
                _LOGGER.warning("Reconnection failed")
                
        except asyncio.CancelledError:
            _LOGGER.debug("Reconnection task cancelled")
        except Exception as err:
            _LOGGER.error("Error during reconnection: %s", err)
            self._record_error(f"Reconnection error: {err}")

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator with cleanup."""
        _LOGGER.info("Shutting down ArrowheadECiDataUpdateCoordinator")
        
        try:
            # Cancel reconnection task
            if self._reconnect_task and not self._reconnect_task.done():
                self._reconnect_task.cancel()
                try:
                    await asyncio.wait_for(self._reconnect_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Disconnect the client
            if self._client:
                await asyncio.wait_for(self._client.disconnect(), timeout=10.0)
        except Exception as err:
            _LOGGER.error("Error during shutdown: %s", err)
        finally:
            self._update_connection_state(ConnectionState.DISCONNECTED)
            
        _LOGGER.info("ArrowheadECiDataUpdateCoordinator shutdown complete")

    # ===== OUTPUT CONTROL METHODS - IMPROVED =====

    async def async_trigger_output(self, output_id: int, duration: Optional[int] = None) -> bool:
        """Trigger an output for a specified duration with enhanced error handling."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot trigger output %s: client not connected", output_id)
                return False
            
            # Validate output ID
            if not isinstance(output_id, int) or output_id < 1 or output_id > 32:
                _LOGGER.error("Invalid output ID: %s", output_id)
                return False
            
            # Validate duration
            if duration is not None:
                if not isinstance(duration, int) or duration < 0:
                    _LOGGER.warning("Invalid duration %s for output %s, using default", 
                                  duration, output_id)
                    duration = None
                elif duration > 3600:
                    _LOGGER.warning("Duration %s too long for output %s, capping at 3600s", 
                                  duration, output_id)
                    duration = 3600
            
            _LOGGER.info("Triggering output %s%s", output_id, 
                        f" for {duration}s" if duration else "")
            
            success = await asyncio.wait_for(
                self._client.trigger_output(output_id, duration),
                timeout=SERVICE_TIMEOUTS["output_control"]
            )
            
            if success:
                _LOGGER.info("Successfully triggered output %s", output_id)
                # Request immediate refresh to update state
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to trigger output %s", output_id)
                
            return success
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout triggering output %s", output_id)
            return False
        except Exception as err:
            _LOGGER.error("Error triggering output %s: %s", output_id, err)
            self._record_error(f"Output trigger error: {err}")
            return False

    # ===== ARM/DISARM METHODS - IMPROVED =====

    async def async_arm_away(self, user_code: Optional[str] = None) -> bool:
        """Arm the system in away mode with timeout."""
        return await self._execute_arm_disarm_command(
            "arm_away", self._client.arm_away, user_code
        )

    async def async_arm_stay(self, user_code: Optional[str] = None) -> bool:
        """Arm the system in stay mode with timeout."""
        return await self._execute_arm_disarm_command(
            "arm_stay", self._client.arm_stay, user_code
        )

    async def async_arm_home(self, user_code: Optional[str] = None) -> bool:
        """Arm the system in home mode with timeout."""
        return await self._execute_arm_disarm_command(
            "arm_home", self._client.arm_stay, user_code
        )

    async def async_disarm(self, user_code: Optional[str] = None) -> bool:
        """Disarm the system with timeout."""
        return await self._execute_arm_disarm_command(
            "disarm", self._client.disarm, user_code
        )

    async def _execute_arm_disarm_command(self, command_name: str, command_func, user_code: Optional[str] = None) -> bool:
        """Execute arm/disarm command with enhanced error handling."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot %s: client not connected", command_name)
                return False
            
            _LOGGER.info("Executing %s command", command_name)
            
            # Execute command with timeout
            if user_code:
                success = await asyncio.wait_for(
                    command_func(user_code),
                    timeout=SERVICE_TIMEOUTS["arm_disarm"]
                )
            else:
                success = await asyncio.wait_for(
                    command_func(),
                    timeout=SERVICE_TIMEOUTS["arm_disarm"]
                )
            
            if success:
                _LOGGER.info("Successfully executed %s", command_name)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to execute %s", command_name)
                
            return success
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during %s command", command_name)
            return False
        except Exception as err:
            _LOGGER.error("Error during %s: %s", command_name, err)
            self._record_error(f"{command_name} error: {err}")
            return False

    # ===== AREA-SPECIFIC METHODS - IMPROVED =====

    async def async_arm_away_area(self, area: int, user_code: Optional[str] = None) -> bool:
        """Arm specific area in away mode with validation."""
        return await self._execute_area_command(
            f"arm_away_area_{area}", area, "away", user_code
        )

    async def async_arm_stay_area(self, area: int, user_code: Optional[str] = None) -> bool:
        """Arm specific area in stay mode with validation."""
        return await self._execute_area_command(
            f"arm_stay_area_{area}", area, "stay", user_code
        )

    async def async_arm_home_area(self, area: int, user_code: Optional[str] = None) -> bool:
        """Arm specific area in home mode with validation."""
        return await self._execute_area_command(
            f"arm_home_area_{area}", area, "stay", user_code
        )

    async def async_disarm_area(self, area: int, user_code: Optional[str] = None) -> bool:
        """Disarm specific area with validation."""
        return await self._execute_area_command(
            f"disarm_area_{area}", area, "disarm", user_code
        )

    async def _execute_area_command(self, command_name: str, area: int, action: str, user_code: Optional[str] = None) -> bool:
        """Execute area-specific command with validation."""
        try:
            # Validate area number
            if not isinstance(area, int) or area < 1 or area > 32:
                _LOGGER.error("Invalid area number for %s: %s", command_name, area)
                return False
            
            if not self._client.is_connected:
                _LOGGER.warning("Cannot execute %s: client not connected", command_name)
                return False
            
            _LOGGER.info("Executing %s for area %d", command_name, area)
            
            # Choose appropriate method based on action
            if action == "away":
                command_func = self._client.arm_away_area
            elif action == "stay":
                command_func = self._client.arm_stay_area
            elif action == "disarm":
                command_func = self._client.disarm_with_pin if user_code else self._client.disarm
            else:
                _LOGGER.error("Unknown action for area command: %s", action)
                return False
            
            # Execute command with timeout
            if action == "disarm" and user_code:
                success = await asyncio.wait_for(
                    command_func(user_code),
                    timeout=SERVICE_TIMEOUTS["arm_disarm"]
                )
            elif action in ["away", "stay"]:
                success = await asyncio.wait_for(
                    command_func(area),
                    timeout=SERVICE_TIMEOUTS["arm_disarm"]
                )
            else:
                success = await asyncio.wait_for(
                    command_func(),
                    timeout=SERVICE_TIMEOUTS["arm_disarm"]
                )
            
            if success:
                _LOGGER.info("Successfully executed %s", command_name)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to execute %s", command_name)
                
            return success
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during %s", command_name)
            return False
        except Exception as err:
            _LOGGER.error("Error during %s: %s", command_name, err)
            self._record_error(f"{command_name} error: {err}")
            return False

    # ===== ZONE BYPASS METHODS - IMPROVED =====

    async def async_bypass_zone(self, zone_id: int) -> bool:
        """Bypass a zone with validation."""
        return await self._execute_zone_bypass_command(zone_id, True)

    async def async_unbypass_zone(self, zone_id: int) -> bool:
        """Remove bypass from a zone with validation."""
        return await self._execute_zone_bypass_command(zone_id, False)

    async def _execute_zone_bypass_command(self, zone_id: int, bypass: bool) -> bool:
        """Execute zone bypass command with validation."""
        try:
            # Validate zone ID
            if not isinstance(zone_id, int) or zone_id < 1 or zone_id > 248:
                _LOGGER.error("Invalid zone ID for bypass: %s", zone_id)
                return False
            
            if not self._client.is_connected:
                action = "bypass" if bypass else "unbypass"
                _LOGGER.warning("Cannot %s zone %s: client not connected", action, zone_id)
                return False
            
            action = "bypass" if bypass else "unbypass"
            _LOGGER.info("%s zone %s", action.capitalize(), zone_id)
            
            # Execute command with timeout
            if bypass:
                success = await asyncio.wait_for(
                    self._client.bypass_zone(zone_id),
                    timeout=SERVICE_TIMEOUTS["zone_bypass"]
                )
            else:
                success = await asyncio.wait_for(
                    self._client.unbypass_zone(zone_id),
                    timeout=SERVICE_TIMEOUTS["zone_bypass"]
                )
            
            if success:
                _LOGGER.info("Successfully %sed zone %s", action, zone_id)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to %s zone %s", action, zone_id)
                
            return success
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout during zone %s", action)
            return False
        except Exception as err:
            _LOGGER.error("Error during zone %s: %s", action, err)
            self._record_error(f"Zone {action} error: {err}")
            return False

    async def async_bulk_bypass_zones(self, zone_ids: List[int], bypass: bool = True) -> bool:
        """Bypass or unbypass multiple zones with enhanced error handling."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot bulk bypass zones: client not connected")
                return False
            
            # Validate all zone IDs first
            invalid_zones = [z for z in zone_ids if not isinstance(z, int) or z < 1 or z > 248]
            if invalid_zones:
                _LOGGER.error("Invalid zone IDs in bulk bypass: %s", invalid_zones)
                return False
            
            action = "bypass" if bypass else "unbypass"
            _LOGGER.info("Bulk %s for %d zones: %s", action, len(zone_ids), zone_ids)
            
            success_count = 0
            total_zones = len(zone_ids)
            
            for zone_id in zone_ids:
                try:
                    if bypass:
                        success = await asyncio.wait_for(
                            self._client.bypass_zone(zone_id),
                            timeout=SERVICE_TIMEOUTS["zone_bypass"]
                        )
                    else:
                        success = await asyncio.wait_for(
                            self._client.unbypass_zone(zone_id),
                            timeout=SERVICE_TIMEOUTS["zone_bypass"]
                        )
                    
                    if success:
                        success_count += 1
                    else:
                        _LOGGER.warning("Failed to %s zone %d", action, zone_id)
                        
                    # Small delay between commands to avoid overwhelming the panel
                    await asyncio.sleep(0.5)
                    
                except asyncio.TimeoutError:
                    _LOGGER.warning("Timeout %s zone %d", action, zone_id)
                except Exception as err:
                    _LOGGER.error("Error %s zone %d: %s", action, zone_id, err)
            
            # Request refresh after all operations
            await self.async_request_refresh()
            
            overall_success = success_count == total_zones
            _LOGGER.info("Bulk %s completed: %d/%d zones successful", 
                        action, success_count, total_zones)
            
            return overall_success
            
        except Exception as err:
            _LOGGER.error("Error in bulk zone %s: %s", action, err)
            self._record_error(f"Bulk {action} error: {err}")
            return False

    # ===== STATUS AND INFORMATION METHODS - IMPROVED =====

    def get_area_status(self, area: int) -> Dict[str, Any]:
        """Get status information for a specific area with validation."""
        if not isinstance(area, int) or area < 1 or area > 32:
            _LOGGER.error("Invalid area number: %s", area)
            return {}
        
        if not self.data:
            return {"area_number": area, "error": "No data available"}
        
        try:
            # Get area armed key (area_a_armed for area 1, area_b_armed for area 2, etc.)
            area_letter = chr(96 + area)  # 1=a, 2=b, etc.
            area_armed_key = f"area_{area_letter}_armed"
            
            # Build comprehensive area status
            area_status = {
                "area_number": area,
                "armed": self.data.get(area_armed_key, False),
                "ready_to_arm": self.data.get("ready_to_arm", True),
                "connection_state": self.data.get("connection_state", "unknown"),
                "last_update": self.data.get("last_update"),
            }
            
            # Add MODE 4 specific information if available
            if self.data.get("mode_4_features_active", False):
                # Area alarm status
                area_alarm_key = f"area_{area_letter}_alarm"
                area_status["area_alarm"] = self.data.get(area_alarm_key, False)
                
                # User who armed/disarmed
                area_user_key = f"area_{area_letter}_armed_by_user"
                area_status["armed_by_user"] = self.data.get(area_user_key)
                
                # Exit delay information
                area_exit_delays = self.data.get("area_exit_delays", {})
                area_status["exit_delay_remaining"] = area_exit_delays.get(area, 0)
            
            # Add zone information for this area (if available)
            zones_in_area = []
            zones = self.data.get("zones", {})
            for zone_id in zones.keys():
                # Note: In ECi panels, zone-to-area mapping is managed by the panel
                # We can't reliably determine which zones belong to which area
                # without querying the panel configuration
                pass
            
            if zones_in_area:
                area_status["zones_in_area"] = zones_in_area
                
                # Count open zones in this area
                open_zones = [z for z in zones_in_area if zones.get(z, False)]
                area_status["open_zones_count"] = len(open_zones)
                area_status["open_zones"] = open_zones
            
            return area_status
            
        except Exception as err:
            _LOGGER.error("Error getting area %d status: %s", area, err)
            return {"area_number": area, "error": str(err)}

    def get_all_areas_status(self) -> Dict[int, Dict[str, Any]]:
        """Get status for all configured areas."""
        if not self.data:
            return {}
        
        try:
            areas_status = {}
            
            # Get configured areas from various sources
            configured_areas = set()
            
            # From active_areas_detected
            if "active_areas_detected" in self.data:
                active_areas = self.data["active_areas_detected"]
                if isinstance(active_areas, (list, tuple, set)):
                    configured_areas.update(active_areas)
            
            # From config entry if available
            if self._config_entry:
                config_areas = self._config_entry.data.get("areas", [])
                if isinstance(config_areas, (list, tuple)):
                    configured_areas.update(config_areas)
            
            # Scan for area armed keys (fallback)
            if not configured_areas:
                for key in self.data.keys():
                    if key.startswith("area_") and key.endswith("_armed"):
                        area_letter = key.split("_")[1]
                        if len(area_letter) == 1 and area_letter.isalpha():
                            area_number = ord(area_letter) - ord('a') + 1
                            if 1 <= area_number <= 32:
                                configured_areas.add(area_number)
            
            # Default to area 1 if nothing found
            if not configured_areas:
                configured_areas = {1}
            
            # Get status for each configured area
            for area in sorted(configured_areas):
                areas_status[area] = self.get_area_status(area)
            
            return areas_status
            
        except Exception as err:
            _LOGGER.error("Error getting all areas status: %s", err)
            return {}

    # ===== UTILITY METHODS - IMPROVED =====

    @property
    def client(self):
        """Return the client instance."""
        return self._client

    def get_zone_name(self, zone_id: int, config_entry: ConfigEntry) -> str:
        """Get the configured name for a zone with fallback."""
        try:
            # Validate zone ID
            if not isinstance(zone_id, int) or zone_id < 1 or zone_id > 248:
                return f"Invalid Zone {zone_id}"
            
            # Check options for custom zone names
            zone_names = config_entry.options.get("zone_names", {})
            zone_key = f"zone_{zone_id}_name"
            
            if zone_key in zone_names and zone_names[zone_key]:
                return zone_names[zone_key]
                
            # Check entry data for zone names (from initial setup)
            entry_zone_names = config_entry.data.get("zone_names", {})
            if zone_key in entry_zone_names and entry_zone_names[zone_key]:
                return entry_zone_names[zone_key]
                
            # Default name with zero-padding
            return f"Zone {zone_id:03d}"
            
        except Exception as err:
            _LOGGER.error("Error getting zone name for zone %d: %s", zone_id, err)
            return f"Zone {zone_id:03d}"

    async def send_custom_command(self, command: str) -> bool:
        """Send a custom command to the panel with enhanced error handling."""
        try:
            if not isinstance(command, str) or not command.strip():
                _LOGGER.error("Invalid command: must be non-empty string")
                return False
            
            if not self._client.is_connected:
                _LOGGER.warning("Cannot send command: client not connected")
                return False
            
            command = command.strip()
            _LOGGER.info("Sending custom command: %s", command)
            
            # Send command with timeout
            response = await asyncio.wait_for(
                self._client._send_command(command),
                timeout=SERVICE_TIMEOUTS["custom_command"]
            )
            
            _LOGGER.info("Custom command response: %r", response)
            
            # Request refresh after custom command
            await self.async_request_refresh()
            
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout sending custom command '%s'", command)
            return False
        except Exception as err:
            _LOGGER.error("Error sending custom command '%s': %s", command, err)
            self._record_error(f"Custom command error: {err}")
            return False

    # ===== MODE 4 SPECIFIC METHODS - IMPROVED =====

    async def async_trigger_keypad_alarm(self, alarm_type: str) -> bool:
        """Trigger keypad alarm with validation (MODE 4 only)."""
        try:
            if not isinstance(alarm_type, str) or alarm_type not in ["panic", "fire", "medical"]:
                _LOGGER.error("Invalid keypad alarm type: %s", alarm_type)
                return False
            
            if not self._client.is_connected:
                _LOGGER.warning("Cannot trigger keypad alarm: client not connected")
                return False
            
            if not self._client.mode_4_features_active:
                _LOGGER.warning("Keypad alarms require MODE 4")
                return False
            
            _LOGGER.info("Triggering %s keypad alarm", alarm_type)
            
            # Execute appropriate command with timeout
            if alarm_type == "panic":
                success = await asyncio.wait_for(
                    self._client.trigger_keypad_panic_alarm(),
                    timeout=SERVICE_TIMEOUTS["custom_command"]
                )
            elif alarm_type == "fire":
                success = await asyncio.wait_for(
                    self._client.trigger_keypad_fire_alarm(),
                    timeout=SERVICE_TIMEOUTS["custom_command"]
                )
            elif alarm_type == "medical":
                success = await asyncio.wait_for(
                    self._client.trigger_keypad_medical_alarm(),
                    timeout=SERVICE_TIMEOUTS["custom_command"]
                )
            else:
                _LOGGER.error("Unknown keypad alarm type: %s", alarm_type)
                return False
            
            if success:
                _LOGGER.info("Successfully triggered %s keypad alarm", alarm_type)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to trigger %s keypad alarm", alarm_type)
                
            return success
            
        except asyncio.TimeoutError:
            _LOGGER.error("Timeout triggering %s keypad alarm", alarm_type)
            return False
        except Exception as err:
            _LOGGER.error("Error triggering %s keypad alarm: %s", alarm_type, err)
            self._record_error(f"Keypad alarm error: {err}")
            return False

    def get_mode_4_status(self) -> Dict[str, Any]:
        """Get MODE 4 specific status information with enhanced details."""
        try:
            if not self.data or not self.data.get("mode_4_features_active", False):
                return {
                    "mode_4_active": False,
                    "reason": "MODE 4 not active or no data available"
                }
            
            mode_4_status = {
                "mode_4_active": True,
                "protocol_mode": self.data.get("protocol_mode", 1),
                "firmware_version": self.data.get("firmware_version", "Unknown"),
                "supports_mode_4": self.data.get("supports_mode_4", False),
                "connection_state": self.data.get("connection_state", "unknown"),
                "last_update": self.data.get("last_update"),
            }
            
            # Keypad alarm status
            mode_4_status["keypad_alarms"] = {
                "panic": self.data.get("keypad_panic_alarm", False),
                "fire": self.data.get("keypad_fire_alarm", False),
                "medical": self.data.get("keypad_medical_alarm", False),
            }
            
            # Enhanced timing information
            timing_info = {}
            
            zone_entry_delays = self.data.get("zone_entry_delays", {})
            if zone_entry_delays:
                timing_info["zone_entry_delays"] = zone_entry_delays
                timing_info["max_entry_delay"] = max(zone_entry_delays.values())
                timing_info["zones_in_entry_delay"] = list(zone_entry_delays.keys())
            
            area_exit_delays = self.data.get("area_exit_delays", {})
            if area_exit_delays:
                timing_info["area_exit_delays"] = area_exit_delays
                timing_info["max_exit_delay"] = max(area_exit_delays.values())
                timing_info["areas_in_exit_delay"] = list(area_exit_delays.keys())
            
            mode_4_status["timing_info"] = timing_info
            
            # User tracking information
            user_tracking = {}
            for key, value in self.data.items():
                if key.endswith("_armed_by_user") and value is not None:
                    area_letter = key.split("_")[1]
                    area_number = ord(area_letter) - ord('a') + 1
                    user_tracking[f"area_{area_number}"] = value
            
            mode_4_status["user_tracking"] = user_tracking
            
            # Enhanced features status
            enhanced_features = {
                "programming_queries": bool(self.data.get("programming_queries_available")),
                "enhanced_status": bool(self.data.get("enhanced_status_available")),
                "user_tracking": bool(user_tracking),
                "enhanced_delays": bool(timing_info),
                "keypad_alarms": any(mode_4_status["keypad_alarms"].values()),
            }
            
            mode_4_status["enhanced_features"] = enhanced_features
            
            return mode_4_status
            
        except Exception as err:
            _LOGGER.error("Error getting MODE 4 status: %s", err)
            return {
                "mode_4_active": False,
                "error": str(err)
            }

    # ===== DIAGNOSTIC AND HEALTH METHODS - NEW =====

    def get_diagnostic_info(self) -> Dict[str, Any]:
        """Get comprehensive diagnostic information."""
        try:
            diagnostic_info = {
                "coordinator_info": {
                    "connection_state": self._connection_state.value,
                    "consecutive_failures": self._consecutive_failures,
                    "reconnect_attempts": self._reconnect_attempts,
                    "last_successful_update": self._last_successful_update.isoformat() if self._last_successful_update else None,
                    "update_interval": self.update_interval.total_seconds(),
                },
                "health_metrics": self.health_metrics,
                "client_info": {},
                "data_summary": {},
                "configuration": {},
            }
            
            # Add client diagnostic info if available
            if hasattr(self._client, 'get_debug_info'):
                try:
                    diagnostic_info["client_info"] = self._client.get_debug_info()
                except Exception as err:
                    diagnostic_info["client_info"] = {"error": str(err)}
            
            # Add data summary
            if self.data:
                zones = self.data.get("zones", {})
                outputs = self.data.get("outputs", {})
                
                diagnostic_info["data_summary"] = {
                    "total_zones": len(zones),
                    "active_zones": sum(1 for state in zones.values() if state),
                    "total_outputs": len(outputs),
                    "active_outputs": sum(1 for state in outputs.values() if state),
                    "data_keys": list(self.data.keys()),
                    "mode_4_active": self.data.get("mode_4_features_active", False),
                }
            
            # Add configuration info
            if self._config_entry:
                diagnostic_info["configuration"] = {
                    "entry_id": self._config_entry.entry_id,
                    "host": self._config_entry.data.get("host", "unknown"),
                    "port": self._config_entry.data.get("port", "unknown"),
                    "max_zones": self._config_entry.data.get("max_zones", "unknown"),
                    "max_outputs": self._config_entry.data.get("max_outputs", "unknown"),
                    "areas": self._config_entry.data.get("areas", "unknown"),
                    "auto_detect_zones": self._config_entry.data.get("auto_detect_zones", "unknown"),
                }
            
            return diagnostic_info
            
        except Exception as err:
            _LOGGER.error("Error getting diagnostic info: %s", err)
            return {"error": str(err)}

    async def async_run_health_check(self) -> Dict[str, Any]:
        """Run a comprehensive health check."""
        health_check = {
            "timestamp": dt_util.utcnow().isoformat(),
            "overall_status": "unknown",
            "checks": {},
            "recommendations": [],
        }
        
        try:
            # Check 1: Connection status
            if self._client.is_connected:
                health_check["checks"]["connection"] = {"status": "ok", "message": "Client connected"}
            else:
                health_check["checks"]["connection"] = {"status": "error", "message": "Client not connected"}
                health_check["recommendations"].append("Check network connectivity and panel status")
            
            # Check 2: Recent updates
            if self._last_successful_update:
                time_since_update = (dt_util.utcnow() - self._last_successful_update).total_seconds()
                if time_since_update < 300:  # 5 minutes
                    health_check["checks"]["recent_updates"] = {"status": "ok", "message": f"Last update {time_since_update:.0f}s ago"}
                else:
                    health_check["checks"]["recent_updates"] = {"status": "warning", "message": f"Last update {time_since_update:.0f}s ago"}
                    health_check["recommendations"].append("Recent updates are delayed - check connection stability")
            else:
                health_check["checks"]["recent_updates"] = {"status": "error", "message": "No successful updates"}
                health_check["recommendations"].append("No successful updates recorded")
            
            # Check 3: Success rate
            success_rate = self.success_rate
            if success_rate >= 95:
                health_check["checks"]["success_rate"] = {"status": "ok", "message": f"Success rate: {success_rate:.1f}%"}
            elif success_rate >= 80:
                health_check["checks"]["success_rate"] = {"status": "warning", "message": f"Success rate: {success_rate:.1f}%"}
                health_check["recommendations"].append("Update success rate is below optimal - check network stability")
            else:
                health_check["checks"]["success_rate"] = {"status": "error", "message": f"Success rate: {success_rate:.1f}%"}
                health_check["recommendations"].append("Low success rate indicates connection problems")
            
            # Check 4: Response time
            avg_response_time = self._health_metrics.get("average_response_time", 0)
            if avg_response_time < 2.0:
                health_check["checks"]["response_time"] = {"status": "ok", "message": f"Average response: {avg_response_time:.2f}s"}
            elif avg_response_time < 5.0:
                health_check["checks"]["response_time"] = {"status": "warning", "message": f"Average response: {avg_response_time:.2f}s"}
                health_check["recommendations"].append("Response time is elevated - check network latency")
            else:
                health_check["checks"]["response_time"] = {"status": "error", "message": f"Average response: {avg_response_time:.2f}s"}
                health_check["recommendations"].append("High response time indicates network or panel issues")
            
            # Check 5: Data integrity
            if self.data and isinstance(self.data, dict):
                essential_keys = ["zones", "outputs", "connection_state"]
                missing_keys = [key for key in essential_keys if key not in self.data]
                
                if not missing_keys:
                    health_check["checks"]["data_integrity"] = {"status": "ok", "message": "All essential data present"}
                else:
                    health_check["checks"]["data_integrity"] = {"status": "warning", "message": f"Missing keys: {missing_keys}"}
                    health_check["recommendations"].append("Some data keys are missing - panel may not be fully configured")
            else:
                health_check["checks"]["data_integrity"] = {"status": "error", "message": "No valid data available"}
                health_check["recommendations"].append("No valid data - check panel communication")
            
            # Determine overall status
            statuses = [check["status"] for check in health_check["checks"].values()]
            if "error" in statuses:
                health_check["overall_status"] = "error"
            elif "warning" in statuses:
                health_check["overall_status"] = "warning"
            else:
                health_check["overall_status"] = "ok"
            
        except Exception as err:
            health_check["checks"]["health_check_error"] = {"status": "error", "message": str(err)}
            health_check["overall_status"] = "error"
            _LOGGER.error("Error during health check: %s", err)
        
        return health_check

    # ===== LEGACY COMPATIBILITY METHODS =====

    async def async_refresh_data(self) -> None:
        """Legacy method for refreshing data."""
        await self.async_request_refresh()

    def get_last_update_success(self) -> bool:
        """Legacy method for checking last update success."""
        return self.last_update_success

    def get_connection_status(self) -> str:
        """Legacy method for getting connection status."""
        return self._connection_state.value
