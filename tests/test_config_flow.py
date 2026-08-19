"""Tests for the ECi-only configuration flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.data_entry_flow import FlowResultType

from custom_components.arrowhead_alarm.config_flow import ArrowheadAlarmConfigFlow
from custom_components.arrowhead_alarm.const import (
    CONF_AREAS,
    CONF_MAX_ZONES,
    CONF_USER_PIN,
    DEFAULT_USER_PIN,
)


@pytest.fixture
def config_flow():
    return ArrowheadAlarmConfigFlow()


@pytest.mark.asyncio
async def test_user_step_is_connection_form(config_flow):
    result = await config_flow.async_step_user()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "host" in result["data_schema"].schema
    assert "panel_type" not in result["data_schema"].schema


def test_validate_areas_input_deduplicates_and_sorts(config_flow):
    result = config_flow._validate_areas_input("3, 1, 3")

    assert result == {"errors": {}, "areas": [1, 3]}


def test_validate_areas_input_rejects_out_of_range(config_flow):
    result = config_flow._validate_areas_input("33")

    assert "areas" in result["errors"]


@pytest.mark.asyncio
async def test_zone_config_form_uses_current_eci_fields(config_flow):
    result = await config_flow.async_step_zone_config()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "zone_config"
    assert CONF_MAX_ZONES in result["data_schema"].schema
    assert CONF_AREAS in result["data_schema"].schema


@pytest.mark.asyncio
async def test_zone_config_skips_optional_zone_names(config_flow):
    result = await config_flow.async_step_zone_config({
        "auto_detect_zones": True,
        "max_zones": 8,
        "areas": "1",
        "configure_zone_names": False,
    })

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "output_config"


@pytest.mark.asyncio
async def test_connection_test_uses_eci_client(config_flow):
    writer = MagicMock()
    writer.wait_closed = AsyncMock()
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.get_status = AsyncMock(return_value={"zones": {1: False}})
    client.disconnect = AsyncMock()

    with patch("asyncio.open_connection", return_value=(AsyncMock(), writer)), \
         patch("custom_components.arrowhead_alarm.config_flow.ArrowheadECiClient", return_value=client), \
         patch.object(config_flow, "_detect_firmware_fixed", new=AsyncMock(return_value={})), \
         patch.object(config_flow, "_detect_zones_fixed", new=AsyncMock(return_value={})): 
        result = await config_flow._test_connection_fixed({
            "host": "192.168.1.100",
            "port": 9000,
            CONF_USER_PIN: DEFAULT_USER_PIN,
            "username": "",
            "password": "",
        })

    assert result["success"] is True
    client.connect.assert_awaited_once()
