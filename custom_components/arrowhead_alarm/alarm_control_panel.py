# Enhanced alarm_control_panel.py with arming effects
"""Arrowhead Alarm Panel alarm control panel platform with arming status effects."""
import asyncio
import logging
from datetime import datetime, timedelta
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
from homeassistant.helpers.event import async_track_time_interval
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

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead alarm control panel from config entry with area support."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    
    entities = []
    
    # Always create the main panel (all areas combined)
    entities.append(
        ArrowheadAlarmControlPanel(coordinator, config_entry, panel_config)
    )
    
    # Wait for initial data to detect areas
    if not coordinator.data:
        await coordinator.async_request_refresh()
    
    # Create individual area panels if multi-area support is detected
    if panel_config["supports_areas"] and coordinator.data:
        _LOGGER.info("Checking for multi-area configuration...")
        
        # Check various sources for active areas
        active_areas = set()
        
        # Method 1: Check detected areas from zone detection
        detected_areas = coordinator.data.get("active_areas_detected", set())
        if isinstance(detected_areas, (list, tuple)):
            active_areas.update(detected_areas)
        elif isinstance(detected_areas, set):
            active_areas.update(detected_areas)
        
        # Method 2: Check config entry for configured areas
        config_areas = config_entry.data.get("areas", [])
        if isinstance(config_areas, (list, tuple)):
            active_areas.update(config_areas)
        
        # Method 3: Check for area status keys in data
        for key in coordinator.data.keys():
            if key.startswith("area_") and key.endswith("_armed"):
                # Extract area number from key like "area_a_armed", "area_b_armed"
                area_letter = key.split("_")[1]
                if len(area_letter) == 1 and area_letter.isalpha():
                    area_number = ord(area_letter.upper()) - ord('A') + 1
                    if area_number <= 8:  # Reasonable limit for areas
                        active_areas.add(area_number)
        
        _LOGGER.info("Detected active areas: %s", sorted(active_areas))
        
        # Create area-specific panels if more than one area detected
        if len(active_areas) > 1:
            for area in sorted(active_areas):
                if 1 <= area <= 8:  # Reasonable area range
                    _LOGGER.info("Creating area-specific panel for area %d", area)
                    entities.append(
                        ArrowheadAreaAlarmControlPanel(coordinator, config_entry, panel_config, area)
                    )
        else:
            _LOGGER.info("Single area detected, no need for area-specific panels")
    
    _LOGGER.info("Created %d alarm control panel entities", len(entities))
    async_add_entities(entities)

class ArrowheadAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of an Arrowhead Alarm Panel with arming effects."""

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
        
        # Arming effects state
        self._arming_state = "idle"  # idle, arming, armed, disarming
        self._arming_start_time = None
        self._exit_delay_seconds = 30  # Default exit delay
        self._arming_progress = 0
        self._arming_time_remaining = 0
        self._arming_cancel_listener = None
        
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
        """Return the state of the alarm control panel with arming effects."""
        if not self.coordinator.data:
            return AlarmControlPanelState.DISARMED
            
        data = self.coordinator.data
        
        # Check for alarm condition first
        if data.get("alarm", False):
            self._update_arming_state("alarm")
            return AlarmControlPanelState.TRIGGERED
            
        # Check for arming/pending state with effects
        if data.get("arming", False) or self._arming_state == "arming":
            self._update_arming_state("arming")
            return AlarmControlPanelState.PENDING
            
        # Check armed states - for main panel, check if ANY area is armed
        if self._panel_config["supports_areas"]:
            # Check individual area states
            area_a_armed = data.get("area_a_armed", False)
            area_b_armed = data.get("area_b_armed", False)
            
            if area_a_armed or area_b_armed:
                self._update_arming_state("armed")
                if data.get("stay_mode", False):
                    return AlarmControlPanelState.ARMED_HOME
                else:
                    return AlarmControlPanelState.ARMED_AWAY
        else:
            # Single area panel
            if data.get("armed", False):
                self._update_arming_state("armed")
                if data.get("stay_mode", False):
                    return AlarmControlPanelState.ARMED_HOME
                else:
                    return AlarmControlPanelState.ARMED_AWAY
        
        # If we get here, system is disarmed
        self._update_arming_state("idle")
        return AlarmControlPanelState.DISARMED

    def _update_arming_state(self, new_state: str):
        """Update arming state and manage effects."""
        if self._arming_state != new_state:
            old_state = self._arming_state
            self._arming_state = new_state
            
            _LOGGER.debug("Arming state changed: %s -> %s", old_state, new_state)
            
            # Handle state transitions
            if new_state == "arming":
                self._start_arming_sequence()
            elif new_state in ["armed", "idle", "alarm"]:
                self._stop_arming_sequence()
                
    def _start_arming_sequence(self):
        """Start the arming sequence with progress tracking."""
        self._arming_start_time = datetime.now()
        self._arming_progress = 0
        self._arming_time_remaining = self._exit_delay_seconds
        
        _LOGGER.info("Starting arming sequence with %d second delay", self._exit_delay_seconds)
        
        # Start progress tracking
        self._arming_cancel_listener = async_track_time_interval(
            self.hass,
            self._update_arming_progress,
            timedelta(seconds=1)
        )
        
    def _stop_arming_sequence(self):
        """Stop the arming sequence."""
        if self._arming_cancel_listener:
            self._arming_cancel_listener()
            self._arming_cancel_listener = None
            
        self._arming_progress = 0
        self._arming_time_remaining = 0
        self._arming_start_time = None
        
        _LOGGER.debug("Arming sequence stopped")
        
    @callback
    def _update_arming_progress(self, now):
        """Update arming progress during exit delay."""
        if not self._arming_start_time:
            return
            
        elapsed = (now - self._arming_start_time).total_seconds()
        self._arming_time_remaining = max(0, self._exit_delay_seconds - elapsed)
        self._arming_progress = min(100, (elapsed / self._exit_delay_seconds) * 100)
        
        # Update the entity state
        self.async_write_ha_state()
        
        # Stop if we've reached the end of the delay
        if self._arming_time_remaining <= 0:
            self._stop_arming_sequence()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes with arming effects information."""
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
            
            # Arming effects attributes
            "arming_state": self._arming_state,
            "arming_progress": self._arming_progress,
            "arming_time_remaining": self._arming_time_remaining,
            "exit_delay_seconds": self._exit_delay_seconds,
        }
        
        # Add arming status details
        if self._arming_state == "arming":
            attributes.update({
                "arming_started_at": self._arming_start_time.isoformat() if self._arming_start_time else None,
                "arming_progress_text": f"{self._arming_progress:.1f}% ({self._arming_time_remaining:.0f}s remaining)",
                "arming_status": "Exit delay in progress",
            })
        elif self._arming_state == "armed":
            attributes.update({
                "arming_status": "System armed",
                "arming_progress_text": "Complete",
            })
        elif self._arming_state == "alarm":
            attributes.update({
                "arming_status": "ALARM TRIGGERED",
                "arming_progress_text": "Alarm active",
            })
        else:
            attributes.update({
                "arming_status": "Disarmed",
                "arming_progress_text": "Ready",
            })
        
        # Add area status if supported
        if self._panel_config["supports_areas"]:
            attributes.update({
                "area_a_armed": data.get("area_a_armed", False),
                "area_b_armed": data.get("area_b_armed", False),
                "supports_areas": True,
            })
            
            # Add area-specific zone information
            zones_in_areas = data.get("zones_in_areas", {})
            if zones_in_areas:
                attributes["zones_in_areas"] = {str(k): list(v) if isinstance(v, set) else v for k, v in zones_in_areas.items()}
                
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
                attributes[ATTR_ACTIVE_AREAS] = list(data["active_areas_detected"]) if isinstance(data["active_areas_detected"], set) else data["active_areas_detected"]
            if "detection_method" in data:
                attributes["zone_detection_method"] = data["detection_method"]
            if "expanders_detected" in data:
                attributes["zone_expanders_detected"] = len(data["expanders_detected"])
                
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
        
        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and
            self.coordinator.data is not None and
            self.coordinator.data.get("connection_state") == "connected"
        )

    @property
    def icon(self) -> str:
        """Return icon based on arming state."""
        if self._arming_state == "arming":
            # Animated icon during arming
            if self._arming_progress < 25:
                return "mdi:shield-sync"
            elif self._arming_progress < 50:
                return "mdi:shield-half-full"
            elif self._arming_progress < 75:
                return "mdi:shield-sync"
            else:
                return "mdi:shield-outline"
        elif self._arming_state == "armed":
            return "mdi:shield-check"
        elif self._arming_state == "alarm":
            return "mdi:shield-alert"
        else:
            return "mdi:shield-home"

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command."""
        _LOGGER.info("Disarming %s", self._attr_name)
        
        # Cancel any active arming sequence
        if self._arming_state == "arming":
            self._stop_arming_sequence()
            _LOGGER.info("Arming sequence cancelled by disarm command")
        
        success = await self.coordinator.async_disarm()
        
        if not success:
            _LOGGER.error("Failed to disarm %s", self._attr_name)

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command with arming effects."""
        _LOGGER.info("Arming %s (away mode)", self._attr_name)
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        success = await self.coordinator.async_arm_away()
        
        if not success:
            _LOGGER.error("Failed to arm %s (away mode)", self._attr_name)
            # Cancel arming sequence on failure
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command with arming effects."""
        _LOGGER.info("Arming %s (stay mode)", self._attr_name)
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        success = await self.coordinator.async_arm_stay()
        
        if success:
            _LOGGER.info("Successfully armed %s in stay mode", self._attr_name)
        else:
            _LOGGER.error("Failed to arm %s (stay mode)", self._attr_name)
            # Cancel arming sequence on failure
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check if actual panel state changed and update arming state accordingly
        if self.coordinator.data:
            panel_armed = self.coordinator.data.get("armed", False)
            panel_arming = self.coordinator.data.get("arming", False)
            
            # If panel reports armed and we were arming, complete the sequence
            if panel_armed and self._arming_state == "arming":
                self._stop_arming_sequence()
                self._update_arming_state("armed")
            # If panel reports not arming and we think we are, stop the sequence
            elif not panel_arming and not panel_armed and self._arming_state == "arming":
                self._stop_arming_sequence()
                self._update_arming_state("idle")
        
        self.async_write_ha_state()


class ArrowheadAreaAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Representation of a specific area on an Arrowhead Alarm Panel with arming effects."""

    def __init__(
        self,
        coordinator: ArrowheadDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        area_number: int,
    ) -> None:
        """Initialize the area alarm control panel."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._area_number = area_number
        self._attr_name = f"Arrowhead {panel_config['name']} Area {area_number}"
        self._attr_unique_id = f"{config_entry.entry_id}_alarm_panel_area_{area_number}"
        
        # Set supported features
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY |
            AlarmControlPanelEntityFeature.ARM_HOME
        )
        
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_code_arm_required = False
        
        # Arming effects state for this area
        self._arming_state = "idle"
        self._arming_start_time = None
        self._exit_delay_seconds = 30
        self._arming_progress = 0
        self._arming_time_remaining = 0
        self._arming_cancel_listener = None
        
        # Set device info (same device, different entity)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Arrowhead {panel_config['name']}",
            "manufacturer": "Arrowhead Alarm Products",
            "model": panel_config["name"],
            "sw_version": self.coordinator.data.get("firmware_version") if self.coordinator.data else None,
        }

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of this specific area with arming effects."""
        if not self.coordinator.data:
            return AlarmControlPanelState.DISARMED
            
        data = self.coordinator.data
        
        # Check for alarm condition in this area's zones
        if data.get("alarm", False):
            area_zones = self._get_area_zones()
            alarm_zones = [zone_id for zone_id, state in data.get("zone_alarms", {}).items() if state]
            if any(zone in area_zones for zone in alarm_zones):
                self._update_arming_state("alarm")
                return AlarmControlPanelState.TRIGGERED
        
        # Check for arming state
        if self._arming_state == "arming":
            return AlarmControlPanelState.PENDING
        
        # Check area-specific armed state
        area_armed_key = self._get_area_armed_key()
        if data.get(area_armed_key, False):
            self._update_arming_state("armed")
            if data.get("stay_mode", False):
                return AlarmControlPanelState.ARMED_HOME
            else:
                return AlarmControlPanelState.ARMED_AWAY
        
        self._update_arming_state("idle")
        return AlarmControlPanelState.DISARMED

    def _update_arming_state(self, new_state: str):
        """Update arming state for this area."""
        if self._arming_state != new_state:
            old_state = self._arming_state
            self._arming_state = new_state
            
            _LOGGER.debug("Area %d arming state changed: %s -> %s", self._area_number, old_state, new_state)
            
            # Handle state transitions
            if new_state == "arming":
                self._start_arming_sequence()
            elif new_state in ["armed", "idle", "alarm"]:
                self._stop_arming_sequence()

    def _start_arming_sequence(self):
        """Start the arming sequence for this area."""
        self._arming_start_time = datetime.now()
        self._arming_progress = 0
        self._arming_time_remaining = self._exit_delay_seconds
        
        _LOGGER.info("Starting area %d arming sequence", self._area_number)
        
        # Start progress tracking
        self._arming_cancel_listener = async_track_time_interval(
            self.hass,
            self._update_arming_progress,
            timedelta(seconds=1)
        )
        
    def _stop_arming_sequence(self):
        """Stop the arming sequence for this area."""
        if self._arming_cancel_listener:
            self._arming_cancel_listener()
            self._arming_cancel_listener = None
            
        self._arming_progress = 0
        self._arming_time_remaining = 0
        self._arming_start_time = None

    @callback
    def _update_arming_progress(self, now):
        """Update arming progress for this area."""
        if not self._arming_start_time:
            return
            
        elapsed = (now - self._arming_start_time).total_seconds()
        self._arming_time_remaining = max(0, self._exit_delay_seconds - elapsed)
        self._arming_progress = min(100, (elapsed / self._exit_delay_seconds) * 100)
        
        self.async_write_ha_state()
        
        if self._arming_time_remaining <= 0:
            self._stop_arming_sequence()

    def _get_area_armed_key(self) -> str:
        """Get the data key for this area's armed status."""
        # Convert area number to letter (1=a, 2=b, etc.)
        area_letter = chr(64 + self._area_number).lower()
        return f"area_{area_letter}_armed"

    def _get_area_zones(self) -> list:
        """Get zones assigned to this area."""
        if not self.coordinator.data:
            return []
        
        zones_in_areas = self.coordinator.data.get("zones_in_areas", {})
        area_zones = zones_in_areas.get(self._area_number, [])
        
        # Handle both set and list formats
        if isinstance(area_zones, set):
            return list(area_zones)
        elif isinstance(area_zones, list):
            return area_zones
        else:
            return []

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes for this area with arming effects."""
        attributes = {
            "area_number": self._area_number,
            "panel_type": self._panel_config["name"],
            "entity_type": "area_specific",
            
            # Arming effects attributes
            "arming_state": self._arming_state,
            "arming_progress": self._arming_progress,
            "arming_time_remaining": self._arming_time_remaining,
            "exit_delay_seconds": self._exit_delay_seconds,
        }
        
        # Add arming status details
        if self._arming_state == "arming":
            attributes.update({
                "arming_started_at": self._arming_start_time.isoformat() if self._arming_start_time else None,
                "arming_progress_text": f"{self._arming_progress:.1f}% ({self._arming_time_remaining:.0f}s remaining)",
                "arming_status": f"Area {self._area_number} exit delay in progress",
            })
        elif self._arming_state == "armed":
            attributes.update({
                "arming_status": f"Area {self._area_number} armed",
                "arming_progress_text": "Complete",
            })
        elif self._arming_state == "alarm":
            attributes.update({
                "arming_status": f"AREA {self._area_number} ALARM",
                "arming_progress_text": "Alarm active",
            })
        else:
            attributes.update({
                "arming_status": f"Area {self._area_number} disarmed",
                "arming_progress_text": "Ready",
            })
        
        if self.coordinator.data:
            data = self.coordinator.data
            
            # Area-specific information
            area_zones = self._get_area_zones()
            area_armed_key = self._get_area_armed_key()
            
            attributes.update({
                "area_zones": area_zones,
                "total_zones_in_area": len(area_zones),
                "area_armed_status": data.get(area_armed_key, False),
                "area_armed_key": area_armed_key,
            })
            
            # Zone states for this area only
            if area_zones:
                zones_data = data.get("zones", {})
                zone_alarms = data.get("zone_alarms", {})
                zone_troubles = data.get("zone_troubles", {})
                zone_bypassed = data.get("zone_bypassed", {})
                
                area_open_zones = [z for z in area_zones if zones_data.get(z, False)]
                area_alarm_zones = [z for z in area_zones if zone_alarms.get(z, False)]
                area_trouble_zones = [z for z in area_zones if zone_troubles.get(z, False)]
                area_bypassed_zones = [z for z in area_zones if zone_bypassed.get(z, False)]
                
                attributes.update({
                    "open_zones_in_area": area_open_zones,
                    "alarm_zones_in_area": area_alarm_zones,
                    "trouble_zones_in_area": area_trouble_zones,
                    "bypassed_zones_in_area": area_bypassed_zones,
                    "area_ready_to_arm": len(area_open_zones) == 0,
                })
                
                # Area status summary with arming consideration
                area_issues = []
                if area_alarm_zones:
                    area_issues.append(f"{len(area_alarm_zones)} zones in alarm")
                if area_trouble_zones:
                    area_issues.append(f"{len(area_trouble_zones)} zones in trouble")
                if area_open_zones and self._arming_state != "arming":
                    area_issues.append(f"{len(area_open_zones)} zones open")
                if area_bypassed_zones:
                    area_issues.append(f"{len(area_bypassed_zones)} zones bypassed")
                
                if self._arming_state == "arming":
                    attributes["area_status_summary"] = f"Arming in progress ({self._arming_time_remaining:.0f}s)"
                else:
                    attributes["area_status_summary"] = "; ".join(area_issues) if area_issues else "All zones normal"
            
            # Connection and system info
            attributes.update({
                "connection_state": data.get("connection_state", "unknown"),
                "last_update": data.get("last_update"),
                "status_message": data.get("status_message", "Unknown"),
            })
        
        return attributes

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success and
            self.coordinator.data is not None and
            self.coordinator.data.get("connection_state") == "connected"
        )

    @property
    def icon(self) -> str:
        """Return icon based on area arming state."""
        if self._arming_state == "arming":
            # Animated icon during arming based on progress
            if self._arming_progress < 25:
                return "mdi:shield-sync"
            elif self._arming_progress < 50:
                return "mdi:shield-half-full" 
            elif self._arming_progress < 75:
                return "mdi:shield-sync"
            else:
                return "mdi:shield-outline"
        elif self._arming_state == "armed":
            return "mdi:shield-check"
        elif self._arming_state == "alarm":
            return "mdi:shield-alert"
        else:
            return f"mdi:shield-home-outline"

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command for this area."""
        _LOGGER.info("Disarming area %d on %s", self._area_number, self._attr_name)
        
        # Cancel any active arming sequence
        if self._arming_state == "arming":
            self._stop_arming_sequence()
            _LOGGER.info("Area %d arming sequence cancelled by disarm command", self._area_number)
        
        # Check if coordinator has area-specific disarm method
        if hasattr(self.coordinator, 'async_disarm_area'):
            success = await self.coordinator.async_disarm_area(self._area_number)
        else:
            # Fallback to general disarm
            _LOGGER.warning("Area-specific disarm not available, using general disarm")
            success = await self.coordinator.async_disarm()
        
        if not success:
            _LOGGER.error("Failed to disarm area %d", self._area_number)

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command for this area."""
        _LOGGER.info("Arming area %d (away mode) on %s", self._area_number, self._attr_name)
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        # Check if coordinator has area-specific arm method
        if hasattr(self.coordinator, 'async_arm_away_area'):
            success = await self.coordinator.async_arm_away_area(self._area_number)
        else:
            # Fallback to general arm away
            _LOGGER.warning("Area-specific arm away not available, using general arm away")
            success = await self.coordinator.async_arm_away()
        
        if not success:
            _LOGGER.error("Failed to arm area %d (away mode)", self._area_number)
            # Cancel arming sequence on failure
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command for this area."""
        _LOGGER.info("Arming area %d (stay mode) on %s", self._area_number, self._attr_name)
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        # Check if coordinator has area-specific arm method
        if hasattr(self.coordinator, 'async_arm_stay_area'):
            success = await self.coordinator.async_arm_stay_area(self._area_number)
        else:
            # Fallback to general arm stay
            _LOGGER.warning("Area-specific arm stay not available, using general arm stay")
            success = await self.coordinator.async_arm_stay()
        
        if not success:
            _LOGGER.error("Failed to arm area %d (stay mode)", self._area_number)
            # Cancel arming sequence on failure
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Check if actual panel state changed for this area
        if self.coordinator.data:
            area_armed_key = self._get_area_armed_key()
            area_armed = self.coordinator.data.get(area_armed_key, False)
            
            # If area reports armed and we were arming, complete the sequence
            if area_armed and self._arming_state == "arming":
                self._stop_arming_sequence()
                self._update_arming_state("armed")
            # If area reports not armed and we think we are arming, stop the sequence
            elif not area_armed and self._arming_state == "arming":
                # Don't stop immediately, let the timer complete naturally
                # This handles cases where the panel hasn't updated yet
                pass
        
        self.async_write_ha_state()