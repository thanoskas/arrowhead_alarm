"""Tests for the ECi client."""

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


def test_configure_manual_outputs_updates_status(client):
    client.configure_manual_outputs(8)

    assert sorted(client._status["outputs"]) == list(range(1, 9))


def test_state_change_callback_is_registered(client):
    callback = MagicMock()

    client.register_state_change_callback(callback)

    assert client._state_change_callback is callback
