"""Tests for the ECi data update coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.arrowhead_alarm.coordinator import (
    ArrowheadECiDataUpdateCoordinator,
    ConnectionState,
)


@pytest.fixture
def coordinator(hass):
    client = MagicMock()
    client.is_connected = True
    client.get_status = AsyncMock(return_value={
        "connection_state": "connected",
        "zones": {1: False},
        "outputs": {},
        "ready_to_arm": True,
    })
    client.register_state_change_callback = MagicMock()
    return ArrowheadECiDataUpdateCoordinator(hass, client, 30)


def test_coordinator_initializes_with_disconnected_state(coordinator):
    assert coordinator.connection_state == ConnectionState.DISCONNECTED
    assert coordinator.success_rate == 0.0
    assert coordinator.health_metrics["total_updates"] == 0


def test_connection_state_listener_receives_changes(coordinator):
    listener = MagicMock()
    coordinator.async_add_connection_state_listener(listener)

    coordinator._update_connection_state(ConnectionState.CONNECTED)

    listener.assert_called_once_with(ConnectionState.CONNECTED)


@pytest.mark.asyncio
async def test_update_data_reads_client_status(coordinator):
    data = await coordinator._async_update_data()

    assert data["zones"] == {1: False}
    assert coordinator.health_metrics["successful_updates"] == 1


@pytest.mark.asyncio
async def test_alarm_commands_delegate_to_client(coordinator):
    coordinator.client.arm_away = AsyncMock(return_value=True)
    coordinator.client.disarm = AsyncMock(return_value=True)
    coordinator.async_request_refresh = AsyncMock()

    assert await coordinator.async_arm_away() is True
    assert await coordinator.async_disarm() is True
    coordinator.client.arm_away.assert_awaited_once()
    coordinator.client.disarm.assert_awaited_once()


@pytest.mark.asyncio
async def test_bypass_state_event_updates_coordinator_without_status_refresh(coordinator):
    coordinator.client._status = {
        "connection_state": "connected",
        "zone_bypassed": {1: True},
    }
    coordinator.async_set_updated_data = MagicMock()
    coordinator.async_request_refresh = AsyncMock()

    await coordinator._handle_client_state_change("zone", {"message": "ZBY1"})

    coordinator.async_set_updated_data.assert_called_once_with(coordinator.client._status)
    coordinator.async_request_refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_disconnects_client(coordinator):
    coordinator.client.disconnect = AsyncMock()

    await coordinator.async_shutdown()

    coordinator.client.disconnect.assert_awaited_once()
