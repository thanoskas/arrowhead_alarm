# Arrowhead Alarm Panel Integration File Structure

## Directory Structure
```
custom_components/arrowhead_alarm/
├── __init__.py                 # Main integration setup and service registration
├── manifest.json              # Integration metadata and requirements
├── config_flow.py             # Configuration flow with zone detection
├── const.py                   # Constants, panel configs, and utility functions
├── coordinator.py             # Data update coordinator
├── arrowhead_client.py         # Core client with protocol handling
├── eci_zone_detection.py       # ECi zone detection and configuration
├── alarm_control_panel.py      # Alarm control panel entity
├── binary_sensor.py           # Zone and system binary sensors
├── services.yaml              # Service definitions
├── strings.json               # UI strings and translations
└── translations/
    └── en.json                # English translations
```

## File Descriptions

### Core Files

- **`__init__.py`** - Integration entry point, coordinator setup, service registration
- **`manifest.json`** - Integration metadata for Home Assistant
- **`const.py`** - All constants, panel configurations, and utility functions
- **`config_flow.py`** - Configuration UI with connection testing and zone setup
- **`coordinator.py`** - Data update coordinator with error handling and reconnection

### Client and Protocol

- **`arrowhead_client.py`** - Main client class with:
  - Version detection and protocol adaptation
  - Connection state management  
  - Message parsing and processing
  - Panel-specific optimizations
  
- **`eci_zone_detection.py`** - ECi-specific zone detection:
  - Auto-detection of zones and areas
  - Expander detection
  - Configuration management

### Entities

- **`alarm_control_panel.py`** - Main alarm panel entity with:
  - Arm/disarm functionality
  - Status attributes
  - Panel-specific features
  
- **`binary_sensor.py`** - Zone and system sensors:
  - Individual zone sensors (state, alarm, trouble, etc.)
  - System status sensors (power, battery, etc.)
  - RF sensors (if supported)

### UI and Services

- **`services.yaml`** - Service definitions for trigger_output, arm/disarm
- **`strings.json`** - UI strings for configuration flow
- **`translations/en.json`** - English translations

## Key Features

### Multi-Panel Support
- **ESX Elite-SX**: Up to 32 zones, 16 outputs, RF support
- **ECi Series**: Up to 248 zones, 32 outputs, dynamic detection

### Advanced Zone Detection (ECi)
- Auto-detection via panel program locations
- Expander detection and configuration
- User override capabilities

### Protocol Adaptation
- Version detection and capability negotiation
- ECi protocol mode selection (Mode 1/4)
- Panel-specific message handling

### Robust Error Handling
- Automatic reconnection with exponential backoff
- Connection state monitoring
- Comprehensive error reporting

### Home Assistant Integration
- Configuration flow with validation
- Options flow for runtime changes
- Proper entity relationships and device info
- Service registration for panel operations

## Installation

1. Copy the entire `arrowhead_alarm` folder to `custom_components/`
2. Restart Home Assistant
3. Go to Settings → Devices & Services → Add Integration
4. Search for "Arrowhead Alarm Panel"
5. Follow the configuration wizard

## Usage

The integration will automatically:
- Detect your panel type and capabilities
- Configure zones based on detection or user preferences  
- Create appropriate entities for zones and system status
- Provide services for arm/disarm and output control
- Handle reconnection and error recovery

All files work together to provide a comprehensive, robust integration for Arrowhead alarm panels with advanced zone detection and panel-specific optimizations.