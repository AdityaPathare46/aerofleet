import streamlit as st
import pandas as pd
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from aerofleet.fault_tolerance.predictive_diagnostics import PredictiveDiagnostics
from aerofleet.fault_tolerance.ppo_fault_recovery import PPOFaultRecoveryController, RecoveryState
from aerofleet.fault_tolerance.multi_fault_handler import MultiFaultHandler, FaultType

st.set_page_config(page_title="Proactive Fault Tolerance", layout="wide", page_icon="🔧")

st.title("🔧 Proactive Fault Tolerance")
st.markdown("Predictive Diagnostics, PPO Fault Recovery, and Multi-Fault Conflict Resolution")

@st.cache_resource
def get_fault_modules():
    pd_engine = PredictiveDiagnostics()
    ppo_recovery = PPOFaultRecoveryController()
    mf_handler = MultiFaultHandler()
    return pd_engine, ppo_recovery, mf_handler

pd_engine, ppo_recovery, mf_handler = get_fault_modules()

col1, col2 = st.columns(2)

with col1:
    st.header("1. Predictive Diagnostics (RF+SOM)")
    
    st.subheader("Simulate Telemetry")
    bat_soc = st.slider("Battery SOC (%)", 0.0, 100.0, 15.0)
    bat_vol = st.slider("Battery Voltage (V)", 18.0, 32.0, 20.0)
    rw_speed = st.slider("Reaction Wheel Speed (RPM)", 0.0, 6000.0, 4000.0)
    
    telemetry = {
        "battery_soc_pct": bat_soc,
        "battery_voltage_v": bat_vol,
        "reaction_wheel_speed_rpm": rw_speed
    }
    
    if st.button("Run Diagnostics"):
        report = pd_engine.analyse(telemetry)
        if report.anomaly_detected:
            st.error(f"Anomaly Detected! Type: {report.anomaly_type}")
            st.write(f"**Confidence:** {report.confidence:.2%}")
            st.write(f"**Description:** {report.description}")
            st.write(f"**Recommendation:** `{report.recommended_action}`")
        else:
            st.success("Telemetry Nominal. No anomalies detected.")

with col2:
    st.header("2. PPO Fault Recovery")
    st.markdown("CBF-Gated PPO Controller")
    
    sys_state = RecoveryState(
        battery_soc=0.4,
        rw_health=0.9,
        thruster_health=1.0,
        sensor_health=1.0,
        power_margin_w=100.0,
        thermal_margin_c=10.0,
        link_margin_db=5.0,
        fault_type_id=1
    )
    
    st.json(sys_state.__dict__)
    
    if st.button("Generate Recovery Action"):
        action = ppo_recovery.select_action("battery_degradation", 0.85, sys_state)
        st.info(f"**Selected Action:** {action.action_name}")
        st.write(f"**Expected Recovery Time:** {action.expected_recovery_time_s}s")
        st.write(f"**Estimated Fuel Cost:** {action.estimated_fuel_cost_kg}kg")
        st.write(f"**Degraded Mode:** {action.degraded_mode}")
        if not action.cbf_safe:
            st.warning("⚠️ Action was modified by the CBF Safety Gate to preserve system integrity.")

st.header("3. Multi-Fault Handler")
st.markdown("Simultaneous Fault Conflict Resolution")

if st.button("Resolve Conflicts"):
    mf_handler.register_fault(FaultType.BATTERY, 0.8, ["EPS"], "F1")
    mf_handler.register_fault(FaultType.REACTION_WHEEL, 0.6, ["ADCS"], "F2")
    mf_handler.register_fault(FaultType.THERMAL, 0.9, ["TCS"], "F3")
    
    report = mf_handler.generate_recovery_plan()
    
    st.write("Current Active Faults:")
    st.table(pd.DataFrame([f.__dict__ for f in report.active_faults]))

    st.success("Conflicts Resolved. Prioritized Execution Plan:")
    
    for r in report.combined_recovery_plan:
        with st.expander(f"{r['fault_id']} ({r['fault_type']})"):
            st.write(f"**Action:** {r['action']}")
            st.write(f"**Priority:** {r['priority']}")
            if 'conflict_resolved' in r:
                st.warning("⚠️ Action modified to resolve subsystem conflict.")
