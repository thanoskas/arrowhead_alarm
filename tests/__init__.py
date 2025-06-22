"""Test the Arrowhead Alarm Panel integration setup."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady

from custom_components.arrowhead_alarm import (
    async_setup_entry,
    async_unload_entry,
    async_reload_entry,
)
from custom_components.arrowhead_alarm.const import (
    DOMAIN,
    CONF_MAX_OUTPUTS,
    PANEL_TYPE_ESX,
    PANEL_TYPE_ECI,
    DEFAULT_MAX_OUTPUTS,
)


class TestIntegrationSetup:
    """Test integration setup and teardown."""

    @pytest.fixture
    def mock_config_entry_data(self):
        """Mock config entry data."""
        return {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123",
            "username": "admin",
            "password": "admin",
            "panel_type": PANEL_TYPE_ESX,
            "max_outputs": 4,
        }

    @pytest.fixture
    def mock_config_entry_esx(self, mock_config_entry_data):
        """Mock ESX config entry."""
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_esx_entry"
        entry.data = mock_config_entry_data
        entry.options = {}
        entry.async_on_unload = MagicMock()
        entry.add_update_listener = MagicMock()
        return entry

    @pytest.fixture
    def mock_config_entry_eci(self, mock_config_entry_data):
        """Mock ECi config entry."""
        eci_data = mock_config_entry_data.copy()
        eci_data.update({
            "panel_type": PANEL_TYPE_ECI,
            "max_zones": 32,
            "areas": [1, 2],
            "auto_detect_zones": True,
            "max_outputs": 8,
        })
        
        entry = MagicMock(spec=ConfigEntry)
        entry.entry_id = "test_eci_entry"
        entry.data = eci_data
        entry.options = {}
        entry.async_on_unload = MagicMock()
        entry.add_update_listener = MagicMock()
        return entry

    @patch("custom_components.arrowhead_alarm.ArrowheadClient")
    @patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator")
    async def test_setup_entry_esx_success(
        self, mock_coordinator_class, mock_client_class, hass: HomeAssistant, mock_config_entry_esx
    ):
        """Test successful setup of ESX entry."""
        # Mock client
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.get_status = AsyncMock(return_value={
            "connection_state": "connected",
            "zones": {1: False, 2: False},
            "outputs": {},
        })
        mock_client.configure_manual_outputs = MagicMock()
        mock_client._status = {"outputs": {1: False, 2: False, 3: False, 4: False}}
        mock_client_class.return_value = mock_client
        
        # Mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.async_setup = AsyncMock()
        mock_coordinator.data = {"connection_state": "connected"}
        mock_coordinator_class.return_value = mock_coordinator
        
        # Mock platform setup
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        
        result = await async_setup_entry(hass, mock_config_entry_esx)
        
        assert result is True
        assert DOMAIN in hass.data
        assert mock_config_entry_esx.entry_id in hass.data[DOMAIN]
        
        # Verify client connection was attempted
        mock_client.connect.assert_called_once()
        mock_client.get_status.assert_called_once()
        
        # Verify manual output configuration
        mock_client.configure_manual_outputs.assert_called_once_with(4)
        
        # Verify coordinator setup
        mock_coordinator.async_setup.assert_called_once()
        
        # Verify platforms were set up
        hass.config_entries.async_forward_entry_setups.assert_called_once()

    @patch("custom_components.arrowhead_alarm.ArrowheadClient")
    @patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator")
    async def test_setup_entry_eci_success(
        self, mock_coordinator_class, mock_client_class, hass: HomeAssistant, mock_config_entry_eci
    ):
        """Test successful setup of ECi entry."""
        # Mock client
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.get_status = AsyncMock(return_value={
            "connection_state": "connected",
            "zones": {i: False for i in range(1, 33)},
            "outputs": {},
        })
        mock_client.configure_manual_outputs = MagicMock()
        mock_client._status = {"outputs": {i: False for i in range(1, 9)}}
        mock_client_class.return_value = mock_client
        
        # Mock coordinator
        mock_coordinator = MagicMock()
        mock_coordinator.async_setup = AsyncMock()
        mock_coordinator.data = {"connection_state": "connected"}
        mock_coordinator_class.return_value = mock_coordinator
        
        # Mock platform setup
        hass.config_entries.async_forward_entry_setups = AsyncMock()
        
        result = await async_setup_entry(hass, mock_config_entry_eci)
        
        assert result is True
        
        # Verify ECi-specific output configuration
        mock_client.configure_manual_outputs.assert_called_once_with(8)

    @patch("custom_components.arrowhead_alarm.ArrowheadClient")
    async def test_setup_entry_connection_failure(
        self, mock_client_class, hass: HomeAssistant, mock_config_entry_esx
    ):
        """Test setup entry with connection failure."""
        # Mock client connection failure
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=False)
        mock_client.disconnect = AsyncMock()
        mock_client_class.return_value = mock_client
        
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry_esx)
        
        # Should disconnect on status failure
        mock_client.disconnect.assert_called_once()

    @patch("custom_components.arrowhead_alarm.ArrowheadClient")
    @patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator")
    async def test_setup_entry_coordinator_failure(
        self, mock_coordinator_class, mock_client_class, hass: HomeAssistant, mock_config_entry_esx
    ):
        """Test setup entry with coordinator setup failure."""
        # Mock client success
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.get_status = AsyncMock(return_value={"connection_state": "connected"})
        mock_client.configure_manual_outputs = MagicMock()
        mock_client._status = {"outputs": {}}
        mock_client.disconnect = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock coordinator failure
        mock_coordinator = MagicMock()
        mock_coordinator.async_setup = AsyncMock(side_effect=Exception("Coordinator setup failed"))
        mock_coordinator_class.return_value = mock_coordinator
        
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry_esx)
        
        # Should disconnect client on coordinator failure
        mock_client.disconnect.assert_called_once()

    async def test_setup_entry_manual_output_configuration(self, hass: HomeAssistant):
        """Test manual output configuration during setup."""
        with patch("custom_components.arrowhead_alarm.ArrowheadClient") as mock_client_class, \
             patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator") as mock_coordinator_class:
            
            # Mock client
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.get_status = AsyncMock(return_value={"connection_state": "connected"})
            mock_client.configure_manual_outputs = MagicMock()
            mock_client._status = {"outputs": {1: False, 2: False}}
            mock_client_class.return_value = mock_client
            
            # Mock coordinator
            mock_coordinator = MagicMock()
            mock_coordinator.async_setup = AsyncMock()
            mock_coordinator.data = {"connection_state": "connected"}
            mock_coordinator_class.return_value = mock_coordinator
            
            # Mock config entry with custom output count
            entry = MagicMock()
            entry.entry_id = "test_entry"
            entry.data = {
                "host": "192.168.1.100",
                "panel_type": PANEL_TYPE_ESX,
                CONF_MAX_OUTPUTS: 8
            }
            entry.options = {}
            entry.async_on_unload = MagicMock()
            entry.add_update_listener = MagicMock()
            
            hass.config_entries.async_forward_entry_setups = AsyncMock()
            
            await async_setup_entry(hass, entry)
            
            # Verify manual output configuration with custom count
            mock_client.configure_manual_outputs.assert_called_once_with(8)

    async def test_setup_entry_default_output_configuration(self, hass: HomeAssistant):
        """Test default output configuration when not specified."""
        with patch("custom_components.arrowhead_alarm.ArrowheadClient") as mock_client_class, \
             patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator") as mock_coordinator_class:
            
            # Mock client
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.get_status = AsyncMock(return_value={"connection_state": "connected"})
            mock_client.configure_manual_outputs = MagicMock()
            mock_client._status = {"outputs": {}}
            mock_client_class.return_value = mock_client
            
            # Mock coordinator
            mock_coordinator = MagicMock()
            mock_coordinator.async_setup = AsyncMock()
            mock_coordinator.data = {"connection_state": "connected"}
            mock_coordinator_class.return_value = mock_coordinator
            
            # Mock config entry without max_outputs
            entry = MagicMock()
            entry.entry_id = "test_entry"
            entry.data = {
                "host": "192.168.1.100",
                "panel_type": PANEL_TYPE_ESX,
                # No max_outputs specified
            }
            entry.options = {}
            entry.async_on_unload = MagicMock()
            entry.add_update_listener = MagicMock()
            
            hass.config_entries.async_forward_entry_setups = AsyncMock()
            
            await async_setup_entry(hass, entry)
            
            # Should use default output count
            mock_client.configure_manual_outputs.assert_called_once_with(DEFAULT_MAX_OUTPUTS)

    async def test_setup_stores_correct_data(self, hass: HomeAssistant):
        """Test that setup stores correct data structure."""
        with patch("custom_components.arrowhead_alarm.ArrowheadClient") as mock_client_class, \
             patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator") as mock_coordinator_class:
            
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.get_status = AsyncMock(return_value={"connection_state": "connected"})
            mock_client.configure_manual_outputs = MagicMock()
            mock_client._status = {"outputs": {}}
            mock_client_class.return_value = mock_client
            
            mock_coordinator = MagicMock()
            mock_coordinator.async_setup = AsyncMock()
            mock_coordinator.data = {"connection_state": "connected"}
            mock_coordinator_class.return_value = mock_coordinator
            
            entry = MagicMock()
            entry.entry_id = "test_entry"
            entry.data = {"host": "192.168.1.100", "panel_type": PANEL_TYPE_ESX}
            entry.options = {}
            entry.async_on_unload = MagicMock()
            entry.add_update_listener = MagicMock()
            
            hass.config_entries.async_forward_entry_setups = AsyncMock()
            
            await async_setup_entry(hass, entry)
            
            # Verify data structure
            assert DOMAIN in hass.data
            assert entry.entry_id in hass.data[DOMAIN]
            
            stored_data = hass.data[DOMAIN][entry.entry_id]
            assert "coordinator" in stored_data
            assert "client" in stored_data
            assert "panel_config" in stored_data
            
            assert stored_data["coordinator"] == mock_coordinator
            assert stored_data["client"] == mock_client
            assert "name" in stored_data["panel_config"]


class TestIntegrationUnload:
    """Test integration unload functionality."""

    async def test_unload_entry_success(self, hass: HomeAssistant):
        """Test successful entry unload."""
        # Setup mock data
        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()
        
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        
        entry = MagicMock()
        entry.entry_id = "test_entry"
        
        hass.data = {
            DOMAIN: {
                entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "client": mock_client,
                    "panel_config": {},
                }
            }
        }
        
        # Mock platform unload
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        
        result = await async_unload_entry(hass, entry)
        
        assert result is True
        
        # Verify cleanup
        mock_coordinator.async_shutdown.assert_called_once()
        mock_client.disconnect.assert_called_once()
        
        # Verify data removal
        assert entry.entry_id not in hass.data[DOMAIN]

    async def test_unload_entry_platform_failure(self, hass: HomeAssistant):
        """Test entry unload with platform unload failure."""
        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()
        
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        
        entry = MagicMock()
        entry.entry_id = "test_entry"
        
        hass.data = {
            DOMAIN: {
                entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "client": mock_client,
                    "panel_config": {},
                }
            }
        }
        
        # Mock platform unload failure
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
        
        result = await async_unload_entry(hass, entry)
        
        assert result is False
        
        # Should not cleanup if platform unload failed
        mock_coordinator.async_shutdown.assert_not_called()
        mock_client.disconnect.assert_not_called()

    async def test_unload_entry_client_disconnect_error(self, hass: HomeAssistant):
        """Test entry unload with client disconnect error."""
        mock_coordinator = MagicMock()
        mock_coordinator.async_shutdown = AsyncMock()
        
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock(side_effect=Exception("Disconnect failed"))
        
        entry = MagicMock()
        entry.entry_id = "test_entry"
        
        hass.data = {
            DOMAIN: {
                entry.entry_id: {
                    "coordinator": mock_coordinator,
                    "client": mock_client,
                    "panel_config": {},
                }
            }
        }
        
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        
        # Should not raise exception
        result = await async_unload_entry(hass, entry)
        
        assert result is True
        
        # Should still clean up coordinator
        mock_coordinator.async_shutdown.assert_called_once()
        
        # Data should still be removed
        assert entry.entry_id not in hass.data[DOMAIN]

    async def test_unload_entry_missing_data(self, hass: HomeAssistant):
        """Test entry unload with missing data."""
        entry = MagicMock()
        entry.entry_id = "nonexistent_entry"
        
        hass.data = {DOMAIN: {}}
        hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        
        # Should handle missing data gracefully
        result = await async_unload_entry(hass, entry)
        
        assert result is True


class TestIntegrationReload:
    """Test integration reload functionality."""

    async def test_reload_entry(self, hass: HomeAssistant):
        """Test entry reload."""
        entry = MagicMock()
        entry.entry_id = "test_entry"
        
        with patch("custom_components.arrowhead_alarm.async_unload_entry") as mock_unload, \
             patch("custom_components.arrowhead_alarm.async_setup_entry") as mock_setup:
            
            mock_unload.return_value = True
            mock_setup.return_value = True
            
            await async_reload_entry(hass, entry)
            
            mock_unload.assert_called_once_with(hass, entry)
            mock_setup.assert_called_once_with(hass, entry)


class TestIntegrationDataStructure:
    """Test integration data structure management."""

    def test_data_structure_initialization(self, hass: HomeAssistant):
        """Test that data structure is properly initialized."""
        # Should handle missing DOMAIN key
        assert DOMAIN not in hass.data
        
        # After setup, should create proper structure
        hass.data.setdefault(DOMAIN, {})
        assert DOMAIN in hass.data
        assert isinstance(hass.data[DOMAIN], dict)

    async def test_multiple_entries_data_isolation(self, hass: HomeAssistant):
        """Test that multiple entries have isolated data."""
        with patch("custom_components.arrowhead_alarm.ArrowheadClient") as mock_client_class, \
             patch("custom_components.arrowhead_alarm.ArrowheadDataUpdateCoordinator") as mock_coordinator_class:
            
            # Mock client and coordinator
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=True)
            mock_client.get_status = AsyncMock(return_value={"connection_state": "connected"})
            mock_client.configure_manual_outputs = MagicMock()
            mock_client._status = {"outputs": {}}
            mock_client_class.return_value = mock_client
            
            mock_coordinator = MagicMock()
            mock_coordinator.async_setup = AsyncMock()
            mock_coordinator.data = {"connection_state": "connected"}
            mock_coordinator_class.return_value = mock_coordinator
            
            # Create two entries
            entry1 = MagicMock()
            entry1.entry_id = "entry_1"
            entry1.data = {"host": "192.168.1.100", "panel_type": PANEL_TYPE_ESX}
            entry1.options = {}
            entry1.async_on_unload = MagicMock()
            entry1.add_update_listener = MagicMock()
            
            entry2 = MagicMock()
            entry2.entry_id = "entry_2"
            entry2.data = {"host": "192.168.1.101", "panel_type": PANEL_TYPE_ECI}
            entry2.options = {}
            entry2.async_on_unload = MagicMock()
            entry2.add_update_listener = MagicMock()
            
            hass.config_entries.async_forward_entry_setups = AsyncMock()
            
            # Setup both entries
            await async_setup_entry(hass, entry1)
            await async_setup_entry(hass, entry2)
            
            # Verify isolated data
            assert entry1.entry_id in hass.data[DOMAIN]
            assert entry2.entry_id in hass.data[DOMAIN]
            assert hass.data[DOMAIN][entry1.entry_id] != hass.data[DOMAIN][entry2.entry_id]

    async def test_entry_data_cleanup_on_failure(self, hass: HomeAssistant):
        """Test that entry data is cleaned up on setup failure."""
        with patch("custom_components.arrowhead_alarm.ArrowheadClient") as mock_client_class:
            
            # Mock client connection failure
            mock_client = MagicMock()
            mock_client.connect = AsyncMock(return_value=False)
            mock_client.disconnect = AsyncMock()
            mock_client_class.return_value = mock_client
            
            entry = MagicMock()
            entry.entry_id = "test_entry"
            entry.data = {"host": "192.168.1.100", "panel_type": PANEL_TYPE_ESX}
            
            # Setup should fail
            with pytest.raises(ConfigEntryNotReady):
                await async_setup_entry(hass, entry)
            
            # Data should not be left in hass.data
            if DOMAIN in hass.data:
                assert entry.entry_id not in hass.data[DOMAIN]client_class.return_value = mock_client
        
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry_esx)
        
        # Should attempt disconnect on failure
        mock_client.disconnect.assert_called_once()

    @patch("custom_components.arrowhead_alarm.ArrowheadClient")
    async def test_setup_entry_connection_timeout(
        self, mock_client_class, hass: HomeAssistant, mock_config_entry_esx
    ):
        """Test setup entry with connection timeout."""
        # Mock client connection timeout
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=asyncio.TimeoutError())
        mock_client.disconnect = AsyncMock()
        mock_client_class.return_value = mock_client
        
        with pytest.raises(ConfigEntryNotReady):
            await async_setup_entry(hass, mock_config_entry_esx)

    @patch("custom_components.arrowhead_alarm.ArrowheadClient")
    async def test_setup_entry_status_failure(
        self, mock_client_class, hass: HomeAssistant, mock_config_entry_esx
    ):
        """Test setup entry with status retrieval failure."""
        # Mock client status failure
        mock_client = MagicMock()
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.get_status = AsyncMock(return_value=None)
        mock_client.disconnect = AsyncMock()
        mock_