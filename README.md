<div align="center">
<h1 style="font-size: 3em; margin: 0.5em 0;">Arrowhead Alarm Panel Integration for Home Assistant</h1>
</div>

<div align="center">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/arrowhead_logo.png" alt="Arrowhead Alarm Products" width="200">
</div>

<div align="center">

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]][license]
[![HACS][hacs-shield]][hacs]
[![Community Forum][forum-shield]][forum]

</div>

<div align="center">
<strong>Advanced Home Assistant integration for Arrowhead ECi Series alarm panels with MODE 4 protocol support, comprehensive zone detection, and individual area management.</strong>
</div>

<div align="center">
<h3>📢 Important Version Notice</h3>
<p><strong>Version 2.0.1+</strong>: ECi Series only (MODE 4 support, enhanced features)</p>
<p><strong>Version 1.x</strong>: <a href="https://github.com/thanoskas/arrowhead_alarm/tree/v1.0.0">ESX Elite-SX support available here</a></p>
</div>

<div align="center">
  <p><strong>Integration implemented by <a href="https://smarthomehellas.gr">smarthomehellas.gr</a> supported by <a href="https://iascom.gr">iascom.gr</a></strong> - <strong>Exclusive Greek Arrowhead Distributor</strong></p>
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/smarthomehellas_logo.png" alt="Smart Home Hellas" width="120">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/iascom_logo.png" alt="Iascom" width="120">
</div>

---
## 🎉 What's New in Version 2.1.0

FULL Individual Area Arm/Stay/Disarm support


EntityARM AwayARM StayDISARMMain PanelARMAWAY(all areas)ARMSTAY(all areas)DISARM user# pin(MODE 4, all areas)Area 1ARMAREA 1(MODE 4, area 1 only)STAYAREA 1(MODE 4, area 1 only)DISARM 1 pin(MODE 2, area 1 only)Area 2ARMAREA 2(MODE 4, area 2 only)STAYAREA 2(MODE 4, area 2 only)DISARM 2 pin(MODE 2, area 2 only)Area 3ARMAREA 3(MODE 4, area 3 only)STAYAREA 3(MODE 4, area 3 only)DISARM 3 pin(MODE 2, area 3 only)

## 🎉 What's New in Version 2.0.1

<div align="center">
<table>
<tr>
<th>Feature</th>
<th>Version 1.x</th>
<th>Version 2.0.1</th>
</tr>
<tr>
<td><strong>Panel Support</strong></td>
<td>ESX + ECi</td>
<td>ECi Only</td>
</tr>
<tr>
<td><strong>MODE 4 Protocol</strong></td>
<td>❌ Not Available</td>
<td>✅ Full Support</td>
</tr>
<tr>
<td><strong>Individual Area Panels</strong></td>
<td>❌ Single Panel Only</td>
<td>✅ Per-Area Control</td>
</tr>
<tr>
<td><strong>Keypad Alarms</strong></td>
<td>❌ Not Available</td>
<td>✅ Panic/Fire/Medical</td>
</tr>
<tr>
<td><strong>Bulk Operations</strong></td>
<td>❌ Limited</td>
<td>✅ Full Support</td>
</tr>
<tr>
<td><strong>Sealed Zone Support</strong></td>
<td>⚠️ Basic</td>
<td>✅ Enhanced</td>
</tr>
</table>
</div>

### 🚀 Major Changes

- **🎯 ECi-Only Focus**: Streamlined exclusively for ECi Series panels
- **🚀 MODE 4 Support**: Full support for firmware 10.3.50+ enhanced features
- **🏠 Individual Area Panels**: Separate alarm panel entity for each configured area
- **⚡ Enhanced Services**: 36+ services including bulk operations and keypad alarms
- **🔍 Improved Detection**: Better zone detection with sealed zone support
- **🐛 Bug Fixes**: Numerous fixes for stability and reliability
- **📊 Better Monitoring**: Health tracking and improved diagnostics

### 📦 Migration from v1.x

**For ECi Users:**
1. ✅ Backup your current configuration
2. ✅ Remove v1.x integration
3. ✅ Install v2.0.1
4. ✅ Reconfigure with manual area specification
5. ✅ Update automations with new entity IDs

**For ESX Users:**
- ❌ Stay on [v1.x](https://github.com/thanoskas/arrowhead_alarm/tree/v1.0.0) - ESX support removed in v2.0.1

> **Breaking Change**: Version 2.0.1 only supports ECi Series panels. ESX Elite-SX users should continue using version 1.x.

---

## ⚠️ Panel Configuration Required

Before installing the Home Assistant integration, you **must** configure your Arrowhead ECi panel with the following settings:

### Network Settings (P201E4E)

- Enable **Serial Over IP** - This is required for TCP/IP communication with Home Assistant

### Serial Port Options (P25E19-21E)

- Enable **Serial Authorization** in Option C under the options tab
- This setting is essential for the integration to authenticate with the panel

### Configuration Steps

1. **Access Panel Programming Mode**
   - Enter installer/programming mode on your panel
   - Navigate to the network and serial port settings

2. **Configure Network Settings**
   - Go to P201E4E (Network Settings)
   - Enable Serial Over IP functionality
   - Note the IP address and port (default: 9000)

3. **Configure Serial Authorization**
   - Navigate to P25E19-21E (Serial Port Options)
   - Select Option C under the options tab
   - Enable Serial Authorization

4. **Save Configuration**
   - Save all changes and exit programming mode
   - The panel may require a restart to apply network settings

> **Note**: Without these panel configurations, the Home Assistant integration will not be able to establish communication with your alarm system.

---

## Overview

This integration provides complete Home Assistant support for **Arrowhead ECi Series** alarm panels, featuring MODE 4 protocol support, advanced zone detection, and individual area management.

### 🔹 Supported Panel: ECi Series

<div align="center">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/eci_panel.jpg" alt="ECi Series Panel" width="300">
</div>

**Key Specifications:**
- Up to 248 zones
- 32 outputs  
- Dynamic zone detection
- Multiple area support (up to 32 areas)
- Zone expander compatibility
- MODE 4 protocol (firmware 10.3.50+)

**Compatible Firmware:**
- ✅ ECi F/W Ver. 10.3.51 (MODE 4 fully functional)
- ✅ ECi F/W Ver. 10.3.50 (MODE 4 supported)
- ✅ Earlier firmware versions (MODE 1 fallback)

---

## 🎯 Key Features

### 🏠 Comprehensive Device Support

- **Main Alarm Control Panel** - Controls all areas together
- **Individual Area Panels** - Separate panel entity for each configured area
- **Zone Monitoring** - Individual sensors for zone state, alarms, troubles, and bypass
- **System Status** - AC power, battery, phone line, and system health monitoring
- **Output Control** - Switches for panel outputs (lights, sirens, automation)
- **Zone Bypass** - Individual bypass buttons and bulk bypass services

### 🚀 MODE 4 Enhanced Features (Firmware 10.3.50+)

- **Keypad Alarms** - Trigger panic, fire, and medical alarms
- **Enhanced Area Commands** - ARMAREA and STAYAREA for better area control
- **User Tracking** - See which user armed/disarmed each area
- **Enhanced Timing** - Precise entry/exit delay information
- **Programming Queries** - Access panel configuration programmatically

### 🔧 Advanced Configuration

- **Auto Zone Detection** - Automatic discovery of configured zones
- **Manual Area Config** - User-specified areas for maximum reliability
- **Custom Zone Names** - Personalize zone names during setup or later
- **Output Detection** - Automatic or manual output configuration
- **Protocol Adaptation** - Automatic selection of best protocol for your firmware

### 🛡️ Robust Operation

- **Connection Management** - Automatic reconnection with exponential backoff
- **Error Recovery** - Comprehensive error handling and status reporting
- **Health Monitoring** - Track connection quality and success rates
- **Performance Optimization** - Panel-specific timing and protocol selection

---

## ⚠️ Panel Configuration Required

Before installing the Home Assistant integration, you **must** configure your Arrowhead ECi panel with the following settings:

### Network Settings (P201E4E)

1. Access panel programming mode
2. Navigate to **P201E4E** (Network Settings)
3. Enable **Serial Over IP** functionality
4. Note the IP address and port (default: 9000)

### Serial Port Options (P25E19-21E)

1. Navigate to **P25E19-21E** (Serial Port Options)
2. Go to the **Options** tab
3. Select **Option C**
4. Enable **Serial Authorization**

> **Important**: Without these settings, the integration cannot communicate with your panel!

---

## 📥 Installation

### HACS Installation (Recommended)

1. **Add Custom Repository**:
   - Open HACS in Home Assistant
   - Click on "Integrations"
   - Click the three dots menu (⋮) in the top right
   - Select "Custom repositories"
   - Add repository URL: `https://github.com/thanoskas/arrowhead_alarm`
   - Select category: "Integration"
   - Click "Add"

2. **Install Integration**:
   - Find "Arrowhead Alarm Panel" in HACS
   - Click "Download"
   - Restart Home Assistant

3. **Add Integration**:
   - Go to Settings → Devices & Services
   - Click "Add Integration"
   - Search for "Arrowhead Alarm Panel"
   - Follow the configuration wizard

<div align="center">

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thanoskas&repository=arrowhead_alarm&category=integration)

</div>

### Manual Installation

1. **Download Files**:
   ```bash
   wget https://github.com/thanoskas/arrowhead_alarm/archive/refs/tags/v2.0.1.zip
   unzip v2.0.1.zip
   ```

2. **Copy Integration**:
   ```bash
   cp -r arrowhead_alarm-2.0.1/custom_components/arrowhead_alarm /config/custom_components/
   ```

3. **Restart Home Assistant** and add the integration through the UI.

---

## ⚙️ Configuration

### Quick Setup Wizard

The integration uses a **guided configuration wizard** with the following steps:

1. **Connection Setup** - Enter IP address, port, and credentials
2. **Zone Configuration** - Auto-detect zones or set manually
3. **Area Configuration** - Specify which areas are active (manual, required)
4. **Zone Naming** - Optionally customize zone names
5. **Output Setup** - Specify number of outputs to control

### Configuration Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| **Host** | IP address of ECi panel | - | Yes |
| **Port** | TCP port for communication | 9000 | No |
| **User PIN** | User number and PIN code | "1 123" | Yes |
| **Username** | Admin username | "admin" | No |
| **Password** | Admin password | "admin" | No |
| **Areas** | Active areas (comma-separated) | "1" | Yes |
| **Max Outputs** | Number of outputs to control | 4 | No |

#### User PIN Format

The User PIN should be formatted as: `[User Number] [PIN Code]`

- ✅ Correct: `"1 123"` (user 1 with PIN 123)
- ✅ Correct: `"2 456"` (user 2 with PIN 456)
- ❌ Wrong: `"123"` or `"1123"`

#### Areas Configuration

Areas must be manually specified as comma-separated numbers:

- Single area: `"1"`
- Multiple areas: `"1,2,3"`
- Valid range: 1-32

> **Why Manual?** Area auto-detection can be unreliable. You know your system best!

---

## 🎛️ Entities Created

### Alarm Control Panels

- **Arrowhead ECi Series** - Main panel controlling all areas
- **Arrowhead ECi Series Area 1** - Individual control for area 1
- **Arrowhead ECi Series Area 2** - Individual control for area 2
- *(Additional area panels for each configured area)*

Each panel provides:
- States: Disarmed, Armed Away, Armed Home, Pending, Triggered
- Attributes: Zone status, system health, area information

### Binary Sensors

#### Zone Sensors (per configured zone)

- **Zone [XXX]** - Zone open/closed state
- **Zone [XXX] Alarm** - Zone alarm condition
- **Zone [XXX] Trouble** - Zone trouble/fault condition
- **Zone [XXX] Bypassed** - Zone bypass status

#### System Sensors

- **ECi AC Power** - Mains power status
- **ECi Battery** - Battery status
- **ECi Ready to Arm** - System ready state
- **ECi Phone Line** - Phone line status
- **ECi Dialer** - Dialer status
- **ECi Fuse/Output** - Fuse and output status
- **ECi Panel Tamper** - Tamper alarm status

### Switches

- **Output 1-32** - Control panel outputs (based on configuration)

### Buttons

- **Zone [XXX] Bypass** - Toggle zone bypass for each zone

---

## 🎮 Services

### Main Panel Control

```yaml
# Arm all areas in away mode
service: arrowhead_alarm.arm_away

# Arm all areas in stay/home mode  
service: arrowhead_alarm.arm_stay

# Disarm all areas
service: arrowhead_alarm.disarm
data:
  user_code: "1 123"  # Optional override
```

### Area-Specific Control

```yaml
# Arm specific area in away mode
service: arrowhead_alarm.arm_away_area
data:
  area: 2
  user_code: "1 123"  # Optional
  use_mode_4: true    # Use MODE 4 if available

# Arm specific area in stay mode
service: arrowhead_alarm.arm_stay_area
data:
  area: 1
  use_mode_4: true

# Disarm specific area
service: arrowhead_alarm.disarm_area
data:
  area: 2
  user_code: "1 123"
```

### Keypad Alarms (MODE 4 Only)

```yaml
# Trigger keypad-based alarm
service: arrowhead_alarm.trigger_keypad_alarm
data:
  alarm_type: panic  # panic, fire, or medical
```

### Bulk Operations

```yaml
# Arm multiple areas at once
service: arrowhead_alarm.bulk_arm_areas
data:
  areas: [1, 2, 3]
  mode: away  # away, stay, or home
  delay: 1    # seconds between commands

# Disarm multiple areas
service: arrowhead_alarm.bulk_disarm_areas
data:
  areas: [1, 2]
  delay: 1

# Bulk zone bypass
service: arrowhead_alarm.bulk_bypass
data:
  zones: [1, 2, 3, 5]
  action: bypass  # or "unbypass"
```

### Output Control

```yaml
# Trigger output for duration
service: arrowhead_alarm.trigger_output
data:
  output_number: 1
  duration: 5  # seconds (0 = momentary)

# Turn output on permanently
service: arrowhead_alarm.turn_output_on
data:
  output_number: 2

# Turn output off
service: arrowhead_alarm.turn_output_off  
data:
  output_number: 2
```

### Zone Management

```yaml
# Bypass single zone
service: arrowhead_alarm.bypass_zone
data:
  zone_number: 1

# Remove zone bypass
service: arrowhead_alarm.unbypass_zone
data:
  zone_number: 1
```

---

## 🤖 Automation Examples

### Basic Alarm Control

```yaml
# Arm when leaving home
automation:
  - alias: "Arm Alarm When Away"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone
        zone: home
        event: leave
    action:
      - service: arrowhead_alarm.arm_away

# Disarm when arriving
  - alias: "Disarm When Home"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone  
        zone: home
        event: enter
    action:
      - service: arrowhead_alarm.disarm
```

### Area-Specific Arming

```yaml
# Arm ground floor at night
automation:
  - alias: "Arm Ground Floor Night"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: arrowhead_alarm.arm_stay_area
        data:
          area: 1
          use_mode_4: true
```

### Zone-Based Automations

```yaml
# Light when door opens
automation:
  - alias: "Front Door Light"
    trigger:
      - platform: state
        entity_id: binary_sensor.zone_001
        to: 'on'
    condition:
      - condition: sun
        after: sunset
    action:
      - service: light.turn_on
        entity_id: light.front_porch

# Notification for alarms
  - alias: "Zone Alarm Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.zone_001_alarm
        to: 'on'
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Security Alert"
          message: "Front Door alarm!"
```

### Smart Zone Bypass

```yaml
# Auto-bypass garage when door open
automation:
  - alias: "Bypass Garage Door Zone"
    trigger:
      - platform: state
        entity_id: binary_sensor.garage_door
        to: 'on'
    action:
      - service: arrowhead_alarm.bypass_zone
        data:
          zone_number: 6
          
  - alias: "Restore Garage Bypass"  
    trigger:
      - platform: state
        entity_id: binary_sensor.garage_door
        to: 'off'
        for: "00:05:00"
    action:
      - service: arrowhead_alarm.unbypass_zone
        data:
          zone_number: 6
```

---

## 🔧 Troubleshooting

### Connection Issues

**Problem**: Cannot connect to panel  
**Solutions**:
- ✅ Verify IP address and port (default: 9000)
- ✅ Check network connectivity
- ✅ Ensure Serial Over IP is enabled (P201E4E)
- ✅ Verify Serial Authorization enabled (P25E19-21E Option C)

**Problem**: Authentication failed  
**Solutions**:
- ✅ Check User PIN format: `"1 123"` (with space!)
- ✅ Verify username/password (default: admin/admin)
- ✅ Ensure Serial Authorization is enabled
- ✅ Try different user account

### Zone Detection Issues

**Problem**: Zones not detected  
**Solutions**:
- ✅ Check zones are configured in panel
- ✅ Verify areas are active
- ✅ Try manual zone configuration
- ✅ Review P4075Ex responses in debug logs

**Problem**: Wrong zone count  
**Solutions**:
- ✅ Override max zones in options
- ✅ Check expander configuration
- ✅ Verify zone programming

### MODE 4 Issues

**Problem**: MODE 4 features not working  
**Solutions**:
- ✅ Verify firmware is 10.3.50 or later
- ✅ Check debug logs for MODE 4 activation
- ✅ Ensure areas configured at P74E/P76E (if using ARMAREA/STAYAREA)

### Performance Issues

**Problem**: Slow or timeouts  
**Solutions**:
- ✅ Increase scan interval in options
- ✅ Check network latency
- ✅ Verify panel not overloaded
- ✅ Consider firmware update

### Debug Logging

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.arrowhead_alarm: debug
```

---

## 🎨 Advanced Configuration

### Custom Zone Names

Customize during setup or in integration options:

```yaml
Zone 001: "Front Door"
Zone 002: "Kitchen Window"  
Zone 003: "Living Room Motion"
Zone 004: "Basement Door"
Zone 005: "Garage Motion"
```

### Multiple Panels

Each panel needs a separate integration instance:
1. Add first panel normally
2. Add additional via "Add Integration"
3. Use different IP addresses
4. Entities get panel-specific names

---

## 📚 Supported Panel Models

### ECi Series (Version 2.0.1+)

<div align="center">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/eci_panel.jpg" alt="ECi Series Panel" width="300">
</div>

- **ECi Pro** - ✅ Fully tested and supported
- **ECi Standard** - ✅ Compatible
- Other ECi variants - ⚠️ Should work (feedback welcome)

**Firmware Compatibility:**
- ✅ ECi F/W Ver. 10.3.51 (MODE 4 fully functional)
- ✅ ECi F/W Ver. 10.3.50 (MODE 4 supported)
- ✅ Earlier firmware versions (MODE 1 fallback)

### ESX Elite-SX Series (Version 1.x Only)

<div align="center">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/esx_panel.jpg" alt="ESX Elite-SX Panel" width="300">
</div>

> **⚠️ ESX Support**: ESX Elite-SX panels are supported in [version 1.x](https://github.com/thanoskas/arrowhead_alarm/tree/v1.0.0). Please use v1.x if you have an ESX panel.

**ESX Features (in v1.x):**
- Up to 32 zones
- 16 outputs
- RF supervision support
- Dual area configuration
- Tamper detection

**To install v1.x for ESX panels:**
```bash
# Download v1.x release
wget https://github.com/thanoskas/arrowhead_alarm/archive/refs/tags/v1.0.0.zip
```

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
git clone https://github.com/thanoskas/arrowhead_alarm.git
cd arrowhead_alarm
pip install -r requirements-dev.txt
pytest tests/
```

### Reporting Issues

Please include:
- Home Assistant version
- Integration version (2.0.1)
- ECi firmware version
- Debug logs (sanitized)
- Steps to reproduce

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- **Arrowhead Alarm Products** - Panel documentation and support
- **Home Assistant Community** - Testing and feedback
- **HACS** - Distribution platform
- **[Iascom.gr](https://iascom.gr)** - Greek Arrowhead distributor

---

## 🆘 Support & Community

- **Issues**: [GitHub Issues](https://github.com/thanoskas/arrowhead_alarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thanoskas/arrowhead_alarm/discussions)
- **Community**: [Home Assistant Forum](https://community.home-assistant.io/)
- **Website**: [Smart Home Hellas](https://smarthomehellas.gr)

---

<div align="center">
<strong>⭐ If this integration helps you secure your home, please star the repository!</strong>
</div>

<div align="center">
<strong>☕ Support Development</strong><br>
If you find this project helpful:<br><br>
<a href="https://paypal.me/thanoskasolas"><img src="https://img.shields.io/badge/PayPal-Donate-blue.svg?style=for-the-badge" alt="PayPal Donate"></a>
</div>

---

<div align="center">
<sub>Made with ❤️ by <a href="https://smarthomehellas.gr">Smart Home Hellas</a></sub>
</div>

<!-- Badge URLs -->
[releases-shield]: https://img.shields.io/github/release/thanoskas/arrowhead_alarm.svg?style=for-the-badge
[releases]: https://github.com/thanoskas/arrowhead_alarm/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/thanoskas/arrowhead_alarm.svg?style=for-the-badge
[commits]: https://github.com/thanoskas/arrowhead_alarm/commits/main
[license-shield]: https://img.shields.io/github/license/thanoskas/arrowhead_alarm.svg?style=for-the-badge
[license]: https://github.com/thanoskas/arrowhead_alarm/blob/main/LICENSE
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
