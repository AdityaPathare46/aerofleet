import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from aerofleet.ssa.multi_sensor_fusion import MultiSensorFusionEngine, SensorReading
from aerofleet.ssa.anomaly_detector import OrbitalAnomalyDetector
from aerofleet.ssa.cyber_monitor import SSACyberMonitor
from aerofleet.ssa.monte_carlo_conjunction import MonteCarloConjunctionAnalyzer

st.set_page_config(page_title="Advanced SSA & Orbital Defense", layout="wide", page_icon="🛰️")

st.title("🛰️ Advanced SSA & Orbital Defense")
st.markdown("Real-time Space Situational Awareness, Multi-Sensor Fusion, and Cyber-Physical Monitoring")

# Initialize modules
@st.cache_resource
def get_ssa_modules():
    fusion_engine = MultiSensorFusionEngine()
    anomaly_detector = OrbitalAnomalyDetector()
    cyber_monitor = SSACyberMonitor()
    mc_analyzer = MonteCarloConjunctionAnalyzer(n_samples=5000)
    return fusion_engine, anomaly_detector, cyber_monitor, mc_analyzer

fusion_engine, anomaly_detector, cyber_monitor, mc_analyzer = get_ssa_modules()

st.sidebar.header("SSA Controls")
simulate_btn = st.sidebar.button("Run SSA Cycle")

# Dummy data generator for UI
def generate_sensor_readings():
    return [
        SensorReading("RADAR", "DEBRIS-1A", [6778.0, 10.0, -5.0], [0.0, 7.7, 0.1], 0.6, 15.0, 60000.0),
        SensorReading("OPTICAL", "DEBRIS-1A", [6778.2, 10.1, -4.9], [0.0, 7.7, 0.1], 0.4, 20.0, 60000.0),
        SensorReading("LIDAR", "SAT-X", [7000.0, 0.0, 0.0], [0.0, 7.5, 0.0], 0.9, 5.0, 60000.0)
    ]

# Multi-Sensor Fusion Section
st.header("1. Multi-Sensor Fusion Tracks")
if simulate_btn or "tracks" not in st.session_state:
    readings = generate_sensor_readings()
    tracks = fusion_engine.fuse(readings)
    st.session_state.tracks = tracks

tracks = st.session_state.tracks

if tracks:
    track_data = []
    for t in tracks:
        track_data.append({
            "Object ID": t.object_id,
            "Sensors Used": ", ".join(t.sensor_types_used),
            "Confidence": f"{t.fusion_confidence:.2%}",
            "Position X (km)": round(t.position_km[0], 2),
            "Velocity Y (km/s)": round(t.velocity_kms[1], 3)
        })
    st.dataframe(pd.DataFrame(track_data), use_container_width=True)

    # 3D Plot
    fig = go.Figure()
    for t in tracks:
        fig.add_trace(go.Scatter3d(
            x=[t.position_km[0]], y=[t.position_km[1]], z=[t.position_km[2]],
            mode='markers',
            name=t.object_id,
            marker=dict(size=8, color='red' if 'DEBRIS' in t.object_id else 'blue')
        ))
    fig.update_layout(scene=dict(xaxis_title='X (km)', yaxis_title='Y (km)', zaxis_title='Z (km)'), title="Fused Objects")
    st.plotly_chart(fig, use_container_width=True)


col1, col2 = st.columns(2)

with col1:
    st.header("2. Orbital Anomaly Detection")
    # Simulate a track for anomaly detection
    sample_track = {
        "object_id": "SAT-X",
        "position_km": [7000, 0, 0],
        "velocity_kms": [0, 8.0, 0],  # Unexpectedly high velocity
        "fusion_confidence": 0.9
    }
    
    # Needs to be fitted first
    if not anomaly_detector._fitted:
        # Fit with some dummy history
        history = [{"position_km": [7000,0,0], "velocity_kms": [0,7.5,0], "fusion_confidence": 0.9} for _ in range(10)]
        anomaly_detector.fit(history)
        
    anomaly = anomaly_detector.detect(sample_track, 60000.0)
    if anomaly:
        st.error(f"⚠️ Anomaly Detected: {anomaly.anomaly_type.name}")
        st.write(f"**Confidence:** {anomaly.confidence:.2f}")
        st.write(f"**Details:** {anomaly.description}")
        if anomaly.delta_v_estimate_ms:
            st.write(f"**Est. Delta-V:** {anomaly.delta_v_estimate_ms} m/s")
    else:
        st.success("No anomalies detected in the current orbital tracks.")

with col2:
    st.header("3. Cyber-Physical Monitor")
    gnss_pos = [6778.0, 0.0, 0.0]
    inertial_pos = [6785.0, 0.0, 0.0]  # 7km discrepancy
    
    cyber_alert = cyber_monitor.check_gnss_spoofing(gnss_pos, inertial_pos)
    if cyber_alert:
        st.warning(f"🚨 Cyber Threat: {cyber_alert.threat_type}")
        st.write(f"**Confidence:** {cyber_alert.confidence:.2%}")
        st.write(f"**System:** {cyber_alert.affected_system}")
        st.write(f"**Action:** `{cyber_alert.recommended_action}`")
        st.json(cyber_alert.evidence)
    else:
        st.success("GNSS and TT&C Links Secure.")

st.header("4. Monte Carlo Conjunction Analysis")
if st.button("Run Monte Carlo Analysis"):
    with st.spinner("Running 5000 MC samples..."):
        mc_result = mc_analyzer.analyse(
            r1_km=[6778.0, 0.0, 0.0],
            r2_km=[6778.01, 0.0, 0.0],
            combined_radius_m=10.0,
            object_pair="SAT-X / DEBRIS-1A"
        )
        st.write(f"**Object Pair:** {mc_result.object_pair}")
        st.write(f"**Mean Collision Probability (Pc):** {mc_result.pc_mean:.2e}")
        st.write(f"**Pc 95th Percentile:** {mc_result.pc_95th_percentile:.2e}")
        st.write(f"**Mean Miss Distance:** {mc_result.miss_distance_km_mean} km")
        if mc_result.uncertainty_dominated:
            st.info("ℹ️ Conjunction is uncertainty-dominated (covariance >> hard body size).")
