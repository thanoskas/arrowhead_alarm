"""Constants for the Arrowhead Alarm Panel integration with enhanced zone, output support, and dynamic icons."""

DOMAIN = "arrowhead_alarm"

# Configuration options
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USER_PIN = "user_pin"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_PANEL_TYPE = "panel_type"

# Zone configuration options
CONF_AUTO_DETECT_ZONES = "auto_detect_zones"
CONF_MAX_ZONES = "max_zones"
CONF_AREAS = "areas"
CONF_ZONE_DETECTION_METHOD = "zone_detection_method"

# Output configuration options
CONF_MAX_OUTPUTS = "max_outputs"

# Panel types
PANEL_TYPE_ESX = "esx"
PANEL_TYPE_ECI = "eci"

PANEL_TYPES = {
    PANEL_TYPE_ESX: "ESX Elite-SX",
    PANEL_TYPE_ECI: "ECi Series"
}

# Default values
DEFAULT_PORT = 9000
DEFAULT_USER_PIN = "1 123"  # User 1 with code 123
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DEFAULT_PANEL_TYPE = PANEL_TYPE_ESX
DEFAULT_MAX_OUTPUTS = 4

# Entity attributes
ATTR_ZONE_STATUS = "zone_status"
ATTR_READY_TO_ARM = "ready_to_arm"
ATTR_MAINS_POWER = "mains_power"
ATTR_BATTERY_STATUS = "battery_status"
ATTR_PANEL_TYPE = "panel_type"
ATTR_TOTAL_ZONES = "total_zones"
ATTR_MAX_ZONES = "max_zones"
ATTR_ACTIVE_AREAS = "active_areas"

# Zone mapping - Basic defaults (will be dynamically expanded based on detection)
ZONES_ESX_BASE = {
    1: "Zone 1", 2: "Zone 2", 3: "Zone 3", 4: "Zone 4",
    5: "Zone 5", 6: "Zone 6", 7: "Zone 7", 8: "Zone 8",
    9: "Zone 9", 10: "Zone 10", 11: "Zone 11", 12: "Zone 12",
    13: "Zone 13", 14: "Zone 14", 15: "Zone 15", 16: "Zone 16"
}

ZONES_ECI_BASE = {
    1: "Zone 1", 2: "Zone 2", 3: "Zone 3", 4: "Zone 4",
    5: "Zone 5", 6: "Zone 6", 7: "Zone 7", 8: "Zone 8",
    9: "Zone 9", 10: "Zone 10", 11: "Zone 11", 12: "Zone 12",
    13: "Zone 13", 14: "Zone 14", 15: "Zone 15", 16: "Zone 16"
}

# Zone range definitions for expander detection
ZONE_RANGES = {
    PANEL_TYPE_ESX: {
        "main_panel": (1, 16),
        "expander_1": (17, 32),
    },
    PANEL_TYPE_ECI: {
        "main_panel": (1, 16),
        "zone_expander_1": (17, 32),
        "zone_expander_2": (33, 48),
        "zone_expander_3": (49, 64),
        "zone_expander_4": (65, 80),
        "zone_expander_5": (81, 96),
        "zone_expander_6": (97, 112),
        "zone_expander_7": (113, 128),
        "zone_expander_8": (129, 144),
        "zone_expander_9": (145, 160),
        "zone_expander_10": (161, 176),
        "zone_expander_11": (177, 192),
        "zone_expander_12": (193, 208),
        "zone_expander_13": (209, 224),
        "zone_expander_14": (225, 240),
        "zone_expander_15": (241, 248),  # Max 248 zones per ECi documentation
    }
}

# Output detection methods
OUTPUT_DETECTION_METHODS = {
    "config_query": "Panel Configuration Query",
    "output_testing": "Output Testing",
    "status_parsing": "Status Message Parsing", 
    "panel_defaults": "Panel Type Defaults",
    "manual_configuration": "Manual Configuration",
    "error_fallback": "Emergency Fallback"
}

# Output range definitions for different panel configurations
OUTPUT_RANGES = {
    PANEL_TYPE_ESX: {
        "main_panel": (1, 4),      # ESX main panel: outputs 1-4
        "expander_1": (5, 8),      # First expander: outputs 5-8
        "expander_2": (9, 16),     # Second expander: outputs 9-16
    },
    PANEL_TYPE_ECI: {
        "main_panel": (1, 4),      # ECi main panel: outputs 1-4
        "expander_1": (5, 8),      # ECi expander 1: outputs 5-8
        "expander_2": (9, 16),     # ECi expander 2: outputs 9-16
        "expander_3": (17, 32),    # ECi expander 3: outputs 17-32
    }
}

# Default output counts by panel type
DEFAULT_OUTPUT_COUNTS = {
    PANEL_TYPE_ESX: 4,   # ESX Elite-SX typically has 4 outputs standard
    PANEL_TYPE_ECI: 4,   # ECi typically has 4 outputs on main panel
}

# Output configuration program locations (ECi specific)
ECI_OUTPUT_PROGRAM_LOCATIONS = {
    "output_config": "P5{output:03d}E1",    # Output configuration (substitute {output})
    "output_type": "P5{output:03d}E2",      # Output type
    "output_timer": "P5{output:03d}E3",     # Output timer settings
}

# ECi Program locations for zone detection
ECI_PROGRAM_LOCATIONS = {
    "active_areas": "P4076E1",      # Query active areas
    "zones_in_area": "P4075E{area}", # Query zones in specific area (substitute {area})
    "user_codes": "P1E{user}",      # User codes (substitute {user})
    "zone_types": "P2E{zone}",      # Zone types (substitute {zone})
}

# Panel-specific configurations
PANEL_CONFIGS = {
    PANEL_TYPE_ESX: {
        "name": "ESX Elite-SX",
        "zones": ZONES_ESX_BASE,
        "max_zones": 32,          # ESX supports up to 32 zones standard
        "max_outputs": 16,        # ESX can support up to 16 outputs with expanders
        "default_outputs": 4,     # Standard configuration
        "supports_areas": True,
        "supports_rf": True,
        "supports_expanders": True,
        "supports_output_detection": True,  # ESX supports output testing
        "default_port": 9000,
        "zone_detection": False,   # ESX doesn't need dynamic detection
    },
    PANEL_TYPE_ECI: {
        "name": "ECi Series", 
        "zones": ZONES_ECI_BASE,
        "max_zones": 248,         # ECi can support up to 248 zones with expanders
        "max_outputs": 32,        # ECi can support up to 32 outputs with expanders
        "default_outputs": 4,     # Standard configuration
        "supports_areas": True,   # ECi supports multiple areas
        "supports_rf": False,     # ECi doesn't have RF supervision
        "supports_expanders": True,
        "supports_output_detection": True,  # ECi supports config queries and testing
        "default_port": 9000,
        "zone_detection": True,   # ECi needs dynamic zone detection
    }
}

# ========================================
# DYNAMIC ICON SYSTEM
# ========================================

# Icon mappings for different entity types and states
ENTITY_ICONS = {
    "alarm_control_panel": {
        "disarmed": "mdi:shield-off",
        "armed_away": "mdi:shield-lock", 
        "armed_home": "mdi:shield-half-full",
        "arming": "mdi:shield-sync",
        "pending": "mdi:shield-sync",
        "triggered": "mdi:shield-alert",
        "default": "mdi:shield-home",
        # System issue variants
        "disarmed_issues": "mdi:shield-alert-outline",
        "armed_issues": "mdi:shield-lock-outline"
    },
    "binary_sensor": {
        # Zone sensors
        "zone_state_closed": "mdi:door-closed",
        "zone_state_open": "mdi:door-open",
        "zone_alarm_active": "mdi:alert-circle",
        "zone_alarm_inactive": "mdi:alert-circle-outline",
        "zone_trouble_active": "mdi:alert-triangle",
        "zone_trouble_inactive": "mdi:alert-triangle-outline",
        "zone_bypassed_active": "mdi:shield-off",
        "zone_bypassed_inactive": "mdi:shield-off-outline",
        "zone_supervise_fail_active": "mdi:wifi-off",
        "zone_supervise_fail_inactive": "mdi:wifi",
        
        # System sensors
        "system_mains_ok": "mdi:power-plug",
        "system_mains_fail": "mdi:power-plug-off",
        "system_battery_ok": "mdi:battery",
        "system_battery_low": "mdi:battery-alert",
        "system_ready_to_arm": "mdi:shield-check",
        "system_not_ready": "mdi:shield-remove",
        "system_line_ok": "mdi:phone",
        "system_line_fail": "mdi:phone-off",
        "system_dialer_ok": "mdi:phone-dial",
        "system_dialer_fail": "mdi:phone-alert",
        "system_fuse_ok": "mdi:fuse",
        "system_fuse_fail": "mdi:fuse-alert",
        "system_rf_receiver_ok": "mdi:radio-tower",
        "system_rf_receiver_fail": "mdi:radio-tower-off",
        "system_rf_battery_ok": "mdi:battery-wireless",
        "system_rf_battery_low": "mdi:battery-wireless-alert",
        "system_sensor_watch_ok": "mdi:eye-check",
        "system_sensor_watch_alarm": "mdi:eye-alert",
        "system_tamper_normal": "mdi:shield-check",
        "system_tamper_alarm": "mdi:shield-alert"
    },
    "switch": {
        "output_off": "mdi:electric-switch",
        "output_on": "mdi:electric-switch-closed",
        "output_momentary": "mdi:gesture-tap-button"
    },
    "button": {
        "bypass_inactive": "mdi:shield-off-outline",
        "bypass_active": "mdi:shield-off"
    }
}

# Custom icon definitions (for future use with custom icon font)
CUSTOM_ICONS = {
    "integration": "arrowhead:shield-panel",
    "alarm_panel": "arrowhead:control-panel", 
    "zone_sensor": "arrowhead:door-sensor",
    "output_switch": "arrowhead:output-relay",
    "system_sensor": "arrowhead:system-status"
}

# Common zone type icons (can be used for zone customization)
ZONE_TYPE_ICONS = {
    "door": {"closed": "mdi:door-closed", "open": "mdi:door-open"},
    "window": {"closed": "mdi:window-closed", "open": "mdi:window-open"},
    "motion": {"inactive": "mdi:motion-sensor-off", "active": "mdi:motion-sensor"},
    "glass": {"normal": "mdi:window-closed-variant", "alarm": "mdi:glass-fragile"},
    "smoke": {"normal": "mdi:smoke-detector", "alarm": "mdi:smoke-detector-alert"},
    "flood": {"normal": "mdi:water-off", "alarm": "mdi:water-alert"},
    "temperature": {"normal": "mdi:thermometer", "alarm": "mdi:thermometer-alert"},
    "panic": {"normal": "mdi:alarm-bell", "alarm": "mdi:alarm-bell"},
    "medical": {"normal": "mdi:medical-bag", "alarm": "mdi:medical-bag"},
    "fire": {"normal": "mdi:fire-off", "alarm": "mdi:fire-alert"},
    "gas": {"normal": "mdi:gas-cylinder", "alarm": "mdi:gas-cylinder-alert"}
}

# ========================================
# ICON HELPER FUNCTIONS
# ========================================

def get_entity_icon(entity_type: str, entity_subtype: str = None, state: any = None, 
                   has_issues: bool = False) -> str:
    """Get appropriate icon for entity type, subtype, and state.
    
    Args:
        entity_type: Type of entity (alarm_control_panel, binary_sensor, etc.)
        entity_subtype: Subtype of entity (zone_state, system_mains, etc.)
        state: Current state (True/False for binary sensors, state enum for alarm)
        has_issues: Whether the entity has system issues
    
    Returns:
        MDI icon string
    """
    if entity_type not in ENTITY_ICONS:
        return "mdi:help-circle"
    
    icons = ENTITY_ICONS[entity_type]
    
    # Handle alarm control panel icons
    if entity_type == "alarm_control_panel":
        if hasattr(state, 'value'):
            state_key = state.value  # Handle enum states
        else:
            state_key = str(state) if state else "disarmed"
        
        # Check for system issues variant
        if has_issues:
            issue_key = f"{state_key}_issues"
            if issue_key in icons:
                return icons[issue_key]
        
        return icons.get(state_key, icons.get("default", "mdi:shield-home"))
    
    # Handle binary sensor icons
    if entity_type == "binary_sensor" and entity_subtype:
        state_suffix = "active" if state else "inactive"
        
        # Special handling for zone state sensors (open/closed instead of active/inactive)
        if entity_subtype == "zone_state":
            state_suffix = "open" if state else "closed"
        
        # Try specific state icon first
        state_key = f"{entity_subtype}_{state_suffix}"
        if state_key in icons:
            return icons[state_key]
        
        # Try base subtype
        if entity_subtype in icons:
            return icons[entity_subtype]
    
    # Handle switch icons
    if entity_type == "switch":
        if entity_subtype == "output":
            if state:
                return icons.get("output_on", "mdi:electric-switch-closed")
            else:
                return icons.get("output_off", "mdi:electric-switch")
    
    # Handle button icons
    if entity_type == "button" and entity_subtype:
        state_suffix = "active" if state else "inactive"
        state_key = f"{entity_subtype}_{state_suffix}"
        if state_key in icons:
            return icons[state_key]
    
    # Fallback to default or help icon
    return icons.get("default", "mdi:help-circle")

def get_alarm_panel_icon(alarm_state: str, has_system_issues: bool = False) -> str:
    """Get icon for alarm panel based on state and system health.
    
    Args:
        alarm_state: Current alarm state
        has_system_issues: Whether there are system issues
        
    Returns:
        MDI icon string
    """
    return get_entity_icon("alarm_control_panel", None, alarm_state, has_system_issues)

def get_zone_sensor_icon(sensor_type: str, is_active: bool = False, zone_type: str = None) -> str:
    """Get icon for zone sensor based on type, state, and optional zone type.
    
    Args:
        sensor_type: Type of sensor (state, alarm, trouble, etc.)
        is_active: Whether the sensor is currently active
        zone_type: Optional zone type (door, window, motion, etc.)
        
    Returns:
        MDI icon string
    """
    # If zone type is specified and it's a state sensor, use zone type icons
    if zone_type and sensor_type == "state" and zone_type in ZONE_TYPE_ICONS:
        zone_icons = ZONE_TYPE_ICONS[zone_type]
        state_key = "open" if is_active else "closed"
        if "active" in zone_icons and "inactive" in zone_icons:
            state_key = "active" if is_active else "inactive"
        elif "alarm" in zone_icons and "normal" in zone_icons:
            state_key = "alarm" if is_active else "normal"
        return zone_icons.get(state_key, zone_icons.get("closed", "mdi:help-circle"))
    
    return get_entity_icon("binary_sensor", f"zone_{sensor_type}", is_active)

def get_system_sensor_icon(sensor_type: str, is_ok: bool = True) -> str:
    """Get icon for system sensor based on type and status.
    
    Args:
        sensor_type: Type of system sensor (mains, battery, etc.)
        is_ok: Whether the system is OK (inverted for problem sensors)
        
    Returns:
        MDI icon string
    """
    # For "ok" type sensors, invert the state for icon selection
    # For alarm type sensors, use state directly
    if sensor_type.endswith("_ok"):
        state = not is_ok  # Invert for "ok" sensors (True = fail icon)
        sensor_base = sensor_type[:-3]  # Remove "_ok" suffix
        state_suffix = "fail" if state else "ok"
    else:
        state = is_ok
        sensor_base = sensor_type
        state_suffix = "alarm" if state else "normal"
    
    state_key = f"system_{sensor_base}_{state_suffix}"
    return get_entity_icon("binary_sensor", state_key, state)

def get_output_switch_icon(is_on: bool = False, is_momentary: bool = False) -> str:
    """Get icon for output switch based on state and type.
    
    Args:
        is_on: Whether the output is currently on
        is_momentary: Whether this is a momentary output
        
    Returns:
        MDI icon string
    """
    if is_momentary:
        return ENTITY_ICONS["switch"]["output_momentary"]
    
    return get_entity_icon("switch", "output", is_on)

def get_bypass_button_icon(is_bypassed: bool = False) -> str:
    """Get icon for bypass button based on state.
    
    Args:
        is_bypassed: Whether the zone is currently bypassed
        
    Returns:
        MDI icon string
    """
    return get_entity_icon("button", "bypass", is_bypassed)

# ========================================
# UTILITY FUNCTIONS
# ========================================

def generate_zone_names(max_zones: int, prefix: str = "Zone", use_padding: bool = True) -> dict:
    """Generate zone names up to max_zones with zero-padding format."""
    if use_padding:
        # Use 3-digit zero-padded format: Zone 001, Zone 002, etc.
        return {i: f"{prefix} {i:03d}" for i in range(1, max_zones + 1)}
    else:
        # Use simple format: Zone 1, Zone 2, etc.
        return {i: f"{prefix} {i}" for i in range(1, max_zones + 1)}

def detect_expander_from_zone(zone_number: int, panel_type: str) -> str:
    """Detect which expander a zone belongs to."""
    ranges = ZONE_RANGES.get(panel_type, ZONE_RANGES[PANEL_TYPE_ECI])
    
    for expander_name, (start, end) in ranges.items():
        if start <= zone_number <= end:
            return expander_name
            
    return "unknown"

def detect_output_expander_from_number(output_number: int, panel_type: str) -> str:
    """Detect which expander an output belongs to."""
    ranges = OUTPUT_RANGES.get(panel_type, OUTPUT_RANGES[PANEL_TYPE_ECI])
    
    for expander_name, (start, end) in ranges.items():
        if start <= output_number <= end:
            return expander_name
            
    return "unknown"

def get_expected_output_count(panel_type: str, detected_zones: int = 0) -> int:
    """Get expected output count based on panel type and configuration."""
    base_count = DEFAULT_OUTPUT_COUNTS.get(panel_type, 4)
    
    # For ECi panels, estimate outputs based on zones (rough heuristic)
    if panel_type == PANEL_TYPE_ECI and detected_zones > 16:
        # If we have more than 16 zones, likely have expanders which may include outputs
        if detected_zones > 32:
            return min(16, base_count * 4)  # Up to 16 outputs with multiple expanders
        else:
            return min(8, base_count * 2)   # Up to 8 outputs with one expander
    
    return base_count

def validate_zone_configuration(panel_type: str, max_zones: int, areas: list) -> dict:
    """Validate zone configuration parameters."""
    panel_config = PANEL_CONFIGS[panel_type]
    
    errors = []
    warnings = []
    
    # Validate max zones
    if max_zones > panel_config["max_zones"]:
        errors.append(f"Max zones ({max_zones}) exceeds panel limit ({panel_config['max_zones']})")
    elif max_zones < 1:
        errors.append("Max zones must be at least 1")
        
    # Validate areas
    if not areas:
        errors.append("At least one area must be specified")
    elif any(area < 1 or area > 32 for area in areas):
        errors.append("Area numbers must be between 1 and 32")
        
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

def get_zone_name_with_type(zone_id: int, zone_type: str = None, use_padding: bool = True) -> str:
    """Generate zone name with optional type information.
    
    Args:
        zone_id: Zone number
        zone_type: Optional zone type (door, window, motion, etc.)
        use_padding: Whether to use zero-padding for zone number
        
    Returns:
        Formatted zone name
    """
    if use_padding:
        base_name = f"Zone {zone_id:03d}"
    else:
        base_name = f"Zone {zone_id}"
    
    if zone_type and zone_type in ZONE_TYPE_ICONS:
        type_names = {
            "door": "Door",
            "window": "Window", 
            "motion": "Motion",
            "glass": "Glass Break",
            "smoke": "Smoke",
            "flood": "Flood",
            "temperature": "Temperature",
            "panic": "Panic",
            "medical": "Medical",
            "fire": "Fire",
            "gas": "Gas"
        }
        type_name = type_names.get(zone_type, zone_type.title())
        return f"{base_name} ({type_name})"
    
    return base_name