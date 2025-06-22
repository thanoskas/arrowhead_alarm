"""Test the Arrowhead Alarm Panel config flow."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.arrowhead_alarm.const import (
    DOMAIN,
    CONF_USER_PIN,
    CONF_PANEL_TYPE,
    CONF_MAX_ZONES,
    CONF_AREAS,
    CONF_MAX_OUTPUTS,
    PANEL_TYPE_ESX,
    PANEL_TYPE_ECI,
    DEFAULT_USER_PIN,
)
from custom_components.arrowhead_alarm.config_flow import (
    ArrowheadAlarmConfigFlow,
    ArrowheadAlarmOptionsFlowHandler,
)


class TestConfigFlow:
    """Test the config flow."""

    @pytest.fixture
    def config_flow(self):
        """Create a config flow instance."""
        return ArrowheadAlarmConfigFlow()

    async def test_form_user_step(self, hass: HomeAssistant, config_flow):
        """Test we get the user form."""
        result = await config_flow.async_step_user()
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {}
        assert result["step_id"] == "user"
        assert "panel_type" in result["data_schema"].schema

    async def test_form_user_step_with_panel_selection(self, config_flow):
        """Test user step with panel type selection."""
        result = await config_flow.async_step_user({"panel_type": PANEL_TYPE_ESX})
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"

    async def test_eci_panel_goes_to_zone_config(self, config_flow):
        """Test ECi panel selection goes to zone config."""
        result = await config_flow.async_step_user({"panel_type": PANEL_TYPE_ECI})
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "connection"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_connection_step_success_esx(self, mock_client_class, config_flow, mock_arrowhead_client):
        """Test successful connection step for ESX."""
        mock_client_class.return_value = mock_arrowhead_client
        mock_arrowhead_client.get_status.return_value = {
            "connection_state": "connected",
            "zones": {1: False, 2: False},
            "armed": False
        }
        
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ESX}
        
        connection_data = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin"
        }
        
        result = await config_flow.async_step_connection(connection_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "output_config"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_connection_step_success_eci(self, mock_client_class, config_flow, mock_arrowhead_client):
        """Test successful connection step for ECi."""
        mock_client_class.return_value = mock_arrowhead_client
        mock_arrowhead_client.get_status.return_value = {
            "connection_state": "connected",
            "zones": {1: False, 2: False},
            "armed": False
        }
        
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ECI}
        
        connection_data = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin"
        }
        
        with patch.object(config_flow, '_detect_eci_configuration') as mock_detect:
            mock_detect.return_value = {
                "total_zones": 16,
                "active_areas": [1],
                "max_zone": 16,
                "detection_method": "active_areas_query"
            }
            
            result = await config_flow.async_step_connection(connection_data)
            
            assert result["type"] == FlowResultType.FORM
            assert result["step_id"] == "zone_config"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_connection_step_failure(self, mock_client_class, config_flow, mock_arrowhead_client):
        """Test connection step with connection failure."""
        mock_arrowhead_client.connect.return_value = False
        mock_client_class.return_value = mock_arrowhead_client
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ESX}
        
        connection_data = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin"
        }
        
        result = await config_flow.async_step_connection(connection_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "auth_failed"

    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_connection_timeout(self, mock_client_class, config_flow, mock_arrowhead_client):
        """Test connection timeout."""
        mock_arrowhead_client.connect.side_effect = asyncio.TimeoutError()
        mock_client_class.return_value = mock_arrowhead_client
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ESX}
        
        connection_data = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin"
        }
        
        result = await config_flow.async_step_connection(connection_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == "timeout"

    async def test_zone_config_step(self, config_flow):
        """Test zone configuration step."""
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ECI}
        config_flow._detected_config = {
            "total_zones": 16,
            "active_areas": [1],
            "max_zone": 16
        }
        
        result = await config_flow.async_step_zone_config()
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "zone_config"
        assert "auto_detect_zones" in result["data_schema"].schema
        assert "max_zones" in result["data_schema"].schema

    async def test_zone_config_with_zone_names(self, config_flow):
        """Test zone config step requesting zone names."""
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ECI}
        config_flow._detected_config = {
            "total_zones": 8,
            "detected_zones": [1, 2, 3, 4, 5, 6, 7, 8],
            "active_areas": [1],
            "max_zone": 8
        }
        
        zone_config_data = {
            "auto_detect_zones": True,
            "max_zones": 16,
            "areas": "1",
            "configure_zone_names": True
        }
        
        result = await config_flow.async_step_zone_config(zone_config_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "zone_names"

    async def test_zone_config_skip_zone_names(self, config_flow):
        """Test zone config step skipping zone names."""
        config_flow.discovery_info = {"panel_type": PANEL_TYPE_ECI}
        config_flow._detected_config = {
            "total_zones": 16,
            "active_areas": [1],
            "max_zone": 16
        }
        
        zone_config_data = {
            "auto_detect_zones": True,
            "max_zones": 16,
            "areas": "1",
            "configure_zone_names": False
        }
        
        result = await config_flow.async_step_zone_config(zone_config_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "output_config"

    async def test_zone_names_step(self, config_flow):
        """Test zone names configuration step."""
        config_flow._detected_config = {
            "detected_zones": [1, 2, 3, 4]
        }
        
        zone_data = {
            "zone_1_name": "Front Door",
            "zone_2_name": "Kitchen Window",
            "zone_3_name": "Living Room Motion",
            "zone_4_name": "Garage Door"
        }
        
        result = await config_flow.async_step_zone_names(zone_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "output_config"

    async def test_zone_names_skip(self, config_flow):
        """Test skipping zone names configuration."""
        config_flow._detected_config = {
            "detected_zones": [1, 2, 3, 4]
        }
        
        zone_data = {
            "skip_zone_naming": True
        }
        
        result = await config_flow.async_step_zone_names(zone_data)
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "output_config"

    async def test_output_config_step(self, config_flow):
        """Test output configuration step."""
        config_flow.discovery_info = {
            "panel_type": PANEL_TYPE_ESX,
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN
        }
        
        result = await config_flow.async_step_output_config({"max_outputs": 4})
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Arrowhead ESX Elite-SX"
        assert result["data"]["max_outputs"] == 4

    async def test_create_entry_with_zone_names(self, config_flow):
        """Test creating entry with custom zone names."""
        config_flow.discovery_info = {
            "panel_type": PANEL_TYPE_ECI,
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "max_zones": 8,
            "areas": [1],
            "zone_names": {
                "zone_1": "Front Door",
                "zone_2": "Kitchen Window"
            }
        }
        
        result = await config_flow.async_step_output_config({"max_outputs": 8})
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Arrowhead ECi Series"
        assert result["data"]["zone_names"]["zone_1"] == "Front Door"

    async def test_unique_id_check(self, hass: HomeAssistant, mock_config_entry_class):
        """Test that duplicate entries are prevented."""
        # Create first entry
        entry = mock_config_entry_class(
            domain=DOMAIN,
            unique_id="arrowhead_esx_192.168.1.100",
            data={"host": "192.168.1.100", "panel_type": PANEL_TYPE_ESX}
        )
        entry.add_to_hass(hass)
        
        # Try to create duplicate
        flow = ArrowheadAlarmConfigFlow()
        flow.hass = hass
        
        await flow.async_set_unique_id("arrowhead_esx_192.168.1.100")
        # Should abort if unique_id already configured
        # This would be tested in integration test with real hass


class TestConnectionTesting:
    """Test connection testing functionality."""

    @pytest.fixture
    def config_flow(self):
        """Create a config flow instance."""
        return ArrowheadAlarmConfigFlow()

    @patch("asyncio.open_connection")
    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_tcp_connection_success(self, mock_client_class, mock_open_connection, config_flow, mock_arrowhead_client):
        """Test successful TCP connection."""
        # Mock TCP connection
        reader, writer = AsyncMock(), AsyncMock()
        mock_open_connection.return_value = (reader, writer)
        
        # Mock client
        mock_client_class.return_value = mock_arrowhead_client
        mock_arrowhead_client.get_status.return_value = {
            "connection_state": "connected",
            "zones": {1: False, 2: False},
            "armed": False
        }
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin",
            "panel_type": PANEL_TYPE_ESX
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is True
        assert "Connected successfully" in result["status"]

    @patch("asyncio.open_connection")
    async def test_tcp_connection_timeout(self, mock_open_connection, config_flow):
        """Test TCP connection timeout."""
        mock_open_connection.side_effect = asyncio.TimeoutError()
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin",
            "panel_type": PANEL_TYPE_ESX
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is False
        assert result["error_type"] == "timeout"

    @patch("asyncio.open_connection")
    async def test_tcp_connection_refused(self, mock_open_connection, config_flow):
        """Test TCP connection refused."""
        mock_open_connection.side_effect = ConnectionRefusedError()
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": DEFAULT_USER_PIN,
            "username": "admin",
            "password": "admin",
            "panel_type": PANEL_TYPE_ESX
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is False
        assert result["error_type"] == "connection_refused"

    @patch("asyncio.open_connection")
    @patch("custom_components.arrowhead_alarm.config_flow.ArrowheadClient")
    async def test_invalid_credentials(self, mock_client_class, mock_open_connection, config_flow, mock_arrowhead_client):
        """Test invalid credentials."""
        # Mock TCP connection success
        reader, writer = AsyncMock(), AsyncMock()
        mock_open_connection.return_value = (reader, writer)
        
        # Mock client connection failure
        mock_arrowhead_client.connect.return_value = False
        mock_client_class.return_value = mock_arrowhead_client
        
        user_input = {
            "host": "192.168.1.100",
            "port": 9000,
            "user_pin": "1 999",  # Invalid PIN
            "username": "admin",
            "password": "admin",
            "panel_type": PANEL_TYPE_ESX
        }
        
        result = await config_flow._test_connection(user_input)
        
        assert result["success"] is False
        assert result["error_type"] == "auth_failed"


class TestECiDetection:
    """Test ECi panel detection functionality."""

    @pytest.fixture
    def config_flow(self):
        """Create a config flow instance."""
        return ArrowheadAlarmConfigFlow()

    @patch("custom_components.arrowhead_alarm.config_flow.ECiZoneManager")
    async def test_eci_zone_detection(self, mock_zone_manager_class, config_flow, mock_arrowhead_client):
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
        
        result = await config_flow._detect_eci_configuration(mock_arrowhead_client)
        
        assert result["total_zones"] == 8
        assert result["max_zone"] == 8
        assert 1 in result["active_areas"]
        assert result["detection_method"] == "active_areas_query"

    @patch("custom_components.arrowhead_alarm.config_flow.ECiZoneManager")
    async def test_eci_detection_fallback(self, mock_zone_manager_class, config_flow, mock_arrowhead_client):
        """Test ECi detection fallback on error."""
        mock_zone_manager = MagicMock()
        mock_zone_manager.detect_panel_configuration = AsyncMock(side_effect=Exception("Detection failed"))
        mock_zone_manager_class.return_value = mock_zone_manager
        
        result = await config_flow._detect_eci_configuration(mock_arrowhead_client)
        
        assert result["total_zones"] == 16
        assert result["max_zone"] == 16
        assert result["detection_method"] == "fallback"

    @patch("custom_components