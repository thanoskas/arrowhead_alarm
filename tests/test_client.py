"""Tests for the ECi client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

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


def test_state_change_callback_is_registered(client):
    callback = MagicMock()

    client.register_state_change_callback(callback)

    assert client._state_change_callback is callback
