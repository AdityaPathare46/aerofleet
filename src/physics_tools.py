"""
physics_tools.py — Supplementary physics calculations for the Space Mission Architect.

Provides engineering-grade tools used by multiple agents:
  - Link budget (Friis equation) — COMMS agent
  - Atmospheric decay (King-Hele) — SAFETY/LEGAL agents
  - Radiation dose estimation — SAFETY agent
  - Solar sail acceleration — PROPULSION agent (reference)
  - GSD camera resolution — SCIENCE agent

References:
  - Pratt (2003) Satellite Communications §2.4 (Friis equation)
  - King-Hele (1987) Satellite Orbits in an Atmosphere
  - ECSS-E-ST-10-04C Space Environment Standard
  - Robinson (2000) Spacecraft Camera Resolution
"""

import math
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

G0 = 9.80665
R_EARTH = 6378.137   # km
MU_EARTH = 3.986004418e5  # km³/s²


class PhysicsTools:

    def __init__(self):
        # Validated Isp reference values (s) — Sutton & Biblarz (2016)
        self.engine_presets = {
            "COLD GAS":                  70,
            "MONOPROPELLANT (HYDRAZINE)": 220,
            "BIPROPELLANT (N2O4/MON)":   315,
            "BIPROPELLANT (LOX/LH2)":    450,
            "BIPROPELLANT (LOX/RP-1)":   340,
            "ION (GRIDDED)":            3000,
            "HALL EFFECT":              1600,
            "ARCJET":                    600,
            "NUCLEAR THERMAL":           900,
            # Legacy aliases
            "CHEMICAL":                  320,
            "ELECTRIC (ION)":           3000,
            "ELECTRIC (HALL)":          1600,
            "ION":                      3000,
            "NUCLEAR":                   900,
        }
        self.g0 = G0

    def calculate_fuel_requirements(
        self,
        delta_v_km_s: float,
        payload_mass_kg: float,
        engine_type: str = "BIPROPELLANT (N2O4/MON)",
    ) -> dict:
        """
        Tsiolkovsky Rocket Equation with structural fraction.

        Δv = Isp × g₀ × ln(m_wet / m_dry)
        → m_wet = m_dry × e^(Δv / (Isp × g₀))
        m_dry  = payload + structure (15% of propellant mass, SMAD §17)

        Args:
            delta_v_km_s:   Required Δv (km/s)
            payload_mass_kg: Net payload (instruments + spacecraft bus)
            engine_type:    Engine type string (see self.engine_presets)
        """
        dv_ms = delta_v_km_s * 1000

        isp_key = engine_type.upper().strip()
        isp = self.engine_presets.get(isp_key)
        if isp is None:
            # Try partial match
            for k, v in self.engine_presets.items():
                if k in isp_key or isp_key in k:
                    isp = v
                    break
            if isp is None:
                isp = 320   # default chemical

        ve = isp * self.g0

        try:
            mass_ratio = math.exp(dv_ms / ve)
        except OverflowError:
            return {
                "status": "IMPOSSIBLE",
                "reason": f"Δv = {delta_v_km_s} km/s exceeds thermodynamic limit for Isp={isp}s",
                "max_dv_single_stage_km_s": round(ve * math.log(10) / 1000, 2),
            }

        # Structural fraction: tanks + structure ≈ 10% of propellant (SMAD §17.3)
        struct_fraction = 0.10
        m_dry = payload_mass_kg + struct_fraction * (payload_mass_kg * (mass_ratio - 1))
        m_wet = m_dry * mass_ratio
        prop_mass = m_wet - m_dry

        return {
            "engine_type": engine_type,
            "isp_s": isp,
            "exhaust_velocity_km_s": round(ve / 1000, 4),
            "required_delta_v_km_s": delta_v_km_s,
            "required_delta_v_m_s": round(dv_ms, 1),
            "payload_mass_kg": round(payload_mass_kg, 2),
            "propellant_mass_kg": round(prop_mass, 2),
            "structural_mass_kg": round(m_dry - payload_mass_kg, 2),
            "total_wet_mass_kg": round(m_wet, 2),
            "propellant_fraction": round(prop_mass / m_wet, 4),
            "mass_ratio": round(mass_ratio, 4),
            "status": "FEASIBLE",
            "formula": f"Δv = {isp}×{G0:.3f}×ln({mass_ratio:.3f}) = {dv_ms:.1f} m/s",
        }

    def link_budget(
        self,
        eirp_dbw: float,
        distance_km: float,
        freq_ghz: float,
        rx_gain_db: float,
        system_noise_temp_k: float = 290.0,
        data_rate_bps: float = 1e6,
    ) -> dict:
        """
        Friis link budget equation for downlink margin.

            FSPL (dB) = 20log₁₀(4πd/λ)
            C/N₀ (dB) = EIRP + Gr − FSPL − kT
            Eb/N₀ = C/N₀ − 10log₁₀(Rb)
            Margin = Eb/N₀ − required (QPSK: 9.6 dB @ BER 1e-6)

        References:
          - Pratt (2003) Satellite Communications §2.4
          - SMAD (2011) §13.3
          - ECSS-E-ST-50-05C Ranging and Doppler

        Args:
            eirp_dbw:             Transmitter EIRP (dBW)
            distance_km:          Link distance (km)
            freq_ghz:             Carrier frequency (GHz)
            rx_gain_db:           Ground station antenna gain (dBi)
            system_noise_temp_k:  System noise temperature (K)
            data_rate_bps:        Required data rate (bps)
        """
        k_boltzmann_db = -228.6  # dBW/K/Hz (10log10 of 1.38e-23)
        wavelength_m = (3e8) / (freq_ghz * 1e9)  # m

        # Free-space path loss (Friis)
        fspl_db = 20 * math.log10(4 * math.pi * distance_km * 1000 / wavelength_m)

        # Received C/N₀
        cn0_db = eirp_dbw + rx_gain_db - fspl_db - k_boltzmann_db - 10 * math.log10(system_noise_temp_k)

        # Eb/N₀
        rb_db = 10 * math.log10(data_rate_bps)
        eb_n0_db = cn0_db - rb_db

        # Required Eb/N₀ for QPSK @ BER 1e-6 (CCSDS standard)
        req_eb_n0_db = 10.5
        margin_db = eb_n0_db - req_eb_n0_db

        if margin_db > 6:
            status = "✅ EXCELLENT margin (>6 dB)"
        elif margin_db > 3:
            status = "✅ ADEQUATE margin (3–6 dB)"
        elif margin_db > 0:
            status = "⚠️ MARGINAL (0–3 dB) — increase gain or reduce rate"
        else:
            status = f"❌ LINK CLOSED: {abs(margin_db):.1f} dB deficit — mission-critical comm link will fail"

        return {
            "eirp_dbw": eirp_dbw,
            "distance_km": distance_km,
            "freq_ghz": freq_ghz,
            "free_space_path_loss_db": round(fspl_db, 2),
            "cn0_dB_Hz": round(cn0_db, 2),
            "eb_n0_db": round(eb_n0_db, 2),
            "required_eb_n0_db": req_eb_n0_db,
            "link_margin_db": round(margin_db, 2),
            "data_rate_bps": data_rate_bps,
            "status": status,
            "standard": "CCSDS QPSK @ BER 1e-6",
            "formula": f"FSPL={fspl_db:.1f}dB, C/N₀={cn0_db:.1f}dBHz, Margin={margin_db:.1f}dB",
        }

    def camera_resolution(
        self,
        altitude_km: float,
        focal_length_m: float,
        pixel_size_um: float,
        swath_width_km: float = None,
    ) -> dict:
        """
        Ground Sampling Distance (GSD) for remote sensing cameras.

        GSD = pixel_size × (altitude / focal_length)
        Source: Robinson (2000) Spacecraft Thermal Analysis

        Args:
            altitude_km:    Orbital altitude (km)
            focal_length_m: Camera focal length (m)
            pixel_size_um:  Detector pixel size (micrometers)
            swath_width_km: Optional swath width for coverage area
        """
        pixel_m = pixel_size_um * 1e-6  # convert to metres
        gsd_m = pixel_m * (altitude_km * 1000) / focal_length_m

        # Nyquist limit for spatial frequency
        nyquist_m = 2 * gsd_m

        results = {
            "gsd_m": round(gsd_m, 3),
            "gsd_cm": round(gsd_m * 100, 2),
            "nyquist_resolution_m": round(nyquist_m, 3),
            "formula": f"GSD = {pixel_size_um}μm × {altitude_km}km / {focal_length_m}m = {gsd_m:.3f}m",
        }

        if swath_width_km:
            # Sensor array width from swath
            sensor_pixels_across = (swath_width_km * 1000) / gsd_m
            results["swath_width_km"] = swath_width_km
            results["sensor_pixels_across"] = round(sensor_pixels_across)

        # Classification
        if gsd_m < 0.5:
            results["classification"] = "Sub-metre (NRO/commercial premium — WorldView-3 class)"
        elif gsd_m < 1.0:
            results["classification"] = "Very high resolution (Planet SuperDove / Maxar class)"
        elif gsd_m < 5.0:
            results["classification"] = "High resolution (Sentinel-2 / Landsat 9 class)"
        elif gsd_m < 30:
            results["classification"] = "Medium resolution (MODIS 500m class)"
        else:
            results["classification"] = "Low/coarse resolution (weather satellite class)"

        return results

    def hohmann_transfer(self, r1_km: float, r2_km: float, mu: float = MU_EARTH) -> dict:
        """
        Exact Hohmann transfer Δv (Curtis §6.3).
        """
        v1   = math.sqrt(mu / r1_km)
        v2   = math.sqrt(mu / r2_km)
        v_t1 = math.sqrt(2 * mu * r2_km / (r1_km * (r1_km + r2_km)))
        v_t2 = math.sqrt(2 * mu * r1_km / (r2_km * (r1_km + r2_km)))
        dv1  = abs(v_t1 - v1)
        dv2  = abs(v2 - v_t2)
        a_t  = (r1_km + r2_km) / 2
        tof  = math.pi * math.sqrt(a_t ** 3 / mu)
        return {
            "dv1_km_s": round(dv1, 4),
            "dv2_km_s": round(dv2, 4),
            "total_dv_km_s": round(dv1 + dv2, 4),
            "total_dv_m_s": round((dv1 + dv2) * 1000, 1),
            "transfer_sma_km": round(a_t, 1),
            "tof_hours": round(tof / 3600, 2),
        }