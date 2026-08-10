"""Automated emergency landing — contingency management for in-flight faults.

Given an active fault (from aerofleet.fault_tolerance.multi_fault_handler)
and the drone's current position, selects the nearest pre-mapped safe zone
(open ground tagged in aerofleet.city.airspace) and diverts the drone
there. This is the concrete implementation of the "Contingency Management"
requirement: fleet software continuously monitors health metrics and
executes automated landing protocols at pre-mapped safe zones during
system anomalies.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from aerofleet.city.airspace import AirspaceModel, SafeZone
from aerofleet.fault_tolerance.multi_fault_handler import ActiveFault, FaultType

logger = logging.getLogger(__name__)

# Faults for which we divert to the nearest safe zone rather than
# attempting a normal return-to-home at the origin depot.
DIVERT_TO_SAFE_ZONE = {
    FaultType.MOTOR,
    FaultType.COMMS_LOSS,
    FaultType.UNKNOWN,
}


@dataclass
class EmergencyLandingPlan:
    drone_id: str
    fault_type: str
    action: str                 # DIVERT_TO_SAFE_ZONE | RETURN_TO_HOME | HOLD_POSITION
    target_zone_id: Optional[str]
    target_lat: Optional[float]
    target_lon: Optional[float]
    distance_m: Optional[float]
    decided_at: float


class EmergencyLandingPlanner:
    def __init__(self, airspace: AirspaceModel):
        self.airspace = airspace

    def plan(
        self,
        drone_id: str,
        fault: ActiveFault,
        current_lat: float,
        current_lon: float,
        home_depot_lat: Optional[float] = None,
        home_depot_lon: Optional[float] = None,
    ) -> EmergencyLandingPlan:
        if fault.fault_type == FaultType.WEATHER_ABORT:
            return EmergencyLandingPlan(
                drone_id=drone_id, fault_type=fault.fault_type.name,
                action="HOLD_POSITION", target_zone_id=None,
                target_lat=None, target_lon=None, distance_m=None,
                decided_at=time.time(),
            )

        if fault.fault_type not in DIVERT_TO_SAFE_ZONE and home_depot_lat is not None:
            dist = self.airspace._haversine_m(current_lat, current_lon, home_depot_lat, home_depot_lon)
            return EmergencyLandingPlan(
                drone_id=drone_id, fault_type=fault.fault_type.name,
                action="RETURN_TO_HOME", target_zone_id=None,
                target_lat=home_depot_lat, target_lon=home_depot_lon,
                distance_m=round(dist, 1), decided_at=time.time(),
            )

        zone: Optional[SafeZone] = self.airspace.nearest_safe_zone(current_lat, current_lon)
        if zone is None:
            logger.warning(f"No pre-mapped safe zone available for {drone_id} — holding position")
            return EmergencyLandingPlan(
                drone_id=drone_id, fault_type=fault.fault_type.name,
                action="HOLD_POSITION", target_zone_id=None,
                target_lat=None, target_lon=None, distance_m=None,
                decided_at=time.time(),
            )

        dist = self.airspace._haversine_m(current_lat, current_lon, zone.center_lat, zone.center_lon)
        logger.warning(
            f"Emergency landing: {drone_id} diverting to {zone.zone_id} "
            f"({zone.name}) — {dist:.0f}m away, fault={fault.fault_type.name}"
        )
        return EmergencyLandingPlan(
            drone_id=drone_id, fault_type=fault.fault_type.name,
            action="DIVERT_TO_SAFE_ZONE", target_zone_id=zone.zone_id,
            target_lat=zone.center_lat, target_lon=zone.center_lon,
            distance_m=round(dist, 1), decided_at=time.time(),
        )
