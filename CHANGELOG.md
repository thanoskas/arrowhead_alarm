# Changelog

All notable changes to the Arrowhead Alarm Panel integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).



## [2.2.4] - 2026-08-13

### Added

- **Integration icon** - the Arrowhead Alarm Products mark is now bundled as
  `brand/icon.png` / `brand/icon@2x.png`, so Home Assistant 2026.3+ shows the
  proper brand icon instead of "icon not available" (served via the local
  Brands Proxy API; no home-assistant/brands PR needed).

### Fixed

- **Config flow failed to load with "Error while loading .../translations/en.json:
  unexpected character"** - a UTF-8 byte-order mark was accidentally introduced
  into `strings.json` and `translations/en.json` in v2.2.3, which Home
  Assistant's JSON loader rejects. Both files are now BOM-free again.

## [2.2.3] - 2026-08-13

### Fixed

- **Setup no longer fails with "Invalid max_zones: 7"** (#5) - panels with
  fewer than 8 zones are now accepted everywhere (1-248).
- **Main alarm entity no longer drops to Disarmed during exit delay** (#7) -
  it now stays in Arming/Pending until the panel reports armed, matching the
  per-area entities. MODE 4 exit-delay messages (EDA/EDS) are now parsed.
- **Output and command reliability** (#6) - unsolicited panel events (zone,
  area, output changes) arriving while a command was waiting for its reply
  were mistaken for the reply, causing false "Failed to trigger output"
  errors. Replies are now matched correctly.
- **Zone names can finally be saved from Panel Options** (#2) - the form no
  longer loops back empty; submitted names are stored and applied.
- **status_message attribute** no longer stays stuck on "Initializing".
- **Integration version** is now reported correctly - previous releases
  bumped a stray root manifest.json while Home Assistant read the one in
  custom_components (still 2.0.0).

## 🎉 What's New in Version 2.2.0

### Inproved event hadnling

✅ Better commands handilg (handle message sequences)
✅ Real-time updates (<200ms instead of 0-30 sec)
✅ No more "Failed to bypass" errors
✅ Instant zone state changes
✅ Responsive UI


## 🎉 What's New in Version 2.1.1

### 🚀 Full Individual Area Control

**Two-Tier System:**
- **Main Panel Entity**: Arms/disarms ALL areas simultaneously (MODE 4)
- **Area Entities**: Individual control per area (MODE 4 ARM, MODE 2 DISARM)

**Key Features:**
- ✅ **Individual Area Arming**: ARMAREA/STAYAREA commands (requires P74E/P76E configuration)
- ✅ **Individual Area Disarm**: Automatic MODE 2/4 switching for area-specific disarm
- ✅ **Smart Protocol**: Client handles mode switching automatically

**Panel Requirements:**
- `P74E` - Configure areas for individual away arming
- `P76E` - Configure areas for individual stay arming

> **Note**: Without P74E/P76E configuration, ARMAREA/STAYAREA will fail with ERR 2

---

## 📊 Version Comparison

| Feature | v1.x | v2.1.1 |
|---------|------|--------|
| **Panel Support** | ESX + ECi | ECi Only |
| **MODE 4 Protocol** | ❌ | ✅ Full Support |
| **Individual Areas** | ❌ | ✅ Per-Area Control |
| **Individual Disarm** | ❌ | ✅ MODE 2 Support |
| **Keypad Alarms** | ❌ | ✅ Panic/Fire/Medical |
| **Bulk Operations** | ⚠️ Limited | ✅ Full Support |
| **Sealed Zones** | ⚠️ Basic | ✅ Enhanced |

### 🚀 Major Changes

- **🎯 ECi-Only Focus**: Streamlined exclusively for ECi Series panels
- **🚀 MODE 4 Support**: Full support for firmware 10.3.50+ enhanced features
- **🏠 Individual Area Panels**: Separate alarm panel entity for each configured area
- **⚡ Enhanced Services**: 36+ services including bulk operations and keypad alarms
- **🔍 Improved Detection**: Better zone detection with sealed zone support
- **🐛 Bug Fixes**: Numerous fixes for stability and reliability
- **📊 Better Monitoring**: Health tracking and improved diagnostics



> **Breaking Change**: Version 2.0.1+ only supports ECi Series panels. ESX Elite-SX users should continue using version 1.x.
## [2.0.0] - 2024-12-03

### 🎯 Major Changes

#### ECi-Only Focus
- **BREAKING**: Removed ESX Elite-SX support (moved to separate branch)
- Streamlined codebase for ECi Series panels only
- Simplified configuration flow for single panel type
- Improved performance with ECi-specific optimizations

#### MODE 4 Protocol Support
- Full support for ECi firmware 10.3.50+ MODE 4 protocol
- Enhanced communication with no acknowledgment overhead
- Better compatibility with latest ECi firmware versions
- Automatic protocol mode detection and adaptation

#### Area Management Overhaul
- Individual alarm panel entities for each configured area
- Separate control and monitoring per area
- Main panel entity controlling all areas
- Better state representation for multi-area systems

### ✨ Added Features

#### Keypad Alarms (MODE 4)
- Trigger panic alarms via `trigger_keypad_alarm` service
- Trigger fire alarms via service
- Trigger medical alarms via service
- Keypad alarm state tracking in binary sensors

#### Enhanced Area Commands
- `ARMAREA` command for MODE 4 away arming
- `STAYAREA` command for MODE 4 stay arming
- More reliable area-specific arming
- User tracking for arm/disarm actions

#### Bulk Operations
- `bulk_arm_areas` service for arming multiple areas
- `bulk_disarm_areas` service for disarming multiple areas
- `bulk_bypass` service for zone bypass operations
- Configurable delays between bulk commands

#### Improved Zone Detection
- Better P4075Ex response parsing
- Sealed zone support and initialization
- More accurate zone count detection
- Enhanced expander detection

#### Health Monitoring
- Comprehensive health check system
- Connection state tracking
- Success rate metrics
- Communication error tracking
- Diagnostic information service

#### Output Management
- Improved output switch creation
- Better state synchronization
- Multiple detection methods with fallback
- Enhanced output control reliability

### 🐛 Bug Fixes

#### Zone Initialization
- Fixed sealed zone initialization
- Corrected zone state tracking for unopened zones
- Better handling of zone configuration from panel
- Improved zone name persistence

#### Switch Platform
- Fixed switch entity creation issues
- Improved output detection from multiple sources
- Better coordinator data initialization
- Enhanced retry mechanism for switch setup

#### Device Info
- Consistent device identifiers across all platforms
- Proper device grouping in Home Assistant
- Firmware version tracking in device info
- Better device attribute updates

#### Connection Management
- Improved reconnection logic with exponential backoff
- Better error handling during connection loss
- Enhanced connection state reporting
- More reliable status updates

#### Area Detection
- Fixed manual area configuration
- Better fallback from auto-detection to manual
- Improved area panel creation logic
- Consistent area numbering

### 🔧 Improvements

#### Configuration Flow
- Enhanced zone and area configuration wizard
- Better error messages and validation
- Improved user guidance with emojis and formatting
- Clearer explanations for manual area configuration

#### Services
- More comprehensive service schemas
- Better parameter validation
- Enhanced service descriptions
- Improved error messages

#### Logging
- More detailed debug logging
- Better structured log messages
- Health metrics logging
- Connection state change logging

#### Code Quality
- Improved code organization
- Better type hints and documentation
- Enhanced error handling throughout
- More consistent naming conventions

### 📚 Documentation

- Complete README overhaul for v2.0.0
- New CHANGELOG for version tracking
- Enhanced service documentation
- More automation examples
- Improved troubleshooting guide

### ⚠️ Breaking Changes

1. **ESX Support Removed**: ESX Elite-SX panels are no longer supported in this version. If you need ESX support, use version 1.x or the ESX-specific branch.

2. **Area Configuration**: Areas are now manually configured during setup (auto-detection unreliable). You must specify which areas are active.

3. **Entity IDs**: Area panel entities now have different naming scheme (e.g., `alarm_control_panel.arrowhead_eci_area_1`).

4. **Configuration Format**: Some configuration options have changed. Existing installations may need reconfiguration.

### 🔄 Migration Guide

#### From Version 1.x to 2.0.0

1. **ESX Users**: Do not upgrade if you have ESX panels. Stay on v1.x or use ESX branch.

2. **ECi Users**:
   - Backup your configuration
   - Remove the old integration
   - Install v2.0.0
   - Reconfigure with manual area specification
   - Update automations to use new entity IDs

3. **Automation Updates**:
   - Update entity IDs for area panels
   - Review new services for better functionality
   - Update zone entity references if needed

### 🧪 Testing

- Tested on ECi F/W Ver. 10.3.51 (MODE 4 fully functional)
- Tested on ECi F/W Ver. 10.3.50 (MODE 4 supported)
- Tested with 1-3 areas configured
- Tested with up to 248 zones
- Tested with output expanders (up to 32 outputs)

---

## [1.0.0] - 2024-06-03 (Original Release)

### Initial Release Features

- Support for Arrowhead ESX Elite-SX panels
- Support for Arrowhead ECi Series panels
- Basic arm/disarm functionality
- Zone monitoring and bypass
- Output control
- System status monitoring
- HACS integration
- Configuration flow
- Service definitions
- Basic area support

---

## Legend

- 🎯 Major Changes
- ✨ Added Features
- 🐛 Bug Fixes
- 🔧 Improvements
- 📚 Documentation
- ⚠️ Breaking Changes
- 🔄 Migration Guide
- 🧪 Testing
