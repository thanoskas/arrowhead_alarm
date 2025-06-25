"""Arrowhead Alarm Panel button platform for zone bypass control."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import ArrowheadDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead zone bypass buttons from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    
    entities = []
    
    # Wait for initial data
    if not coordinator.data:
        await coordinator.async_request_refresh()
        
    if coordinator.data:
        # Create bypass buttons for each configured zone
        zones = coordinator.data.get("zones", {})
        for zone_id in zones.keys():
            entities.append(
                ArrowheadZoneBypassButton(coordinator, config_entry, panel_config, zone_id)
            )
    
    async_add_entities(entities)

class ArrowheadZoneBypassButton(CoordinatorEntity, ButtonEntity):
    """Button entity for zone bypass control."""

    def __init__(
        self,
        coordinator: ArrowheadDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        zone_id: int,
    ) -> None:
        """Initialize the zone bypass button."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._zone_id = zone_id
        
        # Get zone name from options if available, otherwise use defaults
        self._zone_name = self._get_zone_name(config_entry, zone_id)
        
        self._attr_name = f"{self._zone_name} Bypass"
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_bypass_button"
        
        # FIXED: Use consistent device identifier to match other platforms
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},  # Same as other platforms
            "name": f"Arrowhead {panel_config['name']}",
            "manufacturer": "Arrowhead Alarm Products",
            "model": panel_config["name"],
        }

    def _get_zone_name(self, config_entry: ConfigEntry, zone_id: int) -> str:
        """Get zone name from config entry options or use default."""
        # Check config entry data first (from initial setup)
        zone_names = config_entry.data.get("zone_names", {})
        zone_name = zone_names.get(f"zone_{zone_id}")
        
        if not zone_name:
            # Check options (from options flow)
            zone_names = config_entry.options.get("zone_names", {})
            zone_name = zone_names.get(f"zone_{zone_id}")
        
        if not zone_name:
            # Use default zone name
            zone_name = self._get_default_zone_name(zone_id)
            
        return zone_name

    def _get_default_zone_name(self, zone_id: int) -> str:
        """Get default zone name with zero-padding format."""
        # Always use zero-padded format for consistency
        return f"Zone {zone_id:03d}"

    @property
    def icon(self) -> str:
        """Return the icon for the button."""
        if not self.coordinator.data:
            return "mdi:shield-off-outline"
            
        zone_bypassed = self.coordinator.data.get("zone_bypassed", {})
        is_bypassed = zone_bypassed.get(self._zone_id, False)
        
        if is_bypassed:
            return "mdi:shield-off"  # Solid red shield when bypassed
        else:
            return "mdi:shield-off-outline"  # Outline when not bypassed

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and
            self.coordinator.data is not None and
            self.coordinator.data.get("connection_state") == "connected"
        )

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        attributes = {
            "zone_id": self._zone_id,
            "zone_name": self._zone_name,
            "panel_type": self._panel_config["name"],
        }
        
        if self.coordinator.data:
            zone_bypassed = self.coordinator.data.get("zone_bypassed", {})
            zone_state = self.coordinator.data.get("zones", {})
            zone_alarms = self.coordinator.data.get("zone_alarms", {})
            zone_troubles = self.coordinator.data.get("zone_troubles", {})
            
            attributes.update({
                "currently_bypassed": zone_bypassed.get(self._zone_id, False),
                "zone_open": zone_state.get(self._zone_id, False),
                "zone_alarm": zone_alarms.get(self._zone_id, False),
                "zone_trouble": zone_troubles.get(self._zone_id, False),
                "last_update": self.coordinator.data.get("last_update"),
            })
            
            # Add expander information for ECi panels
            if self.coordinator.data.get("panel_type") == "eci":
                from .const import detect_expander_from_zone, PANEL_TYPE_ECI
                expander = detect_expander_from_zone(self._zone_id, PANEL_TYPE_ECI)
                attributes["expander"] = expander
                
            # Add bypass status summary
            bypass_reason = "Active" if attributes["currently_bypassed"] else "None"
            if attributes["zone_trouble"]:
                bypass_reason += " (Trouble)"
            if attributes["zone_alarm"]:
                bypass_reason += " (Alarm)"
                
            attributes["bypass_status"] = bypass_reason
                
        return attributes

    async def async_press(self) -> None:
        """Handle button press to toggle zone bypass."""
        if not self.coordinator.data:
            _LOGGER.error("No coordinator data available for zone %d bypass", self._zone_id)
            return
            
        zone_bypassed = self.coordinator.data.get("zone_bypassed", {})
        is_currently_bypassed = zone_bypassed.get(self._zone_id, False)
        
        if is_currently_bypassed:
            # Remove bypass
            _LOGGER.info("Removing bypass from %s (zone %d)", self._zone_name, self._zone_id)
            success = await self.coordinator.async_unbypass_zone(self._zone_id)
            action = "unbypass"
        else:
            # Add bypass
            _LOGGER.info("Bypassing %s (zone %d)", self._zone_name, self._zone_id)
            success = await self.coordinator.async_bypass_zone(self._zone_id)
            action = "bypass"
        
        if not success:
            _LOGGER.error("Failed to %s %s (zone %d)", action, self._zone_name, self._zone_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update zone name in case it was changed in options
        new_zone_name = self._get_zone_name(self._config_entry, self._zone_id)
        if new_zone_name != self._zone_name:
            self._zone_name = new_zone_name
            self._attr_name = f"{self._zone_name} Bypass"
            
        self.async_write_ha_state()