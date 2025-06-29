"""Data update coordinator for Arrowhead Alarm Panel with area support."""
import asyncio
import logging
from datetime import timedelta
from typing import Dict, Any, Optional
from enum import Enum

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class ConnectionState(Enum):
    """Represents the connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"

class ArrowheadDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Arrowhead alarm panel with area support."""

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
        
    @property
    def connection_state(self) -> ConnectionState:
        """Return the current connection state."""
        return self._connection_state
        
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
            
            # Notify all listeners
            for callback in self._connection_state_callbacks:
                try:
                    callback(new_state)
                except Exception as err:
                    _LOGGER.error("Error in connection state callback: %s", err)

    async def async_setup(self) -> None:
        """Set up the coordinator."""
        _LOGGER.debug("Setting up ArrowheadDataUpdateCoordinator")
        
        # Set initial state
        self._update_connection_state(ConnectionState.CONNECTING)
        
        # Perform first refresh to validate connection
        try:
            await self.async_config_entry_first_refresh()
            _LOGGER.info("ArrowheadDataUpdateCoordinator setup complete")
        except Exception as err:
            _LOGGER.error("Failed to setup coordinator: %s", err)
            # Don't raise here, let the setup continue and try again later
            self._update_connection_state(ConnectionState.DISCONNECTED)

    async def async_config_entry_first_refresh(self) -> None:
        """Perform first refresh and ensure connection is established."""
        try:
            _LOGGER.debug("Starting first refresh for coordinator")
            
            # Ensure client is connected - FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.debug("Client not connected, attempting connection")
                success = await self._client.connect()
                if not success:
                    raise UpdateFailed("Failed to connect to alarm panel during first refresh")
            
            # Get initial status and store it in self.data
            data = await self._async_update_data()
            
            # FIXED: Explicitly set self.data if it's not set by parent class
            if not self.data and data:
                self.data = data
            
            # Log what data we have
            if self.data:
                _LOGGER.info("First refresh complete - Data keys: %s", list(self.data.keys()))
                if "outputs" in self.data:
                    _LOGGER.info("Outputs in coordinator data: %s", list(self.data["outputs"].keys()))
                else:
                    _LOGGER.warning("No outputs found in coordinator data")
            else:
                _LOGGER.error("No data after first refresh - Data is: %s", self.data)
                # Try calling the parent method to ensure proper initialization
                await super().async_config_entry_first_refresh()
                
        except Exception as err:
            _LOGGER.error("Error during first refresh: %s", err)
            raise UpdateFailed(f"First refresh failed: {err}")

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from the alarm panel."""
        try:
            # Ensure connection - FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.debug("Client disconnected, attempting reconnection")
                success = await self._client.connect()
                if not success:
                    raise UpdateFailed("Failed to reconnect to alarm panel")
            
            # Get status from client
            status = await self._client.get_status()
            
            if status is None:
                raise UpdateFailed("No data received from alarm panel")
            
            # Debug log the status data
            _LOGGER.debug("Status received from client: outputs=%s", 
                         list(status.get("outputs", {}).keys()) if "outputs" in status else "None")
            
            # Update connection state
            self._update_connection_state(ConnectionState.CONNECTED)
            
            return status
            
        except Exception as err:
            self._update_connection_state(ConnectionState.DISCONNECTED)
            _LOGGER.error("Failed to update data: %s", err)
            raise UpdateFailed(f"Error communicating with alarm panel: {err}")

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator."""
        _LOGGER.debug("Shutting down ArrowheadDataUpdateCoordinator")
        
        try:
            # Disconnect the client
            if self._client:
                await self._client.disconnect()
        except Exception as err:
            _LOGGER.error("Error during shutdown: %s", err)
        finally:
            self._update_connection_state(ConnectionState.DISCONNECTED)
            
        _LOGGER.info("ArrowheadDataUpdateCoordinator shutdown complete")

    async def async_trigger_output(self, output_id: int, duration: Optional[int] = None) -> bool:
        """Trigger an output for a specified duration."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot trigger output %s: client not connected", output_id)
                return False
                
            success = await self._client.trigger_output(output_id, duration)
            
            if success:
                _LOGGER.info("Successfully triggered output %s", output_id)
                # Request immediate refresh to update state
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to trigger output %s", output_id)
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error triggering output %s: %s", output_id, err)
            return False

    # ===== GENERAL ARM/DISARM METHODS (All Areas) =====

    async def async_arm_away(self, user_code: str = None) -> bool:
        """Arm the system in away mode (all areas)."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot arm system: client not connected")
                return False
                
            success = await self._client.arm_away()
            
            if success:
                _LOGGER.info("System armed in away mode")
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to arm system in away mode")
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error arming system in away mode: %s", err)
            return False

    async def async_arm_stay(self, user_code: str = None) -> bool:
        """Arm the system in stay mode (all areas)."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot arm system: client not connected")
                return False
                
            # FIXED: Call arm_stay() instead of arm_home()
            success = await self._client.arm_stay()
            
            if success:
                _LOGGER.info("System armed in stay mode")
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to arm system in stay mode")
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error arming system in stay mode: %s", err)
            return False

    # ADDED: Alias method for compatibility
    async def async_arm_home(self, user_code: str = None) -> bool:
        """Arm the system in home mode (alias for stay mode)."""
        return await self.async_arm_stay(user_code)

    async def async_disarm(self, user_code: str = None) -> bool:
        """Disarm the system (all areas)."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot disarm system: client not connected")
                return False
                
            success = await self._client.disarm()
            
            if success:
                _LOGGER.info("System disarmed")
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to disarm system")
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error disarming system: %s", err)
            return False

    # ===== AREA-SPECIFIC ARM/DISARM METHODS =====

    async def async_arm_away_area(self, area: int, user_code: str = None) -> bool:
        """Arm specific area in away mode."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot arm area %d: client not connected", area)
                return False
            
            _LOGGER.info("Attempting to arm area %d in away mode", area)
            
            # Check if client supports area-specific commands
            if hasattr(self._client, 'arm_away_area'):
                success = await self._client.arm_away_area(area)
            else:
                _LOGGER.warning("Client doesn't support area-specific arm away, using general command")
                success = await self._client.arm_away()
            
            if success:
                _LOGGER.info("Area %d armed in away mode", area)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to arm area %d in away mode", area)
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error arming area %d in away mode: %s", area, err)
            return False

    async def async_arm_stay_area(self, area: int, user_code: str = None) -> bool:
        """Arm specific area in stay mode."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot arm area %d: client not connected", area)
                return False
            
            _LOGGER.info("Attempting to arm area %d in stay mode", area)
            
            # Check if client supports area-specific commands
            if hasattr(self._client, 'arm_stay_area'):
                success = await self._client.arm_stay_area(area)
            else:
                _LOGGER.warning("Client doesn't support area-specific arm stay, using general command")
                success = await self._client.arm_stay()
            
            if success:
                _LOGGER.info("Area %d armed in stay mode", area)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to arm area %d in stay mode", area)
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error arming area %d in stay mode: %s", area, err)
            return False

    # ADDED: Alias method for area home arming
    async def async_arm_home_area(self, area: int, user_code: str = None) -> bool:
        """Arm specific area in home mode (alias for stay mode)."""
        return await self.async_arm_stay_area(area, user_code)

    async def async_disarm_area(self, area: int, user_code: str = None) -> bool:
        """Disarm specific area."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot disarm area %d: client not connected", area)
                return False
            
            _LOGGER.info("Attempting to disarm area %d", area)
            
            # Check if client supports area-specific commands
            if hasattr(self._client, 'disarm_area'):
                success = await self._client.disarm_area(area)
            else:
                _LOGGER.warning("Client doesn't support area-specific disarm, using general command")
                success = await self._client.disarm()
            
            if success:
                _LOGGER.info("Area %d disarmed", area)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to disarm area %d", area)
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error disarming area %d: %s", area, err)
            return False

    # ===== ZONE BYPASS METHODS =====

    async def async_bypass_zone(self, zone_id: int) -> bool:
        """Bypass a zone."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot bypass zone %s: client not connected", zone_id)
                return False
                
            success = await self._client.bypass_zone(zone_id)
            
            if success:
                _LOGGER.info("Successfully bypassed zone %s", zone_id)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to bypass zone %s", zone_id)
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error bypassing zone %s: %s", zone_id, err)
            return False

    async def async_unbypass_zone(self, zone_id: int) -> bool:
        """Remove bypass from a zone."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot unbypass zone %s: client not connected", zone_id)
                return False
                
            success = await self._client.unbypass_zone(zone_id)
            
            if success:
                _LOGGER.info("Successfully unbypassed zone %s", zone_id)
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to unbypass zone %s", zone_id)
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error unbypassing zone %s: %s", zone_id, err)
            return False

    async def async_bulk_bypass_zones(self, zone_ids: list, bypass: bool = True) -> bool:
        """Bypass or unbypass multiple zones at once."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot bulk bypass zones: client not connected")
                return False
            
            action = "bypass" if bypass else "unbypass"
            _LOGGER.info("Bulk %s for zones: %s", action, zone_ids)
            
            success_count = 0
            total_zones = len(zone_ids)
            
            for zone_id in zone_ids:
                try:
                    if bypass:
                        success = await self._client.bypass_zone(zone_id)
                    else:
                        success = await self._client.unbypass_zone(zone_id)
                    
                    if success:
                        success_count += 1
                    else:
                        _LOGGER.warning("Failed to %s zone %d", action, zone_id)
                        
                    # Small delay between commands to avoid overwhelming the panel
                    await asyncio.sleep(0.5)
                    
                except Exception as err:
                    _LOGGER.error("Error %s zone %d: %s", action, zone_id, err)
            
            # Request refresh after all operations
            await self.async_request_refresh()
            
            overall_success = success_count == total_zones
            _LOGGER.info("Bulk %s completed: %d/%d zones successful", action, success_count, total_zones)
            
            return overall_success
            
        except Exception as err:
            _LOGGER.error("Error in bulk zone %s: %s", action, err)
            return False

    # ===== AREA STATUS METHODS =====

    def get_area_status(self, area: int) -> Dict[str, Any]:
        """Get status information for a specific area."""
        if not self.data:
            return {}
        
        # Get area armed key
        area_letter = chr(64 + area).lower()  # 1=a, 2=b, etc.
        area_armed_key = f"area_{area_letter}_armed"
        
        # Get zones for this area
        zones_in_areas = self.data.get("zones_in_areas", {})
        area_zones = zones_in_areas.get(area, [])
        
        if isinstance(area_zones, set):
            area_zones = list(area_zones)
        
        # Calculate area-specific status
        zone_data = self.data.get("zones", {})
        zone_alarms = self.data.get("zone_alarms", {})
        zone_troubles = self.data.get("zone_troubles", {})
        zone_bypassed = self.data.get("zone_bypassed", {})
        
        area_status = {
            "area_number": area,
            "armed": self.data.get(area_armed_key, False),
            "zones": area_zones,
            "total_zones": len(area_zones),
            "open_zones": [z for z in area_zones if zone_data.get(z, False)],
            "alarm_zones": [z for z in area_zones if zone_alarms.get(z, False)],
            "trouble_zones": [z for z in area_zones if zone_troubles.get(z, False)],
            "bypassed_zones": [z for z in area_zones if zone_bypassed.get(z, False)],
        }
        
        # Calculate ready to arm status for this area
        area_status["ready_to_arm"] = len(area_status["open_zones"]) == 0
        
        return area_status

    def get_all_areas_status(self) -> Dict[int, Dict[str, Any]]:
        """Get status for all detected areas."""
        if not self.data:
            return {}
        
        areas_status = {}
        
        # Detect areas from zones_in_areas or area armed keys
        detected_areas = set()
        
        # Method 1: From zones_in_areas
        zones_in_areas = self.data.get("zones_in_areas", {})
        detected_areas.update(zones_in_areas.keys())
        
        # Method 2: From area armed keys
        for key in self.data.keys():
            if key.startswith("area_") and key.endswith("_armed"):
                area_letter = key.split("_")[1]
                if len(area_letter) == 1 and area_letter.isalpha():
                    area_number = ord(area_letter.upper()) - ord('A') + 1
                    if 1 <= area_number <= 8:  # Reasonable range
                        detected_areas.add(area_number)
        
        # Get status for each detected area
        for area in sorted(detected_areas):
            areas_status[area] = self.get_area_status(area)
        
        return areas_status

    # ===== UTILITY METHODS =====

    @property
    def client(self):
        """Return the client instance."""
        return self._client

    def get_zone_name(self, zone_id: int, config_entry: ConfigEntry) -> str:
        """Get the configured name for a zone."""
        # First check options for custom zone names
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

    async def send_custom_command(self, command: str) -> bool:
        """Send a custom command to the panel."""
        try:
            if not self._client.is_connected:
                _LOGGER.warning("Cannot send command: client not connected")
                return False
            
            _LOGGER.info("Sending custom command: %s", command)
            
            response = await self._client._send_command(command)
            _LOGGER.info("Custom command response: %r", response)
            
            # Request refresh after custom command
            await self.async_request_refresh()
            
            return True
            
        except Exception as err:
            _LOGGER.error("Error sending custom command '%s': %s", command, err)
            return False