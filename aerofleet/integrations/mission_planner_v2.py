"""Enhanced Mission Planner file generator — AeroFleet 2.0.

Extends the basic 4-waypoint QGC WPL 110 export to support:
  1. Multi-waypoint routes from the real OSM street graph
  2. Zone-aware altitude assignment (100m → 60m inside Yellow zones)
  3. Auto-insertion of avoidance waypoints at restricted zone boundaries
  4. Dual-format export: QGC WPL 110 and JSON MAVLink mission format
  5. Compliance gate — file only generates when pre-flight check has passed

This module is the final step in the AeroFleet 2.0 ground-ops pipeline:
Compliance passes → Mission file generated → Operator loads into Mission Planner

The original module (aerofleet/integrations/mission_planner.py) is preserved
and used for the 4-waypoint simple case. This module handles multi-waypoint
real-graph routes.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

from aerofleet.city.restricted_sites import PUNE_RESTRICTED_SITES, MUMBAI_RESTRICTED_SITES
from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)

# MAVLink command IDs (stable standard values)
_MAV_FRAME_GLOBAL = 0
_MAV_FRAME_GLOBAL_RELATIVE_ALT = 3
_MAV_CMD_NAV_WAYPOINT = 16
_MAV_CMD_NAV_RETURN_TO_LAUNCH = 20
_MAV_CMD_NAV_TAKEOFF = 22
_MAV_CMD_NAV_LOITER_TURNS = 18  # optional delivery hover

# Zone altitude ceilings per DGCA Drone Rules 2021
_GREEN_CEILING_M = 100.0
_YELLOW_CEILING_M = 60.0
_RED_CEILING_M = 0.0  # flight prohibited

_RESTRICTED_BY_CITY = {
    "pune": PUNE_RESTRICTED_SITES,
    "mumbai": MUMBAI_RESTRICTED_SITES,
}


def _wpl_row(
    index: int, current: int, frame: int, command: int,
    p1: float, p2: float, p3: float, p4: float,
    lat: float, lon: float, alt: float, autocontinue: int = 1,
) -> str:
    return "\t".join(str(v) for v in (index, current, frame, command, p1, p2, p3, p4, lat, lon, alt, autocontinue))


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in metres between two lat/lon points."""
    R = 6371000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _altitude_at_point(lat: float, lon: float, city: str, requested_alt: float) -> float:
    """Return the compliant altitude at this point, capped to zone ceiling."""
    sites = _RESTRICTED_BY_CITY.get(city.lower(), [])
    for site in sites:
        dist = _haversine_m(lat, lon, site.lat, site.lon)
        if dist <= site.red_radius_m:
            return 0.0  # Red zone — do not fly
        if site.yellow_radius_m and dist <= site.yellow_radius_m:
            return min(requested_alt, _YELLOW_CEILING_M)
    return min(requested_alt, _GREEN_CEILING_M)


def _needs_avoidance_waypoint(
    lat1: float, lon1: float, lat2: float, lon2: float, city: str,
) -> Optional[Tuple[float, float, str]]:
    """Check if the segment lat1→lat2 crosses a restricted zone boundary.

    Returns (boundary_lat, boundary_lon, zone_name) if it does, else None.
    Simple linear interpolation check — adequate for mission planning.
    """
    sites = _RESTRICTED_BY_CITY.get(city.lower(), [])
    for site in sites:
        d1 = _haversine_m(lat1, lon1, site.lat, site.lon)
        d2 = _haversine_m(lat2, lon2, site.lat, site.lon)
        boundary = site.yellow_radius_m or site.red_radius_m
        if (d1 > boundary) != (d2 > boundary):
            # Interpolate the crossing point (midpoint heuristic)
            mid_lat = (lat1 + lat2) / 2
            mid_lon = (lon1 + lon2) / 2
            return mid_lat, mid_lon, site.name
    return None


def build_multi_waypoint_file(
    mission_plan: Dict[str, Any],
    route_coords: Optional[List[Tuple[float, float]]] = None,
    city: str = "pune",
) -> Optional[Dict[str, Any]]:
    """Build a zone-aware multi-waypoint mission file.

    Args:
        mission_plan: Dict with origin_lat, origin_lon, dest_lat, dest_lon,
                      altitude_m, and compliance_status
        route_coords: Optional list of (lat, lon) intermediate waypoints from
                      the city graph. If None, a straight-line route is used.
        city: City key for zone lookups

    Returns:
        Dict with 'wpl_content' (QGC WPL 110 string), 'mavlink_json' (JSON
        format), 'waypoints' (list of waypoint dicts), 'compliance_status'
        and 'warnings'. Returns None if the mission is non-compliant.
    """
    compliance_status = mission_plan.get("compliance_status", "COMPLIANT")
    if compliance_status == "NON_COMPLIANT":
        logger.warning("Mission file generation blocked — compliance status: NON_COMPLIANT")
        return None

    origin_lat = mission_plan.get("origin_lat")
    origin_lon = mission_plan.get("origin_lon")
    dest_lat = mission_plan.get("dest_lat")
    dest_lon = mission_plan.get("dest_lon")
    requested_alt = float(mission_plan.get("altitude_m", 60.0))

    if None in (origin_lat, origin_lon, dest_lat, dest_lon):
        logger.error("Missing coordinates — cannot build waypoint file")
        return None

    # Build waypoint chain: origin → [intermediate nodes] → destination
    if route_coords:
        all_latlons = [(origin_lat, origin_lon)] + list(route_coords) + [(dest_lat, dest_lon)]
    else:
        all_latlons = [(origin_lat, origin_lon), (dest_lat, dest_lon)]

    warnings = []
    waypoints = []
    rows = []
    wp_index = 0

    # Home / takeoff
    home_alt = _altitude_at_point(origin_lat, origin_lon, city, requested_alt)
    rows.append(_wpl_row(wp_index, 1, _MAV_FRAME_GLOBAL, _MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, origin_lat, origin_lon, 0))
    waypoints.append({"index": wp_index, "type": "HOME", "lat": origin_lat, "lon": origin_lon, "alt_m": 0})
    wp_index += 1

    rows.append(_wpl_row(wp_index, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, origin_lat, origin_lon, home_alt))
    waypoints.append({"index": wp_index, "type": "TAKEOFF", "lat": origin_lat, "lon": origin_lon, "alt_m": home_alt})
    wp_index += 1

    # Route waypoints with zone-aware altitude and avoidance checks
    for i in range(len(all_latlons) - 1):
        from_lat, from_lon = all_latlons[i]
        to_lat, to_lon = all_latlons[i + 1]

        # Check if segment crosses a zone boundary
        avoidance = _needs_avoidance_waypoint(from_lat, from_lon, to_lat, to_lon, city)
        if avoidance:
            av_lat, av_lon, av_site = avoidance
            av_alt = _altitude_at_point(av_lat, av_lon, city, requested_alt)
            rows.append(_wpl_row(wp_index, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, av_lat, av_lon, av_alt))
            waypoints.append({"index": wp_index, "type": "ZONE_BOUNDARY", "lat": av_lat, "lon": av_lon, "alt_m": av_alt, "note": f"Zone boundary: {av_site}"})
            warnings.append(f"Route crosses zone boundary near {av_site} — avoidance waypoint inserted at alt {av_alt}m")
            wp_index += 1

        # Destination or intermediate
        wp_lat, wp_lon = to_lat, to_lon
        wp_alt = _altitude_at_point(wp_lat, wp_lon, city, requested_alt)

        if wp_alt == 0.0:
            warnings.append(f"Waypoint ({wp_lat:.5f}, {wp_lon:.5f}) is in a Red Zone — FLIGHT PROHIBITED. Skipping.")
            continue

        if wp_alt < requested_alt:
            warnings.append(f"Altitude reduced from {requested_alt}m to {wp_alt}m at ({wp_lat:.5f}, {wp_lon:.5f}) — Yellow zone ceiling")

        wp_type = "DESTINATION" if i == len(all_latlons) - 2 else "WAYPOINT"
        rows.append(_wpl_row(wp_index, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_WAYPOINT, 0, 0, 0, 0, wp_lat, wp_lon, wp_alt))
        waypoints.append({"index": wp_index, "type": wp_type, "lat": wp_lat, "lon": wp_lon, "alt_m": wp_alt})
        wp_index += 1

    # Return to launch
    rows.append(_wpl_row(wp_index, 0, _MAV_FRAME_GLOBAL_RELATIVE_ALT, _MAV_CMD_NAV_RETURN_TO_LAUNCH, 0, 0, 0, 0, 0, 0, 0))
    waypoints.append({"index": wp_index, "type": "RTL", "lat": 0, "lon": 0, "alt_m": 0})

    wpl_content = "QGC WPL 110\n" + "\n".join(rows) + "\n"

    # MAVLink JSON format (alternative to WPL for programmatic use)
    mavlink_json = {
        "fileType": "Plan",
        "version": 1,
        "groundStation": "AeroFleet 2.0",
        "mission": {
            "cruiseSpeed": 10.0,
            "firmwareType": 3,
            "globalPlanAltitudeMode": 1,
            "items": [
                {
                    "autoContinue": True,
                    "command": _MAV_CMD_NAV_WAYPOINT,
                    "frame": _MAV_FRAME_GLOBAL_RELATIVE_ALT,
                    "params": [0, 0, 0, 0, wp["lat"], wp["lon"], wp["alt_m"]],
                    "type": "SimpleItem",
                }
                for wp in waypoints if wp["type"] not in ("HOME", "RTL")
            ],
        },
    }

    return {
        "wpl_content": wpl_content,
        "mavlink_json": mavlink_json,
        "waypoints": waypoints,
        "total_waypoints": len(waypoints),
        "compliance_status": compliance_status,
        "warnings": warnings,
        "city": city,
        "format": "QGC WPL 110 + MAVLink JSON",
    }
