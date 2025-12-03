"""Arrowhead Alarm Panel binary sensor platform."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN
from .coordinator import ArrowheadECiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead binary sensors from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    
    entities = []
    
    # Wait for initial data
    if not coordinator.data:
        await coordinator.async_request_refresh()
        
    if coordinator.data:
        # Create zone sensors
        zones = coordinator.data.get("zones", {})
        for zone_id in zones.keys():
            entities.extend([
                ArrowheadZoneSensor(coordinator, config_entry, panel_config, zone_id, "state"),
                ArrowheadZoneSensor(coordinator, config_entry, panel_config, zone_id, "alarm"),
                ArrowheadZoneSensor(coordinator, config_entry, panel_config, zone_id, "trouble"),
                ArrowheadZoneSensor(coordinator, config_entry, panel_config, zone_id, "bypassed"),
            ])
            
            # Add RF supervision sensor if supported
            if panel_config["supports_rf"]:
                entities.append(
                    ArrowheadZoneSensor(coordinator, config_entry, panel_config, zone_id, "supervise_fail")
                )
        
        # Create system status sensors
        entities.extend([
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "mains_ok", "AC Power"),
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "battery_ok", "Battery"),
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "ready_to_arm", "Ready to Arm"),
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "line_ok", "Phone Line"),
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "dialer_ok", "Dialer"),
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "fuse_ok", "Fuse/Output"),
        ])
        
        # Add RF system sensors if supported
        if panel_config["supports_rf"]:
            entities.extend([
                ArrowheadSystemSensor(coordinator, config_entry, panel_config, "receiver_ok", "RF Receiver"),
                ArrowheadSystemSensor(coordinator, config_entry, panel_config, "rf_battery_low", "RF Battery Low"),
                ArrowheadSystemSensor(coordinator, config_entry, panel_config, "sensor_watch_alarm", "Sensor Watch"),
            ])
            
        # Add tamper sensor
        entities.append(
            ArrowheadSystemSensor(coordinator, config_entry, panel_config, "tamper_alarm", "Panel Tamper")
        )
    
    async_add_entities(entities)

class ArrowheadZoneSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an Arrowhead zone sensor."""

    def __init__(
        self,
        coordinator: ArrowheadECiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        zone_id: int,
        sensor_type: str,
    ) -> None:
        """Initialize the zone sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._zone_id = zone_id
        self._sensor_type = sensor_type
        
        # Get zone name from config
        zone_name = self._get_zone_name(config_entry, zone_id)
        
        # Set names and IDs
        type_names = {
            "state": "",
            "alarm": "Alarm",
            "trouble": "Trouble", 
            "bypassed": "Bypassed",
            "supervise_fail": "RF Supervision"
        }
        
        type_suffix = type_names.get(sensor_type, sensor_type.title())
        
        if sensor_type == "state":
            self._attr_name = zone_name
        else:
            self._attr_name = f"{zone_name} {type_suffix}"
            
        self._attr_unique_id = f"{config_entry.entry_id}_zone_{zone_id}_{sensor_type}"
        
        # Set device class based on sensor type
        if sensor_type == "state":
            self._attr_device_class = BinarySensorDeviceClass.OPENING
        elif sensor_type == "alarm":
            self._attr_device_class = BinarySensorDeviceClass.SAFETY
        elif sensor_type in ["trouble", "supervise_fail"]:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        else:
            self._attr_device_class = None
            
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
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
    def is_on(self) -> Optional[bool]:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return None
            
        data_key_map = {
            "state": "zones",
            "alarm": "zone_alarms", 
            "trouble": "zone_troubles",
            "bypassed": "zone_bypassed",
            "supervise_fail": "zone_supervise_fail"
        }
        
        data_key = data_key_map.get(self._sensor_type)
        if not data_key:
            return None
            
        zone_data = self.coordinator.data.get(data_key, {})
        return zone_data.get(self._zone_id, False)

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
            "sensor_type": self._sensor_type,
            "panel_type": self._panel_config["name"],
            "zone_name": self._get_zone_name(self._config_entry, self._zone_id),
        }
        
        if self.coordinator.data:
            # Add zone-specific information
            zones_data = self.coordinator.data.get("zones", {})
            if self._zone_id in zones_data:
                attributes["zone_configured"] = True
            else:
                attributes["zone_configured"] = False
                
            # Add current state information for all sensor types
            zone_states = {
                "zone_open": self.coordinator.data.get("zones", {}).get(self._zone_id, False),
                "zone_alarm": self.coordinator.data.get("zone_alarms", {}).get(self._zone_id, False),
                "zone_trouble": self.coordinator.data.get("zone_troubles", {}).get(self._zone_id, False),
                "zone_bypassed": self.coordinator.data.get("zone_bypassed", {}).get(self._zone_id, False),
            }
            
            # Add RF supervision if supported
            if self._panel_config["supports_rf"]:
                zone_states["zone_rf_supervision_fail"] = self.coordinator.data.get("zone_supervise_fail", {}).get(self._zone_id, False)
            
            attributes.update(zone_states)
                
            # Add expander information for ECi panels
            if self.coordinator.data.get("panel_type") == "eci":
                from .const import detect_expander_from_zone
                expander = detect_expander_from_zone(self._zone_id)
                attributes["expander"] = expander
                
            # Add zone status summary
            status_issues = []
            if zone_states["zone_alarm"]:
                status_issues.append("Alarm")
            if zone_states["zone_trouble"]:
                status_issues.append("Trouble")
            if zone_states["zone_bypassed"]:
                status_issues.append("Bypassed")
            if self._panel_config["supports_rf"] and zone_states.get("zone_rf_supervision_fail"):
                status_issues.append("RF Fail")
                
            attributes["status_summary"] = ", ".join(status_issues) if status_issues else "Normal"
                
        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Update zone name in case it was changed in options
        new_zone_name = self._get_zone_name(self._config_entry, self._zone_id)
        
        type_names = {
            "state": "",
            "alarm": "Alarm",
            "trouble": "Trouble", 
            "bypassed": "Bypassed",
            "supervise_fail": "RF Supervision"
        }
        
        type_suffix = type_names.get(self._sensor_type, self._sensor_type.title())
        
        if self._sensor_type == "state":
            new_name = new_zone_name
        else:
            new_name = f"{new_zone_name} {type_suffix}"
            
        # Update name if it changed
        if new_name != self._attr_name:
            self._attr_name = new_name
            
        self.async_write_ha_state()

class ArrowheadSystemSensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of an Arrowhead system status sensor."""

    def __init__(
        self,
        coordinator: ArrowheadECiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        status_key: str,
        friendly_name: str,
    ) -> None:
        """Initialize the system sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._status_key = status_key
        self._friendly_name = friendly_name
        
        self._attr_name = f"{panel_config['name']} {friendly_name}"
        self._attr_unique_id = f"{config_entry.entry_id}_system_{status_key}"
        
        # Set device class based on status type
        if status_key in ["mains_ok", "battery_ok", "line_ok", "dialer_ok", "fuse_ok", "receiver_ok"]:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        elif status_key in ["ready_to_arm"]:
            self._attr_device_class = BinarySensorDeviceClass.SAFETY
        elif status_key in ["tamper_alarm", "rf_battery_low", "sensor_watch_alarm"]:
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        else:
            self._attr_device_class = None
            
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Arrowhead {panel_config['name']}",
            "manufacturer": "Arrowhead Alarm Products",
            "model": panel_config["name"],
        }

    @property
    def is_on(self) -> Optional[bool]:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return None
            
        value = self.coordinator.data.get(self._status_key)
        
        # For "ok" type sensors, invert the logic (sensor is "on" when there's a problem)
        if self._status_key.endswith("_ok"):
            return not value if value is not None else None
        
        # For alarm/problem type sensors, return value directly
        return value

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
            "status_key": self._status_key,
            "panel_type": self._panel_config["name"],
            "sensor_category": "system",
        }
        
        if self.coordinator.data:
            attributes.update({
                "connection_state": self.coordinator.data.get("connection_state", "unknown"),
                "last_update": self.coordinator.data.get("last_update"),
                "communication_errors": self.coordinator.data.get("communication_errors", 0),
            })
            
            # Add related system status
            if self._status_key == "ready_to_arm":
                open_zones = [zone_id for zone_id, is_open in self.coordinator.data.get("zones", {}).items() if is_open]
                bypassed_zones = [zone_id for zone_id, is_bypassed in self.coordinator.data.get("zone_bypassed", {}).items() if is_bypassed]
                
                attributes.update({
                    "open_zones": open_zones,
                    "bypassed_zones": bypassed_zones,
                    "armed_state": self.coordinator.data.get("armed", False),
                })
            
            elif self._status_key in ["mains_ok", "battery_ok"]:
                # Add power related info
                attributes.update({
                    "mains_power": self.coordinator.data.get("mains_ok", True),
                    "battery_status": self.coordinator.data.get("battery_ok", True),
                    "dialer_status": self.coordinator.data.get("dialer_ok", True),
                })
                
        return attributes

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()