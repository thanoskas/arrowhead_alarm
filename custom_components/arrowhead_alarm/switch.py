"""Support for Arrowhead Alarm Panel output switches."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import ArrowheadDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead output switches from config entry with manual configuration."""
    _LOGGER.info("=== SWITCH PLATFORM SETUP START ===")
    _LOGGER.info("Entry ID: %s", config_entry.entry_id)
    
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    
    entities = []
    
    # Check client status directly first
    _LOGGER.info("=== CHECKING CLIENT STATUS ===")
    client_outputs = client._status.get("outputs", {})
    _LOGGER.info("Client outputs: %s", list(client_outputs.keys()))
    _LOGGER.info("Client status keys: %s", list(client._status.keys()))
    
    # Check config entry data
    _LOGGER.info("=== CHECKING CONFIG ENTRY ===")
    max_outputs_config = config_entry.data.get("max_outputs", "NOT_SET")
    _LOGGER.info("Max outputs from config: %s", max_outputs_config)
    
    # Wait for initial data and retry if needed
    _LOGGER.info("=== CHECKING COORDINATOR DATA ===")
    if not coordinator.data:
        _LOGGER.info("No coordinator data, requesting refresh")
        await coordinator.async_request_refresh()
        
    # Wait a bit more if still no data
    if not coordinator.data:
        _LOGGER.info("Still no coordinator data, waiting and retrying")
        import asyncio
        await asyncio.sleep(2)
        await coordinator.async_request_refresh()
        
    if coordinator.data:
        _LOGGER.info("=== COORDINATOR DATA FOUND ===")
        _LOGGER.info("Coordinator data keys: %s", list(coordinator.data.keys()))
        
        # Create output switches for configured outputs
        outputs = coordinator.data.get("outputs", {})
        _LOGGER.info("Found outputs in coordinator data: %s", list(outputs.keys()))
        
        for output_id in outputs.keys():
            _LOGGER.info("Creating switch for output %s", output_id)
            entities.append(
                ArrowheadOutputSwitch(coordinator, config_entry, panel_config, output_id)
            )
        
        # Log configuration info
        total_outputs = coordinator.data.get("total_outputs_detected", len(outputs))
        detection_method = coordinator.data.get("output_detection_method", "unknown")
        
        _LOGGER.info("Created %d output switches (configured %d total outputs via %s)", 
                    len(entities), total_outputs, detection_method)
    else:
        _LOGGER.warning("=== NO COORDINATOR DATA ===")
        # Fallback: try to use client data directly
        if client_outputs:
            _LOGGER.info("Using client outputs directly as fallback: %s", list(client_outputs.keys()))
            for output_id in client_outputs.keys():
                _LOGGER.info("Creating switch for output %s (from client)", output_id)
                entities.append(
                    ArrowheadOutputSwitch(coordinator, config_entry, panel_config, output_id)
                )
        else:
            _LOGGER.error("No outputs found in client or coordinator")
    
    _LOGGER.info("=== SWITCH PLATFORM SETUP COMPLETE ===")
    _LOGGER.info("Total entities created: %d", len(entities))
    async_add_entities(entities)


class ArrowheadOutputSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of an Arrowhead alarm panel output switch."""

    def __init__(
        self,
        coordinator: ArrowheadDataUpdateCoordinator,
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
        
        # FIXED: Use the same device identifier as other platforms
        # This ensures all entities appear under the same device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},  # Same as alarm_control_panel.py
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
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success
            and self.coordinator.data is not None
            and self._output_id in self.coordinator.data.get("outputs", {})
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
        """Return extra state attributes."""
        attributes = {
            "output_id": self._output_id,
            "panel_type": self._panel_config["name"],
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
                
        return attributes

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the output on."""
        _LOGGER.debug("Turning on output %s", self._output_id)
        
        # Get duration from kwargs or use default
        duration = kwargs.get("duration", 5)  # Default 5 seconds
        
        success = await self.coordinator.async_trigger_output(self._output_id, duration)
        
        if not success:
            _LOGGER.error("Failed to turn on output %s", self._output_id)
        else:
            _LOGGER.info("Successfully turned on output %s for %s seconds", self._output_id, duration)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the output off."""
        _LOGGER.debug("Turning off output %s", self._output_id)
        
        # For most alarm panels, outputs are momentary and turn off automatically
        # This method exists for interface compatibility but may not do anything
        _LOGGER.info("Output %s turn off requested (outputs are typically momentary)", self._output_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()