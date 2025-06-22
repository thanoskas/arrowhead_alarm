"""Test the Arrowhead Alarm Panel client."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

from custom_components.arrowhead_alarm.arrowhead_client import (
    ArrowheadClient,
    ConnectionState,
    ProtocolMode,
)
from custom_components.arrowhead_alarm.const import (
    PANEL_TYPE_ESX,
    PANEL_TYPE_ECI,
    DEFAULT_USER_PIN,
)


class TestArrowheadClient:
    """Test the ArrowheadClient class."""

    @pytest.fixture
    def esx_client(self):
        """Create an ESX client instance."""
        return ArrowheadClient(
            host="192.168.1.100",
            port=9000,
            user_pin=DEFAULT_USER_PIN,
            username="admin",
            password="admin",
            panel_type=PANEL_TYPE_ESX
        )

    @pytest.fixture
    def eci_client(self):
        """Create an ECi client instance."""
        return ArrowheadClient(
            host="192.168.1.101",
            port=9000,
            user_pin=DEFAULT_USER_PIN,
            username="admin",
            password="admin",
            panel_type=PANEL_TYPE_ECI
        )

    def test_client_initialization_esx(self, esx_client):
        """Test ESX client initialization."""
        assert esx_client.host == "192.168.1.100"
        assert esx_client.port == 9000
        assert esx_client.panel_type == PANEL_TYPE_ESX
        assert esx_client.protocol_mode == ProtocolMode.MODE_1
        assert esx_client.is_connected is False
        assert esx_client._connection_state == ConnectionState.DISCONNECTED

    def test_client_initialization_eci(self, eci_client):
        """Test ECi client initialization."""
        assert eci_client.host == "192.168.1.101"
        assert eci_client.panel_type == PANEL_TYPE_ECI
        assert eci_client.protocol_mode == ProtocolMode.MODE_1
        assert eci_client.is_connected is False

    def test_initial_status_esx(self, esx_client):
        """Test initial status for ESX client."""
        status = esx_client._status
        
        assert status["panel_type"] == PANEL_TYPE_ESX
        assert status["armed"] is False
        assert status["zones"] is not None
        assert len(status["zones"]) == 16  # ESX default
        assert "outputs" in status
        assert status["connection_state"] == "disconnected"

    def test_initial_status_eci(self, eci_client):
        """Test initial status for ECi client."""
        status = eci_client._status
        
        assert status["panel_type"] == PANEL_TYPE_ECI
        assert status["armed"] is False
        assert status["zones"] is not None
        assert len(status["zones"]) == 16  # ECi default
        assert "outputs" in status

    def test_connection_state_property(self, esx_client):
        """Test connection state property."""
        assert esx_client.connection_state == "disconnected"
        
        esx_client._connection_state = ConnectionState.CONNECTED
        assert esx_client.connection_state == "connected"


class TestClientConnection:
    """Test client connection functionality."""

    @pytest.fixture
    def mock_connection(self):
        """Mock asyncio connection."""
        reader = AsyncMock()
        writer = AsyncMock()
        return reader, writer

    @patch("asyncio.open_connection")
    async def test_connect_success_esx(self, mock_open_connection, esx_client, mock_connection):
        """Test successful connection for ESX."""
        reader, writer = mock_connection
        mock_open_connection.return_value = (reader, writer)
        
        # Mock authentication responses
        reader.readline.side_effect = [
            b"Welcome to ESX Panel\n",
            b"RO\n"  # Ready to arm
        ]
        
        with patch.object(esx_client, '_read_response') as mock_read:
            mock_read.return_value = None  # Don't actually start reading
            result = await esx_client.connect()
        
        assert result is True
        assert esx_client.is_connected is True
        assert esx_client._connection_state == ConnectionState.CONNECTED

    @patch("asyncio.open_connection")
    async def test_connect_success_eci(self, mock_open_connection, eci_client, mock_connection):
        """Test successful connection for ECi."""
        reader, writer = mock_connection
        mock_open_connection.return_value = (reader, writer)
        
        # Mock authentication responses
        reader.readline.side_effect = [
            b"Welcome to ECi Panel\n",
            b"RO\n"  # Ready to arm
        ]
        
        with patch.object(eci_client, '_read_response') as mock_read:
            mock_read.return_value = None
            result = await eci_client.connect()
        
        assert result is True
        assert eci_client.is_connected is True

    @patch("asyncio.open_connection")
    async def test_connect_timeout(self, mock_open_connection, esx_client):
        """Test connection timeout."""
        mock_open_connection.side_effect = asyncio.TimeoutError()
        
        result = await esx_client.connect()
        
        assert result is False
        assert esx_client.is_connected is False
        assert esx_client._connection_state == ConnectionState.DISCONNECTED

    @patch("asyncio.open_connection")
    async def test_connect_connection_error(self, mock_open_connection, esx_client):
        """Test connection error."""
        mock_open_connection.side_effect = ConnectionRefusedError()
        
        result = await esx_client.connect()
        
        assert result is False
        assert esx_client.is_connected is False

    async def test_disconnect(self, esx_client):
        """Test client disconnect."""
        # Mock connected state
        esx_client._connection_state = ConnectionState.CONNECTED
        esx_client.writer = MagicMock()
        esx_client.writer.close = MagicMock()
        esx_client.writer.wait_closed = AsyncMock()
        
        await esx_client.disconnect()
        
        assert esx_client._connection_state == ConnectionState.DISCONNECTED
        assert esx_client.writer is None
        assert esx_client.reader is None


class TestClientAuthentication:
    """Test client authentication methods."""

    @pytest.fixture
    def mock_client_with_connection(self, esx_client):
        """Mock client with active connection."""
        esx_client.reader = AsyncMock()
        esx_client.writer = AsyncMock()
        esx_client._response_queue = AsyncMock()
        esx_client._auth_queue = AsyncMock()
        return esx_client

    async def test_handle_login_authentication(self, mock_client_with_connection):
        """Test login-based authentication."""
        client = mock_client_with_connection
        
        # Mock authentication responses
        client._get_next_response.side_effect = [
            "password:",
            "Welcome to panel"
        ]
        
        result = await client._handle_login_authentication("login:")
        
        assert result is True

    async def test_handle_login_authentication_failure(self, mock_client_with_connection):
        """Test failed login authentication."""
        client = mock_client_with_connection
        
        # Mock failed authentication
        client._get_next_response.side_effect = [
            "password:",
            "Authentication failed"
        ]
        
        result = await client._handle_login_authentication("login:")
        
        assert result is False

    async def test_handle_direct_authentication(self, mock_client_with_connection):
        """Test direct authentication."""
        client = mock_client_with_connection
        
        # Mock direct communication
        client._get_next_response.return_value = "RO"  # Ready to arm
        
        result = await client._handle_direct_authentication()
        
        assert result is True

    async def test_handle_direct_authentication_timeout(self, mock_client_with_connection):
        """Test direct authentication timeout."""
        client = mock_client_with_connection
        
        # Mock timeout
        client._get_next_response.side_effect = asyncio.TimeoutError()
        
        result = await client._handle_direct_authentication()
        
        assert result is False


class TestClientCommands:
    """Test client command functionality."""

    @pytest.fixture
    def connected_client(self, esx_client):
        """Create a connected client."""
        esx_client._connection_state = ConnectionState.CONNECTED
        esx_client.writer = MagicMock()
        esx_client.writer.write = MagicMock()
        esx_client.writer.drain = AsyncMock()
        esx_client._get_next_response = AsyncMock()
        return esx_client

    async def test_send_raw_command(self, connected_client):
        """Test sending raw command."""
        await connected_client._send_raw("STATUS\n")
        
        connected_client.writer.write.assert_called_once_with(b"STATUS\n")
        connected_client.writer.drain.assert_called_once()

    async def test_send_command_without_response(self, connected_client):
        """Test sending command without expecting response."""
        result = await connected_client._send_command("STATUS")
        
        assert result is None
        connected_client.writer.write.assert_called_once()

    async def test_send_command_with_response(self, connected_client):
        """Test sending command and expecting response."""
        connected_client._get_next_response.return_value = "RO"
        
        result = await connected_client._send_command("STATUS", expect_response=True)
        
        assert result == "RO"

    async def test_send_command_not_connected(self, esx_client):
        """Test sending command when not connected."""
        with pytest.raises(ConnectionError):
            await esx_client._send_command("STATUS")

    async def test_get_status(self, connected_client):
        """Test get status command."""
        status = await connected_client.get_status()
        
        assert isinstance(status, dict)
        assert "armed" in status
        assert "zones" in status


class TestAlarmCommands:
    """Test alarm control commands."""

    @pytest.fixture
    def connected_client(self, esx_client):
        """Create a connected client."""
        esx_client._connection_state = ConnectionState.CONNECTED
        esx_client.writer = MagicMock()
        esx_client.writer.write = MagicMock()
        esx_client.writer.drain = AsyncMock()
        esx_client._send_command = AsyncMock()
        esx_client.get_status = AsyncMock()
        return esx_client

    async def test_arm_away_success(self, connected_client):
        """Test successful arm away."""
        connected_client._send_command.return_value = "OK ArmAway"
        connected_client.get_status.return_value = {"armed": True, "stay_mode": False}
        
        result = await connected_client.arm_away()
        
        assert result is True

    async def test_arm_away_not_connected(self, esx_client):
        """Test arm away when not connected."""
        result = await esx_client.arm_away()
        
        assert result is False

    async def test_arm_stay_success(self, connected_client):
        """Test successful arm stay."""
        connected_client._send_command.return_value = "OK ArmStay"
        connected_client.get_status.return_value = {"armed": True, "stay_mode": True}
        
        result = await connected_client.arm_stay()
        
        assert result is True

    async def test_arm_stay_panel_rejection(self, connected_client):
        """Test arm stay panel rejection."""
        connected_client._send_command.return_value = "ERROR"
        
        result = await connected_client.arm_stay()
        
        assert result is False

    async def test_disarm_success(self, connected_client):
        """Test successful disarm."""
        connected_client._send_command.return_value = "OK Disarm"
        connected_client.get_status.return_value = {"armed": False}
        
        result = await connected_client.disarm()
        
        assert result is True

    async def test_disarm_invalid_pin(self, connected_client):
        """Test disarm with invalid PIN format."""
        connected_client.user_pin = "invalid"
        
        result = await connected_client.disarm()
        
        assert result is False

    def test_parse_user_pin_valid(self, esx_client):
        """Test parsing valid user PIN."""
        user, pin = esx_client._parse_user_pin("1 123")
        
        assert user == "1"
        assert pin == "123"

    def test_parse_user_pin_invalid(self, esx_client):
        """Test parsing invalid user PIN."""
        user, pin = esx_client._parse_user_pin("invalid")
        
        assert user is None
        assert pin is None


class TestZoneCommands:
    """Test zone control commands."""

    @pytest.fixture
    def connected_client(self, esx_client):
        """Create a connected client."""
        esx_client._connection_state = ConnectionState.CONNECTED
        esx_client.writer = MagicMock()
        esx_client.writer.write = MagicMock()
        esx_client.writer.drain = AsyncMock()
        esx_client._send_command = AsyncMock()
        return esx_client

    async def test_bypass_zone(self, connected_client):
        """Test zone bypass."""
        result = await connected_client.bypass_zone(1)
        
        assert result is True
        connected_client._send_command.assert_called_once_with("BYPASS 001")

    async def test_unbypass_zone(self, connected_client):
        """Test zone unbypass."""
        result = await connected_client.unbypass_zone(15)
        
        assert result is True
        connected_client._send_command.assert_called_once_with("UNBYPASS 015")

    async def test_bypass_zone_exception(self, connected_client):
        """Test zone bypass with exception."""
        connected_client._send_command.side_effect = Exception("Communication error")
        
        result = await connected_client.bypass_zone(1)
        
        assert result is False


class TestOutputCommands:
    """Test output control commands."""

    @pytest.fixture
    def connected_client(self, esx_client):
        """Create a connected client."""
        esx_client._connection_state = ConnectionState.CONNECTED
        esx_client.writer = MagicMock()
        esx_client.writer.write = MagicMock()
        esx_client.writer.drain = AsyncMock()
        esx_client._send_command = AsyncMock()
        return esx_client

    async def test_trigger_output_with_duration(self, connected_client):
        """Test trigger output with duration."""
        result = await connected_client.trigger_output(1, 5)
        
        assert result is True
        connected_client._send_command.assert_called_once_with("OUTPUTON 1 5")

    async def test_trigger_output_toggle(self, connected_client):
        """Test trigger output toggle (no duration)."""
        result = await connected_client.trigger_output(2, 0)
        
        assert result is True
        connected_client._send_command.assert_called_once_with("OUTPUTON 2")

    async def test_turn_output_on(self, connected_client):
        """Test turn output on."""
        result = await connected_client.turn_output_on(3)
        
        assert result is True
        connected_client._send_command.assert_called_once_with("OUTPUTON 3")

    async def test_turn_output_off(self, connected_client):
        """Test turn output off."""
        result = await connected_client.turn_output_off(4)
        
        assert result is True
        connected_client._send_command.assert_called_once_with("OUTPUTOFF 4")

    async def test_output_command_invalid_number(self, connected_client):
        """Test output command with invalid output number."""
        # ESX max outputs is 16
        result = await connected_client.trigger_output(99)
        
        assert result is False


class TestMessageProcessing:
    """Test message processing functionality."""

    @pytest.fixture
    def client_with_status(self, esx_client):
        """Create client with initialized status."""
        return esx_client

    def test_process_system_message_ready(self, client_with_status):
        """Test processing ready to arm message."""
        client_with_status._process_message("RO")
        
        assert client_with_status._status["ready_to_arm"] is True
        assert client_with_status._status["status_message"] == "Ready to Arm"

    def test_process_system_message_not_ready(self, client_with_status):
        """Test processing not ready message."""
        client_with_status._process_message("NR")
        
        assert client_with_status._status["ready_to_arm"] is False
        assert client_with_status._status["status_message"] == "Not Ready"

    def test_process_system_message_power_fail(self, client_with_status):
        """Test processing power fail message."""
        client_with_status._process_message("MF")
        
        assert client_with_status._status["mains_ok"] is False
        assert client_with_status._status["status_message"] == "Mains Power Fail"

    def test_process_zone_message_open(self, client_with_status):
        """Test processing zone open message."""
        client_with_status._process_message("ZO001")
        
        assert client_with_status._status["zones"][1] is True
        assert "Zone 1 Open" in client_with_status._status["status_message"]

    def test_process_zone_message_close(self, client_with_status):
        """Test processing zone close message."""
        # First open the zone
        client_with_status._status["zones"][2] = True
        
        client_with_status._process_message("ZC002")
        
        assert client_with_status._status["zones"][2] is False
        assert "Zone 2 Closed" in client_with_status._status["status_message"]

    def test_process_zone_alarm(self, client_with_status):
        """Test processing zone alarm message."""
        client_with_status._process_message("ZA003")
        
        assert client_with_status._status["zone_alarms"][3] is True
        assert client_with_status._status["alarm"] is True
        assert "Zone 3 Alarm" in client_with_status._status["status_message"]

    def test_process_zone_alarm_restore(self, client_with_status):
        """Test processing zone alarm restore message."""
        # First set alarm
        client_with_status._status["zone_alarms"][3] = True
        client_with_status._status["alarm"] = True
        
        client_with_status._process_message("ZR003")
        
        assert client_with_status._status["zone_alarms"][3] is False
        # Alarm should be False if no other zone alarms
        assert client_with_status._status["alarm"] is False

    def test_process_output_message_on(self, client_with_status):
        """Test processing output on message."""
        # First add output to status
        client_with_status._status["outputs"][1] = False
        
        client_with_status._process_message("OO1")
        
        assert client_with_status._status["outputs"][1] is True
        assert "Output 1 On" in client_with_status._status["status_message"]

    def test_process_output_message_off(self, client_with_status):
        """Test processing output off message."""
        # First add output to status and turn on
        client_with_status._status["outputs"][2] = True
        
        client_with_status._process_message("OR2")
        
        assert client_with_status._status["outputs"][2] is False
        assert "Output 2 Off" in client_with_status._status["status_message"]

    def test_process_arm_away_message(self, client_with_status):
        """Test processing arm away confirmation."""
        client_with_status._process_message("OK ArmAway")
        
        assert client_with_status._status["armed"] is True
        assert client_with_status._status["stay_mode"] is False
        assert client_with_status._status["arming"] is False
        assert client_with_status._status["status_message"] == "Armed Away"

    def test_process_arm_stay_message(self, client_with_status):
        """Test processing arm stay confirmation."""
        client_with_status._process_message("OK ArmStay")
        
        assert client_with_status._status["armed"] is True
        assert client_with_status._status["stay_mode"] is True
        assert client_with_status._status["arming"] is False
        assert client_with_status._status["status_message"] == "Armed Stay"

    def test_process_disarm_message(self, client_with_status):
        """Test processing disarm confirmation."""
        # First arm the system
        client_with_status._status["armed"] = True
        client_with_status._status["alarm"] = True
        
        client_with_status._process_message("OK Disarm")
        
        assert client_with_status._status["armed"] is False
        assert client_with_status._status["alarm"] is False
        assert client_with_status._status["stay_mode"] is False
        assert client_with_status._status["status_message"] == "Disarmed"

    def test_process_invalid_message(self, client_with_status):
        """Test processing invalid message."""
        original_status = client_with_status._status.copy()
        
        client_with_status._process_message("INVALID123")
        
        # Status should be unchanged (except for processing attempt)
        assert client_with_status._status["armed"] == original_status["armed"]
        assert client_with_status._status["ready_to_arm"] == original_status["ready_to_arm"]


class TestManualOutputConfiguration:
    """Test manual output configuration."""

    def test_configure_manual_outputs(self, esx_client):
        """Test manual output configuration."""
        esx_client.configure_manual_outputs(8)
        
        assert len(esx_client._status["outputs"]) == 8
        assert esx_client._status["total_outputs_detected"] == 8
        assert esx_client._status["max_outputs_detected"] == 8
        assert esx_client._status["output_detection_method"] == "manual_configuration"
        
        # Check all outputs are present and initialized to False
        for i in range(1, 9):
            assert i in esx_client._status["outputs"]
            assert esx_client._status["outputs"][i] is False

    def test_configure_manual_outputs_zero(self, esx_client):
        """Test manual output configuration with zero outputs."""
        esx_client.configure_manual_outputs(0)
        
        assert len(esx_client._status["outputs"]) == 0
        assert esx_client._status["total_outputs_detected"] == 0

    def test_configure_manual_outputs_large_number(self, eci_client):
        """Test manual output configuration with large number."""
        eci_client.configure_manual_outputs(32)
        
        assert len(eci_client._status["outputs"]) == 32
        assert exi_client._status["total_outputs_detected"] == 32
        
        # Check range is correct
        assert 1 in eci_client._status["outputs"]
        assert 32 in eci_client._status["outputs"]
        assert 33 not in eci_client._status["outputs"]