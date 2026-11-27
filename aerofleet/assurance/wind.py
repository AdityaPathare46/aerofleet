"""Wind at cruise height, and what it does to a mission's battery margin.

Pilots usually check the wind near the ground; at 80–120 m it is often much stronger. This module reads
a forecast wind profile (Open-Meteo: 10, 80, 120 and 180 m above ground), interpolates it to the
mission's cruise height, and recomputes the mission's energy with the wind triangle on every leg.

Airframe energy model (self-contained — no dependency on the legacy delivery dispatcher):
  * Choose a named airframe profile (`light_survey`, `agri_sprayer_10l`, `agri_sprayer_16l`, or the legacy
    `light_multirotor` baseline) or supply your drone's actual `cruise_power_w` and `cruise_speed_mps`.
  * The drone holds a constant airspeed V and crabs into the wind; ground speed along a leg is
    g = sqrt(V^2 - crosswind^2) - headwind; a leg with g <= 0.05 m/s cannot be flown.
  * Power in cruise is taken as constant, so a leg's energy is (power_w / 3600) * (distance_m / g).
  * For low-altitude missions (<= 10 m, such as crop spraying), Open-Meteo's lowest forecast level is 10 m,
    so ground and cruise wind are identical and an explicit note says so.
  * Climb, descent, hover, gusts, turns and emptying tank weight are not modelled; a pass is a planning
    estimate, not a guarantee of endurance.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from aerofleet.assurance.deconflict import CRUISE_MPS
from aerofleet.assurance.reconcile import M_PER_DEG, Plan

HEIGHTS_M = (10, 80, 120, 180)
URL = "https://api.open-meteo.com/v1/forecast"
Profile = Dict[int, Tuple[float, float]]            # height m -> (speed m/s, direction the wind blows FROM, degrees)

# Airframe power presets: (cruise_speed_mps, base_power_w, power_per_kg_w, description).
# Legacy light_multirotor preserves the original 3.5 Wh/km * (1 + 0.15 * kg) at 12 m/s (151.2 W + 22.68 W/kg)
# for small survey/delivery test cases; agricultural sprayers draw ~2.5-4.5 kW at 4-6 m/s.
AIRFRAME_PROFILES: Dict[str, Dict[str, Any]] = {
    "light_multirotor": {"cruise_speed_mps": CRUISE_MPS, "base_power_w": 3.5 * CRUISE_MPS * 3.6,
                         "power_per_kg_w": 3.5 * 0.15 * CRUISE_MPS * 3.6,
                         "label": "Small test multirotor (legacy 3.5 Wh/km baseline, 12 m/s)"},
    "light_survey": {"cruise_speed_mps": 10.0, "base_power_w": 380.0, "power_per_kg_w": 95.0,
                     "label": "Survey / mapping quadrotor (10 m/s, ~380 W + 95 W/kg)"},
    "agri_sprayer_10l": {"cruise_speed_mps": 5.0, "base_power_w": 1600.0, "power_per_kg_w": 180.0,
                         "label": "10 L agricultural sprayer (5 m/s, ~1600 W + 180 W/kg)"},
    "agri_sprayer_16l": {"cruise_speed_mps": 5.0, "base_power_w": 2200.0, "power_per_kg_w": 190.0,
                         "label": "16 L agricultural sprayer (5 m/s, ~2200 W + 190 W/kg)"},
}


def resolve_airframe(airframe_profile: Optional[str] = None, cruise_speed_mps: Optional[float] = None,
                     cruise_power_w: Optional[float] = None, payload_kg: float = 0.0) -> Tuple[str, float, float]:
    """Return (profile_name, airspeed_mps, cruise_power_w) for the requested airframe or custom inputs."""
    name = (airframe_profile or "light_multirotor").strip().lower()
    if name not in AIRFRAME_PROFILES:
        raise ValueError(f"Unknown airframe profile '{name}'. Choose from: {', '.join(AIRFRAME_PROFILES)}")
    spec = AIRFRAME_PROFILES[name]
    speed = float(cruise_speed_mps) if cruise_speed_mps is not None else float(spec["cruise_speed_mps"])
    power = (float(cruise_power_w) if cruise_power_w is not None
             else float(spec["base_power_w"]) + float(spec["power_per_kg_w"]) * payload_kg)
    return name, speed, power


class WindUnavailable(RuntimeError):
    pass


def _http_json(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=15) as r:      # noqa: S310 - fixed https host above
        return json.load(r)


def fetch_profiles(lat: float, lon: float, past_days: int = 0, forecast_days: int = 1,
                   fetch: Callable[[str], Dict[str, Any]] = _http_json) -> List[Tuple[str, Profile]]:
    """[(UTC hour 'YYYY-MM-DDTHH:00', profile)] for the requested days."""
    fields = [f"wind_speed_{h}m" for h in HEIGHTS_M] + [f"wind_direction_{h}m" for h in HEIGHTS_M]
    query = urllib.parse.urlencode({"latitude": round(lat, 4), "longitude": round(lon, 4), "hourly": ",".join(fields),
                                    "wind_speed_unit": "ms", "timezone": "UTC", "past_days": past_days, "forecast_days": forecast_days})
    try:
        data = fetch(f"{URL}?{query}")
        hourly = data["hourly"]
        out = []
        for i, t in enumerate(hourly["time"]):
            prof = {h: (hourly[f"wind_speed_{h}m"][i], hourly[f"wind_direction_{h}m"][i]) for h in HEIGHTS_M}
            if all(v is not None for pair in prof.values() for v in pair):
                out.append((t, {h: (float(s), float(d)) for h, (s, d) in prof.items()}))
    except Exception as e:
        raise WindUnavailable(f"Could not get a wind forecast ({type(e).__name__}: {e})") from None
    if not out:
        raise WindUnavailable("The wind forecast came back empty")
    return out


def profile_for(profiles: Sequence[Tuple[str, Profile]], hour_utc: Optional[str]) -> Tuple[str, Profile]:
    if hour_utc is None:                                    # default: the forecast hour we are in now
        hour_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    key = hour_utc[:13]
    for t, p in profiles:
        if t[:13] == key:
            return t, p
    raise WindUnavailable(f"No forecast for {hour_utc} (available {profiles[0][0]} to {profiles[-1][0]})")


def wind_at(profile: Profile, height_m: float) -> Tuple[float, float]:
    """(speed, from-direction) at a height, interpolated between forecast levels (held constant outside them)."""
    hs = sorted(profile)
    if height_m <= hs[0]:
        return profile[hs[0]]
    if height_m >= hs[-1]:
        return profile[hs[-1]]
    lo = max(h for h in hs if h <= height_m)
    hi = min(h for h in hs if h >= height_m)
    if lo == hi:
        return profile[lo]
    u = (height_m - lo) / (hi - lo)
    (s0, d0), (s1, d1) = profile[lo], profile[hi]
    east = (1 - u) * s0 * math.sin(math.radians(d0)) + u * s1 * math.sin(math.radians(d1))     # interpolate as vectors
    north = (1 - u) * s0 * math.cos(math.radians(d0)) + u * s1 * math.cos(math.radians(d1))
    return math.hypot(east, north), math.degrees(math.atan2(east, north)) % 360


def mission_energy(plan: Plan, payload_kg: float, wind: Optional[Tuple[float, float]] = None,
                   airspeed_mps: Optional[float] = None, airframe_profile: Optional[str] = None,
                   cruise_power_w: Optional[float] = None) -> Dict[str, Any]:
    """Energy for the mission's horizontal legs. `wind` = (speed, from-direction); None = still air."""
    _name, speed, power_w = resolve_airframe(airframe_profile, airspeed_mps, cruise_power_w, payload_kg)
    legs, total, flyable = [], 0.0, True
    for (la0, lo0, _), (la1, lo1, _) in zip(plan.path, plan.path[1:]):
        north = (la1 - la0) * M_PER_DEG
        east = (lo1 - lo0) * M_PER_DEG * math.cos(math.radians(la0))
        dist = math.hypot(east, north)
        if dist < 1.0:
            continue
        ground = speed
        if wind is not None and wind[0] > 0:
            track = math.atan2(east, north)
            rel = math.radians(wind[1]) - track                 # angle between where the wind comes from and the track
            head, cross = wind[0] * math.cos(rel), wind[0] * math.sin(rel)
            ground = math.sqrt(max(speed ** 2 - cross ** 2, 0.0)) - head if abs(cross) < speed else 0.0
        if ground <= 0.05:
            flyable = False
            legs.append({"distance_m": round(dist), "ground_speed_mps": 0.0, "energy_wh": None})
            continue
        e = (power_w / 3600.0) * (dist / ground)
        total += e
        legs.append({"distance_m": round(dist), "ground_speed_mps": round(ground, 2), "energy_wh": round(e, 1)})
    return {"energy_wh": round(total, 1) if flyable else None, "flyable": flyable, "legs": legs}


def wind_check(plan: Plan, payload_kg: float, usable_wh: float, profile: Profile,
               max_wind_mps: Optional[float] = None, airframe_profile: Optional[str] = None,
               cruise_speed_mps: Optional[float] = None, cruise_power_w: Optional[float] = None) -> Dict[str, Any]:
    """Battery margin in still air, with the 10 m wind and with the wind at cruise height.

    `usable_wh` is the energy available above the landing reserve. Verdict:
      PASS              enough energy with the wind at cruise height (and within the wind limit, if given)
      FAILS_AT_ALTITUDE passes on the 10 m wind but not on the wind at cruise height - the case a ground check misses
      FAIL              not enough even on the 10 m wind
    """
    prof_name, speed, power_w = resolve_airframe(airframe_profile, cruise_speed_mps, cruise_power_w, payload_kg)
    cruise = plan.max_alt_m
    ground_wind, cruise_wind = profile[min(profile)], wind_at(profile, cruise)
    cases = {"still_air": mission_energy(plan, payload_kg, None, speed, prof_name, power_w),
             "ground_wind": mission_energy(plan, payload_kg, ground_wind, speed, prof_name, power_w),
             "cruise_wind": mission_energy(plan, payload_kg, cruise_wind, speed, prof_name, power_w)}

    def ok(case: Dict[str, Any]) -> bool:
        return case["flyable"] and case["energy_wh"] <= usable_wh

    over_limit = max_wind_mps is not None and cruise_wind[0] > max_wind_mps
    verdict = "PASS" if ok(cases["cruise_wind"]) and not over_limit else "FAILS_AT_ALTITUDE" if ok(cases["ground_wind"]) else "FAIL"
    low_alt_note = ("Mission cruise height is at or below 10 m, so ground and cruise wind both use the 10 m forecast; "
                    "wind shear aloft does not apply." if cruise <= min(profile) else None)
    out: Dict[str, Any] = {
        "verdict": verdict, "cruise_height_m": cruise, "usable_wh": usable_wh, "payload_kg": payload_kg,
        "airframe": {"profile": prof_name, "cruise_speed_mps": round(speed, 2), "cruise_power_w": round(power_w, 1)},
        "wind": {"at_10m": {"speed_mps": round(ground_wind[0], 2), "from_deg": round(ground_wind[1])},
                 "at_cruise": {"speed_mps": round(cruise_wind[0], 2), "from_deg": round(cruise_wind[1])},
                 "ratio": round(cruise_wind[0] / ground_wind[0], 2) if ground_wind[0] > 0.1 else None,
                 "limit_mps": max_wind_mps, "over_limit": over_limit},
        "low_altitude_note": low_alt_note,
        "assumptions": (f"Constant {speed:g} m/s airspeed and constant {power_w:.0f} W cruise power ({prof_name}); "
                        "climb, hover, turns, gusts and emptying tank weight are not modelled; one wind value for the whole mission."),
    }
    for name, case in cases.items():
        out[name] = {"energy_wh": case["energy_wh"], "flyable": case["flyable"],
                     "margin_wh": round(usable_wh - case["energy_wh"], 1) if case["flyable"] else None}
    out["legs_at_cruise"] = cases["cruise_wind"]["legs"]
    return out
