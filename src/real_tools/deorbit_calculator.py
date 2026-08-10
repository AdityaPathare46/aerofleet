"""
deorbit_calculator.py — Atmospheric decay and deorbit ΔV calculations.

Implements the King-Hele drag model for orbital decay lifetime estimation
and computes ΔV required for active deorbit burns.

References:
  - King-Hele, D.G. (1987) Satellite Orbits in an Atmosphere
  - IADC Space Debris Mitigation Guidelines (2021) — 25yr rule
  - NASA Handbook 8719.14A — Process for Limiting Orbital Debris
  - NRLMSISE-00 — US Naval Research Laboratory atmosphere model
"""

import math
from typing import Dict, Any

# ── Constants ────────────────────────────────────────────────────────────
R_EARTH = 6378.137      # km
MU_EARTH = 3.986004418e5  # km³/s²
G0 = 9.80665            # m/s²

# NRLMSISE-00 simplified density model [kg/m³] at altitude
# Source: Picone et al. (2002) NRLMSISE-00 — calibrated for F10.7=150 (average solar activity)
_ALT_DENSITY = [
    (200, 2.50e-10),
    (300, 1.92e-11),
    (400, 2.80e-12),
    (500, 5.20e-13),
    (600, 1.14e-13),
    (700, 3.07e-14),
    (800, 1.14e-14),
    (900, 5.24e-15),
    (1000, 3.02e-15),
    (1200, 1.20e-15),
    (1500, 4.00e-16),
    (2000, 5.00e-17),
]


def _atmospheric_density(alt_km: float) -> float:
    """
    Interpolate atmospheric density from NRLMSISE-00 table.
    Returns density in kg/m³.
    """
    if alt_km <= _ALT_DENSITY[0][0]:
        return _ALT_DENSITY[0][1]
    if alt_km >= _ALT_DENSITY[-1][0]:
        return _ALT_DENSITY[-1][1] * 1e-3  # Extrapolate below exobase

    for i in range(len(_ALT_DENSITY) - 1):
        h0, rho0 = _ALT_DENSITY[i]
        h1, rho1 = _ALT_DENSITY[i + 1]
        if h0 <= alt_km <= h1:
            # Logarithmic interpolation
            t = (alt_km - h0) / (h1 - h0)
            return rho0 * ((rho1 / rho0) ** t)

    return _ALT_DENSITY[-1][1]


def atmospheric_decay_years(
    altitude_km: float,
    mass_kg: float,
    area_m2: float,
    cd: float = 2.2,
    solar_activity: str = "average",
) -> Dict[str, Any]:
    """
    Estimate orbital lifetime using King-Hele drag model.

    Computes decay rate dh/dt from drag force, integrates to find time
    for orbit to decay from given altitude to 80 km (reentry).

    Args:
        altitude_km:     Circular orbit altitude (km)
        mass_kg:         Spacecraft mass (kg)
        area_m2:         Cross-sectional area facing velocity vector (m²)
        cd:              Drag coefficient (dimensionless, typically 2.0–2.4)
        solar_activity:  "low" | "average" | "high" — affects density

    Returns:
        dict with lifetime_years, compliant_25yr, recommendation
    """
    # Solar activity density multiplier (F10.7 index proxy)
    activity_mult = {"low": 0.4, "average": 1.0, "high": 3.5}.get(solar_activity.lower(), 1.0)

    if altitude_km > 2000:
        return {
            "altitude_km": altitude_km,
            "lifetime_years": ">1000 years",
            "lifetime_numeric": 1000,
            "compliant_25yr": False,
            "active_deorbit_required": True,
            "note": "Above 2000 km — natural decay negligible. Active deorbit mandatory.",
            "model": "King-Hele / NRLMSISE-00",
        }

    # Orbital elements at circular orbit
    r = (R_EARTH + altitude_km) * 1000  # m
    v_orb = math.sqrt(MU_EARTH * 1e9 / r)  # m/s

    # Ballistic coefficient B = m / (Cd × A) [kg/m²]
    B = mass_kg / (cd * area_m2)

    # Numerical integration: step down 10 km at a time
    current_alt = float(altitude_km)
    total_seconds = 0.0
    step_km = 10.0

    while current_alt > 80:
        rho = _atmospheric_density(current_alt) * activity_mult  # kg/m³
        r_step = (R_EARTH + current_alt) * 1000  # m
        v_step = math.sqrt(MU_EARTH * 1e9 / r_step)  # m/s

        # Drag deceleration [m/s²]: a = ρv²/(2B)
        a_drag = (rho * v_step ** 2) / (2 * B)

        # Energy loss rate → altitude loss rate
        # dE/dt = F·v = m·a_drag·v  →  dh/dt = -2·a_drag·r² / (mu)
        dh_dt = -(rho * v_step ** 3 * r_step ** 2) / (MU_EARTH * 1e9 * B)  # m/s → alt change

        if dh_dt == 0:
            break

        step_m = step_km * 1000
        dt = abs(step_m / dh_dt)  # seconds to lose step_km altitude
        total_seconds += dt
        current_alt -= step_km

    lifetime_years = total_seconds / (365.25 * 24 * 3600)
    compliant = lifetime_years <= 25.0

    if compliant:
        rec = f"✅ {lifetime_years:.1f} yr < 25 yr IADC limit. Compliant."
    elif lifetime_years < 100:
        rec = f"⚠️ {lifetime_years:.1f} yr > 25 yr. Active deorbit or lower altitude required."
    else:
        rec = f"❌ >100 yr lifetime. Active deorbit system mandatory (IADC §5.3)."

    return {
        "altitude_km": altitude_km,
        "lifetime_years": round(lifetime_years, 1),
        "lifetime_numeric": round(lifetime_years, 1),
        "ballistic_coeff_kg_m2": round(B, 2),
        "solar_activity": solar_activity,
        "compliant_25yr": compliant,
        "active_deorbit_required": not compliant,
        "recommendation": rec,
        "model": "King-Hele / NRLMSISE-00",
        "reference": "IADC 2021 §5.3.2",
    }


def deorbit_dv_budget(
    altitude_km: float,
    mass_kg: float,
    target_alt_km: float = 120.0,
) -> Dict[str, Any]:
    """
    Compute ΔV required for an active deorbit burn.

    Uses Hohmann transfer to lower perigee to target altitude.
    The atmosphere handles the rest once perigee < ~120 km.

    Args:
        altitude_km:   Current circular orbit altitude (km)
        mass_kg:       Spacecraft mass (kg)
        target_alt_km: Target perigee altitude for reentry (km), default 120

    Returns:
        dict with dv_m_s, propellant_mass_kg, time_to_reentry_revs
    """
    r1 = (R_EARTH + altitude_km) * 1000       # m
    r2 = (R_EARTH + target_alt_km) * 1000     # m
    mu = MU_EARTH * 1e9                        # m³/s²

    v_circ = math.sqrt(mu / r1)
    a_transfer = (r1 + r2) / 2
    v_t1 = math.sqrt(mu * (2 / r1 - 1 / a_transfer))
    dv_ms = abs(v_circ - v_t1)   # m/s

    # Propellant for deorbit burn (Tsiolkovsky, hydrazine Isp ≈ 220 s)
    isp_s = 220.0
    prop_kg = mass_kg * (1 - math.exp(-dv_ms / (isp_s * G0)))

    # Time from deorbit burn to reentry (~2–5 revolutions below 300 km)
    period_s = 2 * math.pi * math.sqrt((r1 ** 3) / mu)
    rev_to_reentry = max(1, int(altitude_km / 50))   # approximate

    return {
        "current_altitude_km": altitude_km,
        "target_perigee_km": target_alt_km,
        "deorbit_dv_m_s": round(dv_ms, 2),
        "deorbit_dv_km_s": round(dv_ms / 1000, 4),
        "propellant_mass_kg": round(prop_kg, 2),
        "isp_assumed_s": isp_s,
        "revolutions_to_reentry": rev_to_reentry,
        "period_minutes": round(period_s / 60, 1),
        "note": "Assumes chemical propulsion (Isp=220s hydrazine). Adjust for actual thruster.",
    }
