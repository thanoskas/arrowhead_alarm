Arrowhead Alarm Panel Integration for Home Assistant
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


Advanced Home Assistant integration for Arrowhead Alarm Panel systems with comprehensive zone detection and panel-specific optimizations.



<div align="center">
  <p><strong>Integration implemented by <a href="https://smarthomehellas.gr">smarthomehellas.gr</a> supported by <a href="https://iascom.gr">iascom.gr</a></strong> - <strong>Exclusive Greek Arrowhead Distributor</strong></p>
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/smarthomehellas_logo.png" alt="Smart Home Hellas" width="120">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/iascom_logo.png" alt="Iascom" width="120">
</div>

## Overview

This integration provides complete Home Assistant support for Arrowhead Alarm Panel systems, featuring advanced zone detection and panel-specific optimizations.

### Supported Panel Series

#### 🔹 ECi Series
<div align="center">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/eci_panel.jpg" alt="ECi Series Panel" width="300">
</div>

**Key Specifications:**
- Up to 248 zones
- 32 outputs
- Dynamic zone detection
- Multiple area support
- Zone expander compatibility

#### 🔹 ESX Elite-SX Series
<div align="center">
  <img src="https://github.com/thanoskas/arrowhead_alarm/raw/main/docs/images/esx_panel.jpg" alt="ESX Elite-SX Panel" width="300">
</div>

**Key Specifications:**
- Up to 32 zones
- 16 outputs
- RF supervision support
- Dual area configuration
- Tamper detection
## Key Features

### 🏠 Comprehensive Device Support

- **Alarm Control Panel** - Arm/disarm with away and stay modes
- **Zone Monitoring** - Individual sensors for zone state, alarms, troubles, and bypass status
- **System Status** - AC power, battery, phone line, and RF supervision monitoring
- **Output Control** - Switches and services for panel outputs (lights, sirens, etc.)
- **Zone Bypass** - Individual bypass buttons and bulk bypass services

### 🔧 Advanced Configuration

- **Auto-Detection** - Automatic discovery of zones and areas (ECi panels)
- **Panel-Specific Optimization** - Tailored communication protocols for each panel type
- **Manual Configuration** - Override detection with custom zone counts and names
- **Version Detection** - Automatic protocol adaptation based on firmware version

### 🛡️ Robust Operation

- **Connection Management** - Automatic reconnection with exponential backoff
- **Error Recovery** - Comprehensive error handling and status reporting
- **Performance Optimization** - Panel-specific timing and protocol selection

## Installation

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

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=thanoskas&repository=arrowhead_alarm&category=integration)

### Manual Installation

1. **Download Files**:

   ```bash
   wget https://github.com/thanoskas/arrowhead_alarm/archive/main.zip
   unzip main.zip
   ```

2. **Copy Integration**:

   ```bash
   cp -r arrowhead_alarm-main/custom_components/arrowhead_alarm /config/custom_components/
   ```

3. **Restart Home Assistant** and add the integration through the UI.

## Configuration

### Quick Setup

The integration uses a **guided configuration wizard** that automatically detects your panel type and capabilities:

1. **Panel Type Selection** - Choose ESX Elite-SX or ECi Series
2. **Connection Setup** - Enter IP address, port, and credentials
3. **Zone Configuration** - Auto-detect or manually configure zones (ECi only)
4. **Output Setup** - Specify number of outputs to control
5. **Optional Zone Naming** - Customize zone names for easy identification

### Configuration Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| **Host** | IP address of alarm panel | - | Yes |
| **Port** | TCP port for communication | 9000 | No |
| **User PIN** | User number and PIN code | "1 123" | Yes |
| **Username** | Admin username | "admin" | No |
| **Password** | Admin password | "admin" | No |
| **Panel Type** | ESX or ECi | ESX | Yes |
| **Max Outputs** | Number of outputs to control | 4 | No |

#### User PIN Format

The User PIN should be formatted as: `[User Number] [PIN Code]`

- Example: `"1 123"` for User 1 with PIN 123
- Example: `"2 456"` for User 2 with PIN 456

### Panel-Specific Configuration

#### ESX Elite-SX

- **Zones**: 1-32 (fixed configuration)
- **Outputs**: 1-16 with expander support
- **Features**: RF supervision, dual areas, tamper detection

#### ECi Series

- **Zones**: 1-248 with auto-detection
- **Outputs**: 1-32 with expander support
- **Features**: Multiple areas, zone expanders, advanced detection

## Entities Created

### Alarm Control Panel

- **Arrowhead [Panel Type]** - Main alarm panel entity
  - States: Disarmed, Armed Away, Armed Home, Pending, Triggered
  - Attributes: Zone status, system health, detection info

### Binary Sensors

#### Zone Sensors (per configured zone)

- **Zone [XXX]** - Zone open/closed state
- **Zone [XXX] Alarm** - Zone alarm condition
- **Zone [XXX] Trouble** - Zone trouble condition
- **Zone [XXX] Bypassed** - Zone bypass status
- **Zone [XXX] RF Supervision** - RF supervision status (if supported)

#### System Sensors

- **[Panel] AC Power** - Mains power status
- **[Panel] Battery** - Battery status
- **[Panel] Ready to Arm** - System ready state
- **[Panel] Phone Line** - Phone line status
- **[Panel] Dialer** - Dialer status
- **[Panel] Fuse/Output** - Fuse and output status
- **[Panel] Panel Tamper** - Tamper alarm status
- **[Panel] RF Receiver** - RF receiver status (if supported)

### Switches

- **Output [X]** - Control panel outputs (lights, sirens, etc.)

### Buttons

- **Zone [XXX] Bypass** - Toggle zone bypass status

## Services

### Alarm Control

```yaml
# Arm system in away mode
service: arrowhead_alarm.arm_away

# Arm system in stay/home mode  
service: arrowhead_alarm.arm_stay

# Disarm system
service: arrowhead_alarm.disarm
```

### Output Control

```yaml
# Trigger output for specified duration
service: arrowhead_alarm.trigger_output
data:
  output_number: 1
  duration: 5  # seconds (0 = momentary)

# Turn output on permanently
service: arrowhead_alarm.turn_output_on
data:
  output_number: 1

# Turn output off
service: arrowhead_alarm.turn_output_off  
data:
  output_number: 1
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

# Bulk zone bypass/unbypass
service: arrowhead_alarm.bulk_bypass
data:
  zones: [1, 2, 3, 4]
  action: bypass  # or "unbypass"
```

## Automation Examples

### Basic Alarm Control

```yaml
# Arm system when leaving home
automation:
  - alias: "Arm Alarm When Away"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone
        zone: home
        event: leave
    action:
      - service: arrowhead_alarm.arm_away

# Disarm when arriving home  
  - alias: "Disarm When Home"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone  
        zone: home
        event: enter
    action:
      - service: arrowhead_alarm.disarm
```

### Zone-Based Automations

```yaml
# Turn on lights when front door opens
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

# Notification for zone alarms
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

### Output Control

```yaml
# Flash lights on alarm
automation:
  - alias: "Alarm Lights"
    trigger:
      - platform: state
        entity_id: alarm_control_panel.arrowhead_esx_elite_sx
        to: 'triggered'
    action:
      # Trigger strobe output
      - service: arrowhead_alarm.trigger_output
        data:
          output_number: 2
          duration: 30
```

### Advanced Zone Management

```yaml
# Auto-bypass zones based on conditions
automation:
  - alias: "Bypass Garage When Door Open"
    trigger:
      - platform: state
        entity_id: binary_sensor.garage_door
        to: 'on'
    action:
      - service: arrowhead_alarm.bypass_zone
        data:
          zone_number: 6  # Garage zone
          
  - alias: "Restore Garage Bypass"  
    trigger:
      - platform: state
        entity_id: binary_sensor.garage_door
        to: 'off'
        for: "00:05:00"  # 5 minutes closed
    action:
      - service: arrowhead_alarm.unbypass_zone
        data:
          zone_number: 6
```

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to panel  
**Solutions**:

- Verify IP address and port number
- Check network connectivity to panel
- Ensure panel's TCP interface is enabled
- Try default credentials (admin/admin)

**Problem**: Authentication failed  
**Solutions**:

- Verify username/password combination
- Check User PIN format: `"[user] [pin]"`
- Ensure user has sufficient privileges
- Try different user accounts on panel

### Zone Detection Issues (ECi)

**Problem**: Zones not detected automatically  
**Solutions**:

- Disable auto-detection and set zones manually
- Check that zones are properly configured in panel
- Verify areas are active in panel configuration
- Use manual configuration override

**Problem**: Wrong number of zones detected  
**Solutions**:

- Override max zones in integration options
- Check panel configuration for actual zones
- Verify expander modules are properly configured

### Performance Issues

**Problem**: Slow response or timeouts  
**Solutions**:

- Increase scan interval in integration options
- Check network latency to panel
- Verify panel isn't overloaded with connections
- Consider panel firmware updates

### Debug Logging

Enable debug logging for detailed troubleshooting:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.arrowhead_alarm: debug
```

## Advanced Configuration

### Custom Zone Names

Zone names can be customized during setup or in integration options:

```yaml
# Example custom zone names
Zone 001: "Front Door"
Zone 002: "Kitchen Window"  
Zone 003: "Living Room Motion"
Zone 004: "Basement Door"
Zone 005: "Garage Motion"
```

### Multiple Panel Support

Each panel requires a separate integration instance:

1. Add first panel through normal setup
2. Add additional panels via "Add Integration"
3. Use different IP addresses for each panel
4. Entities will be named with panel-specific identifiers

### Home Assistant Brands

This integration is registered with Home Assistant Brands for consistent UI appearance. The panel icon and manufacturer information are automatically configured.

## Supported Panel Models

### ESX Elite-SX Series

- **ESX-1** (Not tested but should work)

### ECi Series

- **ECi - Pro**


## Contributing

Contributions are welcome! Please read the [contributing guidelines](CONTRIBUTING.md) before submitting PRs.

### Development Setup

```bash
# Clone repository
git clone https://github.com/thanoskas/arrowhead_alarm.git
cd arrowhead_alarm

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Run linting
pre-commit run --all-files
```

### Reporting Issues

When reporting issues, please include:

- Home Assistant version
- Integration version
- Panel model and firmware version
- Debug logs (with sensitive info removed)
- Steps to reproduce the issue

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Arrowhead Alarm Products for panel documentation
- Home Assistant community for guidance and testing
- HACS for streamlined custom component distribution

## Support

- **Issues**: [GitHub Issues](https://github.com/thanoskas/arrowhead_alarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thanoskas/arrowhead_alarm/discussions)
- **Community**: [Home Assistant Community](https://community.home-assistant.io/)

---

**⭐ If this integration helps you secure your home, please consider starring the repository!**

☕ Support My Work
If you find this project helpful and want to support my work, feel free to donate via PayPal:

https://paypal.me/thanoskasolas

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


