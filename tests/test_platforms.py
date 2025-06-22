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
        await alarm_panel.async_alarm_arm_home