"""Arrowhead Alarm Panel alarm control panel platform with dynamic icons."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    ATTR_ZONE_STATUS,
    ATTR_READY_TO_ARM,
    ATTR_MAINS_POWER,
    ATTR_BATTERY_STATUS,
    ATTR_PANEL_TYPE,
    ATTR_TOTAL_ZONES,
    ATTR_MAX_ZONES,
    ATTR_ACTIVE_AREAS,
)
from .coordinator import ArrowheadDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Icon mappings for different alarm states
ALARM_STATE_ICONS = {
    AlarmControlPanelState.DISARMED: "mdi:shield-off",
    AlarmControlPanelState.ARMED_AWAY: "mdi:shield-lock",
    AlarmControlPanelState.ARMED_HOME: "mdi:shield-half-full",
    AlarmControlPanelState.ARMING: "mdi:shield-sync",
    AlarmControlPanelState.PENDING: "mdi:shield-sync",
    AlarmControlPanelState.TRIGGERED: "mdi:shield-alert",
}

# Fallback icon
DEFAULT_ALARM_ICON = "mdi:shield-home"

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead alarm control panel from config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    
    async_add_entities([
        ArrowheadAlarmControlPanel(coordinator, config_entry, panel_config)
    ])

class ArrowheadAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of an Arrowhead Alarm Panel with dynamic icons."""

    def __init__(
        self,
        coordinator: ArrowheadDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
    ) -> None:
        """Initialize the alarm control panel."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._attr_name = f"Arrowhead {panel_config['name']}"
        self._attr_unique_id = f"{config_entry.entry_id}_alarm_panel"
        
        # Set supported features based on panel capabilities
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY |
            AlarmControlPanelEntityFeature.ARM_HOME
        )
        
        # Set code format - no code required since PIN is configured
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_code_arm_required = False  # PIN already configured in client
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Arrowhead {panel_config['name']}",
            "manufacturer": "Arrowhead Alarm Products",
            "model": panel_config["name"],
            "sw_version": self.coordinator.data.get("firmware_version") if self.coordinator.data else None,
        }

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of the alarm control panel using new enum."""
        if not self.coordinator.data:
            return AlarmControlPanelState.DISARMED
            
        data = self.coordinator.data
        
        # Check for alarm condition first
        if data.get("alarm", False):
            return AlarmControlPanelState.TRIGGERED
            
        # Check for arming/pending state
        if data.get("arming", False):
            return AlarmControlPanelState.PENDING
            
        # Check armed states
        if data.get("armed", False):
            if data.get("stay_mode", False):
                return AlarmControlPanelState.ARMED_HOME
            else:
                return AlarmControlPanelState.ARMED_AWAY
                
        return AlarmControlPanelState.DISARMED

    @property
    def icon(self) -> str:
        """Return dynamic icon based on current alarm state."""
        current_state = self.alarm_state
        
        # Get icon for current state
        icon = ALARM_STATE_ICONS.get(current_state, DEFAULT_ALARM_ICON)
        
        # Special handling for triggered state - use animated/attention-getting icon
        if current_state == AlarmControlPanelState.TRIGGERED:
            return "mdi:shield-alert"
        
        # Special handling for pending/arming state
        if current_state in [AlarmControlPanelState.ARMING, AlarmControlPanelState.PENDING]:
            return "mdi:shield-sync"
        
        # Check for system issues and modify icon accordingly
        if self.coordinator.data:
            data = self.coordinator.data
            
            # If there are system issues, use warning variants
            has_issues = (
                not data.get("mains_ok", True) or
                not data.get("battery_ok", True) or
                not data.get("line_ok", True) or
                data.get("tamper_alarm", False)
            )
            
            if has_issues:
                if current_state == AlarmControlPanelState.DISARMED:
                    return "mdi:shield-alert-outline"
                elif current_state in [AlarmControlPanelState.ARMED_AWAY, AlarmControlPanelState.ARMED_HOME]:
                    return "mdi:shield-lock-outline"
        
        return icon

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes with comprehensive output and zone information."""
        if not self.coordinator.data:
            return {}
            
        data = self.coordinator.data
        zones = data.get("zones", {})
        zone_alarms = data.get("zone_alarms", {})
        outputs = data.get("outputs", {})
        
        # Get active zones, alarms, and outputs
        active_zones = [zone_id for zone_id, state in zones.items() if state]
        alarm_zones = [zone_id for zone_id, state in zone_alarms.items() if state]
        active_outputs = [output_id for output_id, state in outputs.items() if state]
        
        attributes = {
            ATTR_READY_TO_ARM: data.get("ready_to_arm", False),
            ATTR_MAINS_POWER: data.get("mains_ok", True),
            ATTR_BATTERY_STATUS: data.get("battery_ok", True),
            ATTR_PANEL_TYPE: data.get("panel_type", "unknown"),
            "status_message": data.get("status_message", "Unknown"),
            "connection_state": data.get("connection_state", "unknown"),
            "active_zones": active_zones,
            "alarm_zones": alarm_zones,
            "active_outputs": active_outputs,
            "total_zones_configured": len(zones),
            "total_outputs_configured": len(outputs),
            "current_icon": self.icon,  # Include current icon for debugging
        }
        
        # Add output detection information
        if "total_outputs_detected" in data:
            attributes["total_outputs_detected"] = data["total_outputs_detected"]
        if "max_outputs_detected" in data:
            attributes["max_outputs_detected"] = data["max_outputs_detected"]
        if "output_detection_method" in data:
            attributes["output_detection_method"] = data["output_detection_method"]
        if "output_ranges" in data:
            attributes["output_ranges"] = data["output_ranges"]
            # Add expander summary for outputs
            ranges = data["output_ranges"]
            expander_count = len([k for k in ranges.keys() if k != "main_panel"])
            if expander_count > 0:
                attributes["output_expanders_detected"] = expander_count
                
            # Add detailed output hardware info
            main_outputs = len(ranges.get("main_panel", []))
            expander_outputs = sum(len(v) for k, v in ranges.items() if k != "main_panel")
            attributes["output_hardware_summary"] = {
                "main_panel_outputs": main_outputs,
                "expander_outputs": expander_outputs,
                "total_expanders": expander_count
            }
        
        # Add panel version and model information
        if "firmware_version" in data:
            attributes["firmware_version"] = data["firmware_version"]
            
        if "panel_model" in data:
            attributes["panel_model"] = data["panel_model"]
            
        # Add protocol information for ECi panels
        if data.get("panel_type") == "eci":
            if "protocol_mode" in data:
                attributes["protocol_mode"] = data["protocol_mode"]
            if "supports_mode_4" in data:
                attributes["supports_mode_4"] = data["supports_mode_4"]
                
        # Add ECi-specific zone detection info
        if data.get("panel_type") == "eci":
            if "total_zones_detected" in data:
                attributes[ATTR_TOTAL_ZONES] = data["total_zones_detected"]
            if "max_zones_detected" in data:
                attributes[ATTR_MAX_ZONES] = data["max_zones_detected"]
            if "active_areas_detected" in data:
                attributes[ATTR_ACTIVE_AREAS] = data["active_areas_detected"]
            if "detection_method" in data:
                attributes["zone_detection_method"] = data["detection_method"]
            if "expanders_detected" in data:
                attributes["zone_expanders_detected"] = len(data["expanders_detected"])
            if "zones_in_areas" in data:
                attributes["zones_in_areas"] = data["zones_in_areas"]
                
        # Add area status if supported
        if self._panel_config["supports_areas"]:
            if "area_a_armed" in data:
                attributes["area_a_armed"] = data["area_a_armed"]
            if "area_b_armed" in data:
                attributes["area_b_armed"] = data["area_b_armed"]
                
        # Add RF status if supported
        if self._panel_config["supports_rf"]:
            if "rf_battery_low" in data:
                attributes["rf_battery_low"] = data["rf_battery_low"]
            if "receiver_ok" in data:
                attributes["receiver_ok"] = data["receiver_ok"]
            if "sensor_watch_alarm" in data:
                attributes["sensor_watch_alarm"] = data["sensor_watch_alarm"]
                
        # Add comprehensive system status
        system_status = []
        if not data.get("mains_ok", True):
            system_status.append("AC Power Fail")
        if not data.get("battery_ok", True):
            system_status.append("Battery Low")
        if data.get("tamper_alarm", False):
            system_status.append("Tamper Alarm")
        if not data.get("line_ok", True):
            system_status.append("Phone Line Fail")
        if not data.get("dialer_ok", True):
            system_status.append("Dialer Fail")
        if not data.get("fuse_ok", True):
            system_status.append("Fuse/Output Fail")
            
        # Add RF-specific system status
        if self._panel_config["supports_rf"]:
            if not data.get("receiver_ok", True):
                system_status.append("RF Receiver Fail")
            if data.get("rf_battery_low", False):
                system_status.append("RF Battery Low")
            if data.get("sensor_watch_alarm", False):
                system_status.append("Sensor Watch Alarm")
                
        attributes["system_status"] = system_status
        
        # Add communication statistics
        attributes["communication_stats"] = {
            "last_update": data.get("last_update"),
            "communication_errors": data.get("communication_errors", 0),
            "connection_state": data.get("connection_state", "unknown")
        }
        
        # Add hardware summary for easy overview
        hardware_summary = {
            "panel_type": data.get("panel_type", "unknown"),
            "total_zones": len(zones),
            "total_outputs": len(outputs),
            "active_zones": len(active_zones),
            "active_outputs": len(active_outputs),
            "alarm_zones": len(alarm_zones)
        }
        
        # Add detection methods summary
        detection_summary = {}
        if data.get("panel_type") == "eci" and "detection_method" in data:
            detection_summary["zone_detection"] = data["detection_method"]
        if "output_detection_method" in data:
            detection_summary["output_detection"] = data["output_detection_method"]
            
        if detection_summary:
            hardware_summary["detection_methods"] = detection_summary
            
        attributes["hardware_summary"] = hardware_summary
        
        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and
            self.coordinator.data is not None and
            self.coordinator.data.get("connection_state") == "connected"
        )

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command."""
        _LOGGER.info("Disarming %s", self._attr_name)
        success = await self.coordinator.async_disarm()
        
        if not success:
            _LOGGER.error("Failed to disarm %s", self._attr_name)

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command."""
        _LOGGER.info("Arming %s (away mode)", self._attr_name)
        success = await self.coordinator.async_arm_away()
        
        if not success:
            _LOGGER.error("Failed to arm %s (away mode)", self._attr_name)

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command."""
        _LOGGER.info("Arming %s (stay mode)", self._attr_name)
        
        # Add debug logging to see what's happening
        _LOGGER.debug("Coordinator data before arm_stay: %s", 
                     list(self.coordinator.data.keys()) if self.coordinator.data else "No data")
        _LOGGER.debug("Client connection state: %s", self.coordinator.client.is_connected)
        
        success = await self.coordinator.async_arm_stay()
        
        if success:
            _LOGGER.info("Successfully armed %s in stay mode", self._attr_name)
        else:
            _LOGGER.error("Failed to arm %s (stay mode)", self._attr_name)
            # Add additional debugging
            _LOGGER.debug("Coordinator data after failed arm_stay: %s", 
                         list(self.coordinator.data.keys()) if self.coordinator.data else "No data")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()