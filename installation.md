# Installation Guide

This guide provides detailed instructions for installing the Arrowhead Alarm Panel integration.

## Prerequisites

Before installing, ensure you meet the following requirements:

### Home Assistant Requirements
- **Home Assistant version**: 2024.4.0 or newer
- **Installation type**: Home Assistant OS, Supervised, Container, or Core
- **Network access**: Ability to reach your alarm panel via TCP/IP

### Panel Requirements
- **Supported panels**: ESX Elite-SX or ECi Series
- **Network connectivity**: Panel must be connected to your network
- **TCP interface**: Panel's TCP interface must be enabled
- **User credentials**: Valid username/password and user PIN

## Installation Methods

### Method 1: HACS Installation (Recommended)

HACS (Home Assistant Community Store) provides the easiest installation and update experience.

#### Step 1: Install HACS
If you don't have HACS installed:
1. Follow the [HACS installation guide](https://hacs.xyz/docs/setup/download)
2. Restart Home Assistant
3. Add the HACS integration via Settings → Devices & Services

#### Step 2: Add Custom Repository
1. Open HACS in Home Assistant
2. Click on **"Integrations"**
3. Click the **three dots menu (⋮)** in the top right corner
4. Select **"Custom repositories"**
5. Add the repository:
   - **Repository URL**: `https://github.com/thanoskas/arrowhead_alarm`
   - **Category**: `Integration`
6. Click **"Add"**

#### Step 3: Install Integration
1. In HACS, search for **"Arrowhead Alarm Panel"**
2. Click on the integration
3. Click **"Download"**
4. Select the latest version
5. **Restart Home Assistant**

#### Step 4: Add Integration
1. Go to **Settings → Devices & Services**
2. Click **"Add Integration"** 
3. Search for **"Arrowhead Alarm Panel"**
4. Follow the configuration wizard

### Method 2: Manual Installation

For users who prefer manual installation or don't use HACS.

#### Step 1: Download Files
```bash
# Using wget
wget https://github.com/thanoskas/arrowhead_alarm/archive/main.zip
unzip main.zip

# Using git
git clone https://github.com/thanoskas/arrowhead_alarm.git
```

#### Step 2: Copy Integration Files
```bash
# Create custom_components directory if it doesn't exist
mkdir -p /config/custom_components

# Copy the integration
cp -r arrowhead_alarm-main/custom_components/arrowhead_alarm /config/custom_components/

# Verify files are in place
ls -la /config/custom_components/arrowhead_alarm/
```

#### Step 3: Restart Home Assistant
Restart Home Assistant to load the new integration.

#### Step 4: Add Integration
1. Go to **Settings → Devices & Services**
2. Click **"Add Integration"**
3. Search for **"Arrowhead Alarm Panel"**
4. Follow the configuration wizard

### Method 3: Git Submodule (Advanced)

For developers or users who want to track development versions.

```bash
cd /config
git submodule add https://github.com/thanoskas/arrowhead_alarm.git custom_components/arrowhead_alarm
```

## Configuration Wizard

The integration includes a comprehensive configuration wizard that guides you through setup:

### Step 1: Panel Type Selection
Choose your alarm panel type:
- **ESX Elite-SX**: Traditional panels with up to 32 zones
- **ECi Series**: Advanced panels with up to 248 zones

### Step 2: Connection Configuration
Enter your panel's network information:

| Field | Description | Example |
|-------|-------------|---------|
| **IP Address** | Panel's IP address | `192.168.1.100` |
| **Port** | TCP port (usually 9000) | `9000` |
| **User PIN** | Format: "user pin" | `"1 123"` |
| **Username** | Admin username | `admin` |
| **Password** | Admin password | `admin` |

### Step 3: Zone Configuration (ECi Only)
For ECi panels, configure zone detection:

- **Auto-detect zones**: Recommended for most setups
- **Manual configuration**: Override detected settings
- **Zone naming**: Customize zone names (optional)

### Step 4: Output Configuration
Specify how many outputs to control:
- **ESX panels**: Usually 4-16 outputs
- **ECi panels**: Usually 4-32 outputs

## Post-Installation Setup

### Verify Installation

1. **Check Integration Status**:
   - Go to Settings → Devices & Services
   - Find "Arrowhead Alarm Panel"
   - Status should be "Connected"

2. **Check Entities**:
   - Go to Settings → Devices & Services → Arrowhead Alarm Panel
   - Verify all expected entities are created
   - Check entity states are updating

3. **Test Basic Functions**:
   - Try arming/disarming the system
   - Check zone sensors respond to physical zone activity
   - Test output controls (if safe to do so)

### Configure Zone Names

If you didn't customize zone names during setup:

1. Go to **Settings → Devices & Services**
2. Find **"Arrowhead Alarm Panel"**
3. Click **"Configure"**
4. Enable **"Configure zone names"**
5. Set friendly names like "Front Door", "Kitchen Window", etc.

### Set Up Automations

Create basic automations for your security system:

```yaml
# Example: Arm system when leaving
automation:
  - alias: "Auto Arm Away"
    trigger:
      - platform: zone
        entity_id: device_tracker.phone
        zone: home
        event: leave
    action:
      - service: arrowhead_alarm.arm_away

# Example: Notification on alarm
  - alias: "Alarm Notification" 
    trigger:
      - platform: state
        entity_id: alarm_control_panel.arrowhead_esx_elite_sx
        to: 'triggered'
    action:
      - service: notify.mobile_app
        data:
          title: "🚨 Security Alert"
          message: "Alarm system triggered!"
```

## Troubleshooting Installation

### Common Issues

#### Integration Not Found
**Problem**: "Arrowhead Alarm Panel" doesn't appear in integrations list

**Solutions**:
- Verify files are in `/config/custom_components/arrowhead_alarm/`
- Check file permissions are correct
- Restart Home Assistant completely
- Clear browser cache (Ctrl+F5)

#### Connection Failed
**Problem**: Cannot connect to panel during setup

**Solutions**:
- Verify panel IP address is correct
- Check port number (usually 9000)
- Ensure panel TCP interface is enabled
- Test network connectivity: `ping [panel-ip]`
- Check firewall settings

#### Authentication Failed
**Problem**: Authentication fails during setup

**Solutions**:
- Verify username/password combination
- Check User PIN format: `"1 123"` not `"1123"`
- Try different user accounts on panel
- Ensure user has sufficient privileges

#### Missing Entities
**Problem**: Expected entities not created

**Solutions**:
- Check integration logs for errors
- Verify panel configuration
- Try reconfiguring with different settings
- Enable debug logging for details

### Debug Logging

Enable detailed logging for troubleshooting:

```yaml
# configuration.yaml
logger:
  default: warning
  logs:
    custom_components.arrowhead_alarm: debug
```

Then restart Home Assistant and reproduce the issue. Check logs at **Settings → System → Logs**.

### Getting Help

If you encounter issues:

1. **Check Documentation**: Review README.md and this installation guide
2. **Search Issues**: Check [existing GitHub issues](https://github.com/thanoskas/arrowhead_alarm/issues)
3. **Enable Debug Logging**: Collect detailed logs
4. **Create Issue**: Provide full details including logs and configuration

## Updating

### HACS Updates
1. HACS will notify you of updates
2. Click **"Update"** in HACS
3. Restart Home Assistant

### Manual Updates
1. Download latest release
2. Replace files in `/config/custom_components/arrowhead_alarm/`
3. Restart Home Assistant

## Uninstallation

### Remove Integration
1. Go to **Settings → Devices & Services**
2. Find **"Arrowhead Alarm Panel"**
3. Click **three dots menu → Delete**
4. Confirm deletion

### Remove Files
```bash
# Remove integration files
rm -rf /config/custom_components/arrowhead_alarm/

# Remove from HACS (if installed via HACS)
# Go to HACS → Integrations → Arrowhead Alarm Panel → Remove
```

## Advanced Configuration

### Multiple Panels
To connect multiple panels:
1. Complete setup for first panel
2. Add integration again with different configuration
3. Each panel will have separate entities

### Custom Network Configuration
For complex network setups:
- Ensure proper routing between Home Assistant and panel
- Configure firewall rules for TCP port access
- Consider VPN setup for remote access

### Performance Tuning
Optimize for your environment:
- Adjust scan interval in integration options
- Configure timeouts based on network latency
- Monitor resource usage and adjust accordingly

---

## Support

For additional help:
- **Documentation**: [Main README](README.md)
- **Issues**: [GitHub Issues](https://github.com/thanoskas/arrowhead_alarm/issues)
- **Discussions**: [GitHub Discussions](https://github.com/thanoskas/arrowhead_alarm/discussions)