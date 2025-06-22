"""Test the Arrowhead Alarm Panel config flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.arrowhead_alarm.const import DOMAIN
from custom_components.arrowhead_alarm.config_flow import ArrowheadAlarmConfigFlow


@pytest.fixture
def mock_client():
    """Mock ArrowheadClient."""
    client = MagicMock()
    client.connect = AsyncMock(return_value=True)
    client.get_status = AsyncMock(return_value={
        "armed": False,
        "zones": {1: False, 2: False},
        "connection_state": "connected"
    })
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def config_flow():
    """Create a config flow instance."""
    return ArrowheadAlarmConfigFlow()


class TestConfigFlow:
    """Test the config flow."""

    async def test_form_user_step(self, hass: HomeAssistant, config_flow):
        """Test we get the user form."""
        result = await config_flow.async_step_user()
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "user"

    async def test_form_user_step_with_panel_selection(self, hass: HomeAssistant, config_flow):
        """Test user step with panel type selection."""
        result = await config_flow.async_step_user({"panel_type": "esx"})
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_connection_step_success(self, mock_client_class, hass: HomeAssistant, config_flow, mock_client):
        """Test successful connection step."""
        mock_client_class.return_value = mock_client
        config_flow.discovery_info = {"panel_type": "esx"}
        
        connection_data = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123",
            "username": "admin",
            "password": "admin"
        }
        
        result = await config_flow.async_step_connection(connection_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "output_config"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_connection_step_failure(self, mock_client_class, hass: HomeAssistant, config_flow, mock_client):
        """Test connection step with connection failure."""
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client
        config_flow.discovery_info = {"panel_type": "esx"}
        
        connection_data = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123",
            "username": "admin",
            "password": "admin"
        }
        
        result = await config_flow.async_step_connection(connection_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "auth_failed"

    async def test_output_config_step(self, hass: HomeAssistant, config_flow):
        """Test output configuration step."""
        config_flow.discovery_info = {
            "panel_type": "esx",
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123"
        }
        
        result = await config_flow.async_step_output_config({"max_outputs": 4})
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Arrowhead ESX Elite-SX"
        assert result["data"]["max_outputs"] == 4

    async def test_eci_zone_config_step(self, hass: HomeAssistant, config_flow):
        """Test ECi zone configuration step."""
        config_flow.discovery_info = {"panel_type": "eci"}
        config_flow._detected_config = {
            "total_zones": 16,
            "active_areas": [1],
            "max_zone": 16
        }
        
        result = await config_flow.async_step_zone_config()
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "zone_config"

    async def test_zone_names_step(self, hass: HomeAssistant, config_flow):
        """Test zone names configuration step."""
        config_flow._detected_config = {
            "detected_zones": [1, 2, 3, 4]
        }
        
        zone_data = {
            "zone_1_name": "Front Door",
            "zone_2_name": "Kitchen Window"
        }
        
        result = await config_flow.async_step_zone_names(zone_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "output_config"

    async def test_unique_id_check(self, hass: HomeAssistant):
        """Test that duplicate entries are prevented."""
        # Create first entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id="arrowhead_esx_192.168.1.100",
            data={"host": "192.168.1.100", "panel_type": "esx"}
        )
        entry.add_to_hass(hass)
        
        # Try to create duplicate
        flow = ArrowheadAlarmConfigFlow()
        flow.hass = hass
        
        discovery_info = {
            "panel_type": "esx",
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123"
        }
        
        await flow.async_set_unique_id("arrowhead_esx_192.168.1.100")
        result = flow._abort_if_unique_id_configured()
        
        # Should not create duplicate


class MockConfigEntry:
    """Mock config entry."""
    
    def __init__(self, **kwargs):
        self.domain = kwargs.get("domain")
        self.unique_id = kwargs.get("unique_id")
        self.data = kwargs.get("data", {})
        self.entry_id = "test_entry_id"
    
    def add_to_hass(self, hass):
        """Add to hass."""
        if not hasattr(hass, "config_entries"):
            hass.config_entries = MagicMock()
        if not hasattr(hass.config_entries, "async_entries"):
            hass.config_entries.async_entries = MagicMock(return_value=[self])


class TestConnectionTesting:
    """Test connection testing functionality."""

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_tcp_connection_success(self, mock_client_class, config_flow, mock_client):
        """Test successful TCP connection."""
        mock_client_class.return_value = mock_client
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123",
            "username": "admin",
            "password": "admin",
            "panel_type": "esx"
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is True
        assert "Connected successfully" in result["status"]

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_tcp_connection_timeout(self, mock_client_class, config_flow, mock_client):
        """Test TCP connection timeout."""
        mock_client.connect.side_effect = TimeoutError()
        mock_client_class.return_value = mock_client
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 123",
            "username": "admin", 
            "password": "admin",
            "panel_type": "esx"
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is False
        assert result["error_type"] == "timeout"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_invalid_credentials(self, mock_client_class, config_flow, mock_client):
        """Test invalid credentials."""
        mock_client.connect.return_value = False
        mock_client_class.return_value = mock_client
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 999",  # Invalid PIN
            "username": "admin",
            "password": "admin",
            "panel_type": "esx"
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is False
        assert result["error_type"] == "auth_failed"


class TestECiDetection:
    """Test ECi panel detection functionality."""

    @patch("custom_components.arrowhead_alarm.config_flow.ECiZoneManager")
    async def test_eci_zone_detection(self, mock_zone_manager_class, config_flow, mock_client):
        """Test ECi zone detection."""
        mock_zone_manager = MagicMock()
        mock_zone_manager.detect_panel_configuration = AsyncMock(return_value={
            "detected_zones": {1, 2, 3, 4, 5, 6, 7, 8},
            "active_areas": {1},
            "max_zone": 8,
            "total_zones": 8,
            "detection_method": "active_areas_query"
        })
        mock_zone_manager_class.return_value = mock_zone_manager
        
        result = await config_flow._detect_eci_configuration(mock_client)
        
        assert result["total_zones"] == 8
        assert result["max_zone"] == 8
        assert 1 in result["active_areas"]
        assert result["detection_method"] == "active_areas_query"

    @patch("custom_components.arrowhead_alarm.config_flow.ECiZoneManager")
    async def test_eci_detection_fallback(self, mock_zone_manager_class, config_flow, mock_client):
        """Test ECi detection fallback on error."""
        mock_zone_manager = MagicMock()
        mock_zone_manager.detect_panel_configuration = AsyncMock(side_effect=Exception("Detection failed"))
        mock_zone_manager_class.return_value = mock_zone_manager
        
        result = await config_flow._detect_eci_configuration(mock_client)
        
        assert result["total_zones"] == 16
        assert result["max_zone"] == 16
        assert result["detection_method"] == "error_fallback"


class TestOptionsFlow:
    """Test the options flow."""

    async def test_options_flow_init(self, hass: HomeAssistant):
        """Test options flow initialization."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"panel_type": "esx", "host": "192.168.1.100"},
            options={"scan_interval": 30}
        )
        
        from custom_components.arrowhead_alarm.config_flow import ArrowheadAlarmOptionsFlowHandler
        flow = ArrowheadAlarmOptionsFlowHandler(entry)
        
        result = await flow.async_step_init()
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"

    async def test_options_flow_save(self, hass: HomeAssistant):
        """Test saving options."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"panel_type": "esx", "host": "192.168.1.100"}
        )
        
        from custom_components.arrowhead_alarm.config_flow import ArrowheadAlarmOptionsFlowHandler
        flow = ArrowheadAlarmOptionsFlowHandler(entry)
        
        options_data = {
            "scan_interval": 60,
            "timeout": 15,
            "enable_debug_logging": True,
            "max_outputs": 8
        }
        
        result = await flow.async_step_init(options_data)
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["scan_interval"] == 60
        assert result["data"]["max_outputs"] == 8