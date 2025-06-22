"""ECi Zone Detection and Dynamic Configuration System."""
import asyncio
import logging
import re
from typing import Dict, List, Set, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

class ECiZoneManager:
    """Manage ECi zone detection and configuration."""
    
    def __init__(self, client):
        """Initialize zone manager."""
        self.client = client
        self.detected_zones: Set[int] = set()
        self.active_areas: Set[int] = set()
        self.zones_in_areas: Dict[int, Set[int]] = {}
        self.zone_detection_complete = False
        self.max_detected_zone = 0
        
    async def detect_panel_configuration(self) -> Dict[str, any]:
        """Auto-detect ECi panel configuration including zones and areas."""
        _LOGGER.info("Starting ECi panel configuration detection")
        
        config = {
            "detected_zones": set(),
            "active_areas": set(),
            "zones_in_areas": {},
            "max_zone": 0,
            "total_zones": 0,
            "expanders_detected": [],
            "detection_method": "unknown"
        }
        
        try:
            # Method 1: Query active areas (most reliable)
            areas_result = await self._query_active_areas()
            if areas_result["success"]:
                config.update(areas_result)
                config["detection_method"] = "active_areas_query"
                
                # Method 2: Query zones in each active area
                for area in config["active_areas"]:
                    zones_result = await self._query_zones_in_area(area)
                    if zones_result["success"]:
                        config["zones_in_areas"][area] = zones_result["zones"]
                        config["detected_zones"].update(zones_result["zones"])
                        
            # Method 3: Parse STATUS response for zone states
            status_result = await self._parse_status_for_zones()
            if status_result["success"]:
                config["detected_zones"].update(status_result["zones"])
                if not config["active_areas"]:
                    config["detection_method"] = "status_parsing"
                    
            # Calculate final configuration
            config["max_zone"] = max(config["detected_zones"]) if config["detected_zones"] else 16
            config["total_zones"] = len(config["detected_zones"])
            
            # Detect expanders based on zone ranges
            config["expanders_detected"] = self._detect_expanders(config["detected_zones"])
            
            _LOGGER.info("ECi detection complete: %d zones detected (max: %d), %d areas active", 
                        config["total_zones"], config["max_zone"], len(config["active_areas"]))
                        
            return config
            
        except Exception as err:
            _LOGGER.error("Error during ECi panel detection: %s", err)
            # Return minimal safe configuration
            return {
                "detected_zones": set(range(1, 17)),  # Safe default
                "active_areas": {1},
                "zones_in_areas": {1: set(range(1, 17))},
                "max_zone": 16,
                "total_zones": 16,
                "expanders_detected": [],
                "detection_method": "fallback"
            }

    async def _query_active_areas(self) -> Dict[str, any]:
        """Query active areas using P4076E1 command."""
        try:
            _LOGGER.debug("Querying active areas with P4076E1")
            
            # Send program location query for active areas
            response = await self.client._send_command("P4076E1?", expect_response=True)
            
            if response and "P4076E1=" in response:
                # Parse response: "P4076E1=1,2,3" or "P4076E1=0" for none
                areas_str = response.split("P4076E1=")[1].strip()
                
                if areas_str == "0":
                    active_areas = {1}  # Default to area 1 if none configured
                else:
                    active_areas = set(int(x.strip()) for x in areas_str.split(",") if x.strip().isdigit())
                
                _LOGGER.info("Detected active areas: %s", sorted(active_areas))
                return {
                    "success": True,
                    "active_areas": active_areas
                }
                
        except Exception as err:
            _LOGGER.warning("Failed to query active areas: %s", err)
            
        return {"success": False, "active_areas": set()}

    async def _query_zones_in_area(self, area: int) -> Dict[str, any]:
        """Query zones in specific area using P4075En command."""
        try:
            _LOGGER.debug("Querying zones in area %d with P4075E%d", area, area)
            
            # Send program location query for zones in area
            response = await self.client._send_command(f"P4075E{area}?", expect_response=True)
            
            if response and f"P4075E{area}=" in response:
                # Parse response: "P4075E1=1,2,3,4,5" or "P4075E1=0" for none
                zones_str = response.split(f"P4075E{area}=")[1].strip()
                
                if zones_str == "0":
                    zones = set()
                else:
                    zones = set(int(x.strip()) for x in zones_str.split(",") if x.strip().isdigit())
                
                _LOGGER.info("Area %d contains zones: %s", area, sorted(zones))
                return {
                    "success": True,
                    "zones": zones
                }
                
        except Exception as err:
            _LOGGER.warning("Failed to query zones in area %d: %s", area, err)
            
        return {"success": False, "zones": set()}

    async def _parse_status_for_zones(self) -> Dict[str, any]:
        """Parse STATUS response to detect zones."""
        try:
            _LOGGER.debug("Parsing STATUS response for zone detection")
            
            # Send STATUS command and collect zone messages
            await self.client._send_command("STATUS")
            
            # Wait a bit for all status messages to arrive
            await asyncio.sleep(2)
            
            # Collect zone messages from recent responses
            detected_zones = set()
            
            # Check for zone messages in the status data
            status = self.client._status
            if "zones" in status:
                detected_zones.update(status["zones"].keys())
            if "zone_alarms" in status:
                detected_zones.update(status["zone_alarms"].keys())
            if "zone_troubles" in status:
                detected_zones.update(status["zone_troubles"].keys())
            if "zone_bypassed" in status:
                detected_zones.update(status["zone_bypassed"].keys())
                
            # Filter out zones that are beyond reasonable limits
            detected_zones = {z for z in detected_zones if 1 <= z <= 248}
            
            _LOGGER.info("Detected zones from STATUS: %s", sorted(detected_zones))
            return {
                "success": True,
                "zones": detected_zones
            }
            
        except Exception as err:
            _LOGGER.warning("Failed to parse STATUS for zones: %s", err)
            
        return {"success": False, "zones": set()}

    def _detect_expanders(self, zones: Set[int]) -> List[Dict[str, any]]:
        """Detect expanders based on zone ranges."""
        from .const import ZONE_RANGES, PANEL_TYPE_ECI
        
        expanders = []
        
        if not zones:
            return expanders
            
        max_zone = max(zones)
        zone_ranges = ZONE_RANGES[PANEL_TYPE_ECI]
        
        for expander_name, (start, end) in zone_ranges.items():
            if expander_name == "main_panel":
                continue
                
            expander_zones_in_range = {z for z in zones if start <= z <= end}
            
            if expander_zones_in_range:
                expanders.append({
                    "type": "zone_expander",
                    "name": expander_name,
                    "zone_range": (start, end),
                    "zones": expander_zones_in_range,
                    "zone_count": len(expander_zones_in_range)
                })
                    
        return expanders


class ECiConfigurationManager:
    """Manage ECi panel configuration with user preferences."""
    
    def __init__(self):
        """Initialize configuration manager."""
        self.auto_detect = True
        self.user_max_zones = None
        self.user_areas = None
        self.detection_cache = None
        
    def set_user_preferences(self, max_zones: Optional[int] = None, 
                           areas: Optional[List[int]] = None,
                           auto_detect: bool = True):
        """Set user configuration preferences."""
        self.auto_detect = auto_detect
        self.user_max_zones = max_zones
        self.user_areas = set(areas) if areas else None
        
        _LOGGER.info("User preferences set: auto_detect=%s, max_zones=%s, areas=%s", 
                    auto_detect, max_zones, areas)

    async def get_panel_configuration(self, client) -> Dict[str, any]:
        """Get final panel configuration based on detection and user preferences."""
        
        if self.auto_detect:
            # Auto-detect configuration
            zone_manager = ECiZoneManager(client)
            detected_config = await zone_manager.detect_panel_configuration()
            
            # Apply user overrides if specified
            final_config = self._apply_user_overrides(detected_config)
            
        else:
            # Use manual configuration
            final_config = self._create_manual_configuration()
            
        # Ensure configuration is valid
        final_config = self._validate_configuration(final_config)
        
        # Cache for future use
        self.detection_cache = final_config
        
        return final_config

    def _apply_user_overrides(self, detected_config: Dict[str, any]) -> Dict[str, any]:
        """Apply user overrides to detected configuration."""
        config = detected_config.copy()
        
        # Override max zones if user specified
        if self.user_max_zones:
            config["max_zone"] = min(self.user_max_zones, config["max_zone"])
            # Filter detected zones to user limit
            config["detected_zones"] = {z for z in config["detected_zones"] if z <= self.user_max_zones}
            config["total_zones"] = len(config["detected_zones"])
            
        # Override areas if user specified
        if self.user_areas:
            config["active_areas"] = self.user_areas
            
        return config

    def _create_manual_configuration(self) -> Dict[str, any]:
        """Create manual configuration based on user preferences."""
        max_zones = self.user_max_zones or 16
        areas = self.user_areas or {1}
        
        # Create zones distributed across areas
        zones_per_area = max_zones // len(areas)
        zones_in_areas = {}
        all_zones = set()
        
        for i, area in enumerate(sorted(areas)):
            start_zone = i * zones_per_area + 1
            end_zone = min((i + 1) * zones_per_area, max_zones)
            if i == len(areas) - 1:  # Last area gets remaining zones
                end_zone = max_zones
                
            area_zones = set(range(start_zone, end_zone + 1))
            zones_in_areas[area] = area_zones
            all_zones.update(area_zones)
            
        return {
            "detected_zones": all_zones,
            "active_areas": areas,
            "zones_in_areas": zones_in_areas,
            "max_zone": max_zones,
            "total_zones": len(all_zones),
            "expanders_detected": [],
            "detection_method": "manual"
        }

    def _validate_configuration(self, config: Dict[str, any]) -> Dict[str, any]:
        """Validate and sanitize configuration."""
        # Ensure minimum configuration
        if not config["detected_zones"]:
            config["detected_zones"] = set(range(1, 17))
            
        if not config["active_areas"]:
            config["active_areas"] = {1}
            
        if not config["zones_in_areas"]:
            config["zones_in_areas"] = {1: config["detected_zones"]}
            
        # Ensure max_zone is reasonable
        if config["max_zone"] > 248:
            config["max_zone"] = 248
        elif config["max_zone"] < 1:
            config["max_zone"] = 16
            
        # Ensure zones don't exceed 248
        config["detected_zones"] = {z for z in config["detected_zones"] if 1 <= z <= 248}
        config["total_zones"] = len(config["detected_zones"])
        
        return config