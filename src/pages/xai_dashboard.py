import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from aerofleet.fault_tolerance.xai_fault_analysis import XAIFaultAnalyzer
from aerofleet.fault_tolerance.predictive_diagnostics import PredictiveDiagnostics
from aerofleet.explainability.decision_trace import DecisionTraceGraph

st.set_page_config(page_title="Explainable AI (XAI) & Decision Trace", layout="wide", page_icon="🧠")

st.title("🧠 Explainable AI (XAI) & Decision Trace")
st.markdown("LIME Explainability for Fault Detection and Full Agent Decision Graph")

@st.cache_resource
def get_xai_modules():
    xai_analyzer = XAIFaultAnalyzer(n_samples=100)
    pd_engine = PredictiveDiagnostics()
    trace_graph = DecisionTraceGraph()
    return xai_analyzer, pd_engine, trace_graph

xai_analyzer, pd_engine, trace_graph = get_xai_modules()

col1, col2 = st.columns(2)

with col1:
    st.header("1. LIME Fault Explanation")
    st.markdown("Understanding *why* the Predictive Diagnostics engine triggered an anomaly.")
    
    telemetry = {
        "battery_soc_pct": 10.0,
        "battery_voltage_v": 19.5,
        "reaction_wheel_speed_rpm": 4200.0,
        "solar_panel_current_a": 1.2
    }
    
    st.write("Input Telemetry:")
    st.json(telemetry)
    
    if st.button("Generate XAI Report"):
        with st.spinner("Running LIME pertubations..."):
            explanation = xai_analyzer.explain(
                telemetry, 
                pd_engine._rf.predict, 
                "battery_degradation", 
                0.92
            )
            
            st.subheader("Human Summary")
            st.info(explanation.human_summary)
            
            st.subheader("Feature Importances")
            
            features = list(explanation.feature_importances.keys())
            weights = list(explanation.feature_importances.values())
            
            fig = go.Figure(go.Bar(
                x=weights,
                y=features,
                orientation='h',
                marker_color=['red' if w > 0 else 'blue' for w in weights]
            ))
            fig.update_layout(title="LIME Feature Contributions", xaxis_title="Weight", yaxis_title="Feature")
            st.plotly_chart(fig, use_container_width=True)

with col2:
    st.header("2. Decision Trace Graph")
    st.markdown("Visualising the 17-Agent Council's consensus loop and CBF Safety Gate.")
    
    if st.button("Generate Sample Decision Trace"):
        trace_id = trace_graph.new_trace("Debris conjunction imminent (Pc=1e-3). Maneuver required.")
        
        trace_graph.add_agent_vote("Orbital Dynamics Agent", "APPROVE", 0.95, "Calculated 15m/s normal maneuver.", round_number=1)
        trace_graph.add_agent_vote("Fuel Agent", "APPROVE", 0.88, "Fuel reserves sufficient for maneuver.", round_number=1)
        trace_graph.add_agent_vote("Safety Agent", "REJECT", 0.9, "Proposed maneuver violates safety distance to Sat-X.", round_number=1)
        
        trace_graph.add_agent_vote("Orbital Dynamics Agent", "APPROVE", 0.95, "Revised maneuver: 5m/s along-track.", round_number=2)
        trace_graph.add_agent_vote("Safety Agent", "APPROVE", 0.95, "Revised maneuver is safe.", round_number=2)
        
        trace_graph.add_cbf_result(True, [])
        trace = trace_graph.finalise("MANEUVER_APPROVED", 0.92)
        
        st.success(f"Trace Generated: {trace.graph_id}")
        
        # Visualize as a table/list for simplicity in Streamlit
        st.subheader("Trace Nodes")
        for node in trace.nodes:
            with st.expander(f"{node.step_type} - {node.agent_name or 'System'} (Conf: {node.confidence:.2f})"):
                st.write(node.content)
                
        st.subheader("Final Verdict")
        st.write(f"**Verdict:** {trace.final_verdict}")
        st.write(f"**Overall Confidence:** {trace.overall_confidence:.2%}")
        st.write(f"**CBF Passed:** {trace.cbf_passed}")
        
        with st.expander("Raw JSON Export"):
            st.json(json.loads(trace_graph.export_json()))
