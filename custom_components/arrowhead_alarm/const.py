"""Constants for the Arrowhead Alarm Panel integration with enhanced zone and output support."""

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