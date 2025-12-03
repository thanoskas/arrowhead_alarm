"""Support for Arrowhead Alarm Panel output switches - IMPROVED VERSION."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArrowheadECiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead output switches from config entry - IMPROVED VERSION."""
    _LOGGER.info("=== SWITCH PLATFORM SETUP START (IMPROVED) ===")
    _LOGGER.info("Entry ID: %s", config_entry.entry_id)
    
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    
    entities = []
    
    # IMPROVED: Ensure coordinator has data with retry mechanism
    await _ensure_coordinator_data_with_retry(coordinator)
    
    # IMPROVED: Get outputs from multiple sources with fallback
    outputs_to_create = await _get_outputs_for_switches(coordinator, config_entry, client)
    
    if outputs_to_create:
        _LOGGER.info("Creating switches for outputs: %s", sorted(outputs_to_create))
        
        for output_id in outputs_to_create:
            _LOGGER.debug("Creating switch for output %d", output_id)
            entities.append(
                ArrowheadOutputSwitch(coordinator, config_entry, panel_config, output_id)
            )
        
        _LOGGER.info("Created %d output switches", len(entities))
    else:
        _LOGGER.warning("No outputs found - no switches will be created")
    
    _LOGGER.info("=== SWITCH PLATFORM SETUP COMPLETE ===")
    async_add_entities(entities)


async def _ensure_coordinator_data_with_retry(coordinator) -> None:
    """Ensure coordinator has data with retry mechanism."""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries and not coordinator.data:
        _LOGGER.info("Coordinator has no data, attempting refresh (attempt %d/%d)", 
                    retry_count + 1, max_retries)
        
        try:
            await coordinator.async_request_refresh()
            
            if coordinator.data:
                _LOGGER.info("Coordinator data obtained successfully")
                break
            else:
                # Wait a bit before next retry
                import asyncio
                await asyncio.sleep(2)
                
        except Exception as err:
            _LOGGER.warning("Error refreshing coordinator (attempt %d): %s", retry_count + 1, err)
            
        retry_count += 1
    
    if not coordinator.data:
        _LOGGER.error("Failed to get coordinator data after %d attempts", max_retries)


async def _get_outputs_for_switches(coordinator, config_entry: ConfigEntry, client) -> set:
    """Get outputs for switch creation from multiple sources with fallback."""
    outputs_to_create = set()
    
    # Priority 1: Get from coordinator data
    if coordinator.data and "outputs" in coordinator.data:
        coordinator_outputs = coordinator.data.get("outputs", {})
        if coordinator_outputs:
            outputs_to_create.update(coordinator_outputs.keys())
            _LOGGER.info("Found %d outputs in coordinator data: %s", 
                        len(coordinator_outputs), sorted(coordinator_outputs.keys()))
    
    # Priority 2: Get from client status directly
    if not outputs_to_create and hasattr(client, '_status'):
        client_outputs = client._status.get("outputs", {})
        if client_outputs:
            outputs_to_create.update(client_outputs.keys())
            _LOGGER.info("Found %d outputs in client status: %s", 
                        len(client_outputs), sorted(client_outputs.keys()))
    
    # Priority 3: Get from config entry (manual configuration)
    if not outputs_to_create:
        max_outputs = config_entry.data.get("max_outputs", 4)
        if max_outputs and max_outputs > 0:
            outputs_to_create = set(range(1, max_outputs + 1))
            _LOGGER.info("Using manual output configuration: 1-%d (%d outputs)", 
                        max_outputs, len(outputs_to_create))
            
            # IMPROVED: Initialize outputs in coordinator data
            if coordinator.data is not None:
                if "outputs" not in coordinator.data:
                    coordinator.data["outputs"] = {}
                
                for output_id in outputs_to_create:
                    if output_id not in coordinator.data["outputs"]:
                        coordinator.data["outputs"][output_id] = False
                        
                _LOGGER.info("Initialized %d outputs in coordinator data", len(outputs_to_create))
    
    # Final fallback
    if not outputs_to_create:
        _LOGGER.warning("No outputs detected from any source, using fallback (1-4)")
        outputs_to_create = {1, 2, 3, 4}
        
        # Initialize in coordinator
        if coordinator.data is not None:
            if "outputs" not in coordinator.data:
                coordinator.data["outputs"] = {}
            for output_id in outputs_to_create:
                coordinator.data["outputs"][output_id] = False
    
    return outputs_to_create


class ArrowheadOutputSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an Arrowhead alarm panel output switch - IMPROVED VERSION."""

    def __init__(
        self,
        coordinator: ArrowheadECiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        output_id: int,
    ) -> None:
        """Initialize the output switch."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._output_id = output_id
        self._attr_device_class = SwitchDeviceClass.SWITCH
        
        # CONSISTENT: Use the same device identifier as other platforms
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Arrowhead {panel_config['name']}",
            "manufacturer": "Arrowhead Alarm Products",
            "model": panel_config["name"],
            "sw_version": self.coordinator.data.get("firmware_version") if self.coordinator.data else None,
        }
        
        # Set up entity attributes
        self._attr_name = f"Output {output_id}"
        self._attr_unique_id = f"{config_entry.entry_id}_output_{output_id}"
        self._attr_icon = "mdi:electric-switch"

    @property
    def available(self) -> bool:
        """Return if entity is available - IMPROVED."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and "outputs" in self.coordinator.data
            and (
                self._output_id in self.coordinator.data.get("outputs", {})
                or self.coordinator.data.get("connection_state") == "connected"
            )
        )

    @property
    def is_on(self) -> bool:
        """Return true if the output is on."""
        if not self.coordinator.data:
            return False
            
        outputs = self.coordinator.data.get("outputs", {})
        return outputs.get(self._output_id, False)

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes - IMPROVED."""
        attributes = {
            "output_id": self._output_id,
            "panel_type": self._panel_config["name"],
            "entity_platform": "switch",
        }
        
        if self.coordinator.data:
            # Add output-specific information if available
            output_ranges = self.coordinator.data.get("output_ranges", {})
            for range_name, output_list in output_ranges.items():
                if self._output_id in output_list:
                    attributes["output_range"] = range_name
                    break
            
            # Add detection method
            detection_method = self.coordinator.data.get("output_detection_method")
            if detection_method:
                attributes["detection_method"] = detection_method
            
            # Add connection status
            attributes["connection_state"] = self.coordinator.data.get("connection_state", "unknown")
            
            # Add last update time
            last_update = self.coordinator.data.get("last_update")
            if last_update:
                attributes["last_update"] = last_update
                
        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on - IMPROVED."""
        _LOGGER.debug("Turning on output %d", self._output_id)
        
        # Validate duration parameter
        duration = kwargs.get("duration", 5)  # Default 5 seconds
        
        # IMPROVED: Validate and sanitize duration
        if not isinstance(duration, (int, float)) or duration < 0:
            _LOGGER.warning("Invalid duration %s for output %d, using default 5 seconds", 
                          duration, self._output_id)
            duration = 5
        elif duration > 3600:  # Cap at 1 hour
            _LOGGER.warning("Duration %s too large for output %d, capping at 3600 seconds", 
                          duration, self._output_id)
            duration = 3600
        
        try:
            success = await self.coordinator.async_trigger_output(self._output_id, int(duration))
            
            if not success:
                _LOGGER.error("Failed to turn on output %d", self._output_id)
            else:
                _LOGGER.info("Successfully turned on output %d for %d seconds", 
                           self._output_id, duration)
                
                # IMPROVED: Update state immediately for better UX
                if self.coordinator.data and "outputs" in self.coordinator.data:
                    self.coordinator.data["outputs"][self._output_id] = True
                    self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error turning on output %d: %s", self._output_id, err)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off - IMPROVED."""
        _LOGGER.debug("Turning off output %d", self._output_id)
        
        try:
            # IMPROVED: Check if client supports turn_output_off method
            client = self.coordinator.client
            
            if hasattr(client, 'turn_output_off'):
                success = await client.turn_output_off(self._output_id)
                
                if success:
                    _LOGGER.info("Successfully turned off output %d", self._output_id)
                    
                    # Update state immediately
                    if self.coordinator.data and "outputs" in self.coordinator.data:
                        self.coordinator.data["outputs"][self._output_id] = False
                        self.async_write_ha_state()
                else:
                    _LOGGER.warning("Failed to turn off output %d", self._output_id)
            else:
                # Fallback: Most ECi outputs are momentary
                _LOGGER.info("Output %d turn off requested (outputs may be momentary)", self._output_id)
                
        except Exception as err:
            _LOGGER.error("Error turning off output %d: %s", self._output_id, err)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator - IMPROVED."""
        # IMPROVED: Update device info if firmware version becomes available
        if (self.coordinator.data and 
            "firmware_version" in self.coordinator.data and 
            self.coordinator.data["firmware_version"] and
            self._attr_device_info.get("sw_version") != self.coordinator.data["firmware_version"]):
            
            self._attr_device_info["sw_version"] = self.coordinator.data["firmware_version"]
        
        self.async_write_ha_state()
