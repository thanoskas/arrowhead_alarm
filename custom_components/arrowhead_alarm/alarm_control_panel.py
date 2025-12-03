"""Arrowhead ECi alarm control panel - MAIN PANEL + INDIVIDUAL AREA PANELS - FIXED VERSION."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

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
from homeassistant.util import dt as dt_util

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
    """Set up Arrowhead ECi alarm control panels - MAIN PANEL + AUTO-DETECTED AREA PANELS."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    panel_config = hass.data[DOMAIN][config_entry.entry_id]["panel_config"]
    firmware_info = hass.data[DOMAIN][config_entry.entry_id]["firmware_info"]
    
    entities = []
    
    # Wait for initial data and ensure zones are properly initialized
    if not coordinator.data:
        await coordinator.async_request_refresh()
    
    # FIXED: Initialize zones from configuration including sealed zones
    await _ensure_zones_initialized_fixed(coordinator, config_entry)
    
    # Get areas - try auto-detection first, then fall back to manual
    areas_to_create = await _get_areas_for_panels(coordinator, config_entry)
    _LOGGER.info("Areas for panel creation: %s", areas_to_create)
    
    # Create MAIN panel (handles all areas)
    _LOGGER.info("Creating main ECi alarm control panel for all areas")
    entities.append(
        ArrowheadECiAlarmControlPanel(coordinator, config_entry, panel_config, firmware_info)
    )
    
    # Create INDIVIDUAL AREA panels for each detected/configured area
    _LOGGER.info("Creating individual area panels for areas: %s", areas_to_create)
    for area_number in areas_to_create:
        _LOGGER.info("Creating individual panel for area %d", area_number)
        entities.append(
            ArrowheadECiAreaAlarmControlPanel(
                coordinator, config_entry, panel_config, firmware_info, area_number
            )
        )
    
    total_panels = len(entities)
    _LOGGER.info("Created %d ECi alarm control panel entities: 1 main + %d area panels", 
                total_panels, total_panels - 1)
    async_add_entities(entities)


async def _get_areas_for_panels(coordinator, config_entry: ConfigEntry) -> List[int]:
    """Get areas for panel creation - auto-detect first, then manual fallback."""
    try:
        # First, try to get auto-detected areas from zone detection
        if coordinator.data and "configured_areas_detected" in coordinator.data:
            auto_detected_areas = coordinator.data.get("configured_areas_detected", [])
            if auto_detected_areas:
                _LOGGER.info("Using auto-detected areas from P4076E1: %s", auto_detected_areas)
                return sorted(auto_detected_areas)
        
        # Check if we have areas from the zone detection process
        detected_zones_data = config_entry.data.get("detected_zones_data")
        if detected_zones_data and "configured_areas" in detected_zones_data:
            auto_detected_areas = detected_zones_data["configured_areas"]
            if auto_detected_areas:
                _LOGGER.info("Using auto-detected areas from zone detection: %s", auto_detected_areas)
                return sorted(auto_detected_areas)
        
        # Fallback to manual areas from config
        manual_areas = _get_manual_areas_from_config(config_entry)
        _LOGGER.info("Using manual areas from config (fallback): %s", manual_areas)
        return manual_areas
        
    except Exception as err:
        _LOGGER.error("Error determining areas for panels: %s", err)
        # Final fallback
        return [1]


async def _ensure_zones_initialized_fixed(coordinator, config_entry: ConfigEntry) -> None:
    """FIXED: Ensure all configured zones are initialized including sealed zones."""
    try:
        # Get zone configuration
        auto_detect_zones = config_entry.data.get("auto_detect_zones", True)
        max_zones = config_entry.data.get("max_zones", 16)
        detected_zones = config_entry.data.get("detected_zones", [])
        sealed_zones = config_entry.data.get("sealed_zones", [])  # FIXED: Get sealed zones
        
        _LOGGER.info("FIXED zone initialization: auto_detect=%s, max_zones=%d, detected=%s, sealed=%s", 
                    auto_detect_zones, max_zones, detected_zones, sealed_zones)
        
        # Determine which zones to initialize
        if auto_detect_zones and detected_zones:
            # Use detected zones
            zones_to_init = set(detected_zones)
            _LOGGER.info("Using detected zones: %s", sorted(zones_to_init))
        else:
            # Use manual zone range
            zones_to_init = set(range(1, max_zones + 1))
            _LOGGER.info("Using manual zone range 1-%d: %s", max_zones, sorted(zones_to_init))
        
        # Initialize zones in coordinator data if not present
        if coordinator.data is None:
            coordinator.data = {}
        
        # FIXED: Ensure all zone dictionaries exist with all configured zones
        zone_keys = ["zones", "zone_alarms", "zone_troubles", "zone_bypassed", "zone_sealed"]  # Added zone_sealed
        
        for zone_key in zone_keys:
            if zone_key not in coordinator.data:
                coordinator.data[zone_key] = {}
            
            # Add missing zones with appropriate default state
            for zone_id in zones_to_init:
                if zone_id not in coordinator.data[zone_key]:
                    # FIXED: Set proper default for sealed zones
                    if zone_key == "zone_sealed":
                        default_value = zone_id in sealed_zones
                    else:
                        default_value = False
                    
                    coordinator.data[zone_key][zone_id] = default_value
                    _LOGGER.debug("Initialized %s[%d] = %s", zone_key, zone_id, default_value)
        
        # FIXED: Log sealed zone initialization
        if sealed_zones:
            _LOGGER.info("Initialized %d sealed zones: %s", len(sealed_zones), sorted(sealed_zones))
        
        _LOGGER.info("Zone initialization complete: %d zones initialized", len(zones_to_init))
        _LOGGER.info("Zones: %s", sorted(coordinator.data.get("zones", {}).keys()))
        _LOGGER.info("Sealed zones: %s", sorted([z for z, sealed in coordinator.data.get("zone_sealed", {}).items() if sealed]))
        
        # Initialize areas - try auto-detected first, then manual
        areas_for_init = await _get_areas_for_panels(coordinator, config_entry)
        active_areas_detected = set(areas_for_init)
        coordinator.data["active_areas_detected"] = active_areas_detected
        coordinator.data["configured_areas_detected"] = areas_for_init
        
        # Initialize area status
        for area in areas_for_init:
            area_letter = chr(96 + area)  # a, b, c, etc.
            area_keys = [
                f"area_{area_letter}_armed",
                f"area_{area_letter}_armed_by_user", 
                f"area_{area_letter}_alarm"
            ]
            for area_key in area_keys:
                if area_key not in coordinator.data:
                    coordinator.data[area_key] = False if not area_key.endswith("_by_user") else None
                    
        _LOGGER.info("Area initialization complete: areas %s", areas_for_init)
        
    except Exception as err:
        _LOGGER.error("Error ensuring zones initialized: %s", err)
        # Fallback initialization
        if coordinator.data is None:
            coordinator.data = {}
        
        # Minimum fallback - zones 1-16
        fallback_zones = set(range(1, 17))
        for zone_key in ["zones", "zone_alarms", "zone_troubles", "zone_bypassed", "zone_sealed"]:
            if zone_key not in coordinator.data:
                coordinator.data[zone_key] = {}
            for zone_id in fallback_zones:
                if zone_id not in coordinator.data[zone_key]:
                    coordinator.data[zone_key][zone_id] = False
        
        _LOGGER.info("Fallback zone initialization: zones 1-16")


def _get_manual_areas_from_config(config_entry: ConfigEntry) -> list:
    """Get manually configured areas from config entry."""
    areas = config_entry.data.get("areas", [1])
    
    if isinstance(areas, str):
        # Parse string format "1,2,3"
        try:
            areas = [int(x.strip()) for x in areas.split(",") if x.strip().isdigit()]
        except (ValueError, AttributeError):
            areas = [1]
    elif not isinstance(areas, list):
        areas = [1]
    
    # Ensure valid areas
    valid_areas = [area for area in areas if isinstance(area, int) and 1 <= area <= 32]
    if not valid_areas:
        valid_areas = [1]
        
    _LOGGER.debug("Manual areas parsed: %s", valid_areas)
    return valid_areas


class ArrowheadECiAlarmControlPanel(CoordinatorEntity, AlarmControlPanelEntity):
    """ECi Main Panel managing all areas with MODE 4 ARMAREA/STAYAREA commands."""

    def __init__(
        self,
        coordinator: ArrowheadECiDataUpdateCoordinator,
        config_entry: ConfigEntry,
        panel_config: Dict[str, Any],
        firmware_info: Dict[str, Any],
    ) -> None:
        """Initialize the ECi main alarm control panel."""
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
            
        # Check armed states - check if ANY manual area is armed
        any_area_armed = False
        stay_mode = False
        
        # Check manual areas only
        manual_areas = data.get("active_areas_detected", {1})
        for area in manual_areas:
            area_letter = chr(96 + area)  # a, b, c, etc.
            area_key = f"area_{area_letter}_armed"
            if data.get(area_key, False):
                any_area_armed = True
                break
        
        # Also check general armed state for compatibility
        if not any_area_armed:
            any_area_armed = data.get("armed", False)
            
        stay_mode = data.get("stay_mode", False)
        
        if any_area_armed:
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
            
            _LOGGER.debug("ECi arming state changed: %s -> %s", old_state, new_state)
            
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
            
        self._arming_start_time = dt_util.utcnow()
        self._arming_progress = 0
        self._arming_time_remaining = self._exit_delay_seconds
        
        _LOGGER.info("Starting ECi arming sequence with %d second delay", self._exit_delay_seconds)
        
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
            
        current_time = dt_util.utcnow()
        elapsed = (current_time - self._arming_start_time).total_seconds()
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
        zone_sealed = data.get("zone_sealed", {})  # FIXED: Add sealed zones
        outputs = data.get("outputs", {})
        
        active_zones = [zone_id for zone_id, state in zones.items() if state]
        alarm_zones = [zone_id for zone_id, state in zone_alarms.items() if state]
        sealed_zones = [zone_id for zone_id, state in zone_sealed.items() if state]  # FIXED
        active_outputs = [output_id for output_id, state in outputs.items() if state]
        
        # Get manual areas
        manual_areas = data.get("active_areas_detected", {1})
        if isinstance(manual_areas, set):
            manual_areas = sorted(list(manual_areas))
        elif not isinstance(manual_areas, list):
            manual_areas = [1]
        
        attributes = {
            ATTR_READY_TO_ARM: data.get("ready_to_arm", False),
            ATTR_MAINS_POWER: data.get("mains_ok", True),
            ATTR_BATTERY_STATUS: data.get("battery_ok", True),
            ATTR_PROTOCOL_MODE: self._protocol_mode,
            ATTR_FIRMWARE_VERSION: self._firmware_version,
            ATTR_ACTIVE_AREAS: manual_areas,
            "configuration_type": "auto_zones_manual_areas",
            "status_message": data.get("status_message", "Unknown"),
            "connection_state": data.get("connection_state", "unknown"),
            "active_zones": active_zones,
            "alarm_zones": alarm_zones,
            "sealed_zones": sealed_zones,  # FIXED: Include sealed zones
            "active_outputs": active_outputs,
            "total_zones_configured": len(zones),
            "total_sealed_zones": len(sealed_zones),  # FIXED: Count sealed zones
            "total_outputs_configured": len(outputs),
            "manual_areas_count": len(manual_areas),
            
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
                
        # Add area status for manual areas only
        area_status = {}
        for area in manual_areas:
            area_letter = chr(96 + area)  # a, b, c, etc.
            area_key = f"area_{area_letter}_armed"
            if area_key in data:
                area_status[f"area_{area}"] = data[area_key]
        
        if area_status:
            attributes["area_armed_status"] = area_status
            
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
        """Send disarm command - user must specify user number if not user 1."""
        _LOGGER.info("Disarming ECi main panel")
        
        # Validate PIN is provided
        if not code:
            raise ServiceValidationError("PIN code is required for disarm operation")
        
        # Cancel any active arming sequence
        if self._arming_state == "arming":
            self._stop_arming_sequence()
            _LOGGER.info("ECi arming sequence cancelled by disarm command")
        
        try:
            code_stripped = code.strip()
            
            if ' ' not in code_stripped:
                # Just PIN provided - assume user 1
                formatted_command = f"1 {code_stripped}"
                _LOGGER.info("PIN only provided, assuming user 1: DISARM %s", formatted_command)
            else:
                # User number and PIN provided - use as-is
                parts = code_stripped.split(' ', 1)
                if len(parts) != 2:
                    raise ServiceValidationError("Invalid format. Use 'PIN' for user 1 or 'USER PIN' for other users")
                
                user_num, pin = parts
                try:
                    user_number = int(user_num)
                    if not (1 <= user_number <= 2000):
                        raise ServiceValidationError("User number must be between 1 and 2000")
                except ValueError:
                    raise ServiceValidationError("User number must be a valid integer")
                
                formatted_command = f"{user_number} {pin}"
                _LOGGER.info("User %d specified: DISARM %s", user_number, formatted_command)
            
            success = await self.coordinator.client.disarm_with_pin(formatted_command)
            
            if not success:
                _LOGGER.error("Failed to disarm ECi panel")
                raise ServiceValidationError("Disarm command failed - check user number and PIN")
                
        except Exception as err:
            _LOGGER.error("Error during disarm: %s", err)
            raise ServiceValidationError(f"Disarm failed: {str(err)}")

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command using ARMAWAY (main panel command)."""
        _LOGGER.info("Arming ECi main panel (away mode) using ARMAWAY command")
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            # Use simple ARMAWAY command for main panel
            success = await self.coordinator.client.send_main_panel_armaway()
            
            if not success:
                _LOGGER.error("Failed to arm ECi main panel (away mode)")
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error during main panel arm away: %s", err)
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command using ARMSTAY (main panel command)."""
        _LOGGER.info("Arming ECi main panel (stay mode) using ARMSTAY command")
        
        # Start arming sequence immediately for UI feedback
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            # Use simple ARMSTAY command for main panel
            success = await self.coordinator.client.send_main_panel_armstay()
            
            if not success:
                _LOGGER.error("Failed to arm ECi main panel (stay mode)")
                self._stop_arming_sequence()
                self._update_arming_state("idle")
                self.async_write_ha_state()
                
        except Exception as err:
            _LOGGER.error("Error during main panel arm stay: %s", err)
            self._stop_arming_sequence()
            self._update_arming_state("idle")
            self.async_write_ha_state()

    def _get_manual_areas(self) -> list:
        """Get manually configured areas from config entry."""
        return _get_manual_areas_from_config(self._config_entry)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data:
            # Check for any manual area armed state
            manual_areas = self._get_manual_areas()
            any_area_armed = False
            
            for area in manual_areas:
                area_letter = chr(96 + area)  # a, b, c, etc.
                area_key = f"area_{area_letter}_armed"
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
            self._update_arming_state("alarm")
            return AlarmControlPanelState.TRIGGERED
        
        # MODE 4: Check for area-specific alarm state
        if self._mode_4_active:
            area_alarm_key = f"area_{chr(96 + self._area_number)}_alarm"
            if data.get(area_alarm_key, False):
                self._update_arming_state("alarm")
                return AlarmControlPanelState.TRIGGERED
                
            # Check for entry delay affecting this area
            zone_entry_delays = data.get("zone_entry_delays", {})
            if zone_entry_delays:
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
        
        self._arming_start_time = dt_util.utcnow()
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
            
        current_time = dt_util.utcnow()
        elapsed = (current_time - self._arming_start_time).total_seconds()
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
        """Return extra state attributes for this area."""
        if not self.coordinator.data:
            return {}
            
        data = self.coordinator.data
        
        attributes = {
            "area_number": self._area_number,
            "ready_to_arm": data.get("ready_to_arm", True),
            "protocol_mode": self._protocol_mode,
            "firmware_version": self._firmware_version,
            "mode_4_active": self._mode_4_active,
            
            # Arming effects for this area
            "arming_state": self._arming_state,
            "arming_progress": self._arming_progress,
            "arming_time_remaining": self._arming_time_remaining,
            "exit_delay_seconds": self._exit_delay_seconds,
        }
        
        # MODE 4 specific attributes for this area
        if self._mode_4_active:
            area_letter = chr(96 + self._area_number)
            
            # Area-specific user tracking
            area_user_key = f"area_{area_letter}_armed_by_user"
            if area_user_key in data:
                attributes["armed_by_user"] = data[area_user_key]
            
            # Area-specific exit delay
            area_exit_delays = data.get("area_exit_delays", {})
            if self._area_number in area_exit_delays:
                attributes["area_exit_delay_remaining"] = area_exit_delays[self._area_number]
            
            # Entry delays for zones (general)
            zone_entry_delays = data.get("zone_entry_delays", {})
            if zone_entry_delays:
                attributes["zone_entry_delays"] = zone_entry_delays
                attributes["max_entry_delay_remaining"] = max(zone_entry_delays.values())
        
        return attributes

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command - user must specify user number if not user 1."""
        _LOGGER.info("Disarming ECi area %d", self._area_number)
        
        # Validate PIN is provided
        if not code:
            raise ServiceValidationError("PIN code is required for disarm operation")
        
        # Cancel any active arming sequence
        if self._arming_state == "arming":
            self._stop_arming_sequence()
        
        try:
            code_stripped = code.strip()
            
            if ' ' not in code_stripped:
                # Just PIN provided - assume user 1
                formatted_command = f"1 {code_stripped}"
                _LOGGER.info("PIN only provided, assuming user 1: DISARM %s", formatted_command)
            else:
                # User number and PIN provided - use as-is
                parts = code_stripped.split(' ', 1)
                if len(parts) != 2:
                    raise ServiceValidationError("Invalid format. Use 'PIN' for user 1 or 'USER PIN' for other users")
                
                user_num, pin = parts
                try:
                    user_number = int(user_num)
                    if not (1 <= user_number <= 2000):
                        raise ServiceValidationError("User number must be between 1 and 2000")
                except ValueError:
                    raise ServiceValidationError("User number must be a valid integer")
                
                formatted_command = f"{user_number} {pin}"
                _LOGGER.info("User %d specified: DISARM %s", user_number, formatted_command)
            
            success = await self.coordinator.client.disarm_with_pin(formatted_command)
            
            if not success:
                raise ServiceValidationError("Disarm command failed - check user number and PIN")
                
        except Exception as err:
            raise ServiceValidationError(f"Disarm failed: {str(err)}")

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command for this area using ARMAREA."""
        _LOGGER.info("Arming ECi area %d (away mode) using ARMAREA %d command", self._area_number, self._area_number)
        
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            success = await self.coordinator.client.send_armarea_command(self._area_number)
            
            if not success:
                _LOGGER.error("Failed to arm area %d away", self._area_number)
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
        _LOGGER.info("Arming ECi area %d (stay mode) using STAYAREA %d command", self._area_number, self._area_number)
        
        self._update_arming_state("arming")
        self.async_write_ha_state()
        
        try:
            success = await self.coordinator.client.send_stayarea_command(self._area_number)
            
            if not success:
                _LOGGER.error("Failed to arm area %d stay", self._area_number)
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
                
                if zone_entry_delays and self._arming_state != "entry_delay":
                    self._update_arming_state("entry_delay")
                elif not zone_entry_delays and self._arming_state == "entry_delay":
                    if area_armed:
                        self._update_arming_state("armed")
                    else:
                        self._update_arming_state("idle")
        
        self.async_write_ha_state()