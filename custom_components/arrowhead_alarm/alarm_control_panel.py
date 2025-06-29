"""Arrowhead ECi alarm control panel with MODE 4 commands and PIN prompts."""
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
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ServiceValidationError

from .const import (
    DOMAIN,
    PANEL_CONFIG,
    ATTR_READY_TO_ARM,
    ATTR_MAINS_POWER,
    ATTR_BATTERY_STATUS,
    ATTR_TOTAL_ZONES,
    ATTR_MAX_ZONES,
    ATTR_ACTIVE_AREAS,
    ATTR_PROTOCOL_MODE,
    ATTR_FIRMWARE_VERSION,
)
from .coordinator import ArrowheadECiDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Arrowhead ECi alarm control panel with MODE 4 area support."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    firmware_info = hass.data[DOMAIN][config_entry.entry_id]["firmware_info"]
    
    entities = []
    
    # Always create the main panel (all areas combined)
    entities.append(
        ArrowheadECiAlarmControlPanel(coordinator, config_entry, panel_config, firmware_info)
    )
    
    # Wait for initial data to detect areas
    if not coordinator.data:
        await coordinator.async_request_refresh()
    
    # Create individual area panels for MODE 4 multi-area support
    if coordinator.data and firmware_info.get("mode_4_active", False):
        _LOGGER.info("MODE 4 active - checking for multi-area configuration...")
        
        # Detect active areas for MODE 4
        active_areas = set()
        
        # Check detected areas from zone detection
        detected_areas = coordinator.data.get("active_areas_detected", set())
        if isinstance(detected_areas, (list, tuple)):
            active_areas.update(detected_areas)
        elif isinstance(detected_areas, set):
            active_areas.update(detected_areas)
        
        # Check config entry for configured areas
        config_areas = config_entry.data.get("areas", [])
        if isinstance(config_areas, (list, tuple)):
            active_areas.update(config_areas)
        
        # Check for area status keys in data
        for key in coordinator.data.keys():
            if key.startswith("area_") and key.endswith("_armed"):
                area_letter = key.split("_")[1]
                if len(area_letter) == 1 and area_letter.isalpha():
                    area_number = ord(area_letter) - ord('a') + 1
                    if area_number <= 32:
                        active_areas.add(area_number)
        
        # Ensure we have at least area 1
        if not active_areas:
            active_areas = {1}
        
        _LOGGER.info("MODE 4 - Detected active ECi areas: %s", sorted(active_areas))
        
        # Create area-specific panels for MODE 4
        for area in sorted(active_areas):
            if 1 <= area <= 32:
                _LOGGER.info("Creating MODE 4 area-specific panel for area %d", area)
                entities.append(
                    ArrowheadECiAreaAlarmControlPanel(coordinator, config_entry, panel_config, firmware_info, area)
                )
    
    _LOGGER.info("Created %d ECi alarm control panel entities", len(entities))
    async_add_entities(entities)

class ArrowheadECiAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """ECi Panel with MODE 4 ARMAREA/STAYAREA commands and PIN prompts."""

    def __init__(
        self,
        coordinator: ArrowheadECiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        firmware_info: Dict[str, Any],
    ) -> None:
        """Initialize the ECi alarm control panel."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._firmware_info = firmware_info
        self._attr_name = f"Arrowhead {panel_config['name']}"
        self._attr_unique_id = f"{config_entry.entry_id}_alarm_panel"
        
        # Set supported features
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY |
            AlarmControlPanelEntityFeature.ARM_HOME
        )
        
        # IMPORTANT: Always require code for disarm
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_code_arm_required = False  # No code for arm (uses ARMAREA/STAYAREA)
        self._attr_code_disarm_required = True  # Always require code for disarm
        
        # MODE 4 specific attributes
        self._mode_4_active = firmware_info.get("mode_4_active", False)
        self._protocol_mode = firmware_info.get("protocol_mode", 4)
        self._firmware_version = firmware_info.get("version", "Unknown")
        
        # Arming effects state
        self._arming_state = "idle"
        self._arming_start_time = None
        self._exit_delay_seconds = 30
        self._arming_progress = 0
        self._arming_time_remaining = 0
        self._arming_cancel_listener = None
        
        # Set device info
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Arrowhead {panel_config['name']}",
            "manufacturer": "Arrowhead Alarm Products",
            "model": f"{panel_config['name']} (MODE 4)",
            "sw_version": self._firmware_version,
            "configuration_url": f"http://{config_entry.data.get('host', 'unknown')}",
        }

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of the alarm control panel."""
        if not self.coordinator.data:
            return AlarmControlPanelState.DISARMED
            
        data = self.coordinator.data
        
        # Check for alarm condition first
        if data.get("alarm", False):
            self._update_arming_state("alarm")
            return AlarmControlPanelState.TRIGGERED
            
        # MODE 4: Check for enhanced entry delay states
        if self._mode_4_active:
            zone_entry_delays = data.get("zone_entry_delays", {})
            if zone_entry_delays:
                self._update_arming_state("entry_delay")
                return AlarmControlPanelState.PENDING
                
        # Check for arming/pending state
        if data.get("arming", False) or self._arming_state == "arming":
            self._update_arming_state("arming")
            return AlarmControlPanelState.PENDING
            
        # Check armed states - check if ANY area is armed
        area_armed = False
        stay_mode = False
        
        # Check up to 32 areas for ECi
        for i in range(1, 33):
            area_key = f"area_{chr(96 + i)}_armed"
            if data.get(area_key, False):
                area_armed = True
                break
        
        # Also check general armed state for compatibility
        if not area_armed:
            area_armed = data.get("armed", False)
            
        stay_mode = data.get("stay_mode", False)
        
        if area_armed:
            self._update_arming_state("armed")
            if stay_mode:
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
            
            _LOGGER.debug("ECi MODE 4 arming state changed: %s -> %s", old_state, new_state)
            
            if new_state == "arming":
                self._start_arming_sequence()
            elif new_state in ["armed", "idle", "alarm", "entry_delay"]:
                self._stop_arming_sequence()
                
    def _start_arming_sequence(self):
        """Start the arming sequence with MODE 4 timing."""
        if self._mode_4_active and self.coordinator.data:
            area_exit_delays = self.coordinator.data.get("area_exit_delays", {})
            if area_exit_delays:
                self._exit_delay_seconds = max(area_exit_delays.values())
            
        self._arming_start_time = datetime.now()
        self._arming_progress = 0
        self._arming_time_remaining = self._exit_delay_seconds
        
        _LOGGER.info("Starting ECi MODE 4 arming sequence with %d second delay", self._exit_delay_seconds)
        
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

    @callback
    def _update_arming_progress(self, now):
        """Update arming progress during exit delay."""
        if not self._arming_start_time:
            return
            
        elapsed = (now - self._arming_start_time).total_seconds()
        self._arming_time_remaining = max(0, self._exit_delay_seconds - elapsed)
        self._arming_progress = min(100, (elapsed / self._exit_delay_seconds) * 100)
        
        self.async_write_ha_state()
        
        if self._arming_time_remaining <= 0:
            self._stop_arming_sequence()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes with MODE 4 information."""
        if not self.coordinator.data:
            return {}
            
        data = self.coordinator.data
        zones = data.get("zones", {})
        zone_alarms = data.get("zone_alarms", {})
        outputs = data.get("outputs", {})
        
        active_zones = [zone_id for zone_id, state in zones.items() if state]
        alarm_zones = [zone_id for zone_id, state in zone_alarms.items() if state]
        active_outputs = [output_id for output_id, state in outputs.items() if state]
        
        attributes = {
            ATTR_READY_TO_ARM: data.get("ready_to_arm", False),
            ATTR_MAINS_POWER: data.get("mains_ok", True),
            ATTR_BATTERY_STATUS: data.get("battery_ok", True),
            ATTR_PROTOCOL_MODE: self._protocol_mode,
            ATTR_FIRMWARE_VERSION: self._firmware_version,
            "mode_4_only": True,
            "status_message": data.get("status_message", "Unknown"),
            "connection_state": data.get("connection_state", "unknown"),
            "active_zones": active_zones,
            "alarm_zones": alarm_zones,
            "active_outputs": active_outputs,
            "total_zones_configured": len(zones),
            "total_outputs_configured": len(outputs),
            
            # Arming effects
            "arming_state": self._arming_state,
            "arming_progress": self._arming_progress,
            "arming_time_remaining": self._arming_time_remaining,
            "exit_delay_seconds": self._exit_delay_seconds,
        }
        
        # MODE 4 specific attributes
        if self._mode_4_active:
            attributes.update({
                "mode_4_features_active": True,
                "uses_armarea_commands": True,
                "uses_stayarea_commands": True,
                "requires_pin_for_disarm": True,
                "p74e_configured": data.get("areas_configured_p74e", False),
                "p76e_configured": data.get("areas_configured_p76e", False),
            })
            
            # Keypad alarm status
            keypad_alarms = {
                "panic": data.get("keypad_panic_alarm", False),
                "fire": data.get("keypad_fire_alarm", False),
                "medical": data.get("keypad_medical_alarm", False),
            }
            attributes["keypad_alarms"] = keypad_alarms
            
            # Enhanced timing information
            zone_entry_delays = data.get("zone_entry_delays", {})
            area_exit_delays = data.get("area_exit_delays", {})
            
            if zone_entry_delays:
                attributes["zones_in_entry_delay"] = list(zone_entry_delays.keys())
                attributes["entry_delay_remaining"] = max(zone_entry_delays.values())
                
            if area_exit_delays:
                attributes["areas_in_exit_delay"] = list(area_exit_delays.keys())
                attributes["max_exit_delay_remaining"] = max(area_exit_delays.values())
                
        # Add area status for all 32 possible areas
        area_status = {}
        for i in range(1, 33):
            area_key = f"area_{chr(96 + i)}_armed"
            if area_key in data:
                area_status[f"area_{i}"] = data[area_key]
        
        if area_status:
            attributes["area_armed_status"] = area_status
            
        # Add zone-area mapping
        zones_in_areas = data.get("zones_in_areas", {})
        if zones_in_areas:
            serializable_zones = {}
            for area, zone_set in zones_in_areas.items():
                if isinstance(zone_set, set):
                    serializable_zones[str(area)] = sorted(list(zone_set))
                else:
                    serializable_zones[str(area)] = zone_set
            attributes["zones_in_areas"] = serializable_zones
        
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
        """Return icon based on MODE 4 state."""
        if self._arming_state == "arming":
            return "mdi:shield-sync"
        elif self._arming_state == "armed":
            return "mdi:shield-star"  # Special icon for MODE 4
        elif self._arming_state == "alarm":
            return "mdi:shield-alert"
        elif self._arming_state == "entry_delay":
            return "mdi:shield-sync-outline"
        else:
            return "mdi:shield-star-outline"  # MODE 4 disarmed icon

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command - ALWAYS requires PIN."""
        _LOGGER.info("Disarming ECi with MODE 4 commands (PIN required)")
        
        # Validate PIN is provided
        if not code:
            raise ServiceValidationError("PIN code is required for disarm operation")
        
        # Cancel any active arming sequence
        if self._arming_state == "arming":
            self._stop_arming_sequence()
            _LOGGER.info("ECi arming sequence cancelled by disarm command")
        
        # Use disarm_with_pin method that requires user PIN format
        try:
            # The code should be in format "user pin" (e.g., "1 123")
            # If user provides just a PIN, prepend with default user number
            if ' ' not in code:
                # Assume user 1 if no user number provided
                formatted_pin = f"1 {code}"
                _LOGGER.info("PIN provided without user number, using user 1")
            else:
                formatted_pin = code
            
            success = await self.coordinator.client.disarm_with_pin(formatted_pin)
            
            if not success:
                _LOGGER.error("Failed to disarm ECi panel")
                raise ServiceValidationError("Disarm command failed - check PIN and user number")
                
        except Exception as err:
            _LOGGER.error("Error during disarm: %s", err)
            raise ServiceValidationError(f"Disarm failed: {str(err)}")

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command using ARMAREA (MODE 4)."""
        _LOGGER.info("Arming ECi (away mode) using MODE 4 ARMAREA commands")
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            # Get active areas and arm them all using ARMAREA
            success = await self._arm_all_areas_away()
            
            if not success:
                _LOGGER.error("Failed to arm ECi (away mode)")
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error during arm away: %s", err)
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command using STAYAREA (MODE 4)."""
        _LOGGER.info("Arming ECi (stay mode) using MODE 4 STAYAREA commands")
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            # Get active areas and arm them all using STAYAREA
            success = await self._arm_all_areas_stay()
            
            if not success:
                _LOGGER.error("Failed to arm ECi (stay mode)")
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error during arm stay: %s", err)
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    async def _arm_all_areas_away(self) -> bool:
        """Arm all active areas using ARMAREA commands."""
        try:
            # Get active areas from coordinator data or config
            active_areas = self._get_active_areas()
            
            _LOGGER.info("Arming areas %s using ARMAREA commands", active_areas)
            
            success_count = 0
            for area in active_areas:
                try:
                    success = await self.coordinator.client.arm_away_area(area)
                    if success:
                        success_count += 1
                    await asyncio.sleep(0.5)  # Small delay between commands
                except Exception as err:
                    _LOGGER.error("Error arming area %d: %s", area, err)
            
            overall_success = success_count == len(active_areas)
            _LOGGER.info("ARMAREA results: %d/%d areas armed successfully", success_count, len(active_areas))
            
            return overall_success
            
        except Exception as err:
            _LOGGER.error("Error in _arm_all_areas_away: %s", err)
            return False

    async def _arm_all_areas_stay(self) -> bool:
        """Arm all active areas using STAYAREA commands."""
        try:
            # Get active areas from coordinator data or config
            active_areas = self._get_active_areas()
            
            _LOGGER.info("Arming areas %s using STAYAREA commands", active_areas)
            
            success_count = 0
            for area in active_areas:
                try:
                    success = await self.coordinator.client.arm_stay_area(area)
                    if success:
                        success_count += 1
                    await asyncio.sleep(0.5)  # Small delay between commands
                except Exception as err:
                    _LOGGER.error("Error stay arming area %d: %s", area, err)
            
            overall_success = success_count == len(active_areas)
            _LOGGER.info("STAYAREA results: %d/%d areas armed successfully", success_count, len(active_areas))
            
            return overall_success
            
        except Exception as err:
            _LOGGER.error("Error in _arm_all_areas_stay: %s", err)
            return False

    def _get_active_areas(self) -> list:
        """Get list of active areas from coordinator data or configuration."""
        active_areas = []
        
        # Method 1: From coordinator data (zones_in_areas)
        if self.coordinator.data:
            zones_in_areas = self.coordinator.data.get("zones_in_areas", {})
            active_areas.extend(zones_in_areas.keys())
        
        # Method 2: From config entry
        config_areas = self._config_entry.data.get("areas", [])
        if isinstance(config_areas, (list, tuple)):
            active_areas.extend(config_areas)
        
        # Method 3: From status keys in coordinator data
        if self.coordinator.data:
            for key in self.coordinator.data.keys():
                if key.startswith("area_") and key.endswith("_armed"):
                    area_letter = key.split("_")[1]
                    if len(area_letter) == 1 and area_letter.isalpha():
                        area_number = ord(area_letter) - ord('a') + 1
                        if 1 <= area_number <= 32:
                            active_areas.append(area_number)
        
        # Remove duplicates and sort
        active_areas = sorted(set(active_areas))
        
        # Default to area 1 if nothing found
        if not active_areas:
            active_areas = [1]
        
        return active_areas

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            # Check for any area armed state
            any_area_armed = False
            for i in range(1, 33):
                area_key = f"area_{chr(96 + i)}_armed"
                if self.coordinator.data.get(area_key, False):
                    any_area_armed = True
                    break
            
            panel_armed = self.coordinator.data.get("armed", False)
            panel_arming = self.coordinator.data.get("arming", False)
            
            # If panel reports armed and we were arming, complete the sequence
            if (panel_armed or any_area_armed) and self._arming_state == "arming":
                self._stop_arming_sequence()
                self._update_arming_state("armed")
            # If panel reports not arming and not armed, stop the sequence
            elif not panel_arming and not panel_armed and not any_area_armed and self._arming_state == "arming":
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                
            # MODE 4: Check for entry delay states
            if self._mode_4_active:
                zone_entry_delays = self.coordinator.data.get("zone_entry_delays", {})
                if zone_entry_delays and self._arming_state != "entry_delay":
                    self._update_arming_state("entry_delay")
                elif not zone_entry_delays and self._arming_state == "entry_delay":
                    if panel_armed or any_area_armed:
                        self._update_arming_state("armed")
                    else:
                        self._update_arming_state("idle")
        
        self.async_write_ha_state()


class ArrowheadECiAreaAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """Individual area control panel using MODE 4 ARMAREA/STAYAREA commands."""

    def __init__(
        self,
        coordinator: ArrowheadECiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        firmware_info: Dict[str, Any],
        area_number: int,
    ) -> None:
        """Initialize the ECi area alarm control panel."""
        super().__init__(coordinator)
        self._config_entry = config_entry
        self._panel_config = panel_config
        self._firmware_info = firmware_info
        self._area_number = area_number
        self._attr_name = f"Arrowhead {panel_config['name']} Area {area_number}"
        self._attr_unique_id = f"{config_entry.entry_id}_alarm_panel_area_{area_number}"
        
        # Set supported features
        self._attr_supported_features = (
            AlarmControlPanelEntityFeature.ARM_AWAY |
            AlarmControlPanelEntityFeature.ARM_HOME
        )
        
        # IMPORTANT: Always require code for disarm
        self._attr_code_format = CodeFormat.NUMBER
        self._attr_code_arm_required = False  # No code for arm (uses ARMAREA/STAYAREA)
        self._attr_code_disarm_required = True  # Always require code for disarm
        
        # MODE 4 specific attributes for area
        self._mode_4_active = firmware_info.get("mode_4_active", False)
        self._protocol_mode = firmware_info.get("protocol_mode", 4)
        self._firmware_version = firmware_info.get("version", "Unknown")
        
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
            "model": f"{panel_config['name']} (MODE 4)",
            "sw_version": self._firmware_version,
        }

    @property
    def alarm_state(self) -> AlarmControlPanelState:
        """Return the state of this specific area."""
        if not self.coordinator.data:
            return AlarmControlPanelState.DISARMED
            
        data = self.coordinator.data
        
        # Check for alarm condition in this area
        if data.get("alarm", False):
            area_zones = self._get_area_zones()
            alarm_zones = [zone_id for zone_id, state in data.get("zone_alarms", {}).items() if state]
            if any(zone in area_zones for zone in alarm_zones):
                self._update_arming_state("alarm")
                return AlarmControlPanelState.TRIGGERED
        
        # MODE 4: Check for area-specific alarm state
        if self._mode_4_active:
            area_alarm_key = f"area_{chr(96 + self._area_number)}_alarm"
            if data.get(area_alarm_key, False):
                self._update_arming_state("alarm")
                return AlarmControlPanelState.TRIGGERED
                
            # Check for entry delay in this area's zones
            zone_entry_delays = data.get("zone_entry_delays", {})
            area_zones = self._get_area_zones()
            area_entry_delays = {z: zone_entry_delays.get(z, 0) for z in area_zones if z in zone_entry_delays}
            if area_entry_delays:
                self._update_arming_state("entry_delay")
                return AlarmControlPanelState.PENDING
        
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

    def _get_area_armed_key(self) -> str:
        """Get the data key for this area's armed status."""
        area_letter = chr(96 + self._area_number)  # a, b, c, etc.
        return f"area_{area_letter}_armed"

    def _get_area_zones(self) -> list:
        """Get zones assigned to this area."""
        if not self.coordinator.data:
            return []
        
        zones_in_areas = self.coordinator.data.get("zones_in_areas", {})
        area_zones = zones_in_areas.get(self._area_number, [])
        
        if isinstance(area_zones, set):
            return list(area_zones)
        elif isinstance(area_zones, list):
            return area_zones
        else:
            return []

    def _update_arming_state(self, new_state: str):
        """Update arming state for this area."""
        if self._arming_state != new_state:
            self._arming_state = new_state
            
            if new_state == "arming":
                self._start_arming_sequence()
            elif new_state in ["armed", "idle", "alarm", "entry_delay"]:
                self._stop_arming_sequence()

    def _start_arming_sequence(self):
        """Start the arming sequence for this area."""
        if self._mode_4_active and self.coordinator.data:
            area_exit_delays = self.coordinator.data.get("area_exit_delays", {})
            area_delay = area_exit_delays.get(self._area_number)
            if area_delay:
                self._exit_delay_seconds = area_delay
        
        self._arming_start_time = datetime.now()
        self._arming_progress = 0
        self._arming_time_remaining = self._exit_delay_seconds
        
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

    @property
    def icon(self) -> str:
        """Return icon for this area."""
        if self._arming_state == "arming":
            return "mdi:shield-sync"
        elif self._arming_state == "armed":
            return "mdi:shield-star"
        elif self._arming_state == "alarm":
            return "mdi:shield-alert"
        elif self._arming_state == "entry_delay":
            return "mdi:shield-sync-outline"
        else:
            return f"mdi:shield-star-outline"

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command for this area - ALWAYS requires PIN."""
        _LOGGER.info("Disarming ECi area %d with MODE 4 commands (PIN required)", self._area_number)
        
        # Validate PIN is provided
        if not code:
            raise ServiceValidationError("PIN code is required for disarm operation")
        
        # Cancel any active arming sequence
        if self._arming_state == "arming":
            self._stop_arming_sequence()
        
        try:
            # Format PIN properly
            if ' ' not in code:
                formatted_pin = f"1 {code}"
            else:
                formatted_pin = code
            
            success = await self.coordinator.client.disarm_with_pin(formatted_pin)
            
            if not success:
                raise ServiceValidationError("Disarm command failed - check PIN and user number")
                
        except Exception as err:
            raise ServiceValidationError(f"Disarm failed: {str(err)}")

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command for this area using ARMAREA."""
        _LOGGER.info("Arming ECi area %d (away mode) using ARMAREA command", self._area_number)
        
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            success = await self.coordinator.client.arm_away_area(self._area_number)
            
            if not success:
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error arming area %d away: %s", self._area_number, err)
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command for this area using STAYAREA."""
        _LOGGER.info("Arming ECi area %d (stay mode) using STAYAREA command", self._area_number)
        
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            success = await self.coordinator.client.arm_stay_area(self._area_number)
            
            if not success:
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error arming area %d stay: %s", self._area_number, err)
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            area_armed_key = self._get_area_armed_key()
            area_armed = self.coordinator.data.get(area_armed_key, False)
            
            if area_armed and self._arming_state == "arming":
                self._stop_arming_sequence()
                self._update_arming_state("armed")
            elif not area_armed and self._arming_state == "arming":
                pass  # Let timer complete naturally
                
            # MODE 4: Check for area-specific entry delay states
            if self._mode_4_active:
                zone_entry_delays = self.coordinator.data.get("zone_entry_delays", {})
                area_zones = self._get_area_zones()
                area_entry_delays = {z: zone_entry_delays.get(z, 0) for z in area_zones if z in zone_entry_delays}
                
                if area_entry_delays and self._arming_state != "entry_delay":
                    self._update_arming_state("entry_delay")
                elif not area_entry_delays and self._arming_state == "entry_delay":
                    if area_armed:
                        self._update_arming_state("armed")
                    else:
                        self._update_arming_state("idle")
        
        self.async_write_ha_state()