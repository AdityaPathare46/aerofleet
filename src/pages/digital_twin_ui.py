import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from aerofleet.digital_twin.mission_twin import MissionDigitalTwin
from aerofleet.digital_twin.spacecraft_twin import SpacecraftSubsystemTwin
from aerofleet.digital_twin.orbital_twin import OrbitalEnvironmentTwin

st.set_page_config(page_title="Digital Twin Environment", layout="wide", page_icon="🌍")

st.title("🌍 Spacecraft & Orbital Digital Twin")
st.markdown("Real-time telemetry shadowing, health trending, and environmental modeling")

@st.cache_resource
def get_twin_modules():
    mission_twin = MissionDigitalTwin("MISSION-ALPHA")
    sc_twin = SpacecraftSubsystemTwin("SC-ALPHA")
    orb_twin = OrbitalEnvironmentTwin()
    return mission_twin, sc_twin, orb_twin

mission_twin, sc_twin, orb_twin = get_twin_modules()

# Auto-update simulation state
if st.sidebar.button("Step Simulation"):
    # Update mission
    mission_twin.update({
        "type": "TELEMETRY_UPDATE", 
        "elapsed_s": mission_twin._state.elapsed_time_s + 60,
        "fuel_kg": 0.05
    })
    # Update spacecraft
    sc_twin.update_from_telemetry({
        "reaction_wheel_health": 0.95, "reaction_wheel_temp_c": 25.0, "adcs_power_w": 45.0,
        "battery_health": 0.98, "battery_temp_c": 20.0, "total_power_w": 250.0,
        "thruster_health": 1.0, "thruster_temp_c": 15.0, "thruster_power_w": 10.0
    })

col1, col2, col3 = st.columns(3)

with col1:
    st.header("1. Mission Digital Twin")
    
    m_state = mission_twin._state
    st.metric("Mission Phase", m_state.mission_phase)
    st.metric("Elapsed Time", f"{m_state.elapsed_time_s / 3600:.2f} hours")
    st.metric("Fuel Consumed", f"{m_state.fuel_consumed_kg:.2f} kg")
    st.metric("Overall Health Score", f"{m_state.health_score:.2%}")
    
    st.subheader("What-If Simulation")
    extra_dv = st.number_input("Extra Maneuver ΔV (m/s)", value=15.0)
    if st.button("Simulate What-If"):
        result = mission_twin.what_if({"extra_maneuver_dv_ms": extra_dv, "total_fuel_kg": 500.0})
        st.write(f"**Projected Fuel Remaining:** {result['projected_fuel_remaining_kg']:.2f} kg")
        if result['mission_viable']:
            st.success("Mission remains viable after maneuver.")
        else:
            st.error("Insufficient fuel for maneuver.")

with col2:
    st.header("2. Spacecraft Twin")
    
    st.metric("Spacecraft Overall Health", f"{sc_twin.get_overall_health():.2%}")
    
    report = sc_twin.get_subsystem_report()
    df = pd.DataFrame(report)
    
    # Format for display
    df['health'] = df['health'].apply(lambda x: f"{x:.2%}")
    
    st.dataframe(df, use_container_width=True)

with col3:
    st.header("3. Orbital Environment Twin")
    
    alt = st.slider("Altitude (km)", 200.0, 2000.0, 600.0)
    f107 = st.slider("Solar Flux (F10.7)", 70.0, 250.0, 150.0)
    kp = st.slider("Geomagnetic Kp Index", 0.0, 9.0, 3.0)
    
    if st.button("Compute Environment State"):
        env_state = orb_twin.compute_state(alt, f107, kp)
        
        st.write(f"**Atmospheric Density:** {env_state.atmospheric_density_kgm3:.2e} kg/m³")
        st.write(f"**Debris Density:** {env_state.debris_density_per_km3:.2e} /km³")
        st.write(f"**Radiation Dose Rate:** {env_state.radiation_dose_rate_rads:.3f} rads/hr")
        
        drag = orb_twin.estimate_drag(env_state, bc_kg_m2=50.0)
        st.write(f"**Estimated Drag Deceleration:** {drag:.2e} m/s²")
