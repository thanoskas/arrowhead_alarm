# Updated const.py for ECi-only support with MODE 4
"""Constants for the Arrowhead ECi Alarm Panel integration - ECi Only Edition."""

DOMAIN = "arrowhead_eci"

# Configuration options
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USER_PIN = "user_pin"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Zone configuration options
CONF_AUTO_DETECT_ZONES = "auto_detect_zones"
CONF_MAX_ZONES = "max_zones"
CONF_AREAS = "areas"
CONF_ZONE_DETECTION_METHOD = "zone_detection_method"

# Output configuration options
CONF_MAX_OUTPUTS = "max_outputs"

# ECi Only - No panel type selection needed
PANEL_TYPE = "eci"
PANEL_NAME = "ECi Series"

# Default values
DEFAULT_PORT = 9000
DEFAULT_USER_PIN = "1 123"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin"
DEFAULT_MAX_OUTPUTS = 4

# Protocol modes for ECi
class ProtocolMode:
    MODE_1 = 1  # Default, no acknowledgments
    MODE_2 = 2  # AAP mode, with acknowledgments
    MODE_3 = 3  # Permaconn mode, with acknowledgments
    MODE_4 = 4  # Home Automation mode, no acknowledgments (ECi FW 10.3.50+)

# MODE 4 specific features (new in 10.3.50)
MODE_4_FEATURES = {
    "keypad_alarms": True,  # KPANICALARM, KFIREALARM, KMEDICALARM
    "enhanced_area_commands": True,  # ARMAREA, STAYAREA
    "user_tracking": True,  # Ax-Uy, Dx-Uy, Sx-Uy messages
    "enhanced_entry_delay": True,  # ZEDS messages with time
    "enhanced_exit_delay": True,  # EDAx-TT, EDSx-TT messages
}

# ECi Panel Configuration
PANEL_CONFIG = {
    "name": "ECi Series",
    "max_zones": 248,
    "max_outputs": 32,
    "default_outputs": 4,
    "supports_areas": True,
    "supports_rf": False,  # ECi doesn't have RF supervision
    "supports_expanders": True,
    "supports_output_detection": True,
    "default_port": 9000,
    "zone_detection": True,
    "protocol_modes": [1, 2, 3, 4],
    "firmware_detection": True,
    "mode_4_minimum_version": "10.3.50",
}

# Zone ranges for ECi expanders
ZONE_RANGES = {
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
    "zone_expander_15": (241, 248),
}

# Output ranges for ECi
OUTPUT_RANGES = {
    "main_panel": (1, 4),
    "expander_1": (5, 8),
    "expander_2": (9, 16),
    "expander_3": (17, 32),
}

# ECi Program locations for detection and configuration
ECI_PROGRAM_LOCATIONS = {
    "active_areas": "P4076E1",  # Query active areas (v10.2.393+)
    "zones_in_area": "P4075E{area}",  # Query zones in area (v10.2.392+)
    "user_codes": "P1E{user}",
    "zone_types": "P2E{zone}",
    "zone_areas": "P3E{zone}",  # Zone area assignments
    "output_config": "P5{output:03d}E1",
    "output_type": "P5{output:03d}E2",
    "output_timer": "P5{output:03d}E3",
}

# Entity attributes
ATTR_ZONE_STATUS = "zone_status"
ATTR_READY_TO_ARM = "ready_to_arm"
ATTR_MAINS_POWER = "mains_power"
ATTR_BATTERY_STATUS = "battery_status"
ATTR_TOTAL_ZONES = "total_zones"
ATTR_MAX_ZONES = "max_zones"
ATTR_ACTIVE_AREAS = "active_areas"
ATTR_PROTOCOL_MODE = "protocol_mode"
ATTR_FIRMWARE_VERSION = "firmware_version"

# Zone detection methods
ZONE_DETECTION_METHODS = {
    "active_areas_query": "Active Areas Query (P4076E1)",
    "zones_in_areas_query": "Zones in Areas Query (P4075Ex)",
    "status_parsing": "Status Message Parsing",
    "manual_configuration": "Manual Configuration",
    "error_fallback": "Error Fallback",
}

# Enhanced icons for MODE 4 features
ENTITY_ICONS = {
    "alarm_control_panel": {
        "disarmed": "mdi:shield-off",
        "armed_away": "mdi:shield-lock",
        "armed_home": "mdi:shield-half-full",
        "arming": "mdi:shield-sync",
        "pending": "mdi:shield-sync",
        "triggered": "mdi:shield-alert",
        "entry_delay": "mdi:shield-sync-outline",
        "exit_delay": "mdi:shield-clock",
        "default": "mdi:shield-home",
    },
    "binary_sensor": {
        "zone_state_closed": "mdi:door-closed",
        "zone_state_open": "mdi:door-open",
        "zone_alarm_active": "mdi:alert-circle",
        "zone_trouble_active": "mdi:alert-triangle",
        "zone_bypassed_active": "mdi:shield-off",
        "system_mains_ok": "mdi:power-plug",
        "system_battery_ok": "mdi:battery",
        "system_ready_to_arm": "mdi:shield-check",
    },
    "switch": {
        "output_off": "mdi:electric-switch",
        "output_on": "mdi:electric-switch-closed",
    },
    "button": {
        "bypass_inactive": "mdi:shield-off-outline",
        "bypass_active": "mdi:shield-off",
        "panic_alarm": "mdi:alarm-bell",
        "fire_alarm": "mdi:fire-alert",
        "medical_alarm": "mdi:medical-bag",
    }
}

# MODE 4 Enhanced Status Messages
MODE_4_STATUS_MESSAGES = {
    # Enhanced area messages with user tracking
    "area_armed_by_user": r"A(\d+)-U(\d+)",  # Area x armed by user y
    "area_disarmed_by_user": r"D(\d+)-U(\d+)",  # Area x disarmed by user y
    "area_stay_armed_by_user": r"S(\d+)-U(\d+)",  # Area x stay armed by user y
    
    # Enhanced alarm messages
    "area_alarm": r"AA(\d+)",  # Area x in alarm
    "area_alarm_restore": r"AR(\d+)",  # Area x alarm restored
    
    # Enhanced delay messages with timing
    "exit_delay_away": r"EDA(\d+)-(\d+)",  # Area x exit delay TT seconds
    "exit_delay_stay": r"EDS(\d+)-(\d+)",  # Area x stay exit delay TT seconds
    "entry_delay_zone": r"ZEDS(\d+)-(\d+)",  # Zone x entry delay TT seconds
    
    # Keypad alarm functions (MODE 4 only)
    "keypad_panic_alarm": "PA",
    "keypad_panic_clear": "PC", 
    "keypad_fire_alarm": "FA",
    "keypad_fire_clear": "FC",
    "keypad_medical_alarm": "MA",
    "keypad_medical_clear": "MC",
}

def get_firmware_version_tuple(version_string: str) -> tuple:
    """Convert version string to tuple for comparison."""
    if not version_string:
        return (0, 0, 0)
    
    # Extract version from strings like "ECi F/W Ver. 10.3.50"
    import re
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_string)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)

def supports_mode_4(firmware_version: str) -> bool:
    """Check if firmware version supports MODE 4."""
    version_tuple = get_firmware_version_tuple(firmware_version)
    minimum_tuple = (10, 3, 50)
    return version_tuple >= minimum_tuple

def get_optimal_protocol_mode(firmware_version: str) -> int:
    """Get the optimal protocol mode for the firmware version."""
    if supports_mode_4(firmware_version):
        return ProtocolMode.MODE_4
    else:
        return ProtocolMode.MODE_1

# Utility functions
def generate_zone_names(max_zones: int, prefix: str = "Zone") -> dict:
    """Generate zone names with zero-padding."""
    return {i: f"{prefix} {i:03d}" for i in range(1, max_zones + 1)}

def detect_expander_from_zone(zone_number: int) -> str:
    """Detect which expander a zone belongs to."""
    for expander_name, (start, end) in ZONE_RANGES.items():
        if start <= zone_number <= end:
            return expander_name
    return "unknown"

def validate_eci_configuration(max_zones: int, areas: list) -> dict:
    """Validate ECi configuration parameters."""
    errors = []
    warnings = []
    
    if max_zones > PANEL_CONFIG["max_zones"]:
        errors.append(f"Max zones ({max_zones}) exceeds ECi limit ({PANEL_CONFIG['max_zones']})")
    elif max_zones < 1:
        errors.append("Max zones must be at least 1")
        
    if not areas:
        errors.append("At least one area must be specified")
    elif any(area < 1 or area > 32 for area in areas):
        errors.append("Area numbers must be between 1 and 32")
        
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }