"""Test the Arrowhead Alarm Panel platforms."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.switch import SwitchDeviceClass

from custom_components.arrowhead_alarm.const import DOMAIN, PANEL_TYPE_ESX
from custom_components.arrowhead_alarm.alarm_control_panel import ArrowheadAlarmControlPanel
from custom_components.arrowhead_alarm.binary_sensor import ArrowheadZoneSensor, ArrowheadSystemSensor
from custom_components.arrowhead_alarm.switch import ArrowheadOutputSwitch
from custom_components.arrowhead_alarm.button import ArrowheadZoneBypassButton


class TestAlarmControlPanel:
    """Test the alarm control panel platform."""

    @pytest.fixture
    def alarm_panel(self, mock_coordinator, mock_config_entry_obj):
        """Create an alarm control panel entity."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        return ArrowheadAlarmControlPanel(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config
        )

    def test_alarm_panel_initialization(self, alarm_panel, mock_config_entry_obj):
        """Test alarm panel initialization."""
        assert alarm_panel._config_entry == mock_config_entry_obj
        assert "Arrowhead ESX Elite-SX" in alarm_panel._attr_name
        assert alarm_panel._attr_unique_id == f"{mock_config_entry_obj.entry_id}_alarm_panel"
        assert alarm_panel._attr_code_arm_required is False

    def test_alarm_state_disarmed(self, alarm_panel, mock_coordinator):
        """Test alarm state when disarmed."""
        mock_coordinator.data = {
            "armed": False,
            "arming": False,
            "alarm": False
        }
        
        assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED

    def test_alarm_state_armed_away(self, alarm_panel, mock_coordinator):
        """Test alarm state when armed away."""
        mock_coordinator.data = {
            "armed": True,
            "stay_mode": False,
            "arming": False,
            "alarm": False
        }
        
        assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_AWAY

    def test_alarm_state_armed_home(self, alarm_panel, mock_coordinator):
        """Test alarm state when armed home."""
        mock_coordinator.data = {
            "armed": True,
            "stay_mode": True,
            "arming": False,
            "alarm": False
        }
        
        assert alarm_panel.alarm_state == AlarmControlPanelState.ARMED_HOME

    def test_alarm_state_pending(self, alarm_panel, mock_coordinator):
        """Test alarm state when pending."""
        mock_coordinator.data = {
            "armed": False,
            "arming": True,
            "alarm": False
        }
        
        assert alarm_panel.alarm_state == AlarmControlPanelState.PENDING

    def test_alarm_state_triggered(self, alarm_panel, mock_coordinator):
        """Test alarm state when triggered."""
        mock_coordinator.data = {
            "armed": True,
            "alarm": True,
            "arming": False
        }
        
        assert alarm_panel.alarm_state == AlarmControlPanelState.TRIGGERED

    def test_alarm_state_no_data(self, alarm_panel, mock_coordinator):
        """Test alarm state with no coordinator data."""
        mock_coordinator.data = None
        
        assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED

    def test_extra_state_attributes(self, alarm_panel, mock_coordinator, mock_panel_status):
        """Test extra state attributes."""
        mock_coordinator.data = mock_panel_status
        
        attributes = alarm_panel.extra_state_attributes
        
        assert "ready_to_arm" in attributes
        assert "mains_power" in attributes
        assert "battery_status" in attributes
        assert "active_zones" in attributes
        assert "alarm_zones" in attributes
        assert "active_outputs" in attributes
        assert "total_zones_configured" in attributes
        assert "total_outputs_configured" in attributes

    def test_extra_state_attributes_with_zones(self, alarm_panel, mock_coordinator):
        """Test extra state attributes with zone data."""
        mock_coordinator.data = {
            "zones": {1: True, 2: False, 3: True},
            "zone_alarms": {1: False, 2: True, 3: False},
            "outputs": {1: False, 2: True},
            "ready_to_arm": True,
            "mains_ok": True,
            "battery_ok": True,
            "panel_type": PANEL_TYPE_ESX
        }
        
        attributes = alarm_panel.extra_state_attributes
        
        assert attributes["active_zones"] == [1, 3]
        assert attributes["alarm_zones"] == [2]
        assert attributes["active_outputs"] == [2]
        assert attributes["total_zones_configured"] == 3
        assert attributes["total_outputs_configured"] == 2

    def test_available_when_connected(self, alarm_panel, mock_coordinator):
        """Test availability when connected."""
        mock_coordinator.last_update_success = True
        mock_coordinator.data = {"connection_state": "connected"}
        
        assert alarm_panel.available is True

    def test_not_available_when_disconnected(self, alarm_panel, mock_coordinator):
        """Test availability when disconnected."""
        mock_coordinator.last_update_success = False
        mock_coordinator.data = {"connection_state": "disconnected"}
        
        assert alarm_panel.available is False

    async def test_async_alarm_disarm(self, alarm_panel, mock_coordinator):
        """Test disarm command."""
        await alarm_panel.async_alarm_disarm()
        
        mock_coordinator.async_disarm.assert_called_once()

    async def test_async_alarm_arm_away(self, alarm_panel, mock_coordinator):
        """Test arm away command."""
        await alarm_panel.async_alarm_arm_away()
        
        mock_coordinator.async_arm_away.assert_called_once()

    async def test_async_alarm_arm_home(self, alarm_panel, mock_coordinator):
        """Test arm home command."""
        await alarm_panel.async_alarm_arm_home()
        
        mock_coordinator.async_arm_stay.assert_called_once()


class TestZoneBinarySensor:
    """Test zone binary sensor platform."""

    @pytest.fixture
    def zone_sensor(self, mock_coordinator, mock_config_entry_obj):
        """Create a zone sensor entity."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        return ArrowheadZoneSensor(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config,
            1,  # zone_id
            "state"  # sensor_type
        )

    def test_zone_sensor_initialization(self, zone_sensor, mock_config_entry_obj):
        """Test zone sensor initialization."""
        assert zone_sensor._zone_id == 1
        assert zone_sensor._sensor_type == "state"
        assert "Zone 001" in zone_sensor._attr_name
        assert zone_sensor._attr_device_class == BinarySensorDeviceClass.OPENING

    def test_zone_sensor_state_on(self, zone_sensor, mock_coordinator):
        """Test zone sensor state when on."""
        mock_coordinator.data = {
            "zones": {1: True, 2: False}
        }
        
        assert zone_sensor.is_on is True

    def test_zone_sensor_state_off(self, zone_sensor, mock_coordinator):
        """Test zone sensor state when off."""
        mock_coordinator.data = {
            "zones": {1: False, 2: False}
        }
        
        assert zone_sensor.is_on is False

    def test_zone_sensor_no_data(self, zone_sensor, mock_coordinator):
        """Test zone sensor with no data."""
        mock_coordinator.data = None
        
        assert zone_sensor.is_on is None

    def test_zone_sensor_extra_attributes(self, zone_sensor, mock_coordinator):
        """Test zone sensor extra attributes."""
        mock_coordinator.data = {
            "zones": {1: True},
            "zone_alarms": {1: False},
            "zone_troubles": {1: False},
            "zone_bypassed": {1: False}
        }
        
        attributes = zone_sensor.extra_state_attributes
        
        assert attributes["zone_id"] == 1
        assert attributes["sensor_type"] == "state"
        assert "zone_configured" in attributes

    def test_zone_sensor_alarm_type(self, mock_coordinator, mock_config_entry_obj):
        """Test zone alarm sensor."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        alarm_sensor = ArrowheadZoneSensor(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config,
            1,
            "alarm"
        )
        
        assert alarm_sensor._sensor_type == "alarm"
        assert alarm_sensor._attr_device_class == BinarySensorDeviceClass.SAFETY
        assert "Zone 001 Alarm" in alarm_sensor._attr_name


class TestSystemBinarySensor:
    """Test system binary sensor platform."""

    @pytest.fixture
    def system_sensor(self, mock_coordinator, mock_config_entry_obj):
        """Create a system sensor entity."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        return ArrowheadSystemSensor(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config,
            "mains_ok",
            "AC Power"
        )

    def test_system_sensor_initialization(self, system_sensor):
        """Test system sensor initialization."""
        assert system_sensor._status_key == "mains_ok"
        assert system_sensor._friendly_name == "AC Power"
        assert "AC Power" in system_sensor._attr_name
        assert system_sensor._attr_device_class == BinarySensorDeviceClass.PROBLEM

    def test_system_sensor_ok_status(self, system_sensor, mock_coordinator):
        """Test system sensor with OK status (inverted for 'ok' sensors)."""
        mock_coordinator.data = {
            "mains_ok": True
        }
        
        # For 'ok' sensors, is_on should be False when status is True (no problem)
        assert system_sensor.is_on is False

    def test_system_sensor_problem_status(self, system_sensor, mock_coordinator):
        """Test system sensor with problem status."""
        mock_coordinator.data = {
            "mains_ok": False
        }
        
        # For 'ok' sensors, is_on should be True when status is False (problem)
        assert system_sensor.is_on is True

    def test_system_sensor_alarm_type(self, mock_coordinator, mock_config_entry_obj):
        """Test alarm type system sensor."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        alarm_sensor = ArrowheadSystemSensor(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config,
            "tamper_alarm",
            "Panel Tamper"
        )
        
        mock_coordinator.data = {
            "tamper_alarm": True
        }
        
        # For alarm sensors, is_on should match the value directly
        assert alarm_sensor.is_on is True


class TestOutputSwitch:
    """Test output switch platform."""

    @pytest.fixture
    def output_switch(self, mock_coordinator, mock_config_entry_obj):
        """Create an output switch entity."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        return ArrowheadOutputSwitch(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config,
            1  # output_id
        )

    def test_output_switch_initialization(self, output_switch, mock_config_entry_obj):
        """Test output switch initialization."""
        assert output_switch._output_id == 1
        assert "Output 1" in output_switch._attr_name
        assert output_switch._attr_device_class == SwitchDeviceClass.SWITCH
        assert output_switch._attr_unique_id == f"{mock_config_entry_obj.entry_id}_output_1"

    def test_output_switch_on_state(self, output_switch, mock_coordinator):
        """Test output switch on state."""
        mock_coordinator.data = {
            "outputs": {1: True, 2: False}
        }
        
        assert output_switch.is_on is True

    def test_output_switch_off_state(self, output_switch, mock_coordinator):
        """Test output switch off state."""
        mock_coordinator.data = {
            "outputs": {1: False, 2: False}
        }
        
        assert output_switch.is_on is False

    def test_output_switch_no_data(self, output_switch, mock_coordinator):
        """Test output switch with no data."""
        mock_coordinator.data = None
        
        assert output_switch.is_on is False

    def test_output_switch_availability(self, output_switch, mock_coordinator):
        """Test output switch availability."""
        mock_coordinator.last_update_success = True
        mock_coordinator.data = {
            "outputs": {1: False}
        }
        
        assert output_switch.available is True

    def test_output_switch_not_available(self, output_switch, mock_coordinator):
        """Test output switch not available."""
        mock_coordinator.last_update_success = False
        mock_coordinator.data = None
        
        assert output_switch.available is False

    async def test_output_switch_turn_on(self, output_switch, mock_coordinator):
        """Test output switch turn on."""
        await output_switch.async_turn_on(duration=5)
        
        mock_coordinator.async_trigger_output.assert_called_once_with(1, 5)

    async def test_output_switch_turn_on_default(self, output_switch, mock_coordinator):
        """Test output switch turn on with default duration."""
        await output_switch.async_turn_on()
        
        mock_coordinator.async_trigger_output.assert_called_once_with(1, 5)

    async def test_output_switch_turn_off(self, output_switch, mock_coordinator):
        """Test output switch turn off."""
        await output_switch.async_turn_off()
        
        # Turn off is typically a no-op for momentary outputs
        # Just verify no errors occur


class TestZoneBypassButton:
    """Test zone bypass button platform."""

    @pytest.fixture
    def bypass_button(self, mock_coordinator, mock_config_entry_obj):
        """Create a zone bypass button entity."""
        from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
        panel_config = PANEL_CONFIGS[PANEL_TYPE_ESX]
        
        return ArrowheadZoneBypassButton(
            mock_coordinator,
            mock_config_entry_obj,
            panel_config,
            1  # zone_id
        )

    def test_bypass_button_initialization(self, bypass_button, mock_config_entry_obj):
        """Test bypass button initialization."""
        assert bypass_button._zone_id == 1
        assert "Zone 001 Bypass" in bypass_button._attr_name
        assert bypass_button._attr_unique_id == f"{mock_config_entry_obj.entry_id}_zone_1_bypass_button"

    def test_bypass_button_icon_not_bypassed(self, bypass_button, mock_coordinator):
        """Test bypass button icon when not bypassed."""
        mock_coordinator.data = {
            "zone_bypassed": {1: False}
        }
        
        assert bypass_button.icon == "mdi:shield-off-outline"

    def test_bypass_button_icon_bypassed(self, bypass_button, mock_coordinator):
        """Test bypass button icon when bypassed."""
        mock_coordinator.data = {
            "zone_bypassed": {1: True}
        }
        
        assert bypass_button.icon == "mdi:shield-off"

    def test_bypass_button_availability(self, bypass_button, mock_coordinator):
        """Test bypass button availability."""
        mock_coordinator.last_update_success = True
        mock_coordinator.data = {"connection_state": "connected"}
        
        assert bypass_button.available is True

    def test_bypass_button_extra_attributes(self, bypass_button, mock_coordinator):
        """Test bypass button extra attributes."""
        mock_coordinator.data = {
            "zone_bypassed": {1: False},
            "zones": {1: True},
            "zone_alarms": {1: False},
            "zone_troubles": {1: False}
        }
        
        attributes = bypass_button.extra_state_attributes
        
        assert attributes["zone_id"] == 1
        assert attributes["currently_bypassed"] is False
        assert attributes["zone_open"] is True
        assert "bypass_status" in attributes

    async def test_bypass_button_press_to_bypass(self, bypass_button, mock_coordinator):
        """Test bypass button press to add bypass."""
        mock_coordinator.data = {
            "zone_bypassed": {1: False}
        }
        
        await bypass_button.async_press()
        
        mock_coordinator.async_bypass_zone.assert_called_once_with(1)

    async def test_bypass_button_press_to_unbypass(self, bypass_button, mock_coordinator):
        """Test bypass button press to remove bypass."""
        mock_coordinator.data = {
            "zone_bypassed": {1: True}
        }
        
        await bypass_button.async_press()
        
        mock_coordinator.async_unbypass_zone.assert_called_once_with(1)

    async def test_bypass_button_press_no_data(self, bypass_button, mock_coordinator):
        """Test bypass button press with no data."""
        mock_coordinator.data = None
        
        await bypass_button.async_press()
        
        # Should not call any coordinator methods
        mock_coordinator.async_bypass_zone.assert_not_called()
        mock_coordinator.async_unbypass_zone.assert_not_called()


class TestPlatformSetup:
    """Test platform setup functions."""

    @pytest.fixture
    def mock_add_entities(self):
        """Mock the add entities callback."""
        return AsyncMock()

    async def test_alarm_control_panel_setup(self, hass: HomeAssistant, mock_config_entry_obj, mock_add_entities, mock_hass_data):
        """Test alarm control panel platform setup."""
        hass.data = mock_hass_data
        
        from custom_components.arrowhead_alarm.alarm_control_panel import async_setup_entry
        
        await async_setup_entry(hass, mock_config_entry_obj, mock_add_entities)
        
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        assert len(entities) == 1
        assert isinstance(entities[0], ArrowheadAlarmControlPanel)

    async def test_binary_sensor_setup(self, hass: HomeAssistant, mock_config_entry_obj, mock_add_entities, mock_hass_data):
        """Test binary sensor platform setup."""
        hass.data = mock_hass_data
        
        # Mock coordinator data with zones
        coordinator = hass.data[DOMAIN][mock_config_entry_obj.entry_id]["coordinator"]
        coordinator.data = {
            "zones": {1: False, 2: False},
            "connection_state": "connected"
        }
        
        from custom_components.arrowhead_alarm.binary_sensor import async_setup_entry
        
        await async_setup_entry(hass, mock_config_entry_obj, mock_add_entities)
        
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        # Should create multiple sensors per zone plus system sensors
        assert len(entities) > 10  # Zones + system sensors
        
        # Check we have zone sensors
        zone_sensors = [e for e in entities if isinstance(e, ArrowheadZoneSensor)]
        assert len(zone_sensors) > 0
        
        # Check we have system sensors
        system_sensors = [e for e in entities if isinstance(e, ArrowheadSystemSensor)]
        assert len(system_sensors) > 0

    async def test_switch_setup(self, hass: HomeAssistant, mock_config_entry_obj, mock_add_entities, mock_hass_data):
        """Test switch platform setup."""
        hass.data = mock_hass_data
        
        # Mock coordinator data with outputs
        coordinator = hass.data[DOMAIN][mock_config_entry_obj.entry_id]["coordinator"]
        coordinator.data = {
            "outputs": {1: False, 2: False, 3: False, 4: False},
            "connection_state": "connected"
        }
        
        from custom_components.arrowhead_alarm.switch import async_setup_entry
        
        await async_setup_entry(hass, mock_config_entry_obj, mock_add_entities)
        
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        assert len(entities) == 4  # 4 output switches
        assert all(isinstance(e, ArrowheadOutputSwitch) for e in entities)

    async def test_button_setup(self, hass: HomeAssistant, mock_config_entry_obj, mock_add_entities, mock_hass_data):
        """Test button platform setup."""
        hass.data = mock_hass_data
        
        # Mock coordinator data with zones
        coordinator = hass.data[DOMAIN][mock_config_entry_obj.entry_id]["coordinator"]
        coordinator.data = {
            "zones": {1: False, 2: False},
            "connection_state": "connected"
        }
        
        from custom_components.arrowhead_alarm.button import async_setup_entry
        
        await async_setup_entry(hass, mock_config_entry_obj, mock_add_entities)
        
        mock_add_entities.assert_called_once()
        entities = mock_add_entities.call_args[0][0]
        
        assert len(entities) == 2  # 2 bypass buttons
        assert all(isinstance(e, ArrowheadZoneBypassButton) for e in entities)