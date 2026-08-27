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
async def test_bypass_zone_returns_false_when_panel_state_does_not_confirm(client):
    client._connection_state = ConnectionState.CONNECTED
    client._status["zone_bypassed"] = {12: False}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock(return_value="OK Bypass")

    result = await client.bypass_zone(12)

    client._send_command_safe.assert_awaited_once_with(
        "BYPASS 012", expect_response=True, timeout=8.0
    )
    assert result is False


@pytest.mark.asyncio
async def test_bypass_zone_rejects_mismatched_command_acknowledgment(client):
    """An 'OK UnBypass' reply must not be accepted as a BYPASS acknowledgment."""
    client._connection_state = ConnectionState.CONNECTED
    client._status["zone_bypassed"] = {12: True}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock(return_value="OK UnBypass")

    result = await client.bypass_zone(12)

    assert result is False


@pytest.mark.asyncio
async def test_bypass_zone_accepts_differently_cased_acknowledgment(client):
    """Firmware variants may differ in casing of the acknowledgment text."""
    client._connection_state = ConnectionState.CONNECTED
    client._status["zone_bypassed"] = {12: True}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock(return_value="OK BYPASS")

    result = await client.bypass_zone(12)

    assert result is True


@pytest.mark.asyncio
async def test_bypass_zone_accepts_documented_zone_number_suffix(client):
    """Docs show 'OK Bypass 3', though some firmware (e.g. 10.3.58) omits it."""
    client._connection_state = ConnectionState.CONNECTED
    client._status["zone_bypassed"] = {3: True}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock(return_value="OK Bypass 3")

    result = await client.bypass_zone(3)

    assert result is True


@pytest.mark.asyncio
async def test_unbypass_zone_rejects_mismatched_command_acknowledgment(client):
    """An 'OK Bypass' reply must not be accepted as an UNBYPASS acknowledgment."""
    client._connection_state = ConnectionState.CONNECTED
    client._status["zone_bypassed"] = {12: False}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock(return_value="OK Bypass")

    result = await client.unbypass_zone(12)

    assert result is False


@pytest.mark.asyncio
async def test_keypad_bypass_event_updates_state_with_no_command_in_flight(client):
    """A keypad-initiated bypass only ever sends ZBY1, with no command from us."""
    callback = AsyncMock()
    client.register_state_change_callback(callback)
    client._status["zone_bypassed"] = {1: False}

    await client._process_message("ZBY1")

    assert client._status["zone_bypassed"][1] is True
    callback.assert_awaited_once_with("zone", {"message": "ZBY1"})


@pytest.mark.asyncio
async def test_process_message_does_not_treat_command_ack_as_event(client):
    callback = AsyncMock()
    client.register_state_change_callback(callback)

    await client._process_message("OK Bypass")

    callback.assert_not_awaited()


@pytest.mark.asyncio
async def test_console_bypass_command_gets_ack_then_confirms_via_event(client):
    """BYPASS 001 gets 'OK Bypass' ack, followed by a separate ZBY1 event."""
    client._connection_state = ConnectionState.CONNECTED
    client._status["zone_bypassed"] = {1: False}
    client._clear_response_queue = AsyncMock()
    client._send_command_safe = AsyncMock(return_value="OK Bypass")

    async def apply_confirmation_event(*args, **kwargs):
        await client._process_message("ZBY1")

    with patch(
        "custom_components.arrowhead_alarm.arrowhead_client.asyncio.sleep",
        side_effect=apply_confirmation_event,
    ):
        result = await client.bypass_zone(1)

    assert result is True
    assert client._status["zone_bypassed"][1] is True


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
