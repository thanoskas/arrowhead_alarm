"""Test the ECi zone detection functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from custom_components.arrowhead_alarm.eci_zone_detection import (
    ECiZoneManager,
    ECiConfigurationManager,
)


class TestECiZoneManager:
    """Test the ECi zone manager."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock ECi client."""
        client = MagicMock()
        client._send_command = AsyncMock()
        client._status = {
            "zones": {},
            "zone_alarms": {},
            "zone_troubles": {},
            "zone_bypassed": {},
        }
        return client

    @pytest.fixture
    def zone_manager(self, mock_client):
        """Create a zone manager instance."""
        return ECiZoneManager(mock_client)

    async def test_detect_panel_configuration_success(self, zone_manager, mock_client):
        """Test successful panel configuration detection."""
        # Mock active areas query response
        mock_client._send_command.side_effect = [
            "P4076E1=1,2",  # Active areas response
            "P4075E1=1,2,3,4",  # Zones in area 1
            "P4075E2=5,6,7,8",  # Zones in area 2
        ]
        
        config = await zone_manager.detect_panel_configuration()
        
        assert config["active_areas"] == {1, 2}
        assert config["detected_zones"] == {1, 2, 3, 4, 5, 6, 7, 8}
        assert config["total_zones"] == 8
        assert config["max_zone"] == 8
        assert config["detection_method"] == "active_areas_query"

    async def test_detect_panel_configuration_single_area(self, zone_manager, mock_client):
        """Test detection with single area."""
        mock_client._send_command.side_effect = [
            "P4076E1=1",  # Single active area
            "P4075E1=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16",  # All zones in area 1
        ]
        
        config = await zone_manager.detect_panel_configuration()
        
        assert config["active_areas"] == {1}
        assert len(config["detected_zones"]) == 16
        assert config["max_zone"] == 16

    async def test_detect_panel_configuration_no_areas(self, zone_manager, mock_client):
        """Test detection with no configured areas."""
        mock_client._send_command.side_effect = [
            "P4076E1=0",  # No areas configured
        ]
        
        config = await zone_manager.detect_panel_configuration()
        
        assert config["active_areas"] == {1}  # Should default to area 1
        assert config["detection_method"] == "active_areas_query"

    async def test_detect_panel_configuration_fallback_to_status(self, zone_manager, mock_client):
        """Test fallback to status parsing when area query fails."""
        # Mock failed area query but successful status parsing
        mock_client._send_command.side_effect = [
            "",  # Empty response for area query
        ]
        
        # Mock status data with zones
        mock_client._status = {
            "zones": {1: False, 2: True, 3: False, 4: True},
            "zone_alarms": {1: False, 2: False, 3: False, 4: False},
            "zone_troubles": {},
            "zone_bypassed": {},
        }
        
        config = await zone_manager.detect_panel_configuration()
        
        assert config["detected_zones"] == {1, 2, 3, 4}
        assert config["total_zones"] == 4
        assert config["detection_method"] == "status_parsing"

    async def test_detect_panel_configuration_error_fallback(self, zone_manager, mock_client):
        """Test error fallback configuration."""
        # Mock exception during detection
        mock_client._send_command.side_effect = Exception("Communication error")
        
        config = await zone_manager.detect_panel_configuration()
        
        assert config["detected_zones"] == set(range(1, 17))  # Safe default
        assert config["total_zones"] == 16
        assert config["max_zone"] == 16
        assert config["detection_method"] == "fallback"

    async def test_query_active_areas_success(self, zone_manager, mock_client):
        """Test successful active areas query."""
        mock_client._send_command.return_value = "P4076E1=1,2,3"
        
        result = await zone_manager._query_active_areas()
        
        assert result["success"] is True
        assert result["active_areas"] == {1, 2, 3}

    async def test_query_active_areas_no_areas(self, zone_manager, mock_client):
        """Test active areas query with no areas."""
        mock_client._send_command.return_value = "P4076E1=0"
        
        result = await zone_manager._query_active_areas()
        
        assert result["success"] is True
        assert result["active_areas"] == {1}  # Default to area 1

    async def test_query_active_areas_failure(self, zone_manager, mock_client):
        """Test active areas query failure."""
        mock_client._send_command.side_effect = Exception("Query failed")
        
        result = await zone_manager._query_active_areas()
        
        assert result["success"] is False
        assert result["active_areas"] == set()

    async def test_query_zones_in_area_success(self, zone_manager, mock_client):
        """Test successful zones in area query."""
        mock_client._send_command.return_value = "P4075E1=1,2,3,4,5"
        
        result = await zone_manager._query_zones_in_area(1)
        
        assert result["success"] is True
        assert result["zones"] == {1, 2, 3, 4, 5}

    async def test_query_zones_in_area_no_zones(self, zone_manager, mock_client):
        """Test zones in area query with no zones."""
        mock_client._send_command.return_value = "P4075E1=0"
        
        result = await zone_manager._query_zones_in_area(1)
        
        assert result["success"] is True
        assert result["zones"] == set()

    async def test_query_zones_in_area_failure(self, zone_manager, mock_client):
        """Test zones in area query failure."""
        mock_client._send_command.side_effect = Exception("Query failed")
        
        result = await zone_manager._query_zones_in_area(1)
        
        assert result["success"] is False
        assert result["zones"] == set()

    async def test_parse_status_for_zones(self, zone_manager, mock_client):
        """Test parsing status for zone detection."""
        # Mock client status with various zone data
        mock_client._status = {
            "zones": {1: False, 2: True, 5: False},
            "zone_alarms": {3: False, 4: True},
            "zone_troubles": {6: True},
            "zone_bypassed": {7: False, 8: True},
        }
        
        result = await zone_manager._parse_status_for_zones()
        
        assert result["success"] is True
        detected = result["zones"]
        assert 1 in detected  # From zones
        assert 2 in detected  # From zones
        assert 3 in detected  # From zone_alarms
        assert 4 in detected  # From zone_alarms
        assert 6 in detected  # From zone_troubles
        assert 7 in detected  # From zone_bypassed
        assert 8 in detected  # From zone_bypassed

    async def test_parse_status_for_zones_with_limits(self, zone_manager, mock_client):
        """Test status parsing respects zone limits."""
        # Mock status with zones beyond reasonable limits
        mock_client._status = {
            "zones": {1: False, 250: True, 999: False},  # 250 and 999 should be filtered
            "zone_alarms": {},
            "zone_troubles": {},
            "zone_bypassed": {},
        }
        
        result = await zone_manager._parse_status_for_zones()
        
        assert result["success"] is True
        detected = result["zones"]
        assert 1 in detected
        assert 250 not in detected  # Beyond 248 limit
        assert 999 not in detected  # Beyond 248 limit

    def test_detect_expanders_no_zones(self, zone_manager):
        """Test expander detection with no zones."""
        expanders = zone_manager._detect_expanders(set())
        
        assert expanders == []

    def test_detect_expanders_main_panel_only(self, zone_manager):
        """Test expander detection with main panel zones only."""
        zones = {1, 2, 3, 4, 8, 12, 16}  # All within main panel range (1-16)
        
        expanders = zone_manager._detect_expanders(zones)
        
        assert expanders == []  # No expanders needed

    def test_detect_expanders_with_expanders(self, zone_manager):
        """Test expander detection with expander zones."""
        zones = {1, 2, 16, 17, 18, 32, 33, 48}  # Spans multiple expanders
        
        expanders = zone_manager._detect_expanders(zones)
        
        assert len(expanders) == 3  # Should detect 3 expanders
        
        # Check first expander (zones 17-32)
        exp1 = next(e for e in expanders if e["name"] == "zone_expander_1")
        assert exp1["zones"] == {17, 18, 32}
        
        # Check second expander (zones 33-48)
        exp2 = next(e for e in expanders if e["name"] == "zone_expander_2")
        assert exp2["zones"] == {33, 48}


class TestECiConfigurationManager:
    """Test the ECi configuration manager."""

    @pytest.fixture
    def config_manager(self):
        """Create a configuration manager instance."""
        return ECiConfigurationManager()

    @pytest.fixture
    def mock_client(self):
        """Create a mock client."""
        return MagicMock()

    def test_set_user_preferences_auto_detect(self, config_manager):
        """Test setting user preferences with auto-detect."""
        config_manager.set_user_preferences(
            max_zones=32,
            areas=[1, 2, 3],
            auto_detect=True
        )
        
        assert config_manager.auto_detect is True
        assert config_manager.user_max_zones == 32
        assert config_manager.user_areas == {1, 2, 3}

    def test_set_user_preferences_manual(self, config_manager):
        """Test setting user preferences for manual configuration."""
        config_manager.set_user_preferences(
            max_zones=64,
            areas=[1, 4],
            auto_detect=False
        )
        
        assert config_manager.auto_detect is False
        assert config_manager.user_max_zones == 64
        assert config_manager.user_areas == {1, 4}

    async def test_get_panel_configuration_auto_detect(self, config_manager, mock_client):
        """Test getting panel configuration with auto-detect."""
        config_manager.auto_detect = True
        config_manager.user_max_zones = 24
        config_manager.user_areas = {1, 2}
        
        # Mock zone manager
        with patch("custom_components.arrowhead_alarm.eci_zone_detection.ECiZoneManager") as mock_manager_class:
            mock_manager = MagicMock()
            mock_manager.detect_panel_configuration = AsyncMock(return_value={
                "detected_zones": set(range(1, 17)),
                "active_areas": {1},
                "max_zone": 16,
                "total_zones": 16,
                "detection_method": "active_areas_query"
            })
            mock_manager_class.return_value = mock_manager
            
            config = await config_manager.get_panel_configuration(mock_client)
            
            assert config["max_zone"] == 16  # Should use detected, not user override (24)
            assert config["active_areas"] == {1, 2}  # Should use user override

    async def test_get_panel_configuration_manual(self, config_manager, mock_client):
        """Test getting panel configuration with manual settings."""
        config_manager.auto_detect = False
        config_manager.user_max_zones = 32
        config_manager.user_areas = {1, 2, 3}
        
        config = await config_manager.get_panel_configuration(mock_client)
        
        assert config["max_zone"] == 32
        assert config["active_areas"] == {1, 2, 3}
        assert config["total_zones"] == 32
        assert config["detection_method"] == "manual"

    def test_apply_user_overrides_max_zones(self, config_manager):
        """Test applying user max zones override."""
        config_manager.user_max_zones = 24
        
        detected_config = {
            "detected_zones": set(range(1, 33)),  # 32 zones detected
            "max_zone": 32,
            "total_zones": 32,
            "active_areas": {1}
        }
        
        final_config = config_manager._apply_user_overrides(detected_config)
        
        assert final_config["max_zone"] == 24  # Limited by user
        assert len(final_config["detected_zones"]) == 24  # Filtered to user limit

    def test_apply_user_overrides_areas(self, config_manager):
        """Test applying user areas override."""
        config_manager.user_areas = {2, 3, 4}
        
        detected_config = {
            "detected_zones": set(range(1, 17)),
            "max_zone": 16,
            "total_zones": 16,
            "active_areas": {1}
        }
        
        final_config = config_manager._apply_user_overrides(detected_config)
        
        assert final_config["active_areas"] == {2, 3, 4}  # User override

    def test_create_manual_configuration_single_area(self, config_manager):
        """Test creating manual configuration with single area."""
        config_manager.user_max_zones = 16
        config_manager.user_areas = {1}
        
        config = config_manager._create_manual_configuration()
        
        assert config["max_zone"] == 16
        assert config["active_areas"] == {1}
        assert config["total_zones"] == 16
        assert config["detected_zones"] == set(range(1, 17))
        assert config["zones_in_areas"][1] == set(range(1, 17))
        assert config["detection_method"] == "manual"

    def test_create_manual_configuration_multiple_areas(self, config_manager):
        """Test creating manual configuration with multiple areas."""
        config_manager.user_max_zones = 32
        config_manager.user_areas = {1, 2}
        
        config = config_manager._create_manual_configuration()
        
        assert config["max_zone"] == 32
        assert config["active_areas"] == {1, 2}
        assert config["total_zones"] == 32
        
        # Zones should be distributed across areas
        assert len(config["zones_in_areas"][1]) == 16  # First 16 zones to area 1
        assert len(config["zones_in_areas"][2]) == 16  # Next 16 zones to area 2

    def test_create_manual_configuration_uneven_distribution(self, config_manager):
        """Test manual configuration with uneven zone distribution."""
        config_manager.user_max_zones = 25  # Not evenly divisible by areas
        config_manager.user_areas = {1, 2, 3}
        
        config = config_manager._create_manual_configuration()
        
        assert config["max_zone"] == 25
        assert config["total_zones"] == 25
        
        # Last area should get remaining zones
        area_zones = config["zones_in_areas"]
        total_distributed = sum(len(zones) for zones in area_zones.values())
        assert total_distributed == 25

    def test_validate_configuration_valid(self, config_manager):
        """Test validation of valid configuration."""
        config = {
            "detected_zones": set(range(1, 17)),
            "active_areas": {1},
            "zones_in_areas": {1: set(range(1, 17))},
            "max_zone": 16,
            "total_zones": 16
        }
        
        validated = config_manager._validate_configuration(config)
        
        assert validated["detected_zones"] == set(range(1, 17))
        assert validated["active_areas"] == {1}
        assert validated["max_zone"] == 16

    def test_validate_configuration_empty_zones(self, config_manager):
        """Test validation fixes empty zones."""
        config = {
            "detected_zones": set(),
            "active_areas": set(),
            "zones_in_areas": {},
            "max_zone": 0,
            "total_zones": 0
        }
        
        validated = config_manager._validate_configuration(config)
        
        # Should fix empty configuration
        assert validated["detected_zones"] == set(range(1, 17))
        assert validated["active_areas"] == {1}
        assert validated["zones_in_areas"] == {1: set(range(1, 17))}
        assert validated["max_zone"] == 16

    def test_validate_configuration_zone_limit(self, config_manager):
        """Test validation enforces zone limits."""
        config = {
            "detected_zones": set(range(1, 300)),  # Beyond 248 limit
            "active_areas": {1},
            "zones_in_areas": {1: set(range(1, 300))},
            "max_zone": 300,
            "total_zones": 299
        }
        
        validated = config_manager._validate_configuration(config)
        
        # Should limit to 248
        assert validated["max_zone"] == 248
        assert max(validated["detected_zones"]) <= 248
        assert validated["total_zones"] <= 248

    def test_validate_configuration_negative_max_zone(self, config_manager):
        """Test validation fixes negative max zone."""
        config = {
            "detected_zones": set(),
            "active_areas": {1},
            "zones_in_areas": {1: set()},
            "max_zone": -5,
            "total_zones": 0
        }
        
        validated = config_manager._validate_configuration(config)
        
        assert validated["max_zone"] == 16  # Should default to 16


class TestECiDetectionIntegration:
    """Test ECi detection integration scenarios."""

    @pytest.fixture
    def mock_client_with_responses(self):
        """Create a mock client with realistic responses."""
        client = MagicMock()
        client._send_command = AsyncMock()
        client._status = {
            "zones": {},
            "zone_alarms": {},
            "zone_troubles": {},
            "zone_bypassed": {},
        }
        return client

    async def test_detection_scenario_small_system(self, mock_client_with_responses):
        """Test detection for small system (single area, few zones)."""
        client = mock_client_with_responses
        
        # Mock responses for small system
        client._send_command.side_effect = [
            "P4076E1=1",  # Single area
            "P4075E1=1,2,3,4,5,6,7,8",  # 8 zones in area 1
        ]
        
        zone_manager = ECiZoneManager(client)
        config = await zone_manager.detect_panel_configuration()
        
        assert config["active_areas"] == {1}
        assert config["detected_zones"] == {1, 2, 3, 4, 5, 6, 7, 8}
        assert config["max_zone"] == 8
        assert config["total_zones"] == 8
        assert len(config["expanders_detected"]) == 0  # No expanders needed

    async def test_detection_scenario_medium_system(self, mock_client_with_responses):
        """Test detection for medium system (multiple areas, expanders)."""
        client = mock_client_with_responses
        
        # Mock responses for medium system
        client._send_command.side_effect = [
            "P4076E1=1,2",  # Two areas
            "P4075E1=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16",  # Area 1: main panel
            "P4075E2=17,18,19,20,21,22,23,24",  # Area 2: first expander
        ]
        
        zone_manager = ECiZoneManager(client)
        config = await zone_manager.detect_panel_configuration()
        
        assert config["active_areas"] == {1, 2}
        assert config["max_zone"] == 24
        assert config["total_zones"] == 24
        assert len(config["expanders_detected"]) == 1  # One expander detected
        
        # Check expander details
        expander = config["expanders_detected"][0]
        assert expander["name"] == "zone_expander_1"
        assert expander["zones"] == {17, 18, 19, 20, 21, 22, 23, 24}

    async def test_detection_scenario_large_system(self, mock_client_with_responses):
        """Test detection for large system (multiple areas, multiple expanders)."""
        client = mock_client_with_responses
        
        # Mock responses for large system
        client._send_command.side_effect = [
            "P4076E1=1,2,3,4",  # Four areas
            "P4075E1=1,2,3,4,5,6,7,8",  # Area 1: partial main panel
            "P4075E2=9,10,11,12,13,14,15,16",  # Area 2: rest of main panel
            "P4075E3=17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32",  # Area 3: expander 1
            "P4075E4=33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48",  # Area 4: expander 2
        ]
        
        zone_manager = ECiZoneManager(client)
        config = await zone_manager.detect_panel_configuration()
        
        assert config["active_areas"] == {1, 2, 3, 4}
        assert config["max_zone"] == 48
        assert config["total_zones"] == 48
        assert len(config["expanders_detected"]) == 2  # Two expanders

    async def test_detection_scenario_communication_failure(self, mock_client_with_responses):
        """Test detection with communication failures and recovery."""
        client = mock_client_with_responses
        
        # Mock area query failure but status parsing success
        client._send_command.side_effect = Exception("Communication timeout")
        client._status = {
            "zones": {i: False for i in range(1, 9)},  # 8 zones from status
            "zone_alarms": {},
            "zone_troubles": {},
            "zone_bypassed": {},
        }
        
        zone_manager = ECiZoneManager(client)
        config = await zone_manager.detect_panel_configuration()
        
        # Should fall back to status parsing
        assert config["detected_zones"] == set(range(1, 9))
        assert config["detection_method"] == "status_parsing"
        assert config["total_zones"] == 8

    async def test_detection_scenario_partial_failure(self, mock_client_with_responses):
        """Test detection with partial communication failure."""
        client = mock_client_with_responses
        
        def mock_command_responses(command):
            if "P4076E1" in command:
                return "P4076E1=1,2,3"  # Areas query succeeds
            elif "P4075E1" in command:
                return "P4075E1=1,2,3,4"  # Area 1 query succeeds
            elif "P4075E2" in command:
                raise Exception("Area 2 query failed")  # Area 2 fails
            elif "P4075E3" in command:
                return "P4075E3=9,10,11,12"  # Area 3 succeeds
            else:
                return ""
        
        client._send_command.side_effect = mock_command_responses
        
        zone_manager = ECiZoneManager(client)
        config = await zone_manager.detect_panel_configuration()
        
        # Should get zones from successful queries only
        assert 1 in config["detected_zones"]  # From area 1
        assert 2 in config["detected_zones"]  # From area 1
        assert 9 in config["detected_zones"]  # From area 3
        assert 10 in config["detected_zones"]  # From area 3
        
        # Should still show all requested areas
        assert config["active_areas"] == {1, 2, 3}

    async def test_configuration_manager_with_overrides(self, mock_client_with_responses):
        """Test configuration manager applying user overrides."""
        client = mock_client_with_responses
        
        # Mock detection of large system
        client._send_command.side_effect = [
            "P4076E1=1,2",
            "P4075E1=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16",
            "P4075E2=17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32",
        ]
        
        config_manager = ECiConfigurationManager()
        config_manager.set_user_preferences(
            max_zones=20,  # User wants to limit to 20 zones
            areas=[1],     # User wants only area 1
            auto_detect=True
        )
        
        config = await config_manager.get_panel_configuration(client)
        
        # Should apply user limits
        assert config["max_zone"] == 20  # Limited by user
        assert config["active_areas"] == {1}  # Limited by user
        assert len(config["detected_zones"]) == 20  # Filtered to user limit

    async def test_configuration_caching(self, mock_client_with_responses):
        """Test that configuration manager caches results."""
        client = mock_client_with_responses
        client._send_command.side_effect = [
            "P4076E1=1",
            "P4075E1=1,2,3,4",
        ]
        
        config_manager = ECiConfigurationManager()
        
        # First call should perform detection
        config1 = await config_manager.get_panel_configuration(client)
        
        # Second call should use cache (no additional client calls)
        config2 = await config_manager.get_panel_configuration(client)
        
        assert config1 == config2
        assert config_manager.detection_cache is not None