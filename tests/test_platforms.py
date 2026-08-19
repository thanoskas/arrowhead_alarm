"""Tests for representative ECi platform entities."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from custom_components.arrowhead_alarm.alarm_control_panel import ArrowheadECiAlarmControlPanel
from custom_components.arrowhead_alarm.binary_sensor import ArrowheadZoneSensor
from custom_components.arrowhead_alarm.const import PANEL_CONFIG


@pytest.fixture
def config_entry(mock_config_entry_obj):
    return mock_config_entry_obj


@pytest.fixture
def alarm_panel(mock_coordinator, config_entry):
    return ArrowheadECiAlarmControlPanel(
        mock_coordinator,
        config_entry,
        PANEL_CONFIG,
        {"version": "10.3.51", "protocol_mode": 4, "mode_4_active": True},
    )


def test_alarm_panel_has_eci_identity(alarm_panel):
    assert alarm_panel._attr_name == "Arrowhead ECi Series"
    assert alarm_panel._attr_unique_id.endswith("_alarm_panel")
    assert alarm_panel._attr_code_disarm_required is True


def test_alarm_panel_reports_disarmed(alarm_panel, mock_coordinator):
    mock_coordinator.data = {"armed": False, "alarm": False, "arming": False}

    assert alarm_panel.alarm_state == AlarmControlPanelState.DISARMED


@pytest.mark.asyncio
async def test_alarm_panel_arm_away_delegates(alarm_panel, mock_coordinator):
    alarm_panel._update_arming_state = lambda state: None
    alarm_panel.async_write_ha_state = lambda: None
    mock_coordinator.client.send_main_panel_armaway = AsyncMock(return_value=True)
    await alarm_panel.async_alarm_arm_away()

    mock_coordinator.client.send_main_panel_armaway.assert_awaited_once()


@pytest.fixture
def zone_sensor(mock_coordinator, config_entry):
    return ArrowheadZoneSensor(mock_coordinator, config_entry, PANEL_CONFIG, 1, "state")


def test_zone_sensor_uses_eci_zone_defaults(zone_sensor):
    assert zone_sensor._attr_device_class == BinarySensorDeviceClass.OPENING
    assert "Zone 001" in zone_sensor._attr_name


def test_zone_sensor_reads_zone_state(zone_sensor, mock_coordinator):
    mock_coordinator.data = {"zones": {1: True}}

    assert zone_sensor.is_on is True
