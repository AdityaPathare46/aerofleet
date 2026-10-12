"""Wind at cruise height, and what it does to a mission's battery margin.

Pilots usually check the wind near the ground; at 100 m it is often much stronger. This module reads
a forecast wind profile (Open-Meteo: 10, 80, 120 and 180 m above ground), interpolates it to the
mission's cruise height, and recomputes the mission's energy with the wind triangle on every leg.

Model, stated plainly (it extends the fleet's existing per-kilometre energy model, nothing more):
  * the drone holds a constant airspeed (12 m/s, the simulator's cruise speed) and crabs into the wind;
  * ground speed along a leg  g = sqrt(V^2 - crosswind^2) + tailwind;  a leg with g <= 0 cannot be flown;
  * power in cruise is taken as constant, so a leg's energy is its still-air energy times V / g;
  * climb, descent, hover, gusts and turbulence are not modelled; one wind value is used for the whole
    mission (the forecast hour at the launch point).
A pass here is therefore a planning check, not a guarantee of endurance.
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
from aerofleet.fleet.dispatch import DispatchEngine

HEIGHTS_M = (10, 80, 120, 180)
URL = "https://api.open-meteo.com/v1/forecast"
Profile = Dict[int, Tuple[float, float]]            # height m -> (speed m/s, direction the wind blows FROM, degrees)


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
                   airspeed_mps: float = CRUISE_MPS) -> Dict[str, Any]:
    """Energy for the mission's horizontal legs. `wind` = (speed, from-direction); None = still air."""
    legs, total, flyable = [], 0.0, True
    for (la0, lo0, _), (la1, lo1, _) in zip(plan.path, plan.path[1:]):
        north = (la1 - la0) * M_PER_DEG
        east = (lo1 - lo0) * M_PER_DEG * math.cos(math.radians(la0))
        dist = math.hypot(east, north)
        if dist < 1.0:
            continue
        still = DispatchEngine.estimate_energy_wh(dist / 1000.0, payload_kg)
        ground = airspeed_mps
        if wind is not None and wind[0] > 0:
            track = math.atan2(east, north)
            rel = math.radians(wind[1]) - track                 # angle between where the wind comes from and the track
            head, cross = wind[0] * math.cos(rel), wind[0] * math.sin(rel)
            ground = math.sqrt(max(airspeed_mps ** 2 - cross ** 2, 0.0)) - head if abs(cross) < airspeed_mps else 0.0
        if ground <= 0.05:
            flyable = False
            legs.append({"distance_m": round(dist), "ground_speed_mps": 0.0, "energy_wh": None})
            continue
        e = still * airspeed_mps / ground
        total += e
        legs.append({"distance_m": round(dist), "ground_speed_mps": round(ground, 2), "energy_wh": round(e, 1)})
    return {"energy_wh": round(total, 1) if flyable else None, "flyable": flyable, "legs": legs}


def wind_check(plan: Plan, payload_kg: float, usable_wh: float, profile: Profile,
               max_wind_mps: Optional[float] = None) -> Dict[str, Any]:
    """Battery margin in still air, with the 10 m wind and with the wind at cruise height.

    `usable_wh` is the energy available above the landing reserve. Verdict:
      PASS              enough energy with the wind at cruise height (and within the wind limit, if given)
      FAILS_AT_ALTITUDE passes on the 10 m wind but not on the wind at cruise height - the case a ground check misses
      FAIL              not enough even on the 10 m wind
    """
    cruise = plan.max_alt_m
    ground_wind, cruise_wind = profile[min(profile)], wind_at(profile, cruise)
    cases = {"still_air": mission_energy(plan, payload_kg), "ground_wind": mission_energy(plan, payload_kg, ground_wind),
             "cruise_wind": mission_energy(plan, payload_kg, cruise_wind)}

    def ok(case: Dict[str, Any]) -> bool:
        return case["flyable"] and case["energy_wh"] <= usable_wh

    over_limit = max_wind_mps is not None and cruise_wind[0] > max_wind_mps
    verdict = "PASS" if ok(cases["cruise_wind"]) and not over_limit else "FAILS_AT_ALTITUDE" if ok(cases["ground_wind"]) else "FAIL"
    out: Dict[str, Any] = {
        "verdict": verdict, "cruise_height_m": cruise, "usable_wh": usable_wh, "payload_kg": payload_kg,
        "wind": {"at_10m": {"speed_mps": round(ground_wind[0], 2), "from_deg": round(ground_wind[1])},
                 "at_cruise": {"speed_mps": round(cruise_wind[0], 2), "from_deg": round(cruise_wind[1])},
                 "ratio": round(cruise_wind[0] / ground_wind[0], 2) if ground_wind[0] > 0.1 else None,
                 "limit_mps": max_wind_mps, "over_limit": over_limit},
        "assumptions": "Constant 12 m/s airspeed and constant cruise power; climb, hover and gusts not modelled; one wind value for the whole mission.",
    }
    for name, case in cases.items():
        out[name] = {"energy_wh": case["energy_wh"], "flyable": case["flyable"],
                     "margin_wh": round(usable_wh - case["energy_wh"], 1) if case["flyable"] else None}
    out["legs_at_cruise"] = cases["cruise_wind"]["legs"]
    return out
