# IMPROVED const.py for ECi-only support with enhanced configuration management
"""Constants for the Arrowhead ECi Alarm Panel integration - IMPROVED VERSION."""

import re
from typing import Tuple, Dict, Any, List
from enum import Enum

DOMAIN = "arrowhead_alarm"

# Configuration options
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USER_PIN = "user_pin"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

# Zone configuration options
CONF_AUTO_DETECT_ZONES = "auto_detect_zones"
CONF_MAX_ZONES = "max_zones"
CONF_AREAS = "areas"  # Manual areas only

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
class ProtocolMode(Enum):
    """ECi Protocol modes with descriptions."""
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
    "programming_queries": True,  # P4075Ex?, P4076E1? commands
    "enhanced_status": True,  # Enhanced status reporting
}

# ECi Panel Configuration - IMPROVED
PANEL_CONFIG = {
    "name": "ECi Series",
    "max_zones": 248,
    "max_outputs": 32,
    "default_outputs": 4,
    "supports_areas": True,
    "max_areas": 32,
    "supports_rf": False,  # ECi doesn't have RF supervision
    "supports_expanders": True,
    "supports_output_detection": True,
    "default_port": 9000,
    "zone_detection": True,  # AUTO ZONE DETECTION
    "area_detection": False,  # MANUAL AREA CONFIGURATION
    "protocol_modes": [1, 2, 3, 4],
    "firmware_detection": True,
    "mode_4_minimum_version": "10.3.50",
    "connection_timeout": 30,
    "command_timeout": 10,
    "zone_name_max_length": 50,
    "supported_baud_rates": [9600, 19200, 38400],
}

# Zone ranges for ECi expanders - IMPROVED
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

# Output ranges for ECi - IMPROVED
OUTPUT_RANGES = {
    "main_panel": (1, 4),
    "output_expander_1": (5, 8),
    "output_expander_2": (9, 16),
    "output_expander_3": (17, 32),
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
ATTR_CONNECTION_STATE = "connection_state"
ATTR_LAST_UPDATE = "last_update"

# Enhanced icons for MODE 4 features - IMPROVED
ENTITY_ICONS = {
    "alarm_control_panel": {
        "disarmed": "mdi:shield-off",
        "armed_away": "mdi:shield-lock",
        "armed_home": "mdi:shield-half-full",
        "armed_night": "mdi:shield-moon",
        "armed_vacation": "mdi:shield-airplane",
        "arming": "mdi:shield-sync",
        "pending": "mdi:shield-sync",
        "triggered": "mdi:shield-alert",
        "entry_delay": "mdi:shield-sync-outline",
        "exit_delay": "mdi:shield-clock",
        "mode_4_active": "mdi:shield-star",
        "mode_4_disarmed": "mdi:shield-star-outline",
        "default": "mdi:shield-home",
    },
    "binary_sensor": {
        "zone_state_closed": "mdi:door-closed",
        "zone_state_open": "mdi:door-open",
        "zone_alarm_active": "mdi:alert-circle",
        "zone_trouble_active": "mdi:alert-triangle",
        "zone_bypassed_active": "mdi:shield-off",
        "zone_sealed": "mdi:lock",
        "system_mains_ok": "mdi:power-plug",
        "system_battery_ok": "mdi:battery",
        "system_ready_to_arm": "mdi:shield-check",
        "system_connection_ok": "mdi:lan-connect",
    },
    "switch": {
        "output_off": "mdi:electric-switch",
        "output_on": "mdi:electric-switch-closed",
        "output_momentary": "mdi:gesture-tap",
    },
    "button": {
        "bypass_inactive": "mdi:shield-off-outline",
        "bypass_active": "mdi:shield-off",
        "panic_alarm": "mdi:alarm-bell",
        "fire_alarm": "mdi:fire-alert",
        "medical_alarm": "mdi:medical-bag",
    }
}

# MODE 4 Enhanced Status Messages - IMPROVED
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
    
    # Programming query responses
    "areas_config_response": r"P4076E1=(.+)",  # Areas configuration
    "area_zones_response": r"P4075E(\d+)=(.+)",  # Zones for area
}

# Configuration validation patterns - NEW
VALIDATION_PATTERNS = {
    "host_ip": r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$",
    "host_fqdn": r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$",
    "user_pin": r"^[1-9]\d{0,3}\s+\d{3,8}$",  # User number (1-9999) space PIN (3-8 digits)
    "areas_list": r"^[1-9]\d{0,1}(,[1-9]\d{0,1})*$",  # Comma-separated area numbers 1-32
    "zone_name": r"^[a-zA-Z0-9\s\-_\.]{1,50}$",  # Zone name validation
}

# Error messages for validation - NEW
VALIDATION_ERRORS = {
    "invalid_host": "Host must be a valid IP address or hostname",
    "invalid_port": "Port must be between 1 and 65535",
    "invalid_user_pin": "User PIN must be in format 'USER PIN' (e.g., '1 123')",
    "invalid_areas": "Areas must be comma-separated numbers between 1 and 32 (e.g., '1,2,3')",
    "too_many_areas": "Maximum 8 areas supported for optimal performance",
    "invalid_zone_name": "Zone name must be 1-50 characters, alphanumeric with spaces, hyphens, underscores, dots",
    "invalid_max_zones": "Max zones must be between 8 and 248",
    "invalid_max_outputs": "Max outputs must be between 1 and 32",
}

def get_firmware_version_tuple(version_string: str) -> Tuple[int, int, int]:
    """Convert version string to tuple for comparison - IMPROVED."""
    if not version_string:
        return (0, 0, 0)
    
    # Extract version from various formats
    patterns = [
        r'(\d+)\.(\d+)\.(\d+)',  # Standard x.y.z
        r'V(\d+)\.(\d+)\.(\d+)',  # Version Vx.y.z
        r'(\d+)\.(\d+)\.(\d+)\.(\d+)',  # Extended x.y.z.w (use first 3)
        r'(\d+)\.(\d+)',  # Short x.y (assume .0)
    ]
    
    for pattern in patterns:
        match = re.search(pattern, version_string)
        if match:
            groups = match.groups()
            if len(groups) >= 3:
                return tuple(int(x) for x in groups[:3])
            elif len(groups) == 2:
                return (int(groups[0]), int(groups[1]), 0)
    
    return (0, 0, 0)

def supports_mode_4(firmware_version: str) -> bool:
    """Check if firmware version supports MODE 4 - IMPROVED."""
    if not firmware_version:
        return False
    
    try:
        version_tuple = get_firmware_version_tuple(firmware_version)
        minimum_tuple = (10, 3, 50)
        result = version_tuple >= minimum_tuple
        
        # Log for debugging
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.debug("MODE 4 check: %s -> %s >= %s = %s", 
                     firmware_version, version_tuple, minimum_tuple, result)
        
        return result
    except Exception as err:
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.warning("Error checking MODE 4 support for '%s': %s", firmware_version, err)
        return False

def get_optimal_protocol_mode(firmware_version: str) -> int:
    """Get the optimal protocol mode for the firmware version - IMPROVED."""
    if supports_mode_4(firmware_version):
        return ProtocolMode.MODE_4.value
    else:
        # Check for other mode support based on version
        version_tuple = get_firmware_version_tuple(firmware_version)
        
        # MODE 3 support (example threshold)
        if version_tuple >= (8, 0, 0):
            return ProtocolMode.MODE_3.value
        # MODE 2 support (example threshold)
        elif version_tuple >= (6, 0, 0):
            return ProtocolMode.MODE_2.value
        else:
            return ProtocolMode.MODE_1.value

def get_panel_capabilities(firmware_version: str) -> Dict[str, bool]:
    """Get panel capabilities based on firmware version - NEW."""
    capabilities = {
        "mode_4_support": supports_mode_4(firmware_version),
        "programming_queries": False,
        "enhanced_status": False,
        "user_tracking": False,
        "keypad_alarms": False,
        "enhanced_delays": False,
    }
    
    if capabilities["mode_4_support"]:
        capabilities.update({
            "programming_queries": True,
            "enhanced_status": True,
            "user_tracking": True,
            "keypad_alarms": True,
            "enhanced_delays": True,
        })
    
    return capabilities

# Utility functions - IMPROVED

def generate_zone_names(max_zones: int, prefix: str = "Zone") -> Dict[int, str]:
    """Generate zone names with zero-padding - IMPROVED."""
    if max_zones <= 0 or max_zones > 248:
        raise ValueError("max_zones must be between 1 and 248")
    
    return {i: f"{prefix} {i:03d}" for i in range(1, max_zones + 1)}

def detect_expander_from_zone(zone_number: int) -> str:
    """Detect which expander a zone belongs to - IMPROVED."""
    if not isinstance(zone_number, int) or zone_number < 1 or zone_number > 248:
        return "invalid"
    
    for expander_name, (start, end) in ZONE_RANGES.items():
        if start <= zone_number <= end:
            return expander_name
    
    return "unknown"

def detect_output_expander(output_number: int) -> str:
    """Detect which output expander an output belongs to - NEW."""
    if not isinstance(output_number, int) or output_number < 1 or output_number > 32:
        return "invalid"
    
    for expander_name, (start, end) in OUTPUT_RANGES.items():
        if start <= output_number <= end:
            return expander_name
    
    return "unknown"

def validate_configuration_input(config_type: str, value: str) -> Dict[str, Any]:
    """Validate configuration input against patterns - NEW."""
    result = {
        "valid": False,
        "value": value,
        "processed_value": None,
        "errors": [],
        "warnings": []
    }
    
    try:
        if config_type == "host":
            # Allow both IP and hostname
            if (re.match(VALIDATION_PATTERNS["host_ip"], value) or 
                re.match(VALIDATION_PATTERNS["host_fqdn"], value)):
                result["valid"] = True
                result["processed_value"] = value.strip().lower()
            else:
                result["errors"].append(VALIDATION_ERRORS["invalid_host"])
        
        elif config_type == "user_pin":
            if re.match(VALIDATION_PATTERNS["user_pin"], value):
                result["valid"] = True
                result["processed_value"] = value.strip()
            else:
                result["errors"].append(VALIDATION_ERRORS["invalid_user_pin"])
        
        elif config_type == "areas":
            if re.match(VALIDATION_PATTERNS["areas_list"], value):
                areas = [int(x.strip()) for x in value.split(",")]
                # Remove duplicates and sort
                areas = sorted(set(areas))
                
                if len(areas) > 8:
                    result["warnings"].append(VALIDATION_ERRORS["too_many_areas"])
                    areas = areas[:8]
                
                result["valid"] = True
                result["processed_value"] = areas
            else:
                result["errors"].append(VALIDATION_ERRORS["invalid_areas"])
        
        elif config_type == "zone_name":
            if re.match(VALIDATION_PATTERNS["zone_name"], value):
                result["valid"] = True
                result["processed_value"] = value.strip()
            else:
                result["errors"].append(VALIDATION_ERRORS["invalid_zone_name"])
        
        else:
            result["errors"].append(f"Unknown configuration type: {config_type}")
    
    except Exception as err:
        result["errors"].append(f"Validation error: {str(err)}")
    
    return result

def parse_areas_string(areas_str: str) -> List[int]:
    """Parse areas string into list of integers - IMPROVED."""
    try:
        if not areas_str or not areas_str.strip():
            return [1]  # Default to area 1
        
        # Use validation function
        validation = validate_configuration_input("areas", areas_str.strip())
        
        if validation["valid"]:
            return validation["processed_value"]
        else:
            # Log warnings but continue
            import logging
            _LOGGER = logging.getLogger(__name__)
            _LOGGER.warning("Areas string validation failed: %s", validation["errors"])
            
            # Fallback parsing
            areas = []
            for area_str in areas_str.split(","):
                area_str = area_str.strip()
                if area_str.isdigit():
                    area = int(area_str)
                    if 1 <= area <= 32:
                        areas.append(area)
            
            # Remove duplicates and sort
            areas = sorted(set(areas))
            
            # Limit to 8 areas for stability
            if len(areas) > 8:
                areas = areas[:8]
            
            # Ensure at least area 1 if nothing valid
            if not areas:
                areas = [1]
            
            return areas
        
    except Exception as err:
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.error("Error parsing areas string '%s': %s", areas_str, err)
        return [1]  # Safe fallback

def format_areas_for_display(areas: List[int]) -> str:
    """Format areas list for display in UI - IMPROVED."""
    try:
        if not areas:
            return "1"
        
        # Ensure all are integers and in valid range
        valid_areas = [area for area in areas if isinstance(area, int) and 1 <= area <= 32]
        
        if not valid_areas:
            return "1"
        
        # Remove duplicates and sort
        unique_areas = sorted(set(valid_areas))
        
        return ",".join(map(str, unique_areas))
        
    except Exception as err:
        import logging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.error("Error formatting areas %s: %s", areas, err)
        return "1"

def get_zone_type_from_number(zone_number: int) -> str:
    """Get zone type description from zone number - NEW."""
    zone_types = {
        (1, 8): "Entry/Exit",
        (9, 16): "Perimeter",
        (17, 24): "Interior",
        (25, 32): "Basement/Garage",
        (33, 248): "Expansion"
    }
    
    for (start, end), zone_type in zone_types.items():
        if start <= zone_number <= end:
            return zone_type
    
    return "Unknown"

def validate_pin_format(user_pin: str) -> Dict[str, Any]:
    """Validate user PIN format - NEW."""
    result = {
        "valid": False,
        "user_number": None,
        "pin": None,
        "formatted": None,
        "errors": []
    }
    
    try:
        if not user_pin or not user_pin.strip():
            result["errors"].append("PIN is required")
            return result
        
        validation = validate_configuration_input("user_pin", user_pin.strip())
        
        if validation["valid"]:
            parts = validation["processed_value"].split()
            result["user_number"] = int(parts[0])
            result["pin"] = parts[1]
            result["formatted"] = validation["processed_value"]
            result["valid"] = True
        else:
            result["errors"] = validation["errors"]
    
    except Exception as err:
        result["errors"].append(f"PIN validation error: {str(err)}")
    
    return result

# Configuration presets for common setups - NEW
CONFIG_PRESETS = {
    "small_home": {
        "max_zones": 16,
        "areas": [1],
        "max_outputs": 4,
        "description": "Small home or apartment (1-16 zones, 1 area, 4 outputs)"
    },
    "medium_home": {
        "max_zones": 32,
        "areas": [1, 2],
        "max_outputs": 8,
        "description": "Medium home (1-32 zones, 2 areas, 8 outputs)"
    },
    "large_home": {
        "max_zones": 64,
        "areas": [1, 2, 3, 4],
        "max_outputs": 16,
        "description": "Large home (1-64 zones, 4 areas, 16 outputs)"
    },
    "commercial": {
        "max_zones": 248,
        "areas": [1, 2, 3, 4, 5, 6, 7, 8],
        "max_outputs": 32,
        "description": "Commercial building (1-248 zones, 8 areas, 32 outputs)"
    }
}

def get_recommended_preset(detected_zones: int = 0, detected_areas: int = 0) -> str:
    """Get recommended configuration preset - NEW."""
    if detected_zones > 64 or detected_areas > 4:
        return "commercial"
    elif detected_zones > 32 or detected_areas > 2:
        return "large_home"
    elif detected_zones > 16 or detected_areas > 1:
        return "medium_home"
    else:
        return "small_home"

# Integration health check constants - NEW
HEALTH_CHECK = {
    "connection_timeout": 30,
    "max_consecutive_failures": 5,
    "reconnect_delay_base": 10,  # seconds
    "reconnect_delay_max": 300,  # 5 minutes
    "status_check_interval": 60,  # seconds
    "zone_update_timeout": 5,
    "output_update_timeout": 3,
}

# Service call timeouts - NEW
SERVICE_TIMEOUTS = {
    "arm_disarm": 15,
    "output_control": 10,
    "zone_bypass": 8,
    "custom_command": 20,
    "status_refresh": 10,
    "area_status": 5,
}
