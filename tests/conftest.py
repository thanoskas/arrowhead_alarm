"""Global fixtures for Arrowhead Alarm Panel integration tests."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from custom_components.arrowhead_alarm.const import (
    DOMAIN,
    CONF_USER_PIN,
    CONF_PANEL_TYPE,
    PANEL_TYPE_ESX,
    PANEL_TYPE_ECI,
    DEFAULT_USER_PIN,
    DEFAULT_USERNAME,
    DEFAULT_PASSWORD,
)


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 9000,
        CONF_USER_PIN: DEFAULT_USER_PIN,
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
        CONF_PANEL_TYPE: PANEL_TYPE_ESX,
        "max_outputs": 4,
    }


@pytest.fixture
def mock_esx_config_entry():
    """Return a mock ESX config entry."""
    return {
        CONF_HOST: "192.168.1.100",
        CONF_PORT: 9000,
        CONF_USER_PIN: DEFAULT_USER_PIN,
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
        CONF_PANEL_TYPE: PANEL_TYPE_ESX,
        "max_outputs": 4,
    }


@pytest.fixture
def mock_eci_config_entry():
    """Return a mock ECi config entry."""
    return {
        CONF_HOST: "192.168.1.101",
        CONF_PORT: 9000,
        CONF_USER_PIN: DEFAULT_USER_PIN,
        "username": DEFAULT_USERNAME,
        "password": DEFAULT_PASSWORD,
        CONF_PANEL_TYPE: PANEL_TYPE_ECI,
        "max_zones": 32,
        "areas": [1, 2],
        "auto_detect_zones": True,
        "max_outputs": 8,
    }


@pytest.fixture
def mock_panel_status():
    """Return mock panel status data."""
    return {
        "armed": False,
        "arming": False,
        "stay_mode": False,
        "ready_to_arm": True,
        "alarm": False,
        "status_message": "System Ready",
        "panel_type": PANEL_TYPE_ESX,
        "panel_name": "ESX Elite-SX",
        "connection_state": "connected",
        "zones": {1: False, 2: False, 3: True, 4: False},
        "zone_alarms": {1: False, 2: False, 3: False, 4: False},
        "zone_troubles": {1: False, 2: False, 3: False, 4: False},
        "zone_bypassed": {1: False, 2: True, 3: False, 4: False},
        "outputs": {1: False, 2: False, 3: False, 4: False},
        "battery_ok": True,
        "mains_ok": True,
        "tamper_alarm": False,
        "line_ok": True,
        "dialer_ok": True,
        "fuse_ok": True,
        "last_update": "2025-01-01T12:00:00Z",
        "communication_errors": 0,
    }


@pytest.fixture
def mock_arrowhead_client():
    """Return a mock ArrowheadClient."""
    client = MagicMock()
    client.host = "192.168.1.100"
    client.port = 9000
    client.panel_type = PANEL_TYPE_ESX
    client.is_connected = True
    client.connection_state = "connected"
    
    # Mock async methods
    client.connect = AsyncMock(return_value=True)
    client.disconnect = AsyncMock()
    client.get_status = AsyncMock()
    client.arm_away = AsyncMock(return_value=True)
    client.arm_stay = AsyncMock(return_value=True)
    client.disarm = AsyncMock(return_value=True)
    client.bypass_zone = AsyncMock(return_value=True)
    client.unbypass_zone = AsyncMock(return_value=True)
    client.trigger_output = AsyncMock(return_value=True)
    client.turn_output_on = AsyncMock(return_value=True)
    client.turn_output_off = AsyncMock(return_value=True)
    
    return client


@pytest.fixture
def mock_coordinator(mock_arrowhead_client, mock_panel_status):
    """Return a mock ArrowheadDataUpdateCoordinator."""
    coordinator = MagicMock()
    coordinator.client = mock_arrowhead_client
    coordinator.data = mock_panel_status
    coordinator.last_update_success = True
    coordinator.connection_state = "connected"
    
    # Mock async methods
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_setup = AsyncMock()
    coordinator.async_shutdown = AsyncMock()
    coordinator.async_arm_away = AsyncMock(return_value=True)
    coordinator.async_arm_stay = AsyncMock(return_value=True)
    coordinator.async_disarm = AsyncMock(return_value=True)
    coordinator.async_bypass_zone = AsyncMock(return_value=True)
    coordinator.async_unbypass_zone = AsyncMock(return_value=True)
    coordinator.async_trigger_output = AsyncMock(return_value=True)
    
    return coordinator


@pytest.fixture
def mock_config_entry_obj(mock_config_entry):
    """Return a mock ConfigEntry object."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.domain = DOMAIN
    entry.data = mock_config_entry
    entry.options = {}
    entry.title = "Arrowhead ESX Elite-SX"
    entry.unique_id = f"arrowhead_{PANEL_TYPE_ESX}_192.168.1.100"
    return entry


@pytest.fixture
def mock_hass_data(mock_coordinator, mock_arrowhead_client):
    """Return mock hass.data structure."""
    from custom_components.arrowhead_alarm.const import PANEL_CONFIGS
    
    return {
        DOMAIN: {
            "test_entry_id": {
                "coordinator": mock_coordinator,
                "client": mock_arrowhead_client,
                "panel_config": PANEL_CONFIGS[PANEL_TYPE_ESX],
            }
        }
    }


@pytest.fixture
async def mock_hass(mock_hass_data):
    """Return a mock HomeAssistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.data = mock_hass_data
    hass.config_entries = MagicMock()
    hass.states = MagicMock()
    hass.services = MagicMock()
    
    # Mock async methods
    hass.async_add_executor_job = AsyncMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    
    return hass


@pytest.fixture
def mock_zone_manager():
    """Return a mock ECiZoneManager."""
    manager = MagicMock()
    manager.detect_panel_configuration = AsyncMock(return_value={
        "detected_zones": {1, 2, 3, 4, 5, 6, 7, 8},
        "active_areas": {1},
        "zones_in_areas": {1: {1, 2, 3, 4, 5, 6, 7, 8}},
        "max_zone": 8,
        "total_zones": 8,
        "expanders_detected": [],
        "detection_method": "active_areas_query"
    })
    return manager


@pytest.fixture
def mock_tcp_connection():
    """Mock TCP connection for testing."""
    reader = AsyncMock()
    writer = AsyncMock()
    
    # Mock successful connection
    with patch("asyncio.open_connection", return_value=(reader, writer)):
        yield reader, writer


@pytest.fixture
def panel_responses():
    """Return mock panel responses for different scenarios."""
    return {
        "login_prompt": "login:",
        "password_prompt": "password:",
        "welcome": "Welcome to Arrowhead Alarm Panel",
        "status_ready": "RO",  # Ready to arm
        "status_not_ready": "NR",  # Not ready
        "zone_open": "ZO001",  # Zone 1 open
        "zone_close": "ZC001",  # Zone 1 close
        "zone_alarm": "ZA001",  # Zone 1 alarm
        "zone_alarm_restore": "ZR001",  # Zone 1 alarm restore
        "output_on": "OO1",  # Output 1 on
        "output_off": "OR1",  # Output 1 off
        "arm_away_ok": "OK ArmAway",
        "arm_stay_ok": "OK ArmStay",
        "disarm_ok": "OK Disarm",
        "bypass_ok": "OK Bypass 001",
        "unbypass_ok": "OK Unbypass 001",
        "error": "ERROR",
        "timeout": None,
    }


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


class MockConfigEntry:
    """Mock ConfigEntry for testing."""
    
    def __init__(self, **kwargs):
        self.entry_id = kwargs.get("entry_id", "test_entry_id")
        self.domain = kwargs.get("domain", DOMAIN)
        self.data = kwargs.get("data", {})
        self.options = kwargs.get("options", {})
        self.title = kwargs.get("title", "Test Entry")
        self.unique_id = kwargs.get("unique_id")
        self.version = kwargs.get("version", 1)
        self.source = kwargs.get("source", "user")
        self.state = kwargs.get("state", "loaded")
        
    def add_to_hass(self, hass):
        """Add this entry to hass."""
        if not hasattr(hass, "config_entries"):
            hass.config_entries = MagicMock()
        if not hasattr(hass.config_entries, "async_entries"):
            hass.config_entries.async_entries = MagicMock(return_value=[self])
        if not hasattr(hass, "data"):
            hass.data = {}
        
    async def async_unload(self, hass):
        """Unload this entry."""
        return True
        
    def async_on_unload(self, func):
        """Register unload callback."""
        pass
        
    def add_update_listener(self, func):
        """Add update listener."""
        pass


@pytest.fixture
def mock_config_entry_class():
    """Return MockConfigEntry class."""
    return MockConfigEntry