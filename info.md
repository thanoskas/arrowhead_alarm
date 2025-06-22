# Arrowhead Alarm Panel Integration

**Professional-grade Home Assistant integration for Arrowhead Alarm Panel systems**

## ✨ What Makes This Special

This integration provides **comprehensive support** for Arrowhead alarm panels with enterprise-level features:

### 🎯 **Smart Auto-Detection**
- Automatically discovers zones, areas, and expanders
- Panel-specific protocol optimization  
- Version detection and capability negotiation

### 🔒 **Complete Security Monitoring**
- Individual zone monitoring (state, alarm, trouble, bypass)
- System health monitoring (power, battery, communications)
- RF supervision for wireless zones (where supported)

### ⚡ **Advanced Control**
- Full alarm control (arm away, arm stay, disarm)
- Output control for lights, sirens, and automation
- Zone bypass management with bulk operations

### 🔧 **Robust Operation**
- Automatic reconnection with smart retry logic
- Connection state monitoring and reporting
- Comprehensive error handling and recovery

## 🏠 Supported Panels

| Panel Series | Max Zones | Max Outputs | Special Features |
|--------------|-----------|-------------|------------------|
| **ESX Elite-SX** | 32 | 16 | RF supervision, dual areas |
| **ECi Series** | 248 | 32 | Zone expanders, auto-detection |

## 🚀 Quick Start

1. **Install via HACS** (recommended) or manually
2. **Add Integration** through Home Assistant UI
3. **Follow the wizard** - it handles everything automatically
4. **Customize zones** with friendly names (optional)
5. **Start automating** your security system

## 📱 What You Get

### Entities Created
- **1 Alarm Control Panel** - Main system control
- **4-5 sensors per zone** - State, alarm, trouble, bypass, RF (if applicable)
- **6-8 system sensors** - Power, battery, communications, etc.
- **1 switch per output** - Control connected devices  
- **1 button per zone** - Quick bypass toggle

### Services Available
- `arm_away` / `arm_stay` / `disarm` - Alarm control
- `trigger_output` / `turn_output_on/off` - Device control
- `bypass_zone` / `unbypass_zone` / `bulk_bypass` - Zone management

## 🎛️ Configuration Made Easy

The integration features a **smart configuration wizard** that:

1. **Detects your panel type** automatically
2. **Tests connectivity** with helpful error messages  
3. **Discovers zones and areas** (ECi panels)
4. **Configures outputs** based on your needs
5. **Sets up custom zone names** (optional)

No complex YAML editing required!

## 🔧 Advanced Features

### ECi Auto-Detection
- Queries panel configuration via program locations
- Detects active areas and zone assignments
- Identifies expander modules automatically
- Provides fallback options for edge cases

### Connection Management  
- Smart reconnection with exponential backoff
- Connection state monitoring and reporting
- Protocol adaptation based on panel firmware
- Automatic keep-alive management

### Panel Optimization
- ESX-specific timing and message handling
- ECi protocol mode selection (Mode 1/4)
- Version-aware feature detection
- Hardware-specific communication patterns

## 📊 Rich Status Information

Each entity provides comprehensive attributes:

- **Zone sensors**: Current state, expander info, detection method
- **System sensors**: Communication stats, error counts, last update
- **Alarm panel**: Hardware summary, detection info, system status
- **Output switches**: Hardware location, detection method, capabilities

## 🔄 Seamless Updates

- **Automatic version detection** ensures compatibility
- **Incremental configuration updates** preserve your settings  
- **Backward compatibility** with existing installations
- **Migration assistance** for breaking changes

## 🛡️ Enterprise-Grade Reliability

- **Comprehensive error handling** with detailed logging
- **Graceful degradation** when features unavailable
- **Connection recovery** without manual intervention
- **Status reporting** for monitoring and diagnostics

## 🎨 Home Assistant Integration

- **Proper device grouping** - all entities under one device
- **Consistent naming** and icon selection
- **Rich attributes** for advanced automations
- **Service discovery** and documentation
- **Options flow** for runtime configuration changes

## 💡 Perfect For

- **Home security systems** with Arrowhead panels
- **Commercial installations** requiring monitoring
- **Smart home integration** with existing automation
- **Remote monitoring** and control applications
- **Security professionals** needing comprehensive access

---

**Ready to enhance your Home Assistant security monitoring?**

This integration transforms your Arrowhead alarm panel into a fully integrated part of your smart home ecosystem.