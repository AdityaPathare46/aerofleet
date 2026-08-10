import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import sys
import os
import time

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from aerofleet.event_bus.async_bus import AsyncEventBus, Event
from aerofleet.event_bus.telemetry_stream import TelemetryStream

st.set_page_config(page_title="Mission Replay & Event Bus", layout="wide", page_icon="⏪")

st.title("⏪ Mission Replay & Event Bus")
st.markdown("Inspect the asynchronous event logs and replay historical telemetry streams")

@st.cache_resource
def get_event_modules():
    event_bus = AsyncEventBus()
    telemetry = TelemetryStream("SC-ALPHA", expected_rate_hz=1.0)
    
    # Pre-populate with some dummy events
    event_bus.publish(Event("EVT-001", "MISSION_PHASE_CHANGE", "ORBITAL_MECHANICS_AGENT", {"old": "PRE_LAUNCH", "new": "LAUNCH"}, priority=1))
    event_bus.publish(Event("EVT-002", "TELEMETRY_ANOMALY", "FAULT_TOLERANCE_AGENT", {"subsystem": "EPS", "confidence": 0.9}, priority=3))
    event_bus.publish(Event("EVT-003", "CONJUNCTION_WARNING", "SSA_AGENT", {"object": "DEBRIS-X", "pc": 1e-3}, priority=3))
    event_bus.publish(Event("EVT-004", "MANEUVER_APPROVED", "COUNCIL", {"dv_ms": 15.0}, priority=2))
    
    # Pre-populate telemetry
    for i in range(60):
        telemetry.ingest({
            "battery_soc_pct": max(10.0, 100.0 - i * 1.5),
            "altitude_km": 600.0 - np.sin(i / 10.0) * 10,
            "reaction_wheel_rpm": 3000 + np.random.normal(0, 50)
        })
        
    return event_bus, telemetry

event_bus, telemetry = get_event_modules()

col1, col2 = st.columns(2)

with col1:
    st.header("1. Async Event Bus Log")
    
    event_type_filter = st.selectbox("Filter by Event Type", ["ALL", "MISSION_PHASE_CHANGE", "TELEMETRY_ANOMALY", "CONJUNCTION_WARNING", "MANEUVER_APPROVED"])
    
    events = event_bus.get_events()
    if event_type_filter != "ALL":
        events = [e for e in events if e.event_type == event_type_filter]
        
    if events:
        event_data = []
        for e in reversed(events):
            event_data.append({
                "Event ID": e.event_id,
                "Type": e.event_type,
                "Source": e.source,
                "Priority": e.priority,
                "Payload": str(e.payload)
            })
        st.dataframe(pd.DataFrame(event_data), use_container_width=True)
    else:
        st.info("No events match the filter.")

with col2:
    st.header("2. Telemetry Stream History")
    
    frames = telemetry.get_latest(60)
    if frames:
        st.write(f"Showing last {len(frames)} frames for {telemetry.spacecraft_id}")
        
        # Plot Battery SOC
        soc_history = telemetry.get_field_history("battery_soc_pct", 60)
        if soc_history:
            fig = px.line(y=soc_history, title="Battery SOC (%) over time", labels={'x': 'Time Step', 'y': 'SOC (%)'})
            st.plotly_chart(fig, use_container_width=True)
            
        # Plot Altitude
        alt_history = telemetry.get_field_history("altitude_km", 60)
        if alt_history:
            fig2 = px.line(y=alt_history, title="Altitude (km) over time", labels={'x': 'Time Step', 'y': 'Altitude (km)'})
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No telemetry data available.")
