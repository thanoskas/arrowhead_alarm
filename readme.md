# Arrowhead Alarm Panel - Home Assistant Integration

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

Advanced Home Assistant integration for **Arrowhead ECi Series** alarm panels with comprehensive zone detection, area management, and MODE 4 protocol support.

**Integration developed by [Smart Home Hellas](https://smarthomehellas.gr)**  
**Supported by [Iascom.gr](https://iascom.gr) - Exclusive Greek Arrowhead Distributor**

---

## ✨ What's New in Version 2.0.0

### 🎯 Major Changes
- **ECi-Only Focus**: Streamlined for ECi Series panels (ESX support moved to separate branch)
- **MODE 4 Protocol Support**: Full support for firmware 10.3.50+ enhanced features
- **Individual Area Panels**: Separate alarm panel entities for each configured area
- **Improved Zone Detection**: Enhanced automatic zone detection with sealed zone support
- **Better Output Management**: Improved output switch creation and state tracking

### 🚀 New Features
- **Keypad Alarms**: Trigger panic, fire, and medical alarms (MODE 4)
- **Enhanced Area Commands**: ARMAREA and STAYAREA commands for better area control
- **User Tracking**: Track which user armed/disarmed each area
- **Bulk Operations**: Arm/disarm multiple areas or zones at once
- **Health Monitoring**: Comprehensive health checks and diagnostics
- **Connection Management**: Improved reconnection logic with exponential backoff

### 🐛 Bug Fixes
- Fixed zone initialization for sealed zones
- Improved switch platform entity creation
- Better device info consistency across platforms
- Enhanced error handling and logging

---

## 🔧 Panel Compatibility

### Supported Panel
- **Arrowhead ECi Series**
  - Up to 248 zones
  - Up to 32 outputs  
  - Up to 32 areas
  - Firmware versions: All (enhanced features require 10.3.50+)

### Tested Firmware Versions
- ✅ ECi F/W Ver. 10.3.51 (MODE 4 fully tested)
- ✅ ECi F/W Ver. 10.3.50 (MODE 4 supported)
- ✅ Earlier versions (MODE 1 fallback)

---

## 📋 Features

### Panel Control
- ✅ Arm/Disarm (Away, Stay, Home modes)
- ✅ Individual area control
- ✅ Bulk area operations
- ✅ Force arm with bypassed zones
- ✅ Emergency disarm

### Zone Management
- ✅ Automatic zone detection from panel configuration
- ✅ Zone state monitoring (open/closed)
- ✅ Zone alarm detection
- ✅ Zone trouble monitoring
- ✅ Zone bypass control (individual and bulk)
- ✅ Custom zone naming
- ✅ Sealed zone support

### System Monitoring
- ✅ AC power status
- ✅ Battery status
- ✅ Ready to arm status
- ✅ Phone line monitoring
- ✅ Dialer status
- ✅ Fuse/output monitoring
- ✅ Panel tamper detection

### Output Control
- ✅ Individual output switches
- ✅ Timed output triggering
- ✅ Permanent on/off control
- ✅ Up to 32 outputs supported

### MODE 4 Features (Firmware 10.3.50+)
- ✅ Keypad alarm triggering (panic, fire, medical)
- ✅ Enhanced area commands (ARMAREA, STAYAREA)
- ✅ User tracking for arm/disarm actions
- ✅ Enhanced entry/exit delay reporting
- ✅ Programming location queries

---

## 🔌 Installation

### Method 1: HACS (Recommended)

1. **Add Custom Repository**:
   - Open HACS in Home Assistant
   - Click "Integrations"
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

### Method 2: Manual Installation

1. **Download Files**:
   ```bash
   cd /config
   wget https://github.com/thanoskas/arrowhead_alarm/archive/refs/tags/v2.0.0.zip
   unzip v2.0.0.zip
   ```

2. **Copy Integration**:
   ```bash
   cp -r arrowhead_alarm-2.0.0/custom_components/arrowhead_alarm /config/custom_components/
   ```

3. **Restart Home Assistant** and add the integration through the UI.

---

## ⚙️ Panel Configuration

### Required Panel Settings

Before configuring the integration, you must enable network communication on your ECi panel:

#### Network Settings (P201E4E)
1. Access panel programming mode
2. Navigate to **P201E4E** (Network Settings)
3. Enable **Serial Over IP**
4. Note the panel's IP address and port (default: 9000)

#### Serial Authorization (P25E19-21E)
1. Navigate to **P25E19-21E** (Serial Port Options)
2. Go to the **Options** tab
3. Select **Option C**
4. Enable **Serial Authorization**

⚠️ **Important**: Without these settings, the integration cannot communicate with your panel.

---

## 🎛️ Configuration

### Initial Setup

The integration uses a guided setup wizard:

#### Step 1: Connection Details
- **IP Address**: Your panel's IP address
- **Port**: TCP port (default: 9000)
- **User PIN**: Format: `USER PIN` (e.g., `1 123`)
- **Username**: Admin username (typically `admin`)
- **Password**: Admin password (typically `admin`)

#### Step 2: Zone and Area Configuration
- **Auto-detect Zones**: ✅ Recommended - automatically discovers zones
- **Maximum Zones**: Override if needed (8-248)
- **Active Areas**: **Required** - Specify which areas to monitor (e.g., `1,2,3`)
- **Configure Zone Names**: Optional - customize zone names

💡 **Why Manual Areas?** Area auto-detection can be unreliable. You know your system best!

#### Step 3: Zone Naming (Optional)
- Customize names for each detected zone
- Examples: "Front Door", "Kitchen Window", "Garage Motion"
- Can be changed later in Settings → Integrations → Configure

#### Step 4: Output Configuration
- Specify number of outputs (1-32)
- Default: 4 (standard ECi panel)
- Increase if you have output expanders

---

## 🏠 Entities Created

### Main Entities

#### Alarm Control Panel
- **Main Panel**: Controls all areas
- **Area Panels**: Individual panel for each configured area (e.g., "ECi Area 1", "ECi Area 2")

#### Binary Sensors (per zone)
- **Zone State**: Open/Closed status
- **Zone Alarm**: Alarm condition
- **Zone Trouble**: Trouble/fault condition
- **Zone Bypassed**: Bypass status

#### System Binary Sensors
- **AC Power**: Mains power status
- **Battery**: Battery status
- **Ready to Arm**: System ready state
- **Phone Line**: Phone line status
- **Dialer**: Dialer status
- **Fuse/Output**: Fuse and output status
- **Panel Tamper**: Tamper alarm status

#### Switches (per output)
- **Output 1-32**: Control panel outputs

#### Buttons (per zone)
- **Zone Bypass**: Toggle zone bypass

---

## 🎮 Services

### Panel Control

#### `arrowhead_alarm.arm_away`
Arm all areas in away mode.

```yaml
service: arrowhead_alarm.arm_away
data:
  user_code: "1 123"  # Optional override
```

#### `arrowhead_alarm.arm_stay`
Arm all areas in stay/home mode.

```yaml
service: arrowhead_alarm.arm_stay
data:
  user_code: "1 123"  # Optional override
```

#### `arrowhead_alarm.disarm`
Disarm all areas.

```yaml
service: arrowhead_alarm.disarm
data:
  user_code: "1 123"  # Optional override
```

### Area-Specific Control

#### `arrowhead_alarm.arm_away_area`
Arm specific area in away mode (uses MODE 4 ARMAREA if available).

```yaml
service: arrowhead_alarm.arm_away_area
data:
  area: 1
  user_code: "1 123"  # Optional
  use_mode_4: true    # Use enhanced MODE 4 command
```

#### `arrowhead_alarm.arm_stay_area`
Arm specific area in stay mode (uses MODE 4 STAYAREA if available).

```yaml
service: arrowhead_alarm.arm_stay_area
data:
  area: 2
  use_mode_4: true
```

#### `arrowhead_alarm.disarm_area`
Disarm specific area.

```yaml
service: arrowhead_alarm.disarm_area
data:
  area: 1
```

### Keypad Alarms (MODE 4 Only)

#### `arrowhead_alarm.trigger_keypad_alarm`
Trigger keypad-based alarm (requires firmware 10.3.50+).

```yaml
service: arrowhead_alarm.trigger_keypad_alarm
data:
  alarm_type: panic  # panic, fire, or medical
```

### Zone Control

#### `arrowhead_alarm.bypass_zone`
Bypass a single zone.

```yaml
service: arrowhead_alarm.bypass_zone
data:
  zone_number: 5
```

#### `arrowhead_alarm.bulk_bypass`
Bypass or unbypass multiple zones.

```yaml
service: arrowhead_alarm.bulk_bypass
data:
  zones: [1, 2, 3, 5]
  action: bypass  # or "unbypass"
```

### Output Control

#### `arrowhead_alarm.trigger_output`
Trigger output for specified duration.

```yaml
service: arrowhead_alarm.trigger_output
data:
  output_number: 1
  duration: 5  # seconds (0 = momentary)
```

#### `arrowhead_alarm.turn_output_on`
Turn output on permanently.

```yaml
service: arrowhead_alarm.turn_output_on
data:
  output_number: 2
```

### Bulk Operations

#### `arrowhead_alarm.bulk_arm_areas`
Arm multiple areas at once.

```yaml
service: arrowhead_alarm.bulk_arm_areas
data:
  areas: [1, 2, 3]
  mode: away  # away, stay, or home
  delay: 1    # seconds between commands
  use_mode_4: true
```

#### `arrowhead_alarm.bulk_disarm_areas`
Disarm multiple areas at once.

```yaml
service: arrowhead_alarm.bulk_disarm_areas
data:
  areas: [1, 2, 3]
  delay: 1
```

### Advanced

#### `arrowhead_alarm.send_custom_command`
Send custom command to panel (advanced users).

```yaml
service: arrowhead_alarm.send_custom_command
data:
  command: "ARMAREA 2"
  expect_response: false
```

---

## 📱 Automation Examples

### Arm When Leaving Home
```yaml
automation:
  - alias: "Arm Alarm When Away"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone
        zone: home
        event: leave
    action:
      - service: arrowhead_alarm.arm_away
```

### Disarm When Arriving
```yaml
automation:
  - alias: "Disarm When Home"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone
        zone: home
        event: enter
    action:
      - service: arrowhead_alarm.disarm
```

### Light Control on Zone Open
```yaml
automation:
  - alias: "Front Door Light"
    trigger:
      - platform: state
        entity_id: binary_sensor.zone_001  # Front Door
        to: 'on'
    condition:
      - condition: sun
        after: sunset
    action:
      - service: light.turn_on
        entity_id: light.front_porch
```

### Zone Alarm Notification
```yaml
automation:
  - alias: "Zone Alarm Alert"
    trigger:
      - platform: state
        entity_id: binary_sensor.zone_001_alarm
        to: 'on'
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Security Alert"
          message: "Front Door alarm triggered!"
```

### Area-Specific Night Arming
```yaml
automation:
  - alias: "Arm Ground Floor at Night"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: arrowhead_alarm.arm_stay_area
        data:
          area: 1
          use_mode_4: true
```

---

## 🔧 Troubleshooting

### Connection Issues

**Problem**: Cannot connect to panel

**Solutions**:
- ✅ Verify IP address and port number
- ✅ Check network connectivity to panel
- ✅ Ensure panel's TCP interface is enabled (P201E4E)
- ✅ Verify Serial Authorization is enabled (P25E19-21E)
- ✅ Check firewall settings

### Authentication Failed

**Problem**: Authentication errors

**Solutions**:
- ✅ Verify username/password combination
- ✅ Check User PIN format: `"USER PIN"` (e.g., `"1 123"`)
- ✅ Ensure user has sufficient privileges
- ✅ Try default credentials (admin/admin)

### Zone Detection Issues

**Problem**: Zones not detected or wrong count

**Solutions**:
- ✅ Ensure zones are properly configured in panel
- ✅ Check that areas are active in panel configuration
- ✅ Try manual override in integration options
- ✅ Review P4075Ex responses in debug logs

### Slow Response

**Problem**: Slow or timeout issues

**Solutions**:
- ✅ Increase scan interval in options
- ✅ Check network latency to panel
- ✅ Verify panel isn't overloaded with connections
- ✅ Consider firmware update

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.arrowhead_alarm: debug
```

---

## 🔐 Security Considerations

- Store User PINs securely
- Use strong admin passwords
- Limit network access to panel
- Enable panel tamper detection
- Regularly review alarm logs
- Keep firmware updated

---

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/thanoskas/arrowhead_alarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thanoskas/arrowhead_alarm/discussions)
- **Community**: [Home Assistant Community](https://community.home-assistant.io/)
- **Smart Home Hellas**: [Website](https://smarthomehellas.gr)

---

## 💝 Support the Project

If you find this integration helpful and want to support development:

[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue.svg)](https://paypal.me/thanoskasolas)

Your support helps maintain and improve this integration!

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Credits

- **Developer**: [Thanos Kasolas](https://github.com/thanoskas) - [Smart Home Hellas](https://smarthomehellas.gr)
- **Panel Support**: [Iascom.gr](https://iascom.gr) - Exclusive Greek Arrowhead Distributor
- **Community**: Home Assistant community for testing and feedback
- **Arrowhead Alarm Products**: For panel documentation and support

---

## 📚 Additional Resources

- [Arrowhead Alarm Products](http://www.arrowheadalarm.com/) - Official panel documentation
- [Home Assistant](https://www.home-assistant.io/) - Home automation platform
- [HACS](https://hacs.xyz/) - Home Assistant Community Store

---

**Version**: 2.0.0  
**Last Updated**: December 2024  
**Compatibility**: Home Assistant 2023.1+
