"""
space_environment.py — Real space environment models for Safety & Power agents.

Models:
  - Solar flux vs distance (inverse-square law, NASA solar constant)
  - Van Allen belt radiation dose (AE8/AP8 simplified model)
  - Orbital debris density (MASTER-8 simplified for LEO/MEO)

References:
  - Wertz & Larson (2011) Space Mission Engineering
  - NASA SP-8069 — Solar Electromagnetic Radiation
  - ECSS-E-ST-10-04C — Space Environment Standard
  - Tribble (2003) The Space Environment
"""

import math
from typing import Dict, Any, List

# ── Physical Constants ────────────────────────────────────────────────────
SOLAR_CONSTANT = 1361.0   # W/m² at 1 AU (NASA 2014 TIM value)
AU_KM          = 1.496e8  # km per AU
R_EARTH        = 6378.137 # km


def solar_flux_at_distance(distance_au: float) -> Dict[str, Any]:
    """
    Calculate solar irradiance at a given distance from the Sun.

    Uses NASA solar constant and inverse-square law: S = S₀ / d²

    Args:
        distance_au: Distance from Sun in AU (Earth = 1.0)

    Returns:
        dict with flux_w_m2, solar_constant_w_m2, distance_au, panel_efficiency_note
    """
    if distance_au <= 0:
        distance_au = 1.0

    flux = SOLAR_CONSTANT / (distance_au ** 2)

    # Panel temperature effect at distance (simplified — Messenger/Parker models)
    if distance_au < 0.5:
        panel_note = "⚠️ HIGH FLUX: Active thermal management required for panels"
    elif distance_au > 3.0:
        panel_note = "⚠️ LOW FLUX: Solar power insufficient beyond ~3.5 AU (Cassini limit). RTG recommended."
    elif distance_au > 5.0:
        panel_note = "❌ SOLAR POWER IMPRACTICAL: < 54 W/m². Use RTG (Pu-238) or nuclear fission."
    else:
        panel_note = "✅ Solar power viable for this distance"

    return {
        "distance_au": distance_au,
        "flux_w_m2": round(flux, 2),
        "solar_constant_w_m2": SOLAR_CONSTANT,
        "panel_note": panel_note,
        "formula": f"S = {SOLAR_CONSTANT} / {distance_au}² = {flux:.2f} W/m²",
    }


def van_allen_dose(
    perigee_km: float,
    apogee_km: float,
    inclination_deg: float,
    duration_days: float,
    shielding_mm_al: float = 2.5,
) -> Dict[str, Any]:
    """
    Estimate total ionising radiation dose using ECSS-E-ST-10-04C model regions.

    The Van Allen belts are divided into:
      - Inner Belt: 1,000 – 6,000 km — proton-dominated
      - Slot Region: 6,000 – 13,000 km — relatively benign
      - Outer Belt: 13,000 – 60,000 km — electron-dominated

    Args:
        perigee_km:       Perigee altitude (km)
        apogee_km:        Apogee altitude (km)
        inclination_deg:  Orbital inclination (degrees)
        duration_days:    Mission duration (days)
        shielding_mm_al:  Aluminium equivalent shielding thickness (mm)

    Returns:
        dict with total_dose_krad, dose_rate_krad_day, belt_flags, recommendation
    """
    flags: List[str] = []
    dose_rate = 0.0  # krad/day behind 2.5mm Al

    alt_avg = (perigee_km + apogee_km) / 2

    # Inner proton belt (most damaging to electronics and humans)
    if 1000 <= perigee_km <= 6000 or 1000 <= apogee_km <= 6000:
        flags.append("INNER BELT — High proton flux. Proton dose dominates.")
        dose_rate += 20.0 if alt_avg < 3000 else 10.0   # krad/day (AE8/AP8 simplified)

    # Outer electron belt
    if 13000 <= apogee_km <= 60000:
        flags.append("OUTER BELT — High electron flux. TID threat to solar panels.")
        dose_rate += 5.0

    # Slot region
    if 6000 <= alt_avg <= 13000 and apogee_km < 13000:
        flags.append("SLOT REGION — Moderate dose. Rapid transit recommended.")
        dose_rate += 2.0

    # LEO — relatively benign but SAA matters
    if apogee_km < 1000:
        if inclination_deg > 50:
            flags.append("HIGH INCLINATION LEO — South Atlantic Anomaly (SAA) crossings add proton dose.")
            dose_rate += 0.5
        else:
            dose_rate += 0.1  # krad/day for equatorial LEO

    # Shielding correction (simple exponential approximation)
    shielding_factor = math.exp(-0.15 * (shielding_mm_al - 2.5))
    effective_dose_rate = dose_rate * shielding_factor

    total_dose_krad = effective_dose_rate * duration_days
    total_dose_gy   = total_dose_krad * 10  # 1 krad = 10 Gy

    # EEE parts radiation tolerance (ECSS-E-ST-20-07)
    if total_dose_krad > 100:
        rec = "❌ EXCEEDS 100 krad. RHA-grade components mandatory. Mission not viable without additional shielding."
    elif total_dose_krad > 30:
        rec = "⚠️ 30–100 krad range. Space-grade EEE parts required. EDAC and triple-redundancy for memory."
    elif total_dose_krad > 10:
        rec = "✅ 10–30 krad. Commercial space-grade parts acceptable with screening."
    else:
        rec = "✅ <10 krad. COTS components acceptable with standard screening."

    return {
        "total_dose_krad": round(total_dose_krad, 2),
        "total_dose_gy": round(total_dose_gy, 2),
        "dose_rate_krad_day": round(effective_dose_rate, 4),
        "belt_flags": flags if flags else ["No major belt traversal detected"],
        "shielding_mm_al": shielding_mm_al,
        "recommendation": rec,
        "model": "ECSS-E-ST-10-04C / AE8-AP8 simplified",
    }


def debris_density_factor(altitude_km: float, inclination_deg: float) -> Dict[str, Any]:
    """
    Estimate debris collision risk using MASTER-8 simplified density model.

    MASTER-8 (ESA) provides spatial density of debris >10cm.
    We use piece-wise altitude bands calibrated to MASTER-8 output.

    Args:
        altitude_km:      Orbital altitude (km)
        inclination_deg:  Inclination (degrees) — affects SSO debris concentration

    Returns:
        dict with debris_density_per_km3, collision_prob_per_year, risk_level
    """
    # MASTER-8 simplified density [objects/km³, >10cm] by altitude band
    # Source: ESA Space Debris Office, MASTER-8 2021
    if altitude_km < 400:
        density = 1e-9
    elif altitude_km < 600:
        density = 4e-8   # Densest region (historical launches, ISS regime)
    elif altitude_km < 800:
        density = 3e-7   # Peak LEO density — Iridium/Fengyun debris
    elif altitude_km < 1000:
        density = 1.5e-7
    elif altitude_km < 1200:
        density = 8e-8
    elif altitude_km < 2000:
        density = 2e-8
    elif altitude_km < 6000:
        density = 1e-10  # Slot region — sparse
    elif altitude_km < 36000:
        density = 1e-11
    else:
        density = 1e-12   # GEO / above GEO

    # SSO inclination penalty (passes through denser Fengyun/Cosmos debris clouds)
    if 90 <= inclination_deg <= 100:
        density *= 3.0

    # Collision probability (NASA standard cross-section 10m², rel. velocity 7.5 km/s)
    area_m2   = 10.0
    v_rel_km_s = 7.5
    pc_per_year = density * area_m2 * 1e-6 * v_rel_km_s * 1000 * 3.156e7  # per year

    if pc_per_year > 1e-3:
        risk = "🔴 CRITICAL — Active collision avoidance maneuvers required"
    elif pc_per_year > 1e-4:
        risk = "🟡 HIGH — Collision avoidance system mandatory (>1e-4 IADC threshold)"
    elif pc_per_year > 1e-5:
        risk = "🟡 MODERATE — Monitor conjunction database (SpaceTrack/SOCRATES)"
    else:
        risk = "🟢 LOW — No immediate debris concern"

    return {
        "altitude_km": altitude_km,
        "debris_density_m3_per_km3": round(density, 15),
        "collision_probability_per_year": round(pc_per_year, 8),
        "risk_level": risk,
        "model": "ESA MASTER-8 simplified",
        "iadc_threshold": 1e-4,
        "exceeds_iadc": pc_per_year > 1e-4,
    }
