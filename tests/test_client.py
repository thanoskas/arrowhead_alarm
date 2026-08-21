"""Tests for the ECi client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.arrowhead_alarm.arrowhead_client import (
    ArrowheadECiClient,
    ConnectionState,
)


@pytest.fixture
def client():
    return ArrowheadECiClient("192.168.1.100", 9000, "1 123")


def test_client_initializes_with_eci_defaults(client):
    assert client.host == "192.168.1.100"
    assert client.port == 9000
    assert client.panel_model == "ECi Series"
    assert client.connection_state == "disconnected"
    assert client.configured_areas == [1]


def test_set_configured_areas_updates_status(client):
    client.set_configured_areas([3, 1, 2])

    assert client.configured_areas == [1, 2, 3]
    assert client.single_area_mode is False
    assert client._status["configured_areas"] == [1, 2, 3]


@pytest.mark.asyncio
async def test_connect_returns_false_on_timeout(client, monkeypatch):
    async def timeout(*args, **kwargs):
        raise TimeoutError

    monkeypatch.setattr("asyncio.open_connection", timeout)

    assert await client.connect() is False
    assert client.connection_state == "disconnected"


@pytest.mark.asyncio
async def test_disconnect_clears_connection(client):
    client._connection_state = ConnectionState.CONNECTED
    client.writer = MagicMock()
    client.writer.wait_closed = AsyncMock()

    await client.disconnect()

    assert client.connection_state == "disconnected"
    assert client.reader is None
    assert client.writer is None


@pytest.mark.asyncio
async def test_arm_away_delegates_to_main_panel_command(client):
    client._connection_state = ConnectionState.CONNECTED
    client.send_main_panel_armaway = AsyncMock(return_value=True)

    assert await client.arm_away() is True
    client.send_main_panel_armaway.assert_awaited_once()


@pytest.mark.asyncio
async def test_status_returns_copy(client):
    status = await client.get_status()

    assert status["panel_type"] == "eci"
    assert status["panel_name"] == "ECi Series"
    assert status is not client._status


@pytest.mark.asyncio
async def test_populate_zones_from_panel_handles_ok_before_zone_data(client, monkeypatch):
    client.configured_areas = [1]
    client._status["zones"] = {}
    client._status["zone_alarms"] = {}
    client._status["zone_troubles"] = {}
    client._status["zone_bypassed"] = {}
    monkeypatch.setattr(client, "_clear_response_queue", AsyncMock())
    monkeypatch.setattr(client, "_send_raw_safe", AsyncMock())
    monkeypatch.setattr(client, "_send_command_safe", AsyncMock(return_value="OK"))
    responses = iter(["OK", "P4075E1=1,2,3"])
    monkeypatch.setattr(client, "_get_response_safe", AsyncMock(side_effect=lambda: next(responses)))

    await client._populate_zones_from_panel()

    assert set(client._status["zones"].keys()) == {1, 2, 3}


@pytest.mark.asyncio
async def test_populate_zones_from_panel_handles_immediate_zone_response(client, monkeypatch):
    client.configured_areas = [1]
    client._status["zones"] = {}
    client._status["zone_alarms"] = {}
    client._status["zone_troubles"] = {}
    client._status["zone_bypassed"] = {}
    monkeypatch.setattr(client, "_clear_response_queue", AsyncMock())
    monkeypatch.setattr(client, "_send_raw_safe", AsyncMock())
    monkeypatch.setattr(client, "_get_response_safe", AsyncMock(return_value="P4075E1=1,2,3"))

    await client._populate_zones_from_panel()

    assert set(client._status["zones"].keys()) == {1, 2, 3}


@pytest.mark.asyncio
async def test_query_zones_for_area_ignores_ok_and_event_messages(client, monkeypatch):
    monkeypatch.setattr(client, "_clear_response_queue", AsyncMock())
    monkeypatch.setattr(client, "_send_raw_safe", AsyncMock())
    monkeypatch.setattr(
        client,
        "_get_response_safe",
        AsyncMock(side_effect=["OK", "ZR1", "P4075E1=1,2,3"]),
    )

    result = await client._query_zones_for_area(1)

    assert result == {1, 2, 3}


@pytest.mark.asyncio
async def test_populate_zones_from_panel_does_not_fake_zones_when_no_data_arrives(client, monkeypatch):
    client.configured_areas = [1]
    client._status["zones"] = {}
    client._status["zone_alarms"] = {}
    client._status["zone_troubles"] = {}
    client._status["zone_bypassed"] = {}
    monkeypatch.setattr(client, "_clear_response_queue", AsyncMock())
    monkeypatch.setattr(client, "_send_raw_safe", AsyncMock())
    monkeypatch.setattr(client, "_get_response_safe", AsyncMock(side_effect=["OK", asyncio.TimeoutError()]))

    await client._populate_zones_from_panel()

    assert client._status["zones"] == {}


@pytest.mark.asyncio
async def test_populate_zones_from_panel_handles_multiple_areas(client, monkeypatch):
    client.configured_areas = [1, 2]
    client._status["zones"] = {}
    client._status["zone_alarms"] = {}
    client._status["zone_troubles"] = {}
    client._status["zone_bypassed"] = {}
    monkeypatch.setattr(client, "_clear_response_queue", AsyncMock())
    monkeypatch.setattr(client, "_send_raw_safe", AsyncMock())
    monkeypatch.setattr(
        client,
        "_get_response_safe",
        AsyncMock(side_effect=["OK", "P4075E1=1,2,3", "OK", "P4075E2=4,5,6"]),
    )

    await client._populate_zones_from_panel()

    assert set(client._status["zones"].keys()) == {1, 2, 3, 4, 5, 6}


def test_configure_manual_outputs_updates_status(client):
    client.configure_manual_outputs(8)

    assert sorted(client._status["outputs"]) == list(range(1, 9))


@pytest.mark.asyncio
async def test_query_unsealed_zones_uses_status_and_waits_for_status_updates(client):
    client._status["zones"] = {}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock()

    async def receive_status_updates(_delay):
        client._status["zones"] = {
            1: False,
            2: True,
            5: True,
            9: False,
        }

    with patch(
        "custom_components.arrowhead_alarm.arrowhead_client.asyncio.sleep",
        side_effect=receive_status_updates,
    ) as sleep:
        result = await client.query_unsealed_zones()

    client._send_command_safe.assert_awaited_once_with("STATUS")
    sleep.assert_awaited_once_with(0.5)
    assert result == [2, 5]


def test_state_change_callback_is_registered(client):
    callback = MagicMock()

    client.register_state_change_callback(callback)

    assert client._state_change_callback is callback


@pytest.mark.asyncio
async def test_client_refresh_firmware_info_updates_runtime_state():
    client = ArrowheadECiClient("192.168.1.100", 9000, "1234")
    client._connection_state = client._connection_state.__class__.CONNECTED
    client.protocol_mode = "MODE_1"
    client.mode_4_features_active = False
    client.writer = MagicMock()
    client._status = {
        "firmware_version": "Unknown",
        "protocol_mode": "MODE_1",
        "supports_mode_4": False,
        "mode_4_features_active": False,
    }
    client._send_command_safe = AsyncMock(return_value="ECi F/W Ver. 10.3.51")

    version = await client.refresh_firmware_info()

    assert version == "10.3.51"
    assert client.firmware_version == "10.3.51"
    assert client.supports_mode_4 is True
    assert client.protocol_mode == "MODE_1"
    assert client.mode_4_features_active is False
    assert client._status["firmware_version"] == "10.3.51"
    assert client._status["supports_mode_4"] is True
    assert client._status["protocol_mode"] == "MODE_1"
    assert client._status["mode_4_features_active"] is False


@pytest.mark.asyncio
async def test_connect_refreshes_firmware_version_on_connection():
    client = ArrowheadECiClient("192.168.1.100", 9000, "1234")
    client._authenticate = AsyncMock(return_value=True)
    client._configure_protocol = AsyncMock()
    client._get_initial_status = AsyncMock()
    client.refresh_firmware_info = AsyncMock(return_value="10.3.51")

    writer = MagicMock()
    writer.is_closing.return_value = False
    writer.wait_closed = AsyncMock()
    reader = AsyncMock()

    def fake_create_task(coro):
        coro.close()
        return MagicMock()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))), \
         patch("asyncio.create_task", side_effect=fake_create_task):
        result = await client.connect()

    assert result is True
    client.refresh_firmware_info.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnect_refreshes_firmware_version_again():
    client = ArrowheadECiClient("192.168.1.100", 9000, "1234")
    client.firmware_version = "10.3.51"
    client._authenticate = AsyncMock(return_value=True)
    client._configure_protocol = AsyncMock()
    client._get_initial_status = AsyncMock()

    async def refresh_side_effect():
        client.firmware_version = "11.0.0"
        return "11.0.0"

    client.refresh_firmware_info = AsyncMock(side_effect=refresh_side_effect)

    writer = MagicMock()
    writer.is_closing.return_value = False
    writer.wait_closed = AsyncMock()
    reader = AsyncMock()

    def fake_create_task(coro):
        coro.close()
        return MagicMock()

    with patch("asyncio.open_connection", AsyncMock(return_value=(reader, writer))), \
         patch("asyncio.create_task", side_effect=fake_create_task):
        first = await client.connect()
        second = await client.connect()

    assert first is True
    assert second is True
    assert client.refresh_firmware_info.await_count == 2
    assert client.firmware_version == "11.0.0"


@pytest.mark.asyncio
async def test_get_status_does_not_refresh_firmware_on_normal_poll():
    client = ArrowheadECiClient("192.168.1.100", 9000, "1234")
    client._connection_state = client._connection_state.__class__.CONNECTED
    client._send_command_safe = AsyncMock(return_value="STATUS OK")
    client.refresh_firmware_info = AsyncMock()

    await client.get_status()

    client.refresh_firmware_info.assert_not_called()
    client._send_command_safe.assert_awaited_once_with("STATUS")
