"""Data update coordinator for Arrowhead Alarm Panel."""
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
    """Class to manage fetching data from the Arrowhead alarm panel."""

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
        await self.async_config_entry_first_refresh()
        
        _LOGGER.info("ArrowheadDataUpdateCoordinator setup complete")

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
            
            # Get initial status
            await self._async_update_data()
            
            # Log what data we have
            if self.data:
                _LOGGER.info("First refresh complete - Data keys: %s", list(self.data.keys()))
                if "outputs" in self.data:
                    _LOGGER.info("Outputs in coordinator data: %s", list(self.data["outputs"].keys()))
                else:
                    _LOGGER.warning("No outputs found in coordinator data")
            else:
                _LOGGER.error("No data after first refresh")
                
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

    async def async_arm_away(self, user_code: str = None) -> bool:
        """Arm the system in away mode."""
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
            _LOGGER.error("Error arming system: %s", err)
            return False

    async def async_arm_stay(self, user_code: str = None) -> bool:
        """Arm the system in home/stay mode."""
        try:
            # FIXED: is_connected is a property, not method
            if not self._client.is_connected:
                _LOGGER.warning("Cannot arm system: client not connected")
                return False
                
            success = await self._client.arm_stay()
            
            if success:
                _LOGGER.info("System armed in home mode")
                await self.async_request_refresh()
            else:
                _LOGGER.error("Failed to arm system in home mode")
                
            return success
            
        except Exception as err:
            _LOGGER.error("Error arming system: %s", err)
            return False

    async def async_disarm(self, user_code: str = None) -> bool:
        """Disarm the system."""
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