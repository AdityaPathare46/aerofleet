"""Agent tools for physics/logistics-based dispatch validation."""

import math
from typing import Any, Dict

from aerofleet.utils.logging import get_logger

logger = get_logger(__name__)


class AgentTools:
    """Deterministic validation tools used by specialized agents. These are
    the same "hard facts" the CBF gate later checks — agents use them to
    reason and critique, but the CBF gate's own evaluation is what actually
    gates execution, so a tool bug here cannot silently approve an unsafe
    dispatch."""

    @staticmethod
    def route_feasibility_check(
        distance_km: float, deadline_minutes: float, avg_speed_kmh: float = 40.0
    ) -> Dict[str, Any]:
        """Validate whether a route can be flown within the order's deadline."""
        logger.debug("Route feasibility check")
        try:
            eta_minutes = (distance_km / avg_speed_kmh) * 60.0 if avg_speed_kmh > 0 else float("inf")
            margin_minutes = deadline_minutes - eta_minutes

            if margin_minutes < 0:
                return {
                    "status": "FAIL",
                    "reason": f"ETA {eta_minutes:.1f} min exceeds deadline {deadline_minutes:.1f} min",
                    "eta_minutes": round(eta_minutes, 1),
                }
            return {
                "status": "PASS",
                "eta_minutes": round(eta_minutes, 1),
                "margin_minutes": round(margin_minutes, 1),
            }
        except Exception as e:
            logger.error(f"Route feasibility check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    @staticmethod
    def battery_margin_check(
        distance_km: float,
        payload_kg: float,
        battery_soc: float,
        battery_capacity_wh: float,
        reserve_margin: float = 0.20,
        wh_per_km: float = 3.5,
        payload_energy_factor: float = 0.15,
    ) -> Dict[str, Any]:
        """Audit whether the drone's battery covers the round trip plus reserve."""
        logger.debug("Running battery margin check")
        try:
            energy_required_wh = distance_km * wh_per_km * (1.0 + payload_energy_factor * payload_kg)
            usable_wh = battery_capacity_wh * battery_soc
            reserve_wh = battery_capacity_wh * reserve_margin
            margin_wh = usable_wh - reserve_wh - energy_required_wh

            if margin_wh < 0:
                status = "FAIL"
                reason = f"Insufficient battery margin. Deficit: {abs(margin_wh):.1f} Wh"
            elif margin_wh < battery_capacity_wh * 0.1:
                status = "WARNING"
                reason = f"Low battery margin: {margin_wh:.1f} Wh"
            else:
                status = "PASS"
                reason = f"Healthy battery margin: {margin_wh:.1f} Wh"

            return {
                "status": status,
                "reason": reason,
                "energy_required_wh": round(energy_required_wh, 1),
                "margin_wh": round(margin_wh, 1),
                "margin_percent": round((margin_wh / battery_capacity_wh) * 100, 1) if battery_capacity_wh else 0,
            }
        except Exception as e:
            logger.error(f"Battery margin check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    @staticmethod
    def geofence_check(
        in_red_zone: bool,
        in_yellow_zone: bool,
        atc_permission: bool,
        altitude_m: float,
        max_altitude_m: float = 100.0,
        min_separation_m: float = 15.0,
        current_separation_m: float = 999.0,
    ) -> Dict[str, Any]:
        """Check airspace safety: geofence, altitude ceiling, separation."""
        logger.debug("Running geofence/airspace safety check")
        try:
            if in_red_zone:
                return {"status": "FAIL", "reason": "Route enters a DGCA Red Zone (no-fly)"}
            if in_yellow_zone and not atc_permission:
                return {"status": "FAIL", "reason": "Yellow Zone requires ATC permission — not on record"}
            if altitude_m > max_altitude_m:
                return {
                    "status": "FAIL",
                    "reason": f"Altitude {altitude_m}m exceeds ceiling {max_altitude_m}m",
                }
            if current_separation_m < min_separation_m:
                return {
                    "status": "WARNING",
                    "reason": f"Separation {current_separation_m}m below minimum {min_separation_m}m",
                }
            return {
                "status": "PASS",
                "separation_margin_m": round(current_separation_m - min_separation_m, 1),
                "recommendation": "Nominal airspace safety margins",
            }
        except Exception as e:
            logger.error(f"Geofence check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    @staticmethod
    def weather_check(
        wind_speed_mps: float,
        visibility_m: float,
        precipitation: bool,
        max_wind_mps: float = 10.0,
        min_visibility_m: float = 1500.0,
    ) -> Dict[str, Any]:
        """Check current weather against the airframe's operating envelope."""
        logger.debug("Running weather check")
        try:
            if wind_speed_mps > max_wind_mps:
                return {
                    "status": "FAIL",
                    "reason": f"Wind {wind_speed_mps} m/s exceeds max operating speed {max_wind_mps} m/s",
                }
            if visibility_m < min_visibility_m:
                return {
                    "status": "FAIL",
                    "reason": f"Visibility {visibility_m}m below BVLOS minimum {min_visibility_m}m",
                }
            if precipitation:
                return {"status": "WARNING", "reason": "Active precipitation — reduced sensor reliability"}

            return {
                "status": "PASS",
                "wind_margin_mps": round(max_wind_mps - wind_speed_mps, 1),
                "visibility_margin_m": round(visibility_m - min_visibility_m, 1),
            }
        except Exception as e:
            logger.error(f"Weather check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    @staticmethod
    def cost_estimation_parametric(
        distance_km: float, energy_wh: float, priority: str = "STANDARD"
    ) -> Dict[str, Any]:
        """Parametric per-delivery cost estimation."""
        logger.debug("Running parametric delivery cost estimation")
        try:
            energy_cost = energy_wh * 0.008          # ~INR 8/kWh -> USD-equivalent per Wh, illustrative
            amortisation_cost = distance_km * 0.05    # drone wear/amortisation per km
            ops_cost = 0.15                            # fixed depot handling cost per delivery

            multiplier = {"MEDICAL": 1.5, "EXPRESS": 1.2, "STANDARD": 1.0}.get(priority, 1.0)
            total_cost = (energy_cost + amortisation_cost + ops_cost) * multiplier

            return {
                "status": "INFO",
                "estimated_cost_usd": round(total_cost, 3),
                "breakdown": {
                    "energy_usd": round(energy_cost, 3),
                    "amortisation_usd": round(amortisation_cost, 3),
                    "ops_usd": round(ops_cost, 3),
                },
                "confidence": "Low (parametric model)",
            }
        except Exception as e:
            logger.error(f"Cost estimation failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    @staticmethod
    def dgca_compliance_check(
        zone_color: str, uin_registered: bool, atc_permission: bool, altitude_m: float
    ) -> Dict[str, Any]:
        """Check compliance against India's DGCA Drone Rules 2021."""
        logger.debug("Running DGCA compliance check")
        try:
            issues = []
            zone_color = (zone_color or "GREEN").upper()

            if not uin_registered:
                issues.append("Drone missing valid UIN (Unique Identification Number) registration")
            if zone_color == "RED":
                issues.append("Rule 24 — Red Zone: flight prohibited")
            if zone_color == "YELLOW" and not atc_permission:
                issues.append("Rule 24 — Yellow Zone: ATC/ATS permission required and not on record")
            if altitude_m > 120.0:
                issues.append("Altitude exceeds the 120m (400ft) AGL default ceiling")

            if issues:
                return {"status": "FAIL", "issues": issues, "recommendation": "Resolve before dispatch"}

            return {"status": "PASS", "compliance": "Meets DGCA Drone Rules 2021 baseline requirements"}
        except Exception as e:
            logger.error(f"DGCA compliance check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    @staticmethod
    def comms_link_budget(distance_km: float, tx_power_w: float, data_rate_mbps: float) -> Dict[str, Any]:
        """Short-range 2.4GHz/900MHz command & telemetry link budget."""
        logger.debug("Running comms link budget")
        try:
            freq_hz = 2.4e9
            c = 3e8
            lam = c / freq_hz

            tx_gain_dbi = 5   # small omni antenna
            eirp_dbw = 10 * math.log10(max(1e-6, tx_power_w)) + tx_gain_dbi

            distance_m = max(10.0, distance_km * 1000)
            fspl_db = 20 * math.log10(4 * math.pi * distance_m / lam)

            rx_gain_dbi = 8   # depot ground-station antenna
            k_db = -228.6
            sys_temp_k = 290

            c_n0_db = eirp_dbw - fspl_db + rx_gain_dbi - k_db - 10 * math.log10(sys_temp_k)
            data_rate_bps = max(1.0, data_rate_mbps * 1e6)
            eb_n0_db = c_n0_db - 10 * math.log10(data_rate_bps)

            required_eb_n0 = 10.0
            margin = eb_n0_db - required_eb_n0

            if margin < 0:
                status, reason = "FAIL", f"Link margin negative ({margin:.1f} dB)"
            elif margin < 3:
                status, reason = "WARNING", f"Link margin low ({margin:.1f} dB)"
            else:
                status, reason = "PASS", f"Link margin healthy ({margin:.1f} dB)"

            return {
                "status": status,
                "reason": reason,
                "fspl_db": round(fspl_db, 1),
                "margin_db": round(margin, 1),
            }
        except Exception as e:
            logger.error(f"Comms check failed: {e}")
            return {"status": "ERROR", "error": str(e)}
