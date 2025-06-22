"""Test the Arrowhead Alarm Panel coordinator."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.arrowhead_alarm.coordinator import (
    ArrowheadDataUpdateCoordinator,
    ConnectionState,
)
from custom_components.arrowhead_alarm.const import DOMAIN


class TestArrowheadDataUpdateCoordinator:
    """Test the data update coordinator."""

    @pytest.fixture
    async def coordinator(self, hass: HomeAssistant, mock_arrowhead_client):
        """Create a coordinator instance."""
        coordinator = ArrowheadDataUpdateCoordinator(hass, mock_arrowhead_client, 30)
        return coordinator

    async def test_coordinator_initialization(self, coordinator, mock_arrowhead_client):
        """Test coordinator initialization."""
        assert coordinator._client == mock_arrowhead_client
        assert coordinator._connection_state == ConnectionState.DISCONNECTED
        assert coordinator.update_interval == timedelta(seconds=30)
        assert coordinator._consecutive_failures == 0

    async def test_coordinator_setup_success(self, coordinator, mock_arrowhead_client, mock_panel_status):
        """Test successful coordinator setup."""
        mock_arrowhead_client.get_status.return_value = mock_panel_status
        
        await coordinator.async_setup()
        
        assert coordinator._connection_state == ConnectionState.CONNECTED
        mock_arrowhead_client.connect.assert_called_once()

    async def test_coordinator_setup_connection_failure(self, coordinator, mock_arrowhead_client):
        """Test coordinator setup with connection failure."""
        mock_arrowhead_client.connect.return_value = False
        
        # Setup should not raise but connection state should be disconnected
        await coordinator.async_setup()
        
        assert coordinator._connection_state == ConnectionState.DISCONNECTED

    async def test_coordinator_first_refresh_success(self, coordinator, mock_arrowhead_client, mock_panel_status):
        """Test successful first refresh."""
        mock_arrowhead_client.get_status.return_value = mock_panel_status
        
        await coordinator.async_config_entry_first_refresh()
        
        assert coordinator.data == mock_panel_status
        assert coordinator.last_update_success is True

    async def test_coordinator_first_refresh_not_connected(self, coordinator, mock_arrowhead_client, mock_panel_status):
        """Test first refresh when client not connected."""
        mock_arrowhead_client.is_connected = False
        mock_arrowhead_client.get_status.return_value = mock_panel_status
        
        await coordinator.async_config_entry_first_refresh()
        
        # Should attempt to connect first
        mock_arrowhead_client.connect.assert_called()
        assert coordinator.data == mock_panel_status

    async def test_coordinator_first_refresh_connection_failure(self, coordinator, mock_arrowhead_client):
        """Test first refresh with connection failure."""
        mock_arrowhead_client.is_connected = False
        mock_arrowhead_client.connect.return_value = False
        
        with pytest.raises(UpdateFailed):
            await coordinator.async_config_entry_first_refresh()

    async def test_update_data_success(self, coordinator, mock_arrowhead_client, mock_panel_status):
        """Test successful data update."""
        mock_arrowhead_client.get_status.return_value = mock_panel_status
        
        data = await coordinator._async_update_data()
        
        assert data == mock_panel_status
        assert coordinator._connection_state == ConnectionState.CONNECTED

    async def test_update_data_not_connected(self, coordinator, mock_arrowhead_client, mock_panel_status):
        """Test data update when not connected."""
        mock_arrowhead_client.is_connected = False
        mock_arrowhead_client.get_status.return_value = mock_panel_status
        
        data = await coordinator._async_update_data()
        
        # Should reconnect and get data
        mock_arrowhead_client.connect.assert_called()
        assert data == mock_panel_status

    async def test_update_data_reconnection_failure(self, coordinator, mock_arrowhead_client):
        """Test data update with reconnection failure."""
        mock_arrowhead_client.is_connected = False
        mock_arrowhead_client.connect.return_value = False
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_update_data_no_status(self, coordinator, mock_arrowhead_client):
        """Test data update with no status returned."""
        mock_arrowhead_client.get_status.return_value = None
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

    async def test_update_data_exception(self, coordinator, mock_arrowhead_client):
        """Test data update with exception."""
        mock_arrowhead_client.get_status.side_effect = Exception("Communication error")
        
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        
        assert coordinator._connection_state == ConnectionState.DISCONNECTED

    async def test_coordinator_shutdown(self, coordinator, mock_arrowhead_client):
        """Test coordinator shutdown."""
        coordinator._connection_state = ConnectionState.CONNECTED
        
        await coordinator.async_shutdown()
        
        mock_arrowhead_client.disconnect.assert_called_once()
        assert coordinator._connection_state == ConnectionState.DISCONNECTED

    async def test_coordinator_shutdown_with_exception(self, coordinator, mock_arrowhead_client):
        """Test coordinator shutdown with exception."""
        mock_arrowhead_client.disconnect.side_effect = Exception("Disconnect error")
        
        # Should not raise exception
        await coordinator.async_shutdown()
        
        assert coordinator._connection_state == ConnectionState.DISCONNECTED


class TestCoordinatorAlarmControl:
    """Test alarm control methods."""

    @pytest.fixture
    async def coordinator(self, hass: HomeAssistant, mock_arrowhead_client):
        """Create a coordinator instance."""
        return ArrowheadDataUpdateCoordinator(hass, mock_arrowhead_client, 30)

    async def test_arm_away_success(self, coordinator, mock_arrowhead_client):
        """Test successful arm away."""
        mock_arrowhead_client.arm_away.return_value = True
        
        result = await coordinator.async_arm_away()
        
        assert result is True
        mock_arrowhead_client.arm_away.assert_called_once()

    async def test_arm_away_not_connected(self, coordinator, mock_arrowhead_client):
        """Test arm away when not connected."""
        mock_arrowhead_client.is_connected = False
        
        result = await coordinator.async_arm_away()
        
        assert result is False
        mock_arrowhead_client.arm_away.assert_not_called()

    async def test_arm_away_failure(self, coordinator, mock_arrowhead_client):
        """Test arm away failure."""
        mock_arrowhead_client.arm_away.return_value = False
        
        result = await coordinator.async_arm_away()
        
        assert result is False

    async def test_arm_away_exception(self, coordinator, mock_arrowhead_client):
        """Test arm away with exception."""
        mock_arrowhead_client.arm_away.side_effect = Exception("Communication error")
        
        result = await coordinator.async_arm_away()
        
        assert result is False

    async def test_arm_stay_success(self, coordinator, mock_arrowhead_client):
        """Test successful arm stay."""
        mock_arrowhead_client.arm_stay.return_value = True
        
        result = await coordinator.async_arm_stay()
        
        assert result is True
        mock_arrowhead_client.arm_stay.assert_called_once()

    async def test_arm_home_alias(self, coordinator, mock_arrowhead_client):
        """Test arm home alias method."""
        mock_arrowhead_client.arm_stay.return_value = True
        
        result = await coordinator.async_arm_home()
        
        assert result is True
        mock_arrowhead_client.arm_stay.assert_called_once()

    async def test_disarm_success(self, coordinator, mock_arrowhead_client):
        """Test successful disarm."""
        mock_arrowhead_client.disarm.return_value = True
        
        result = await coordinator.async_disarm()
        
        assert result is True
        mock_arrowhead_client.disarm.assert_called_once()

    async def test_disarm_not_connected(self, coordinator, mock_arrowhead_client):
        """Test disarm when not connected."""
        mock_arrowhead_client.is_connected = False
        
        result = await coordinator.async_disarm()
        
        assert result is False


class TestCoordinatorZoneControl:
    """Test zone control methods."""

    @pytest.fixture
    async def coordinator(self, hass: HomeAssistant, mock_arrowhead_client):
        """Create a coordinator instance."""
        return ArrowheadDataUpdateCoordinator(hass, mock_arrowhead_client, 30)

    async def test_bypass_zone_success(self, coordinator, mock_arrowhead_client):
        """Test successful zone bypass."""
        mock_arrowhead_client.bypass_zone.return_value = True
        
        result = await coordinator.async_bypass_zone(1)
        
        assert result is True
        mock_arrowhead_client.bypass_zone.assert_called_once_with(1)

    async def test_bypass_zone_not_connected(self, coordinator, mock_arrowhead_client):
        """Test zone bypass when not connected."""
        mock_arrowhead_client.is_connected = False
        
        result = await coordinator.async_bypass_zone(1)
        
        assert result is False

    async def test_bypass_zone_failure(self, coordinator, mock_arrowhead_client):
        """Test zone bypass failure."""
        mock_arrowhead_client.bypass_zone.return_value = False
        
        result = await coordinator.async_bypass_zone(1)
        
        assert result is False

    async def test_unbypass_zone_success(self, coordinator, mock_arrowhead_client):
        """Test successful zone unbypass."""
        mock_arrowhead_client.unbypass_zone.return_value = True
        
        result = await coordinator.async_unbypass_zone(1)
        
        assert result is True
        mock_arrowhead_client.unbypass_zone.assert_called_once_with(1)

    async def test_unbypass_zone_exception(self, coordinator, mock_arrowhead_client):
        """Test zone unbypass with exception."""
        mock_arrowhead_client.unbypass_zone.side_effect = Exception("Communication error")
        
        result = await coordinator.async_unbypass_zone(1)
        
        assert result is False


class TestCoordinatorOutputControl:
    """Test output control methods."""

    @pytest.fixture
    async def coordinator(self, hass: HomeAssistant, mock_arrowhead_client):
        """Create a coordinator instance."""
        return ArrowheadDataUpdateCoordinator(hass, mock_arrowhead_client, 30)

    async def test_trigger_output_success(self, coordinator, mock_arrowhead_client):
        """Test successful output trigger."""
        mock_arrowhead_client.trigger_output.return_value = True
        
        result = await coordinator.async_trigger_output(1, 5)
        
        assert result is True
        mock_arrowhead_client.trigger_output.assert_called_once_with(1, 5)

    async def test_trigger_output_no_duration(self, coordinator, mock_arrowhead_client):
        """Test output trigger without duration."""
        mock_arrowhead_client.trigger_output.return_value = True
        
        result = await coordinator.async_trigger_output(1)
        
        assert result is True
        mock_arrowhead_client.trigger_output.assert_called_once_with(1, None)

    async def test_trigger_output_not_connected(self, coordinator, mock_arrowhead_client):
        """Test output trigger when not connected."""
        mock_arrowhead_client.is_connected = False
        
        result = await coordinator.async_trigger_output(1)
        
        assert result is False

    async def test_trigger_output_failure(self, coordinator, mock_arrowhead_client):
        """Test output trigger failure."""
        mock_arrowhead_client.trigger_output.return_value = False
        
        result = await coordinator.async_trigger_output(1)
        
        assert result is False

    async def test_trigger_output_exception(self, coordinator, mock_arrowhead_client):
        """Test output trigger with exception."""
        mock_arrowhead_client.trigger_output.side_effect = Exception("Communication error")
        
        result = await coordinator.async_trigger_output(1)
        
        assert result is False


class TestConnectionStateManagement:
    """Test connection state management."""

    @pytest.fixture
    async def coordinator(self, hass: HomeAssistant, mock_arrowhead_client):
        """Create a coordinator instance."""
        return ArrowheadDataUpdateCoordinator(hass, mock_arrowhead_client, 30)

    async def test_connection_state_callbacks(self, coordinator):
        """Test connection state callbacks."""
        callback_called = False
        new_state = None
        
        def state_callback(state):
            nonlocal callback_called, new_state
            callback_called = True
            new_state = state
        
        # Add callback
        remove_callback = coordinator.async_add_connection_state_listener(state_callback)
        
        # Change state
        coordinator._update_connection_state(ConnectionState.CONNECTED)
        
        assert callback_called is True
        assert new_state == ConnectionState.CONNECTED
        
        # Remove callback
        remove_callback()
        
        # Reset and change state again
        callback_called = False
        coordinator._update_connection_state(ConnectionState.DISCONNECTED)
        
        # Callback should not be called
        assert callback_called is False

    async def test_connection_state_callback_exception(self, coordinator):
        """Test connection state callback with exception."""
        def failing_callback(state):
            raise Exception("Callback error")
        
        coordinator.async_add_connection_state_listener(failing_callback)
        
        # Should not raise exception
        coordinator._update_connection_state(ConnectionState.CONNECTED)
        
        assert coordinator._connection_state == ConnectionState.CONNECTED

    async def test_connection_state_property(self, coordinator):
        """Test connection state property."""
        assert coordinator.connection_state == ConnectionState.DISCONNECTED
        
        coordinator._update_connection_state(ConnectionState.CONNECTED)
        assert coordinator.connection_state == ConnectionState.CONNECTED


class TestCoordinatorUtilities:
    """Test coordinator utility methods."""

    @pytest.fixture
    async def coordinator(self, hass: HomeAssistant, mock_arrowhead_client):
        """Create a coordinator instance."""
        return ArrowheadDataUpdateCoordinator(hass, mock_arrowhead_client, 30)

    def test_client_property(self, coordinator, mock_arrowhead_client):
        """Test client property."""
        assert coordinator.client == mock_arrowhead_client

    def test_get_zone_name_from_options(self, coordinator, mock_config_entry_class):
        """Test getting zone name from options."""
        config_entry = mock_config_entry_class(
            options={"zone_names": {"zone_1_name": "Front Door"}}
        )
        
        zone_name = coordinator.get_zone_name(1, config_entry)
        assert zone_name == "Front Door"

    def test_get_zone_name_from_data(self, coordinator, mock_config_entry_class):
        """Test getting zone name from entry data."""
        config_entry = mock_config_entry_class(
            data={"zone_names": {"zone_1_name": "Kitchen Window"}}
        )
        
        zone_name = coordinator.get_zone_name(1, config_entry)
        assert zone_name == "Kitchen Window"

    def test_get_zone_name_default(self, coordinator, mock_config_entry_class):
        """Test getting default zone name."""
        config_entry = mock_config_entry_class()
        
        zone_name = coordinator.get_zone_name(1, config_entry)
        assert zone_name == "Zone 001"

    def test_get_zone_name_priority(self, coordinator, mock_config_entry_class):
        """Test zone name priority (options over data)."""
        config_entry = mock_config_entry_class(
            data={"zone_names": {"zone_1_name": "Data Name"}},
            options={"zone_names": {"zone_1_name": "Options Name"}}
        )
        
        zone_name = coordinator.get_zone_name(1, config_entry)
        assert zone_name == "Options Name"